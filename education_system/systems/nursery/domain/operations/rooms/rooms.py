"""Domain layer for Rooms & Age Groups (Nursery System).

Owns the ``rooms`` table of the shared nursery DB
(``nursery_system/data/nursery.db`` — see ``core/database.py``). Each room is
an age band with an EYFS staff:child ratio and a capacity; live occupancy is
derived by matching the children's free-text ``pupils.room`` against the room
``name``.

Follows the 4-layer pattern used across the other systems: validation +
SQLite access here, CLI in ``rooms_cli.py``, Tk GUI in ``rooms_views.py``.

Every public function initialises the schema (idempotent), logs at the
appropriate level and raises :class:`ValidationError` for bad form input so
the interface layers can show a friendly message.
"""

from __future__ import annotations

import logging
import random
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Rooms & Age Groups"
CATEGORY = "Children & Admissions"

ID_PREFIX = "NRM"
ID_DIGITS = 3

STATUSES = ("open", "closed")

# The EYFS statutory staff:child ratios by age band — offered as defaults in
# the UI; the field accepts free text so a setting can record its own ratio.
RATIO_OPTIONS = ("", "1:3", "1:4", "1:8", "1:13")


class ValidationError(ValueError):
    """Raised for invalid room-form input."""


@dataclass
class Room:
    room_id: str
    name: str
    age_group: str | None
    min_age_months: int | None
    max_age_months: int | None
    capacity: int
    staff_ratio: str | None
    room_leader: str | None
    location: str | None
    notes: str | None
    status: str
    # Joined / derived, not stored columns.
    room_leader_name: str | None = None
    occupancy: int = 0

    @property
    def places_left(self) -> int:
        return max(self.capacity - self.occupancy, 0)

    @property
    def is_full(self) -> bool:
        return self.capacity > 0 and self.occupancy >= self.capacity


def _ensure_schema() -> None:
    """Create (and demo-seed) the nursery tables if needed. Idempotent."""
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for rooms")
        raise


# Read query that joins the room leader's name and a live occupancy count
# (active children whose room name matches). Kept in one place so list/get
# present the same shape.
_SELECT = """
SELECT r.*,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS room_leader_name,
       (SELECT COUNT(*) FROM pupils p
         WHERE p.room = r.name AND p.status = 'active') AS occupancy
FROM rooms r
LEFT JOIN staff s ON s.staff_id = r.room_leader
"""


def _row(r: sqlite3.Row) -> Room:
    keys = r.keys()
    return Room(
        room_id=r["room_id"],
        name=r["name"],
        age_group=r["age_group"],
        min_age_months=r["min_age_months"],
        max_age_months=r["max_age_months"],
        capacity=r["capacity"],
        staff_ratio=r["staff_ratio"],
        room_leader=r["room_leader"],
        location=r["location"],
        notes=r["notes"],
        status=r["status"],
        room_leader_name=r["room_leader_name"] if "room_leader_name" in keys else None,
        occupancy=r["occupancy"] if "occupancy" in keys else 0,
    )


# ── Validation ───────────────────────────────────────────────────────────────

def _require(value: str | None, label: str) -> str:
    if not value or not str(value).strip():
        raise ValidationError(f"{label} is required")
    return str(value).strip()


def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


