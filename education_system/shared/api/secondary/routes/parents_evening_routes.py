"""Parents Evening API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.communication.parents_evening.services.parents_evening_service import ParentsEveningService

parents_evening_bp = Blueprint("parents_evening", __name__, url_prefix="/api/parents-evening")

_db_path = None


def init_parents_evening_routes(db_path=None):
    global _db_path
    _db_path = db_path


@parents_evening_bp.route("", methods=["POST"])
@token_required
@role_required("admin")
def create_event():
    data = get_json_body()
    require_fields(data, "title", "event_date")
    svc = ParentsEveningService(_db_path)
    result = svc.create_event(title=data["title"], event_date=data["event_date"], slot_duration=data.get("slot_duration", 10))
    return jsonify({"message": "Created.", "data": result}), 201


@parents_evening_bp.route("", methods=["GET"])
@token_required
def list_events():
    svc = ParentsEveningService(_db_path)
    result = svc.list_events()
    return jsonify({"data": result})


@parents_evening_bp.route("/<int:event_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_event(event_id):
    svc = ParentsEveningService(_db_path)
    result = svc.delete_event(event_id)
    return jsonify({"message": "Deleted.", "data": result})


@parents_evening_bp.route("/<int:event_id>/slots", methods=["POST"])
@token_required
def book_slot(event_id):
    data = get_json_body()
    require_fields(data, "teacher_id", "parent_id", "time_slot")
    svc = ParentsEveningService(_db_path)
    result = svc.book_slot(event_id, data["teacher_id"], data["parent_id"], data["time_slot"])
    return jsonify({"message": "Created.", "data": result}), 201


@parents_evening_bp.route("/<int:event_id>/slots", methods=["GET"])
@token_required
def list_slots(event_id):
    svc = ParentsEveningService(_db_path)
    result = svc.list_slots(event_id)
    return jsonify({"data": result})


@parents_evening_bp.route("/slots/<int:slot_id>", methods=["DELETE"])
@token_required
def cancel_slot(slot_id):
    svc = ParentsEveningService(_db_path)
    result = svc.cancel_slot(slot_id)
    return jsonify({"message": "Deleted.", "data": result})

