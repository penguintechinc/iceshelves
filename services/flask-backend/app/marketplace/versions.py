"""Version Tracking and Management Endpoints."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from flask import Blueprint, jsonify, request
from pydal import DAL

from ..middleware import auth_required, get_current_user, maintainer_or_admin_required
from .models import (
    VALID_UPDATE_URGENCIES,
    get_cluster_by_id,
    get_default_cluster,
    get_version_updates,
    list_clusters,
)

versions_bp = Blueprint("versions", __name__, url_prefix="/versions")


@dataclass(slots=True)
class VersionInfo:
    """Version information dataclass."""

    resource_type: str
    resource_name: str
    current_version: str
    latest_version: str
    update_available: bool
    update_urgency: Optional[str] = None
    release_notes_url: Optional[str] = None
    last_checked: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "resource_type": self.resource_type,
            "resource_name": self.resource_name,
            "current_version": self.current_version,
            "latest_version": self.latest_version,
            "update_available": self.update_available,
            "update_urgency": self.update_urgency,
            "release_notes_url": self.release_notes_url,
            "last_checked": self.last_checked.isoformat()
            if self.last_checked
            else None,
        }


@dataclass(slots=True)
class KubernetesVersionInfo:
    """Kubernetes cluster version information dataclass."""

    cluster_name: str
    cluster_id: int
    k8s_version: str
    latest_k8s_version: Optional[str] = None
    update_available: bool = False
    update_urgency: Optional[str] = None
    last_health_check: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "cluster_name": self.cluster_name,
            "cluster_id": self.cluster_id,
            "k8s_version": self.k8s_version,
            "latest_k8s_version": self.latest_k8s_version,
            "update_available": self.update_available,
            "update_urgency": self.update_urgency,
            "last_health_check": self.last_health_check.isoformat()
            if self.last_health_check
            else None,
        }


@dataclass(slots=True)
class AddonVersionInfo:
    """Addon version information dataclass."""

    addon_name: str
    addon_type: str
    current_version: str
    latest_version: Optional[str] = None
    update_available: bool = False
    update_urgency: Optional[str] = None
    cluster_id: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "addon_name": self.addon_name,
            "addon_type": self.addon_type,
            "current_version": self.current_version,
            "latest_version": self.latest_version,
            "update_available": self.update_available,
            "update_urgency": self.update_urgency,
            "cluster_id": self.cluster_id,
        }


def get_db() -> DAL:
    """Get database instance from Flask app context."""
    from flask import current_app

    return current_app.config.get("db")


@versions_bp.route("", methods=["GET"])
@auth_required
def get_all_versions():
    """Get all version tracking information (auth required)."""
    db = get_db()
    cluster_id = request.args.get("cluster_id", type=int)

    try:
        query = db.version_tracking.id > 0
        if cluster_id:
            query &= db.version_tracking.cluster_id == cluster_id

        versions = db(query).select(orderby=~db.version_tracking.last_checked)

        version_list = []
        for v in versions:
            version_list.append(
                VersionInfo(
                    resource_type=v.resource_type,
                    resource_name=v.resource_name,
                    current_version=v.current_version,
                    latest_version=v.latest_version,
                    update_available=v.update_available,
                    update_urgency=v.update_urgency,
                    release_notes_url=v.release_notes_url,
                    last_checked=v.last_checked,
                ).to_dict()
            )

        return jsonify({"versions": version_list, "total": len(version_list)}), 200

    except Exception as e:
        return (
            jsonify({"error": f"Failed to retrieve versions: {str(e)}"}),
            500,
        )


@versions_bp.route("/kubernetes", methods=["GET"])
@auth_required
def get_kubernetes_versions():
    """Get Kubernetes version information for all clusters (auth required)."""
    db = get_db()

    try:
        clusters = list_clusters(db, active_only=True)

        k8s_versions = []
        for cluster in clusters:
            # Get K8s version update info if available
            k8s_update = db(
                (db.version_tracking.cluster_id == cluster["id"])
                & (db.version_tracking.resource_type == "kubernetes")
            ).select().first()

            k8s_version_info = KubernetesVersionInfo(
                cluster_name=cluster["name"],
                cluster_id=cluster["id"],
                k8s_version=cluster.get("k8s_version", "unknown"),
                latest_k8s_version=k8s_update.latest_version
                if k8s_update
                else None,
                update_available=k8s_update.update_available if k8s_update else False,
                update_urgency=k8s_update.update_urgency if k8s_update else None,
                last_health_check=cluster.get("last_health_check"),
            )
            k8s_versions.append(k8s_version_info.to_dict())

        return jsonify({"kubernetes_versions": k8s_versions}), 200

    except Exception as e:
        return (
            jsonify(
                {"error": f"Failed to retrieve Kubernetes versions: {str(e)}"}
            ),
            500,
        )


@versions_bp.route("/addons", methods=["GET"])
@auth_required
def get_addon_versions():
    """Get addon version information (auth required)."""
    db = get_db()
    cluster_id = request.args.get("cluster_id", type=int)

    try:
        query = (db.version_tracking.resource_type.startswith("addon")) | (
            db.version_tracking.resource_type == "addon"
        )

        if cluster_id:
            query &= db.version_tracking.cluster_id == cluster_id

        addons = db(query).select(orderby=db.version_tracking.resource_name)

        addon_list = []
        for addon in addons:
            addon_info = AddonVersionInfo(
                addon_name=addon.resource_name,
                addon_type=addon.resource_type,
                current_version=addon.current_version,
                latest_version=addon.latest_version,
                update_available=addon.update_available,
                update_urgency=addon.update_urgency,
                cluster_id=addon.cluster_id,
            )
            addon_list.append(addon_info.to_dict())

        return jsonify({"addons": addon_list, "total": len(addon_list)}), 200

    except Exception as e:
        return (
            jsonify({"error": f"Failed to retrieve addon versions: {str(e)}"}),
            500,
        )


@versions_bp.route("/updates", methods=["GET"])
@auth_required
def get_available_updates():
    """Get available updates with filtering options (auth required)."""
    db = get_db()
    cluster_id = request.args.get("cluster_id", type=int)
    resource_type = request.args.get("resource_type", type=str)
    urgency_filter = request.args.get("urgency", type=str)

    try:
        # Get updates from model function
        updates = get_version_updates(
            db, cluster_id=cluster_id, resource_type=resource_type
        )

        # Filter by urgency if specified
        if urgency_filter:
            if urgency_filter not in VALID_UPDATE_URGENCIES:
                return (
                    jsonify(
                        {
                            "error": f"Invalid urgency. Must be one of: {', '.join(VALID_UPDATE_URGENCIES)}"
                        }
                    ),
                    400,
                )
            updates = [u for u in updates if u.get("update_urgency") == urgency_filter]

        # Group by urgency level
        by_urgency = {"critical": [], "high": [], "medium": [], "low": []}
        for update in updates:
            urgency = update.get("update_urgency", "low")
            if urgency in by_urgency:
                by_urgency[urgency].append(update)

        return (
            jsonify(
                {
                    "total_updates": len(updates),
                    "by_urgency": by_urgency,
                    "updates": updates,
                }
            ),
            200,
        )

    except Exception as e:
        return (
            jsonify({"error": f"Failed to retrieve updates: {str(e)}"}),
            500,
        )


@versions_bp.route("/check", methods=["POST"])
@auth_required
@maintainer_or_admin_required
def force_version_check():
    """Force version check for specified clusters/resources (maintainer+ only)."""
    db = get_db()
    current_user = get_current_user()
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    cluster_ids = data.get("cluster_ids", [])
    resource_types = data.get("resource_types", [])

    if not cluster_ids and not resource_types:
        return (
            jsonify(
                {
                    "error": "At least one of cluster_ids or resource_types must be provided"
                }
            ),
            400,
        )

    try:
        # Query for records to check
        query = db.version_tracking.id > 0

        if cluster_ids:
            if not isinstance(cluster_ids, list):
                cluster_ids = [cluster_ids]
            query &= db.version_tracking.cluster_id.belongs(cluster_ids)

        if resource_types:
            if not isinstance(resource_types, list):
                resource_types = [resource_types]
            # Match resource types that start with or equal the specified types
            type_query = None
            for rt in resource_types:
                if type_query is None:
                    type_query = db.version_tracking.resource_type == rt
                else:
                    type_query |= db.version_tracking.resource_type == rt
            if type_query:
                query &= type_query

        # Update last_checked timestamp
        records = db(query).select()
        updated_count = 0

        for record in records:
            record.update_record(last_checked=datetime.utcnow())
            updated_count += 1

        db.commit()

        return (
            jsonify(
                {
                    "message": f"Version check triggered for {updated_count} records",
                    "updated_count": updated_count,
                    "triggered_by": current_user.get("email"),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            202,
        )

    except Exception as e:
        db.rollback()
        return (
            jsonify({"error": f"Failed to trigger version check: {str(e)}"}),
            500,
        )
