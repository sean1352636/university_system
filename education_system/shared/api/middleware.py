"""Shared API middleware for all education system Flask apps.

Improvement #12: Consistent API middleware across all systems.

Provides:
- Request logging
- Request ID tracking
- Response time headers
- Standard error response format
"""

import logging
import time
import uuid

logger = logging.getLogger(__name__)


def register_middleware(app):
    """Register shared middleware on a Flask app.

    Usage (in create_app):
        from education_system.shared.api.middleware import register_middleware
        register_middleware(app)
    """

    @app.before_request
    def add_request_id():
        from flask import request, g
        g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        g.request_start = time.time()

    @app.after_request
    def add_response_headers(response):
        from flask import g
        # Request ID for tracing
        request_id = getattr(g, "request_id", None)
        if request_id:
            response.headers["X-Request-ID"] = request_id

        # Response time
        start = getattr(g, "request_start", None)
        if start:
            elapsed = (time.time() - start) * 1000
            response.headers["X-Response-Time"] = f"{elapsed:.1f}ms"

        return response

    @app.after_request
    def log_request(response):
        from flask import request, g
        if request.path.startswith("/api/health"):
            return response  # Don't log health checks

        request_id = getattr(g, "request_id", "-")
        start = getattr(g, "request_start", None)
        elapsed = f"{(time.time() - start) * 1000:.0f}ms" if start else "-"

        logger.info(
            "%s %s %s %s [%s]",
            request.method,
            request.path,
            response.status_code,
            elapsed,
            request_id,
        )
        return response


def standard_error_response(code: int, message: str, details: dict | None = None) -> tuple:
    """Create a standardised JSON error response.

    Usage:
        return standard_error_response(404, "Student not found")
        return standard_error_response(422, "Validation failed", {"field": "email", "error": "invalid"})
    """
    from flask import jsonify
    body = {"error": message, "status": code}
    if details:
        body["details"] = details
    return jsonify(body), code
