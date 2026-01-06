"""Deployment Wizard and Management REST API Endpoints."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import secrets

from flask import Blueprint, g, jsonify, request

from app.middleware import auth_required, maintainer_or_admin_required

deployments_bp = Blueprint("deployments", __name__, url_prefix="/deployments")


@dataclass(slots=True)
class PaginationParams:
    """Pagination parameters."""

    page: int
    per_page: int

    def __post_init__(self) -> None:
        """Validate pagination parameters."""
        self.per_page = min(max(self.per_page, 1), 100)
        self.page = max(self.page, 1)

    @property
    def offset(self) -> int:
        """Calculate offset from page and per_page."""
        return (self.page - 1) * self.per_page


@dataclass(slots=True)
class WizardSession:
    """Wizard session data structure."""

    session_id: str
    wizard_type: str
    user_id: int
    cluster_id: Optional[int]
    app_id: Optional[int]
    current_step: int
    state: dict
    expires_at: datetime


@dataclass(slots=True)
class DeploymentResponse:
    """Deployment response data structure."""

    id: int
    name: str
    namespace: str
    cluster_id: int
    app_id: int
    source_type: str
    installed_version: str
    status: str
    health_status: Optional[str]
    replicas_desired: int
    replicas_ready: int
    replicas_available: int
    cpu_usage: Optional[str]
    memory_usage: Optional[str]
    deployed_by: int
    created_at: datetime
    updated_at: datetime


def _get_db():
    """Get database connection from Flask g context."""
    return g.db


def _get_current_user() -> dict:
    """Get current authenticated user."""
    from app.middleware import get_current_user
    return get_current_user()


def _generate_session_id() -> str:
    """Generate unique session ID."""
    return secrets.token_hex(32)


def _build_wizard_response(session_row: dict) -> dict:
    """Convert wizard session to response dictionary."""
    return {
        "session_id": session_row.get("session_id"),
        "wizard_type": session_row.get("wizard_type"),
        "current_step": session_row.get("current_step"),
        "state": session_row.get("state") or {},
        "expires_at": session_row.get("expires_at").isoformat() if session_row.get("expires_at") else None,
        "created_at": session_row.get("created_at").isoformat() if session_row.get("created_at") else None,
    }


def _build_deployment_response(deployment_row: dict) -> dict:
    """Convert deployment row to response dictionary."""
    return {
        "id": deployment_row.get("id"),
        "name": deployment_row.get("name"),
        "namespace": deployment_row.get("namespace"),
        "cluster_id": deployment_row.get("cluster_id"),
        "app_id": deployment_row.get("app_id"),
        "source_type": deployment_row.get("source_type"),
        "installed_version": deployment_row.get("installed_version"),
        "status": deployment_row.get("status"),
        "health_status": deployment_row.get("health_status"),
        "replicas_desired": deployment_row.get("replicas_desired", 0),
        "replicas_ready": deployment_row.get("replicas_ready", 0),
        "replicas_available": deployment_row.get("replicas_available", 0),
        "cpu_usage": deployment_row.get("cpu_usage"),
        "memory_usage": deployment_row.get("memory_usage"),
        "deployed_by": deployment_row.get("deployed_by"),
        "created_at": deployment_row.get("created_at").isoformat() if deployment_row.get("created_at") else None,
        "updated_at": deployment_row.get("updated_at").isoformat() if deployment_row.get("updated_at") else None,
    }


# Wizard Endpoints

@deployments_bp.route("/wizard/start", methods=["POST"])
@auth_required
def start_wizard():
    """Start deployment wizard session."""
    try:
        data = request.get_json() or {}
        user = _get_current_user()
        db = _get_db()

        # Validate required fields
        wizard_type = data.get("wizard_type", "").strip()
        if not wizard_type:
            return jsonify({"error": "wizard_type is required"}), 400

        cluster_id = data.get("cluster_id")
        app_id = data.get("app_id")

        # Validate cluster exists if provided
        if cluster_id:
            cluster = db(db.clusters.id == cluster_id).select().first()
            if not cluster:
                return jsonify({"error": "Cluster not found"}), 404

        # Validate app exists if provided
        if app_id:
            app = db(db.marketplace_apps.id == app_id).select().first()
            if not app:
                return jsonify({"error": "App not found"}), 404

        # Create wizard session
        session_id = _generate_session_id()
        expires_at = datetime.utcnow() + timedelta(hours=24)

        wizard_id = db.wizard_sessions.insert(
            session_id=session_id,
            wizard_type=wizard_type,
            user_id=user.get("id"),
            cluster_id=cluster_id,
            app_id=app_id,
            current_step=1,
            state={},
            expires_at=expires_at,
        )

        db.commit()

        return jsonify({
            "session_id": session_id,
            "wizard_id": wizard_id,
            "message": "Wizard session started",
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@deployments_bp.route("/wizard/<session_id>", methods=["GET"])
@auth_required
def get_wizard(session_id: str):
    """Get wizard session state."""
    try:
        db = _get_db()

        session = db(db.wizard_sessions.session_id == session_id).select().first()
        if not session:
            return jsonify({"error": "Wizard session not found"}), 404

        # Check if session has expired
        if session.expires_at < datetime.utcnow():
            db(db.wizard_sessions.id == session.id).delete()
            db.commit()
            return jsonify({"error": "Wizard session has expired"}), 410

        return jsonify(_build_wizard_response(session.as_dict())), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@deployments_bp.route("/wizard/<session_id>", methods=["PUT"])
@auth_required
def update_wizard(session_id: str):
    """Update wizard session state."""
    try:
        data = request.get_json() or {}
        db = _get_db()

        session = db(db.wizard_sessions.session_id == session_id).select().first()
        if not session:
            return jsonify({"error": "Wizard session not found"}), 404

        # Check if session has expired
        if session.expires_at < datetime.utcnow():
            db(db.wizard_sessions.id == session.id).delete()
            db.commit()
            return jsonify({"error": "Wizard session has expired"}), 410

        # Update fields
        update_data = {}

        if "current_step" in data:
            step = data.get("current_step", type=int)
            if step and step > 0:
                update_data["current_step"] = step

        if "state" in data:
            if isinstance(data["state"], dict):
                current_state = session.state or {}
                current_state.update(data["state"])
                update_data["state"] = current_state

        if "cluster_id" in data:
            cluster_id = data.get("cluster_id")
            if cluster_id:
                cluster = db(db.clusters.id == cluster_id).select().first()
                if not cluster:
                    return jsonify({"error": "Cluster not found"}), 404
                update_data["cluster_id"] = cluster_id

        if "app_id" in data:
            app_id = data.get("app_id")
            if app_id:
                app = db(db.marketplace_apps.id == app_id).select().first()
                if not app:
                    return jsonify({"error": "App not found"}), 404
                update_data["app_id"] = app_id

        if not update_data:
            return jsonify({"error": "No valid fields to update"}), 400

        # Update session
        db(db.wizard_sessions.id == session.id).update(**update_data)
        db.commit()

        # Fetch updated session
        updated = db(db.wizard_sessions.id == session.id).select().first()
        return jsonify(_build_wizard_response(updated.as_dict())), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@deployments_bp.route("/wizard/<session_id>/deploy", methods=["POST"])
@auth_required
@maintainer_or_admin_required
def execute_deployment(session_id: str):
    """Execute deployment from wizard."""
    try:
        data = request.get_json() or {}
        user = _get_current_user()
        db = _get_db()

        session = db(db.wizard_sessions.session_id == session_id).select().first()
        if not session:
            return jsonify({"error": "Wizard session not found"}), 404

        # Check if session has expired
        if session.expires_at < datetime.utcnow():
            db(db.wizard_sessions.id == session.id).delete()
            db.commit()
            return jsonify({"error": "Wizard session has expired"}), 410

        # Validate deployment config
        state = session.state or {}
        cluster_id = session.cluster_id or state.get("cluster_id")
        app_id = session.app_id or state.get("app_id")
        namespace = state.get("namespace", "default").strip()
        deployment_name = state.get("deployment_name", "").strip()
        values = state.get("values", {})

        if not cluster_id:
            return jsonify({"error": "Cluster ID is required"}), 400
        if not app_id:
            return jsonify({"error": "App ID is required"}), 400
        if not deployment_name:
            return jsonify({"error": "Deployment name is required"}), 400
        if not namespace:
            return jsonify({"error": "Namespace is required"}), 400

        # Validate cluster and app exist
        cluster = db(db.clusters.id == cluster_id).select().first()
        if not cluster:
            return jsonify({"error": "Cluster not found"}), 404

        app = db(db.marketplace_apps.id == app_id).select().first()
        if not app:
            return jsonify({"error": "App not found"}), 404

        # Create deployment record
        deployment_id = db.deployed_apps.insert(
            name=deployment_name,
            namespace=namespace,
            cluster_id=cluster_id,
            app_id=app_id,
            source_type=app.source_type,
            installed_version=app.app_version,
            deployed_values=values,
            deployed_manifests={},
            status="pending",
            replicas_desired=1,
            deployed_by=user.get("id"),
        )

        db.commit()

        # Clean up wizard session
        db(db.wizard_sessions.id == session.id).delete()
        db.commit()

        return jsonify({
            "message": "Deployment initiated",
            "deployment_id": deployment_id,
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@deployments_bp.route("/wizard/<session_id>/preview", methods=["GET"])
@auth_required
def preview_deployment(session_id: str):
    """Preview deployment manifests."""
    try:
        db = _get_db()

        session = db(db.wizard_sessions.session_id == session_id).select().first()
        if not session:
            return jsonify({"error": "Wizard session not found"}), 404

        # Check if session has expired
        if session.expires_at < datetime.utcnow():
            db(db.wizard_sessions.id == session.id).delete()
            db.commit()
            return jsonify({"error": "Wizard session has expired"}), 410

        state = session.state or {}
        app_id = session.app_id or state.get("app_id")
        cluster_id = session.cluster_id or state.get("cluster_id")
        namespace = state.get("namespace", "default")
        values = state.get("values", {})

        # Build preview manifests
        preview_manifests = {
            "namespace": namespace,
            "cluster_id": cluster_id,
            "app_id": app_id,
            "values": values,
            "rendered_manifests": [],
        }

        # Add app metadata if available
        if app_id:
            app = db(db.marketplace_apps.id == app_id).select().first()
            if app:
                preview_manifests["app_name"] = app.app_name
                preview_manifests["app_version"] = app.app_version

        return jsonify({
            "preview": preview_manifests,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@deployments_bp.route("/wizard/<session_id>", methods=["DELETE"])
@auth_required
def cancel_wizard(session_id: str):
    """Cancel wizard session."""
    try:
        db = _get_db()

        session = db(db.wizard_sessions.session_id == session_id).select().first()
        if not session:
            return jsonify({"error": "Wizard session not found"}), 404

        db(db.wizard_sessions.id == session.id).delete()
        db.commit()

        return jsonify({
            "message": "Wizard session cancelled",
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Deployment Management Endpoints

@deployments_bp.route("", methods=["GET"])
@auth_required
def list_deployments():
    """List deployed apps with pagination."""
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        cluster_id = request.args.get("cluster_id", type=int)
        namespace = request.args.get("namespace", "").strip()
        status = request.args.get("status", "").strip()

        pagination = PaginationParams(page=page, per_page=per_page)
        db = _get_db()

        # Build query
        query = db.deployed_apps.id > 0

        if cluster_id:
            query &= db.deployed_apps.cluster_id == cluster_id

        if namespace:
            query &= db.deployed_apps.namespace == namespace

        if status:
            query &= db.deployed_apps.status == status

        # Count total
        total = db(query).count()

        # Fetch paginated results
        deployments = db(query).select(
            orderby=~db.deployed_apps.created_at,
            limitby=(pagination.offset, pagination.offset + pagination.per_page),
        )

        deployments_list = [_build_deployment_response(d.as_dict()) for d in deployments]

        return jsonify({
            "deployments": deployments_list,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": total,
                "pages": (total + pagination.per_page - 1) // pagination.per_page,
            },
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@deployments_bp.route("/<int:deployment_id>", methods=["GET"])
@auth_required
def get_deployment(deployment_id: int):
    """Get deployment details by ID."""
    try:
        db = _get_db()

        deployment = db(db.deployed_apps.id == deployment_id).select().first()
        if not deployment:
            return jsonify({"error": "Deployment not found"}), 404

        return jsonify(_build_deployment_response(deployment.as_dict())), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@deployments_bp.route("/<int:deployment_id>/status", methods=["GET"])
@auth_required
def get_deployment_status(deployment_id: int):
    """Get deployment status."""
    try:
        db = _get_db()

        deployment = db(db.deployed_apps.id == deployment_id).select().first()
        if not deployment:
            return jsonify({"error": "Deployment not found"}), 404

        return jsonify({
            "deployment_id": deployment_id,
            "status": deployment.status,
            "health_status": deployment.health_status,
            "replicas_desired": deployment.replicas_desired,
            "replicas_ready": deployment.replicas_ready,
            "replicas_available": deployment.replicas_available,
            "cpu_usage": deployment.cpu_usage,
            "memory_usage": deployment.memory_usage,
            "last_health_check": deployment.last_health_check.isoformat() if deployment.last_health_check else None,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@deployments_bp.route("/<int:deployment_id>", methods=["DELETE"])
@auth_required
@maintainer_or_admin_required
def uninstall_deployment(deployment_id: int):
    """Uninstall deployment."""
    try:
        db = _get_db()

        deployment = db(db.deployed_apps.id == deployment_id).select().first()
        if not deployment:
            return jsonify({"error": "Deployment not found"}), 404

        # Mark for deletion
        db(db.deployed_apps.id == deployment_id).update(status="deleted")
        db.commit()

        # Clean up dependencies
        db(db.app_dependencies.deployed_app_id == deployment_id).delete()
        db.commit()

        return jsonify({
            "message": "Deployment uninstall initiated",
            "deployment_id": deployment_id,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@deployments_bp.route("/<int:deployment_id>/upgrade", methods=["POST"])
@auth_required
@maintainer_or_admin_required
def upgrade_deployment(deployment_id: int):
    """Upgrade deployed app."""
    try:
        data = request.get_json() or {}
        user = _get_current_user()
        db = _get_db()

        deployment = db(db.deployed_apps.id == deployment_id).select().first()
        if not deployment:
            return jsonify({"error": "Deployment not found"}), 404

        target_version = data.get("target_version", "").strip()
        if not target_version:
            return jsonify({"error": "target_version is required"}), 400

        # Update deployment
        db(db.deployed_apps.id == deployment_id).update(
            installed_version=target_version,
            status="deploying",
        )
        db.commit()

        return jsonify({
            "message": "Deployment upgrade initiated",
            "deployment_id": deployment_id,
            "target_version": target_version,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@deployments_bp.route("/<int:deployment_id>/logs", methods=["GET"])
@auth_required
def get_deployment_logs(deployment_id: int):
    """Get deployment logs."""
    try:
        lines = request.args.get("lines", 100, type=int)
        lines = min(max(lines, 1), 1000)

        db = _get_db()

        deployment = db(db.deployed_apps.id == deployment_id).select().first()
        if not deployment:
            return jsonify({"error": "Deployment not found"}), 404

        # Return placeholder logs structure
        return jsonify({
            "deployment_id": deployment_id,
            "name": deployment.name,
            "namespace": deployment.namespace,
            "logs": [],
            "line_count": 0,
            "max_lines": lines,
            "message": "Log retrieval requires cluster connection",
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
