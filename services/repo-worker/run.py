#!/usr/bin/env python3
"""Entry point for repo-worker service."""

import os
import asyncio
import logging

from app import create_app
from app.config import Config
from app.storage.s3 import S3Storage, set_storage

logger = logging.getLogger(__name__)


async def init_storage(config: Config) -> None:
    """Initialize S3 storage and create bucket if needed."""
    storage = S3Storage(config.s3)
    set_storage(storage)

    # Ensure bucket exists
    try:
        await storage.ensure_bucket_exists()
        logger.info(f"S3 bucket '{config.s3.bucket}' ready")
    except Exception as e:
        logger.error(f"Failed to initialize S3 storage: {e}")
        raise


def main():
    """Run the application."""
    # Load configuration
    config_path = os.getenv("CONFIG_PATH")
    if config_path and os.path.exists(config_path):
        config = Config.from_yaml(config_path)
    else:
        config = Config.from_env()

    # Initialize storage
    asyncio.get_event_loop().run_until_complete(init_storage(config))

    # Create app
    app = create_app(config)

    # Run with hypercorn for production, or built-in for dev
    if config.debug:
        app.run(host=config.host, port=config.port, debug=True)
    else:
        import hypercorn.asyncio
        from hypercorn.config import Config as HypercornConfig

        hypercorn_config = HypercornConfig()
        hypercorn_config.bind = [f"{config.host}:{config.port}"]
        hypercorn_config.workers = config.workers

        asyncio.run(hypercorn.asyncio.serve(app, hypercorn_config))


if __name__ == "__main__":
    main()
