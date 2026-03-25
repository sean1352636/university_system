"""Notification API routes."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.college_system.modules.domain.notifications.services.notification_service import NotificationService
from education_system.college_system.core.i18n import t

notification_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")

_db_path = None


def init_notification_routes(db_path=None):
    global _db_path
    _db_path = db_path


@notification_bp.route("", methods=["GET"])
@token_required
def get_notifications():
    svc = NotificationService(_db_path)
    user_id = g.current_user["user_id"]
    unread_only = request.args.get("unread_only", "false").lower() == "true"
    limit = request.args.get("limit", 50, type=int)

    notifications = svc.get_notifications(user_id, unread_only=unread_only, limit=limit)
    return jsonify({"data": notifications, "count": len(notifications)})


@notification_bp.route("/count", methods=["GET"])
@token_required
def count_unread():
    svc = NotificationService(_db_path)
    count = svc.count_unread(g.current_user["user_id"])
    return jsonify({"unread_count": count})


@notification_bp.route("/<int:notification_id>/read", methods=["POST"])
@token_required
def mark_read(notification_id):
    svc = NotificationService(_db_path)
    svc.mark_read(notification_id, g.current_user["user_id"])
    return jsonify({"message": t("api.notification.marked_read")})


@notification_bp.route("/read-all", methods=["POST"])
@token_required
def mark_all_read():
    svc = NotificationService(_db_path)
    count = svc.mark_all_read(g.current_user["user_id"])
    return jsonify({"message": t("api.notification.all_marked_read"), "count": count})


@notification_bp.route("/send", methods=["POST"])
@token_required
@role_required("admin", "staff")
def send_notification():
    data = get_json_body()
    require_fields(data, "user_id", "title")

    svc = NotificationService(_db_path)
    notification = svc.send(
        data["user_id"], data["title"],
        message=data.get("message"),
        type=data.get("type", "info"),
    )
    return jsonify({"message": t("api.notification.sent"), "data": notification}), 201
