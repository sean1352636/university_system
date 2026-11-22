"""Course section form choices, the enrolled count, and safe delete.
Runs on an in-memory database built here, with foreign keys on as in production."""

import sqlite3

import pytest

from education_system.systems.university.application.modules import sections
from education_system.systems.university.domains.teaching.domain.academic_calendar import terms

SCHEMA = """
CREATE TABLE courses (id INTEGER PRIMARY KEY, code TEXT, name TEXT, course_code TEXT,
    course_name TEXT, department TEXT);
CREATE TABLE students (student_id TEXT PRIMARY KEY, course TEXT, status TEXT DEFAULT 'Active',
    is_active INTEGER DEFAULT 1);
CREATE TABLE instructors (id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT,
    status TEXT, is_active INTEGER DEFAULT 1);
CREATE TABLE rooms (id INTEGER PRIMARY KEY, room_number TEXT, building TEXT, capacity INTEGER,
    is_active INTEGER DEFAULT 1, status TEXT DEFAULT 'available');
CREATE TABLE buildings (building_id INTEGER PRIMARY KEY, building_name TEXT, building_type TEXT,
    is_active INTEGER DEFAULT 1);
CREATE TABLE course_sections (id INTEGER PRIMARY KEY, course_code TEXT, status TEXT DEFAULT 'Open',
    updated_at TEXT);
CREATE TABLE section_meetings (id INTEGER PRIMARY KEY, section_id INTEGER NOT NULL,
    FOREIGN KEY (section_id) REFERENCES course_sections (id));
CREATE TABLE student_modules (id INTEGER PRIMARY KEY, student_id TEXT, status TEXT DEFAULT 'Enrolled',
    section_id INTEGER);
CREATE TABLE module_waitlist (id INTEGER PRIMARY KEY, section_id INTEGER, status TEXT DEFAULT 'waiting');
CREATE TABLE module_schedule (id INTEGER PRIMARY KEY, section_id INTEGER, status TEXT DEFAULT 'published');
CREATE TABLE ta_assignments (id INTEGER PRIMARY KEY, section_id TEXT);
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript(SCHEMA)
    c.execute("INSERT INTO courses (code, name, course_code, course_name) "
              "VALUES ('CS', 'Computer Science', 'CS', 'Computer Science')")
    c.execute("INSERT INTO course_sections (id, course_code) VALUES (1, 'CS')")
    yield c
    c.close()


def test_only_available_instructors_are_offered(conn):
    conn.executemany("INSERT INTO instructors (first_name, last_name, status, is_active) "
                     "VALUES (?, ?, ?, ?)",
                     [("Ben", "Smith", "Active", 1), ("On", "Leave", "On Leave", 1),
                      ("Gone", "Away", "Active", 0), ("No", "Status", None, 1)])
    assert sections.instructor_names(conn) == ["Ben Smith", "No Status"]


def test_locations_are_available_rooms_and_teaching_buildings_without_rooms(conn):
    conn.executemany("INSERT INTO rooms (room_number, building, capacity, is_active, status) "
                     "VALUES (?, ?, ?, ?, ?)",
                     [("101", "Main", 40, 1, "available"), ("102", "Main", 0, 1, "available"),
                      ("103", "Main", 50, 1, "maintenance"), ("104", "Main", 60, 0, "available")])
    conn.executemany("INSERT INTO buildings (building_name, building_type) VALUES (?, ?)",
                     [("Main", "academic"), ("Annex", "academic"), ("Halls", "Residence")])
    assert sections.locations(conn) == {"101 — Main": 40, "102 — Main": None, "Annex": None}


def test_enrolled_counts_students_filed_under_code_or_name_and_skips_finished(conn):
    conn.executemany("INSERT INTO students (student_id, course, status) VALUES (?, ?, ?)",
                     [("1", "CS", "Active"), ("2", "Computer Science", "Active"),
                      ("3", "CS", "Completed"), ("4", "Maths", "Active"),
                      ("5", "CS", "Merged")])
    assert sections.enrolled_count(conn, "CS") == 2


def test_enrolled_prefers_students_placed_on_the_section(conn):
    conn.execute("INSERT INTO students (student_id, course) VALUES ('1', 'CS'), ('2', 'CS')")
    conn.execute("INSERT INTO student_modules (student_id, section_id) VALUES ('1', 1)")
    assert sections.enrolled_count(conn, "CS", section_id=1) == 1
    assert sections.enrolled_count(conn, "CS", section_id=99) == 2


def test_enrolled_is_zero_for_a_code_that_is_not_a_course(conn):
    assert sections.enrolled_count(conn, "NOPE") == 0


def test_delete_takes_the_meetings_with_it(conn):
    conn.execute("INSERT INTO section_meetings (id, section_id) VALUES (7, 1), (8, 1)")
    assert sections.delete_section(conn, 1) == [7, 8]
    assert conn.execute("SELECT COUNT(*) FROM course_sections").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM section_meetings").fetchone()[0] == 0


@pytest.mark.parametrize("insert, kind", [
    ("INSERT INTO student_modules (student_id, section_id) VALUES ('1', 1)", "students"),
    ("INSERT INTO module_waitlist (section_id) VALUES (1)", "waitlist"),
    ("INSERT INTO module_schedule (section_id) VALUES (1)", "timetable"),
    ("INSERT INTO ta_assignments (section_id) VALUES ('1')", "assistants"),
])
def test_delete_is_refused_while_something_refers_to_the_section(conn, insert, kind):
    conn.execute(insert)
    assert sections.delete_blockers(conn, 1) == {kind: 1}
    with pytest.raises(ValueError, match="still in use"):
        sections.delete_section(conn, 1)
    assert conn.execute("SELECT COUNT(*) FROM course_sections").fetchone()[0] == 1


def test_finished_references_do_not_block_delete(conn):
    conn.execute("INSERT INTO module_waitlist (section_id, status) VALUES (1, 'removed')")
    conn.execute("INSERT INTO module_schedule (section_id, status) VALUES (1, 'cancelled')")
    assert sections.delete_blockers(conn, 1) == {}


def test_cancel_keeps_the_section(conn):
    sections.cancel_section(conn, 1)
    assert conn.execute("SELECT status FROM course_sections").fetchone()[0] == "Cancelled"


@pytest.fixture
def term_db():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript("""
        CREATE TABLE academic_terms (id INTEGER PRIMARY KEY);
        CREATE TABLE course_sections (id INTEGER PRIMARY KEY, course_code TEXT, term_id INTEGER,
            section_number TEXT, FOREIGN KEY (term_id) REFERENCES academic_terms (id));
        CREATE TABLE section_meetings (id INTEGER PRIMARY KEY, section_id INTEGER NOT NULL,
            FOREIGN KEY (section_id) REFERENCES course_sections (id));
        CREATE TABLE module_waitlist (id INTEGER PRIMARY KEY, section_id INTEGER,
            status TEXT DEFAULT 'waiting');
        CREATE TABLE unified_events (source_type TEXT, source_event_id TEXT);
        INSERT INTO academic_terms VALUES (1), (2);
        INSERT INTO course_sections VALUES (1, 'CS', 1, '001'), (2, 'CS', 1, '002'),
                                           (3, 'CS', 2, '001');
        INSERT INTO section_meetings VALUES (7, 1), (8, 3);
        INSERT INTO unified_events VALUES ('section_meeting', '7:2026-11-02'),
                                          ('section_meeting', '8:2026-11-02'),
                                          ('academic_calendar', '7:2026-11-02');
    """)
    yield c
    c.close()


def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_term_delete_takes_sections_meetings_and_their_calendar_entries(term_db):
    assert terms.delete_term(1, cascade_sections=True, conn=term_db) == 2
    assert term_db.execute("SELECT id FROM academic_terms").fetchall() == [(2,)]
    assert term_db.execute("SELECT id FROM course_sections").fetchall() == [(3,)]
    assert term_db.execute("SELECT id FROM section_meetings").fetchall() == [(8,)]
    assert sorted(term_db.execute("SELECT * FROM unified_events").fetchall()) == [
        ("academic_calendar", "7:2026-11-02"), ("section_meeting", "8:2026-11-02")]


def test_term_delete_without_cascade_is_refused(term_db):
    with pytest.raises(terms.TermError, match="2 course section"):
        terms.delete_term(1, conn=term_db)
    assert _count(term_db, "course_sections") == 3


def test_term_delete_removes_nothing_if_any_section_is_in_use(term_db):
    term_db.execute("INSERT INTO module_waitlist (section_id) VALUES (2)")
    with pytest.raises(terms.TermError, match="CS section 002"):
        terms.delete_term(1, cascade_sections=True, conn=term_db)
    assert _count(term_db, "academic_terms") == 2
    assert _count(term_db, "course_sections") == 3
    assert _count(term_db, "section_meetings") == 2
    assert _count(term_db, "unified_events") == 3
