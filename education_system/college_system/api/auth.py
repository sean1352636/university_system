"""JWT authentication decorators for the API."""

import functools
from datetime import datetime, timedelta

import jwt
from flask import request, jsonify, g

from education_system.college_system.api.config import Config
from education_system.college_system.infrastructure.database.db import connect
import logging

logger = logging.getLogger(__name__)


def generate_token(user_id: int, username: str, role: str) -> str:
    """Generate a JWT token for a user."""
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=Config.JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow(),
    }
    logger.debug("JWT token generated for user '%s' (role=%s)", username, role)
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    return jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])


def token_required(f):
    """Decorator that requires a valid JWT token."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

        if not token:
            logger.warning("API request without token: %s %s", request.method, request.path)
            return jsonify({"error": "Authentication required", "message": "Missing token."}), 401

        try:
            data = decode_token(token)
            g.current_user = {
                "user_id": data["user_id"],
                "username": data["username"],
                "role": data["role"],
            }
        except jwt.ExpiredSignatureError:
            logger.warning("Expired JWT token: %s %s", request.method, request.path)
            return jsonify({"error": "Token expired", "message": "Please log in again."}), 401
        except jwt.InvalidTokenError:
            logger.warning("Invalid JWT token: %s %s", request.method, request.path)
            return jsonify({"error": "Invalid token", "message": "Token is invalid."}), 401

        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """Decorator that requires the user to have one of the specified roles."""
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, "current_user"):
                return jsonify({"error": "Authentication required"}), 401

            if g.current_user["role"] not in roles:
                logger.warning("Access denied: user '%s' (role=%s) requires %s", g.current_user["username"], g.current_user["role"], roles)
                return jsonify({
                    "error": "Access denied",
                    "message": f"Requires role: {', '.join(roles)}",
                }), 403

            return f(*args, **kwargs)
        return decorated
    return decorator


def _create_mfa_token(user_id: int) -> str:
    """Create a short-lived JWT for MFA verification (5 minutes)."""
    payload = {
        "user_id": user_id,
        "purpose": "mfa_verify",
        "exp": datetime.utcnow() + timedelta(minutes=5),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm="HS256")


def mfa_token_required(f):
    """Decorator that requires a valid MFA verification token."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

        if not token:
            return jsonify({"error": "MFA token required"}), 401

        try:
            data = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
            if data.get("purpose") != "mfa_verify":
                return jsonify({"error": "Invalid token type"}), 401
            g.mfa_user_id = data["user_id"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "MFA token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid MFA token"}), 401

        return f(*args, **kwargs)
    return decorated
