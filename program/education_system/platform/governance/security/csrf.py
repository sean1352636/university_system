"""CSRF token generation and validation."""

import hashlib
import hmac
import os
import time
import threading
from urllib.parse import urlsplit

_SECRET = os.environ.get("CSRF_SECRET", os.urandom(32).hex())
_TOKEN_LIFETIME = 3600  # 1 hour
_USED_TOKENS: dict[str, float] = {}
_USED_LOCK = threading.Lock()


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


def consume_csrf_token(token: str, session_id: str) -> bool:
    """Validate and atomically consume a token, preventing replay."""
    if not validate_csrf_token(token, session_id):
        return False
    now = time.time()
    with _USED_LOCK:
        for key, expiry in list(_USED_TOKENS.items()):
            if expiry <= now:
                _USED_TOKENS.pop(key, None)
        key = f"{session_id}:{token}"
        if key in _USED_TOKENS:
            return False
        _USED_TOKENS[key] = now + _TOKEN_LIFETIME
    return True


def _same_origin(request) -> bool:
    """Require an explicit same-origin Origin or Referer on mutations."""
    allowed = {str(x).strip().rstrip("/") for x in os.getenv("CSRF_ALLOWED_ORIGINS", "").split(",") if x.strip()}
    expected = f"{request.scheme}://{request.host}".rstrip("/")
    allowed.add(expected)
    origin = request.headers.get("Origin")
    if origin:
        return origin.rstrip("/") in allowed
    referer = request.headers.get("Referer")
    if referer:
        parsed = urlsplit(referer)
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/") in allowed
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
                if not _same_origin(request) or not token or not sid or not consume_csrf_token(token, sid):
                    abort(403, "Invalid or missing CSRF token")
            return f(*args, **kwargs)
        return wrapper
    return decorator


def register_csrf_middleware(app):
    """Protect state-changing requests carrying a browser session cookie."""
    from flask import abort, request, session

    # The per-process random fallback in _SECRET mints tokens that every other
    # gunicorn worker rejects and that die on restart — in production that is
    # indistinguishable from CSRF protection being broken, so require a
    # persistent shared secret there. Unset APP_ENV counts as production.
    app_env = os.getenv("APP_ENV", "production").strip().lower()
    if app_env not in ("development", "dev", "local", "test", "testing"):
        if not os.environ.get("CSRF_SECRET"):
            raise RuntimeError(
                "CSRF_SECRET must be set in production: without it each worker "
                "mints tokens the others reject. Set a persistent CSRF_SECRET "
                "via the environment or secret manager."
            )

    @app.before_request
    def _csrf_cookie_guard():
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return
        # Bearer-only API calls are not vulnerable to cookie CSRF.  Any
        # request with a session cookie must, however, prove possession of a
        # current session-bound token and same-origin browser context.
        cookie_name = app.config.get("SESSION_COOKIE_NAME", "session")
        if cookie_name not in request.cookies:
            return
        sid = session.get("session_id") or session.get("id")
        token = request.headers.get("X-CSRF-Token") or request.form.get("_csrf_token")
        if not sid or not token or not _same_origin(request) or not consume_csrf_token(token, str(sid)):
            abort(403, "Invalid or missing CSRF token")
