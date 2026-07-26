"""Tier-1 integration tests: disciplinary, safeguarding, accommodation."""

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
        CREATE TABLE users (
            user_id TEXT PRIMARY KEY,
            email TEXT, role TEXT
        );
        CREATE TABLE disciplinary_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT, offense_type TEXT, severity TEXT,
            description TEXT, date_occurred TEXT, date_reported TEXT,
            reported_by TEXT, location TEXT, status TEXT DEFAULT 'Open'
        );
        CREATE TABLE exam_portal_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER, student_id TEXT, status TEXT,
            time_remaining INTEGER DEFAULT 3600,
            score REAL, percentage REAL, passed INTEGER,
            submitted_at TEXT, graded_at TEXT
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
    conn.commit(); conn.close()

    from education_system.systems.university.infrastructure.database import db as db_mod

    def fake_get(*_a, **_k):
        c = sqlite3.connect(str(db_path))
        c.row_factory = sqlite3.Row
        return c

    class FakeTx:
        def __enter__(self):
            self.conn = fake_get(); return self.conn
        def __exit__(self, *exc):
            try: self.conn.commit()
            finally: self.conn.close()

    def fake_tx(*_a, **_k):
        return FakeTx()

    monkeypatch.setattr(db_mod, "get_connection", fake_get)
    monkeypatch.setattr(db_mod, "transaction", fake_tx)

    from education_system.systems.university.services.bus import (
        integration_bus, email_bus, cases_bus, finance_bus,
    )
    monkeypatch.setattr(integration_bus, "get_connection", fake_get)
    monkeypatch.setattr(integration_bus, "transaction", fake_tx)
    monkeypatch.setattr(email_bus, "get_connection", fake_get)
    monkeypatch.setattr(cases_bus, "get_connection", fake_get)
    monkeypatch.setattr(finance_bus, "get_connection", fake_get)
    monkeypatch.setattr(email_bus, "_attempt_send", lambda r, s, b: True)

    from education_system.systems.university.interfaces.gui.academics import _event_bus
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
# Item 2 — health risk → safeguarding case + DSL email
# ---------------------------------------------------------------------------

def test_high_risk_assessment_opens_case_and_emails_dsl(tmp_db):
    from education_system.systems.university.services.bus import integration_bus

    _seed(tmp_db, "INSERT INTO users VALUES ('DSL1','dsl@uni.edu','safeguarding_lead')")

    integration_bus.publish_health_risk_assessment(
        student_id="S77", assessment_type="Mental Health Risk",
        risk_score=85, risk_factors=["isolation"],
        assessed_by="nurse1",
    )

    cases = _query(tmp_db,
                   "SELECT user_id, severity, description FROM disciplinary_records")
    assert len(cases) == 1
    assert cases[0]["user_id"] == "S77"
    assert "Mental Health" in cases[0]["description"]

    mails = _query(tmp_db,
                   "SELECT student_id, template_name FROM email_log "
                   "WHERE template_name='hs.incident.logged'")
    assert mails
    assert mails[0]["student_id"] == "DSL1"


def test_low_risk_assessment_does_not_escalate(tmp_db):
    from education_system.systems.university.services.bus import integration_bus

    integration_bus.publish_health_risk_assessment(
        student_id="S88", assessment_type="General Health Risk",
        risk_score=30,
    )

    cases = _query(tmp_db, "SELECT * FROM disciplinary_records")
    assert cases == []
    mails = _query(tmp_db, "SELECT * FROM email_log")
    assert mails == []


# ---------------------------------------------------------------------------
# Item 3 — accommodation approved → exam tag + time bump
# ---------------------------------------------------------------------------

def test_accommodation_tags_in_progress_attempt(tmp_db):
    from education_system.systems.university.services.bus import integration_bus

    _seed(tmp_db,
          "INSERT INTO exam_portal_attempts (id, exam_id, student_id, status, time_remaining) "
          "VALUES (1, 7, 'S5', 'in_progress', 3600)")

    integration_bus.publish_accommodation_decision(
        request_id=12, student_id="S5", status="approved",
        accommodation_type="extended_time", extended_time_pct=25,
        separate_room=True,
    )

    rows = _query(tmp_db,
                  "SELECT accommodation_notes, time_remaining "
                  "FROM exam_portal_attempts WHERE id = 1")
    assert "extended_time" in (rows[0]["accommodation_notes"] or "")
    assert "25%" in (rows[0]["accommodation_notes"] or "")
    assert "separate room" in (rows[0]["accommodation_notes"] or "")
    # +25% on 3600 = 4500
    assert rows[0]["time_remaining"] == 4500


def test_accommodation_does_not_modify_graded_attempts(tmp_db):
    from education_system.systems.university.services.bus import integration_bus

    _seed(tmp_db,
          "INSERT INTO exam_portal_attempts (id, exam_id, student_id, status, time_remaining) "
          "VALUES (2, 7, 'S5', 'graded', 3600)")

    integration_bus.publish_accommodation_decision(
        request_id=13, student_id="S5", status="approved",
        accommodation_type="extra_time", extended_time_pct=50,
    )

    rows = _query(tmp_db,
                  "SELECT accommodation_notes, time_remaining "
                  "FROM exam_portal_attempts WHERE id = 2")
    # Still 3600 — graded attempts are immune
    assert rows[0]["time_remaining"] == 3600
    assert (rows[0]["accommodation_notes"] or "") == ""


def test_accommodation_rejected_is_no_op(tmp_db):
    from education_system.systems.university.services.bus import integration_bus

    _seed(tmp_db,
          "INSERT INTO exam_portal_attempts (id, exam_id, student_id, status, time_remaining) "
          "VALUES (3, 7, 'S5', 'in_progress', 3600)")

    integration_bus.publish_accommodation_decision(
        request_id=14, student_id="S5", status="rejected",
        accommodation_type="extra_time", extended_time_pct=25,
    )

    rows = _query(tmp_db,
                  "SELECT time_remaining FROM exam_portal_attempts WHERE id = 3")
    assert rows[0]["time_remaining"] == 3600
