"""Trips are written through to the academic calendar automatically.

The two manual menu entries ("Create Calendar Event for Trip", "View Trip
Events in Calendar") were removed in favour of this write-through, so the
sync helpers carry the whole integration.
"""

from __future__ import annotations

import sqlite3

import pytest

from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management.calendar_integration import (  # noqa: E501
    TRIP_EVENT_TYPE,
    remove_trip_calendar_event,
    sync_trip_calendar_event,
)


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE academic_calendar_events (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            date TEXT,
            date_start TEXT,
            date_end TEXT,
            description TEXT,
            event_type TEXT DEFAULT 'Academic',
            date_added TEXT NOT NULL,
            last_modified TEXT,
            created_by TEXT,
            trip_id INTEGER
        )
        """
    )
    yield connection
    connection.close()


def _event(conn, trip_id):
    return conn.execute(
        "SELECT id, name, date_start, date_end, event_type "
        "FROM academic_calendar_events WHERE trip_id = ?",
        (trip_id,),
    ).fetchall()


@pytest.mark.unit
def test_sync_creates_event_for_new_trip(conn):
    event_id = sync_trip_calendar_event(
        conn, 7,
        trip_name="Museum Day", destination="Science Museum",
        start_date="2026-09-10", end_date="2026-09-10", cost=12.5,
        created_by="admin",
    )

    rows = _event(conn, 7)
    assert len(rows) == 1
    assert rows[0][0] == event_id
    assert "Museum Day" in rows[0][1]
    assert rows[0][2] == "2026-09-10"
    assert rows[0][3] == "2026-09-10"
    assert rows[0][4] == TRIP_EVENT_TYPE


@pytest.mark.unit
def test_sync_updates_in_place_rather_than_duplicating(conn):
    first = sync_trip_calendar_event(
        conn, 7,
        trip_name="Field Week", destination="Snowdonia",
        start_date="2026-10-01", end_date="2026-10-05", cost=250.0,
    )
    second = sync_trip_calendar_event(
        conn, 7,
        trip_name="Field Fortnight", destination="Snowdonia",
        start_date="2026-10-02", end_date="2026-10-12", cost=250.0,
    )

    assert first == second
    rows = _event(conn, 7)
    assert len(rows) == 1
    assert "Field Fortnight" in rows[0][1]
    assert (rows[0][2], rows[0][3]) == ("2026-10-02", "2026-10-12")


@pytest.mark.unit
def test_remove_drops_the_event(conn):
    sync_trip_calendar_event(
        conn, 7,
        trip_name="Museum Day", destination="Science Museum",
        start_date="2026-09-10", end_date="2026-09-10",
    )

    assert remove_trip_calendar_event(conn, 7) == 1
    assert _event(conn, 7) == []
    assert remove_trip_calendar_event(conn, 7) == 0


@pytest.mark.unit
def test_sync_survives_a_missing_calendar_table():
    connection = sqlite3.connect(":memory:")
    try:
        assert sync_trip_calendar_event(
            connection, 7,
            trip_name="Museum Day", destination="Science Museum",
            start_date="2026-09-10", end_date="2026-09-10",
        ) is None
    finally:
        connection.close()
