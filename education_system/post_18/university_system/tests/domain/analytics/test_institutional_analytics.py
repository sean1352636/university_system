"""Tests for the institutional analytics service.

The service computes read-only aggregates over the operational tables
(students, student_modules, courses, payments, student_fees,
student_finance_accounts). Each test seeds a fresh SQLite file with a
minimal subset of those schemas and exercises the service against it.
"""
from __future__ import annotations

import sqlite3

import pytest

from education_system.post_18.university_system.infrastructure.database import db as db_module
from education_system.post_18.university_system.modules.domain.analytics.institutional_analytics.services.institutional_analytics_service import (  # noqa: E501
    InstitutionalAnalyticsError,
    InstitutionalAnalyticsService,
)


SCHEMA = """
CREATE TABLE students (
    student_id TEXT PRIMARY KEY,
    course TEXT,
    status TEXT,
    gender TEXT,
    age INTEGER,
    ucas_tariff INTEGER,
    gpa REAL
);
CREATE TABLE student_modules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT,
    module_code TEXT,
    module_name TEXT,
    status TEXT,
    grade TEXT
);
CREATE TABLE courses (
    id TEXT PRIMARY KEY,
    course_code TEXT,
    course_name TEXT,
    current_enrollment INTEGER,
    max_enrollment INTEGER
);
CREATE TABLE payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT,
    amount REAL,
    payment_method TEXT,
    payment_date TEXT,
    status TEXT
);
CREATE TABLE student_fees (
    student_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT,
    amount REAL,
    status TEXT
);
CREATE TABLE student_finance_accounts (
    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT,
    balance REAL
);
"""


@pytest.fixture
def seeded_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "analytics_test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    # Students: case-varied statuses to exercise normalisation.
    conn.executemany(
        "INSERT INTO students (student_id, course, status, gender, age, ucas_tariff, gpa) "
        "VALUES (?,?,?,?,?,?,?)",
        [
            ("s1", "CS", "Active", "male", 20, 120, 3.5),
            ("s2", "CS", "active", "female", 21, 112, 3.2),
            ("s3", "CS", "Graduated", "male", 23, 128, None),
            ("s4", "DS", "graduated", "other", 24, 104, None),
            ("s5", "DS", "Withdrawn", "female", 22, 96, None),
            ("s6", "DS", "Suspended", None, None, None, None),
        ],
    )
    # Modules: two graded (one pass, one fail), plus in-progress + numeric grade.
    conn.executemany(
        "INSERT INTO student_modules (student_id, module_code, module_name, status, grade) "
        "VALUES (?,?,?,?,?)",
        [
            ("s1", "CIS101", "Programming", "Completed", "First"),   # pass
            ("s2", "CIS101", "Programming", "Failed", "F"),          # fail
            ("s3", "CIS102", "Algorithms", "Completed", "72"),       # numeric pass
            ("s4", "CIS102", "Algorithms", "Completed", "31"),       # numeric fail
            ("s5", "CIS103", "Databases", "Enrolled", None),         # in_progress
        ],
    )
    conn.executemany(
        "INSERT INTO courses (id, course_code, course_name, current_enrollment, max_enrollment) "
        "VALUES (?,?,?,?,?)",
        [
            ("CS", "CS", "Computer Science", 30, 30),   # full
            ("DS", "DS", "Data Science", 10, 40),       # 25%
        ],
    )
    conn.executemany(
        "INSERT INTO payments (student_id, amount, payment_method, payment_date, status) "
        "VALUES (?,?,?,?,?)",
        [
            ("s1", 1000.0, "Card", "2026-01-15", "completed"),
            ("s2", 500.0, "card", "2026-02-10", "completed"),
            ("s3", 250.0, "Cash", "2026-02-20", "completed"),
            ("s4", 999.0, "Card", "2026-03-01", "pending"),   # excluded (not completed)
        ],
    )
    conn.executemany(
        "INSERT INTO student_fees (student_id, amount, status) VALUES (?,?,?)",
        [
            ("s1", 2000.0, "pending"),
            ("s2", 1500.0, "paid"),
            ("s3", 500.0, "waived"),
            ("s5", 800.0, "overdue"),
        ],
    )
    conn.executemany(
        "INSERT INTO student_finance_accounts (student_id, balance) VALUES (?,?)",
        [("s1", 100.0), ("s2", -50.0)],
    )
    conn.commit()
    conn.close()
    yield db_path


@pytest.fixture
def svc(seeded_db):
    return InstitutionalAnalyticsService(seeded_db)


