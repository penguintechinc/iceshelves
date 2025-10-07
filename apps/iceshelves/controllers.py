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

    # Active clusters
    active_clusters = db(db.deployment_targets.is_active == True).select()

    return dict(
        stats=stats,
        recent_deployments=recent_deployments,
        active_clusters=active_clusters,
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
