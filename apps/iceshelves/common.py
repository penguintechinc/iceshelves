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
            cluster_record: Database record from lxd_clusters table
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
    cluster = db.lxd_clusters[cluster_id]
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
        (db.deployments.cluster_id == cluster_id) &
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
    cluster = db.lxd_clusters[cluster_id]
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
    cluster = db.lxd_clusters[cluster_id]
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
