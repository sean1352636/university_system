"""Port onto Admissions for other slices.

Learners' Create Student imports sixth-form leavers ("Admit from UCAS"): it
lists the applicants, asks Admissions whether an application is already
staged for a learner, enrols through the admissions lifecycle when the
application is ready, and otherwise binds the student it created directly
to that application. The slice rules keep Learners from importing Admissions
itself, so those calls come through here.
"""

from __future__ import annotations


def _lifecycle():
    from education_system.systems.university.domains.admissions.domain.services import (
        admissions_lifecycle,
    )
    return admissions_lifecycle


def _intake():
    from education_system.systems.university.domains.admissions.domain import (
        sixthform_intake,
    )
    return sixthform_intake


def list_applicants(**kwargs) -> list:
    """Everyone applying to the university (UCAS and staged sixth-form
    handovers), actionable people first."""
    from education_system.systems.university.domains.admissions.domain.ucas import (
        applicants,
    )
    return applicants.list_all_applicants(**kwargs)


def application_for_journey(journey_id: str) -> dict | None:
    """The admission application already staged for ``journey_id``, if any."""
    return _intake().find_application_for_journey(journey_id)


def applications_for_journeys(journey_ids, *, strict: bool = False) -> dict[str, dict]:
    return _intake().find_applications_for_journeys(journey_ids, strict=strict)


def readiness_issues(application_id: int) -> list[str]:
    """Why an accepted application cannot enrol yet (empty when it can)."""
    return _lifecycle().readiness_issues(application_id)


def convert_to_student(application_id: int, *, actor_id: str = "") -> str:
    """Enrol from the application (all gates), returning the student id."""
    return _lifecycle().convert_to_student(application_id, actor_id=actor_id)


def attach_direct_enrolment(application_id: int, student_id: str, *,
                            actor_id: str = "", reason: str = "") -> bool:
    """Bind a student created outside the lifecycle to their application."""
    return _lifecycle().attach_direct_enrolment(application_id, student_id,
                                                actor_id=actor_id, reason=reason)
