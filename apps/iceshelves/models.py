"""
IceShelves Database Models

Defines all database tables and relationships for the IceShelves application.
"""

from py4web import DAL, Field
from pydal.validators import (
    IS_NOT_EMPTY,
    IS_EMAIL,
    IS_IN_SET,
    IS_URL,
    IS_JSON,
    IS_INT_IN_RANGE,
    IS_DATETIME,
    IS_IN_DB,
    IS_EMPTY_OR,
)
import settings

# Initialize database
db = DAL(
    settings.DB_URI,
    pool_size=settings.DB_POOL_SIZE,
    migrate=settings.DB_MIGRATE,
    fake_migrate=False,
    check_reserved=['all']
)

# Egg Types
EGG_TYPES = ['lxd-container', 'kvm-vm', 'aws-ec2', 'gcp-vm', 'hybrid']

# Provider Types
PROVIDER_TYPES = ['lxd', 'aws', 'gcp']

# Deployment Status
DEPLOYMENT_STATUS = ['pending', 'in_progress', 'completed', 'failed', 'cancelled', 'timeout']

# Cluster/Target Status
CLUSTER_STATUS = ['active', 'inactive', 'error', 'unknown']

# LXD Cluster Authentication Types
AUTH_TYPES = ['tls', 'certificate', 'candid', 'rbac']

# Connection Methods (for LXD)
CONNECTION_METHODS = ['direct-api', 'ssh', 'agent-poll']

# Secrets Manager Types
SECRETS_MANAGER_TYPES = ['database', 'aws', 'gcp', 'infisical']

# Template Categories
TEMPLATE_CATEGORIES = ['base', 'webserver', 'database', 'kubernetes', 'docker', 'custom']

# ============================================================================
# EGGS - Deployment Package Definitions
# ============================================================================
db.define_table(
    'eggs',
    Field('name', 'string', requires=IS_NOT_EMPTY(), unique=True,
          label='Egg Name',
          comment='Unique identifier for the egg (e.g., ubuntu-base, ubuntu-docker)'),
    Field('display_name', 'string', requires=IS_NOT_EMPTY(),
          label='Display Name',
          comment='Human-readable name for display'),
    Field('description', 'text', requires=IS_NOT_EMPTY(),
          label='Description',
          comment='Detailed description of what this egg provides'),
    Field('version', 'string', default='1.0.0',
          label='Version',
          comment='Semantic version of this egg'),
    Field('egg_type', 'string', requires=IS_IN_SET(EGG_TYPES), default='lxd-container',
          label='Egg Type',
          comment='Type of deployment: LXD container, KVM VM, or hybrid'),
    Field('category', 'string', requires=IS_IN_SET(TEMPLATE_CATEGORIES), default='custom',
          label='Category',
          comment='Category for organizing eggs'),
    Field('base_image', 'string',
          label='Base Image',
          comment='Base image for LXD (e.g., ubuntu/24.04, alpine/3.19)'),
    Field('cloud_init_path', 'string',
          label='Cloud-init Path',
          comment='Relative path to cloud-init YAML file'),
    Field('lxd_profile_path', 'string',
          label='LXD Profile Path',
          comment='Relative path to LXD profile YAML (optional)'),
    Field('kvm_config_path', 'string',
          label='KVM Config Path',
          comment='Relative path to KVM libvirt XML config (optional)'),
    Field('metadata_json', 'json',
          label='Additional Metadata',
          comment='Additional metadata in JSON format'),
    Field('is_active', 'boolean', default=True,
          label='Active',
          comment='Whether this egg is active and available for deployment'),
    Field('is_skeleton', 'boolean', default=False,
          label='Is Skeleton Template',
          comment='Whether this egg is a skeleton template for creating new eggs'),
    Field('author', 'string',
          label='Author',
          comment='Author or maintainer of this egg'),
    Field('tags', 'list:string',
          label='Tags',
          comment='Tags for search and categorization'),
    # Docker Compose-style features
    Field('compose_template', 'text',
          label='Compose Template',
          comment='Docker Compose-style YAML for multi-instance deployments'),
    Field('build_context', 'json',
          label='Build Context',
          comment='Build context configuration (environment vars, volumes, networks)'),
    Field('service_dependencies', 'list:string',
          label='Service Dependencies',
          comment='List of other egg names this egg depends on'),
    Field('healthcheck_config', 'json',
          label='Health Check Configuration',
          comment='Docker-style health check configuration'),
    Field('created_on', 'datetime', default=lambda: __import__('datetime').datetime.utcnow(),
          writable=False, readable=True),
    Field('updated_on', 'datetime', update=lambda: __import__('datetime').datetime.utcnow(),
          writable=False, readable=True),
    format='%(name)s (%(version)s)'
)

