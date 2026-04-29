"""Submissions adapter — read-only access to ``assignment_submissions``.

The grade-tracking analytics view used to embed half-a-dozen raw
SQL queries against ``assignment_submissions``. This module gives
those callers one place to fetch the rows so a future
``AssignmentSubmissionService`` can swap in transparently.
"""

from __future__ import annotations

import logging

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


def fetch_assignment_submissions(
    *,
    student_id: str | None = None,
    module_code: str | None = None,
    only_graded: bool = True,
    limit: int = 1000,
) -> list[dict]:
    """Return submission rows joined with their assignment metadata.

    Each row is a dict with keys: ``submission_id``, ``assignment_id``,
    ``student_id``, ``title``, ``module_code``, ``grade``,
    ``submission_date``, ``late_submission``, ``late_days``.
    """
    where = []
    params: list = []
    if only_graded:
        where.append("s.grade IS NOT NULL")
    if student_id is not None:
        where.append("s.student_id = ?")
        params.append(str(student_id))
    if module_code is not None:
        where.append("a.module_code = ?")
        params.append(module_code)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    sql = (
        "SELECT s.id AS submission_id, s.assignment_id, s.student_id, "
        "       a.title, a.module_code, s.grade, s.submission_date, "
        "       s.late_submission, s.late_days "
        "FROM assignment_submissions s "
        "JOIN assignments a ON s.assignment_id = a.id "
        f"{where_sql} "
        "ORDER BY s.submission_date DESC "
        "LIMIT ?"
    )
    params.append(limit)

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("fetch_assignment_submissions failed: %s", exc)
        return []


def fetch_graded_submission_count(*, module_code: str | None = None) -> int:
    """Count graded submissions; supports a single optional module filter."""
    sql = "SELECT COUNT(*) FROM assignment_submissions s "
    params: tuple = ()
    if module_code:
        sql += "JOIN assignments a ON s.assignment_id = a.id WHERE s.grade IS NOT NULL AND a.module_code = ?"
        params = (module_code,)
    else:
        sql += "WHERE s.grade IS NOT NULL"
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            row = conn.execute(sql, params).fetchone()
            return int(row[0] or 0) if row else 0
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("fetch_graded_submission_count failed: %s", exc)
        return 0
