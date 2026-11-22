"""Assignment rules: who sees an assignment, whether a student may submit, marker
allocation, staff scope and the scheduled job. Temporary in-memory databases."""

import sqlite3
from datetime import datetime, timedelta

import pytest

from education_system.systems.university.domains.assessment.domain.assignments.assignment_rules import (
    jobs,
    markers,
    peer,
    reports,
    schema,
    scope,
    submitting,
    visibility,
)

NOW = datetime(2026, 11, 1, 12, 0, 0)
SOON = "2026-11-02 12:00:00"
LATER = "2026-12-01 12:00:00"
PAST = "2026-10-30 12:00:00"

SCHEMA = """
CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT, email_address TEXT);
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role TEXT, email TEXT);
CREATE TABLE modules (module_code TEXT PRIMARY KEY, module_name TEXT, instructor TEXT);
CREATE TABLE student_modules (student_id TEXT, module_code TEXT);
CREATE TABLE assignments (id INTEGER PRIMARY KEY, module_code TEXT, title TEXT, due_date TEXT,
    status TEXT DEFAULT 'active', is_active INTEGER DEFAULT 1, allow_late_submission INTEGER DEFAULT 1,
    assignment_type TEXT DEFAULT 'individual', created_by TEXT, created_at TEXT, updated_at TEXT, max_marks REAL,
    weight REAL);
CREATE TABLE assignment_submissions (id INTEGER PRIMARY KEY, assignment_id INTEGER, student_id TEXT,
    grade REAL, status TEXT DEFAULT 'submitted', group_id INTEGER, version_number INTEGER DEFAULT 1,
    is_final_submission INTEGER DEFAULT 1, submission_date TEXT, is_late INTEGER DEFAULT 0);
CREATE TABLE extension_requests (id INTEGER PRIMARY KEY, assignment_id INTEGER, student_id TEXT,
    new_due_date TEXT, status TEXT);
CREATE TABLE peer_reviews (id INTEGER PRIMARY KEY, assignment_id INTEGER, reviewer_id TEXT,
    reviewee_id TEXT, submission_id INTEGER, reviewee_submission_id INTEGER, overall_score REAL,
    review_text TEXT, is_anonymous INTEGER, status TEXT, review_date TEXT);
CREATE TABLE peer_review_criteria (id INTEGER PRIMARY KEY, review_id INTEGER, criteria_name TEXT,
    score REAL, comment TEXT);
CREATE TABLE peer_review_config (id INTEGER PRIMARY KEY, assignment_id INTEGER UNIQUE,
    is_anonymous INTEGER);
CREATE TABLE peer_review_criteria_templates (id INTEGER PRIMARY KEY, config_id INTEGER,
    criteria_name TEXT, max_score REAL, order_index INTEGER);
INSERT INTO students VALUES ('S1', 'Asha', 'Khan', 's1@uni.test'), ('S2', 'Ben', 'Ng', 's2@uni.test');
INSERT INTO users VALUES (5, 'lect', 'instructor', 'lect@uni.test'), (6, 'other', 'instructor', NULL);
INSERT INTO modules VALUES ('CS1', 'Computing', 'lect'), ('CS2', 'Maths', NULL);
INSERT INTO student_modules VALUES ('S1', 'CS1'), ('S2', 'CS1');
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA)
    schema.apply_to_connection(c)
    yield c
    c.close()


@pytest.fixture(autouse=True)
def no_mitigating_circumstances(monkeypatch):
    """The real lookup opens the application's own database."""
    from education_system.systems.university.domains.assessment.domain.mitigating_circumstances import (
        integration,
    )
    monkeypatch.setattr(integration, "get_active_extension", lambda *_a, **_k: None)


def _assignment(conn, due=LATER, module="CS1", **columns):
    names = ["module_code", "title", "due_date", *columns]
    values = [module, "Essay", due, *columns.values()]
    marks = ",".join("?" * len(values))
    return conn.execute(f"INSERT INTO assignments ({','.join(names)}) VALUES ({marks})", values).lastrowid


