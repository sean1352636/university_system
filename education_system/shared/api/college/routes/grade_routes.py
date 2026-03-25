"""Grade API routes."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.college_system.modules.domain.grades.services.grade_service import GradeService
from education_system.college_system.core.i18n import t

grade_bp = Blueprint("grades", __name__, url_prefix="/api/grades")

_db_path = None


def init_grade_routes(db_path=None):
    global _db_path
    _db_path = db_path


@grade_bp.route("/record", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor", "teacher")
def record_grade():
    data = get_json_body()
    require_fields(data, "student_id", "course_id", "score")

    svc = GradeService(_db_path)
    grade = svc.record_grade(
        student_pk=data["student_id"],
        course_pk=data["course_id"],
        score=data["score"],
        term=data.get("term"),
        grade_type=data.get("grade_type", "actual"),
        recorded_by=g.current_user["username"],
    )
    return jsonify({"message": t("api.grade.recorded"), "data": grade}), 201


@grade_bp.route("/predicted", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor", "teacher")
def record_predicted():
    data = get_json_body()
    require_fields(data, "student_id", "course_id", "predicted_grade")

    svc = GradeService(_db_path)
    result = svc.record_predicted_grade(
        student_pk=data["student_id"],
        course_pk=data["course_id"],
        predicted_grade=data["predicted_grade"],
        term=data.get("term"),
        recorded_by=g.current_user["username"],
    )
    return jsonify({"message": t("api.grade.predicted_recorded"), "data": result}), 201


def _check_student_access(student_pk):
    """Verify the current user can access this student's data."""
    user = g.current_user
    if user["role"] in ("admin", "staff", "instructor", "teacher"):
        return None  # Staff roles can access any student
    if user.get("user_id") != student_pk:
        return jsonify({"error": t("api.grade.access_denied"), "message": t("api.grade.own_records_only")}), 403
    return None


@grade_bp.route("/student/<int:student_pk>", methods=["GET"])
@token_required
def student_grades(student_pk):
    denied = _check_student_access(student_pk)
    if denied:
        return denied
    svc = GradeService(_db_path)
    grades = svc.get_student_grades(student_pk)
    return jsonify({"data": grades, "count": len(grades)})


@grade_bp.route("/student/<int:student_pk>/predicted", methods=["GET"])
@token_required
def student_predicted_grades(student_pk):
    denied = _check_student_access(student_pk)
    if denied:
        return denied
    svc = GradeService(_db_path)
    grades = svc.get_student_predicted_grades(student_pk)
    return jsonify({"data": grades, "count": len(grades)})


@grade_bp.route("/student/<int:student_pk>/ucas-points", methods=["GET"])
@token_required
def student_ucas_points(student_pk):
    denied = _check_student_access(student_pk)
    if denied:
        return denied
    svc = GradeService(_db_path)
    ucas_points = svc.calculate_ucas_points(student_pk)
    return jsonify({"data": {"student_id": student_pk, "ucas_points": ucas_points}})


@grade_bp.route("/student/<int:student_pk>/transcript", methods=["GET"])
@token_required
def student_transcript(student_pk):
    denied = _check_student_access(student_pk)
    if denied:
        return denied
    svc = GradeService(_db_path)
    transcript = svc.get_transcript(student_pk)
    return jsonify({"data": transcript})


@grade_bp.route("/course/<int:course_pk>", methods=["GET"])
@token_required
@role_required("admin", "staff", "instructor", "teacher")
def course_grades(course_pk):
    svc = GradeService(_db_path)
    grades = svc.get_course_grades(course_pk)
    return jsonify({"data": grades, "count": len(grades)})


@grade_bp.route("/course/<int:course_pk>/stats", methods=["GET"])
@token_required
def course_stats(course_pk):
    svc = GradeService(_db_path)
    stats = svc.get_class_statistics(course_pk)
    return jsonify({"data": stats})
