"""Flask blueprint exposing Prometheus metrics and an enhanced health endpoint.

Endpoints
---------
GET /metrics
    Prometheus text exposition format.  Scraped by Prometheus or Grafana Agent.

GET /health/metrics
    JSON health snapshot including system status, DB connectivity, and uptime.
    Complements (but does not replace) the existing /api/v1/health endpoint.

Usage in unified_server.py::

    from education_system.platform.delivery.api.metrics_routes import metrics_bp, init_metrics
    init_metrics(db_paths={"auth": str(AUTH_DB_FILE)})
    app.register_blueprint(metrics_bp)
"""

from __future__ import annotations

import logging
import platform
import sqlite3
import time

from flask import Blueprint, Response, jsonify

logger = logging.getLogger(__name__)

from education_system.platform.kernel.core.metrics import metrics as _metrics

__all__ = ["metrics_bp", "init_metrics"]

metrics_bp = Blueprint("metrics", __name__)

_start_time = time.time()
_db_paths: dict[str, str] = {}
_system_name: str = "Education System (Unified)"


def init_metrics(
    db_paths: dict[str, str] | None = None,
    system_name: str = "Education System (Unified)",
) -> None:
    """Configure the metrics blueprint.

    Parameters
    ----------
    db_paths:
        Mapping of label → SQLite file path to probe in the health check,
        e.g. ``{"auth": "/path/to/auth.db"}``.
    system_name:
        Human-readable system name included in the health JSON response.
    """
    global _db_paths, _system_name
    _db_paths = db_paths or {}
    _system_name = system_name


# ---------------------------------------------------------------------------
# /metrics — Prometheus scrape endpoint
# ---------------------------------------------------------------------------

@metrics_bp.route("/metrics", methods=["GET"])
def prometheus_metrics() -> Response:
    """Expose all in-memory metrics in Prometheus text format."""
    body = _metrics.format_prometheus()
    return Response(body, status=200, mimetype="text/plain; version=0.0.4; charset=utf-8")


# ---------------------------------------------------------------------------
# /health/metrics — enriched JSON health check
# ---------------------------------------------------------------------------

@metrics_bp.route("/health/metrics", methods=["GET"])
def health_with_metrics() -> Response:
    """Return system status, DB connectivity, and current metric snapshot."""
    db_checks: dict[str, dict] = {}
    overall_healthy = True

    for label, path in _db_paths.items():
        try:
            conn = sqlite3.connect(path, timeout=3)
            conn.execute("SELECT 1")
            conn.close()
            db_checks[label] = {"status": "healthy"}
        except Exception as exc:
            logger.warning("Health check failed for %s: %s", label, exc)
            db_checks[label] = {"status": "unhealthy"}
            overall_healthy = False

    uptime = round(time.time() - _start_time, 1)
    metric_snapshot = _metrics.get_metrics()

    body = {
        "status": "healthy" if overall_healthy else "unhealthy",
        "system": _system_name,
        "uptime_seconds": uptime,
        "python_version": platform.python_version(),
        "databases": db_checks,
        "metrics": {
            "http_requests_total": sum(
                v for k, v in metric_snapshot["counters"].items()
                if k.startswith("http_requests_total")
            ),
            "http_errors_total": sum(
                v for k, v in metric_snapshot["counters"].items()
                if k.startswith("http_errors_total")
            ),
            "active_connections": metric_snapshot["gauges"].get("active_connections", 0),
        },
    }

    return jsonify(body), 200 if overall_healthy else 503
