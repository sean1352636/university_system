"""Enrichment activities and clubs for the Secondary School System.

Two tables:

* ``clubs``             — one row per club. Includes when it meets,
                          the leader, the room, capacity, the year
                          groups eligible (comma-separated subset of
                          YEAR_GROUPS — empty means all years), and an
                          ``is_active`` soft-delete.
* ``club_memberships``  — one row per (club, pupil) pairing. Holds
                          joined_date and a status workflow.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

CLUB_CATEGORIES: tuple[str, ...] = (
    "Sport", "Arts", "Academic", "STEM", "Service", "Music",
    "Drama", "Other")
DEFAULT_CATEGORY: str = "Other"

DAYS_OF_WEEK: tuple[str, ...] = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat")

MEMBERSHIP_STATUSES: tuple[str, ...] = (
    "Active", "Left", "Suspended", "Waitlisted")
DEFAULT_MEMBERSHIP_STATUS: str = "Active"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS clubs (
    club_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL UNIQUE,
    category         TEXT NOT NULL DEFAULT 'Other',
    description      TEXT,
    day_of_week      TEXT,
    start_time       TEXT,
    end_time         TEXT,
    room             TEXT,
    leader           TEXT,
    max_capacity     INTEGER,
    eligible_years   TEXT,
    is_active        INTEGER NOT NULL DEFAULT 1,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS club_memberships (
    membership_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id          INTEGER NOT NULL,
    pupil_id         TEXT NOT NULL,
    joined_date      TEXT NOT NULL DEFAULT (date('now')),
    status           TEXT NOT NULL DEFAULT 'Active',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    UNIQUE (club_id, pupil_id),
    FOREIGN KEY (club_id) REFERENCES clubs(club_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_clubs_active ON clubs(is_active);
CREATE INDEX IF NOT EXISTS idx_clubmem_pupil ON club_memberships(pupil_id);
"""


@dataclass
class Club:
    club_id: int
    name: str
    category: str
    description: str | None
    day_of_week: str | None
    start_time: str | None
    end_time: str | None
    room: str | None
    leader: str | None
    max_capacity: int | None
    eligible_years: str | None
    is_active: bool
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def eligible_year_set(self) -> set[str]:
        if not self.eligible_years:
            return set(YEAR_GROUPS)
        return {y.strip() for y in self.eligible_years.split(",")
                if y.strip()}


@dataclass
class ClubMembership:
    membership_id: int
    club_id: int
    pupil_id: str
    joined_date: str
    status: str
    notes: str | None
    club_name: str | None = None
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
        logger.exception("Failed to initialise clubs tables")
        raise
    logger.info("Secondary clubs tables ready")
    _DB_READY = True


