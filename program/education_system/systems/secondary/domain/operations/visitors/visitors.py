"""Visitors data layer for Secondary School System.

Reception sign-in / sign-out log for everyone on site that isn't
a student or member of staff. Tracks DBS / photo-ID seen,
safeguarding briefing given, host staff member, escort required,
badge number and overdue-departure detection.

Standalone table — no FK (visitors aren't staff or students).
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system.systems.secondary.infrastructure import paths as _paths

logger = logging.getLogger(__name__)

VISITOR_TYPES: tuple[str, ...] = (
    "Parent / Carer",
    "Prospective Parent",
    "Contractor",
    "Supply Teacher",
    "Inspector / Ofsted",
    "Governor",
    "Guest Speaker",
    "External Examiner",
    "Auditor",
    "Delivery",
    "Job Candidate",
    "Police",
    "Social Worker",
    "External Agency",
    "Trainee / Volunteer",
    "Alumni",
    "Press / Media",
    "Other",
)
DEFAULT_VISITOR_TYPE = "Parent / Carer"

ID_TYPES: tuple[str, ...] = (
    "Photo ID Seen",
    "DBS Certificate Seen",
    "Both Seen",
    "Vouched For",
    "Not Required",
    "None Seen",
)
DEFAULT_ID_TYPE = "Photo ID Seen"

STATUSES: tuple[str, ...] = (
    "Expected",
    "Signed In",
    "On Site",
    "Signed Out",
    "No-Show",
    "Refused Entry",
    "Overstay",
)
DEFAULT_STATUS = "Expected"


class ValidationError(Exception):
    pass


@dataclass
class Visitor:
    visitor_id: int
    visitor_name: str
    organisation: str | None
    visitor_type: str
    purpose: str | None
    host_staff_id: str | None
    host_name: str | None
    badge_number: str | None
    visit_date: str
    arrived_at: str | None
    expected_departure: str | None
    signed_out_at: str | None
    id_check: str
    dbs_seen: bool
    photo_id_seen: bool
    induction_given: bool
    safeguarding_briefing: bool
    car_registration: str | None
    car_park_used: str | None
    contact_phone: str | None
    contact_email: str | None
    escort_required: bool
    escorted_by: str | None
    safeguarding_concern: bool
    status: str
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_on_site(self) -> bool:
        return self.status in ("Signed In", "On Site",
                                       "Overstay")

    @property
    def is_overdue(self) -> bool:
        if (not self.is_on_site
                or not self.expected_departure):
            return False
        try:
            exp = _dt.datetime.fromisoformat(
                self.expected_departure)
        except ValueError:
            try:
                exp_d = _dt.date.fromisoformat(
                    self.expected_departure)
                exp = _dt.datetime.combine(
                    exp_d, _dt.time(23, 59))
            except ValueError:
                return False
        return _dt.datetime.now() > exp


@dataclass
class VisitorsSummary:
    total: int = 0
    on_site_now: int = 0
    overdue: int = 0
    expected_today: int = 0
    no_shows: int = 0
    safeguarding_concerns: int = 0
    contractors_on_site: int = 0
    dbs_seen_count: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_id_check: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.VISITORS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS visitors (
                visitor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_name TEXT NOT NULL,
                organisation TEXT,
                visitor_type TEXT NOT NULL,
                purpose TEXT,
                host_staff_id TEXT,
                host_name TEXT,
                badge_number TEXT,
                visit_date TEXT NOT NULL,
                arrived_at TEXT,
                expected_departure TEXT,
                signed_out_at TEXT,
                id_check TEXT NOT NULL,
                dbs_seen INTEGER NOT NULL DEFAULT 0,
                photo_id_seen INTEGER NOT NULL DEFAULT 0,
                induction_given INTEGER NOT NULL DEFAULT 0,
                safeguarding_briefing INTEGER NOT NULL DEFAULT 0,
                car_registration TEXT,
                car_park_used TEXT,
                contact_phone TEXT,
                contact_email TEXT,
                escort_required INTEGER NOT NULL DEFAULT 0,
                escorted_by TEXT,
                safeguarding_concern INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL
            )
        """)


