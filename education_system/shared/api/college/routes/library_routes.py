"""API routes for library."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.library.services.library_service import LibraryService
from education_system.college_system.core.i18n import t

library_bp = Blueprint("library", __name__, url_prefix="/api/library")

_db_path = None


def init_library_routes(db_path=None):
    global _db_path
    _db_path = db_path


@library_bp.route("", methods=["GET"])
@token_required
def list_items():
    svc = LibraryService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_items(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@library_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_item(pk):
    svc = LibraryService(_db_path)
    item = svc.get_item(pk)
    if not item:
        return jsonify({"error": t("api.library.not_found")}), 404
    return jsonify({"data": item})
@library_bp.route("", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def add_item():
    data = get_json_body()
    svc = LibraryService(_db_path)
    result = svc.add_item(**data)
    return jsonify({"message": t("api.library.created"), "data": result}), 201
@library_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_item(pk):
    data = get_json_body()
    svc = LibraryService(_db_path)
    result = svc.update_item(pk, **data)
    return jsonify({"message": t("api.library.updated"), "data": result})
@library_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_item(pk):
    svc = LibraryService(_db_path)
    svc.delete_item(pk)
    return jsonify({"message": t("api.library.deleted")})
@library_bp.route("/checkout", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def checkout():
    data = get_json_body()
    svc = LibraryService(_db_path)
    result = svc.checkout(**data)
    return jsonify({"message": t("api.library.created"), "data": result}), 201
@library_bp.route("/return", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def return_item():
    data = get_json_body()
    svc = LibraryService(_db_path)
    result = svc.return_item(**data)
    return jsonify({"message": t("api.library.created"), "data": result}), 201
@library_bp.route("/loans", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_loans():
    svc = LibraryService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_loans(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@library_bp.route("/overdue", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_overdue():
    svc = LibraryService(_db_path)
    result = svc.get_overdue()
    return jsonify({"data": result})
