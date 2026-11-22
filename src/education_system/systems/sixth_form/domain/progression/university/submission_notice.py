"""Telling a student their UCAS application has gone in.

The application's status is no longer typed by hand — it is *derived*
from whether a submission date is on the form (see
:func:`ucas.derive_status`). The moment that derivation moves an
application from Draft to Submitted, the student needs to hear about
it, because from then on the copy on their screen is the one the
universities are reading.

Kept beside the data layer rather than inside it: ``ucas.py`` owns
rows and validation, and reaching from there into the messages log
would make every UCAS write depend on the communications package.
This module is the one place that crosses, and it is best-effort
throughout — a mail server having a bad afternoon must never be the
reason a submission fails to save.
"""

from __future__ import annotations

import logging

from education_system.systems.sixth_form.domain.progression.university import ucas as data

logger = logging.getLogger(__name__)

TEMPLATE = "ucas_application_submitted"

#: Where a student replies if the submission confirmation looks wrong.
CONTACT_EMAIL = "ucas@sixthform.ac.uk"


def _system_name() -> str:
    try:
        from education_system.systems.sixth_form import SYSTEM_NAME
        return SYSTEM_NAME
    except Exception:
        return "Sixth Form"


def _choices_block(choices) -> str:
    """The five slots as they stand, for the body of the email.

    A student reading a submission confirmation is checking one thing:
    that the five choices listed are the five they meant. So they are
    listed in slot order with the course code, and an application sent
    with empty slots says so rather than quietly listing fewer lines
    than the student expects.
    """
    if not choices:
        return ("No choices were listed on this application. If that is "
                "not right, contact us before UCAS processes it.")
    lines = []
    for c in sorted(choices, key=lambda c: c.choice_order):
        code = f" ({c.course_code})" if c.course_code else ""
        year = f", entry {c.entry_year}" if c.entry_year else ""
        lines.append(f"  {c.choice_order}. {c.university} — "
                     f"{c.course_name}{code}{year}")
    remaining = data.MAX_CHOICES - len(lines)
    if remaining > 0:
        lines.append(f"  ({remaining} of your {data.MAX_CHOICES} choice "
                     "slots were left empty.)")
    return "\n".join(lines)


def send_submission_email(application) -> object | None:
    """Email the student that *application* has been submitted.

    Returns the logged ``Message``, or ``None`` when there is nobody to
    write to (student deleted, no address on file) or the send fails.
    Never raises — the caller has already saved the submission.
    """
    try:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        student = _students.get_student(application.student_id)
    except Exception:
        logger.exception(
            "UCAS submission email skipped: could not load student %s",
            application.student_id)
        return None

    if student is None:
        logger.warning(
            "UCAS submission email skipped: no student %s for "
            "application #%d", application.student_id,
            application.application_id)
        return None
    if not (student.email or "").strip():
        logger.warning(
            "UCAS submission email skipped: no email address on file "
            "for %s", student.student_id)
        return None

    try:
        choices = data.list_choices(application.application_id)
    except Exception:
        logger.exception("Could not list choices for application #%d",
                         application.application_id)
        choices = []

    context = {
        "system_name":    _system_name(),
        "student_id":     student.student_id,
        "first_name":     student.first_name,
        "full_name":      student.full_name,
        "cycle_year":     str(application.cycle_year),
        "ucas_id":        application.ucas_id or "—",
        "submitted_at":   application.submitted_at or "—",
        "n_choices":      str(len(choices)),
        "max_choices":    str(data.MAX_CHOICES),
        "choices_block":  _choices_block(choices),
        "contact_email":  CONTACT_EMAIL,
    }

    try:
        from education_system.systems.sixth_form.domains.communications.domain.messages import (
            email_templates as _tpl,
        )
        msg = _tpl.send_from_template(
            TEMPLATE, context,
            to_name=student.full_name,
            to_address=student.email,
            student_id=student.student_id,
        )
    except Exception:
        logger.exception(
            "UCAS submission email failed for application #%d (%s) "
            "(the submission itself was saved)",
            application.application_id, student.student_id)
        return None

    logger.info(
        "Sent UCAS submission confirmation to %s (%s) for "
        "application #%d as message #%d",
        student.student_id, student.email,
        application.application_id, msg.message_id)
    return msg


__all__ = ["TEMPLATE", "CONTACT_EMAIL", "send_submission_email"]
