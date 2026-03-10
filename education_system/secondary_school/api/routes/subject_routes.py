"""Subject API routes."""

from flask import Blueprint, jsonify, request

from education_system.secondary_school.api.auth import token_required, role_required
from education_system.secondary_school.api.validators import get_json_body, require_fields
from education_system.secondary_school.api.pagination import get_pagination_params, paginated_response
from education_system.secondary_school.modules.domain.academics.subjects.services.subject_service import SubjectService

subject_bp = Blueprint("subjects", __name__, url_prefix="/api/subjects")

_db_path = None


def init_subject_routes(db_path=None):
    global _db_path
    _db_path = db_path


@subject_bp.route("", methods=["GET"])
@token_required
def list_subjects():
    svc = SubjectService(_db_path)
    limit, offset = get_pagination_params()
    subjects = svc.list_subjects(
        status=request.args.get("status"),
        key_stage=request.args.get("key_stage"),
        department=request.args.get("department"),
        search=request.args.get("search"),
        limit=limit, offset=offset,
    )
    return jsonify({"data": subjects})


@subject_bp.route("/<int:subject_pk>", methods=["GET"])
@token_required
def get_subject(subject_pk):
    svc = SubjectService(_db_path)
    subject = svc.get_subject(subject_pk)
    if not subject:
        return jsonify({"error": "Subject not found."}), 404
    return jsonify({"data": subject})


@subject_bp.route("/by-code/<subject_code>", methods=["GET"])
@token_required
def get_subject_by_code(subject_code):
    svc = SubjectService(_db_path)
    subject = svc.get_subject_by_code(subject_code)
    if not subject:
        return jsonify({"error": "Subject not found."}), 404
    return jsonify({"data": subject})


@subject_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_subject():
    data = get_json_body()
    require_fields(data, "subject_code", "title")

    svc = SubjectService(_db_path)
    subject = svc.create_subject(
        subject_code=data["subject_code"],
        title=data["title"],
        description=data.get("description"),
        department=data.get("department"),
        key_stage=data.get("key_stage", "KS3"),
        is_core=data.get("is_core", False),
        capacity=data.get("capacity", 30),
        teacher=data.get("teacher"),
        room=data.get("room"),
    )
    return jsonify({"message": "Subject created.", "data": subject}), 201


@subject_bp.route("/<int:subject_pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_subject(subject_pk):
    data = get_json_body()
    svc = SubjectService(_db_path)
    subject = svc.update_subject(subject_pk, **data)
    return jsonify({"message": "Subject updated.", "data": subject})


@subject_bp.route("/<int:subject_pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_subject(subject_pk):
    svc = SubjectService(_db_path)
    svc.delete_subject(subject_pk)
    return jsonify({"message": "Subject deleted."})
