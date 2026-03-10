"""Attendance API routes."""

from flask import Blueprint, jsonify, request

from education_system.secondary_school.api.auth import token_required, role_required
from education_system.secondary_school.api.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.academics.attendance.services.attendance_service import AttendanceService

attendance_bp = Blueprint("attendance", __name__, url_prefix="/api/attendance")

_db_path = None


def init_attendance_routes(db_path=None):
    global _db_path
    _db_path = db_path


@attendance_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def record_attendance():
    data = get_json_body()
    require_fields(data, "student_id", "date")

    svc = AttendanceService(_db_path)
    record = svc.record_attendance(
        student_id=data["student_id"],
        date_str=data["date"],
        status=data.get("status", "present"),
        subject_id=data.get("subject_id"),
        period=data.get("period"),
        note=data.get("note"),
        recorded_by=data.get("recorded_by"),
    )
    return jsonify({"message": "Attendance recorded.", "data": record}), 201


@attendance_bp.route("/student/<int:student_id>", methods=["GET"])
@token_required
def get_student_attendance(student_id):
    svc = AttendanceService(_db_path)
    records = svc.get_student_attendance(
        student_id,
        start_date=request.args.get("start_date"),
        end_date=request.args.get("end_date"),
    )
    return jsonify({"data": records})


@attendance_bp.route("/student/<int:student_id>/summary", methods=["GET"])
@token_required
def get_student_summary(student_id):
    svc = AttendanceService(_db_path)
    summary = svc.get_attendance_summary(student_id)
    return jsonify({"data": summary})


@attendance_bp.route("/date/<date_str>", methods=["GET"])
@token_required
def get_by_date(date_str):
    svc = AttendanceService(_db_path)
    records = svc.get_attendance_by_date(
        date_str,
        subject_id=request.args.get("subject_id", type=int),
        year_group=request.args.get("year_group"),
    )
    return jsonify({"data": records})


@attendance_bp.route("/year-groups", methods=["GET"])
@token_required
def compare_year_groups():
    svc = AttendanceService(_db_path)
    comparison = svc.compare_year_groups()
    return jsonify({"data": comparison})


@attendance_bp.route("/persistent-absentees/<year_group>", methods=["GET"])
@token_required
def persistent_absentees(year_group):
    svc = AttendanceService(_db_path)
    absentees = svc.get_persistent_absentees(year_group)
    return jsonify({"data": absentees})


@attendance_bp.route("/below-threshold/<year_group>", methods=["GET"])
@token_required
def below_threshold(year_group):
    threshold = request.args.get("threshold", 90.0, type=float)
    svc = AttendanceService(_db_path)
    students = svc.get_students_below_threshold(year_group, threshold)
    return jsonify({"data": students})
