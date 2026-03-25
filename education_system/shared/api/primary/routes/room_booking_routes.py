"""Room Bookings API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.primary.auth import token_required, role_required
from education_system.shared.api.primary.validators import get_json_body, require_fields
from education_system.shared.api.primary.pagination import get_pagination_params, paginated_response
from education_system.primary_school.modules.domain.facilities.room_booking.services.room_booking_service import RoomBookingService

room_bookings_bp = Blueprint("room_bookings", __name__, url_prefix="/api/room-bookings")

_db_path = None


def init_room_bookings_routes(db_path=None):
    global _db_path
    _db_path = db_path


@room_bookings_bp.route("", methods=["GET"])
@token_required
def list_bookings():
    svc = RoomBookingService(_db_path)
    limit, offset = get_pagination_params()
    items = svc.list_bookings(date=request.args.get("date"))
    total = len(items)
    return jsonify(paginated_response(items, total))


@room_bookings_bp.route("/<int:pk>", methods=["GET"])
@token_required
def get_booking(pk):
    svc = RoomBookingService(_db_path)
    item = svc.get_booking(pk)
    if not item:
        return jsonify({"error": "Booking not found."}), 404
    return jsonify({"data": dict(item) if hasattr(item, "keys") else item})


@room_bookings_bp.route("", methods=["POST"])
@token_required
@role_required("admin", "teacher")
def create_booking():
    data = get_json_body()
    require_fields(data, "room_name", "date", "start_time", "end_time", "booked_by")
    svc = RoomBookingService(_db_path)
    result = svc.create_booking(**data)
    return jsonify({"message": "Booking created.", "data": result}), 201


@room_bookings_bp.route("/<int:pk>", methods=["PUT"])
@token_required
@role_required("admin", "teacher")
def update_booking(pk):
    data = get_json_body()
    svc = RoomBookingService(_db_path)
    result = svc.update_booking(pk, **data)
    return jsonify({"message": "Booking updated.", "data": result})

@room_bookings_bp.route("/<int:pk>", methods=["DELETE"])
@token_required
@role_required("admin")
def delete_booking(pk):
    svc = RoomBookingService(_db_path)
    svc.delete_booking(pk)
    return jsonify({"message": "Booking deleted."})