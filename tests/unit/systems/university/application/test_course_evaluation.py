"""Course evaluation surveys: eligibility, one response each, anonymity,
window, threshold, course-team access, screening, reminders, closing the
loop, frozen questions, branching, legacy anonymising and teaching history.
In-memory database."""

import sqlite3
from datetime import date, datetime, timedelta

import pytest

from education_system.systems.university.application.evaluation import course as ce
from education_system.systems.university.application.evaluation import module as me
from education_system.systems.university.infrastructure.database.schemas import (
    course_evaluation_schema,
)

SCHEMA = [
    "CREATE TABLE courses (id INTEGER PRIMARY KEY, code TEXT, name TEXT, course_code TEXT, "
    "course_name TEXT, department TEXT)",
    "CREATE TABLE students (student_id TEXT PRIMARY KEY, email_address TEXT, course TEXT, "
    "status TEXT, is_active INTEGER DEFAULT 1)",
    "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT, "
    "email TEXT, role TEXT, student_id TEXT)",
    "CREATE TABLE modules (module_code TEXT, module_name TEXT, department TEXT, course TEXT, "
    "semester TEXT, instructor TEXT, instructor_id INTEGER, is_active INTEGER DEFAULT 1)",
    "CREATE TABLE student_modules (student_id TEXT, module_code TEXT, status TEXT)",
    "CREATE TABLE academic_terms (id INTEGER PRIMARY KEY, name TEXT, start_date TEXT, end_date TEXT)",
    """CREATE TABLE messages (id INTEGER PRIMARY KEY, sender_id INTEGER, recipient_id INTEGER,
        subject TEXT, message TEXT, content TEXT, is_read INTEGER, sent_at TEXT)""",
    """CREATE TABLE evaluation_templates (template_id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_name TEXT NOT NULL, template_type TEXT NOT NULL DEFAULT 'student',
        description TEXT, created_by TEXT, created_at TEXT, is_active INTEGER DEFAULT 1,
        is_default INTEGER DEFAULT 0, deleted_at TEXT)""",
    """CREATE TABLE evaluation_questions (question_id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER NOT NULL, question_text TEXT NOT NULL, question_type TEXT NOT NULL,
        question_category TEXT, scale_min INTEGER, scale_max INTEGER, display_order INTEGER,
        is_required INTEGER DEFAULT 1, options TEXT, options_json TEXT, bank_id INTEGER,
        parent_question_id INTEGER, show_if_value TEXT, show_if_op TEXT, aria_label TEXT)""",
    """CREATE TABLE course_evaluations (evaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_code TEXT NOT NULL, academic_year TEXT NOT NULL, semester TEXT NOT NULL,
        instructor_id TEXT NOT NULL, template_id INTEGER NOT NULL, start_date TEXT NOT NULL,
        end_date TEXT NOT NULL, response_count INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
        created_at TEXT, completion_rate REAL DEFAULT 0, is_anonymous INTEGER DEFAULT 1,
        deleted_at TEXT)""",
    """CREATE TABLE evaluation_responses (response_id INTEGER PRIMARY KEY AUTOINCREMENT,
        evaluation_id INTEGER NOT NULL, student_id TEXT, is_complete INTEGER DEFAULT 0,
        is_anonymous INTEGER DEFAULT 1, time_taken_minutes INTEGER, submitted_at TEXT,
        response_date TEXT)""",
    """CREATE TABLE evaluation_answers (answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        response_id INTEGER NOT NULL, question_id INTEGER NOT NULL, answer_value TEXT,
        numeric_value REAL, created_at TEXT)""",
    "CREATE TABLE evaluations (id INTEGER PRIMARY KEY, course_id TEXT, student_id TEXT, "
    "overall INTEGER, comments TEXT, submitted_at TEXT)",
    "CREATE TABLE evaluation_question_bank (bank_id INTEGER PRIMARY KEY, question_text TEXT, "
    "question_type TEXT, question_category TEXT)",
    "CREATE TABLE evaluation_question_tags (tag_id INTEGER PRIMARY KEY, bank_id INTEGER, tag TEXT)",
    """CREATE TABLE instructor_performance_history (performance_id INTEGER PRIMARY KEY,
        instructor_id TEXT NOT NULL, academic_year TEXT NOT NULL, semester TEXT NOT NULL,
        avg_overall_rating REAL, avg_teaching_effectiveness REAL, avg_course_organization REAL,
        avg_student_engagement REAL, total_evaluations INTEGER, total_responses INTEGER,
        calculated_at TEXT)""",
    """CREATE TABLE evaluation_forms (id INTEGER PRIMARY KEY AUTOINCREMENT, module_code TEXT NOT NULL,
        module_name TEXT NOT NULL, academic_year TEXT NOT NULL, semester TEXT,
        status TEXT DEFAULT 'draft', created_by TEXT, created_at TEXT, closes_at TEXT,
        is_anonymous INTEGER DEFAULT 1)""",
    """CREATE TABLE eval_form_questions (id INTEGER PRIMARY KEY AUTOINCREMENT, form_id INTEGER NOT NULL,
        question_text TEXT NOT NULL, question_type TEXT DEFAULT 'rating', options TEXT,
        display_order INTEGER DEFAULT 0, is_required INTEGER DEFAULT 1)""",
    """CREATE TABLE eval_form_responses (id INTEGER PRIMARY KEY AUTOINCREMENT, form_id INTEGER NOT NULL,
        student_hash TEXT NOT NULL, submitted_at TEXT)""",
    """CREATE TABLE eval_form_answers (id INTEGER PRIMARY KEY AUTOINCREMENT, response_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL, rating_value INTEGER, text_value TEXT)""",
]
NOW = datetime(2026, 10, 16, 12)
TODAY = NOW.date()


