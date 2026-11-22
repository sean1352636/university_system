"""The course catalogue lists courses, then the modules on the chosen one.
Runs on an in-memory database built here."""

import sqlite3

import pytest

from education_system.systems.university.application.programmes import catalogue, record

SCHEMA = """
CREATE TABLE courses (id INTEGER PRIMARY KEY, code TEXT, name TEXT, course_code TEXT, level TEXT, duration TEXT,
    course_name TEXT, credits INTEGER, course_type TEXT, department TEXT, status TEXT,
    max_enrollment INTEGER, current_enrollment INTEGER);
CREATE TABLE modules (module_id INTEGER PRIMARY KEY, module_code TEXT, module_name TEXT, course TEXT, level TEXT,
    year TEXT, credits INTEGER, module_type TEXT, is_active INTEGER DEFAULT 1);
CREATE TABLE course_curriculum (id INTEGER PRIMARY KEY, course_code TEXT, year INTEGER,
    module_code TEXT, module_name TEXT);
CREATE TABLE students (student_id TEXT PRIMARY KEY, course TEXT, status TEXT DEFAULT 'Active',
    is_active INTEGER DEFAULT 1);
CREATE TABLE student_modules (id INTEGER PRIMARY KEY, student_id TEXT, module_code TEXT,
    status TEXT DEFAULT 'Enrolled');
INSERT INTO courses (code, name, course_code, course_name, credits, course_type, department,
                     status, max_enrollment, current_enrollment) VALUES
    ('CS', 'Computer Science', 'CS', 'Computer Science', 360, 'Bachelors', 'Computing', 'active', 100, 77),
    ('LAW', 'Law', 'LAW', 'Law', 360, 'Masters', 'Law School', 'active', 50, 0),
    ('OLD', 'Closed Course', 'OLD', 'Closed Course', 360, 'Bachelors', 'Computing', 'archived', 50, 0);
INSERT INTO modules (module_code, module_name, course, year, credits, module_type, is_active) VALUES
    ('CS-1', 'Algorithms', 'CS', '1', 20, 'Core', 1),
    ('CS-2', 'Retired Topic', 'CS', '1', 20, 'Core', 0),
    ('LAW-1', 'Contract', 'LAW', '1', 20, 'Core', 1);
INSERT INTO course_curriculum (course_code, year, module_code, module_name) VALUES
    ('CS', 1, 'CS-1', 'Algorithms'), ('CS', 1, 'CS-2', 'Retired Topic'), ('LAW', 1, 'LAW-1', 'Contract');
INSERT INTO students VALUES ('1', 'CS', 'Active', 1), ('2', 'Computer Science', 'Active', 1),
    ('3', 'CS', 'Completed', 0), ('4', 'CS', 'Merged', 1);
INSERT INTO student_modules (student_id, module_code, status) VALUES ('1', 'CS-1', 'Enrolled'),
    ('2', 'CS-1', 'Dropped');
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA)
    record.ensure(c)
    yield c
    c.close()


def _codes(rows):
    return [r["code"] for r in rows]


def test_lists_offered_courses_not_modules(conn):
    assert _codes(catalogue.courses(conn)) == ["CS", "LAW"]


def test_enrolled_is_the_live_count_not_the_stored_counter(conn):
    cs = catalogue.courses(conn)[0]
    assert cs["enrolled"] == 2 and cs["capacity"] == 100


def test_marks_the_students_own_course(conn):
    statuses = {r["code"]: r["status"] for r in catalogue.courses(conn, student_id="2")}
    assert statuses == {"CS": "Your course", "LAW": "Offered"}


@pytest.mark.parametrize("term, expected", [
    ("computer", ["CS"]), ("law sch", ["LAW"]), ("algorithms", ["CS"]), ("100%", []), ("", ["CS", "LAW"]),
])
def test_search_covers_course_department_and_modules(conn, term, expected):
    assert _codes(catalogue.courses(conn, term)) == expected


def test_filters_by_course_type(conn):
    assert _codes(catalogue.courses(conn, course_type="Masters")) == ["LAW"]
    assert catalogue.course_types(conn) == ["Bachelors", "Masters"]


def test_modules_on_a_course_leave_out_inactive_ones(conn):
    rows = catalogue.modules_on(conn, "CS")
    assert _codes(rows) == ["CS-1"]
    assert rows[0]["name"] == "Algorithms" and rows[0]["designation"] == "Core"
    assert rows[0]["enrolled"] == 1 and rows[0]["status"] == "Available"


def test_modules_show_this_students_status(conn):
    assert catalogue.modules_on(conn, "CS", "1")[0]["status"] == "Enrolled"
    assert catalogue.modules_on(conn, "CS", "2")[0]["status"] == "Dropped"