def _opt_int(value: Any, label: str) -> int | None:
    raw = str(value if value is not None else "").strip()
    if not raw:
        return None
    try:
        n = int(raw)
    except ValueError as e:
        raise ValidationError(f"{label} must be a whole number") from e
    if n < 0:
        raise ValidationError(f"{label} cannot be negative")
    return n


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["name"] = _require(data.get("name"), "Room name")
    out["age_group"] = _opt(data.get("age_group"))

    out["min_age_months"] = _opt_int(data.get("min_age_months"), "Minimum age (months)")
    out["max_age_months"] = _opt_int(data.get("max_age_months"), "Maximum age (months)")
    if (out["min_age_months"] is not None and out["max_age_months"] is not None
            and out["min_age_months"] > out["max_age_months"]):
        raise ValidationError("Minimum age cannot be greater than maximum age")

    cap = _opt_int(data.get("capacity"), "Capacity")
    out["capacity"] = cap if cap is not None else 0

    out["staff_ratio"] = _opt(data.get("staff_ratio"))
    out["room_leader"] = _opt(data.get("room_leader"))
    out["location"] = _opt(data.get("location"))
    out["notes"] = _opt(data.get("notes"))

    status = (data.get("status") or "open").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_room_id() -> str:
    """Allocate a unique ``NRM###`` id, widening past the demo range if full."""
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {
                r[0] for r in conn.execute("SELECT room_id FROM rooms").fetchall()
            }
    except sqlite3.Error:
        logger.exception("Could not read existing room ids")
        raise

    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"

    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        rid = f"{ID_PREFIX}{n}"
        if rid not in existing:
            logger.info("Allocated room id %s after sequential range full", rid)
            return rid
    logger.error("Exhausted attempts allocating a unique room id")
    raise RuntimeError("Could not allocate a unique room id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_rooms(*, include_closed: bool = True) -> list[Room]:
    _ensure_schema()
    sql = _SELECT
    params: tuple[Any, ...] = ()
    if not include_closed:
        sql += " WHERE r.status = ?"
        params = ("open",)
    sql += " ORDER BY r.min_age_months, r.name"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_rooms failed")
        raise
    logger.debug("list_rooms(include_closed=%s) -> %d row(s)",
                 include_closed, len(rows))
    return [_row(r) for r in rows]


def get_room(room_id: str) -> Room | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE r.room_id = ?", (room_id,)
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_room(%s) failed", room_id)
        raise
    if row is None:
        logger.debug("get_room(%s) -> miss", room_id)
        return None
    return _row(row)


def list_room_choices(*, open_only: bool = False) -> list[str]:
    """Return room names for pickers in admissions / enrolment forms."""
    return [r.name for r in list_rooms(include_closed=not open_only)]


def list_leader_choices() -> list[tuple[str, str]]:
    """Return ``(staff_id, "Name (id)")`` pairs for room-leader pickers."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name FROM staff "
                "ORDER BY last_name, first_name"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_leader_choices failed")
        raise
    return [
        (r["staff_id"], f"{r['first_name']} {r['last_name']} ({r['staff_id']})")
        for r in rows
    ]


# ── Writes ───────────────────────────────────────────────────────────────────

def create_room(data: dict[str, Any]) -> Room:
    _ensure_schema()
    logger.debug("create_room called with fields: %s",
                 sorted(k for k, v in data.items() if v not in (None, "")))
    payload = _validate(data)
    rid = generate_room_id()
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO rooms (
                    room_id, name, age_group, min_age_months, max_age_months,
                    capacity, staff_ratio, room_leader, location, notes, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rid, payload["name"], payload["age_group"],
                 payload["min_age_months"], payload["max_age_months"],
                 payload["capacity"], payload["staff_ratio"],
                 payload["room_leader"], payload["location"],
                 payload["notes"], payload["status"]),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        logger.exception("INSERT failed for new room id=%s", rid)
        raise ValidationError(
            f"Could not create room — a room named '{payload['name']}' may "
            f"already exist ({e})") from e
    except sqlite3.Error:
        logger.exception("Database error creating room id=%s", rid)
        raise
    room = get_room(rid)
    assert room is not None
    logger.info("Created room %s (%s, capacity %d)",
                room.room_id, room.name, room.capacity)
    return room


def update_room(room_id: str, data: dict[str, Any]) -> Room:
    _ensure_schema()
    logger.debug("update_room(%s) called", room_id)
    payload = _validate(data)
    try:
        with connect() as conn:
            cur = conn.execute(
                """
                UPDATE rooms SET
                    name = ?, age_group = ?, min_age_months = ?,
                    max_age_months = ?, capacity = ?, staff_ratio = ?,
                    room_leader = ?, location = ?, notes = ?, status = ?
                WHERE room_id = ?
                """,
                (payload["name"], payload["age_group"],
                 payload["min_age_months"], payload["max_age_months"],
                 payload["capacity"], payload["staff_ratio"],
                 payload["room_leader"], payload["location"],
                 payload["notes"], payload["status"], room_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No room with id {room_id}")
            conn.commit()
    except sqlite3.IntegrityError as e:
        logger.exception("UPDATE failed for room id=%s", room_id)
        raise ValidationError(f"Could not update room — {e}") from e
    except sqlite3.Error:
        logger.exception("Database error updating room id=%s", room_id)
        raise
    room = get_room(room_id)
    assert room is not None
    logger.info("Updated room %s (%s)", room_id, room.name)
    return room


def delete_room(room_id: str) -> bool:
    _ensure_schema()
    snapshot = get_room(room_id)
    if snapshot is not None and snapshot.occupancy > 0:
        raise ValidationError(
            f"Cannot delete '{snapshot.name}' — {snapshot.occupancy} child(ren) "
            "are assigned to it. Move them to another room first, or close the "
            "room instead.")
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM rooms WHERE room_id = ?", (room_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting room id=%s", room_id)
        raise
    if deleted:
        who = snapshot.name if snapshot else "(no snapshot — race?)"
        logger.info("Deleted room %s (%s)", room_id, who)
    else:
        logger.warning("delete_room called for unknown id %s", room_id)
    return deleted


def set_status(room_id: str, status: str) -> Room:
    """Open or close a room without re-validating the whole record."""
    _ensure_schema()
    status = (status or "").strip().lower()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    try:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE rooms SET status = ? WHERE room_id = ?",
                (status, room_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No room with id {room_id}")
            conn.commit()
    except sqlite3.Error:
        logger.exception("Database error setting status for room id=%s", room_id)
        raise
    room = get_room(room_id)
    assert room is not None
    logger.info("Set room %s status -> %s", room_id, status)
    return room
