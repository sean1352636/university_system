"""Primary-side consumer for nursery progression events.

Subscribes to ``student.progression.completed`` on the durable
cross-system bus and admits the child into the primary school: it creates
a primary ``pupils`` row linked to the canonical ``journey_id``.

Mirrors ``university_system/.../admissions/sixthform_intake.py`` but built
on the reusable :class:`~education_system.platform.cross_system.progression.ProgressionIntake`.

Idempotent: the bus's ``cross_system_event_consumed`` table drops
re-delivery, and the intake skips any journey whose ``primary`` slot is
already filled — which it always is when the in-process
``primary_transfer`` flow created the pupil synchronously. The intake is
therefore the cross-process / API safety net.

Drained by :func:`drain_intake`, which the launcher calls on primary
startup.
"""

from __future__ import annotations

import logging

from education_system.platform.cross_system import progression

logger = logging.getLogger(__name__)

CONSUMER_SYSTEM = "primary"
# Reception is the standard nursery leaving point.
_DEFAULT_YEAR_GROUP = "R"


def _admit(journey_id: str, payload: dict) -> str | None:
    """Create a primary pupil from a progression payload."""
    from education_system.systems.primary.domain.learners.pupils import pupils
    from education_system.platform.cross_system import person

    # Canonical demographics are the source of truth; the event payload
    # only fills in the system-specific extras.
    p = person.get(journey_id)
    year = (payload.get("year_group") or "").strip()
    if year not in pupils.YEAR_GROUPS:
        year = _DEFAULT_YEAR_GROUP
    pupil = pupils.create_pupil({
        "first_name": payload.get("first_name")
        or (p.legal_first_name if p else ""),
        "last_name": payload.get("last_name")
        or (p.legal_last_name if p else ""),
        "year_group": year,
        "class_name": payload.get("class_name") or "",
        "date_of_birth": payload.get("date_of_birth")
        or (p.date_of_birth if p else ""),
        "parent_name": payload.get("parent_name") or "",
        "parent_phone": payload.get("parent_phone") or "",
        "medical_notes": payload.get("medical_notes") or "",
    })
    return pupil.pupil_id


_intake = progression.ProgressionIntake(
    CONSUMER_SYSTEM, _admit,
    handler_name="primary.pupils.primary_intake",
    from_system="nursery")


def register_intake_consumer() -> None:
    """Idempotently subscribe the intake handler to the bus."""
    _intake.register()


def drain_intake(*, db_path: str | None = None) -> int:
    """Process any pending nursery progression events. Returns the number
    of (event, handler) dispatches. Safe to call repeatedly."""
    return _intake.drain(db_path=db_path)
