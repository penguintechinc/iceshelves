"""MarchProxy Integration Endpoints (Admin/Maintainer Only)."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import requests
from flask import Blueprint, current_app, g, jsonify, request

from ..middleware import admin_required, auth_required, get_current_user, maintainer_or_admin_required

marchproxy_bp = Blueprint("marchproxy", __name__, url_prefix="/marchproxy")


@dataclass(slots=True)
class MarchProxyConfig:
    """MarchProxy configuration data class."""

    cluster_id: int
    api_endpoint: str
    api_key_encrypted: str
    auto_apply: bool = False
    is_enabled: bool = True
    last_sync: Optional[datetime] = None
    id: Optional[int] = None


@dataclass(slots=True)
class MarchProxyService:
    """MarchProxy service data class."""

    name: str
    api_version: str = "v1"
    metadata: dict = field(default_factory=dict)
    spec: dict = field(default_factory=dict)


@dataclass(slots=True)
class ImportConfig:
    """MarchProxy import configuration data class."""

    cluster_name: str
    services: list = field(default_factory=list)
    timestamp: Optional[datetime] = None
    format_version: str = "1.0"


def get_db():
    """Get database connection from Flask app context."""
    return current_app.config.get("db")


def get_marchproxy_config(cluster_id: int) -> Optional[dict]:
    """Fetch MarchProxy config for a cluster from database."""
    db = get_db()
    if not db:
        return None

    config = db(db.marchproxy_configs.cluster_id == cluster_id).select().first()
    return config.as_dict() if config else None


def save_marchproxy_config(cluster_id: int, api_endpoint: str, api_key: str,
                           auto_apply: bool = False) -> dict:
    """Save or update MarchProxy config in database."""
    db = get_db()
    if not db:
        return {"error": "Database connection unavailable"}

    user = get_current_user()
    existing = db(db.marchproxy_configs.cluster_id == cluster_id).select().first()

    config_data = {
        "api_endpoint": api_endpoint,
        "api_key_encrypted": api_key,
        "auto_apply": auto_apply,
        "is_enabled": True,
        "updated_at": datetime.utcnow(),
    }

    if existing:
        existing.update_record(**config_data)
        return existing.as_dict()
    else:
        config_data["cluster_id"] = cluster_id
        config_data["created_by"] = user["id"] if user else None
        config_data["created_at"] = datetime.utcnow()
        config_id = db.marchproxy_configs.insert(**config_data)
        return db(db.marchproxy_configs.id == config_id).select().first().as_dict()


def generate_import_config(cluster_id: int, services: list) -> dict:
    """Generate MarchProxy import configuration."""
    db = get_db()
    if not db:
        return {"error": "Database connection unavailable"}

    cluster = db(db.clusters.id == cluster_id).select().first()
    if not cluster:
        return {"error": "Cluster not found"}

    # Build import config with deployed apps
    deployed_apps = db(db.deployed_apps.cluster_id == cluster_id).select()

    services_config = []
    for app in deployed_apps:
        app_dict = app.as_dict()
        services_config.append({
            "name": app_dict["name"],
            "namespace": app_dict["namespace"],
            "type": app_dict["source_type"],
            "status": app_dict["status"],
            "replicas": {
                "desired": app_dict.get("replicas_desired", 1),
                "ready": app_dict.get("replicas_ready", 0),
                "available": app_dict.get("replicas_available", 0),
            },
        })

    config = {
        "cluster": cluster.as_dict()["name"],
        "timestamp": datetime.utcnow().isoformat(),
        "format_version": "1.0",
        "services": services_config,
    }

    return config


def apply_config_to_marchproxy(api_endpoint: str, api_key: str,
                               config: dict) -> tuple[bool, str]:
    """Apply configuration to MarchProxy via API."""
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            f"{api_endpoint}/api/v1/services/import",
            json=config,
            headers=headers,
            timeout=30,
        )

        if response.status_code in [200, 201]:
            return True, response.json().get("message", "Config applied successfully")
        else:
            error_msg = response.json().get("error", response.text)
            return False, f"MarchProxy error: {error_msg}"

    except requests.exceptions.ConnectionError as e:
        return False, f"Connection error: {str(e)}"
    except requests.exceptions.Timeout:
        return False, "Request timeout - MarchProxy not responding"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


@marchproxy_bp.route("/config/<int:cluster_id>", methods=["GET"])
@auth_required
@maintainer_or_admin_required
def get_config(cluster_id: int):
    """Get MarchProxy config for a cluster."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database connection unavailable"}), 500

    # Verify cluster exists
    cluster = db(db.clusters.id == cluster_id).select().first()
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404

    config = get_marchproxy_config(cluster_id)

    if not config:
        return jsonify({
            "cluster_id": cluster_id,
            "configured": False,
            "message": "No MarchProxy configuration found",
        }), 200

    # Don't return encrypted API key in full
    config.pop("api_key_encrypted", None)
    config["configured"] = True

    return jsonify(config), 200


