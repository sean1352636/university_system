"""JWT authentication for the Flask API.

Provides token creation, validation, and the ``@token_required``
decorator that populates ``flask.g.current_user``.
"""

from __future__ import annotations

import functools
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from flask import current_app, g, jsonify, request

logger = logging.getLogger(__name__)

# In-memory set of invalidated JTIs (cleared on restart – acceptable for
# single-process deployments).
_blacklisted_tokens: set[str] = set()


def create_access_token(user: dict[str, Any], config: dict) -> str:
    """Create a signed JWT access token for *user*."""
    jwt_cfg = config["jwt"]
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=jwt_cfg.get("access_token_expires_minutes", 30)
    )
    payload = {
        "sub": user["username"],
        "user_id": user["id"],
        "role": user["role"],
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": expires,
    }
    return jwt.encode(payload, jwt_cfg["secret_key"], algorithm=jwt_cfg.get("algorithm", "HS256"))


def create_refresh_token(user: dict[str, Any], config: dict) -> str:
    """Create a signed JWT refresh token for *user*."""
    jwt_cfg = config["jwt"]
    expires = datetime.now(timezone.utc) + timedelta(
        days=jwt_cfg.get("refresh_token_expires_days", 7)
    )
    payload = {
        "sub": user["username"],
        "user_id": user["id"],
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
        "exp": expires,
    }
    return jwt.encode(payload, jwt_cfg["secret_key"], algorithm=jwt_cfg.get("algorithm", "HS256"))


def decode_token(token: str, config: dict) -> dict[str, Any]:
    """Decode and validate a JWT token.  Raises on invalid/expired tokens."""
    jwt_cfg = config["jwt"]
    return jwt.decode(token, jwt_cfg["secret_key"], algorithms=[jwt_cfg.get("algorithm", "HS256")])


def blacklist_token(token: str) -> None:
    """Mark a token as revoked."""
    _blacklisted_tokens.add(token)


def is_token_blacklisted(token: str) -> bool:
    return token in _blacklisted_tokens


def _extract_bearer_token() -> Optional[str]:
    """Extract the Bearer token from the Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def token_required(fn):
    """Decorator that enforces a valid access token.

    On success, ``flask.g.current_user`` is set to the decoded payload.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        token = _extract_bearer_token()
        if not token:
            return jsonify({"error": "Missing authorization token", "status": 401}), 401

        if is_token_blacklisted(token):
            return jsonify({"error": "Token has been revoked", "status": 401}), 401

        try:
            config = current_app.config["API_CONFIG"]
            payload = decode_token(token, config)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired", "status": 401}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token", "status": 401}), 401

        if payload.get("type") != "access":
            return jsonify({"error": "Invalid token type", "status": 401}), 401

        g.current_user = payload
        g.raw_token = token
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    """Decorator that requires an admin role (must be used after @token_required)."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if g.get("current_user", {}).get("role") != "admin":
            return jsonify({"error": "Admin access required", "status": 403}), 403
        return fn(*args, **kwargs)

    return wrapper


# ---- Simple in-memory rate limiter ------------------------------------------

_rate_limit_store: dict[str, list[float]] = {}


def check_rate_limit(config: dict) -> Optional[tuple]:
    """Return an error tuple if the caller has exceeded the rate limit, else None."""
    rl_cfg = config.get("rate_limiting", {})
    if not rl_cfg.get("enabled", False):
        return None

    rpm = rl_cfg.get("requests_per_minute", 100)
    ip = request.remote_addr or "unknown"
    now = time.time()
    window_start = now - 60

    timestamps = _rate_limit_store.get(ip, [])
    timestamps = [t for t in timestamps if t > window_start]
    timestamps.append(now)
    _rate_limit_store[ip] = timestamps

    if len(timestamps) > rpm:
        return jsonify({"error": "Rate limit exceeded", "status": 429}), 429

    return None
