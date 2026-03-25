"""Authentication API routes."""

import time
from collections import defaultdict

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import generate_token, token_required, _create_mfa_token
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.core.i18n import t

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

_db_path = None
_auth_db_path = None

# In-memory rate limiting (per IP)
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_LOGIN_RATE_LIMIT = 10  # max requests per window
_LOGIN_RATE_WINDOW = 60  # seconds
_REGISTER_RATE_LIMIT = 5
_REGISTER_RATE_WINDOW = 3600  # 1 hour


def _check_rate_limit(key: str, limit: int, window: int) -> bool:
    """Return True if rate limit exceeded."""
    now = time.time()
    timestamps = _rate_limit_store[key]
    # Prune old entries
    _rate_limit_store[key] = [t for t in timestamps if now - t < window]
    if len(_rate_limit_store[key]) >= limit:
        return True
    _rate_limit_store[key].append(now)
    return False


def init_auth_routes(db_path=None, auth_db_path=None):
    global _db_path, _auth_db_path
    _db_path = db_path
    _auth_db_path = auth_db_path


@auth_bp.route("/login", methods=["POST"])
def login():
    ip = request.remote_addr or "unknown"
    if _check_rate_limit(f"login:{ip}", _LOGIN_RATE_LIMIT, _LOGIN_RATE_WINDOW):
        return jsonify({"error": t("api.auth.rate_limit_login", default="Too many login attempts. Please try again later.")}), 429

    data = get_json_body()
    require_fields(data, "username", "password")

    auth = UserAuth(_auth_db_path or _db_path)
    user = auth.login(data["username"], data["password"])

    if user.get("mfa_required"):
        mfa_token = _create_mfa_token(user["user_id"])
        return jsonify({
            "mfa_required": True,
            "mfa_token": mfa_token,
            "user_id": user["user_id"],
            "username": user["username"],
        })

    systems = user.get("systems", [])
    # Extract the college role from systems list
    role = "student"
    for s in systems:
        if s["system_key"] == "college":
            role = s["role"]
            break
    token = generate_token(user["user_id"], user["username"], systems)

    return jsonify({
        "message": t("api.auth.login_success"),
        "token": token,
        "user": {
            "user_id": user["user_id"],
            "username": user["username"],
            "role": role,
            "systems": systems,
        },
    })


@auth_bp.route("/register", methods=["POST"])
def register():
    ip = request.remote_addr or "unknown"
    if _check_rate_limit(f"register:{ip}", _REGISTER_RATE_LIMIT, _REGISTER_RATE_WINDOW):
        return jsonify({"error": t("api.auth.rate_limit_register", default="Too many registration attempts. Please try again later.")}), 429

    data = get_json_body()
    require_fields(data, "username", "password")

    auth = UserAuth(_auth_db_path or _db_path)
    role = data.get("role", "student")
    user_id = auth.create_user(
        username=data["username"],
        password=data["password"],
        email=data.get("email"),
        systems=[("college", role)],
    )

    return jsonify({"message": t("api.auth.user_created", default="User created."), "user_id": user_id}), 201


@auth_bp.route("/me", methods=["GET"])
@token_required
def get_me():
    return jsonify({"user": g.current_user})


@auth_bp.route("/change-password", methods=["POST"])
@token_required
def change_password():
    data = get_json_body()
    require_fields(data, "old_password", "new_password")

    auth = UserAuth(_auth_db_path or _db_path)
    auth.change_password(g.current_user["user_id"], data["old_password"], data["new_password"])

    return jsonify({"message": t("api.auth.password_changed")})
