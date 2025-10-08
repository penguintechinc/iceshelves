"""
IceShelves Controllers

Main routes and API endpoints for the IceShelves application.
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from py4web import action, request, response, abort, redirect, URL
from py4web.utils.cors import CORS
from py4web.utils.form import Form, FormStyleBulma
from pydal.validators import IS_NOT_EMPTY

# Add shared modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.licensing.python_client import (
    get_client,
    requires_feature,
    FeatureNotAvailableError,
    LicenseValidationError,
)

import settings
from models import db
import common

# Configure logging
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Session fixture
from py4web import Session
session = Session(secret=settings.SESSION_SECRET)

# Prometheus metrics (if enabled)
if settings.ENABLE_METRICS:
    from prometheus_client import Counter, Histogram, generate_latest

    REQUEST_COUNT = Counter('iceshelves_http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
    REQUEST_DURATION = Histogram('iceshelves_http_request_duration_seconds', 'HTTP request duration')
    DEPLOYMENT_COUNT = Counter('iceshelves_deployments_total', 'Total deployments', ['status', 'type'])


# ============================================================================
# HEALTH AND METRICS ENDPOINTS
# ============================================================================

@action('healthz')
@action('health')
@CORS()
def healthz():
    """Health check endpoint."""
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': settings.VERSION,
        'app': 'iceshelves',
        'database': 'connected' if db else 'disconnected',
        'dependencies': {
            'pylxd': common.PYLXD_AVAILABLE,
            'libvirt': common.LIBVIRT_AVAILABLE,
        }
    }

    # Check database connection
    try:
        db.executesql('SELECT 1')
        health_status['database'] = 'connected'
    except Exception as e:
        health_status['database'] = f'error: {str(e)}'
        health_status['status'] = 'degraded'
        response.status = 503

    return health_status


@action('metrics')
def metrics():
    """Prometheus metrics endpoint."""
    if not settings.ENABLE_METRICS:
        abort(404)

    response.headers['Content-Type'] = 'text/plain'
    return generate_latest()


# ============================================================================
# MAIN DASHBOARD
# ============================================================================

@action('index')
@action.uses('index.html', session, db)
def index():
    """Main dashboard."""
    # Get statistics
    stats = {
        'total_eggs': db(db.eggs.is_active == True).count(),
        'total_targets': db(db.deployment_targets.is_active == True).count(),
        'total_deployments': db(db.deployments).count(),
        'active_deployments': db(db.deployments.status.belongs(['pending', 'in_progress'])).count(),
        'successful_deployments': db(db.deployments.status == 'completed').count(),
        'failed_deployments': db(db.deployments.status == 'failed').count(),
    }

    # Recent deployments
    recent_deployments = db(db.deployments).select(
        orderby=~db.deployments.created_on,
        limitby=(0, 10)
    )

    # Active clusters (all types)
    active_clusters = db(db.deployment_targets.is_active == True).select()

    # Cloud providers (AWS, GCP)
    cloud_providers = db(
        (db.deployment_targets.is_active == True) &
        (db.deployment_targets.provider_type.belongs(['aws', 'gcp']))
    ).select()

    # LXD clusters
    lxd_clusters = db(
        (db.deployment_targets.is_active == True) &
        (db.deployment_targets.provider_type == 'lxd')
    ).select()

    return dict(
        stats=stats,
        recent_deployments=recent_deployments,
        active_clusters=active_clusters,
        cloud_providers=cloud_providers,
        lxd_clusters=lxd_clusters,
    )


# ============================================================================
# EGG MANAGEMENT
# ============================================================================

@action('eggs')
@action('eggs/list')
@action.uses('eggs/list.html', session, db)
def eggs_list():
    """List all eggs."""
    # Pagination
    page = int(request.query.get('page', 1))
    per_page = settings.ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    # Filters
    category = request.query.get('category')
    search = request.query.get('search')

    # Build query
    query = (db.eggs.is_active == True)

    if category:
        query &= (db.eggs.category == category)

    if search:
        query &= (
            db.eggs.name.contains(search) |
            db.eggs.display_name.contains(search) |
            db.eggs.description.contains(search)
        )

    # Get eggs
    total_eggs = db(query).count()
    eggs = db(query).select(
        orderby=db.eggs.name,
        limitby=(offset, offset + per_page)
    )

    total_pages = (total_eggs + per_page - 1) // per_page

    return dict(
        eggs=eggs,
        page=page,
        total_pages=total_pages,
        total_eggs=total_eggs,
        category=category,
        search=search,
    )


@action('eggs/view/<egg_id:int>')
@action.uses('eggs/view.html', session, db)
def eggs_view(egg_id):
    """View egg details."""
    egg = db.eggs[egg_id]
    if not egg:
        abort(404, "Egg not found")

    # Load egg files
    files = common.load_egg_files(egg)

    # Get deployment history
    deployments = db(db.deployments.egg_id == egg_id).select(
        orderby=~db.deployments.created_on,
        limitby=(0, 20)
    )

    return dict(
        egg=egg,
        files=files,
        deployments=deployments,
    )


@action('eggs/create', method=['GET', 'POST'])
@action.uses('eggs/create.html', session, db)
def eggs_create():
    """Create new egg from template."""
    templates = db(db.egg_templates.is_active == True).select()

    if request.method == 'POST':
        egg_name = request.forms.get('egg_name')
        template_id = request.forms.get('template_id')
        variables = {}

        # Get template
        template = db.egg_templates[template_id]
        if not template:
            response.flash = "Template not found"
            redirect(URL('eggs/create'))

        # Collect template variables
        for var in template.required_variables or []:
            variables[var] = request.forms.get(f'var_{var}')

        # Create egg skeleton
        success, message = common.create_egg_skeleton(egg_name, template, variables)

        if success:
            # Create database record
            egg_id = db.eggs.insert(
                name=egg_name,
                display_name=request.forms.get('display_name', egg_name),
                description=request.forms.get('description', f'Created from template: {template.name}'),
                version='1.0.0',
                egg_type=template.template_type,
                category=template.category,
                cloud_init_path='cloud-init.yaml',
                lxd_profile_path='lxd-profile.yaml' if template.lxd_profile_template else None,
                kvm_config_path='kvm-config.xml' if template.kvm_config_template else None,
                is_active=True,
                author=request.forms.get('author', 'IceShelves User'),
            )
            db.commit()

            response.flash = message
            redirect(URL(f'eggs/view/{egg_id}'))
        else:
            response.flash = f"Error: {message}"

    return dict(templates=templates)


# ============================================================================
# CLUSTER MANAGEMENT
# ============================================================================

@action('clusters')
@action('clusters/list')
@action.uses('clusters/list.html', session, db)
def clusters_list():
    """List all clusters."""
    clusters = db(db.deployment_targets).select(orderby=db.deployment_targets.name)

    return dict(clusters=clusters)


@action('clusters/view/<cluster_id:int>')
@action.uses('clusters/view.html', session, db)
def clusters_view(cluster_id):
    """View cluster details."""
    cluster = db.deployment_targets[cluster_id]
    if not cluster:
        abort(404, "Cluster not found")

    # Get cluster health
    status, details = common.check_cluster_health(cluster_id)

    # Get deployments for this cluster
    deployments = db(db.deployments.target_id == cluster_id).select(
        orderby=~db.deployments.created_on,
        limitby=(0, 20)
    )

    # Get cluster members if it's a cluster
    members = []
    if cluster.connection_method == 'direct-api' and cluster.is_cluster:
        try:
            client = common.LXDClient(cluster)
            if client.connect():
                members = client.get_cluster_members()
        except Exception as e:
            logger.error(f"Failed to get cluster members: {e}")

    return dict(
        cluster=cluster,
        status=status,
        details=details,
        deployments=deployments,
        members=members,
    )


@action('clusters/add', method=['GET', 'POST'])
@action.uses('clusters/add.html', session, db)
def clusters_add():
    """Add new cluster."""
    if request.method == 'POST':
        connection_method = request.forms.get('connection_method')

        # Common fields
        cluster_data = {
            'name': request.forms.get('name'),
            'description': request.forms.get('description'),
            'connection_method': connection_method,
            'is_cluster': request.forms.get('is_cluster') == 'on',
            'is_active': True,
        }

        # Method-specific fields
        if connection_method == 'direct-api':
            cluster_data.update({
                'endpoint_url': request.forms.get('endpoint_url'),
                'auth_type': request.forms.get('auth_type', 'certificate'),
                'client_cert': request.forms.get('client_cert'),
                'client_key': request.forms.get('client_key'),
                'verify_ssl': request.forms.get('verify_ssl') == 'on',
            })
        elif connection_method == 'ssh':
            cluster_data.update({
                'ssh_host': request.forms.get('ssh_host'),
                'ssh_port': int(request.forms.get('ssh_port', 22)),
                'ssh_user': request.forms.get('ssh_user'),
                'ssh_key': request.forms.get('ssh_key'),
            })
        elif connection_method == 'agent-poll':
            agent_key = common.generate_agent_key()
            cluster_data.update({
                'agent_key': agent_key,
                'agent_poll_interval': int(request.forms.get('agent_poll_interval', 300)),
            })

        # Insert cluster
        cluster_id = db.deployment_targets.insert(**cluster_data)
        db.commit()

        # Test connection (except for agent-poll)
        if connection_method != 'agent-poll':
            cluster = db.deployment_targets[cluster_id]
            status, message = common.check_cluster_health(cluster_id)
            cluster.update_record(status=status, last_check=datetime.utcnow())
            db.commit()

        response.flash = f"Cluster '{cluster_data['name']}' added successfully"
        redirect(URL(f'clusters/view/{cluster_id}'))

    return dict()


@action('clusters/test/<cluster_id:int>')
@CORS()
def clusters_test(cluster_id):
    """Test cluster connection."""
    status, details = common.check_cluster_health(cluster_id)

    # Update cluster status
    cluster = db.deployment_targets[cluster_id]
    if cluster:
        cluster.update_record(status=status, last_check=datetime.utcnow())
        db.commit()

    return dict(status=status, details=details)


# ============================================================================
# DEPLOYMENT
# ============================================================================

@action('deploy', method=['GET', 'POST'])
@action('deploy/<egg_id:int>', method=['GET', 'POST'])
@action.uses('deploy.html', session, db)
def deploy(egg_id=None):
    """Deploy an egg to a cluster."""
    if request.method == 'POST':
        egg_id = int(request.forms.get('egg_id'))
        cluster_id = int(request.forms.get('cluster_id'))
        instance_name = request.forms.get('instance_name')

        egg = db.eggs[egg_id]
        cluster = db.deployment_targets[cluster_id]

        if not egg or not cluster:
            response.flash = "Egg or cluster not found"
            redirect(URL('deploy'))

        # Load egg cloud-init
        files = common.load_egg_files(egg)

        # Determine deployment type based on egg type and target provider
        if egg.egg_type == 'aws-ec2':
            deployment_type = 'aws-ec2'
        elif egg.egg_type == 'gcp-vm':
            deployment_type = 'gcp-vm'
        elif egg.egg_type == 'lxd-container':
            deployment_type = 'lxd'
        elif egg.egg_type == 'kvm-vm':
            deployment_type = 'kvm'
        else:
            deployment_type = cluster.provider_type  # Fall back to provider type

        # Create deployment record
        deployment_id = db.deployments.insert(
            egg_id=egg_id,
            target_id=cluster_id,
            instance_name=instance_name,
            status='pending',
            deployment_type=deployment_type,
            cloud_init_data=files['cloud_init'],
            deployed_by=session.get('user', 'anonymous'),
            started_at=datetime.utcnow(),
        )
        db.commit()

        # Log deployment initiation
        common.log_deployment(deployment_id, 'INFO', f'Deployment initiated for instance {instance_name}')

        # For agent-based deployments (LXD only), just mark as pending
        # Agent will pick it up on next poll
        if cluster.provider_type == 'lxd' and cluster.connection_method == 'agent-poll':
            response.flash = f"Deployment queued for agent pickup. Instance: {instance_name}"
            redirect(URL(f'deployments/view/{deployment_id}'))
        else:
            # For direct deployments (LXD, AWS, GCP), trigger immediately
            # TODO: Implement async deployment with background tasks
            try:
                # Update status
                common.update_deployment_status(deployment_id, 'in_progress')

                # Route to appropriate provider client
                if cluster.provider_type == 'lxd':
                    # LXD deployment
                    client = common.LXDClient(cluster)
                    if not client.connect():
                        raise common.ConnectionError("Failed to connect to LXD cluster")

                    # Create instance
                    source = {'type': 'image', 'alias': egg.base_image}
                    config = {'user.cloud-init.user-data': files['cloud_init']}

                    instance = client.create_instance(
                        name=instance_name,
                        source=source,
                        config=config,
                        wait=True
                    )

                    # Start instance
                    instance.start(wait=True)

                    # Update deployment
                    common.update_deployment_status(
                        deployment_id,
                        'completed',
                        instance_info={
                            'name': instance.name,
                            'status': instance.status,
                            'architecture': instance.architecture,
                        }
                    )

                elif cluster.provider_type == 'aws':
                    # AWS EC2 deployment
                    from secrets import get_secrets_manager
                    secrets_mgr = get_secrets_manager(cluster.as_dict(), db, cluster_id)

                    client = common.AWSEC2Client(cluster, secrets_mgr)
                    if not client.connect():
                        raise common.ConnectionError("Failed to connect to AWS EC2")

                    # Get AWS configuration from cloud_config
                    cloud_config = cluster.cloud_config or {}
                    ami = cloud_config.get('ami', 'ami-0e2c8caa4b6378d8c')  # Ubuntu 24.04 LTS default
                    instance_type = cloud_config.get('instance_type', 't3.micro')
                    security_groups = cloud_config.get('security_groups', [])
                    subnet_id = cloud_config.get('subnet_id')
                    key_name = cloud_config.get('key_name')

                    # Launch instance with cloud-init user-data
                    instance = client.launch_instance(
                        name=instance_name,
                        ami=ami,
                        instance_type=instance_type,
                        user_data=files['cloud_init'],
                        security_groups=security_groups,
                        subnet_id=subnet_id,
                        key_name=key_name,
                        wait=True
                    )

                    # Update deployment
                    common.update_deployment_status(
                        deployment_id,
                        'completed',
                        instance_info=instance
                    )

                elif cluster.provider_type == 'gcp':
                    # GCP Compute Engine deployment
                    from secrets import get_secrets_manager
                    secrets_mgr = get_secrets_manager(cluster.as_dict(), db, cluster_id)

                    client = common.GCPComputeClient(cluster, secrets_mgr)
                    if not client.connect():
                        raise common.ConnectionError("Failed to connect to GCP Compute Engine")

                    # Get GCP configuration from cloud_config
                    cloud_config = cluster.cloud_config or {}
                    machine_type = cloud_config.get('machine_type', 'e2-micro')
                    image_project = cloud_config.get('image_project', 'ubuntu-os-cloud')
                    image_family = cloud_config.get('image_family', 'ubuntu-2404-lts')
                    network = cloud_config.get('network', 'default')

                    # Create instance with cloud-init startup script
                    instance = client.create_instance(
                        name=instance_name,
                        machine_type=machine_type,
                        image_project=image_project,
                        image_family=image_family,
                        startup_script=files['cloud_init'],
                        network=network,
                        wait=True
                    )

                    # Update deployment
                    common.update_deployment_status(
                        deployment_id,
                        'completed',
                        instance_info=instance
                    )

                else:
                    raise ValueError(f"Unknown provider type: {cluster.provider_type}")

                common.log_deployment(deployment_id, 'INFO', f'Deployment completed successfully')

                if settings.ENABLE_METRICS:
                    DEPLOYMENT_COUNT.labels(status='completed', type=deployment_type).inc()

                response.flash = f"Instance '{instance_name}' deployed successfully!"

            except Exception as e:
                logger.error(f"Deployment failed: {e}")
                common.update_deployment_status(deployment_id, 'failed', error_message=str(e))
                common.log_deployment(deployment_id, 'ERROR', f'Deployment failed: {str(e)}')

                if settings.ENABLE_METRICS:
                    DEPLOYMENT_COUNT.labels(status='failed', type='lxd').inc()

                response.flash = f"Deployment failed: {str(e)}"

            redirect(URL(f'deployments/view/{deployment_id}'))

    # GET request - show deployment form
    eggs = db(db.eggs.is_active == True).select(orderby=db.eggs.name)
    clusters = db(db.deployment_targets.is_active == True).select(orderby=db.deployment_targets.name)

    selected_egg = db.eggs[egg_id] if egg_id else None

    return dict(eggs=eggs, clusters=clusters, selected_egg=selected_egg)


@action('deployments')
@action('deployments/list')
@action.uses('deployments/list.html', session, db)
def deployments_list():
    """List all deployments."""
    # Pagination
    page = int(request.query.get('page', 1))
    per_page = settings.ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    # Filters
    status = request.query.get('status')
    cluster_id = request.query.get('cluster')

    # Build query
    query = (db.deployments.id > 0)

    if status:
        query &= (db.deployments.status == status)

    if cluster_id:
        query &= (db.deployments.target_id == int(cluster_id))

    # Get deployments
    total_deployments = db(query).count()
    deployments = db(query).select(
        orderby=~db.deployments.created_on,
        limitby=(offset, offset + per_page)
    )

    total_pages = (total_deployments + per_page - 1) // per_page

    return dict(
        deployments=deployments,
        page=page,
        total_pages=total_pages,
        total_deployments=total_deployments,
        status=status,
        cluster_id=cluster_id,
    )


@action('deployments/view/<deployment_id:int>')
@action.uses('deployments/view.html', session, db)
def deployments_view(deployment_id):
    """View deployment details and logs."""
    deployment = db.deployments[deployment_id]
    if not deployment:
        abort(404, "Deployment not found")

    # Get egg and cluster
    egg = db.eggs[deployment.egg_id]
    cluster = db.deployment_targets[deployment.target_id]

    # Get logs
    logs = db(db.deployment_logs.deployment_id == deployment_id).select(
        orderby=db.deployment_logs.timestamp
    )

    return dict(
        deployment=deployment,
        egg=egg,
        cluster=cluster,
        logs=logs,
    )


# ============================================================================
# AGENT API ENDPOINTS
# ============================================================================

@action('api/agent/poll/<cluster_id:int>', method='POST')
@CORS()
def api_agent_poll(cluster_id):
    """Agent polling endpoint - get pending deployments."""
    # Verify agent key
    agent_key = request.get_header('X-Agent-Key')
    if not agent_key or not common.verify_agent_key(cluster_id, agent_key):
        response.status = 401
        return dict(error="Invalid agent key")

    # Update agent last seen
    common.update_agent_last_seen(cluster_id)

    # Get pending deployments
    deployments = common.get_pending_deployments_for_agent(cluster_id)

    return dict(deployments=deployments)


@action('api/agent/status/<deployment_id:int>', method='POST')
@CORS()
def api_agent_status(deployment_id):
    """Agent status update endpoint."""
    # Get deployment
    deployment = db.deployments[deployment_id]
    if not deployment:
        response.status = 404
        return dict(error="Deployment not found")

    # Verify agent key
    agent_key = request.get_header('X-Agent-Key')
    cluster = db.deployment_targets[deployment.target_id]

    if not agent_key or not cluster or cluster.agent_key != agent_key:
        response.status = 401
        return dict(error="Invalid agent key")

    # Parse request body
    try:
        data = request.json
    except:
        response.status = 400
        return dict(error="Invalid JSON")

    # Update deployment status
    status = data.get('status')
    error_message = data.get('error_message')
    instance_info = data.get('instance_info')

    common.update_deployment_status(deployment_id, status, error_message, instance_info)

    # Add log entry
    message = data.get('message', f'Status updated to {status}')
    log_level = 'ERROR' if status == 'failed' else 'INFO'
    common.log_deployment(deployment_id, log_level, message, data.get('details'))

    return dict(success=True, message="Status updated")


# ============================================================================
# TEMPLATES API
# ============================================================================

@action('templates')
@action.uses('templates/list.html', session, db)
def templates_list():
    """List egg templates."""
    templates = db(db.egg_templates.is_active == True).select(
        orderby=db.egg_templates.category
    )

    return dict(templates=templates)


# ============================================================================
# CREDENTIALS MANAGEMENT
# ============================================================================

@action('credentials/manage', method=['GET', 'POST'])
@action.uses('credentials/manage.html', session, db)
def credentials_manage():
    """Manage user credentials for cloud providers."""
    user_id = session.get('user', 'default_user')  # TODO: Get from auth system

    # Get user's credentials
    credentials = db(db.user_credentials.user_id == user_id).select(
        orderby=db.user_credentials.created_on
    )

    return dict(credentials=credentials)


@action('credentials/add/aws', method='POST')
@CORS()
def credentials_add_aws():
    """Add AWS credentials."""
    user_id = session.get('user', 'default_user')  # TODO: Get from auth system

    try:
        data = request.json
        name = data.get('name')
        aws_access_key_id = data.get('aws_access_key_id')
        aws_secret_access_key = data.get('aws_secret_access_key')
        storage_type = data.get('storage_type', 'database')

        # Validate required fields
        if not all([name, aws_access_key_id, aws_secret_access_key]):
            response.status = 400
            return dict(success=False, message="Missing required fields")

        # Save credential
        credential_id = common.save_user_credential(
            user_id=user_id,
            name=name,
            credential_type='aws',
            storage_type=storage_type,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )

        return dict(success=True, message="AWS credentials saved successfully", credential_id=credential_id)

    except Exception as e:
        logger.error(f"Failed to add AWS credentials: {e}")
        response.status = 500
        return dict(success=False, message=str(e))


@action('credentials/add/gcp', method='POST')
@CORS()
def credentials_add_gcp():
    """Add GCP credentials."""
    user_id = session.get('user', 'default_user')  # TODO: Get from auth system

    try:
        data = request.json
        name = data.get('name')
        gcp_service_account_json = data.get('gcp_service_account_json')
        gcp_project_id = data.get('gcp_project_id')
        storage_type = data.get('storage_type', 'database')

        # Validate required fields
        if not all([name, gcp_service_account_json, gcp_project_id]):
            response.status = 400
            return dict(success=False, message="Missing required fields")

        # Save credential
        credential_id = common.save_user_credential(
            user_id=user_id,
            name=name,
            credential_type='gcp',
            storage_type=storage_type,
            gcp_service_account_json=gcp_service_account_json,
            gcp_project_id=gcp_project_id
        )

        return dict(success=True, message="GCP credentials saved successfully", credential_id=credential_id)

    except Exception as e:
        logger.error(f"Failed to add GCP credentials: {e}")
        response.status = 500
        return dict(success=False, message=str(e))


@action('credentials/add/ssh', method='POST')
@CORS()
def credentials_add_ssh():
    """Add SSH credentials."""
    user_id = session.get('user', 'default_user')  # TODO: Get from auth system

    try:
        data = request.json
        name = data.get('name')
        ssh_private_key = data.get('ssh_private_key')
        ssh_public_key = data.get('ssh_public_key')
        storage_type = data.get('storage_type', 'database')

        # Validate required fields
        if not all([name, ssh_private_key]):
            response.status = 400
            return dict(success=False, message="Missing required fields")

        # Save credential
        credential_id = common.save_user_credential(
            user_id=user_id,
            name=name,
            credential_type='ssh',
            storage_type=storage_type,
            ssh_private_key=ssh_private_key,
            ssh_public_key=ssh_public_key or ''
        )

        return dict(success=True, message="SSH credentials saved successfully", credential_id=credential_id)

    except Exception as e:
        logger.error(f"Failed to add SSH credentials: {e}")
        response.status = 500
        return dict(success=False, message=str(e))


@action('credentials/delete/<credential_id:int>', method='POST')
@CORS()
def credentials_delete(credential_id):
    """Delete credential."""
    user_id = session.get('user', 'default_user')  # TODO: Get from auth system

    try:
        credential = db.user_credentials[credential_id]

        if not credential:
            response.status = 404
            return dict(success=False, message="Credential not found")

        # Verify ownership
        if credential.user_id != user_id:
            response.status = 403
            return dict(success=False, message="Unauthorized")

        # Delete credential
        del db.user_credentials[credential_id]
        db.commit()

        return dict(success=True, message="Credential deleted successfully")

    except Exception as e:
        logger.error(f"Failed to delete credential: {e}")
        response.status = 500
        return dict(success=False, message=str(e))


@action('credentials/test/<credential_id:int>', method='POST')
@CORS()
def credentials_test(credential_id):
    """Test credential connection."""
    import asyncio

    try:
        credential = common.load_user_credential(credential_id)

        if not credential:
            response.status = 404
            return dict(success=False, message="Credential not found")

        # Test based on credential type
        if credential['credential_type'] == 'aws':
            creds = common.AWSCredentials(
                access_key_id=credential['aws_access_key_id'],
                secret_access_key=credential['aws_secret_access_key']
            )
            result = asyncio.run(common.validate_aws_credentials_async(creds))

        elif credential['credential_type'] == 'gcp':
            creds = common.GCPCredentials(
                project_id=credential['gcp_project_id'],
                service_account_json=credential['gcp_service_account_json']
            )
            result = asyncio.run(common.validate_gcp_credentials_async(creds))

        else:
            response.status = 400
            return dict(success=False, message="Testing not supported for this credential type")

        return dict(
            success=result.valid,
            message=result.message,
            metadata=result.metadata
        )

    except Exception as e:
        logger.error(f"Failed to test credential: {e}")
        response.status = 500
        return dict(success=False, message=str(e))


# ============================================================================
# CLOUD PROVIDER CONFIGURATION
# ============================================================================

@action('clouds/add')
@action.uses('clouds/select_provider.html', session, db)
def clouds_select_provider():
    """Select cloud provider to add."""
    return dict()


@action('clouds/add/aws', method=['GET', 'POST'])
@action.uses('clouds/add_aws.html', session, db)
def clouds_add_aws():
    """Add AWS EC2 deployment target."""
    user_id = session.get('user', 'default_user')  # TODO: Get from auth system

    if request.method == 'POST':
        try:
            data = request.json

            # Basic information
            name = data.get('name')
            description = data.get('description', '')
            region = data.get('region', 'us-east-1')

            # Credentials
            credential_id = data.get('credential_id')
            credential_source = data.get('credential_source', 'saved')

            # Configuration
            instance_type = data.get('instance_type', 't3.micro')
            ami = data.get('ami')
            vpc_id = data.get('vpc_id')
            subnet_id = data.get('subnet_id')
            security_group_ids = data.get('security_group_ids', [])
            ebs_volume_size = data.get('ebs_volume_size', 20)
            ebs_volume_type = data.get('ebs_volume_type', 'gp3')

            # Build cloud_config
            cloud_config = {
                'region': region,
                'instance_type': instance_type,
                'ami': ami,
                'vpc_id': vpc_id,
                'subnet_id': subnet_id,
                'security_groups': security_group_ids,
                'ebs_volume_size': ebs_volume_size,
                'ebs_volume_type': ebs_volume_type,
            }

            # Add credential reference
            if credential_source == 'saved' and credential_id:
                cloud_config['credential_id'] = credential_id
            elif credential_source == 'inline':
                cloud_config['aws_access_key_id'] = data.get('aws_access_key_id')
                cloud_config['aws_secret_access_key'] = data.get('aws_secret_access_key')
            # else: IAM role (no credentials needed)

            # Create deployment target
            target_id = db.deployment_targets.insert(
                name=name,
                description=description,
                provider_type='aws',
                connection_method='direct-api',  # AWS uses SDK, not direct API
                cloud_config=cloud_config,
                is_active=True,
                created_by=user_id,
            )
            db.commit()

            return dict(success=True, message="AWS deployment target added successfully", target_id=target_id)

        except Exception as e:
            logger.error(f"Failed to add AWS deployment target: {e}")
            response.status = 500
            return dict(success=False, message=str(e))

    # GET request - show wizard
    return dict()


@action('clouds/add/gcp', method=['GET', 'POST'])
@action.uses('clouds/add_gcp.html', session, db)
def clouds_add_gcp():
    """Add GCP Compute Engine deployment target."""
    user_id = session.get('user', 'default_user')  # TODO: Get from auth system

    if request.method == 'POST':
        try:
            data = request.json

            # Basic information
            name = data.get('name')
            description = data.get('description', '')
            zone = data.get('zone', 'us-central1-a')

            # Credentials
            credential_id = data.get('credential_id')
            credential_source = data.get('credential_source', 'saved')

            # Configuration
            machine_type = data.get('machine_type', 'e2-micro')
            image_project = data.get('image_project', 'ubuntu-os-cloud')
            image_family = data.get('image_family', 'ubuntu-2404-lts')
            network = data.get('network', 'default')
            firewall_tags = data.get('firewall_tags', [])
            disk_size_gb = data.get('disk_size_gb', 20)
            disk_type = data.get('disk_type', 'pd-standard')

            # Build cloud_config
            cloud_config = {
                'zone': zone,
                'machine_type': machine_type,
                'image_project': image_project,
                'image_family': image_family,
                'network': network,
                'firewall_tags': firewall_tags,
                'disk_size_gb': disk_size_gb,
                'disk_type': disk_type,
            }

            # Add credential reference
            if credential_source == 'saved' and credential_id:
                cloud_config['credential_id'] = credential_id
            elif credential_source == 'upload':
                cloud_config['gcp_service_account_json'] = data.get('gcp_service_account_json')
                cloud_config['gcp_project_id'] = data.get('gcp_project_id')

            # Create deployment target
            target_id = db.deployment_targets.insert(
                name=name,
                description=description,
                provider_type='gcp',
                connection_method='direct-api',  # GCP uses SDK
                cloud_config=cloud_config,
                is_active=True,
                created_by=user_id,
            )
            db.commit()

            return dict(success=True, message="GCP deployment target added successfully", target_id=target_id)

        except Exception as e:
            logger.error(f"Failed to add GCP deployment target: {e}")
            response.status = 500
            return dict(success=False, message=str(e))

    # GET request - show wizard
    return dict()


# ============================================================================
# CLOUD API ENDPOINTS (for wizard dropdowns and validation)
# ============================================================================

@action('api/user/credentials', method='GET')
@CORS()
def api_user_credentials():
    """Get user's credentials for dropdown population."""
    user_id = session.get('user', 'default_user')  # TODO: Get from auth system
    credential_type = request.query.get('type')  # aws, gcp, ssh

    query = (db.user_credentials.user_id == user_id)

    if credential_type:
        query &= (db.user_credentials.credential_type == credential_type)

    credentials = db(query).select(
        db.user_credentials.id,
        db.user_credentials.name,
        db.user_credentials.credential_type,
        db.user_credentials.created_on,
        orderby=db.user_credentials.name
    )

    return dict(credentials=[
        {
            'id': c.id,
            'name': c.name,
            'type': c.credential_type,
            'created_on': c.created_on.isoformat() if c.created_on else None
        }
        for c in credentials
    ])


