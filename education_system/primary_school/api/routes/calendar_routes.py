"""Calendar API routes."""

from flask import Blueprint, jsonify, request

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.api.validators import get_json_body, require_fields
from education_system.primary_school.api.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.communication.calendar.services.calendar_service import CalendarService

calendar_bp = Blueprint("calendar", __name__, url_prefix="/api/calendar")

_db_path = None


def init_calendar_routes(db_path=None):
    global _db_path
    _db_path = db_path


@calendar_bp.route("", methods=["GET"])
@token_required
def list_events():
    svc = CalendarService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_events()
    total = len(items)
    return jsonify(paginated_response(items, total))


@calendar_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_event(pk):
    svc = CalendarService(_db_path)
    item = svc.get_event(pk)
    if not item:
        return jsonify({"error": "Event not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@calendar_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_event():
    data = get_json_body()
    require_fields(data, "title", "start_date")
    svc = CalendarService(_db_path)
    result = svc.create_event(**data)
    return jsonify({"message": "Event created.", "data": result}), 201


@calendar_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_event(pk):
    data = get_json_body()
    svc = CalendarService(_db_path)
    result = svc.update_event(pk, **data)
    return jsonify({"message": "Event updated.", "data": result})

@calendar_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_event(pk):
    svc = CalendarService(_db_path)
    svc.delete_event(pk)
    return jsonify({"message": "Event deleted."})