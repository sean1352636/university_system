"""API routes for data dashboard."""

from flask import Blueprint, jsonify, request
from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.data_dashboard.services.data_dashboard_service import DataDashboardService
from education_system.college_system.core.i18n import t

data_dashboard_bp = Blueprint("data-dashboard", __name__, url_prefix="/api/data-dashboard")

_db_path = None


def init_data_dashboard_routes(db_path=None):
    global _db_path
    _db_path = db_path


@data_dashboard_bp.route("", methods=["GET"])
@token_required
def list_widgets():
    svc = DataDashboardService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_widgets(limit=limit, offset=offset)
    total = svc.count_widgets()
    return jsonify(paginated_response(items, total))


@data_dashboard_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_widget(pk):
    svc = DataDashboardService(_db_path)
    item = svc.get_widget(pk)
    if not item:
        return jsonify({"error": t("api.common.not_found")}), 404
    return jsonify({"data": item})


@data_dashboard_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_widget():
    data = get_json_body()
    require_fields(data, "user_id", "widget_type")
    svc = DataDashboardService(_db_path)
    item = svc.create_widget(**data)
    return jsonify({"message": t("api.common.created"), "data": item}), 201


@data_dashboard_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_widget(pk):
    data = get_json_body()
    svc = DataDashboardService(_db_path)
    item = svc.update_widget(pk, **data)
    return jsonify({"message": t("api.common.updated"), "data": item})


@data_dashboard_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_widget(pk):
    svc = DataDashboardService(_db_path)
    svc.delete_widget(pk)
    return jsonify({"message": t("api.common.deleted")})
