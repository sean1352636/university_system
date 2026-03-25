"""API routes for safeguarding."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.safeguarding.services.safeguarding_service import SafeguardingService
from education_system.college_system.core.i18n import t

safeguarding_bp = Blueprint("safeguarding", __name__, url_prefix="/api/safeguarding")

_db_path = None


def init_safeguarding_routes(db_path=None):
    global _db_path
    _db_path = db_path


@safeguarding_bp.route("", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_concerns():
    svc = SafeguardingService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_concerns(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@safeguarding_bp.route("/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_concern(pk):
    svc = SafeguardingService(_db_path)
    item = svc.get_concern(pk)
    if not item:
        return jsonify({"error": t("api.safeguarding.not_found")}), 404
    return jsonify({"data": item})
@safeguarding_bp.route("", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def report_concern():
    data = get_json_body()
    svc = SafeguardingService(_db_path)
    result = svc.report_concern(**data)
    return jsonify({"message": t("api.safeguarding.created"), "data": result}), 201
@safeguarding_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_concern(pk):
    data = get_json_body()
    svc = SafeguardingService(_db_path)
    result = svc.update_concern(pk, **data)
    return jsonify({"message": t("api.safeguarding.updated"), "data": result})
@safeguarding_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_concern(pk):
    svc = SafeguardingService(_db_path)
    svc.delete_concern(pk)
    return jsonify({"message": t("api.safeguarding.deleted")})
@safeguarding_bp.route("/student/<student_id>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_student_concerns(student_id):
    svc = SafeguardingService(_db_path)
    item = svc.get_student_concerns(student_id)
    if not item:
        return jsonify({"error": t("api.safeguarding.not_found")}), 404
    return jsonify({"data": item})
