"""Exam results → the marking rules.

Results used to be written straight into ``student_grades`` and
``student_modules``: one exam set the whole module to completed/failed, the
mark never reached the module result, students saw it at once, and a module
an exam board had ratified could be overwritten.

Now each sitting is linked to an assessment and its results go through
``application/exams/results`` into ``grades``: they count in the combined
module result, follow release, moderation and anonymous marking, respect
board locks, and reach transcripts (``student_grades``) when released. The
module's status is the exam board's to set.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

from education_system.systems.university.domains.assessment.interfaces.gui.exam_management.models import Exam

logger = logging.getLogger(__name__)

DEFAULT_PASS_MARK = 40.0


def _assessment_name(exam: Exam) -> str:
    return f"{exam.module_code} Exam ({exam.date})"


def _connect():
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        return get_connection()
    except Exception as exc:
        logger.error("DB unavailable for grade writeback: %s", exc)
        return None


def _letter_grade(percent: float) -> str:
    """Map a 0–100 score to a coarse UK-style letter grade."""
    if percent >= 70:
        return "A"
    if percent >= 60:
        return "B"
    if percent >= 50:
        return "C"
    if percent >= 40:
        return "D"
    return "F"


def apply_exam_results(exam: Exam,
                       results: Dict[str, object],
                       graded_by: str = "exam_management",
                       pass_mark: float = DEFAULT_PASS_MARK,
                       reason: Optional[str] = None,
                       errors: Optional[list] = None) -> Tuple[int, int]:
    """Record a sitting's results through the marking rules.

    ``results`` is ``{student_id: percentage or 'ABS'/'ABS-MC'}``. Changing
    a recorded result needs ``reason``. Per-student refusals (for example a
    module result ratified by an exam board) are appended to ``errors`` as
    ``(student_id, message)``. Returns ``(written, failed)``.
    """
    if not results:
        return (0, 0)
    from education_system.systems.university.application.exams import results as exam_results
    conn = _connect()
    if conn is None:
        return (0, len(results))
    try:
        outcome = exam_results.record_results(conn, exam.id, results, graded_by, reason)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        if errors is not None:
            errors.append(("", str(exc)))
        logger.error("Exam results not recorded for %s: %s", exam.module_code, exc)
        return (0, len(results))
    finally:
        conn.close()
    if errors is not None:
        errors.extend(outcome["errors"])

    # Step 3 of the attendance/absence/exam closed loop: mirror exam-day
    # presence into attendance_records so the eligibility gate reflects who
    # actually sat. Students with a numeric result were present.
    try:
        from education_system.systems.university.domains.assessment.interfaces.gui._exam_attendance_writer import (
            record_exam_attendance_bulk,
        )
        present_ids = [sid for sid, score in results.items() if not isinstance(score, str)]
        record_exam_attendance_bulk(exam, present_ids, recorded_by=graded_by)
    except Exception:
        logger.exception("exam-attendance writeback failed for %s/%s",
                         exam.module_code, getattr(exam, "id", "?"))
    return (outcome["written"], len(outcome["errors"]))


def changed_students(exam: Exam, results: Dict[str, object]) -> list:
    """Students whose new result differs from one already recorded."""
    from education_system.systems.university.application.exams import results as exam_results
    conn = _connect()
    if conn is None:
        return []
    try:
        changed = exam_results.changed_students(conn, exam.id, results)
        conn.commit()
        return changed
    finally:
        conn.close()


def get_existing_results(exam: Exam) -> Dict[str, object]:
    """``{student_id: percentage or absence code}`` already recorded for *exam*."""
    from education_system.systems.university.application.exams import results as exam_results
    conn = _connect()
    if conn is None:
        return {}
    try:
        return exam_results.existing_results(conn, exam.id)
    except Exception as exc:
        logger.debug("get_existing_results failed: %s", exc)
        return {}
    finally:
        conn.close()


def marker_labels(exam: Exam, students) -> Dict[str, str]:
    """{student_id: label} — the candidate number while marking is anonymous."""
    from education_system.systems.university.application.exams import results as exam_results
    conn = _connect()
    if conn is None:
        return {}
    try:
        numbers = exam_results.candidate_numbers(conn, exam.id, [s.get("student_id") for s in students])
        anonymous = exam_results.is_anonymous(conn, exam.id)
        conn.commit()
    finally:
        conn.close()
    if not anonymous:
        return {}
    return {sid: f"Candidate {num}" for sid, num in numbers.items()}
