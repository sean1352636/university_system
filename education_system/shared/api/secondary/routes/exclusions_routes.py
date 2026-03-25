"""Exclusions API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.pastoral_care.exclusions.services.exclusion_service import ExclusionService

exclusions_bp = Blueprint("exclusions", __name__, url_prefix="/api/exclusions")

_db_path = None


def init_exclusions_routes(db_path=None):
    global _db_path
    _db_path = db_path


@exclusions_bp.route("", methods=["POST"])
@token_required
@role_required("admin")
def create_exclusion():
    data = get_json_body()
    require_fields(data, "student_id", "exclusion_type", "reason", "start_date")
    svc = ExclusionService(_db_path)
    result = svc.create_exclusion(student_id=data["student_id"], exclusion_type=data["exclusion_type"], reason=data["reason"], start_date=data["start_date"], end_date=data.get("end_date", ""), days=data.get("days", 1))
    return jsonify({"message": "Created.", "data": result}), 201


@exclusions_bp.route("", methods=["GET"])
@token_required
@role_required("admin", "teacher")
def list_exclusions():
    svc = ExclusionService(_db_path)
    result = svc.list_exclusions()
    return jsonify({"data": result})


@exclusions_bp.route("/<int:exc_id>/close", methods=["PUT"])
@token_required
@role_required("admin")
def close_exclusion(exc_id):
    svc = ExclusionService(_db_path)
    result = svc.close_exclusion(exc_id)
    return jsonify({"message": "Updated.", "data": result})


@exclusions_bp.route("/<int:exc_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_exclusion(exc_id):
    svc = ExclusionService(_db_path)
    result = svc.delete_exclusion(exc_id)
    return jsonify({"message": "Deleted.", "data": result})


@exclusions_bp.route("/summary", methods=["GET"])
@token_required
@role_required("admin")
def summary():
    svc = ExclusionService(_db_path)
    result = svc.summary()
    return jsonify({"data": result})