def _seed(c):
    for ddl in SCHEMA:
        c.execute(ddl)
    c.executemany("INSERT INTO courses (code, name, course_code, course_name, department) "
                  "VALUES (?, ?, ?, ?, 'Computing')",
                  [("CS", "Computer Science", "CS", "Computer Science"),
                   ("DS", "Data Science", "DS", "Data Science")])
    for i in range(1, 8):
        c.execute("INSERT INTO students VALUES (?, ?, ?, 'Active', 1)",
                  (f"S{i}", f"s{i}@uni.ac.uk", "CS" if i % 2 else "Computer Science"))
    c.execute("INSERT INTO students VALUES ('D1', 'd1@uni.ac.uk', 'DS', 'Active', 1)")
    c.execute("INSERT INTO students VALUES ('G1', 'g1@uni.ac.uk', 'CS', 'Graduated', 1)")
    c.executemany("INSERT INTO users (id, username, first_name, last_name, role) VALUES "
                  "(?, ?, ?, ?, ?)", [(1, "admin", "Ad", "Min", "admin"),
                                      (2, "lee", "Jo", "Lee", "staff"),
                                      (3, "kim", "Al", "Kim", "staff"),
                                      (4, "S1", "Sam", "One", "student")])
    c.execute("INSERT INTO modules VALUES ('CS101', 'Programming', 'Computing', 'CS', 'Fall', "
              "'kim', 3, 1)")
    c.execute("INSERT INTO academic_terms VALUES (1, 'Fall 2026', '2026-09-21', '2026-12-11')")
    c.execute("INSERT INTO evaluation_question_bank VALUES (1, 'Support services met my needs.', "
              "'likert', 'support')")


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    _seed(c)
    ce.ensure(c)
    ce.set_team_member(c, "CS", "lee", "leader", actor="admin")
    c.commit()
    yield c
    c.close()


def _open(c, **kw):
    kw.setdefault("opens_at", TODAY - timedelta(days=1))
    kw.setdefault("closes_at", TODAY + timedelta(days=20))
    return ce.open_survey(c, "CS", actor="lee", now=NOW, **kw)["evaluation_id"]


def _answers(c, eid, score, text=""):
    return {q["question_id"]: (text if q["question_type"] == "text" else score)
            for q in ce.questions(c, eid) if q["question_type"] == "text" or
            q["question_type"] in ce.NUMERIC}


def test_only_active_students_on_the_course_are_invited(conn):
    assert ce.students_on(conn, "CS") == ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]
    _open(conn)
    assert conn.execute("SELECT COUNT(*) FROM course_eval_invitations").fetchone()[0] == 7


def test_default_window_is_the_end_of_the_current_term(conn):
    assert ce.default_window(conn, TODAY) == (date(2026, 11, 20), date(2026, 12, 11))


def test_only_the_leader_or_an_admin_opens_it(conn):
    with pytest.raises(ValueError, match="course leader"):
        ce.open_survey(conn, "CS", actor="kim", now=NOW)
    assert ce.open_survey(conn, "CS", actor="admin", admin=True, now=NOW)["invited"] == 7


def test_questions_are_frozen_with_required_overall_and_comments(conn):
    me.set_required(conn, 1, True)
    eid = _open(conn)
    texts = [q["question_text"] for q in ce.questions(conn, eid)]
    assert texts[:5] == list(ce.DEFAULT_CRITERIA)
    assert "Support services met my needs." in texts and ce.COMMENTS in texts
    template = conn.execute("SELECT template_type, is_active FROM evaluation_templates WHERE "
                            "template_id = (SELECT template_id FROM course_evaluations WHERE "
                            "evaluation_id = ?)", (eid,)).fetchone()
    assert template == (ce.SURVEY_TYPE, 0)


