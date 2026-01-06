"""Marketplace PyDAL Database Models.

This module defines the database tables for the IceShelves marketplace feature,
including clusters, Helm repositories, Docker registries, apps, deployments,
version tracking, and notification systems.
"""

from datetime import datetime
from typing import Optional

from pydal import DAL, Field
from pydal.validators import IS_IN_SET, IS_NOT_EMPTY, IS_URL

# Valid values for various fields
VALID_SOURCE_TYPES = ["helm", "docker", "aws", "gcp", "manifest"]
VALID_CLOUD_PROVIDERS = ["aws", "gcp", "azure", "generic"]
VALID_DEPLOYMENT_STATUSES = [
    "pending", "deploying", "running", "failed", "deleted", "degraded", "unknown"
]
VALID_DEPENDENCY_TYPES = ["database", "cache", "storage", "messaging"]
VALID_AUTH_TYPES = ["none", "basic", "bearer", "token"]
VALID_HELM_VERSIONS = ["v2", "v3"]
VALID_REGISTRY_TYPES = ["dockerhub", "ghcr", "ecr", "gcr", "acr", "quay", "custom"]
VALID_WEBHOOK_TYPES = ["slack", "discord", "teams", "generic"]
VALID_UPDATE_URGENCIES = ["critical", "high", "medium", "low"]
VALID_EMAIL_FREQUENCIES = ["realtime", "hourly", "daily", "weekly"]


