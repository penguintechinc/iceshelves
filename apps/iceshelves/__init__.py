"""
IceShelves - LXD/KVM Egg Deployment Platform

A comprehensive py4web application for managing and deploying "eggs" (cloud-init
deployment packages) to LXD clusters and KVM virtual machines.

Supports three connection methods:
- Direct API: Direct connection to LXD API endpoint
- SSH: SSH tunnel to LXD unix socket
- Agent Poll: Polling agent installed on hypervisor
"""

__version__ = "1.0.0"
__author__ = "Penguin Tech Inc"
__license__ = "Limited AGPL3"

import logging
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)
logger.info(f"IceShelves v{__version__} initializing...")

# Import settings to ensure configuration is loaded
import settings

# Ensure eggs library directory exists
if not settings.EGGS_STORAGE_PATH.exists():
    settings.EGGS_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created eggs library directory: {settings.EGGS_STORAGE_PATH}")

# Import models to initialize database
import models

# Import controllers to register routes
import controllers

logger.info("IceShelves initialized successfully")
