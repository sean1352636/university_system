"""Office hours routes: scheduling, booking, and management."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

office_hours_bp = Blueprint("office_hours", __name__, url_prefix="/api/office-hours")

# Initialize the service at module level
from education_system.post_18.university_system.modules.domain.academics.services.office_hours.office_hours_service import (
    OfficeHoursService,
)

_service = OfficeHoursService()


# ---- Office Hours CRUD ----


@office_hours_bp.route("", methods=["GET"])
@token_required
def list_office_hours():
    """List all active office hours, optionally filtered by instructor_id or department."""
    instructor_id = request.args.get("instructor_id")
    department = request.args.get("department")

    try:
        items = _service.get_available_office_hours(
            instructor_id=instructor_id,
            department=department,
        )
        log_activity("view", "office_hours", user=g.current_user.get("sub"))
        return jsonify({"items": items, "total": len(items)})
    except Exception as e:
        logger.error(f"Error listing office hours: {e}")
        return jsonify({"error": "Internal server error"}), 500


@office_hours_bp.route("/<int:id>", methods=["GET"])
@token_required
def get_office_hour(id: int):
    """Get a specific office hour by ID."""
    try:
        item = _service.get_office_hours(id)
        if not item:
            return jsonify({"error": f"Office hours {id} not found"}), 404

        log_activity("view", "office_hour", user=g.current_user.get("sub"))
        return jsonify(item)
    except Exception as e:
        logger.error(f"Error retrieving office hours {id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@office_hours_bp.route("", methods=["POST"])
@token_required
def create_office_hours():
    """Create a new office hours slot."""
    data = request.get_json(silent=True) or {}

    required_fields = ["instructor_id", "day_of_week", "start_time", "end_time", "location"]
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    try:
        office_hour_id = _service.create_office_hours(
            instructor_id=data["instructor_id"],
            day_of_week=data["day_of_week"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            location=data["location"],
            capacity=data.get("capacity", 5),
            notes=data.get("notes", ""),
        )

        item = _service.get_office_hours(office_hour_id)
        log_activity("create", "office_hours", user=g.current_user.get("sub"))
        return jsonify(item), 201
    except ValueError as e:
        logger.warning("Invalid office hours creation request: %s", e)
        return jsonify({"error": "Invalid request parameters"}), 400
    except Exception as e:
        logger.error("Error creating office hours: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@office_hours_bp.route("/<int:id>", methods=["PUT"])
@token_required
def update_office_hours(id: int):
    """Update an existing office hours slot."""
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "No fields provided for update"}), 400

    try:
        updated = _service.update_office_hours(id, **data)
        if not updated:
            return jsonify({"error": f"Office hours {id} not found or inactive"}), 404

        item = _service.get_office_hours(id)
        log_activity("update", "office_hours", user=g.current_user.get("sub"))
        return jsonify(item)
    except ValueError as e:
        logger.warning("Invalid office hours update for %s: %s", id, e)
        return jsonify({"error": "Invalid request parameters"}), 400
    except Exception as e:
        logger.error("Error updating office hours %s: %s", id, e)
        return jsonify({"error": "Internal server error"}), 500


@office_hours_bp.route("/<int:id>", methods=["DELETE"])
@token_required
def delete_office_hours(id: int):
    """Soft-delete an office hours slot."""
    try:
        deleted = _service.delete_office_hours(id)
        if not deleted:
            return jsonify({"error": f"Office hours {id} not found or already inactive"}), 404

        log_activity("delete", "office_hours", user=g.current_user.get("sub"))
        return jsonify({"message": f"Office hours {id} deleted successfully"})
    except Exception as e:
        logger.error(f"Error deleting office hours {id}: {e}")
        return jsonify({"error": "Internal server error"}), 500


# ---- Bookings ----


@office_hours_bp.route("/bookings", methods=["GET"])
@token_required
def get_my_bookings():
    """Get bookings for the current user based on their role.

    Instructors see bookings for their office hours; students see their own bookings.
    """
    try:
        user = g.current_user
        role = user.get("role", "")
        user_sub = user.get("sub", "")

        if role == "instructor":
            bookings = _service.get_instructor_bookings(user_sub)
        else:
            bookings = _service.get_student_bookings(user_sub)

        log_activity("view", "office_hour_bookings", user=user_sub)
        return jsonify({"items": bookings, "total": len(bookings)})
    except Exception as e:
        logger.error(f"Error retrieving bookings: {e}")
        return jsonify({"error": "Internal server error"}), 500


@office_hours_bp.route("/<int:id>/book", methods=["POST"])
@token_required
def book_office_hour(id: int):
    """Book an office hour slot for the current user."""
    data = request.get_json(silent=True) or {}

    if not data.get("booking_date"):
        return jsonify({"error": "Missing required field: booking_date"}), 400

    try:
        student_id = g.current_user.get("sub", "")
        booking_id = _service.book_office_hour(
            office_hour_id=id,
            student_id=student_id,
            booking_date=data["booking_date"],
            notes=data.get("notes", ""),
        )

        log_activity("create", "office_hour_booking", user=student_id)
        return jsonify({
            "message": "Office hour booked successfully",
            "booking_id": booking_id,
            "office_hour_id": id,
            "booking_date": data["booking_date"],
        }), 201
    except ValueError as e:
        logger.warning("Invalid booking request for office hour %s: %s", id, e)
        return jsonify({"error": "Invalid request parameters"}), 400
    except Exception as e:
        logger.error("Error booking office hour %s: %s", id, e)
        return jsonify({"error": "Internal server error"}), 500


@office_hours_bp.route("/bookings/<int:booking_id>", methods=["DELETE"])
@token_required
def cancel_booking(booking_id: int):
    """Cancel an existing booking for the current user."""
    try:
        student_id = g.current_user.get("sub", "")
        cancelled = _service.cancel_booking(booking_id, student_id)

        if not cancelled:
            return jsonify({
                "error": f"Booking {booking_id} not found or not owned by current user",
            }), 404

        log_activity("delete", "office_hour_booking", user=student_id)
        return jsonify({"message": f"Booking {booking_id} cancelled successfully"})
    except ValueError as e:
        logger.warning("Invalid cancellation request for booking %s: %s", booking_id, e)
        return jsonify({"error": "Invalid request parameters"}), 400
    except Exception as e:
        logger.error("Error cancelling booking %s: %s", booking_id, e)
        return jsonify({"error": "Internal server error"}), 500
