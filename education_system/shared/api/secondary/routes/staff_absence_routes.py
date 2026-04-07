"""Staff absence API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.shared.api.secondary.pagination import get_pagination_params, paginated_response
from education_system.secondary_school.modules.domain.staff.staff_absence.services.staff_absence_service import StaffAbsenceService

staff_absence_bp = Blueprint("staff-absence", __name__, url_prefix="/api/staff-absence")

_db_path = None


def init_staff_absence_routes(db_path=None):
    global _db_path
    _db_path = db_path


@staff_absence_bp.route("", methods=["GET"])
@token_required
def list_staff_absence():
    svc = StaffAbsenceService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_all(limit=limit, offset=offset)
    total = len(items)
    return jsonify(paginated_response(items, total))


@staff_absence_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_staff_absence_item(pk):
    svc = StaffAbsenceService(_db_path)
    item = svc.get(pk)
    if not item:
        return jsonify({"error": "Not found."}), 404
    return jsonify({"data": item})


@staff_absence_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_staff_absence_item():
    data = get_json_body()
    svc = StaffAbsenceService(_db_path)
    result = svc.create(**data)
    return jsonify({"message": "Created.", "data": result}), 201


@staff_absence_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_staff_absence_item(pk):
    data = get_json_body()
    svc = StaffAbsenceService(_db_path)
    result = svc.update(pk, **data)
    return jsonify({"message": "Updated.", "data": result})


@staff_absence_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_staff_absence_item(pk):
    svc = StaffAbsenceService(_db_path)
    svc.delete(pk)
    return jsonify({"message": "Deleted."})
