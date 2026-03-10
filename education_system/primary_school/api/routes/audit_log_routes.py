"""Audit Log API routes."""

from flask import Blueprint, jsonify, request

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.modules.domain.admin.audit_log.services.audit_service import AuditService

audit_log_bp = Blueprint("audit_log", __name__, url_prefix="/api/audit-log")

_db_path = None


def init_audit_log_routes(db_path=None):
    global _db_path
    _db_path = db_path


@audit_log_bp.route("", methods=["GET"])
@token_required
@role_required("admin")
def list_audit_entries():
    svc = AuditService(_db_path)
    limit = int(request.args.get("limit", 50))
    items = svc.get_logs(limit=limit)
    return jsonify({"data": items, "count": len(items)})
