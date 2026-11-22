"""Dated timetable sessions: terms, holidays, teaching weeks, deliveries,
one-off changes, room bookings, warnings, notices and the versioned
timetabler applied to the live timetable. In-memory database built here."""

import sqlite3

import pytest

from education_system.systems.university.application.teaching import occurrences as tt
from education_system.systems.university.domains.teaching.application import timetabling

SCHEMA = [
    "CREATE TABLE modules (module_code TEXT, module_name TEXT, course TEXT, year TEXT, "
    "is_active INTEGER DEFAULT 1)",
    "CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT, "
    "email_address TEXT)",
    "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, student_id TEXT, email TEXT, "
    "role TEXT)",
    "CREATE TABLE student_modules (student_id TEXT, module_code TEXT, status TEXT)",
    "CREATE TABLE rooms (id INTEGER PRIMARY KEY, building TEXT, room_number TEXT, "
    "room_name TEXT, capacity INTEGER, is_active INTEGER DEFAULT 1)",
    "CREATE TABLE instructors (id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, "
    "email TEXT, max_hours_per_week INTEGER, preferred_days TEXT, preferred_times TEXT)",
    """CREATE TABLE module_schedule (id INTEGER PRIMARY KEY, module_code TEXT,
        day_of_week TEXT, start_time TEXT, end_time TEXT, room_id INTEGER,
        instructor_id INTEGER, session_type TEXT, semester TEXT, year INTEGER,
        status TEXT DEFAULT 'published', recurrence_until TEXT, modified_date TEXT)""",
    "CREATE TABLE academic_terms (id INTEGER PRIMARY KEY, name TEXT, start_date TEXT, "
    "end_date TEXT)",
    "CREATE TABLE holidays (id INTEGER PRIMARY KEY, holiday_name TEXT, start_date TEXT, "
    "end_date TEXT)",
    "CREATE TABLE course_sections (id INTEGER PRIMARY KEY, course_code TEXT, term_id INTEGER, "
    "section_number TEXT, capacity INTEGER, status TEXT DEFAULT 'Open')",
    "CREATE TABLE room_bookings (booking_id INTEGER PRIMARY KEY, room_id INTEGER, "
    "booked_by TEXT, booking_type TEXT, purpose TEXT, start_datetime TEXT, end_datetime TEXT, "
    "booking_status TEXT DEFAULT 'confirmed')",
    """CREATE TABLE messages (id INTEGER PRIMARY KEY, sender_id INTEGER, recipient_id INTEGER,
        subject TEXT, message TEXT, content TEXT, is_read INTEGER, sent_at TEXT)""",
]


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    for ddl in SCHEMA:
        c.execute(ddl)
    c.execute("INSERT INTO modules VALUES ('CS101', 'Programming', 'CS', '1', 1)")
    c.execute("INSERT INTO modules VALUES ('CS102', 'Maths', 'CS', '1', 1)")
    c.executemany("INSERT INTO students VALUES (?, ?, '', ?)",
                  [("S1", "Ann", "ann@uni.ac.uk"), ("S2", "Bob", "bob@uni.ac.uk")])
    c.executemany("INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                  [(1, "admin", None, "a@uni.ac.uk", "admin"),
                   (2, "S1", "S1", "ann@uni.ac.uk", "student")])
    c.executemany("INSERT INTO student_modules VALUES (?, ?, ?)",
                  [("S1", "CS101", "Enrolled"), ("S2", "CS101", "Withdrawn")])
    c.execute("INSERT INTO rooms VALUES (1, 'Main', '101', NULL, 30, 1)")
    c.execute("INSERT INTO instructors VALUES (7, 'Jo', 'Lee', 'jo@uni.ac.uk', 4, "
              "'Mon, Tue', '09:00-12:00')")
    # Autumn term: Monday 7 Sep – Friday 11 Dec 2026.
    c.execute("INSERT INTO academic_terms VALUES (1, 'Fall 2026', '2026-09-07', '2026-12-11')")
    c.execute("INSERT INTO academic_terms VALUES (2, 'Spring 2027', '2027-01-11', '2027-03-26')")
    c.execute("INSERT INTO module_schedule (id, module_code, day_of_week, start_time, end_time, "
              "room_id, instructor_id, session_type, semester, year) VALUES "
              "(1, 'CS101', 'Monday', '10:00', '11:00', 1, 7, 'Lecture', 'Fall', 2026)")
    c.commit()
    tt.ensure(c)  # adds module_schedule.section_id / week_pattern, student_modules.section_id
    yield c
    c.close()


def _dates(c, start="2026-08-01", end="2027-06-30", code="CS101"):
    return [o["date"] for o in tt.for_module(c, code, start, end) if o["status"] != "cancelled"]


def test_sessions_only_inside_their_term(conn):
    dates = _dates(conn)
    assert dates[0] == "2026-09-07" and dates[-1] == "2026-12-07"
    assert len(dates) == 14


def test_holidays_and_end_date_are_skipped(conn):
    conn.execute("INSERT INTO holidays VALUES (1, 'Reading', '2026-10-26', '2026-10-30')")
    conn.execute("UPDATE module_schedule SET recurrence_until = '2026-11-30'")
    dates = _dates(conn)
    assert "2026-10-26" not in dates and dates[-1] == "2026-11-30"


def test_teaching_week_pattern(conn):
    conn.execute("UPDATE module_schedule SET week_pattern = '1-2,4'")
    assert _dates(conn) == ["2026-09-07", "2026-09-14", "2026-09-28"]
    with pytest.raises(ValueError):
        tt.parse_weeks("3-1")


def test_slot_matching_no_term_is_reported(conn):
    conn.execute("UPDATE module_schedule SET semester = 'Summer'")
    assert _dates(conn) == []
    assert [s["id"] for s in tt.unplaced(conn, tt.slots(conn))] == [1]


