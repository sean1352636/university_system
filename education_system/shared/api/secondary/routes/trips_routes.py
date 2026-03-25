"""Trips API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.student_life.trips.services.trips_service import TripsService

trips_bp = Blueprint("trips", __name__, url_prefix="/api/trips")

_db_path = None


def init_trips_routes(db_path=None):
    global _db_path
    _db_path = db_path


@trips_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_trip():
    data = get_json_body()
    require_fields(data, "title", "destination", "date")
    svc = TripsService(_db_path)
    result = svc.create_trip(title=data["title"], destination=data["destination"], date=data["date"], lead_staff=data.get("lead_staff", ""), cost=data.get("cost", 0))
    return jsonify({"message": "Created.", "data": result}), 201


@trips_bp.route("", methods=["GET"])
@token_required
def list_trips():
    svc = TripsService(_db_path)
    result = svc.list_trips()
    return jsonify({"data": result})


@trips_bp.route("/<int:trip_id>/status", methods=["PUT"])
@token_required
@role_required("admin")
def update_status(trip_id):
    data = get_json_body()
    require_fields(data, "status")
    svc = TripsService(_db_path)
    result = svc.update_status(trip_id, data["status"])
    return jsonify({"message": "Updated.", "data": result})


@trips_bp.route("/<int:trip_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_trip(trip_id):
    svc = TripsService(_db_path)
    result = svc.delete_trip(trip_id)
    return jsonify({"message": "Deleted.", "data": result})


@trips_bp.route("/<int:trip_id>/students", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def add_student(trip_id):
    data = get_json_body()
    require_fields(data, "student_id")
    svc = TripsService(_db_path)
    result = svc.add_student(trip_id, data["student_id"])
    return jsonify({"message": "Created.", "data": result}), 201


@trips_bp.route("/<int:trip_id>/students", methods=["GET"])
@token_required
def list_trip_students(trip_id):
    svc = TripsService(_db_path)
    result = svc.list_trip_students(trip_id)
    return jsonify({"data": result})


@trips_bp.route("/<int:trip_id>/students/<int:student_id>", methods=["DELETE"])
@token_required
@role_required("admin")
def remove_student(trip_id, student_id):
    svc = TripsService(_db_path)
    result = svc.remove_student(trip_id, student_id)
    return jsonify({"message": "Deleted.", "data": result})

