"""Exam results writeback to the canonical grade tables.

When an exam is marked, the per-student outcome should propagate to:

- ``student_grades`` — assessment-level row used by the gradebook UI.
- ``student_modules.grade`` — current/aggregate grade shown on transcripts
  and degree-progress reports.
- ``grade_audit_log`` — append-only audit record of each change.

The writeback is idempotent: re-entering results for the same exam
overwrites the previous (student_id, module_code, assessment_name) row
in ``student_grades`` and updates the same ``student_modules`` row,
rather than producing duplicates.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

from education_system.post_18.university_system.modules.domain.academics.gui.exam_management.models import Exam

logger = logging.getLogger(__name__)

DEFAULT_PASS_MARK = 40.0


def _assessment_name(exam: Exam) -> str:
    return f"{exam.module_code} Exam ({exam.date})"


def _connect():
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
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
                       results: Dict[str, float],
                       graded_by: str = "exam_management",
                       pass_mark: float = DEFAULT_PASS_MARK) -> Tuple[int, int]:
    """Write per-student exam scores to the gradebook tables.

    Args:
        exam: The exam being graded.
        results: ``{student_id: score}`` where score is a 0–100 percentage.
        graded_by: Username/identifier recorded in audit + student_grades.
        pass_mark: Threshold below which the module is considered failed.

    Returns:
        ``(written, failed)`` — number of students successfully written
        and number that errored.
    """
    if not results:
        return (0, 0)

    conn = _connect()
    if conn is None:
        return (0, len(results))

    written = failed = 0
    assessment_name = _assessment_name(exam)

    try:
        with conn:
            for student_id, score in results.items():
                try:
                    score_f = float(score)
                except (TypeError, ValueError):
                    failed += 1
                    continue
                if score_f < 0 or score_f > 100:
                    failed += 1
                    continue

                letter = _letter_grade(score_f)
                completed = "Completed" if score_f >= pass_mark else "Failed"

                try:
                    _upsert_student_grade(
                        conn, exam, student_id, score_f, letter,
                        assessment_name, graded_by,
                    )
                    _upsert_student_module(
                        conn, exam, student_id, score_f, completed,
                    )
                    _audit_grade_change(
                        conn, exam, student_id, score_f, graded_by,
                    )
                    written += 1
                except Exception as exc:
                    logger.error("Writeback failed for %s/%s: %s",
                                 student_id, exam.module_code, exc)
                    failed += 1
    finally:
        try:
            conn.close()
        except Exception:
            pass

    logger.info(
        "Exam results applied for %s: %d written, %d failed",
        exam.module_code, written, failed,
    )

    # Step 3 of the attendance/absence/exam closed loop: mirror exam-day
    # presence into attendance_records so the % the eligibility gate
    # reads (step 1) reflects students who actually sat the exam.
    # Students with a result are Present; enrolled students missing
    # from the results dict are auto-marked Absent. Best-effort —
    # writeback failure must not affect grade saves.
    try:
        from education_system.post_18.university_system.modules.domain.academics.gui._exam_attendance_writer import (
            record_exam_attendance_bulk,
        )
        present_ids = [sid for sid, score in results.items()
                       if isinstance(score, (int, float)) and 0 <= float(score) <= 100]
        record_exam_attendance_bulk(
            exam, present_ids, recorded_by=graded_by,
        )
    except Exception:
        logger.exception(
            "exam-attendance writeback failed for %s/%s",
            exam.module_code, getattr(exam, "id", "?"),
        )

    return (written, failed)


def _upsert_student_grade(conn, exam: Exam, student_id: str,
                          score: float, letter: str,
                          assessment_name: str, graded_by: str) -> None:
    """Insert-or-update one student_grades row for this (student, exam)."""
    existing = conn.execute(
        "SELECT id FROM student_grades "
        "WHERE student_id = ? AND module_code = ? AND assessment_name = ? "
        "LIMIT 1",
        (student_id, exam.module_code, assessment_name),
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE student_grades SET "
            "  grade = ?, grade_value = ?, percentage = ?, "
            "  assessment_type = 'exam', assessment_date = ?, "
            "  grade_date = date('now'), instructor = ?, "
            "  is_final = 1, weight = 100, updated_at = datetime('now') "
            "WHERE id = ?",
            (letter, str(score), score, exam.date, graded_by, existing[0]),
        )
    else:
        conn.execute(
            "INSERT INTO student_grades "
            "(student_id, module_code, assessment_name, grade, "
            " grade_value, percentage, assessment_type, assessment_date, "
            " grade_date, instructor, is_final, weight) "
            "VALUES (?, ?, ?, ?, ?, ?, 'exam', ?, date('now'), ?, 1, 100)",
            (student_id, exam.module_code, assessment_name,
             letter, str(score), score, exam.date, graded_by),
        )


def _upsert_student_module(conn, exam: Exam, student_id: str,
                           score: float, status: str) -> None:
    """Update the student_modules row with the latest grade + status."""
    row = conn.execute(
        "SELECT id FROM student_modules "
        "WHERE student_id = ? AND module_code = ?",
        (student_id, exam.module_code),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE student_modules SET "
            "  grade = ?, completion_date = ?, status = ? "
            "WHERE id = ?",
            (str(score), exam.date, status, row[0]),
        )
    # If the student isn't enrolled in this module we silently skip —
    # writing to student_grades alone still records the assessment.


def _audit_grade_change(conn, exam: Exam, student_id: str,
                        new_score: float, graded_by: str) -> None:
    """Append a row to grade_audit_log, recording the previous score."""
    prev = conn.execute(
        "SELECT percentage FROM student_grades "
        "WHERE student_id = ? AND module_code = ? "
        "  AND assessment_name = ? LIMIT 1",
        (student_id, exam.module_code, _assessment_name(exam)),
    ).fetchone()
    old_grade = prev[0] if prev and prev[0] is not None else None

    try:
        conn.execute(
            "INSERT INTO grade_audit_log "
            "(student_id, old_grade, new_grade, changed_by, reason) "
            "VALUES (?, ?, ?, ?, ?)",
            (student_id, old_grade, new_score, graded_by,
             f"Exam result: {exam.module_code} on {exam.date}"),
        )
    except Exception as exc:
        # Audit table is best-effort — never block the writeback.
        logger.debug("grade_audit_log insert failed: %s", exc)


def get_existing_results(exam: Exam) -> Dict[str, float]:
    """Return ``{student_id: score}`` for results already stored for *exam*.

    Used by the results-entry dialog to pre-fill marks when the exam has
    been graded before.
    """
    conn = _connect()
    if conn is None:
        return {}
    try:
        rows = conn.execute(
            "SELECT student_id, percentage FROM student_grades "
            "WHERE module_code = ? AND assessment_name = ?",
            (exam.module_code, _assessment_name(exam)),
        ).fetchall()
        return {sid: float(pct) for sid, pct in rows
                if pct is not None}
    except Exception as exc:
        logger.debug("get_existing_results failed: %s", exc)
        return {}
    finally:
        try:
            conn.close()
        except Exception:
            pass
