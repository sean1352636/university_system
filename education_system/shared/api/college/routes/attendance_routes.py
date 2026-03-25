"""Attendance API routes."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.college_system.modules.domain.attendance.services.attendance_service import AttendanceService
from education_system.college_system.core.i18n import t

attendance_bp = Blueprint("attendance", __name__, url_prefix="/api/attendance")

_db_path = None


def init_attendance_routes(db_path=None):
    global _db_path
    _db_path = db_path


@attendance_bp.route("/sessions", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_session():
    data = get_json_body()
    require_fields(data, "course_id")

    svc = AttendanceService(_db_path)
    session = svc.create_session(
        course_pk=data["course_id"],
        session_date=data.get("session_date"),
        topic=data.get("topic"),
        created_by=g.current_user["username"],
    )
    return jsonify({"message": t("api.attendance.session_created"), "data": session}), 201


@attendance_bp.route("/sessions/<int:session_id>", methods=["GET"])
@token_required
def get_session(session_id):
    svc = AttendanceService(_db_path)
    session = svc.get_session(session_id)
    if not session:
        return jsonify({"error": t("api.attendance.not_found")}), 404
    return jsonify({"data": session})


@attendance_bp.route("/record", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def record_attendance():
    data = get_json_body()
    require_fields(data, "session_id", "student_id", "status")

    svc = AttendanceService(_db_path)
    result = svc.record_attendance(
        session_id=data["session_id"],
        student_pk=data["student_id"],
        status=data["status"],
        notes=data.get("notes"),
    )
    return jsonify({"message": t("api.attendance.recorded"), "data": result}), 201


@attendance_bp.route("/bulk-record", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def bulk_record():
    data = get_json_body()
    require_fields(data, "session_id", "records")

    svc = AttendanceService(_db_path)
    count = svc.bulk_record_attendance(data["session_id"], data["records"])
    return jsonify({"message": t("api.attendance.bulk_recorded", count=count), "count": count}), 201


@attendance_bp.route("/sessions/<int:session_id>/records", methods=["GET"])
@token_required
def session_records(session_id):
    svc = AttendanceService(_db_path)
    records = svc.get_session_records(session_id)
    return jsonify({"data": records, "count": len(records)})


@attendance_bp.route("/student/<int:student_pk>", methods=["GET"])
@token_required
def student_attendance(student_pk):
    svc = AttendanceService(_db_path)
    course_pk = request.args.get("course_id", type=int)
    records = svc.get_student_attendance(student_pk, course_pk)
    return jsonify({"data": records, "count": len(records)})


@attendance_bp.route("/summary/<int:student_pk>/<int:course_pk>", methods=["GET"])
@token_required
def attendance_summary(student_pk, course_pk):
    svc = AttendanceService(_db_path)
    summary = svc.get_attendance_summary(student_pk, course_pk)
    return jsonify({"data": summary})


@attendance_bp.route("/course/<int:course_pk>/sessions", methods=["GET"])
@token_required
def course_sessions(course_pk):
    svc = AttendanceService(_db_path)
    sessions = svc.get_course_sessions(course_pk)
    return jsonify({"data": sessions, "count": len(sessions)})


@attendance_bp.route("/course/<int:course_pk>/report", methods=["GET"])
@token_required
@role_required("admin", "staff", "instructor")
def course_report(course_pk):
    svc = AttendanceService(_db_path)
    report = svc.get_course_attendance_report(course_pk)
    return jsonify({"data": report, "count": len(report)})


@attendance_bp.route("/generate-registers", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def generate_registers():
    data = get_json_body()
    require_fields(data, "date")

    svc = AttendanceService(_db_path)
    sessions = svc.generate_registers_for_date(
        data["date"], created_by=g.current_user["username"],
    )
    return jsonify({
        "message": t("api.attendance.registers_generated", count=len(sessions), default=f"Generated {len(sessions)} register(s)."),
        "data": sessions,
        "count": len(sessions),
    }), 201


@attendance_bp.route("/sessions/from-slot", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_session_from_slot():
    data = get_json_body()
    require_fields(data, "timetable_slot_id")

    svc = AttendanceService(_db_path)
    session = svc.create_session_from_slot(
        timetable_slot_id=data["timetable_slot_id"],
        session_date=data.get("session_date"),
        created_by=g.current_user["username"],
    )
    return jsonify({"message": t("api.attendance.session_created"), "data": session}), 201


@attendance_bp.route("/sessions/<int:session_id>/populate", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def populate_register(session_id):
    svc = AttendanceService(_db_path)
    count = svc.pre_populate_register(session_id)
    return jsonify({"message": t("api.attendance.pre_populated", count=count, default=f"Pre-populated {count} absent record(s)."), "count": count}), 201
