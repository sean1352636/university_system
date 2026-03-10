"""API routes for emergency management."""

from flask import Blueprint, jsonify, request
from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.api.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.emergency.services.emergency_service import EmergencyService

emergency_bp = Blueprint("emergency", __name__, url_prefix="/api/emergency")

_db_path = None


def init_emergency_routes(db_path=None):
    global _db_path
    _db_path = db_path


@emergency_bp.route("", methods=["GET"])
@token_required
def list_drills():
    svc = EmergencyService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_drills(limit=limit, offset=offset)
    total = svc.count_drills()
    return jsonify(paginated_response(items, total))


@emergency_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_drill(pk):
    svc = EmergencyService(_db_path)
    item = svc.get_drill(pk)
    if not item:
        return jsonify({"error": "Drill not found."}), 404
    return jsonify({"data": item})


@emergency_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_drill():
    data = get_json_body()
    require_fields(data, "drill_type", "scheduled_date")
    svc = EmergencyService(_db_path)
    item = svc.create_drill(**data)
    return jsonify({"message": "Drill created.", "data": item}), 201


@emergency_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_drill(pk):
    data = get_json_body()
    svc = EmergencyService(_db_path)
    item = svc.update_drill(pk, **data)
    return jsonify({"message": "Drill updated.", "data": item})


@emergency_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_drill(pk):
    svc = EmergencyService(_db_path)
    svc.delete_drill(pk)
    return jsonify({"message": "Drill deleted."})