def _row_club(r: sqlite3.Row) -> Club:
    return Club(
        club_id=r["club_id"], name=r["name"], category=r["category"],
        description=r["description"], day_of_week=r["day_of_week"],
        start_time=r["start_time"], end_time=r["end_time"],
        room=r["room"], leader=r["leader"],
        max_capacity=r["max_capacity"],
        eligible_years=r["eligible_years"],
        is_active=bool(r["is_active"]), notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_membership(r: sqlite3.Row) -> ClubMembership:
    keys = r.keys()
    return ClubMembership(
        membership_id=r["membership_id"], club_id=r["club_id"],
        pupil_id=r["pupil_id"], joined_date=r["joined_date"],
        status=r["status"], notes=r["notes"],
        club_name=r["club_name"] if "club_name" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_time(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    if not _TIME_RE.match(s):
        raise ValidationError(f"{label} must be HH:MM (24-hour)")
    return s


def _validate_date(value: Any, label: str = "Date") -> str:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_club(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = (data.get("name") or "").strip()
    if not name:
        raise ValidationError("Club name is required")
    if len(name) > 64:
        raise ValidationError("Club name must be 64 characters or fewer")
    out["name"] = name

    cat = (data.get("category") or DEFAULT_CATEGORY).strip()
    if cat not in CLUB_CATEGORIES:
        raise ValidationError(
            f"Category must be one of {', '.join(CLUB_CATEGORIES)}")
    out["category"] = cat

    out["description"] = (data.get("description") or "").strip() or None
    day = (data.get("day_of_week") or "").strip()
    if day in ("Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday"):
        day = day[:3]
    if day and day not in DAYS_OF_WEEK:
        raise ValidationError(
            f"Day must be one of {', '.join(DAYS_OF_WEEK)}")
    out["day_of_week"] = day or None

    out["start_time"] = _validate_time(data.get("start_time"),
                                         "Start time")
    out["end_time"]   = _validate_time(data.get("end_time"), "End time")
    if (out["start_time"] and out["end_time"]
            and out["end_time"] <= out["start_time"]):
        raise ValidationError("End time must be after start time")

    out["room"]   = (data.get("room") or "").strip() or None
    out["leader"] = (data.get("leader") or "").strip() or None

    cap = data.get("max_capacity")
    if cap in (None, "") or (isinstance(cap, str) and not cap.strip()):
        out["max_capacity"] = None
    else:
        try:
            n = int(cap)
        except (TypeError, ValueError):
            raise ValidationError(
                "Max capacity must be a whole number") from None
        if n < 1 or n > 1000:
            raise ValidationError(
                "Max capacity must be between 1 and 1000")
        out["max_capacity"] = n

    yrs = (data.get("eligible_years") or "").strip()
    if yrs:
        parts = [p.strip() for p in yrs.split(",") if p.strip()]
        bad = [p for p in parts if p not in YEAR_GROUPS]
        if bad:
            raise ValidationError(
                f"Eligible years contains invalid value(s) {bad} — "
                f"must each be one of {', '.join(YEAR_GROUPS)}")
        out["eligible_years"] = ",".join(parts)
    else:
        out["eligible_years"] = None

    is_active = data.get("is_active")
    out["is_active"] = True if is_active is None else bool(is_active)
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


# ── Club CRUD ─────────────────────────────────────────────────────

def create_club(data: dict[str, Any]) -> Club:
    init_db()
    payload = _validate_club(data)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT club_id FROM clubs WHERE name = ?",
                (payload["name"],)).fetchone()
            if dup:
                raise ValidationError(
                    f"A club named {payload['name']!r} already exists")
            cur = conn.execute(
                """INSERT INTO clubs
                       (name, category, description, day_of_week,
                        start_time, end_time, room, leader,
                        max_capacity, eligible_years, is_active, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["name"], payload["category"],
                 payload["description"], payload["day_of_week"],
                 payload["start_time"], payload["end_time"],
                 payload["room"], payload["leader"],
                 payload["max_capacity"], payload["eligible_years"],
                 1 if payload["is_active"] else 0, payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create club")
        raise
    rec = get_club(new_id)
    assert rec is not None
    logger.info("Created club #%d %r (%s, %s, cap=%s, active=%s)",
                rec.club_id, rec.name, rec.category,
                rec.day_of_week or "-",
                rec.max_capacity, rec.is_active)
    return rec


def get_club(club_id: int) -> Club | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM clubs WHERE club_id = ?", (club_id,)
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_club(%s) failed", club_id)
        raise
    return _row_club(r) if r else None


def list_clubs(*, active_only: bool = False,
               category: str | None = None,
               day_of_week: str | None = None) -> list[Club]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if active_only:
        where.append("is_active = 1")
    if category:
        if category not in CLUB_CATEGORIES:
            raise ValidationError(
                f"Category filter must be one of "
                f"{', '.join(CLUB_CATEGORIES)}")
        where.append("category = ?")
        params.append(category)
    if day_of_week:
        day = day_of_week.strip()
        if day in ("Monday", "Tuesday", "Wednesday", "Thursday",
                    "Friday", "Saturday"):
            day = day[:3]
        if day not in DAYS_OF_WEEK:
            raise ValidationError(
                f"Day filter must be one of {', '.join(DAYS_OF_WEEK)}")
        where.append("day_of_week = ?")
        params.append(day)
    sql = "SELECT * FROM clubs"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY name COLLATE NOCASE"
    try:
        with _connect() as conn:
            return [_row_club(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_clubs failed")
        raise


def update_club(club_id: int, data: dict[str, Any]) -> Club:
    init_db()
    existing = get_club(club_id)
    if existing is None:
        raise ValidationError(f"No club #{club_id}")
    merged = {
        "name":          data.get("name", existing.name),
        "category":      data.get("category", existing.category),
        "description":   data.get("description", existing.description),
        "day_of_week":   data.get("day_of_week", existing.day_of_week),
        "start_time":    data.get("start_time", existing.start_time),
        "end_time":      data.get("end_time", existing.end_time),
        "room":          data.get("room", existing.room),
        "leader":        data.get("leader", existing.leader),
        "max_capacity":  data.get("max_capacity", existing.max_capacity),
        "eligible_years": data.get("eligible_years",
                                     existing.eligible_years),
        "is_active":     data.get("is_active", existing.is_active),
        "notes":         data.get("notes", existing.notes),
    }
    payload = _validate_club(merged)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT club_id FROM clubs WHERE name = ? AND club_id <> ?",
                (payload["name"], club_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A club named {payload['name']!r} already exists")
            conn.execute(
                """UPDATE clubs SET
                       name = ?, category = ?, description = ?,
                       day_of_week = ?, start_time = ?, end_time = ?,
                       room = ?, leader = ?, max_capacity = ?,
                       eligible_years = ?, is_active = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE club_id = ?""",
                (payload["name"], payload["category"],
                 payload["description"], payload["day_of_week"],
                 payload["start_time"], payload["end_time"],
                 payload["room"], payload["leader"],
                 payload["max_capacity"], payload["eligible_years"],
                 1 if payload["is_active"] else 0, payload["notes"],
                 club_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update club #%d", club_id)
        raise
    rec = get_club(club_id)
    assert rec is not None
    logger.info("Updated club #%d %s (active=%s)",
                rec.club_id, rec.name, rec.is_active)
    return rec


def toggle_active(club_id: int) -> Club:
    existing = get_club(club_id)
    if existing is None:
        raise ValidationError(f"No club #{club_id}")
    return update_club(club_id, {"is_active": not existing.is_active})


def delete_club(club_id: int) -> bool:
    init_db()
    existing = get_club(club_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            cur = conn.execute(
                "DELETE FROM clubs WHERE club_id = ?", (club_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete club #%d", club_id)
        raise
    if deleted:
        logger.info("Deleted club #%d %s (cascade: memberships)",
                    club_id, existing.name)
    return deleted


# ── Memberships ──────────────────────────────────────────────────

def _active_membership_count(club_id: int) -> int:
    with _connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM club_memberships "
            "WHERE club_id = ? AND status = 'Active'",
            (club_id,),
        ).fetchone()[0]


def join_club(club_id: int, pupil_id: str, *,
              joined_date: str | None = None,
              notes: str | None = None,
              force_waitlist: bool = False) -> ClubMembership:
    """Insert / re-activate a pupil's membership.

    If the club is over capacity, returns the row with status
    'Waitlisted' rather than Active (unless capacity is unset).
    Use ``force_waitlist=True`` to skip the eligibility check (used by
    edit flows).
    """
    init_db()
    club = get_club(club_id)
    if club is None:
        raise ValidationError(f"No club #{club_id}")
    if not club.is_active:
        raise ValidationError(
            f"Club {club.name!r} is inactive — re-activate first")
    pupil_id = (pupil_id or "").strip()
    if not pupil_id:
        raise ValidationError("Pupil ID is required")
    # Pupil & eligibility checks
    from education_system.secondarysch_system.modules.domain.pupils.pupils import (
        pupils as pupils_data,
    )
    pupil = pupils_data.get_pupil(pupil_id)
    if pupil is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    if not force_waitlist and pupil.year_group not in club.eligible_year_set:
        raise ValidationError(
            f"Pupil {pupil_id} (Year {pupil.year_group}) is not eligible "
            f"— club accepts years "
            f"{', '.join(sorted(club.eligible_year_set))}")
    jdate = _validate_date(joined_date or _dt.date.today().isoformat(),
                            "Joined date")

    # Decide status based on capacity
    target_status = DEFAULT_MEMBERSHIP_STATUS
    if club.max_capacity is not None:
        with _connect() as conn:
            already = conn.execute(
                "SELECT membership_id, status FROM club_memberships "
                "WHERE club_id = ? AND pupil_id = ?",
                (club_id, pupil_id),
            ).fetchone()
        active_n = _active_membership_count(club_id)
        if active_n >= club.max_capacity and (
                not already or already["status"] != "Active"):
            target_status = "Waitlisted"

    try:
        with _connect() as conn:
            existing = conn.execute(
                "SELECT membership_id FROM club_memberships "
                "WHERE club_id = ? AND pupil_id = ?",
                (club_id, pupil_id),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE club_memberships SET status = ?, "
                    "joined_date = ?, notes = ?, "
                    "updated_at = datetime('now') "
                    "WHERE membership_id = ?",
                    (target_status, jdate, notes or None,
                     existing["membership_id"]),
                )
                mid = existing["membership_id"]
                action = "re-joined"
            else:
                cur = conn.execute(
                    "INSERT INTO club_memberships "
                    "(club_id, pupil_id, joined_date, status, notes) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (club_id, pupil_id, jdate, target_status,
                     notes or None),
                )
                mid = cur.lastrowid
                action = "joined"
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to join_club(%d, %s)", club_id, pupil_id)
        raise
    logger.info("Membership %s: club=#%d pupil=%s status=%s",
                action, club_id, pupil_id, target_status)
    rec = get_membership(mid)
    assert rec is not None
    return rec


def get_membership(membership_id: int) -> ClubMembership | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT m.*, c.name AS club_name
                   FROM club_memberships m
                   LEFT JOIN clubs c ON c.club_id = m.club_id
                   WHERE m.membership_id = ?""",
                (membership_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_membership(%s) failed", membership_id)
        raise
    return _row_membership(r) if r else None


def list_memberships(club_id: int,
                     *, status: str | None = None
                     ) -> list[ClubMembership]:
    init_db()
    where = ["m.club_id = ?"]
    params: list[Any] = [club_id]
    if status:
        if status not in MEMBERSHIP_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(MEMBERSHIP_STATUSES)}")
        where.append("m.status = ?")
        params.append(status)
    sql = ("""SELECT m.*, c.name AS club_name
              FROM club_memberships m
              LEFT JOIN clubs c ON c.club_id = m.club_id
              WHERE """ + " AND ".join(where)
           + " ORDER BY m.status, m.pupil_id")
    try:
        with _connect() as conn:
            return [_row_membership(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_memberships(%s) failed", club_id)
        raise


def memberships_for_pupil(pupil_id: str,
                           *, status: str | None = None
                           ) -> list[ClubMembership]:
    init_db()
    pid = (pupil_id or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    where = ["m.pupil_id = ?"]
    params: list[Any] = [pid]
    if status:
        if status not in MEMBERSHIP_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(MEMBERSHIP_STATUSES)}")
        where.append("m.status = ?")
        params.append(status)
    sql = ("""SELECT m.*, c.name AS club_name
              FROM club_memberships m
              LEFT JOIN clubs c ON c.club_id = m.club_id
              WHERE """ + " AND ".join(where)
           + " ORDER BY c.name COLLATE NOCASE")
    try:
        with _connect() as conn:
            return [_row_membership(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("memberships_for_pupil(%s) failed", pupil_id)
        raise


def set_membership_status(membership_id: int,
                           status: str) -> ClubMembership:
    init_db()
    if status not in MEMBERSHIP_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(MEMBERSHIP_STATUSES)}")
    existing = get_membership(membership_id)
    if existing is None:
        raise ValidationError(f"No membership #{membership_id}")
    try:
        with _connect() as conn:
            # Capacity check on Active promotion
            if status == "Active" and existing.status != "Active":
                club = get_club(existing.club_id)
                if club and club.max_capacity is not None:
                    n = _active_membership_count(existing.club_id)
                    if n >= club.max_capacity:
                        raise ValidationError(
                            f"Club {club.name!r} is at capacity "
                            f"({club.max_capacity})")
            conn.execute(
                "UPDATE club_memberships SET status = ?, "
                "updated_at = datetime('now') WHERE membership_id = ?",
                (status, membership_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to set membership status #%d",
                         membership_id)
        raise
    rec = get_membership(membership_id)
    assert rec is not None
    logger.info("Membership #%d status %s -> %s",
                membership_id, existing.status, rec.status)
    return rec


def delete_membership(membership_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM club_memberships WHERE membership_id = ?",
                (membership_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete membership #%d", membership_id)
        raise
    if deleted:
        logger.info("Deleted membership #%d", membership_id)
    return deleted


def club_summary(club_id: int) -> dict[str, Any]:
    init_db()
    c = get_club(club_id)
    if c is None:
        raise ValidationError(f"No club #{club_id}")
    rows = list_memberships(club_id)
    counts = Counter(r.status for r in rows)
    return {
        "club":     c,
        "total":    len(rows),
        "by_status": {s: counts.get(s, 0) for s in MEMBERSHIP_STATUSES},
        "active":   counts.get("Active", 0),
        "capacity": c.max_capacity,
        "spaces":   (c.max_capacity - counts.get("Active", 0)
                     if c.max_capacity is not None else None),
    }


def overview() -> dict[str, Any]:
    init_db()
    try:
        with _connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM clubs").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM clubs WHERE is_active = 1"
            ).fetchone()[0]
            members = conn.execute(
                "SELECT COUNT(*) FROM club_memberships "
                "WHERE status = 'Active'"
            ).fetchone()[0]
    except sqlite3.Error:
        logger.exception("clubs overview failed")
        raise
    return {"total": total, "active": active, "active_memberships": members}
