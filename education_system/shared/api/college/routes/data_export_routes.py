"""API routes for data export."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.data_export.services.data_export_service import DataExportService
from education_system.college_system.core.i18n import t

data_export_bp = Blueprint("data-export", __name__, url_prefix="/api/data-export")

_db_path = None


def init_data_export_routes(db_path=None):
    global _db_path
    _db_path = db_path


@data_export_bp.route("/jobs", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_jobs():
    svc = DataExportService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_jobs(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@data_export_bp.route("/jobs/<int:pk>", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def get_job(pk):
    svc = DataExportService(_db_path)
    item = svc.get_job(pk)
    if not item:
        return jsonify({"error": t("api.data_export.not_found")}), 404
    return jsonify({"data": item})
@data_export_bp.route("/jobs", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_job():
    data = get_json_body()
    svc = DataExportService(_db_path)
    result = svc.create_job(**data)
    return jsonify({"message": t("api.data_export.created"), "data": result}), 201
@data_export_bp.route("/jobs/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_job(pk):
    svc = DataExportService(_db_path)
    svc.delete_job(pk)
    return jsonify({"message": t("api.data_export.deleted")})
@data_export_bp.route("/templates", methods=["GET"])
@token_required
@role_required('admin', 'staff')
def list_templates():
    svc = DataExportService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_templates(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@data_export_bp.route("/templates", methods=["POST"])
@token_required
@role_required('admin')
def create_template():
    data = get_json_body()
    svc = DataExportService(_db_path)
    result = svc.create_template(**data)
    return jsonify({"message": t("api.data_export.created"), "data": result}), 201
@data_export_bp.route("/stats", methods=["GET"])
@token_required
@role_required('admin')
def get_stats():
    svc = DataExportService(_db_path)
    result = svc.get_stats()
    return jsonify({"data": result})
