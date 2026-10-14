from __future__ import annotations

import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from education_system.systems.university.domains.admissions.domain.services import (
    admissions_lifecycle as lifecycle,
)
from education_system.systems.university.domains.admissions.domain.services.admissions_crm_core import (
    ApplicationManager,
    ProspectManager,
)
from education_system.systems.university.domains.admissions.domain.services.admissions_policies import (
    RightToStudyPolicy,
)
from education_system.systems.university.infrastructure.database import db as db_module
from education_system.systems.university.infrastructure.database.schemas.admissions_schemas import (
    init_admissions_crm_system_db,
)
from education_system.systems.university.infrastructure.database.schemas.core_schemas import (
    init_grade_system_db,
)


def _upgrade(path: str, revision: str) -> None:
    migration = importlib.import_module(
        f"education_system.migrations.versions.{revision}"
    )
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()


def test_offer_to_registered_student_is_one_atomic_journey(
    tmp_path, monkeypatch
) -> None:
    path = str(tmp_path / "conversion.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", path)
    init_grade_system_db()
    init_admissions_crm_system_db()
    _upgrade(path, "0a7d9c3e5f21_canonical_university_lifecycles")
    _upgrade(path, "7c2e4a9b1d63_university_transactional_outbox")
    _upgrade(path, "91d4e6f2a8b0_admissions_policy_and_consumer_receipts")

    prospect_id = ProspectManager.create_prospect(
        "Ada", "Lovelace", "ada@example.test", date_of_birth="2007-01-01"
    )
    application_id = ApplicationManager.submit_application(
        prospect_id, "undergraduate", "Computing", "2026/27", "autumn"
    )
    choice_id = lifecycle.add_choice(application_id, "COMP", rank=1)
    lifecycle.accept_choice(application_id, choice_id)
    requirement_id = lifecycle.add_requirement(
        application_id, "right_to_study", "Passport"
    )
    lifecycle.verify_requirement(requirement_id, verified_by="compliance")
    RightToStudyPolicy().approve(
        application_id, route="british", evidence_reference="PASS-1",
        actor_id="compliance",
    )
    lifecycle.transition(application_id, lifecycle.READY_TO_ENROL, force=True)

    # External identity linkage is a downstream integration, not part of the
    # source database transaction.
    monkeypatch.setattr(
        "education_system.platform.cross_system.identity_service.link_system",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "education_system.platform.cross_system.identity_service.record_transition",
        lambda *args, **kwargs: None,
    )
    student_id = lifecycle.convert_to_student(application_id, actor_id="registrar")

    with db_module.get_connection() as connection:
        assert connection.execute(
            "SELECT status FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()["status"] == "Active"
        assert connection.execute(
            "SELECT COUNT(*) FROM programme_registrations WHERE student_id = ?",
            (student_id,),
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM student_registrations WHERE student_id = ?",
            (student_id,),
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM student_lifecycle_actions WHERE student_id = ?",
            (student_id,),
        ).fetchone()[0] == 6
        assert connection.execute(
            """SELECT COUNT(*) FROM university_event_outbox
                WHERE event_name = 'admissions.student.converted'
                  AND aggregate_id = ?""",
            (student_id,),
        ).fetchone()[0] == 1

    # Conversion is idempotent and cannot create a second student or event.
    assert lifecycle.convert_to_student(application_id) == student_id
