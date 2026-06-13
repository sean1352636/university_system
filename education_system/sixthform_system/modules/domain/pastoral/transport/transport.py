"""Transport data layer for Sixth Form System.

Two tables:
- `transport_routes`: routes the school works with (school bus,
  partner coach, train season, etc.) with operator, schedule
  and cost.
- `transport_arrangements`: per-student transport arrangement
  (FK cascade on students) with mode, pickup/drop points, days
  of week, fee status and lifecycle workflow.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system.sixthform_system.core import paths as _paths

logger = logging.getLogger(__name__)

MODES: tuple[str, ...] = (
    "School Bus",
    "Public Bus",
    "Train",
    "Tram",
    "Coach",
    "Walking",
    "Cycling",
    "Car-Share",
    "Parent Drop-off",
    "Self-Drive",
    "Taxi",
    "Other",
)
DEFAULT_MODE = "Public Bus"

ROUTE_TYPES: tuple[str, ...] = (
    "School Bus",
    "Public Bus",
    "Train",
    "Tram",
    "Coach",
    "Mixed",
    "Other",
)
DEFAULT_ROUTE_TYPE = "School Bus"

ROUTE_STATUSES: tuple[str, ...] = (
    "Active",
    "Suspended",
    "Withdrawn",
)
DEFAULT_ROUTE_STATUS = "Active"

ARRANGEMENT_STATUSES: tuple[str, ...] = (
    "Active",
    "Pending",
    "Suspended",
    "Cancelled",
    "Ended",
)
DEFAULT_ARRANGEMENT_STATUS = "Active"

FEE_STATUSES: tuple[str, ...] = (
    "Paid",
    "Partial",
    "Unpaid",
    "Bursary Funded",
    "Free",
    "Not Applicable",
)
DEFAULT_FEE_STATUS = "Not Applicable"

DAYS: tuple[str, ...] = (
    "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday", "Sunday",
)


class ValidationError(Exception):
    pass


@dataclass
class Route:
    route_id: int
    route_name: str
    route_type: str
    operator: str | None
    contact_phone: str | None
    contact_email: str | None
    days: str
    am_pickup_time: str | None
    pm_return_time: str | None
    pickup_points: str | None
    cost_per_term: float | None
    cost_per_year: float | None
    capacity: int | None
    notes: str | None
    status: str
    created_on: str
    updated_on: str

    @property
    def is_active(self) -> bool:
        return self.status == "Active"


@dataclass
class Arrangement:
    arrangement_id: int
    student_id: str
    mode: str
    route_id: int | None
    route_name_cache: str | None
    pickup_point: str | None
    drop_point: str | None
    days: str
    start_date: str
    end_date: str | None
    fee_status: str
    fee_amount: float | None
    bursary_supported: bool
    pass_number: str | None
    pass_expires_on: str | None
    emergency_contact: str | None
    emergency_phone: str | None
    medical_notes: str | None
    notes: str | None
    status: str
    created_on: str
    updated_on: str

    @property
    def is_active(self) -> bool:
        return self.status == "Active"

    @property
    def pass_expired(self) -> bool:
        if not self.pass_expires_on:
            return False
        return self.pass_expires_on < _dt.date.today().isoformat()

    @property
    def is_overdue_unpaid(self) -> bool:
        return (self.is_active
                  and self.fee_status in ("Unpaid", "Partial"))


@dataclass
class TransportSummary:
    total_routes: int = 0
    active_routes: int = 0
    total_arrangements: int = 0
    active_arrangements: int = 0
    suspended: int = 0
    pending: int = 0
    unpaid_or_partial: int = 0
    bursary_supported: int = 0
    pass_expired: int = 0
    distinct_students: int = 0
    by_mode: dict[str, int] = field(default_factory=dict)
    by_fee_status: dict[str, int] = field(default_factory=dict)
    by_route: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.TRANSPORT_DB)
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
            CREATE TABLE IF NOT EXISTS transport_routes (
                route_id INTEGER PRIMARY KEY AUTOINCREMENT,
                route_name TEXT NOT NULL UNIQUE,
                route_type TEXT NOT NULL,
                operator TEXT,
                contact_phone TEXT,
                contact_email TEXT,
                days TEXT NOT NULL,
                am_pickup_time TEXT,
                pm_return_time TEXT,
                pickup_points TEXT,
                cost_per_term REAL,
                cost_per_year REAL,
                capacity INTEGER,
                notes TEXT,
                status TEXT NOT NULL,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transport_arrangements (
                arrangement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                route_id INTEGER,
                pickup_point TEXT,
                drop_point TEXT,
                days TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                fee_status TEXT NOT NULL,
                fee_amount REAL,
                bursary_supported INTEGER NOT NULL DEFAULT 0,
                pass_number TEXT,
                pass_expires_on TEXT,
                emergency_contact TEXT,
                emergency_phone TEXT,
                medical_notes TEXT,
                notes TEXT,
                status TEXT NOT NULL,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(student_id)
                  ON DELETE CASCADE,
                FOREIGN KEY(route_id)
                  REFERENCES transport_routes(route_id)
                  ON DELETE SET NULL
            )
        """)


