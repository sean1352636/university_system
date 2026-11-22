"""Batch operations: file reading and mapping, student imports through the
lifecycle service (preview, duplicates, updates with a reason, transfers),
marks through the marking rules, staff accounts (never admin), jobs and
per-job undo, and watched folders. Temporary databases only; sign-in and
email steps are stubbed."""

import csv
import sqlite3

import pytest

from education_system.systems.university.application.batch import files as bf
from education_system.systems.university.application.batch import imports as bi
from education_system.systems.university.application.batch import jobs as bj
from education_system.systems.university.application.students.search import Viewer

SCHEMA = [
    """CREATE TABLE students (student_id TEXT PRIMARY KEY, email_address TEXT UNIQUE, title TEXT,
        first_name TEXT, middle_name TEXT, last_name TEXT, gender TEXT, dob TEXT, age INTEGER,
        course TEXT, registration_datetime TEXT, status TEXT, enrollment_date TEXT,
        is_active INTEGER, entry_qualifications TEXT, ucas_tariff INTEGER, phone TEXT,
        address TEXT, nationality TEXT, mode_of_study TEXT, pronouns TEXT,
        emergency_contact TEXT)""",
    "CREATE TABLE courses (course_code TEXT PRIMARY KEY, code TEXT, course_name TEXT, name TEXT, "
    "status TEXT, current_enrollment INTEGER DEFAULT 0)",
    "INSERT INTO courses VALUES ('CS', 'CS', 'Computer Science', 'Computer Science', 'active', 0)",
    "INSERT INTO courses VALUES ('DS', 'DS', 'Data Science', 'Data Science', 'active', 0)",
    "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, student_id TEXT, role TEXT, "
    "first_name TEXT, last_name TEXT, updated_at TEXT)",
    "INSERT INTO users (username, role) VALUES ('lead', 'staff')",
    "CREATE TABLE student_modules (student_id TEXT, module_code TEXT, module_name TEXT, "
    "module_type TEXT, year TEXT, status TEXT, UNIQUE (student_id, module_code))",
    """CREATE TABLE university_event_outbox (event_id TEXT PRIMARY KEY, event_name TEXT,
        event_version INTEGER, aggregate_id TEXT, correlation_id TEXT, causation_id TEXT,
        idempotency_key TEXT UNIQUE, payload_json TEXT, available_at TEXT,
        attempts INTEGER DEFAULT 0, delivered_at TEXT, dead_lettered_at TEXT, last_error TEXT)""",
    "CREATE TABLE assessments (assessment_id INTEGER PRIMARY KEY, assessment_name TEXT, "
    "module_code TEXT, max_points REAL, status TEXT)",
    "INSERT INTO assessments VALUES (7, 'Final exam', 'CS101', 50, 'Active')",
    "CREATE TABLE grades (grade_id INTEGER PRIMARY KEY, student_id TEXT, assessment_id INTEGER, "
    "score REAL, letter_grade TEXT, submission_date TEXT, comments TEXT, graded_by TEXT, "
    "result_code TEXT)",
    "CREATE TABLE module_grades (id INTEGER PRIMARY KEY, student_id TEXT, module_code TEXT, "
    "final_score REAL, locked INTEGER DEFAULT 0)",
    "CREATE TABLE grade_change_log (source TEXT, record_id INTEGER, student_id TEXT, "
    "module_code TEXT, old_value TEXT, new_value TEXT, reason TEXT, changed_by TEXT, "
    "changed_at TEXT)",
    "CREATE TABLE staff (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash "
    "TEXT NOT NULL, name TEXT NOT NULL, email TEXT, role TEXT NOT NULL, hire_date TEXT, "
    "status TEXT DEFAULT 'active')",
]
ADMIN = Viewer("admin", "admin", True, True, True, True, True, can_mark=True,
               can_manage_users=True)


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "students.db"
    with sqlite3.connect(path) as conn:
        for ddl in SCHEMA:
            conn.execute(ddl)
        conn.execute("INSERT INTO students (student_id, email_address, first_name, last_name, "
                     "dob, course, status, is_active) VALUES ('1111111', 'c1@uni.uk', 'John', "
                     "'Smith', '2002-05-15', 'CS', 'Active', 1)")
        conn.executemany("INSERT INTO student_modules (student_id, module_code, status) VALUES "
                         "(?, 'CS101', 'Enrolled')", [("1111111",), ("2222222",)])
    from education_system.systems.university.domains.admissions.domain.services import (
        admissions_selection,
    )
    monkeypatch.setattr(admissions_selection, "enrol_student_in_curriculum",
                        lambda cur, sid, code, name: [])
    monkeypatch.setattr(admissions_selection, "curriculum_for", lambda cur, code, name: [])
    from education_system.systems.university.application.exams import marking as exam_marking
    monkeypatch.setattr(exam_marking, "after_mark", lambda conn, grade_id, marker=None: {})
    from education_system.systems.university.application.assessment import module_results
    monkeypatch.setattr(module_results, "recompute_safely", lambda *a: None)
    return str(path)


