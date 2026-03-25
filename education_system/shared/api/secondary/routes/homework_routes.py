"""Homework API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.academics.homework.services.homework_service import HomeworkService

homework_bp = Blueprint("homework", __name__, url_prefix="/api/homework")

_db_path = None


def init_homework_routes(db_path=None):
    global _db_path
    _db_path = db_path


@homework_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_homework():
    data = get_json_body()
    require_fields(data, "subject_id", "title", "due_date")
    svc = HomeworkService(_db_path)
    result = svc.create_homework(subject_id=data["subject_id"], title=data["title"], due_date=data["due_date"], description=data.get("description", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@homework_bp.route("", methods=["GET"])
@token_required
def list_homework():
    svc = HomeworkService(_db_path)
    result = svc.list_homework()
    return jsonify({"data": result})


@homework_bp.route("/<int:hw_id>", methods=["DELETE"])
@token_required
@role_required("admin", "teacher")
def delete_homework(hw_id):
    svc = HomeworkService(_db_path)
    result = svc.delete_homework(hw_id)
    return jsonify({"message": "Deleted.", "data": result})


@homework_bp.route("/<int:hw_id>/submit", methods=["POST"])
@token_required
@role_required("admin", "teacher", "student")
def submit_homework(hw_id):
    data = get_json_body()
    require_fields(data, "student_id")
    svc = HomeworkService(_db_path)
    result = svc.submit(hw_id, data["student_id"], data.get("content", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@homework_bp.route("/<int:hw_id>/submissions", methods=["GET"])
@token_required
def get_submissions(hw_id):
    svc = HomeworkService(_db_path)
    result = svc.get_submissions(hw_id)
    return jsonify({"data": result})


@homework_bp.route("/<int:hw_id>/mark", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def mark_submission(hw_id):
    data = get_json_body()
    require_fields(data, "student_id", "grade")
    svc = HomeworkService(_db_path)
    result = svc.mark_submission(hw_id, data["student_id"], data["grade"], data.get("feedback", ""))
    return jsonify({"message": "Created.", "data": result}), 201

