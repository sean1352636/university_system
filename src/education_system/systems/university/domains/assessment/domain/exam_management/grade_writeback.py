"""Online exam results writeback, through the marking rules.

(Superseded description below: results now go to ``grades`` via
``application/exams/results`` rather than straight to ``student_grades``.)

Scheduled sit-down exams already propagate to the gradebook: the Exam
Scheduler's results dialog calls ``apply_exam_results``, which writes
``student_grades``, ``student_modules`` and ``grade_audit_log``.

Online exams had no equivalent. A student could sit one in the exam portal,
have it graded, see the score under "My Results" — and nothing would ever
reach the gradebook, because the portal keeps its scores in
``exam_portal_attempts`` and nothing carried them across. The portal's
exam-side sync (``sync_from_scheduler``) only ever ran the other way, and
only for exams, never results.

This module closes that gap. It is deliberately the mirror image of
``apply_exam_results``:

* the same three tables, in the same order;
* idempotent — re-grading an attempt updates the same ``student_grades`` row
  rather than adding another;
* the audit insert is best-effort and never blocks the write.

It lives in the domain layer and imports no interface code, so both the
service and any GUI can call it. The letter-grade mapping is repeated here
rather than imported from the scheduler's ``results`` module, because that
module sits under ``interfaces/gui`` and a domain service must not import
an interface.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

DEFAULT_PASS_MARK = 50.0


def _letter_grade(percent: float) -> str:
    """Map a 0–100 score to a coarse UK-style letter grade.

    Matches the scheduler's mapping so an online exam and a sit-down exam of
    the same percentage get the same letter.
    """
    if percent >= 70:
        return "A"
    if percent >= 60:
        return "B"
    if percent >= 50:
        return "C"
    if percent >= 40:
        return "D"
    return "F"


def assessment_name_for(title: str, portal_exam_id) -> str:
    """The stable ``student_grades.assessment_name`` for an online exam.

    Carries the exam id so two exams sharing a title cannot collide on the
    same gradebook row, and so re-grading always finds the row it wrote last
    time. Distinct from the scheduler's ``"{module} Exam ({date})"``, so an
    online exam and a scheduled one for the same module stay separate rows.
    """
    clean = (title or "Online exam").strip() or "Online exam"
    return f"{clean} (online exam #{portal_exam_id})"


def apply_attempt_result(attempt_id: int,
                         graded_by: str = "exam_portal",
                         conn=None) -> Optional[Dict]:
    """Write one graded portal attempt into the gradebook.

    Returns a summary dict, or None when there was nothing to write —
    an unknown attempt, one that is not graded yet, or a portal exam with no
    ``module_code`` to attach a grade to.

    Never raises: a gradebook problem must not undo a grading decision that
    is already committed on the portal side.
    """
    close = conn is None
    conn = conn or get_connection()
    try:
        row = conn.execute(
            """SELECT a.student_id, a.score, a.percentage, a.passed, a.status,
                      COALESCE(a.submitted_at, a.graded_at) AS taken_at,
                      e.id, e.title, e.module_code, e.pass_mark
               FROM exam_portal_attempts a
               JOIN exam_portal_exams e ON e.id = a.exam_id
               WHERE a.id = ?""", (attempt_id,)).fetchone()
        if row is None:
            logger.debug("attempt %s not found for writeback", attempt_id)
            return None

        (student_id, score, percentage, passed, status, taken_at,
         portal_exam_id, title, module_code, pass_mark) = tuple(row)

        if str(status or "").lower() != "graded":
            # Still awaiting manual marking — writing a partial score would
            # put a provisional grade in the gradebook.
            return None
        if not module_code:
            logger.info(
                "attempt %s has no module_code; nothing to attach a grade to",
                attempt_id)
            return None
        if not student_id:
            return None

        percentage = float(percentage or 0.0)
        letter = _letter_grade(percentage)
        assessment_name = assessment_name_for(title, portal_exam_id)
        taken_date = str(taken_at or "")[:10] or None
        threshold = float(pass_mark if pass_mark is not None else DEFAULT_PASS_MARK)
        is_pass = bool(passed) if passed is not None else percentage >= threshold

        # Through the marking rules: the mark goes to ``grades`` against the
        # online exam's assessment (its scheduled sitting's, when it mirrors
        # one), counts in the module result, is held until released (which
        # also writes the transcript row), and respects board locks. It no
        # longer sets the module's status from a single exam.
        from education_system.systems.university.application.exams import results as exam_results
        exam_results.record_online_result(
            conn, portal_exam_id, student_id, percentage, graded_by,
            scheduler_exam_id=_scheduler_exam_id(conn, portal_exam_id))

        if close:
            conn.commit()

        logger.info("Wrote online exam result to gradebook: %s / %s = %.1f%%",
                    student_id, module_code, percentage)
        return {
            "student_id": student_id,
            "module_code": module_code,
            "assessment_name": assessment_name,
            "percentage": round(percentage, 1),
            "grade": letter,
            "passed": is_pass,
        }
    except Exception as exc:
        logger.error("Gradebook writeback failed for attempt %s: %s",
                     attempt_id, exc)
        return None
    finally:
        if close:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)


def _scheduler_exam_id(conn, portal_exam_id):
    """The scheduled sitting an online exam mirrors (same module, date and start)."""
    row = conn.execute("SELECT module_code, start_time FROM exam_portal_exams WHERE id = ?",
                       (portal_exam_id,)).fetchone()
    if not row or not row[0] or not row[1] or " " not in str(row[1]):
        return None
    date_part, time_part = str(row[1]).split(" ", 1)
    match = conn.execute("SELECT id FROM exams WHERE module_code = ? AND date = ? AND start_time = ? "
                         "LIMIT 1", (row[0], date_part, time_part[:5])).fetchone()
    return match[0] if match else None


def _upsert_student_grade(conn, student_id, module_code, assessment_name,
                          letter, percentage, taken_date, graded_by) -> None:
    """Insert-or-update the one gradebook row for this attempt."""
    existing = conn.execute(
        "SELECT id FROM student_grades "
        "WHERE student_id = ? AND module_code = ? AND assessment_name = ? "
        "LIMIT 1",
        (student_id, module_code, assessment_name)).fetchone()

    if existing:
        conn.execute(
            "UPDATE student_grades SET "
            "  grade = ?, grade_value = ?, percentage = ?, "
            "  assessment_type = 'exam', assessment_date = ?, "
            "  grade_date = date('now'), instructor = ?, "
            "  is_final = 1, weight = 100, updated_at = datetime('now') "
            "WHERE id = ?",
            (letter, str(percentage), percentage, taken_date, graded_by,
             tuple(existing)[0]))
    else:
        conn.execute(
            "INSERT INTO student_grades "
            "(student_id, module_code, assessment_name, grade, "
            " grade_value, percentage, assessment_type, assessment_date, "
            " grade_date, instructor, is_final, weight) "
            "VALUES (?, ?, ?, ?, ?, ?, 'exam', ?, date('now'), ?, 1, 100)",
            (student_id, module_code, assessment_name, letter,
             str(percentage), percentage, taken_date, graded_by))


def _upsert_student_module(conn, student_id, module_code, percentage,
                           taken_date, is_pass) -> None:
    """Update the enrolment row's current grade, when one exists.

    A student not enrolled in the module is skipped silently — the
    ``student_grades`` row still records the assessment. Same rule the
    scheduler's writeback follows.
    """
    row = conn.execute(
        "SELECT id FROM student_modules WHERE student_id = ? AND module_code = ?",
        (student_id, module_code)).fetchone()
    if not row:
        return
    conn.execute(
        "UPDATE student_modules SET grade = ?, completion_date = ?, status = ? "
        "WHERE id = ?",
        (str(percentage), taken_date,
         "completed" if is_pass else "failed", tuple(row)[0]))


def _audit(conn, student_id, module_code, assessment_name, new_percentage,
           graded_by, title) -> None:
    """Append to grade_audit_log, capturing the score being replaced."""
    try:
        prev = conn.execute(
            "SELECT percentage FROM student_grades "
            "WHERE student_id = ? AND module_code = ? AND assessment_name = ? "
            "LIMIT 1",
            (student_id, module_code, assessment_name)).fetchone()
        old = tuple(prev)[0] if prev else None
        conn.execute(
            "INSERT INTO grade_audit_log "
            "(student_id, old_grade, new_grade, changed_by, reason) "
            "VALUES (?, ?, ?, ?, ?)",
            (student_id, old, new_percentage, graded_by,
             f"Online exam result: {title}"))
    except Exception as exc:
        # Best-effort, exactly as the scheduler's writeback treats it.
        logger.debug("grade_audit_log insert failed: %s", exc)


__all__ = ["apply_attempt_result", "assessment_name_for", "DEFAULT_PASS_MARK"]
