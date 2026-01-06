"""Notification Management Endpoints."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import requests
from flask import Blueprint, current_app, jsonify, request

from ..middleware import auth_required, get_current_user, maintainer_or_admin_required
from ..models import get_db
from .models import VALID_EMAIL_FREQUENCIES, VALID_WEBHOOK_TYPES

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@dataclass(slots=True)
class NotificationPreference:
    """Notification preference data model."""
    user_id: int
    email_enabled: bool
    email_frequency: str
    in_app_enabled: bool
    critical_updates_only: bool
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass(slots=True)
class NotificationWebhook:
    """Notification webhook data model."""
    name: str
    url: str
    webhook_type: str
    is_enabled: bool
    events: list = field(default_factory=list)
    secret_encrypted: Optional[str] = None
    last_triggered: Optional[datetime] = None
    last_status_code: Optional[int] = None
    failure_count: int = 0
    id: Optional[int] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def _get_db():
    """Get database instance from Flask app context."""
    return get_db()


def _get_user_preferences(user_id: int) -> Optional[dict]:
    """Get notification preferences for user."""
    db = _get_db()
    prefs = db(db.notification_preferences.user_id == user_id).select().first()
    return prefs.as_dict() if prefs else None


def _create_user_preferences(user_id: int) -> dict:
    """Create default notification preferences for user."""
    db = _get_db()
    prefs_id = db.notification_preferences.insert(
        user_id=user_id,
        email_enabled=True,
        email_frequency="daily",
        in_app_enabled=True,
        critical_updates_only=False,
    )
    db.commit()
    return _get_user_preferences(user_id)


def _get_webhook(webhook_id: int) -> Optional[dict]:
    """Get webhook by ID."""
    db = _get_db()
    webhook = db(db.notification_webhooks.id == webhook_id).select().first()
    return webhook.as_dict() if webhook else None


def _list_user_webhooks(user_id: int) -> list[dict]:
    """List webhooks for a user."""
    db = _get_db()
    webhooks = db(db.notification_webhooks.created_by == user_id).select(
        orderby=db.notification_webhooks.created_at
    )
    return [w.as_dict() for w in webhooks]


def _validate_webhook_events(events: list) -> bool:
    """Validate webhook events list."""
    valid_events = [
        "deployment.created",
        "deployment.updated",
        "deployment.deleted",
        "deployment.failed",
        "version.update_available",
        "cluster.health_check",
        "app.installed",
        "app.uninstalled",
    ]
    if not isinstance(events, list):
        return False
    return all(event in valid_events for event in events) if events else True


@notifications_bp.route("/preferences", methods=["GET"])
@auth_required
def get_preferences():
    """Get user notification preferences."""
    user = get_current_user()
    user_id = user["id"]

    prefs = _get_user_preferences(user_id)

    if not prefs:
        prefs = _create_user_preferences(user_id)

    return jsonify({
        "preferences": prefs,
    }), 200


@notifications_bp.route("/preferences", methods=["PUT"])
@auth_required
def update_preferences():
    """Update user notification preferences."""
    user = get_current_user()
    user_id = user["id"]

    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    db = _get_db()

    # Get or create preferences
    prefs = _get_user_preferences(user_id)
    if not prefs:
        prefs = _create_user_preferences(user_id)
        prefs_id = prefs["id"]
    else:
        prefs_id = prefs["id"]

    update_data = {}

    # Email enabled
    if "email_enabled" in data:
        update_data["email_enabled"] = bool(data["email_enabled"])

    # Email frequency
    if "email_frequency" in data:
        freq = data["email_frequency"]
        if freq not in VALID_EMAIL_FREQUENCIES:
            return jsonify({
                "error": f"Invalid email frequency. Must be one of: {', '.join(VALID_EMAIL_FREQUENCIES)}"
            }), 400
        update_data["email_frequency"] = freq

    # In-app notifications
    if "in_app_enabled" in data:
        update_data["in_app_enabled"] = bool(data["in_app_enabled"])

    # Critical updates only
    if "critical_updates_only" in data:
        update_data["critical_updates_only"] = bool(data["critical_updates_only"])

    if not update_data:
        return jsonify({"error": "No valid fields to update"}), 400

    db(db.notification_preferences.id == prefs_id).update(**update_data)
    db.commit()

    updated_prefs = _get_user_preferences(user_id)

    return jsonify({
        "message": "Preferences updated successfully",
        "preferences": updated_prefs,
    }), 200


@notifications_bp.route("/webhooks", methods=["GET"])
@auth_required
def list_webhooks():
    """List user's webhooks."""
    user = get_current_user()
    user_id = user["id"]

    webhooks = _list_user_webhooks(user_id)

    return jsonify({
        "webhooks": webhooks,
        "count": len(webhooks),
    }), 200


