"""Focused regression tests for formerly advertised placeholder features."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from education_system.systems.university.domains.finance.domain.reporting.revenue_analytics import agencies
from education_system.systems.university.application.students.bulk_actions import send_bulk_email
from education_system.systems.university.domains.health.domain.health.records import data_purge
from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration import admin_management
from education_system.systems.university.shell.gui.analytics.enhanced_reporting.tabular_io import (
    read_records, write_records,
)


def _transaction_for(path):
    @contextmanager
    def factory():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    return factory


def test_collection_workflow_creates_and_assigns_case(tmp_path, monkeypatch):
    database = tmp_path / "finance.db"
    with sqlite3.connect(database) as conn:
        conn.executescript('''
            CREATE TABLE student_fees(student_fee_id INTEGER PRIMARY KEY, student_id TEXT,
                amount REAL, status TEXT, due_date TEXT);
            CREATE TABLE students(student_id TEXT PRIMARY KEY, email TEXT);
            CREATE TABLE payment_allocations(student_fee_id INTEGER, amount REAL);
            CREATE TABLE collection_cases(case_id INTEGER PRIMARY KEY, student_id TEXT,
                agency_id INTEGER, total_debt REAL, case_status TEXT, assigned_date TEXT,
                resolution_date TEXT, amount_collected REAL DEFAULT 0,
                commission_paid REAL DEFAULT 0, notes TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE collection_agencies(agency_id INTEGER PRIMARY KEY, agency_name TEXT,
                commission_rate REAL, minimum_amount REAL, is_active INTEGER);
            INSERT INTO student_fees VALUES(1, 'S1', 500, 'unpaid', '2020-01-01');
            INSERT INTO students VALUES('S1', 's1@example.test');
            INSERT INTO collection_agencies VALUES(1, 'Agency', 5, 100, 1);
        ''')
    monkeypatch.setattr(agencies, "transaction", _transaction_for(database))
    workflow_id = agencies.save_collection_workflow("Overdue", 100, 14, 30, True)
    assert agencies.run_collection_workflow(workflow_id) == {
        "created": 1, "assigned": 1, "reminded": 0, "escalated": 0,
    }
    with sqlite3.connect(database) as conn:
        assert conn.execute("SELECT case_status FROM collection_cases").fetchone()[0] == "assigned"


def test_bulk_email_reports_individual_failures():
    with patch(
        "education_system.systems.university.infrastructure.email.email_service.send_email",
        side_effect=[True, False],
    ):
        assert send_bulk_email(["a@example.test", "b@example.test"], "Subject", "Body") == {
            "sent": 1, "failed": ["b@example.test"],
        }


def test_reporting_tabular_json_and_csv_round_trip(tmp_path):
    records = [{"student_id": "S1", "name": "Student"}]
    json_path = tmp_path / "students.json"
    csv_path = tmp_path / "students.csv"
    write_records(records, json_path, "json")
    write_records(records, csv_path, "csv")
    assert read_records(json_path) == records
    assert read_records(csv_path) == records


def test_health_purge_writes_recovery_archive_before_delete(tmp_path, monkeypatch):
    database = tmp_path / "health.db"
    with sqlite3.connect(database) as conn:
        conn.execute('''CREATE TABLE health_records(
            id INTEGER PRIMARY KEY, student_id TEXT, record_type TEXT,
            record_date TEXT, description TEXT)''')
        conn.execute("INSERT INTO health_records VALUES(1, 'S1', 'note', '2020-01-01', 'recoverable')")
    monkeypatch.setattr(data_purge, "get_connection", lambda: sqlite3.connect(database))
    monkeypatch.setattr(data_purge, "backup_before_operation", lambda _name: True)
    result = data_purge.purge_health_records("2021-01-01", archive_dir=tmp_path / "archive")
    assert result["deleted"] == 1
    assert "recoverable" in Path(result["archive_path"]).read_text(encoding="utf-8")
    with sqlite3.connect(database) as conn:
        assert conn.execute("SELECT COUNT(*) FROM health_records").fetchone()[0] == 0


def test_support_group_compliance_reports_real_issues():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE peer_support_groups(
        group_id INTEGER PRIMARY KEY, group_name TEXT, facilitator_id TEXT,
        current_members INTEGER, max_members INTEGER, meeting_schedule TEXT,
        status TEXT)''')
    cursor.execute("INSERT INTO peer_support_groups VALUES(1, 'Peer group', NULL, 12, 10, NULL, 'active')")
    report = admin_management.support_group_compliance_report(cursor, conn)
    assert report[0]["status"] == "Review"
    assert {"no facilitator", "no meeting schedule", "over capacity"} <= set(report[0]["issues"])
    conn.close()
