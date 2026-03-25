"""Subjects API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.academics.subjects.services.subject_service import SubjectService

subjects_bp = Blueprint("subjects", __name__, url_prefix="/api/subjects")

_db_path = None


def init_subjects_routes(db_path=None):
    global _db_path
    _db_path = db_path


@subjects_bp.route("", methods=["GET"])
@token_required
def list_subjects():
    svc = SubjectService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_subjects()
    total = len(items)
    return jsonify(paginated_response(items, total))


@subjects_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_subject(pk):
    svc = SubjectService(_db_path)
    item = svc.get_subject(pk)
    if not item:
        return jsonify({"error": "Subject not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@subjects_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_subject():
    data = get_json_body()
    require_fields(data, "name", "subject_code")
    svc = SubjectService(_db_path)
    result = svc.create_subject(**data)
    return jsonify({"message": "Subject created.", "data": result}), 201


@subjects_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_subject(pk):
    data = get_json_body()
    svc = SubjectService(_db_path)
    result = svc.update_subject(pk, **data)
    return jsonify({"message": "Subject updated.", "data": result})

@subjects_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_subject(pk):
    svc = SubjectService(_db_path)
    svc.delete_subject(pk)
    return jsonify({"message": "Subject deleted."})