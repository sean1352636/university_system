"""Documents API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.admin.documents.services.document_service import DocumentService

documents_bp = Blueprint("documents", __name__, url_prefix="/api/documents")

_db_path = None


def init_documents_routes(db_path=None):
    global _db_path
    _db_path = db_path


@documents_bp.route("", methods=["POST"])
@token_required
@role_required("admin")
def add_document():
    data = get_json_body()
    require_fields(data, "title", "category")
    svc = DocumentService(_db_path)
    result = svc.add_document(title=data["title"], category=data["category"], content=data.get("content", ""), uploaded_by=data.get("uploaded_by", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@documents_bp.route("", methods=["GET"])
@token_required
def list_documents():
    svc = DocumentService(_db_path)
    result = svc.list_documents()
    return jsonify({"data": result})


@documents_bp.route("/<int:doc_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_document(doc_id):
    svc = DocumentService(_db_path)
    result = svc.delete_document(doc_id)
    return jsonify({"message": "Deleted.", "data": result})


@documents_bp.route("/<int:doc_id>/acknowledge", methods=["POST"])
@token_required
def acknowledge(doc_id):
    data = get_json_body()
    require_fields(data, "user_id")
    svc = DocumentService(_db_path)
    result = svc.acknowledge(doc_id, data["user_id"])
    return jsonify({"message": "Created.", "data": result}), 201

