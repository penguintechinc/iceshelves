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
EGG_TYPES = ['lxd-container', 'kvm-vm', 'hybrid']

# Deployment Status
DEPLOYMENT_STATUS = ['pending', 'in_progress', 'completed', 'failed', 'cancelled', 'timeout']

# Cluster Status
CLUSTER_STATUS = ['active', 'inactive', 'error', 'unknown']

# LXD Cluster Authentication Types
AUTH_TYPES = ['tls', 'certificate', 'candid', 'rbac']

# Connection Methods
CONNECTION_METHODS = ['direct-api', 'ssh', 'agent-poll']

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
    Field('created_on', 'datetime', default=lambda: __import__('datetime').datetime.utcnow(),
          writable=False, readable=True),
    Field('updated_on', 'datetime', update=lambda: __import__('datetime').datetime.utcnow(),
          writable=False, readable=True),
    format='%(name)s (%(version)s)'
)

# ============================================================================
# LXD CLUSTERS - Connection Configuration
# ============================================================================
db.define_table(
    'lxd_clusters',
    Field('name', 'string', requires=IS_NOT_EMPTY(), unique=True,
          label='Cluster Name',
          comment='Unique name for this LXD cluster or host'),
    Field('description', 'text',
          label='Description',
          comment='Description of this cluster'),
    Field('connection_method', 'string', requires=IS_IN_SET(CONNECTION_METHODS), default='direct-api',
          label='Connection Method',
          comment='How to connect: direct-api (LXD API), ssh (SSH tunnel), or agent-poll (polling agent)'),
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
    Field('auth_type', 'string', requires=IS_IN_SET(AUTH_TYPES), default='certificate',
          label='Authentication Type',
          comment='Type of authentication to use - for direct-api method'),
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
    Field('cluster_id', 'reference lxd_clusters', requires=IS_IN_DB(db, 'lxd_clusters.id', '%(name)s'),
          label='Cluster',
          comment='Target cluster for deployment'),
    Field('instance_name', 'string', requires=IS_NOT_EMPTY(),
          label='Instance Name',
          comment='Name of the deployed instance'),
    Field('target_member', 'string',
          label='Target Cluster Member',
          comment='Specific cluster member to deploy to (optional)'),
    Field('status', 'string', requires=IS_IN_SET(DEPLOYMENT_STATUS), default='pending',
          label='Status',
          comment='Current deployment status'),
    Field('deployment_type', 'string', requires=IS_IN_SET(['lxd', 'kvm']), default='lxd',
          label='Deployment Type',
          comment='Type of deployment performed'),
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

# LXD Clusters indexes
db.executesql('CREATE INDEX IF NOT EXISTS idx_clusters_name ON lxd_clusters(name);')
db.executesql('CREATE INDEX IF NOT EXISTS idx_clusters_status ON lxd_clusters(status);')
db.executesql('CREATE INDEX IF NOT EXISTS idx_clusters_active ON lxd_clusters(is_active);')

# Deployments indexes
db.executesql('CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status);')
db.executesql('CREATE INDEX IF NOT EXISTS idx_deployments_egg ON deployments(egg_id);')
db.executesql('CREATE INDEX IF NOT EXISTS idx_deployments_cluster ON deployments(cluster_id);')
db.executesql('CREATE INDEX IF NOT EXISTS idx_deployments_created ON deployments(created_on);')

# Deployment logs indexes
db.executesql('CREATE INDEX IF NOT EXISTS idx_logs_deployment ON deployment_logs(deployment_id);')
db.executesql('CREATE INDEX IF NOT EXISTS idx_logs_level ON deployment_logs(log_level);')
db.executesql('CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON deployment_logs(timestamp);')

# Commit any pending migrations
db.commit()
