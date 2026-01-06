"""Kubernetes Manifest Management REST API Endpoints."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid

import yaml
from flask import Blueprint, g, jsonify, request

from app.middleware import auth_required, maintainer_or_admin_required

manifests_bp = Blueprint("marketplace_manifests", __name__, url_prefix="/manifests")

# Valid Kubernetes resource kinds for manifest validation
VALID_K8S_KINDS = {
    "ConfigMap",
    "Secret",
    "Deployment",
    "StatefulSet",
    "Service",
    "Ingress",
    "PersistentVolumeClaim",
    "ServiceAccount",
    "Role",
    "RoleBinding",
    "HorizontalPodAutoscaler",
}


@dataclass(slots=True)
class ManifestValidationError:
    """Manifest validation error details."""

    field: str
    message: str
    line_number: Optional[int] = None


@dataclass(slots=True)
class ManifestWizardState:
    """Manifest wizard state tracking."""

    wizard_id: str
    step: int
    manifest_data: Optional[dict]
    validation_errors: list[dict]
    created_at: datetime
    updated_at: datetime


def _get_db():
    """Get database connection from Flask g context."""
    return g.db


def _get_current_user():
    """Get current user from Flask g context."""
    return g.current_user


def _validate_yaml(yaml_content: str) -> tuple[bool, Optional[list], Optional[dict]]:
    """
    Validate YAML syntax and return parsed content.

    Args:
        yaml_content: Raw YAML content string.

    Returns:
        Tuple of (is_valid, error_list, parsed_dict).
    """
    try:
        parsed = yaml.safe_load(yaml_content)
        if not isinstance(parsed, dict):
            return False, [{"message": "YAML must contain a document object"}], None
        return True, None, parsed
    except yaml.YAMLError as e:
        error_msg = str(e)
        line_num = getattr(e, "problem_mark", None)
        line = None
        if line_num:
            line = line_num.line + 1

        return False, [{"message": error_msg, "line": line}], None


def _validate_k8s_manifest(manifest: dict) -> tuple[bool, Optional[list]]:
    """
    Validate Kubernetes manifest structure and resource kind.

    Args:
        manifest: Parsed manifest dictionary.

    Returns:
        Tuple of (is_valid, error_list).
    """
    errors = []

    # Check required fields
    if "apiVersion" not in manifest:
        errors.append({"field": "apiVersion", "message": "apiVersion is required"})

    if "kind" not in manifest:
        errors.append({"field": "kind", "message": "kind is required"})
    elif manifest.get("kind") not in VALID_K8S_KINDS:
        errors.append({
            "field": "kind",
            "message": f"Invalid kind '{manifest.get('kind')}'. "
            f"Must be one of: {', '.join(sorted(VALID_K8S_KINDS))}"
        })

    if "metadata" not in manifest:
        errors.append({"field": "metadata", "message": "metadata is required"})
    else:
        metadata = manifest.get("metadata", {})
        if not isinstance(metadata, dict):
            errors.append({
                "field": "metadata",
                "message": "metadata must be an object"
            })
        elif "name" not in metadata:
            errors.append({
                "field": "metadata.name",
                "message": "metadata.name is required"
            })

    return len(errors) == 0, errors if errors else None


def _validate_manifest_yaml(yaml_content: str) -> tuple[bool, Optional[list], Optional[dict]]:
    """
    Validate YAML manifest format and Kubernetes schema.

    Args:
        yaml_content: Raw YAML content string.

    Returns:
        Tuple of (is_valid, error_list, parsed_manifest).
    """
    # Validate YAML syntax
    yaml_valid, yaml_errors, parsed = _validate_yaml(yaml_content)
    if not yaml_valid:
        return False, yaml_errors, None

    # Validate Kubernetes manifest structure
    k8s_valid, k8s_errors = _validate_k8s_manifest(parsed)
    if not k8s_valid:
        return False, k8s_errors, None

    return True, None, parsed


@manifests_bp.route("/validate", methods=["POST"])
@auth_required
def validate_manifest():
    """
    Validate a Kubernetes YAML manifest.

    Expected JSON body:
    {
        "manifest": "<yaml content>"
    }

    Returns:
    {
        "is_valid": bool,
        "errors": [{"field": str, "message": str, "line": int}],
        "manifest": {parsed manifest object},
        "kind": str,
        "name": str
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    manifest_content = data.get("manifest", "").strip()
    if not manifest_content:
        return jsonify({"error": "manifest field is required"}), 400

    is_valid, errors, parsed = _validate_manifest_yaml(manifest_content)

    response = {
        "is_valid": is_valid,
        "errors": errors or [],
        "manifest": parsed,
        "kind": parsed.get("kind") if parsed else None,
        "name": parsed.get("metadata", {}).get("name") if parsed else None,
    }

    return jsonify(response), 200


@manifests_bp.route("/wizard/start", methods=["POST"])
@auth_required
def start_wizard():
    """
    Start a manifest creation wizard session.

    Expected JSON body:
    {
        "name": "optional wizard name"
    }

    Returns:
    {
        "wizard_id": str,
        "step": int,
        "state": dict,
        "message": str
    }
    """
    data = request.get_json() or {}

    wizard_id = str(uuid.uuid4())
    user_id = _get_current_user().get("id")
    db = _get_db()

    try:
        # Create wizard session in database
        wizard_id_result = db.wizard_sessions.insert(
            session_id=wizard_id,
            wizard_type="manifest",
            user_id=user_id,
            current_step=1,
            state={"name": data.get("name", "")},
            expires_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        return jsonify({
            "wizard_id": wizard_id,
            "step": 1,
            "state": {
                "name": data.get("name", ""),
                "manifest": None,
            },
            "message": "Wizard session created",
        }), 201

    except Exception as e:
        return jsonify({"error": f"Failed to create wizard session: {str(e)}"}), 500


@manifests_bp.route("/wizard/<wizard_id>", methods=["PUT"])
@auth_required
def update_wizard(wizard_id: str):
    """
    Update manifest wizard state.

    Expected JSON body:
    {
        "step": int,
        "state": {
            "name": str,
            "manifest": str (yaml content),
            "cluster_id": int (optional),
            "namespace": str (optional)
        }
    }

    Returns:
    {
        "wizard_id": str,
        "step": int,
        "state": dict,
        "validation": {"is_valid": bool, "errors": []}
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    db = _get_db()
    user_id = _get_current_user().get("id")

    try:
        # Get wizard session
        wizard = db(db.wizard_sessions.session_id == wizard_id).select().first()

        if not wizard:
            return jsonify({"error": "Wizard session not found"}), 404

        if wizard.user_id != user_id:
            return jsonify({"error": "Unauthorized access to wizard"}), 403

        # Update wizard state
        current_state = wizard.state or {}
        new_state = data.get("state", {})
        current_state.update(new_state)

        step = data.get("step", wizard.current_step)

        # Validate manifest if provided
        validation_result = {"is_valid": True, "errors": []}
        if new_state.get("manifest"):
            is_valid, errors, parsed = _validate_manifest_yaml(new_state["manifest"])
            validation_result = {
                "is_valid": is_valid,
                "errors": errors or [],
            }

        # Update database
        wizard.update_record(
            current_step=step,
            state=current_state,
            updated_at=datetime.utcnow(),
        )

        return jsonify({
            "wizard_id": wizard_id,
            "step": step,
            "state": current_state,
            "validation": validation_result,
        }), 200

    except Exception as e:
        return jsonify({"error": f"Failed to update wizard: {str(e)}"}), 500


@manifests_bp.route("/wizard/<wizard_id>/deploy", methods=["POST"])
@auth_required
@maintainer_or_admin_required
def deploy_wizard_manifest(wizard_id: str):
    """
    Deploy manifests from wizard session.

    Expected JSON body:
    {
        "cluster_id": int,
        "namespace": str,
        "manifest_name": str (optional, auto-generated if not provided)
    }

    Returns:
    {
        "message": str,
        "deployment_id": int,
        "wizard_id": str,
        "cluster_id": int,
        "namespace": str,
        "manifest_name": str,
        "status": str
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    cluster_id = data.get("cluster_id")
    namespace = data.get("namespace", "default").strip()
    manifest_name = data.get("manifest_name", "").strip()

    # Validation
    if not cluster_id:
        return jsonify({"error": "cluster_id is required"}), 400

    if not namespace:
        return jsonify({"error": "namespace cannot be empty"}), 400

    db = _get_db()
    user_id = _get_current_user().get("id")

    try:
        # Get wizard session
        wizard = db(db.wizard_sessions.session_id == wizard_id).select().first()

        if not wizard:
            return jsonify({"error": "Wizard session not found"}), 404

        if wizard.user_id != user_id:
            return jsonify({"error": "Unauthorized access to wizard"}), 403

        # Get manifest from wizard state
        state = wizard.state or {}
        manifest_yaml = state.get("manifest")

        if not manifest_yaml:
            return jsonify({"error": "No manifest found in wizard state"}), 400

        # Validate manifest
        is_valid, errors, parsed = _validate_manifest_yaml(manifest_yaml)
        if not is_valid:
            return jsonify({
                "error": "Manifest validation failed",
                "validation_errors": errors,
            }), 400

        # Generate manifest name if not provided
        if not manifest_name:
            manifest_name = f"{parsed.get('metadata', {}).get('name', 'manifest')}-{uuid.uuid4().hex[:8]}"

        # Verify cluster exists and is active
        cluster = db(db.clusters.id == cluster_id).select().first()
        if not cluster:
            return jsonify({"error": "Cluster not found"}), 404

        if not cluster.is_active:
            return jsonify({"error": "Cluster is not active"}), 400

        # Create deployment record (simulated deployment)
        deployment_id = db.deployed_apps.insert(
            name=manifest_name,
            namespace=namespace,
            cluster_id=cluster_id,
            app_id=None,
            source_type="manifest",
            deployed_manifests=parsed,
            status="pending",
            deployed_by=user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Update wizard session
        wizard.update_record(
            state={"manifest_deployed": True, "deployment_id": deployment_id},
            updated_at=datetime.utcnow(),
        )

        return jsonify({
            "message": "Manifest deployment initiated",
            "deployment_id": deployment_id,
            "wizard_id": wizard_id,
            "cluster_id": cluster_id,
            "namespace": namespace,
            "manifest_name": manifest_name,
            "status": "pending",
        }), 201

    except Exception as e:
        return jsonify({"error": f"Failed to deploy manifest: {str(e)}"}), 500
