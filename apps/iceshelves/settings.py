"""
IceShelves Application Settings

Configuration settings for the IceShelves LXD/KVM egg deployment application.
"""

import os
from pathlib import Path

# Application information
APP_NAME = "iceshelves"
APP_FOLDER = Path(__file__).parent
EGGS_LIBRARY = APP_FOLDER / "libraries" / "eggs"

# Database configuration
DB_URI = os.getenv(
    "ICESHELVES_DATABASE_URL",
    os.getenv("DATABASE_URL", "sqlite://storage.db")
)
DB_POOL_SIZE = int(os.getenv("ICESHELVES_DB_POOL_SIZE", "10"))
DB_MIGRATE = os.getenv("ICESHELVES_DB_MIGRATE", "True").lower() == "true"

# License configuration
LICENSE_KEY = os.getenv("LICENSE_KEY")
PRODUCT_NAME = os.getenv("PRODUCT_NAME", "iceshelves")
LICENSE_SERVER_URL = os.getenv("LICENSE_SERVER_URL", "https://license.penguintech.io")

# LXD configuration defaults
LXD_DEFAULT_PROTOCOL = os.getenv("LXD_DEFAULT_PROTOCOL", "lxd")
LXD_VERIFY_CERT = os.getenv("LXD_VERIFY_CERT", "True").lower() == "true"
LXD_CONNECTION_TIMEOUT = int(os.getenv("LXD_CONNECTION_TIMEOUT", "30"))

# KVM/libvirt configuration defaults
LIBVIRT_DEFAULT_URI = os.getenv("LIBVIRT_DEFAULT_URI", "qemu:///system")
LIBVIRT_CONNECTION_TIMEOUT = int(os.getenv("LIBVIRT_CONNECTION_TIMEOUT", "30"))

# Deployment configuration
MAX_CONCURRENT_DEPLOYMENTS = int(os.getenv("MAX_CONCURRENT_DEPLOYMENTS", "5"))
DEPLOYMENT_TIMEOUT = int(os.getenv("DEPLOYMENT_TIMEOUT", "600"))  # 10 minutes
DEPLOYMENT_LOG_RETENTION_DAYS = int(os.getenv("DEPLOYMENT_LOG_RETENTION_DAYS", "30"))

# Storage configuration
EGGS_STORAGE_PATH = EGGS_LIBRARY
MAX_EGG_SIZE_MB = int(os.getenv("MAX_EGG_SIZE_MB", "100"))

# Session configuration
SESSION_SECRET = os.getenv("SESSION_SECRET", "iceshelves-secret-change-in-production")

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "False").lower() == "true"
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "/var/log/iceshelves/app.log")

# Feature flags
ENABLE_KVM_SUPPORT = os.getenv("ENABLE_KVM_SUPPORT", "True").lower() == "true"
ENABLE_CLUSTER_DEPLOYMENT = os.getenv("ENABLE_CLUSTER_DEPLOYMENT", "True").lower() == "true"
ENABLE_METRICS = os.getenv("ENABLE_METRICS", "True").lower() == "true"

# Prometheus metrics
METRICS_PORT = int(os.getenv("METRICS_PORT", "9100"))
METRICS_PATH = os.getenv("METRICS_PATH", "/metrics")

# Application version
VERSION = os.getenv("VERSION", open(Path(__file__).parent.parent.parent / ".version").read().strip())

# Cache configuration
CACHE_TYPE = os.getenv("CACHE_TYPE", "redis")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_DEFAULT_TIMEOUT = int(os.getenv("CACHE_DEFAULT_TIMEOUT", "300"))

# Security settings
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://localhost:3000").split(",")
CSRF_ENABLED = os.getenv("CSRF_ENABLED", "True").lower() == "true"

# Email notifications (optional)
SMTP_SERVER = os.getenv("SMTP_SERVER", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_SENDER = os.getenv("SMTP_SENDER", "iceshelves@localhost")
SMTP_TLS = os.getenv("SMTP_TLS", "True").lower() == "true"
ENABLE_EMAIL_NOTIFICATIONS = os.getenv("ENABLE_EMAIL_NOTIFICATIONS", "False").lower() == "true"

# UI Configuration
ITEMS_PER_PAGE = int(os.getenv("ITEMS_PER_PAGE", "20"))
DATE_FORMAT = os.getenv("DATE_FORMAT", "%Y-%m-%d %H:%M:%S")

# Cloud-init defaults
DEFAULT_CLOUD_INIT_USER = os.getenv("DEFAULT_CLOUD_INIT_USER", "ubuntu")
DEFAULT_CLOUD_INIT_TIMEZONE = os.getenv("DEFAULT_CLOUD_INIT_TIMEZONE", "UTC")
DEFAULT_CLOUD_INIT_LOCALE = os.getenv("DEFAULT_CLOUD_INIT_LOCALE", "en_US.UTF-8")

# Ensure eggs library directory exists
EGGS_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
