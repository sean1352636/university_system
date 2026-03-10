"""API routes for mobile dashboard."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.mobile_dashboard.services.mobile_dashboard_service import MobileDashboardService

mobile_dashboard_bp = Blueprint("mobile-dashboard", __name__, url_prefix="/api/mobile-dashboard")

_db_path = None


def init_mobile_dashboard_routes(db_path=None):
    global _db_path
    _db_path = db_path


@mobile_dashboard_bp.route("", methods=["GET"])
@token_required
def list_widgets():
    svc = MobileDashboardService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_widgets(limit=limit, offset=offset)
    total = svc.count_widgets()
    return jsonify(paginated_response(items, total))


@mobile_dashboard_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_widget(pk):
    svc = MobileDashboardService(_db_path)
    item = svc.get_widget(pk)
    if not item:
        return jsonify({"error": "Widget not found."}), 404
    return jsonify({"data": item})


@mobile_dashboard_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_widget():
    data = get_json_body()
    require_fields(data, "user_id", "widget_type")
    svc = MobileDashboardService(_db_path)
    item = svc.create_widget(**data)
    return jsonify({"message": "Widget created.", "data": item}), 201


@mobile_dashboard_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_widget(pk):
    data = get_json_body()
    svc = MobileDashboardService(_db_path)
    item = svc.update_widget(pk, **data)
    return jsonify({"message": "Widget updated.", "data": item})


@mobile_dashboard_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_widget(pk):
    svc = MobileDashboardService(_db_path)
    svc.delete_widget(pk)
    return jsonify({"message": "Widget deleted."})
