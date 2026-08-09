"""House points data layer.

Two tables:

* ``houses`` — one row per house (e.g. "Falcon", "Dragon").
* ``house_point_awards`` — one row per award. ``pupil_id`` is optional:
  if set, the award is credited to a named pupil and (transitively) to
  their house; if blank, the award is house-level only. Negative
  ``points`` are deductions.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.domain.learners.pupils import (
    pupils as pupils_data,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    Pupil, ValidationError,
    _connect as _pupils_connect, _DOB_RE,
)

logger = logging.getLogger(__name__)

POINTS_MIN = -50
POINTS_MAX = 50

_SCHEMA = """
CREATE TABLE IF NOT EXISTS houses (
    house_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    colour      TEXT,
    motto       TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS house_point_awards (
    award_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    house_id     INTEGER NOT NULL,
    pupil_id     TEXT,
    points       INTEGER NOT NULL,
    reason       TEXT,
    awarded_by   TEXT,
    awarded_on   TEXT NOT NULL,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(house_id) REFERENCES houses(house_id) ON DELETE CASCADE,
    FOREIGN KEY(pupil_id) REFERENCES pupils(pupil_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_hpa_house  ON house_point_awards(house_id);
CREATE INDEX IF NOT EXISTS idx_hpa_pupil  ON house_point_awards(pupil_id);
CREATE INDEX IF NOT EXISTS idx_hpa_date   ON house_point_awards(awarded_on DESC);
"""


@dataclass
class House:
    house_id: int
    name: str
    colour: str | None
    motto: str | None
    is_active: bool
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class Award:
    award_id: int
    house_id: int
    pupil_id: str | None
    points: int
    reason: str | None
    awarded_by: str | None
    awarded_on: str
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
        logger.exception("Failed to initialise house tables")
        raise
    logger.info("Primary house tables ready")
    _DB_READY = True


def _row_house(r: sqlite3.Row) -> House:
    return House(
        house_id=r["house_id"],
        name=r["name"],
        colour=r["colour"],
        motto=r["motto"],
        is_active=bool(r["is_active"]),
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _row_award(r: sqlite3.Row) -> Award:
    return Award(
        award_id=r["award_id"],
        house_id=r["house_id"],
        pupil_id=r["pupil_id"],
        points=r["points"],
        reason=r["reason"],
        awarded_by=r["awarded_by"],
        awarded_on=r["awarded_on"],
        notes=r["notes"],
        created_at=r["created_at"],
    )


# --- Houses ---------------------------------------------------------------

def _validate_house(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = (data.get("name") or "").strip()
    if not name:
        raise ValidationError("House name is required")
    if len(name) > 40:
        raise ValidationError("House name must be 40 characters or fewer")
    out["name"] = name
    out["colour"] = (data.get("colour") or "").strip() or None
    out["motto"]  = (data.get("motto") or "").strip() or None
    is_active = data.get("is_active")
    out["is_active"] = True if is_active is None else bool(is_active)
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def create_house(data: dict[str, Any]) -> House:
    init_db()
    payload = _validate_house(data)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT house_id FROM houses WHERE name = ?",
                (payload["name"],),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A house named {payload['name']!r} already exists")
            cur = conn.execute(
                """INSERT INTO houses (name, colour, motto, is_active, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (payload["name"], payload["colour"], payload["motto"],
                 1 if payload["is_active"] else 0, payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create house")
        raise
    rec = get_house(new_id)
    assert rec is not None
    logger.info("Created house #%d %s", rec.house_id, rec.name)
    return rec


def get_house(house_id: int) -> House | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM houses WHERE house_id = ?", (house_id,)
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_house(%s) failed", house_id)
        raise
    return _row_house(r) if r else None


def get_house_by_name(name: str) -> House | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM houses WHERE name = ?",
                ((name or "").strip(),),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_house_by_name(%s) failed", name)
        raise
    return _row_house(r) if r else None


def list_houses(*, active_only: bool = False) -> list[House]:
    init_db()
    sql = "SELECT * FROM houses"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY name COLLATE NOCASE"
    try:
        with _connect() as conn:
            rows = conn.execute(sql).fetchall()
    except sqlite3.Error:
        logger.exception("list_houses failed")
        raise
    return [_row_house(r) for r in rows]


def update_house(house_id: int, data: dict[str, Any]) -> House:
    init_db()
    existing = get_house(house_id)
    if existing is None:
        raise ValidationError(f"No house #{house_id}")
    merged = {
        "name":      data.get("name", existing.name),
        "colour":    data.get("colour", existing.colour),
        "motto":     data.get("motto", existing.motto),
        "is_active": data.get("is_active", existing.is_active),
        "notes":     data.get("notes", existing.notes),
    }
    payload = _validate_house(merged)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT house_id FROM houses WHERE name = ? AND house_id <> ?",
                (payload["name"], house_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A house named {payload['name']!r} already exists")
            conn.execute(
                """UPDATE houses SET
                       name = ?, colour = ?, motto = ?,
                       is_active = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE house_id = ?""",
                (payload["name"], payload["colour"], payload["motto"],
                 1 if payload["is_active"] else 0,
                 payload["notes"], house_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update house #%d", house_id)
        raise
    rec = get_house(house_id)
    assert rec is not None
    logger.info("Updated house #%d %s", rec.house_id, rec.name)
    return rec


def toggle_house_active(house_id: int) -> House:
    init_db()
    existing = get_house(house_id)
    if existing is None:
        raise ValidationError(f"No house #{house_id}")
    new_val = 0 if existing.is_active else 1
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE houses SET is_active = ?, "
                "updated_at = datetime('now') WHERE house_id = ?",
                (new_val, house_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("toggle_house_active(%s) failed", house_id)
        raise
    rec = get_house(house_id)
    assert rec is not None
    logger.info("House #%d %s -> active=%s",
                rec.house_id, rec.name, rec.is_active)
    return rec


def delete_house(house_id: int) -> bool:
    init_db()
    existing = get_house(house_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM house_point_awards WHERE house_id = ?",
                (house_id,),
            ).fetchone()[0]
            if n > 0:
                raise ValidationError(
                    f"House {existing.name!r} has {n} award(s) on record — "
                    f"deactivate it instead of deleting")
            cur = conn.execute(
                "DELETE FROM houses WHERE house_id = ?", (house_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete house #%d", house_id)
        raise
    if deleted:
        logger.info("Deleted house #%d %s", house_id, existing.name)
    return deleted


# --- Awards ---------------------------------------------------------------

def _validate_award(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    hid = data.get("house_id")
    if hid in (None, ""):
        raise ValidationError("House is required")
    try:
        out["house_id"] = int(hid)
    except (TypeError, ValueError) as e:
        raise ValidationError("House ID must be an integer") from e
    pid = (data.get("pupil_id") or "").strip()
    out["pupil_id"] = pid or None
    pts_raw = data.get("points")
    if pts_raw in (None, ""):
        raise ValidationError("Points are required")
    try:
        pts = int(pts_raw)
    except (TypeError, ValueError) as e:
        raise ValidationError("Points must be an integer") from e
    if pts == 0:
        raise ValidationError("Points cannot be zero")
    if not (POINTS_MIN <= pts <= POINTS_MAX):
        raise ValidationError(
            f"Points must be between {POINTS_MIN} and {POINTS_MAX}")
    out["points"] = pts
    out["reason"]     = (data.get("reason") or "").strip() or None
    out["awarded_by"] = (data.get("awarded_by") or "").strip() or None
    ao = (data.get("awarded_on") or "").strip()
    if ao and not _DOB_RE.match(ao):
        raise ValidationError("Awarded-on date must be YYYY-MM-DD")
    out["awarded_on"] = ao or None
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def award_points(data: dict[str, Any]) -> Award:
    init_db()
    payload = _validate_award(data)
    if get_house(payload["house_id"]) is None:
        raise ValidationError(f"No house #{payload['house_id']}")
    if payload["pupil_id"]:
        if pupils_data.get_pupil(payload["pupil_id"]) is None:
            raise ValidationError(f"No pupil with id {payload['pupil_id']}")
    try:
        with _connect() as conn:
            ao = payload["awarded_on"] or conn.execute(
                "SELECT date('now')").fetchone()[0]
            cur = conn.execute(
                """INSERT INTO house_point_awards
                       (house_id, pupil_id, points, reason,
                        awarded_by, awarded_on, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (payload["house_id"], payload["pupil_id"], payload["points"],
                 payload["reason"], payload["awarded_by"], ao,
                 payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to award points")
        raise
    rec = get_award(new_id)
    assert rec is not None
    logger.info("Awarded %+d to house #%d%s (#%d)",
                rec.points, rec.house_id,
                f" pupil {rec.pupil_id}" if rec.pupil_id else "",
                rec.award_id)
    return rec


def get_award(award_id: int) -> Award | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM house_point_awards WHERE award_id = ?",
                (award_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_award(%s) failed", award_id)
        raise
    return _row_award(r) if r else None


def update_award(award_id: int, data: dict[str, Any]) -> Award:
    init_db()
    existing = get_award(award_id)
    if existing is None:
        raise ValidationError(f"No award #{award_id}")
    merged = {
        "house_id":   data.get("house_id", existing.house_id),
        "pupil_id":   data.get("pupil_id", existing.pupil_id or ""),
        "points":     data.get("points", existing.points),
        "reason":     data.get("reason", existing.reason),
        "awarded_by": data.get("awarded_by", existing.awarded_by),
        "awarded_on": data.get("awarded_on", existing.awarded_on),
        "notes":      data.get("notes", existing.notes),
    }
    payload = _validate_award(merged)
    if get_house(payload["house_id"]) is None:
        raise ValidationError(f"No house #{payload['house_id']}")
    if payload["pupil_id"]:
        if pupils_data.get_pupil(payload["pupil_id"]) is None:
            raise ValidationError(f"No pupil with id {payload['pupil_id']}")
    try:
        with _connect() as conn:
            ao = payload["awarded_on"] or existing.awarded_on or conn.execute(
                "SELECT date('now')").fetchone()[0]
            conn.execute(
                """UPDATE house_point_awards SET
                       house_id = ?, pupil_id = ?, points = ?, reason = ?,
                       awarded_by = ?, awarded_on = ?, notes = ?
                   WHERE award_id = ?""",
                (payload["house_id"], payload["pupil_id"], payload["points"],
                 payload["reason"], payload["awarded_by"], ao,
                 payload["notes"], award_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update award #%d", award_id)
        raise
    rec = get_award(award_id)
    assert rec is not None
    logger.info("Updated award #%d", award_id)
    return rec


def delete_award(award_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM house_point_awards WHERE award_id = ?",
                (award_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete award #%d", award_id)
        raise
    if deleted:
        logger.info("Deleted award #%d", award_id)
    return deleted


def list_awards(
    *, house_id: int | None = None,
    pupil_id: str | None = None,
    awarded_by: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int | None = None,
) -> list[tuple[Award, House | None, Pupil | None]]:
    init_db()
    if from_date and not _DOB_RE.match(from_date):
        raise ValidationError("From-date must be YYYY-MM-DD")
    if to_date and not _DOB_RE.match(to_date):
        raise ValidationError("To-date must be YYYY-MM-DD")
    where: list[str] = []
    params: list[Any] = []
    if house_id is not None:
        where.append("house_id = ?")
        params.append(house_id)
    if pupil_id:
        where.append("pupil_id = ?")
        params.append(pupil_id.strip())
    if awarded_by:
        where.append("awarded_by LIKE ?")
        params.append(f"%{awarded_by.strip()}%")
    if from_date:
        where.append("awarded_on >= ?")
        params.append(from_date)
    if to_date:
        where.append("awarded_on <= ?")
        params.append(to_date)
    sql = "SELECT * FROM house_point_awards"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY awarded_on DESC, award_id DESC"
    if limit is not None and limit > 0:
        sql += f" LIMIT {int(limit)}"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_awards failed")
        raise
    out: list[tuple[Award, House | None, Pupil | None]] = []
    for r in rows:
        a = _row_award(r)
        house = get_house(a.house_id)
        pupil = pupils_data.get_pupil(a.pupil_id) if a.pupil_id else None
        out.append((a, house, pupil))
    return out


def house_totals(*, from_date: str | None = None,
                 to_date: str | None = None) -> list[tuple[House, int]]:
    """Return [(House, total_points), ...] for every house (active or not)."""
    init_db()
    if from_date and not _DOB_RE.match(from_date):
        raise ValidationError("From-date must be YYYY-MM-DD")
    if to_date and not _DOB_RE.match(to_date):
        raise ValidationError("To-date must be YYYY-MM-DD")
    where: list[str] = []
    params: list[Any] = []
    if from_date:
        where.append("awarded_on >= ?")
        params.append(from_date)
    if to_date:
        where.append("awarded_on <= ?")
        params.append(to_date)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    try:
        with _connect() as conn:
            totals = {
                r["house_id"]: r["total"]
                for r in conn.execute(
                    f"SELECT house_id, COALESCE(SUM(points), 0) AS total "
                    f"FROM house_point_awards{clause} GROUP BY house_id",
                    tuple(params),
                ).fetchall()
            }
    except sqlite3.Error:
        logger.exception("house_totals failed")
        raise
    out: list[tuple[House, int]] = []
    for h in list_houses():
        out.append((h, totals.get(h.house_id, 0)))
    out.sort(key=lambda t: t[1], reverse=True)
    return out


def pupil_totals(*, house_id: int | None = None,
                 limit: int | None = None) -> list[tuple[str, int, int]]:
    """Return [(pupil_id, total_points, award_count), ...] sorted desc."""
    init_db()
    where = "WHERE pupil_id IS NOT NULL"
    params: list[Any] = []
    if house_id is not None:
        where += " AND house_id = ?"
        params.append(house_id)
    try:
        with _connect() as conn:
            sql = (
                f"SELECT pupil_id, COALESCE(SUM(points), 0) AS total, "
                f"COUNT(*) AS n FROM house_point_awards {where} "
                f"GROUP BY pupil_id ORDER BY total DESC, n DESC"
            )
            if limit is not None and limit > 0:
                sql += f" LIMIT {int(limit)}"
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("pupil_totals failed")
        raise
    return [(r["pupil_id"], r["total"], r["n"]) for r in rows]


def pupil_total(pupil_id: str) -> int:
    init_db()
    if pupils_data.get_pupil(pupil_id) is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT COALESCE(SUM(points), 0) AS total "
                "FROM house_point_awards WHERE pupil_id = ?",
                (pupil_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("pupil_total(%s) failed", pupil_id)
        raise
    return int(r["total"])
