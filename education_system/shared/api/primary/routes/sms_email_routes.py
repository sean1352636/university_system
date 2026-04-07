"""SMS and email API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.communication.sms_email.services.sms_email_service import SmsEmailService

sms_email_bp = Blueprint("sms-email", __name__, url_prefix="/api/sms-email")

_db_path = None


def init_sms_email_routes(db_path=None):
    global _db_path
    _db_path = db_path


@sms_email_bp.route("", methods=["GET"])
@token_required
def list_sms_email():
    svc = SmsEmailService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_all(limit=limit, offset=offset)
    total = len(items)
    return jsonify(paginated_response(items, total))


@sms_email_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_sms_email_item(pk):
    svc = SmsEmailService(_db_path)
    item = svc.get(pk)
    if not item:
        return jsonify({"error": "Not found."}), 404
    return jsonify({"data": item})


@sms_email_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_sms_email_item():
    data = get_json_body()
    svc = SmsEmailService(_db_path)
    result = svc.create(**data)
    return jsonify({"message": "Created.", "data": result}), 201


@sms_email_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_sms_email_item(pk):
    data = get_json_body()
    svc = SmsEmailService(_db_path)
    result = svc.update(pk, **data)
    return jsonify({"message": "Updated.", "data": result})


@sms_email_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_sms_email_item(pk):
    svc = SmsEmailService(_db_path)
    svc.delete(pk)
    return jsonify({"message": "Deleted."})
