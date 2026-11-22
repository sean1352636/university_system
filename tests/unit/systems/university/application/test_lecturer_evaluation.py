"""Lecturer evaluation: who is rated, eligibility, one anonymous rating per
lecturer per module, the module survey's window, threshold, who may read
results (self, line manager, module leader, admin), screening, reminders,
reflections, trends and comparisons, teaching history, legacy table and the
transaction-safe ensure. In-memory database."""

import sqlite3
from datetime import datetime

import pytest

from education_system.systems.university.application.evaluation import lecturer as le
from education_system.systems.university.application.evaluation import lecturer_feedback as lf
from education_system.systems.university.application.evaluation import module as me
from education_system.systems.university.application.evaluation import teaching_history
from education_system.systems.university.infrastructure.database.schemas import (
    lecturer_evaluation_schema,
)

SCHEMA = [
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
    "CREATE TABLE modules (module_code TEXT, module_name TEXT, department TEXT, course TEXT, "
    "semester TEXT, instructor TEXT, instructor_id INTEGER, is_active INTEGER DEFAULT 1)",
    "CREATE TABLE students (student_id TEXT PRIMARY KEY, email_address TEXT)",
    "CREATE TABLE student_modules (student_id TEXT, module_code TEXT, status TEXT)",
    "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT, "
    "email TEXT, role TEXT, student_id TEXT)",
    "CREATE TABLE staff (id INTEGER PRIMARY KEY, username TEXT, name TEXT, email TEXT)",
    "CREATE TABLE staff_profiles (profile_id INTEGER PRIMARY KEY, user_id TEXT, employee_id TEXT, "
    "manager_id TEXT)",
    "CREATE TABLE instructors (id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, "
    "email TEXT, department TEXT, is_active INTEGER DEFAULT 1)",
    "CREATE TABLE module_schedule (id INTEGER PRIMARY KEY, module_code TEXT, instructor_id INTEGER)",
    "CREATE TABLE academic_terms (id INTEGER PRIMARY KEY, name TEXT, start_date TEXT, end_date TEXT)",
    """CREATE TABLE messages (id INTEGER PRIMARY KEY, sender_id INTEGER, recipient_id INTEGER,
        subject TEXT, message TEXT, content TEXT, is_read INTEGER, sent_at TEXT)""",
    """CREATE TABLE instructor_performance_history (performance_id INTEGER PRIMARY KEY,
        instructor_id TEXT NOT NULL, academic_year TEXT NOT NULL, semester TEXT NOT NULL,
        avg_overall_rating REAL, avg_teaching_effectiveness REAL, avg_course_organization REAL,
        avg_student_engagement REAL, total_evaluations INTEGER, total_responses INTEGER,
        calculated_at TEXT)""",
]
NOW = datetime(2026, 10, 16, 12)
YEAR = "2026/2027"
STUDENTS = ("S1", "S2", "S3", "S4", "S5", "S6")


def _seed(c):
    for ddl in SCHEMA:
        c.execute(ddl)
    c.executemany("INSERT INTO modules VALUES (?, ?, 'Computing', 'CS', 'Fall', ?, NULL, 1)",
                  [("CS101", "Programming", "lee"), ("CS102", "Data", "kim")])
    for sid in STUDENTS:
        c.execute("INSERT INTO students VALUES (?, ?)", (sid, f"{sid.lower()}@uni.ac.uk"))
        for code in ("CS101", "CS102"):
            c.execute("INSERT INTO student_modules VALUES (?, ?, 'Enrolled')", (sid, code))
    c.execute("INSERT INTO students VALUES ('X1', 'x1@uni.ac.uk')")
    c.executemany("INSERT INTO users (id, username, first_name, last_name, role) VALUES "
                  "(?, ?, ?, ?, ?)", [(1, "admin", "Ad", "Min", "admin"),
                                      (2, "lee", "Jo", "Lee", "staff"),
                                      (3, "kim", "Al", "Kim", "staff"),
                                      (4, "ann", "Ann", "Boss", "staff")])
    c.executemany("INSERT INTO staff VALUES (?, ?, ?, ?)",
                  [(1, "lee", "Jo Lee", "lee@uni.ac.uk"), (4, "tom", "Tom Tutor", "tom@uni.ac.uk")])
    c.executemany("INSERT INTO staff_profiles (user_id, employee_id, manager_id) VALUES (?, ?, ?)",
                  [("lee", "E2", "E3"), ("ann", "E3", None)])
    c.execute("INSERT INTO instructors VALUES (10, 'Tom', 'Tutor', 'TOM@uni.ac.uk', '', 1)")
    c.executemany("INSERT INTO module_schedule (module_code, instructor_id) VALUES (?, 10)",
                  [("CS101",), ("CS102",)])
    c.execute("INSERT INTO academic_terms VALUES (1, 'Fall 2026', '2026-09-21', '2026-12-11')")


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    _seed(c)
    le.ensure(c)
    c.commit()
    yield c
    c.close()


