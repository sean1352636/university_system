"""API routes for progress dashboard."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.progress_dashboard.services.progress_dashboard_service import ProgressDashboardService

progress_dashboard_bp = Blueprint("progress-dashboard", __name__, url_prefix="/api/progress-dashboard")

_db_path = None


def init_progress_dashboard_routes(db_path=None):
    global _db_path
    _db_path = db_path


@progress_dashboard_bp.route("", methods=["GET"])
@token_required
def list_snapshots():
    svc = ProgressDashboardService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_snapshots(limit=limit, offset=offset)
    total = svc.count_snapshots()
    return jsonify(paginated_response(items, total))


@progress_dashboard_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_snapshot(pk):
    svc = ProgressDashboardService(_db_path)
    item = svc.get_snapshot(pk)
    if not item:
        return jsonify({"error": "Snapshot not found."}), 404
    return jsonify({"data": item})


@progress_dashboard_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff", "instructor")
def create_snapshot():
    data = get_json_body()
    require_fields(data, "student_id")
    svc = ProgressDashboardService(_db_path)
    item = svc.create_snapshot(**data)
    return jsonify({"message": "Snapshot created.", "data": item}), 201


@progress_dashboard_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff", "instructor")
def update_snapshot(pk):
    data = get_json_body()
    svc = ProgressDashboardService(_db_path)
    item = svc.update_snapshot(pk, **data)
    return jsonify({"message": "Snapshot updated.", "data": item})


@progress_dashboard_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_snapshot(pk):
    svc = ProgressDashboardService(_db_path)
    svc.delete_snapshot(pk)
    return jsonify({"message": "Snapshot deleted."})
