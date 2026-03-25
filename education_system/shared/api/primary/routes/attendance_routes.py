"""Attendance API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.academics.attendance.services.attendance_service import AttendanceService

attendance_bp = Blueprint("attendance", __name__, url_prefix="/api/attendance")

_db_path = None


def init_attendance_routes(db_path=None):
    global _db_path
    _db_path = db_path


@attendance_bp.route("", methods=["GET"])
@token_required
def list_attendance_records():
    svc = AttendanceService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_attendance_records(pupil_id=request.args.get("pupil_id"), date=request.args.get("date"), class_name=request.args.get("class_name"))
    total = len(items)
    return jsonify(paginated_response(items, total))


@attendance_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_attendance(pk):
    svc = AttendanceService(_db_path)
    item = svc.get_attendance(pk)
    if not item:
        return jsonify({"error": "Attendance not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@attendance_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_attendance():
    data = get_json_body()
    require_fields(data, "pupil_id", "date", "status")
    svc = AttendanceService(_db_path)
    result = svc.create_attendance(**data)
    return jsonify({"message": "Attendance created.", "data": result}), 201


@attendance_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_attendance(pk):
    data = get_json_body()
    svc = AttendanceService(_db_path)
    result = svc.update_attendance(pk, **data)
    return jsonify({"message": "Attendance updated.", "data": result})

@attendance_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_attendance(pk):
    svc = AttendanceService(_db_path)
    svc.delete_attendance(pk)
    return jsonify({"message": "Attendance deleted."})