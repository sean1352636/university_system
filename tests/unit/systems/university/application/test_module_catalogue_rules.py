"""Module catalogue rules: specification and change control, designations,
exclusions, waitlist, cohorts, teaching team, deliveries, timetable and the
credit / level fill. Runs on an in-memory database built here."""

import sqlite3

import pytest

from education_system.systems.university.application.modules import delivery
from education_system.systems.university.application.modules import enrolment
from education_system.systems.university.application.modules import specification as spec

SCHEMA = [
    """CREATE TABLE modules (module_id INTEGER PRIMARY KEY AUTOINCREMENT, module_code TEXT,
        module_name TEXT, module_type TEXT, credits INTEGER DEFAULT 0, semester TEXT, year TEXT,
        course TEXT, department TEXT, instructor TEXT, instructor_id INTEGER, capacity INTEGER,
        is_active INTEGER DEFAULT 1, description TEXT, updated_at TEXT)""",
    """CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT,
        course TEXT, program TEXT, year_of_study INTEGER, year INTEGER,
        is_active INTEGER DEFAULT 1, status TEXT DEFAULT 'Active')""",
    """CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        last_name TEXT, role TEXT)""",
    """CREATE TABLE courses (id INTEGER PRIMARY KEY, code TEXT, name TEXT, course_code TEXT,
        course_name TEXT, credits INTEGER, credit_hours INTEGER)""",
    """CREATE TABLE student_modules (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT,
        module_code TEXT, enrollment_date TEXT, status TEXT DEFAULT 'Enrolled',
        module_name TEXT, grade TEXT, semester TEXT, year TEXT,
        UNIQUE(student_id, module_code))""",
    """CREATE TABLE module_grades (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT,
        module_code TEXT, final_score REAL, final_grade TEXT)""",
    """CREATE TABLE degree_course_prerequisites (prerequisite_id INTEGER PRIMARY KEY
        AUTOINCREMENT, module_code TEXT NOT NULL, prerequisite_module_code TEXT NOT NULL,
        min_grade TEXT, is_corequisite INTEGER DEFAULT 0, created_at TEXT)""",
    """CREATE TABLE academic_terms (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE,
        academic_year TEXT DEFAULT '', start_date TEXT, end_date TEXT)""",
    """CREATE TABLE course_sections (id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL, term_id INTEGER NOT NULL, section_number TEXT NOT NULL,
        instructor TEXT DEFAULT '', capacity INTEGER NOT NULL DEFAULT 30,
        enrolled INTEGER NOT NULL DEFAULT 0, delivery_mode TEXT NOT NULL DEFAULT 'In Person',
        location TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'Open', notes TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')),
        UNIQUE(course_code, term_id, section_number))""",
    """CREATE TABLE learning_outcomes (outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
        outcome_code TEXT NOT NULL, description TEXT NOT NULL, category TEXT, level INTEGER,
        module_code TEXT, code TEXT, bloom_level TEXT, outcome_type TEXT)""",
    """CREATE TABLE external_examiners (examiner_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, institution TEXT, appointment_end TEXT,
        status TEXT DEFAULT 'active')""",
    """CREATE TABLE rooms (id INTEGER PRIMARY KEY, room_number TEXT, building TEXT,
        room_name TEXT, capacity INTEGER, is_active INTEGER DEFAULT 1)""",
    """CREATE TABLE instructors (id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT,
        is_active INTEGER DEFAULT 1)""",
    """CREATE TABLE module_schedule (id INTEGER PRIMARY KEY AUTOINCREMENT, module_code TEXT,
        day_of_week TEXT, start_time TEXT, end_time TEXT, room_id INTEGER,
        instructor_id INTEGER, session_type TEXT, semester TEXT, year INTEGER,
        status TEXT DEFAULT 'published', recurrence TEXT, recurrence_until TEXT,
        modified_date TEXT)""",
]


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    for ddl in SCHEMA:
        c.execute(ddl)
    c.executemany("INSERT INTO modules (module_code, module_name, credits, course, year) "
                  "VALUES (?, ?, ?, 'CS', ?)",
                  [("CS101", "Programming", 20, "1"), ("CS102", "Maths", 20, "1"),
                   ("CS201", "Algorithms", 0, "2")])
    c.executemany("INSERT INTO students (student_id, first_name, course, year_of_study) "
                  "VALUES (?, ?, 'CS', ?)", [("S1", "Ann", 1), ("S2", "Bob", 1), ("S3", "Cy", 2)])
    c.executemany("INSERT INTO users (id, username, first_name, last_name, role) "
                  "VALUES (?, ?, ?, ?, ?)",
                  [(1, "admin", "Ad", "Min", "admin"), (2, "lead", "Lee", "Der", "staff"),
                   (3, "S1", "Ann", "", "student")])
    c.execute("INSERT INTO courses (code, name, credits) VALUES ('CS', 'Computer Science', 60)")
    c.execute("INSERT INTO academic_terms (name, academic_year, start_date, end_date) "
              "VALUES ('Spring', '2026/27', '2027-01-15', '2027-05-31')")
    c.commit()
    yield c
    c.close()


