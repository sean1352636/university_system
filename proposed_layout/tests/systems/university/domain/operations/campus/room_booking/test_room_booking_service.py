"""Tests for the generic room-booking service.

``RoomBookingService`` operates on the shared ``rooms`` / ``room_bookings``
tables but adds **no DDL** of its own. It accepts an explicit ``db_path`` in its
constructor, so each test gets a fully isolated SQLite file (built by the
``room_booking_db`` fixture) rather than monkeypatching a module-level
``DEFAULT_DB_PATH``. The schema mirrors the relevant columns from
``infrastructure/database/schemas/facilities_housing_schemas.py``.

Datetimes are ISO ``YYYY-MM-DD HH:MM`` strings, which are lexically comparable
and so used directly for clash detection.
"""

from __future__ import annotations

import sqlite3

import pytest

from education_system.systems.university.domain.operations.campus.room_booking.services.room_booking_service import (  # noqa: E501
    RoomBookingError,
    RoomBookingService,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
def _build_schema(db_path: str) -> None:
    """Create the minimal rooms/room_bookings tables the service depends on."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE rooms (
                room_id INTEGER PRIMARY KEY AUTOINCREMENT,
                building_id INTEGER NOT NULL,
                room_number TEXT NOT NULL,
                room_name TEXT,
                room_type TEXT,
                capacity INTEGER,
                equipment TEXT,
                status TEXT DEFAULT 'available'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE room_bookings (
                booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                booked_by TEXT NOT NULL,
                booking_type TEXT NOT NULL,
                purpose TEXT,
                start_datetime TEXT NOT NULL,
                end_datetime TEXT NOT NULL,
                equipment_needed TEXT,
                booking_status TEXT DEFAULT 'confirmed',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _seed_room(
    db_path: str,
    *,
    capacity: int = 10,
    equipment: str = "",
    status: str = "available",
) -> int:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO rooms (building_id, room_number, room_name, room_type, "
            "capacity, equipment, status) VALUES (1, '101', 'Room 101', 'study', ?, ?, ?)",
            (capacity, equipment, status),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


@pytest.fixture
def room_booking_db(tmp_path):
    db_path = str(tmp_path / "room_booking_test.db")
    _build_schema(db_path)
    return db_path


@pytest.fixture
def service(room_booking_db):
    return RoomBookingService(db_path=room_booking_db)


# ---------------------------------------------------------------------------
# create_booking
# ---------------------------------------------------------------------------
class TestCreateBooking:
    def test_create_booking_returns_id_and_persists_row(self, service, room_booking_db):
        room_id = _seed_room(room_booking_db)
        bid = service.create_booking(
            room_id=room_id,
            start_datetime="2026-06-01 10:00",
            end_datetime="2026-06-01 11:00",
            booked_by="S12345",
            purpose="Group study",
        )
        assert isinstance(bid, int) and bid > 0

        rows = service.list_bookings(room_id=room_id)
        assert len(rows) == 1
        row = rows[0]
        assert row["booked_by"] == "S12345"
        assert row["purpose"] == "Group study"
        assert row["booking_status"] == "confirmed"
        # Datetime normalised to the minute-precision format.
        assert row["start_datetime"] == "2026-06-01 10:00"
        assert row["end_datetime"] == "2026-06-01 11:00"

    def test_create_booking_normalises_seconds_precision_input(self, service, room_booking_db):
        room_id = _seed_room(room_booking_db)
        bid = service.create_booking(
            room_id=room_id,
            start_datetime="2026-06-01 10:00:30",
            end_datetime="2026-06-01 11:00:45",
            booked_by="S1",
            purpose="x",
        )
        row = service.list_bookings(room_id=room_id)[0]
        assert row["booking_id"] == bid
        assert row["start_datetime"] == "2026-06-01 10:00"
        assert row["end_datetime"] == "2026-06-01 11:00"

    def test_create_booking_trims_booked_by_and_defaults_equipment(self, service, room_booking_db):
        room_id = _seed_room(room_booking_db)
        service.create_booking(
            room_id=room_id,
            start_datetime="2026-06-01 10:00",
            end_datetime="2026-06-01 11:00",
            booked_by="  staff01  ",
            purpose="meeting",
        )
        row = service.list_bookings(room_id=room_id)[0]
        assert row["booked_by"] == "staff01"
        assert row["equipment_needed"] == ""


class TestCreateBookingValidation:
    def test_invalid_room_id_raises(self, service):
        with pytest.raises(RoomBookingError, match="room_id must be a positive integer"):
            service.create_booking(
                room_id=0,
                start_datetime="2026-06-01 10:00",
                end_datetime="2026-06-01 11:00",
                booked_by="S1",
                purpose="x",
            )

    def test_missing_booked_by_raises(self, service, room_booking_db):
        room_id = _seed_room(room_booking_db)
        with pytest.raises(RoomBookingError, match="booked_by is required"):
            service.create_booking(
                room_id=room_id,
                start_datetime="2026-06-01 10:00",
                end_datetime="2026-06-01 11:00",
                booked_by="   ",
                purpose="x",
            )

    def test_end_before_start_raises(self, service, room_booking_db):
        room_id = _seed_room(room_booking_db)
        with pytest.raises(RoomBookingError, match="end_datetime must be after start_datetime"):
            service.create_booking(
                room_id=room_id,
                start_datetime="2026-06-01 11:00",
                end_datetime="2026-06-01 10:00",
                booked_by="S1",
                purpose="x",
            )

    def test_malformed_datetime_raises(self, service, room_booking_db):
        room_id = _seed_room(room_booking_db)
        with pytest.raises(RoomBookingError, match="Invalid start_datetime"):
            service.create_booking(
                room_id=room_id,
                start_datetime="not-a-date",
                end_datetime="2026-06-01 11:00",
                booked_by="S1",
                purpose="x",
            )


# ---------------------------------------------------------------------------
# Clash detection
# ---------------------------------------------------------------------------
class TestClashDetection:
    def _book(self, service, room_id, start, end):
        return service.create_booking(
            room_id=room_id, start_datetime=start, end_datetime=end,
            booked_by="S1", purpose="x",
        )

    def test_overlapping_booking_raises_clash(self, service, room_booking_db):
        room_id = _seed_room(room_booking_db)
        first = self._book(service, room_id, "2026-06-01 10:00", "2026-06-01 12:00")
        with pytest.raises(RoomBookingError, match=f"clash with booking #{first}"):
            self._book(service, room_id, "2026-06-01 11:00", "2026-06-01 13:00")

    def test_adjacent_bookings_do_not_clash(self, service, room_booking_db):
        room_id = _seed_room(room_booking_db)
        self._book(service, room_id, "2026-06-01 10:00", "2026-06-01 11:00")
        # Starts exactly when the previous ends — boundary touch, no overlap.
        second = self._book(service, room_id, "2026-06-01 11:00", "2026-06-01 12:00")
        assert second > 0
        assert len(service.list_bookings(room_id=room_id)) == 2

    def test_same_slot_different_room_does_not_clash(self, service, room_booking_db):
        room_a = _seed_room(room_booking_db)
        room_b = _seed_room(room_booking_db)
        self._book(service, room_a, "2026-06-01 10:00", "2026-06-01 11:00")
        # Identical time window but a different room — allowed.
        second = self._book(service, room_b, "2026-06-01 10:00", "2026-06-01 11:00")
        assert second > 0

    def test_cancelled_booking_frees_the_slot(self, service, room_booking_db):
        room_id = _seed_room(room_booking_db)
        first = self._book(service, room_id, "2026-06-01 10:00", "2026-06-01 12:00")
        assert service.cancel_booking(first) is True
        # The previously-clashing slot is now bookable.
        second = self._book(service, room_id, "2026-06-01 11:00", "2026-06-01 13:00")
        assert second > 0


# ---------------------------------------------------------------------------
# cancel / reschedule
# ---------------------------------------------------------------------------
class TestCancelAndReschedule:
    def test_cancel_marks_status_and_returns_true(self, service, room_booking_db):
        room_id = _seed_room(room_booking_db)
        bid = service.create_booking(
            room_id=room_id, start_datetime="2026-06-01 10:00",
            end_datetime="2026-06-01 11:00", booked_by="S1", purpose="x",
        )
        assert service.cancel_booking(bid) is True
        row = service.list_bookings(room_id=room_id)[0]
        assert row["booking_status"] == "cancelled"

    def test_cancel_twice_returns_false_second_time(self, service, room_booking_db):
        room_id = _seed_room(room_booking_db)
        bid = service.create_booking(
            room_id=room_id, start_datetime="2026-06-01 10:00",
            end_datetime="2026-06-01 11:00", booked_by="S1", purpose="x",
        )
        assert service.cancel_booking(bid) is True
        # Already cancelled -> no row updated.
        assert service.cancel_booking(bid) is False

    def test_reschedule_updates_times(self, service, room_booking_db):
        room_id = _seed_room(room_booking_db)
        bid = service.create_booking(
            room_id=room_id, start_datetime="2026-06-01 10:00",
            end_datetime="2026-06-01 11:00", booked_by="S1", purpose="x",
        )
        service.reschedule_booking(bid, "2026-06-01 14:00", "2026-06-01 15:00")
        row = service.list_bookings(room_id=room_id)[0]
        assert row["start_datetime"] == "2026-06-01 14:00"
        assert row["end_datetime"] == "2026-06-01 15:00"

    def test_reschedule_missing_booking_raises(self, service):
        with pytest.raises(RoomBookingError, match="not found"):
            service.reschedule_booking(99999, "2026-06-01 14:00", "2026-06-01 15:00")

    def test_reschedule_into_clash_raises(self, service, room_booking_db):
        room_id = _seed_room(room_booking_db)
        a = service.create_booking(
            room_id=room_id, start_datetime="2026-06-01 10:00",
            end_datetime="2026-06-01 11:00", booked_by="S1", purpose="x",
        )
        service.create_booking(
            room_id=room_id, start_datetime="2026-06-01 12:00",
            end_datetime="2026-06-01 13:00", booked_by="S2", purpose="y",
        )
        # Move booking 'a' on top of the 12:00-13:00 slot -> clash.
        with pytest.raises(RoomBookingError, match="clash"):
            service.reschedule_booking(a, "2026-06-01 12:30", "2026-06-01 12:45")
        # Original times preserved after the failed reschedule.
        row = next(r for r in service.list_bookings(room_id=room_id) if r["booking_id"] == a)
        assert row["start_datetime"] == "2026-06-01 10:00"

    def test_reschedule_cancelled_booking_raises(self, service, room_booking_db):
        room_id = _seed_room(room_booking_db)
        bid = service.create_booking(
            room_id=room_id, start_datetime="2026-06-01 10:00",
            end_datetime="2026-06-01 11:00", booked_by="S1", purpose="x",
        )
        service.cancel_booking(bid)
        with pytest.raises(RoomBookingError, match="cancelled"):
            service.reschedule_booking(bid, "2026-06-01 14:00", "2026-06-01 15:00")


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
class TestQueries:
    def test_list_bookings_filters_by_date(self, service, room_booking_db):
        room_id = _seed_room(room_booking_db)
        service.create_booking(
            room_id=room_id, start_datetime="2026-06-01 10:00",
            end_datetime="2026-06-01 11:00", booked_by="S1", purpose="day1",
        )
        service.create_booking(
            room_id=room_id, start_datetime="2026-06-02 10:00",
            end_datetime="2026-06-02 11:00", booked_by="S2", purpose="day2",
        )
        on_day1 = service.list_bookings(on_date="2026-06-01")
        purposes = {r["purpose"] for r in on_day1}
        assert purposes == {"day1"}

    def test_list_bookings_invalid_date_raises(self, service):
        with pytest.raises(RoomBookingError, match="on_date must be YYYY-MM-DD"):
            service.list_bookings(on_date="01/06/2026")

    def test_find_available_rooms_excludes_booked_and_respects_capacity(
        self, service, room_booking_db
    ):
        small = _seed_room(room_booking_db, capacity=4)
        large_free = _seed_room(room_booking_db, capacity=20)
        large_booked = _seed_room(room_booking_db, capacity=20)
        service.create_booking(
            room_id=large_booked, start_datetime="2026-06-01 10:00",
            end_datetime="2026-06-01 12:00", booked_by="S1", purpose="x",
        )
        available = service.find_available_rooms(
            "2026-06-01 10:30", "2026-06-01 11:30", capacity_min=10,
        )
        ids = {r["room_id"] for r in available}
        # Free + big enough -> in. Booked (clash) and too-small -> out.
        assert large_free in ids
        assert large_booked not in ids
        assert small not in ids

    def test_find_available_rooms_filters_by_equipment(self, service, room_booking_db):
        projector_room = _seed_room(room_booking_db, equipment="projector, whiteboard")
        plain_room = _seed_room(room_booking_db, equipment="whiteboard")
        available = service.find_available_rooms(
            "2026-06-01 10:00", "2026-06-01 11:00", equipment_csv="projector",
        )
        ids = {r["room_id"] for r in available}
        assert projector_room in ids
        assert plain_room not in ids
