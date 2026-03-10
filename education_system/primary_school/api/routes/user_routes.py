"""Users API routes."""

from flask import Blueprint, jsonify, request

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.api.validators import get_json_body, require_fields
from education_system.primary_school.api.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.admin.users.services.user_service import UserService

users_bp = Blueprint("users", __name__, url_prefix="/api/users")

_db_path = None


def init_users_routes(db_path=None):
    global _db_path
    _db_path = db_path


@users_bp.route("", methods=["GET"])
@token_required
def list_users():
    svc = UserService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_users()
    total = len(items)
    return jsonify(paginated_response(items, total))


@users_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_user(pk):
    svc = UserService(_db_path)
    item = svc.get_user(pk)
    if not item:
        return jsonify({"error": "User not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@users_bp.route("", methods=["POST"])
@token_required
@role_required("admin")
def create_user():
    data = get_json_body()
    require_fields(data, "username", "password", "role")
    svc = UserService(_db_path)
    result = svc.create_user(**data)
    return jsonify({"message": "User created.", "data": result}), 201


@users_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin")
def update_user(pk):
    data = get_json_body()
    svc = UserService(_db_path)
    result = svc.update_user(pk, **data)
    return jsonify({"message": "User updated.", "data": result})

@users_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_user(pk):
    svc = UserService(_db_path)
    svc.delete_user(pk)
    return jsonify({"message": "User deleted."})