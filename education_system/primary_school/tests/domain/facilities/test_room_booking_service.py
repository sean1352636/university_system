"""Tests for the RoomBookingService in the Primary School system."""

import pytest

from education_system.primary_school.core.exceptions import RoomBookingError


class TestCreateBooking:
    """Tests for creating room bookings."""

    def test_create_booking_returns_dict_with_id(self, room_booking_service):
        """Creating a booking returns a dict with a valid ID."""
        result = room_booking_service.create_booking(
            room_name="Hall",
            booked_by="STF0001",
            booking_date="2026-04-10",
            start_time="09:00",
            end_time="10:00",
            purpose="Assembly",
        )
        assert isinstance(result, dict)
        assert result["id"] > 0
        assert result["room_name"] == "Hall"

    def test_create_booking_persists(self, room_booking_service):
        """A created booking is retrievable via get_booking."""
        result = room_booking_service.create_booking(
            room_name="Music Room",
            booked_by="STF0002",
            booking_date="2026-04-11",
            start_time="13:00",
            end_time="14:00",
            purpose="Choir practice",
            recurring=1,
        )
        fetched = room_booking_service.get_booking(result["id"])
        assert fetched is not None
        assert fetched["room_name"] == "Music Room"
        assert fetched["purpose"] == "Choir practice"
        assert fetched["recurring"] == 1
        assert fetched["status"] == "Confirmed"

    def test_create_overlapping_booking_raises(self, room_booking_service):
        """Creating an overlapping booking for the same room raises an error."""
        room_booking_service.create_booking(
            room_name="Hall",
            booked_by="STF0001",
            booking_date="2026-04-12",
            start_time="09:00",
            end_time="10:00",
        )
        with pytest.raises(RoomBookingError):
            room_booking_service.create_booking(
                room_name="Hall",
                booked_by="STF0002",
                booking_date="2026-04-12",
                start_time="09:30",
                end_time="10:30",
            )


class TestGetBooking:
    """Tests for retrieving a single booking."""

    def test_get_nonexistent_booking_returns_none(self, room_booking_service):
        """Requesting a non-existent booking ID returns None."""
        assert room_booking_service.get_booking(99999) is None


class TestListBookings:
    """Tests for listing and filtering bookings."""

    def test_list_bookings_empty_db(self, room_booking_service):
        """Listing bookings on an empty database returns an empty list."""
        assert room_booking_service.list_bookings() == []

    def test_list_bookings_filter_by_room(self, room_booking_service):
        """Filtering by room_name returns only that room's bookings."""
        room_booking_service.create_booking(
            room_name="Hall", booked_by="STF0001",
            booking_date="2026-04-14", start_time="09:00", end_time="10:00",
        )
        room_booking_service.create_booking(
            room_name="Library", booked_by="STF0002",
            booking_date="2026-04-14", start_time="09:00", end_time="10:00",
        )
        hall = room_booking_service.list_bookings(room_name="Hall")
        assert len(hall) == 1
        assert hall[0]["room_name"] == "Hall"

    def test_list_bookings_filter_by_date(self, room_booking_service):
        """Filtering by booking_date returns only bookings on that date."""
        room_booking_service.create_booking(
            room_name="Hall", booked_by="STF0001",
            booking_date="2026-04-15", start_time="09:00", end_time="10:00",
        )
        room_booking_service.create_booking(
            room_name="Hall", booked_by="STF0001",
            booking_date="2026-04-16", start_time="09:00", end_time="10:00",
        )
        day = room_booking_service.list_bookings(booking_date="2026-04-15")
        assert len(day) == 1


class TestUpdateBooking:
    """Tests for updating bookings."""

    def test_update_booking_changes_fields(self, room_booking_service):
        """Updating a booking persists the new values."""
        result = room_booking_service.create_booking(
            room_name="Hall", booked_by="STF0001",
            booking_date="2026-04-17", start_time="09:00", end_time="10:00",
            purpose="Meeting",
        )
        updated = room_booking_service.update_booking(
            result["id"], purpose="Staff briefing",
        )
        assert updated["purpose"] == "Staff briefing"

    def test_update_booking_no_valid_fields_returns_none(self, room_booking_service):
        """Passing only unrecognised fields returns None."""
        result = room_booking_service.create_booking(
            room_name="Hall", booked_by="STF0001",
            booking_date="2026-04-18", start_time="11:00", end_time="12:00",
        )
        assert room_booking_service.update_booking(result["id"], bogus="x") is None


class TestDeleteBooking:
    """Tests for deleting bookings."""

    def test_delete_existing_booking(self, room_booking_service):
        """Deleting an existing booking returns True and removes it."""
        result = room_booking_service.create_booking(
            room_name="Art Room", booked_by="STF0001",
            booking_date="2026-04-19", start_time="09:00", end_time="10:00",
        )
        assert room_booking_service.delete_booking(result["id"]) is True
        assert room_booking_service.get_booking(result["id"]) is None

    def test_delete_nonexistent_booking(self, room_booking_service):
        """Deleting a non-existent booking returns False."""
        assert room_booking_service.delete_booking(99999) is False


class TestCheckAvailability:
    """Tests for checking room availability."""

    def test_available_when_no_bookings(self, room_booking_service):
        """A room with no bookings is reported as available."""
        assert room_booking_service.check_availability(
            "Hall", "2026-05-01", "09:00", "10:00",
        ) is True

    def test_unavailable_when_overlap_exists(self, room_booking_service):
        """A room is unavailable when an overlapping booking exists."""
        room_booking_service.create_booking(
            room_name="Hall", booked_by="STF0001",
            booking_date="2026-05-02", start_time="09:00", end_time="10:00",
        )
        assert room_booking_service.check_availability(
            "Hall", "2026-05-02", "09:30", "10:30",
        ) is False

    def test_available_for_adjacent_slot(self, room_booking_service):
        """A room is available for a time slot immediately after an existing booking."""
        room_booking_service.create_booking(
            room_name="Hall", booked_by="STF0001",
            booking_date="2026-05-03", start_time="09:00", end_time="10:00",
        )
        assert room_booking_service.check_availability(
            "Hall", "2026-05-03", "10:00", "11:00",
        ) is True
