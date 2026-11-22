"""Module evaluation surveys: window, invitations, anonymity, threshold,
screening, visibility, reminders and closing the loop. In-memory database."""

import hashlib
import sqlite3
from datetime import datetime, timedelta

import pytest

from education_system.systems.university.application.evaluation import module as me
from education_system.systems.university.infrastructure.database.schemas import (
    module_evaluation_schema,
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
    "CREATE TABLE academic_terms (id INTEGER PRIMARY KEY, name TEXT, start_date TEXT, end_date TEXT)",
    "CREATE TABLE assignments (id INTEGER PRIMARY KEY, module_code TEXT, grades_released_at TEXT)",
    """CREATE TABLE messages (id INTEGER PRIMARY KEY, sender_id INTEGER, recipient_id INTEGER,
        subject TEXT, message TEXT, content TEXT, is_read INTEGER, sent_at TEXT)""",
    "CREATE TABLE evaluation_question_bank (bank_id INTEGER PRIMARY KEY, question_text TEXT, "
    "question_type TEXT, question_category TEXT)",
    "CREATE TABLE evaluation_question_tags (tag_id INTEGER PRIMARY KEY, bank_id INTEGER, tag TEXT)",
]
NOW = datetime(2026, 10, 16, 12)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    for ddl in SCHEMA:
        c.execute(ddl)
    c.execute("INSERT INTO modules VALUES ('CS101', 'Programming', 'Computing', 'CS', 'Fall', "
              "'lee', 2, 1)")
    c.execute("INSERT INTO academic_terms VALUES (1, 'Fall 2026', '2026-09-21', '2026-12-11')")
    for i in range(1, 8):
        c.execute("INSERT INTO students VALUES (?, ?)", (f"S{i}", f"s{i}@uni.ac.uk"))
        c.execute("INSERT INTO student_modules VALUES (?, 'CS101', 'Enrolled')", (f"S{i}",))
    c.executemany("INSERT INTO users (id, username, first_name, last_name, role) VALUES "
                  "(?, ?, ?, ?, ?)", [(1, "admin", "Ad", "Min", "admin"),
                                      (2, "lee", "Jo", "Lee", "staff"),
                                      (3, "kim", "Al", "Kim", "staff")])
    c.execute("INSERT INTO evaluation_question_bank VALUES (1, 'The library had what I needed.', "
              "'likert', 'resources')")
    me.ensure(c)
    c.commit()
    yield c
    c.close()


def _answers(c, form_id, score, text=None):
    return {q["id"]: ((None, text) if q["question_type"] == "text" else (score, None))
            for q in me.questions(c, form_id)}


def _open(c, **kw):
    return me.open_survey(c, "CS101", opens_at="2026-10-01", closes_at="2026-11-30",
                          actor="lee", now=NOW, **kw)["form_id"]


def test_default_window_is_end_of_term(conn):
    assert [d.isoformat() for d in me.default_window(conn, "CS101", NOW.date())] == \
        ["2026-11-20", "2026-12-11"]


def test_open_invites_enrolled_and_adds_required_and_staff_questions(conn):
    assert not any(q["scope"] == "staff" for q in me.questions(conn, _open(conn)))
    me.set_required(conn, 1, True)
    form_id = _open(conn, custom=[("Labs helped.", "likert")], include_staff=True)
    texts = [q["question_text"] for q in me.questions(conn, form_id)]
    assert "The library had what I needed." in texts and "Labs helped." in texts
    assert "Jo Lee explained things clearly." in texts
    assert conn.execute("SELECT COUNT(*) FROM eval_form_invitations").fetchone()[0] == 7


def test_window_and_marks_release_close_the_survey(conn):
    form_id = _open(conn)
    with pytest.raises(ValueError, match="not open"):
        me.submit(conn, form_id, "S1", _answers(conn, form_id, 4), now=datetime(2026, 12, 2))
    conn.execute("INSERT INTO assignments VALUES (1, 'CS101', '2026-10-10 09:00:00')")
    assert me.state(conn, me.form(conn, form_id), NOW) == "closed_marks"


def test_responses_carry_no_student_identity(conn):
    form_id = _open(conn)
    me.submit(conn, form_id, "S1", _answers(conn, form_id, 4), now=NOW)
    token, day = conn.execute("SELECT student_hash, submitted_at FROM eval_form_responses"
                              ).fetchone()
    assert token.startswith("tok-") and day == "2026-10-16"
    assert hashlib.sha256(b"S1").hexdigest() != token
    assert conn.execute("SELECT responded FROM eval_form_invitations WHERE student_id = 'S1'"
                        ).fetchone()[0] == 1
    with pytest.raises(ValueError, match="already"):
        me.submit(conn, form_id, "S1", _answers(conn, form_id, 4), now=NOW)


def test_only_enrolled_students_and_valid_ratings(conn):
    form_id = _open(conn)
    with pytest.raises(ValueError, match="students on the module"):
        me.submit(conn, form_id, "X9", _answers(conn, form_id, 4), now=NOW)
    with pytest.raises(ValueError, match="1 to 5"):
        me.submit(conn, form_id, "S1", _answers(conn, form_id, 9), now=NOW)


