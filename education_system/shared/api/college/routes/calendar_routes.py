"""API routes for calendar."""

from flask import Blueprint, jsonify, request, g

from education_system.shared.api.college.auth import token_required, role_required
from education_system.shared.api.college.validators import get_json_body, require_fields
from education_system.shared.api.college.pagination import get_pagination_params, paginated_response
from education_system.college_system.modules.domain.calendar.services.calendar_service import CalendarService
from education_system.college_system.core.i18n import t

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
    items = svc.list_events(limit=limit, offset=offset)
    return jsonify(paginated_response(items, len(items)))
@calendar_bp.route("", methods=["POST"])
@token_required
@role_required('admin', 'staff')
def create_event():
    data = get_json_body()
    svc = CalendarService(_db_path)
    result = svc.create_event(**data)
    return jsonify({"message": t("api.calendar.created"), "data": result}), 201
@calendar_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required('admin', 'staff')
def update_event(pk):
    data = get_json_body()
    svc = CalendarService(_db_path)
    result = svc.update_event(pk, **data)
    return jsonify({"message": t("api.calendar.updated"), "data": result})
@calendar_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required('admin')
def delete_event(pk):
    svc = CalendarService(_db_path)
    svc.delete_event(pk)
    return jsonify({"message": t("api.calendar.deleted")})