@notifications_bp.route("/webhooks", methods=["POST"])
@auth_required
def create_webhook():
    """Create a new webhook."""
    user = get_current_user()
    user_id = user["id"]

    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    name = data.get("name", "").strip()
    url = data.get("url", "").strip()
    webhook_type = data.get("webhook_type", "generic")
    events = data.get("events", [])
    secret = data.get("secret", "").strip()

    # Validation
    if not name:
        return jsonify({"error": "Webhook name is required"}), 400

    if not url:
        return jsonify({"error": "Webhook URL is required"}), 400

    if webhook_type not in VALID_WEBHOOK_TYPES:
        return jsonify({
            "error": f"Invalid webhook type. Must be one of: {', '.join(VALID_WEBHOOK_TYPES)}"
        }), 400

    if not _validate_webhook_events(events):
        return jsonify({
            "error": "Invalid webhook events"
        }), 400

    # Validate URL format
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            raise ValueError("Invalid scheme")
    except Exception:
        return jsonify({"error": "Invalid webhook URL"}), 400

    db = _get_db()

    webhook_id = db.notification_webhooks.insert(
        name=name,
        url=url,
        webhook_type=webhook_type,
        events=events or [],
        secret_encrypted=secret if secret else None,
        is_enabled=True,
        created_by=user_id,
    )
    db.commit()

    webhook = _get_webhook(webhook_id)

    return jsonify({
        "message": "Webhook created successfully",
        "webhook": webhook,
    }), 201


@notifications_bp.route("/webhooks/<int:webhook_id>", methods=["GET"])
@auth_required
def get_webhook(webhook_id: int):
    """Get webhook by ID."""
    user = get_current_user()
    user_id = user["id"]

    webhook = _get_webhook(webhook_id)

    if not webhook:
        return jsonify({"error": "Webhook not found"}), 404

    # Check ownership
    if webhook["created_by"] != user_id:
        return jsonify({"error": "Unauthorized"}), 403

    return jsonify({
        "webhook": webhook,
    }), 200


@notifications_bp.route("/webhooks/<int:webhook_id>", methods=["PUT"])
@auth_required
def update_webhook(webhook_id: int):
    """Update webhook by ID."""
    user = get_current_user()
    user_id = user["id"]

    webhook = _get_webhook(webhook_id)

    if not webhook:
        return jsonify({"error": "Webhook not found"}), 404

    # Check ownership
    if webhook["created_by"] != user_id:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    db = _get_db()

    update_data = {}

    # Update name
    if "name" in data:
        name = data["name"].strip()
        if not name:
            return jsonify({"error": "Webhook name cannot be empty"}), 400
        update_data["name"] = name

    # Update URL
    if "url" in data:
        url = data["url"].strip()
        if not url:
            return jsonify({"error": "Webhook URL cannot be empty"}), 400
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if parsed.scheme not in ["http", "https"]:
                raise ValueError("Invalid scheme")
        except Exception:
            return jsonify({"error": "Invalid webhook URL"}), 400
        update_data["url"] = url

    # Update webhook type
    if "webhook_type" in data:
        webhook_type = data["webhook_type"]
        if webhook_type not in VALID_WEBHOOK_TYPES:
            return jsonify({
                "error": f"Invalid webhook type. Must be one of: {', '.join(VALID_WEBHOOK_TYPES)}"
            }), 400
        update_data["webhook_type"] = webhook_type

    # Update events
    if "events" in data:
        events = data["events"]
        if not _validate_webhook_events(events):
            return jsonify({"error": "Invalid webhook events"}), 400
        update_data["events"] = events or []

    # Update secret
    if "secret" in data:
        secret = data["secret"].strip()
        update_data["secret_encrypted"] = secret if secret else None

    # Update enabled status
    if "is_enabled" in data:
        update_data["is_enabled"] = bool(data["is_enabled"])

    if not update_data:
        return jsonify({"error": "No valid fields to update"}), 400

    db(db.notification_webhooks.id == webhook_id).update(**update_data)
    db.commit()

    updated_webhook = _get_webhook(webhook_id)

    return jsonify({
        "message": "Webhook updated successfully",
        "webhook": updated_webhook,
    }), 200


