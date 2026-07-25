"""Generic room booking package — clash-aware bookings against the shared `room_bookings` table."""
from education_system.systems.university.domain.operations.campus.room_booking.services.room_booking_service import (
    RoomBookingService,
    RoomBookingError,
)

__all__ = ["RoomBookingService", "RoomBookingError"]
