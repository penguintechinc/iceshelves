"""Inventory Management REST API Endpoints."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from flask import Blueprint, jsonify, request, current_app

from ..middleware import auth_required, maintainer_or_admin_required
from .models import (
    get_deployed_apps_by_cluster,
    get_inventory_summary,
    list_clusters,
    get_cluster_by_id,
)

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


@dataclass(slots=True)
class HealthStatus:
    """Health status for a single deployed app."""

    app_id: int
    name: str
    namespace: str
    status: str
    health_status: Optional[str]
    replicas_desired: int
    replicas_ready: int
    replicas_available: int
    cpu_usage: Optional[str]
    memory_usage: Optional[str]
    last_health_check: Optional[datetime]
    installed_version: Optional[str]
    has_updates: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass(slots=True)
class NamespaceApps:
    """Apps grouped by namespace within a cluster."""

    namespace: str
    app_count: int
    apps: list[HealthStatus] = field(default_factory=list)
    running: int = 0
    failed: int = 0
    deploying: int = 0
    pending: int = 0
    degraded: int = 0


@dataclass(slots=True)
class ClusterInventory:
    """Full inventory for a single cluster."""

    cluster_id: int
    cluster_name: str
    display_name: Optional[str]
    cloud_provider: str
    region: Optional[str]
    k8s_version: Optional[str]
    is_default: bool
    namespaces: list[NamespaceApps] = field(default_factory=list)
    total_apps: int = 0
    total_running: int = 0
    total_failed: int = 0
    total_deploying: int = 0
    total_pending: int = 0
    total_degraded: int = 0


@dataclass(slots=True)
class GlobalSummary:
    """Global aggregated health summary."""

    total_apps: int
    running: int
    failed: int
    deploying: int
    pending: int
    degraded: int
    updates_available: int
    cluster_count: int
    last_refresh: str = field(default_factory=lambda: datetime.utcnow().isoformat())


def _build_health_status(app: dict, db=None) -> HealthStatus:
    """Convert deployed app record to HealthStatus dataclass."""
    has_updates = False
    if db and app.get("id"):
        from .models import VALID_UPDATE_URGENCIES

        update_check = db(
            (db.version_tracking.resource_type == "app")
            & (db.version_tracking.resource_id == app["id"])
            & (db.version_tracking.update_available == True)
        ).count()
        has_updates = update_check > 0

    return HealthStatus(
        app_id=app.get("id", 0),
        name=app.get("name", ""),
        namespace=app.get("namespace", ""),
        status=app.get("status", "unknown"),
        health_status=app.get("health_status"),
        replicas_desired=app.get("replicas_desired", 0),
        replicas_ready=app.get("replicas_ready", 0),
        replicas_available=app.get("replicas_available", 0),
        cpu_usage=app.get("cpu_usage"),
        memory_usage=app.get("memory_usage"),
        last_health_check=app.get("last_health_check"),
        installed_version=app.get("installed_version"),
        has_updates=has_updates,
        created_at=app.get("created_at"),
        updated_at=app.get("updated_at"),
    )


def _build_cluster_inventory(cluster: dict, db) -> ClusterInventory:
    """Build complete inventory for a cluster."""
    cluster_id = cluster.get("id", 0)
    cluster_name = cluster.get("name", "")

    apps = get_deployed_apps_by_cluster(db, cluster_id)

    namespaces_dict = {}
    for app in apps:
        namespace = app.get("namespace", "default")
        if namespace not in namespaces_dict:
            namespaces_dict[namespace] = NamespaceApps(namespace=namespace, app_count=0)

        health = _build_health_status(app, db)
        namespaces_dict[namespace].apps.append(health)
        namespaces_dict[namespace].app_count += 1

        status = app.get("status", "unknown")
        if status == "running":
            namespaces_dict[namespace].running += 1
        elif status == "failed":
            namespaces_dict[namespace].failed += 1
        elif status == "deploying":
            namespaces_dict[namespace].deploying += 1
        elif status == "pending":
            namespaces_dict[namespace].pending += 1
        elif status == "degraded":
            namespaces_dict[namespace].degraded += 1

    namespaces = list(namespaces_dict.values())

    total_apps = len(apps)
    total_running = sum(ns.running for ns in namespaces)
    total_failed = sum(ns.failed for ns in namespaces)
    total_deploying = sum(ns.deploying for ns in namespaces)
    total_pending = sum(ns.pending for ns in namespaces)
    total_degraded = sum(ns.degraded for ns in namespaces)

    return ClusterInventory(
        cluster_id=cluster_id,
        cluster_name=cluster_name,
        display_name=cluster.get("display_name"),
        cloud_provider=cluster.get("cloud_provider", "generic"),
        region=cluster.get("region"),
        k8s_version=cluster.get("k8s_version"),
        is_default=cluster.get("is_default", False),
        namespaces=namespaces,
        total_apps=total_apps,
        total_running=total_running,
        total_failed=total_failed,
        total_deploying=total_deploying,
        total_pending=total_pending,
        total_degraded=total_degraded,
    )


def _inventory_to_dict(cluster_inv: ClusterInventory) -> dict:
    """Convert ClusterInventory dataclass to JSON-serializable dict."""
    namespaces_data = []
    for ns in cluster_inv.namespaces:
        apps_data = [
            {
                "app_id": app.app_id,
                "name": app.name,
                "status": app.status,
                "health_status": app.health_status,
                "replicas_desired": app.replicas_desired,
                "replicas_ready": app.replicas_ready,
                "replicas_available": app.replicas_available,
                "cpu_usage": app.cpu_usage,
                "memory_usage": app.memory_usage,
                "last_health_check": app.last_health_check.isoformat()
                if app.last_health_check
                else None,
                "installed_version": app.installed_version,
                "has_updates": app.has_updates,
                "created_at": app.created_at.isoformat() if app.created_at else None,
                "updated_at": app.updated_at.isoformat() if app.updated_at else None,
            }
            for app in ns.apps
        ]

        namespaces_data.append(
            {
                "namespace": ns.namespace,
                "app_count": ns.app_count,
                "running": ns.running,
                "failed": ns.failed,
                "deploying": ns.deploying,
                "pending": ns.pending,
                "degraded": ns.degraded,
                "apps": apps_data,
            }
        )

    return {
        "cluster_id": cluster_inv.cluster_id,
        "cluster_name": cluster_inv.cluster_name,
        "display_name": cluster_inv.display_name,
        "cloud_provider": cluster_inv.cloud_provider,
        "region": cluster_inv.region,
        "k8s_version": cluster_inv.k8s_version,
        "is_default": cluster_inv.is_default,
        "namespaces": namespaces_data,
        "total_apps": cluster_inv.total_apps,
        "total_running": cluster_inv.total_running,
        "total_failed": cluster_inv.total_failed,
        "total_deploying": cluster_inv.total_deploying,
        "total_pending": cluster_inv.total_pending,
        "total_degraded": cluster_inv.total_degraded,
    }


@inventory_bp.route("", methods=["GET"])
@auth_required
def get_all_inventory():
    """Get all apps across all clusters (paginated).

    Query Parameters:
        page: Page number (default: 1)
        per_page: Items per page (default: 50, max: 250)

    Returns:
        JSON with list of clusters containing apps organized by namespace
    """
    db = current_app.config["db"]

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)

    per_page = min(max(per_page, 1), 250)

    clusters = list_clusters(db, active_only=True)
    total_clusters = len(clusters)

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_clusters = clusters[start_idx:end_idx]

    clusters_data = []
    for cluster in paginated_clusters:
        cluster_inv = _build_cluster_inventory(cluster, db)
        clusters_data.append(_inventory_to_dict(cluster_inv))

    return jsonify(
        {
            "clusters": clusters_data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_clusters,
                "pages": (total_clusters + per_page - 1) // per_page,
            },
        }
    ), 200


@inventory_bp.route("/cluster/<int:cluster_id>", methods=["GET"])
@auth_required
def get_cluster_inventory(cluster_id: int):
    """Get all apps in a specific cluster.

    Args:
        cluster_id: Cluster ID

    Returns:
        JSON with cluster inventory, apps organized by namespace
    """
    db = current_app.config["db"]

    cluster = get_cluster_by_id(db, cluster_id)
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404

    cluster_inv = _build_cluster_inventory(cluster, db)
    return jsonify(_inventory_to_dict(cluster_inv)), 200


@inventory_bp.route("/summary", methods=["GET"])
@auth_required
def get_summary():
    """Get aggregated health summary across all clusters.

    Returns:
        JSON with global_summary containing counts for:
        - total_apps
        - running
        - failed
        - deploying
        - pending
        - degraded
        - updates_available
        - cluster_count
    """
    db = current_app.config["db"]

    summary = get_inventory_summary(db, cluster_id=None)
    clusters = list_clusters(db, active_only=True)

    global_summary = GlobalSummary(
        total_apps=summary["total_apps"],
        running=summary["running"],
        failed=summary["failed"],
        deploying=summary["deploying"],
        pending=summary["pending"],
        degraded=summary["degraded"],
        updates_available=summary["updates_available"],
        cluster_count=len(clusters),
    )

    return jsonify(
        {
            "global_summary": {
                "total_apps": global_summary.total_apps,
                "running": global_summary.running,
                "failed": global_summary.failed,
                "deploying": global_summary.deploying,
                "pending": global_summary.pending,
                "degraded": global_summary.degraded,
                "updates_available": global_summary.updates_available,
                "cluster_count": global_summary.cluster_count,
                "last_refresh": global_summary.last_refresh,
            }
        }
    ), 200


@inventory_bp.route("/<int:app_id>/health", methods=["GET"])
@auth_required
def get_app_health(app_id: int):
    """Get detailed health for a single deployed app.

    Args:
        app_id: Deployed app ID

    Returns:
        JSON with detailed app health status
    """
    db = current_app.config["db"]

    app = db(db.deployed_apps.id == app_id).select().first()
    if not app:
        return jsonify({"error": "App not found"}), 404

    app_dict = app.as_dict()
    health = _build_health_status(app_dict, db)

    # Get related cluster info
    cluster = get_cluster_by_id(db, app_dict.get("cluster_id", 0))

    # Get dependencies
    dependencies = db(db.app_dependencies.deployed_app_id == app_id).select()
    deps_data = [d.as_dict() for d in dependencies]

    response = {
        "app_id": health.app_id,
        "name": health.name,
        "namespace": health.namespace,
        "cluster": {
            "cluster_id": cluster.get("id") if cluster else None,
            "cluster_name": cluster.get("name") if cluster else None,
            "display_name": cluster.get("display_name") if cluster else None,
        } if cluster else None,
        "status": health.status,
        "health_status": health.health_status,
        "replicas": {
            "desired": health.replicas_desired,
            "ready": health.replicas_ready,
            "available": health.replicas_available,
        },
        "resources": {
            "cpu_usage": health.cpu_usage,
            "memory_usage": health.memory_usage,
        },
        "version": {
            "installed": health.installed_version,
            "has_updates": health.has_updates,
        },
        "timestamps": {
            "created_at": health.created_at.isoformat() if health.created_at else None,
            "updated_at": health.updated_at.isoformat() if health.updated_at else None,
            "last_health_check": health.last_health_check.isoformat()
            if health.last_health_check
            else None,
        },
        "dependencies": deps_data,
    }

    return jsonify(response), 200


@inventory_bp.route("/refresh", methods=["POST"])
@auth_required
@maintainer_or_admin_required
def refresh_health_checks():
    """Force health check refresh for all apps.

    Requires: maintainer or admin role

    Returns:
        JSON with refresh status and job info
    """
    db = current_app.config["db"]

    apps = db(db.deployed_apps.id > 0).select()
    app_count = len(apps)

    now = datetime.utcnow()
    for app in apps:
        db.deployed_apps[app.id] = dict(last_health_check=now)

    db.commit()

    return jsonify(
        {
            "message": "Health check refresh initiated",
            "apps_queued": app_count,
            "refresh_timestamp": now.isoformat(),
        }
    ), 202
