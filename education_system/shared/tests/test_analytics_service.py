"""Tests for the shared AnalyticsService."""

import sqlite3
from pathlib import Path

import pytest

from education_system.shared.analytics.analytics_service import AnalyticsService


@pytest.fixture()
def temp_dbs(tmp_path):
    """Create temporary DBs with student data for all 4 systems."""
    db_map = {}
    for system, table, id_col in [
        ("primary", "pupils", "pupil_id"),
        ("secondary", "students", "student_id"),
        ("college", "students", "student_id"),
        ("university", "students", "student_id"),
    ]:
        db_file = tmp_path / f"{system}.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute(
            f"""CREATE TABLE {table} (
                {id_col} INTEGER PRIMARY KEY,
                name TEXT,
                status TEXT,
                enrollment_date TEXT
            )"""
        )
        conn.execute(
            f"INSERT INTO {table} (name, status, enrollment_date) "
            f"VALUES ('Alice', 'active', '2024-09-01')"
        )
        conn.execute(
            f"INSERT INTO {table} (name, status, enrollment_date) "
            f"VALUES ('Bob', 'graduated', '2023-09-01')"
        )
        conn.execute(
            f"INSERT INTO {table} (name, status, enrollment_date) "
            f"VALUES ('Charlie', 'transferred', '2023-01-15')"
        )
        conn.commit()
        conn.close()
        db_map[system] = db_file
    return db_map


@pytest.fixture()
def svc(temp_dbs):
    return AnalyticsService(
        primary_db=str(temp_dbs["primary"]),
        secondary_db=str(temp_dbs["secondary"]),
        college_db=str(temp_dbs["college"]),
        university_db=str(temp_dbs["university"]),
    )


class TestSummary:
    def test_total_students(self, svc):
        summary = svc.get_summary()
        assert summary["total_students"] == 12  # 3 per system x 4
        assert len(summary["systems"]) == 4

    def test_active_count(self, svc):
        summary = svc.get_summary()
        assert summary["total_active"] == 4  # 1 active per system

    def test_graduated_count(self, svc):
        summary = svc.get_summary()
        assert summary["total_graduated"] == 4

    def test_transferred_count(self, svc):
        summary = svc.get_summary()
        assert summary["total_transferred"] == 4

    def test_per_system_breakdown(self, svc):
        summary = svc.get_summary()
        for s in summary["systems"]:
            assert s["total"] == 3
            assert s["active"] == 1
            assert s["graduated"] == 1
            assert s["transferred"] == 1


class TestRetention:
    def test_retention_stats(self, svc):
        retention = svc.get_retention_stats()
        assert len(retention) == 4
        for r in retention:
            assert r["total"] == 3
            assert r["active"] == 1
            assert "retained_pct" in r
            assert "dropout_pct" in r


class TestYearTrends:
    def test_returns_trends(self, svc):
        trends = svc.get_year_trends()
        assert len(trends) > 0
        for t in trends:
            assert "year" in t
            assert "student_count" in t
            assert t["student_count"] > 0


class TestTransferRates:
    def test_returns_list(self, svc):
        # No transfer_history table, so may be empty
        rates = svc.get_transfer_rates()
        assert isinstance(rates, list)


class TestExportCSV:
    def test_exports_csv_string(self, svc):
        csv_str = svc.export_summary_csv()
        assert isinstance(csv_str, str)
        assert "System" in csv_str
        assert "Primary School" in csv_str
        assert "University" in csv_str
        lines = csv_str.strip().split("\n")
        assert len(lines) > 5  # headers + data
