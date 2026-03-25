"""Users API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.admin.users.services.user_service import UserService

users_bp = Blueprint("users", __name__, url_prefix="/api/users")

_db_path = None


def init_users_routes(db_path=None):
    global _db_path
    _db_path = db_path


@users_bp.route("", methods=["GET"])
@token_required
@role_required("admin")
def list_users():
    svc = UserService(_db_path)
    result = svc.list_users()
    return jsonify({"data": result})


@users_bp.route("", methods=["POST"])
@token_required
@role_required("admin")
def create_user():
    data = get_json_body()
    require_fields(data, "username", "role")
    svc = UserService(_db_path)
    result = svc.create_user(data["username"], data.get("password", "changeme"), data["role"])
    return jsonify({"message": "Created.", "data": result}), 201


@users_bp.route("/<int:user_id>/reset-password", methods=["POST"])
@token_required
@role_required("admin")
def reset_password(user_id):
    data = request.get_json(silent=True) or {}
    svc = UserService(_db_path)
    result = svc.reset_password(user_id, data.get("new_password", "changeme") if data else "changeme")
    return jsonify({"message": "Created.", "data": result}), 201


@users_bp.route("/<int:user_id>/toggle-active", methods=["PUT"])
@token_required
@role_required("admin")
def toggle_active(user_id):
    svc = UserService(_db_path)
    result = svc.toggle_active(user_id)
    return jsonify({"message": "Updated.", "data": result})


@users_bp.route("/<int:user_id>/role", methods=["PUT"])
@token_required
@role_required("admin")
def update_role(user_id):
    data = get_json_body()
    require_fields(data, "role")
    svc = UserService(_db_path)
    result = svc.update_role(user_id, data["role"])
    return jsonify({"message": "Updated.", "data": result})


@users_bp.route("/<int:user_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_user(user_id):
    svc = UserService(_db_path)
    result = svc.delete_user(user_id)
    return jsonify({"message": "Deleted.", "data": result})

