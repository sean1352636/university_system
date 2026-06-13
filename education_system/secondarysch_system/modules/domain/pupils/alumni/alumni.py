"""Alumni data layer for the Secondary School System.

Tracks former pupils — typically created when a pupil leaves at end of
Year 11, but legacy alumni (with no pupil_id link) are also supported.
"""

from __future__ import annotations

import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.secondarysch_system.modules.domain.pupils.pupils import pupils as pupils_data
from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect, _DOB_RE,
)

logger = logging.getLogger(__name__)

ID_PREFIX = "AL"
ID_DIGITS = 7

STATUSES = ("active", "inactive", "deceased")

_PHONE_RE = re.compile(r"^[0-9 +()\-]{6,20}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS alumni (
    alumni_id              TEXT PRIMARY KEY,
    pupil_id               TEXT,
    first_name             TEXT NOT NULL,
    last_name              TEXT NOT NULL,
    date_of_birth          TEXT,
    year_left              TEXT NOT NULL,
    leaving_date           TEXT DEFAULT (date('now')),
    current_email          TEXT,
    current_phone          TEXT,
    destination            TEXT,
    employer               TEXT,
    status                 TEXT NOT NULL DEFAULT 'active',
    notes                  TEXT,
    created_at             TEXT DEFAULT (datetime('now'))
);
"""


@dataclass
class Alumnus:
    alumni_id: str
    pupil_id: str | None
    first_name: str
    last_name: str
    date_of_birth: str | None
    year_left: str
    leaving_date: str | None
    current_email: str | None
    current_phone: str | None
    destination: str | None
    employer: str | None
    status: str
    notes: str | None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


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
        logger.exception("Failed to initialise alumni table")
        raise
    logger.info("Secondary alumni table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> Alumnus:
    return Alumnus(
        alumni_id=r["alumni_id"],
        pupil_id=r["pupil_id"],
        first_name=r["first_name"],
        last_name=r["last_name"],
        date_of_birth=r["date_of_birth"],
        year_left=r["year_left"],
        leaving_date=r["leaving_date"],
        current_email=r["current_email"],
        current_phone=r["current_phone"],
        destination=r["destination"],
        employer=r["employer"],
        status=r["status"],
        notes=r["notes"],
    )


def generate_alumni_id() -> str:
    init_db()
    with _connect() as conn:
        for attempt in range(50):
            n = random.randint(10 ** (ID_DIGITS - 1), 10 ** ID_DIGITS - 1)
            aid = f"{ID_PREFIX}{n}"
            if conn.execute(
                "SELECT 1 FROM alumni WHERE alumni_id = ?", (aid,)
            ).fetchone() is None:
                if attempt > 0:
                    logger.info("Allocated alumni id %s after %d collisions",
                                aid, attempt)
                return aid
    logger.error("Exhausted 50 attempts allocating alumni id")
    raise RuntimeError("Could not allocate a unique alumni id")


def _require(value: str | None, label: str) -> str:
    if not value or not str(value).strip():
        raise ValidationError(f"{label} is required")
    return str(value).strip()


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["first_name"] = _require(data.get("first_name"), "First name")
    out["last_name"]  = _require(data.get("last_name"),  "Last name")
    yg = _require(data.get("year_left"), "Year left")
    if yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year left must be one of {', '.join(YEAR_GROUPS)}")
    out["year_left"] = yg
    dob = (data.get("date_of_birth") or "").strip()
    if dob and not _DOB_RE.match(dob):
        raise ValidationError("Date of birth must be YYYY-MM-DD")
    out["date_of_birth"] = dob or None
    ld = (data.get("leaving_date") or "").strip()
    if ld and not _DOB_RE.match(ld):
        raise ValidationError("Leaving date must be YYYY-MM-DD")
    out["leaving_date"] = ld or None
    em = (data.get("current_email") or "").strip()
    if em and not _EMAIL_RE.match(em):
        raise ValidationError("Current email is not a valid address")
    out["current_email"] = em or None
    ph = (data.get("current_phone") or "").strip()
    if ph and not _PHONE_RE.match(ph):
        raise ValidationError("Current phone contains invalid characters")
    out["current_phone"] = ph or None
    out["destination"] = (data.get("destination") or "").strip() or None
    out["employer"]    = (data.get("employer") or "").strip() or None
    status = (data.get("status") or "active").strip().lower() or "active"
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status
    out["notes"] = (data.get("notes") or "").strip() or None
    out["pupil_id"] = (data.get("pupil_id") or "").strip() or None
    return out


def create_alumnus(data: dict[str, Any]) -> Alumnus:
    init_db()
    logger.debug("create_alumnus called with fields: %s",
                 sorted(k for k, v in data.items() if v not in (None, "")))
    try:
        payload = _validate(data)
    except ValidationError as e:
        logger.warning("create_alumnus validation failed: %s", e)
        raise
    if payload["pupil_id"]:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT alumni_id FROM alumni WHERE pupil_id = ?",
                (payload["pupil_id"],),
            ).fetchone()
        if dup:
            raise ValidationError(
                f"Pupil {payload['pupil_id']} is already alumni "
                f"({dup['alumni_id']})")
    aid = generate_alumni_id()
    try:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO alumni (
                    alumni_id, pupil_id, first_name, last_name,
                    date_of_birth, year_left, leaving_date,
                    current_email, current_phone,
                    destination, employer, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (aid, payload["pupil_id"], payload["first_name"],
                 payload["last_name"], payload["date_of_birth"],
                 payload["year_left"], payload["leaving_date"],
                 payload["current_email"], payload["current_phone"],
                 payload["destination"], payload["employer"],
                 payload["status"], payload["notes"]),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Database error creating alumnus %s", aid)
        raise
    rec = get_alumnus(aid)
    assert rec is not None
    logger.info("Created alumnus %s for %s (year left %s)",
                aid, rec.full_name, rec.year_left)
    return rec


def get_alumnus(alumni_id: str) -> Alumnus | None:
    init_db()
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT * FROM alumni WHERE alumni_id = ?",
                (alumni_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_alumnus(%s) failed", alumni_id)
        raise
    return _row(row) if row else None


def list_alumni(status: str | None = None,
                year_left: str | None = None) -> list[Alumnus]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status filter must be one of {', '.join(STATUSES)}")
        where.append("status = ?")
        params.append(status)
    if year_left:
        if year_left not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("year_left = ?")
        params.append(year_left)
    sql = "SELECT * FROM alumni"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY leaving_date DESC, last_name, first_name"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_alumni failed")
        raise
    logger.debug("list_alumni(status=%s,year_left=%s) -> %d",
                 status, year_left, len(rows))
    return [_row(r) for r in rows]


def search_alumni(query: str) -> list[Alumnus]:
    init_db()
    q = (query or "").strip()
    if not q:
        return list_alumni()
    like = f"%{q}%"
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM alumni
                WHERE alumni_id LIKE ? OR pupil_id LIKE ?
                   OR first_name LIKE ? OR last_name LIKE ?
                   OR current_email LIKE ? OR destination LIKE ?
                   OR employer LIKE ?
                ORDER BY leaving_date DESC, last_name, first_name
                """,
                (like, like, like, like, like, like, like),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("search_alumni(%s) failed", q)
        raise
    logger.debug("search_alumni(%s) -> %d", q, len(rows))
    return [_row(r) for r in rows]


