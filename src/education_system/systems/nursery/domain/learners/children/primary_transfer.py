"""Move a nursery child into the Primary School System, through the platform.

The nursery's natural leaving destination is Reception (year ``R``). This
module used to import the primary school's pupil table and write a pupil
row itself, copying the child's medical notes straight across. It now runs
the platform's seven-step transition instead:

* the nursery adapter exports what the nursery holds;
* ``handover.NURSERY_TO_PRIMARY`` decides what may cross, and medical,
  SEND and communication detail cross only with the parent's consent;
* the primary adapter creates the applicant and puts them on roll;
* the nursery adapter takes the child off roll (status ``left``) — kept,
  never deleted, so the EYFS record survives for safeguarding and audit.

The nursery never imports the primary system. A failure part-way leaves
the transition at the step it reached, and running the move again resumes
it rather than creating a second pupil.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from education_system.platform.cross_system import route_support
from education_system.platform.cross_system.adapters.base import AdapterError
from education_system.systems.nursery.domain.learners.children import children
from education_system.systems.nursery.domain.learners.children.children import (
    ValidationError,
)

logger = logging.getLogger(__name__)

SOURCE = "nursery"
DESTINATION = "primary"

# Reception is the first primary year and the standard nursery leaving point.
DEFAULT_YEAR_GROUP = "R"

#: The primary phase's year groups, for the dialog. Stated here rather than
#: read from the primary system: the nursery reaches primary only through
#: the platform, and the primary adapter re-validates the year it is given.
PRIMARY_YEAR_GROUPS = ("R", "1", "2", "3", "4", "5", "6")

#: The fields on this boundary that need the parent's consent to cross.
#: ``medical_alerts`` is also required, so the move cannot complete
#: without consent to share it.
MEDICAL_CONSENT = "medical_alerts"
SUPPORT_CONSENT = ("send_support", "communication_needs")


@dataclass(frozen=True)
class PrimaryTransferResult:
    source_child_id: str
    primary_pupil_id: str
    primary_email: str
    year_group: str
    journey_id: str | None = None
    transition_id: str | None = None
    withheld: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def primary_year_groups() -> tuple[str, ...]:
    """The primary school's year groups (R, 1–6)."""
    return PRIMARY_YEAR_GROUPS


def consent_for(*, medical: bool, support: bool) -> set[str]:
    """The granular consent a parent gave, as build_handover expects it."""
    granted: set[str] = set()
    if medical:
        granted.add(MEDICAL_CONSENT)
    if support:
        granted.update(SUPPORT_CONSENT)
    return granted


def move_to_primary_school(
    child_id: str,
    *,
    year_group: str | None = None,
    class_name: str | None = None,
    consent: bool | set[str] | None = None,
    safeguarding_reference: str | None = None,
    actor_user_id: int | None = None,
    db_path: str | None = None,
) -> PrimaryTransferResult:
    """Move a nursery child into the primary system and take them off roll.

    ``consent`` is the parent's consent to the sensitive fields — ``True``
    for all of them, or a set such as :func:`consent_for` builds. The
    NURSERY_TO_PRIMARY spec requires medical alerts, so without consent to
    share them this raises rather than sending a child to Reception with
    their allergies silently missing.
    """
    child_id = (child_id or "").strip()
    if not child_id:
        raise ValidationError("Child ID is required")

    child = children.get_child(child_id)
    if child is None:
        raise ValidationError(f"No child with id {child_id}")
    if child.status == "left":
        raise ValidationError(
            f"{child.full_name} ({child_id}) has already left the nursery"
        )

    year = (year_group or DEFAULT_YEAR_GROUP).strip() or DEFAULT_YEAR_GROUP
    if year not in PRIMARY_YEAR_GROUPS:
        raise ValidationError(
            "Year group must be one of " + ", ".join(PRIMARY_YEAR_GROUPS)
        )

    try:
        outcome = route_support.transfer(
            source_system=SOURCE, destination_system=DESTINATION,
            student_id=child.pupil_id, reason="Moved to primary school",
            consent=consent, safeguarding_reference=safeguarding_reference,
            year_group=year, accepted_by="nursery",
            enrolment_details={"year_group": year, "class_name": class_name or ""},
            actor_user_id=actor_user_id, db_path=db_path)
    except (route_support.RouteError, AdapterError) as exc:
        raise ValidationError(str(exc)) from exc

    enrolment = outcome.enrolment
    pupil_id = outcome.local_student_id or ""
    logger.info("Moved nursery child %s to primary pupil %s (year %s) via "
                "transition %s", child.pupil_id, pupil_id, year,
                outcome.transition.get("transition_id"))
    return PrimaryTransferResult(
        source_child_id=child.pupil_id,
        primary_pupil_id=pupil_id,
        primary_email=getattr(enrolment, "email", None) or "",
        year_group=(enrolment.year_group if enrolment else None) or year,
        journey_id=outcome.journey_id,
        transition_id=outcome.transition.get("transition_id"),
        withheld=tuple(outcome.released.withheld_no_consent),
        warnings=tuple(outcome.warnings),
    )


__all__ = [
    "DEFAULT_YEAR_GROUP",
    "PRIMARY_YEAR_GROUPS",
    "PrimaryTransferResult",
    "consent_for",
    "move_to_primary_school",
    "primary_year_groups",
]
