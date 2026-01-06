"""Marketplace App Catalog REST API Endpoints."""

from dataclasses import dataclass
from typing import Optional

from flask import Blueprint, g, jsonify, request

from app.middleware import auth_required

apps_bp = Blueprint("marketplace_apps", __name__, url_prefix="/apps")


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
class AppResponse:
    """App response data structure."""

    id: int
    app_name: str
    app_version: str
    latest_version: str
    description: Optional[str]
    icon_url: Optional[str]
    home_url: Optional[str]
    category: Optional[str]
    tags: Optional[list]
    maintainers: Optional[list]
    source_type: str
    is_deprecated: bool


def _get_db():
    """Get database connection from Flask g context."""
    return g.db


def _build_app_response(app_row: dict) -> dict:
    """Convert app row to response dictionary."""
    return {
        "id": app_row.get("id"),
        "app_name": app_row.get("app_name"),
        "app_version": app_row.get("app_version"),
        "latest_version": app_row.get("latest_version"),
        "description": app_row.get("description"),
        "icon_url": app_row.get("icon_url"),
        "home_url": app_row.get("home_url"),
        "category": app_row.get("category"),
        "tags": app_row.get("tags") or [],
        "maintainers": app_row.get("maintainers") or [],
        "source_type": app_row.get("source_type"),
        "is_deprecated": app_row.get("is_deprecated", False),
    }


@apps_bp.route("", methods=["GET"])
@auth_required
def list_apps():
    """List apps with pagination."""
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        include_deprecated = request.args.get("include_deprecated", "false").lower() == "true"

        pagination = PaginationParams(page=page, per_page=per_page)
        db = _get_db()

        # Build query
        query = db.marketplace_apps.id > 0
        if not include_deprecated:
            query &= db.marketplace_apps.is_deprecated == False

        # Count total
        total = db(query).count()

        # Fetch paginated results
        apps = db(query).select(
            orderby=~db.marketplace_apps.created_at,
            limitby=(pagination.offset, pagination.offset + pagination.per_page),
        )

        apps_list = [_build_app_response(app.as_dict()) for app in apps]

        return jsonify({
            "apps": apps_list,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": total,
                "pages": (total + pagination.per_page - 1) // pagination.per_page,
            },
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@apps_bp.route("/search", methods=["GET"])
@auth_required
def search_apps():
    """Search apps by query string."""
    try:
        query_str = request.args.get("q", "").strip()
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)

        if not query_str or len(query_str) < 2:
            return jsonify({"error": "Query must be at least 2 characters"}), 400

        pagination = PaginationParams(page=page, per_page=per_page)
        db = _get_db()

        # Build search query (case-insensitive)
        query = (
            (db.marketplace_apps.app_name.like(f"%{query_str}%")) |
            (db.marketplace_apps.description.like(f"%{query_str}%"))
        ) & (db.marketplace_apps.is_deprecated == False)

        # Count total
        total = db(query).count()

        # Fetch paginated results
        apps = db(query).select(
            orderby=~db.marketplace_apps.created_at,
            limitby=(pagination.offset, pagination.offset + pagination.per_page),
        )

        apps_list = [_build_app_response(app.as_dict()) for app in apps]

        return jsonify({
            "apps": apps_list,
            "query": query_str,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": total,
                "pages": (total + pagination.per_page - 1) // pagination.per_page,
            },
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@apps_bp.route("/<int:app_id>", methods=["GET"])
@auth_required
def get_app(app_id: int):
    """Get app details by ID."""
    try:
        db = _get_db()

        app = db(db.marketplace_apps.id == app_id).select().first()

        if not app:
            return jsonify({"error": "App not found"}), 404

        app_dict = app.as_dict()

        return jsonify({
            "app": _build_app_response(app_dict),
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@apps_bp.route("/<int:app_id>/versions", methods=["GET"])
@auth_required
def get_app_versions(app_id: int):
    """Get available versions for an app."""
    try:
        db = _get_db()

        app = db(db.marketplace_apps.id == app_id).select().first()

        if not app:
            return jsonify({"error": "App not found"}), 404

        app_dict = app.as_dict()
        versions = []

        # Add current version
        if app_dict.get("app_version"):
            versions.append({
                "version": app_dict["app_version"],
                "is_latest": False,
                "released_at": app_dict.get("updated_at"),
            })

        # Add latest version if different
        if (app_dict.get("latest_version") and
                app_dict["latest_version"] != app_dict.get("app_version")):
            versions.append({
                "version": app_dict["latest_version"],
                "is_latest": True,
                "released_at": None,
            })

        return jsonify({
            "app_id": app_id,
            "app_name": app_dict.get("app_name"),
            "versions": versions,
            "total": len(versions),
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@apps_bp.route("/<int:app_id>/values-schema", methods=["GET"])
@auth_required
def get_app_values_schema(app_id: int):
    """Get values schema for an app."""
    try:
        db = _get_db()

        app = db(db.marketplace_apps.id == app_id).select().first()

        if not app:
            return jsonify({"error": "App not found"}), 404

        app_dict = app.as_dict()
        values_schema = app_dict.get("values_schema") or {}

        return jsonify({
            "app_id": app_id,
            "app_name": app_dict.get("app_name"),
            "values_schema": values_schema,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@apps_bp.route("/categories", methods=["GET"])
@auth_required
def get_app_categories():
    """Get all app categories."""
    try:
        db = _get_db()

        # Get distinct categories
        rows = db(db.marketplace_apps.id > 0).select(
            db.marketplace_apps.category,
            distinct=True,
            orderby=db.marketplace_apps.category,
        )

        categories = [row.category for row in rows if row.category]

        return jsonify({
            "categories": categories,
            "total": len(categories),
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
