"""Cross-domain port for UCAS applicant clear-down.

Admitting a student is done in **Learners** (the student CRUD GUI), but the
UCAS application belongs to **Admissions**, and the choice being closed is the
sixth form's — which is told by event (``university.student.enrolled``) and
marks its own choice *Placed*; nothing is deleted. The learners slice may not reach into another domain — its
allow-list is already the largest in the university and is meant to shrink —
so the call goes through here, the same way enrolment rules and finance holds
do.

Thin by design: the rules live in
``admissions.domain.ucas.post_admission``; this only forwards, and swallows
nothing it should not. See that module for what is recorded and published.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _post_admission():
    from education_system.systems.university.domains.admissions.domain.ucas import (
        post_admission,
    )
    return post_admission


def clear_after_admission(sf_student_id: str,
                          uni_student_id: Optional[str] = None, *,
                          actor: Optional[str] = None,
                          university_name: Optional[str] = None,
                          delete_choices: bool = True) -> Optional[dict[str, Any]]:
    """End a UCAS application now that the applicant is a student here.

    Returns the summary dict, or None when the clear-down could not run at
    all — the caller has already created the student, so this must never
    raise into an otherwise successful admission.
    """
    if not sf_student_id:
        return None
    try:
        return _post_admission().clear_after_admission(
            sf_student_id, uni_student_id, actor=actor,
            university_name=university_name, delete_choices=delete_choices)
    except Exception:
        logger.exception(
            "Could not clear the UCAS application for %s after admitting "
            "them as %s; they may still appear in the UCAS picker",
            sf_student_id, uni_student_id)
        return None


def describe(summary: Optional[dict[str, Any]]) -> str:
    """A one-line account of a clear-down, for a status line or a dialog."""
    if summary is None:
        return "The UCAS application could not be cleared."
    try:
        return _post_admission().describe(summary)
    except Exception:
        return ""
