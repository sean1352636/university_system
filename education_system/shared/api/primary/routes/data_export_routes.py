"""Data Export API routes."""

from flask import Blueprint, jsonify

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.primary_school.modules.domain.admin.data_export.services.data_export_service import DataExportService

data_export_bp = Blueprint("data_export", __name__, url_prefix="/api/data-export")

_db_path = None


def init_data_export_routes(db_path=None):
    global _db_path
    _db_path = db_path


@data_export_bp.route("/export", methods=["POST"])
@token_required
@role_required("admin")
def export_data():
    data = get_json_body()
    require_fields(data, "export_type")
    svc = DataExportService(_db_path)
    result = svc.export_data(data["export_type"])
    return jsonify({"message": "Export completed.", "data": result})
