"""Repository Management REST API Endpoints.

This module provides REST API endpoints for managing Helm repositories and
Docker registries, including listing, creating, updating, deleting, and
syncing repositories.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import yaml
from flask import Blueprint, g, jsonify, request

from ..middleware import admin_required, auth_required, maintainer_or_admin_required
from .models import (
    VALID_AUTH_TYPES,
    VALID_HELM_VERSIONS,
    VALID_REGISTRY_TYPES,
    get_cluster_by_id,
)

repositories_bp = Blueprint("repositories", __name__, url_prefix="")


@dataclass(slots=True)
class HelmRepositoryRequest:
    """Request DTO for Helm repository operations."""
    name: str
    url: str
    description: Optional[str] = None
    category: Optional[str] = None
    is_enabled: bool = True
    helm_version: str = "v3"
    auth_type: str = "none"
    auth_username: Optional[str] = None
    auth_password: Optional[str] = None


@dataclass(slots=True)
class DockerRegistryRequest:
    """Request DTO for Docker registry operations."""
    name: str
    url: str
    registry_type: str = "custom"
    is_enabled: bool = True
    auth_type: str = "none"
    auth_username: Optional[str] = None
    auth_password: Optional[str] = None


@dataclass(slots=True)
class RepositoryResponse:
    """Response DTO for repository data."""
    id: int
    name: str
    url: str
    is_enabled: bool
    created_at: str
    updated_at: str


def _serialize_helm_repo(repo: dict) -> dict:
    """Serialize Helm repository record to JSON-safe format."""
    return {
        "id": repo.get("id"),
        "name": repo.get("name"),
        "url": repo.get("url"),
        "description": repo.get("description"),
        "category": repo.get("category"),
        "is_builtin": repo.get("is_builtin", False),
        "is_enabled": repo.get("is_enabled", True),
        "helm_version": repo.get("helm_version", "v3"),
        "auth_type": repo.get("auth_type", "none"),
        "auth_username": repo.get("auth_username"),
        "last_synced": (
            repo.get("last_synced").isoformat()
            if repo.get("last_synced")
            else None
        ),
        "chart_count": repo.get("chart_count", 0),
        "created_at": (
            repo.get("created_at").isoformat()
            if repo.get("created_at")
            else None
        ),
        "updated_at": (
            repo.get("updated_at").isoformat()
            if repo.get("updated_at")
            else None
        ),
    }


def _serialize_docker_registry(registry: dict) -> dict:
    """Serialize Docker registry record to JSON-safe format."""
    return {
        "id": registry.get("id"),
        "name": registry.get("name"),
        "url": registry.get("url"),
        "registry_type": registry.get("registry_type", "custom"),
        "is_builtin": registry.get("is_builtin", False),
        "is_enabled": registry.get("is_enabled", True),
        "auth_type": registry.get("auth_type", "none"),
        "auth_username": registry.get("auth_username"),
        "created_at": (
            registry.get("created_at").isoformat()
            if registry.get("created_at")
            else None
        ),
        "updated_at": (
            registry.get("updated_at").isoformat()
            if registry.get("updated_at")
            else None
        ),
    }


def _get_helm_repo_by_id(db, repo_id: int) -> Optional[dict]:
    """Get Helm repository by ID."""
    repo = db(db.helm_repositories.id == repo_id).select().first()
    return repo.as_dict() if repo else None


def _get_helm_repo_by_name(db, name: str) -> Optional[dict]:
    """Get Helm repository by name."""
    repo = db(db.helm_repositories.name == name).select().first()
    return repo.as_dict() if repo else None


def _get_docker_registry_by_id(db, registry_id: int) -> Optional[dict]:
    """Get Docker registry by ID."""
    registry = db(db.docker_registries.id == registry_id).select().first()
    return registry.as_dict() if registry else None


def _get_docker_registry_by_name(db, name: str) -> Optional[dict]:
    """Get Docker registry by name."""
    registry = db(db.docker_registries.name == name).select().first()
    return registry.as_dict() if registry else None


def _list_helm_repositories(
    db,
    enabled_only: bool = False,
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


def _list_docker_registries(
    db,
    enabled_only: bool = False,
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


def load_builtin_repositories(db) -> dict:
    """Load and initialize builtin repositories from builtin_repos.yaml on startup.

    Args:
        db: PyDAL database connection instance.

    Returns:
        Dictionary with counts of loaded Helm repos and Docker registries.
    """
    try:
        # Load YAML file
        yaml_path = "/app/marketplace/builtin_repos.yaml"
        with open(yaml_path, "r") as f:
            config = yaml.safe_load(f)

        helm_count = 0
        docker_count = 0

        # Load Helm repositories
        for repo_config in config.get("helm_repositories", []):
            repo_name = repo_config.get("name")
            if not repo_name:
                continue

            # Check if repo already exists
            existing = _get_helm_repo_by_name(db, repo_name)
            if existing:
                continue

            # Insert builtin repo
            db.helm_repositories.insert(
                name=repo_name,
                url=repo_config.get("url"),
                description=repo_config.get("description"),
                category=repo_config.get("category"),
                is_builtin=True,
                is_enabled=repo_config.get("enabled", True),
                helm_version=repo_config.get("helm_version", "v3"),
                auth_type="none",
            )
            helm_count += 1

        # Load Docker registries
        for registry_config in config.get("docker_registries", []):
            registry_name = registry_config.get("name")
            if not registry_name:
                continue

            # Check if registry already exists
            existing = _get_docker_registry_by_name(db, registry_name)
            if existing:
                continue

            # Insert builtin registry
            db.docker_registries.insert(
                name=registry_name,
                url=registry_config.get("url"),
                registry_type=registry_config.get("registry_type", "custom"),
                is_builtin=True,
                is_enabled=registry_config.get("enabled", True),
                auth_type="none",
            )
            docker_count += 1

        db.commit()

        return {
            "helm_repositories_loaded": helm_count,
            "docker_registries_loaded": docker_count,
        }

    except FileNotFoundError:
        return {
            "helm_repositories_loaded": 0,
            "docker_registries_loaded": 0,
            "error": "builtin_repos.yaml not found",
        }
    except Exception as e:
        return {
            "helm_repositories_loaded": 0,
            "docker_registries_loaded": 0,
            "error": str(e),
        }


# ==================== Helm Repository Endpoints ====================


@repositories_bp.route("/helm", methods=["GET"])
@auth_required
def list_helm_repos():
    """List all Helm repositories.

    Query parameters:
        - enabled_only (bool): Filter to enabled repos only (default: false)
        - include_builtin (bool): Include builtin repos (default: true)

    Returns:
        JSON response with Helm repositories list.
    """
    enabled_only = request.args.get("enabled_only", "false").lower() == "true"
    include_builtin = request.args.get("include_builtin", "true").lower() == "true"

    db = g.db
    repos = _list_helm_repositories(db, enabled_only=enabled_only,
                                     include_builtin=include_builtin)

    repos_data = [_serialize_helm_repo(r) for r in repos]

    return jsonify({
        "repositories": repos_data,
        "total": len(repos_data),
    }), 200


@repositories_bp.route("/helm/<int:repo_id>", methods=["GET"])
@auth_required
def get_helm_repo(repo_id: int):
    """Get Helm repository by ID.

    Args:
        repo_id: The repository ID to retrieve.

    Returns:
        JSON response with repository details or 404 if not found.
    """
    db = g.db
    repo = _get_helm_repo_by_id(db, repo_id)

    if not repo:
        return jsonify({"error": "Helm repository not found"}), 404

    return jsonify(_serialize_helm_repo(repo)), 200


@repositories_bp.route("/helm", methods=["POST"])
@auth_required
@admin_required
def create_helm_repo():
    """Create a new Helm repository (Admin only).

    Required fields:
        - name: Unique repository identifier
        - url: Repository URL

    Optional fields:
        - description: Repository description
        - category: Repository category (general, networking, monitoring, etc.)
        - is_enabled: Enable/disable repository (default: true)
        - helm_version: Helm version (v2 or v3, default: v3)
        - auth_type: Authentication type (none, basic, bearer, token)
        - auth_username: Username for authentication
        - auth_password: Password for authentication

    Returns:
        JSON response with created repository (201) or validation errors (400).
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    # Required field validation
    name = data.get("name", "").strip().lower()
    url = data.get("url", "").strip()

    if not name:
        return jsonify({"error": "Repository name is required"}), 400

    if not url:
        return jsonify({"error": "Repository URL is required"}), 400

    # Check for duplicate repo name
    db = g.db
    existing = _get_helm_repo_by_name(db, name)
    if existing:
        return jsonify({"error": "Repository name already exists"}), 409

    # Optional fields with validation
    helm_version = data.get("helm_version", "v3").strip()
    if helm_version not in VALID_HELM_VERSIONS:
        return jsonify({
            "error": f"Invalid Helm version. Must be one of: "
                     f"{', '.join(VALID_HELM_VERSIONS)}"
        }), 400

    auth_type = data.get("auth_type", "none").strip().lower()
    if auth_type not in VALID_AUTH_TYPES:
        return jsonify({
            "error": f"Invalid auth type. Must be one of: "
                     f"{', '.join(VALID_AUTH_TYPES)}"
        }), 400

    # Create repository
    current_user = g.current_user
    repo_id = db.helm_repositories.insert(
        name=name,
        url=url,
        description=data.get("description", "").strip() or None,
        category=data.get("category", "").strip() or None,
        is_enabled=bool(data.get("is_enabled", True)),
        helm_version=helm_version,
        auth_type=auth_type,
        auth_username=data.get("auth_username", "").strip() or None,
        auth_password_encrypted=data.get("auth_password", "").strip() or None,
        created_by=current_user["id"],
    )
    db.commit()

    repo = _get_helm_repo_by_id(db, repo_id)

    return jsonify({
        "message": "Helm repository created successfully",
        "repository": _serialize_helm_repo(repo),
    }), 201


