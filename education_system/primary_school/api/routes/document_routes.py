"""Documents API routes."""

from flask import Blueprint, jsonify, request

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.api.validators import get_json_body, require_fields
from education_system.primary_school.api.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.admin.documents.services.document_service import DocumentService

documents_bp = Blueprint("documents", __name__, url_prefix="/api/documents")

_db_path = None


def init_documents_routes(db_path=None):
    global _db_path
    _db_path = db_path


@documents_bp.route("", methods=["GET"])
@token_required
def list_documents():
    svc = DocumentService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_documents()
    total = len(items)
    return jsonify(paginated_response(items, total))


@documents_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_document(pk):
    svc = DocumentService(_db_path)
    item = svc.get_document(pk)
    if not item:
        return jsonify({"error": "Document not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@documents_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_document():
    data = get_json_body()
    require_fields(data, "title", "document_type")
    svc = DocumentService(_db_path)
    result = svc.create_document(**data)
    return jsonify({"message": "Document created.", "data": result}), 201


@documents_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_document(pk):
    data = get_json_body()
    svc = DocumentService(_db_path)
    result = svc.update_document(pk, **data)
    return jsonify({"message": "Document updated.", "data": result})

@documents_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_document(pk):
    svc = DocumentService(_db_path)
    svc.delete_document(pk)
    return jsonify({"message": "Document deleted."})