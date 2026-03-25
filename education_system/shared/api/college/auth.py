"""JWT authentication for the College API — delegates to shared auth."""

from education_system.shared.api.auth import (
    generate_token,
    decode_token,
    token_required,
    role_required,
    system_required,
    _create_mfa_token,
)

# MFA token decorator kept locally for college-specific MFA routes
import functools
import jwt
from flask import request, jsonify, g
from education_system.shared.api.college.config import Config


def mfa_token_required(f):
    """Decorator that requires a valid MFA verification token."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "MFA token required"}), 401

        token = auth_header.split(" ", 1)[1]
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
