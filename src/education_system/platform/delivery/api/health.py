"""Health check blueprint for Flask APIs.

Improvement #20: Health Check Endpoints
"""

import sqlite3
import time
import platform
import logging
from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

health_bp = Blueprint("health", __name__, url_prefix="/api")

_start_time = time.time()
_db_path: str | None = None
_system_name: str = "Education System"


def init_health(db_path: str | None = None, system_name: str = "Education System"):
    """Configure the health check endpoint."""
    global _db_path, _system_name
    _db_path = db_path
    _system_name = system_name


@health_bp.route("/health", methods=["GET"])
def health_check():
    """Comprehensive health check that verifies DB connectivity."""
    checks = {}
    healthy = True

    if _db_path:
        try:
            conn = sqlite3.connect(_db_path, timeout=5)
            conn.execute("SELECT 1")
            conn.close()
            checks["database"] = {"status": "healthy"}
        except Exception as e:
            logger.error("Database health check failed: %s", e)
            checks["database"] = {"status": "unhealthy", "error": "Database connection failed"}
            healthy = False
    else:
        checks["database"] = {"status": "unconfigured"}

    uptime = time.time() - _start_time
    response = {
        "status": "healthy" if healthy else "unhealthy",
        "system": _system_name,
        "uptime_seconds": round(uptime, 1),
        "python_version": platform.python_version(),
        "checks": checks,
    }
    return jsonify(response), 200 if healthy else 503


@health_bp.route("/health/ready", methods=["GET"])
def readiness_check():
    """Readiness probe — checks if the service can accept requests."""
    if _db_path:
        try:
            conn = sqlite3.connect(_db_path, timeout=5)
            conn.execute("SELECT 1")
            conn.close()
            return jsonify({"ready": True}), 200
        except Exception:
            return jsonify({"ready": False}), 503
    return jsonify({"ready": True}), 200


@health_bp.route("/health/live", methods=["GET"])
def liveness_check():
    """Liveness probe — confirms the process is running."""
    return jsonify({"alive": True}), 200
