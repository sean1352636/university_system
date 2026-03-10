"""API routes for attachments."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.attachments.services.attachments_service import AttachmentService

attachment_bp = Blueprint("attachments", __name__, url_prefix="/api/attachments")

_db_path = None


def init_attachment_routes(db_path=None):
    global _db_path
    _db_path = db_path


@attachment_bp.route("", methods=["GET"])
@token_required
def list_attachments():
    svc = AttachmentService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_attachments(limit=limit, offset=offset)
    total = svc.count_attachments()
    return jsonify(paginated_response(items, total))


@attachment_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_attachment(pk):
    svc = AttachmentService(_db_path)
    item = svc.get_attachment(pk)
    if not item:
        return jsonify({"error": "Attachment not found."}), 404
    return jsonify({"data": item})


@attachment_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_attachment():
    data = get_json_body()
    require_fields(data, "uploaded_by", "filename", "original_filename", "file_path")
    svc = AttachmentService(_db_path)
    item = svc.create_attachment(**data)
    return jsonify({"message": "Attachment created.", "data": item}), 201


@attachment_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_attachment(pk):
    data = get_json_body()
    svc = AttachmentService(_db_path)
    item = svc.update_attachment(pk, **data)
    return jsonify({"message": "Attachment updated.", "data": item})


@attachment_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_attachment(pk):
    svc = AttachmentService(_db_path)
    svc.delete_attachment(pk)
    return jsonify({"message": "Attachment deleted."})
