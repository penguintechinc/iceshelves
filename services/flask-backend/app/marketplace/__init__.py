"""Marketplace Blueprint - Multi-cloud application marketplace and deployment management."""

from flask import Blueprint

marketplace_bp = Blueprint("marketplace", __name__, url_prefix="/api/v1/marketplace")

# Import and register sub-blueprints/routes from marketplace modules
try:
    from .repositories import repositories_bp
    marketplace_bp.register_blueprint(repositories_bp)
except ImportError:
    pass

try:
    from .apps import apps_bp
    marketplace_bp.register_blueprint(apps_bp)
except ImportError:
    pass

try:
    from .deployments import deployments_bp
    marketplace_bp.register_blueprint(deployments_bp)
except ImportError:
    pass

try:
    from .manifests import manifests_bp
    marketplace_bp.register_blueprint(manifests_bp)
except ImportError:
    pass

try:
    from .clusters import clusters_bp
    marketplace_bp.register_blueprint(clusters_bp)
except ImportError:
    pass

try:
    from .versions import versions_bp
    marketplace_bp.register_blueprint(versions_bp)
except ImportError:
    pass

try:
    from .notifications import notifications_bp
    marketplace_bp.register_blueprint(notifications_bp)
except ImportError:
    pass

try:
    from .cloud import cloud_bp
    marketplace_bp.register_blueprint(cloud_bp)
except ImportError:
    pass

try:
    from .inventory import inventory_bp
    marketplace_bp.register_blueprint(inventory_bp)
except ImportError:
    pass