def define_marketplace_tables(db: DAL) -> None:
    """Define all marketplace-related database tables.

    Args:
        db: PyDAL database connection instance.
    """
    # Kubernetes clusters (multi-cluster support)
    db.define_table(
        "clusters",
        Field("name", "string", length=100, unique=True,
              requires=IS_NOT_EMPTY(error_message="Cluster name is required")),
        Field("display_name", "string", length=200),
        Field("kubeconfig_encrypted", "text"),
        Field("context_name", "string", length=100),
        Field("cloud_provider", "string", length=50, default="generic",
              requires=IS_IN_SET(VALID_CLOUD_PROVIDERS)),
        Field("region", "string", length=50),
        Field("k8s_version", "string", length=20),
        Field("is_default", "boolean", default=False),
        Field("is_active", "boolean", default=True),
        Field("last_health_check", "datetime"),
        Field("detected_ingress", "string", length=100),
        Field("detected_storage_classes", "json"),
        Field("created_by", "reference users"),
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", default=datetime.utcnow,
              update=datetime.utcnow),
    )

    # Helm repositories
    db.define_table(
        "helm_repositories",
        Field("name", "string", length=100, unique=True,
              requires=IS_NOT_EMPTY(error_message="Repository name is required")),
        Field("url", "string", length=500,
              requires=[IS_NOT_EMPTY(), IS_URL(error_message="Invalid URL")]),
        Field("description", "text"),
        Field("category", "string", length=50),
        Field("is_builtin", "boolean", default=False),
        Field("is_enabled", "boolean", default=True),
        Field("helm_version", "string", length=10, default="v3",
              requires=IS_IN_SET(VALID_HELM_VERSIONS)),
        Field("auth_type", "string", length=20, default="none",
              requires=IS_IN_SET(VALID_AUTH_TYPES)),
        Field("auth_username", "string", length=255),
        Field("auth_password_encrypted", "text"),
        Field("last_synced", "datetime"),
        Field("chart_count", "integer", default=0),
        Field("created_by", "reference users"),
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", default=datetime.utcnow,
              update=datetime.utcnow),
    )

    # Docker registries
    db.define_table(
        "docker_registries",
        Field("name", "string", length=100, unique=True,
              requires=IS_NOT_EMPTY(error_message="Registry name is required")),
        Field("url", "string", length=500,
              requires=[IS_NOT_EMPTY(), IS_URL(error_message="Invalid URL")]),
        Field("registry_type", "string", length=50, default="custom",
              requires=IS_IN_SET(VALID_REGISTRY_TYPES)),
        Field("is_builtin", "boolean", default=False),
        Field("is_enabled", "boolean", default=True),
        Field("auth_type", "string", length=20, default="none",
              requires=IS_IN_SET(VALID_AUTH_TYPES)),
        Field("auth_username", "string", length=255),
        Field("auth_password_encrypted", "text"),
        Field("created_by", "reference users"),
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", default=datetime.utcnow,
              update=datetime.utcnow),
    )

    # Cached app metadata from all sources
    db.define_table(
        "marketplace_apps",
        Field("source_type", "string", length=20,
              requires=IS_IN_SET(VALID_SOURCE_TYPES)),
        Field("source_id", "integer"),
        Field("app_name", "string", length=200,
              requires=IS_NOT_EMPTY(error_message="App name is required")),
        Field("app_version", "string", length=50),
        Field("latest_version", "string", length=50),
        Field("description", "text"),
        Field("icon_url", "string", length=500),
        Field("home_url", "string", length=500),
        Field("category", "string", length=100),
        Field("tags", "json"),
        Field("maintainers", "json"),
        Field("dependencies", "json"),
        Field("values_schema", "json"),
        Field("metadata", "json"),
        Field("is_deprecated", "boolean", default=False),
        Field("last_synced", "datetime"),
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", default=datetime.utcnow,
              update=datetime.utcnow),
    )

    # Deployed applications
    db.define_table(
        "deployed_apps",
        Field("name", "string", length=100,
              requires=IS_NOT_EMPTY(error_message="Deployment name is required")),
        Field("k8s_namespace", "string", length=100,
              requires=IS_NOT_EMPTY(error_message="Namespace is required")),
        Field("cluster_id", "reference clusters"),
        Field("app_id", "reference marketplace_apps"),
        Field("source_type", "string", length=20,
              requires=IS_IN_SET(VALID_SOURCE_TYPES)),
        Field("installed_version", "string", length=50),
        Field("deployed_values", "json"),
        Field("deployed_manifests", "json"),
        Field("status", "string", length=50, default="pending",
              requires=IS_IN_SET(VALID_DEPLOYMENT_STATUSES)),
        Field("health_status", "string", length=50),
        Field("last_health_check", "datetime"),
        Field("replicas_desired", "integer", default=1),
        Field("replicas_ready", "integer", default=0),
        Field("replicas_available", "integer", default=0),
        Field("cpu_usage", "string", length=20),
        Field("memory_usage", "string", length=20),
        Field("deployed_by", "reference users"),
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", default=datetime.utcnow,
              update=datetime.utcnow),
    )

    # App dependencies (databases, caches, etc.)
    db.define_table(
        "app_dependencies",
        Field("deployed_app_id", "reference deployed_apps"),
        Field("dependency_type", "string", length=50,
              requires=IS_IN_SET(VALID_DEPENDENCY_TYPES)),
        Field("dependency_name", "string", length=100),
        Field("provider", "string", length=50),
        Field("connection_string_encrypted", "text"),
        Field("config", "json"),
        Field("is_managed", "boolean", default=False),
        Field("managed_service_id", "string", length=200),
        Field("created_at", "datetime", default=datetime.utcnow),
    )

    # Version tracking for K8s, addons, and apps
    db.define_table(
        "version_tracking",
        Field("cluster_id", "reference clusters"),
        Field("resource_type", "string", length=50),
        Field("resource_name", "string", length=200),
        Field("resource_id", "integer"),
        Field("current_version", "string", length=50),
        Field("latest_version", "string", length=50),
        Field("update_available", "boolean", default=False),
        Field("update_urgency", "string", length=20,
              requires=IS_IN_SET(VALID_UPDATE_URGENCIES + [None])),
        Field("release_notes_url", "string", length=500),
        Field("last_checked", "datetime"),
        Field("metadata", "json"),
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", default=datetime.utcnow,
              update=datetime.utcnow),
    )

    # User notification preferences
    db.define_table(
        "notification_preferences",
        Field("user_id", "reference users", unique=True),
        Field("email_enabled", "boolean", default=True),
        Field("email_frequency", "string", length=20, default="daily",
              requires=IS_IN_SET(VALID_EMAIL_FREQUENCIES)),
        Field("in_app_enabled", "boolean", default=True),
        Field("critical_updates_only", "boolean", default=False),
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", default=datetime.utcnow,
              update=datetime.utcnow),
    )

    # Webhook configurations for notifications
    db.define_table(
        "notification_webhooks",
        Field("name", "string", length=100,
              requires=IS_NOT_EMPTY(error_message="Webhook name is required")),
        Field("url", "string", length=500,
              requires=[IS_NOT_EMPTY(), IS_URL(error_message="Invalid URL")]),
        Field("webhook_type", "string", length=50, default="generic",
              requires=IS_IN_SET(VALID_WEBHOOK_TYPES)),
        Field("secret_encrypted", "text"),
        Field("is_enabled", "boolean", default=True),
        Field("events", "json"),
        Field("last_triggered", "datetime"),
        Field("last_status_code", "integer"),
        Field("failure_count", "integer", default=0),
        Field("created_by", "reference users"),
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", default=datetime.utcnow,
              update=datetime.utcnow),
    )

    # MarchProxy configurations per cluster
    db.define_table(
        "marchproxy_configs",
        Field("cluster_id", "reference clusters"),
        Field("api_endpoint", "string", length=500),
        Field("api_key_encrypted", "text"),
        Field("auto_apply", "boolean", default=False),
        Field("is_enabled", "boolean", default=True),
        Field("last_sync", "datetime"),
        Field("created_by", "reference users"),
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", default=datetime.utcnow,
              update=datetime.utcnow),
    )

    # Deployment wizard sessions (temporary state)
    db.define_table(
        "wizard_sessions",
        Field("session_id", "string", length=64, unique=True),
        Field("wizard_type", "string", length=50),
        Field("user_id", "reference users"),
        Field("cluster_id", "reference clusters"),
        Field("app_id", "reference marketplace_apps"),
        Field("current_step", "integer", default=1),
        Field("wizard_state", "json"),
        Field("expires_at", "datetime"),
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", default=datetime.utcnow,
              update=datetime.utcnow),
    )


