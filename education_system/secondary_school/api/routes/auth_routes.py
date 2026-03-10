"""Authentication API routes."""

from flask import Blueprint, jsonify, request

from education_system.secondary_school.api.auth import generate_token, token_required
from education_system.secondary_school.api.validators import get_json_body, require_fields
from education_system.secondary_school.infrastructure.auth.core import UserAuth

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

_db_path = None
_auth_db_path = None


def init_auth_routes(db_path=None, auth_db_path=None):
    global _db_path, _auth_db_path
    _db_path = db_path
    _auth_db_path = auth_db_path


@auth_bp.route("/login", methods=["POST"])
def login():
    data = get_json_body()
    require_fields(data, "username", "password")

    auth = UserAuth(_auth_db_path)
    user = auth.login(data["username"], data["password"])

    # Extract the school role from systems list
    role = "student"
    for s in user.get("systems", []):
        if s["system_key"] == "school":
            role = s["role"]
            break
    token = generate_token(user["user_id"], user["username"], role)
    return jsonify({
        "message": "Login successful.",
        "token": token,
        "user": user,
    })


@auth_bp.route("/register", methods=["POST"])
def register():
    data = get_json_body()
    require_fields(data, "username", "password")

    auth = UserAuth(_auth_db_path)
    role = data.get("role", "student")
    user_id = auth.create_user(
        username=data["username"],
        password=data["password"],
        email=data.get("email"),
        systems=[("school", role)],
    )
    return jsonify({"message": "User created.", "user_id": user_id}), 201
