"""Orchestration for one learner's simultaneous apprenticeship and degree."""

from __future__ import annotations

from typing import Any
from datetime import UTC, datetime, timedelta

from education_system.platform.cross_system import enrolments, identity_service
from education_system.platform.identity.auth.db import connect as auth_connect
from education_system.platform.integrations.external import cross_system_bus
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    degree_apprenticeship_repository as repo,
    programme_repository,
)
from education_system.systems.apprenticeships.infrastructure.integrations.university_gateway import (
    UniversityGateway,
    UniversityGatewayError,
    as_dict,
)
from education_system.systems.apprenticeships.infrastructure.integrations import degree_events
from education_system.systems.apprenticeships.services import apprentice_service
from education_system.systems.apprenticeships.services.access import Actor, require


INTEGRATION_TYPES = frozenset({"Integrated", "Non-integrated"})


def map_programme(
    actor: Actor,
    apprenticeship_programme_id: int,
    university_degree_program_id: int,
    *,
    credits_required: float | None = None,
    integration_type: str = "Integrated",
    active: bool = True,
):
    """Associate a Level 6/7 standard with a university degree programme."""
    require(actor, "programme.manage")
    programme = programme_repository.get(apprenticeship_programme_id)
    if programme is None:
        raise ValidationError(f"No programme with id {apprenticeship_programme_id}")
    if programme.level not in (6, 7):
        raise ValidationError("Degree apprenticeship mappings require a Level 6 or 7 programme")
    if integration_type not in INTEGRATION_TYPES:
        raise ValidationError(f"Integration type must be one of {', '.join(sorted(INTEGRATION_TYPES))}")
    if credits_required is not None and credits_required <= 0:
        raise ValidationError("Credits required must be greater than zero")
    return repo.save_programme_mapping({
        "apprenticeship_programme_id": apprenticeship_programme_id,
        "university_degree_program_id": int(university_degree_program_id),
        "credits_required": credits_required,
        "integration_type": integration_type,
        "active": active,
    })


def link_learner(
    actor: Actor,
    apprentice_id: int,
    *,
    journey_id: str,
    university_student_id: str,
    institution_id: str | None = None,
    start_date: str | None = None,
    university_gateway: UniversityGateway | None = None,
    platform_db_path: str | None = None,
    grant_account_access: bool = True,
):
    """Create the association and ensure both enrolments are concurrently active.

    The local link is first marked Pending. If either shared enrolment cannot be
    written, retrying this operation is safe and completes the same link.
    """
    require(actor, "apprentice.manage")
    summary = apprentice_service.get_apprentice(actor, apprentice_id)
    programme_id = summary.apprentice.programme_id
    mapping = repo.get_programme_mapping(programme_id or -1)
    if mapping is None or not mapping.active:
        raise ValidationError("The apprentice's programme has no active university degree mapping")
    journey_id = journey_id.strip()
    university_student_id = university_student_id.strip()
    if not journey_id or not university_student_id:
        raise ValidationError("journey_id and university_student_id are required")

    # A supplied gateway is an explicit synchronous verifier (useful for
    # imports/tests). Normal operation learns university state from durable
    # events and does not open the university database here.
    university_confirmed = university_gateway is not None
    if university_gateway is not None:
        try:
            registration = university_gateway.registration(
                university_student_id, mapping.university_degree_program_id
            )
        except UniversityGatewayError as exc:
            raise ValidationError(str(exc)) from exc
        if registration.journey_id and registration.journey_id != journey_id:
            raise ValidationError(
                f"University student {university_student_id} belongs to a different learner journey"
            )

    current_journey = repo.apprentice_journey_id(apprentice_id)
    if current_journey and current_journey != journey_id:
        raise ValidationError("The apprentice is already attached to a different learner journey")
    try:
        repo.set_apprentice_journey_id(apprentice_id, journey_id)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    repo.upsert_pending_link({
        "apprentice_id": apprentice_id, "journey_id": journey_id,
        "university_student_id": university_student_id,
        "university_degree_program_id": mapping.university_degree_program_id,
    })
    # Stamp both local identifiers onto the one canonical learner identity.
    # set_current stays false: a degree apprentice has two current systems,
    # represented by the active enrolment rows below rather than one slot.
    identity_service.link_system(
        journey_id, "apprenticeships", student_id=str(apprentice_id),
        pk=apprentice_id, set_current=False, db_path=platform_db_path,
    )
    if university_confirmed:
        identity_service.link_system(
            journey_id, "university", student_id=university_student_id,
            set_current=False, db_path=platform_db_path,
        )
    enrolments.link_local_enrolment(
        journey_id=journey_id, system="apprenticeships",
        local_student_id=str(apprentice_id), status="active",
        institution_id=institution_id, start_date=start_date,
        db_path=platform_db_path,
    )
    enrolments.link_local_enrolment(
        journey_id=journey_id, system="university",
        local_student_id=university_student_id,
        status="active" if university_confirmed else "applicant",
        institution_id=institution_id, start_date=start_date,
        db_path=platform_db_path,
    )
    if university_confirmed and grant_account_access and summary.apprentice.username:
        grant_shared_account_access(
            summary.apprentice.username, platform_db_path=platform_db_path
        )
    link = (
        repo.activate_link(apprentice_id)
        if university_confirmed else repo.get_link(apprentice_id)
    )
    assert link is not None
    degree_events.publish(
        cross_system_bus.EVENT_DEGREE_APPRENTICESHIP_LINKED,
        journey_id=journey_id, target_system="university",
        db_path=platform_db_path,
        idempotency_key=f"degree-apprenticeship-linked:{link.link_id}",
        apprentice_id=apprentice_id, university_student_id=university_student_id,
        university_degree_program_id=mapping.university_degree_program_id,
        given_name=summary.apprentice.given_name,
        family_name=summary.apprentice.family_name,
        date_of_birth=summary.apprentice.date_of_birth,
        email=summary.apprentice.email,
    )
    return link


