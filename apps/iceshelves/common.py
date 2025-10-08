"""
IceShelves Common Utilities

Shared utilities, LXD client wrappers, and helper functions for the IceShelves application.
Supports three connection methods:
- direct-api: Direct connection to LXD API
- ssh: SSH tunnel to LXD socket
- agent-poll: Polling agent installed on hypervisor
"""

import os
import sys
import json
import yaml
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import secrets

# Add shared modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    import pylxd
    from pylxd.models import Instance
    from pylxd.exceptions import LXDAPIException, NotFound
    PYLXD_AVAILABLE = True
except ImportError:
    PYLXD_AVAILABLE = False
    logging.warning("pylxd not available - LXD functionality will be limited")

try:
    import libvirt
    LIBVIRT_AVAILABLE = True
except ImportError:
    LIBVIRT_AVAILABLE = False
    logging.warning("libvirt not available - KVM functionality will be disabled")

from jinja2 import Template, Environment, FileSystemLoader, TemplateError

import settings
from models import db

logger = logging.getLogger(__name__)


# ============================================================================
# EXCEPTIONS
# ============================================================================

class IceShelvesError(Exception):
    """Base exception for IceShelves errors."""
    pass


class ConnectionError(IceShelvesError):
    """Raised when connection to cluster fails."""
    pass


class DeploymentError(IceShelvesError):
    """Raised when deployment fails."""
    pass


class ValidationError(IceShelvesError):
    """Raised when validation fails."""
    pass


class AgentError(IceShelvesError):
    """Raised when agent operations fail."""
    pass


# ============================================================================
# LXD CLIENT WRAPPER
# ============================================================================

class LXDClient:
    """
    Wrapper for LXD client supporting multiple connection methods.

    Connection Methods:
    - direct-api: Direct connection to LXD API endpoint
    - ssh: SSH tunnel to LXD unix socket
    - agent-poll: Not used directly (agent fetches deployments)
    """

    def __init__(self, cluster_record: Any):
        """
        Initialize LXD client from cluster database record.

        Args:
            cluster_record: Database record from deployment_targets table
        """
        self.cluster = cluster_record
        self.client = None
        self.connection_method = cluster_record.connection_method

        if not PYLXD_AVAILABLE:
            raise ConnectionError("pylxd library not available")

    def connect(self) -> bool:
        """
        Establish connection to LXD based on connection method.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            if self.connection_method == 'direct-api':
                self._connect_direct_api()
            elif self.connection_method == 'ssh':
                self._connect_ssh()
            elif self.connection_method == 'agent-poll':
                # Agent-based deployments don't use direct connections
                raise ConnectionError("Agent-poll method does not support direct connections")
            else:
                raise ConnectionError(f"Unknown connection method: {self.connection_method}")

            return True
        except Exception as e:
            logger.error(f"Failed to connect to cluster {self.cluster.name}: {e}")
            return False

    def _connect_direct_api(self):
        """Connect using direct LXD API."""
        endpoint = self.cluster.endpoint_url

        if self.cluster.auth_type == 'certificate' and self.cluster.client_cert and self.cluster.client_key:
            # Use certificate authentication
            cert = (self.cluster.client_cert, self.cluster.client_key)
            self.client = pylxd.Client(
                endpoint=endpoint,
                cert=cert,
                verify=self.cluster.verify_ssl
            )
        else:
            # Trust password or unauthenticated
            self.client = pylxd.Client(
                endpoint=endpoint,
                verify=self.cluster.verify_ssl
            )

    def _connect_ssh(self):
        """Connect using SSH tunnel to LXD unix socket."""
        # Create temporary SSH config for tunneling
        ssh_host = self.cluster.ssh_host
        ssh_port = self.cluster.ssh_port or 22
        ssh_user = self.cluster.ssh_user

        # Use paramiko or create SSH tunnel
        # For now, we'll use the pylxd SSH endpoint feature
        endpoint = f"ssh://{ssh_user}@{ssh_host}:{ssh_port}"

        self.client = pylxd.Client(endpoint=endpoint)

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection to LXD cluster.

        Returns:
            Tuple of (success, message)
        """
        try:
            if not self.client:
                if not self.connect():
                    return False, "Failed to establish connection"

            # Try to get server info
            info = self.client.api.get().json()
            return True, f"Connected successfully to LXD {info.get('metadata', {}).get('environment', {}).get('server_version', 'unknown')}"
        except Exception as e:
            return False, str(e)

    def get_cluster_members(self) -> List[Dict]:
        """Get list of cluster members if this is a cluster."""
        if not self.cluster.is_cluster:
            return []

        try:
            members = self.client.cluster.members.all()
            return [
                {
                    'name': m.server_name,
                    'url': m.url,
                    'database': m.database,
                    'status': m.status,
                    'message': m.message,
                }
                for m in members
            ]
        except Exception as e:
            logger.error(f"Failed to get cluster members: {e}")
            return []

    def create_instance(
        self,
        name: str,
        source: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        profiles: Optional[List[str]] = None,
        target: Optional[str] = None,
        wait: bool = True
    ) -> Optional[Instance]:
        """
        Create a new LXD instance.

        Args:
            name: Instance name
            source: Source configuration (image, etc.)
            config: Instance configuration
            profiles: List of profiles to apply
            target: Target cluster member (if cluster)
            wait: Wait for instance to be created

        Returns:
            Instance object if successful, None otherwise
        """
        try:
            instance_config = {
                'name': name,
                'source': source,
                'config': config or {},
                'profiles': profiles or ['default'],
            }

            if target and self.cluster.is_cluster:
                instance = self.client.instances.create(instance_config, wait=wait, target=target)
            else:
                instance = self.client.instances.create(instance_config, wait=wait)

            return instance
        except LXDAPIException as e:
            logger.error(f"Failed to create instance {name}: {e}")
            raise DeploymentError(f"LXD API error: {e}")

    def get_instance(self, name: str) -> Optional[Instance]:
        """Get instance by name."""
        try:
            return self.client.instances.get(name)
        except NotFound:
            return None
        except Exception as e:
            logger.error(f"Error getting instance {name}: {e}")
            return None

    def delete_instance(self, name: str, force: bool = False) -> bool:
        """Delete instance by name."""
        try:
            instance = self.get_instance(name)
            if instance:
                if instance.status == 'Running' and force:
                    instance.stop(wait=True, force=True)
                instance.delete(wait=True)
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting instance {name}: {e}")
            return False


# ============================================================================
# AWS EC2 CLIENT
# ============================================================================

