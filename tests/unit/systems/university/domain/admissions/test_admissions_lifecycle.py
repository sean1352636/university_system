from __future__ import annotations

import importlib
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from education_system.systems.university.infrastructure.database import db as db_module
from education_system.systems.university.infrastructure.database.schemas.admissions_schemas import (
    init_admissions_crm_system_db,
)
from education_system.systems.university.domains.admissions.domain.services.admissions_crm_core import (
    ApplicationManager,
    ProspectManager,
)
from education_system.systems.university.domains.admissions.domain.services import (
    admissions_lifecycle as lifecycle,
)
from education_system.systems.university.domains.admissions.domain.services.admissions_policies import (
    DepositPolicy,
    RightToStudyPolicy,
)
from education_system.systems.university.services.boundary_errors import (
    AdmissionsBoundaryError,
)


@pytest.fixture
def admissions_db(tmp_path, monkeypatch):
    path = str(tmp_path / "admissions.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", path)
    init_admissions_crm_system_db()
    migration = importlib.import_module(
        "education_system.migrations.versions."
        "91d4e6f2a8b0_admissions_policy_and_consumer_receipts"
    )
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
    return path


def _application() -> int:
    prospect = ProspectManager.create_prospect(
        "Ada", "Lovelace", "ada@example.test", date_of_birth="2007-01-01"
    )
    return ApplicationManager.submit_application(
        prospect, "undergraduate", "BSc Computing", "2026/27", "autumn"
    )


def test_multiple_choices_and_full_checklist(admissions_db):
    application_id = _application()
    first = lifecycle.add_choice(
        application_id, "CS", programme_name="BSc Computing", rank=1
    )
    lifecycle.add_choice(
        application_id, "MATH", programme_name="BSc Mathematics", rank=2
    )
    lifecycle.accept_choice(application_id, first)
    requirement = lifecycle.add_requirement(
        application_id, "identity", "Passport or birth certificate"
    )
    condition = lifecycle.add_condition(
        application_id, "deposit", "Pay international deposit",
        amount=3000, currency="GBP",
    )
    lifecycle.schedule_activity(
        application_id, "2026-03-01T10:00:00", activity_type="audition"
    )

    lifecycle.verify_requirement(requirement, verified_by="admissions-1")
    lifecycle.satisfy_condition(condition, evidence_reference="PAY-123")
    DepositPolicy(3000).decide(
        application_id, received_amount=3000,
        payment_reference="PAY-123", actor_id="finance",
    )
    application = lifecycle.get_application(application_id)

    assert len(application["choices"]) == 2
    assert application["accepted_choice_id"] == first
    assert application["requirements"][0]["status"] == "verified"
    assert application["conditions"][0]["status"] == "satisfied"
    assert application["interviews"][0]["activity_type"] == "audition"


def test_state_machine_rejects_skipping_to_enrolment(admissions_db):
    application_id = _application()
    with pytest.raises(
        AdmissionsBoundaryError, match="Invalid admissions transition"
    ):
        lifecycle.transition(application_id, lifecycle.ENROLLED)


def test_transition_history_is_audited(admissions_db):
    application_id = _application()
    lifecycle.transition(
        application_id, lifecycle.DOCUMENTS_PENDING,
        reason="Checklist generated", actor_id="staff-7",
    )
    lifecycle.transition(application_id, lifecycle.UNDER_REVIEW)
    application = lifecycle.get_application(application_id)

    assert application["status"] == lifecycle.UNDER_REVIEW
    assert [row["to_status"] for row in application["history"]] == [
        lifecycle.DOCUMENTS_PENDING,
        lifecycle.UNDER_REVIEW,
    ]
    assert application["history"][0]["actor_id"] == "staff-7"


def test_readiness_requires_choice_checks_and_conditions(admissions_db):
    application_id = _application()
    choice = lifecycle.add_choice(application_id, "LAW")
    requirement = lifecycle.add_requirement(
        application_id, "right_to_study", "Verify immigration status"
    )
    condition = lifecycle.add_condition(
        application_id, "academic", "Achieve ABB"
    )
    lifecycle.transition(application_id, lifecycle.UNDER_REVIEW)
    lifecycle.transition(application_id, lifecycle.CONDITIONAL_OFFER)
    lifecycle.transition(application_id, lifecycle.ACCEPTED)
    lifecycle.transition(application_id, lifecycle.CONDITIONS_MET)
    lifecycle.transition(application_id, lifecycle.RIGHT_TO_STUDY)
    lifecycle.transition(application_id, lifecycle.READY_TO_ENROL)

    issues = lifecycle.readiness_issues(application_id)
    assert "no accepted programme choice" in issues
    assert "required documents/checks remain outstanding" in issues
    assert "offer, deposit or sponsorship conditions remain outstanding" in issues

    lifecycle.accept_choice(application_id, choice)
    lifecycle.verify_requirement(requirement, verified_by="compliance")
    lifecycle.satisfy_condition(condition, evidence_reference="RESULTS-1")
    RightToStudyPolicy().approve(
        application_id, route="british", evidence_reference="PASSPORT-1",
        actor_id="compliance",
    )
    assert lifecycle.readiness_issues(application_id) == []
