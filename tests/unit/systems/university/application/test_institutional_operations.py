from __future__ import annotations

import json

from education_system.systems.university.application import (
    case_management, connectors, timetabling,
)
from education_system.systems.university.domains.learners.application import alumni_transition, identity_management
from education_system.systems.university.infrastructure.database import db as db_module


def _schema(conn) -> None:
    conn.executescript("""
        CREATE TABLE students (
            student_id TEXT PRIMARY KEY, first_name TEXT, middle_name TEXT,
            last_name TEXT, dob TEXT, gender TEXT, email_address TEXT, status TEXT
        );
        CREATE TABLE institutional_cases (
            case_id TEXT PRIMARY KEY, case_type TEXT, subject_id TEXT, status TEXT DEFAULT 'open',
            summary TEXT, owner_id TEXT, confidentiality TEXT, opened_by TEXT,
            opened_at TEXT DEFAULT CURRENT_TIMESTAMP, closed_at TEXT,
            UNIQUE(case_type, subject_id, summary)
        );
        CREATE TABLE institutional_case_events (
            event_id INTEGER PRIMARY KEY, case_id TEXT, event_type TEXT,
            payload_json TEXT, actor_id TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE student_identity_changes (
            change_id TEXT PRIMARY KEY, student_id TEXT, change_type TEXT,
            before_json TEXT, after_json TEXT, reason TEXT, requested_by TEXT,
            approved_by TEXT, reversed_at TEXT, reversed_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE student_identity_merges (
            merge_id TEXT PRIMARY KEY, survivor_id TEXT, merged_id TEXT UNIQUE,
            reason TEXT, requested_by TEXT, approved_by TEXT, status TEXT DEFAULT 'active',
            reversed_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE timetable_versions (
            version_id TEXT PRIMARY KEY, academic_year TEXT, status TEXT DEFAULT 'draft',
            input_hash TEXT, schedule_json TEXT, created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, published_at TEXT
        );
        CREATE TABLE timetable_change_requests (
            request_id TEXT PRIMARY KEY, version_id TEXT, reason TEXT,
            proposed_json TEXT, requested_by TEXT, approved_by TEXT,
            status TEXT DEFAULT 'pending', created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE connector_configurations (
            connector_name TEXT PRIMARY KEY, enabled INTEGER, config_json TEXT,
            status TEXT, last_checked_at TEXT, last_error TEXT
        );
        CREATE TABLE connector_receipts (
            connector_name TEXT, idempotency_key TEXT, external_reference TEXT,
            outcome TEXT, processed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(connector_name, idempotency_key)
        );
        CREATE TABLE alumni_transition_steps (
            student_id TEXT, step_name TEXT, status TEXT, details_json TEXT,
            completed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(student_id, step_name)
        );
        CREATE TABLE university_event_outbox (
            event_id TEXT PRIMARY KEY, event_name TEXT, event_version INTEGER,
            aggregate_id TEXT, correlation_id TEXT, causation_id TEXT,
            idempotency_key TEXT UNIQUE, payload_json TEXT, available_at TEXT,
            attempts INTEGER DEFAULT 0, delivered_at TEXT, dead_lettered_at TEXT,
            last_error TEXT
        );
        INSERT INTO students(student_id, first_name, last_name, status)
        VALUES ('S1','Ada','Lovelace','Completed'), ('S2','Duplicate','Person','Inactive');
    """)


def test_shared_cases_identity_timetable_connectors_and_alumni(tmp_path, monkeypatch) -> None:
    path = str(tmp_path / "operations.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", path)
    with db_module.transaction() as conn:
        _schema(conn)

    for case_type in case_management.CASE_TYPES:
        case_id = case_management.open_case(
            case_type, "S1", f"{case_type} summary", opened_by="case-team"
        )
        case_management.transition_case(
            case_id, "investigation", actor_id="investigator", reason="Evidence received"
        )
        assert case_management.case_record(case_id)["status"] == "investigation"

    identity_management.correct_identity(
        "S1", {"last_name": "Byron"}, reason="Legal evidence",
        requested_by="registry-a", approved_by="registry-b",
    )
    merge_id = identity_management.merge_students(
        "S1", "S2", reason="Duplicate record",
        requested_by="registry-a", approved_by="registry-b",
    )
    identity_management.reverse_merge(
        merge_id, reversed_by="registry-c", reason="Merge matched wrong person"
    )

    version = timetabling.optimise(
        [
            {"activity_id": "A", "staff_id": "T1", "cohorts": ["C1"]},
            {"activity_id": "B", "staff_id": "T1", "cohorts": ["C2"]},
        ],
        ["MON-09", "MON-10"], ["R1"], academic_year="2027/28", created_by="planner",
    )
    timetabling.publish(version, approved_by="registrar")
    assert len(timetabling.published_schedule()) == 2

    delivered: list[str] = []
    for name in connectors.SUPPORTED_CONNECTORS:
        connectors.configure(name, {"endpoint": f"https://example.test/{name}"})
        adapter = lambda payload, connector=name: delivered.append(connector) or f"REF-{connector}"
        assert connectors.deliver(name, "K1", {"student": "S1"}, adapter)
        assert not connectors.deliver(name, "K1", {"student": "S1"}, adapter)
    assert set(delivered) == set(connectors.SUPPORTED_CONNECTORS)

    calls: list[str] = []
    adapters = {
        step: (lambda student_id, current=step: calls.append(current) or {"ok": True})
        for step in alumni_transition.STEPS
    }
    assert alumni_transition.transition_to_alumni("S1", adapters) == 5
    assert alumni_transition.transition_to_alumni("S1", adapters) == 0
    with db_module.get_connection() as conn:
        assert conn.execute(
            "SELECT status FROM students WHERE student_id='S1'"
        ).fetchone()["status"] == "Alumni"
        assert json.loads(conn.execute(
            "SELECT payload_json FROM university_event_outbox"
        ).fetchone()[0])["student_id"] == "S1"
