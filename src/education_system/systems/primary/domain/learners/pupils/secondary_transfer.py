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

A pupil whose move was prepared in **Year 6 Transition**
(``year6_transition``) already has an open transition — expected, applied,
offered, accepted or handover-approved. ``route_support.transfer`` finds
that open transition on the pupil's journey and carries on from its
current step, so the final move never opens a second one. Unless the
caller says otherwise, the consent, destination name and safeguarding
pointer recorded there are used, and the Year 6 record is closed as moved.

The primary school never imports the secondary system.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from education_system.platform.cross_system import route_support
from education_system.platform.cross_system.adapters.base import AdapterError
from education_system.systems.primary.domain.learners.pupils import pupils as primary_pupils
from education_system.systems.primary.domain.learners.pupils import year6_transition
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
CONSENT_FIELDS = year6_transition.CONSENT_FIELDS


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


def _year6_record(pupil_id: str) -> year6_transition.Year6Record | None:
    try:
        return year6_transition.latest_record(pupil_id)
    except Exception:  # noqa: BLE001 - the move does not depend on Year 6 records
        logger.exception("Could not read the Year 6 transition record for %s", pupil_id)
        return None


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

    With a Year 6 Transition record: ``consent=None`` uses the consent
    recorded there, ``destination_school=None`` its destination name and
    ``safeguarding_reference=None`` the DSL transfer pointer. A pupil
    recorded as going to an external school is refused here (Year 6
    Transition records that move instead).
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

    y6 = _year6_record(pupil.pupil_id)
    if y6 is not None:
        if y6.destination_type == year6_transition.DESTINATION_EXTERNAL:
            raise ValidationError(
                f"{pupil.full_name} is recorded in Year 6 Transition as going to "
                f"{y6.destination_school}, not the platform's secondary school. "
                f"Record that move in Year 6 Transition, or change the destination "
                f"there first")
        if consent is None and y6.consented_fields:
            consent = set(y6.consented_fields)
        if not destination_school and y6.destination_school:
            destination_school = y6.destination_school
        if not safeguarding_reference:
            safeguarding_reference = year6_transition.safeguarding_reference_for(
                pupil.pupil_id, y6.academic_year)

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
    if y6 is not None:
        try:
            year6_transition.mark_moved(
                pupil.pupil_id, secondary_pupil_id=secondary_id or None,
                transition_id=outcome.transition.get("transition_id"))
        except Exception:  # noqa: BLE001 - the move itself has succeeded
            logger.exception("Could not close the Year 6 transition record for %s",
                             pupil.pupil_id)
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
