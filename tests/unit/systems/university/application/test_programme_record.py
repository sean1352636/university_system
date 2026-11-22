"""Programme record rules: specification, exit awards, progression, fees,
intake, examiners, structure, curriculum map, cohort and closure guard.
In-memory database built here."""

import sqlite3

import pytest

from education_system.systems.university.application.modules import enrolment as module_enrolment
from education_system.systems.university.application.programmes import record
from education_system.systems.university.application.programmes import structure

SCHEMA = [
    """CREATE TABLE courses (id TEXT PRIMARY KEY, code TEXT, name TEXT, course_code TEXT,
        course_name TEXT, level TEXT, credits INTEGER, credit_hours INTEGER, duration TEXT,
        status TEXT, department TEXT, current_enrollment INTEGER)""",
    """CREATE TABLE modules (module_id INTEGER PRIMARY KEY, module_code TEXT, module_name TEXT,
        credits INTEGER, course TEXT, year TEXT, is_active INTEGER DEFAULT 1, level INTEGER,
        module_type TEXT)""",
    "CREATE TABLE course_curriculum (id INTEGER PRIMARY KEY, course_code TEXT, year INTEGER, "
    "module_code TEXT, module_name TEXT)",
    """CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT,
        course TEXT, year_of_study INTEGER, year INTEGER, status TEXT, is_active INTEGER DEFAULT 1,
        mode_of_study TEXT, enrollment_date TEXT, registration_datetime TEXT)""",
    """CREATE TABLE student_modules (id INTEGER PRIMARY KEY, student_id TEXT, module_code TEXT,
        module_type TEXT, module_name TEXT, credits_earned INTEGER, status TEXT, grade TEXT)""",
    """CREATE TABLE module_grades (id INTEGER PRIMARY KEY, student_id TEXT, module_code TEXT,
        final_score REAL, final_grade TEXT, completion_date TEXT, date_recorded TEXT)""",
    "CREATE TABLE fee_types (fee_type_id INTEGER PRIMARY KEY, fee_name TEXT, is_active INTEGER)",
    """CREATE TABLE program_fees (program_fee_id INTEGER PRIMARY KEY, fee_type_id INTEGER,
        course TEXT, amount REAL, currency TEXT, academic_year TEXT, created_at TEXT,
        updated_at TEXT)""",
    """CREATE TABLE admission_applications (application_id INTEGER PRIMARY KEY,
        program_applied TEXT, academic_year TEXT, status TEXT)""",
    "CREATE TABLE external_examiners (examiner_id INTEGER PRIMARY KEY, name TEXT, "
    "institution TEXT, status TEXT DEFAULT 'active')",
    """CREATE TABLE course_learning_outcomes (id INTEGER PRIMARY KEY, course_code TEXT,
        outcome_code TEXT, description TEXT)""",
    "CREATE TABLE learning_outcomes (outcome_id INTEGER PRIMARY KEY, module_code TEXT, "
    "outcome_code TEXT)",
    """CREATE TABLE governed_programmes (programme_id INTEGER PRIMARY KEY, programme_code TEXT
        UNIQUE, programme_name TEXT, owning_school TEXT, award_type TEXT, status TEXT,
        created_by TEXT)""",
    "CREATE TABLE programme_governance_history (history_id INTEGER PRIMARY KEY, "
    "programme_id INTEGER, action TEXT, actor_id TEXT, reason TEXT)",
    "CREATE TABLE programme_teach_out_plans (plan_id INTEGER PRIMARY KEY, programme_id INTEGER)",
]


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    for ddl in SCHEMA:
        c.execute(ddl)
    c.execute("INSERT INTO courses VALUES ('CS', 'CS', 'Computer Science', 'CS', "
              "'Computer Science', 'Undergraduate', 360, 360, '3 years', 'active', 'Computing', 5)")
    c.executemany("INSERT INTO modules (module_code, module_name, credits, course, year, level) "
                  "VALUES (?, ?, ?, 'CS', ?, ?)",
                  [("CS101", "Programming", 60, "1", 4), ("CS102", "Maths", 60, "1", 4),
                   ("CS201", "Algorithms", 120, "2", 5)])
    c.executemany("INSERT INTO course_curriculum (course_code, year, module_code) VALUES (?, ?, ?)",
                  [("CS", 1, "CS101"), ("CS", 1, "CS102"), ("CS", 2, "CS201")])
    c.executemany("INSERT INTO students (student_id, first_name, course, status, enrollment_date) "
                  "VALUES (?, ?, ?, ?, ?)",
                  [("S1", "Ann", "CS", "Active", "2024-09-20"),
                   ("S2", "Bob", "Computer Science", "Active", "2024-09-20"),
                   ("S3", "Cy", "CS", "Withdrawn", "2024-09-20"),
                   ("S4", "Di", "Mathematics", "Active", "2025-09-20")])
    c.executemany("INSERT INTO student_modules (student_id, module_code, status) VALUES (?, ?, ?)",
                  [("S1", "CS101", "Completed"), ("S1", "CS102", "Completed")])
    c.executemany("INSERT INTO module_grades (student_id, module_code, final_score, final_grade) "
                  "VALUES (?, ?, ?, ?)", [("S1", "CS101", 65, "B"), ("S1", "CS102", 35, "F")])
    c.executemany("INSERT INTO fee_types VALUES (?, ?, 1)",
                  [(1, "Undergraduate Tuition"), (2, "Graduate Tuition"),
                   (3, "International Student Tuition")])
    c.commit()
    yield c
    c.close()


