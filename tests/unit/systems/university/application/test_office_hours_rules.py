"""Office hours: dates, appointment slots, booking rules, waitlist, one-off
cancellations, meeting records, reminders, reporting and the directory
mirror. In-memory database built here."""

import sqlite3
from datetime import datetime

import pytest

from education_system.systems.university.application.teaching import office_hours as oh

SCHEMA = [
    """CREATE TABLE office_hours (id INTEGER PRIMARY KEY AUTOINCREMENT, instructor_id TEXT NOT NULL,
        day_of_week TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL,
        location TEXT NOT NULL, capacity INTEGER DEFAULT 5, notes TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT)""",
    """CREATE TABLE office_hour_bookings (id INTEGER PRIMARY KEY AUTOINCREMENT,
        office_hour_id INTEGER NOT NULL, student_id TEXT NOT NULL, booking_date TEXT NOT NULL,
        notes TEXT DEFAULT '', status TEXT DEFAULT 'confirmed', created_at TEXT, module_code TEXT)""",
    """CREATE TABLE staff_office_hours_directory (hours_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL, day_of_week TEXT NOT NULL, start_time TEXT NOT NULL,
        end_time TEXT NOT NULL, location TEXT, virtual_link TEXT, is_by_appointment INTEGER,
        semester TEXT, is_active INTEGER DEFAULT 1)""",
    "CREATE TABLE academic_terms (id INTEGER PRIMARY KEY, name TEXT, start_date TEXT, end_date TEXT)",
    "CREATE TABLE holidays (id INTEGER PRIMARY KEY, start_date TEXT, end_date TEXT)",
    "CREATE TABLE students (student_id TEXT PRIMARY KEY, email_address TEXT)",
    "CREATE TABLE student_modules (student_id TEXT, module_code TEXT, status TEXT)",
    "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, email TEXT, role TEXT, "
    "student_id TEXT)",
    """CREATE TABLE messages (id INTEGER PRIMARY KEY, sender_id INTEGER, recipient_id INTEGER,
        subject TEXT, message TEXT, content TEXT, is_read INTEGER, sent_at TEXT)""",
]
NOW = datetime(2026, 10, 16, 12, 0)          # a Friday


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    for ddl in SCHEMA:
        c.execute(ddl)
    c.execute("INSERT INTO academic_terms VALUES (1, 'Autumn', '2026-09-21', '2026-12-11')")
    c.execute("INSERT INTO holidays VALUES (1, '2026-11-03', '2026-11-03')")
    c.executemany("INSERT INTO students VALUES (?, ?)",
                  [("S1", "s1@uni.ac.uk"), ("S2", None), ("S3", None)])
    c.execute("INSERT INTO student_modules VALUES ('S1', 'CS101', 'Enrolled')")
    c.executemany("INSERT INTO users (id, username, email, role, student_id) VALUES (?, ?, ?, ?, ?)",
                  [(1, "admin", None, "admin", None), (2, "lee", "lee@uni.ac.uk", "staff", None),
                   (3, "S1", None, "student", "S1")])
    oh.ensure(c)
    yield c
    c.close()


def _slots_block(c, **extra):
    values = {"instructor_id": "lee", "day_of_week": "Tuesday", "start_time": "10:00",
              "end_time": "11:00", "location": "B12", "slot_minutes": 20}
    values.update(extra)
    return oh.save_block(c, values, actor="lee")


def test_dates_skip_holidays_and_out_of_term(conn):
    block = _slots_block(conn)
    assert oh.dates(conn, block, weeks=10, now=NOW) == [
        "2026-10-20", "2026-10-27", "2026-11-10", "2026-11-17", "2026-11-24", "2026-12-01",
        "2026-12-08"]


def test_block_validation(conn):
    with pytest.raises(ValueError, match="meeting link"):
        _slots_block(conn, mode="online")
    with pytest.raises(ValueError, match="fit in the block"):
        _slots_block(conn, slot_minutes=90)
    with pytest.raises(ValueError, match="capacity"):
        _slots_block(conn, slot_minutes="", capacity="")


def test_booking_checks_weekday_past_and_slot(conn):
    block = _slots_block(conn)
    with pytest.raises(ValueError, match="Wednesday"):
        oh.book(conn, block, "S1", "2026-10-21", slot_start="10:00", now=NOW)
    with pytest.raises(ValueError, match="passed"):
        oh.book(conn, block, "S1", "2026-10-13", slot_start="10:00", now=NOW)
    made = oh.book(conn, block, "S1", "2026-10-20", slot_start="10:20", module_code="CS101",
                   now=NOW)
    assert made["when"] == "Tuesday 20 October 10:20–10:40"
    with pytest.raises(ValueError, match="not a free"):
        oh.book(conn, block, "S2", "2026-10-20", slot_start="10:20", now=NOW)
    with pytest.raises(ValueError, match="not enrolled"):
        oh.book(conn, block, "S2", "2026-10-20", slot_start="10:00", module_code="CS101", now=NOW)


