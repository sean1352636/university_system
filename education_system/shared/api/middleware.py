"""Shared API middleware for all education system Flask apps.

Improvement #12: Consistent API middleware across all systems.

Provides:
- Request logging (structured JSON when LOG_FORMAT=json)
- Correlation / request ID tracking via contextvars
- Response time headers
- Prometheus metrics recording
- Standard error response format
"""

import logging
import time
import uuid

from education_system.shared.core.correlation import set_correlation_id
from education_system.shared.core.metrics import metrics

logger = logging.getLogger(__name__)

# Paths that are too noisy / low-value to log on every scrape
_SILENT_PATHS = frozenset({"/metrics", "/api/v1/health", "/health"})


def register_middleware(app):
    """Register shared middleware on a Flask app.

    Usage (in create_app):
        from education_system.shared.api.middleware import register_middleware
        register_middleware(app)
    """

    @app.before_request
    def add_request_id():
        from flask import request, g
        # Honour an incoming correlation header; generate one if absent
        cid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        g.request_id = cid
        g.request_start = time.time()
        # Propagate into the correlation context so all log records carry it
        set_correlation_id(cid)
        metrics.gauge_inc("active_connections")

    @app.after_request
    def add_response_headers(response):
        from flask import g
        request_id = getattr(g, "request_id", None)
        if request_id:
            response.headers["X-Request-ID"] = request_id

        start = getattr(g, "request_start", None)
        if start:
            elapsed = (time.time() - start) * 1000
            response.headers["X-Response-Time"] = f"{elapsed:.1f}ms"

        return response

    @app.after_request
    def record_metrics_and_log(response):
        from flask import request, g

        start = getattr(g, "request_start", None)
        duration = (time.time() - start) if start else 0.0

        # Record Prometheus metrics (also decrements active_connections)
        metrics.record_request(
            method=request.method,
            status_code=response.status_code,
            duration_seconds=duration,
        )

        # Skip structured log for high-frequency scrape endpoints
        if any(request.path.startswith(p) for p in _SILENT_PATHS):
            return response

        request_id = getattr(g, "request_id", "-")
        elapsed_ms = duration * 1000

        logger.info(
            "%s %s %s %.0fms",
            request.method,
            request.path,
            response.status_code,
            elapsed_ms,
            extra={
                "request_id": request_id,
                "http_method": request.method,
                "http_path": request.path,
                "http_status": response.status_code,
                "duration_ms": round(elapsed_ms, 1),
            },
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
