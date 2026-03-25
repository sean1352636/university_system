"""Exams API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.academics.exams.services.exam_service import ExamService

exams_bp = Blueprint("exams", __name__, url_prefix="/api/exams")

_db_path = None


def init_exams_routes(db_path=None):
    global _db_path
    _db_path = db_path


@exams_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_exam():
    data = get_json_body()
    require_fields(data, "subject_id", "name", "exam_date")
    svc = ExamService(_db_path)
    result = svc.create_exam(subject_id=data["subject_id"], name=data["name"], exam_date=data["exam_date"], exam_type=data.get("exam_type", "written"), max_marks=data.get("max_marks", 100))
    return jsonify({"message": "Created.", "data": result}), 201


@exams_bp.route("", methods=["GET"])
@token_required
def list_exams():
    svc = ExamService(_db_path)
    result = svc.list_exams()
    return jsonify({"data": result})


@exams_bp.route("/<int:exam_id>/status", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_exam_status(exam_id):
    data = get_json_body()
    require_fields(data, "status")
    svc = ExamService(_db_path)
    result = svc.update_exam_status(exam_id, data["status"])
    return jsonify({"message": "Updated.", "data": result})


@exams_bp.route("/<int:exam_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_exam(exam_id):
    svc = ExamService(_db_path)
    result = svc.delete_exam(exam_id)
    return jsonify({"message": "Deleted.", "data": result})


@exams_bp.route("/<int:exam_id>/results", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def record_result(exam_id):
    data = get_json_body()
    require_fields(data, "student_id", "marks")
    svc = ExamService(_db_path)
    result = svc.record_result(exam_id, data["student_id"], data["marks"])
    return jsonify({"message": "Created.", "data": result}), 201


@exams_bp.route("/<int:exam_id>/results", methods=["GET"])
@token_required
def get_exam_results(exam_id):
    svc = ExamService(_db_path)
    result = svc.get_exam_results(exam_id)
    return jsonify({"data": result})


@exams_bp.route("/student/<int:student_id>", methods=["GET"])
@token_required
def get_student_exams(student_id):
    svc = ExamService(_db_path)
    result = svc.get_student_exam_results(student_id)
    return jsonify({"data": result})

