"""Tests for the cross-module integration_bus.

Each test exercises one of the nine cross-module features end-to-end:
publisher → event bus → subscriber → side-effect on the consumer
table.

Tests run against a fresh SQLite file so writes don't leak into the
shared dev DB.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(monkeypatch):
    """Point get_connection() at a fresh SQLite file for the duration of one test."""
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test.db"

    # Pre-create the schema we need across the suite.
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE clearing_vacancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT, course_name TEXT, department TEXT,
            available_places INTEGER DEFAULT 0,
            minimum_tariff INTEGER DEFAULT 0,
            requirements TEXT, is_active INTEGER DEFAULT 1,
            academic_year TEXT,
            updated_at TEXT
        );
        CREATE TABLE clearing_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            applicant_name TEXT, email TEXT, phone TEXT, ucas_id TEXT,
            tariff_points INTEGER, qualifications TEXT, preferred_course TEXT,
            status TEXT DEFAULT 'pending', applied_at TEXT,
            processed_by TEXT, processed_at TEXT, notes TEXT
        );
        CREATE TABLE adjustment_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT, original_course TEXT, requested_course TEXT,
            reason TEXT, current_grades TEXT,
            status TEXT DEFAULT 'pending', requested_at TEXT,
            decided_by TEXT, decided_at TEXT
        );
        CREATE TABLE module_schedule (
            schedule_id INTEGER PRIMARY KEY,
            module_code TEXT, day_of_week TEXT, start_time TEXT, end_time TEXT,
            enrolled INTEGER DEFAULT 0, capacity INTEGER DEFAULT 50
        );
        CREATE TABLE program_fees (
            id INTEGER PRIMARY KEY,
            course TEXT, amount REAL, currency TEXT,
            due_date TEXT, academic_year TEXT
        );
        CREATE TABLE kpi_metrics (
            kpi_id INTEGER PRIMARY KEY AUTOINCREMENT,
            kpi_name TEXT, kpi_category TEXT,
            current_value REAL, target_value REAL,
            measurement_date TEXT, period TEXT, trend TEXT
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
        CREATE TABLE student_plans (
            plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT, academic_year TEXT
        );
        CREATE TABLE plan_courses (
            plan_id INTEGER, course_code TEXT, status TEXT,
            PRIMARY KEY (plan_id, course_code)
        );
        CREATE TABLE faculty_schedule_blocks (
            block_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT, day_of_week TEXT,
            start_time TEXT, end_time TEXT,
            activity_type TEXT, course_code TEXT,
            is_locked INTEGER DEFAULT 0
        );
        CREATE TABLE payroll_periods (
            period_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, period_type TEXT,
            start_date TEXT, end_date TEXT,
            status TEXT DEFAULT 'open',
            contracted_hours REAL
        );
        CREATE TABLE employees (
            user_id TEXT PRIMARY KEY,
            employee_id TEXT, department TEXT,
            job_title TEXT, salary REAL
        );
        """
    )
    conn.commit()
    conn.close()

    # Patch get_connection across the bus modules.
    from education_system.systems.university.infrastructure.database import db as db_mod
    real_get = db_mod.get_connection
    real_tx = db_mod.transaction

    def fake_get(*_a, **_k):
        c = sqlite3.connect(str(db_path))
        c.row_factory = sqlite3.Row
        return c

    class FakeTx:
        def __enter__(self):
            self.conn = fake_get()
            return self.conn

        def __exit__(self, *exc):
            try:
                self.conn.commit()
            finally:
                self.conn.close()

    def fake_tx(*_a, **_k):
        return FakeTx()

    monkeypatch.setattr(db_mod, "get_connection", fake_get)
    monkeypatch.setattr(db_mod, "transaction", fake_tx)
    # The bus modules import these names at module import time.
    from education_system.systems.university.services.bus import (
        finance_bus, integration_bus,
    )
    monkeypatch.setattr(finance_bus, "get_connection", fake_get)
    monkeypatch.setattr(integration_bus, "get_connection", fake_get)
    monkeypatch.setattr(integration_bus, "transaction", fake_tx)

    # Reset bus subscribers across tests.
    from education_system.systems.university.interfaces.gui.academics import _event_bus
    _event_bus.reset_for_tests()
    integration_bus.reset_for_tests()
    integration_bus.wire_subscribers()

    yield db_path

    _event_bus.reset_for_tests()
    integration_bus.reset_for_tests()


def _seed(db_path: Path, sql: str, params: tuple = ()):
    conn = sqlite3.connect(str(db_path))
    conn.execute(sql, params)
    conn.commit()
    conn.close()


def _query(db_path: Path, sql: str, params: tuple = ()):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Feature 1 — clearing acceptance
# ---------------------------------------------------------------------------

