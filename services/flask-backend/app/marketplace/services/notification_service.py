"""
Notification delivery service for marketplace updates.

Handles webhook delivery, email notifications, and formatted messages
for Slack, Discord, and MS Teams integration.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from flask import current_app

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class NotificationPayload:
    """Notification payload with cluster and resource information."""

    event: str
    timestamp: datetime
    cluster: str
    resources: List[Dict[str, Any]] = field(default_factory=list)
    iceshelves_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert payload to dictionary format."""
        return {
            "event": self.event,
            "timestamp": self.timestamp.isoformat(),
            "cluster": self.cluster,
            "resources": self.resources,
            "iceshelves_url": self.iceshelves_url,
        }


class NotificationService:
    """Service for managing notification delivery across multiple channels."""

    def __init__(self, app=None):
        """Initialize notification service.

        Args:
            app: Flask application instance (optional)
        """
        self.app = app

    def send_webhook(self, webhook_config: Dict[str, Any], payload: NotificationPayload) -> bool:
        """Send notification to generic webhook endpoint.

        Args:
            webhook_config: Configuration with 'url' and optional 'headers'
            payload: NotificationPayload instance

        Returns:
            True if webhook delivery succeeded, False otherwise
        """
        try:
            url = webhook_config.get("url")
            if not url:
                logger.error("Webhook URL not provided in configuration")
                return False

            headers = webhook_config.get("headers", {"Content-Type": "application/json"})
            timeout = webhook_config.get("timeout", 10)

            response = requests.post(
                url,
                json=payload.to_dict(),
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()

            logger.info(f"Webhook delivered successfully to {url}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Webhook delivery failed: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during webhook delivery: {str(e)}")
            return False

    def format_slack_message(self, payload: NotificationPayload) -> Dict[str, Any]:
        """Format notification for Slack webhook.

        Args:
            payload: NotificationPayload instance

        Returns:
            Dictionary formatted for Slack's Block Kit API
        """
        color_map = {
            "update_available": "#0099FF",
            "deployment_started": "#FFA500",
            "deployment_complete": "#00CC00",
            "deployment_failed": "#FF0000",
            "error": "#FF0000",
        }

        color = color_map.get(payload.event, "#808080")
        event_text = payload.event.replace("_", " ").title()

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Ice Shelves Notification - {event_text}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Event:*\n{event_text}"},
                    {"type": "mrkdwn", "text": f"*Cluster:*\n{payload.cluster}"},
                    {"type": "mrkdwn", "text": f"*Time:*\n{payload.timestamp.isoformat()}"},
                    {"type": "mrkdwn", "text": f"*Resources:*\n{len(payload.resources)}"},
                ],
            },
        ]

        if payload.resources:
            resource_text = "\n".join(
                [f"• {r.get('name', 'Unknown')}: {r.get('version', 'N/A')}" for r in payload.resources]
            )
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Resources Affected:*\n{resource_text}",
                    },
                }
            )

        if payload.iceshelves_url:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"<{payload.iceshelves_url}|View in Ice Shelves>",
                    },
                }
            )

        return {
            "blocks": blocks,
            "attachments": [
                {
                    "color": color,
                    "fallback": event_text,
                }
            ],
        }

    def format_discord_message(self, payload: NotificationPayload) -> Dict[str, Any]:
        """Format notification for Discord webhook.

        Args:
            payload: NotificationPayload instance

        Returns:
            Dictionary formatted for Discord's message API
        """
        color_map = {
            "update_available": 0x0099FF,
            "deployment_started": 0xFFA500,
            "deployment_complete": 0x00CC00,
            "deployment_failed": 0xFF0000,
            "error": 0xFF0000,
        }

        color = color_map.get(payload.event, 0x808080)
        event_text = payload.event.replace("_", " ").title()

        fields = [
            {"name": "Event", "value": event_text, "inline": True},
            {"name": "Cluster", "value": payload.cluster, "inline": True},
            {"name": "Time", "value": payload.timestamp.isoformat(), "inline": False},
            {"name": "Resources Affected", "value": str(len(payload.resources)), "inline": True},
        ]

        if payload.resources:
            resource_list = "\n".join(
                [f"• {r.get('name', 'Unknown')}: {r.get('version', 'N/A')}" for r in payload.resources]
            )
            fields.append({"name": "Details", "value": resource_list, "inline": False})

        embed = {
            "title": f"Ice Shelves - {event_text}",
            "color": color,
            "fields": fields,
            "timestamp": payload.timestamp.isoformat(),
        }

        if payload.iceshelves_url:
            embed["url"] = payload.iceshelves_url

        return {"embeds": [embed]}

    def format_teams_message(self, payload: NotificationPayload) -> Dict[str, Any]:
        """Format notification for MS Teams webhook.

        Args:
            payload: NotificationPayload instance

        Returns:
            Dictionary formatted for Microsoft Teams Adaptive Card
        """
        color_map = {
            "update_available": "0078D4",
            "deployment_started": "FFA500",
            "deployment_complete": "107C10",
            "deployment_failed": "E81123",
            "error": "E81123",
        }

        color = color_map.get(payload.event, "737373")
        event_text = payload.event.replace("_", " ").title()

        facts = [
            {"name": "Event", "value": event_text},
            {"name": "Cluster", "value": payload.cluster},
            {"name": "Time", "value": payload.timestamp.isoformat()},
            {"name": "Resources Affected", "value": str(len(payload.resources))},
        ]

        if payload.resources:
            resource_list = "\n".join(
                [f"• {r.get('name', 'Unknown')}: {r.get('version', 'N/A')}" for r in payload.resources]
            )
            facts.append({"name": "Details", "value": resource_list})

        potential_action = []
        if payload.iceshelves_url:
            potential_action.append(
                {
                    "@type": "OpenUri",
                    "name": "View in Ice Shelves",
                    "targets": [{"os": "default", "uri": payload.iceshelves_url}],
                }
            )

        return {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": f"Ice Shelves - {event_text}",
            "themeColor": color,
            "sections": [
                {
                    "activityTitle": f"Ice Shelves Notification",
                    "activitySubtitle": event_text,
                    "facts": facts,
                }
            ],
            "potentialAction": potential_action,
        }

    def send_email(self, user_email: str, payload: NotificationPayload) -> bool:
        """Send email notification to user.

        Args:
            user_email: Recipient email address
            payload: NotificationPayload instance

        Returns:
            True if email delivery succeeded, False otherwise
        """
        try:
            # Import here to avoid circular dependencies
            from flask_mail import Mail, Message

            if not current_app:
                logger.error("Flask app context not available for email delivery")
                return False

            mail = Mail(current_app)
            event_text = payload.event.replace("_", " ").title()

            subject = f"Ice Shelves Notification: {event_text}"

            resource_details = ""
            if payload.resources:
                resource_details = "\n".join(
                    [f"  • {r.get('name', 'Unknown')}: {r.get('version', 'N/A')}" for r in payload.resources]
                )
                resource_details = f"\nAffected Resources:\n{resource_details}"

            body = f"""
Event: {event_text}
Cluster: {payload.cluster}
Time: {payload.timestamp.isoformat()}
Resources Affected: {len(payload.resources)}{resource_details}

For more details, visit: {payload.iceshelves_url}
"""

            msg = Message(
                subject=subject,
                recipients=[user_email],
                body=body,
                sender=current_app.config.get("MAIL_DEFAULT_SENDER", "noreply@iceshelves.local"),
            )

            mail.send(msg)
            logger.info(f"Email notification sent to {user_email}")
            return True

        except Exception as e:
            logger.error(f"Email delivery failed: {str(e)}")
            return False

    def notify_update_available(
        self, db, cluster_id: str, updates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Trigger notifications for available updates.

        Args:
            db: Database instance
            cluster_id: ID of the cluster with available updates
            updates: List of available updates with details

        Returns:
            Dictionary with notification results
        """
        try:
            # Query cluster and notification preferences from database
            cluster_query = db(db.clusters.id == cluster_id).select().first()
            if not cluster_query:
                logger.error(f"Cluster {cluster_id} not found")
                return {"success": False, "error": "Cluster not found"}

            cluster_name = cluster_query.name

            # Create notification payload
            payload = NotificationPayload(
                event="update_available",
                timestamp=datetime.utcnow(),
                cluster=cluster_name,
                resources=updates,
                iceshelves_url=current_app.config.get("ICESHELVES_URL", ""),
            )

            # Get notification preferences for cluster
            prefs_query = db(db.notification_preferences.cluster_id == cluster_id).select()

            results = {
                "cluster_id": cluster_id,
                "cluster_name": cluster_name,
                "update_count": len(updates),
                "notifications": {
                    "webhooks": [],
                    "emails": [],
                    "slack": [],
                    "discord": [],
                    "teams": [],
                },
            }

            for pref in prefs_query:
                if pref.webhook_url and pref.enabled:
                    webhook_config = {
                        "url": pref.webhook_url,
                        "headers": {"Content-Type": "application/json"},
                    }
                    success = self.send_webhook(webhook_config, payload)
                    results["notifications"]["webhooks"].append(
                        {"url": pref.webhook_url, "success": success}
                    )

                if pref.email and pref.enabled:
                    success = self.send_email(pref.email, payload)
                    results["notifications"]["emails"].append(
                        {"email": pref.email, "success": success}
                    )

                if pref.slack_webhook and pref.enabled:
                    slack_msg = self.format_slack_message(payload)
                    success = self.send_webhook(
                        {"url": pref.slack_webhook},
                        payload,
                    )
                    if success:
                        try:
                            requests.post(pref.slack_webhook, json=slack_msg, timeout=10)
                        except Exception as e:
                            logger.error(f"Slack message format send failed: {str(e)}")
                    results["notifications"]["slack"].append(
                        {"webhook": pref.slack_webhook, "success": success}
                    )

                if pref.discord_webhook and pref.enabled:
                    discord_msg = self.format_discord_message(payload)
                    success = self.send_webhook(
                        {"url": pref.discord_webhook},
                        payload,
                    )
                    if success:
                        try:
                            requests.post(pref.discord_webhook, json=discord_msg, timeout=10)
                        except Exception as e:
                            logger.error(f"Discord message format send failed: {str(e)}")
                    results["notifications"]["discord"].append(
                        {"webhook": pref.discord_webhook, "success": success}
                    )

                if pref.teams_webhook and pref.enabled:
                    teams_msg = self.format_teams_message(payload)
                    success = self.send_webhook(
                        {"url": pref.teams_webhook},
                        payload,
                    )
                    if success:
                        try:
                            requests.post(pref.teams_webhook, json=teams_msg, timeout=10)
                        except Exception as e:
                            logger.error(f"Teams message format send failed: {str(e)}")
                    results["notifications"]["teams"].append(
                        {"webhook": pref.teams_webhook, "success": success}
                    )

            logger.info(f"Update notifications sent for cluster {cluster_name}")
            return {"success": True, "data": results}

        except Exception as e:
            logger.error(f"Error triggering update notifications: {str(e)}")
            return {"success": False, "error": str(e)}
