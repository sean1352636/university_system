"""Transfer primary pupils into the secondary school system, through the platform.

This used to import the secondary school's pupil table, create the pupil
and their login from inside the primary system, and then delete the
primary pupil. It now runs the platform's seven-step transition:

* the primary adapter exports what the school holds;
* ``handover.PRIMARY_TO_SECONDARY`` decides what may cross — SEND and
  medical detail only with the parent's consent;
* the secondary adapter creates the Year 7 applicant, puts them on roll
  and makes their login;
* the primary adapter records the leaver and takes the pupil off roll.
  The pupil row is kept, never deleted.

The primary school never imports the secondary system.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from education_system.platform.cross_system import route_support
from education_system.platform.cross_system.adapters.base import AdapterError
from education_system.systems.primary.domain.learners.pupils import pupils as primary_pupils
from education_system.systems.primary.domain.learners.pupils.cross_system_adapter import (
    leaver_id_for,
)
from education_system.systems.primary.domain.learners.pupils.pupils import ValidationError

logger = logging.getLogger(__name__)

SOURCE = "primary"
DESTINATION = "secondary"
SECONDARY_ENTRY_YEAR = "7"
DEFAULT_DESTINATION = "Secondary School System"

#: The sensitive fields on this boundary a parent may consent to share.
CONSENT_FIELDS = ("send_provision", "support_indicators",
                  "current_interventions", "medical_requirements")


@dataclass(frozen=True)
class SecondaryTransferResult:
    source_pupil_id: str
    secondary_pupil_id: str
    secondary_email: str
    password: str | None
    leaver_id: str | None
    auth_user_id: int | None
    journey_id: str | None = None
    transition_id: str | None = None
    withheld: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def _ensure_not_already_leaver(pupil_id: str) -> None:
    existing = leaver_id_for(pupil_id)
    if existing:
        raise ValidationError(f"Pupil {pupil_id} is already a leaver ({existing})")


def move_to_secondary_school(
    pupil_id: str,
    *,
    form_group: str | None = None,
    destination_school: str | None = None,
    notes: str | None = None,
    consent: bool | set[str] | None = None,
    safeguarding_reference: str | None = None,
    actor_user_id: int | None = None,
    db_path: str | None = None,
) -> SecondaryTransferResult:
    """Move a primary pupil to secondary; the secondary school makes the login.

    The generated password is returned once, when the secondary created a
    new login, so the operator can pass it on. A retried move that finds
    the login already made returns ``password=None``.
    """
    pupil_id = (pupil_id or "").strip()
    if not pupil_id:
        raise ValidationError("Pupil ID is required")

    pupil = primary_pupils.get_pupil(pupil_id)
    if pupil is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    if pupil.roll_status == "left":
        raise ValidationError(f"Pupil {pupil_id} has already left the school")
    _ensure_not_already_leaver(pupil_id)

    def _leaver_details(outcome: route_support.TransferOutcome) -> dict:
        return {
            "destination_school": destination_school or DEFAULT_DESTINATION,
            "current_email": getattr(outcome.enrolment, "email", None) or "",
            "notes": notes or "",
        }

    try:
        outcome = route_support.transfer(
            source_system=SOURCE, destination_system=DESTINATION,
            student_id=pupil.pupil_id, reason="Moved to secondary school",
            consent=consent, safeguarding_reference=safeguarding_reference,
            year_group=SECONDARY_ENTRY_YEAR, accepted_by="primary",
            enrolment_details={"form_group": form_group or "",
                               "provision_login": True},
            close_details=_leaver_details,
            actor_user_id=actor_user_id, db_path=db_path)
    except (route_support.RouteError, AdapterError) as exc:
        raise ValidationError(str(exc)) from exc

    enrolment = outcome.enrolment
    secondary_id = outcome.local_student_id or ""
    logger.info("Moved primary pupil %s to secondary pupil %s via transition %s",
                pupil.pupil_id, secondary_id,
                outcome.transition.get("transition_id"))
    return SecondaryTransferResult(
        source_pupil_id=pupil.pupil_id,
        secondary_pupil_id=secondary_id,
        secondary_email=getattr(enrolment, "email", None) or "",
        password=getattr(enrolment, "initial_password", None),
        leaver_id=leaver_id_for(pupil.pupil_id),
        auth_user_id=getattr(enrolment, "auth_user_id", None),
        journey_id=outcome.journey_id,
        transition_id=outcome.transition.get("transition_id"),
        withheld=tuple(outcome.released.withheld_no_consent),
        warnings=tuple(outcome.warnings),
    )


__all__ = [
    "CONSENT_FIELDS",
    "DEFAULT_DESTINATION",
    "SecondaryTransferResult",
    "move_to_secondary_school",
]
