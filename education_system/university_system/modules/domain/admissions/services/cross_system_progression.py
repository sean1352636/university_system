"""University-side consumer for cross-system progression events.

When the college subsystem publishes ``student.progression.offered``
(see ``college_system.ucas.set_firm_insurance``), this handler creates
a draft ``students`` row in the university DB with
``status='Pending'`` and links it back to the shared
``student_journey`` row. It is the receiving half of step 4 of the
cross-system integration plan.

Wired in by calling ``wire_subscribers(...)`` from the university
process startup. Idempotent: re-delivery of the same event finds the
existing university record and exits cleanly.
"""

from __future__ import annotations

import json
import logging
import secrets
import sqlite3
from datetime import datetime
from typing import Any

from education_system.shared.cross_system import identity_service as ids
from education_system.shared.cross_system.journey_events import (
    record_student_transition,
)
from education_system.shared.integrations import cross_system_bus as bus

logger = logging.getLogger(__name__)


_HANDLER_NAME = (
    "education_system.university_system.modules.domain.admissions."
    "services.cross_system_progression.on_progression_offered"
)
_HANDLER_NAME_ACCEPTED = (
    "education_system.university_system.modules.domain.admissions."
    "services.cross_system_progression.on_progression_accepted"
)


def wire_subscribers(
    *,
    university_db_path: str,
    auth_db_path: str | None = None,
    email_domain: str = "tees.ac.uk",
) -> None:
    """Register the progression-offered handler on the in-process bus.

    Closes over the DB paths so the handler can receive the standard
    ``(envelope) -> None`` signature. Call once at university process
    startup. Calling it more than once with the same paths is a no-op
    (the registry de-dupes by handler name in
    ``cross_system_event_consumed``, but registering twice would just
    fire it twice in-process — avoid that).
    """
    def _handler(envelope: dict) -> None:
        on_progression_offered(
            envelope,
            university_db_path=university_db_path,
            auth_db_path=auth_db_path,
            email_domain=email_domain,
        )
    _handler.__qualname__ = "on_progression_offered"
    _handler.__module__ = __name__
    bus.subscribe(
        bus.EVENT_STUDENT_PROGRESSION_OFFERED, _handler,
        handler_name=_HANDLER_NAME,
    )

    def _accepted_handler(envelope: dict) -> None:
        on_progression_accepted(
            envelope,
            university_db_path=university_db_path,
            auth_db_path=auth_db_path,
        )
    _accepted_handler.__qualname__ = "on_progression_accepted"
    _accepted_handler.__module__ = __name__
    bus.subscribe(
        bus.EVENT_STUDENT_PROGRESSION_ACCEPTED, _accepted_handler,
        handler_name=_HANDLER_NAME_ACCEPTED,
    )

    logger.info(
        "cross_system_progression: subscribed handlers for "
        "offered+accepted (university_db=%s)",
        university_db_path,
    )