@action('api/aws/test-connection', method='POST')
@CORS()
def api_aws_test_connection():
    """Test AWS credentials and return validation result."""
    import asyncio

    try:
        data = request.json
        access_key_id = data.get('aws_access_key_id')
        secret_access_key = data.get('aws_secret_access_key')
        region = data.get('region', 'us-east-1')

        if not access_key_id or not secret_access_key:
            response.status = 400
            return dict(success=False, message="Missing credentials")

        creds = common.AWSCredentials(
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            region=region
        )

        result = asyncio.run(common.validate_aws_credentials_async(creds))

        return dict(
            success=result.valid,
            message=result.message,
            metadata=result.metadata
        )

    except Exception as e:
        logger.error(f"AWS connection test failed: {e}")
        response.status = 500
        return dict(success=False, message=str(e))


@action('api/aws/vpcs', method='POST')
@CORS()
def api_aws_vpcs():
    """Fetch AWS VPCs."""
    import asyncio

    try:
        data = request.json
        credential_id = data.get('credential_id')

        if not credential_id:
            response.status = 400
            return dict(success=False, message="Missing credential_id")

        credential = common.load_user_credential(credential_id)
        if not credential:
            response.status = 404
            return dict(success=False, message="Credential not found")

        creds = common.AWSCredentials(
            access_key_id=credential['aws_access_key_id'],
            secret_access_key=credential['aws_secret_access_key'],
            region=data.get('region', 'us-east-1')
        )

        vpcs = asyncio.run(common.fetch_aws_vpcs_async(creds))

        return dict(success=True, vpcs=[
            {
                'vpc_id': vpc.vpc_id,
                'cidr_block': vpc.cidr_block,
                'is_default': vpc.is_default,
                'state': vpc.state,
                'tags': vpc.tags
            }
            for vpc in vpcs
        ])

    except Exception as e:
        logger.error(f"Failed to fetch AWS VPCs: {e}")
        response.status = 500
        return dict(success=False, message=str(e))


