"""Regression tests for the library events schema.

``library_events`` had three disagreeing definitions and
``library_event_attendance`` was declared only by the library CLI, lazily, on
the way into its events menu — so on the live database it had never been
created and every attendance and reporting query ran against a missing table.

Both tables now have a single definition in
:mod:`education_system.systems.university.infrastructure.database.schemas.library_events_table`.
"""

import sqlite3

import pytest

from education_system.systems.university.infrastructure.database.schemas.library_events_table import (
    DEFAULT_EVENT_STATUS,
    ensure_library_events_schema,
)


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(str(tmp_path / "library.db"))
    ensure_library_events_schema(c)
    yield c
    c.close()


def _add_event(conn, name="Poetry Night", date="2026-09-01"):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO library_events (event_name, event_date, event_time, location, "
        "description, max_capacity, registered_count, status, created_by, created_at) "
        "VALUES (?, ?, '18:00', 'Main Hall', 'desc', 30, 0, ?, 'tester', '2026-01-01')",
        (name, date, DEFAULT_EVENT_STATUS),
    )
    return cur.lastrowid


def test_both_tables_are_created(conn):
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'library_event%'")}
    assert names == {"library_events", "library_event_attendance"}


def test_ensure_is_idempotent(conn):
    event_id = _add_event(conn)
    ensure_library_events_schema(conn)
    ensure_library_events_schema(conn)
    assert conn.execute("SELECT COUNT(*) FROM library_events").fetchone()[0] == 1
    assert event_id


def test_status_column_is_backfilled_on_a_pre_existing_table(tmp_path):
    """The live table pre-dates ``status``; ensure() must add it, not assume it."""
    db = tmp_path / "old.db"
    c = sqlite3.connect(str(db))
    c.execute(
        "CREATE TABLE library_events ("
        " event_id INTEGER PRIMARY KEY AUTOINCREMENT, event_name TEXT NOT NULL,"
        " event_date TEXT NOT NULL, event_time TEXT NOT NULL, location TEXT,"
        " description TEXT, max_capacity INTEGER DEFAULT 50,"
        " registered_count INTEGER DEFAULT 0, created_by TEXT, created_at TEXT)"
    )
    assert "status" not in {r[1] for r in c.execute("PRAGMA table_info(library_events)")}

    ensure_library_events_schema(c)

    assert "status" in {r[1] for r in c.execute("PRAGMA table_info(library_events)")}
    c.close()


def test_attendance_and_report_queries_run(conn):
    """The queries that previously hit a non-existent table."""
    event_id = _add_event(conn)
    for who in ("S12345", "S99999"):
        conn.execute(
            "INSERT INTO library_event_attendance (event_id, attendee_id, "
            "attendee_name, registered_at) VALUES (?, ?, ?, '2026-01-01')",
            (event_id, who, who),
        )

    assert conn.execute("SELECT COUNT(*) FROM library_event_attendance").fetchone()[0] == 2
    rows = conn.execute(
        "SELECT e.event_name, COUNT(a.attendance_id) FROM library_events e "
        "LEFT JOIN library_event_attendance a ON e.event_id = a.event_id "
        "GROUP BY e.event_id"
    ).fetchall()
    assert rows == [("Poetry Night", 2)]


def test_gui_and_cli_agree_on_status(conn):
    """Events created by either screen must read back the same way."""
    cli_id = _add_event(conn, name="CLI event")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO library_events (event_name, event_date, event_time, location, "
        "description, max_capacity, registered_count, status, created_by, created_at) "
        "VALUES ('GUI event', '2026-09-05', '10:00', 'Atrium', 'desc', 50, 0, ?, "
        "'gui_user', '2026-01-01')",
        (DEFAULT_EVENT_STATUS,),
    )
    statuses = {r[0] for r in conn.execute(
        "SELECT status FROM library_events WHERE event_id IN (?, ?)", (cli_id, cur.lastrowid))}
    assert statuses == {DEFAULT_EVENT_STATUS}
