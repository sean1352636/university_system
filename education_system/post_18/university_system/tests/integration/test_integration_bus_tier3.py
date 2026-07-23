"""Tier-3 integration tests: events, internships, admissions,
complaints, health appointments."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db(monkeypatch):
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE users (
            user_id TEXT PRIMARY KEY, email TEXT, role TEXT
        );
        CREATE TABLE kpi_metrics (
            kpi_id INTEGER PRIMARY KEY AUTOINCREMENT,
            kpi_name TEXT, kpi_category TEXT,
            current_value REAL, target_value REAL,
            measurement_date TEXT, period TEXT, trend TEXT
        );
        CREATE TABLE admission_applications (
            application_id INTEGER PRIMARY KEY,
            prospect_id TEXT,
            decision TEXT,
            decision_date TEXT,
            status TEXT,
            application_fee_paid INTEGER DEFAULT 0
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
        CREATE TABLE disciplinary_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT, offense_type TEXT, severity TEXT,
            description TEXT, date_occurred TEXT, date_reported TEXT,
            reported_by TEXT, location TEXT, status TEXT DEFAULT 'Open'
        );
        CREATE TABLE module_schedule (
            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT, day_of_week TEXT,
            start_time TEXT, end_time TEXT,
            enrolled INTEGER DEFAULT 0, capacity INTEGER DEFAULT 50
        );
        CREATE TABLE student_enrolment (
            student_id TEXT, module_code TEXT, status TEXT
        );
        CREATE TABLE health_appointments (
            appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT, appointment_type TEXT,
            appointment_date TEXT, appointment_time TEXT,
            provider TEXT, reason TEXT, status TEXT,
            scheduled_at TEXT
        );
        """
    )
    conn.commit(); conn.close()

    from education_system.post_18.university_system.infrastructure.database import db as db_mod

    def fake_get(*_a, **_k):
        c = sqlite3.connect(str(db_path))
        c.row_factory = sqlite3.Row
        return c

    class FakeTx:
        def __enter__(self): self.conn = fake_get(); return self.conn
        def __exit__(self, *exc):
            try: self.conn.commit()
            finally: self.conn.close()

    def fake_tx(*_a, **_k): return FakeTx()

    monkeypatch.setattr(db_mod, "get_connection", fake_get)
    monkeypatch.setattr(db_mod, "transaction", fake_tx)

    from education_system.post_18.university_system.modules.services import (
        integration_bus, email_bus, finance_bus, cases_bus,
    )
    monkeypatch.setattr(integration_bus, "get_connection", fake_get)
    monkeypatch.setattr(integration_bus, "transaction", fake_tx)
    monkeypatch.setattr(email_bus, "get_connection", fake_get)
    monkeypatch.setattr(finance_bus, "get_connection", fake_get)
    monkeypatch.setattr(cases_bus, "get_connection", fake_get)
    monkeypatch.setattr(email_bus, "_attempt_send", lambda r, s, b: True)

    from education_system.post_18.university_system.modules.domain.academics.gui import _event_bus
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
# #8 — event check-in → engagement KPI
# ---------------------------------------------------------------------------

def test_event_check_in_bumps_engagement_kpi(tmp_db):
    from education_system.post_18.university_system.modules.services import integration_bus

    integration_bus.publish_event_attendance(
        event_id=1, user_id="S1", event_name="Open Day",
    )
    integration_bus.publish_event_attendance(
        event_id=2, user_id="S2", event_name="Career fair",
    )

    rows = _query(tmp_db,
                  "SELECT current_value FROM kpi_metrics "
                  "WHERE kpi_name='Student Engagement'")
    assert rows and rows[0]["current_value"] == 2


# ---------------------------------------------------------------------------
# #9 — internship placement → KPI + employer email
# ---------------------------------------------------------------------------

def test_internship_placement_bumps_kpi_and_emails_supervisor(tmp_db):
    from education_system.post_18.university_system.modules.services import integration_bus

    integration_bus.publish_internship_placement(
        placement_id=99, student_id="S1", internship_id=5,
        company="Acme Co", supervisor_email="boss@acme.com",
        start_date="2026-06-01", end_date="2026-08-31",
    )

    kpi = _query(tmp_db,
                 "SELECT current_value FROM kpi_metrics "
                 "WHERE kpi_name='Internship Placements'")
    assert kpi and kpi[0]["current_value"] == 1

    mails = _query(tmp_db,
                   "SELECT student_id, template_name FROM email_log "
                   "WHERE template_name='careers.engagement.started'")
    assert mails
    assert mails[0]["student_id"] == "boss@acme.com"


# ---------------------------------------------------------------------------
# #10 — admissions decision → yield KPI + app fee
# ---------------------------------------------------------------------------