def _csv(tmp_path, name, rows):
    path = tmp_path / name
    with path.open("w", newline="") as handle:
        csv.writer(handle).writerows(rows)
    return str(path)


def _count(db, sql, args=()):
    with sqlite3.connect(db) as conn:
        return conn.execute(sql, args).fetchone()[0]


def test_headers_are_mapped_by_alias_and_missing_columns_refused(tmp_path):
    path = _csv(tmp_path, "s.csv", [["Forename", "Surname", "Date of Birth", "Programme"],
                                    ["Mia", "Patel", "2005-05-05", "CS"]])
    rows, mapping = bi.read_and_map(path, "students")
    assert mapping == {"first_name": "Forename", "last_name": "Surname", "dob": "Date of Birth",
                       "course": "Programme"}
    assert rows == [{"first_name": "Mia", "last_name": "Patel", "dob": "2005-05-05",
                     "course": "CS"}]
    with pytest.raises(ValueError, match="Missing column"):
        bi.read_and_map(_csv(tmp_path, "x.csv", [["Forename"], ["Mia"]]), "students")
    assert bi.read_and_map(_csv(tmp_path, "u.csv", [["student_id", "phone"], ["1", "2"]]),
                           "students", mode="update")[0] == [{"student_id": "1", "phone": "2"}]


def test_preview_changes_nothing_and_flags_every_problem(db):
    rows = [{"first_name": "Mia", "last_name": "Patel", "dob": "2005-05-05", "course": "CS"},
            {"first_name": "JOHN", "last_name": "smith", "dob": "2002-05-15", "course": "CS"},
            {"first_name": "Mia", "last_name": "Patel", "dob": "2005-05-05", "course": "DS"},
            {"first_name": "Al", "last_name": "B", "dob": "2004-01-01",
             "course": "Basket Weaving"}]
    result = bi.import_students(rows, ADMIN, dry_run=True, db_path=db)
    assert [r["action"] for r in result["rows"]] == ["create", "skip", "skip", "failed"]
    assert "1111111" in result["rows"][1]["message"]
    assert "row 2" in result["rows"][2]["message"]
    assert result["job_id"] is None and _count(db, "SELECT COUNT(*) FROM students") == 1


def test_import_creates_by_course_name_records_a_job_and_undo_withdraws(db):
    rows = [{"first_name": "Mia", "last_name": "Patel", "dob": "2005-05-05",
             "course": "Data Science", "phone": "07700 900111"}]
    result = bi.import_students(rows, ADMIN, provision=False, db_path=db)
    new = result["rows"][0]["ref"]
    assert result["rows"][0]["action"] == "created"
    assert _count(db, "SELECT course FROM students WHERE student_id = ?", (new,)) == "DS"
    with sqlite3.connect(db) as conn:
        assert bj.job(conn, result["job_id"])["succeeded"] == 1
    assert bj.undo(result["job_id"], ADMIN, "Wrong file", db_path=db)["undone"] == 1
    assert _count(db, "SELECT status FROM students WHERE student_id = ?", (new,)) == "Withdrawn"
    with pytest.raises(ValueError, match="undone"):
        bj.undo(result["job_id"], ADMIN, "again", db_path=db)


def test_update_needs_a_reason_changes_only_supplied_fields_and_undoes(db):
    rows = [{"student_id": "1111111", "phone": "07000 000001", "course": "DS"},
            {"student_id": "1111111"}, {"student_id": "9999999", "phone": "1"}]
    with pytest.raises(ValueError, match="reason"):
        bi.import_students(rows, ADMIN, mode="update", db_path=db)
    result = bi.import_students(rows, ADMIN, mode="update", reason="Corrections", db_path=db)
    assert [r["action"] for r in result["rows"]] == ["updated", "unchanged", "failed"]
    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT phone, course, first_name FROM students").fetchone()
    assert row == ("07000 000001", "DS", "John")
    bj.undo(result["job_id"], ADMIN, "Revert", db_path=db)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT phone, course FROM students").fetchone() == (None, "CS")


