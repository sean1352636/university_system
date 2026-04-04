"""Tests for RoomBookingService."""
import pytest


class TestRoomBooking:
    def test_book_room(self, room_booking_service):
        booking = room_booking_service.book_room(
            room="Hall A", date="2026-04-01",
            start_time="09:00", end_time="10:00",
            purpose="Staff meeting", booked_by="admin",
        )
        assert booking["room"] == "Hall A"
        assert booking["purpose"] == "Staff meeting"

    def test_list_bookings(self, room_booking_service):
        room_booking_service.book_room("Room 1", "2026-04-01", "09:00", "10:00", "Meeting")
        room_booking_service.book_room("Room 2", "2026-04-01", "09:00", "10:00", "Workshop")
        bookings = room_booking_service.list_bookings()
        assert len(bookings) >= 2

    def test_list_bookings_filters_by_room(self, room_booking_service):
        room_booking_service.book_room("Lab A", "2026-04-01", "09:00", "10:00", "Science")
        room_booking_service.book_room("Lab B", "2026-04-01", "09:00", "10:00", "Chemistry")
        bookings = room_booking_service.list_bookings(room="Lab A")
        assert all(b["room"] == "Lab A" for b in bookings)

    def test_list_bookings_filters_by_date(self, room_booking_service):
        room_booking_service.book_room("Room 1", "2026-04-01", "09:00", "10:00", "Day 1")
        room_booking_service.book_room("Room 1", "2026-04-02", "09:00", "10:00", "Day 2")
        bookings = room_booking_service.list_bookings(date="2026-04-01")
        assert all(b["date"] == "2026-04-01" for b in bookings)

    def test_cancel_booking(self, room_booking_service):
        booking = room_booking_service.book_room("Room 1", "2026-04-05", "09:00", "10:00", "Cancel me")
        room_booking_service.cancel_booking(booking["id"])
        bookings = room_booking_service.list_bookings()
        cancelled = [b for b in bookings if b["id"] == booking["id"]][0]
        assert cancelled["status"] == "cancelled"

    def test_delete_booking(self, room_booking_service):
        booking = room_booking_service.book_room("Room 1", "2026-04-06", "09:00", "10:00", "Delete me")
        room_booking_service.delete_booking(booking["id"])
        bookings = room_booking_service.list_bookings()
        assert all(b["id"] != booking["id"] for b in bookings)