@action('api/aws/subnets', method='POST')
@CORS()
def api_aws_subnets():
    """Fetch AWS subnets for a VPC."""
    import asyncio

    try:
        data = request.json
        credential_id = data.get('credential_id')
        vpc_id = data.get('vpc_id')

        if not credential_id:
            response.status = 400
            return dict(success=False, message="Missing credential_id")

        credential = common.load_user_credential(credential_id)
        if not credential:
            response.status = 404
            return dict(success=False, message="Credential not found")

        creds = common.AWSCredentials(
            access_key_id=credential['aws_access_key_id'],
            secret_access_key=credential['aws_secret_access_key'],
            region=data.get('region', 'us-east-1')
        )

        subnets = asyncio.run(common.fetch_aws_subnets_async(creds, vpc_id))

        return dict(success=True, subnets=[
            {
                'subnet_id': subnet.subnet_id,
                'vpc_id': subnet.vpc_id,
                'cidr_block': subnet.cidr_block,
                'availability_zone': subnet.availability_zone,
                'available_ip_address_count': subnet.available_ip_address_count,
                'tags': subnet.tags
            }
            for subnet in subnets
        ])

    except Exception as e:
        logger.error(f"Failed to fetch AWS subnets: {e}")
        response.status = 500
        return dict(success=False, message=str(e))