# ============================================================================
# DEPLOYMENT TARGETS - LXD Clusters, AWS, GCP Configuration
# ============================================================================
db.define_table(
    'deployment_targets',
    Field('name', 'string', requires=IS_NOT_EMPTY(), unique=True,
          label='Target Name',
          comment='Unique name for this deployment target'),
    Field('description', 'text',
          label='Description',
          comment='Description of this deployment target'),
    Field('provider_type', 'string', requires=IS_IN_SET(PROVIDER_TYPES), default='lxd',
          label='Provider Type',
          comment='Infrastructure provider: lxd, aws, or gcp'),
    Field('connection_method', 'string', requires=IS_EMPTY_OR(IS_IN_SET(CONNECTION_METHODS)),
          label='Connection Method (LXD only)',
          comment='For LXD: direct-api, ssh, or agent-poll'),
    Field('endpoint_url', 'string', requires=IS_EMPTY_OR(IS_URL()),
          label='Endpoint URL',
          comment='LXD API endpoint (e.g., https://lxd-host:8443) - for direct-api method'),
    Field('ssh_host', 'string',
          label='SSH Host',
          comment='SSH hostname or IP - for ssh method'),
    Field('ssh_port', 'integer', default=22,
          label='SSH Port',
          comment='SSH port - for ssh method'),
    Field('ssh_user', 'string',
          label='SSH User',
          comment='SSH username - for ssh method'),
    Field('ssh_key', 'text',
          label='SSH Private Key',
          comment='SSH private key for authentication - for ssh method'),
    Field('agent_key', 'string',
          label='Agent Key',
          comment='Unique key for agent authentication - for agent-poll method'),
    Field('agent_poll_interval', 'integer', default=300,
          label='Agent Poll Interval (seconds)',
          comment='How often agent should poll for new deployments (1-600 seconds)'),
    Field('agent_last_seen', 'datetime',
          label='Agent Last Seen',
          comment='Last time agent checked in - for agent-poll method'),
    # Secrets Management
    Field('secrets_manager_type', 'string', requires=IS_IN_SET(SECRETS_MANAGER_TYPES), default='database',
          label='Secrets Manager',
          comment='Where to store sensitive credentials: database, aws, gcp, or infisical'),
    Field('secrets_config', 'json',
          label='Secrets Configuration',
          comment='Configuration for secrets manager (secret IDs, project IDs, etc.)'),
    # Cloud Provider Configuration (AWS/GCP)
    Field('cloud_config', 'json',
          label='Cloud Provider Configuration',
          comment='AWS/GCP specific configuration (region, zone, credentials path, etc.)'),
    # LXD Authentication (for LXD provider only)
    Field('auth_type', 'string', requires=IS_IN_SET(AUTH_TYPES), default='certificate',
          label='Authentication Type',
          comment='Type of authentication to use - for LXD direct-api method'),
    Field('client_cert', 'text',
          label='Client Certificate',
          comment='PEM-encoded client certificate for TLS authentication'),
    Field('client_key', 'text',
          label='Client Key',
          comment='PEM-encoded client private key for TLS authentication'),
    Field('server_cert', 'text',
          label='Server Certificate',
          comment='PEM-encoded server certificate (for verification)'),
    Field('verify_ssl', 'boolean', default=True,
          label='Verify SSL',
          comment='Whether to verify SSL certificates'),
    Field('trust_password', 'password',
          label='Trust Password',
          comment='Trust password for initial connection setup'),
    Field('is_cluster', 'boolean', default=False,
          label='Is Cluster',
          comment='Whether this is a cluster (vs single host)'),
    Field('status', 'string', requires=IS_IN_SET(CLUSTER_STATUS), default='unknown',
          label='Status',
          comment='Current connection status'),
    Field('last_check', 'datetime',
          label='Last Health Check',
          comment='Last time cluster health was checked'),
    Field('metadata', 'json',
          label='Cluster Metadata',
          comment='Additional cluster information (members, resources, etc.)'),
    Field('is_active', 'boolean', default=True,
          label='Active',
          comment='Whether this cluster is active'),
    Field('created_on', 'datetime', default=lambda: __import__('datetime').datetime.utcnow(),
          writable=False, readable=True),
    Field('updated_on', 'datetime', update=lambda: __import__('datetime').datetime.utcnow(),
          writable=False, readable=True),
    format='%(name)s'
)

