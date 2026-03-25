"""Authentication API routes."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.primary.auth import generate_token, token_required, _create_mfa_token
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.primary_school.infrastructure.auth.core import UserAuth

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

_db_path = None


def init_auth_routes(db_path=None):
    global _db_path
    _db_path = db_path


@auth_bp.route("/login", methods=["POST"])
def login():
    data = get_json_body()
    require_fields(data, "username", "password")
    auth = UserAuth(_db_path)
    user = auth.login(data["username"], data["password"])
    if user.get("mfa_required"):
        mfa_token = _create_mfa_token(user["user_id"])
        return jsonify({"mfa_required": True, "mfa_token": mfa_token,
                        "user_id": user["user_id"], "username": user["username"]})
    token = generate_token(user["user_id"], user["username"], user["role"])
    return jsonify({"message": "Login successful.", "token": token,
                    "user": {"user_id": user["user_id"], "username": user["username"], "role": user["role"]}})


@auth_bp.route("/register", methods=["POST"])
def register():
    data = get_json_body()
    require_fields(data, "username", "password")
    auth = UserAuth(_db_path)
    user_id = auth.create_user(data["username"], data["password"],
                               role=data.get("role", "student"), email=data.get("email"))
    return jsonify({"message": "User created.", "user_id": user_id}), 201


@auth_bp.route("/me", methods=["GET"])
@token_required
def get_me():
    return jsonify({"user": g.current_user})


@auth_bp.route("/change-password", methods=["POST"])
@token_required
def change_password():
    data = get_json_body()
    require_fields(data, "old_password", "new_password")
    auth = UserAuth(_db_path)
    auth.change_password(g.current_user["user_id"], data["old_password"], data["new_password"])
    return jsonify({"message": "Password changed successfully."})
