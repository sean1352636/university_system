"""External cover-agency roster + bookings for the Secondary School System.

Two tables:

* ``agency_staff``    — roster of agency-supplied teachers / cover
                         supervisors. Tracks contact details, hourly
                         rate, DBS-clearance flag, and an is_active
                         soft-delete.
* ``agency_bookings`` — one row per (staff_id, date, period). May
                         optionally link to an existing
                         ``cover_arrangements.cover_id`` row, in which
                         case booking the staff also updates that
                         row's cover_teacher + status to Assigned.

Booking validation:
* staff member must be active and DBS-cleared (warned via
  ``ValidationError`` if not)
* same staff can't be double-booked on the same date+period
* if a ``cover_id`` is supplied, the date+period in the booking must
  match the cover row.
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
    ValidationError, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

MIN_PERIOD = 1
MAX_PERIOD = 8

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^[0-9 +()\-]{6,20}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agency_staff (
    staff_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name       TEXT NOT NULL,
    agency_name     TEXT,
    role            TEXT,
    hourly_rate     REAL,
    contact_email   TEXT,
    contact_phone   TEXT,
    dbs_cleared     INTEGER NOT NULL DEFAULT 0,
    is_active       INTEGER NOT NULL DEFAULT 1,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE (full_name, agency_name)
);

CREATE TABLE IF NOT EXISTS agency_bookings (
    booking_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id        INTEGER NOT NULL,
    date            TEXT NOT NULL,
    period          INTEGER NOT NULL,
    cover_id        INTEGER,
    rate_charged    REAL,
    status          TEXT NOT NULL DEFAULT 'Booked',
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE (staff_id, date, period),
    FOREIGN KEY (staff_id) REFERENCES agency_staff(staff_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agency_active
    ON agency_staff(is_active);
CREATE INDEX IF NOT EXISTS idx_agency_bookings_date
    ON agency_bookings(date, period);
"""


BOOKING_STATUSES: tuple[str, ...] = (
    "Booked", "Confirmed", "Completed", "Cancelled")
DEFAULT_BOOKING_STATUS: str = "Booked"


@dataclass
class AgencyStaff:
    staff_id: int
    full_name: str
    agency_name: str | None
    role: str | None
    hourly_rate: float | None
    contact_email: str | None
    contact_phone: str | None
    dbs_cleared: bool
    is_active: bool
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class AgencyBooking:
    booking_id: int
    staff_id: int
    date: str
    period: int
    cover_id: int | None
    rate_charged: float | None
    status: str
    notes: str | None
    staff_name: str | None = None
    agency_name: str | None = None
    created_at: str | None = None


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
        logger.exception("Failed to initialise agency tables")
        raise
    logger.info("Secondary agency tables ready")
    _DB_READY = True


