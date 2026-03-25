"""API routes for reports."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.reports.services.reports_service import ReportsService
from education_system.college_system.core.i18n import t

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")

_db_path = None


def init_reports_routes(db_path=None):
    global _db_path
    _db_path = db_path


@reports_bp.route("", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_reports():
    svc = ReportsService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_reports(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@reports_bp.route("/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_report(pk):
    svc = ReportsService(_db_path)
    item = svc.get_report(pk)
    if not item:
        return jsonify({"error": t("api.reports.not_found")}), 404
    return jsonify({"data": item})
@reports_bp.route("", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_report():
    data = get_json_body()
    svc = ReportsService(_db_path)
    result = svc.create_report(**data)
    return jsonify({"message": t("api.reports.created"), "data": result}), 201
@reports_bp.route("/<int:pk>/entries", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_entries(pk):
    svc = ReportsService(_db_path)
    result = svc.list_entries(pk)
    return jsonify({"data": result})
@reports_bp.route("/<int:pk>/entries", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def add_entry(pk):
    data = get_json_body()
    svc = ReportsService(_db_path)
    result = svc.add_entry(pk, **data)
    return jsonify({"message": t("api.reports.success"), "data": result}), 201