# ============================================================================
# DEPLOYMENTS - Deployment History and Tracking
# ============================================================================
db.define_table(
    'deployments',
    Field('egg_id', 'reference eggs', requires=IS_IN_DB(db, 'eggs.id', '%(name)s'),
          label='Egg',
          comment='The egg being deployed'),
    Field('target_id', 'reference deployment_targets', requires=IS_IN_DB(db, 'deployment_targets.id', '%(name)s'),
          label='Deployment Target',
          comment='Target infrastructure for deployment'),
    Field('instance_name', 'string', requires=IS_NOT_EMPTY(),
          label='Instance Name',
          comment='Name of the deployed instance'),
    Field('target_member', 'string',
          label='Target Cluster Member',
          comment='Specific cluster member to deploy to (optional)'),
    Field('status', 'string', requires=IS_IN_SET(DEPLOYMENT_STATUS), default='pending',
          label='Status',
          comment='Current deployment status'),
    Field('deployment_type', 'string', requires=IS_IN_SET(['lxd', 'kvm', 'aws-ec2', 'gcp-vm']), default='lxd',
          label='Deployment Type',
          comment='Type of deployment performed'),
    Field('compose_deployment', 'boolean', default=False,
          label='Compose Deployment',
          comment='Whether this is a multi-instance compose-style deployment'),
    Field('compose_config', 'json',
          label='Compose Configuration',
          comment='Docker Compose-style configuration for multi-instance deployments'),
    Field('config_overrides', 'json',
          label='Config Overrides',
          comment='Custom configuration overrides for this deployment'),
    Field('cloud_init_data', 'text',
          label='Cloud-init Data',
          comment='Final cloud-init YAML used for deployment'),
    Field('instance_info', 'json',
          label='Instance Information',
          comment='Details about the deployed instance'),
    Field('started_at', 'datetime',
          label='Started At',
          comment='When deployment started'),
    Field('completed_at', 'datetime',
          label='Completed At',
          comment='When deployment completed'),
    Field('error_message', 'text',
          label='Error Message',
          comment='Error message if deployment failed'),
    Field('deployed_by', 'string',
          label='Deployed By',
          comment='User who initiated deployment'),
    Field('created_on', 'datetime', default=lambda: __import__('datetime').datetime.utcnow(),
          writable=False, readable=True),
    Field('updated_on', 'datetime', update=lambda: __import__('datetime').datetime.utcnow(),
          writable=False, readable=True),
    format='%(instance_name)s'
)

