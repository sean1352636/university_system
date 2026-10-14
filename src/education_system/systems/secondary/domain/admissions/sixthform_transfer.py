"""Transfer secondary pupils into the sixth form system, through the platform.

This used to import the sixth form's student table, create the student
and an email login from inside the secondary school, and then delete the
secondary pupil. It now runs the platform's seven-step transition:

* the secondary adapter exports what the school holds, and the three
  subject choices travel as the spec's ``application_details``;
* ``handover.SECONDARY_TO_SIXTH_FORM`` decides what may cross;
* the sixth form adapter creates the applicant and enrols them — the
  sixth form provisions its own login for the student, as it does for any
  student it creates;
* the secondary adapter records the pupil on the alumni register and
  takes them off roll, keeping the pupil row.

For a Year 11 pupil weighing several destinations at once, use the post-16
application board (``platform.cross_system.secondary_post16``); this is the
direct move for a pupil whose sixth-form place is already settled.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from education_system.platform.cross_system import route_support
from education_system.platform.cross_system.adapters.base import AdapterError
from education_system.systems.secondary.domain.admissions.cross_system_adapter import (
    alumni_id_for,
)
from education_system.systems.secondary.domain.learners.pupils import (
    pupils as secondary_pupils,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError,
)

logger = logging.getLogger(__name__)

SOURCE = "secondary"
DESTINATION = "sixth_form"
DEFAULT_DESTINATION = "Sixth Form System"

#: The sensitive fields on this boundary a learner or parent may consent to.
CONSENT_FIELDS = ("attendance_behaviour", "access_arrangements", "references",
                  "bursary_indicators")


@dataclass(frozen=True)
class SixthFormTransferResult:
    source_pupil_id: str
    sixthform_student_id: str
    sixthform_email: str | None
    password: str | None
    alumni_id: str | None
    auth_user_id: int | None
    journey_id: str | None = None
    transition_id: str | None = None
    withheld: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def _ensure_not_already_alumni(pupil_id: str) -> None:
    existing = alumni_id_for(pupil_id)
    if existing:
        raise ValidationError(f"Pupil {pupil_id} is already alumni ({existing})")


def move_to_sixth_form(
    pupil_id: str,
    *,
    subject_1: str,
    subject_2: str,
    subject_3: str,
    destination: str | None = None,
    notes: str | None = None,
    consent: bool | set[str] | None = None,
    safeguarding_reference: str | None = None,
    actor_user_id: int | None = None,
    db_path: str | None = None,
) -> SixthFormTransferResult:
    """Move a secondary pupil to the sixth form and take them off roll.

    The sixth form issues the student's login itself; this returns
    ``password=None`` because the secondary school no longer creates, or
    sees, another system's credentials.
    """
    pupil_id = (pupil_id or "").strip()
    if not pupil_id:
        raise ValidationError("Pupil ID is required")
    subjects = [s.strip() for s in (subject_1, subject_2, subject_3) if s and s.strip()]
    if len(subjects) != 3 or len(set(subjects)) != 3:
        raise ValidationError("Choose three different A-level subjects")

    pupil = secondary_pupils.get_pupil(pupil_id)
    if pupil is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    if pupil.roll_status == "left":
        raise ValidationError(f"Pupil {pupil_id} has already left the school")
    _ensure_not_already_alumni(pupil_id)

    try:
        outcome = route_support.transfer(
            source_system=SOURCE, destination_system=DESTINATION,
            student_id=pupil.pupil_id, reason="Moved to sixth form",
            consent=consent, safeguarding_reference=safeguarding_reference,
            extra_record={
                "application_details": {"subjects": subjects,
                                        "route": "direct progression",
                                        "notes": notes or None},
                "subject_recommendations": subjects,
            },
            year_group="12", accepted_by="secondary",
            close_details={"destination": destination or DEFAULT_DESTINATION,
                           "notes": notes or ""},
            actor_user_id=actor_user_id, db_path=db_path)
    except (route_support.RouteError, AdapterError) as exc:
        raise ValidationError(str(exc)) from exc

    student_id = outcome.local_student_id or ""
    logger.info("Moved secondary pupil %s to sixth form student %s via "
                "transition %s", pupil.pupil_id, student_id,
                outcome.transition.get("transition_id"))
    return SixthFormTransferResult(
        source_pupil_id=pupil.pupil_id,
        sixthform_student_id=student_id,
        sixthform_email=getattr(outcome.enrolment, "email", None),
        password=None,
        alumni_id=alumni_id_for(pupil.pupil_id),
        auth_user_id=None,
        journey_id=outcome.journey_id,
        transition_id=outcome.transition.get("transition_id"),
        withheld=tuple(outcome.released.withheld_no_consent),
        warnings=tuple(outcome.warnings),
    )


__all__ = [
    "CONSENT_FIELDS",
    "DEFAULT_DESTINATION",
    "SixthFormTransferResult",
    "move_to_sixth_form",
]