class AWSEC2Client:
    """
    AWS EC2 client for deploying instances with cloud-init.

    Uses boto3 to launch EC2 instances with cloud-init user-data.
    """

    def __init__(self, target_record: Any, secrets_manager=None):
        """
        Initialize AWS EC2 client from deployment target record.

        Args:
            target_record: Database record from deployment_targets table
            secrets_manager: SecretsManager instance for retrieving credentials
        """
        self.target = target_record
        self.secrets_manager = secrets_manager
        self.client = None
        self.ec2_resource = None

        try:
            import boto3
            from botocore.exceptions import ClientError, BotoCoreError

            self.boto3 = boto3
            self.ClientError = ClientError
            self.BotoCoreError = BotoCoreError

        except ImportError:
            raise ConnectionError("boto3 library not available")

        # Get cloud configuration
        self.cloud_config = target_record.cloud_config or {}
        self.region = self.cloud_config.get('region', os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))

    def connect(self) -> bool:
        """
        Establish connection to AWS EC2.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Check for credentials in cloud_config or environment
            aws_access_key = self.cloud_config.get('aws_access_key_id')
            aws_secret_key = self.cloud_config.get('aws_secret_access_key')

            if aws_access_key and aws_secret_key:
                # Use explicit credentials
                self.client = self.boto3.client(
                    'ec2',
                    region_name=self.region,
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key
                )
                self.ec2_resource = self.boto3.resource(
                    'ec2',
                    region_name=self.region,
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key
                )
            else:
                # Use IAM role or environment credentials
                self.client = self.boto3.client('ec2', region_name=self.region)
                self.ec2_resource = self.boto3.resource('ec2', region_name=self.region)

            return True

        except Exception as e:
            logger.error(f"Failed to connect to AWS EC2: {e}")
            return False

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection to AWS EC2.

        Returns:
            Tuple of (success, message)
        """
        try:
            if not self.client:
                if not self.connect():
                    return False, "Failed to establish connection"

            # Try to describe regions to test credentials
            response = self.client.describe_regions()
            return True, f"Connected successfully to AWS EC2 in region {self.region}"

        except Exception as e:
            return False, str(e)

    def launch_instance(
        self,
        name: str,
        ami: str,
        instance_type: str,
        user_data: str,
        security_groups: Optional[List[str]] = None,
        subnet_id: Optional[str] = None,
        key_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        wait: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Launch an EC2 instance with cloud-init user-data.

        Args:
            name: Instance name (set as Name tag)
            ami: AMI ID (e.g., ami-xxxxx for Ubuntu 24.04)
            instance_type: Instance type (e.g., t3.micro, t3.small)
            user_data: Cloud-init user-data script
            security_groups: List of security group IDs
            subnet_id: Subnet ID for VPC
            key_name: SSH key pair name
            tags: Additional tags for the instance
            wait: Wait for instance to be running

        Returns:
            Instance information dict if successful, None otherwise
        """
        try:
            # Build launch parameters
            launch_params = {
                'ImageId': ami,
                'InstanceType': instance_type,
                'UserData': user_data,
                'MinCount': 1,
                'MaxCount': 1,
                'TagSpecifications': [
                    {
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': name},
                            {'Key': 'ManagedBy', 'Value': 'IceShelves'}
                        ]
                    }
                ]
            }

            # Add optional parameters
            if security_groups:
                launch_params['SecurityGroupIds'] = security_groups

            if subnet_id:
                launch_params['SubnetId'] = subnet_id

            if key_name:
                launch_params['KeyName'] = key_name

            # Add additional tags
            if tags:
                for key, value in tags.items():
                    launch_params['TagSpecifications'][0]['Tags'].append({'Key': key, 'Value': value})

            # Launch instance
            response = self.client.run_instances(**launch_params)

            instance_id = response['Instances'][0]['InstanceId']
            logger.info(f"Launched EC2 instance {instance_id} ({name})")

            # Wait for instance to be running if requested
            if wait:
                logger.info(f"Waiting for instance {instance_id} to be running...")
                waiter = self.client.get_waiter('instance_running')
                waiter.wait(InstanceIds=[instance_id])

            # Get full instance details
            instance = self.get_instance(instance_id)

            return instance

        except (self.ClientError, self.BotoCoreError) as e:
            logger.error(f"Failed to launch EC2 instance {name}: {e}")
            raise DeploymentError(f"AWS EC2 error: {e}")

    def get_instance(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """
        Get instance details by ID.

        Args:
            instance_id: EC2 instance ID

        Returns:
            Instance information dict or None
        """
        try:
            response = self.client.describe_instances(InstanceIds=[instance_id])

            if response['Reservations']:
                instance_data = response['Reservations'][0]['Instances'][0]

                # Parse into consistent format
                return {
                    'instance_id': instance_data['InstanceId'],
                    'name': next((tag['Value'] for tag in instance_data.get('Tags', []) if tag['Key'] == 'Name'), None),
                    'state': instance_data['State']['Name'],
                    'instance_type': instance_data['InstanceType'],
                    'public_ip': instance_data.get('PublicIpAddress'),
                    'private_ip': instance_data.get('PrivateIpAddress'),
                    'launch_time': instance_data['LaunchTime'].isoformat() if instance_data.get('LaunchTime') else None,
                    'availability_zone': instance_data['Placement']['AvailabilityZone'],
                    'architecture': instance_data.get('Architecture'),
                }

            return None

        except Exception as e:
            logger.error(f"Error getting EC2 instance {instance_id}: {e}")
            return None

    def terminate_instance(self, instance_id: str, wait: bool = True) -> bool:
        """
        Terminate an EC2 instance.

        Args:
            instance_id: EC2 instance ID
            wait: Wait for termination to complete

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.terminate_instances(InstanceIds=[instance_id])
            logger.info(f"Terminated EC2 instance {instance_id}")

            if wait:
                waiter = self.client.get_waiter('instance_terminated')
                waiter.wait(InstanceIds=[instance_id])

            return True

        except Exception as e:
            logger.error(f"Error terminating EC2 instance {instance_id}: {e}")
            return False


# ============================================================================
# GCP COMPUTE ENGINE CLIENT
# ============================================================================

class GCPComputeClient:
    """
    GCP Compute Engine client for deploying instances with cloud-init.

    Uses google-cloud-compute to create VM instances with startup scripts.
    """

    def __init__(self, target_record: Any, secrets_manager=None):
        """
        Initialize GCP Compute Engine client from deployment target record.

        Args:
            target_record: Database record from deployment_targets table
            secrets_manager: SecretsManager instance for retrieving credentials
        """
        self.target = target_record
        self.secrets_manager = secrets_manager
        self.client = None

        try:
            from google.cloud import compute_v1

            self.compute_v1 = compute_v1

        except ImportError:
            raise ConnectionError("google-cloud-compute library not available")

        # Get cloud configuration
        self.cloud_config = target_record.cloud_config or {}
        self.project_id = self.cloud_config.get('project_id', os.getenv('GCP_PROJECT_ID'))
        self.zone = self.cloud_config.get('zone', 'us-central1-a')

        if not self.project_id:
            raise ValueError("GCP project_id is required")

    def connect(self) -> bool:
        """
        Establish connection to GCP Compute Engine.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Initialize Compute Engine client
            # Uses Application Default Credentials or GOOGLE_APPLICATION_CREDENTIALS env var
            self.client = self.compute_v1.InstancesClient()

            return True

        except Exception as e:
            logger.error(f"Failed to connect to GCP Compute Engine: {e}")
            return False

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection to GCP Compute Engine.

        Returns:
            Tuple of (success, message)
        """
        try:
            if not self.client:
                if not self.connect():
                    return False, "Failed to establish connection"

            # Try to list instances to test credentials
            request = self.compute_v1.ListInstancesRequest(
                project=self.project_id,
                zone=self.zone
            )
            _ = self.client.list(request=request)

            return True, f"Connected successfully to GCP Compute Engine in project {self.project_id}"

        except Exception as e:
            return False, str(e)

    def create_instance(
        self,
        name: str,
        machine_type: str,
        image_project: str,
        image_family: str,
        startup_script: str,
        network: str = 'default',
        tags: Optional[List[str]] = None,
        labels: Optional[Dict[str, str]] = None,
        wait: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Create a GCP VM instance with cloud-init startup script.

        Args:
            name: Instance name
            machine_type: Machine type (e.g., e2-micro, e2-small)
            image_project: Project containing the image (e.g., ubuntu-os-cloud)
            image_family: Image family (e.g., ubuntu-2404-lts)
            startup_script: Cloud-init startup script
            network: VPC network name
            tags: Network tags for firewall rules
            labels: Instance labels
            wait: Wait for instance to be created

        Returns:
            Instance information dict if successful, None otherwise
        """
        try:
            # Get image
            image_client = self.compute_v1.ImagesClient()
            image = image_client.get_from_family(project=image_project, family=image_family)

            # Build machine type URL
            machine_type_url = f"zones/{self.zone}/machineTypes/{machine_type}"

            # Build network interface
            network_interface = self.compute_v1.NetworkInterface(
                name=network,
                access_configs=[
                    self.compute_v1.AccessConfig(
                        name="External NAT",
                        type_="ONE_TO_ONE_NAT"
                    )
                ]
            )

            # Build metadata with startup script (cloud-init)
            metadata_items = [
                self.compute_v1.Items(key="startup-script", value=startup_script),
                self.compute_v1.Items(key="enable-oslogin", value="TRUE")
            ]

            # Build instance configuration
            instance = self.compute_v1.Instance(
                name=name,
                machine_type=machine_type_url,
                disks=[
                    self.compute_v1.AttachedDisk(
                        boot=True,
                        auto_delete=True,
                        initialize_params=self.compute_v1.AttachedDiskInitializeParams(
                            source_image=image.self_link,
                            disk_size_gb=10
                        )
                    )
                ],
                network_interfaces=[network_interface],
                metadata=self.compute_v1.Metadata(items=metadata_items),
                tags=self.compute_v1.Tags(items=tags or []),
                labels=labels or {'managed-by': 'iceshelves'}
            )

            # Create instance
            request = self.compute_v1.InsertInstanceRequest(
                project=self.project_id,
                zone=self.zone,
                instance_resource=instance
            )

            operation = self.client.insert(request=request)

            logger.info(f"Launched GCP instance {name}")

            # Wait for operation to complete if requested
            if wait:
                logger.info(f"Waiting for instance {name} to be created...")
                operation_client = self.compute_v1.ZoneOperationsClient()
                while True:
                    result = operation_client.get(
                        project=self.project_id,
                        zone=self.zone,
                        operation=operation.name
                    )
                    if result.status == self.compute_v1.Operation.Status.DONE:
                        if result.error:
                            raise DeploymentError(f"Instance creation failed: {result.error}")
                        break

            # Get full instance details
            instance_info = self.get_instance(name)

            return instance_info

        except Exception as e:
            logger.error(f"Failed to create GCP instance {name}: {e}")
            raise DeploymentError(f"GCP Compute Engine error: {e}")

    def get_instance(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get instance details by name.

        Args:
            name: Instance name

        Returns:
            Instance information dict or None
        """
        try:
            request = self.compute_v1.GetInstanceRequest(
                project=self.project_id,
                zone=self.zone,
                instance=name
            )

            instance = self.client.get(request=request)

            # Parse network interfaces for IPs
            network_interface = instance.network_interfaces[0] if instance.network_interfaces else None
            external_ip = None
            internal_ip = None

            if network_interface:
                internal_ip = network_interface.network_i_p
                if network_interface.access_configs:
                    external_ip = network_interface.access_configs[0].nat_i_p

            return {
                'name': instance.name,
                'instance_id': str(instance.id),
                'status': instance.status,
                'machine_type': instance.machine_type.split('/')[-1],
                'zone': instance.zone.split('/')[-1],
                'internal_ip': internal_ip,
                'external_ip': external_ip,
                'creation_timestamp': instance.creation_timestamp,
                'labels': dict(instance.labels) if instance.labels else {}
            }

        except Exception as e:
            logger.error(f"Error getting GCP instance {name}: {e}")
            return None

    def delete_instance(self, name: str, wait: bool = True) -> bool:
        """
        Delete a GCP VM instance.

        Args:
            name: Instance name
            wait: Wait for deletion to complete

        Returns:
            True if successful, False otherwise
        """
        try:
            request = self.compute_v1.DeleteInstanceRequest(
                project=self.project_id,
                zone=self.zone,
                instance=name
            )

            operation = self.client.delete(request=request)

            logger.info(f"Deleted GCP instance {name}")

            if wait:
                operation_client = self.compute_v1.ZoneOperationsClient()
                while True:
                    result = operation_client.get(
                        project=self.project_id,
                        zone=self.zone,
                        operation=operation.name
                    )
                    if result.status == self.compute_v1.Operation.Status.DONE:
                        break

            return True

        except Exception as e:
            logger.error(f"Error deleting GCP instance {name}: {e}")
            return False


# ============================================================================
# CLOUD-INIT UTILITIES
# ============================================================================

def validate_cloud_init(cloud_init_yaml: str) -> Tuple[bool, str, Optional[Dict]]:
    """
    Validate cloud-init YAML.

    Args:
        cloud_init_yaml: Cloud-init YAML content

    Returns:
        Tuple of (is_valid, error_message, parsed_data)
    """
    try:
        data = yaml.safe_load(cloud_init_yaml)

        # Basic validation
        if not isinstance(data, dict):
            return False, "Cloud-init must be a YAML dictionary", None

        # Check for common cloud-init keys
        valid_keys = {'#cloud-config', 'users', 'packages', 'runcmd', 'write_files',
                      'ssh_authorized_keys', 'timezone', 'locale', 'bootcmd', 'apt'}

        return True, "Valid cloud-init YAML", data
    except yaml.YAMLError as e:
        return False, f"Invalid YAML: {e}", None
    except Exception as e:
        return False, f"Validation error: {e}", None


def render_cloud_init_template(template_str: str, variables: Dict[str, Any]) -> str:
    """
    Render cloud-init template with variables using Jinja2.

    Args:
        template_str: Jinja2 template string
        variables: Template variables

    Returns:
        Rendered cloud-init YAML
    """
    try:
        template = Template(template_str)
        return template.render(**variables)
    except TemplateError as e:
        raise ValidationError(f"Template rendering error: {e}")


def merge_cloud_init(base: str, overrides: Dict[str, Any]) -> str:
    """
    Merge cloud-init overrides into base configuration.

    Args:
        base: Base cloud-init YAML string
        overrides: Dictionary of overrides to merge

    Returns:
        Merged cloud-init YAML string
    """
    base_data = yaml.safe_load(base)

    # Deep merge function
    def deep_merge(dict1, dict2):
        result = dict1.copy()
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    merged = deep_merge(base_data, overrides)
    return yaml.dump(merged, default_flow_style=False)


# ============================================================================
# EGG MANAGEMENT
# ============================================================================

def get_egg_path(egg_name: str) -> Path:
    """Get the filesystem path for an egg."""
    return settings.EGGS_STORAGE_PATH / egg_name


def load_egg_files(egg_record: Any) -> Dict[str, Any]:
    """
    Load all files associated with an egg.

    Args:
        egg_record: Database record from eggs table

    Returns:
        Dictionary with loaded file contents
    """
    egg_path = get_egg_path(egg_record.name)
    result = {
        'cloud_init': None,
        'lxd_profile': None,
        'kvm_config': None,
        'readme': None,
    }

    # Load cloud-init
    if egg_record.cloud_init_path:
        cloud_init_file = egg_path / egg_record.cloud_init_path
        if cloud_init_file.exists():
            result['cloud_init'] = cloud_init_file.read_text()

    # Load LXD profile
    if egg_record.lxd_profile_path:
        profile_file = egg_path / egg_record.lxd_profile_path
        if profile_file.exists():
            result['lxd_profile'] = profile_file.read_text()

    # Load KVM config
    if egg_record.kvm_config_path:
        kvm_file = egg_path / egg_record.kvm_config_path
        if kvm_file.exists():
            result['kvm_config'] = kvm_file.read_text()

    # Load README
    readme_file = egg_path / "README.md"
    if readme_file.exists():
        result['readme'] = readme_file.read_text()

    return result


def create_egg_skeleton(
    egg_name: str,
    template_record: Any,
    variables: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Create a new egg from a skeleton template.

    Args:
        egg_name: Name for the new egg
        template_record: Database record from egg_templates table
        variables: Variables for template rendering

    Returns:
        Tuple of (success, message)
    """
    try:
        egg_path = get_egg_path(egg_name)

        # Check if egg already exists
        if egg_path.exists():
            return False, f"Egg '{egg_name}' already exists"

        # Create egg directory
        egg_path.mkdir(parents=True, exist_ok=True)

        # Render and save cloud-init
        if template_record.cloud_init_template:
            cloud_init = render_cloud_init_template(template_record.cloud_init_template, variables)
            (egg_path / "cloud-init.yaml").write_text(cloud_init)

        # Render and save LXD profile
        if template_record.lxd_profile_template:
            profile = render_cloud_init_template(template_record.lxd_profile_template, variables)
            (egg_path / "lxd-profile.yaml").write_text(profile)

        # Render and save KVM config
        if template_record.kvm_config_template:
            kvm_config = render_cloud_init_template(template_record.kvm_config_template, variables)
            (egg_path / "kvm-config.xml").write_text(kvm_config)

        # Create README
        readme_content = f"""# {egg_name}

## Description
{variables.get('description', 'Generated from template: ' + template_record.name)}

## Template
Generated from template: **{template_record.display_name}**

## Variables Used
```json
{json.dumps(variables, indent=2)}
```

## Files
- `cloud-init.yaml`: Cloud-init configuration
- `lxd-profile.yaml`: LXD profile (if applicable)
- `kvm-config.xml`: KVM libvirt configuration (if applicable)
- `metadata.json`: Egg metadata

## Usage
Deploy this egg using the IceShelves web interface or API.
"""
        (egg_path / "README.md").write_text(readme_content)

        # Create metadata.json
        metadata = {
            'name': egg_name,
            'version': variables.get('version', '1.0.0'),
            'template': template_record.name,
            'created': datetime.utcnow().isoformat(),
            'variables': variables,
        }
        (egg_path / "metadata.json").write_text(json.dumps(metadata, indent=2))

        return True, f"Egg '{egg_name}' created successfully"
    except Exception as e:
        logger.error(f"Failed to create egg skeleton: {e}")
        return False, str(e)


# ============================================================================
# AGENT UTILITIES
# ============================================================================

def generate_agent_key() -> str:
    """Generate a secure random key for agent authentication."""
    return secrets.token_urlsafe(32)


def verify_agent_key(cluster_id: int, provided_key: str) -> bool:
    """
    Verify agent authentication key.

    Args:
        cluster_id: Cluster ID
        provided_key: Key provided by agent

    Returns:
        True if key is valid, False otherwise
    """
    cluster = db.deployment_targets[cluster_id]
    if not cluster:
        return False

    if cluster.connection_method != 'agent-poll':
        return False

    return cluster.agent_key == provided_key


def get_pending_deployments_for_agent(cluster_id: int) -> List[Dict[str, Any]]:
    """
    Get pending deployments for an agent.

    Args:
        cluster_id: Cluster ID

    Returns:
        List of deployment records ready for agent
    """
    deployments = db(
        (db.deployments.target_id == cluster_id) &
        (db.deployments.status == 'pending')
    ).select()

    result = []
    for deployment in deployments:
        egg = db.eggs[deployment.egg_id]
        if not egg:
            continue

        # Load egg files
        files = load_egg_files(egg)

        result.append({
            'deployment_id': deployment.id,
            'egg_name': egg.name,
            'instance_name': deployment.instance_name,
            'deployment_type': deployment.deployment_type,
            'cloud_init': files['cloud_init'],
            'lxd_profile': files['lxd_profile'],
            'config_overrides': deployment.config_overrides or {},
            'target_member': deployment.target_member,
        })

    return result


def update_agent_last_seen(cluster_id: int):
    """Update the last seen timestamp for an agent."""
    cluster = db.deployment_targets[cluster_id]
    if cluster and cluster.connection_method == 'agent-poll':
        cluster.update_record(agent_last_seen=datetime.utcnow())
        db.commit()


# ============================================================================
# DEPLOYMENT UTILITIES
# ============================================================================

def log_deployment(deployment_id: int, level: str, message: str, details: Optional[Dict] = None):
    """
    Log a deployment event.

    Args:
        deployment_id: Deployment ID
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        message: Log message
        details: Optional structured details
    """
    db.deployment_logs.insert(
        deployment_id=deployment_id,
        log_level=level,
        message=message,
        details=details,
        timestamp=datetime.utcnow()
    )
    db.commit()


def update_deployment_status(
    deployment_id: int,
    status: str,
    error_message: Optional[str] = None,
    instance_info: Optional[Dict] = None
):
    """
    Update deployment status.

    Args:
        deployment_id: Deployment ID
        status: New status
        error_message: Error message if failed
        instance_info: Instance information if successful
    """
    update_data = {'status': status, 'updated_on': datetime.utcnow()}

    if status == 'in_progress' and not db.deployments[deployment_id].started_at:
        update_data['started_at'] = datetime.utcnow()

    if status in ['completed', 'failed', 'cancelled', 'timeout']:
        update_data['completed_at'] = datetime.utcnow()

    if error_message:
        update_data['error_message'] = error_message

    if instance_info:
        update_data['instance_info'] = instance_info

    db.deployments[deployment_id] = update_data
    db.commit()


# ============================================================================
# ASYNC CLOUD HELPERS WITH DATACLASSES (Python 3.12+)
# ============================================================================

import asyncio
from dataclasses import dataclass, field
from typing import ClassVar
from concurrent.futures import ThreadPoolExecutor

# Thread pool for async operations
_executor = ThreadPoolExecutor(max_workers=10)


@dataclass
class AWSCredentials:
    """AWS credential data structure."""
    access_key_id: str
    secret_access_key: str
    region: str = 'us-east-1'
    session_token: Optional[str] = None


@dataclass
class GCPCredentials:
    """GCP credential data structure."""
    project_id: str
    service_account_json: str
    zone: str = 'us-central1-a'


@dataclass
class AWSRegion:
    """AWS region information."""
    name: str
    endpoint: str
    opt_in_status: str


@dataclass
class AWSVPC:
    """AWS VPC information."""
    vpc_id: str
    cidr_block: str
    is_default: bool
    state: str
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class AWSSubnet:
    """AWS subnet information."""
    subnet_id: str
    vpc_id: str
    cidr_block: str
    availability_zone: str
    available_ip_address_count: int
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class AWSSecurityGroup:
    """AWS security group information."""
    group_id: str
    group_name: str
    description: str
    vpc_id: str
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class AWSAMI:
    """AWS AMI information."""
    ami_id: str
    name: str
    description: str
    architecture: str
    root_device_type: str
    virtualization_type: str
    creation_date: str


@dataclass
class GCPNetwork:
    """GCP network information."""
    name: str
    self_link: str
    auto_create_subnetworks: bool
    routing_mode: str


@dataclass
class GCPMachineType:
    """GCP machine type information."""
    name: str
    guest_cpus: int
    memory_mb: int
    zone: str
    description: str


@dataclass
class GCPImage:
    """GCP image information."""
    name: str
    self_link: str
    family: str
    description: str
    creation_timestamp: str


@dataclass
class CredentialValidationResult:
    """Result of credential validation."""
    valid: bool
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)


async def validate_aws_credentials_async(credentials: AWSCredentials) -> CredentialValidationResult:
    """
    Validate AWS credentials asynchronously.

    Args:
        credentials: AWS credentials dataclass

    Returns:
        CredentialValidationResult with validation status
    """
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError

        def _validate():
            client = boto3.client(
                'ec2',
                region_name=credentials.region,
                aws_access_key_id=credentials.access_key_id,
                aws_secret_access_key=credentials.secret_access_key
            )
            # Test credentials by describing regions
            response = client.describe_regions()
            return response

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(_executor, _validate)

        return CredentialValidationResult(
            valid=True,
            message=f"AWS credentials valid for region {credentials.region}",
            metadata={'regions_count': len(response.get('Regions', []))}
        )

    except (ClientError, NoCredentialsError) as e:
        return CredentialValidationResult(
            valid=False,
            message=f"AWS credential validation failed: {str(e)}",
            metadata={'error_type': type(e).__name__}
        )
    except Exception as e:
        return CredentialValidationResult(
            valid=False,
            message=f"Unexpected error: {str(e)}",
            metadata={'error_type': type(e).__name__}
        )


async def validate_gcp_credentials_async(credentials: GCPCredentials) -> CredentialValidationResult:
    """
    Validate GCP credentials asynchronously.

    Args:
        credentials: GCP credentials dataclass

    Returns:
        CredentialValidationResult with validation status
    """
    try:
        from google.cloud import compute_v1
        from google.oauth2 import service_account
        import json

        def _validate():
            # Parse service account JSON
            service_account_info = json.loads(credentials.service_account_json)
            creds = service_account.Credentials.from_service_account_info(service_account_info)

            # Create compute client
            client = compute_v1.InstancesClient(credentials=creds)

            # Test credentials by listing instances
            request = compute_v1.ListInstancesRequest(
                project=credentials.project_id,
                zone=credentials.zone
            )
            _ = client.list(request=request)

            return service_account_info.get('project_id')

        # Run in thread pool
        loop = asyncio.get_event_loop()
        project_id = await loop.run_in_executor(_executor, _validate)

        return CredentialValidationResult(
            valid=True,
            message=f"GCP credentials valid for project {credentials.project_id}",
            metadata={'project_id': project_id, 'zone': credentials.zone}
        )

    except Exception as e:
        return CredentialValidationResult(
            valid=False,
            message=f"GCP credential validation failed: {str(e)}",
            metadata={'error_type': type(e).__name__}
        )


async def fetch_aws_vpcs_async(credentials: AWSCredentials) -> List[AWSVPC]:
    """
    Fetch AWS VPCs asynchronously.

    Args:
        credentials: AWS credentials dataclass

    Returns:
        List of AWSVPC dataclasses
    """
    try:
        import boto3

        def _fetch():
            client = boto3.client(
                'ec2',
                region_name=credentials.region,
                aws_access_key_id=credentials.access_key_id,
                aws_secret_access_key=credentials.secret_access_key
            )
            response = client.describe_vpcs()
            return response['Vpcs']

        loop = asyncio.get_event_loop()
        vpcs_data = await loop.run_in_executor(_executor, _fetch)

        return [
            AWSVPC(
                vpc_id=vpc['VpcId'],
                cidr_block=vpc['CidrBlock'],
                is_default=vpc.get('IsDefault', False),
                state=vpc['State'],
                tags={tag['Key']: tag['Value'] for tag in vpc.get('Tags', [])}
            )
            for vpc in vpcs_data
        ]

    except Exception as e:
        logger.error(f"Failed to fetch AWS VPCs: {e}")
        return []


async def fetch_aws_subnets_async(credentials: AWSCredentials, vpc_id: Optional[str] = None) -> List[AWSSubnet]:
    """
    Fetch AWS subnets asynchronously.

    Args:
        credentials: AWS credentials dataclass
        vpc_id: Optional VPC ID to filter subnets

    Returns:
        List of AWSSubnet dataclasses
    """
    try:
        import boto3

        def _fetch():
            client = boto3.client(
                'ec2',
                region_name=credentials.region,
                aws_access_key_id=credentials.access_key_id,
                aws_secret_access_key=credentials.secret_access_key
            )

            filters = [{'Name': 'vpc-id', 'Values': [vpc_id]}] if vpc_id else []
            response = client.describe_subnets(Filters=filters)
            return response['Subnets']

        loop = asyncio.get_event_loop()
        subnets_data = await loop.run_in_executor(_executor, _fetch)

        return [
            AWSSubnet(
                subnet_id=subnet['SubnetId'],
                vpc_id=subnet['VpcId'],
                cidr_block=subnet['CidrBlock'],
                availability_zone=subnet['AvailabilityZone'],
                available_ip_address_count=subnet['AvailableIpAddressCount'],
                tags={tag['Key']: tag['Value'] for tag in subnet.get('Tags', [])}
            )
            for subnet in subnets_data
        ]

    except Exception as e:
        logger.error(f"Failed to fetch AWS subnets: {e}")
        return []


async def fetch_aws_security_groups_async(credentials: AWSCredentials, vpc_id: Optional[str] = None) -> List[AWSSecurityGroup]:
    """
    Fetch AWS security groups asynchronously.

    Args:
        credentials: AWS credentials dataclass
        vpc_id: Optional VPC ID to filter security groups

    Returns:
        List of AWSSecurityGroup dataclasses
    """
    try:
        import boto3

        def _fetch():
            client = boto3.client(
                'ec2',
                region_name=credentials.region,
                aws_access_key_id=credentials.access_key_id,
                aws_secret_access_key=credentials.secret_access_key
            )

            filters = [{'Name': 'vpc-id', 'Values': [vpc_id]}] if vpc_id else []
            response = client.describe_security_groups(Filters=filters)
            return response['SecurityGroups']

        loop = asyncio.get_event_loop()
        sgs_data = await loop.run_in_executor(_executor, _fetch)

        return [
            AWSSecurityGroup(
                group_id=sg['GroupId'],
                group_name=sg['GroupName'],
                description=sg['Description'],
                vpc_id=sg['VpcId'],
                tags={tag['Key']: tag['Value'] for tag in sg.get('Tags', [])}
            )
            for sg in sgs_data
        ]

    except Exception as e:
        logger.error(f"Failed to fetch AWS security groups: {e}")
        return []


async def fetch_aws_amis_async(credentials: AWSCredentials, filters: Optional[List[Dict]] = None) -> List[AWSAMI]:
    """
    Fetch AWS AMIs asynchronously.

    Args:
        credentials: AWS credentials dataclass
        filters: Optional filters for AMI search

    Returns:
        List of AWSAMI dataclasses
    """
    try:
        import boto3

        def _fetch():
            client = boto3.client(
                'ec2',
                region_name=credentials.region,
                aws_access_key_id=credentials.access_key_id,
                aws_secret_access_key=credentials.secret_access_key
            )

            # Default to Ubuntu 24.04 LTS if no filters
            if not filters:
                filters = [
                    {'Name': 'name', 'Values': ['ubuntu/images/hvm-ssd/ubuntu-*-24.04-*']},
                    {'Name': 'state', 'Values': ['available']},
                    {'Name': 'architecture', 'Values': ['x86_64']}
                ]

            response = client.describe_images(Filters=filters, Owners=['099720109477'])  # Canonical
            return response['Images']

        loop = asyncio.get_event_loop()
        amis_data = await loop.run_in_executor(_executor, _fetch)

        return [
            AWSAMI(
                ami_id=ami['ImageId'],
                name=ami['Name'],
                description=ami.get('Description', ''),
                architecture=ami['Architecture'],
                root_device_type=ami['RootDeviceType'],
                virtualization_type=ami['VirtualizationType'],
                creation_date=ami['CreationDate']
            )
            for ami in amis_data
        ]

    except Exception as e:
        logger.error(f"Failed to fetch AWS AMIs: {e}")
        return []


async def fetch_gcp_networks_async(credentials: GCPCredentials) -> List[GCPNetwork]:
    """
    Fetch GCP networks asynchronously.

    Args:
        credentials: GCP credentials dataclass

    Returns:
        List of GCPNetwork dataclasses
    """
    try:
        from google.cloud import compute_v1
        from google.oauth2 import service_account
        import json

        def _fetch():
            service_account_info = json.loads(credentials.service_account_json)
            creds = service_account.Credentials.from_service_account_info(service_account_info)

            client = compute_v1.NetworksClient(credentials=creds)
            request = compute_v1.ListNetworksRequest(project=credentials.project_id)
            networks = client.list(request=request)

            return list(networks)

        loop = asyncio.get_event_loop()
        networks_data = await loop.run_in_executor(_executor, _fetch)

        return [
            GCPNetwork(
                name=network.name,
                self_link=network.self_link,
                auto_create_subnetworks=network.auto_create_subnetworks,
                routing_mode=network.routing_config.routing_mode if hasattr(network, 'routing_config') else 'REGIONAL'
            )
            for network in networks_data
        ]

    except Exception as e:
        logger.error(f"Failed to fetch GCP networks: {e}")
        return []


async def fetch_gcp_machine_types_async(credentials: GCPCredentials) -> List[GCPMachineType]:
    """
    Fetch GCP machine types asynchronously.

    Args:
        credentials: GCP credentials dataclass

    Returns:
        List of GCPMachineType dataclasses
    """
    try:
        from google.cloud import compute_v1
        from google.oauth2 import service_account
        import json

        def _fetch():
            service_account_info = json.loads(credentials.service_account_json)
            creds = service_account.Credentials.from_service_account_info(service_account_info)

            client = compute_v1.MachineTypesClient(credentials=creds)
            request = compute_v1.ListMachineTypesRequest(
                project=credentials.project_id,
                zone=credentials.zone
            )
            machine_types = client.list(request=request)

            return list(machine_types)

        loop = asyncio.get_event_loop()
        machine_types_data = await loop.run_in_executor(_executor, _fetch)

        return [
            GCPMachineType(
                name=mt.name,
                guest_cpus=mt.guest_cpus,
                memory_mb=mt.memory_mb,
                zone=credentials.zone,
                description=mt.description
            )
            for mt in machine_types_data
        ]

    except Exception as e:
        logger.error(f"Failed to fetch GCP machine types: {e}")
        return []


async def fetch_gcp_images_async(credentials: GCPCredentials, family: str = 'ubuntu-2404-lts') -> List[GCPImage]:
    """
    Fetch GCP images asynchronously.

    Args:
        credentials: GCP credentials dataclass
        family: Image family to fetch (default: ubuntu-2404-lts)

    Returns:
        List of GCPImage dataclasses
    """
    try:
        from google.cloud import compute_v1
        from google.oauth2 import service_account
        import json

        def _fetch():
            service_account_info = json.loads(credentials.service_account_json)
            creds = service_account.Credentials.from_service_account_info(service_account_info)

            client = compute_v1.ImagesClient(credentials=creds)

            # Fetch from ubuntu-os-cloud project
            request = compute_v1.ListImagesRequest(project='ubuntu-os-cloud')
            images = client.list(request=request)

            # Filter by family
            return [img for img in images if family in img.family]

        loop = asyncio.get_event_loop()
        images_data = await loop.run_in_executor(_executor, _fetch)

        return [
            GCPImage(
                name=img.name,
                self_link=img.self_link,
                family=img.family,
                description=img.description or '',
                creation_timestamp=img.creation_timestamp
            )
            for img in images_data
        ]

    except Exception as e:
        logger.error(f"Failed to fetch GCP images: {e}")
        return []


async def fetch_all_aws_resources_concurrent(credentials: AWSCredentials) -> Dict[str, Any]:
    """
    Fetch all AWS resources concurrently for performance.

    Args:
        credentials: AWS credentials dataclass

    Returns:
        Dictionary with all fetched resources
    """
    # Run all fetch operations concurrently
    vpcs, amis = await asyncio.gather(
        fetch_aws_vpcs_async(credentials),
        fetch_aws_amis_async(credentials),
        return_exceptions=True
    )

    result = {
        'vpcs': vpcs if not isinstance(vpcs, Exception) else [],
        'amis': amis if not isinstance(amis, Exception) else [],
        'subnets': [],
        'security_groups': []
    }

    # If we have VPCs, fetch subnets and security groups for each
    if result['vpcs']:
        subnet_tasks = [fetch_aws_subnets_async(credentials, vpc.vpc_id) for vpc in result['vpcs'][:5]]  # Limit to first 5 VPCs
        sg_tasks = [fetch_aws_security_groups_async(credentials, vpc.vpc_id) for vpc in result['vpcs'][:5]]

        subnets_results, sgs_results = await asyncio.gather(
            asyncio.gather(*subnet_tasks, return_exceptions=True),
            asyncio.gather(*sg_tasks, return_exceptions=True)
        )

        # Flatten results
        for subnet_list in subnets_results:
            if not isinstance(subnet_list, Exception):
                result['subnets'].extend(subnet_list)

        for sg_list in sgs_results:
            if not isinstance(sg_list, Exception):
                result['security_groups'].extend(sg_list)

    return result


async def fetch_all_gcp_resources_concurrent(credentials: GCPCredentials) -> Dict[str, Any]:
    """
    Fetch all GCP resources concurrently for performance.

    Args:
        credentials: GCP credentials dataclass

    Returns:
        Dictionary with all fetched resources
    """
    # Run all fetch operations concurrently
    networks, machine_types, images = await asyncio.gather(
        fetch_gcp_networks_async(credentials),
        fetch_gcp_machine_types_async(credentials),
        fetch_gcp_images_async(credentials),
        return_exceptions=True
    )

    return {
        'networks': networks if not isinstance(networks, Exception) else [],
        'machine_types': machine_types if not isinstance(machine_types, Exception) else [],
        'images': images if not isinstance(images, Exception) else []
    }


# ============================================================================
# ENCRYPTION UTILITIES (AES-256)
# ============================================================================

from cryptography.fernet import Fernet
from base64 import b64encode, b64decode


class EncryptionManager:
    """
    Manages encryption/decryption of sensitive data using Fernet (AES-256).

    Uses encryption key from environment variable ICESHELVES_ENCRYPTION_KEY.
    If not set, generates a new key (WARNING: data will be unrecoverable on restart).
    """

    def __init__(self):
        """Initialize encryption manager with key from environment or generate new."""
        self.encryption_key = os.getenv('ICESHELVES_ENCRYPTION_KEY')

        if not self.encryption_key:
            # Generate new key if not in environment
            self.encryption_key = Fernet.generate_key().decode('utf-8')
            logger.warning(
                "ICESHELVES_ENCRYPTION_KEY not set in environment. "
                "Generated temporary key - data will be unrecoverable on restart! "
                f"Set this key in your environment: ICESHELVES_ENCRYPTION_KEY={self.encryption_key}"
            )

        # Ensure key is bytes for Fernet
        if isinstance(self.encryption_key, str):
            self.encryption_key = self.encryption_key.encode('utf-8')

        self.fernet = Fernet(self.encryption_key)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext string.

        Args:
            plaintext: String to encrypt

        Returns:
            Base64 encoded encrypted string
        """
        if not plaintext:
            return ''

        encrypted_bytes = self.fernet.encrypt(plaintext.encode('utf-8'))
        return b64encode(encrypted_bytes).decode('utf-8')

    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt encrypted string.

        Args:
            encrypted: Base64 encoded encrypted string

        Returns:
            Decrypted plaintext string
        """
        if not encrypted:
            return ''

        try:
            encrypted_bytes = b64decode(encrypted.encode('utf-8'))
            decrypted_bytes = self.fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to decrypt data: {e}")
            raise ValidationError("Decryption failed - invalid key or corrupted data")

    def encrypt_dict(self, data: Dict[str, Any], fields_to_encrypt: List[str]) -> Dict[str, Any]:
        """
        Encrypt specific fields in a dictionary.

        Args:
            data: Dictionary with data to encrypt
            fields_to_encrypt: List of field names to encrypt

        Returns:
            Dictionary with encrypted fields
        """
        encrypted_data = data.copy()

        for field in fields_to_encrypt:
            if field in encrypted_data and encrypted_data[field]:
                encrypted_data[field] = self.encrypt(str(encrypted_data[field]))

        return encrypted_data

    def decrypt_dict(self, data: Dict[str, Any], fields_to_decrypt: List[str]) -> Dict[str, Any]:
        """
        Decrypt specific fields in a dictionary.

        Args:
            data: Dictionary with encrypted data
            fields_to_decrypt: List of field names to decrypt

        Returns:
            Dictionary with decrypted fields
        """
        decrypted_data = data.copy()

        for field in fields_to_decrypt:
            if field in decrypted_data and decrypted_data[field]:
                decrypted_data[field] = self.decrypt(str(decrypted_data[field]))

        return decrypted_data


# Global encryption manager instance
_encryption_manager = None

def get_encryption_manager() -> EncryptionManager:
    """Get global encryption manager instance."""
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager


def encrypt_aws_credentials(access_key_id: str, secret_access_key: str) -> Tuple[str, str]:
    """
    Encrypt AWS credentials for database storage.

    Args:
        access_key_id: AWS access key ID
        secret_access_key: AWS secret access key

    Returns:
        Tuple of (encrypted_access_key, encrypted_secret_key)
    """
    manager = get_encryption_manager()
    return (
        manager.encrypt(access_key_id),
        manager.encrypt(secret_access_key)
    )


def decrypt_aws_credentials(encrypted_access_key: str, encrypted_secret_key: str) -> Tuple[str, str]:
    """
    Decrypt AWS credentials from database storage.

    Args:
        encrypted_access_key: Encrypted AWS access key ID
        encrypted_secret_key: Encrypted AWS secret access key

    Returns:
        Tuple of (access_key_id, secret_access_key)
    """
    manager = get_encryption_manager()
    return (
        manager.decrypt(encrypted_access_key),
        manager.decrypt(encrypted_secret_key)
    )


def encrypt_gcp_credentials(service_account_json: str, project_id: str) -> Tuple[str, str]:
    """
    Encrypt GCP credentials for database storage.

    Args:
        service_account_json: GCP service account JSON string
        project_id: GCP project ID

    Returns:
        Tuple of (encrypted_json, encrypted_project_id)
    """
    manager = get_encryption_manager()
    return (
        manager.encrypt(service_account_json),
        manager.encrypt(project_id)
    )


def decrypt_gcp_credentials(encrypted_json: str, encrypted_project_id: str) -> Tuple[str, str]:
    """
    Decrypt GCP credentials from database storage.

    Args:
        encrypted_json: Encrypted service account JSON
        encrypted_project_id: Encrypted project ID

    Returns:
        Tuple of (service_account_json, project_id)
    """
    manager = get_encryption_manager()
    return (
        manager.decrypt(encrypted_json),
        manager.decrypt(encrypted_project_id)
    )


def encrypt_ssh_keys(private_key: str, public_key: str) -> Tuple[str, str]:
    """
    Encrypt SSH keys for database storage.

    Args:
        private_key: SSH private key
        public_key: SSH public key

    Returns:
        Tuple of (encrypted_private_key, encrypted_public_key)
    """
    manager = get_encryption_manager()
    return (
        manager.encrypt(private_key),
        manager.encrypt(public_key)
    )


def decrypt_ssh_keys(encrypted_private_key: str, encrypted_public_key: str) -> Tuple[str, str]:
    """
    Decrypt SSH keys from database storage.

    Args:
        encrypted_private_key: Encrypted SSH private key
        encrypted_public_key: Encrypted SSH public key

    Returns:
        Tuple of (private_key, public_key)
    """
    manager = get_encryption_manager()
    return (
        manager.decrypt(encrypted_private_key),
        manager.decrypt(encrypted_public_key)
    )


def load_user_credential(credential_id: int) -> Optional[Dict[str, Any]]:
    """
    Load and decrypt user credential from database.

    Args:
        credential_id: Credential ID

    Returns:
        Dictionary with decrypted credential data or None
    """
    credential = db.user_credentials[credential_id]
    if not credential:
        return None

    result = {
        'id': credential.id,
        'user_id': credential.user_id,
        'name': credential.name,
        'credential_type': credential.credential_type,
        'storage_type': credential.storage_type,
        'is_encrypted': credential.is_encrypted,
    }

    # Decrypt based on type if stored in database
    if credential.storage_type == 'database' and credential.is_encrypted:
        manager = get_encryption_manager()

        if credential.credential_type == 'aws':
            result['aws_access_key_id'] = manager.decrypt(credential.aws_access_key_id)
            result['aws_secret_access_key'] = manager.decrypt(credential.aws_secret_access_key)

        elif credential.credential_type == 'gcp':
            result['gcp_service_account_json'] = manager.decrypt(credential.gcp_service_account_json)
            result['gcp_project_id'] = manager.decrypt(credential.gcp_project_id)

        elif credential.credential_type == 'ssh':
            result['ssh_private_key'] = manager.decrypt(credential.ssh_private_key)
            result['ssh_public_key'] = manager.decrypt(credential.ssh_public_key)
    else:
        # Not encrypted or stored externally
        result['aws_access_key_id'] = credential.aws_access_key_id
        result['aws_secret_access_key'] = credential.aws_secret_access_key
        result['gcp_service_account_json'] = credential.gcp_service_account_json
        result['gcp_project_id'] = credential.gcp_project_id
        result['ssh_private_key'] = credential.ssh_private_key
        result['ssh_public_key'] = credential.ssh_public_key

    return result


def save_user_credential(
    user_id: str,
    name: str,
    credential_type: str,
    storage_type: str = 'database',
    **credential_data
) -> int:
    """
    Save and encrypt user credential to database.

    Args:
        user_id: User ID who owns the credential
        name: Friendly name for credential
        credential_type: Type of credential (aws, gcp, ssh)
        storage_type: Storage type (database, aws, gcp, infisical)
        **credential_data: Credential-specific data

    Returns:
        Credential ID
    """
    manager = get_encryption_manager()

    # Prepare data for insertion
    insert_data = {
        'user_id': user_id,
        'name': name,
        'credential_type': credential_type,
        'storage_type': storage_type,
        'is_encrypted': True if storage_type == 'database' else False,
    }

    # Encrypt credentials if storing in database
    if storage_type == 'database':
        if credential_type == 'aws':
            insert_data['aws_access_key_id'] = manager.encrypt(credential_data['aws_access_key_id'])
            insert_data['aws_secret_access_key'] = manager.encrypt(credential_data['aws_secret_access_key'])

        elif credential_type == 'gcp':
            insert_data['gcp_service_account_json'] = manager.encrypt(credential_data['gcp_service_account_json'])
            insert_data['gcp_project_id'] = manager.encrypt(credential_data['gcp_project_id'])

        elif credential_type == 'ssh':
            insert_data['ssh_private_key'] = manager.encrypt(credential_data['ssh_private_key'])
            insert_data['ssh_public_key'] = manager.encrypt(credential_data['ssh_public_key'])
    else:
        # Store reference to external secret manager
        # TODO: Implement external secret manager integration
        pass

    credential_id = db.user_credentials.insert(**insert_data)
    db.commit()

    return credential_id


# ============================================================================
# HEALTH CHECK
# ============================================================================

def check_cluster_health(cluster_id: int) -> Tuple[str, Dict[str, Any]]:
    """
    Check health of a cluster connection.

    Args:
        cluster_id: Cluster ID

    Returns:
        Tuple of (status, details)
    """
    cluster = db.deployment_targets[cluster_id]
    if not cluster:
        return 'error', {'message': 'Cluster not found'}

    try:
        if cluster.connection_method == 'agent-poll':
            # Check agent last seen
            if cluster.agent_last_seen:
                time_since_last = datetime.utcnow() - cluster.agent_last_seen
                if time_since_last < timedelta(seconds=cluster.agent_poll_interval * 2):
                    return 'active', {'message': 'Agent is active', 'last_seen': cluster.agent_last_seen}
                else:
                    return 'inactive', {'message': 'Agent has not checked in recently', 'last_seen': cluster.agent_last_seen}
            else:
                return 'unknown', {'message': 'Agent has never checked in'}
        else:
            # Direct connection test
            client = LXDClient(cluster)
            success, message = client.test_connection()
            if success:
                return 'active', {'message': message}
            else:
                return 'error', {'message': message}
    except Exception as e:
        return 'error', {'message': str(e)}