def _submission(conn, assignment_id, student="S1", **columns):
    names = ["assignment_id", "student_id", *columns]
    values = [assignment_id, student, *columns.values()]
    marks = ",".join("?" * len(values))
    return conn.execute(f"INSERT INTO assignment_submissions ({','.join(names)}) VALUES ({marks})",
                        values).lastrowid


# ── visibility ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("choice", ["draft", "hidden"])
def test_unpublished_assignment_is_closed_and_nobody_is_told(conn, choice):
    aid = _assignment(conn)
    assert visibility.set_visibility(conn, aid, choice, now=NOW) is False
    assert conn.execute("SELECT is_active FROM assignments WHERE id = ?", (aid,)).fetchone()[0] == 0
    with pytest.raises(ValueError, match="not open"):
        submitting.check_can_submit(conn, aid, "S1", NOW)


def test_students_are_told_only_the_first_time_it_is_published(conn):
    aid = _assignment(conn, status="draft", is_active=0)
    assert visibility.set_visibility(conn, aid, "published", now=NOW) is True
    visibility.set_visibility(conn, aid, "hidden", now=NOW)
    assert visibility.set_visibility(conn, aid, "published", now=NOW) is False


@pytest.mark.parametrize("opens, wanted", [
    ("", "Give the opening date"),
    ("not a date", "Give the opening date"),
    ("2026-10-01", "has passed"),
    ("2027-01-01", "before the due date"),
])
def test_scheduled_needs_a_usable_opening_date(opens, wanted):
    with pytest.raises(ValueError, match=wanted):
        visibility.check_settings("scheduled", opens, LATER, NOW)


def test_scheduled_opens_when_its_date_comes_and_says_so_once(conn):
    aid = _assignment(conn)
    visibility.set_visibility(conn, aid, "scheduled", "2026-11-10 09:00", now=NOW)
    assert jobs.open_scheduled(conn, NOW) == []
    with pytest.raises(ValueError, match="opens on"):
        submitting.check_can_submit(conn, aid, "S1", NOW)
    assert jobs.open_scheduled(conn, NOW + timedelta(days=10)) == [aid]
    assert jobs.open_scheduled(conn, NOW + timedelta(days=11)) == []


# ── submitting ──────────────────────────────────────────────────────────


def test_quiz_cannot_be_uploaded_to(conn):
    aid = _assignment(conn, assignment_type="quiz")
    with pytest.raises(ValueError, match="My Quizzes"):
        submitting.check_can_submit(conn, aid, "S1", NOW)


def test_late_rules(conn):
    assert submitting.check_can_submit(conn, _assignment(conn), "S1", NOW)["late"] is False
    allowed = submitting.check_can_submit(conn, _assignment(conn, due=PAST), "S1", NOW)
    assert allowed["late"] is True and allowed["late_days"] == 2
    with pytest.raises(ValueError, match="not allowed"):
        submitting.check_can_submit(conn, _assignment(conn, due=PAST, allow_late_submission=0), "S1", NOW)
    with pytest.raises(ValueError, match="closed 1 day"):
        submitting.check_can_submit(conn, _assignment(conn, due=PAST, max_late_days=1), "S1", NOW)


def test_approved_extension_moves_this_students_deadline_only(conn):
    aid = _assignment(conn, due=PAST, allow_late_submission=0)
    conn.execute("INSERT INTO extension_requests (assignment_id, student_id, new_due_date, status) "
                 "VALUES (?, 'S1', ?, 'approved')", (aid, LATER))
    assert submitting.check_can_submit(conn, aid, "S1", NOW)["late"] is False
    with pytest.raises(ValueError):
        submitting.check_can_submit(conn, aid, "S2", NOW)


