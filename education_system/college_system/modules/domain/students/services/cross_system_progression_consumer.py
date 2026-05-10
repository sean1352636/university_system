"""College-side consumer for ``student.progression.completed``.

When the university confirms enrolment (see
``university_system.modules.domain.admissions.services.cross_system_progression
.confirm_enrolment``), this handler flips the college student's
``status`` from ``active`` to ``progressed`` and stores the back-link
to the university student id on the local row.

Wired in by calling ``wire_subscribers(...)`` from the college process
startup. Idempotent: a student already marked ``progressed`` is a
no-op so re-deliveries don't churn audit history.
"""

from __future__ import annotations

import logging
import sqlite3

from education_system.shared.cross_system import identity_service as ids
from education_system.shared.integrations import cross_system_bus as bus

logger = logging.getLogger(__name__)


_HANDLER_NAME = (
    "education_system.college_system.modules.domain.students.services."
    "cross_system_progression_consumer.on_progression_completed"
)

# We keep the back-link to the university student id in
# ``progressed_to_university_id`` if the column exists, so the GUI's
# student-detail panel can show it. The migration is best-effort — if
# the column hasn't been added yet we just skip the update.
_BACKLINK_COLUMN = "progressed_to_university_id"


def wire_subscribers(
    *,
    college_db_path: str,
    auth_db_path: str | None = None,
) -> None:
    """Register the progression-completed handler on the in-process bus."""
    def _handler(envelope: dict) -> None:
        on_progression_completed(
            envelope,
            college_db_path=college_db_path,
            auth_db_path=auth_db_path,
        )
    _handler.__qualname__ = "on_progression_completed"
    _handler.__module__ = __name__
    bus.subscribe(
        bus.EVENT_STUDENT_PROGRESSION_COMPLETED, _handler,
        handler_name=_HANDLER_NAME,
    )
    logger.info(
        "cross_system_progression_consumer: subscribed handler for %s "
        "(college_db=%s)",
        bus.EVENT_STUDENT_PROGRESSION_COMPLETED, college_db_path,
    )


def on_progression_completed(
    envelope: dict,
    *,
    college_db_path: str,
    auth_db_path: str | None = None,
) -> bool:
    """Handle one ``student.progression.completed`` event.

    Returns ``True`` if the local college row was updated, ``False`` if
    there was nothing to do (no journey, no matching college row, or
    the student is already ``progressed``). Never raises on normal
    "nothing to do" cases — those would just churn the bus retry
    counter for no reason.
    """
    journey_id = envelope.get("journey_id")
    if not journey_id:
        logger.warning(
            "progression.completed without journey_id — dropping",
        )
        return False
    payload = envelope.get("payload", {})

    journey = ids.get_journey(journey_id, db_path=auth_db_path)
    if not journey or journey.get("college_pk") is None:
        logger.info(
            "progression.completed: journey %s has no college link — "
            "nothing to update",
            journey_id,
        )
        return False

    college_pk = journey["college_pk"]
    uni_student_id = payload.get("university_student_id")

    conn = sqlite3.connect(college_db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, status FROM students WHERE id = ?",
            (college_pk,),
        ).fetchone()
        if not row:
            logger.warning(
                "progression.completed: college pk %s not found "
                "(journey=%s)",
                college_pk, journey_id,
            )
            return False
        if row["status"] == "progressed":
            logger.info(
                "progression.completed: college pk %s already "
                "progressed (idempotent no-op)",
                college_pk,
            )
            return False

        update_cols = ["status = 'progressed'",
                       "updated_at = datetime('now')"]
        params: list = []

        # Best-effort: write the uni back-link only if the column exists.
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(students)").fetchall()}
        if uni_student_id and _BACKLINK_COLUMN in cols:
            update_cols.insert(1, f"{_BACKLINK_COLUMN} = ?")
            params.append(uni_student_id)

        params.append(college_pk)
        conn.execute(
            f"UPDATE students SET {', '.join(update_cols)} "
            f" WHERE id = ?",  # nosec B608
            params,
        )
        conn.commit()
    finally:
        conn.close()

    logger.info(
        "progression.completed: college pk %s flipped to "
        "'progressed' (journey=%s, uni_student_id=%s)",
        college_pk, journey_id, uni_student_id,
    )
    return True


__all__ = ["wire_subscribers", "on_progression_completed"]
