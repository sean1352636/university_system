"""Domain layer for the Daily Register (Nursery System).

The Daily Register is the per-date "who's in today" screen. It has NO table of
its own — it is a view over the existing ``attendance_records`` table and reuses
the ``attendance_report`` domain (``mark_attendance``, ``active_children``,
``STATUSES``). It lists every active child for a chosen date (left-joined to that
date's all-day register row) and lets you mark each child in or out.

Follows the 4-layer pattern: validation + aggregation + SQLite access here, CLI
in ``daily_register_cli.py``, Tk GUI in ``daily_register_views.py``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from typing import Any

from education_system.nursery_system.core.database import connect, init_db
from education_system.nursery_system.modules.domain.attendance_report import (
    attendance_report as _att,
)

logger = logging.getLogger(__name__)

FEATURE_NAME = "Daily Register"
CATEGORY = "Daily Care & Routines"

# Re-exported from the attendance_report domain so callers depend only on us.
STATUSES = _att.STATUSES
active_children = _att.active_children
ValidationError = _att.ValidationError

_SESSION = "all-day"


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for daily register")
        raise


def today() -> str:
    """Today's date as an ISO ``YYYY-MM-DD`` string."""
    return _dt.date.today().isoformat()


def register_for_date(attend_date: str) -> list[dict[str, Any]]:
    """All active children for a date, left-joined to that date's register.

    Each dict has: ``pupil_id``, ``name``, ``room``, ``status`` (``None`` when
    the child has no row yet), ``arrival_time``, ``departure_time`` and
    ``absence_reason``.
    """
    _ensure_schema()
    d = _att._check_date(attend_date, "Date")
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT p.pupil_id AS pupil_id, "
                "TRIM(p.first_name || ' ' || p.last_name) AS name, "
                "p.room AS room, a.status AS status, "
                "a.arrival_time AS arrival_time, "
                "a.departure_time AS departure_time, "
                "a.absence_reason AS absence_reason "
                "FROM pupils p "
                "LEFT JOIN attendance_records a "
                "ON a.pupil_id = p.pupil_id "
                "AND a.attend_date = ? AND a.session = ? "
                "WHERE p.status = 'active' "
                "ORDER BY p.room, p.last_name",
                (d, _SESSION),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("register_for_date(%s) failed", attend_date)
        raise
    return [dict(r) for r in rows]


def mark(pupil_id: str, attend_date: str, status: str, **kw: Any) -> None:
    """Mark one child's all-day register row for a date (thin UPSERT wrapper)."""
    kw.setdefault("session", _SESSION)
    _att.mark_attendance(pupil_id, attend_date, status, **kw)


def mark_all_present(attend_date: str) -> int:
    """Mark every active child not yet marked that date as ``present``.

    Returns the number of children newly marked.
    """
    d = _att._check_date(attend_date, "Date")
    count = 0
    for row in register_for_date(d):
        if row["status"] is None:
            mark(row["pupil_id"], d, "present", room=row["room"])
            count += 1
    logger.info("Marked %d unmarked child(ren) present on %s", count, d)
    return count


def day_summary(attend_date: str) -> dict[str, int]:
    """Counts per status for a date, plus ``not_marked`` and ``total``."""
    rows = register_for_date(attend_date)
    summary = {s: 0 for s in STATUSES}
    summary["not_marked"] = 0
    for row in rows:
        st = row["status"]
        if st in summary:
            summary[st] += 1
        else:
            summary["not_marked"] += 1
    summary["total"] = len(rows)
    return summary
