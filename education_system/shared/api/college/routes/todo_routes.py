"""API routes for todo."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.todo.services.todo_service import TodoService
from education_system.college_system.core.i18n import t

todo_bp = Blueprint("todo", __name__, url_prefix="/api/todo")

_db_path = None


def init_todo_routes(db_path=None):
    global _db_path
    _db_path = db_path


@todo_bp.route("", methods=["GET"])
@token_required
def list_items():
    svc = TodoService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_items(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@todo_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_item(pk):
    svc = TodoService(_db_path)
    item = svc.get_item(pk)
    if not item:
        return jsonify({"error": t("api.todo.not_found")}), 404
    return jsonify({"data": item})
@todo_bp.route("", methods=["POST"])
@token_required
def create_item():
    data = get_json_body()
    svc = TodoService(_db_path)
    result = svc.create_item(**data)
    return jsonify({"message": t("api.todo.created"), "data": result}), 201
@todo_bp.route("/<int:pk>", methods=["PUT"])
@token_required
def update_item(pk):
    data = get_json_body()
    svc = TodoService(_db_path)
    result = svc.update_item(pk, **data)
    return jsonify({"message": t("api.todo.updated"), "data": result})
@todo_bp.route("/<int:pk>/toggle", methods=["POST"])
@token_required
def toggle_complete(pk):
    data = get_json_body()
    svc = TodoService(_db_path)
    result = svc.toggle_complete(pk, **data)
    return jsonify({"message": t("api.todo.success"), "data": result}), 201
@todo_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
def delete_item(pk):
    svc = TodoService(_db_path)
    svc.delete_item(pk)
    return jsonify({"message": t("api.todo.deleted")})
