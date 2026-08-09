from __future__ import annotations

import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from education_system.systems.university.infrastructure.database import db as db_module
from education_system.systems.university.domain.academics.programme_governance import (
    service,
)


@pytest.fixture
def governance_db(tmp_path, monkeypatch):
    path = str(tmp_path / "governance.db")
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
            CREATE TABLE historical_degree_audits (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT, assignment_id INTEGER,
                regulation_version_id INTEGER, input_json TEXT,
                result_json TEXT, snapshot_hash TEXT, calculated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
    service.ensure_schema()
    return path


def _approved_programme():
    programme, proposal = service.create_proposal(
        "BSC-CS", "BSc Computer Science", "BSc", "2027/28",
        created_by="school", rationale="Replace legacy programme",
        market_need="Strong demand", strategic_alignment="Digital strategy",
        owning_school="Computing",
    )
    business = service.record_business_case(
        proposal, forecast_students={"2027": 100},
        income={"tuition": 900000}, costs={"staff": 500000},
        staffing_plan="Six FTE", facilities_plan="Existing labs",
        risk_register="Recruitment risk",
    )
    service.approve_business_case(business, approved_by="finance-committee")
    version = service.create_version(
        programme, "2027/28",
        curriculum={
            "modules": [
                {"code": "CS101", "credits": 20, "core": True},
                {"code": "CS102", "credits": 20, "core": True},
            ]
        },
        regulations={
            "credits_required": 360,
            "classification": {"first": 70, "upper_second": 60},
        },
        created_by="programme-leader",
    )
    committee = service.create_committee(
        "Academic Validation Committee", "validation", 3
    )
    service.validate_version(
        version, committee, "2026-12-01", ["A", "B", "C"],
        external_advisers=["External 1"], outcome="approved", conditions=[],
        minutes_reference="MIN-1", chair_id="A",
    )
    service.approve_version(version, approved_by="senate")
    return programme, version


def test_full_proposal_business_case_validation_and_approval(governance_db):
    programme, version = _approved_programme()
    effective = service.effective_version(programme, "2027/28")
    assert effective["version_id"] == version
    assert effective["snapshot_hash"]


def test_approved_versions_are_immutable_and_amendments_copy(governance_db):
    programme, version = _approved_programme()
    with pytest.raises(ValueError, match="immutable"):
        service.amend_draft(
            version, curriculum={"modules": []}, actor_id="leader"
        )
    amendment, new_version = service.propose_amendment(
        version, "module", "Replace CS102", "No effect on current students",
        requested_by="leader", effective_academic_year="2028/29",
    )
    assert amendment > 0
    service.amend_draft(
        new_version,
        curriculum={"modules": [{"code": "CS201", "credits": 20}]},
        actor_id="leader",
    )
    with db_module.get_connection() as conn:
        old = conn.execute(
            "SELECT curriculum_json FROM programme_versions WHERE version_id=?",
            (version,),
        ).fetchone()[0]
        new = conn.execute(
            "SELECT curriculum_json FROM programme_versions WHERE version_id=?",
            (new_version,),
        ).fetchone()[0]
    assert "CS101" in old
    assert "CS201" in new


def test_student_keeps_assigned_regulation_snapshot(governance_db):
    programme, version = _approved_programme()
    service.assign_student(
        "S1", programme, version, assigned_by="registry",
        reason="Version effective at first enrolment",
    )
    snapshot = service.regulation_for_student("S1")
    assert snapshot["version_id"] == version
    assert snapshot["regulations"]["credits_required"] == 360
    assert snapshot["curriculum"]["modules"][0]["code"] == "CS101"

    first_audit = service.record_historical_degree_audit(
        "S1", {"CS101": 70, "CS102": 65}
    )
    _amendment, new_version = service.propose_amendment(
        version, "curriculum", "Replace core modules", "Future cohorts only",
        requested_by="leader", effective_academic_year="2028/29",
    )
    service.amend_draft(
        new_version,
        curriculum={"modules": [{"code": "NEW999", "credits": 120, "core": True}]},
        actor_id="leader",
    )
    second_audit = service.record_historical_degree_audit(
        "S1", {"CS101": 70, "CS102": 65}
    )
    assert second_audit == first_audit


def test_accreditation_teach_out_suspension_and_closure(governance_db):
    programme, version = _approved_programme()
    accreditation = service.record_accreditation(
        programme, "BCS", "accredited", version_id=version,
        accreditation_reference="BCS-2027", valid_from="2027-09-01",
        valid_until="2032-08-31",
    )
    assert accreditation > 0
    service.set_programme_status(
        programme, "suspended", actor_id="senate",
        reason="No recruitment for one year",
    )
    with pytest.raises(ValueError, match="teach-out"):
        service.set_programme_status(
            programme, "closed", actor_id="senate", reason="Closure"
        )
    service.create_teach_out(
        programme, version_id=version, last_intake_year="2029/30",
        final_delivery_year="2032/33",
        student_communication="Individual communication plan",
        staffing_commitment="Modules staffed through completion",
        module_availability={"CS101": ["2029", "2030"]},
        approved_by="senate",
    )
    service.set_programme_status(
        programme, "closed", actor_id="senate",
        reason="Teach-out approved",
    )
    with db_module.get_connection() as conn:
        status = conn.execute(
            "SELECT status FROM governed_programmes WHERE programme_id=?",
            (programme,),
        ).fetchone()[0]
    assert status == "closed"


def test_validation_requires_approved_business_case(governance_db):
    programme, _proposal = service.create_proposal(
        "BA-X", "BA Experimental", "BA", "2027/28",
        created_by="school", rationale="Test",
    )
    version = service.create_version(
        programme, "2027/28", curriculum={}, regulations={},
        created_by="leader",
    )
    committee = service.create_committee("Second Committee", "validation", 1)
    with pytest.raises(ValueError, match="business case"):
        service.validate_version(
            version, committee, "2026-01-01", ["A"],
            external_advisers=[], outcome="approved", conditions=[],
            minutes_reference="M", chair_id="A",
        )
