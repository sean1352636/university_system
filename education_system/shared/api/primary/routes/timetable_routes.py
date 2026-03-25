"""Timetable API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.academics.timetable.services.timetable_service import TimetableService

timetable_bp = Blueprint("timetable", __name__, url_prefix="/api/timetable")

_db_path = None


def init_timetable_routes(db_path=None):
    global _db_path
    _db_path = db_path


@timetable_bp.route("", methods=["GET"])
@token_required
def list_slots():
    svc = TimetableService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_slots(class_name=request.args.get("class_name"), day=request.args.get("day"))
    total = len(items)
    return jsonify(paginated_response(items, total))


@timetable_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_slot(pk):
    svc = TimetableService(_db_path)
    item = svc.get_slot(pk)
    if not item:
        return jsonify({"error": "Slot not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@timetable_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_slot():
    data = get_json_body()
    require_fields(data, "class_name", "day", "period", "subject_code")
    svc = TimetableService(_db_path)
    result = svc.create_slot(**data)
    return jsonify({"message": "Slot created.", "data": result}), 201


@timetable_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_slot(pk):
    data = get_json_body()
    svc = TimetableService(_db_path)
    result = svc.update_slot(pk, **data)
    return jsonify({"message": "Slot updated.", "data": result})

@timetable_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_slot(pk):
    svc = TimetableService(_db_path)
    svc.delete_slot(pk)
    return jsonify({"message": "Slot deleted."})