"""Module registration: course structure (curriculum + designations),
who may register, compulsory modules, optional choices and approval,
credit limits, waitlisting, registration periods and deadlines, keeping
module_enrolments in step, module credits, and the transaction-safe ensure.
Temporary databases only."""

import sqlite3
from datetime import date, timedelta

import pytest

from education_system.systems.university.application.modules import enrolment as me
from education_system.systems.university.application.modules import registration as mr
from education_system.systems.university.application.modules import registration_admin as ma

SCHEMA = [
    "CREATE TABLE courses (course_code TEXT, code TEXT, course_name TEXT, name TEXT, status TEXT, "
    "department TEXT)",
    "INSERT INTO courses VALUES ('CS', 'CS', 'Computer Science', 'Computer Science', 'active', "
    "'Computing')",
    """CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT,
        status TEXT, course TEXT, enrollment_date TEXT, year_of_study INTEGER,
        email_address TEXT, mode_of_study TEXT, campus_code TEXT)""",
    """CREATE TABLE modules (module_code TEXT PRIMARY KEY, module_name TEXT, credits INTEGER,
        capacity INTEGER, is_active INTEGER DEFAULT 1, course TEXT, level TEXT,
        department TEXT, instructor TEXT)""",
    """CREATE TABLE student_modules (student_id TEXT, module_code TEXT, module_name TEXT,
        status TEXT, enrollment_date TEXT, semester TEXT, year TEXT,
        UNIQUE (student_id, module_code))""",
    "CREATE TABLE course_curriculum (id INTEGER PRIMARY KEY, course_code TEXT, year INTEGER, "
    "module_code TEXT, module_name TEXT)",
    "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role TEXT, student_id TEXT, "
    "first_name TEXT, last_name TEXT)",
    """CREATE TABLE messages (id INTEGER PRIMARY KEY, sender_id INTEGER, recipient_id INTEGER,
        subject TEXT, message TEXT, content TEXT, is_read INTEGER, sent_at TEXT)""",
    """CREATE TABLE programme_registrations (registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT, programme_code TEXT, academic_year TEXT, occurrence_code TEXT,
        mode_of_study TEXT, status TEXT, effective_from TEXT, registered_at TEXT,
        registered_by TEXT)""",
    """CREATE TABLE module_enrolments (module_enrolment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        registration_id INTEGER, student_id TEXT, module_code TEXT, academic_year TEXT,
        teaching_period TEXT, attempt_number INTEGER DEFAULT 1, status TEXT,
        effective_from TEXT, created_at TEXT, updated_at TEXT)""",
    "CREATE TABLE tutor_groups (group_id INTEGER PRIMARY KEY, lead_tutor_id TEXT, is_active "
    "INTEGER DEFAULT 1)",
    "CREATE TABLE tutor_group_members (membership_id INTEGER PRIMARY KEY, group_id INTEGER, "
    "student_id TEXT, is_active INTEGER DEFAULT 1)",
    "CREATE TABLE course_evaluations (evaluation_id INTEGER PRIMARY KEY, module_code TEXT, "
    "is_active INTEGER DEFAULT 1, deleted_at TEXT)",
]
CORE = ["CS101", "CS102", "CS103"]
OPTIONS = ["CS151", "CS152", "CS153"]


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    for ddl in SCHEMA:
        c.execute(ddl)
    for code in CORE + OPTIONS + ["ACC101"]:
        c.execute("INSERT INTO modules (module_code, module_name, credits, course) VALUES "
                  "(?, ?, 20, 'CS')", (code, f"Module {code}"))
    c.executemany("INSERT INTO course_curriculum (course_code, year, module_code) VALUES "
                  "('CS', 1, ?)", [(m,) for m in CORE + OPTIONS])
    c.executemany("INSERT INTO students (student_id, first_name, last_name, status, course, "
                  "year_of_study) VALUES (?, ?, 'Test', ?, ?, 1)",
                  [("S1", "Ana", "Active", "CS"), ("S2", "Bo", "Withdrawn", "CS"),
                   ("S3", "Cy", "Active", "Computer Science")])
    c.executemany("INSERT INTO users (username, role, student_id) VALUES (?, ?, ?)",
                  [("S1", "student", "S1"), ("tutor1", "staff", None), ("other", "staff", None)])
    c.execute("INSERT INTO tutor_groups (group_id, lead_tutor_id) VALUES (1, 'tutor1')")
    c.execute("INSERT INTO tutor_group_members (group_id, student_id) VALUES (1, 'S1')")
    for code in OPTIONS:
        me.set_designation(c, code, "CS", "optional", 1, "admin")
    c.commit()
    yield c
    c.close()


