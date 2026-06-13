"""Tests for cross-module exam + email features (10–17).

Each test exercises one feature: publisher → bus → consumer side
effect. Uses a temporary SQLite DB; patches `get_connection` /
`transaction` across `integration_bus`, `email_bus`, and
`finance_bus`.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def tmp_db(monkeypatch):
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test.db"

    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE exam_portal_exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT, title TEXT, status TEXT DEFAULT 'draft',
            duration_minutes INTEGER DEFAULT 60,
            start_time TEXT, end_time TEXT, room_id TEXT,
            pass_mark REAL DEFAULT 50, total_marks REAL DEFAULT 100,
            max_attempts INTEGER DEFAULT 1,
            created_by TEXT, published_at TEXT, updated_at TEXT
        );
        CREATE TABLE exam_portal_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER, student_id TEXT, student_name TEXT,
            access_token TEXT, ip_address TEXT,
            time_remaining INTEGER, status TEXT,
            submitted_at TEXT, graded_at TEXT,
            score REAL, percentage REAL, passed INTEGER,
            auto_submitted INTEGER, graded_by TEXT
        );
        CREATE TABLE student_enrolment (
            student_id TEXT, module_code TEXT, status TEXT
        );
        CREATE TABLE users (
            user_id TEXT PRIMARY KEY,
            email TEXT, role TEXT
        );
        CREATE TABLE program_fees (
            id INTEGER PRIMARY KEY,
            course TEXT, amount REAL, currency TEXT, academic_year TEXT
        );
        CREATE TABLE student_finance_accounts (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT, balance REAL DEFAULT 0,
            currency TEXT, account_status TEXT,
            created_at TEXT, updated_at TEXT
        );
        CREATE TABLE student_finance_transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER, student_id TEXT,
            transaction_type TEXT, amount REAL,
            balance_before REAL, balance_after REAL,
            description TEXT, reference_id TEXT,
            processed_by TEXT, created_at TEXT
        );
        CREATE TABLE email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient TEXT, subject TEXT, message TEXT,
            sent_date TEXT, status TEXT, related_to TEXT,
            student_id TEXT, template_name TEXT, sent_at TEXT
        );
        CREATE TABLE email_preferences (
            user_id TEXT, event_kind TEXT, enabled INTEGER DEFAULT 1,
            updated_at TEXT, PRIMARY KEY (user_id, event_kind)
        );
        """
    )
    conn.commit()
    conn.close()

    from education_system.university_system.infrastructure.database import db as db_mod

    def fake_get(*_a, **_k):
        c = sqlite3.connect(str(db_path))
        c.row_factory = sqlite3.Row
        return c

    class FakeTx:
        def __enter__(self):
            self.conn = fake_get()
            return self.conn
        def __exit__(self, *exc):
            try: self.conn.commit()
            finally: self.conn.close()

    def fake_tx(*_a, **_k):
        return FakeTx()

    monkeypatch.setattr(db_mod, "get_connection", fake_get)
    monkeypatch.setattr(db_mod, "transaction", fake_tx)

    from education_system.university_system.modules.services import (
        finance_bus, integration_bus, email_bus,
    )
    monkeypatch.setattr(finance_bus, "get_connection", fake_get)
    monkeypatch.setattr(integration_bus, "get_connection", fake_get)
    monkeypatch.setattr(integration_bus, "transaction", fake_tx)
    monkeypatch.setattr(email_bus, "get_connection", fake_get)

    # Stub the SMTP layer so tests don't try to send.
    monkeypatch.setattr(email_bus, "_attempt_send", lambda r, s, b: True)

    from education_system.university_system.modules.domain.academics.gui import _event_bus
    _event_bus.reset_for_tests()
    integration_bus.reset_for_tests()
    integration_bus.wire_subscribers()

    yield db_path

    _event_bus.reset_for_tests()
    integration_bus.reset_for_tests()


def _seed(db_path, sql, params=()):
    c = sqlite3.connect(str(db_path)); c.execute(sql, params); c.commit(); c.close()

def _query(db_path, sql, params=()):
    c = sqlite3.connect(str(db_path)); c.row_factory = sqlite3.Row
    rows = c.execute(sql, params).fetchall(); c.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Feature 10 — exam published → email roster
