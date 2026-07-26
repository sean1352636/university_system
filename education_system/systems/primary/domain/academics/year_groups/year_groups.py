"""Year-group configuration data layer for the Primary School System.

One row per UK secondary year (7–11). Captures the head of year, an
intended cohort capacity, and free-form notes. Live pupil counts are
derived on demand from the ``pupils`` table.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS year_groups (
    year_group     TEXT PRIMARY KEY,
    head_of_year   TEXT,
    capacity       INTEGER,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
);
"""


@dataclass
class YearGroup:
    year_group: str
    head_of_year: str | None
    capacity: int | None
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise year_groups table")
        raise
    logger.info("Secondary year_groups table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> YearGroup:
    return YearGroup(
        year_group=r["year_group"],
        head_of_year=r["head_of_year"],
        capacity=r["capacity"],
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _validate(data: dict[str, Any], *, require_year: bool = True
              ) -> dict[str, Any]:
    out: dict[str, Any] = {}
    yg = (data.get("year_group") or "").strip()
    if require_year:
        if not yg:
            raise ValidationError("Year group is required")
        if yg not in YEAR_GROUPS:
            raise ValidationError(
                f"Year group must be one of {', '.join(YEAR_GROUPS)}")
        out["year_group"] = yg
    out["head_of_year"] = (data.get("head_of_year") or "").strip() or None
    cap_raw = data.get("capacity")
    if cap_raw in (None, ""):
        out["capacity"] = None
    else:
        try:
            cap = int(cap_raw)
        except (TypeError, ValueError):
            raise ValidationError("Capacity must be a whole number") from None
        if cap < 0 or cap > 1000:
            raise ValidationError("Capacity must be between 0 and 1000")
        out["capacity"] = cap
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def upsert(data: dict[str, Any]) -> YearGroup:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            existed = conn.execute(
                "SELECT 1 FROM year_groups WHERE year_group = ?",
                (payload["year_group"],),
            ).fetchone()
            if existed:
                conn.execute(
                    """UPDATE year_groups SET
                           head_of_year = ?, capacity = ?, notes = ?,
                           updated_at = datetime('now')
                       WHERE year_group = ?""",
                    (payload["head_of_year"], payload["capacity"],
                     payload["notes"], payload["year_group"]),
                )
            else:
                conn.execute(
                    """INSERT INTO year_groups
                           (year_group, head_of_year, capacity, notes)
                       VALUES (?, ?, ?, ?)""",
                    (payload["year_group"], payload["head_of_year"],
                     payload["capacity"], payload["notes"]),
                )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to upsert year group %s",
                         payload["year_group"])
        raise
    rec = get(payload["year_group"])
    assert rec is not None
    logger.info("%s year group %s (head=%s, cap=%s)",
                "Updated" if existed else "Created",
                rec.year_group, rec.head_of_year, rec.capacity)
    return rec


def get(year_group: str) -> YearGroup | None:
    init_db()
    yg = (year_group or "").strip()
    if not yg:
        return None
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM year_groups WHERE year_group = ?", (yg,)
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", yg)
        raise
    return _row(r) if r else None


def list_all() -> list[YearGroup]:
    """Return one entry per UK year (7–11) — gaps filled with defaults."""
    init_db()
    try:
        with _connect() as conn:
            rows = {r["year_group"]: _row(r)
                    for r in conn.execute(
                        "SELECT * FROM year_groups").fetchall()}
    except sqlite3.Error:
        logger.exception("list_all year_groups failed")
        raise
    out: list[YearGroup] = []
    for yg in YEAR_GROUPS:
        out.append(rows.get(
            yg, YearGroup(year_group=yg, head_of_year=None,
                          capacity=None, notes=None)))
    return out


def pupil_counts() -> dict[str, int]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT year_group, COUNT(*) AS n FROM pupils "
                "GROUP BY year_group").fetchall()
    except sqlite3.Error:
        logger.exception("pupil_counts failed")
        raise
    counts = {yg: 0 for yg in YEAR_GROUPS}
    for r in rows:
        if r["year_group"] in counts:
            counts[r["year_group"]] = r["n"]
    return counts


def delete(year_group: str) -> bool:
    init_db()
    yg = (year_group or "").strip()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM year_groups WHERE year_group = ?", (yg,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("delete year_group %s failed", yg)
        raise
    if deleted:
        logger.info("Cleared year-group config for %s", yg)
    return deleted