def _status(conn, sid, code):
    row = conn.execute("SELECT status FROM student_modules WHERE student_id = ? AND "
                       "module_code = ?", (sid, code)).fetchone()
    return row[0] if row else None


def test_structure_curriculum_minus_options_and_course_by_name(conn):
    plan = mr.structure(conn, "CS", 1)
    assert [m["code"] for m in plan["compulsory"]] == CORE
    assert [m["code"] for m in plan["optional"]] == OPTIONS
    assert mr.student(conn, "S3")["course"] == "CS"


def test_only_active_students_register_and_compulsory_is_automatic(conn):
    with pytest.raises(ValueError, match="Withdrawn"):
        mr.enrol(conn, "S2", "CS101", "admin", staff=True, override="x")
    assert mr.enrol_compulsory(conn, "S1", "S1") == {c: "enrolled" for c in CORE}
    assert conn.execute("SELECT COUNT(*) FROM module_enrolments WHERE student_id = 'S1' AND "
                        "status = 'enrolled'").fetchone() == (3,)


def test_off_structure_needs_staff_override_which_is_logged(conn):
    with pytest.raises(ValueError, match="not part of CS year 1"):
        mr.enrol(conn, "S1", "ACC101", "S1")
    assert mr.enrol(conn, "S1", "ACC101", "admin", staff=True,
                    override="Elective agreed")["result"] == "enrolled"
    assert "Elective agreed" in conn.execute(
        "SELECT note FROM enrolment_status_changes WHERE module_code = 'ACC101'").fetchone()[0]


def test_compulsory_cannot_be_dropped_by_the_student(conn):
    mr.enrol_compulsory(conn, "S1", "S1")
    with pytest.raises(ValueError, match="compulsory"):
        mr.drop(conn, "S1", "CS101", "S1")
    assert mr.drop(conn, "S1", "CS101", "admin", staff=True, reason="Exempt") == "Dropped"
    assert _status(conn, "S1", "CS101") == "Dropped"
    assert conn.execute("SELECT status FROM module_enrolments WHERE module_code = 'CS101'"
                        ).fetchone() == ("dropped",)


def test_choices_respect_limits_and_need_the_tutors_approval(conn):
    ma.set_rules(conn, "CS", 1, max_credits=200, min_optional=1, max_optional=2, admin=True)
    for codes, msg in ((OPTIONS, "at most 2"), (["CS101"], "Not optional"), ([], "at least 1")):
        with pytest.raises(ValueError, match=msg):
            mr.submit_choices(conn, "S1", codes, "S1")
    sub = mr.submit_choices(conn, "S1", ["CS151", "CS152"], "S1")
    assert sub["status"] == "submitted" and _status(conn, "S1", "CS151") is None
    assert [s["id"] for s in mr.submissions(conn, "tutor1")] == [sub["submission_id"]]
    assert mr.submissions(conn, "other") == []
    with pytest.raises(ValueError, match="personal tutor"):
        mr.decide(conn, sub["submission_id"], True, "other")
    result = mr.decide(conn, sub["submission_id"], True, "tutor1")
    assert result["results"] == {"CS151": "enrolled", "CS152": "enrolled"}
    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone() == (1,)


def test_rejection_needs_a_reason_and_no_approval_courses_enrol_at_once(conn):
    sub = mr.submit_choices(conn, "S1", ["CS151"], "S1")
    with pytest.raises(ValueError, match="Say why"):
        mr.decide(conn, sub["submission_id"], False, "tutor1")
    assert mr.decide(conn, sub["submission_id"], False, "tutor1", note="Clash")["status"] \
        == "rejected"
    ma.set_rules(conn, "CS", 1, needs_approval=False, admin=True)
    assert mr.submit_choices(conn, "S1", ["CS153"], "S1")["results"] == {"CS153": "enrolled"}