@notifications_bp.route("/webhooks/<int:webhook_id>", methods=["DELETE"])
@auth_required
def delete_webhook(webhook_id: int):
    """Delete webhook by ID."""
    user = get_current_user()
    user_id = user["id"]

    webhook = _get_webhook(webhook_id)

    if not webhook:
        return jsonify({"error": "Webhook not found"}), 404

    # Check ownership
    if webhook["created_by"] != user_id:
        return jsonify({"error": "Unauthorized"}), 403

    db = _get_db()

    db(db.notification_webhooks.id == webhook_id).delete()
    db.commit()

    return jsonify({
        "message": "Webhook deleted successfully",
    }), 200


@notifications_bp.route("/webhooks/<int:webhook_id>/test", methods=["POST"])
@auth_required
def test_webhook(webhook_id: int):
    """Test webhook with a sample payload."""
    user = get_current_user()
    user_id = user["id"]

    webhook = _get_webhook(webhook_id)

    if not webhook:
        return jsonify({"error": "Webhook not found"}), 404

    # Check ownership
    if webhook["created_by"] != user_id:
        return jsonify({"error": "Unauthorized"}), 403

    if not webhook["is_enabled"]:
        return jsonify({"error": "Webhook is disabled"}), 400

    # Prepare test payload
    test_payload = {
        "event": "test",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "message": "This is a test webhook payload",
            "source": "iceshelves",
        },
    }

    # Send test request
    try:
        headers = {"Content-Type": "application/json"}

        if webhook["secret_encrypted"]:
            import hmac
            import hashlib
            signature = hmac.new(
                webhook["secret_encrypted"].encode(),
                str(test_payload).encode(),
                hashlib.sha256,
            ).hexdigest()
            headers["X-Webhook-Signature"] = signature

        response = requests.post(
            webhook["url"],
            json=test_payload,
            headers=headers,
            timeout=10,
        )

        db = _get_db()

        # Update webhook status
        db(db.notification_webhooks.id == webhook_id).update(
            last_triggered=datetime.utcnow(),
            last_status_code=response.status_code,
            failure_count=0 if response.status_code < 400 else 1,
        )
        db.commit()

        return jsonify({
            "message": "Webhook test completed",
            "status_code": response.status_code,
            "response_time_ms": response.elapsed.total_seconds() * 1000,
            "success": response.status_code < 400,
        }), 200

    except requests.Timeout:
        db = _get_db()
        db(db.notification_webhooks.id == webhook_id).update(
            failure_count=webhook["failure_count"] + 1,
        )
        db.commit()
        return jsonify({
            "error": "Webhook request timeout",
            "success": False,
        }), 504

    except requests.RequestException as e:
        db = _get_db()
        db(db.notification_webhooks.id == webhook_id).update(
            failure_count=webhook["failure_count"] + 1,
        )
        db.commit()
        return jsonify({
            "error": f"Webhook request failed: {str(e)}",
            "success": False,
        }), 500

    except Exception as e:
        return jsonify({
            "error": f"Unexpected error: {str(e)}",
            "success": False,
        }), 500
