"""API routes for staff hr."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.staff_hr.services.staff_hr_service import StaffHRService
from education_system.college_system.core.i18n import t

staff_hr_bp = Blueprint("staff-hr", __name__, url_prefix="/api/staff-hr")

_db_path = None


def init_staff_hr_routes(db_path=None):
    global _db_path
    _db_path = db_path


@staff_hr_bp.route("", methods=["GET"])
@token_required
@role_required('admin')
def list_records():
    svc = StaffHRService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_records(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@staff_hr_bp.route("/<int:pk>", methods=["GET"])
@token_required
@role_required('admin')
def get_record(pk):
    svc = StaffHRService(_db_path)
    item = svc.get_record(pk)
    if not item:
        return jsonify({"error": t("api.staff_hr.not_found")}), 404
    return jsonify({"data": item})
@staff_hr_bp.route("", methods=["POST"])
@token_required
@role_required('admin')
def create_record():
    data = get_json_body()
    svc = StaffHRService(_db_path)
    result = svc.create_record(**data)
    return jsonify({"message": t("api.staff_hr.created"), "data": result}), 201
@staff_hr_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin')
def update_record(pk):
    data = get_json_body()
    svc = StaffHRService(_db_path)
    result = svc.update_record(pk, **data)
    return jsonify({"message": t("api.staff_hr.updated"), "data": result})
@staff_hr_bp.route("/staff/<staff_id>", methods=["GET"])
@token_required
@role_required('admin')
def get_by_staff(staff_id):
    svc = StaffHRService(_db_path)
    item = svc.get_by_staff(staff_id)
    if not item:
        return jsonify({"error": t("api.staff_hr.not_found")}), 404
    return jsonify({"data": item})
