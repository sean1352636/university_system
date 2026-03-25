"""API routes for forums."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.forums.services.forums_service import ForumService
from education_system.college_system.core.i18n import t

forums_bp = Blueprint("forums", __name__, url_prefix="/api/forums")

_db_path = None


def init_forums_routes(db_path=None):
    global _db_path
    _db_path = db_path


@forums_bp.route("/categories", methods=["GET"])
@token_required
def list_categories():
    svc = ForumService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_categories(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@forums_bp.route("/categories", methods=["POST"])
@token_required
@role_required('admin')
def create_category():
    data = get_json_body()
    svc = ForumService(_db_path)
    result = svc.create_category(**data)
    return jsonify({"message": t("api.forums.created"), "data": result}), 201
@forums_bp.route("/threads", methods=["GET"])
@token_required
def list_threads():
    svc = ForumService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_threads(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@forums_bp.route("/threads/<int:pk>", methods=["GET"])
@token_required
def get_thread(pk):
    svc = ForumService(_db_path)
    item = svc.get_thread(pk)
    if not item:
        return jsonify({"error": t("api.forums.not_found")}), 404
    return jsonify({"data": item})
@forums_bp.route("/threads", methods=["POST"])
@token_required
def create_thread():
    data = get_json_body()
    svc = ForumService(_db_path)
    result = svc.create_thread(**data)
    return jsonify({"message": t("api.forums.created"), "data": result}), 201
@forums_bp.route("/threads/<int:pk>/posts", methods=["GET"])
@token_required
def list_posts(pk):
    svc = ForumService(_db_path)
    result = svc.list_posts(pk)
    return jsonify({"data": result})
@forums_bp.route("/threads/<int:pk>/posts", methods=["POST"])
@token_required
def create_post(pk):
    data = get_json_body()
    svc = ForumService(_db_path)
    result = svc.create_post(pk, **data)
    return jsonify({"message": t("api.forums.success"), "data": result}), 201
@forums_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_stats():
    svc = ForumService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
