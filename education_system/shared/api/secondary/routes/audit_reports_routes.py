"""Audit reports API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.shared.api.secondary.pagination import get_pagination_params, paginated_response
from education_system.secondary_school.modules.domain.admin.audit_reports.services.audit_reports_service import AuditReportsService

audit_reports_bp = Blueprint("audit-reports", __name__, url_prefix="/api/audit-reports")

_db_path = None


def init_audit_reports_routes(db_path=None):
    global _db_path
    _db_path = db_path


@audit_reports_bp.route("", methods=["GET"])
@token_required
def list_audit_reports():
    svc = AuditReportsService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_all(limit=limit, offset=offset)
    total = len(items)
    return jsonify(paginated_response(items, total))


@audit_reports_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_audit_reports_item(pk):
    svc = AuditReportsService(_db_path)
    item = svc.get(pk)
    if not item:
        return jsonify({"error": "Not found."}), 404
    return jsonify({"data": item})


@audit_reports_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_audit_reports_item():
    data = get_json_body()
    svc = AuditReportsService(_db_path)
    result = svc.create(**data)
    return jsonify({"message": "Created.", "data": result}), 201


@audit_reports_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_audit_reports_item(pk):
    data = get_json_body()
    svc = AuditReportsService(_db_path)
    result = svc.update(pk, **data)
    return jsonify({"message": "Updated.", "data": result})


@audit_reports_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_audit_reports_item(pk):
    svc = AuditReportsService(_db_path)
    svc.delete(pk)
    return jsonify({"message": "Deleted."})
