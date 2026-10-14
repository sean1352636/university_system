"""Degree apprentices hold two authoritative records under one journey."""

from __future__ import annotations

import sqlite3

import pytest

from education_system.platform.cross_system import enrolments, identity_service
from education_system.platform.identity.auth.db import connect as auth_connect
from education_system.platform.integrations.external import cross_system_bus
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.infrastructure.persistence.schema import connect
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    degree_apprenticeship_repository,
)
from education_system.systems.apprenticeships.infrastructure.integrations import degree_events
from education_system.systems.apprenticeships.infrastructure.integrations.university_gateway import (
    UniversityGateway,
    UniversityRegistration,
)
from education_system.systems.apprenticeships.services import degree_apprenticeship_service
from education_system.systems.university.services.bus import (
    degree_apprenticeship_events as university_degree_events,
)


class FakeUniversityGateway:
    def __init__(self, journey_id: str, student_id: str = "U100") -> None:
        self.journey_id = journey_id
        self.student_id = student_id

    def registration(self, student_id: str, degree_program_id: int):
        return UniversityRegistration(
            student_id=self.student_id, journey_id=self.journey_id,
            student_name="Jo Bell", student_status="Active",
            degree_program_id=degree_program_id, degree_program_code="BSC-SE",
            degree_program_name="Software Engineering", credits_required=360,
            credits_earned=120, academic_status="in_progress",
            completion_percentage=33.3,
        )


def _prepare_degree_cohort(cohort, admin, platform_db):
    programme_id = cohort["programme"].programme_id
    with connect() as conn:
        conn.execute("UPDATE programmes SET level=6 WHERE programme_id=?", (programme_id,))
    mapping = degree_apprenticeship_service.map_programme(
        admin, programme_id, 42, credits_required=360,
    )
    journey_id = identity_service.get_or_create_journey(
        first_name="Jo", last_name="Bell", date_of_birth="2003-05-01",
        system="apprenticeships", student_id=str(cohort["apprentice_id"]),
        db_path=str(platform_db),
    )
    return mapping, journey_id


def test_link_creates_two_active_enrolments_and_is_idempotent(cohort, admin, tmp_path):
    platform_db = tmp_path / "auth.db"
    mapping, journey_id = _prepare_degree_cohort(cohort, admin, platform_db)
    gateway = FakeUniversityGateway(journey_id)

    first = degree_apprenticeship_service.link_learner(
        admin, cohort["apprentice_id"], journey_id=journey_id,
        university_student_id="U100", university_gateway=gateway,
        platform_db_path=str(platform_db),
        grant_account_access=False,
    )
    second = degree_apprenticeship_service.link_learner(
        admin, cohort["apprentice_id"], journey_id=journey_id,
        university_student_id="U100", university_gateway=gateway,
        platform_db_path=str(platform_db),
        grant_account_access=False,
    )

    assert first.link_id == second.link_id
    assert first.status == "Active"
    active = enrolments.active_enrolments(journey_id, db_path=str(platform_db))
    assert {(row["system"], row["local_student_id"]) for row in active} == {
        ("apprenticeships", str(cohort["apprentice_id"])), ("university", "U100")
    }
    assert mapping.university_degree_program_id == 42


def test_university_journey_mismatch_is_refused(cohort, admin, tmp_path):
    platform_db = tmp_path / "auth.db"
    _, journey_id = _prepare_degree_cohort(cohort, admin, platform_db)
    with pytest.raises(ValidationError, match="different learner journey"):
        degree_apprenticeship_service.link_learner(
            admin, cohort["apprentice_id"], journey_id=journey_id,
            university_student_id="U100", university_gateway=FakeUniversityGateway("other"),
            platform_db_path=str(platform_db),
            grant_account_access=False,
        )


def test_academic_progress_is_read_from_university_owner(cohort, admin, tmp_path):
    platform_db = tmp_path / "auth.db"
    _, journey_id = _prepare_degree_cohort(cohort, admin, platform_db)
    gateway = FakeUniversityGateway(journey_id)
    degree_apprenticeship_service.link_learner(
        admin, cohort["apprentice_id"], journey_id=journey_id,
        university_student_id="U100", university_gateway=gateway,
        platform_db_path=str(platform_db),
        grant_account_access=False,
    )
    progress = degree_apprenticeship_service.academic_progress(
        cohort["learner"], cohort["apprentice_id"], university_gateway=gateway
    )
    assert progress["credits_earned"] == 120
    link = degree_apprenticeship_repository.get_link(cohort["apprentice_id"])
    assert link is not None
    assert link.last_academic_sync_at is not None
    with connect() as conn:
        columns = {row[1] for row in conn.execute(
            "PRAGMA table_info(degree_apprenticeship_links)"
        )}
    assert "credits_earned" not in columns


