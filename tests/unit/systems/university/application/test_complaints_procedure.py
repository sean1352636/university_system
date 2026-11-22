"""Complaints procedure: OIA stages, deadlines, assignment, outcomes,
escalation windows, closure with the Completion of Procedures letter,
legacy statuses, reminders and statistics. In-memory database built here."""

import contextlib
import sqlite3
from datetime import date

import pytest

from education_system.systems.university.application.complaints import procedure as cp
from education_system.systems.university.infrastructure.database.schemas import (
    complaints_procedure_schema as schema,
)

TODAY = date(2026, 10, 30)          # a Friday
STAFF = cp.Actor("lee", "staff", frozenset({"lee"}))
STUDENT = cp.Actor("S1", "student", frozenset({"S1", "3"}))
OTHER = cp.Actor("S2", "student", frozenset({"S2"}))


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, email TEXT, "
              "role TEXT, student_id TEXT)")
    c.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, sender_id INTEGER, "
              "recipient_id INTEGER, subject TEXT, message TEXT, content TEXT, is_read INTEGER, "
              "sent_at TEXT)")
    c.executemany("INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                  [(1, "admin", "admin@uni.ac.uk", "admin", None),
                   (2, "lee", "lee@uni.ac.uk", "staff", None),
                   (3, "S1", None, "student", "S1")])
    cp.ensure(c)
    yield c
    c.close()


def _submit(c, cid="ABC12345", submitted="2026-10-30 09:00"):
    complaint = {"id": cid, "name": "Ada Lovelace", "user_id": "S1", "email": "s1@uni.ac.uk",
                 "category": "Academic", "priority": "Medium", "subject": "Feedback late",
                 "description": "Marks were returned after six weeks.", "status": "Pending",
                 "response": "", "submitted": submitted, "updated": submitted}
    return cp.submit(c, complaint, submitted_by="3", today=TODAY)


def test_working_days_skip_weekends():
    assert cp.add_working_days(TODAY, 1) == date(2026, 11, 2)
    assert cp.add_working_days(TODAY, 10) == date(2026, 11, 13)


def test_formal_deadline_capped_at_90_days_from_receipt():
    received = date(2026, 6, 1)
    assert cp.stage_due("formal", date(2026, 8, 20), received) == date(2026, 8, 30)


def test_submission_starts_early_resolution_with_deadline(conn):
    row = _submit(conn)
    assert row["stage"] == "early_resolution"
    assert row["stage_due"] == "2026-11-13"
    assert row["status"] == "Pending"
    assert [e["event_type"] for e in cp.history(conn, row["id"])] == ["submitted"]


def test_assign_requires_staff_handler_and_actor(conn):
    _submit(conn)
    with pytest.raises(ValueError, match="not a member of staff"):
        cp.assign(conn, "ABC12345", "S1", STAFF)
    with pytest.raises(PermissionError):
        cp.assign(conn, "ABC12345", "lee", STUDENT)
    emails = cp.assign(conn, "ABC12345", "lee", STAFF)
    assert emails and emails[0][0] == "lee@uni.ac.uk"
    assert cp.get(conn, "ABC12345", TODAY)["status"] == "In Progress"


def test_outcome_opens_escalation_window_then_student_escalates(conn):
    _submit(conn)
    result = cp.record_outcome(conn, "ABC12345", STAFF, "not_upheld", "Policy was followed",
                               "Turnaround time\nCommunication", today=TODAY)
    assert result["closed"] is False
    row = cp.get(conn, "ABC12345", TODAY)
    assert row["status"] == "Rejected" and row["can_escalate"]
    assert row["escalation_due"] == "2026-11-13"
    with pytest.raises(PermissionError):
        cp.escalate(conn, "ABC12345", OTHER, "I disagree", today=TODAY)
    cp.escalate(conn, "ABC12345", STUDENT, "I disagree", today=date(2026, 11, 2))
    row = cp.get(conn, "ABC12345", date(2026, 11, 2))
    assert row["stage"] == "formal" and row["outcome"] is None
    assert row["status"] == "In Progress"


def test_escalation_refused_after_deadline(conn):
    _submit(conn)
    cp.record_outcome(conn, "ABC12345", STAFF, "upheld", "Apology given", today=TODAY)
    with pytest.raises(ValueError, match="no longer be escalated"):
        cp.escalate(conn, "ABC12345", STUDENT, "late", today=date(2026, 12, 1))


def test_resolved_early_only_at_stage_one(conn):
    _submit(conn)
    cp.advance(conn, "ABC12345", STAFF, "Complex", today=TODAY)
    with pytest.raises(ValueError, match="early resolution"):
        cp.record_outcome(conn, "ABC12345", STAFF, "resolved_early", "x", today=TODAY)


def test_close_waits_for_escalation_window_unless_accepted(conn):
    _submit(conn)
    cp.record_outcome(conn, "ABC12345", STAFF, "upheld", "Refund", today=TODAY)
    with pytest.raises(ValueError, match="may escalate until"):
        cp.finalise(conn, "ABC12345", STAFF, today=TODAY)
    result = cp.finalise(conn, "ABC12345", STUDENT, today=TODAY)
    assert result["closed"] and result["letter"] is None     # closed at stage 1: no CoP
    row = cp.get(conn, "ABC12345", TODAY)
    assert row["stage"] == "closed" and row["closed_stage"] == "early_resolution"


