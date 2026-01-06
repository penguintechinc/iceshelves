"""Cluster Management REST API Endpoints.

This module provides REST API endpoints for managing Kubernetes clusters,
including listing, creating, updating, deleting, and health checking clusters.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from flask import Blueprint, g, jsonify, request

from ..middleware import admin_required, auth_required, maintainer_or_admin_required
from .models import (
    VALID_CLOUD_PROVIDERS,
    get_cluster_by_id,
    get_cluster_by_name,
    get_default_cluster,
    get_deployed_apps_by_cluster,
    list_clusters,
)

clusters_bp = Blueprint("clusters", __name__, url_prefix="/clusters")


@dataclass(slots=True)
class CreateClusterRequest:
    """Request DTO for creating a new cluster."""
    name: str
    display_name: str
    context_name: str
    cloud_provider: str
    kubeconfig: str
    region: Optional[str] = None
    k8s_version: Optional[str] = None
    is_default: bool = False


@dataclass(slots=True)
class UpdateClusterRequest:
    """Request DTO for updating a cluster."""
    display_name: Optional[str] = None
    context_name: Optional[str] = None
    region: Optional[str] = None
    k8s_version: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


@dataclass(slots=True)
class ClusterResponse:
    """Response DTO for cluster data."""
    id: int
    name: str
    display_name: str
    context_name: str
    cloud_provider: str
    region: Optional[str]
    k8s_version: Optional[str]
    is_default: bool
    is_active: bool
    last_health_check: Optional[str]
    detected_ingress: Optional[str]
    detected_storage_classes: Optional[dict]
    created_at: str
    updated_at: str


@dataclass(slots=True)
class HealthCheckResponse:
    """Response DTO for health check result."""
    cluster_id: int
    cluster_name: str
    status: str
    last_check_time: str
    message: str


@dataclass(slots=True)
class NamespaceResponse:
    """Response DTO for namespace data."""
    name: str
    app_count: int
    status: str


def _serialize_cluster(cluster: dict) -> dict:
    """Serialize cluster record to JSON-safe format."""
    return {
        "id": cluster.get("id"),
        "name": cluster.get("name"),
        "display_name": cluster.get("display_name"),
        "context_name": cluster.get("context_name"),
        "cloud_provider": cluster.get("cloud_provider"),
        "region": cluster.get("region"),
        "k8s_version": cluster.get("k8s_version"),
        "is_default": cluster.get("is_default", False),
        "is_active": cluster.get("is_active", True),
        "last_health_check": (
            cluster.get("last_health_check").isoformat()
            if cluster.get("last_health_check")
            else None
        ),
        "detected_ingress": cluster.get("detected_ingress"),
        "detected_storage_classes": cluster.get("detected_storage_classes"),
        "created_at": (
            cluster.get("created_at").isoformat()
            if cluster.get("created_at")
            else None
        ),
        "updated_at": (
            cluster.get("updated_at").isoformat()
            if cluster.get("updated_at")
            else None
        ),
    }


@clusters_bp.route("", methods=["GET"])
@auth_required
def list_all_clusters():
    """List all clusters with optional filtering.

    Query parameters:
        - active_only (bool): Filter to active clusters only (default: true)
        - page (int): Page number for pagination (default: 1)
        - per_page (int): Results per page (default: 20, max: 100)

    Returns:
        JSON response with clusters list and pagination info.
    """
    active_only = request.args.get("active_only", "true").lower() == "true"
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    # Limit per_page to reasonable bounds
    per_page = min(max(per_page, 1), 100)

    db = g.db
    all_clusters = list_clusters(db, active_only=active_only)

    # Pagination
    start = (page - 1) * per_page
    end = start + per_page
    paginated = all_clusters[start:end]

    clusters_data = [_serialize_cluster(c) for c in paginated]

    return jsonify({
        "clusters": clusters_data,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": len(all_clusters),
            "pages": (len(all_clusters) + per_page - 1) // per_page,
        },
    }), 200


@clusters_bp.route("/<int:cluster_id>", methods=["GET"])
@auth_required
def get_cluster(cluster_id: int):
    """Get cluster by ID.

    Args:
        cluster_id: The cluster ID to retrieve.

    Returns:
        JSON response with cluster details or 404 if not found.
    """
    db = g.db
    cluster = get_cluster_by_id(db, cluster_id)

    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404

    return jsonify(_serialize_cluster(cluster)), 200


@clusters_bp.route("", methods=["POST"])
@auth_required
@admin_required
def create_cluster():
    """Create a new cluster (Admin only).

    Required fields:
        - name: Unique cluster identifier
        - display_name: Human-readable cluster name
        - context_name: Kubernetes context name
        - cloud_provider: One of aws, gcp, azure, generic
        - kubeconfig: Base64-encoded kubeconfig content

    Optional fields:
        - region: Cloud region
        - k8s_version: Kubernetes version
        - is_default: Set as default cluster

    Returns:
        JSON response with created cluster (201) or validation errors (400).
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    # Required field validation
    name = data.get("name", "").strip()
    display_name = data.get("display_name", "").strip()
    context_name = data.get("context_name", "").strip()
    cloud_provider = data.get("cloud_provider", "").strip().lower()
    kubeconfig = data.get("kubeconfig", "").strip()

    if not name:
        return jsonify({"error": "Cluster name is required"}), 400

    if not display_name:
        return jsonify({"error": "Display name is required"}), 400

    if not context_name:
        return jsonify({"error": "Context name is required"}), 400

    if not cloud_provider:
        return jsonify({"error": "Cloud provider is required"}), 400

    if cloud_provider not in VALID_CLOUD_PROVIDERS:
        return jsonify({
            "error": f"Invalid cloud provider. Must be one of: "
                     f"{', '.join(VALID_CLOUD_PROVIDERS)}"
        }), 400

    if not kubeconfig:
        return jsonify({"error": "Kubeconfig is required"}), 400

    # Check for duplicate cluster name
    db = g.db
    existing = get_cluster_by_name(db, name)
    if existing:
        return jsonify({"error": "Cluster name already exists"}), 409

    # Optional fields
    region = data.get("region", "").strip() or None
    k8s_version = data.get("k8s_version", "").strip() or None
    is_default = bool(data.get("is_default", False))

    # If setting as default, unset other default clusters
    if is_default:
        db(db.clusters.is_default == True).update(is_default=False)

    # Create cluster record
    current_user = g.current_user
    cluster_id = db.clusters.insert(
        name=name,
        display_name=display_name,
        context_name=context_name,
        cloud_provider=cloud_provider,
        region=region,
        k8s_version=k8s_version,
        is_default=is_default,
        is_active=True,
        kubeconfig_encrypted=kubeconfig,
        created_by=current_user["id"],
    )
    db.commit()

    cluster = get_cluster_by_id(db, cluster_id)

    return jsonify({
        "message": "Cluster created successfully",
        "cluster": _serialize_cluster(cluster),
    }), 201