def test_real_gateway_reads_university_database_read_only(tmp_path):
    db_path = tmp_path / "university.db"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE students (
          student_id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT,
          status TEXT, journey_id TEXT);
        CREATE TABLE degree_programs (
          program_id INTEGER PRIMARY KEY, program_code TEXT, program_name TEXT,
          total_credits_required REAL, is_active INTEGER);
        CREATE TABLE student_degree_progress (
          student_id TEXT, program_id INTEGER, total_credits_earned REAL,
          completion_percentage REAL, status TEXT, last_updated TEXT);
        INSERT INTO students VALUES ('U100', 'Jo', 'Bell', 'Active', 'journey-1');
        INSERT INTO degree_programs VALUES (42, 'BSC-SE', 'Software Engineering', 360, 1);
        INSERT INTO student_degree_progress VALUES ('U100', 42, 120, 33.3, 'in_progress', '2026-08-10');
    """)
    conn.commit()
    conn.close()
    result = UniversityGateway(db_path).registration("U100", 42)
    assert result.journey_id == "journey-1"
    assert result.credits_earned == 120


def test_shared_account_receives_both_learner_roles(tmp_path):
    platform_db = tmp_path / "auth.db"
    identity_service.get_or_create_journey(
        first_name="Jo", last_name="Bell", date_of_birth="2003-05-01",
        system="apprenticeships", student_id="1", db_path=str(platform_db),
    )
    conn = auth_connect(str(platform_db))
    conn.execute(
        "INSERT INTO users (username, password_hash) VALUES ('apprentice1', 'unused')"
    )
    conn.commit()
    conn.close()
    degree_apprenticeship_service.grant_shared_account_access(
        "apprentice1", platform_db_path=str(platform_db)
    )
    conn = auth_connect(str(platform_db))
    roles = {(r["system_key"], r["role"]) for r in conn.execute(
        """SELECT us.system_key, us.role FROM user_systems us
             JOIN users u ON u.id=us.user_id WHERE u.username='apprentice1'"""
    )}
    conn.close()
    assert roles == {("apprenticeships", "apprentice"), ("university", "student")}


def test_duplicate_academic_event_is_projected_once(cohort, admin, tmp_path):
    platform_db = tmp_path / "auth.db"
    _, journey_id = _prepare_degree_cohort(cohort, admin, platform_db)
    degree_apprenticeship_service.link_learner(
        admin, cohort["apprentice_id"], journey_id=journey_id,
        university_student_id="U100", university_gateway=FakeUniversityGateway(journey_id),
        platform_db_path=str(platform_db), grant_account_access=False,
    )
    envelope = {
        "event_id": "academic-event-1",
        "event_name": cross_system_bus.EVENT_UNIVERSITY_CREDITS_UPDATED,
        "journey_id": journey_id,
        "payload": {
            "university_student_id": "U100", "university_degree_program_id": 42,
            "degree_program_code": "BSC-SE", "degree_program_name": "Software Engineering",
            "registration_status": "Active", "credits_earned": 180,
            "credits_required": 360, "modules_completed": 12,
            "academic_standing": "Good standing",
        },
    }
    degree_events._consume_academic(envelope)
    degree_events._consume_academic(envelope)
    projection = degree_apprenticeship_repository.academic_projection(
        cohort["apprentice_id"]
    )
    assert projection is not None
    assert projection["credits_earned"] == 180
    assert projection["modules_completed"] == 12


def test_mismatched_event_flags_reconciliation(cohort, admin, tmp_path):
    platform_db = tmp_path / "auth.db"
    _, journey_id = _prepare_degree_cohort(cohort, admin, platform_db)
    degree_apprenticeship_service.link_learner(
        admin, cohort["apprentice_id"], journey_id=journey_id,
        university_student_id="U100", university_gateway=FakeUniversityGateway(journey_id),
        platform_db_path=str(platform_db), grant_account_access=False,
    )
    with pytest.raises(ValueError, match="does not match"):
        degree_events._consume_academic({
            "event_id": "wrong-student", "journey_id": journey_id,
            "event_name": cross_system_bus.EVENT_UNIVERSITY_CREDITS_UPDATED,
            "payload": {"university_student_id": "U999"},
        })
    link = degree_apprenticeship_repository.get_link(cohort["apprentice_id"])
    assert link is not None
    assert link.reconciliation_state == "Identity Mismatch"


def test_unverified_link_waits_for_university_registration(cohort, admin, tmp_path):
    platform_db = tmp_path / "auth.db"
    _, journey_id = _prepare_degree_cohort(cohort, admin, platform_db)
    link = degree_apprenticeship_service.link_learner(
        admin, cohort["apprentice_id"], journey_id=journey_id,
        university_student_id="U100", platform_db_path=str(platform_db),
        grant_account_access=False,
    )
    assert link.status == "Pending"
    university = enrolments.current_enrolment(
        journey_id, "university", db_path=str(platform_db)
    )
    assert university is not None and university["status"] == "applicant"


def test_registration_event_activates_pending_link(cohort, admin, tmp_path,
                                                   monkeypatch):
    platform_db = tmp_path / "auth.db"
    _, journey_id = _prepare_degree_cohort(cohort, admin, platform_db)
    degree_apprenticeship_service.link_learner(
        admin, cohort["apprentice_id"], journey_id=journey_id,
        university_student_id="U100", platform_db_path=str(platform_db),
        grant_account_access=False,
    )
    monkeypatch.setattr(enrolments, "link_local_enrolment", lambda **_: None)
    degree_events._consume_academic({
        "event_id": "registered-1",
        "event_name": cross_system_bus.EVENT_UNIVERSITY_REGISTRATION_CHANGED,
        "journey_id": journey_id,
        "payload": {
            "university_student_id": "U100",
            "university_degree_program_id": 42,
            "registration_status": "Active",
        },
    })
    link = degree_apprenticeship_repository.get_link(cohort["apprentice_id"])
    assert link is not None and link.status == "Active"


def test_reconciliation_dashboard_surfaces_missing_projection(cohort, admin,
                                                              tmp_path):
    platform_db = tmp_path / "auth.db"
    _, journey_id = _prepare_degree_cohort(cohort, admin, platform_db)
    degree_apprenticeship_service.link_learner(
        admin, cohort["apprentice_id"], journey_id=journey_id,
        university_student_id="U100", platform_db_path=str(platform_db),
        grant_account_access=False,
    )
    rows = degree_apprenticeship_service.reconciliation_dashboard(admin)
    assert len(rows) == 1
    assert rows[0]["needs_attention"]
    assert "academic projection not received" in rows[0]["issues"]


def test_reconciliation_event_updates_operational_state(cohort, admin, tmp_path):
    platform_db = tmp_path / "auth.db"
    _, journey_id = _prepare_degree_cohort(cohort, admin, platform_db)
    degree_apprenticeship_service.link_learner(
        admin, cohort["apprentice_id"], journey_id=journey_id,
        university_student_id="U100", platform_db_path=str(platform_db),
        grant_account_access=False,
    )
    degree_events._consume_reconciliation({
        "journey_id": journey_id,
        "payload": {
            "reconciliation_state": "Apprenticeship Complete; Degree Incomplete"
        },
    })
    link = degree_apprenticeship_repository.get_link(cohort["apprentice_id"])
    assert link is not None
    assert link.reconciliation_state == "Apprenticeship Complete; Degree Incomplete"


def test_both_sides_register_their_durable_consumers(monkeypatch):
    subscribed = []
    monkeypatch.setattr(
        cross_system_bus, "subscribe",
        lambda event, handler, handler_name="": subscribed.append(
            (event, handler_name)
        ),
    )
    monkeypatch.setattr(degree_events, "_registered", False)
    monkeypatch.setattr(university_degree_events, "_registered", False)
    degree_events.register_consumers()
    university_degree_events.register_consumers()
    names = {event for event, _ in subscribed}
    assert cross_system_bus.EVENT_DEGREE_APPRENTICESHIP_LINKED in names
    assert cross_system_bus.EVENT_UNIVERSITY_REGISTRATION_CHANGED in names
    assert cross_system_bus.EVENT_UNIVERSITY_CREDITS_UPDATED in names
    assert cross_system_bus.EVENT_UNIVERSITY_DEGREE_AWARDED in names
    assert cross_system_bus.EVENT_APPRENTICESHIP_COMPLETED in names
    assert cross_system_bus.EVENT_DEGREE_APPRENTICESHIP_RECONCILIATION_REQUIRED in names
