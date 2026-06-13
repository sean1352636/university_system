"""Domain layer for the Occupancy Report (Nursery System).

A computed, read-only report. It owns no table of its own — for each room it
combines the room's ``capacity`` with the live count of active ``pupils`` placed
there (matching ``pupils.room`` to ``rooms.name``) to work out occupancy, places
remaining and an occupancy percentage, plus a setting-wide roll-up and the count
of children not assigned to a known room.

Follows the 4-layer pattern: computation + SQLite access here, CLI in
``occupancy_report_cli.py``, Tk GUI in ``occupancy_report_views.py``.
"""

from __future__ import annotations

import csv
import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from education_system.nursery_system.core import paths
from education_system.nursery_system.core.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Occupancy Report"
CATEGORY = "Compliance & Reports"


@dataclass
class RoomOccupancy:
    room_id: str
    name: str
    age_group: str | None
    capacity: int
    occupied: int
    status: str

    @property
    def places_remaining(self) -> int:
        return max(self.capacity - self.occupied, 0)

    @property
    def over_capacity(self) -> int:
        return max(self.occupied - self.capacity, 0)

    @property
    def occupancy_pct(self) -> float | None:
        if self.capacity <= 0:
            return None
        return round(self.occupied / self.capacity * 100, 1)


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for occupancy report")
        raise


# ── Reads / computation ──────────────────────────────────────────────────────

def list_room_occupancy() -> list[RoomOccupancy]:
    """Per-room occupancy, ordered by age band."""
    _ensure_schema()
    try:
        with connect() as conn:
            rooms = conn.execute(
                "SELECT room_id, name, age_group, capacity, status "
                "FROM rooms ORDER BY min_age_months, name").fetchall()
            counts = dict(conn.execute(
                "SELECT room, COUNT(*) FROM pupils WHERE status = 'active' "
                "GROUP BY room").fetchall())
    except sqlite3.Error:
        logger.exception("list_room_occupancy failed")
        raise
    return [
        RoomOccupancy(
            room_id=r["room_id"], name=r["name"], age_group=r["age_group"],
            capacity=int(r["capacity"] or 0),
            occupied=int(counts.get(r["name"], 0)), status=r["status"],
        )
        for r in rooms
    ]


def unplaced_children() -> int:
    """Active children whose ``room`` doesn't match any defined room name."""
    _ensure_schema()
    try:
        with connect() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM pupils WHERE status = 'active' AND "
                "(room IS NULL OR room = '' OR room NOT IN "
                "(SELECT name FROM rooms))").fetchone()[0]
    except sqlite3.Error:
        logger.exception("unplaced_children failed")
        raise


def summary() -> dict[str, object]:
    rows = list_room_occupancy()
    capacity = sum(r.capacity for r in rows)
    occupied = sum(r.occupied for r in rows)
    full = sum(1 for r in rows if r.capacity and r.occupied >= r.capacity)
    over = sum(1 for r in rows if r.over_capacity)
    pct = round(occupied / capacity * 100, 1) if capacity else None
    return {
        "rooms": len(rows),
        "capacity": capacity,
        "occupied": occupied,
        "places_remaining": max(capacity - occupied, 0),
        "occupancy_pct": pct,
        "full_rooms": full,
        "over_capacity_rooms": over,
        "unplaced_children": unplaced_children(),
    }


# ── Export ───────────────────────────────────────────────────────────────────

def export_csv(path: str | Path | None = None) -> dict[str, object]:
    """Write the per-room occupancy report to CSV; return path + row count."""
    rows = list_room_occupancy()
    if path is None:
        paths.ensure_directories()
        path = paths.DATA_DIR / (
            f"occupancy_report_{_dt.date.today().isoformat()}.csv")
    path = Path(path)
    headers = ["room_id", "room", "age_group", "capacity", "occupied",
               "places_remaining", "occupancy_pct", "status"]
    try:
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(headers)
            for r in rows:
                w.writerow([
                    r.room_id, r.name, r.age_group or "", r.capacity, r.occupied,
                    r.places_remaining,
                    "" if r.occupancy_pct is None else r.occupancy_pct, r.status,
                ])
    except OSError as e:
        logger.exception("Could not write occupancy CSV to %s", path)
        raise OSError(f"Could not write report — {e}") from e
    return {"path": str(path), "row_count": len(rows)}
