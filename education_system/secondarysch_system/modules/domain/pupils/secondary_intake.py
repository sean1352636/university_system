"""Secondary-side consumer for primary progression events.

Subscribes to ``student.progression.completed`` on the durable
cross-system bus and admits the pupil into the secondary school: it
creates a secondary ``pupils`` row linked to the canonical ``journey_id``.

Idempotent: re-delivery is dropped by the bus, and a journey whose
``school`` slot is already filled (the in-process ``secondary_transfer``
path) is skipped. The intake is the cross-process / API safety net.

Drained by :func:`drain_intake`, called on secondary startup.
"""

from __future__ import annotations

import logging

from education_system.shared.cross_system import progression

logger = logging.getLogger(__name__)

CONSUMER_SYSTEM = "school"
# Year 7 is the entry year for secondary school.
_DEFAULT_YEAR_GROUP = "7"


def _admit(journey_id: str, payload: dict) -> str | None:
    """Create a secondary pupil from a progression payload."""
    from education_system.secondarysch_system.modules.domain.pupils.pupils import (
        pupils,
    )
    from education_system.shared.cross_system import person

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
        "form_group": payload.get("form_group") or "",
        "date_of_birth": payload.get("date_of_birth")
        or (p.date_of_birth if p else ""),
        "phone": payload.get("phone") or "",
        "parent_name": payload.get("parent_name") or "",
        "parent_phone": payload.get("parent_phone") or "",
    })
    return pupil.pupil_id


_intake = progression.ProgressionIntake(
    CONSUMER_SYSTEM, _admit,
    handler_name="secondary.pupils.secondary_intake",
    from_system="primary")


def register_intake_consumer() -> None:
    """Idempotently subscribe the intake handler to the bus."""
    _intake.register()


def drain_intake(*, db_path: str | None = None) -> int:
    """Process any pending primary progression events. Returns the number
    of (event, handler) dispatches. Safe to call repeatedly."""
    return _intake.drain(db_path=db_path)