class TestEnrollment:
    def test_totals_and_status_buckets(self, svc):
        d = svc.enrollment_summary()
        assert d["total_students"] == 6
        assert d["current"] == 2       # Active + active
        assert d["completed"] == 2     # Graduated + graduated
        assert d["attrition"] == 2     # Withdrawn + Suspended

    def test_by_course(self, svc):
        d = svc.enrollment_summary()
        by_course = {r["label"]: r["count"] for r in d["by_course"]}
        assert by_course == {"CS": 3, "DS": 3}


class TestRetention:
    def test_overall_rates(self, svc):
        o = svc.retention_metrics()["overall"]
        # retained = current(2) + completed(2) = 4 of 6
        assert o["retention_rate"] == pytest.approx(66.67, abs=0.01)
        assert o["attrition_rate"] == pytest.approx(33.33, abs=0.01)
        assert o["completion_rate"] == pytest.approx(33.33, abs=0.01)

    def test_per_course(self, svc):
        rows = {c["course"]: c for c in svc.retention_metrics()["by_course"]}
        assert rows["CS"]["retention_rate"] == 100.0   # all active/graduated
        assert rows["DS"]["attrition_rate"] == pytest.approx(66.67, abs=0.01)


class TestModulePerformance:
    def test_outcome_classification(self, svc):
        d = svc.module_performance()
        t = d["totals"]
        assert t["enrolments"] == 5
        assert t["pass"] == 2          # First + 72
        assert t["fail"] == 2          # F + 31
        assert t["in_progress"] == 1   # Enrolled/no grade
        assert t["overall_pass_rate"] == 50.0

    def test_per_module_pass_rate(self, svc):
        mods = {m["module_code"]: m for m in svc.module_performance()["modules"]}
        assert mods["CIS101"]["pass_rate"] == 50.0
        assert mods["CIS103"]["pass_rate"] is None   # no graded outcomes

    def test_limit(self, svc):
        assert len(svc.module_performance(limit=1)["modules"]) == 1


class TestCourseCapacity:
    def test_fill_rates(self, svc):
        d = svc.course_capacity()
        assert d["total_enrolled"] == 40
        assert d["total_capacity"] == 70
        assert d["courses_at_capacity"] == 1
        by = {c["course_code"]: c for c in d["courses"]}
        assert by["CS"]["fill_rate"] == 100.0
        assert by["CS"]["at_capacity"] is True
        assert by["DS"]["fill_rate"] == 25.0


class TestFinancialSummary:
    def test_revenue_only_counts_completed(self, svc):
        rev = svc.financial_summary()["revenue"]
        assert rev["collected_total"] == 1750.0   # 1000 + 500 + 250, pending excluded
        assert rev["payment_count"] == 3
        # Card + card normalised together = 1500
        assert rev["by_method"]["card"] == 1500.0

    def test_outstanding_and_waived_fees(self, svc):
        fees = svc.financial_summary()["fees"]
        assert fees["outstanding_total"] == 2800.0  # pending 2000 + overdue 800
        assert fees["waived_total"] == 500.0

    def test_account_balances(self, svc):
        acct = svc.financial_summary()["accounts"]
        assert acct["account_count"] == 2
        assert acct["total_balance"] == 50.0


class TestOverview:
    def test_headline_and_no_errors(self, svc):
        ov = svc.institutional_overview()
        assert ov["errors"] == {}
        h = ov["headline"]
        assert h["total_students"] == 6
        assert h["module_pass_rate"] == 50.0
        assert h["revenue_collected"] == 1750.0

    def test_missing_table_is_reported_not_raised(self, tmp_path, monkeypatch):
        # A DB with only students -> other sections degrade into errors.
        db_path = str(tmp_path / "partial.db")
        monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE students (student_id TEXT, course TEXT, status TEXT)")
        conn.execute("INSERT INTO students VALUES ('s1','CS','Active')")
        conn.commit()
        conn.close()
        ov = InstitutionalAnalyticsService(db_path).institutional_overview()
        assert ov["headline"]["total_students"] == 1
        assert "capacity" in ov["errors"]     # no courses table
        assert "modules" in ov["errors"]      # no student_modules table


class TestValidation:
    def test_missing_students_table_raises(self, tmp_path):
        db_path = str(tmp_path / "empty.db")
        sqlite3.connect(db_path).close()
        with pytest.raises(InstitutionalAnalyticsError):
            InstitutionalAnalyticsService(db_path).enrollment_summary()
