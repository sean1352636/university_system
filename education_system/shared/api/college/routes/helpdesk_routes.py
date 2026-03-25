"""API routes for helpdesk."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.helpdesk.services.helpdesk_service import HelpdeskService
from education_system.college_system.core.i18n import t

helpdesk_bp = Blueprint("helpdesk", __name__, url_prefix="/api/helpdesk")

_db_path = None


def init_helpdesk_routes(db_path=None):
    global _db_path
    _db_path = db_path


@helpdesk_bp.route("", methods=["GET"])
@token_required
def list_tickets():
    svc = HelpdeskService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_tickets(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@helpdesk_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_ticket(pk):
    svc = HelpdeskService(_db_path)
    item = svc.get_ticket(pk)
    if not item:
        return jsonify({"error": t("api.helpdesk.not_found")}), 404
    return jsonify({"data": item})
@helpdesk_bp.route("", methods=["POST"])
@token_required
def create_ticket():
    data = get_json_body()
    svc = HelpdeskService(_db_path)
    result = svc.create_ticket(**data)
    return jsonify({"message": t("api.helpdesk.created"), "data": result}), 201
@helpdesk_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_ticket(pk):
    data = get_json_body()
    svc = HelpdeskService(_db_path)
    result = svc.update_ticket(pk, **data)
    return jsonify({"message": t("api.helpdesk.updated"), "data": result})
@helpdesk_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_ticket(pk):
    svc = HelpdeskService(_db_path)
    svc.delete_ticket(pk)
    return jsonify({"message": t("api.helpdesk.deleted")})
@helpdesk_bp.route("/<int:pk>/assign", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def assign_ticket(pk):
    data = get_json_body()
    svc = HelpdeskService(_db_path)
    result = svc.assign_ticket(pk, **data)
    return jsonify({"message": t("api.helpdesk.success"), "data": result}), 201
@helpdesk_bp.route("/<int:pk>/respond", methods=["POST"])
@token_required
def add_response(pk):
    data = get_json_body()
    svc = HelpdeskService(_db_path)
    result = svc.add_response(pk, **data)
    return jsonify({"message": t("api.helpdesk.success"), "data": result}), 201
