"""System API routes (health check, info)."""

from flask import Blueprint, jsonify

from education_system.college_system import __version__
from education_system.shared.api.college.auth import token_required, role_required
from education_system.college_system.infrastructure.security.audit import AuditLogger
from education_system.college_system.core.i18n import t

system_bp = Blueprint("system", __name__, url_prefix="/api/system")

_db_path = None


def init_system_routes(db_path=None):
    global _db_path
    _db_path = db_path


@system_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "version": __version__})


@system_bp.route("/info", methods=["GET"])
@token_required
def system_info():
    return jsonify({
        "name": "College Management System",
        "version": __version__,
        "modules": ["students", "courses", "enrollment", "grades", "attendance"],
    })


@system_bp.route("/audit", methods=["GET"])
@token_required
@role_required("admin")
def audit_log():
    logger = AuditLogger(_db_path)
    logs = logger.get_logs(limit=50)
    return jsonify({"data": logs, "count": len(logs)})