def test_attempt_limit_and_withdrawing_gives_the_attempt_back(conn):
    aid = _assignment(conn, max_attempts=1)
    sid = _submission(conn, aid)
    with pytest.raises(ValueError, match="used all 1"):
        submitting.check_can_submit(conn, aid, "S1", NOW)
    submitting.withdraw(conn, sid, "S1", NOW)
    assert submitting.check_can_submit(conn, aid, "S1", NOW)["late"] is False


def test_withdrawing_restores_the_earlier_version(conn):
    aid = _assignment(conn)
    first = _submission(conn, aid, is_final_submission=0)
    second = _submission(conn, aid)
    submitting.withdraw(conn, second, "S1", NOW)
    assert conn.execute("SELECT is_final_submission FROM assignment_submissions WHERE id = ?",
                        (first,)).fetchone()[0] == 1
    status, final, when = conn.execute(
        "SELECT status, is_final_submission, withdrawn_at FROM assignment_submissions WHERE id = ?",
        (second,)).fetchone()
    assert (status, final) == ("withdrawn", 0) and when


@pytest.mark.parametrize("due, columns, student, wanted", [
    (LATER, {"grade": 60}, "S1", "has been marked"),
    (LATER, {"group_id": 3}, "S1", "whole group"),
    (PAST, {}, "S1", "deadline has passed"),
    (LATER, {}, "S2", "isn't one of your"),
    (LATER, {"status": "withdrawn"}, "S1", "already been withdrawn"),
])
def test_withdrawal_is_refused(conn, due, columns, student, wanted):
    sid = _submission(conn, _assignment(conn, due=due), **columns)
    with pytest.raises(ValueError, match=wanted):
        submitting.withdraw(conn, sid, student, NOW)


# ── staff scope ─────────────────────────────────────────────────────────


def test_admin_sees_everything_and_a_lecturer_their_own(conn):
    assert scope.modules_for(conn, "root", 1, "admin") is None
    assert scope.modules_for(conn, "lect", 5, "instructor") == {"CS1"}
    assert scope.modules_for(conn, "other", 6, "instructor") == set()


def test_setting_an_assignment_brings_the_module_into_scope(conn):
    _assignment(conn, module="CS2", created_by="6")
    assert scope.modules_for(conn, "other", 6, "instructor") == {"CS2"}


def test_sql_filter_shapes():
    assert scope.sql_filter(None) == ("", [])
    assert scope.sql_filter(set()) == (" AND 1 = 0", [])
    clause, params = scope.sql_filter({"B", "A"})
    assert clause == " AND a.module_code IN (?,?)" and params == ["A", "B"]


# ── markers ─────────────────────────────────────────────────────────────


def test_share_evenly_skips_marked_work_and_keeps_existing_allocations(conn):
    aid = _assignment(conn)
    for n in range(4):
        _submission(conn, aid, student=f"N{n}")
    _submission(conn, aid, student="done", grade=70)
    assert markers.share_evenly(conn, aid, ["a", "b"], "lead") == 4
    assert markers.share_evenly(conn, aid, ["a", "b"], "lead") == 0
    held = [r["marker"] for r in markers.rows(conn, aid) if r["grade"] is None]
    assert sorted(held) == ["a", "a", "b", "b"]


def test_a_student_with_two_current_versions_is_listed_once(conn):
    aid = _assignment(conn)
    _submission(conn, aid)
    newest = _submission(conn, aid)
    listed = markers.rows(conn, aid)
    assert [r["submission_id"] for r in listed] == [newest]


def test_share_evenly_needs_a_marker(conn):
    with pytest.raises(ValueError, match="at least one"):
        markers.share_evenly(conn, _assignment(conn), [" "], "lead")


