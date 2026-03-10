"""JWT authentication decorators for the Secondary School API."""

import functools
from datetime import datetime, timedelta

import jwt
from flask import request, jsonify, g

from education_system.secondary_school.api.config import Config
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
            return jsonify({"error": "Authentication required", "message": "Missing token."}), 401

        try:
            data = decode_token(token)
            g.current_user = {
                "user_id": data["user_id"],
                "username": data["username"],
                "role": data["role"],
            }
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired", "message": "Please log in again."}), 401
        except jwt.InvalidTokenError:
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
                return jsonify({
                    "error": "Access denied",
                    "message": f"Requires role: {', '.join(roles)}",
                }), 403

            return f(*args, **kwargs)
        return decorated
    return decorator