def update_alumnus(alumni_id: str, data: dict[str, Any]) -> Alumnus:
    init_db()
    logger.debug("update_alumnus(%s) fields: %s", alumni_id,
                 sorted(k for k, v in data.items() if v not in (None, "")))
    existing = get_alumnus(alumni_id)
    if existing is None:
        raise ValidationError(f"No alumnus with id {alumni_id}")
    payload = _validate(data)
    if (payload["pupil_id"]
            and payload["pupil_id"] != existing.pupil_id):
        with _connect() as conn:
            dup = conn.execute(
                "SELECT alumni_id FROM alumni "
                "WHERE pupil_id = ? AND alumni_id != ?",
                (payload["pupil_id"], alumni_id),
            ).fetchone()
        if dup:
            raise ValidationError(
                f"Pupil {payload['pupil_id']} is already alumni "
                f"({dup['alumni_id']})")
    try:
        with _connect() as conn:
            cur = conn.execute(
                """
                UPDATE alumni SET
                    pupil_id = ?, first_name = ?, last_name = ?,
                    date_of_birth = ?, year_left = ?, leaving_date = ?,
                    current_email = ?, current_phone = ?,
                    destination = ?, employer = ?, status = ?, notes = ?
                WHERE alumni_id = ?
                """,
                (payload["pupil_id"], payload["first_name"],
                 payload["last_name"], payload["date_of_birth"],
                 payload["year_left"], payload["leaving_date"],
                 payload["current_email"], payload["current_phone"],
                 payload["destination"], payload["employer"],
                 payload["status"], payload["notes"], alumni_id),
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No alumnus with id {alumni_id}")
            conn.commit()
    except sqlite3.Error:
        logger.exception("Database error updating alumnus %s", alumni_id)
        raise
    rec = get_alumnus(alumni_id)
    assert rec is not None
    logger.info("Updated alumnus %s (%s)", alumni_id, rec.full_name)
    return rec


def set_status(alumni_id: str, new_status: str) -> Alumnus:
    init_db()
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(STATUSES)}")
    existing = get_alumnus(alumni_id)
    if existing is None:
        raise ValidationError(f"No alumnus with id {alumni_id}")
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE alumni SET status = ? WHERE alumni_id = ?",
                (new_status, alumni_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Database error setting status for %s", alumni_id)
        raise
    logger.info("Alumnus %s: %s -> %s",
                alumni_id, existing.status, new_status)
    rec = get_alumnus(alumni_id)
    assert rec is not None
    return rec


def promote_from_pupil(pupil_id: str,
                       extras: dict[str, Any] | None = None) -> Alumnus:
    """Create an alumnus record from an existing pupil, then delete the pupil.

    The pupil's year_group becomes ``year_left``. Extra fields supplied
    via ``extras`` (destination, employer, current_email, notes, etc.)
    are merged before validation.
    """
    init_db()
    pupil_id = (pupil_id or "").strip()
    if not pupil_id:
        raise ValidationError("Pupil ID is required")
    pupil = pupils_data.get_pupil(pupil_id)
    if pupil is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    with _connect() as conn:
        dup = conn.execute(
            "SELECT alumni_id FROM alumni WHERE pupil_id = ?",
            (pupil_id,),
        ).fetchone()
    if dup:
        raise ValidationError(
            f"Pupil {pupil_id} is already alumni ({dup['alumni_id']})")
    payload: dict[str, Any] = {
        "pupil_id":      pupil.pupil_id,
        "first_name":    pupil.first_name,
        "last_name":     pupil.last_name,
        "date_of_birth": pupil.date_of_birth,
        "year_left":     pupil.year_group,
        "current_phone": pupil.phone,
    }
    if extras:
        for k, v in extras.items():
            if v not in (None, ""):
                payload[k] = v
    rec = create_alumnus(payload)
    try:
        pupils_data.delete_pupil(pupil_id)
    except Exception:
        logger.exception(
            "Alumnus %s created but pupil %s could not be removed — "
            "manual reconciliation required", rec.alumni_id, pupil_id)
        raise
    logger.info("Promoted pupil %s to alumnus %s",
                pupil_id, rec.alumni_id)
    return rec


def delete_alumnus(alumni_id: str) -> bool:
    init_db()
    snapshot = get_alumnus(alumni_id)
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM alumni WHERE alumni_id = ?",
                (alumni_id,),
            )
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting alumnus %s", alumni_id)
        raise
    if deleted:
        name = snapshot.full_name if snapshot else "(unknown)"
        logger.info("Deleted alumnus %s (%s)", alumni_id, name)
    else:
        logger.warning("delete_alumnus: no alumnus with id %s", alumni_id)
    return deleted


def status_counts() -> dict[str, int]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM alumni GROUP BY status"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("alumni status_counts failed")
        raise
    counts = {s: 0 for s in STATUSES}
    for r in rows:
        counts[r["status"]] = r["n"]
    return counts