def test_only_the_allocated_marker_sees_the_work_but_admin_sees_all(conn):
    aid = _assignment(conn)
    sid = _submission(conn, aid)
    markers.set_marker(conn, aid, "S1", "a", "lead")

    def visible(username, role):
        clause, params = markers.queue_filter(username, role)
        return conn.execute(f"SELECT COUNT(*) FROM assignment_submissions s WHERE 1 = 1{clause}",
                            params).fetchone()[0]

    assert visible("a", "instructor") == 1
    assert visible("b", "instructor") == 0
    assert visible("root", "admin") == 1
    assert markers.allocated_elsewhere(conn, sid, "b", "instructor") == "a"
    assert markers.allocated_elsewhere(conn, sid, "a", "instructor") is None
    markers.set_marker(conn, aid, "S1", "", "lead")
    assert visible("b", "instructor") == 1


# ── peer review ─────────────────────────────────────────────────────────


def test_peer_questions_are_the_ones_the_lecturer_set(conn):
    aid = _assignment(conn)
    assert peer.criteria_for_assignment(conn, aid) == list(peer.DEFAULT_CRITERIA)
    peer.save_criteria(conn, aid, ["Argument", "Sources"], True)
    review = conn.execute("INSERT INTO peer_reviews (assignment_id, reviewer_id, status) "
                          "VALUES (?, 'S1', 'pending')", (aid,)).lastrowid
    assert peer.criteria_for_review(conn, review) == ["Argument", "Sources"]


def test_anonymous_reviewer_is_not_named_in_results(conn):
    aid = _assignment(conn)
    conn.execute("INSERT INTO peer_reviews (assignment_id, reviewer_id, reviewee_id, overall_score, "
                 "is_anonymous, status) VALUES (?, 'S2', 'S1', 4, 1, 'completed')", (aid,))
    assert peer.results_for(conn, "S1")[0]["reviewer"] == "Anonymous"


# ── job ─────────────────────────────────────────────────────────────────


def test_reminder_goes_once_and_only_to_those_who_have_not_submitted(conn):
    aid = _assignment(conn, due=SOON, reminder_days=2)
    _submission(conn, aid, student="S2")
    first = jobs.due_reminders(conn, NOW)
    assert [r["email"] for r in first] == ["s1@uni.test"]
    assert jobs.due_reminders(conn, NOW) == []


def test_reminders_hold_no_write_while_looking_up_an_extension(conn, monkeypatch):
    """The lookup uses its own connection; an open write here would block it."""
    from education_system.systems.university.domains.assessment.domain.mitigating_circumstances import (
        integration,
    )
    seen = []
    monkeypatch.setattr(integration, "get_active_extension",
                        lambda *_a, **_k: seen.append(conn.in_transaction))
    aid = _assignment(conn, due=SOON, reminder_days=2)
    conn.commit()
    assert len(jobs.due_reminders(conn, NOW)) == 2
    assert seen and not any(seen)
    assert conn.execute("SELECT COUNT(*) FROM assignment_reminders_sent WHERE assignment_id = ?",
                        (aid,)).fetchone()[0] == 2


def test_no_reminder_outside_the_period_or_when_switched_off(conn):
    _assignment(conn, due=LATER, reminder_days=2)
    _assignment(conn, due=SOON, reminder_days=0)
    assert jobs.due_reminders(conn, NOW) == []


def test_extension_delays_the_reminder(conn):
    aid = _assignment(conn, due=SOON, reminder_days=2)
    conn.execute("INSERT INTO extension_requests (assignment_id, student_id, new_due_date, status) "
                 "VALUES (?, 'S1', ?, 'approved')", (aid, LATER))
    assert [r["email"] for r in jobs.due_reminders(conn, NOW)] == ["s2@uni.test"]


# ── reports ─────────────────────────────────────────────────────────────


def test_export_neutralises_formula_cells(conn, tmp_path):
    report = {"wording": "x", "performance": [("=cmd()", "CS1", 1, 1, 50, 60, 40, 100)],
              "submissions": [], "comparative": []}
    path = tmp_path / "report.csv"
    reports.export(report, str(path))
    assert "=cmd()" not in path.read_text().replace("'=cmd()", "")