# ============================================================================
# EGG TEMPLATES - Skeleton Templates for Creating New Eggs
# ============================================================================
db.define_table(
    'egg_templates',
    Field('name', 'string', requires=IS_NOT_EMPTY(), unique=True,
          label='Template Name',
          comment='Unique name for this template'),
    Field('display_name', 'string', requires=IS_NOT_EMPTY(),
          label='Display Name',
          comment='Human-readable template name'),
    Field('description', 'text', requires=IS_NOT_EMPTY(),
          label='Description',
          comment='Description of what this template provides'),
    Field('category', 'string', requires=IS_IN_SET(TEMPLATE_CATEGORIES), default='custom',
          label='Category',
          comment='Template category'),
    Field('template_type', 'string', requires=IS_IN_SET(EGG_TYPES), default='lxd-container',
          label='Template Type',
          comment='Type of egg this template creates'),
    Field('cloud_init_template', 'text',
          label='Cloud-init Template',
          comment='Jinja2 template for cloud-init YAML'),
    Field('lxd_profile_template', 'text',
          label='LXD Profile Template',
          comment='Jinja2 template for LXD profile (optional)'),
    Field('kvm_config_template', 'text',
          label='KVM Config Template',
          comment='Jinja2 template for KVM config (optional)'),
    Field('default_values', 'json',
          label='Default Values',
          comment='Default values for template variables'),
    Field('required_variables', 'list:string',
          label='Required Variables',
          comment='List of required template variables'),
    Field('is_active', 'boolean', default=True,
          label='Active',
          comment='Whether this template is active'),
    Field('created_on', 'datetime', default=lambda: __import__('datetime').datetime.utcnow(),
          writable=False, readable=True),
    Field('updated_on', 'datetime', update=lambda: __import__('datetime').datetime.utcnow(),
          writable=False, readable=True),
    format='%(name)s'
)

# ============================================================================
# DEPLOYMENT LOGS - Detailed Deployment Logs
# ============================================================================
db.define_table(
    'deployment_logs',
    Field('deployment_id', 'reference deployments', requires=IS_IN_DB(db, 'deployments.id'),
          label='Deployment',
          comment='Associated deployment'),
    Field('log_level', 'string', requires=IS_IN_SET(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']),
          default='INFO',
          label='Log Level',
          comment='Log severity level'),
    Field('message', 'text', requires=IS_NOT_EMPTY(),
          label='Message',
          comment='Log message'),
    Field('details', 'json',
          label='Details',
          comment='Additional structured log data'),
    Field('timestamp', 'datetime', default=lambda: __import__('datetime').datetime.utcnow(),
          writable=False, readable=True,
          label='Timestamp',
          comment='When this log entry was created'),
    format='%(log_level)s: %(message)s'
)

# ============================================================================
# INDEXES for Performance
# ============================================================================

# Eggs indexes
db.executesql('CREATE INDEX IF NOT EXISTS idx_eggs_name ON eggs(name);')
db.executesql('CREATE INDEX IF NOT EXISTS idx_eggs_category ON eggs(category);')
db.executesql('CREATE INDEX IF NOT EXISTS idx_eggs_active ON eggs(is_active);')

# Deployment Targets indexes
db.executesql('CREATE INDEX IF NOT EXISTS idx_targets_name ON deployment_targets(name);')
db.executesql('CREATE INDEX IF NOT EXISTS idx_targets_provider ON deployment_targets(provider_type);')
db.executesql('CREATE INDEX IF NOT EXISTS idx_targets_status ON deployment_targets(status);')
db.executesql('CREATE INDEX IF NOT EXISTS idx_targets_active ON deployment_targets(is_active);')

# Deployments indexes
db.executesql('CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status);')
db.executesql('CREATE INDEX IF NOT EXISTS idx_deployments_egg ON deployments(egg_id);')
db.executesql('CREATE INDEX IF NOT EXISTS idx_deployments_target ON deployments(target_id);')
db.executesql('CREATE INDEX IF NOT EXISTS idx_deployments_type ON deployments(deployment_type);')
db.executesql('CREATE INDEX IF NOT EXISTS idx_deployments_created ON deployments(created_on);')

# Deployment logs indexes
db.executesql('CREATE INDEX IF NOT EXISTS idx_logs_deployment ON deployment_logs(deployment_id);')
db.executesql('CREATE INDEX IF NOT EXISTS idx_logs_level ON deployment_logs(log_level);')
db.executesql('CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON deployment_logs(timestamp);')

# Commit any pending migrations
db.commit()