def _enrolled(c, code):
    return {r[0] for r in c.execute("SELECT student_id FROM student_modules WHERE module_code = ? "
                                    "AND status = 'Enrolled'", (code,))}


# ── specification & change control ─────────────────────────────────────


def test_applied_changes_are_recorded_field_by_field(conn):
    changed = spec.apply_changes(conn, "CS101", {"credits": 30, "spec.aims": "Learn to code",
                                                 "module_name": "Programming"}, "admin")
    assert set(changed) == {"credits", "spec.aims"}  # the unchanged name is not logged
    log = {h["field"]: h for h in spec.history(conn, "CS101")}
    assert log["credits"]["old_value"] == "20" and log["credits"]["new_value"] == "30"
    assert spec.get_spec(conn, "CS101")["aims"] == "Learn to code"


def test_validation_refuses_bad_values(conn):
    with pytest.raises(ValueError, match="Level"):
        spec.apply_changes(conn, "CS101", {"level": 9}, "admin")
    with pytest.raises(ValueError, match="cannot be changed"):
        spec.apply_changes(conn, "CS101", {"module_code": "X"}, "admin")


def test_proposal_needs_another_person_and_an_unchanged_module(conn):
    rid = spec.propose_change(conn, "CS101", {"capacity": 40}, "lead", "more places")
    with pytest.raises(ValueError, match="proposed it"):
        spec.decide_request(conn, rid, True, "lead")
    spec.apply_changes(conn, "CS101", {"capacity": 35}, "admin")
    with pytest.raises(ValueError, match="changed since"):
        spec.decide_request(conn, rid, True, "admin")
    assert spec.decide_request(conn, rid, False, "admin", "superseded")["status"] == "rejected"


def test_approval_applies_and_links_history_to_the_request(conn):
    rid = spec.propose_change(conn, "CS101", {"capacity": 40}, "lead", "more places")
    spec.decide_request(conn, rid, True, "admin")
    assert conn.execute("SELECT capacity FROM modules WHERE module_code = 'CS101'"
                        ).fetchone()[0] == 40
    assert spec.history(conn, "CS101")[0]["request_id"] == rid


def test_assessment_plan_cannot_pass_100_and_must_name_real_outcomes(conn):
    spec.add_outcome(conn, "CS101", "Write programs")
    spec.add_component(conn, "CS101", "Exam", "Exam", 60, outcomes="LO1")
    with pytest.raises(ValueError, match="100%"):
        spec.add_component(conn, "CS101", "CW", "Coursework", 50)
    with pytest.raises(ValueError, match="LO9"):
        spec.add_component(conn, "CS101", "CW", "Coursework", 40, outcomes="LO9")


def test_spec_issues_check_notional_hours(conn):
    spec.apply_changes(conn, "CS101", {"spec.contact_hours": 40,
                                       "spec.independent_study_hours": 100}, "admin")
    assert any("200 notional hours" in i for i in spec.spec_issues(conn, "CS101"))


# ── designations, exclusions ────────────────────────────────────────────


def test_designation_and_year_credit_check(conn):
    enrolment.set_designation(conn, "CS101", "CS", "core", 1)
    assert enrolment.designations(conn, "CS101")["CS"]["category"] == "core"
    assert enrolment.programme_credit_issues(conn, "CS") == [
        "CS year 1: only 20 credits designated, a year needs 120"]
    with pytest.raises(ValueError):
        enrolment.set_designation(conn, "CS101", "CS", "elective", 1)


def test_exclusion_blocks_enrolment_both_ways(conn):
    enrolment.add_exclusion(conn, "CS101", "CS102", "overlap")
    enrolment.enrol(conn, "CS102", "S1")
    blocks = [b.kind for b in enrolment.eligibility(conn, "CS101", "S1").blocks]
    assert blocks == ["exclusion"]
    with pytest.raises(ValueError, match="already exclude"):
        enrolment.add_exclusion(conn, "CS102", "CS101")


def test_withdrawn_enrolment_does_not_trigger_an_exclusion(conn):
    enrolment.add_exclusion(conn, "CS101", "CS102")
    enrolment.enrol(conn, "CS102", "S1")
    enrolment.withdraw(conn, "CS102", "S1")
    assert enrolment.eligibility(conn, "CS101", "S1").ok