def test_admissions_accept_charges_fee_and_updates_yield(tmp_db):
    from education_system.post_18.university_system.modules.services import integration_bus

    # Three decisions: 2 accepted, 1 rejected → yield = 66.67%
    _seed(tmp_db,
          "INSERT INTO admission_applications "
          "(application_id, prospect_id, decision, status, application_fee_paid) "
          "VALUES (1, 'P1', 'accepted', 'decision_made', 0)")
    _seed(tmp_db,
          "INSERT INTO admission_applications "
          "(application_id, prospect_id, decision, status, application_fee_paid) "
          "VALUES (2, 'P2', 'rejected', 'decision_made', 0)")
    _seed(tmp_db,
          "INSERT INTO admission_applications "
          "(application_id, prospect_id, decision, status, application_fee_paid) "
          "VALUES (3, 'P3', 'accepted', 'decision_made', 1)")

    integration_bus.publish_admissions_decision(
        application_id=1, decision="accepted",
        applicant_id="P1", fee_paid=False,
    )

    txns = _query(tmp_db,
                  "SELECT amount, reference_id FROM student_finance_transactions "
                  "WHERE student_id='P1'")
    assert txns
    assert txns[0]["amount"] == 25.0  # default
    assert txns[0]["reference_id"] == "admission_app:1"

    kpi = _query(tmp_db,
                 "SELECT current_value FROM kpi_metrics "
                 "WHERE kpi_name='Yield Rate'")
    assert kpi
    assert abs(kpi[0]["current_value"] - 66.66666666666667) < 0.001


def test_admissions_accept_with_paid_fee_no_charge(tmp_db):
    from education_system.post_18.university_system.modules.services import integration_bus

    integration_bus.publish_admissions_decision(
        application_id=2, decision="accepted",
        applicant_id="P2", fee_paid=True,
    )
    txns = _query(tmp_db,
                  "SELECT * FROM student_finance_transactions WHERE student_id='P2'")
    assert txns == []


# ---------------------------------------------------------------------------
# #11 — urgent complaint → cases_bus + dean email
# ---------------------------------------------------------------------------

def test_urgent_complaint_opens_case_and_emails_dean(tmp_db):
    from education_system.post_18.university_system.modules.services import integration_bus

    _seed(tmp_db, "INSERT INTO users VALUES ('DEAN1','dean@uni.edu','dean_of_students')")

    integration_bus.publish_complaint_filed(
        complaint_id="C001", user_id="S5",
        email="s5@uni.edu", category="harassment",
        priority="urgent", subject="Need help",
    )

    cases = _query(tmp_db,
                   "SELECT user_id, severity FROM disciplinary_records")
    assert cases and cases[0]["user_id"] == "S5"
    assert cases[0]["severity"] == "critical"

    mails = _query(tmp_db,
                   "SELECT student_id, template_name FROM email_log "
                   "WHERE template_name='case.opened'")
    assert mails and mails[0]["student_id"] == "DEAN1"


def test_low_priority_complaint_does_not_escalate(tmp_db):
    from education_system.post_18.university_system.modules.services import integration_bus

    integration_bus.publish_complaint_filed(
        complaint_id="C002", user_id="S6",
        priority="low", subject="Minor",
    )
    cases = _query(tmp_db, "SELECT * FROM disciplinary_records")
    assert cases == []


# ---------------------------------------------------------------------------
# #12 — health appointment → calendar conflict
# ---------------------------------------------------------------------------

def test_health_appointment_clash_flags_and_emails(tmp_db):
    from education_system.post_18.university_system.modules.services import integration_bus

    # Wednesday 10:00 class
    _seed(tmp_db,
          "INSERT INTO module_schedule "
          "(module_code, day_of_week, start_time, end_time) "
          "VALUES ('CS101','Wednesday','10:00','11:00')")
    _seed(tmp_db,
          "INSERT INTO student_enrolment VALUES ('S7','CS101','active')")
    _seed(tmp_db,
          "INSERT INTO health_appointments "
          "(appointment_id, student_id, appointment_type, appointment_date, "
          " appointment_time, provider, status) "
          "VALUES (1, 'S7', 'GP', '2026-05-06', '10:30', 'Dr Who', 'scheduled')")
    # 2026-05-06 is a Wednesday

    integration_bus.publish_health_appointment(
        appointment_id=1, student_id="S7",
        appointment_date="2026-05-06",
        appointment_time="10:30",
        provider="Dr Who",
        appointment_type="GP",
    )

    rows = _query(tmp_db,
                  "SELECT has_conflict FROM health_appointments WHERE appointment_id=1")
    assert rows[0]["has_conflict"] == 1

    mails = _query(tmp_db,
                   "SELECT student_id, template_name FROM email_log "
                   "WHERE template_name='hs.incident.logged'")
    assert mails and mails[0]["student_id"] == "S7"


def test_health_appointment_no_clash_no_action(tmp_db):
    from education_system.post_18.university_system.modules.services import integration_bus

    # No class enrolled, no clash possible
    _seed(tmp_db,
          "INSERT INTO health_appointments "
          "(appointment_id, student_id, appointment_type, appointment_date, "
          " appointment_time, provider, status) "
          "VALUES (2, 'S8', 'GP', '2026-05-06', '14:00', 'Dr Who', 'scheduled')")

    integration_bus.publish_health_appointment(
        appointment_id=2, student_id="S8",
        appointment_date="2026-05-06",
        appointment_time="14:00",
    )

    mails = _query(tmp_db,
                   "SELECT * FROM email_log "
                   "WHERE template_name='hs.incident.logged' AND student_id='S8'")
    assert mails == []
