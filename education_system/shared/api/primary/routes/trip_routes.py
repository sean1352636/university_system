"""Trips API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.pupil_life.trips.services.trip_service import TripService

trips_bp = Blueprint("trips", __name__, url_prefix="/api/trips")

_db_path = None


def init_trips_routes(db_path=None):
    global _db_path
    _db_path = db_path


@trips_bp.route("", methods=["GET"])
@token_required
def list_trips():
    svc = TripService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_trips()
    total = len(items)
    return jsonify(paginated_response(items, total))


@trips_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_trip(pk):
    svc = TripService(_db_path)
    item = svc.get_trip(pk)
    if not item:
        return jsonify({"error": "Trip not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@trips_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_trip():
    data = get_json_body()
    require_fields(data, "title", "destination", "date")
    svc = TripService(_db_path)
    result = svc.create_trip(**data)
    return jsonify({"message": "Trip created.", "data": result}), 201


@trips_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_trip(pk):
    data = get_json_body()
    svc = TripService(_db_path)
    result = svc.update_trip(pk, **data)
    return jsonify({"message": "Trip updated.", "data": result})

@trips_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_trip(pk):
    svc = TripService(_db_path)
    svc.delete_trip(pk)
    return jsonify({"message": "Trip deleted."})