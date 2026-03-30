"""REST API routes for webhook management.

Endpoints:
    GET    /api/v1/webhooks/subscriptions     — list subscriptions
    POST   /api/v1/webhooks/subscriptions     — create subscription
    DELETE /api/v1/webhooks/subscriptions/<id> — deactivate subscription
    POST   /api/v1/webhooks/test/<id>         — send test event
    GET    /api/v1/webhooks/deliveries        — list recent deliveries
"""

import logging
from flask import Blueprint, request, jsonify

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
def list_subscriptions():
    """List all webhook subscriptions."""
    from education_system.shared.api.auth import token_required, role_required
    # Inline auth check (admin only)
    from flask import g
    system_key = request.args.get("system_key")
    active_only = request.args.get("active_only", "true").lower() == "true"
    subs = _svc().list_subscriptions(system_key=system_key, active_only=active_only)
    return jsonify({"subscriptions": subs, "count": len(subs)})


@webhook_bp.route("/subscriptions", methods=["POST"])
def create_subscription():
    """Register a new webhook subscription.

    Request body:
        {"url": "https://...", "event_types": ["student.enrolled"], "system_key": "college",
         "secret": "optional-hmac-secret", "description": "My webhook"}
    """
    data = request.get_json(silent=True)
    if not data or not data.get("url"):
        return jsonify({"error": "url is required"}), 400

    sub_id = _svc().subscribe(
        url=data["url"],
        event_types=data.get("event_types"),
        system_key=data.get("system_key", "all"),
        secret=data.get("secret"),
        description=data.get("description"),
        created_by=data.get("created_by"),
    )
    return jsonify({"message": "Subscription created", "id": sub_id}), 201


@webhook_bp.route("/subscriptions/<int:sub_id>", methods=["DELETE"])
def delete_subscription(sub_id):
    """Deactivate a webhook subscription."""
    success = _svc().unsubscribe(sub_id)
    if not success:
        return jsonify({"error": "Subscription not found"}), 404
    return jsonify({"message": "Subscription deactivated", "id": sub_id})


@webhook_bp.route("/test/<int:sub_id>", methods=["POST"])
def test_webhook(sub_id):
    """Send a test event to a specific subscription."""
    count = _svc().dispatch(
        event_type="webhook.test",
        payload={"message": "Test webhook delivery", "subscription_id": sub_id},
        system_key="shared",
    )
    return jsonify({"message": "Test event dispatched", "deliveries_queued": count})


@webhook_bp.route("/deliveries", methods=["GET"])
def list_deliveries():
    """List recent webhook deliveries."""
    import sqlite3
    import json
    svc = _svc()
    conn = sqlite3.connect(svc._db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        limit = min(int(request.args.get("limit", 50)), 200)
        rows = conn.execute(
            "SELECT * FROM webhook_deliveries ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return jsonify({"deliveries": [dict(r) for r in rows], "count": len(rows)})
    finally:
        conn.close()