def test_feature1_clearing_acceptance_fanout(tmp_db):
    from education_system.systems.university.services.bus import integration_bus

    _seed(tmp_db,
          "INSERT INTO module_schedule (module_code, day_of_week, start_time, end_time, enrolled) "
          "VALUES ('CS101','Mon','09:00','10:00', 5)")
    _seed(tmp_db,
          "INSERT INTO kpi_metrics (kpi_name, kpi_category, current_value, target_value) "
          "VALUES ('New Enrolments','enrollment', 100, 200)")

    integration_bus.publish_clearing_accepted(
        application_id=42, course_code="CS101",
        ucas_id="U777", applicant_name="A. Test",
    )

    enrolled = _query(tmp_db, "SELECT enrolled FROM module_schedule WHERE module_code='CS101'")
    assert enrolled[0]["enrolled"] == 6, "module_schedule enrolment should bump"

    kpi = _query(tmp_db, "SELECT current_value FROM kpi_metrics WHERE kpi_category='enrollment'")
    assert kpi[0]["current_value"] == 101

    log = _query(tmp_db, "SELECT event_name FROM integration_log WHERE event_name LIKE 'course%'")
    assert log, "event should be logged in integration_log"


# ---------------------------------------------------------------------------
# Feature 3 — adjustment approved
# ---------------------------------------------------------------------------

def test_feature3_adjustment_swaps_plan_and_bills(tmp_db):
    from education_system.systems.university.services.bus import integration_bus

    _seed(tmp_db,
          "INSERT INTO student_plans (plan_id, student_id, academic_year) VALUES (1,'S001','2025/26')")
    _seed(tmp_db,
          "INSERT INTO plan_courses (plan_id, course_code, status) VALUES (1,'CS100','in_progress')")
    _seed(tmp_db,
          "INSERT INTO program_fees (course, amount, currency) VALUES ('CS100', 1000, 'GBP')")
    _seed(tmp_db,
          "INSERT INTO program_fees (course, amount, currency) VALUES ('CS200', 1500, 'GBP')")

    integration_bus.publish_adjustment_approved(
        request_id=7, student_id="S001",
        from_course="CS100", to_course="CS200",
    )

    plan = _query(tmp_db, "SELECT course_code FROM plan_courses WHERE plan_id=1")
    assert plan[0]["course_code"] == "CS200", "plan_courses should swap"

    txns = _query(tmp_db,
                  "SELECT amount, reference_id FROM student_finance_transactions "
                  "WHERE student_id='S001' ORDER BY transaction_id")
    refs = {t["reference_id"] for t in txns}
    assert any("credit" in (r or "") for r in refs)
    assert any("debit" in (r or "") for r in refs)


# ---------------------------------------------------------------------------
# Feature 4 — locked timetable → KPI utilisation
# ---------------------------------------------------------------------------

def test_feature4_lock_timetable_updates_kpi(tmp_db):
    from education_system.systems.university.services.bus import integration_bus

    _seed(tmp_db,
          "INSERT INTO faculty_schedule_blocks (user_id, day_of_week, start_time, end_time, is_locked) "
          "VALUES ('U1','Mon','09:00','12:00', 1)")
    _seed(tmp_db,
          "INSERT INTO faculty_schedule_blocks (user_id, day_of_week, start_time, end_time, is_locked) "
          "VALUES ('U1','Tue','13:00','15:00', 1)")

    integration_bus.publish_timetable_locked(["U1"], academic_year="2025/26")

    kpi = _query(tmp_db, "SELECT kpi_name FROM kpi_metrics WHERE kpi_name='Staff Utilisation'")
    assert kpi, "Staff Utilisation KPI should be created"


# ---------------------------------------------------------------------------
# Feature 5 — degree audit sweep
# ---------------------------------------------------------------------------

def test_feature5_degree_audit_writes_grad_forecast(tmp_db):
    from education_system.systems.university.services.bus import integration_bus

    _seed(tmp_db,
          "INSERT INTO student_plans (plan_id, student_id, academic_year) VALUES (1,'S001','2024')")
    _seed(tmp_db,
          "INSERT INTO student_plans (plan_id, student_id, academic_year) VALUES (2,'S002','2024')")
    _seed(tmp_db,
          "INSERT INTO plan_courses (plan_id, course_code, status) VALUES (1,'CS100','completed')")
    _seed(tmp_db,
          "INSERT INTO plan_courses (plan_id, course_code, status) VALUES (2,'CS100','pending')")

    result = integration_bus.run_degree_audit_sweep(cohort_year=2024)
    assert result["total"] == 2
    assert result["on_track"] == 1
    assert result["rate"] == 0.5

    kpi = _query(tmp_db,
                 "SELECT current_value FROM kpi_metrics WHERE kpi_name='Graduation Forecast'")
    assert kpi and kpi[0]["current_value"] == 50.0


# ---------------------------------------------------------------------------
# Feature 6 — KPI demand forecast → suggested places
# ---------------------------------------------------------------------------

