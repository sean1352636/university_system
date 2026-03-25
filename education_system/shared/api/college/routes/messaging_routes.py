"""API routes for messaging."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.messaging.services.message_service import MessageService
from education_system.college_system.core.i18n import t

messaging_bp = Blueprint("messaging", __name__, url_prefix="/api/messaging")

_db_path = None


def init_messaging_routes(db_path=None):
    global _db_path
    _db_path = db_path


@messaging_bp.route("/inbox", methods=["GET"])
@token_required
def get_inbox():
    svc = MessageService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.get_inbox(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@messaging_bp.route("/sent", methods=["GET"])
@token_required
def get_sent():
    svc = MessageService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.get_sent(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@messaging_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_message(pk):
    svc = MessageService(_db_path)
    item = svc.get_message(pk)
    if not item:
        return jsonify({"error": t("api.messaging.not_found")}), 404
    return jsonify({"data": item})
@messaging_bp.route("", methods=["POST"])
@token_required
def send_message():
    data = get_json_body()
    svc = MessageService(_db_path)
    result = svc.send_message(**data)
    return jsonify({"message": t("api.messaging.created"), "data": result}), 201
@messaging_bp.route("/<int:pk>/read", methods=["POST"])
@token_required
def mark_read(pk):
    data = get_json_body()
    svc = MessageService(_db_path)
    result = svc.mark_read(pk, **data)
    return jsonify({"message": t("api.messaging.success"), "data": result}), 201
@messaging_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
def delete_message(pk):
    svc = MessageService(_db_path)
    svc.delete_message(pk)
    return jsonify({"message": t("api.messaging.deleted")})
@messaging_bp.route("/unread-count", methods=["GET"])
@token_required
def count_unread():
    svc = MessageService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.count_unread(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
