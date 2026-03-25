"""Communication Log API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.communication.communication_log.services.comms_service import CommsService

comms_bp = Blueprint("comms", __name__, url_prefix="/api/communication-log")

_db_path = None


def init_communication_log_routes(db_path=None):
    global _db_path
    _db_path = db_path


@comms_bp.route("", methods=["POST"])
@token_required
def add_entry():
    data = get_json_body()
    require_fields(data, "student_id", "contact_type", "summary")
    svc = CommsService(_db_path)
    result = svc.add_entry(student_id=data["student_id"], contact_type=data["contact_type"], summary=data["summary"], staff_member=data.get("staff_member", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@comms_bp.route("", methods=["GET"])
@token_required
def list_entries():
    svc = CommsService(_db_path)
    result = svc.list_entries()
    return jsonify({"data": result})


@comms_bp.route("/<int:entry_id>/follow-up", methods=["PUT"])
@token_required
def mark_follow_up(entry_id):
    svc = CommsService(_db_path)
    result = svc.mark_follow_up_done(entry_id)
    return jsonify({"message": "Updated.", "data": result})


@comms_bp.route("/<int:entry_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_entry(entry_id):
    svc = CommsService(_db_path)
    result = svc.delete_entry(entry_id)
    return jsonify({"message": "Deleted.", "data": result})