def _open(c, code="CS101", **kw):
    kw.setdefault("opens_at", "2026-10-01")
    kw.setdefault("closes_at", "2026-11-30")
    return me.open_survey(c, code, actor="lee", now=NOW, **kw)["form_id"]


def _rate(score):
    return {k: score for k in le.KEYS}


def _rate_all(c, form_id, lecturer, score, students=STUDENTS[:5]):
    for sid in students:
        le.submit(c, form_id, lecturer, sid, _rate(score), now=NOW)


def test_lecturers_are_the_leader_team_and_linked_timetabled_instructors(conn):
    assert conn.execute("SELECT staff_id FROM instructors WHERE id = 10").fetchone() == (4,)
    assert [p["username"] for p in le.lecturers_for(conn, "CS101")] == ["lee", "tom"]
    assert le.name_of(conn, "tom") == "Tom Tutor"


def test_module_survey_no_longer_asks_about_each_lecturer_by_default(conn):
    assert not any(q["scope"] == "staff" for q in me.questions(conn, _open(conn)))


def test_one_anonymous_rating_per_lecturer_per_module(conn):
    fid = _open(conn)
    le.submit(conn, fid, "lee", "S1", _rate(4), "Clear", now=NOW)
    token, day = conn.execute("SELECT respondent, submitted_at FROM lecturer_evaluations"
                              ).fetchone()
    assert token.startswith("tok-") and day == "2026-10-16"
    with pytest.raises(ValueError, match="already"):
        le.submit(conn, fid, "lee", "S1", _rate(4), now=NOW)
    le.submit(conn, fid, "tom", "S1", _rate(3), now=NOW)  # a different lecturer is fine


def test_refusals(conn):
    fid = _open(conn)
    with pytest.raises(ValueError, match="Please rate"):
        le.submit(conn, fid, "lee", "S1", {"overall": 4}, now=NOW)
    with pytest.raises(ValueError, match="1 to 5"):
        le.submit(conn, fid, "lee", "S1", _rate(7), now=NOW)
    with pytest.raises(ValueError, match="students on the module"):
        le.submit(conn, fid, "lee", "X1", _rate(4), now=NOW)
    with pytest.raises(ValueError, match="does not teach"):
        le.submit(conn, fid, "kim", "S1", _rate(4), now=NOW)
    with pytest.raises(ValueError, match="not open"):
        le.submit(conn, fid, "lee", "S1", _rate(4), now=datetime(2026, 12, 5))


def test_threshold_and_who_may_read(conn):
    fid = _open(conn)
    _rate_all(conn, fid, "lee", 4, STUDENTS[:4])
    assert lf.results(conn, "lee", "lee")["modules"][0]["withheld"] is True
    le.submit(conn, fid, "lee", "S5", _rate(2), now=NOW)
    mine = lf.results(conn, "lee", "lee")["modules"][0]
    assert (mine["withheld"], mine["means"]["overall"], mine["invited"]) == (False, 3.6, 6)
    assert mine["distribution"]["overall"] == {1: 0, 2: 1, 3: 0, 4: 4, 5: 0}
    assert lf.results(conn, "lee", "ann")["modules"]  # line manager, via employee id
    for outsider in ("kim", "S1"):
        with pytest.raises(ValueError, match="cannot see"):
            lf.results(conn, "lee", outsider)


def test_module_leader_sees_only_their_modules(conn):
    first, second = _open(conn), _open(conn, "CS102")
    _rate_all(conn, first, "tom", 4)
    _rate_all(conn, second, "tom", 5)
    assert [m["module_code"] for m in lf.results(conn, "tom", "kim")["modules"]] == ["CS102"]
    assert [m["module_code"] for m in lf.results(conn, "tom", "lee")["modules"]] == ["CS101"]
    assert len(lf.results(conn, "tom", "admin", admin=True)["modules"]) == 2
    assert {p["username"] for p in le.visible_lecturers(conn, "kim")} == {"kim", "tom"}


def test_flagged_comment_waits_for_release(conn):
    fid = _open(conn)
    _rate_all(conn, fid, "lee", 4, STUDENTS[:4])
    assert le.submit(conn, fid, "lee", "S5", _rate(4), "he is an idiot", now=NOW)["flagged"] == 1
    assert lf.results(conn, "lee", "lee")["modules"][0]["comments"] == []
    le.review_comment(conn, le.review_queue(conn)[0]["evaluation_id"], True, "admin")
    assert lf.results(conn, "lee", "lee")["modules"][0]["comments"] == ["he is an idiot"]