def test_delivery_slot_runs_in_its_term_and_only_for_its_students(conn):
    tt.ensure(conn)
    conn.execute("INSERT INTO course_sections VALUES (5, 'CS101', 2, '001', 20, 'Open')")
    conn.execute("UPDATE module_schedule SET section_id = 5, semester = NULL, year = NULL")
    assert _dates(conn)[0] == "2027-01-11"
    assert tt.student_slots(conn, "S1") == []            # S1 is on no delivery
    conn.execute("UPDATE student_modules SET section_id = 5 WHERE student_id = 'S1'")
    assert len(tt.student_slots(conn, "S1")) == 1


def test_withdrawn_students_see_nothing_and_get_no_notice(conn):
    assert tt.student_slots(conn, "S2") == []
    assert [r["student_id"] for r in tt.recipients(conn, "CS101")] == ["S1"]


def test_cancel_move_and_restore_one_week(conn):
    result = tt.cancel_session(conn, 1, "2026-09-14", "ill", "admin")
    assert ("ann@uni.ac.uk", ) == tuple(e[0] for e in result["emails"] if "ann" in e[0])
    assert conn.execute("SELECT COUNT(*) FROM messages WHERE recipient_id = 2").fetchone()[0] == 1
    tt.move_session(conn, 1, "2026-09-21", new_date="2026-09-23", new_start="14:00",
                    new_end="15:00", reason="works", actor="admin", force=True)
    week = {o["date"]: o for o in tt.for_module(conn, "CS101", "2026-09-14", "2026-09-27")}
    assert week["2026-09-14"]["status"] == "cancelled"
    assert week["2026-09-23"]["moved_from"] == "2026-09-21" and "2026-09-21" not in week
    change = week["2026-09-14"]["change_id"]
    tt.restore_session(conn, change, "admin")
    assert tt.for_module(conn, "CS101", "2026-09-14", "2026-09-14")[0]["status"] == "scheduled"
    with pytest.raises(ValueError, match="does not run"):
        tt.cancel_session(conn, 1, "2026-09-15", "x", "admin")


def test_move_into_an_occupied_room_is_refused(conn):
    conn.execute("INSERT INTO module_schedule (id, module_code, day_of_week, start_time, "
                 "end_time, room_id, semester, year) VALUES "
                 "(2, 'CS102', 'Wednesday', '14:00', '16:00', 1, 'Fall', 2026)")
    with pytest.raises(ValueError, match="CS102"):
        tt.move_session(conn, 1, "2026-09-21", new_date="2026-09-23", new_start="15:00",
                        new_end="16:00", reason="works", actor="admin")


def test_room_bookings_and_timetable_check_each_other(conn):
    conn.execute("INSERT INTO room_bookings VALUES (1, 1, 'exams', 'exam', 'Exam', "
                 "'2099-09-07 10:30', '2099-09-07 12:00', 'confirmed')")  # a Monday
    assert tt.booking_clashes_for_slot(conn, 1, "Monday", "10:00", "11:00")
    assert "CS101" in tt.timetable_clash_for_booking(conn, 1, "2026-09-07 10:30",
                                                     "2026-09-07 11:30")
    assert tt.timetable_clash_for_booking(conn, 1, "2026-09-07 11:00", "2026-09-07 12:00") is None


def test_room_size_and_staff_warnings(conn):
    conn.execute("UPDATE rooms SET capacity = 0")
    assert tt.capacity_warning(conn, "CS101", 1) is None      # unknown capacity: no guess
    conn.execute("UPDATE rooms SET capacity = 1")
    conn.execute("INSERT INTO student_modules (student_id, module_code, status) "
                 "VALUES ('S3', 'CS101', 'Enrolled')")
    assert "holds 1" in tt.capacity_warning(conn, "CS101", 1)
    warnings = tt.staff_warnings(conn, 7, "Friday", "14:00", "18:00")
    assert any("5 h a week" in w for w in warnings)
    assert any("Mon, Tue" in w for w in warnings) and any("09:00-12:00" in w for w in warnings)


def test_ical_leaves_out_cancelled_sessions(conn):
    tt.cancel_session(conn, 1, "2026-09-14", "ill", "admin")
    ics = tt.ical(tt.for_module(conn, "CS101", "2026-09-07", "2026-09-20"))
    assert ics.count("BEGIN:VEVENT") == 1 and "20260907T100000" in ics


def test_overlapping_labels_collide_in_the_optimiser():
    assert timetabling._slots_overlap("Monday 09:00-11:00", "Monday 10:00-12:00")
    assert not timetabling._slots_overlap("Monday 09:00-10:00", "Monday 10:00-11:00")
    assert not timetabling._slots_overlap("MON-09", "MON-10")


def test_applying_a_live_draft_moves_the_slot(conn):
    conn.execute("INSERT INTO module_schedule (id, module_code, day_of_week, start_time, "
                 "end_time, room_id, semester, year) VALUES "
                 "(2, 'CS101', 'Monday', '10:00', '11:00', 1, 'Fall', 2026)")
    activities, _rooms = timetabling.activities_from_timetable(conn)
    assert {a["activity_id"] for a in activities} == {"slot:1", "slot:2"}
    schedule = [dict(a, slot=a["allowed_slots"][0], room=a["allowed_rooms"][0])
                for a in activities]
    next(p for p in schedule if p["activity_id"] == "slot:2")["slot"] = "Tuesday 10:00-11:00"
    moved, emails = timetabling._apply_to_timetable(conn, schedule, "registrar")
    assert moved == 1 and emails
    assert conn.execute("SELECT day_of_week FROM module_schedule WHERE id = 2").fetchone()[0] \
        == "Tuesday"