def _check_date(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD")


def _check_time(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.time.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be HH:MM")


def _student_exists(student_id: str) -> bool:
    with _connect() as conn:
        try:
            row = conn.execute(
                "SELECT 1 FROM students WHERE student_id=?",
                (student_id,)).fetchone()
        except sqlite3.OperationalError:
            return False
    return row is not None


# ── Routes ──────────────────────────────────────────────────────

def _validate_route(p: dict[str, Any], *,
                         existing_id: int | None = None
                         ) -> dict[str, Any]:
    out = dict(p)
    out["route_name"] = (out.get("route_name") or "").strip()
    if not out["route_name"]:
        raise ValidationError("Route name is required")
    rtype = (out.get("route_type") or "").strip()
    if rtype not in ROUTE_TYPES:
        raise ValidationError(
            f"Route type must be one of: "
            f"{', '.join(ROUTE_TYPES)}")
    out["route_type"] = rtype
    out["days"] = (out.get("days") or "").strip()
    if not out["days"]:
        raise ValidationError(
            "Days are required (e.g. 'Mon-Fri')")
    status = (out.get("status") or DEFAULT_ROUTE_STATUS).strip()
    if status not in ROUTE_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(ROUTE_STATUSES)}")
    out["status"] = status
    _check_time("AM pickup", out.get("am_pickup_time"))
    _check_time("PM return", out.get("pm_return_time"))

    for k in ("operator", "contact_phone", "contact_email",
               "pickup_points", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("am_pickup_time", "pm_return_time"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v

    for key in ("cost_per_term", "cost_per_year"):
        v = out.get(key)
        if v in (None, ""):
            out[key] = None
        else:
            try:
                out[key] = float(v)
            except (TypeError, ValueError):
                raise ValidationError(
                    f"{key.replace('_', ' ')} must be a number")
            if out[key] < 0:
                raise ValidationError(
                    f"{key.replace('_', ' ')} must be >= 0")
    cap = out.get("capacity")
    if cap in (None, ""):
        out["capacity"] = None
    else:
        try:
            out["capacity"] = int(cap)
        except (TypeError, ValueError):
            raise ValidationError(
                "Capacity must be an integer")
        if out["capacity"] < 0:
            raise ValidationError("Capacity must be >= 0")

    # Uniqueness
    with _connect() as conn:
        row = conn.execute(
            "SELECT route_id FROM transport_routes "
            "WHERE route_name=?",
            (out["route_name"],)).fetchone()
    if row and row["route_id"] != existing_id:
        raise ValidationError(
            f"A route named {out['route_name']!r} already exists")
    return out


def _row_route(r: sqlite3.Row) -> Route:
    return Route(
        route_id=r["route_id"],
        route_name=r["route_name"],
        route_type=r["route_type"],
        operator=r["operator"],
        contact_phone=r["contact_phone"],
        contact_email=r["contact_email"],
        days=r["days"],
        am_pickup_time=r["am_pickup_time"],
        pm_return_time=r["pm_return_time"],
        pickup_points=r["pickup_points"],
        cost_per_term=r["cost_per_term"],
        cost_per_year=r["cost_per_year"],
        capacity=r["capacity"],
        notes=r["notes"],
        status=r["status"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_route(payload: dict[str, Any]) -> Route:
    init_db()
    p = _validate_route(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO transport_routes (
              route_name, route_type, operator,
              contact_phone, contact_email,
              days, am_pickup_time, pm_return_time,
              pickup_points, cost_per_term, cost_per_year,
              capacity, notes, status, created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["route_name"], p["route_type"], p["operator"],
            p["contact_phone"], p["contact_email"],
            p["days"], p["am_pickup_time"], p["pm_return_time"],
            p["pickup_points"], p["cost_per_term"],
            p["cost_per_year"], p["capacity"], p["notes"],
            p["status"], now, now,
        ))
        new_id = cur.lastrowid
    return get_route(new_id)


def update_route(route_id: int,
                      payload: dict[str, Any]) -> Route:
    init_db()
    if get_route(route_id) is None:
        raise ValidationError(f"No route with id {route_id}")
    p = _validate_route(payload, existing_id=route_id)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE transport_routes SET
              route_name=?, route_type=?, operator=?,
              contact_phone=?, contact_email=?,
              days=?, am_pickup_time=?, pm_return_time=?,
              pickup_points=?, cost_per_term=?, cost_per_year=?,
              capacity=?, notes=?, status=?, updated_on=?
            WHERE route_id=?
        """, (
            p["route_name"], p["route_type"], p["operator"],
            p["contact_phone"], p["contact_email"],
            p["days"], p["am_pickup_time"], p["pm_return_time"],
            p["pickup_points"], p["cost_per_term"],
            p["cost_per_year"], p["capacity"], p["notes"],
            p["status"], now, route_id,
        ))
    return get_route(route_id)


def delete_route(route_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM transport_routes WHERE route_id=?",
            (route_id,))
        return cur.rowcount > 0


def get_route(route_id: int) -> Route | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM transport_routes WHERE route_id=?",
            (route_id,)).fetchone()
        return _row_route(r) if r else None


def list_routes(*,
                     route_type: str | None = None,
                     status: str | None = None,
                     active_only: bool = False,
                     operator_like: str | None = None,
                     name_like: str | None = None,
                     ) -> list[Route]:
    init_db()
    sql = "SELECT * FROM transport_routes WHERE 1=1"
    params: list[Any] = []
    if route_type:
        sql += " AND route_type=?"
        params.append(route_type)
    if status:
        sql += " AND status=?"
        params.append(status)
    if active_only:
        sql += " AND status='Active'"
    if operator_like:
        sql += " AND operator LIKE ?"
        params.append(f"%{operator_like}%")
    if name_like:
        sql += " AND route_name LIKE ?"
        params.append(f"%{name_like}%")
    sql += " ORDER BY route_name ASC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_route(r) for r in rows]


def _to_route_dict(r: Route) -> dict[str, Any]:
    return {
        "route_name": r.route_name,
        "route_type": r.route_type,
        "operator": r.operator,
        "contact_phone": r.contact_phone,
        "contact_email": r.contact_email,
        "days": r.days,
        "am_pickup_time": r.am_pickup_time,
        "pm_return_time": r.pm_return_time,
        "pickup_points": r.pickup_points,
        "cost_per_term": r.cost_per_term,
        "cost_per_year": r.cost_per_year,
        "capacity": r.capacity,
        "notes": r.notes,
        "status": r.status,
    }


def set_route_status(route_id: int, new_status: str) -> Route:
    if new_status not in ROUTE_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(ROUTE_STATUSES)}")
    r = get_route(route_id)
    if r is None:
        raise ValidationError(f"No route with id {route_id}")
    return update_route(route_id,
                             {**_to_route_dict(r),
                               "status": new_status})


def route_seats_used(route_id: int) -> int:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) c FROM transport_arrangements "
            "WHERE route_id=? AND status='Active'",
            (route_id,)).fetchone()
    return int(row["c"]) if row else 0


# ── Arrangements ────────────────────────────────────────────────

def _validate_arrangement(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["student_id"] = (out.get("student_id") or "").strip()
    if not out["student_id"]:
        raise ValidationError("Student is required")
    if not _student_exists(out["student_id"]):
        raise ValidationError(
            f"No student with id {out['student_id']}")

    mode = (out.get("mode") or "").strip()
    if mode not in MODES:
        raise ValidationError(
            f"Mode must be one of: {', '.join(MODES)}")
    out["mode"] = mode

    out["start_date"] = (out.get("start_date") or "").strip()
    if not out["start_date"]:
        raise ValidationError("Start date is required")
    _check_date("Start date", out["start_date"])
    _check_date("End date",   out.get("end_date"))
    if (out.get("end_date") and out["end_date"]
            < out["start_date"]):
        raise ValidationError(
            "End date must be on or after start date")
    _check_date("Pass expires", out.get("pass_expires_on"))

    out["days"] = (out.get("days") or "").strip()
    if not out["days"]:
        raise ValidationError(
            "Days are required (e.g. 'Mon-Fri')")

    fs = (out.get("fee_status") or DEFAULT_FEE_STATUS).strip()
    if fs not in FEE_STATUSES:
        raise ValidationError(
            f"Fee status must be one of: "
            f"{', '.join(FEE_STATUSES)}")
    out["fee_status"] = fs

    status = (out.get("status") or
              DEFAULT_ARRANGEMENT_STATUS).strip()
    if status not in ARRANGEMENT_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(ARRANGEMENT_STATUSES)}")
    out["status"] = status

    rid = out.get("route_id")
    if rid in (None, ""):
        out["route_id"] = None
    else:
        try:
            out["route_id"] = int(rid)
        except (TypeError, ValueError):
            raise ValidationError(
                "Route id must be an integer")
        # Soft validation — route must exist if specified
        if get_route(out["route_id"]) is None:
            raise ValidationError(
                f"No route with id {out['route_id']}")

    fa = out.get("fee_amount")
    if fa in (None, ""):
        out["fee_amount"] = None
    else:
        try:
            out["fee_amount"] = float(fa)
        except (TypeError, ValueError):
            raise ValidationError("Fee amount must be a number")
        if out["fee_amount"] < 0:
            raise ValidationError("Fee amount must be >= 0")

    for k in ("pickup_point", "drop_point", "pass_number",
               "emergency_contact", "emergency_phone",
               "medical_notes", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("end_date", "pass_expires_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v
    out["bursary_supported"] = bool(out.get("bursary_supported"))
    return out


def _row_arrangement_with_route(r: sqlite3.Row) -> Arrangement:
    return Arrangement(
        arrangement_id=r["arrangement_id"],
        student_id=r["student_id"],
        mode=r["mode"],
        route_id=r["route_id"],
        route_name_cache=(r["route_name_cache"]
                              if "route_name_cache" in r.keys()
                              else None),
        pickup_point=r["pickup_point"],
        drop_point=r["drop_point"],
        days=r["days"],
        start_date=r["start_date"],
        end_date=r["end_date"],
        fee_status=r["fee_status"],
        fee_amount=r["fee_amount"],
        bursary_supported=bool(r["bursary_supported"]),
        pass_number=r["pass_number"],
        pass_expires_on=r["pass_expires_on"],
        emergency_contact=r["emergency_contact"],
        emergency_phone=r["emergency_phone"],
        medical_notes=r["medical_notes"],
        notes=r["notes"],
        status=r["status"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


_LIST_SQL = """
    SELECT a.*, r.route_name AS route_name_cache
    FROM transport_arrangements a
    LEFT JOIN transport_routes r ON r.route_id = a.route_id
"""


def create_arrangement(payload: dict[str, Any]) -> Arrangement:
    init_db()
    p = _validate_arrangement(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO transport_arrangements (
              student_id, mode, route_id, pickup_point, drop_point,
              days, start_date, end_date,
              fee_status, fee_amount, bursary_supported,
              pass_number, pass_expires_on,
              emergency_contact, emergency_phone, medical_notes,
              notes, status, created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?)
        """, (
            p["student_id"], p["mode"], p["route_id"],
            p["pickup_point"], p["drop_point"], p["days"],
            p["start_date"], p["end_date"],
            p["fee_status"], p["fee_amount"],
            1 if p["bursary_supported"] else 0,
            p["pass_number"], p["pass_expires_on"],
            p["emergency_contact"], p["emergency_phone"],
            p["medical_notes"], p["notes"], p["status"],
            now, now,
        ))
        new_id = cur.lastrowid
    return get_arrangement(new_id)


def update_arrangement(arrangement_id: int,
                           payload: dict[str, Any]) -> Arrangement:
    init_db()
    if get_arrangement(arrangement_id) is None:
        raise ValidationError(
            f"No arrangement with id {arrangement_id}")
    p = _validate_arrangement(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE transport_arrangements SET
              student_id=?, mode=?, route_id=?, pickup_point=?,
              drop_point=?, days=?, start_date=?, end_date=?,
              fee_status=?, fee_amount=?, bursary_supported=?,
              pass_number=?, pass_expires_on=?,
              emergency_contact=?, emergency_phone=?,
              medical_notes=?, notes=?, status=?, updated_on=?
            WHERE arrangement_id=?
        """, (
            p["student_id"], p["mode"], p["route_id"],
            p["pickup_point"], p["drop_point"], p["days"],
            p["start_date"], p["end_date"],
            p["fee_status"], p["fee_amount"],
            1 if p["bursary_supported"] else 0,
            p["pass_number"], p["pass_expires_on"],
            p["emergency_contact"], p["emergency_phone"],
            p["medical_notes"], p["notes"], p["status"],
            now, arrangement_id,
        ))
    return get_arrangement(arrangement_id)


def delete_arrangement(arrangement_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM transport_arrangements "
            "WHERE arrangement_id=?", (arrangement_id,))
        return cur.rowcount > 0


def get_arrangement(arrangement_id: int) -> Arrangement | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            _LIST_SQL + " WHERE a.arrangement_id=?",
            (arrangement_id,)).fetchone()
        return _row_arrangement_with_route(r) if r else None


def list_arrangements(*,
                          student_id: str | None = None,
                          mode: str | None = None,
                          route_id: int | None = None,
                          status: str | None = None,
                          fee_status: str | None = None,
                          active_only: bool = False,
                          unpaid_only: bool = False,
                          bursary_only: bool = False,
                          pass_expired: bool = False,
                          ) -> list[Arrangement]:
    init_db()
    sql = _LIST_SQL + " WHERE 1=1"
    params: list[Any] = []
    if student_id:
        sql += " AND a.student_id=?"
        params.append(student_id)
    if mode:
        sql += " AND a.mode=?"
        params.append(mode)
    if route_id is not None:
        sql += " AND a.route_id=?"
        params.append(route_id)
    if status:
        sql += " AND a.status=?"
        params.append(status)
    if fee_status:
        sql += " AND a.fee_status=?"
        params.append(fee_status)
    if active_only:
        sql += " AND a.status='Active'"
    if unpaid_only:
        sql += (" AND a.fee_status IN ('Unpaid','Partial')"
                  " AND a.status='Active'")
    if bursary_only:
        sql += " AND a.bursary_supported=1"
    if pass_expired:
        today = _dt.date.today().isoformat()
        sql += (" AND a.pass_expires_on IS NOT NULL"
                  " AND a.pass_expires_on < ?"
                  " AND a.status='Active'")
        params.append(today)
    sql += " ORDER BY a.start_date DESC, a.arrangement_id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_arrangement_with_route(r) for r in rows]


def arrangements_for_student(student_id: str
                                 ) -> list[Arrangement]:
    return list_arrangements(student_id=student_id)


def _to_arrangement_dict(a: Arrangement) -> dict[str, Any]:
    return {
        "student_id": a.student_id,
        "mode": a.mode,
        "route_id": a.route_id,
        "pickup_point": a.pickup_point,
        "drop_point": a.drop_point,
        "days": a.days,
        "start_date": a.start_date,
        "end_date": a.end_date,
        "fee_status": a.fee_status,
        "fee_amount": a.fee_amount,
        "bursary_supported": a.bursary_supported,
        "pass_number": a.pass_number,
        "pass_expires_on": a.pass_expires_on,
        "emergency_contact": a.emergency_contact,
        "emergency_phone": a.emergency_phone,
        "medical_notes": a.medical_notes,
        "notes": a.notes,
        "status": a.status,
    }


def activate(arrangement_id: int) -> Arrangement:
    a = get_arrangement(arrangement_id)
    if a is None:
        raise ValidationError(
            f"No arrangement with id {arrangement_id}")
    return update_arrangement(arrangement_id,
                                    {**_to_arrangement_dict(a),
                                      "status": "Active"})


def suspend(arrangement_id: int) -> Arrangement:
    a = get_arrangement(arrangement_id)
    if a is None:
        raise ValidationError(
            f"No arrangement with id {arrangement_id}")
    return update_arrangement(arrangement_id,
                                    {**_to_arrangement_dict(a),
                                      "status": "Suspended"})


def end_arrangement(arrangement_id: int, *,
                         end_date: str | None = None
                         ) -> Arrangement:
    a = get_arrangement(arrangement_id)
    if a is None:
        raise ValidationError(
            f"No arrangement with id {arrangement_id}")
    data = _to_arrangement_dict(a)
    data["status"] = "Ended"
    data["end_date"] = (end_date
                            or _dt.date.today().isoformat())
    return update_arrangement(arrangement_id, data)


def cancel(arrangement_id: int) -> Arrangement:
    a = get_arrangement(arrangement_id)
    if a is None:
        raise ValidationError(
            f"No arrangement with id {arrangement_id}")
    data = _to_arrangement_dict(a)
    data["status"] = "Cancelled"
    if not data["end_date"]:
        data["end_date"] = _dt.date.today().isoformat()
    return update_arrangement(arrangement_id, data)


def set_fee_status(arrangement_id: int,
                        new_fee_status: str) -> Arrangement:
    if new_fee_status not in FEE_STATUSES:
        raise ValidationError(
            f"Fee status must be one of: "
            f"{', '.join(FEE_STATUSES)}")
    a = get_arrangement(arrangement_id)
    if a is None:
        raise ValidationError(
            f"No arrangement with id {arrangement_id}")
    return update_arrangement(arrangement_id,
                                    {**_to_arrangement_dict(a),
                                      "fee_status": new_fee_status})


def set_arrangement_status(arrangement_id: int,
                                new_status: str) -> Arrangement:
    if new_status not in ARRANGEMENT_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(ARRANGEMENT_STATUSES)}")
    a = get_arrangement(arrangement_id)
    if a is None:
        raise ValidationError(
            f"No arrangement with id {arrangement_id}")
    return update_arrangement(arrangement_id,
                                    {**_to_arrangement_dict(a),
                                      "status": new_status})


# ── Summary ───────────────────────────────────────────────────────

def summary() -> TransportSummary:
    routes = list_routes()
    arrangements = list_arrangements()
    out = TransportSummary(
        total_routes=len(routes),
        active_routes=sum(1 for r in routes if r.is_active),
        total_arrangements=len(arrangements),
    )
    students: set[str] = set()
    today = _dt.date.today().isoformat()
    for a in arrangements:
        students.add(a.student_id)
        if a.status == "Active":
            out.active_arrangements += 1
            if a.fee_status in ("Unpaid", "Partial"):
                out.unpaid_or_partial += 1
            if (a.pass_expires_on
                    and a.pass_expires_on < today):
                out.pass_expired += 1
        if a.status == "Suspended":
            out.suspended += 1
        if a.status == "Pending":
            out.pending += 1
        if a.bursary_supported:
            out.bursary_supported += 1
        out.by_mode[a.mode] = out.by_mode.get(a.mode, 0) + 1
        out.by_fee_status[a.fee_status] = (
            out.by_fee_status.get(a.fee_status, 0) + 1)
        out.by_status[a.status] = (
            out.by_status.get(a.status, 0) + 1)
        rn = a.route_name_cache or "—"
        out.by_route[rn] = out.by_route.get(rn, 0) + 1
    out.distinct_students = len(students)
    return out


__all__ = [
    "MODES", "DEFAULT_MODE",
    "ROUTE_TYPES", "DEFAULT_ROUTE_TYPE",
    "ROUTE_STATUSES", "DEFAULT_ROUTE_STATUS",
    "ARRANGEMENT_STATUSES", "DEFAULT_ARRANGEMENT_STATUS",
    "FEE_STATUSES", "DEFAULT_FEE_STATUS",
    "DAYS",
    "ValidationError",
    "Route", "Arrangement", "TransportSummary",
    "init_db",
    "create_route", "update_route", "delete_route",
    "get_route", "list_routes", "set_route_status",
    "route_seats_used",
    "create_arrangement", "update_arrangement",
    "delete_arrangement", "get_arrangement",
    "list_arrangements", "arrangements_for_student",
    "activate", "suspend", "end_arrangement", "cancel",
    "set_fee_status", "set_arrangement_status",
    "summary",
]
