"""CSRF token generation and validation."""

import hashlib
import hmac
import os
import time

_SECRET = os.environ.get("CSRF_SECRET", os.urandom(32).hex())
_TOKEN_LIFETIME = 3600  # 1 hour


def generate_csrf_token(session_id: str) -> str:
    """Generate a CSRF token tied to a session."""
    timestamp = str(int(time.time()))
    payload = f"{session_id}:{timestamp}"
    signature = hmac.new(
        _SECRET.encode() if isinstance(_SECRET, str) else _SECRET,
        payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{timestamp}:{signature}"


def validate_csrf_token(token: str, session_id: str) -> bool:
    """Validate a CSRF token against a session."""
    try:
        parts = token.split(":", 1)
        if len(parts) != 2:
            return False
        timestamp_str, signature = parts
        timestamp = int(timestamp_str)
        if time.time() - timestamp > _TOKEN_LIFETIME:
            return False
        payload = f"{session_id}:{timestamp_str}"
        expected = hmac.new(
            _SECRET.encode() if isinstance(_SECRET, str) else _SECRET,
            payload.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


def csrf_protect(get_session_id):
    """Flask decorator factory for CSRF protection.

    Usage:
        @app.before_request
        @csrf_protect(lambda: session.get('id'))
        def check_csrf(): ...
    """
    from functools import wraps

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            from flask import request, abort
            if request.method in ("POST", "PUT", "DELETE", "PATCH"):
                token = (request.headers.get("X-CSRF-Token")
                         or request.form.get("_csrf_token"))
                sid = get_session_id()
                if not token or not sid or not validate_csrf_token(token, sid):
                    abort(403, "Invalid or missing CSRF token")
            return f(*args, **kwargs)
        return wrapper
    return decorator