def _row_staff(r: sqlite3.Row) -> AgencyStaff:
    return AgencyStaff(
        staff_id=r["staff_id"], full_name=r["full_name"],
        agency_name=r["agency_name"], role=r["role"],
        hourly_rate=r["hourly_rate"],
        contact_email=r["contact_email"],
        contact_phone=r["contact_phone"],
        dbs_cleared=bool(r["dbs_cleared"]),
        is_active=bool(r["is_active"]),
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_booking(r: sqlite3.Row) -> AgencyBooking:
    keys = r.keys()
    return AgencyBooking(
        booking_id=r["booking_id"], staff_id=r["staff_id"],
        date=r["date"], period=r["period"],
        cover_id=r["cover_id"], rate_charged=r["rate_charged"],
        status=r["status"], notes=r["notes"],
        staff_name=r["staff_name"] if "staff_name" in keys else None,
        agency_name=r["agency_name"] if "agency_name" in keys else None,
        created_at=r["created_at"],
    )


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


def _validate_staff(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = (data.get("full_name") or "").strip()
    if not name:
        raise ValidationError("Full name is required")
    if len(name) > 64:
        raise ValidationError("Full name must be 64 characters or fewer")
    out["full_name"] = name
    out["agency_name"] = (data.get("agency_name") or "").strip() or None
    out["role"]        = (data.get("role") or "").strip() or None

    rate = data.get("hourly_rate")
    if rate in (None, "") or (isinstance(rate, str) and not rate.strip()):
        out["hourly_rate"] = None
    else:
        try:
            r = float(rate)
        except (TypeError, ValueError):
            raise ValidationError(
                "Hourly rate must be a number") from None
        if r < 0 or r > 1000:
            raise ValidationError(
                "Hourly rate must be between 0 and 1000")
        out["hourly_rate"] = r

    email = (data.get("contact_email") or "").strip()
    if email and not _EMAIL_RE.match(email):
        raise ValidationError("Contact email is not a valid address")
    out["contact_email"] = email or None
    phone = (data.get("contact_phone") or "").strip()
    if phone and not _PHONE_RE.match(phone):
        raise ValidationError("Contact phone contains invalid characters")
    out["contact_phone"] = phone or None

    out["dbs_cleared"] = bool(data.get("dbs_cleared"))
    is_active = data.get("is_active")
    out["is_active"]   = True if is_active is None else bool(is_active)
    out["notes"]       = (data.get("notes") or "").strip() or None
    return out


# ── Staff CRUD ────────────────────────────────────────────────────

def create_staff(data: dict[str, Any]) -> AgencyStaff:
    init_db()
    payload = _validate_staff(data)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT staff_id FROM agency_staff "
                "WHERE full_name = ? AND (agency_name IS ? OR agency_name = ?)",
                (payload["full_name"], payload["agency_name"],
                 payload["agency_name"]),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"{payload['full_name']!r} from "
                    f"{payload['agency_name'] or '(no agency)'} "
                    f"is already on the roster")
            cur = conn.execute(
                """INSERT INTO agency_staff
                       (full_name, agency_name, role, hourly_rate,
                        contact_email, contact_phone,
                        dbs_cleared, is_active, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["full_name"], payload["agency_name"],
                 payload["role"], payload["hourly_rate"],
                 payload["contact_email"], payload["contact_phone"],
                 1 if payload["dbs_cleared"] else 0,
                 1 if payload["is_active"] else 0,
                 payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create agency staff record")
        raise
    rec = get_staff(new_id)
    assert rec is not None
    logger.info("Created agency staff #%d %s (%s, DBS=%s, active=%s)",
                rec.staff_id, rec.full_name, rec.agency_name or "-",
                rec.dbs_cleared, rec.is_active)
    return rec


def get_staff(staff_id: int) -> AgencyStaff | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM agency_staff WHERE staff_id = ?",
                (staff_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_staff(%s) failed", staff_id)
        raise
    return _row_staff(r) if r else None


def list_staff(*, active_only: bool = False,
               agency_name: str | None = None) -> list[AgencyStaff]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if active_only:
        where.append("is_active = 1")
    if agency_name:
        where.append("agency_name = ?")
        params.append(agency_name.strip())
    sql = "SELECT * FROM agency_staff"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY agency_name, full_name COLLATE NOCASE"
    try:
        with _connect() as conn:
            return [_row_staff(r) for r in conn.execute(sql,
                                                         tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_staff failed")
        raise


def update_staff(staff_id: int, data: dict[str, Any]) -> AgencyStaff:
    init_db()
    existing = get_staff(staff_id)
    if existing is None:
        raise ValidationError(f"No agency staff #{staff_id}")
    merged = {
        "full_name":     data.get("full_name", existing.full_name),
        "agency_name":   data.get("agency_name", existing.agency_name),
        "role":          data.get("role", existing.role),
        "hourly_rate":   data.get("hourly_rate", existing.hourly_rate),
        "contact_email": data.get("contact_email", existing.contact_email),
        "contact_phone": data.get("contact_phone", existing.contact_phone),
        "dbs_cleared":   data.get("dbs_cleared", existing.dbs_cleared),
        "is_active":     data.get("is_active", existing.is_active),
        "notes":         data.get("notes", existing.notes),
    }
    payload = _validate_staff(merged)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT staff_id FROM agency_staff "
                "WHERE full_name = ? "
                "AND (agency_name IS ? OR agency_name = ?) "
                "AND staff_id <> ?",
                (payload["full_name"], payload["agency_name"],
                 payload["agency_name"], staff_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"{payload['full_name']!r} from "
                    f"{payload['agency_name'] or '(no agency)'} "
                    f"is already on the roster")
            conn.execute(
                """UPDATE agency_staff SET
                       full_name = ?, agency_name = ?, role = ?,
                       hourly_rate = ?, contact_email = ?,
                       contact_phone = ?, dbs_cleared = ?,
                       is_active = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE staff_id = ?""",
                (payload["full_name"], payload["agency_name"],
                 payload["role"], payload["hourly_rate"],
                 payload["contact_email"], payload["contact_phone"],
                 1 if payload["dbs_cleared"] else 0,
                 1 if payload["is_active"] else 0,
                 payload["notes"], staff_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update agency staff #%d", staff_id)
        raise
    rec = get_staff(staff_id)
    assert rec is not None
    logger.info("Updated agency staff #%d %s (active=%s)",
                rec.staff_id, rec.full_name, rec.is_active)
    return rec


def toggle_active(staff_id: int) -> AgencyStaff:
    existing = get_staff(staff_id)
    if existing is None:
        raise ValidationError(f"No agency staff #{staff_id}")
    return update_staff(staff_id, {"is_active": not existing.is_active})


def delete_staff(staff_id: int) -> bool:
    init_db()
    existing = get_staff(staff_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            # Block delete if active bookings exist
            booked = conn.execute(
                "SELECT COUNT(*) FROM agency_bookings "
                "WHERE staff_id = ? AND status NOT IN ('Cancelled')",
                (staff_id,),
            ).fetchone()[0]
            if booked:
                raise ValidationError(
                    f"{existing.full_name} has {booked} active booking(s) "
                    f"— cancel them first or set the record inactive")
            conn.execute("PRAGMA foreign_keys=ON")
            cur = conn.execute(
                "DELETE FROM agency_staff WHERE staff_id = ?", (staff_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete agency staff #%d", staff_id)
        raise
    if deleted:
        logger.info("Deleted agency staff #%d %s "
                    "(cascade: cancelled bookings)",
                    staff_id, existing.full_name)
    return deleted


# ── Bookings ──────────────────────────────────────────────────────

def _validate_booking(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    sid = data.get("staff_id")
    if sid in (None, ""):
        raise ValidationError("Staff is required")
    try:
        out["staff_id"] = int(sid)
    except (TypeError, ValueError):
        raise ValidationError("Staff ID must be a number") from None
    out["date"] = _validate_date(data.get("date"))
    period = data.get("period")
    if period in (None, ""):
        raise ValidationError("Period is required")
    try:
        period = int(period)
    except (TypeError, ValueError):
        raise ValidationError("Period must be a number") from None
    if not (MIN_PERIOD <= period <= MAX_PERIOD):
        raise ValidationError(
            f"Period must be between {MIN_PERIOD} and {MAX_PERIOD}")
    out["period"] = period
    cover_raw = data.get("cover_id")
    if cover_raw in (None, "") or (isinstance(cover_raw, str)
                                    and not cover_raw.strip()):
        out["cover_id"] = None
    else:
        try:
            out["cover_id"] = int(cover_raw)
        except (TypeError, ValueError):
            raise ValidationError("Cover ID must be a number") from None
    rate = data.get("rate_charged")
    if rate in (None, "") or (isinstance(rate, str) and not rate.strip()):
        out["rate_charged"] = None
    else:
        try:
            v = float(rate)
        except (TypeError, ValueError):
            raise ValidationError(
                "Rate charged must be a number") from None
        if v < 0:
            raise ValidationError("Rate charged cannot be negative")
        out["rate_charged"] = v
    status = (data.get("status") or DEFAULT_BOOKING_STATUS).strip()
    if status not in BOOKING_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(BOOKING_STATUSES)}")
    out["status"] = status
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def create_booking(data: dict[str, Any]) -> AgencyBooking:
    init_db()
    payload = _validate_booking(data)
    staff = get_staff(payload["staff_id"])
    if staff is None:
        raise ValidationError(f"No agency staff #{payload['staff_id']}")
    if not staff.is_active:
        raise ValidationError(
            f"{staff.full_name} is marked inactive — re-activate first")
    if not staff.dbs_cleared:
        raise ValidationError(
            f"{staff.full_name} is not DBS-cleared — cannot be booked")

    # Cross-check cover_id
    cover_row = None
    if payload["cover_id"] is not None:
        with _connect() as conn:
            cover_row = conn.execute(
                "SELECT * FROM cover_arrangements WHERE cover_id = ?",
                (payload["cover_id"],),
            ).fetchone()
        if cover_row is None:
            raise ValidationError(
                f"No cover arrangement #{payload['cover_id']}")
        if (cover_row["date"] != payload["date"]
                or cover_row["period"] != payload["period"]):
            raise ValidationError(
                f"Cover #{cover_row['cover_id']} is for "
                f"{cover_row['date']} P{cover_row['period']} — booking "
                f"must match")

    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT booking_id FROM agency_bookings "
                "WHERE staff_id = ? AND date = ? AND period = ? "
                "AND status NOT IN ('Cancelled')",
                (payload["staff_id"], payload["date"], payload["period"]),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"{staff.full_name} is already booked on "
                    f"{payload['date']} P{payload['period']} "
                    f"(booking #{dup['booking_id']})")
            cur = conn.execute(
                """INSERT INTO agency_bookings
                       (staff_id, date, period, cover_id,
                        rate_charged, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (payload["staff_id"], payload["date"], payload["period"],
                 payload["cover_id"], payload["rate_charged"],
                 payload["status"], payload["notes"]),
            )
            new_id = cur.lastrowid
            # If this booking covers an arrangement, update cover row.
            if payload["cover_id"] is not None:
                conn.execute(
                    """UPDATE cover_arrangements SET
                           cover_teacher = ?, status = 'Assigned',
                           updated_at = datetime('now')
                       WHERE cover_id = ?""",
                    (staff.full_name, payload["cover_id"]),
                )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to create agency booking")
        raise
    rec = get_booking(new_id)
    assert rec is not None
    logger.info("Created agency booking #%d staff=#%d (%s) %s P%d "
                "cover=%s",
                rec.booking_id, rec.staff_id, staff.full_name,
                rec.date, rec.period, rec.cover_id)
    return rec


def get_booking(booking_id: int) -> AgencyBooking | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT b.*, s.full_name AS staff_name,
                          s.agency_name AS agency_name
                   FROM agency_bookings b
                   LEFT JOIN agency_staff s ON s.staff_id = b.staff_id
                   WHERE b.booking_id = ?""",
                (booking_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_booking(%s) failed", booking_id)
        raise
    return _row_booking(r) if r else None


def list_bookings(*, date: str | None = None,
                  staff_id: int | None = None,
                  status: str | None = None) -> list[AgencyBooking]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if date:
        where.append("b.date = ?")
        params.append(_validate_date(date))
    if staff_id is not None:
        where.append("b.staff_id = ?")
        params.append(int(staff_id))
    if status:
        if status not in BOOKING_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(BOOKING_STATUSES)}")
        where.append("b.status = ?")
        params.append(status)
    sql = ("""SELECT b.*, s.full_name AS staff_name,
                     s.agency_name AS agency_name
              FROM agency_bookings b
              LEFT JOIN agency_staff s ON s.staff_id = b.staff_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY b.date DESC, b.period, b.booking_id DESC"
    try:
        with _connect() as conn:
            return [_row_booking(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_bookings failed")
        raise


def set_booking_status(booking_id: int, status: str) -> AgencyBooking:
    init_db()
    if status not in BOOKING_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(BOOKING_STATUSES)}")
    existing = get_booking(booking_id)
    if existing is None:
        raise ValidationError(f"No agency booking #{booking_id}")
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE agency_bookings SET status = ? WHERE booking_id = ?",
                (status, booking_id),
            )
            # Mirror Cancelled / Completed back onto linked cover row.
            if existing.cover_id is not None:
                if status == "Cancelled":
                    conn.execute(
                        "UPDATE cover_arrangements SET status = 'Pending', "
                        "cover_teacher = NULL, "
                        "updated_at = datetime('now') WHERE cover_id = ?",
                        (existing.cover_id,),
                    )
                elif status == "Completed":
                    conn.execute(
                        "UPDATE cover_arrangements SET status = 'Completed', "
                        "updated_at = datetime('now') WHERE cover_id = ?",
                        (existing.cover_id,),
                    )
                elif status == "Confirmed":
                    conn.execute(
                        "UPDATE cover_arrangements SET status = 'Confirmed', "
                        "updated_at = datetime('now') WHERE cover_id = ?",
                        (existing.cover_id,),
                    )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to set booking status #%d", booking_id)
        raise
    rec = get_booking(booking_id)
    assert rec is not None
    logger.info("Booking #%d status %s -> %s",
                booking_id, existing.status, rec.status)
    return rec


def delete_booking(booking_id: int) -> bool:
    init_db()
    existing = get_booking(booking_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM agency_bookings WHERE booking_id = ?",
                (booking_id,))
            # Unlink cover arrangement, return it to Pending.
            if existing.cover_id is not None:
                conn.execute(
                    "UPDATE cover_arrangements SET cover_teacher = NULL, "
                    "status = 'Pending', updated_at = datetime('now') "
                    "WHERE cover_id = ? AND status NOT IN ('Cancelled')",
                    (existing.cover_id,),
                )
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete booking #%d", booking_id)
        raise
    if deleted:
        logger.info("Deleted agency booking #%d", booking_id)
    return deleted


def staff_summary() -> dict[str, Any]:
    init_db()
    try:
        with _connect() as conn:
            row = conn.execute(
                """SELECT
                       COUNT(*) AS total,
                       SUM(is_active) AS active,
                       SUM(dbs_cleared) AS dbs
                   FROM agency_staff"""
            ).fetchone()
            agencies = conn.execute(
                "SELECT COUNT(DISTINCT agency_name) FROM agency_staff "
                "WHERE agency_name IS NOT NULL"
            ).fetchone()[0]
            booking_counts = conn.execute(
                "SELECT status, COUNT(*) AS n FROM agency_bookings "
                "GROUP BY status"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("staff_summary failed")
        raise
    return {
        "total":     int(row["total"] or 0),
        "active":    int(row["active"] or 0),
        "dbs":       int(row["dbs"] or 0),
        "agencies":  int(agencies or 0),
        "bookings":  {s: 0 for s in BOOKING_STATUSES} | {
            r["status"]: r["n"] for r in booking_counts},
    }
