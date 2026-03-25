"""API routes for first aid."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.first_aid.services.first_aid_service import FirstAidService
from education_system.college_system.core.i18n import t

first_aid_bp = Blueprint("first-aid", __name__, url_prefix="/api/first-aid")

_db_path = None


def init_first_aid_routes(db_path=None):
    global _db_path
    _db_path = db_path


@first_aid_bp.route("", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_incidents():
    svc = FirstAidService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_incidents(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@first_aid_bp.route("/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_incident(pk):
    svc = FirstAidService(_db_path)
    item = svc.get_incident(pk)
    if not item:
        return jsonify({"error": t("api.first_aid.not_found")}), 404
    return jsonify({"data": item})
@first_aid_bp.route("", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def report_incident():
    data = get_json_body()
    svc = FirstAidService(_db_path)
    result = svc.report_incident(**data)
    return jsonify({"message": t("api.first_aid.created"), "data": result}), 201
@first_aid_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_incident(pk):
    data = get_json_body()
    svc = FirstAidService(_db_path)
    result = svc.update_incident(pk, **data)
    return jsonify({"message": t("api.first_aid.updated"), "data": result})
@first_aid_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_incident(pk):
    svc = FirstAidService(_db_path)
    svc.delete_incident(pk)
    return jsonify({"message": t("api.first_aid.deleted")})