@clusters_bp.route("/<int:cluster_id>", methods=["PUT"])
@auth_required
@admin_required
def update_cluster(cluster_id: int):
    """Update cluster by ID (Admin only).

    Args:
        cluster_id: The cluster ID to update.

    Optional update fields:
        - display_name: Human-readable name
        - context_name: Kubernetes context name
        - region: Cloud region
        - k8s_version: Kubernetes version
        - is_default: Set as default cluster
        - is_active: Active status

    Returns:
        JSON response with updated cluster (200) or errors (400/404).
    """
    db = g.db
    cluster = get_cluster_by_id(db, cluster_id)

    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404

    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    update_data = {}

    # Display name update
    if "display_name" in data:
        display_name = data["display_name"].strip()
        if display_name:
            update_data["display_name"] = display_name

    # Context name update
    if "context_name" in data:
        context_name = data["context_name"].strip()
        if context_name:
            update_data["context_name"] = context_name

    # Region update
    if "region" in data:
        region = data["region"].strip() or None
        update_data["region"] = region

    # Kubernetes version update
    if "k8s_version" in data:
        k8s_version = data["k8s_version"].strip() or None
        update_data["k8s_version"] = k8s_version

    # Default cluster update
    if "is_default" in data:
        is_default = bool(data["is_default"])
        if is_default and not cluster.get("is_default"):
            # Unset other default clusters
            db(db.clusters.is_default == True).update(is_default=False)
        update_data["is_default"] = is_default

    # Active status update
    if "is_active" in data:
        update_data["is_active"] = bool(data["is_active"])

    if not update_data:
        return jsonify({"error": "No valid fields to update"}), 400

    update_data["updated_at"] = datetime.utcnow()

    db(db.clusters.id == cluster_id).update(**update_data)
    db.commit()

    updated_cluster = get_cluster_by_id(db, cluster_id)

    return jsonify({
        "message": "Cluster updated successfully",
        "cluster": _serialize_cluster(updated_cluster),
    }), 200