def on_progression_offered(
    envelope: dict,
    *,
    university_db_path: str,
    auth_db_path: str | None = None,
    email_domain: str = "tees.ac.uk",
) -> str | None:
    """Handle one ``student.progression.offered`` event.

    Returns the new (or existing) university ``student_id`` on success,
    or ``None`` if the envelope was unusable. Raises only on a fatal DB
    error — normal "already there" or "unknown journey" cases are
    logged and return ``None`` so the bus doesn't retry forever.
    """
    journey_id = envelope.get("journey_id")
    if not journey_id:
        logger.warning("progression.offered without journey_id — dropping")
        return None
    payload = envelope.get("payload", {})

    journey = ids.get_journey(journey_id, db_path=auth_db_path)
    if not journey:
        logger.warning(
            "progression.offered for unknown journey_id=%s — dropping",
            journey_id,
        )
        return None

    # Idempotency: if this journey already has a university record, we're done.
    if journey.get("university_student_id"):
        logger.info(
            "progression.offered: journey %s already linked to "
            "university student_id=%s — skipping",
            journey_id, journey["university_student_id"],
        )
        return journey["university_student_id"]

    student_id = _generate_student_id(university_db_path)
    email_address = f"C{student_id}@{email_domain}"
    course = payload.get("course_title") or payload.get("ucas_code") or ""
    registration_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(university_db_path, timeout=30)
    try:
        conn.execute(
            """INSERT INTO students
                (student_id, email_address, first_name, last_name, dob,
                 course, status, registration_datetime, journey_id)
                VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?, ?)""",
            (
                student_id, email_address,
                journey.get("legal_first_name"),
                journey.get("legal_last_name"),
                journey.get("date_of_birth"),
                course, registration_at, journey_id,
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # Race / re-delivery: another insert won. Re-read the journey
        # to recover the now-populated student_id.
        conn.rollback()
        logger.warning(
            "progression.offered: insert raced for journey=%s — "
            "treating as already-applied",
            journey_id,
        )
        existing = ids.get_journey(journey_id, db_path=auth_db_path)
        return existing.get("university_student_id") if existing else None
    finally:
        conn.close()

    # Link back into the shared identity table.
    try:
        ids.attach_system_record(
            journey_id, "university", student_id=student_id,
            db_path=auth_db_path,
        )
    except Exception:
        logger.exception(
            "progression.offered: attach_system_record failed for "
            "journey=%s student_id=%s", journey_id, student_id,
        )

    # Audit + downstream notification: this is a college->university move.
    record_student_transition(
        journey_id,
        from_system="college", to_system="university",
        reason="progression",
        notes=(
            f"Auto-created from UCAS firm choice "
            f"(application_id={payload.get('application_id')})"
        ),
        source_module=__name__,
        extra_payload={
            "university_student_id": student_id,
            "course_title": payload.get("course_title"),
            "ucas_code": payload.get("ucas_code"),
        },
        auth_db_path=auth_db_path,
    )
    logger.info(
        "progression.offered: created uni student %s for journey %s "
        "(course=%r)", student_id, journey_id, course,
    )
    return student_id


def on_progression_accepted(
    envelope: dict,
    *,
    university_db_path: str,
    auth_db_path: str | None = None,
) -> bool:
    """Handle one ``student.progression.accepted`` event.

    Updates the matching ``Pending`` university student row with the
    final grades + ``conditions_met`` flag. The Pending → Active
    promotion stays a separate, manual ``confirm_enrolment`` call so
    admissions staff can review failed conditions before enrolling.

    Returns ``True`` if a row was updated, ``False`` for any other
    outcome (no journey, no university record yet, etc.). Never
    raises on normal "nothing to do" cases.
    """
    journey_id = envelope.get("journey_id")
    if not journey_id:
        logger.warning(
            "progression.accepted without journey_id — dropping",
        )
        return False
    payload = envelope.get("payload", {})

    journey = ids.get_journey(journey_id, db_path=auth_db_path)
    if not journey or not journey.get("university_student_id"):
        # Either we never received the offered event, or the order is
        # racing. Either way, dropping is correct — the offered handler
        # is the one that creates the Pending row.
        logger.info(
            "progression.accepted: journey %s has no university link "
            "yet; dropping (offered handler hasn't run)",
            journey_id,
        )
        return False

    uni_student_id = journey["university_student_id"]
    grades = payload.get("final_grades") or {}
    conditions_met = payload.get("conditions_met")
    grades_json = json.dumps(grades) if grades else None
    cm = (None if conditions_met is None
          else (1 if conditions_met else 0))

    conn = sqlite3.connect(university_db_path, timeout=30)
    try:
        cur = conn.execute(
            "UPDATE students "
            "   SET entry_qualifications = ?, conditions_met = ? "
            " WHERE student_id = ?",
            (grades_json, cm, uni_student_id),
        )
        if cur.rowcount == 0:
            logger.warning(
                "progression.accepted: university row %s not found "
                "(journey=%s)", uni_student_id, journey_id,
            )
            return False
        conn.commit()
    finally:
        conn.close()

    logger.info(
        "progression.accepted: stored grades for uni student %s "
        "(journey=%s, conditions_met=%s)",
        uni_student_id, journey_id, conditions_met,
    )
    return True


def confirm_enrolment(
    student_id: str,
    *,
    university_db_path: str,
    auth_db_path: str | None = None,
) -> bool:
    """Promote a ``Pending`` university student to ``Active`` and publish
    ``student.progression.completed`` targeted at the college subsystem.

    Returns ``True`` if the row was found and the event published.
    Returns ``False`` if the student doesn't exist or wasn't in
    ``Pending`` (idempotent — calling this on an already-confirmed
    student is a safe no-op).

    The publish is best-effort: if the bus write fails the status flip
    is still committed, since the local truth is the uni DB.
    """
    conn = sqlite3.connect(university_db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT student_id, journey_id, course, status "
            "  FROM students WHERE student_id = ?",
            (student_id,),
        ).fetchone()
        if not row:
            logger.warning(
                "confirm_enrolment: no university student with id=%s",
                student_id,
            )
            return False
        if row["status"] != "Pending":
            logger.info(
                "confirm_enrolment: student %s already in status=%s "
                "(idempotent no-op)",
                student_id, row["status"],
            )
            return False

        enrolled_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE students SET status = 'Active', "
            "       enrollment_date = ? WHERE student_id = ?",
            (enrolled_at, student_id),
        )
        conn.commit()
    finally:
        conn.close()

    journey_id = row["journey_id"]
    if not journey_id:
        logger.warning(
            "confirm_enrolment: student %s has no journey_id; "
            "skipping bus publish.", student_id,
        )
        return True

    try:
        bus.publish_cross_system(
            bus.EVENT_STUDENT_PROGRESSION_COMPLETED,
            source_system="university",
            source_module=__name__,
            journey_id=journey_id,
            target_system="college",
            university_student_id=student_id,
            course=row["course"],
            enrolled_at=enrolled_at,
            db_path=auth_db_path,
        )
    except Exception:
        logger.exception(
            "confirm_enrolment: bus publish failed for student %s",
            student_id,
        )
    return True


def _generate_student_id(university_db_path: str,
                          *, max_attempts: int = 8) -> str:
    """Return a 7-digit numeric id that doesn't collide with existing rows.

    Matches the existing ``create_student_dialog`` convention (see
    ``students/student_crud_gui.py``). Collisions are vanishingly rare
    in 9M-key space, but we re-roll up to ``max_attempts`` times rather
    than blindly inserting and catching ``IntegrityError``.
    """
    conn = sqlite3.connect(university_db_path, timeout=30)
    try:
        for _ in range(max_attempts):
            sid = str(secrets.randbelow(9_000_000) + 1_000_000)
            taken = conn.execute(
                "SELECT 1 FROM students WHERE student_id = ?", (sid,),
            ).fetchone()
            if not taken:
                return sid
    finally:
        conn.close()
    # Extreme bad luck — fall through. Caller's INSERT will raise
    # IntegrityError, which we already handle.
    return str(secrets.randbelow(9_000_000) + 1_000_000)


__all__ = [
    "wire_subscribers",
    "on_progression_offered",
    "on_progression_accepted",
    "confirm_enrolment",
]
