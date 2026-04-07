"""Multi-language API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.admin.multi_language.services.multi_language_service import MultiLanguageService

multi_language_bp = Blueprint("multi-language", __name__, url_prefix="/api/multi-language")

_db_path = None


def init_multi_language_routes(db_path=None):
    global _db_path
    _db_path = db_path


@multi_language_bp.route("", methods=["GET"])
@token_required
def list_multi_language():
    svc = MultiLanguageService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_all(limit=limit, offset=offset)
    total = len(items)
    return jsonify(paginated_response(items, total))


@multi_language_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_multi_language_item(pk):
    svc = MultiLanguageService(_db_path)
    item = svc.get(pk)
    if not item:
        return jsonify({"error": "Not found."}), 404
    return jsonify({"data": item})


@multi_language_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_multi_language_item():
    data = get_json_body()
    svc = MultiLanguageService(_db_path)
    result = svc.create(**data)
    return jsonify({"message": "Created.", "data": result}), 201


@multi_language_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_multi_language_item(pk):
    data = get_json_body()
    svc = MultiLanguageService(_db_path)
    result = svc.update(pk, **data)
    return jsonify({"message": "Updated.", "data": result})


@multi_language_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_multi_language_item(pk):
    svc = MultiLanguageService(_db_path)
    svc.delete(pk)
    return jsonify({"message": "Deleted."})
