"""Clubs / extracurricular activities data layer.

Two tables:

* ``clubs`` — one row per club/activity (e.g. "Choir", "Football").
* ``club_memberships`` — one row per (club, pupil) pair, with status
  active / withdrawn and a join date.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.domain.learners.pupils import (
    pupils as pupils_data,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    Pupil, ValidationError, YEAR_GROUPS,
    _connect as _pupils_connect, _DOB_RE,
)

logger = logging.getLogger(__name__)

DAYS_OF_WEEK: tuple[str, ...] = (
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
)
MEMBERSHIP_STATUSES: tuple[str, ...] = ("active", "withdrawn")

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS clubs (
    club_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE,
    description    TEXT,
    day_of_week    TEXT,
    start_time     TEXT,
    end_time       TEXT,
    location       TEXT,
    lead_staff     TEXT,
    year_groups    TEXT,
    max_members    INTEGER,
    is_active      INTEGER NOT NULL DEFAULT 1,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS club_memberships (
    membership_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id        INTEGER NOT NULL,
    pupil_id       TEXT NOT NULL,
    joined_on      TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'active',
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    UNIQUE(club_id, pupil_id),
    FOREIGN KEY(club_id) REFERENCES clubs(club_id) ON DELETE CASCADE,
    FOREIGN KEY(pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_club_members_club  ON club_memberships(club_id);
CREATE INDEX IF NOT EXISTS idx_club_members_pupil ON club_memberships(pupil_id);
"""


@dataclass
class Club:
    club_id: int
    name: str
    description: str | None
    day_of_week: str | None
    start_time: str | None
    end_time: str | None
    location: str | None
    lead_staff: str | None
    year_groups: str | None
    max_members: int | None
    is_active: bool
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def year_group_list(self) -> list[str]:
        if not self.year_groups:
            return []
        return [y.strip() for y in self.year_groups.split(",") if y.strip()]


@dataclass
class Membership:
    membership_id: int
    club_id: int
    pupil_id: str
    joined_on: str
    status: str
    notes: str | None
    created_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    pupils_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise clubs tables")
        raise
    logger.info("Primary clubs tables ready")
    _DB_READY = True


