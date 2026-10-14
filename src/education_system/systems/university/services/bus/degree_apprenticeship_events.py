"""University-owned publishers for degree-apprenticeship academic snapshots."""

from __future__ import annotations

from typing import Any
from datetime import UTC, datetime

from education_system.platform.integrations.external import cross_system_bus as bus
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)

_registered = False


def publish_academic_snapshot(
    *, event_name: str, journey_id: str, university_student_id: str,
    university_degree_program_id: int, idempotency_key: str,
    db_path: str | None = None, **academic: Any,
) -> str:
    """Publish a replaceable projection while university retains ownership."""
    allowed = {
        bus.EVENT_UNIVERSITY_REGISTRATION_CHANGED,
        bus.EVENT_UNIVERSITY_CREDITS_UPDATED,
        bus.EVENT_UNIVERSITY_DEGREE_AWARDED,
    }
    if event_name not in allowed:
        raise ValueError(f"Unsupported degree apprenticeship event {event_name!r}")
    return bus.publish_cross_system(
        event_name, source_system="university",
        source_module="degree_apprenticeship_events", target_system="apprenticeships",
        journey_id=journey_id, idempotency_key=idempotency_key, db_path=db_path,
        university_student_id=university_student_id,
        university_degree_program_id=university_degree_program_id,
        **academic,
    )


def publish_current_snapshot(
    *, journey_id: str, university_student_id: str,
    university_degree_program_id: int, reason: str = "credits",
    university_gateway_confirmed: bool = False,
    degree_outcome: str | None = None,
    degree_awarded_at: str | None = None,
    db_path: str | None = None,
) -> str:
    """Publish the university-owned current state for a linked apprentice."""
    with get_connection() as conn:
        student = conn.execute(
            "SELECT status FROM students WHERE student_id=?",
            (university_student_id,),
        ).fetchone()
        degree = conn.execute(
            """SELECT program_code, program_name, total_credits_required
                 FROM degree_programs WHERE program_id=? AND is_active=1""",
            (university_degree_program_id,),
        ).fetchone()
        progress = conn.execute(
            """SELECT total_credits_earned, completion_percentage, status,
                      last_updated
                 FROM student_degree_progress
                WHERE student_id=? AND program_id=?
                ORDER BY last_updated DESC LIMIT 1""",
            (university_student_id, university_degree_program_id),
        ).fetchone()
        modules = conn.execute(
            """SELECT COUNT(*) FROM student_modules
                WHERE student_id=? AND status='Completed'""",
            (university_student_id,),
        ).fetchone()[0]
    if student is None or degree is None:
        raise ValueError("Linked university student or degree programme is unavailable")
    event_name = {
        "registration": bus.EVENT_UNIVERSITY_REGISTRATION_CHANGED,
        "award": bus.EVENT_UNIVERSITY_DEGREE_AWARDED,
    }.get(reason, bus.EVENT_UNIVERSITY_CREDITS_UPDATED)
    version = (
        str(progress["last_updated"]) if progress and progress["last_updated"]
        else datetime.now(UTC).isoformat()
    )
    return publish_academic_snapshot(
        event_name=event_name, journey_id=journey_id,
        university_student_id=university_student_id,
        university_degree_program_id=university_degree_program_id,
        idempotency_key=(
            f"university-degree:{reason}:{university_student_id}:"
            f"{university_degree_program_id}:{version}"
        ),
        db_path=db_path,
        degree_program_code=degree["program_code"],
        degree_program_name=degree["program_name"],
        registration_status=student["status"],
        credits_earned=progress["total_credits_earned"] if progress else 0,
        credits_required=degree["total_credits_required"],
        completion_percentage=(progress["completion_percentage"] if progress else 0),
        modules_completed=modules,
        academic_standing=progress["status"] if progress else None,
        university_gateway_confirmed=university_gateway_confirmed,
        degree_outcome=degree_outcome,
        degree_awarded_at=degree_awarded_at,
    )