def test_one_reminder_per_student_at_most_every_three_days(conn):
    fid = _open(conn)
    le.submit(conn, fid, "lee", "S1", _rate(4), now=NOW)
    le.submit(conn, fid, "tom", "S1", _rate(4), now=NOW)
    first = le.send_reminders(conn, now=NOW)
    assert first["sent"] == 5 and len(first["emails"]) == 5
    assert le.send_reminders(conn, now=datetime(2026, 10, 18))["sent"] == 0
    assert le.send_reminders(conn, now=datetime(2026, 10, 19))["sent"] == 5


def test_reflect_after_close_then_publish_to_the_lecturers_students(conn):
    fid = _open(conn)
    with pytest.raises(ValueError, match="closed"):
        le.reflect(conn, fid, "lee", "Notes", actor="lee", now=NOW)
    later = datetime(2026, 12, 5)
    with pytest.raises(ValueError, match="Only the lecturer"):
        le.reflect(conn, fid, "lee", "Notes", actor="kim", now=later)
    rid = le.reflect(conn, fid, "lee", "Notes", "Recaps", "Too fast", "Added recaps", "lee",
                     now=later)
    assert le.publish_reflection(conn, rid, "lee")["notified"] == 6
    assert le.published_for_student(conn, "S2")[0]["we_did"] == "Added recaps"
    assert len(le.reflections(conn, "lee", "ann")) == 1
    assert le.reflections(conn, "lee", "kim") == []


def test_trend_last_year_and_department(conn):
    old = _open(conn, year="2025/2026", opens_at="2025-10-01", closes_at="2025-11-30")
    for i, sid in enumerate(STUDENTS[:5]):
        conn.execute("INSERT INTO lecturer_evaluations (form_id, module_code, academic_year, "
                     f"lecturer, respondent, {', '.join(le.KEYS)}, submitted_at) VALUES "
                     f"(?, 'CS101', '2025/2026', 'lee', ?, {', '.join('2' for _ in le.KEYS)}, "
                     "'2025-11-01')", (old, f"tok-{i}"))
    _rate_all(conn, _open(conn), "lee", 4)
    conn.execute("UPDATE modules SET instructor = 'kim' WHERE module_code = 'CS102'")
    _rate_all(conn, _open(conn, "CS102"), "kim", 5)
    result = lf.results(conn, "lee", "lee")
    assert [t["overall"] for t in result["trend"]] == [4.0, 2.0]
    assert result["comparison"]["last_year"] == 2.0
    assert result["comparison"]["department"] == {"overall": 5.0, "lecturers": 1}


def test_teaching_history_counts_lecturer_ratings(conn):
    _rate_all(conn, _open(conn), "lee", 4)
    assert teaching_history.refresh_instructor_history(conn, YEAR) == 1
    row = teaching_history.instructor_history(conn, "lee")[0]
    assert (row["avg_teaching_effectiveness"], row["total_responses"]) == (4.0, 5)


@pytest.mark.parametrize("rows, legacy", [(0, False), (1, True)])
def test_old_instructor_id_table_is_replaced(tmp_path, rows, legacy):
    c = sqlite3.connect(tmp_path / "old.db")
    for ddl in SCHEMA:
        c.execute(ddl)
    c.execute("CREATE TABLE lecturer_evaluations (evaluation_id INTEGER PRIMARY KEY, "
              "student_id TEXT NOT NULL, module_code TEXT, lecturer_id INTEGER, overall INTEGER, "
              "submitted_at TEXT)")
    for _ in range(rows):
        c.execute("INSERT INTO lecturer_evaluations VALUES (1, 'S1', 'CS101', 10, 4, "
                  "'2026-05-01T10:00:00')")
    lecturer_evaluation_schema.apply(c.execute)
    assert "lecturer" in {r[1] for r in c.execute("PRAGMA table_info(lecturer_evaluations)")}
    kept = c.execute("SELECT 1 FROM sqlite_master WHERE name = 'lecturer_evaluations_legacy'"
                     ).fetchone()
    assert bool(kept) is legacy
    if legacy:
        assert c.execute("SELECT student_id, submitted_at FROM lecturer_evaluations_legacy"
                         ).fetchone()[1] == "2026-05-01"
        assert c.execute("SELECT student_id FROM lecturer_evaluations_legacy").fetchone()[0] \
            .startswith("tok-")
    c.close()


def test_ensure_inside_a_transaction_does_not_commit_the_callers_work(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    for ddl in SCHEMA:
        c.execute(ddl)
    c.commit()
    c.execute("INSERT INTO students VALUES ('P1', NULL)")
    assert c.in_transaction
    le.ensure(c)
    c.rollback()
    assert c.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0
    le.ensure(c)
    assert not c.in_transaction
    assert c.execute("SELECT 1 FROM sqlite_master WHERE name = 'lecturer_reflections'").fetchone()
    c.close()