def grant_shared_account_access(username: str, *, platform_db_path: str | None = None) -> None:
    """Give one existing platform account its learner role in both systems."""
    conn = auth_connect(platform_db_path)
    try:
        user = conn.execute(
            "SELECT id FROM users WHERE LOWER(username)=LOWER(?)", (username.strip(),)
        ).fetchone()
        if user is None:
            raise ValidationError(
                f"No shared platform account named {username!r}; create it before admission"
            )
        for system, role in (("apprenticeships", "apprentice"), ("university", "student")):
            conn.execute(
                """INSERT INTO user_systems (user_id, system_key, role)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id, system_key) DO UPDATE SET role=excluded.role""",
                (user["id"], system, role),
            )
        conn.commit()
    finally:
        conn.close()

    from education_system.systems.apprenticeships.services import login_links

    login_links.try_sync_username(username, db_path=platform_db_path)


def academic_progress(
    actor: Actor,
    apprentice_id: int,
    *,
    university_gateway: UniversityGateway | None = None,
) -> dict[str, Any]:
    """Read current academic progress directly from its university owner."""
    apprentice_service.get_apprentice(actor, apprentice_id)
    link = repo.get_link(apprentice_id)
    if link is None or link.status != "Active":
        raise ValidationError("This apprentice has no active university link")
    if university_gateway is not None:
        try:
            registration = university_gateway.registration(
                link.university_student_id, link.university_degree_program_id
            )
        except UniversityGatewayError as exc:
            raise ValidationError(str(exc)) from exc
        if registration.journey_id and registration.journey_id != link.journey_id:
            raise ValidationError("The linked university record now belongs to a different learner journey")
        repo.record_academic_sync(apprentice_id)
        return as_dict(registration)
    projection = repo.academic_projection(apprentice_id)
    if projection is None:
        raise ValidationError("University academic progress has not been received yet")
    return projection


def require_university_gateway_confirmation(apprentice_id: int) -> None:
    """Enforce the academic half of gateway for integrated programmes."""
    link = repo.get_link(apprentice_id)
    if link is None:
        return
    apprentice = apprentice_repository.get(apprentice_id)
    if apprentice is None or apprentice.programme_id is None:
        return
    mapping = repo.get_programme_mapping(apprentice.programme_id)
    if mapping is None or mapping.integration_type != "Integrated":
        return
    projection = repo.academic_projection(apprentice_id)
    if not projection or not bool(projection.get("university_gateway_confirmed")):
        raise ValidationError(
            "The university has not confirmed the academic gateway requirements"
        )


def reconciliation_dashboard(
    actor: Actor, *, stale_after_days: int = 7,
) -> list[dict[str, Any]]:
    """Operational view of every dual enrolment and anything needing action."""
    require(actor, "apprentice.view")
    cutoff = datetime.now(UTC) - timedelta(days=max(1, stale_after_days))
    rows: list[dict[str, Any]] = []
    for link in repo.list_links():
        summary = apprentice_service.get_apprentice(actor, link.apprentice_id)
        projection = repo.academic_projection(link.apprentice_id)
        stale = True
        if link.last_academic_sync_at:
            try:
                synced = datetime.fromisoformat(
                    link.last_academic_sync_at.replace("Z", "+00:00")
                )
                if synced.tzinfo is None:
                    synced = synced.replace(tzinfo=UTC)
                stale = synced < cutoff
            except ValueError:
                stale = True
        issues: list[str] = []
        if link.status != "Active":
            issues.append(f"link is {link.status.lower()}")
        if link.reconciliation_state != "In Sync":
            issues.append(link.reconciliation_state)
        if projection is None:
            issues.append("academic projection not received")
        elif stale:
            issues.append("academic projection is stale")
        rows.append({
            "apprentice_id": link.apprentice_id,
            "apprentice_name": summary.full_name,
            "journey_id": link.journey_id,
            "university_student_id": link.university_student_id,
            "degree_program_id": link.university_degree_program_id,
            "link_status": link.status,
            "reconciliation_state": link.reconciliation_state,
            "last_academic_sync_at": link.last_academic_sync_at,
            "projection": projection,
            "issues": issues,
            "needs_attention": bool(issues),
        })
    return rows


def acknowledge_reconciliation(
    actor: Actor, apprentice_id: int, *, state: str = "Pending Review",
) -> None:
    require(actor, "apprentice.manage")
    if repo.get_link(apprentice_id) is None:
        raise ValidationError("This apprentice has no university link")
    repo.set_reconciliation(apprentice_id, state.strip() or "Pending Review")