@action('api/aws/security-groups', method='POST')
@CORS()
def api_aws_security_groups():
    """Fetch AWS security groups for a VPC."""
    import asyncio

    try:
        data = request.json
        credential_id = data.get('credential_id')
        vpc_id = data.get('vpc_id')

        if not credential_id:
            response.status = 400
            return dict(success=False, message="Missing credential_id")

        credential = common.load_user_credential(credential_id)
        if not credential:
            response.status = 404
            return dict(success=False, message="Credential not found")

        creds = common.AWSCredentials(
            access_key_id=credential['aws_access_key_id'],
            secret_access_key=credential['aws_secret_access_key'],
            region=data.get('region', 'us-east-1')
        )

        security_groups = asyncio.run(common.fetch_aws_security_groups_async(creds, vpc_id))

        return dict(success=True, security_groups=[
            {
                'group_id': sg.group_id,
                'group_name': sg.group_name,
                'description': sg.description,
                'vpc_id': sg.vpc_id,
                'tags': sg.tags
            }
            for sg in security_groups
        ])

    except Exception as e:
        logger.error(f"Failed to fetch AWS security groups: {e}")
        response.status = 500
        return dict(success=False, message=str(e))


@action('api/aws/amis', method='POST')
@CORS()
def api_aws_amis():
    """Fetch AWS AMIs."""
    import asyncio

    try:
        data = request.json
        credential_id = data.get('credential_id')

        if not credential_id:
            response.status = 400
            return dict(success=False, message="Missing credential_id")

        credential = common.load_user_credential(credential_id)
        if not credential:
            response.status = 404
            return dict(success=False, message="Credential not found")

        creds = common.AWSCredentials(
            access_key_id=credential['aws_access_key_id'],
            secret_access_key=credential['aws_secret_access_key'],
            region=data.get('region', 'us-east-1')
        )

        amis = asyncio.run(common.fetch_aws_amis_async(creds))

        return dict(success=True, amis=[
            {
                'ami_id': ami.ami_id,
                'name': ami.name,
                'description': ami.description,
                'architecture': ami.architecture,
                'root_device_type': ami.root_device_type,
                'virtualization_type': ami.virtualization_type,
                'creation_date': ami.creation_date
            }
            for ami in amis[:20]  # Limit to 20 most recent
        ])

    except Exception as e:
        logger.error(f"Failed to fetch AWS AMIs: {e}")
        response.status = 500
        return dict(success=False, message=str(e))


