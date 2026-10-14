"""Sending a reviewer's personal-statement feedback to the student.

Feedback that only ever lives in a `feedback` column is feedback the
student never reads. This sends it — with the draft's status and its
UCAS character/line counts, because "you are 300 characters over" is
the single most actionable thing a reviewer says about a statement.

Kept beside the data layer rather than inside it, for the same reason
as the UCAS submission notice: ``personal_statements.py`` owns rows and
validation, and reaching from there into the messages log would make
every draft write depend on the communications package. Best-effort
throughout — a failing mail server must not be what stops a review
being saved.
"""

from __future__ import annotations

import logging

from education_system.systems.sixth_form.domain.progression.university import statements as data

logger = logging.getLogger(__name__)

TEMPLATE = "personal_statement_feedback"

#: Where a student replies to feedback about a statement.
CONTACT_EMAIL = "ucas@sixthform.ac.uk"


def _system_name() -> str:
    try:
        from education_system.systems.sixth_form import SYSTEM_NAME
        return SYSTEM_NAME
    except Exception:
        return "Sixth Form"


def _limits_block(statement) -> str:
    """The UCAS limits, said as headroom or as an overrun.

    Two different messages, because they call for two different actions:
    a statement with room to spare can be developed, and one over the
    limit cannot be submitted at all until it is cut.
    """
    over_chars = statement.char_count - data.MAX_CHARS
    over_lines = statement.line_count - data.MAX_LINES
    if over_chars > 0 or over_lines > 0:
        problems = []
        if over_chars > 0:
            problems.append(f"{over_chars} characters over the "
                            f"{data.MAX_CHARS}-character limit")
        if over_lines > 0:
            problems.append(f"{over_lines} lines over the "
                            f"{data.MAX_LINES}-line limit")
        return ("This draft is " + " and ".join(problems) + ". UCAS will "
                "not accept it until it is cut down, so treat that as the "
                "first job.")
    return (f"You have {data.MAX_CHARS - statement.char_count} characters "
            f"and {data.MAX_LINES - statement.line_count} lines still "
            "available within the UCAS limits.")


def send_feedback_email(statement, *, reviewer: str | None = None):
    """Email *statement*'s feedback to the student it belongs to.

    Returns the logged ``Message``, or ``None`` when there is nothing to
    send (no feedback), nobody to send it to (student deleted, no
    address), or the send failed. Never raises.
    """
    if not (statement.feedback or "").strip():
        logger.warning(
            "Feedback email skipped: statement #%d has no feedback on it",
            statement.statement_id)
        return None

    try:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        student = _students.get_student(statement.student_id)
    except Exception:
        logger.exception(
            "Feedback email skipped: could not load student %s",
            statement.student_id)
        return None

    if student is None:
        logger.warning(
            "Feedback email skipped: no student %s for statement #%d",
            statement.student_id, statement.statement_id)
        return None
    if not (student.email or "").strip():
        logger.warning(
            "Feedback email skipped: no email address on file for %s",
            student.student_id)
        return None

    context = {
        "system_name":   _system_name(),
        "student_id":    student.student_id,
        "first_name":    student.first_name,
        "full_name":     student.full_name,
        "title":         statement.title or "(untitled draft)",
        "status":        statement.status,
        "reviewer":      (reviewer or statement.reviewer
                          or "your reviewer"),
        "feedback":      statement.feedback.strip(),
        "word_count":    str(statement.word_count),
        "char_count":    str(statement.char_count),
        "line_count":    str(statement.line_count),
        "max_chars":     str(data.MAX_CHARS),
        "max_lines":     str(data.MAX_LINES),
        "limits_block":  _limits_block(statement),
        "contact_email": CONTACT_EMAIL,
    }

    try:
        from education_system.systems.sixth_form.domain.operations.communications.messages import (
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
            "Feedback email failed for statement #%d (%s)",
            statement.statement_id, student.student_id)
        return None

    logger.info(
        "Sent personal-statement feedback to %s (%s) for statement #%d "
        "as message #%d",
        student.student_id, student.email, statement.statement_id,
        msg.message_id)
    return msg


__all__ = ["TEMPLATE", "CONTACT_EMAIL", "send_feedback_email"]
