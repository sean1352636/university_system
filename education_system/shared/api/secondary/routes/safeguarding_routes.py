"""Safeguarding API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.pastoral_care.safeguarding.services.safeguarding_service import SafeguardingService

safeguarding_bp = Blueprint("safeguarding", __name__, url_prefix="/api/safeguarding")

_db_path = None


def init_safeguarding_routes(db_path=None):
    global _db_path
    _db_path = db_path


@safeguarding_bp.route("", methods=["POST"])
@token_required
def log_concern():
    data = get_json_body()
    require_fields(data, "student_id", "concern_type", "description")
    svc = SafeguardingService(_db_path)
    result = svc.log_concern(student_id=data["student_id"], concern_type=data["concern_type"], description=data["description"], reported_by=data.get("reported_by", ""), severity=data.get("severity", "medium"))
    return jsonify({"message": "Created.", "data": result}), 201


@safeguarding_bp.route("", methods=["GET"])
@token_required
@role_required("admin", "teacher")
def list_concerns():
    svc = SafeguardingService(_db_path)
    result = svc.list_concerns()
    return jsonify({"data": result})


@safeguarding_bp.route("/<int:concern_id>/resolve", methods=["PUT"])
@token_required
@role_required("admin")
def resolve_concern(concern_id):
    data = request.get_json(silent=True) or {}
    svc = SafeguardingService(_db_path)
    result = svc.resolve_concern(concern_id, data.get("resolution", "") if data else "")
    return jsonify({"message": "Updated.", "data": result})


@safeguarding_bp.route("/<int:concern_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_concern(concern_id):
    svc = SafeguardingService(_db_path)
    result = svc.delete_concern(concern_id)
    return jsonify({"message": "Deleted.", "data": result})