def test_feature6_demand_forecast_writes_suggested_places(tmp_db):
    from education_system.systems.university.services.bus import integration_bus

    _seed(tmp_db,
          "INSERT INTO clearing_vacancies (course_code, course_name, available_places, academic_year) "
          "VALUES ('CS101','Intro CS', 10, '2025/26')")

    integration_bus.publish_demand_forecast(
        course_code="CS101", predicted_enrollment=42,
        academic_year="2025/26",
    )

    rows = _query(tmp_db,
                  "SELECT suggested_places FROM clearing_vacancies WHERE course_code='CS101'")
    assert rows[0]["suggested_places"] == 42


# ---------------------------------------------------------------------------
# Feature 7 — appraisal → merit pay proposal
# ---------------------------------------------------------------------------

def test_feature7_appraisal_creates_merit_proposal(tmp_db):
    from education_system.systems.university.services.bus import integration_bus

    _seed(tmp_db,
          "INSERT INTO employees (user_id, salary, job_title) VALUES ('U1', 50000, 'Lecturer')")

    calls = []

    def fake_add_allowance(**kwargs):
        calls.append(kwargs)
        return 1

    with patch(
        "education_system.systems.university.domain.staff.staff_hr."
        "services.managers.payroll_manager.PayrollManager.add_allowance",
        side_effect=fake_add_allowance,
    ):
        integration_bus.publish_appraisal_completed(
            user_id="U1", cycle_id=3, rating=4.6,
        )

    assert calls, "PayrollManager.add_allowance should be called"
    assert calls[0]["allowance_type"] == "merit_proposal"
    # 4.6 → 5% band → 50000 * 0.05 = 2500
    assert calls[0]["amount"] == 2500.0
    assert calls[0]["is_active"] is False


# ---------------------------------------------------------------------------
# Feature 8 — cert expiry → KPI risk gauge
# ---------------------------------------------------------------------------

def test_feature8_cert_sweep_publishes_and_sets_kpi(tmp_db):
    from education_system.systems.university.services.bus import integration_bus

    _seed(tmp_db,
          "INSERT INTO employees (user_id, salary, job_title) VALUES ('U1', 50000, 'Compliance Officer')")
    _seed(tmp_db,
          "INSERT INTO employees (user_id, salary, job_title) VALUES ('U2', 40000, 'Cleaner')")

    rows = [
        {"user_id": "U1", "name": "GDPR cert", "expiry_date": "2099-12-31",
         "certification_id": 11},
        {"user_id": "U2", "name": "Generic cert", "expiry_date": "2099-12-31",
         "certification_id": 12},
    ]
    with patch(
        "education_system.systems.university.domain.staff.staff_hr."
        "services.managers.training_manager.TrainingManager.get_expiring_certs",
        return_value=rows,
    ):
        n = integration_bus.sweep_expiring_certifications(within_days=30)

    assert n == 2
    kpi = _query(tmp_db,
                 "SELECT current_value FROM kpi_metrics WHERE kpi_name='Compliance Risk'")
    assert kpi and kpi[0]["current_value"] == 50.0  # 1 of 2 critical


# ---------------------------------------------------------------------------
# Feature 9 — waitlist promotion atomic
# ---------------------------------------------------------------------------

def test_feature9_waitlist_promote_enrols_and_bills(tmp_db):
    from education_system.systems.university.services.bus import integration_bus

    _seed(tmp_db,
          "INSERT INTO student_plans (plan_id, student_id, academic_year) VALUES (10,'S99','2025/26')")
    _seed(tmp_db,
          "INSERT INTO module_schedule (module_code, day_of_week, start_time, end_time, enrolled) "
          "VALUES ('CS300','Wed','10:00','11:00', 20)")
    _seed(tmp_db,
          "INSERT INTO program_fees (course, amount, currency) VALUES ('CS300', 800, 'GBP')")

    ok = integration_bus.promote_from_waitlist("S99", "CS300", plan_id=10)
    assert ok is True

    plan = _query(tmp_db, "SELECT status FROM plan_courses WHERE plan_id=10 AND course_code='CS300'")
    assert plan and plan[0]["status"] == "in_progress"

    sched = _query(tmp_db, "SELECT enrolled FROM module_schedule WHERE module_code='CS300'")
    assert sched[0]["enrolled"] == 21

    txns = _query(tmp_db,
                  "SELECT amount FROM student_finance_transactions "
                  "WHERE student_id='S99'")
    assert txns and txns[0]["amount"] == 800.0


# ---------------------------------------------------------------------------
# Integration log
# ---------------------------------------------------------------------------

def test_integration_log_records_events(tmp_db):
    from education_system.systems.university.services.bus import integration_bus

    integration_bus.log_and_publish(
        "course.changed", source="test",
        action="clearing_accepted", course_code="CS101",
    )
    rows = integration_bus.recent_events(limit=5)
    assert rows
    assert rows[0]["event_name"] == "course.changed"
    assert rows[0]["payload"]["action"] == "clearing_accepted"