def test_marks_go_through_the_rules_and_undo_restores_them(db):
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO grades (student_id, assessment_id, score) VALUES "
                     "('2222222', 7, 30)")
    rows = [{"student_id": "1111111", "assessment_id": "7", "score": "40"},
            {"student_id": "2222222", "module_code": "CS101", "assessment": "final exam",
             "percentage": "50"},
            {"student_id": "3333333", "assessment_id": "7", "score": "10"},
            {"student_id": "1111111", "assessment_id": "7", "score": "60"}]
    with pytest.raises(ValueError, match="permission"):
        bi.import_marks(rows, Viewer("x", "staff", True), db_path=db)
    result = bi.import_marks(rows, ADMIN, reason="Board upload", db_path=db)
    assert [r["action"] for r in result["rows"]] == ["created", "updated", "failed", "failed"]
    assert "not enrolled" in result["rows"][2]["message"]
    assert "between 0 and 50" in result["rows"][3]["message"]
    assert _count(db, "SELECT score FROM grades WHERE student_id = '2222222'") == 25
    assert _count(db, "SELECT COUNT(*) FROM grade_change_log") == 1
    bj.undo(result["job_id"], ADMIN, "Wrong sheet", db_path=db)
    assert _count(db, "SELECT COUNT(*) FROM grades WHERE student_id = '1111111'") == 0
    assert _count(db, "SELECT score FROM grades WHERE student_id = '2222222'") == 30


def test_marks_refused_once_a_board_has_confirmed_the_result(db):
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO module_grades (student_id, module_code, locked) VALUES "
                     "('1111111', 'CS101', 1)")
    result = bi.import_marks([{"student_id": "1111111", "assessment_id": "7", "score": "40"}],
                             ADMIN, reason="r", db_path=db)
    assert "confirmed" in result["rows"][0]["message"]


def test_staff_accounts_never_admin_and_get_an_activation_email(db, monkeypatch):
    from education_system.systems.university.services import staff_provisioning
    from education_system.systems.university.services import student_provisioning
    calls = []
    monkeypatch.setattr(staff_provisioning, "provision_staff_login",
                        lambda member, auth=None: calls.append(member["username"])
                        or {"shared_ok": True})
    monkeypatch.setattr(staff_provisioning, "provision_instructor_profile", lambda *a: None)
    monkeypatch.setattr(student_provisioning, "send_student_activation", lambda e: True)
    disabled = []
    monkeypatch.setattr(student_provisioning, "set_student_login_active",
                        lambda u, active, path=None: disabled.append((u, active)))
    rows = [{"username": "kpatel", "first_name": "Kiran", "last_name": "Patel",
             "email": "k@uni.ac.uk", "role": "lecturer"},
            {"username": "boss", "first_name": "B", "last_name": "B", "email": "b@uni.ac.uk",
             "role": "admin"},
            {"username": "lead", "first_name": "L", "last_name": "L", "email": "l@uni.ac.uk"}]
    result = bi.import_staff(rows, ADMIN, db_path=db)
    assert [r["action"] for r in result["rows"]] == ["created", "failed", "skip"]
    assert "activation email sent" in result["rows"][0]["message"] and calls == ["kpatel"]
    assert _count(db, "SELECT password_hash FROM staff WHERE username = 'kpatel'") == "!"
    bj.undo(result["job_id"], ADMIN, "Not starting", db_path=db)
    assert _count(db, "SELECT status FROM staff WHERE username = 'kpatel'") == "inactive"
    assert disabled == [("kpatel", False)]


def test_watched_folder_imports_new_files_and_files_them(db, tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO users (username, role) VALUES ('admin', 'admin')")
        bj.add_watch(conn, ADMIN, "marks", str(inbox), "Nightly marks")
        conn.commit()
    _csv(inbox, "good.csv", [["student_id", "assessment_id", "score"], ["1111111", "7", "45"]])
    _csv(inbox, "bad.csv", [["foo"], ["bar"]])
    result = bi.run_watch_folders(db_path=db)
    assert result["watches"][0][1] == "1 file(s) imported, 1 problem(s)"
    assert len(list((inbox / "processed").iterdir())) == 1
    assert {p.suffix for p in (inbox / "failed").iterdir()} == {".csv", ".txt"}
    assert _count(db, "SELECT score FROM grades WHERE student_id = '1111111'") == 45
    assert bi.run_watch_folders(db_path=db)["watches"][0][1] == "0 file(s) imported, 0 problem(s)"


def test_saved_mappings_and_templates(db, tmp_path):
    with sqlite3.connect(db) as conn:
        mid = bf.save_mapping(conn, "lead", "students", "SITS export",
                              {"first_name": "FORENAME"}, shared=True)
        assert bf.mappings(conn, "other", "students")[0]["id"] == mid
        with pytest.raises(ValueError, match="Unknown"):
            bf.save_mapping(conn, "lead", "students", "bad", {"password": "x"})
        with pytest.raises(ValueError, match="owner"):
            bf.delete_mapping(conn, "other", mid)
    header = (tmp_path / "t.csv")
    bf.write_template("marks", header)
    assert header.read_text().splitlines()[0].startswith("student_id,assessment_id")
