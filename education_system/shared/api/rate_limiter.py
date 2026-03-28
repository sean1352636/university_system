"""In-memory rate limiter for Flask APIs (no Redis dependency).

Supports both per-IP and per-user (JWT-based) rate limiting.
"""

import time
import threading
import logging
from functools import wraps
from flask import request, jsonify, g

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token-bucket rate limiter with per-IP and per-user tracking.

    Usage:
        limiter = RateLimiter()
        limiter.init_app(app)

        @app.route("/api/login", methods=["POST"])
        @limiter.limit("5/minute")
        def login():
            ...

        @app.route("/api/v1/college/students")
        @limiter.limit("100/minute", key_func=limiter.user_key)
        def list_students():
            ...
    """

    def __init__(self):
        self._buckets: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._cleanup_interval = 300
        self._last_cleanup = time.time()
        self._enabled = True

    def init_app(self, app):
        """Register rate limiter with a Flask app."""
        self._enabled = not app.config.get("TESTING", False)

        @app.after_request
        def add_rate_limit_headers(response):
            info = getattr(request, "_rate_limit_info", None)
            if info:
                response.headers["X-RateLimit-Limit"] = str(info["limit"])
                response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
                response.headers["X-RateLimit-Reset"] = str(int(info["reset"]))
            return response

    # ── Key functions ──────────────────────────────────────────────────

    @staticmethod
    def ip_key() -> str:
        """Rate limit key based on client IP address."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"  # nosemgrep: python.flask.security.audit.directly-returned-format-string
        return f"ip:{request.remote_addr or 'unknown'}"  # nosemgrep: python.flask.security.audit.directly-returned-format-string

    @staticmethod
    def user_key() -> str:
        """Rate limit key based on authenticated user ID.

        Falls back to IP if no user is authenticated.
        """
        user = getattr(g, "current_user", None)
        if user and user.get("user_id"):
            return f"user:{user['user_id']}"  # nosemgrep: python.flask.security.audit.directly-returned-format-string
        # Check API key
        api_info = getattr(g, "api_key_info", None)
        if api_info:
            return f"apikey:{api_info['id']}"  # nosemgrep: python.flask.security.audit.directly-returned-format-string
        # Fallback to IP
        return RateLimiter.ip_key()

    @staticmethod
    def user_and_ip_key() -> str:
        """Combined key: limits per-user AND per-IP simultaneously."""
        user = getattr(g, "current_user", None)
        ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr or "unknown"
        if user and user.get("user_id"):
            return f"user:{user['user_id']}+ip:{ip}"  # nosemgrep: python.flask.security.audit.directly-returned-format-string
        return f"ip:{ip}"  # nosemgrep: python.flask.security.audit.directly-returned-format-string

    # ── Decorator ──────────────────────────────────────────────────────

    def limit(self, rate_string: str, key_func=None):
        """Decorator to apply rate limiting.

        Args:
            rate_string: Format "{count}/{period}" e.g. "5/minute", "100/hour"
            key_func: Callable returning the rate limit key. Defaults to ip_key.
                      Use limiter.user_key for per-user limiting.
        """
        count, period = self._parse_rate(rate_string)
        if key_func is None:
            key_func = self.ip_key

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self._enabled:
                    return func(*args, **kwargs)

                key = f"{request.endpoint}:{key_func()}"
                allowed, info = self._check_rate(key, count, period)
                request._rate_limit_info = info

                if not allowed:
                    logger.warning("Rate limit exceeded: %s from %s",
                                   request.endpoint, key_func())
                    response = jsonify({
                        "error": "Rate limit exceeded",
                        "retry_after": int(info["reset"] - time.time()),
                    })
                    response.status_code = 429
                    response.headers["Retry-After"] = str(int(info["reset"] - time.time()))
                    return response

                return func(*args, **kwargs)
            return wrapper
        return decorator

    # ── Internal helpers ───────────────────────────────────────────────

    def _get_client_ip(self) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.remote_addr or "unknown"

    def _parse_rate(self, rate_string: str) -> tuple[int, float]:
        parts = rate_string.split("/")
        count = int(parts[0])
        period_map = {"second": 1, "sec": 1, "s": 1,
                      "minute": 60, "min": 60, "m": 60,
                      "hour": 3600, "hr": 3600, "h": 3600,
                      "day": 86400, "d": 86400}
        period = period_map.get(parts[1].lower(), 60)
        return count, period

    def _check_rate(self, key: str, max_count: int, period: float) -> tuple[bool, dict]:
        now = time.time()
        with self._lock:
            if now - self._last_cleanup > self._cleanup_interval:
                self._cleanup(now)
                self._last_cleanup = now

            bucket = self._buckets.get(key)
            if bucket is None or now > bucket["reset"]:
                self._buckets[key] = {"count": 1, "reset": now + period, "limit": max_count}
                return True, {"limit": max_count, "remaining": max_count - 1, "reset": now + period}

            bucket["count"] += 1
            remaining = max(0, max_count - bucket["count"])
            info = {"limit": max_count, "remaining": remaining, "reset": bucket["reset"]}
            return (bucket["count"] <= max_count), info

    def _cleanup(self, now: float) -> None:
        expired = [k for k, v in self._buckets.items() if now > v["reset"]]
        for k in expired:
            del self._buckets[k]


rate_limiter = RateLimiter()