def test_weekly_limit_and_notice(conn):
    block = _slots_block(conn, max_per_student_week=1, min_notice_hours=48)
    with pytest.raises(ValueError, match="hour"):
        oh.book(conn, block, "S1", "2026-10-20", slot_start="10:00",
                now=datetime(2026, 10, 19, 12))
    oh.book(conn, block, "S1", "2026-10-20", slot_start="10:00", now=NOW)
    other = oh.save_block(conn, {"instructor_id": "lee", "day_of_week": "Thursday",
                                 "start_time": "10:00", "end_time": "11:00", "location": "B12",
                                 "capacity": 3, "max_per_student_week": 1}, actor="lee")
    with pytest.raises(ValueError, match="a week"):
        oh.book(conn, other, "S1", "2026-10-22", now=NOW)


def test_full_waitlist_and_promotion_on_cancel(conn):
    block = oh.save_block(conn, {"instructor_id": "lee", "day_of_week": "Tuesday",
                                 "start_time": "10:00", "end_time": "11:00", "location": "B12",
                                 "capacity": 1}, actor="lee")
    first = oh.book(conn, block, "S1", "2026-10-20", now=NOW)
    with pytest.raises(oh.FullError):
        oh.book(conn, block, "S2", "2026-10-20", now=NOW)
    assert oh.join_waitlist(conn, block, "S2", "2026-10-20") == 1
    with pytest.raises(ValueError, match="cancelled up to"):
        oh.cancel(conn, first["booking_id"], "S1", now=datetime(2026, 10, 20, 9, 0))
    oh.cancel(conn, first["booking_id"], "S1", now=NOW)
    assert conn.execute("SELECT student_id FROM office_hour_bookings WHERE status = "
                        "'confirmed'").fetchall() == [("S2",)]


def test_cancel_one_date_tells_students_and_closes_it(conn):
    block = _slots_block(conn)
    oh.book(conn, block, "S1", "2026-10-20", slot_start="10:00", now=NOW)
    result = oh.cancel_date(conn, block, "2026-10-20", "Ill", "lee")
    assert result["cancelled"] == 1
    assert ("s1@uni.ac.uk", ) == tuple(e[0] for e in result["emails"] if e[0].startswith("s1"))
    assert "2026-10-20" not in oh.dates(conn, block, now=NOW)
    with pytest.raises(ValueError, match="cancelled that day"):
        oh.book(conn, block, "S2", "2026-10-20", slot_start="10:20", now=NOW)


def test_reschedule_and_meeting_record(conn):
    block = _slots_block(conn)
    made = oh.book(conn, block, "S1", "2026-10-20", slot_start="10:00", now=NOW)
    moved = oh.reschedule(conn, made["booking_id"], "S1", "2026-10-27", slot_start="10:40",
                          now=NOW)
    with pytest.raises(ValueError, match="not happened"):
        oh.record_meeting(conn, moved["booking_id"], "attended", now=NOW)
    oh.record_meeting(conn, moved["booking_id"], "no_show", actor="lee",
                      now=datetime(2026, 10, 27, 12))
    (row,) = oh.report(conn, "2026-10-01", "2026-10-31")
    assert (row["booked"], row["no_show"], row["no_show_pct"]) == (1, 1, 100.0)


def test_reminders_once(conn):
    block = _slots_block(conn)
    oh.book(conn, block, "S1", "2026-10-20", slot_start="10:00", now=NOW)
    assert oh.send_reminders(conn, now=datetime(2026, 10, 19, 12))["sent"] == 1
    assert oh.send_reminders(conn, now=datetime(2026, 10, 19, 13))["sent"] == 0


def test_directory_mirrors_bookable_blocks(conn):
    block = _slots_block(conn)
    assert conn.execute("SELECT user_id, office_hour_id, is_by_appointment FROM "
                        "staff_office_hours_directory").fetchall() == [("lee", block, 1)]
    oh.retire_block(conn, block)
    assert conn.execute("SELECT COUNT(*) FROM staff_office_hours_directory").fetchone()[0] == 0
    conn.execute("INSERT INTO staff_office_hours_directory (user_id, day_of_week, start_time, "
                 "end_time, location) VALUES ('lee', 'Friday', '14:00', '15:00', 'B3')")
    (loose,) = oh.directory_only(conn, "lee")
    made = oh.make_bookable(conn, loose["hours_id"], capacity=4)
    assert oh.block(conn, made)["capacity"] == 4 and oh.directory_only(conn, "lee") == []


def test_ensure_never_commits_a_callers_transaction(tmp_path):
    path = tmp_path / "t.db"
    c = sqlite3.connect(path)
    for ddl in SCHEMA[:2]:
        c.execute(ddl)
    c.commit()
    c.execute("INSERT INTO office_hours (instructor_id, day_of_week, start_time, end_time, "
              "location) VALUES ('x', 'Monday', '09:00', '10:00', 'A')")
    oh.ensure(c)
    c.rollback()
    assert c.execute("SELECT COUNT(*) FROM office_hours").fetchone()[0] == 0
    c.close()
