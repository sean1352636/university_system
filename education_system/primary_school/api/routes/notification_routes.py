"""Notifications API routes."""

from flask import Blueprint, jsonify, request

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.api.validators import get_json_body, require_fields
from education_system.primary_school.api.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.communication.notifications.services.notification_service import NotificationService

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")

_db_path = None


def init_notifications_routes(db_path=None):
    global _db_path
    _db_path = db_path


@notifications_bp.route("", methods=["GET"])
@token_required
def list_notifications():
    svc = NotificationService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_notifications(user_id=request.args.get("user_id"))
    total = len(items)
    return jsonify(paginated_response(items, total))


@notifications_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_notification(pk):
    svc = NotificationService(_db_path)
    item = svc.get_notification(pk)
    if not item:
        return jsonify({"error": "Notification not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@notifications_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_notification():
    data = get_json_body()
    require_fields(data, "user_id", "title", "message")
    svc = NotificationService(_db_path)
    result = svc.create_notification(**data)
    return jsonify({"message": "Notification created.", "data": result}), 201


@notifications_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_notification(pk):
    data = get_json_body()
    svc = NotificationService(_db_path)
    result = svc.update_notification(pk, **data)
    return jsonify({"message": "Notification updated.", "data": result})

@notifications_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_notification(pk):
    svc = NotificationService(_db_path)
    svc.delete_notification(pk)
    return jsonify({"message": "Notification deleted."})