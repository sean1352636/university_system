from __future__ import annotations

import pytest
import importlib
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from education_system.systems.university.infrastructure.database import db as db_module
from education_system.systems.university.infrastructure.database.schemas.core_schemas import (
    init_grade_system_db,
)
from education_system.systems.university.infrastructure.database.schemas.admissions_schemas import (
    init_admissions_crm_system_db,
)
from education_system.systems.university.domain.learners import student_lifecycle as lifecycle
from education_system.systems.university.services.boundary_errors import (
    EnrolmentBoundaryError,
)


@pytest.fixture
def student_db(tmp_path, monkeypatch):
    path = str(tmp_path / "student_lifecycle.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", path)
    init_grade_system_db()
    init_admissions_crm_system_db()
    migration = importlib.import_module(
        "education_system.migrations.versions."
        "0a7d9c3e5f21_canonical_university_lifecycles"
    )
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        outbox = importlib.import_module(
            "education_system.migrations.versions."
            "7c2e4a9b1d63_university_transactional_outbox"
        )
        outbox.op = Operations(MigrationContext.configure(connection))
        outbox.upgrade()
        connection.exec_driver_sql("""
            CREATE TABLE student_lifecycle_corrections (
                correction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                history_id INTEGER UNIQUE, reversal_history_id INTEGER,
                reason TEXT, requested_by TEXT, approved_by TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
    with db_module.transaction() as conn:
        conn.execute(
            """INSERT INTO students
                 (student_id, first_name, last_name, course, status)
               VALUES ('S1', 'Ada', 'Lovelace', 'CS', 'Active')"""
        )
        conn.execute(
            """INSERT INTO modules (module_code, module_name, course)
               VALUES ('CS101', 'Introduction', 'CS')"""
        )
        conn.execute(
            """INSERT INTO student_modules
                 (student_id, module_code, status)
               VALUES ('S1', 'CS101', 'Enrolled')"""
        )
    return path


def test_annual_registration_and_reregistration(student_db, monkeypatch):
    monkeypatch.setattr(lifecycle, "_publish", lambda *a, **k: None)
    first = lifecycle.register(
        "S1", "2026/27", actor_id="registrar",
        mode_of_study="full-time", campus_code="MAIN",
        declarations={"terms_accepted": True},
    )
    assert first > 0
    with pytest.raises(Exception):
        lifecycle.register("S1", "2026/27", actor_id="registrar", returning=True)

    second = lifecycle.register(
        "S1", "2027/28", actor_id="registrar", returning=True
    )
    assert second > first
    assert [h["action"] for h in lifecycle.history("S1")] == [
        "annual_registration", "re-registration"
    ]


def test_interruption_pauses_modules_and_resumption_restores(student_db, monkeypatch):
    monkeypatch.setattr(lifecycle, "_publish", lambda *a, **k: None)
    lifecycle.change_status(
        "S1", "interrupt", actor_id="registry", reason="Health",
        expected_return_date="2027-01-10",
    )
    with db_module.get_connection() as conn:
        student = conn.execute(
            "SELECT status, expected_return_date FROM students WHERE student_id='S1'"
        ).fetchone()
        module = conn.execute(
            "SELECT status FROM student_modules WHERE student_id='S1'"
        ).fetchone()
    assert student["status"] == "Interrupted"
    assert student["expected_return_date"] == "2027-01-10"
    assert module["status"] == "Paused"

    lifecycle.change_status(
        "S1", "resume", actor_id="registry", reason="Returned"
    )
    with db_module.get_connection() as conn:
        assert conn.execute(
            "SELECT status FROM student_modules WHERE student_id='S1'"
        ).fetchone()["status"] == "Enrolled"


def test_programme_mode_campus_and_repeat_year(student_db, monkeypatch):
    monkeypatch.setattr(lifecycle, "_publish", lambda *a, **k: None)
    lifecycle.change_study(
        "S1", actor_id="registry", reason="Approved transfer",
        programme_code="MATH",
    )
    lifecycle.change_study(
        "S1", actor_id="registry", reason="Work commitments",
        mode_of_study="part-time",
    )
    lifecycle.change_study(
        "S1", actor_id="registry", reason="Relocation", campus_code="CITY"
    )
    lifecycle.change_study(
        "S1", actor_id="board", reason="Progression decision",
        repeat_year=2, academic_year="2027/28",
    )
    with db_module.get_connection() as conn:
        row = conn.execute(
            "SELECT course, mode_of_study, campus_code, grade_level, "
            "academic_year FROM students WHERE student_id='S1'"
        ).fetchone()
    assert tuple(row) == ("MATH", "part-time", "CITY", "2", "2027/28")


def test_every_change_queues_all_downstream_systems(student_db, monkeypatch):
    monkeypatch.setattr(lifecycle, "_publish", lambda *a, **k: None)
    lifecycle.change_status(
        "S1", "suspend", actor_id="registry", reason="Temporary suspension"
    )
    pending = lifecycle.pending_actions()
    assert {row["target_system"] for row in pending} == set(
        lifecycle.DOWNSTREAM_SYSTEMS
    )
    lifecycle.complete_action(pending[0]["action_id"])
    remaining = lifecycle.pending_actions()
    assert len(remaining) == len(lifecycle.DOWNSTREAM_SYSTEMS) - 1


def test_completion_then_permanent_closure(student_db, monkeypatch):
    monkeypatch.setattr(lifecycle, "_publish", lambda *a, **k: None)
    lifecycle.change_status(
        "S1", "complete", actor_id="registry", reason="Award complete"
    )
    lifecycle.change_status(
        "S1", "close", actor_id="records", reason="Retention closure"
    )
    with db_module.get_connection() as conn:
        row = conn.execute(
            "SELECT status, record_closed_at FROM students WHERE student_id='S1'"
        ).fetchone()
    assert row["status"] == "Closed"
    assert row["record_closed_at"]


def test_unknown_lifecycle_action_is_typed(student_db):
    with pytest.raises(EnrolmentBoundaryError, match="Unknown lifecycle action"):
        lifecycle.change_status(
            "S1", "invented", actor_id="registry", reason="Invalid request"
        )


def test_controlled_reversal_and_reconciliation_dashboard(student_db):
    history_id = lifecycle.change_status(
        "S1", "suspend", actor_id="registry", reason="Temporary suspension"
    )
    reversal_id = lifecycle.reverse_change(
        history_id, reason="Decision entered against wrong student",
        requested_by="registry-a", approved_by="registry-b",
    )
    assert reversal_id > history_id
    with db_module.get_connection() as conn:
        assert conn.execute(
            "SELECT status FROM students WHERE student_id='S1'"
        ).fetchone()["status"] == "Active"
    dashboard = lifecycle.reconciliation_dashboard()
    assert dashboard["summary"]
