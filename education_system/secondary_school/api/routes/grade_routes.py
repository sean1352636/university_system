"""Grade API routes."""

from flask import Blueprint, jsonify, request

from education_system.secondary_school.api.auth import token_required, role_required
from education_system.secondary_school.api.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.academics.grades.services.grade_service import GradeService

grade_bp = Blueprint("grades", __name__, url_prefix="/api/grades")

_db_path = None


def init_grade_routes(db_path=None):
    global _db_path
    _db_path = db_path


@grade_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def add_grade():
    data = get_json_body()
    require_fields(data, "student_id", "subject_id")

    svc = GradeService(_db_path)
    grade = svc.add_grade(
        student_id=data["student_id"],
        subject_id=data["subject_id"],
        assessment_type=data.get("assessment_type", "classwork"),
        assessment_name=data.get("assessment_name"),
        score=data.get("score"),
        grade=data.get("grade"),
        term=data.get("term"),
        academic_year=data.get("academic_year"),
        teacher_comment=data.get("teacher_comment"),
    )
    return jsonify({"message": "Grade recorded.", "data": grade}), 201


@grade_bp.route("/student/<int:student_id>", methods=["GET"])
@token_required
def get_student_grades(student_id):
    svc = GradeService(_db_path)
    grades = svc.get_student_grades(
        student_id,
        subject_id=request.args.get("subject_id", type=int),
        term=request.args.get("term"),
    )
    return jsonify({"data": grades})


@grade_bp.route("/subject/<int:subject_id>", methods=["GET"])
@token_required
def get_subject_grades(subject_id):
    svc = GradeService(_db_path)
    grades = svc.get_subject_grades(
        subject_id,
        assessment_name=request.args.get("assessment_name"),
    )
    return jsonify({"data": grades})


@grade_bp.route("/<int:grade_id>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_grade(grade_id):
    data = get_json_body()
    svc = GradeService(_db_path)
    grade = svc.update_grade(grade_id, **data)
    return jsonify({"message": "Grade updated.", "data": grade})


@grade_bp.route("/<int:grade_id>", methods=["DELETE"])
@token_required
@role_required("admin", "teacher")
def delete_grade(grade_id):
    svc = GradeService(_db_path)
    svc.delete_grade(grade_id)
    return jsonify({"message": "Grade deleted."})


@grade_bp.route("/student/<int:student_id>/average", methods=["GET"])
@token_required
def get_student_average(student_id):
    svc = GradeService(_db_path)
    avg = svc.get_student_average(
        student_id,
        subject_id=request.args.get("subject_id", type=int),
    )
    return jsonify({"data": {"average": avg}})