# ---------------------------------------------------------------------------

def test_feature10_exam_published_emails_roster(tmp_db):
    from education_system.university_system.modules.services import integration_bus

    _seed(tmp_db,
          "INSERT INTO exam_portal_exams (id, module_code, title, status, duration_minutes, "
          "start_time, end_time, pass_mark) "
          "VALUES (1, 'CS101', 'Final', 'draft', 90, '2026-05-01 09:00', '2026-05-01 10:30', 50)")
    _seed(tmp_db, "INSERT INTO student_enrolment VALUES ('S1','CS101','active')")
    _seed(tmp_db, "INSERT INTO student_enrolment VALUES ('S2','CS101','active')")
    _seed(tmp_db, "INSERT INTO users VALUES ('S1','s1@uni.edu','student')")
    _seed(tmp_db, "INSERT INTO users VALUES ('S2','s2@uni.edu','student')")

    integration_bus.publish_exam_event(
        1, action="published", module_code="CS101",
        exam_title="Final", start_time="2026-05-01 09:00",
        duration_minutes=90, pass_mark=50,
    )

    logs = _query(tmp_db,
                  "SELECT student_id, template_name FROM email_log "
                  "WHERE template_name='exam.scheduled'")
    assert len(logs) == 2
    assert {l["student_id"] for l in logs} == {"S1", "S2"}


# ---------------------------------------------------------------------------
# Feature 11 — hold blocks exam start
# ---------------------------------------------------------------------------

def test_feature11_hold_blocks_exam(tmp_db):
    from education_system.university_system.modules.services import (
        integration_bus, finance_bus,
    )
    finance_bus.place_hold("S1", reason="unpaid tuition", source="finance")
    allowed, reason = integration_bus.can_student_start_exam("S1")
    assert allowed is False
    assert "unpaid" in (reason or "").lower()

    allowed2, _ = integration_bus.can_student_start_exam("S99")
    assert allowed2 is True


# ---------------------------------------------------------------------------
# Feature 12 — exam graded → email student
# ---------------------------------------------------------------------------

def test_feature12_graded_emails_student(tmp_db):
    from education_system.university_system.modules.services import integration_bus

    _seed(tmp_db, "INSERT INTO users VALUES ('S1','s1@uni.edu','student')")

    integration_bus.publish_exam_event(
        7, action="graded", module_code="CS101",
        exam_title="Final", student_id="S1",
        score=80, total_marks=100, percentage=80.0, passed=True,
    )

    logs = _query(tmp_db,
                  "SELECT student_id, template_name, subject FROM email_log "
                  "WHERE template_name='exam.graded'")
    assert len(logs) == 1
    assert "Final" in logs[0]["subject"]


# ---------------------------------------------------------------------------
# Feature 13 — module reschedule → exam room conflict
# ---------------------------------------------------------------------------

def test_feature13_module_reschedule_conflict(tmp_db):
    from education_system.university_system.modules.services import integration_bus
    from education_system.university_system.modules.domain.academics.gui._event_bus import (
        publish, EVENT_MODULE_SCHEDULE_CHANGED,
    )

    _seed(tmp_db,
          "INSERT INTO exam_portal_exams (id, module_code, title, status, "
          "start_time, end_time, room_id) "
          "VALUES (5, 'CS101', 'Midterm', 'published', "
          "'2026-05-10 10:00', '2026-05-10 11:30', 'R1')")
    _seed(tmp_db, "INSERT INTO users VALUES ('admin','a@uni.edu','admin')")

    publish(
        EVENT_MODULE_SCHEDULE_CHANGED,
        module_code="CS101",
        start_time="2026-05-10 10:30",
        end_time="2026-05-10 12:00",
        room_id="R1",
        action="rescheduled",
    )

    log = integration_bus.recent_events(limit=20)
    kinds = [e["payload"].get("kind") for e in log]
    assert "exam_room_conflict" in kinds

    mails = _query(tmp_db,
                   "SELECT subject FROM email_log WHERE template_name='exam.room_conflict'")
    assert mails


# ---------------------------------------------------------------------------
# Feature 14 — finance report through email_bus
# ---------------------------------------------------------------------------

