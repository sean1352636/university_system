"""Attendance-based exam eligibility — single source of truth.

The Exam Scheduler's Eligibility tab computed attendance % inline
(no persistence) and the Attendance / Absence subsystems didn't see
the verdict at all. This module:

1. Owns the schema (auto-creates ``exam_eligibility`` on first call).
2. Exposes ``compute_exam_eligibility`` — the canonical calculator.
   Returns a dict and (by default) upserts the row.
3. Exposes ``get_exam_eligibility`` so other GUIs can read the
   persisted verdict without recomputing.
4. Exposes ``bulk_recompute_for_exam`` for the Eligibility tab so a
   single call refreshes every enrolled student.

Publishers fire ``EVENT_ENROLMENT_CHANGED`` after a recompute (any
caller subscribed to it auto-refreshes their views).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Iterable

from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 75.0  # matches ELIGIBILITY_THRESHOLD in the Exam scheduler tab

_ATTENDED_STATUSES = ("present", "late", "excused")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

# exam_id uses 0 as a sentinel for "no specific exam" (i.e. module-level
# eligibility) so a plain UNIQUE constraint on (student, module, exam_id)
# is sufficient — SQLite doesn't allow expressions inside an inline
# UNIQUE clause, and the COALESCE sentinel is clearer than a partial
# unique index for callers that read the table directly.
_NO_EXAM_SENTINEL = 0

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS exam_eligibility (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL,
    module_code     TEXT NOT NULL,
    exam_id         INTEGER NOT NULL DEFAULT 0,
    eligible        INTEGER NOT NULL,
    attended        INTEGER,
    total_sessions  INTEGER,
    percentage      REAL,
    threshold       REAL,
    verdict         TEXT,
    computed_at     TEXT NOT NULL,
    UNIQUE(student_id, module_code, exam_id)
)
"""

_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_exam_eligibility_student "
    "ON exam_eligibility(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_exam_eligibility_exam "
    "ON exam_eligibility(exam_id)",
    "CREATE INDEX IF NOT EXISTS idx_exam_eligibility_module "
    "ON exam_eligibility(module_code)",
)


def _ensure_table(conn: sqlite3.Connection) -> None:
    """Idempotent schema bootstrap. Cheap to call repeatedly."""
    conn.executescript(_SCHEMA_SQL)
    for sql in _INDEX_SQL:
        conn.execute(sql)


# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------

