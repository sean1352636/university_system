"""API routes for staff."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.staff.services.staff_service import StaffService
from education_system.college_system.core.i18n import t

staff_bp = Blueprint("staff", __name__, url_prefix="/api/staff")

_db_path = None


def init_staff_routes(db_path=None):
    global _db_path
    _db_path = db_path


@staff_bp.route("", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_staff():
    svc = StaffService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_staff(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@staff_bp.route("/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_staff(pk):
    svc = StaffService(_db_path)
    item = svc.get_staff(pk)
    if not item:
        return jsonify({"error": t("api.staff.not_found")}), 404
    return jsonify({"data": item})
@staff_bp.route("", methods=["POST"])
@token_required
@role_required('admin')
def create_staff():
    data = get_json_body()
    svc = StaffService(_db_path)
    result = svc.create_staff(**data)
    return jsonify({"message": t("api.staff.created"), "data": result}), 201
@staff_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin')
def update_staff(pk):
    data = get_json_body()
    svc = StaffService(_db_path)
    result = svc.update_staff(pk, **data)
    return jsonify({"message": t("api.staff.updated"), "data": result})
@staff_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_staff(pk):
    svc = StaffService(_db_path)
    svc.delete_staff(pk)
    return jsonify({"message": t("api.staff.deleted")})
@staff_bp.route("/<int:pk>/courses", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_assigned_courses(pk):
    svc = StaffService(_db_path)
    item = svc.get_assigned_courses(pk)
    if not item:
        return jsonify({"error": t("api.staff.not_found")}), 404
    return jsonify({"data": item})
