"""
Repo-Worker: Multi-architecture Helm and Docker Repository Service

A Python async service providing:
- Local Docker registry (OCI Distribution API)
- Pull-through proxy/cache for external registries
- Helm chart repository
- S3-compatible storage backend (MinIO default)
"""

from quart import Quart
import logging

from app.config import Config


def create_app(config: Config | None = None) -> Quart:
    """Create and configure the Quart application."""
    app = Quart(__name__)

    if config is None:
        config = Config.from_env()

    app.config.from_object(config)
    app.config["CONFIG"] = config

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if config.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Register blueprints
    from app.registry.routes import registry_bp
    from app.helm.routes import helm_bp

    app.register_blueprint(registry_bp)
    app.register_blueprint(helm_bp)

    # Register health endpoints
    @app.route("/healthz")
    async def healthz():
        """Health check endpoint."""
        return {"status": "healthy"}, 200

    @app.route("/readyz")
    async def readyz():
        """Readiness check endpoint."""
        # Check S3 connectivity
        from app.storage.s3 import get_storage
        storage = get_storage()
        try:
            await storage.check_connection()
            return {"status": "ready"}, 200
        except Exception as e:
            return {"status": "not ready", "error": str(e)}, 503

    return app
