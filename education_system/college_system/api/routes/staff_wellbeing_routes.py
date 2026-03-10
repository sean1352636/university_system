"""API routes for staff wellbeing."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.staff_wellbeing.services.staff_wellbeing_service import StaffWellbeingService

staff_wellbeing_bp = Blueprint("staff-wellbeing", __name__, url_prefix="/api/staff-wellbeing")

_db_path = None


def init_staff_wellbeing_routes(db_path=None):
    global _db_path
    _db_path = db_path


@staff_wellbeing_bp.route("", methods=["GET"])
@token_required
def list_checkins():
    svc = StaffWellbeingService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_checkins(limit=limit, offset=offset)
    total = svc.count_checkins()
    return jsonify(paginated_response(items, total))


@staff_wellbeing_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_checkin(pk):
    svc = StaffWellbeingService(_db_path)
    item = svc.get_checkin(pk)
    if not item:
        return jsonify({"error": "Checkin not found."}), 404
    return jsonify({"data": item})


@staff_wellbeing_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_checkin():
    data = get_json_body()
    require_fields(data, "staff_id")
    svc = StaffWellbeingService(_db_path)
    item = svc.create_checkin(**data)
    return jsonify({"message": "Checkin created.", "data": item}), 201


@staff_wellbeing_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_checkin(pk):
    data = get_json_body()
    svc = StaffWellbeingService(_db_path)
    item = svc.update_checkin(pk, **data)
    return jsonify({"message": "Checkin updated.", "data": item})


@staff_wellbeing_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_checkin(pk):
    svc = StaffWellbeingService(_db_path)
    svc.delete_checkin(pk)
    return jsonify({"message": "Checkin deleted."})