def test_one_anonymous_response_per_student(conn):
    eid = _open(conn)
    ce.submit(conn, eid, "S1", _answers(conn, eid, 4), now=NOW)
    token, day = conn.execute("SELECT student_id, submitted_at FROM evaluation_responses"
                              ).fetchone()
    assert token.startswith("tok-") and day == TODAY.isoformat()
    with pytest.raises(ValueError, match="already"):
        ce.submit(conn, eid, "S1", _answers(conn, eid, 4), now=NOW)


def test_other_courses_graduates_and_blank_answers_are_refused(conn):
    eid = _open(conn)
    for student in ("D1", "G1"):
        with pytest.raises(ValueError, match="students on the course"):
            ce.submit(conn, eid, student, _answers(conn, eid, 4), now=NOW)
    with pytest.raises(ValueError, match="Please answer"):
        ce.submit(conn, eid, "S1", {}, now=NOW)
    with pytest.raises(ValueError, match="1 to 5"):
        ce.submit(conn, eid, "S1", _answers(conn, eid, 9), now=NOW)


def test_closed_and_scheduled_surveys_take_no_answers(conn):
    eid = _open(conn, opens_at=TODAY + timedelta(days=2), closes_at=TODAY + timedelta(days=9))
    with pytest.raises(ValueError, match="not open"):
        ce.submit(conn, eid, "S1", _answers(conn, eid, 4), now=NOW)
    assert ce.student_surveys(conn, "S1", now=NOW)[0]["state"] == "scheduled"


def test_results_withheld_until_threshold_and_only_for_the_team(conn):
    eid = _open(conn)
    for sid in ("S1", "S2", "S3", "S4"):
        ce.submit(conn, eid, sid, _answers(conn, eid, 4, "Good"), now=NOW)
    assert ce.results(conn, eid, "lee")["withheld"] is True
    ce.submit(conn, eid, "S5", _answers(conn, eid, 2), now=NOW)
    result = ce.results(conn, eid, "kim")  # leads a module on the course
    assert result["withheld"] is False and result["overall"] == 3.6
    assert result["rate"] == round(5 / 7 * 100, 1)
    assert result["questions"][0]["distribution"][4] == 4
    for outsider in ("S1", "nobody"):
        with pytest.raises(ValueError, match="course team"):
            ce.results(conn, eid, outsider)


def test_flagged_comment_waits_for_release(conn):
    eid = _open(conn)
    for sid in ("S1", "S2", "S3", "S4"):
        ce.submit(conn, eid, sid, _answers(conn, eid, 4), now=NOW)
    assert ce.submit(conn, eid, "S5", _answers(conn, eid, 3, "the tutor is an idiot"),
                     now=NOW)["flagged"] == 1
    assert ce.results(conn, eid, "lee")["comments"] == []
    ce.review_comment(conn, ce.review_queue(conn)[0]["answer_id"], True, "admin")
    assert ce.results(conn, eid, "lee")["comments"] == ["the tutor is an idiot"]


def test_reminders_skip_responders_and_respect_the_interval(conn):
    eid = _open(conn)
    ce.submit(conn, eid, "S1", _answers(conn, eid, 4), now=NOW)
    assert ce.send_reminders(conn, now=NOW + timedelta(days=4))["sent"] == 6
    assert ce.send_reminders(conn, now=NOW + timedelta(days=5))["sent"] == 0


def test_respond_after_close_then_publish_to_invited_students(conn):
    eid = _open(conn)
    with pytest.raises(ValueError, match="closed"):
        ce.respond(conn, eid, "Summary", actor="lee", now=NOW)
    ce.close_survey(conn, eid, "lee", now=NOW)
    rid = ce.respond(conn, eid, "Summary", "Act", "More labs", "Added labs", "lee", now=NOW)
    with pytest.raises(ValueError, match="course leader"):
        ce.publish(conn, rid, "kim")
    assert ce.publish(conn, rid, "lee")["notified"] == 7
    assert ce.published_for_student(conn, "S2")[0]["we_did"] == "Added labs"
    assert ce.published_for_student(conn, "D1") == []


