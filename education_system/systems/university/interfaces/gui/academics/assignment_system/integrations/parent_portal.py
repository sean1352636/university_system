"""Parent portal adapter — pure data, no UI.

The CLI ``view_child_assignments`` in
``services/parent_portal/academics.py`` mixed presentation with the SQL
fetch. ``fetch_child_assignments`` exposes the same query so both the
CLI mixin and the assignment GUI share one path.
"""

from __future__ import annotations

import datetime
import logging

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


def fetch_parent_children(parent_id: int) -> list[dict]:
    """Return the children registered to ``parent_id``.

    Each row is a dict with student_id, first_name, last_name, course
    and access_level. Mirrors the projection used by
    ``parent_portal.accounts.AccountsMixin.view_children`` but without
    relying on its tuple ordering.
    """
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='parent_children'"
            )
            if not cur.fetchone():
                return []
            cur.execute(
                """
                SELECT s.student_id, s.first_name, s.last_name, s.course,
                       COALESCE(pc.access_level, 'full') AS access_level
                FROM parent_children pc
                JOIN students s ON s.student_id = pc.student_id
                WHERE pc.parent_id = ?
                ORDER BY s.last_name, s.first_name
                """,
                (parent_id,),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("fetch_parent_children failed for %s: %s", parent_id, exc)
        return []


def fetch_child_assignments(student_id: str | int) -> dict[str, list[dict]]:
    """Return upcoming / overdue / recently-completed assignments for a child.

    Returned shape:
        {
            "upcoming":  [ {id, title, due_date, module_code, module_name, status}, ... ],
            "overdue":   [ ... ],
            "completed": [ ... ],   # last 5
        }

    Tries the rich ``assignments`` + ``student_modules`` join first
    (matches what dashboards already use); falls back to the legacy
    ``student_assignments`` table that the parent portal CLI used to
    query directly.
    """
    today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out: dict[str, list[dict]] = {"upcoming": [], "overdue": [], "completed": []}

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            tables = {
                r[0]
                for r in cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }

            if {"assignments", "student_modules"}.issubset(tables):
                cur.execute(
                    """
                    SELECT a.id, a.title, a.description, a.due_date,
                           a.module_code, COALESCE(m.module_name, a.module_code) AS module_name,
                           CASE WHEN s.id IS NOT NULL THEN 'submitted' ELSE 'pending' END AS status
                    FROM assignments a
                    JOIN student_modules sm ON sm.module_code = a.module_code
                    LEFT JOIN modules m ON m.module_code = a.module_code
                    LEFT JOIN assignment_submissions s
                           ON s.assignment_id = a.id AND s.student_id = sm.student_id
                    WHERE sm.student_id = ? AND a.is_active = 1
                    ORDER BY a.due_date
                    """,
                    (str(student_id),),
                )
                for r in cur.fetchall():
                    item = dict(r)
                    due = item.get("due_date") or ""
                    if item["status"] == "submitted":
                        out["completed"].append(item)
                    elif due and due < today:
                        out["overdue"].append(item)
                    else:
                        out["upcoming"].append(item)
                out["completed"] = out["completed"][-5:]
                return out

            if "student_assignments" in tables:
                cur.execute(
                    """
                    SELECT sa.id, sa.title, sa.description, sa.due_date,
                           m.module_code,
                           COALESCE(m.module_name, m.module_code) AS module_name,
                           sa.status
                    FROM student_assignments sa
                    JOIN modules m ON sa.module_code = m.module_code
                    WHERE sa.student_id = ?
                    ORDER BY sa.due_date
                    """,
                    (str(student_id),),
                )
                for r in cur.fetchall():
                    item = dict(r)
                    if item["status"] == "completed":
                        out["completed"].append(item)
                    elif (item.get("due_date") or "") < today:
                        out["overdue"].append(item)
                    else:
                        out["upcoming"].append(item)
                out["completed"] = out["completed"][-5:]
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("fetch_child_assignments failed for %s: %s", student_id, exc)
    return out
