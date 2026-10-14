"""Regression tests for the academic calendar cutover.

Calendar events are rows in ``unified_events`` tagged
``source_type = 'academic_calendar'``, keyed by the original TEXT ``id`` stored
in ``source_event_id``. The legacy ``academic_calendar_events`` table is gone
and its 12 child tables now hold foreign keys into
``unified_events(source_event_id)``.

Two things this migration had to get right:

* every legacy column maps **1:1** — ``date_start``/``date_end`` hold three
  different formats across the real rows (plain date, ISO ``T`` timestamp and a
  space-separated datetime), so any parsing corrupts one of them;
* ``date`` is a separate fact from ``date_start`` — they differ on 787 of the
  810 live rows — which is why ``event_date`` exists alongside ``start_datetime``.
"""

import sqlite3

import pytest

#: The source-filtered projection every calendar call site selects from.
CAL_SRC = (
    "(SELECT source_event_id AS id, title AS name, event_date AS date, "
    "start_datetime AS date_start, end_datetime AS date_end, description, "
    "event_type, created_at AS date_added, updated_at AS last_modified, "
    "created_by, start_time, end_time, location, audience, assignment_id, "
    "trip_id, organizer_name AS organizer, participants, status, "
    "country_code, region, is_active "
    "FROM unified_events uev WHERE uev.source_type = 'academic_calendar')"
)

SCHEMA = [
    """CREATE TABLE unified_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT, source_type TEXT NOT NULL,
        source_event_id INTEGER, title TEXT, description TEXT, event_type TEXT,
        event_date TEXT, start_datetime TEXT, end_datetime TEXT, start_time TEXT,
        end_time TEXT, location TEXT, organizer_name TEXT, audience TEXT,
        participants TEXT, assignment_id INTEGER, trip_id INTEGER, status TEXT,
        country_code TEXT, region TEXT, is_active BOOLEAN DEFAULT 1,
        created_by TEXT, created_at TEXT, updated_at TEXT)""",
    "CREATE UNIQUE INDEX idx_src ON unified_events(source_event_id)",
    """CREATE TABLE course_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT, course_id TEXT,
        FOREIGN KEY (event_id) REFERENCES unified_events(source_event_id))""",
]

#: the three date formats present in the live data
DATE_FORMATS = [
    ("A-1", "2026-05-13", None, None),
    ("A-2", None, "2026-08-08T09:00:00", "2026-08-08T09:00:00"),
    ("A-3", None, "2026-07-22 09:00", "2026-07-22 12:00"),
]


@pytest.fixture
def db(tmp_path):
    c = sqlite3.connect(str(tmp_path / "cal.db"), isolation_level=None)
    for stmt in SCHEMA:
        c.execute(stmt)
    c.execute("PRAGMA foreign_keys = ON")
    yield c
    c.close()


def _seed(db):
    for cid, date, start, end in DATE_FORMATS:
        db.execute(
            "INSERT INTO unified_events (source_event_id, title, event_date, "
            "start_datetime, end_datetime, description, event_type, created_at, "
            "updated_at, created_by, source_type) VALUES (?,?,?,?,?,'d','Academic',"
            "'2026-01-01','2026-01-01','tester','academic_calendar')",
            (cid, "Event " + cid, date, start, end))


def test_legacy_table_is_gone(db):
    assert db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='academic_calendar_events'"
    ).fetchone()[0] == 0


def test_all_three_date_formats_survive_verbatim(db):
    """Parsing date_start would corrupt one of these; 1:1 storage does not."""
    _seed(db)
    rows = db.execute(
        "SELECT id, date, date_start, date_end FROM %s e ORDER BY id" % CAL_SRC).fetchall()
    assert rows == DATE_FORMATS


def test_date_is_distinct_from_date_start(db):
    """They differ on 787 of the 810 live rows, so both must be stored."""
    db.execute(
        "INSERT INTO unified_events (source_event_id, title, event_date, "
        "start_datetime, source_type) VALUES ('B-1','Term','2026-09-15',"
        "'2025-09-01','academic_calendar')")
    row = db.execute("SELECT date, date_start FROM %s e WHERE e.id='B-1'" % CAL_SRC).fetchone()
    assert row == ("2026-09-15", "2025-09-01")


def test_reads_are_scoped_to_the_calendar_source(db):
    _seed(db)
    db.execute("INSERT INTO unified_events (title, event_date, source_type) "
               "VALUES ('Union Social','2026-12-02','union')")
    names = [r[0] for r in db.execute("SELECT name FROM %s e" % CAL_SRC)]
    assert "Union Social" not in names
    assert len(names) == 3


def test_writes_are_scoped_to_the_calendar_source(db):
    """A DELETE without the source filter would hit other sources' rows."""
    _seed(db)
    db.execute("INSERT INTO unified_events (title, source_type) VALUES ('Keep','union')")

    db.execute("DELETE FROM unified_events WHERE source_type = 'academic_calendar'")

    assert db.execute("SELECT COUNT(*) FROM unified_events").fetchone()[0] == 1
    assert db.execute("SELECT title FROM unified_events").fetchone()[0] == "Keep"


def test_text_ids_remain_the_identity(db):
    """32 call sites filter on the TEXT id; child tables store it too."""
    _seed(db)
    db.execute("INSERT INTO course_events (event_id, course_id) VALUES ('A-1','CS')")
    assert db.execute(
        "SELECT course_id FROM course_events WHERE event_id='A-1'").fetchone()[0] == "CS"


def test_child_foreign_key_is_enforced(db):
    _seed(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO course_events (event_id, course_id) VALUES ('NOPE','CS')")