def test_branching_question_only_required_when_shown(conn):
    tid = conn.execute("INSERT INTO evaluation_templates (template_name) VALUES ('B')").lastrowid
    parent = conn.execute("INSERT INTO evaluation_questions (template_id, question_text, "
                          "question_type, display_order) VALUES (?, 'Did you use the lab?', "
                          "'Yes/No', 1)", (tid,)).lastrowid
    conn.execute("INSERT INTO evaluation_questions (template_id, question_text, question_type, "
                 "scale_min, scale_max, display_order, parent_question_id, show_if_value, "
                 "show_if_op) VALUES (?, 'Rate the lab', 'rating', 1, 5, 2, ?, 'Yes', 'eq')",
                 (tid, parent))
    eid = _open(conn, template_id=tid)
    qs = {q["question_text"]: q["question_id"] for q in ce.questions(conn, eid)}
    base = {qs[ce.OVERALL]: 4, qs["Did you use the lab?"]: "No"}
    ce.submit(conn, eid, "S1", base, now=NOW)
    with pytest.raises(ValueError, match="Rate the lab"):
        ce.submit(conn, eid, "S2", dict(base, **{qs["Did you use the lab?"]: "Yes"}), now=NOW)


def test_teaching_history_from_module_surveys(conn):
    conn.execute("INSERT INTO student_modules SELECT student_id, 'CS101', 'Enrolled' FROM "
                 "students WHERE student_id LIKE 'S%'")
    form_id = me.open_survey(conn, "CS101", opens_at="2026-10-01", closes_at="2026-11-30",
                             actor="kim", now=NOW, include_staff=True)["form_id"]
    for sid in ("S1", "S2", "S3", "S4", "S5"):
        me.submit(conn, form_id, sid, {q["id"]: ((None, None) if q["question_type"] == "text"
                                                 else (4, None))
                                       for q in me.questions(conn, form_id)}, now=NOW)
    assert ce.refresh_instructor_history(conn, "2026/2027") == 1
    row = ce.instructor_history(conn, "kim")[0]
    assert (row["avg_overall_rating"], row["avg_teaching_effectiveness"],
            row["total_responses"]) == (4.0, 4.0, 5)


def test_legacy_ids_become_tokens_and_legacy_course_surveys_close(tmp_path):
    c = sqlite3.connect(tmp_path / "old.db")
    for ddl in SCHEMA:
        c.execute(ddl)
    c.execute("INSERT INTO courses (code, name) VALUES ('CS', 'Computer Science')")
    c.execute("INSERT INTO students (student_id, course) VALUES ('S1', 'CS')")
    c.execute("INSERT INTO course_evaluations (module_code, academic_year, semester, "
              "instructor_id, template_id, start_date, end_date) VALUES ('CS', '2026', 'auto', "
              "'auto', 1, '2026-05-06', '2027-05-06')")
    c.execute("INSERT INTO evaluation_responses (evaluation_id, student_id, submitted_at) VALUES "
              "(1, 'S1', '2026-05-06 19:30:30')")
    c.execute("INSERT INTO evaluations VALUES (1, 'CS', 'S1', 4, 'ok', '2026-05-06 19:30:30')")
    course_evaluation_schema.apply(c.execute)
    assert c.execute("SELECT course_code, is_active FROM course_evaluations").fetchone() == \
        ("CS", 0)
    token, day = c.execute("SELECT student_id, submitted_at FROM evaluation_responses").fetchone()
    assert token.startswith("tok-") and day == "2026-05-06"
    assert c.execute("SELECT responded FROM course_eval_invitations").fetchone() == (1,)
    assert c.execute("SELECT student_id FROM evaluations").fetchone()[0].startswith("tok-")
    c.close()


def test_ensure_inside_a_transaction_does_not_commit_the_callers_work(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    for ddl in SCHEMA:
        c.execute(ddl)
    c.commit()
    c.execute("INSERT INTO courses (code, name) VALUES ('X1', 'Pending')")
    assert c.in_transaction
    ce.ensure(c)
    c.rollback()
    assert c.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 0
    ce.ensure(c)
    assert not c.in_transaction
    assert c.execute("SELECT 1 FROM sqlite_master WHERE name = 'course_team'").fetchone()
    c.close()


def test_closing_date_in_the_past_is_refused(conn):
    with pytest.raises(ValueError, match="already passed"):
        _open(conn, opens_at=TODAY - timedelta(days=9), closes_at=TODAY - timedelta(days=2))


def test_launch_records_semester_and_instructor_and_stays_open(conn):
    eid = ce.open_survey(conn, "CS", actor="lee", now=NOW, opens_at=TODAY,
                         closes_at=TODAY + timedelta(days=9), semester="Fall",
                         instructor_id="16")["evaluation_id"]
    s = ce.survey(conn, eid)
    assert (s["semester"], str(s["instructor_id"])) == ("Fall", "16")
    assert s["course_code"] == "CS" and ce.state(s, NOW) == "open"