def test_spec_validation_and_save(conn):
    changed = record.save_spec(conn, "CS", {"ucas_code": "g400", "hecos_code": "100366",
                                            "mode_of_study": "full-time"}, "admin")
    assert changed["ucas_code"] == (None, "G400")
    for bad in ({"ucas_code": "G4"}, {"hecos_code": "1"}, {"pass_mark": 101},
                {"mode_of_study": "evenings"}, {"nonsense": 1}):
        with pytest.raises(ValueError):
            record.save_spec(conn, "CS", bad, "admin")
    assert record.save_spec(conn, "CS", {"ucas_code": "G400"}, "admin") == {}


def test_standard_exit_awards_and_eligibility(conn):
    assert record.use_standard_exit_awards(conn, "CS") == 4
    assert record.use_standard_exit_awards(conn, "CS") == 0
    assert record.eligible_exit_award(conn, "S1", "CS") is None          # 60 credits earned
    conn.execute("UPDATE module_grades SET final_score = 70, final_grade = 'A' "
                 "WHERE module_code = 'CS102'")
    assert record.eligible_exit_award(conn, "S1", "CS")["award_name"] == \
        "Certificate of Higher Education"


def test_progression_with_and_without_compensation(conn):
    with pytest.raises(ValueError, match="no progression rule"):
        record.progression(conn, "S1", "CS", 1)
    record.use_standard_progression(conn, "CS", "admin")
    assert record.progression(conn, "S1", "CS", 1)["outcome"] == "resit required"
    record.save_spec(conn, "CS", {"max_compensated_credits": 60}, "admin")
    assert record.progression(conn, "S1", "CS", 1)["outcome"] == "progress with compensation"
    conn.execute("UPDATE module_grades SET final_score = 20 WHERE module_code = 'CS102'")
    assert record.progression(conn, "S1", "CS", 1)["outcome"] == "resit required"
    assert record.progression(conn, "S1", "CS", 2)["outcome"] == "no results for this year"


def test_fees_go_to_finance_and_update_in_place(conn):
    record.set_fee(conn, "CS", "2026/27", "home", 9535)
    record.set_fee(conn, "CS", "2026/27", "home", 9790)
    record.set_fee(conn, "CS", "2026/27", "international", 21000)
    fees = {(f["fee_status"], f["amount"]) for f in record.fees(conn, "CS")}
    assert fees == {("home", 9790), ("international", 21000)}
    with pytest.raises(ValueError):
        record.set_fee(conn, "CS", "26-27x", "home", 1)