# Helper functions for marketplace models

def get_cluster_by_id(db: DAL, cluster_id: int) -> Optional[dict]:
    """Get cluster by ID."""
    cluster = db(db.clusters.id == cluster_id).select().first()
    return cluster.as_dict() if cluster else None


def get_cluster_by_name(db: DAL, name: str) -> Optional[dict]:
    """Get cluster by name."""
    cluster = db(db.clusters.name == name).select().first()
    return cluster.as_dict() if cluster else None


def list_clusters(db: DAL, active_only: bool = True) -> list[dict]:
    """List all clusters."""
    query = db.clusters.is_active == True if active_only else db.clusters.id > 0
    clusters = db(query).select(orderby=db.clusters.name)
    return [c.as_dict() for c in clusters]


def get_default_cluster(db: DAL) -> Optional[dict]:
    """Get the default cluster."""
    cluster = db(
        (db.clusters.is_default == True) &
        (db.clusters.is_active == True)
    ).select().first()
    return cluster.as_dict() if cluster else None


def list_helm_repositories(
    db: DAL,
    enabled_only: bool = True,
    include_builtin: bool = True
) -> list[dict]:
    """List Helm repositories."""
    query = db.helm_repositories.id > 0
    if enabled_only:
        query &= db.helm_repositories.is_enabled == True
    if not include_builtin:
        query &= db.helm_repositories.is_builtin == False

    repos = db(query).select(orderby=db.helm_repositories.name)
    return [r.as_dict() for r in repos]


def list_docker_registries(
    db: DAL,
    enabled_only: bool = True,
    include_builtin: bool = True
) -> list[dict]:
    """List Docker registries."""
    query = db.docker_registries.id > 0
    if enabled_only:
        query &= db.docker_registries.is_enabled == True
    if not include_builtin:
        query &= db.docker_registries.is_builtin == False

    registries = db(query).select(orderby=db.docker_registries.name)
    return [r.as_dict() for r in registries]


def get_deployed_apps_by_cluster(
    db: DAL,
    cluster_id: int,
    k8s_namespace: Optional[str] = None
) -> list[dict]:
    """Get deployed apps for a cluster, optionally filtered by namespace."""
    query = db.deployed_apps.cluster_id == cluster_id
    if k8s_namespace:
        query &= db.deployed_apps.k8s_namespace == k8s_namespace

    apps = db(query).select(orderby=db.deployed_apps.name)
    return [a.as_dict() for a in apps]


def get_inventory_summary(db: DAL, cluster_id: Optional[int] = None) -> dict:
    """Get inventory summary statistics."""
    query = db.deployed_apps.id > 0
    if cluster_id:
        query &= db.deployed_apps.cluster_id == cluster_id

    total = db(query).count()
    running = db(query & (db.deployed_apps.status == "running")).count()
    failed = db(query & (db.deployed_apps.status == "failed")).count()
    deploying = db(query & (db.deployed_apps.status == "deploying")).count()
    pending = db(query & (db.deployed_apps.status == "pending")).count()
    degraded = db(query & (db.deployed_apps.status == "degraded")).count()

    # Count apps with updates available
    updates_available = db(
        (db.version_tracking.resource_type == "app") &
        (db.version_tracking.update_available == True)
    ).count()

    return {
        "total_apps": total,
        "running": running,
        "failed": failed,
        "deploying": deploying,
        "pending": pending,
        "degraded": degraded,
        "updates_available": updates_available,
    }


def get_version_updates(
    db: DAL,
    cluster_id: Optional[int] = None,
    resource_type: Optional[str] = None
) -> list[dict]:
    """Get available version updates."""
    query = db.version_tracking.update_available == True
    if cluster_id:
        query &= db.version_tracking.cluster_id == cluster_id
    if resource_type:
        query &= db.version_tracking.resource_type == resource_type

    updates = db(query).select(orderby=~db.version_tracking.last_checked)
    return [u.as_dict() for u in updates]
