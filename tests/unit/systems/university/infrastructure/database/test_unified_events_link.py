"""Tests for unified_events provenance and the library migration pilot.

``unified_events`` was built as a consolidation target — it carries
``source_type`` and ``source_event_id`` — but ``source_event_id`` was never
written, so nothing recorded *which* source row a unified row came from. That
is the fact a phased migration needs: without it a backfill cannot be re-run
safely, because there is no way to tell what has already been copied.
"""

import sqlite3

import pytest

from education_system.systems.university.infrastructure.database.schemas.unified_events_link import (
    SOURCE_LIBRARY,
    ensure_source_link,
    link_source_event,
    registered_count,
)

UNIFIED_EVENTS = """
CREATE TABLE unified_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_event_id INTEGER,
    title TEXT NOT NULL,
    description TEXT,
    start_datetime TEXT,
    location TEXT,
    max_capacity INTEGER,
    status TEXT,
    created_by TEXT,
    created_at TEXT,
    event_type TEXT
)
"""

UNIFIED_REGISTRATIONS = """
CREATE TABLE unified_event_registrations (
    registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    user_id TEXT,
    registered_at TEXT,
    registration_date TEXT,
    status TEXT
)
"""


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(str(tmp_path / "unified.db"))
    c.execute(UNIFIED_EVENTS)
    c.execute(UNIFIED_REGISTRATIONS)
    ensure_source_link(c)
    yield c
    c.close()


def test_provenance_index_exists(conn):
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'idx_unified_events_source'"
    ).fetchone()
    assert sql is not None
    assert "UNIQUE" in sql[0]
    assert "source_event_id IS NOT NULL" in sql[0]


def test_attendee_name_is_added_to_registrations(conn):
    """A library walk-in has a name and no user account; it must survive."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(unified_event_registrations)")}
    assert "attendee_name" in cols


def test_linking_the_same_source_row_twice_updates_rather_than_duplicates(conn):
    first = link_source_event(conn, SOURCE_LIBRARY, 1, {"title": "Poetry Night"})
    second = link_source_event(conn, SOURCE_LIBRARY, 1, {"title": "Poetry Night (moved)"})

    assert first == second
    rows = conn.execute(
        "SELECT title FROM unified_events WHERE source_type = ? AND source_event_id = 1",
        (SOURCE_LIBRARY,),
    ).fetchall()
    assert rows == [("Poetry Night (moved)",)]


def test_the_index_rejects_a_duplicate_written_directly(conn):
    link_source_event(conn, SOURCE_LIBRARY, 7, {"title": "Book Fair"})
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO unified_events (source_type, source_event_id, title) "
            "VALUES (?, 7, 'Duplicate')",
            (SOURCE_LIBRARY,),
        )


def test_native_events_do_not_collide(conn):
    """Rows with no source row leave source_event_id NULL — many may coexist."""
    for name in ("One", "Two", "Three"):
        conn.execute(
            "INSERT INTO unified_events (source_type, title) VALUES (?, ?)",
            (SOURCE_LIBRARY, name),
        )
    assert conn.execute(
        "SELECT COUNT(*) FROM unified_events WHERE source_event_id IS NULL"
    ).fetchone()[0] == 3


def test_different_sources_may_share_a_source_id(conn):
    """library #1 and campus #1 are different events."""
    a = link_source_event(conn, SOURCE_LIBRARY, 1, {"title": "Library one"})
    b = link_source_event(conn, "campus", 1, {"title": "Campus one"})
    assert a != b


def test_registered_count_is_derived(conn):
    """The per-source tables carried a denormalised count that could drift."""
    event_id = link_source_event(conn, SOURCE_LIBRARY, 1, {"title": "Poetry Night"})
    assert registered_count(conn, event_id) == 0

    for who in ("S12345", "WALKIN1"):
        conn.execute(
            "INSERT INTO unified_event_registrations (event_id, user_id) VALUES (?, ?)",
            (event_id, who),
        )
    assert registered_count(conn, event_id) == 2


def test_link_requires_a_source_event_id(conn):
    with pytest.raises(ValueError):
        link_source_event(conn, SOURCE_LIBRARY, None, {"title": "No provenance"})
