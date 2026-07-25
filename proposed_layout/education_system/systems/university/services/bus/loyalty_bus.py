"""Unified loyalty ledger.

A single ``loyalty_ledger`` table that any venue (cinema, gym,
restaurant, shop, SU) can write to via ``add_points`` and any venue
can read via ``points_balance`` / ``tier``.

The existing per-venue points stores aren't migrated — instead
``points_balance`` *also* reads ``restaurant_customers.loyalty_points``
and SU ``points`` rows so legacy data still counts toward tier. New
earnings land in ``loyalty_ledger`` and become the canonical source.

Tier thresholds:

* Bronze   <  500
* Silver   ≥  500
* Gold     ≥ 2000
* Platinum ≥ 5000
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from education_system.systems.university.infrastructure.database.db import (
    sqlite3, get_connection,
)

logger = logging.getLogger(__name__)


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS loyalty_ledger (
    entry_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    source       TEXT NOT NULL,
    points       INTEGER NOT NULL,
    reference_id TEXT,
    description  TEXT,
    created_at   TEXT NOT NULL
)
"""

_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_loyalty_ledger_student "
    "ON loyalty_ledger(student_id)",
)


_TIER_THRESHOLDS = (
    ("Platinum", 5000),
    ("Gold",     2000),
    ("Silver",    500),
    ("Bronze",      0),
)


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_SQL)
    for sql in _INDEX_SQL:
        conn.execute(sql)


def _publish(event: str, **payload: Any) -> None:
    try:
        from education_system.systems.university.interfaces.gui.academics._event_bus import publish
        publish(event, **payload)
    except Exception as exc:
        logger.debug("loyalty publish failed: %s", exc)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

def add_points(student_id: str | int,
               *, source: str, points: int,
               reference_id: str | None = None,
               description: str | None = None) -> int | None:
    """Append a points entry to the ledger and return the new balance.

    ``points`` may be negative to redeem. Best-effort — returns
    ``None`` on any failure.
    """
    if not student_id or not points:
        return None
    sid = str(student_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_connection() as conn:
            _ensure_schema(conn)
            conn.execute(
                "INSERT INTO loyalty_ledger "
                "(student_id, source, points, reference_id, "
                " description, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (sid, source, int(points), reference_id, description, now),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("add_points(%s, %s) failed: %s", sid, points, exc)
        return None

    bal = points_balance(sid)
    _publish("loyalty.points.changed",
             student_id=sid, source=source, delta=int(points),
             balance=bal, reference_id=reference_id)
    return bal


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def points_balance(student_id: str | int) -> int:
    """Return the student's total points across the unified ledger
    plus any legacy stores (restaurant_customers, su_points)."""
    if not student_id:
        return 0
    sid = str(student_id)
    total = 0
    try:
        with get_connection() as conn:
            _ensure_schema(conn)
            row = conn.execute(
                "SELECT COALESCE(SUM(points), 0) FROM loyalty_ledger "
                "WHERE student_id = ?",
                (sid,),
            ).fetchone()
            if row:
                total += int(row[0] or 0)
            # Legacy: restaurant points
            try:
                row = conn.execute(
                    "SELECT COALESCE(SUM(loyalty_points), 0) "
                    "FROM restaurant_customers "
                    "WHERE customer_id = ? OR student_id = ?",
                    (sid, sid),
                ).fetchone()
                if row:
                    total += int(row[0] or 0)
            except Exception:
                pass
            # Legacy: SU points (table layout varies — sum points col
            # if present; tolerate missing table)
            try:
                row = conn.execute(
                    "SELECT COALESCE(SUM(points), 0) FROM su_points "
                    "WHERE student_id = ?",
                    (sid,),
                ).fetchone()
                if row:
                    total += int(row[0] or 0)
            except Exception:
                pass
    except Exception as exc:
        logger.warning("points_balance(%s) failed: %s", sid, exc)
    return total


def tier(student_id: str | int) -> str:
    """Return the student's loyalty tier from total points."""
    bal = points_balance(student_id)
    for name, threshold in _TIER_THRESHOLDS:
        if bal >= threshold:
            return name
    return "Bronze"


def list_recent(student_id: str | int,
                *, limit: int = 25) -> list[dict[str, Any]]:
    if not student_id:
        return []
    out: list[dict[str, Any]] = []
    try:
        with get_connection() as conn:
            _ensure_schema(conn)
            for r in conn.execute(
                "SELECT entry_id, source, points, reference_id, "
                "       description, created_at "
                "FROM loyalty_ledger WHERE student_id = ? "
                "ORDER BY entry_id DESC LIMIT ?",
                (str(student_id), int(limit)),
            ).fetchall():
                out.append(dict(r))
    except Exception as exc:
        logger.warning("list_recent(%s) failed: %s", student_id, exc)
    return out


__all__ = ["add_points", "points_balance", "tier", "list_recent"]