@marchproxy_bp.route("/config/<int:cluster_id>", methods=["PUT"])
@auth_required
@admin_required
def update_config(cluster_id: int):
    """Update MarchProxy config for a cluster."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database connection unavailable"}), 500

    # Verify cluster exists
    cluster = db(db.clusters.id == cluster_id).select().first()
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    api_endpoint = data.get("api_endpoint", "").strip()
    api_key = data.get("api_key", "").strip()
    auto_apply = data.get("auto_apply", False)

    # Validate required fields
    if not api_endpoint:
        return jsonify({"error": "api_endpoint is required"}), 400

    if not api_key:
        return jsonify({"error": "api_key is required"}), 400

    if not api_endpoint.startswith("http://") and not api_endpoint.startswith("https://"):
        return jsonify({"error": "api_endpoint must start with http:// or https://"}), 400

    # Save configuration
    config = save_marchproxy_config(
        cluster_id=cluster_id,
        api_endpoint=api_endpoint,
        api_key=api_key,
        auto_apply=bool(auto_apply),
    )

    if "error" in config:
        return jsonify(config), 500

    # Remove encrypted key from response
    config.pop("api_key_encrypted", None)

    return jsonify({
        "message": "MarchProxy configuration updated successfully",
        "config": config,
    }), 200


@marchproxy_bp.route("/generate/<int:cluster_id>", methods=["POST"])
@auth_required
@maintainer_or_admin_required
def generate_config(cluster_id: int):
    """Generate MarchProxy import configuration for a cluster."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database connection unavailable"}), 500

    # Verify cluster exists
    cluster = db(db.clusters.id == cluster_id).select().first()
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404

    data = request.get_json() or {}
    services = data.get("services", [])

    config = generate_import_config(cluster_id, services)

    if "error" in config:
        return jsonify(config), 500

    return jsonify({
        "message": "Import configuration generated successfully",
        "config": config,
    }), 200


@marchproxy_bp.route("/apply/<int:cluster_id>", methods=["POST"])
@auth_required
@admin_required
def apply_config(cluster_id: int):
    """Apply configuration to MarchProxy API."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database connection unavailable"}), 500

    # Verify cluster exists
    cluster = db(db.clusters.id == cluster_id).select().first()
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404

    # Get MarchProxy configuration
    mp_config = get_marchproxy_config(cluster_id)
    if not mp_config:
        return jsonify({"error": "MarchProxy not configured for this cluster"}), 400

    if not mp_config.get("is_enabled"):
        return jsonify({"error": "MarchProxy is disabled for this cluster"}), 400

    # Generate import configuration
    data = request.get_json() or {}
    services = data.get("services", [])

    import_config = generate_import_config(cluster_id, services)
    if "error" in import_config:
        return jsonify(import_config), 500

    # Apply to MarchProxy
    success, message = apply_config_to_marchproxy(
        api_endpoint=mp_config["api_endpoint"],
        api_key=mp_config["api_key_encrypted"],
        config=import_config,
    )

    if not success:
        return jsonify({
            "error": message,
            "cluster_id": cluster_id,
        }), 500

    # Update last_sync timestamp
    db(db.marchproxy_configs.cluster_id == cluster_id).update(
        last_sync=datetime.utcnow()
    )
    db.commit()

    return jsonify({
        "message": message,
        "cluster_id": cluster_id,
        "config": import_config,
    }), 200


@marchproxy_bp.route("/status/<int:cluster_id>", methods=["GET"])
@auth_required
@maintainer_or_admin_required
def get_status(cluster_id: int):
    """Get MarchProxy connection status for a cluster."""
    db = get_db()
    if not db:
        return jsonify({"error": "Database connection unavailable"}), 500

    # Verify cluster exists
    cluster = db(db.clusters.id == cluster_id).select().first()
    if not cluster:
        return jsonify({"error": "Cluster not found"}), 404

    config = get_marchproxy_config(cluster_id)
    if not config:
        return jsonify({
            "cluster_id": cluster_id,
            "connected": False,
            "configured": False,
            "message": "MarchProxy not configured",
        }), 200

    if not config.get("is_enabled"):
        return jsonify({
            "cluster_id": cluster_id,
            "connected": False,
            "configured": True,
            "enabled": False,
            "message": "MarchProxy is disabled",
        }), 200

    # Try to connect to MarchProxy
    try:
        headers = {
            "Authorization": f"Bearer {config['api_key_encrypted']}",
        }

        response = requests.get(
            f"{config['api_endpoint']}/api/v1/status",
            headers=headers,
            timeout=10,
        )

        connected = response.status_code == 200
        status_data = response.json() if connected else {}

        return jsonify({
            "cluster_id": cluster_id,
            "configured": True,
            "enabled": config.get("is_enabled", True),
            "connected": connected,
            "last_sync": config.get("last_sync"),
            "auto_apply": config.get("auto_apply", False),
            "status": status_data if connected else None,
        }), 200

    except Exception as e:
        return jsonify({
            "cluster_id": cluster_id,
            "configured": True,
            "enabled": config.get("is_enabled", True),
            "connected": False,
            "error": str(e),
            "last_sync": config.get("last_sync"),
        }), 200
