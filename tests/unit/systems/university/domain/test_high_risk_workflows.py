from datetime import datetime, timedelta

import pytest

from education_system.systems.university.domain.pastoral.health.appointments.models import Appointment
from education_system.systems.university.domain.pastoral.health.appointments.service import validate_appointment
from education_system.systems.university.domain.pastoral.health.appointments.policies import appointment_is_in_future
from education_system.systems.university.domain.operations.campus.room_booking.services.room_booking_service import (
    RoomBookingService,
    RoomBookingError,
    _parse_dt,
)
from education_system.systems.university.domains.governance.domain.legal.risk_management.risk_service import Risk


def test_pastoral_appointment_requires_consent_ready_future_slot():
    now = datetime(2026, 8, 4, 12, 0)
    assert appointment_is_in_future(now + timedelta(days=1), now=now)
    with pytest.raises(ValueError, match="future"):
        validate_appointment(Appointment(1, "counselling", now))
    with pytest.raises(ValueError, match="required"):
        validate_appointment(Appointment(1, "   ", now + timedelta(days=1)))


def test_operations_booking_datetime_validation_rejects_invalid_interval():
    assert _parse_dt("2026-09-01 09:00:00", "start") == "2026-09-01 09:00"
    with pytest.raises(RoomBookingError, match="Invalid"):
        _parse_dt("tomorrow", "start")


def test_operations_booking_rejects_overlapping_reservation(tmp_path):
    db = tmp_path / "rooms.db"
    import sqlite3
    with sqlite3.connect(db) as conn:
        conn.executescript("""
            CREATE TABLE rooms (room_id INTEGER PRIMARY KEY, equipment TEXT);
            CREATE TABLE room_bookings (
                booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER, booked_by TEXT, booking_type TEXT, purpose TEXT,
                start_datetime TEXT, end_datetime TEXT, equipment_needed TEXT,
                booking_status TEXT
            );
            INSERT INTO rooms(room_id, equipment) VALUES (1, 'projector');
        """)
    service = RoomBookingService(str(db))
    service.create_booking(1, "2026-09-01 09:00", "2026-09-01 10:00", "staff", "lecture")
    with pytest.raises(RoomBookingError, match="clash"):
        service.create_booking(1, "2026-09-01 09:30", "2026-09-01 10:30", "staff", "meeting")


def test_governance_risk_score_and_rating_boundaries():
    risk = Risk(None, "Outage", "Operational", "IT Services", "", 5, 4, "Open", "owner", "", "", "")
    assert risk.score == 20
    assert risk.rating == "Critical"
    risk.likelihood = 1
    risk.impact = 1
    assert risk.rating == "Low"
