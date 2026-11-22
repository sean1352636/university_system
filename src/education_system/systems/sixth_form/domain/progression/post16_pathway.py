"""Sixth Form to FE College referral and enrolment workflow.

The workflow lives in the platform's integration layer
(:mod:`education_system.platform.cross_system.fe_applications`), which the
FE College also uses for its incoming queue, so neither system imports the
other. This module keeps the sixth form's own names for it.
"""

from __future__ import annotations

from education_system.platform.cross_system import fe_applications as _fe

SOURCE = "sixth_form"
DESTINATION = _fe.DESTINATION
PathwayError = _fe.PathwayError


def refer(student_id: str, **kwargs) -> dict:
    """Refer a sixth-form learner and create an idempotent FE applicant."""
    return _fe.refer(SOURCE, student_id, **kwargs)


accept_referral = _fe.accept_referral
enrol_referral = _fe.enrol_referral


def incoming_referrals(*, status: str | None = None, db_path: str | None = None) -> list[dict]:
    """FE admissions' queue of Sixth Form referrals."""
    return _fe.incoming_referrals(source_system=SOURCE, status=status, db_path=db_path)


__all__ = ["PathwayError", "refer", "accept_referral", "enrol_referral",
           "incoming_referrals"]
