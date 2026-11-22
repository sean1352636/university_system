from __future__ import annotations

import importlib
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from education_system.systems.university.infrastructure.database import db as db_module
from education_system.systems.university.domains.research.domain.research.pgr import service


@pytest.fixture
def pgr_db(tmp_path, monkeypatch):
    path = str(tmp_path / "pgr.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", path)
    migration = importlib.import_module(
        "education_system.migrations.versions."
        "3f8b2a1c9d70_core_feature_owned_schemas"
    )
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        connection.exec_driver_sql("""
            CREATE TABLE pgr_overdue_escalations (
                escalation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER, source_type TEXT, source_id INTEGER,
                due_date TEXT, severity TEXT, owner TEXT,
                status TEXT DEFAULT 'open', escalated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_type, source_id, status)
            )
        """)
    service.ensure_schema()
    return path


def _project() -> int:
    return service.create_project(
        "PGR1", "Reliable distributed education platforms",
        "Research into dependable distributed student systems.",
        created_by="doctoral-college", department="Computing",
        start_date="2026-10-01", expected_end_date="2030-09-30",
    )


def test_proposal_supervision_training_reviews_and_milestones(pgr_db):
    project = _project()
    service.add_supervisor(
        project, "SUP1", "primary", workload_fte=0.6,
        start_date="2026-10-01",
    )
    service.add_supervisor(
        project, "SUP2", "secondary", workload_fte=0.4,
        start_date="2026-10-01",
    )
    with pytest.raises(ValueError, match="exceeds"):
        service.add_supervisor(
            project, "SUP3", "advisor", workload_fte=0.1,
            start_date="2026-10-01",
        )

    service.log_supervision(
        project, "2026-10-15T10:00:00", ["PGR1", "SUP1"],
        progress_summary="Scope agreed",
        actions=[{"owner": "PGR1", "action": "Draft literature review"}],
        created_by="SUP1",
    )
    service.add_training_need(
        project, "methods", "Advanced qualitative methods",
        planned_activity="Doctoral training workshop",
    )
    review = service.schedule_review(project, 1, "2027-09-01")
    service.decide_review(
        review, "satisfactory", panel=["SUP2", "PANEL1"],
        approved_by="doctoral-director",
    )
    milestone = service.add_milestone(
        project, "annual_review", "Year 2 review", "2028-09-01"
    )
    service.extend_milestone(
        milestone, "2028-10-01", reason="Approved medical extension",
        approved_by="doctoral-director",
    )

    record = service.project_record(project)
    assert len(record["supervisors"]) == 2
    assert len(record["meetings"]) == 1
    assert record["reviews"][0]["outcome"] == "satisfactory"
    assert record["milestones"][0]["status"] == "extended"
    assert service.supervisor_workload("SUP1")["total_fte"] == pytest.approx(0.6)


def test_mphil_upgrade_to_phd(pgr_db):
    project = _project()
    service.set_registration(project, "MPhil", actor_id="doctoral-college")
    upgrade = service.submit_upgrade(
        project, "DOC-UPGRADE-1", ["PANEL1", "PANEL2"]
    )
    service.decide_upgrade(
        upgrade, "approved", decided_by="doctoral-director"
    )
    assert service.project_record(project)["status"] == "registered_phd"


def test_thesis_viva_corrections_and_final_deposit(pgr_db):
    project = _project()
    service.set_registration(project, "PhD", actor_id="doctoral-college")
    service.record_approval(
        project, "research_ethics", reference="ETH-1",
        status="approved", approved_by="ethics-chair",
    )
    submission = service.submit_thesis(
        project, "Reliable Platforms", "REPO-DRAFT-1",
        declaration_accepted=True,
    )
    assert submission > 0
    internal = service.nominate_examiner(
        project, "EX1", "internal", institution="This University",
        expertise="Distributed systems", conflict_declaration="No conflict",
        nominated_by="SUP1",
    )
    external = service.nominate_examiner(
        project, "EX2", "external", institution="Other University",
        expertise="Education platforms", conflict_declaration="No conflict",
        nominated_by="SUP1",
    )
    service.approve_examiner(internal, approved_by="doctoral-director")
    service.approve_examiner(external, approved_by="doctoral-director")
    service.schedule_viva(
        project, "2030-11-01T10:00:00", location="Boardroom",
        chair_id="CHAIR1",
    )
    service.record_viva_outcome(
        project, "minor_corrections", decided_by="CHAIR1",
        corrections_due="2031-02-01", corrections="Correct chapter 4",
    )
    with db_module.get_connection() as conn:
        correction = conn.execute(
            "SELECT correction_id FROM pgr_corrections WHERE project_id = ?",
            (project,),
        ).fetchone()[0]
    service.approve_corrections(correction, approved_by="EX2")
    deposit = service.final_deposit(
        project, "REPO-FINAL-1", licence="CC-BY-NC",
        checked_by="repository-team",
    )
    assert deposit > 0
    assert service.project_record(project)["status"] == "completed"


def test_viva_requires_both_approved_examiner_types(pgr_db):
    project = _project()
    service.set_registration(project, "PhD", actor_id="doctoral-college")
    service.submit_thesis(
        project, "Thesis", "REPO-1", declaration_accepted=True
    )
    nomination = service.nominate_examiner(
        project, "EX1", "internal", institution="Here", expertise="Topic",
        conflict_declaration="None", nominated_by="SUP1",
    )
    service.approve_examiner(nomination, approved_by="director")
    with pytest.raises(ValueError, match="internal and external"):
        service.schedule_viva(
            project, "2030-01-01T10:00:00", location="Room",
            chair_id="CHAIR",
        )


def test_overdue_milestones_escalate_once_and_stay_separate_from_taught_assessment(pgr_db):
    project = _project()
    service.add_milestone(project, "review", "Overdue review", "2027-01-01")
    assert service.escalate_overdue(as_of="2027-05-01") == 1
    assert service.escalate_overdue(as_of="2027-05-01") == 0
    source = Path(service.__file__).read_text(encoding="utf-8")
    assert "domain.assessment" not in source
    with db_module.get_connection() as conn:
        row = conn.execute("SELECT * FROM pgr_overdue_escalations").fetchone()
        assert row["severity"] == "critical"
