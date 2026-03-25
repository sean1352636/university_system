"""Room Booking API routes."""

from flask import Blueprint, jsonify, request

from education_system.shared.api.secondary.auth import token_required, role_required
from education_system.shared.api.secondary.validators import get_json_body, require_fields
from education_system.secondary_school.modules.domain.facilities.room_booking.services.room_booking_service import RoomBookingService

room_booking_bp = Blueprint("room_booking", __name__, url_prefix="/api/room-booking")

_db_path = None


def init_room_booking_routes(db_path=None):
    global _db_path
    _db_path = db_path


@room_booking_bp.route("", methods=["POST"])
@token_required
def book_room():
    data = get_json_body()
    require_fields(data, "room_name", "date", "period")
    svc = RoomBookingService(_db_path)
    result = svc.book_room(room_name=data["room_name"], date=data["date"], period=data["period"], booked_by=data.get("booked_by", ""), purpose=data.get("purpose", ""))
    return jsonify({"message": "Created.", "data": result}), 201


@room_booking_bp.route("", methods=["GET"])
@token_required
def list_bookings():
    svc = RoomBookingService(_db_path)
    result = svc.list_bookings()
    return jsonify({"data": result})


@room_booking_bp.route("/<int:booking_id>", methods=["DELETE"])
@token_required
def cancel_booking(booking_id):
    svc = RoomBookingService(_db_path)
    result = svc.cancel_booking(booking_id)
    return jsonify({"message": "Deleted.", "data": result})


@room_booking_bp.route("/rooms", methods=["GET"])
@token_required
def get_rooms():
    svc = RoomBookingService(_db_path)
    result = svc.get_rooms()
    return jsonify({"data": result})

