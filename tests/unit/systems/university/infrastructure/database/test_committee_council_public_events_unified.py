"""Regression tests for folding public_events, sc_events and committee_meetings
into ``unified_events``.

Community public events, student council events and committee meetings are now
rows in ``unified_events`` tagged ``community`` / ``student_council`` /
``committee``. Call sites read through source-filtered projections that keep the
legacy column names. ``committee_agenda_items`` and ``committee_votes`` reference
``unified_events(event_id)`` — foreign keys are enforced, so never a view.
"""

import importlib.util
import sqlite3
from pathlib import Path

import pytest

from education_system.systems.university.infrastructure.database.schemas.unified_events_link import (
    COMMITTEE_MEETINGS_SRC,
    PUBLIC_EVENTS_SRC,
    SC_EVENTS_SRC,
)

_SCRIPT = (Path(__file__).resolve().parents[6]
           / "tools" / "university" / "migrate_committee_council_events.py")


def _load_script():
    spec = importlib.util.spec_from_file_location("migrate_ccpe", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCHEMA = [
    """CREATE TABLE unified_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT, source_type TEXT NOT NULL,
        source_event_id INTEGER, title TEXT NOT NULL, description TEXT,
        event_type TEXT, event_category TEXT, start_datetime TEXT, end_datetime TEXT,
        location TEXT, organizer_id TEXT, organizer_name TEXT, max_capacity INTEGER,
        status TEXT DEFAULT 'scheduled', virtual_link TEXT, created_by TEXT,
        created_at TEXT, updated_at TEXT, notes TEXT, event_date TEXT,
        start_time TEXT, end_time TEXT)""",
    # The live database has this non-partial index as well as the partial one.
    "CREATE UNIQUE INDEX idx_unified_events_source_id ON unified_events(source_event_id)",
    """CREATE TABLE unified_event_registrations (
        registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL REFERENCES unified_events(event_id), user_id TEXT)""",
    """CREATE TABLE committees (committee_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL)""",
    """CREATE TABLE public_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT, event_name TEXT, organizer_id TEXT,
        event_date TEXT, location TEXT, description TEXT,
        expected_attendance INTEGER DEFAULT 0, status TEXT DEFAULT 'planned',
        created_at TEXT)""",
    """CREATE TABLE sc_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, event_date TEXT,
        event_time TEXT, venue TEXT, organiser TEXT, description TEXT,
        calendar_event_id TEXT, created_at TEXT)""",
    """CREATE TABLE committee_meetings (
        meeting_id INTEGER PRIMARY KEY AUTOINCREMENT, committee_id INTEGER NOT NULL,
        title TEXT NOT NULL, meeting_date TEXT NOT NULL, start_time TEXT NOT NULL,
        end_time TEXT, location TEXT, virtual_link TEXT, status TEXT DEFAULT 'scheduled',
        chair_id TEXT, secretary_id TEXT, recurrence TEXT DEFAULT 'none', notes TEXT,
        created_by TEXT, created_at TEXT, updated_at TEXT,
        FOREIGN KEY (committee_id) REFERENCES committees(committee_id))""",
    "CREATE INDEX idx_committee_meetings_date ON committee_meetings(meeting_date)",
    """CREATE TABLE committee_agenda_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT, meeting_id INTEGER NOT NULL,
        item_order INTEGER NOT NULL DEFAULT 1, title TEXT NOT NULL,
        FOREIGN KEY (meeting_id) REFERENCES committee_meetings(meeting_id))""",
    "CREATE INDEX idx_meeting_agenda_meeting ON committee_agenda_items(meeting_id)",
    """CREATE TABLE committee_votes (
        vote_id INTEGER PRIMARY KEY AUTOINCREMENT, meeting_id INTEGER NOT NULL,
        committee_id INTEGER NOT NULL, title TEXT NOT NULL,
        FOREIGN KEY (meeting_id) REFERENCES committee_meetings(meeting_id),
        FOREIGN KEY (committee_id) REFERENCES committees(committee_id))""",
]


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "records.db"
    c = sqlite3.connect(str(path))
    for stmt in SCHEMA:
        c.execute(stmt)
    c.execute("INSERT INTO unified_events (source_type, source_event_id, title) "
              "VALUES ('academic_calendar', 'abc-uuid', 'Open Day')")
    c.execute("INSERT INTO public_events (event_name, organizer_id, event_date, "
              "location, description, expected_attendance, status, created_at) "
              "VALUES ('Beach clean', 'user:admin', '2026-09-08', 'Pier', 'd', 50, "
              "'planned', '2026-08-17 08:19:28')")
    c.execute("INSERT INTO sc_events (name, event_date, event_time, venue, organiser, "
              "calendar_event_id) VALUES ('Town hall', '2026-10-01', '18:00', "
              "'Hall', 'Pres', 'cal-9')")
    c.execute("INSERT INTO committees (name) VALUES ('Senate')")
    # meeting_id 1 on purpose: the same bare id as the other two tables' rows.
    c.execute("INSERT INTO committee_meetings (committee_id, title, meeting_date, "
              "start_time, chair_id) VALUES (1, 'Autumn Senate', '2026-10-05', "
              "'10:00', 'staff1')")
    c.execute("INSERT INTO committee_agenda_items (meeting_id, title) VALUES (1, 'Minutes')")
    c.execute("INSERT INTO committee_votes (meeting_id, committee_id, title) "
              "VALUES (1, 1, 'Approve')")
    c.commit()
    c.close()
    return path


def _connect(path):
    c = sqlite3.connect(str(path))
    c.execute("PRAGMA foreign_keys = ON")
    return c


def _tables(c):
    return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_dry_run_changes_nothing(db_path):
    _load_script().migrate(db_path, apply=False, backup=False)
    c = _connect(db_path)
    assert {"public_events", "sc_events", "committee_meetings"} <= _tables(c)
    assert c.execute("SELECT COUNT(*) FROM unified_events").fetchone()[0] == 1


def test_apply_moves_rows_and_drops_legacy_tables(db_path):
    _load_script().migrate(db_path, apply=True, backup=False)
    c = _connect(db_path)
    assert not {"public_events", "sc_events", "committee_meetings"} & _tables(c)
    assert c.execute(
        "SELECT source_type, source_event_id FROM unified_events "
        "WHERE source_type != 'academic_calendar' ORDER BY source_type").fetchall() == [
        ("committee", "committee_meetings:1"),
        ("community", "public_events:1"),
        ("student_council", "sc_events:1"),
    ]


def test_legacy_column_names_resolve_through_projections(db_path):
    _load_script().migrate(db_path, apply=True, backup=False)
    c = _connect(db_path)
    assert c.execute(
        "SELECT event_name, organizer_id, event_date, location, expected_attendance, "
        "status FROM %s e WHERE e.organizer_id = 'user:admin'" % PUBLIC_EVENTS_SRC
    ).fetchall() == [("Beach clean", "user:admin", "2026-09-08", "Pier", 50, "planned")]
    assert c.execute(
        "SELECT name, event_date, event_time, venue, organiser FROM %s e "
        "ORDER BY event_date DESC" % SC_EVENTS_SRC
    ).fetchall() == [("Town hall", "2026-10-01", "18:00", "Hall", "Pres")]
    row = c.execute(
        "SELECT id, meeting_id, committee_id, title, meeting_date, start_time, chair_id "
        "FROM %s m WHERE m.committee_id = 1" % COMMITTEE_MEETINGS_SRC).fetchone()
    assert row[0] == row[1]
    assert row[2:] == (1, "Autumn Senate", "2026-10-05", "10:00", "staff1")


def test_projections_are_scoped_to_their_source(db_path):
    _load_script().migrate(db_path, apply=True, backup=False)
    c = _connect(db_path)
    for src in (PUBLIC_EVENTS_SRC, SC_EVENTS_SRC, COMMITTEE_MEETINGS_SRC):
        assert c.execute("SELECT COUNT(*) FROM %s x" % src).fetchone()[0] == 1


def test_child_tables_follow_the_meeting_to_unified_events(db_path):
    _load_script().migrate(db_path, apply=True, backup=False)
    c = _connect(db_path)
    new_id = c.execute("SELECT event_id FROM unified_events "
                       "WHERE source_type = 'committee'").fetchone()[0]
    for table in ("committee_agenda_items", "committee_votes"):
        fks = {(r[2], r[3], r[4]) for r in c.execute(f"PRAGMA foreign_key_list({table})")}
        assert ("unified_events", "meeting_id", "event_id") in fks
        assert c.execute(f"SELECT meeting_id FROM {table}").fetchall() == [(new_id,)]
    assert c.execute("SELECT name FROM sqlite_master WHERE type='index' "
                     "AND name='idx_meeting_agenda_meeting'").fetchone()
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []


def test_foreign_key_rejects_an_orphan_agenda_item(db_path):
    _load_script().migrate(db_path, apply=True, backup=False)
    c = _connect(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO committee_agenda_items (meeting_id, title) "
                  "VALUES (999999, 'Orphan')")


def test_rerun_is_a_no_op(db_path):
    script = _load_script()
    script.migrate(db_path, apply=True, backup=False)
    script.migrate(db_path, apply=True, backup=False)
    c = _connect(db_path)
    assert c.execute("SELECT COUNT(*) FROM unified_events").fetchone()[0] == 4


def test_an_orphaned_child_row_rolls_the_whole_run_back(db_path):
    c = sqlite3.connect(str(db_path))
    c.execute("INSERT INTO committee_votes (meeting_id, committee_id, title) "
              "VALUES (42, 1, 'Dangling')")
    c.commit()
    c.close()
    with pytest.raises(RuntimeError):
        _load_script().migrate(db_path, apply=True, backup=False)
    c = _connect(db_path)
    assert {"public_events", "sc_events", "committee_meetings"} <= _tables(c)
    assert c.execute("SELECT COUNT(*) FROM unified_events").fetchone()[0] == 1
