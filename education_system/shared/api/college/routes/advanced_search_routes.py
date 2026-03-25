"""API routes for advanced search."""

from flask import Blueprint, jsonify, request
from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.advanced_search.services.advanced_search_service import AdvancedSearchService
from education_system.college_system.core.i18n import t

advanced_search_bp = Blueprint("search", __name__, url_prefix="/api/search")

_db_path = None


def init_advanced_search_routes(db_path=None):
    global _db_path
    _db_path = db_path


@advanced_search_bp.route("", methods=["GET"])
@token_required
def list_searches():
    svc = AdvancedSearchService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_searches(limit=limit, offset=offset)
    total = svc.count_searches()
    return jsonify(paginated_response(items, total))


@advanced_search_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_search(pk):
    svc = AdvancedSearchService(_db_path)
    item = svc.get_search(pk)
    if not item:
        return jsonify({"error": t("api.advanced_search.no_results")}), 404
    return jsonify({"data": item})


@advanced_search_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_search():
    data = get_json_body()
    require_fields(data, "user_id", "query")
    svc = AdvancedSearchService(_db_path)
    item = svc.create_search(**data)
    return jsonify({"message": t("api.common.created"), "data": item}), 201


@advanced_search_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_search(pk):
    data = get_json_body()
    svc = AdvancedSearchService(_db_path)
    item = svc.update_search(pk, **data)
    return jsonify({"message": t("api.common.updated"), "data": item})


@advanced_search_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_search(pk):
    svc = AdvancedSearchService(_db_path)
    svc.delete_search(pk)
    return jsonify({"message": t("api.common.deleted")})
