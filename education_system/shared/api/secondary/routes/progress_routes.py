"""Progress API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.academics.progress.services.progress_service import ProgressService

progress_bp = Blueprint("progress", __name__, url_prefix="/api/progress")

_db_path = None


def init_progress_routes(db_path=None):
    global _db_path
    _db_path = db_path


@progress_bp.route("/target", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def set_target():
    data = get_json_body()
    require_fields(data, "student_id", "subject_id", "target_grade")
    svc = ProgressService(_db_path)
    result = svc.set_target(data["student_id"], data["subject_id"], data["target_grade"])
    return jsonify({"message": "Created.", "data": result}), 201


@progress_bp.route("/grade", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_grade():
    data = get_json_body()
    require_fields(data, "student_id", "subject_id", "current_grade")
    svc = ProgressService(_db_path)
    result = svc.update_grade(data["student_id"], data["subject_id"], data["current_grade"])
    return jsonify({"message": "Updated.", "data": result})


@progress_bp.route("/student/<int:student_id>", methods=["GET"])
@token_required
def student_progress(student_id):
    svc = ProgressService(_db_path)
    result = svc.list_student_progress(student_id)
    return jsonify({"data": result})


@progress_bp.route("/subject/<int:subject_id>", methods=["GET"])
@token_required
def subject_progress(subject_id):
    svc = ProgressService(_db_path)
    result = svc.list_subject_progress(subject_id)
    return jsonify({"data": result})


@progress_bp.route("", methods=["GET"])
@token_required
def list_all():
    svc = ProgressService(_db_path)
    result = svc.list_all()
    return jsonify({"data": result})


@progress_bp.route("/target/<int:target_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_target(target_id):
    svc = ProgressService(_db_path)
    result = svc.delete_target(target_id)
    return jsonify({"message": "Deleted.", "data": result})