@repositories_bp.route("/helm/<int:repo_id>", methods=["PUT"])
@auth_required
@admin_required
def update_helm_repo(repo_id: int):
    """Update Helm repository by ID (Admin only).

    Args:
        repo_id: The repository ID to update.

    Optional update fields:
        - url: Repository URL
        - description: Repository description
        - category: Repository category
        - is_enabled: Enable/disable repository
        - helm_version: Helm version
        - auth_type: Authentication type
        - auth_username: Username for authentication
        - auth_password: Password for authentication

    Returns:
        JSON response with updated repository (200) or errors (400/404).
    """
    db = g.db
    repo = _get_helm_repo_by_id(db, repo_id)

    if not repo:
        return jsonify({"error": "Helm repository not found"}), 404

    # Prevent updating builtin repos
    if repo.get("is_builtin", False):
        return jsonify({"error": "Cannot modify builtin repositories"}), 403

    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    update_data = {}

    # URL update
    if "url" in data:
        url = data["url"].strip()
        if url:
            update_data["url"] = url

    # Description update
    if "description" in data:
        update_data["description"] = data["description"].strip() or None

    # Category update
    if "category" in data:
        update_data["category"] = data["category"].strip() or None

    # Enabled status update
    if "is_enabled" in data:
        update_data["is_enabled"] = bool(data["is_enabled"])

    # Helm version update
    if "helm_version" in data:
        helm_version = data["helm_version"].strip()
        if helm_version not in VALID_HELM_VERSIONS:
            return jsonify({
                "error": f"Invalid Helm version. Must be one of: "
                         f"{', '.join(VALID_HELM_VERSIONS)}"
            }), 400
        update_data["helm_version"] = helm_version

    # Auth type update
    if "auth_type" in data:
        auth_type = data["auth_type"].strip().lower()
        if auth_type not in VALID_AUTH_TYPES:
            return jsonify({
                "error": f"Invalid auth type. Must be one of: "
                         f"{', '.join(VALID_AUTH_TYPES)}"
            }), 400
        update_data["auth_type"] = auth_type

    # Auth username update
    if "auth_username" in data:
        update_data["auth_username"] = data["auth_username"].strip() or None

    # Auth password update
    if "auth_password" in data:
        update_data["auth_password_encrypted"] = (
            data["auth_password"].strip() or None
        )

    if not update_data:
        return jsonify({"error": "No valid fields to update"}), 400

    update_data["updated_at"] = datetime.utcnow()

    db(db.helm_repositories.id == repo_id).update(**update_data)
    db.commit()

    updated_repo = _get_helm_repo_by_id(db, repo_id)

    return jsonify({
        "message": "Helm repository updated successfully",
        "repository": _serialize_helm_repo(updated_repo),
    }), 200