def test_credit_maximum_and_full_modules(conn):
    ma.set_rules(conn, "CS", 1, target_credits=40, max_credits=60, admin=True)
    mr.enrol_compulsory(conn, "S1", "S1")                       # 60 credits
    with pytest.raises(ValueError, match="over the 60 maximum"):
        mr.enrol(conn, "S1", "CS151", "S1")
    conn.execute("UPDATE modules SET capacity = 1 WHERE module_code = 'CS101'")  # S1 has it
    assert mr.enrol(conn, "S3", "CS101", "S3")["result"] == "waitlisted"
    assert conn.execute("SELECT status FROM module_waitlist WHERE student_id = 'S3'"
                        ).fetchone() == ("waiting",)


def test_registration_period_and_deadlines(conn):
    today = date.today()
    with pytest.raises(ValueError, match="close after it opens"):
        ma.add_period(conn, academic_year="x", opens=today.isoformat(),
                      closes=(today - timedelta(days=1)).isoformat(), admin=True)
    with pytest.raises(ValueError, match="admin"):
        ma.add_period(conn, academic_year="x", opens="2026-01-01", closes="2026-02-01")
    mr.enrol(conn, "S1", "CS151", "admin", staff=True)
    ma.add_period(conn, academic_year=mr.academic_year(),
                  opens=(today - timedelta(days=60)).isoformat(),
                  closes=(today - timedelta(days=1)).isoformat(),
                  drop_deadline=(today - timedelta(days=30)).isoformat(),
                  withdraw_deadline=(today - timedelta(days=5)).isoformat(), admin=True)
    with pytest.raises(ValueError, match="closed"):
        mr.submit_choices(conn, "S1", ["CS152"], "S1")
    with pytest.raises(ValueError, match="withdrawal deadline"):
        mr.drop(conn, "S1", "CS151", "S1")


def test_module_enrolments_are_reconciled_with_student_modules(conn):
    conn.execute("INSERT INTO student_modules (student_id, module_code, status) VALUES "
                 "('S1', 'CS101', 'Enrolled')")
    conn.execute("INSERT INTO module_enrolments (student_id, module_code, academic_year, "
                 "status, effective_from) VALUES ('S1', 'CS102', 'legacy', 'enrolled', 'x')")
    found = {(m["module_code"], m["fix"].split()[0]) for m in ma.mismatches(conn)}
    assert found == {("CS101", "add"), ("CS102", "mark")}
    assert ma.fix_mismatches(conn, "admin", admin=True) == 2
    assert ma.mismatches(conn) == []


def test_module_credits_are_set_by_admins_with_history(conn):
    conn.execute("UPDATE modules SET credits = 0 WHERE module_code = 'CS101'")
    assert [m["module_code"] for m in ma.modules_without_credits(conn)] == ["CS101"]
    with pytest.raises(ValueError, match="admin"):
        ma.set_credits(conn, ["CS101"], 20, "x")
    assert ma.set_credits(conn, ["CS101"], 20, "admin", admin=True) == 1
    assert conn.execute("SELECT new_value FROM module_change_history WHERE module_code = "
                        "'CS101'").fetchone() == ("20",)


def test_year_of_study_inferred_from_enrolment_date(conn):
    conn.execute("UPDATE students SET year_of_study = NULL, enrollment_date = ? WHERE "
                 "student_id = 'S1'", (f"{mr.academic_year()[:4]}-07-01",))
    assert mr.student(conn, "S1")["year_of_study"] == 1


def test_ensure_inside_a_transaction_does_not_commit(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    for ddl in SCHEMA:
        c.execute(ddl)
    c.commit()
    c.execute("INSERT INTO students (student_id, status) VALUES ('P1', 'Active')")
    mr.ensure(c)
    c.rollback()
    assert c.execute("SELECT COUNT(*) FROM students").fetchone() == (0,)
    c.close()