def compute_exam_eligibility(
    student_id: str | int,
    module_code: str,
    *,
    exam_id: int | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    cutoff_date: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Calculate attendance % and persist the verdict.

    Returns ``{student_id, module_code, exam_id, eligible, attended,
    total_sessions, percentage, threshold, verdict}``.

    ``cutoff_date`` (YYYY-MM-DD, exclusive) lets the caller restrict
    counted sessions to those before the exam date, matching what the
    Eligibility tab already does. Defaults to "today".

    ``persist=True`` upserts the row into ``exam_eligibility`` so the
    Attendance / Absence GUIs can read the same verdict without
    recomputing.
    """
    cutoff = cutoff_date or datetime.now().strftime("%Y-%m-%d")
    out = {
        "student_id": str(student_id),
        "module_code": module_code,
        "exam_id": exam_id,
        "eligible": False,
        "attended": 0,
        "total_sessions": 0,
        "percentage": 0.0,
        "threshold": float(threshold),
        "verdict": "No data",
    }
    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN LOWER(status) IN ('present','late','excused')
                             THEN 1 ELSE 0 END) AS attended,
                    COUNT(*) AS total
                FROM attendance_records
                WHERE student_id = ? AND module_code = ? AND date < ?
                """,
                (str(student_id), module_code, cutoff),
            ).fetchone()
            if row is None:
                attended, total = 0, 0
            else:
                attended = int(row[0] or 0)
                total = int(row[1] or 0)

            pct = (100.0 * attended / total) if total else 0.0
            if not total:
                verdict = "No data"
                eligible = False
            else:
                eligible = pct >= float(threshold)
                verdict = "Eligible" if eligible else "Not Eligible"

            out.update({
                "eligible": eligible,
                "attended": attended,
                "total_sessions": total,
                "percentage": round(pct, 2),
                "verdict": verdict,
            })

            if persist:
                _ensure_table(conn)
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                stored_exam = (
                    int(exam_id) if exam_id is not None else _NO_EXAM_SENTINEL
                )
                conn.execute(
                    """
                    INSERT INTO exam_eligibility
                        (student_id, module_code, exam_id, eligible,
                         attended, total_sessions, percentage, threshold,
                         verdict, computed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(student_id, module_code, exam_id)
                    DO UPDATE SET
                        eligible       = excluded.eligible,
                        attended       = excluded.attended,
                        total_sessions = excluded.total_sessions,
                        percentage     = excluded.percentage,
                        threshold      = excluded.threshold,
                        verdict        = excluded.verdict,
                        computed_at    = excluded.computed_at
                    """,
                    (str(student_id), module_code, stored_exam,
                     1 if eligible else 0, attended, total, pct,
                     float(threshold), verdict, now),
                )
                conn.commit()
    except Exception as exc:
        logger.warning(
            "compute_exam_eligibility(%s, %s, exam_id=%s) failed: %s",
            student_id, module_code, exam_id, exc,
        )
    return out


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_exam_eligibility(
    student_id: str | int,
    module_code: str,
    *,
    exam_id: int | None = None,
) -> dict[str, Any] | None:
    """Read the persisted verdict, or None if no row exists yet."""
    try:
        with get_connection() as conn:
            tbl = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='exam_eligibility'"
            ).fetchone()
            if not tbl:
                return None
            stored_exam = int(exam_id) if exam_id is not None else _NO_EXAM_SENTINEL
            row = conn.execute(
                """
                SELECT eligible, attended, total_sessions, percentage,
                       threshold, verdict, computed_at
                FROM exam_eligibility
                WHERE student_id = ? AND module_code = ? AND exam_id = ?
                """,
                (str(student_id), module_code, stored_exam),
            ).fetchone()
            if not row:
                return None
            return {
                "student_id": str(student_id),
                "module_code": module_code,
                "exam_id": exam_id,
                "eligible": bool(row[0]),
                "attended": row[1],
                "total_sessions": row[2],
                "percentage": row[3],
                "threshold": row[4],
                "verdict": row[5],
                "computed_at": row[6],
            }
    except Exception as exc:
        logger.warning("get_exam_eligibility failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Bulk
# ---------------------------------------------------------------------------

def bulk_recompute_for_exam(
    exam_id: int,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    publish_event: bool = True,
) -> list[dict[str, Any]]:
    """Recompute eligibility for every student enrolled on ``exam_id``.

    Reads the exam's roster from ``exams.enrolled_student_ids`` (JSON
    list) and runs ``compute_exam_eligibility`` for each. Returns the
    list of result dicts.
    """
    out: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT module_code, date, enrolled_student_ids "
                "FROM exams WHERE id = ?",
                (int(exam_id),),
            ).fetchone()
        if not row:
            return out
        module_code, exam_date, raw_ids = row[0], row[1], row[2]
        student_ids = list(_parse_enrolled_ids(raw_ids))
    except Exception as exc:
        logger.warning("bulk_recompute_for_exam: lookup failed: %s", exc)
        return out

    for sid in student_ids:
        out.append(compute_exam_eligibility(
            sid, module_code,
            exam_id=int(exam_id),
            threshold=threshold,
            cutoff_date=exam_date,
            persist=True,
        ))

    if publish_event and out:
        try:
            from education_system.systems.university.interfaces.gui.academics._event_bus import (
                publish, EVENT_ENROLMENT_CHANGED,
            )
            publish(EVENT_ENROLMENT_CHANGED,
                    exam_id=int(exam_id), module_code=module_code,
                    action="eligibility_recomputed")
        except Exception:
            pass

    return out


def _parse_enrolled_ids(raw: Any) -> Iterable[str]:
    """``exams.enrolled_student_ids`` is a JSON-encoded list. Handle the
    rare bare-list case too."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    try:
        import json
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except Exception:
        pass
    # Last-ditch CSV fallback
    return [s.strip() for s in str(raw).split(",") if s.strip()]


__all__ = [
    "DEFAULT_THRESHOLD",
    "compute_exam_eligibility",
    "get_exam_eligibility",
    "bulk_recompute_for_exam",
]
