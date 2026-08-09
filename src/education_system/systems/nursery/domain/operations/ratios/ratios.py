"""Domain layer for Staff : Child Ratios (Nursery System).

A computed EYFS compliance board — it owns no table of its own. For each room it
combines three live sources:

* the room's required ratio (``rooms.staff_ratio``, e.g. ``1:3``),
* the children in that room (active ``pupils`` whose ``room`` matches),
* the staff deployed there (``staff`` whose ``room`` matches and who are still
  employed),

and works out the required number of adults, whether the room currently meets
ratio, and any shortfall. The only write it offers is setting a room's required
ratio (which lives on the ``rooms`` row).

Follows the 4-layer pattern: computation + SQLite access here, CLI in
``ratios_cli.py``, Tk GUI in ``ratios_views.py``.
"""

from __future__ import annotations

import logging
import math
import re
import sqlite3
from dataclasses import dataclass

from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Staff : Child Ratios"
CATEGORY = "Staff & Ratios"

_RATIO_RE = re.compile(r"^\s*(\d+)\s*:\s*(\d+)\s*$")


class ValidationError(ValueError):
    """Raised for invalid ratio input."""


@dataclass
class RoomRatio:
    room_id: str
    name: str
    age_group: str | None
    staff_ratio: str | None
    children: int
    staff: int
    required_staff: int | None  # None when no ratio is set
    status: str  # room open/closed

    @property
    def compliant(self) -> bool | None:
        if self.required_staff is None:
            return None
        return self.staff >= self.required_staff

    @property
    def shortfall(self) -> int:
        if self.required_staff is None:
            return 0
        return max(self.required_staff - self.staff, 0)

    @property
    def children_per_adult(self) -> float | None:
        if self.staff <= 0:
            return None
        return round(self.children / self.staff, 1)


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for ratios")
        raise


def parse_ratio(ratio: str | None) -> int | None:
    """Return children-per-adult denominator from an ``a:b`` ratio, or None."""
    if not ratio:
        return None
    m = _RATIO_RE.match(ratio)
    if not m:
        return None
    adults, children = int(m.group(1)), int(m.group(2))
    if adults <= 0:
        return None
    # children per adult, e.g. "1:3" -> 3, "2:6" -> 3
    return children // adults if children % adults == 0 else math.ceil(children / adults)


def required_staff_for(children: int, ratio: str | None) -> int | None:
    denom = parse_ratio(ratio)
    if denom is None or denom <= 0:
        return None
    if children <= 0:
        return 0
    return math.ceil(children / denom)


# ── Reads / computation ──────────────────────────────────────────────────────

def list_room_ratios() -> list[RoomRatio]:
    """Per-room ratio board, ordered by age band."""
    _ensure_schema()
    try:
        with connect() as conn:
            rooms = conn.execute(
                "SELECT room_id, name, age_group, staff_ratio, status, "
                "min_age_months FROM rooms ORDER BY min_age_months, name"
            ).fetchall()
            child_counts = dict(conn.execute(
                "SELECT room, COUNT(*) FROM pupils WHERE status = 'active' "
                "GROUP BY room").fetchall())
            staff_counts = dict(conn.execute(
                "SELECT room, COUNT(*) FROM staff "
                "WHERE end_date IS NULL OR end_date = '' GROUP BY room").fetchall())
    except sqlite3.Error:
        logger.exception("list_room_ratios failed")
        raise

    out: list[RoomRatio] = []
    for r in rooms:
        children = int(child_counts.get(r["name"], 0))
        staff = int(staff_counts.get(r["name"], 0))
        out.append(RoomRatio(
            room_id=r["room_id"], name=r["name"], age_group=r["age_group"],
            staff_ratio=r["staff_ratio"], children=children, staff=staff,
            required_staff=required_staff_for(children, r["staff_ratio"]),
            status=r["status"],
        ))
    return out


def list_unplaced_children() -> int:
    """Active children whose ``room`` doesn't match any defined room name."""
    _ensure_schema()
    try:
        with connect() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM pupils WHERE status = 'active' AND "
                "(room IS NULL OR room = '' OR room NOT IN "
                "(SELECT name FROM rooms))").fetchone()[0]
    except sqlite3.Error:
        logger.exception("list_unplaced_children failed")
        raise


def summary() -> dict[str, int]:
    rows = list_room_ratios()
    breaches = sum(1 for r in rows if r.compliant is False)
    no_ratio = sum(1 for r in rows if r.required_staff is None)
    return {
        "rooms": len(rows),
        "children": sum(r.children for r in rows),
        "staff": sum(r.staff for r in rows),
        "breaches": breaches,
        "no_ratio_set": no_ratio,
        "unplaced_children": list_unplaced_children(),
    }


# ── Write (the one management action) ────────────────────────────────────────

def set_room_ratio(room_id: str, ratio: str) -> RoomRatio:
    """Set a room's required staff:child ratio (``a:b``)."""
    _ensure_schema()
    ratio = (ratio or "").strip()
    if not _RATIO_RE.match(ratio):
        raise ValidationError("Ratio must look like '1:3' (adults:children)")
    try:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE rooms SET staff_ratio = ? WHERE room_id = ?",
                (ratio, room_id))
            if cur.rowcount == 0:
                raise ValidationError(f"No room with id {room_id}")
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("Database error setting ratio for room %s", room_id)
        raise
    for rr in list_room_ratios():
        if rr.room_id == room_id:
            logger.info("Set ratio for room %s -> %s", room_id, ratio)
            return rr
    raise ValidationError(f"No room with id {room_id}")
