"""University-side consumer for sixth-form progression events.

Subscribes to ``student.progression.completed`` on the durable
cross-system bus and admits the student into the university: it creates
a university ``students`` row **linked to the canonical journey_id**
(rather than re-keying demographics), records the transition, and copies
the sixth-form medical record across.

Idempotent on three levels: the bus's ``cross_system_event_consumed``
table drops re-delivery; the journey's ``university_student_id`` short-
circuits a second admit; and a generated id collision is caught.

Drained by :func:`drain_intake`, which the launcher calls on university
startup (and which a scheduled job could call too).
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime

from education_system.shared.cross_system import identity_service
from education_system.shared.integrations import cross_system_bus

logger = logging.getLogger(__name__)

CONSUMER_SYSTEM = "university"
_DEFAULT_COURSE = "CS"


def _age_from_dob(dob: str | None) -> int | None:
    if not dob:
        return None
    try:
        d = datetime.strptime(dob, "%Y-%m-%d")
    except ValueError:
        return None
    now = datetime.now()
    return now.year - d.year - ((now.month, now.day) < (d.month, d.day))


def _new_student_id() -> str:
    return str(secrets.randbelow(9000000) + 1000000).zfill(7)


def _stamp_journey_id(student_id: str, journey_id: str) -> None:
    from education_system.post_18.university_system.infrastructure.database.db import (
        transaction,
    )
    with transaction() as conn:
        # The students.journey_id link column is normally added by the
        # university DB migration; ensure it exists so intake doesn't
        # depend on that having run first.
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(students)").fetchall()}
        if "journey_id" not in cols:
            conn.execute(
                "ALTER TABLE students ADD COLUMN journey_id TEXT")
        conn.execute(
            "UPDATE students SET journey_id = ? WHERE student_id = ?",
            (journey_id, student_id))


def _admit_student(journey_id: str, payload: dict) -> str | None:
    """Create a university student linked to the journey. Returns the new
    university student_id, or None if one already exists for the journey."""
    journey = identity_service.get(journey_id)
    if journey and journey.get("university_student_id"):
        logger.info(
            "Journey %s already admitted as university student %s — "
            "skipping", journey_id, journey["university_student_id"])
        return None

    from education_system.post_18.university_system.infrastructure.repositories.student import (
        Student, SQLiteStudentRepository,
    )
    repo = SQLiteStudentRepository()

    first = payload.get("first_name") or (journey or {}).get(
        "legal_first_name")
    last = payload.get("last_name") or (journey or {}).get(
        "legal_last_name")
    dob = payload.get("date_of_birth") or (journey or {}).get(
        "date_of_birth")

    for _ in range(5):
        sid = _new_student_id()
        if repo.get_by_id(sid) is None:
            break
    else:
        raise RuntimeError("Could not allocate a free university id")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    student = Student(
        student_id=sid,
        email_address=f"C{sid}@tees.ac.uk",
        title=payload.get("title"),
        first_name=first, middle_name=payload.get("middle_name"),
        last_name=last, gender=(payload.get("gender") or None),
        dob=dob, age=_age_from_dob(dob),
        course=_DEFAULT_COURSE, registration_datetime=now,
        status="Active", enrollment_date=now,
    )
    repo.save(student)
    _stamp_journey_id(sid, journey_id)
    identity_service.link_system(journey_id, "university",
                                 student_id=sid, set_current=True)
    identity_service.record_transition(
        journey_id, from_system="college", to_system="university",
        reason="Sixth-form progression intake (bus)")
    logger.info("Admitted journey %s as university student %s",
                journey_id, sid)
    return sid


def _import_medical(uni_student_id: str, sf_student_id: str) -> None:
    try:
        from education_system.post_18.university_system.modules.domain.health.records import (
            sixth_form_import,
        )
        sixth_form_import.import_from_sixth_form(
            uni_student_id=uni_student_id, sf_student_id=sf_student_id)
    except Exception:
        logger.exception(
            "Medical import failed for sf=%s -> uni=%s (admission "
            "still stands)", sf_student_id, uni_student_id)


def handle_progression_completed(envelope: dict) -> None:
    """Bus handler: admit the student and pull their medical record."""
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
    uni_id = _admit_student(journey_id, payload)
    if uni_id and sf_student_id:
        _import_medical(uni_id, sf_student_id)


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