def publish_for_student(
    student_id: str, program_id: int, *, reason: str = "credits",
    university_gateway_confirmed: bool = False,
    degree_outcome: str | None = None,
    degree_awarded_at: str | None = None,
) -> str | None:
    """Publish only when the student belongs to a cross-system journey."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT journey_id FROM students WHERE student_id=?", (student_id,),
        ).fetchone()
    journey_id = str(row["journey_id"] or "") if row else ""
    if not journey_id:
        return None
    return publish_current_snapshot(
        journey_id=journey_id, university_student_id=str(student_id),
        university_degree_program_id=int(program_id), reason=reason,
        university_gateway_confirmed=university_gateway_confirmed,
        degree_outcome=degree_outcome, degree_awarded_at=degree_awarded_at,
    )


def confirm_academic_gateway(student_id: str, program_id: int) -> str | None:
    """University-owned acknowledgement consumed by the EPA gateway gate."""
    return publish_for_student(
        student_id, program_id, reason="credits",
        university_gateway_confirmed=True,
    )


def _consume_linked(envelope: dict[str, Any]) -> None:
    """Match an enrolled student or stage a guarded admissions application.

    A link request is not evidence that the university's admissions checks
    passed.  Existing students can be acknowledged immediately; everybody
    else enters the normal admissions lifecycle and receives a student record
    only from ``admissions_lifecycle.convert_to_student``.
    """
    payload = dict(envelope.get("payload") or {})
    journey_id = str(envelope.get("journey_id") or "")
    student_id = str(payload.get("university_student_id") or "")
    program_id = int(payload["university_degree_program_id"])
    if not journey_id or not student_id:
        raise ValueError("Degree apprenticeship link lacks learner identifiers")
    with get_connection() as conn:
        degree = conn.execute(
            """SELECT program_code, program_name, total_credits_required
                 FROM degree_programs WHERE program_id=? AND is_active=1""",
            (program_id,),
        ).fetchone()
        if degree is None:
            raise ValueError(f"No active degree programme {program_id}")
        by_journey = conn.execute(
            "SELECT student_id FROM students WHERE journey_id=?", (journey_id,)
        ).fetchone()
        if by_journey and str(by_journey["student_id"]) != student_id:
            raise ValueError("Learner journey is already assigned to another university student")
        student = conn.execute(
            "SELECT student_id, journey_id FROM students WHERE student_id=?", (student_id,)
        ).fetchone()
        if student and student["journey_id"] not in (None, "", journey_id):
            raise ValueError("University student is already assigned to another learner journey")
        if not student:
            _stage_application(
                journey_id=journey_id,
                requested_student_id=student_id,
                programme_code=str(degree["program_code"]),
                programme_name=str(degree["program_name"]),
                payload=payload,
            )
            return
        if student["journey_id"] in (None, ""):
            with transaction() as write_conn:
                write_conn.execute(
                    "UPDATE students SET journey_id=? WHERE student_id=?",
                    (journey_id, student_id),
                )
    publish_current_snapshot(
        journey_id=journey_id, university_student_id=student_id,
        university_degree_program_id=program_id, reason="registration",
    )


def _consume_apprenticeship_completed(envelope: dict[str, Any]) -> None:
    """Reconcile provider completion against the university-owned award."""
    payload = dict(envelope.get("payload") or {})
    journey_id = str(envelope.get("journey_id") or "")
    student_id = str(payload.get("university_student_id") or "")
    with get_connection() as conn:
        student = conn.execute(
            "SELECT student_id FROM students WHERE student_id=? AND journey_id=?",
            (student_id, journey_id),
        ).fetchone()
        awarded = conn.execute(
            """SELECT 1 FROM graduation_checklist
                WHERE student_id=? AND conferral_status='approved' LIMIT 1""",
            (student_id,),
        ).fetchone()
    if student is None:
        raise ValueError("Completed apprenticeship does not match a university learner")
    if awarded:
        return
    bus.publish_cross_system(
        bus.EVENT_DEGREE_APPRENTICESHIP_RECONCILIATION_REQUIRED,
        source_system="university", source_module="degree_apprenticeship_events",
        journey_id=journey_id, target_system=None,
        idempotency_key=f"university-reconcile:{envelope['event_id']}",
        university_student_id=student_id,
        reconciliation_state="Apprenticeship Complete; Degree Incomplete",
    )


def _stage_application(
    *, journey_id: str, requested_student_id: str, programme_code: str,
    programme_name: str, payload: dict[str, Any],
) -> int:
    """Idempotently place a link request into the university admissions CRM."""
    from education_system.systems.university.infrastructure.database.schemas.admissions_schemas import (
        init_admissions_crm_system_db,
    )
    from education_system.systems.university.domains.admissions.domain.services import (
        admissions_lifecycle,
    )
    from education_system.systems.university.domains.admissions.domain.services.admissions_crm_core import (
        ApplicationManager,
        ProspectManager,
    )

    init_admissions_crm_system_db()
    with get_connection() as conn:
        existing = conn.execute(
            """SELECT application_id FROM admission_applications
                 WHERE journey_id=? AND application_type='degree_apprenticeship'
                 ORDER BY application_id LIMIT 1""",
            (journey_id,),
        ).fetchone()
    if existing:
        return int(existing["application_id"])

    prospect_id = ProspectManager.create_prospect(
        first_name=str(payload.get("given_name") or ""),
        last_name=str(payload.get("family_name") or ""),
        email=str(payload.get("email") or ""),
        date_of_birth=str(payload.get("date_of_birth") or ""),
        intended_major=programme_name,
        source="degree_apprenticeship_link",
    )
    application_id = ApplicationManager.submit_application(
        prospect_id=prospect_id,
        application_type="degree_apprenticeship",
        program_applied=programme_name or programme_code,
        academic_year=str(payload.get("academic_year") or ""),
        semester=str(payload.get("semester") or "autumn"),
    )
    with transaction() as conn:
        conn.execute(
            """UPDATE admission_applications
                  SET journey_id=?, external_reference=?, status='documents_pending'
                WHERE application_id=?""",
            (journey_id, requested_student_id, application_id),
        )
    choice_id = admissions_lifecycle.add_choice(
        application_id, programme_code, programme_name=programme_name,
        entry_year=str(payload.get("academic_year") or ""),
    )
    admissions_lifecycle.accept_choice(application_id, choice_id)
    for requirement_type, description in (
        ("identity", "Identity and date-of-birth evidence"),
        ("employer_commitment", "Employer commitment and training agreement"),
        ("right_to_study", "Right-to-study check"),
    ):
        admissions_lifecycle.add_requirement(
            application_id, requirement_type, description,
        )
    return application_id


def register_consumers() -> None:
    global _registered
    if _registered:
        return
    bus.subscribe(
        bus.EVENT_DEGREE_APPRENTICESHIP_LINKED, _consume_linked,
        handler_name="university.degree_apprenticeship.ensure_student",
    )
    bus.subscribe(
        bus.EVENT_APPRENTICESHIP_COMPLETED, _consume_apprenticeship_completed,
        handler_name="university.degree_apprenticeship.reconcile_completion",
    )
    _registered = True