@repositories_bp.route("/helm/<int:repo_id>", methods=["DELETE"])
@auth_required
@admin_required
def delete_helm_repo(repo_id: int):
    """Delete Helm repository by ID (Admin only).

    Args:
        repo_id: The repository ID to delete.

    Returns:
        JSON response confirming deletion (200) or error (403/404).
    """
    db = g.db
    repo = _get_helm_repo_by_id(db, repo_id)

    if not repo:
        return jsonify({"error": "Helm repository not found"}), 404

    # Prevent deleting builtin repos
    if repo.get("is_builtin", False):
        return jsonify({"error": "Cannot delete builtin repositories"}), 403

    db(db.helm_repositories.id == repo_id).delete()
    db.commit()

    return jsonify({"message": "Helm repository deleted successfully"}), 200


@repositories_bp.route("/helm/<int:repo_id>/sync", methods=["POST"])
@auth_required
@maintainer_or_admin_required
def sync_helm_repo(repo_id: int):
    """Sync Helm repository (Maintainer+).

    This endpoint initiates a sync of the specified Helm repository.
    The actual sync logic should be handled by a background task.

    Args:
        repo_id: The repository ID to sync.

    Returns:
        JSON response with sync status (200/202) or error (404).
    """
    db = g.db
    repo = _get_helm_repo_by_id(db, repo_id)

    if not repo:
        return jsonify({"error": "Helm repository not found"}), 404

    # Update last_synced timestamp
    db(db.helm_repositories.id == repo_id).update(
        last_synced=datetime.utcnow(),
    )
    db.commit()

    # In production, this would queue a background task
    # to perform actual Helm repository sync

    return jsonify({
        "message": "Helm repository sync initiated",
        "repository_id": repo_id,
        "repository_name": repo.get("name"),
        "status": "pending",
        "last_synced": datetime.utcnow().isoformat(),
    }), 202