def test_review_decision_closes_and_issues_cop_letter(conn, tmp_path):
    _submit(conn)
    cp.advance(conn, "ABC12345", STAFF, "Needs investigation", today=TODAY)
    cp.record_outcome(conn, "ABC12345", STAFF, "partly_upheld", "Partly", today=TODAY)
    cp.escalate(conn, "ABC12345", STUDENT, "Review please", today=TODAY)
    result = cp.record_outcome(conn, "ABC12345", STAFF, "not_upheld", "Procedure followed",
                               "Process", today=TODAY, letter_dir=tmp_path)
    assert result["closed"]
    assert result["letter"].endswith(".pdf")
    assert (tmp_path / result["letter"].split("/")[-1]).read_bytes().startswith(b"%PDF")
    row = cp.get(conn, "ABC12345", TODAY)
    assert row["cop_issued_at"] == TODAY.isoformat() and row["closed_stage"] == "review"
    assert any(e[3] for e in result["emails"])           # the letter is attached


def test_cop_letter_only_for_closed_complaints(conn, tmp_path):
    _submit(conn)
    with pytest.raises(ValueError, match="once the complaint is closed"):
        cp.issue_cop(conn, "ABC12345", STAFF, today=TODAY, directory=tmp_path)


def test_student_can_withdraw_own_complaint(conn):
    _submit(conn)
    result = cp.record_outcome(conn, "ABC12345", STUDENT, "withdrawn", "Sorted", today=TODAY)
    assert result["closed"] and result["letter"] is None
    with pytest.raises(PermissionError):
        _submit(conn, "ZZZ00001")
        cp.record_outcome(conn, "ZZZ00001", OTHER, "withdrawn", "x", today=TODAY)


def test_legacy_resolved_status_records_stage_outcome(conn):
    _submit(conn)
    assert cp.legacy_status(conn, "ABC12345", STAFF, "Resolved", "Done", today=TODAY)
    assert cp.get(conn, "ABC12345", TODAY)["outcome"] == "resolved_early"
    assert cp.legacy_status(conn, "ABC12345", STAFF, "In Progress", "") is None


def test_legacy_rows_get_a_stage():
    c = sqlite3.connect(":memory:")
    c.execute(schema.COMPLAINTS_DDL)
    c.execute("INSERT INTO complaints (id, name, user_id, email, category, priority, subject, "
              "description, status, submitted, updated) VALUES ('OLD1', 'n', 'S1', 'e@x.uk', "
              "'Other', 'Low', 's', 'd', 'Resolved', '2026-01-05 10:00', '2026-01-09 10:00'), "
              "('OLD2', 'n', 'S1', 'e@x.uk', 'Other', 'Low', 's', 'd', 'Pending', "
              "'2026-10-30 10:00', '2026-10-30 10:00')")
    cp.ensure(c)
    stages = dict(c.execute("SELECT id, stage FROM complaints"))
    assert stages == {"OLD1": "closed", "OLD2": "early_resolution"}
    assert c.execute("SELECT stage_due FROM complaints WHERE id = 'OLD2'").fetchone()[0] == \
        "2026-11-13"


def test_reminders_once_a_day_to_handler_or_admins(conn, monkeypatch):
    _submit(conn, submitted="2026-10-01 09:00")         # stage 1 overdue by TODAY
    emails = cp.remind(conn, TODAY)
    assert [e[0] for e in emails] == ["admin@uni.ac.uk"]  # nobody assigned
    assert cp.remind(conn, TODAY) == []                  # not twice the same day
    cp.assign(conn, "ABC12345", "lee", STAFF)
    sent = []

    @contextlib.contextmanager
    def fake_transaction(*_a, **_k):
        yield conn

    from education_system.systems.university.infrastructure.database import db as db_module
    monkeypatch.setattr(db_module, "transaction", fake_transaction)
    monkeypatch.setattr(cp, "send_emails", lambda emails, **_k: sent.extend(emails))
    assert cp.run_reminders(date(2026, 11, 2)) == 1
    assert [e[0] for e in sent] == ["lee@uni.ac.uk"]


def test_statistics(conn, tmp_path):
    _submit(conn, "A0000001")
    _submit(conn, "A0000002")
    cp.record_outcome(conn, "A0000001", STAFF, "upheld", "Fixed", today=TODAY)
    cp.finalise(conn, "A0000001", STAFF, student_accepted=True, today=TODAY)
    stats = cp.statistics(conn, "2026-10-01", "2026-10-31", today=TODAY)
    assert stats["received"] == 2 and stats["closed"] == 1 and stats["open"] == 1
    assert stats["outcomes"] == {"upheld": 1}
    assert stats["decisions"] == 1 and stats["percent_on_time"] == 100.0
    assert stats["average_days_to_close"] == 0.0
    assert any("Completion of Procedures" in line for line in cp.statistics_lines(stats))


def test_own_lists_only_the_complainants_complaints(conn):
    _submit(conn)
    assert [r["id"] for r in cp.own(conn, STUDENT, TODAY)] == ["ABC12345"]
    assert cp.own(conn, OTHER, TODAY) == []
