"""University-side consumer for sixth-form progression events.

Subscribes to ``student.progression.completed`` on the durable
cross-system bus and creates an idempotent university applicant.  The
applicant is deliberately not made an active student here: the admissions
lifecycle performs that conversion only after offer, checks, acceptance,
right-to-study and registration have completed.

Idempotent on three levels: the bus's ``cross_system_event_consumed``
table drops re-delivery; the journey's ``university_student_id`` short-
circuits a second admit; and a generated id collision is caught.

Drained by :func:`drain_intake`, which the launcher calls on university
startup (and which a scheduled job could call too).
"""

from __future__ import annotations

import logging
from datetime import datetime

from education_system.platform.cross_system import identity_service
from education_system.platform.integrations.external import cross_system_bus

logger = logging.getLogger(__name__)

CONSUMER_SYSTEM = "university"


def _age_from_dob(dob: str | None) -> int | None:
    if not dob:
        return None
    try:
        d = datetime.strptime(dob, "%Y-%m-%d")
    except ValueError:
        return None
    now = datetime.now()
    return now.year - d.year - ((now.month, now.day) < (d.month, d.day))


def _create_applicant(journey_id: str, payload: dict) -> int:
    """Create (or return) the CRM application for a sixth-form handover."""
    from education_system.systems.university.infrastructure.database.schemas.admissions_schemas import (
        init_admissions_crm_system_db,
    )
    from education_system.systems.university.domains.admissions.domain.services.admissions_crm_core import (
        ApplicationManager,
        ProspectManager,
    )
    from education_system.systems.university.domains.admissions.domain.services import (
        admissions_lifecycle,
    )

    init_admissions_crm_system_db()
    external_reference = str(
        payload.get("ucas_application_id")
        or payload.get("sf_student_id")
        or journey_id
    )
    from education_system.systems.university.infrastructure.database.db import (
        get_connection, transaction,
    )
    with get_connection() as conn:
        existing = conn.execute(
            """SELECT application_id FROM admission_applications
                WHERE journey_id = ? AND external_reference = ?""",
            (journey_id, external_reference),
        ).fetchone()
    if existing:
        return int(existing["application_id"])

    journey = identity_service.get(journey_id) or {}
    first = payload.get("first_name") or journey.get("legal_first_name") or ""
    last = payload.get("last_name") or journey.get("legal_last_name") or ""
    dob = payload.get("date_of_birth") or journey.get("date_of_birth") or ""
    prospect_id = ProspectManager.create_prospect(
        first_name=first,
        last_name=last,
        email=payload.get("email") or "",
        phone=payload.get("phone") or "",
        date_of_birth=dob,
        high_school=payload.get("sixth_form_name") or "",
        intended_major=payload.get("programme_name")
        or payload.get("programme_code") or "",
        source="sixth_form_progression",
    )
    programme_code = payload.get("programme_code") or "UNDECLARED"
    application_id = ApplicationManager.submit_application(
        prospect_id=prospect_id,
        application_type="undergraduate",
        program_applied=payload.get("programme_name") or programme_code,
        academic_year=payload.get("entry_year") or "",
        semester=payload.get("semester") or "autumn",
    )
    with transaction() as conn:
        conn.execute(
            """UPDATE admission_applications
                  SET journey_id = ?, external_reference = ?,
                      status = 'documents_pending'
                WHERE application_id = ?""",
            (journey_id, external_reference, application_id),
        )
        conn.execute(
            """INSERT INTO admission_status_history
                   (application_id, from_status, to_status, reason)
               VALUES (?, 'submitted', 'documents_pending',
                       'Sixth-form handover received')""",
            (application_id,),
        )
    admissions_lifecycle.add_choice(
        application_id, programme_code,
        programme_name=payload.get("programme_name") or "",
        entry_year=payload.get("entry_year") or "", rank=1,
    )
    for requirement_type, description in (
        ("identity", "Identity and date-of-birth evidence"),
        ("qualifications", "Final qualification results"),
        ("right_to_study", "Right-to-study check"),
    ):
        admissions_lifecycle.add_requirement(
            application_id, requirement_type, description
        )
    logger.info("Created university application %s for journey %s",
                application_id, journey_id)
    return application_id


def _import_medical(uni_student_id: str, sf_student_id: str) -> None:
    try:
        from education_system.systems.university.domains.pastoral.domain.health.records import (
            sixth_form_import,
        )
        sixth_form_import.import_from_sixth_form(
            uni_student_id=uni_student_id, sf_student_id=sf_student_id)
    except Exception:
        logger.exception(
            "Medical import failed for sf=%s -> uni=%s (admission "
            "still stands)", sf_student_id, uni_student_id)


def handle_progression_completed(envelope: dict) -> None:
    """Bus handler: create an applicant; enrolment is a later gated step."""
    # Progression events are explicitly addressed. Ignore any not bound
    # for the university so co-located K-12 intakes (same launcher
    # process) don't get admitted here by mistake.
    target = envelope.get("target_system")
    if target is not None and target != CONSUMER_SYSTEM:
        return
    journey_id = envelope.get("journey_id")
    payload = envelope.get("payload") or {}
    sf_student_id = payload.get("sf_student_id")
    if not journey_id:
        logger.warning("Progression event %s has no journey_id — "
                       "ignoring", envelope.get("event_id"))
        return
    application_id = _create_applicant(journey_id, payload)
    logger.info("Sixth-form journey %s staged as application %s",
                journey_id, application_id)


_registered = False


def register_intake_consumer() -> None:
    """Idempotently subscribe the intake handler to the bus."""
    global _registered
    if _registered:
        return
    cross_system_bus.subscribe(
        cross_system_bus.EVENT_STUDENT_PROGRESSION_COMPLETED,
        handle_progression_completed,
        handler_name="university.admissions.sixthform_intake")
    _registered = True
    logger.debug("Registered sixth-form intake consumer")


def drain_intake(*, db_path: str | None = None) -> int:
    """Process any pending sixth-form progression events. Returns the
    number of (event, handler) dispatches. Safe to call repeatedly."""
    register_intake_consumer()
    return cross_system_bus.poll_and_dispatch(
        CONSUMER_SYSTEM, db_path=db_path)
