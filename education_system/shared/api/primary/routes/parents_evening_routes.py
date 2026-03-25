"""Parents Evening API routes."""

from flask import Blueprint, jsonify

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.primary_school.modules.domain.communication.parents_evening.services.parents_evening_service import ParentsEveningService

parents_evening_bp = Blueprint("parents_evening", __name__, url_prefix="/api/parents-evening")

_db_path = None


def init_parents_evening_routes(db_path=None):
    global _db_path
    _db_path = db_path


@parents_evening_bp.route("/events", methods=["GET"])
@token_required
def list_events():
    svc = ParentsEveningService(_db_path)
    items = svc.list_events()
    return jsonify({"data": items})


@parents_evening_bp.route("/events", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_event():
    data = get_json_body()
    require_fields(data, "title", "date")
    svc = ParentsEveningService(_db_path)
    result = svc.create_event(**data)
    return jsonify({"message": "Event created.", "data": result}), 201


@parents_evening_bp.route("/slots/<int:event_id>", methods=["GET"])
@token_required
def list_slots(event_id):
    svc = ParentsEveningService(_db_path)
    items = svc.list_slots(event_id)
    return jsonify({"data": items})


@parents_evening_bp.route("/slots", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_slot():
    data = get_json_body()
    require_fields(data, "event_id", "teacher_id", "time_slot")
    svc = ParentsEveningService(_db_path)
    result = svc.create_slot(**data)
    return jsonify({"message": "Slot created.", "data": result}), 201
