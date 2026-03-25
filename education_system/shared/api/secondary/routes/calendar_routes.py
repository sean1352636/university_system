"""Calendar API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.communication.calendar.services.calendar_service import CalendarService

calendar_bp = Blueprint("calendar", __name__, url_prefix="/api/calendar")

_db_path = None


def init_calendar_routes(db_path=None):
    global _db_path
    _db_path = db_path


@calendar_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def add_event():
    data = get_json_body()
    require_fields(data, "title", "event_date")
    svc = CalendarService(_db_path)
    result = svc.add_event(title=data["title"], event_date=data["event_date"], event_type=data.get("event_type", "general"), description=data.get("description", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@calendar_bp.route("", methods=["GET"])
@token_required
def list_events():
    svc = CalendarService(_db_path)
    result = svc.list_events()
    return jsonify({"data": result})


@calendar_bp.route("/<int:event_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_event(event_id):
    svc = CalendarService(_db_path)
    result = svc.delete_event(event_id)
    return jsonify({"message": "Deleted.", "data": result})

