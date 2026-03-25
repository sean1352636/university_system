"""Notifications API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.communication.notifications.services.notification_service import NotificationService

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")

_db_path = None


def init_notifications_routes(db_path=None):
    global _db_path
    _db_path = db_path


@notifications_bp.route("", methods=["POST"])
@token_required
def create_notification():
    data = get_json_body()
    require_fields(data, "user_id", "message")
    svc = NotificationService(_db_path)
    result = svc.create(user_id=data["user_id"], message=data["message"], notification_type=data.get("type", "info"))
    return jsonify({"message": "Created.", "data": result}), 201


@notifications_bp.route("/user/<int:user_id>", methods=["GET"])
@token_required
def list_notifications(user_id):
    svc = NotificationService(_db_path)
    result = svc.list_notifications(user_id)
    return jsonify({"data": result})


@notifications_bp.route("/<int:notif_id>/read", methods=["PUT"])
@token_required
def mark_read(notif_id):
    svc = NotificationService(_db_path)
    result = svc.mark_read(notif_id)
    return jsonify({"message": "Updated.", "data": result})


@notifications_bp.route("/user/<int:user_id>/read-all", methods=["PUT"])
@token_required
def mark_all_read(user_id):
    svc = NotificationService(_db_path)
    result = svc.mark_all_read(user_id)
    return jsonify({"message": "Updated.", "data": result})


@notifications_bp.route("/<int:notif_id>", methods=["DELETE"])
@token_required
def delete_notification(notif_id):
    svc = NotificationService(_db_path)
    result = svc.delete_notification(notif_id)
    return jsonify({"message": "Deleted.", "data": result})


@notifications_bp.route("/user/<int:user_id>/unread", methods=["GET"])
@token_required
def unread_count(user_id):
    svc = NotificationService(_db_path)
    result = svc.unread_count(user_id)
    return jsonify({"data": result})