def _check_date(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD")


def _check_datetime(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.datetime.fromisoformat(value)
    except ValueError:
        # Also accept plain date
        try:
            _dt.date.fromisoformat(value)
        except ValueError:
            raise ValidationError(
                f"{label} must be YYYY-MM-DD or "
                "YYYY-MM-DDTHH:MM")


def _staff_exists(staff_id: str) -> bool:
    with _connect() as conn:
        try:
            row = conn.execute(
                "SELECT 1 FROM staff WHERE staff_id=?",
                (staff_id,)).fetchone()
        except sqlite3.OperationalError:
            return False
    return row is not None


def _validate_payload(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["visitor_name"] = (out.get("visitor_name") or "").strip()
    if not out["visitor_name"]:
        raise ValidationError("Visitor name is required")
    vt = (out.get("visitor_type") or "").strip()
    if vt not in VISITOR_TYPES:
        raise ValidationError(
            f"Visitor type must be one of: "
            f"{', '.join(VISITOR_TYPES)}")
    out["visitor_type"] = vt

    out["visit_date"] = (out.get("visit_date") or "").strip()
    if not out["visit_date"]:
        out["visit_date"] = _dt.date.today().isoformat()
    _check_date("Visit date", out["visit_date"])
    _check_datetime("Arrived at",         out.get("arrived_at"))
    _check_datetime("Expected departure",
                       out.get("expected_departure"))
    _check_datetime("Signed out at",      out.get("signed_out_at"))

    idc = (out.get("id_check") or DEFAULT_ID_TYPE).strip()
    if idc not in ID_TYPES:
        raise ValidationError(
            f"ID check must be one of: {', '.join(ID_TYPES)}")
    out["id_check"] = idc

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    host = (out.get("host_staff_id") or "").strip()
    if host and not _staff_exists(host):
        raise ValidationError(
            f"No staff with id {host} (host)")
    out["host_staff_id"] = host or None

    for k in ("organisation", "purpose", "host_name",
               "badge_number", "car_registration",
               "car_park_used", "contact_phone",
               "contact_email", "escorted_by", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("arrived_at", "expected_departure",
               "signed_out_at"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v
    for k in ("dbs_seen", "photo_id_seen", "induction_given",
               "safeguarding_briefing", "escort_required",
               "safeguarding_concern"):
        out[k] = bool(out.get(k))
    return out


def _row(r: sqlite3.Row) -> Visitor:
    return Visitor(
        visitor_id=r["visitor_id"],
        visitor_name=r["visitor_name"],
        organisation=r["organisation"],
        visitor_type=r["visitor_type"],
        purpose=r["purpose"],
        host_staff_id=r["host_staff_id"],
        host_name=r["host_name"],
        badge_number=r["badge_number"],
        visit_date=r["visit_date"],
        arrived_at=r["arrived_at"],
        expected_departure=r["expected_departure"],
        signed_out_at=r["signed_out_at"],
        id_check=r["id_check"],
        dbs_seen=bool(r["dbs_seen"]),
        photo_id_seen=bool(r["photo_id_seen"]),
        induction_given=bool(r["induction_given"]),
        safeguarding_briefing=bool(r["safeguarding_briefing"]),
        car_registration=r["car_registration"],
        car_park_used=r["car_park_used"],
        contact_phone=r["contact_phone"],
        contact_email=r["contact_email"],
        escort_required=bool(r["escort_required"]),
        escorted_by=r["escorted_by"],
        safeguarding_concern=bool(r["safeguarding_concern"]),
        status=r["status"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_visitor(payload: dict[str, Any]) -> Visitor:
    init_db()
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO visitors (
              visitor_name, organisation, visitor_type, purpose,
              host_staff_id, host_name, badge_number,
              visit_date, arrived_at, expected_departure,
              signed_out_at, id_check,
              dbs_seen, photo_id_seen, induction_given,
              safeguarding_briefing,
              car_registration, car_park_used,
              contact_phone, contact_email,
              escort_required, escorted_by,
              safeguarding_concern, status, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["visitor_name"], p["organisation"],
            p["visitor_type"], p["purpose"],
            p["host_staff_id"], p["host_name"],
            p["badge_number"], p["visit_date"],
            p["arrived_at"], p["expected_departure"],
            p["signed_out_at"], p["id_check"],
            1 if p["dbs_seen"] else 0,
            1 if p["photo_id_seen"] else 0,
            1 if p["induction_given"] else 0,
            1 if p["safeguarding_briefing"] else 0,
            p["car_registration"], p["car_park_used"],
            p["contact_phone"], p["contact_email"],
            1 if p["escort_required"] else 0,
            p["escorted_by"],
            1 if p["safeguarding_concern"] else 0,
            p["status"], p["notes"], now, now,
        ))
        new_id = cur.lastrowid
    return get_visitor(new_id)


def update_visitor(visitor_id: int,
                       payload: dict[str, Any]) -> Visitor:
    init_db()
    if get_visitor(visitor_id) is None:
        raise ValidationError(f"No visitor with id {visitor_id}")
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE visitors SET
              visitor_name=?, organisation=?, visitor_type=?,
              purpose=?, host_staff_id=?, host_name=?,
              badge_number=?, visit_date=?, arrived_at=?,
              expected_departure=?, signed_out_at=?,
              id_check=?, dbs_seen=?, photo_id_seen=?,
              induction_given=?, safeguarding_briefing=?,
              car_registration=?, car_park_used=?,
              contact_phone=?, contact_email=?,
              escort_required=?, escorted_by=?,
              safeguarding_concern=?, status=?, notes=?,
              updated_on=?
            WHERE visitor_id=?
        """, (
            p["visitor_name"], p["organisation"],
            p["visitor_type"], p["purpose"],
            p["host_staff_id"], p["host_name"],
            p["badge_number"], p["visit_date"],
            p["arrived_at"], p["expected_departure"],
            p["signed_out_at"], p["id_check"],
            1 if p["dbs_seen"] else 0,
            1 if p["photo_id_seen"] else 0,
            1 if p["induction_given"] else 0,
            1 if p["safeguarding_briefing"] else 0,
            p["car_registration"], p["car_park_used"],
            p["contact_phone"], p["contact_email"],
            1 if p["escort_required"] else 0,
            p["escorted_by"],
            1 if p["safeguarding_concern"] else 0,
            p["status"], p["notes"], now, visitor_id,
        ))
    return get_visitor(visitor_id)


def delete_visitor(visitor_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM visitors WHERE visitor_id=?",
            (visitor_id,))
        return cur.rowcount > 0


def get_visitor(visitor_id: int) -> Visitor | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM visitors WHERE visitor_id=?",
            (visitor_id,)).fetchone()
        return _row(r) if r else None


def list_visitors(*,
                       visitor_type: str | None = None,
                       status: str | None = None,
                       host_staff_id: str | None = None,
                       name_like: str | None = None,
                       org_like: str | None = None,
                       on_site_only: bool = False,
                       overdue_only: bool = False,
                       today_only: bool = False,
                       no_show_only: bool = False,
                       safeguarding_only: bool = False,
                       date_from: str | None = None,
                       date_to: str | None = None,
                       ) -> list[Visitor]:
    init_db()
    sql = "SELECT * FROM visitors WHERE 1=1"
    params: list[Any] = []
    if visitor_type:
        sql += " AND visitor_type=?"
        params.append(visitor_type)
    if status:
        sql += " AND status=?"
        params.append(status)
    if host_staff_id:
        sql += " AND host_staff_id=?"
        params.append(host_staff_id)
    if name_like:
        sql += " AND visitor_name LIKE ?"
        params.append(f"%{name_like}%")
    if org_like:
        sql += " AND organisation LIKE ?"
        params.append(f"%{org_like}%")
    if on_site_only:
        sql += (" AND status IN "
                  "('Signed In','On Site','Overstay')")
    if today_only:
        sql += " AND visit_date=?"
        params.append(_dt.date.today().isoformat())
    if no_show_only:
        sql += " AND status='No-Show'"
    if safeguarding_only:
        sql += " AND safeguarding_concern=1"
    if date_from:
        _check_date("From", date_from)
        sql += " AND visit_date >= ?"
        params.append(date_from)
    if date_to:
        _check_date("To", date_to)
        sql += " AND visit_date <= ?"
        params.append(date_to)
    sql += " ORDER BY visit_date DESC, visitor_id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    visitors = [_row(r) for r in rows]
    if overdue_only:
        visitors = [v for v in visitors if v.is_overdue]
    return visitors


def visitors_for_host(host_staff_id: str) -> list[Visitor]:
    return list_visitors(host_staff_id=host_staff_id)


# ── Workflow ──────────────────────────────────────────────

def _to_dict(v: Visitor) -> dict[str, Any]:
    return {
        "visitor_name": v.visitor_name,
        "organisation": v.organisation,
        "visitor_type": v.visitor_type,
        "purpose": v.purpose,
        "host_staff_id": v.host_staff_id,
        "host_name": v.host_name,
        "badge_number": v.badge_number,
        "visit_date": v.visit_date,
        "arrived_at": v.arrived_at,
        "expected_departure": v.expected_departure,
        "signed_out_at": v.signed_out_at,
        "id_check": v.id_check,
        "dbs_seen": v.dbs_seen,
        "photo_id_seen": v.photo_id_seen,
        "induction_given": v.induction_given,
        "safeguarding_briefing": v.safeguarding_briefing,
        "car_registration": v.car_registration,
        "car_park_used": v.car_park_used,
        "contact_phone": v.contact_phone,
        "contact_email": v.contact_email,
        "escort_required": v.escort_required,
        "escorted_by": v.escorted_by,
        "safeguarding_concern": v.safeguarding_concern,
        "status": v.status,
        "notes": v.notes,
    }


def sign_in(visitor_id: int, *,
                badge_number: str | None = None,
                arrived_at: str | None = None) -> Visitor:
    v = get_visitor(visitor_id)
    if v is None:
        raise ValidationError(f"No visitor with id {visitor_id}")
    data = _to_dict(v)
    data["arrived_at"] = (arrived_at
                              or _dt.datetime.now().isoformat(
                                  timespec="minutes"))
    if badge_number:
        data["badge_number"] = badge_number
    data["status"] = "Signed In"
    return update_visitor(visitor_id, data)


def sign_out(visitor_id: int, *,
                 signed_out_at: str | None = None) -> Visitor:
    v = get_visitor(visitor_id)
    if v is None:
        raise ValidationError(f"No visitor with id {visitor_id}")
    data = _to_dict(v)
    data["signed_out_at"] = (signed_out_at
                                  or _dt.datetime.now().isoformat(
                                      timespec="minutes"))
    data["status"] = "Signed Out"
    return update_visitor(visitor_id, data)


def mark_overstay(visitor_id: int) -> Visitor:
    v = get_visitor(visitor_id)
    if v is None:
        raise ValidationError(f"No visitor with id {visitor_id}")
    return update_visitor(visitor_id,
                                {**_to_dict(v), "status": "Overstay"})


def mark_no_show(visitor_id: int) -> Visitor:
    v = get_visitor(visitor_id)
    if v is None:
        raise ValidationError(f"No visitor with id {visitor_id}")
    return update_visitor(visitor_id,
                                {**_to_dict(v), "status": "No-Show"})


def refuse_entry(visitor_id: int, *,
                      reason: str | None = None) -> Visitor:
    v = get_visitor(visitor_id)
    if v is None:
        raise ValidationError(f"No visitor with id {visitor_id}")
    data = _to_dict(v)
    data["status"] = "Refused Entry"
    if reason:
        existing = data["notes"] or ""
        prefix = (existing + "\n") if existing else ""
        data["notes"] = (
            prefix
            + f"Refused entry "
            f"({_dt.date.today().isoformat()}): {reason}")
    return update_visitor(visitor_id, data)


def raise_safeguarding(visitor_id: int, *,
                              detail: str | None = None
                              ) -> Visitor:
    v = get_visitor(visitor_id)
    if v is None:
        raise ValidationError(f"No visitor with id {visitor_id}")
    data = _to_dict(v)
    data["safeguarding_concern"] = True
    if detail:
        existing = data["notes"] or ""
        prefix = (existing + "\n") if existing else ""
        data["notes"] = (
            prefix
            + f"Safeguarding concern "
            f"({_dt.datetime.now().isoformat(timespec='minutes')}): "
            f"{detail}")
    return update_visitor(visitor_id, data)


def set_status(visitor_id: int, new_status: str) -> Visitor:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    v = get_visitor(visitor_id)
    if v is None:
        raise ValidationError(f"No visitor with id {visitor_id}")
    return update_visitor(visitor_id,
                                {**_to_dict(v),
                                  "status": new_status})


# ── Summary ──────────────────────────────────────────────

def summary() -> VisitorsSummary:
    rows = list_visitors()
    out = VisitorsSummary(total=len(rows))
    if not rows:
        return out
    today = _dt.date.today().isoformat()
    for v in rows:
        if v.is_on_site:
            out.on_site_now += 1
        if v.is_overdue:
            out.overdue += 1
        if v.visit_date == today:
            out.expected_today += 1
        if v.status == "No-Show":
            out.no_shows += 1
        if v.safeguarding_concern:
            out.safeguarding_concerns += 1
        if (v.visitor_type == "Contractor"
                and v.is_on_site):
            out.contractors_on_site += 1
        if v.dbs_seen:
            out.dbs_seen_count += 1
        out.by_type[v.visitor_type] = (
            out.by_type.get(v.visitor_type, 0) + 1)
        out.by_status[v.status] = (
            out.by_status.get(v.status, 0) + 1)
        out.by_id_check[v.id_check] = (
            out.by_id_check.get(v.id_check, 0) + 1)
    return out


__all__ = [
    "VISITOR_TYPES", "DEFAULT_VISITOR_TYPE",
    "ID_TYPES", "DEFAULT_ID_TYPE",
    "STATUSES", "DEFAULT_STATUS",
    "ValidationError",
    "Visitor", "VisitorsSummary",
    "init_db",
    "create_visitor", "update_visitor", "delete_visitor",
    "get_visitor", "list_visitors", "visitors_for_host",
    "sign_in", "sign_out", "mark_overstay",
    "mark_no_show", "refuse_entry",
    "raise_safeguarding", "set_status",
    "summary",
]
