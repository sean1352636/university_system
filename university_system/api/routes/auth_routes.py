"""Authentication routes: login, logout, refresh, current user."""

from __future__ import annotations

import logging

from flask import Blueprint, current_app, g, jsonify, request

from university_system.api.auth import (
    blacklist_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    is_token_blacklisted,
    token_required,
)
from university_system.api.validators import validate_login
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth
from university_system.modules.shared.utils.activity_logger import log_activity, log_login

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    validate_login(data)

    auth = get_auth()
    # login() raises InvalidCredentialsError / AuthenticationError on failure
    result = auth.login(data["username"], data["password"])

    if result == "password_reset_required":
        return jsonify({
            "message": "Password reset required",
            "password_reset_required": True,
        }), 200

    if isinstance(result, dict) and result.get("requires_2fa"):
        return jsonify({
            "message": "Two-factor authentication required",
            "requires_2fa": True,
        }), 200

    # Successful login – build tokens
    user = auth.get_current_user()
    config = current_app.config["API_CONFIG"]
    access_token = create_access_token(user, config)
    refresh_token = create_refresh_token(user, config)

    log_login(user["username"], success=True)

    # Log the user out of the shared context so the thread-global state
    # is not left holding a session (API is stateless per-request).
    try:
        auth.logout()
    except Exception:
        pass

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "username": user["username"],
            "role": user["role"],
            "user_id": user["id"],
        },
    })


@auth_bp.route("/logout", methods=["POST"])
@token_required
def logout():
    token = g.get("raw_token")
    if token:
        blacklist_token(token)
    log_activity("logout", "session", user=g.current_user.get("sub"))
    return jsonify({"message": "Successfully logged out"})


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    data = request.get_json(silent=True) or {}
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        return jsonify({"error": "Missing refresh_token", "status": 400}), 400

    if is_token_blacklisted(refresh_token):
        return jsonify({"error": "Token has been revoked", "status": 401}), 401

    config = current_app.config["API_CONFIG"]
    try:
        payload = decode_token(refresh_token, config)
    except Exception:
        return jsonify({"error": "Invalid or expired refresh token", "status": 401}), 401

    if payload.get("type") != "refresh":
        return jsonify({"error": "Invalid token type", "status": 401}), 401

    user_stub = {
        "username": payload["sub"],
        "id": payload["user_id"],
        "role": payload.get("role", "student"),
    }
    new_access = create_access_token(user_stub, config)
    return jsonify({"access_token": new_access})


@auth_bp.route("/me", methods=["GET"])
@token_required
def me():
    user = g.current_user
    return jsonify({
        "username": user.get("sub"),
        "user_id": user.get("user_id"),
        "role": user.get("role"),
    })
