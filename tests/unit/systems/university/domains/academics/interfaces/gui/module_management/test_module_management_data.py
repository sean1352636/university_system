"""Tests for the Module Management data layer and the module-level prerequisite
rules the enrolment gate now reads.

Everything runs against a temporary SQLite file: every data function takes a
``conn``, so nothing here touches the live database.
"""

import sqlite3

import pytest

from education_system.systems.university.domains.curriculum.interfaces.gui.module_management import (
    data,
)
from education_system.systems.university.services.bus.enrolment_bus import (
    missing_requisites,
)

SCHEMA = [
    """CREATE TABLE modules (
        module_id INTEGER PRIMARY KEY AUTOINCREMENT, module_code TEXT, module_name TEXT,
        module_type TEXT, credits INTEGER, semester TEXT, year TEXT, course TEXT,
        department TEXT, instructor TEXT, instructor_id INTEGER, capacity INTEGER,
        is_active INTEGER DEFAULT 1, description TEXT, updated_at TEXT)""",
    """CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT,
        last_name TEXT, email_address TEXT)""",
    """CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        last_name TEXT, role TEXT)""",
    """CREATE TABLE courses (id INTEGER PRIMARY KEY, code TEXT, name TEXT,
        course_code TEXT, course_name TEXT)""",
    """CREATE TABLE student_modules (
        id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, module_code TEXT,
        enrollment_date TEXT, status TEXT DEFAULT 'Enrolled', module_name TEXT, grade TEXT,
        UNIQUE(student_id, module_code))""",
    """CREATE TABLE module_grades (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT,
        module_code TEXT, final_score REAL, final_grade TEXT)""",
    """CREATE TABLE course_module_map (
        id INTEGER PRIMARY KEY AUTOINCREMENT, course_code TEXT NOT NULL,
        module_code TEXT NOT NULL, link_source TEXT NOT NULL DEFAULT 'manual',
        created_at TEXT, UNIQUE(course_code, module_code))""",
    """CREATE TABLE degree_course_prerequisites (
        prerequisite_id INTEGER PRIMARY KEY AUTOINCREMENT, module_code TEXT NOT NULL,
        prerequisite_module_code TEXT NOT NULL, min_grade TEXT,
        is_corequisite INTEGER DEFAULT 0, created_at TEXT,
        UNIQUE(module_code, prerequisite_module_code))""",
    """CREATE TABLE assessments (assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_name TEXT, assessment_type TEXT, module_code TEXT, max_points REAL,
        weight REAL, due_date TEXT, status TEXT)""",
]


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(str(tmp_path / "records.db"))
    c.row_factory = sqlite3.Row
    for stmt in SCHEMA:
        c.execute(stmt)
    c.executemany(
        "INSERT INTO modules (module_code, module_name, credits, course, is_active) "
        "VALUES (?, ?, ?, ?, ?)",
        [("CS101", "Programming", 15, "CS", 1), ("CS201", "Algorithms", 15, None, 1),
         ("CS301", "Compilers", 0, None, 1), ("OLD1", "Retired thing", 15, None, 0),
         ("", "Blank code row", 15, None, 1)])
    c.executemany("INSERT INTO students VALUES (?, ?, ?, ?)",
                  [("S1", "Ada", "L", "ada@example.com"), ("S2", "Alan", "T", None)])
    c.executemany("INSERT INTO users (id, username, role) VALUES (?, ?, ?)",
                  [(1, "admin", "admin"), (2, "tutor", "staff"), (3, "stud", "student")])
    c.executemany("INSERT INTO courses (code, name) VALUES (?, ?)",
                  [("CS", "Computer Science"), ("DS", "Data Science")])
    c.commit()
    yield c
    c.close()


def test_catalogue_hides_retired_and_blank_codes(conn):
    codes = [m["module_code"] for m in data.list_modules(conn=conn)]
    assert codes == ["CS101", "CS201", "CS301"]
    everything = [m["module_code"] for m in data.list_modules(include_inactive=True, conn=conn)]
    assert "OLD1" in everything and "" not in everything


def test_search_escapes_like_wildcards(conn):
    assert [m["module_code"] for m in data.list_modules("algo", conn=conn)] == ["CS201"]
    assert data.list_modules("%", conn=conn) == []


def test_retire_and_reinstate_never_delete(conn):
    assert data.set_active("CS101", False, conn=conn)
    assert "CS101" not in [m["module_code"] for m in data.list_modules(conn=conn)]
    assert data.get_module("CS101", conn=conn)["is_active"] == 0
    data.set_active("CS101", True, conn=conn)
    assert data.get_module("CS101", conn=conn)["is_active"] == 1


def test_programme_links_show_source_and_only_map_rows_are_removable(conn):
    assert data.add_programme("CS101", "DS", conn=conn) is True
    assert data.add_programme("CS101", "DS", conn=conn) is False
    links = {p["course_code"]: p for p in data.list_programmes("CS101", conn=conn)}
    assert links["CS"]["removable"] is False          # from modules.course
    assert links["DS"]["removable"] is True
    assert links["DS"]["course_name"] == "Data Science"
    assert data.remove_programme("CS101", "DS", conn=conn)
    assert [p["course_code"] for p in data.list_programmes("CS101", conn=conn)] == ["CS"]


def test_link_to_unknown_course_is_refused(conn):
    with pytest.raises(ValueError):
        data.add_programme("CS101", "NOPE", conn=conn)


