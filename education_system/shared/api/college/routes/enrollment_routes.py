"""Enrollment API routes."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.college_system.modules.domain.enrollment.services.enrollment_service import EnrollmentService
from education_system.college_system.core.i18n import t

enrollment_bp = Blueprint("enrollments", __name__, url_prefix="/api/enrollments")

_db_path = None


def init_enrollment_routes(db_path=None):
    global _db_path
    _db_path = db_path


@enrollment_bp.route("", methods=["GET"])
@token_required
def list_enrollments():
    svc = EnrollmentService(_db_path)
    enrollments = svc.list_enrollments(
        student_pk=request.args.get("student_id", type=int),
        course_pk=request.args.get("course_id", type=int),
        status=request.args.get("status"),
    )
    return jsonify({"data": enrollments, "count": len(enrollments)})


@enrollment_bp.route("/enroll", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def enroll_student():
    data = get_json_body()
    require_fields(data, "student_id", "course_id")

    svc = EnrollmentService(_db_path)
    result = svc.enroll_student(data["student_id"], data["course_id"])
    status_code = 201 if result["status"] == "enrolled" else 200
    msg = t("api.enrollment.enrolled") if result["status"] == "enrolled" else t("api.enrollment.waitlisted")
    return jsonify({"message": msg, "data": result}), status_code


@enrollment_bp.route("/drop", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def drop_student():
    data = get_json_body()
    require_fields(data, "student_id", "course_id")

    svc = EnrollmentService(_db_path)
    result = svc.drop_student(data["student_id"], data["course_id"])
    return jsonify({"message": t("api.enrollment.dropped"), "data": result})


@enrollment_bp.route("/student/<int:student_pk>", methods=["GET"])
@token_required
def student_enrollments(student_pk):
    svc = EnrollmentService(_db_path)
    enrollments = svc.get_student_enrollments(student_pk)
    return jsonify({"data": enrollments, "count": len(enrollments)})


@enrollment_bp.route("/waitlist/<int:course_pk>", methods=["GET"])
@token_required
def course_waitlist(course_pk):
    svc = EnrollmentService(_db_path)
    waitlist = svc.get_waitlist(course_pk)
    return jsonify({"data": waitlist, "count": len(waitlist)})
