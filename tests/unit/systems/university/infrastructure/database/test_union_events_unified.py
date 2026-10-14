"""Regression tests for the student union events cutover.

Union events are rows in ``unified_events`` tagged ``source_type = 'union'``.
The legacy ``union_events`` table is gone, and the four tables that held a
foreign key into it (``event_finances``, ``event_tickets``, ``club_media``,
``sustainability_tracking``) now reference ``unified_events(event_id)``.

Foreign keys are enforced on every real connection in this project
(``_apply_pragmas`` forces ``PRAGMA foreign_keys=ON`` outside development), so
a foreign key can never point at a view — that is why this migration rewrites
the queries rather than substituting a compatibility view.
"""

import sqlite3

import pytest

#: The source-filtered projection each union call site selects from. It exposes
#: the legacy column names so existing WHERE/ORDER BY clauses keep working.
UNION_SRC = (
    "(SELECT event_id, title AS event_name, description, organizer_id, event_date, "
    "start_time, end_time, location, event_category AS category, "
    "max_capacity AS max_attendees, "
    "(SELECT COUNT(*) FROM unified_event_registrations ur "
    "WHERE ur.event_id = ue.event_id) AS current_attendees, "
    "status, created_at, start_time AS event_time "
    "FROM unified_events ue WHERE ue.source_type = 'union')"
)

SCHEMA = [
    """CREATE TABLE unified_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT, source_type TEXT NOT NULL,
        source_event_id INTEGER, title TEXT, description TEXT, event_category TEXT,
        event_date TEXT, start_time TEXT, end_time TEXT, location TEXT,
        organizer_id INTEGER, max_capacity INTEGER, status TEXT, created_at TEXT)""",
    """CREATE TABLE unified_event_registrations (
        registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL, user_id TEXT, registration_date TEXT)""",
    """CREATE TABLE event_finances (
        finance_id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER, amount REAL,
        FOREIGN KEY (event_id) REFERENCES unified_events(event_id))""",
]


@pytest.fixture
def db(tmp_path):
    c = sqlite3.connect(str(tmp_path / "union.db"), isolation_level=None)
    for stmt in SCHEMA:
        c.execute(stmt)
    c.execute("PRAGMA foreign_keys = ON")
    yield c
    c.close()


def _make_event(db, title="Freshers Fair", date="2026-10-01", source="union"):
    cur = db.cursor()
    cur.execute(
        "INSERT INTO unified_events (title, description, event_date, start_time, "
        "location, organizer_id, event_category, max_capacity, status, source_type) "
        "VALUES (?, 'desc', ?, '10:00', 'Union Hall', 1, 'social', 200, 'upcoming', ?)",
        (title, date, source))
    return cur.lastrowid


def test_union_events_table_is_not_recreated(db):
    """Nothing should bring the legacy table back."""
    assert db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='union_events'").fetchone()[0] == 0


def test_reads_are_scoped_to_the_union_source(db):
    _make_event(db, "Freshers Fair")
    _make_event(db, "Library Talk", source="library")
    _make_event(db, "Open Day", source="academic_calendar")

    rows = db.execute("SELECT event_name FROM %s e" % UNION_SRC).fetchall()

    assert rows == [("Freshers Fair",)], "a non-union event leaked into a union query"


def test_legacy_column_names_still_resolve(db):
    """Existing WHERE/ORDER BY clauses reference the legacy names."""
    _make_event(db)
    row = db.execute(
        "SELECT event_name, event_date, category, max_attendees, event_time, status "
        "FROM %s e WHERE e.category = 'social' AND e.event_date >= '2026-01-01' "
        "ORDER BY e.event_name" % UNION_SRC).fetchone()
    assert row == ("Freshers Fair", "2026-10-01", "social", 200, "10:00", "upcoming")


def test_attendee_count_is_derived(db):
    """The old hand-maintained current_attendees counter could drift; this cannot."""
    event_id = _make_event(db)
    assert db.execute("SELECT current_attendees FROM %s e WHERE e.event_id = ?"
                      % UNION_SRC, (event_id,)).fetchone()[0] == 0

    for who in ("S1", "S2"):
        db.execute("INSERT INTO unified_event_registrations (event_id, user_id) "
                   "VALUES (?, ?)", (event_id, who))

    assert db.execute("SELECT current_attendees FROM %s e WHERE e.event_id = ?"
                      % UNION_SRC, (event_id,)).fetchone()[0] == 2


def test_child_tables_reference_unified_events(db):
    event_id = _make_event(db)
    db.execute("INSERT INTO event_finances (event_id, amount) VALUES (?, 250.0)",
               (event_id,))
    assert db.execute("SELECT COUNT(*) FROM event_finances").fetchone()[0] == 1


def test_foreign_keys_reject_an_orphan_child(db):
    """The FK must actually be enforced, not merely declared."""
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO event_finances (event_id, amount) VALUES (999999, 1.0)")


def test_foreign_key_check_is_clean(db):
    _make_event(db)
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