@action('api/gcp/test-connection', method='POST')
@CORS()
def api_gcp_test_connection():
    """Test GCP credentials and return validation result."""
    import asyncio

    try:
        data = request.json
        service_account_json = data.get('gcp_service_account_json')
        project_id = data.get('gcp_project_id')
        zone = data.get('zone', 'us-central1-a')

        if not service_account_json or not project_id:
            response.status = 400
            return dict(success=False, message="Missing credentials")

        creds = common.GCPCredentials(
            project_id=project_id,
            service_account_json=service_account_json,
            zone=zone
        )

        result = asyncio.run(common.validate_gcp_credentials_async(creds))

        return dict(
            success=result.valid,
            message=result.message,
            metadata=result.metadata
        )

    except Exception as e:
        logger.error(f"GCP connection test failed: {e}")
        response.status = 500
        return dict(success=False, message=str(e))


@action('api/gcp/networks', method='POST')
@CORS()
def api_gcp_networks():
    """Fetch GCP networks."""
    import asyncio

    try:
        data = request.json
        credential_id = data.get('credential_id')

        if not credential_id:
            response.status = 400
            return dict(success=False, message="Missing credential_id")

        credential = common.load_user_credential(credential_id)
        if not credential:
            response.status = 404
            return dict(success=False, message="Credential not found")

        creds = common.GCPCredentials(
            project_id=credential['gcp_project_id'],
            service_account_json=credential['gcp_service_account_json'],
            zone=data.get('zone', 'us-central1-a')
        )

        networks = asyncio.run(common.fetch_gcp_networks_async(creds))

        return dict(success=True, networks=[
            {
                'name': net.name,
                'self_link': net.self_link,
                'auto_create_subnetworks': net.auto_create_subnetworks,
                'routing_mode': net.routing_mode
            }
            for net in networks
        ])

    except Exception as e:
        logger.error(f"Failed to fetch GCP networks: {e}")
        response.status = 500
        return dict(success=False, message=str(e))