def _row_club(r: sqlite3.Row) -> Club:
    return Club(
        club_id=r["club_id"],
        name=r["name"],
        description=r["description"],
        day_of_week=r["day_of_week"],
        start_time=r["start_time"],
        end_time=r["end_time"],
        location=r["location"],
        lead_staff=r["lead_staff"],
        year_groups=r["year_groups"],
        max_members=r["max_members"],
        is_active=bool(r["is_active"]),
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _row_membership(r: sqlite3.Row) -> Membership:
    return Membership(
        membership_id=r["membership_id"],
        club_id=r["club_id"],
        pupil_id=r["pupil_id"],
        joined_on=r["joined_on"],
        status=r["status"],
        notes=r["notes"],
        created_at=r["created_at"],
    )


def _validate_year_groups(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        items = [str(y).strip() for y in raw if str(y).strip()]
    else:
        items = [y.strip() for y in str(raw).split(",") if y.strip()]
    if not items:
        return None
    seen: list[str] = []
    for y in items:
        if y not in YEAR_GROUPS:
            raise ValidationError(
                f"Year group {y!r} must be one of {', '.join(YEAR_GROUPS)}")
        if y not in seen:
            seen.append(y)
    return ",".join(seen)


def _validate_club(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = (data.get("name") or "").strip()
    if not name:
        raise ValidationError("Club name is required")
    if len(name) > 80:
        raise ValidationError("Club name must be 80 characters or fewer")
    out["name"] = name
    out["description"] = (data.get("description") or "").strip() or None
    day = (data.get("day_of_week") or "").strip()
    if day:
        if day not in DAYS_OF_WEEK:
            raise ValidationError(
                f"Day must be one of {', '.join(DAYS_OF_WEEK)}")
    out["day_of_week"] = day or None
    for k, label in (("start_time", "Start time"), ("end_time", "End time")):
        v = (data.get(k) or "").strip()
        if v and not _TIME_RE.match(v):
            raise ValidationError(f"{label} must be HH:MM (24-hour)")
        out[k] = v or None
    if out["start_time"] and out["end_time"] and out["end_time"] <= out["start_time"]:
        raise ValidationError("End time must be after start time")
    out["location"]   = (data.get("location") or "").strip() or None
    out["lead_staff"] = (data.get("lead_staff") or "").strip() or None
    out["year_groups"] = _validate_year_groups(data.get("year_groups"))
    cap_raw = data.get("max_members")
    if cap_raw in (None, ""):
        out["max_members"] = None
    else:
        try:
            cap = int(cap_raw)
        except (TypeError, ValueError) as e:
            raise ValidationError("Max members must be an integer") from e
        if cap < 1 or cap > 200:
            raise ValidationError("Max members must be between 1 and 200")
        out["max_members"] = cap
    is_active = data.get("is_active")
    out["is_active"] = True if is_active is None else bool(is_active)
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def create(data: dict[str, Any]) -> Club:
    init_db()
    payload = _validate_club(data)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT club_id FROM clubs WHERE name = ?",
                (payload["name"],),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A club named {payload['name']!r} already exists")
            cur = conn.execute(
                """INSERT INTO clubs
                       (name, description, day_of_week, start_time, end_time,
                        location, lead_staff, year_groups, max_members,
                        is_active, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["name"], payload["description"], payload["day_of_week"],
                 payload["start_time"], payload["end_time"],
                 payload["location"], payload["lead_staff"],
                 payload["year_groups"], payload["max_members"],
                 1 if payload["is_active"] else 0, payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create club %s", payload["name"])
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info("Created club #%d %s", rec.club_id, rec.name)
    return rec


def get(club_id: int) -> Club | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM clubs WHERE club_id = ?", (club_id,)
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get club(%s) failed", club_id)
        raise
    return _row_club(r) if r else None


def list_all(*, active_only: bool = False,
             day_of_week: str | None = None) -> list[Club]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if active_only:
        where.append("is_active = 1")
    if day_of_week:
        if day_of_week not in DAYS_OF_WEEK:
            raise ValidationError(
                f"Day filter must be one of {', '.join(DAYS_OF_WEEK)}")
        where.append("day_of_week = ?")
        params.append(day_of_week)
    sql = "SELECT * FROM clubs"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY name COLLATE NOCASE"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list clubs failed")
        raise
    return [_row_club(r) for r in rows]


def update(club_id: int, data: dict[str, Any]) -> Club:
    init_db()
    existing = get(club_id)
    if existing is None:
        raise ValidationError(f"No club #{club_id}")
    merged = {
        "name":         data.get("name", existing.name),
        "description":  data.get("description", existing.description),
        "day_of_week":  data.get("day_of_week", existing.day_of_week),
        "start_time":   data.get("start_time", existing.start_time),
        "end_time":     data.get("end_time", existing.end_time),
        "location":     data.get("location", existing.location),
        "lead_staff":   data.get("lead_staff", existing.lead_staff),
        "year_groups":  data.get("year_groups", existing.year_groups),
        "max_members":  data.get("max_members", existing.max_members),
        "is_active":    data.get("is_active", existing.is_active),
        "notes":        data.get("notes", existing.notes),
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
                       name = ?, description = ?, day_of_week = ?,
                       start_time = ?, end_time = ?, location = ?,
                       lead_staff = ?, year_groups = ?, max_members = ?,
                       is_active = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE club_id = ?""",
                (payload["name"], payload["description"], payload["day_of_week"],
                 payload["start_time"], payload["end_time"],
                 payload["location"], payload["lead_staff"],
                 payload["year_groups"], payload["max_members"],
                 1 if payload["is_active"] else 0,
                 payload["notes"], club_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update club #%d", club_id)
        raise
    rec = get(club_id)
    assert rec is not None
    logger.info("Updated club #%d %s", rec.club_id, rec.name)
    return rec


def toggle_active(club_id: int) -> Club:
    init_db()
    existing = get(club_id)
    if existing is None:
        raise ValidationError(f"No club #{club_id}")
    new_val = 0 if existing.is_active else 1
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE clubs SET is_active = ?, "
                "updated_at = datetime('now') WHERE club_id = ?",
                (new_val, club_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to toggle club #%d", club_id)
        raise
    rec = get(club_id)
    assert rec is not None
    logger.info("Toggled club #%d %s -> active=%s",
                rec.club_id, rec.name, rec.is_active)
    return rec


def delete(club_id: int) -> bool:
    init_db()
    existing = get(club_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute("DELETE FROM clubs WHERE club_id = ?",
                               (club_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete club #%d", club_id)
        raise
    if deleted:
        logger.info("Deleted club #%d %s (memberships cascaded)",
                    club_id, existing.name)
    return deleted


# --- Memberships ----------------------------------------------------------

def list_members(club_id: int, *, active_only: bool = False
                 ) -> list[tuple[Pupil, Membership]]:
    init_db()
    if get(club_id) is None:
        raise ValidationError(f"No club #{club_id}")
    sql = "SELECT * FROM club_memberships WHERE club_id = ?"
    params: list[Any] = [club_id]
    if active_only:
        sql += " AND status = 'active'"
    sql += " ORDER BY status, joined_on"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_members(%s) failed", club_id)
        raise
    out: list[tuple[Pupil, Membership]] = []
    for r in rows:
        m = _row_membership(r)
        p = pupils_data.get_pupil(m.pupil_id)
        if p is None:
            logger.warning("Membership %d refers to missing pupil %s",
                           m.membership_id, m.pupil_id)
            continue
        out.append((p, m))
    return out


def list_clubs_for_pupil(pupil_id: str, *, active_only: bool = False
                          ) -> list[tuple[Club, Membership]]:
    init_db()
    if pupils_data.get_pupil(pupil_id) is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    sql = "SELECT * FROM club_memberships WHERE pupil_id = ?"
    params: list[Any] = [pupil_id]
    if active_only:
        sql += " AND status = 'active'"
    sql += " ORDER BY joined_on DESC"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_clubs_for_pupil(%s) failed", pupil_id)
        raise
    out: list[tuple[Club, Membership]] = []
    for r in rows:
        m = _row_membership(r)
        c = get(m.club_id)
        if c is None:
            continue
        out.append((c, m))
    return out


def _count_active_members(club_id: int) -> int:
    with _connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM club_memberships "
            "WHERE club_id = ? AND status = 'active'",
            (club_id,),
        ).fetchone()[0]


def add_member(club_id: int, pupil_id: str, *,
               joined_on: str | None = None,
               notes: str | None = None) -> Membership:
    init_db()
    club = get(club_id)
    if club is None:
        raise ValidationError(f"No club #{club_id}")
    if not club.is_active:
        raise ValidationError(f"Club {club.name!r} is inactive")
    pupil = pupils_data.get_pupil(pupil_id)
    if pupil is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    if club.year_group_list and pupil.year_group not in club.year_group_list:
        raise ValidationError(
            f"Pupil year {pupil.year_group} is not eligible for "
            f"{club.name!r} (allowed: {', '.join(club.year_group_list)})")
    if joined_on:
        joined_on = joined_on.strip()
        if not _DOB_RE.match(joined_on):
            raise ValidationError("Joined-on date must be YYYY-MM-DD")
    try:
        with _connect() as conn:
            existing = conn.execute(
                "SELECT * FROM club_memberships "
                "WHERE club_id = ? AND pupil_id = ?",
                (club_id, pupil_id),
            ).fetchone()
            if existing is not None:
                if existing["status"] == "active":
                    raise ValidationError(
                        f"Pupil {pupil_id} is already a member of "
                        f"{club.name!r}")
                # Reactivate a withdrawn membership.
                if club.max_members is not None and (
                        _count_active_members(club_id) >= club.max_members):
                    raise ValidationError(
                        f"Club {club.name!r} is at capacity "
                        f"({club.max_members})")
                conn.execute(
                    "UPDATE club_memberships SET status = 'active', "
                    "joined_on = COALESCE(?, joined_on), "
                    "notes = COALESCE(?, notes) "
                    "WHERE membership_id = ?",
                    (joined_on, notes, existing["membership_id"]),
                )
                conn.commit()
                new_id = existing["membership_id"]
            else:
                if club.max_members is not None and (
                        _count_active_members(club_id) >= club.max_members):
                    raise ValidationError(
                        f"Club {club.name!r} is at capacity "
                        f"({club.max_members})")
                jd = joined_on or conn.execute("SELECT date('now')").fetchone()[0]
                cur = conn.execute(
                    """INSERT INTO club_memberships
                           (club_id, pupil_id, joined_on, status, notes)
                       VALUES (?, ?, ?, 'active', ?)""",
                    (club_id, pupil_id, jd, notes),
                )
                conn.commit()
                new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("add_member(club=%s, pupil=%s) failed",
                         club_id, pupil_id)
        raise
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM club_memberships WHERE membership_id = ?",
            (new_id,),
        ).fetchone()
    rec = _row_membership(r)
    logger.info("Added pupil %s to club #%d %s", pupil_id, club_id, club.name)
    return rec


def set_member_status(membership_id: int, new_status: str) -> Membership:
    init_db()
    if new_status not in MEMBERSHIP_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(MEMBERSHIP_STATUSES)}")
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM club_memberships WHERE membership_id = ?",
                (membership_id,),
            ).fetchone()
            if r is None:
                raise ValidationError(
                    f"No membership #{membership_id}")
            existing = _row_membership(r)
            if existing.status == new_status:
                return existing
            if new_status == "active":
                club = get(existing.club_id)
                if club and club.max_members is not None and (
                        _count_active_members(existing.club_id) >= club.max_members):
                    raise ValidationError(
                        f"Club is at capacity ({club.max_members})")
            conn.execute(
                "UPDATE club_memberships SET status = ? WHERE membership_id = ?",
                (new_status, membership_id),
            )
            conn.commit()
            r = conn.execute(
                "SELECT * FROM club_memberships WHERE membership_id = ?",
                (membership_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("set_member_status(%s, %s) failed",
                         membership_id, new_status)
        raise
    rec = _row_membership(r)
    logger.info("Membership #%d -> %s", membership_id, new_status)
    return rec


def remove_member(membership_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM club_memberships WHERE membership_id = ?",
                (membership_id,),
            )
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("remove_member(%s) failed", membership_id)
        raise
    if deleted:
        logger.info("Removed membership #%d", membership_id)
    return deleted


def counts() -> dict[str, int]:
    init_db()
    try:
        with _connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM clubs").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM clubs WHERE is_active = 1"
            ).fetchone()[0]
            members = conn.execute(
                "SELECT COUNT(*) FROM club_memberships WHERE status = 'active'"
            ).fetchone()[0]
    except sqlite3.Error:
        logger.exception("clubs counts failed")
        raise
    return {"total": total, "active": active,
            "inactive": total - active, "active_members": members}