@clusters_bp.route("/<int:cluster_id>", methods=["DELETE"])
@auth_required
@admin_required
def delete_cluster(cluster_id: int):
    """Delete cluster by ID (Admin only).

    Args:
        cluster_id: The cluster ID to delete.

    Returns:
        JSON response confirming deletion (200) or error (404).
    """
    db = g.db
    cluster = get_cluster_by_id(db, cluster_id)

    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404

    # Soft delete: mark as inactive
    db(db.clusters.id == cluster_id).update(
        is_active=False,
        updated_at=datetime.utcnow(),
    )
    db.commit()

    return jsonify({"message": "Cluster deleted successfully"}), 200


@clusters_bp.route("/<int:cluster_id>/health", methods=["POST"])
@auth_required
@maintainer_or_admin_required
def trigger_health_check(cluster_id: int):
    """Trigger health check for a cluster (Maintainer+).

    This endpoint initiates a health check of the specified cluster.
    The actual health check logic should be handled by a background task.

    Args:
        cluster_id: The cluster ID to health check.

    Returns:
        JSON response with health check status (200/202) or error (404).
    """
    db = g.db
    cluster = get_cluster_by_id(db, cluster_id)

    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404

    # Update last_health_check timestamp
    db(db.clusters.id == cluster_id).update(
        last_health_check=datetime.utcnow(),
    )
    db.commit()

    # In production, this would queue a background task
    # to perform actual health checks against the cluster

    return jsonify({
        "message": "Health check initiated",
        "cluster_id": cluster_id,
        "cluster_name": cluster.get("name"),
        "status": "pending",
        "last_check_time": datetime.utcnow().isoformat(),
    }), 202


@clusters_bp.route("/<int:cluster_id>/namespaces", methods=["GET"])
@auth_required
def list_namespaces(cluster_id: int):
    """List namespaces and deployed apps in a cluster.

    Args:
        cluster_id: The cluster ID to list namespaces for.

    Returns:
        JSON response with namespaces and app counts (200) or error (404).
    """
    db = g.db
    cluster = get_cluster_by_id(db, cluster_id)

    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404

    # Get all deployed apps in this cluster
    deployed_apps = get_deployed_apps_by_cluster(db, cluster_id)

    # Group apps by namespace
    namespaces = {}
    for app in deployed_apps:
        ns = app.get("namespace", "default")
        if ns not in namespaces:
            namespaces[ns] = {
                "name": ns,
                "app_count": 0,
                "status": "active",
            }
        namespaces[ns]["app_count"] += 1

    # If no apps, return at least common namespaces
    if not namespaces:
        namespaces = {
            "default": {"name": "default", "app_count": 0, "status": "active"},
            "kube-system": {"name": "kube-system", "app_count": 0, "status": "active"},
            "kube-public": {"name": "kube-public", "app_count": 0, "status": "active"},
        }

    namespace_list = sorted(
        namespaces.values(),
        key=lambda x: x["name"],
    )

    return jsonify({
        "cluster_id": cluster_id,
        "cluster_name": cluster.get("name"),
        "namespaces": namespace_list,
        "total_namespaces": len(namespace_list),
    }), 200
