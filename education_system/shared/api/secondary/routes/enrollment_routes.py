"""Enrollment API routes."""

from flask import Blueprint, jsonify

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.academics.enrollment.services.enrollment_service import EnrollmentService

enrollment_bp = Blueprint("enrollments", __name__, url_prefix="/api/enrollments")

_db_path = None


def init_enrollment_routes(db_path=None):
    global _db_path
    _db_path = db_path


@enrollment_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def enroll_student():
    data = get_json_body()
    require_fields(data, "student_id", "subject_id")

    svc = EnrollmentService(_db_path)
    enrollment = svc.enroll_student(data["student_id"], data["subject_id"])
    return jsonify({"message": "Student enrolled.", "data": enrollment}), 201


@enrollment_bp.route("/drop", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def drop_enrollment():
    data = get_json_body()
    require_fields(data, "student_id", "subject_id")

    svc = EnrollmentService(_db_path)
    svc.drop_enrollment(data["student_id"], data["subject_id"])
    return jsonify({"message": "Enrollment dropped."})


@enrollment_bp.route("/student/<int:student_id>", methods=["GET"])
@token_required
def get_student_enrollments(student_id):
    svc = EnrollmentService(_db_path)
    enrollments = svc.get_student_enrollments(student_id)
    return jsonify({"data": enrollments})


@enrollment_bp.route("/subject/<int:subject_id>", methods=["GET"])
@token_required
def get_subject_students(subject_id):
    svc = EnrollmentService(_db_path)
    students = svc.get_subject_students(subject_id)
    return jsonify({"data": students})
