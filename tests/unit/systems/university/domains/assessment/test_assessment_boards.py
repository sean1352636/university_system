from __future__ import annotations

import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from education_system.systems.university.infrastructure.database import db as db_module
from education_system.systems.university.infrastructure.database.schemas.core_schemas import (
    init_grade_system_db,
)
from education_system.systems.university.domains.assessment.domain.boards import service
from education_system.systems.university.domains.progression.domain.degree_audit.graduation_eligibility import (
    check_eligibility,
)


@pytest.fixture
def board_db(tmp_path, monkeypatch):
    path = str(tmp_path / "boards.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", path)
    init_grade_system_db()
    with db_module.transaction() as conn:
        conn.execute(
            """INSERT INTO students
                 (student_id, first_name, last_name, course, status, grade_level)
               VALUES ('S1', 'Ada', 'Lovelace', 'CS', 'Active', '3')"""
        )
        conn.execute(
            """INSERT INTO modules
                 (module_code, module_name, credits, course)
               VALUES ('CS301', 'Project', 40, 'CS')"""
        )
        conn.execute(
            """INSERT INTO student_modules
                 (student_id, module_code, grade, status)
               VALUES ('S1', 'CS301', '72', 'Completed')"""
        )
    migration = importlib.import_module(
        "education_system.migrations.versions."
        "3f8b2a1c9d70_core_feature_owned_schemas"
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
    service.ensure_schema()
    return path


def _award_board() -> int:
    return service.create_board(
        "progression_award", "Computing Award Board", "2026/27",
        created_by="secretary", programme_code="CS", chair_id="chair-1",
    )


def test_complete_board_ratifies_and_releases_award(board_db):
    board_id = _award_board()
    assert service.generate_agenda(board_id) == 1
    service.lock_agenda(board_id, actor_id="secretary")
    service.record_decision(
        board_id, "S1", "award", decided_by="board",
        rationale="Programme requirements satisfied",
        classification="First Class",
    )
    service.save_minutes(
        board_id, "The board unanimously approved the award.",
        actor_id="secretary",
    )
    service.chair_approve(board_id, chair_id="chair-1")
    assert service.ratify(board_id, ratified_by="senate") == 1

    award = service.releasable_award("S1")
    assert award is not None
    assert award["classification"] == "First Class"
    assert service.get_board(board_id)["status"] == "ratified"


def test_chair_cannot_approve_with_undecided_agenda(board_db):
    board_id = _award_board()
    service.generate_agenda(board_id)
    service.lock_agenda(board_id, actor_id="secretary")
    # Put the board into the convened state while leaving a second item pending.
    with db_module.transaction() as conn:
        conn.execute(
            """INSERT INTO students
                 (student_id, first_name, last_name, course, status)
               VALUES ('S2', 'Alan', 'Turing', 'CS', 'Active')"""
        )
        conn.execute(
            """INSERT INTO assessment_board_agenda
                 (board_id, student_id, programme_code)
               VALUES (?, 'S2', 'CS')""", (board_id,)
        )
    service.record_decision(
        board_id, "S1", "continue", decided_by="board",
        rationale="Progress satisfactory",
    )
    service.save_minutes(board_id, "Draft minutes", actor_id="secretary")
    with pytest.raises(ValueError, match="Every agenda item"):
        service.chair_approve(board_id, chair_id="chair-1")


def test_compensation_decisions_enforce_board_rules(board_db):
    board_id = service.create_board(
        "module", "CS Module Board", "2026/27", created_by="secretary",
        programme_code="CS", module_code="CS301",
    )
    service.add_rule(
        board_id, "compensation", minimum_mark=35, maximum_credits=20
    )
    service.generate_agenda(board_id)
    service.lock_agenda(board_id, actor_id="secretary")
    with pytest.raises(ValueError, match="credit limit"):
        service.record_decision(
            board_id, "S1", "compensate", decided_by="board",
            rationale="Near pass", confirmed_result="38",
            credits_affected=40, module_code="CS301",
        )
    decision = service.record_decision(
        board_id, "S1", "compensate", decided_by="board",
        rationale="Near pass within approved regulations",
        confirmed_result="38", credits_affected=20, module_code="CS301",
    )
    assert decision > 0


def test_minutes_lock_and_controlled_reopening(board_db):
    board_id = _award_board()
    service.generate_agenda(board_id)
    service.lock_agenda(board_id, actor_id="secretary")
    service.record_decision(
        board_id, "S1", "award", decided_by="board",
        rationale="Complete", classification="Upper Second",
    )
    service.save_minutes(board_id, "Approved minutes", actor_id="secretary")
    service.chair_approve(board_id, chair_id="chair-1")
    service.ratify(board_id, ratified_by="senate")

    with pytest.raises(ValueError, match="independent approval"):
        service.reopen(
            board_id, requested_by="same", approved_by="same",
            reason="Correction",
        )
    correction_id = service.reopen(
        board_id, requested_by="registry", approved_by="deputy-chair",
        reason="Confirmed administrative error",
    )
    assert correction_id > 0
    assert service.releasable_award("S1") is None
    service.save_minutes(
        board_id, "Corrected minutes", actor_id="secretary"
    )
    assert service.get_board(board_id)["version"] == 2


def test_graduation_is_blocked_until_award_ratified(board_db):
    report = check_eligibility("S1")
    assert report["eligible"] is False
    assert report["award_ratified"] is False
    assert any("ratified" in reason for reason in report["reasons"])

    board_id = _award_board()
    service.generate_agenda(board_id)
    service.lock_agenda(board_id, actor_id="secretary")
    service.record_decision(
        board_id, "S1", "award", decided_by="board",
        rationale="Complete", classification="First Class",
    )
    service.save_minutes(board_id, "Minutes", actor_id="secretary")
    service.chair_approve(board_id, chair_id="chair-1")
    service.ratify(board_id, ratified_by="senate")

    report = check_eligibility("S1")
    assert report["eligible"] is True
    assert report["award_ratified"] is True
