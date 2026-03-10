"""Destination API routes."""

from flask import Blueprint, jsonify, request

from education_system.college_system.api.auth import token_required, role_required
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.modules.domain.destinations.services.destination_service import DestinationService

destination_bp = Blueprint("destinations", __name__, url_prefix="/api/destinations")

_db_path = None


def init_destination_routes(db_path=None):
    global _db_path
    _db_path = db_path


@destination_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "staff")
def create_destination():
    data = get_json_body()
    require_fields(data, "student_id")
    svc = DestinationService(_db_path)
    dest = svc.create_destination(
        data["student_id"],
        academic_year=data.get("academic_year"),
        intended_destination=data.get("intended_destination"),
        destination_type=data.get("destination_type", "unknown"),
        institution_name=data.get("institution_name"),
        course_title=data.get("course_title"),
        notes=data.get("notes"),
    )
    return jsonify({"message": "Destination created.", "data": dest}), 201


@destination_bp.route("", methods=["GET"])
@token_required
def list_destinations():
    svc = DestinationService(_db_path)
    academic_year = request.args.get("academic_year")
    dtype = request.args.get("destination_type")
    dests = svc.list_destinations(academic_year=academic_year, destination_type=dtype)
    return jsonify({"data": dests, "count": len(dests)})


@destination_bp.route("/<int:dest_id>", methods=["GET"])
@token_required
def get_destination(dest_id):
    svc = DestinationService(_db_path)
    dest = svc.get_destination(dest_id)
    if not dest:
        return jsonify({"error": "Destination not found."}), 404
    return jsonify({"data": dest})


@destination_bp.route("/<int:dest_id>", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def update_destination(dest_id):
    data = get_json_body()
    svc = DestinationService(_db_path)
    dest = svc.update_destination(dest_id, **data)
    return jsonify({"message": "Destination updated.", "data": dest})


@destination_bp.route("/<int:dest_id>/confirm", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def confirm_destination(dest_id):
    data = get_json_body()
    require_fields(data, "confirmed_destination")
    svc = DestinationService(_db_path)
    dest = svc.confirm_destination(dest_id, data["confirmed_destination"],
                                    data.get("destination_type"))
    return jsonify({"message": "Destination confirmed.", "data": dest})


@destination_bp.route("/neet-risk", methods=["GET"])
@token_required
@role_required("admin", "staff")
def neet_risk():
    svc = DestinationService(_db_path)
    students = svc.get_neet_risk_students()
    return jsonify({"data": students, "count": len(students)})


@destination_bp.route("/stats", methods=["GET"])
@token_required
def destination_stats():
    svc = DestinationService(_db_path)
    stats = svc.get_destination_stats()
    return jsonify({"data": stats})


@destination_bp.route("/<int:dest_id>/contact", methods=["PUT"])
@token_required
@role_required("admin", "staff")
def record_contact(dest_id):
    svc = DestinationService(_db_path)
    dest = svc.record_contact(dest_id)
    return jsonify({"message": "Contact recorded.", "data": dest})


@destination_bp.route("/followups", methods=["GET"])
@token_required
@role_required("admin", "staff")
def pending_followups():
    svc = DestinationService(_db_path)
    followups = svc.get_pending_followups()
    return jsonify({"data": followups, "count": len(followups)})
