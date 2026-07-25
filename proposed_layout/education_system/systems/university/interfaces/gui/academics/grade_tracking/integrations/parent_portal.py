"""Parent portal adapter — child grades read path.

Mirrors the assignment-side ``fetch_child_assignments`` helper so
the CLI ``view_child_grades`` and any future GUI panel share one
data path.
"""

from __future__ import annotations

import logging

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


def fetch_child_grades(student_id: str | int) -> list[dict]:
    """Return per-module grade summary for a child.

    Each row: ``module_code, module_name, assessment_name,
    grade_or_score, grade_date``. Reads ``student_grades`` first
    (the canonical gradebook now populated by both grade-tracking
    and the assignment GUI's ``sync_grade_to_gradebook``); falls
    back to ``module_grades`` joined with ``modules``.
    """
    out: list[dict] = []
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            tables = {
                r[0] for r in cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if "student_grades" in tables:
                cur.execute(
                    """
                    SELECT sg.module_code,
                           COALESCE(m.module_name, sg.module_code) AS module_name,
                           sg.assessment_name,
                           COALESCE(sg.grade_value, sg.grade) AS grade,
                           sg.percentage,
                           sg.grade_date,
                           sg.is_final
                    FROM student_grades sg
                    LEFT JOIN modules m ON m.module_code = sg.module_code
                    WHERE sg.student_id = ?
                    ORDER BY sg.module_code, sg.grade_date
                    """,
                    (str(student_id),),
                )
                out = [dict(r) for r in cur.fetchall()]
                if out:
                    return out

            if "module_grades" in tables:
                cur.execute(
                    """
                    SELECT mg.module_code,
                           COALESCE(m.module_name, mg.module_code) AS module_name,
                           '' AS assessment_name,
                           mg.final_grade AS grade,
                           mg.final_score AS percentage,
                           mg.completion_date AS grade_date,
                           1 AS is_final
                    FROM module_grades mg
                    LEFT JOIN modules m ON m.module_code = mg.module_code
                    WHERE mg.student_id = ?
                    ORDER BY mg.module_code
                    """,
                    (str(student_id),),
                )
                out = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("fetch_child_grades failed for %s: %s", student_id, exc)
    return out
