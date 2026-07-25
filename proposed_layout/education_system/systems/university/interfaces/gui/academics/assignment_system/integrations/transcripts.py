"""Gradebook / transcript adapter — mirror finalised assignment grades
into ``student_grades`` so transcript generation picks them up.

The assignment subsystem stores grades in ``assignment_submissions``;
``grade_calculation/transcripts.py`` reads from ``student_grades``.
Without this bridge a grade entered in the assignment GUI would be
invisible on transcripts.
"""

from __future__ import annotations

import logging
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


def sync_grade_to_gradebook(
    *,
    student_id: str,
    module_code: str,
    assessment_name: str,
    grade_value: float | int,
    max_marks: float | int,
    instructor: str | None = None,
    is_final: bool = True,
) -> int | None:
    """Upsert a row into ``student_grades`` keyed on (student, module, assessment).

    Returns the row id of the upserted record, or ``None`` if the
    table is missing.
    """
    if not student_id or not module_code or not assessment_name:
        return None

    pct = (
        round(float(grade_value) / float(max_marks) * 100.0, 2)
        if max_marks
        else None
    )
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            cur = conn.cursor()
            row = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='student_grades'"
            ).fetchone()
            if not row:
                return None

            cur.execute(
                """
                SELECT id FROM student_grades
                WHERE student_id = ? AND module_code = ? AND assessment_name = ?
                LIMIT 1
                """,
                (str(student_id), module_code, assessment_name),
            )
            existing = cur.fetchone()
            grade_str = f"{grade_value}/{max_marks}"

            if existing:
                cur.execute(
                    """
                    UPDATE student_grades
                       SET grade = ?, grade_value = ?, percentage = ?,
                           grade_date = ?, instructor = COALESCE(?, instructor),
                           is_final = ?, updated_at = ?
                     WHERE id = ?
                    """,
                    (
                        grade_str, str(grade_value), pct, now,
                        instructor, 1 if is_final else 0, now, existing[0],
                    ),
                )
                conn.commit()
                return existing[0]

            cur.execute(
                """
                INSERT INTO student_grades
                    (student_id, module_code, assessment_name, grade,
                     grade_value, percentage, assessment_type, grade_date,
                     instructor, is_final, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'assignment', ?, ?, ?, ?, ?)
                """,
                (
                    str(student_id), module_code, assessment_name, grade_str,
                    str(grade_value), pct, now, instructor,
                    1 if is_final else 0, now, now,
                ),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()
    except Exception as exc:
        logger.warning(
            "sync_grade_to_gradebook failed for %s/%s/%s: %s",
            student_id, module_code, assessment_name, exc,
        )
        return None
