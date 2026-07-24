"""REST API routes for webhook management (admin only).

Endpoints:
    GET    /api/v1/webhooks/subscriptions     — list subscriptions
    POST   /api/v1/webhooks/subscriptions     — create subscription
    DELETE /api/v1/webhooks/subscriptions/<id> — deactivate subscription
    POST   /api/v1/webhooks/test/<id>         — send test event
    GET    /api/v1/webhooks/deliveries        — list recent deliveries
"""

import logging
from flask import Blueprint, request, jsonify

from education_system.shared.api.auth import role_required

logger = logging.getLogger(__name__)

webhook_bp = Blueprint("webhooks", __name__, url_prefix="/api/webhooks")

_webhook_service = None


def init_webhook_routes(db_path: str | None = None):
    """Initialise the webhook routes with a service instance."""
    global _webhook_service
    from education_system.shared.webhooks.webhook_service import WebhookService
    _webhook_service = WebhookService(db_path)


def _svc():
    if _webhook_service is None:
        from education_system.shared.webhooks.webhook_service import WebhookService
        return WebhookService()
    return _webhook_service


@webhook_bp.route("/subscriptions", methods=["GET"])
@role_required("admin")
def list_subscriptions():
    """List all webhook subscriptions."""
    system_key = request.args.get("system_key")
    active_only = request.args.get("active_only", "true").lower() == "true"
    subs = _svc().list_subscriptions(system_key=system_key, active_only=active_only)
    return jsonify({"subscriptions": subs, "count": len(subs)})


@webhook_bp.route("/subscriptions", methods=["POST"])
@role_required("admin")
def create_subscription():
    """Register a new webhook subscription.

    Request body:
        {"url": "https://...", "event_types": ["student.enrolled"], "system_key": "sixth_form",
         "secret": "optional-hmac-secret", "description": "My webhook"}
    """
    data = request.get_json(silent=True)
    if not data or not data.get("url"):
        return jsonify({"error": "url is required"}), 400

    from flask import g
    sub_id = _svc().subscribe(
        url=data["url"],
        event_types=data.get("event_types"),
        system_key=data.get("system_key", "all"),
        secret=data.get("secret"),
        description=data.get("description"),
        created_by=g.current_user.get("user_id"),
    )
    return jsonify({"message": "Subscription created", "id": sub_id}), 201


@webhook_bp.route("/subscriptions/<int:sub_id>", methods=["DELETE"])
@role_required("admin")
def delete_subscription(sub_id):
    """Deactivate a webhook subscription."""
    success = _svc().unsubscribe(sub_id)
    if not success:
        return jsonify({"error": "Subscription not found"}), 404
    return jsonify({"message": "Subscription deactivated", "id": sub_id})


@webhook_bp.route("/test/<int:sub_id>", methods=["POST"])
@role_required("admin")
def test_webhook(sub_id):
    """Send a test event to a specific subscription."""
    count = _svc().dispatch(
        event_type="webhook.test",
        payload={"message": "Test webhook delivery", "subscription_id": sub_id},
        system_key="shared",
    )
    return jsonify({"message": "Test event dispatched", "deliveries_queued": count})


@webhook_bp.route("/deliveries", methods=["GET"])
@role_required("admin")
def list_deliveries():
    """List recent webhook deliveries."""
    limit = min(int(request.args.get("limit", 50)), 200)
    deliveries = _svc().get_recent_deliveries(limit=limit)
    return jsonify({"deliveries": deliveries, "count": len(deliveries)})
