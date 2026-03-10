"""API routes for document hub."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.document_hub.services.document_hub_service import DocumentHubService

document_hub_bp = Blueprint("document-hub", __name__, url_prefix="/api/document-hub")

_db_path = None


def init_document_hub_routes(db_path=None):
    global _db_path
    _db_path = db_path


@document_hub_bp.route("", methods=["GET"])
@token_required
def list_documents():
    svc = DocumentHubService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_documents(limit=limit, offset=offset)
    total = svc.count_documents()
    return jsonify(paginated_response(items, total))


@document_hub_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_document(pk):
    svc = DocumentHubService(_db_path)
    item = svc.get_document(pk)
    if not item:
        return jsonify({"error": "Document not found."}), 404
    return jsonify({"data": item})


@document_hub_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_document():
    data = get_json_body()
    require_fields(data, "title", "uploaded_by")
    svc = DocumentHubService(_db_path)
    item = svc.create_document(**data)
    return jsonify({"message": "Document created.", "data": item}), 201


@document_hub_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_document(pk):
    data = get_json_body()
    svc = DocumentHubService(_db_path)
    item = svc.update_document(pk, **data)
    return jsonify({"message": "Document updated.", "data": item})


@document_hub_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_document(pk):
    svc = DocumentHubService(_db_path)
    svc.delete_document(pk)
    return jsonify({"message": "Document deleted."})