def test_results_hidden_below_threshold_then_shown(conn):
    form_id = _open(conn)
    for sid in ("S1", "S2", "S3", "S4"):
        me.submit(conn, form_id, sid, _answers(conn, form_id, 4, "Good"), now=NOW)
    assert me.results(conn, form_id, "lee")["withheld"] is True
    me.submit(conn, form_id, "S5", _answers(conn, form_id, 2, "Too fast"), now=NOW)
    result = me.results(conn, form_id, "lee")
    assert result["withheld"] is False and result["rate"] == round(5 / 7 * 100, 1)
    overall = next(q for q in result["questions"] if q["question_text"] == me.OVERALL)
    assert overall["mean"] == 3.6 and overall["distribution"][4] == 4


def test_screened_comment_is_held_until_released(conn):
    form_id = _open(conn)
    for sid in ("S1", "S2", "S3", "S4"):
        me.submit(conn, form_id, sid, _answers(conn, form_id, 4), now=NOW)
    assert me.submit(conn, form_id, "S5", _answers(conn, form_id, 1, "he is an idiot"),
                     now=NOW)["flagged"] >= 1
    assert "he is an idiot" not in me.results(conn, form_id, "lee")["comments"]
    me.review_comment(conn, me.review_queue(conn)[0]["answer_id"], True, "admin")
    assert "he is an idiot" in me.results(conn, form_id, "lee")["comments"]


def test_visibility_by_role(conn):
    from education_system.systems.university.application.modules import delivery as module_delivery
    module_delivery.add_member(conn, "CS101", "kim", "tutor", 5)
    form_id = _open(conn, include_staff=True)
    for sid in ("S1", "S2", "S3", "S4", "S5"):
        me.submit(conn, form_id, sid, _answers(conn, form_id, 4), now=NOW)
    staff_seen = {q["staff_username"] for q in me.results(conn, form_id, "kim")["questions"]
                  if q["scope"] == "staff"}
    assert staff_seen == {"kim"}
    with pytest.raises(ValueError, match="teaching team"):
        me.results(conn, form_id, "nobody")


def test_reminders_skip_responders_and_respect_interval(conn):
    form_id = _open(conn)
    me.submit(conn, form_id, "S1", _answers(conn, form_id, 4), now=NOW)
    assert me.send_reminders(conn, now=datetime(2026, 10, 20))["sent"] == 6
    assert me.send_reminders(conn, now=datetime(2026, 10, 21))["sent"] == 0


def test_respond_after_close_and_publish(conn):
    # respond() checks the real clock, so the window straddles today.
    today = datetime.now().date()
    form_id = me.open_survey(conn, "CS101", opens_at=today - timedelta(days=1),
                             closes_at=today + timedelta(days=30), actor="lee")["form_id"]
    with pytest.raises(ValueError, match="closed"):
        me.respond(conn, form_id, "Summary")
    me.close_survey(conn, form_id)
    rid = me.respond(conn, form_id, "Summary", "Act", "Too fast", "Slowed down", "lee")
    assert me.publish(conn, rid, "lee")["notified"] == 7
    assert me.published_for_student(conn, "S1")[0]["we_did"] == "Slowed down"


def test_legacy_hashes_become_tokens_and_legacy_forms_get_a_window(tmp_path):
    c = sqlite3.connect(tmp_path / "old.db")
    for ddl in SCHEMA:
        c.execute(ddl)
    c.execute("INSERT INTO students VALUES ('S1', NULL)")
    c.execute("INSERT INTO evaluation_forms (module_code, module_name, academic_year, status, "
              "created_at) VALUES ('CS101', 'P', '2025/2026', 'open', '2026-05-01 10:00:00')")
    c.execute("INSERT INTO eval_form_responses (form_id, student_hash, submitted_at) VALUES "
              "(1, ?, '2026-05-02 11:22:33')", (hashlib.sha256(b"S1").hexdigest(),))
    module_evaluation_schema.apply(c.execute)
    token, day = c.execute("SELECT student_hash, submitted_at FROM eval_form_responses").fetchone()
    assert token.startswith("tok-") and day == "2026-05-02"
    assert c.execute("SELECT responded FROM eval_form_invitations").fetchone()[0] == 1
    assert c.execute("SELECT closes_at FROM evaluation_forms").fetchone()[0] == "2026-08-31 23:59:59"
    c.close()


def test_ensure_inside_a_transaction_does_not_commit_the_callers_work(tmp_path):
    c = sqlite3.connect(tmp_path / "t.db")
    for ddl in SCHEMA:
        c.execute(ddl)
    c.commit()
    c.execute("INSERT INTO modules (module_code, module_name) VALUES ('X1', 'Pending')")
    assert c.in_transaction
    me.ensure(c)
    c.rollback()
    assert c.execute("SELECT COUNT(*) FROM modules").fetchone()[0] == 0
    me.ensure(c)  # not cached while busy, so a clean call still applies and commits
    assert not c.in_transaction
    assert c.execute("SELECT name FROM sqlite_master WHERE name = 'eval_form_invitations'"
                     ).fetchone()
    c.close()
