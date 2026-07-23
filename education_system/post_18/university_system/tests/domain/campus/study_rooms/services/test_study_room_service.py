"""Tests for the study-room booking service.

Relies on the autouse ``_isolate_db`` fixture (patches ``DEFAULT_DB_PATH``) so
``get_connection()`` uses a throw-away DB. ``init_db()`` creates the study-room
tables and seeds sample rooms.
"""

import pytest

from education_system.post_18.university_system.modules.domain.campus.study_rooms.services import (
    study_room_service as srs,
)


@pytest.fixture
def rooms_db(temp_db):
    srs.init_db()
    return temp_db


class TestRoomQueries:
    def test_init_seeds_sample_rooms(self, rooms_db):
        rooms = srs.get_available_rooms()
        assert len(rooms) == 8

    def test_filter_by_building(self, rooms_db):
        library = srs.get_available_rooms(building="Library")
        assert len(library) == 3
        assert all(r["building"] == "Library" for r in library)

    def test_filter_by_room_type(self, rooms_db):
        group = srs.get_available_rooms(room_type="group_study")
        assert len(group) == 3
        assert all(r["room_type"] == "group_study" for r in group)

    def test_all_sentinel_means_no_filter(self, rooms_db):
        assert len(srs.get_available_rooms(building="All", room_type="All")) == 8

    def test_get_room_list_shape(self, rooms_db):
        rl = srs.get_room_list()
        assert len(rl) == 8
        # Each row exposes id, number, building, capacity
        first = rl[0]
        assert first["room_number"]
        assert first["capacity"] >= 1


class TestBooking:
    def test_book_room_and_list(self, rooms_db):
        srs.book_room(1, "STU-SR1", "2026-05-01", "10:00", "12:00", purpose="study")
        bookings = srs.get_bookings("STU-SR1")
        assert len(bookings) == 1
        assert bookings[0]["room_number"]  # joined room number present
        assert bookings[0]["status"] == "confirmed"

    def test_book_room_conflict_raises(self, rooms_db):
        srs.book_room(2, "STU-SR2", "2026-05-02", "10:00", "12:00")
        with pytest.raises(ValueError, match="already booked"):
            srs.book_room(2, "STU-SR3", "2026-05-02", "11:00", "13:00")

    def test_non_overlapping_slot_allowed(self, rooms_db):
        srs.book_room(3, "STU-SR4", "2026-05-03", "10:00", "12:00")
        # Starts exactly when the other ends -> no overlap
        srs.book_room(3, "STU-SR5", "2026-05-03", "12:00", "14:00")
        assert len(srs.get_bookings("STU-SR5")) == 1

    def test_invalid_date_raises(self, rooms_db):
        with pytest.raises(ValueError, match="Invalid date"):
            srs.book_room(1, "STU-SR6", "01/05/2026", "10:00", "12:00")

    def test_end_before_start_raises(self, rooms_db):
        with pytest.raises(ValueError, match="after start time"):
            srs.book_room(1, "STU-SR7", "2026-05-04", "14:00", "12:00")

    def test_cancel_booking(self, rooms_db):
        srs.book_room(4, "STU-SR8", "2026-05-05", "09:00", "10:00")
        booking_id = srs.get_bookings("STU-SR8")[0]["booking_id"]
        assert srs.cancel_booking(booking_id) is True
        # Cancelling again is a no-op
        assert srs.cancel_booking(booking_id) is False
