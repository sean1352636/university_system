"""Cover Agency — supply-teacher agencies the school uses.

One row per agency. The school keeps a contact + rate card for each,
plus a 1–5 star rating and a status (Active / Suspended / Inactive).
The Cover module references this table via ``agency_id`` when an
absence is filled by a supply teacher.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.sixthform_system.core import paths
from education_system.sixthform_system.modules.domain.academics.cover_agency import (
    cover_agency as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.COVER_AGENCY_DB


STATUSES: tuple[str, ...] = ("Active", "Suspended", "Inactive", "Prospect")
DEFAULT_STATUS: str = "Active"

SPECIALISMS: tuple[str, ...] = (
    "General Supply",
    "STEM",
    "Humanities",
    "Languages",
    "Arts",
    "PE / Sport",
    "Vocational",
    "SEND",
    "Cover Manager",
    "Long-Term",
    "Other",
)


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DATE_RE  = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PHONE_RE = re.compile(r"^[0-9 +()\-]+$")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS cover_agencies (
    agency_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL UNIQUE,
    contact_name     TEXT,
    email            TEXT,
    phone            TEXT,
    website          TEXT,
    address          TEXT,
    specialisms      TEXT,
    hourly_rate      REAL,
    daily_rate       REAL,
    rating           INTEGER,
    status           TEXT NOT NULL DEFAULT 'Active',
    onboarded_on     TEXT,
    last_used_on     TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ag_name     ON cover_agencies(name);
CREATE INDEX IF NOT EXISTS idx_ag_status   ON cover_agencies(status);
CREATE INDEX IF NOT EXISTS idx_ag_rating   ON cover_agencies(rating);
"""


@dataclass
class Agency:
    agency_id: int
    name: str
    contact_name: str | None
    email: str | None
    phone: str | None
    website: str | None
    address: str | None
    specialisms: str | None
    hourly_rate: float | None
    daily_rate: float | None
    rating: int | None
    status: str
    onboarded_on: str | None
    last_used_on: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_active(self) -> bool:
        return self.status == "Active"

    @property
    def rate_label(self) -> str:
        bits = []
        if self.daily_rate is not None:
            bits.append(f"£{self.daily_rate:.2f}/day")
        if self.hourly_rate is not None:
            bits.append(f"£{self.hourly_rate:.2f}/hr")
        return " · ".join(bits) if bits else "—"

    @property
    def stars(self) -> str:
        if self.rating is None:
            return "—"
        n = max(0, min(5, int(self.rating)))
        return "★" * n + "☆" * (5 - n)