@action('api/gcp/machine-types', method='POST')
@CORS()
def api_gcp_machine_types():
    """Fetch GCP machine types."""
    import asyncio

    try:
        data = request.json
        credential_id = data.get('credential_id')
        zone = data.get('zone', 'us-central1-a')

        if not credential_id:
            response.status = 400
            return dict(success=False, message="Missing credential_id")

        credential = common.load_user_credential(credential_id)
        if not credential:
            response.status = 404
            return dict(success=False, message="Credential not found")

        creds = common.GCPCredentials(
            project_id=credential['gcp_project_id'],
            service_account_json=credential['gcp_service_account_json'],
            zone=zone
        )

        machine_types = asyncio.run(common.fetch_gcp_machine_types_async(creds))

        return dict(success=True, machine_types=[
            {
                'name': mt.name,
                'guest_cpus': mt.guest_cpus,
                'memory_mb': mt.memory_mb,
                'zone': mt.zone,
                'description': mt.description
            }
            for mt in machine_types
        ])

    except Exception as e:
        logger.error(f"Failed to fetch GCP machine types: {e}")
        response.status = 500
        return dict(success=False, message=str(e))


@action('api/gcp/images', method='POST')
@CORS()
def api_gcp_images():
    """Fetch GCP images."""
    import asyncio

    try:
        data = request.json
        credential_id = data.get('credential_id')
        family = data.get('family', 'ubuntu-2404-lts')

        if not credential_id:
            response.status = 400
            return dict(success=False, message="Missing credential_id")

        credential = common.load_user_credential(credential_id)
        if not credential:
            response.status = 404
            return dict(success=False, message="Credential not found")

        creds = common.GCPCredentials(
            project_id=credential['gcp_project_id'],
            service_account_json=credential['gcp_service_account_json'],
            zone=data.get('zone', 'us-central1-a')
        )

        images = asyncio.run(common.fetch_gcp_images_async(creds, family))

        return dict(success=True, images=[
            {
                'name': img.name,
                'self_link': img.self_link,
                'family': img.family,
                'description': img.description,
                'creation_timestamp': img.creation_timestamp
            }
            for img in images[:20]  # Limit to 20 most recent
        ])

    except Exception as e:
        logger.error(f"Failed to fetch GCP images: {e}")
        response.status = 500
        return dict(success=False, message=str(e))


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@action('error/404')
@action.uses('error.html')
def error_404():
    """404 error page."""
    return dict(
        error="Page Not Found",
        message="The requested page could not be found.",
        code=404
    )


@action('error/500')
@action.uses('error.html')
def error_500():
    """500 error page."""
    return dict(
        error="Internal Server Error",
        message="An unexpected error occurred. Please try again later.",
        code=500
    )
