"""Incidents API routes."""

from flask import Blueprint, jsonify, request

from education_system.primary_school.api.auth import token_required, role_required
from education_system.primary_school.api.validators import get_json_body, require_fields
from education_system.primary_school.api.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.facilities.incidents.services.incident_service import IncidentService

incidents_bp = Blueprint("incidents", __name__, url_prefix="/api/incidents")

_db_path = None


def init_incidents_routes(db_path=None):
    global _db_path
    _db_path = db_path


@incidents_bp.route("", methods=["GET"])
@token_required
def list_incidents():
    svc = IncidentService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_incidents()
    total = len(items)
    return jsonify(paginated_response(items, total))


@incidents_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_incident(pk):
    svc = IncidentService(_db_path)
    item = svc.get_incident(pk)
    if not item:
        return jsonify({"error": "Incident not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@incidents_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_incident():
    data = get_json_body()
    require_fields(data, "title", "description", "date")
    svc = IncidentService(_db_path)
    result = svc.create_incident(**data)
    return jsonify({"message": "Incident created.", "data": result}), 201


@incidents_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_incident(pk):
    data = get_json_body()
    svc = IncidentService(_db_path)
    result = svc.update_incident(pk, **data)
    return jsonify({"message": "Incident updated.", "data": result})

@incidents_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_incident(pk):
    svc = IncidentService(_db_path)
    svc.delete_incident(pk)
    return jsonify({"message": "Incident deleted."})