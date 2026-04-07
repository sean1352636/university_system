"""Progress dashboard API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.shared.api.secondary.pagination import get_pagination_params, paginated_response
from education_system.secondary_school.modules.domain.portals.progress_dashboard.services.progress_dashboard_service import ProgressDashboardService

progress_dashboard_bp = Blueprint("progress-dashboard", __name__, url_prefix="/api/progress-dashboard")

_db_path = None


def init_progress_dashboard_routes(db_path=None):
    global _db_path
    _db_path = db_path


@progress_dashboard_bp.route("", methods=["GET"])
@token_required
def list_progress_dashboard():
    svc = ProgressDashboardService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_all(limit=limit, offset=offset)
    total = len(items)
    return jsonify(paginated_response(items, total))


@progress_dashboard_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_progress_dashboard_item(pk):
    svc = ProgressDashboardService(_db_path)
    item = svc.get(pk)
    if not item:
        return jsonify({"error": "Not found."}), 404
    return jsonify({"data": item})


@progress_dashboard_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_progress_dashboard_item():
    data = get_json_body()
    svc = ProgressDashboardService(_db_path)
    result = svc.create(**data)
    return jsonify({"message": "Created.", "data": result}), 201


@progress_dashboard_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_progress_dashboard_item(pk):
    data = get_json_body()
    svc = ProgressDashboardService(_db_path)
    result = svc.update(pk, **data)
    return jsonify({"message": "Updated.", "data": result})


@progress_dashboard_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_progress_dashboard_item(pk):
    svc = ProgressDashboardService(_db_path)
    svc.delete(pk)
    return jsonify({"message": "Deleted."})
