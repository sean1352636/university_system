"""API routes for multi-language."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.multi_language.services.multi_language_service import MultiLanguageService

multi_language_bp = Blueprint("multi-language", __name__, url_prefix="/api/multi-language")

_db_path = None


def init_multi_language_routes(db_path=None):
    global _db_path
    _db_path = db_path


@multi_language_bp.route("", methods=["GET"])
@token_required
def list_overrides():
    svc = MultiLanguageService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_overrides(limit=limit, offset=offset)
    total = svc.count_overrides()
    return jsonify(paginated_response(items, total))


@multi_language_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_override(pk):
    svc = MultiLanguageService(_db_path)
    item = svc.get_override(pk)
    if not item:
        return jsonify({"error": "Override not found."}), 404
    return jsonify({"data": item})


@multi_language_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_override():
    data = get_json_body()
    require_fields(data, "locale", "key", "value")
    svc = MultiLanguageService(_db_path)
    item = svc.create_override(**data)
    return jsonify({"message": "Override created.", "data": item}), 201


@multi_language_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_override(pk):
    data = get_json_body()
    svc = MultiLanguageService(_db_path)
    item = svc.update_override(pk, **data)
    return jsonify({"message": "Override updated.", "data": item})


@multi_language_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_override(pk):
    svc = MultiLanguageService(_db_path)
    svc.delete_override(pk)
    return jsonify({"message": "Override deleted."})
