"""API routes for audit & compliance reports."""

from flask import Blueprint, jsonify, request
from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.audit_reports.services.audit_reports_service import AuditReportService
from education_system.college_system.core.i18n import t

audit_report_bp = Blueprint("audit-reports", __name__, url_prefix="/api/audit-reports")

_db_path = None


def init_audit_report_routes(db_path=None):
    global _db_path
    _db_path = db_path


@audit_report_bp.route("", methods=["GET"])
@token_required
def list_reports():
    svc = AuditReportService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_reports(limit=limit, offset=offset)
    total = svc.count_reports()
    return jsonify(paginated_response(items, total))


@audit_report_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_report(pk):
    svc = AuditReportService(_db_path)
    item = svc.get_report(pk)
    if not item:
        return jsonify({"error": t("api.audit_reports.not_found")}), 404
    return jsonify({"data": item})


@audit_report_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_report():
    data = get_json_body()
    require_fields(data, "report_type", "title")
    svc = AuditReportService(_db_path)
    item = svc.create_report(**data)
    return jsonify({"message": t("api.audit_reports.generated"), "data": item}), 201


@audit_report_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_report(pk):
    data = get_json_body()
    svc = AuditReportService(_db_path)
    item = svc.update_report(pk, **data)
    return jsonify({"message": t("api.common.updated"), "data": item})


@audit_report_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_report(pk):
    svc = AuditReportService(_db_path)
    svc.delete_report(pk)
    return jsonify({"message": t("api.common.deleted")})
