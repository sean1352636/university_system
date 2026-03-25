"""Detentions API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.pastoral_care.detentions.services.detention_service import DetentionService

detentions_bp = Blueprint("detentions", __name__, url_prefix="/api/detentions")

_db_path = None


def init_detentions_routes(db_path=None):
    global _db_path
    _db_path = db_path


@detentions_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_detention():
    data = get_json_body()
    require_fields(data, "student_id", "reason", "date")
    svc = DetentionService(_db_path)
    result = svc.create_detention(student_id=data["student_id"], reason=data["reason"], date=data["date"], detention_type=data.get("detention_type", "after_school"), duration=data.get("duration", 30))
    return jsonify({"message": "Created.", "data": result}), 201


@detentions_bp.route("", methods=["GET"])
@token_required
def list_detentions():
    svc = DetentionService(_db_path)
    result = svc.list_detentions()
    return jsonify({"data": result})


@detentions_bp.route("/<int:det_id>/attended", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def mark_attended(det_id):
    svc = DetentionService(_db_path)
    result = svc.mark_attended(det_id)
    return jsonify({"message": "Updated.", "data": result})


@detentions_bp.route("/<int:det_id>/missed", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def mark_missed(det_id):
    svc = DetentionService(_db_path)
    result = svc.mark_missed(det_id)
    return jsonify({"message": "Updated.", "data": result})


@detentions_bp.route("/<int:det_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_detention(det_id):
    svc = DetentionService(_db_path)
    result = svc.delete_detention(det_id)
    return jsonify({"message": "Deleted.", "data": result})

