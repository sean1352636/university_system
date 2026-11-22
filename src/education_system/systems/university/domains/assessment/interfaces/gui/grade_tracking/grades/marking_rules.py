"""Grade Tracking's hooks into the shared marking rules.

The rules themselves (module results, exam marking control, board locks) live
in ``university/application``; this module only adapts them to the dialogs:
asking for a reason, explaining a lock, and running the post-write rules on
the dialog's own connection.
"""

from __future__ import annotations

import logging
from tkinter import simpledialog

from education_system.systems.university.application.exams import marking as exam_marking
from education_system.systems.university.application.assessment import module_results
from education_system.systems.university.infrastructure.database.schemas.grade_results_schema import (
    LOCK_MESSAGE,
)

logger = logging.getLogger(__name__)

ABSENCE_CODES = exam_marking.ABSENCE_CODES


def ask_reason(parent, what="change this mark"):
    """Ask why a recorded mark is changing. Returns the reason, or None if cancelled.

    A blank answer is asked again: a mark nobody can account for is the thing
    this prevents.
    """
    while True:
        reason = simpledialog.askstring(
            "Reason required", f"Why do you need to {what}?\n(This is recorded in the change log.)",
            parent=parent)
        if reason is None:
            return None
        if reason.strip():
            return reason.strip()


def locked_message(cursor, student_id, module_code):
    """The lock explanation if this student's module result is ratified, else None."""
    try:
        if student_id and module_code and module_results.is_locked(cursor.connection, student_id, module_code):
            return LOCK_MESSAGE
    except Exception:
        logger.debug("Lock check failed", exc_info=True)
    return None


def after_exam_mark(conn, grade_id, marker=None):
    """Referral cap, moderation sync and module result for a just-written grade.

    Returns the rules' result; if they cannot run the mark is treated as
    visible (the behaviour before these rules) so saving never fails here.
    """
    try:
        return exam_marking.after_mark(conn, grade_id, marker)
    except Exception:
        logger.warning("Exam marking rules not applied to grade %s", grade_id, exc_info=True)
        return {"capped": False, "released": True}


def log_change(conn, **fields):
    exam_marking.log_change(conn, **fields)


def label_for(conn, assessment_id, student_id, name):
    try:
        return exam_marking.marker_label(conn, assessment_id, student_id, name)
    except Exception:
        return name


def is_lock_error(exc) -> bool:
    return "ratified by an exam board" in str(exc)