# ── waitlist & cohorts ──────────────────────────────────────────────────


def test_full_module_waitlists_and_a_freed_place_is_promoted(conn):
    conn.execute("UPDATE modules SET capacity = 1 WHERE module_code = 'CS101'")
    result = enrolment.bulk_enrol(conn, "CS101", ["S1", "S2"])
    assert result["enrolled"] == ["S1"] and result["waitlisted"] == [("S2", 1)]
    moved = enrolment.bulk_withdraw(conn, "CS101", ["S1"], "admin")
    assert moved == {"withdrawn": ["S1"], "promoted": ["S2"]}
    assert _enrolled(conn, "CS101") == {"S2"}
    assert enrolment.waitlist(conn, "CS101") == []


def test_promotion_skips_a_waiting_student_who_fails_another_rule(conn):
    conn.execute("UPDATE modules SET capacity = 1 WHERE module_code = 'CS101'")
    enrolment.enrol(conn, "CS101", "S3")
    enrolment.join_waitlist(conn, "CS101", "S1")
    enrolment.join_waitlist(conn, "CS101", "S2")
    enrolment.add_exclusion(conn, "CS101", "CS102")
    enrolment.enrol(conn, "CS102", "S1")
    enrolment.withdraw(conn, "CS101", "S3")
    promoted = enrolment.promote_next(conn, "CS101", "admin")
    assert promoted["student_id"] == "S2" and promoted["skipped"][0][0] == "S1"
    assert [w["student_id"] for w in enrolment.waitlist(conn, "CS101")] == ["S1"]


def test_any_enrolment_clears_the_students_waiting_entry(conn):
    conn.execute("UPDATE modules SET capacity = 1 WHERE module_code = 'CS101'")
    enrolment.enrol(conn, "CS101", "S3")
    enrolment.join_waitlist(conn, "CS101", "S1")
    enrolment.bulk_enrol(conn, "CS101", ["S1"], override=True)
    assert enrolment.waitlist(conn, "CS101") == []


def test_cohort_by_programme_and_year(conn):
    assert [s["student_id"] for s in enrolment.cohort(conn, "CS", 1)] == ["S1", "S2"]
    assert len(enrolment.cohort(conn, "Computer Science")) == 0  # code, not name, is the key
    assert len(enrolment.cohort(conn, "CS")) == 3


# ── team, deliveries, timetable, fill ───────────────────────────────────


def test_one_leader_mirrored_into_the_module_record(conn):
    delivery.add_member(conn, "CS101", "lead", "leader", 40)
    assert tuple(conn.execute("SELECT instructor, instructor_id FROM modules WHERE module_code = "
                        "'CS101'").fetchone()) == ("lead", 2)
    with pytest.raises(ValueError, match="already leads"):
        delivery.add_member(conn, "CS101", "admin", "leader")
    with pytest.raises(ValueError, match="No staff account"):
        delivery.add_member(conn, "CS101", "S1", "tutor")
    assert delivery.workload(conn, "lead")["total_hours"] == 40


def test_delivery_makes_enrolment_choose_a_section(conn):
    section = delivery.add_delivery(conn, "CS101", 1, 1)
    kinds = [b.kind for b in enrolment.eligibility(conn, "CS101", "S1").blocks]
    assert kinds == ["section_required"]
    enrolment.enrol(conn, "CS101", "S1", section)
    row = conn.execute("SELECT section_id, semester FROM student_modules WHERE student_id = "
                       "'S1'").fetchone()
    assert tuple(row) == (section, "Spring")
    with pytest.raises(ValueError, match="enrolled"):
        delivery.update_delivery(conn, "CS101", section, status="Cancelled")


def test_timetable_clashes(conn):
    conn.execute("INSERT INTO rooms (id, room_number) VALUES (1, 'A1')")
    delivery.add_slot(conn, "CS102", "Monday", "09:00", "11:00", room_id=1)
    with pytest.raises(ValueError, match="room"):
        delivery.add_slot(conn, "CS101", "Monday", "10:00", "12:00", room_id=1)
    assert delivery.add_slot(conn, "CS101", "Monday", "11:00", "12:00", room_id=1)
    with pytest.raises(ValueError, match="end after"):
        delivery.add_slot(conn, "CS101", "Tuesday", "12:00", "11:00")


def test_fill_plan_derives_credits_and_level(conn):
    plan = {p["module_code"]: p for p in delivery.fill_plan(conn)}
    assert plan["CS201"]["credits"] == 20      # 60 programme credits / 3 modules
    assert plan["CS101"]["level"] == 4 and "credits" not in plan["CS101"]
    assert delivery.apply_fill(conn, list(plan.values()), "admin") == 3
    assert delivery.fill_plan(conn) == []