def test_feature14_finance_report_logged(tmp_db):
    from education_system.university_system.modules.services import integration_bus

    _seed(tmp_db, "INSERT INTO users VALUES ('admin','a@uni.edu','admin')")
    msg_id = integration_bus.send_finance_report(
        report_title="Q4 Variance",
        summary="Salaries +3% over budget; bursaries flat.",
    )
    assert msg_id, "should return a message_id"
    rows = _query(tmp_db,
                  "SELECT subject, template_name FROM email_log "
                  "WHERE template_name='finance.report.sent'")
    assert rows
    assert "Q4 Variance" in rows[0]["subject"]


# ---------------------------------------------------------------------------
# Feature 15 — ungraded sweep
# ---------------------------------------------------------------------------

def test_feature15_ungraded_sweep_emails_and_holds(tmp_db):
    from education_system.university_system.modules.services import integration_bus

    _seed(tmp_db,
          "INSERT INTO exam_portal_exams (id, module_code, title, status, created_by) "
          "VALUES (3, 'CS101', 'Quiz', 'published', 'INST1')")
    _seed(tmp_db, "INSERT INTO users VALUES ('INST1','i@uni.edu','staff')")
    # Old attempt: 20 days ago, ungraded → should both email and hold.
    _seed(tmp_db,
          "INSERT INTO exam_portal_attempts (exam_id, student_id, status, submitted_at) "
          "VALUES (3, 'S5', 'submitted', datetime('now','-20 days'))")
    # Recent attempt: 8 days ago → email but no hold.
    _seed(tmp_db,
          "INSERT INTO exam_portal_attempts (exam_id, student_id, status, submitted_at) "
          "VALUES (3, 'S6', 'submitted', datetime('now','-8 days'))")

    result = integration_bus.sweep_ungraded_exams(reminder_after_days=7,
                                                   hold_after_days=14)
    assert result["reminded"] == 2
    assert result["held"] == 1

    holds = _query(tmp_db,
                   "SELECT student_id, source FROM finance_holds "
                   "WHERE source='exam_management'")
    assert len(holds) == 1
    assert holds[0]["student_id"] == "S5"


# ---------------------------------------------------------------------------
# Feature 16 — exam outside term
# ---------------------------------------------------------------------------

def test_feature16_exam_outside_term_refused(tmp_db):
    from education_system.university_system.modules.services import integration_bus
    from education_system.university_system.modules.domain.academics.gui._event_bus import (
        publish, EVENT_TERM_CHANGED,
    )

    publish(EVENT_TERM_CHANGED,
            start_date="2026-01-15", end_date="2026-04-30",
            term="Spring 2026")

    assert integration_bus.is_exam_within_term("2026-02-01 09:00", "2026-02-01 11:00") is True
    assert integration_bus.is_exam_within_term("2026-06-01 09:00", "2026-06-01 11:00") is False
    # Permissive when term unknown
    integration_bus._current_term["start"] = None
    integration_bus._current_term["end"] = None
    assert integration_bus.is_exam_within_term("2099-01-01", "2099-01-02") is True


# ---------------------------------------------------------------------------
# Feature 17 — withdraw cancels attempts + queues refund
# ---------------------------------------------------------------------------

def test_feature17_withdraw_cancels_attempts_and_queues_refund(tmp_db):
    from education_system.university_system.modules.services import integration_bus

    _seed(tmp_db, "INSERT INTO program_fees (course, amount, currency) VALUES ('CS101', 1000, 'GBP')")
    _seed(tmp_db,
          "INSERT INTO exam_portal_exams (id, module_code, title, status) "
          "VALUES (9, 'CS101', 'Q1', 'published')")
    _seed(tmp_db,
          "INSERT INTO exam_portal_attempts (exam_id, student_id, status) "
          "VALUES (9, 'S7', 'in_progress')")

    integration_bus.publish_enrolment_withdrew(
        "S7", "CS101", reason="personal",
    )

    attempts = _query(tmp_db,
                      "SELECT status FROM exam_portal_attempts WHERE student_id='S7'")
    assert attempts[0]["status"] == "cancelled"

    previews = _query(tmp_db,
                      "SELECT student_id, course_code, amount FROM refund_previews")
    assert previews
    assert previews[0]["amount"] == 1000.0