# ==================== Docker Registry Endpoints ====================


@repositories_bp.route("/docker", methods=["GET"])
@auth_required
def list_docker_registries():
    """List all Docker registries.

    Query parameters:
        - enabled_only (bool): Filter to enabled registries only (default: false)
        - include_builtin (bool): Include builtin registries (default: true)

    Returns:
        JSON response with Docker registries list.
    """
    enabled_only = request.args.get("enabled_only", "false").lower() == "true"
    include_builtin = request.args.get("include_builtin", "true").lower() == "true"

    db = g.db
    registries = _list_docker_registries(db, enabled_only=enabled_only,
                                          include_builtin=include_builtin)

    registries_data = [_serialize_docker_registry(r) for r in registries]

    return jsonify({
        "registries": registries_data,
        "total": len(registries_data),
    }), 200


@repositories_bp.route("/docker/<int:registry_id>", methods=["GET"])
@auth_required
def get_docker_registry(registry_id: int):
    """Get Docker registry by ID.

    Args:
        registry_id: The registry ID to retrieve.

    Returns:
        JSON response with registry details or 404 if not found.
    """
    db = g.db
    registry = _get_docker_registry_by_id(db, registry_id)

    if not registry:
        return jsonify({"error": "Docker registry not found"}), 404

    return jsonify(_serialize_docker_registry(registry)), 200