@dataclass
class Summary:
    total: int
    by_status: dict[str, int]
    active_count: int
    average_rating: float | None
    used_recently: int       # last_used_on within 30 days
    rate_average_daily: float | None
    rate_average_hourly: float | None


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Cover-agency schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> Agency:
    return Agency(
        agency_id=r["agency_id"], name=r["name"],
        contact_name=r["contact_name"], email=r["email"],
        phone=r["phone"], website=r["website"],
        address=r["address"], specialisms=r["specialisms"],
        hourly_rate=r["hourly_rate"], daily_rate=r["daily_rate"],
        rating=r["rating"], status=r["status"],
        onboarded_on=r["onboarded_on"],
        last_used_on=r["last_used_on"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str, *,
                    required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_email(value: Any) -> str | None:
    if not value:
        return None
    s = str(value).strip()
    if not _EMAIL_RE.match(s):
        raise ValidationError("Email is not a valid address")
    return s


def _validate_phone(value: Any) -> str | None:
    if not value:
        return None
    s = str(value).strip()
    if not _PHONE_RE.match(s):
        raise ValidationError("Phone contains invalid characters")
    return s


def _validate_rate(value: Any, label: str) -> float | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number") from None
    if f < 0:
        raise ValidationError(f"{label} cannot be negative")
    return f


def _validate_rating(value: Any) -> int | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError("Rating must be a whole number") from None
    if not (1 <= n <= 5):
        raise ValidationError("Rating must be 1..5")
    return n


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["name"] = _require(payload.get("name"), "Name").strip()
    out["contact_name"] = (payload.get("contact_name")
                              or "").strip() or None
    out["email"]   = _validate_email(payload.get("email"))
    out["phone"]   = _validate_phone(payload.get("phone"))
    out["website"] = (payload.get("website") or "").strip() or None
    out["address"] = (payload.get("address") or "").strip() or None

    specs = payload.get("specialisms") or ""
    if isinstance(specs, (list, tuple)):
        specs = ", ".join(str(s).strip() for s in specs if s)
    out["specialisms"] = (specs or "").strip() or None

    out["hourly_rate"] = _validate_rate(payload.get("hourly_rate"),
                                            "Hourly rate")
    out["daily_rate"]  = _validate_rate(payload.get("daily_rate"),
                                            "Daily rate")
    out["rating"]      = _validate_rating(payload.get("rating"))

    status = (payload.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    out["onboarded_on"] = _validate_date(
        payload.get("onboarded_on"), "Onboarded on")
    out["last_used_on"] = _validate_date(
        payload.get("last_used_on"), "Last used on")
    out["notes"] = (payload.get("notes") or "").strip() or None
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def create_agency(payload: dict[str, Any]) -> Agency:
    init_db()
    p = _validate_payload(payload)
    with _connect() as conn:
        if conn.execute(
                "SELECT 1 FROM cover_agencies WHERE name = ?",
                (p["name"],)).fetchone():
            raise ValidationError(
                f"An agency named {p['name']!r} already exists")
        cur = conn.execute(
            """INSERT INTO cover_agencies
                   (name, contact_name, email, phone, website, address,
                    specialisms, hourly_rate, daily_rate, rating,
                    status, onboarded_on, last_used_on, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["name"], p["contact_name"], p["email"], p["phone"],
             p["website"], p["address"], p["specialisms"],
             p["hourly_rate"], p["daily_rate"], p["rating"],
             p["status"], p["onboarded_on"], p["last_used_on"],
             p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_agency(new_id)
    assert out is not None
    logger.info("Created agency #%d %r (status=%s)",
                new_id, p["name"], p["status"])
    return out


def get_agency(agency_id: int) -> Agency | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM cover_agencies WHERE agency_id = ?",
            (agency_id,)).fetchone()
        return _row(r) if r else None


def get_agency_by_name(name: str) -> Agency | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM cover_agencies WHERE name = ?",
            (name.strip(),)).fetchone()
        return _row(r) if r else None


def list_agencies(
    *,
    status: str | None = None,
    active_only: bool = False,
    search: str | None = None,
    min_rating: int | None = None,
    specialism_like: str | None = None,
) -> list[Agency]:
    init_db()
    clauses, args = [], []
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if active_only:
        clauses.append("status = 'Active'")
    if min_rating is not None:
        n = _validate_rating(min_rating)
        clauses.append("rating IS NOT NULL AND rating >= ?")
        args.append(n)
    if specialism_like:
        clauses.append("specialisms LIKE ?")
        args.append(f"%{specialism_like.strip()}%")
    if search:
        s = f"%{search.strip()}%"
        clauses.append(
            "(name LIKE ? OR contact_name LIKE ? OR email LIKE ?)")
        args.extend([s, s, s])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM cover_agencies {where} "
           "ORDER BY CASE status "
           "  WHEN 'Active'    THEN 0 "
           "  WHEN 'Prospect'  THEN 1 "
           "  WHEN 'Suspended' THEN 2 "
           "  WHEN 'Inactive'  THEN 3 "
           "  ELSE 4 END, "
           "rating DESC, name ASC")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def update_agency(agency_id: int,
                   payload: dict[str, Any]) -> Agency:
    init_db()
    existing = get_agency(agency_id)
    if existing is None:
        raise ValidationError(f"No agency #{agency_id}")
    merged = {
        "name":         payload.get("name", existing.name),
        "contact_name": payload.get("contact_name",
                                     existing.contact_name),
        "email":        payload.get("email", existing.email),
        "phone":        payload.get("phone", existing.phone),
        "website":      payload.get("website", existing.website),
        "address":      payload.get("address", existing.address),
        "specialisms":  payload.get("specialisms",
                                     existing.specialisms),
        "hourly_rate":  payload.get("hourly_rate",
                                     existing.hourly_rate),
        "daily_rate":   payload.get("daily_rate",
                                     existing.daily_rate),
        "rating":       payload.get("rating", existing.rating),
        "status":       payload.get("status", existing.status),
        "onboarded_on": payload.get("onboarded_on",
                                     existing.onboarded_on),
        "last_used_on": payload.get("last_used_on",
                                     existing.last_used_on),
        "notes":        payload.get("notes", existing.notes),
    }
    p = _validate_payload(merged)
    with _connect() as conn:
        row = conn.execute(
            "SELECT agency_id FROM cover_agencies WHERE name = ?",
            (p["name"],)).fetchone()
        if row and row["agency_id"] != agency_id:
            raise ValidationError(
                f"An agency named {p['name']!r} already exists")
        conn.execute(
            """UPDATE cover_agencies SET
                   name = ?, contact_name = ?, email = ?, phone = ?,
                   website = ?, address = ?, specialisms = ?,
                   hourly_rate = ?, daily_rate = ?, rating = ?,
                   status = ?, onboarded_on = ?, last_used_on = ?,
                   notes = ?, updated_at = datetime('now')
               WHERE agency_id = ?""",
            (p["name"], p["contact_name"], p["email"], p["phone"],
             p["website"], p["address"], p["specialisms"],
             p["hourly_rate"], p["daily_rate"], p["rating"],
             p["status"], p["onboarded_on"], p["last_used_on"],
             p["notes"], agency_id),
        )
        conn.commit()
    out = get_agency(agency_id)
    assert out is not None
    logger.info("Updated agency #%d (status=%s, rating=%s)",
                agency_id, out.status, out.rating)
    return out


def set_status(agency_id: int, status: str) -> Agency:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_agency(agency_id, {"status": status})


def set_rating(agency_id: int, rating: int | None) -> Agency:
    return update_agency(agency_id, {"rating": rating})


def record_use(agency_id: int, *,
                when: str | None = None) -> Agency:
    return update_agency(agency_id, {
        "last_used_on": when or _dt.date.today().isoformat(),
    })


def delete_agency(agency_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM cover_agencies WHERE agency_id = ?",
            (agency_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted agency #%d", agency_id)
            return True
        return False


# ── Summary ───────────────────────────────────────────────────────

def summary() -> Summary:
    init_db()
    rows = list_agencies()
    by_status = {s: 0 for s in STATUSES}
    rating_sum, rating_count = 0, 0
    daily_sum, daily_count = 0.0, 0
    hourly_sum, hourly_count = 0.0, 0
    cutoff = (_dt.date.today() - _dt.timedelta(days=30)).isoformat()
    used_recently = 0
    for a in rows:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        if a.rating is not None:
            rating_sum += a.rating
            rating_count += 1
        if a.daily_rate is not None:
            daily_sum += a.daily_rate
            daily_count += 1
        if a.hourly_rate is not None:
            hourly_sum += a.hourly_rate
            hourly_count += 1
        if a.last_used_on and a.last_used_on >= cutoff:
            used_recently += 1
    return Summary(
        total=len(rows),
        by_status=by_status,
        active_count=by_status.get("Active", 0),
        average_rating=(round(rating_sum / rating_count, 2)
                          if rating_count else None),
        used_recently=used_recently,
        rate_average_daily=(round(daily_sum / daily_count, 2)
                              if daily_count else None),
        rate_average_hourly=(round(hourly_sum / hourly_count, 2)
                               if hourly_count else None),
    )