def test_intake_counts_name_or_code_and_merges_year_spellings(conn):
    conn.executemany("INSERT INTO admission_applications (program_applied, academic_year, status) "
                     "VALUES (?, ?, ?)", [("Computer Science", "2024", "offer_made"),
                                          ("CS", "2024", "enrolled"), ("Law", "2024", "enrolled")])
    record.set_intake_target(conn, "CS", "2024/25", 4)
    (row,) = record.intake_report(conn, "CS")
    assert (row["academic_year"], row["applications"], row["offers"], row["accepted"],
            row["started"], row["against_target"]) == ("2024/25", 2, 2, 1, 3, 75)


def test_examiner_term_report_then_response(conn):
    conn.execute("INSERT INTO external_examiners (name) VALUES ('Dr X')")
    with pytest.raises(ValueError, match="at most 4 years"):
        record.appoint_examiner(conn, "CS", 1, "2026-09-01", "2031-09-01")
    aid = record.appoint_examiner(conn, "CS", 1, "2026-09-01", "2030-08-31", "2020-01-01")
    assert record.examiners(conn, "CS")[0]["report_overdue"]
    with pytest.raises(ValueError, match="report before"):
        record.record_response(conn, aid, "noted", "admin")
    record.record_report(conn, aid, "fine")
    assert record.examiners(conn, "CS")[0]["response_outstanding"]


def test_structure_designations_and_credit_checks(conn):
    module_enrolment.set_designation(conn, "CS101", "CS", "core", 1)
    module_enrolment.set_designation(conn, "CS102", "CS", "optional", 1)
    year1 = structure.stages(conn, "CS")[0]
    assert (year1["year"], year1["required_credits"], year1["offered_credits"]) == (1, 60, 120)
    assert year1["issues"] == []


def test_curriculum_map_and_gaps(conn):
    oid = conn.execute("INSERT INTO course_learning_outcomes (course_code, outcome_code, "
                       "description) VALUES ('CS', 'PLO1', 'Build software')").lastrowid
    structure.map_outcome(conn, oid, "CS101", "introduced")
    assert "PLO1 is never assessed" in structure.curriculum_map(conn, "CS")["gaps"]
    structure.map_outcome(conn, oid, "CS201", "assessed")
    gaps = structure.curriculum_map(conn, "CS")["gaps"]
    assert "PLO1 is never assessed" not in gaps and "CS102 serves no programme outcome" in gaps
    with pytest.raises(ValueError, match="not part of"):
        structure.map_outcome(conn, oid, "LAW101", "assessed")


def test_cohort_counts_and_name_fix(conn):
    assert {r["student_id"] for r in structure.cohort(conn, "CS")} == {"S1", "S2", "S3"}
    assert structure.live_counts(conn)["CS"] == (2, 5)
    assert structure.refresh_counters(conn) == 1
    plan = structure.name_fix_plan(conn)
    assert plan == {"fix": [("S2", "Computer Science", "CS")], "unknown": [("S4", "Mathematics")]}
    assert structure.apply_name_fix(conn, plan) == 1


def test_cohort_outcomes(conn):
    (row,) = structure.cohort_outcomes(conn, "CS")
    assert (row["started"], row["left"], row["continuation_pct"]) == (3, 1, 66.7)


def test_closure_needs_a_teach_out_plan_while_students_remain(conn):
    assert "2 student(s)" in record.closure_blocker(conn, "CS", "archived")
    assert record.closure_blocker(conn, "CS", "active") is None
    pid = record.register_for_governance(conn, "CS", "admin")
    assert record.register_for_governance(conn, "CS", "admin") == pid
    conn.execute("INSERT INTO programme_teach_out_plans (programme_id) VALUES (?)", (pid,))
    assert record.closure_blocker(conn, "CS", "archived") is None


def test_missing_progression_rule_is_filled_without_touching_what_is_set(conn):
    assert not record.has_progression_rule(conn, "CS")
    record.save_spec(conn, "CS", {"pass_mark": 50, "award_title": "BSc CS"}, "admin")
    assert not record.has_progression_rule(conn, "CS")
    record.fill_progression_rule(conn, "CS", "admin")
    assert record.has_progression_rule(conn, "CS")
    spec = record.get_spec(conn, "CS")
    assert spec["pass_mark"] == 50 and spec["award_title"] == "BSc CS"
    assert spec["progression_credits"] == record.STANDARD_PROGRESSION["progression_credits"]
    assert record.fill_progression_rule(conn, "CS", "admin") == {}