@repositories_bp.route("/docker", methods=["POST"])
@auth_required
@admin_required
def create_docker_registry():
    """Create a new Docker registry (Admin only).

    Required fields:
        - name: Unique registry identifier
        - url: Registry URL

    Optional fields:
        - registry_type: Registry type (dockerhub, ghcr, ecr, gcr, acr, quay, custom)
        - is_enabled: Enable/disable registry (default: true)
        - auth_type: Authentication type (none, basic, bearer, token)
        - auth_username: Username for authentication
        - auth_password: Password for authentication

    Returns:
        JSON response with created registry (201) or validation errors (400).
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    # Required field validation
    name = data.get("name", "").strip().lower()
    url = data.get("url", "").strip()

    if not name:
        return jsonify({"error": "Registry name is required"}), 400

    if not url:
        return jsonify({"error": "Registry URL is required"}), 400

    # Check for duplicate registry name
    db = g.db
    existing = _get_docker_registry_by_name(db, name)
    if existing:
        return jsonify({"error": "Registry name already exists"}), 409

    # Optional fields with validation
    registry_type = data.get("registry_type", "custom").strip().lower()
    if registry_type not in VALID_REGISTRY_TYPES:
        return jsonify({
            "error": f"Invalid registry type. Must be one of: "
                     f"{', '.join(VALID_REGISTRY_TYPES)}"
        }), 400

    auth_type = data.get("auth_type", "none").strip().lower()
    if auth_type not in VALID_AUTH_TYPES:
        return jsonify({
            "error": f"Invalid auth type. Must be one of: "
                     f"{', '.join(VALID_AUTH_TYPES)}"
        }), 400

    # Create registry
    current_user = g.current_user
    registry_id = db.docker_registries.insert(
        name=name,
        url=url,
        registry_type=registry_type,
        is_enabled=bool(data.get("is_enabled", True)),
        auth_type=auth_type,
        auth_username=data.get("auth_username", "").strip() or None,
        auth_password_encrypted=data.get("auth_password", "").strip() or None,
        created_by=current_user["id"],
    )
    db.commit()

    registry = _get_docker_registry_by_id(db, registry_id)

    return jsonify({
        "message": "Docker registry created successfully",
        "registry": _serialize_docker_registry(registry),
    }), 201


@repositories_bp.route("/docker/<int:registry_id>", methods=["PUT"])
@auth_required
@admin_required
def update_docker_registry(registry_id: int):
    """Update Docker registry by ID (Admin only).

    Args:
        registry_id: The registry ID to update.

    Optional update fields:
        - url: Registry URL
        - registry_type: Registry type
        - is_enabled: Enable/disable registry
        - auth_type: Authentication type
        - auth_username: Username for authentication
        - auth_password: Password for authentication

    Returns:
        JSON response with updated registry (200) or errors (400/404).
    """
    db = g.db
    registry = _get_docker_registry_by_id(db, registry_id)

    if not registry:
        return jsonify({"error": "Docker registry not found"}), 404

    # Prevent updating builtin registries
    if registry.get("is_builtin", False):
        return jsonify({"error": "Cannot modify builtin registries"}), 403

    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    update_data = {}

    # URL update
    if "url" in data:
        url = data["url"].strip()
        if url:
            update_data["url"] = url

    # Registry type update
    if "registry_type" in data:
        registry_type = data["registry_type"].strip().lower()
        if registry_type not in VALID_REGISTRY_TYPES:
            return jsonify({
                "error": f"Invalid registry type. Must be one of: "
                         f"{', '.join(VALID_REGISTRY_TYPES)}"
            }), 400
        update_data["registry_type"] = registry_type

    # Enabled status update
    if "is_enabled" in data:
        update_data["is_enabled"] = bool(data["is_enabled"])

    # Auth type update
    if "auth_type" in data:
        auth_type = data["auth_type"].strip().lower()
        if auth_type not in VALID_AUTH_TYPES:
            return jsonify({
                "error": f"Invalid auth type. Must be one of: "
                         f"{', '.join(VALID_AUTH_TYPES)}"
            }), 400
        update_data["auth_type"] = auth_type

    # Auth username update
    if "auth_username" in data:
        update_data["auth_username"] = data["auth_username"].strip() or None

    # Auth password update
    if "auth_password" in data:
        update_data["auth_password_encrypted"] = (
            data["auth_password"].strip() or None
        )

    if not update_data:
        return jsonify({"error": "No valid fields to update"}), 400

    update_data["updated_at"] = datetime.utcnow()

    db(db.docker_registries.id == registry_id).update(**update_data)
    db.commit()

    updated_registry = _get_docker_registry_by_id(db, registry_id)

    return jsonify({
        "message": "Docker registry updated successfully",
        "registry": _serialize_docker_registry(updated_registry),
    }), 200


@repositories_bp.route("/docker/<int:registry_id>", methods=["DELETE"])
@auth_required
@admin_required
def delete_docker_registry(registry_id: int):
    """Delete Docker registry by ID (Admin only).

    Args:
        registry_id: The registry ID to delete.

    Returns:
        JSON response confirming deletion (200) or error (403/404).
    """
    db = g.db
    registry = _get_docker_registry_by_id(db, registry_id)

    if not registry:
        return jsonify({"error": "Docker registry not found"}), 404

    # Prevent deleting builtin registries
    if registry.get("is_builtin", False):
        return jsonify({"error": "Cannot delete builtin registries"}), 403

    db(db.docker_registries.id == registry_id).delete()
    db.commit()

    return jsonify({"message": "Docker registry deleted successfully"}), 200