def test_prerequisites_refuse_self_duplicates_and_cycles(conn):
    data.add_prerequisite("CS201", "CS101", min_grade="C", conn=conn)
    data.add_prerequisite("CS301", "CS201", conn=conn)
    with pytest.raises(ValueError):
        data.add_prerequisite("CS101", "CS101", conn=conn)
    with pytest.raises(ValueError):
        data.add_prerequisite("CS201", "CS101", conn=conn)
    with pytest.raises(ValueError, match="cycle"):
        data.add_prerequisite("CS101", "CS301", conn=conn)   # CS301 -> CS201 -> CS101
    with pytest.raises(ValueError):
        data.add_prerequisite("CS101", "MISSING", conn=conn)
    rules = data.list_prerequisites("CS201", conn=conn)
    assert [(r["code"], r["min_grade"], r["removable"]) for r in rules] == [("CS101", "C", True)]


def test_enrolment_gate_enforces_module_level_rules(conn):
    """A rule entered in Module Management must actually block enrolment."""
    data.add_prerequisite("CS201", "CS101", conn=conn)
    missing, _ = missing_requisites(conn, "S1", "CS201")
    assert [m["code"] for m in missing] == ["CS101"]

    conn.execute("INSERT INTO module_grades (student_id, module_code, final_grade) "
                 "VALUES ('S1', 'CS101', 'B')")
    assert missing_requisites(conn, "S1", "CS201") == ([], [])


def test_corequisite_is_met_by_current_enrolment(conn):
    data.add_prerequisite("CS201", "CS101", corequisite=True, conn=conn)
    _, missing_co = missing_requisites(conn, "S1", "CS201")
    assert [m["code"] for m in missing_co] == ["CS101"]
    data.enrol_student("CS101", "S1", conn=conn)
    assert missing_requisites(conn, "S1", "CS201") == ([], [])


def test_enrol_withdraw_reinstate_keeps_one_row(conn):
    assert data.enrol_student("CS101", "S1", conn=conn) == "enrolled"
    assert data.enrol_student("CS101", "S1", conn=conn) == "already"
    assert data.withdraw_student("CS101", "S1", conn=conn) is True
    assert data.withdraw_student("CS101", "S1", conn=conn) is False
    assert data.enrol_student("CS101", "S1", conn=conn) == "reinstated"
    assert conn.execute("SELECT COUNT(*) FROM student_modules").fetchone()[0] == 1
    assert data.list_modules("CS101", conn=conn)[0]["enrolled"] == 1


def test_withdrawn_rows_are_hidden_on_request(conn):
    data.enrol_student("CS101", "S1", conn=conn)
    data.enrol_student("CS101", "S2", conn=conn)
    data.withdraw_student("CS101", "S2", conn=conn)
    assert len(data.list_enrolments("CS101", conn=conn)) == 2
    assert [r["student_id"] for r in
            data.list_enrolments("CS101", include_withdrawn=False, conn=conn)] == ["S1"]


def test_enrol_unknown_student_is_refused(conn):
    with pytest.raises(ValueError):
        data.enrol_student("CS101", "NOBODY", conn=conn)


def test_student_emails_skip_missing_addresses(conn):
    data.enrol_student("CS101", "S1", conn=conn)
    data.enrol_student("CS101", "S2", conn=conn)
    assert data.student_emails("CS101", conn=conn) == [
        {"student_id": "S1", "email": "ada@example.com"}]


def test_assign_instructor_resolves_the_local_user_id(conn):
    data.assign_instructor("CS101", "tutor", conn=conn)
    row = conn.execute("SELECT instructor, instructor_id FROM modules "
                       "WHERE module_code = 'CS101'").fetchone()
    assert tuple(row) == ("tutor", 2)
    assert [m["module_code"] for m in data.list_modules(instructor="tutor", conn=conn)] == ["CS101"]
    data.assign_instructor("CS101", None, conn=conn)
    assert data.list_modules(instructor="tutor", conn=conn) == []
    with pytest.raises(ValueError):
        data.assign_instructor("CS101", "ghost", conn=conn)


def test_instructor_choices_exclude_students(conn):
    assert [p["username"] for p in data.instructor_choices(conn=conn)] == ["admin", "tutor"]


def test_grade_summary(conn):
    conn.executemany("INSERT INTO assessments (assessment_name, module_code, weight) "
                     "VALUES (?, 'CS101', ?)", [("Exam", 60), ("Essay", 40)])
    conn.executemany("INSERT INTO module_grades (student_id, module_code, final_score, "
                     "final_grade) VALUES (?, 'CS101', ?, ?)",
                     [("S1", 70, "A"), ("S2", 30, "F")])
    summary = data.grade_summary("CS101", conn=conn)
    assert summary == {"graded": 2, "average": 50.0, "passed": 1,
                       "assessments": 2, "total_weight": 100}


def test_csv_round_trip_skips_existing_codes(conn, tmp_path):
    path = str(tmp_path / "modules.csv")
    assert data.export_csv(path, conn=conn) == 5
    conn.execute("DELETE FROM modules WHERE module_code = 'CS201'")
    imported, problems = data.import_csv(path, conn=conn)
    assert imported == 1
    assert data.get_module("CS201", conn=conn)["credits"] == 15
    assert any("already exists" in p for p in problems)
    assert any("missing module_code" in p for p in problems)   # the blank-code row


def test_import_requires_code_and_name_columns(conn, tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("code,name\nX,Y\n", encoding="utf-8")
    with pytest.raises(ValueError):
        data.import_csv(str(path), conn=conn)


def test_validate_reports_without_changing_anything(conn):
    conn.execute("INSERT INTO student_modules (student_id, module_code) VALUES ('S1', 'GONE')")
    before = conn.execute("SELECT COUNT(*) FROM student_modules").fetchone()[0]
    issues = data.validate(conn=conn)
    assert any("no module code" in i for i in issues)
    assert any("no credit value" in i for i in issues)
    assert any("no module record" in i for i in issues)
    assert conn.execute("SELECT COUNT(*) FROM student_modules").fetchone()[0] == before
