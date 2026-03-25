"""Incidents API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.facilities.incidents.services.incident_service import IncidentService

incidents_bp = Blueprint("incidents", __name__, url_prefix="/api/incidents")

_db_path = None


def init_incidents_routes(db_path=None):
    global _db_path
    _db_path = db_path


@incidents_bp.route("", methods=["POST"])
@token_required
def log_incident():
    data = get_json_body()
    require_fields(data, "title", "description")
    svc = IncidentService(_db_path)
    result = svc.log_incident(title=data["title"], description=data["description"], location=data.get("location", ""), severity=data.get("severity", "low"), reported_by=data.get("reported_by", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@incidents_bp.route("", methods=["GET"])
@token_required
def list_incidents():
    svc = IncidentService(_db_path)
    result = svc.list_incidents()
    return jsonify({"data": result})


@incidents_bp.route("/<int:inc_id>/close", methods=["PUT"])
@token_required
@role_required("admin")
def close_incident(inc_id):
    svc = IncidentService(_db_path)
    result = svc.close_incident(inc_id)
    return jsonify({"message": "Updated.", "data": result})


@incidents_bp.route("/<int:inc_id>/follow-up", methods=["PUT"])
@token_required
@role_required("admin")
def mark_follow_up(inc_id):
    svc = IncidentService(_db_path)
    result = svc.mark_follow_up_done(inc_id)
    return jsonify({"message": "Updated.", "data": result})


@incidents_bp.route("/<int:inc_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_incident(inc_id):
    svc = IncidentService(_db_path)
    result = svc.delete_incident(inc_id)
    return jsonify({"message": "Deleted.", "data": result})

