"""Audit Log API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.admin.audit_log.services.audit_service import AuditService

audit_log_bp = Blueprint("audit_log", __name__, url_prefix="/api/audit-log")

_db_path = None


def init_audit_log_routes(db_path=None):
    global _db_path
    _db_path = db_path


@audit_log_bp.route("", methods=["GET"])
@token_required
@role_required("admin")
def list_entries():
    svc = AuditService(_db_path)
    result = svc.list_entries()
    return jsonify({"data": result})


@audit_log_bp.route("/count", methods=["GET"])
@token_required
@role_required("admin")
def entry_count():
    svc = AuditService(_db_path)
    result = svc.entry_count()
    return jsonify({"data": result})

