"""API routes for staff absence."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.staff_absence.services.staff_absence_service import StaffAbsenceService
from education_system.college_system.core.i18n import t

staff_absence_bp = Blueprint("staff-absence", __name__, url_prefix="/api/staff-absence")

_db_path = None


def init_staff_absence_routes(db_path=None):
    global _db_path
    _db_path = db_path


@staff_absence_bp.route("", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_absences():
    svc = StaffAbsenceService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_absences(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@staff_absence_bp.route("/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_absence(pk):
    svc = StaffAbsenceService(_db_path)
    item = svc.get_absence(pk)
    if not item:
        return jsonify({"error": t("api.staff_absence.not_found")}), 404
    return jsonify({"data": item})
@staff_absence_bp.route("", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_absence():
    data = get_json_body()
    svc = StaffAbsenceService(_db_path)
    result = svc.create_absence(**data)
    return jsonify({"message": t("api.staff_absence.created"), "data": result}), 201
@staff_absence_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_absence(pk):
    data = get_json_body()
    svc = StaffAbsenceService(_db_path)
    result = svc.update_absence(pk, **data)
    return jsonify({"message": t("api.staff_absence.updated"), "data": result})
@staff_absence_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_absence(pk):
    svc = StaffAbsenceService(_db_path)
    svc.delete_absence(pk)
    return jsonify({"message": t("api.staff_absence.deleted")})
@staff_absence_bp.route("/<int:pk>/close", methods=["POST"])
@token_required
@role_required('admin')
def close_absence(pk):
    data = get_json_body()
    svc = StaffAbsenceService(_db_path)
    result = svc.close_absence(pk, **data)
    return jsonify({"message": t("api.staff_absence.success"), "data": result}), 201
@staff_absence_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin')
def get_stats():
    svc = StaffAbsenceService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
