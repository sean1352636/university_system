"""Trips & Payments data layer for the Sixth Form System.

Three linked tables:

* ``trips``         — the trip itself: name, destination, dates,
                      cost per place, deposit, capacity, status,
                      lead staff, year-group target.
* ``trip_bookings`` — one row per student booked onto a trip:
                      booking status, consent, medical/dietary
                      notes. ``(trip_id, student_id)`` is unique.
* ``trip_payments`` — payments against a booking. Status
                      'Cleared' counts toward the booking total.

A booking's *payment state* is derived live:
    paid    = sum(payments where status='Cleared')
    balance = trip.cost_per_place - paid
    state = 'Refunded'  if status in ('Cancelled','Withdrawn') and paid>0
            'Paid'      if paid >= cost_per_place
            'Deposit'   if paid >= trip.deposit and deposit > 0
            'Partial'   if paid > 0
            'Unpaid'    otherwise

Capacity warning: the data layer **allows** over-booking (waitlist
management) but flags it. The unique index prevents double-booking
the same student on the same trip.

Cascade: deleting a trip removes its bookings and payments;
deleting a student or booking removes the related rows.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import date as _date
from decimal import Decimal, InvalidOperation
from typing import Any
from education_system.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.TRIPS_DB

YEAR_GROUPS: tuple[str, ...] = ("Year 12", "Year 13", "Both", "Open")
DEFAULT_YEAR_GROUP: str = "Both"

TRIP_STATUSES: tuple[str, ...] = (
    "Planning", "Open for Booking", "Closed for Booking",
    "Confirmed", "In Progress", "Completed", "Cancelled",
)
DEFAULT_TRIP_STATUS: str = "Planning"
OPEN_TRIP_STATUSES: tuple[str, ...] = (
    "Open for Booking", "Closed for Booking", "Confirmed",
    "In Progress", "Planning")

BOOKING_STATUSES: tuple[str, ...] = (
    "Interested", "Confirmed", "Waitlist",
    "Cancelled", "Withdrawn", "Attended", "No-Show",
)
DEFAULT_BOOKING_STATUS: str = "Interested"
ACTIVE_BOOKING_STATUSES: tuple[str, ...] = (
    "Interested", "Confirmed", "Waitlist", "Attended")

PAYMENT_METHODS: tuple[str, ...] = (
    "Cash", "Card", "Bank Transfer", "Cheque",
    "Online Portal", "Bursary", "Voucher",
    "Adjustment", "Other",
)
DEFAULT_METHOD: str = "Card"

PAYMENT_STATUSES: tuple[str, ...] = (
    "Cleared", "Pending", "Failed", "Refunded",
)
DEFAULT_PAYMENT_STATUS: str = "Cleared"

PAYMENT_STATES: tuple[str, ...] = (
    "Unpaid", "Partial", "Deposit", "Paid", "Refunded",
)

CURRENCY_SYMBOL: str = "£"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS trips (
    trip_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    destination    TEXT,
    start_date     TEXT NOT NULL,
    end_date       TEXT,
    year_group     TEXT NOT NULL DEFAULT 'Both',
    cost_per_place REAL NOT NULL DEFAULT 0,
    deposit        REAL NOT NULL DEFAULT 0,
    capacity       INTEGER,
    payment_due    TEXT,
    status         TEXT NOT NULL DEFAULT 'Planning',
    lead_staff_id  TEXT,
    description    TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (lead_staff_id) REFERENCES staff(staff_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS trip_bookings (
    booking_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id        INTEGER NOT NULL,
    student_id     TEXT NOT NULL,
    booking_date   TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Interested',
    consent_received INTEGER NOT NULL DEFAULT 0,
    consent_note   TEXT,
    medical_note   TEXT,
    dietary_note   TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now')),
    UNIQUE (trip_id, student_id),
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trip_payments (
    payment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id  INTEGER NOT NULL,
    amount      REAL NOT NULL,
    paid_on     TEXT NOT NULL,
    method      TEXT NOT NULL DEFAULT 'Card',
    status      TEXT NOT NULL DEFAULT 'Cleared',
    reference   TEXT,
    recorded_by TEXT,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (booking_id) REFERENCES trip_bookings(booking_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_trip_status  ON trips(status);
CREATE INDEX IF NOT EXISTS idx_trip_date    ON trips(start_date);
CREATE INDEX IF NOT EXISTS idx_tb_trip      ON trip_bookings(trip_id);
CREATE INDEX IF NOT EXISTS idx_tb_student   ON trip_bookings(student_id);
CREATE INDEX IF NOT EXISTS idx_tb_status    ON trip_bookings(status);
CREATE INDEX IF NOT EXISTS idx_tp_booking   ON trip_payments(booking_id);
CREATE INDEX IF NOT EXISTS idx_tp_paid_on   ON trip_payments(paid_on);
"""


@dataclass
class Trip:
    trip_id: int
    name: str
    destination: str | None
    start_date: str
    end_date: str | None
    year_group: str
    cost_per_place: float
    deposit: float
    capacity: int | None
    payment_due: str | None
    status: str
    lead_staff_id: str | None
    description: str | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class Booking:
    booking_id: int
    trip_id: int
    student_id: str
    booking_date: str
    status: str
    consent_received: bool
    consent_note: str | None
    medical_note: str | None
    dietary_note: str | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class Payment:
    payment_id: int
    booking_id: int
    amount: float
    paid_on: str
    method: str
    status: str
    reference: str | None
    recorded_by: str | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class BookingView:
    booking: Booking
    trip: Trip
    student_name: str
    paid: float
    balance: float
    payment_state: str
    payment_count: int

    @property
    def is_active(self) -> bool:
        return self.booking.status in ACTIVE_BOOKING_STATUSES


@dataclass
class TripView:
    trip: Trip
    confirmed: int
    interested: int
    waitlist: int
    cancelled: int
    total_active: int
    capacity_used_pct: float | None
    total_charged: float
    total_paid: float
    total_balance: float


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    from education_system.sixthform_system.modules.domain.staff import staff
    from education_system.sixthform_system.modules.domain.students import students as _staff
    from education_system.sixthform_system.modules.domain.students import students as _students
    _students.init_db()
    _staff.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Trips schema ready at %s", DB_PATH)


def _row_trip(r: sqlite3.Row) -> Trip:
    return Trip(
        trip_id=r["trip_id"], name=r["name"],
        destination=r["destination"],
        start_date=r["start_date"], end_date=r["end_date"],
        year_group=r["year_group"],
        cost_per_place=r["cost_per_place"], deposit=r["deposit"],
        capacity=r["capacity"], payment_due=r["payment_due"],
        status=r["status"], lead_staff_id=r["lead_staff_id"],
        description=r["description"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_booking(r: sqlite3.Row) -> Booking:
    return Booking(
        booking_id=r["booking_id"], trip_id=r["trip_id"],
        student_id=r["student_id"],
        booking_date=r["booking_date"], status=r["status"],
        consent_received=bool(r["consent_received"]),
        consent_note=r["consent_note"],
        medical_note=r["medical_note"],
        dietary_note=r["dietary_note"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_payment(r: sqlite3.Row) -> Payment:
    return Payment(
        payment_id=r["payment_id"], booking_id=r["booking_id"],
        amount=r["amount"], paid_on=r["paid_on"],
        method=r["method"], status=r["status"],
        reference=r["reference"], recorded_by=r["recorded_by"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(v, label: str):
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        raise ValidationError(f"{label} is required")
    return v


def _validate_date(v: Any, label: str, *,
                    required: bool = False) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(v).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_amount(v: Any, label: str, *,
                       required: bool = False,
                       allow_zero: bool = True) -> float | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    try:
        d = Decimal(str(v))
    except (InvalidOperation, TypeError):
        raise ValidationError(f"{label} must be a number") from None
    if d.as_tuple().exponent < -2:
        raise ValidationError(
            f"{label} must have at most 2 decimal places")
    if d < 0:
        raise ValidationError(f"{label} cannot be negative")
    if not allow_zero and d == 0:
        raise ValidationError(f"{label} cannot be zero")
    return float(d.quantize(Decimal("0.01")))


def _validate_student(v: Any) -> str:
    sid = _require(v, "Student ID").strip()
    from education_system.sixthform_system.modules.domain.students import students as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_staff(v: Any) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    sid = str(v).strip().upper()
    from education_system.sixthform_system.modules.domain.staff import staff as _staff
    if _staff.get_staff(sid) is None:
        raise ValidationError(f"No staff with id {sid}")
    return sid


def _validate_trip_payload(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["name"] = _require(d.get("name"), "Name").strip()
    out["destination"] = (d.get("destination") or "").strip() or None

    out["start_date"] = _validate_date(d.get("start_date"),
                                          "Start date", required=True)
    out["end_date"]   = _validate_date(d.get("end_date"), "End date")
    if out["end_date"] and out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")

    yg = (d.get("year_group") or DEFAULT_YEAR_GROUP).strip()
    if yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of: {', '.join(YEAR_GROUPS)}")
    out["year_group"] = yg

    cost = _validate_amount(d.get("cost_per_place"),
                              "Cost per place")
    out["cost_per_place"] = cost if cost is not None else 0.0
    deposit = _validate_amount(d.get("deposit"), "Deposit")
    out["deposit"] = deposit if deposit is not None else 0.0
    if out["deposit"] > out["cost_per_place"]:
        raise ValidationError(
            "Deposit cannot exceed the cost per place")

    cap = d.get("capacity")
    if cap in (None, ""):
        out["capacity"] = None
    else:
        try:
            n = int(cap)
        except (TypeError, ValueError):
            raise ValidationError(
                "Capacity must be a whole number") from None
        if n < 0 or n > 5000:
            raise ValidationError("Capacity must be 0..5000")
        out["capacity"] = n

    out["payment_due"] = _validate_date(d.get("payment_due"),
                                          "Payment due")

    status = (d.get("status") or DEFAULT_TRIP_STATUS).strip()
    if status not in TRIP_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(TRIP_STATUSES)}")
    out["status"] = status

    out["lead_staff_id"] = _validate_staff(d.get("lead_staff_id"))
    out["description"]   = (d.get("description") or "").strip() or None
    out["notes"]         = (d.get("notes") or "").strip() or None
    return out


def _validate_booking_payload(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(d.get("student_id"))
    out["booking_date"] = _validate_date(
        d.get("booking_date") or _date.today().isoformat(),
        "Booking date", required=True)
    status = (d.get("status") or DEFAULT_BOOKING_STATUS).strip()
    if status not in BOOKING_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(BOOKING_STATUSES)}")
    out["status"] = status
    out["consent_received"] = bool(d.get("consent_received"))
    out["consent_note"] = (d.get("consent_note") or "").strip() or None
    out["medical_note"] = (d.get("medical_note") or "").strip() or None
    out["dietary_note"] = (d.get("dietary_note") or "").strip() or None
    out["notes"]        = (d.get("notes") or "").strip() or None
    return out


def _validate_payment_payload(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["amount"] = _validate_amount(
        d.get("amount"), "Amount", required=True, allow_zero=False)
    out["paid_on"] = _validate_date(
        d.get("paid_on") or _date.today().isoformat(),
        "Paid on", required=True)
    method = (d.get("method") or DEFAULT_METHOD).strip()
    if method not in PAYMENT_METHODS:
        raise ValidationError(
            f"Method must be one of: {', '.join(PAYMENT_METHODS)}")
    out["method"] = method
    status = (d.get("status") or DEFAULT_PAYMENT_STATUS).strip()
    if status not in PAYMENT_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(PAYMENT_STATUSES)}")
    out["status"] = status
    out["reference"]   = (d.get("reference") or "").strip() or None
    out["recorded_by"] = (d.get("recorded_by") or "").strip() or None
    out["notes"]       = (d.get("notes") or "").strip() or None
    return out


# ── Trip CRUD ─────────────────────────────────────────────────────

def create_trip(d: dict[str, Any]) -> Trip:
    init_db()
    p = _validate_trip_payload(d)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO trips (
                  name, destination, start_date, end_date, year_group,
                  cost_per_place, deposit, capacity, payment_due,
                  status, lead_staff_id, description, notes,
                  created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["name"], p["destination"], p["start_date"], p["end_date"],
             p["year_group"], p["cost_per_place"], p["deposit"],
             p["capacity"], p["payment_due"], p["status"],
             p["lead_staff_id"], p["description"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_trip(new_id)
    assert out is not None
    logger.info("Created trip #%d %s on %s",
                new_id, p["name"], p["start_date"])
    return out


def get_trip(trip_id: int) -> Trip | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM trips WHERE trip_id = ?",
            (trip_id,)).fetchone()
        return _row_trip(r) if r else None


def list_trips(
    *,
    year_group: str | None = None,
    status: str | None = None,
    open_only: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[Trip]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year group must be one of: {', '.join(YEAR_GROUPS)}")
        clauses.append("year_group = ?")
        args.append(year_group)
    if status:
        if status not in TRIP_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(TRIP_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if open_only:
        ph = ",".join("?" * len(OPEN_TRIP_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(OPEN_TRIP_STATUSES)
    if date_from:
        clauses.append("start_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("start_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM trips {where} "
           "ORDER BY start_date DESC, trip_id DESC")
    with _connect() as conn:
        return [_row_trip(r)
                 for r in conn.execute(sql, args).fetchall()]


def update_trip(trip_id: int, d: dict[str, Any]) -> Trip:
    init_db()
    existing = get_trip(trip_id)
    if existing is None:
        raise ValidationError(f"No trip with id {trip_id}")
    merged = {
        "name":           d.get("name", existing.name),
        "destination":    d.get("destination", existing.destination),
        "start_date":     d.get("start_date", existing.start_date),
        "end_date":       d.get("end_date", existing.end_date),
        "year_group":     d.get("year_group", existing.year_group),
        "cost_per_place": d.get("cost_per_place",
                                  existing.cost_per_place),
        "deposit":        d.get("deposit", existing.deposit),
        "capacity":       d.get("capacity", existing.capacity),
        "payment_due":    d.get("payment_due", existing.payment_due),
        "status":         d.get("status", existing.status),
        "lead_staff_id":  d.get("lead_staff_id",
                                  existing.lead_staff_id),
        "description":    d.get("description", existing.description),
        "notes":          d.get("notes", existing.notes),
    }
    p = _validate_trip_payload(merged)

    # If a new cost is lower than any single cleared payment total,
    # refuse — the booking can't owe a negative balance.
    if p["cost_per_place"] < existing.cost_per_place:
        with _connect() as conn:
            r = conn.execute(
                """SELECT MAX(b.paid) AS m FROM (
                       SELECT booking_id,
                              COALESCE(SUM(amount), 0) AS paid
                         FROM trip_payments
                        WHERE status='Cleared'
                        GROUP BY booking_id
                   ) AS b
                   JOIN trip_bookings tb ON tb.booking_id = b.booking_id
                  WHERE tb.trip_id = ?""", (trip_id,)).fetchone()
            max_paid = float(r["m"] or 0.0)
        if max_paid > p["cost_per_place"]:
            raise ValidationError(
                f"Cost {CURRENCY_SYMBOL}{p['cost_per_place']:.2f} is "
                f"less than the most a student has already paid "
                f"({CURRENCY_SYMBOL}{max_paid:.2f}). "
                f"Refund first or pick a higher cost.")

    with _connect() as conn:
        conn.execute(
            """UPDATE trips SET
                  name=?, destination=?, start_date=?, end_date=?,
                  year_group=?, cost_per_place=?, deposit=?, capacity=?,
                  payment_due=?, status=?, lead_staff_id=?,
                  description=?, notes=?, updated_at=datetime('now')
               WHERE trip_id=?""",
            (p["name"], p["destination"], p["start_date"], p["end_date"],
             p["year_group"], p["cost_per_place"], p["deposit"],
             p["capacity"], p["payment_due"], p["status"],
             p["lead_staff_id"], p["description"], p["notes"], trip_id),
        )
        conn.commit()
    out = get_trip(trip_id)
    assert out is not None
    logger.info("Updated trip #%d (status=%s)", trip_id, out.status)
    return out


def set_trip_status(trip_id: int, status: str) -> Trip:
    if status not in TRIP_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(TRIP_STATUSES)}")
    return update_trip(trip_id, {"status": status})


def delete_trip(trip_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM trips WHERE trip_id = ?", (trip_id,))
        conn.commit()
        if cur.rowcount:
            logger.info(
                "Deleted trip #%d (and bookings + payments)", trip_id)
            return True
        return False


# ── Booking CRUD ──────────────────────────────────────────────────

def create_booking(trip_id: int, d: dict[str, Any]) -> Booking:
    init_db()
    trip = get_trip(trip_id)
    if trip is None:
        raise ValidationError(f"No trip with id {trip_id}")
    p = _validate_booking_payload(d)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO trip_bookings
                     (trip_id, student_id, booking_date, status,
                      consent_received, consent_note, medical_note,
                      dietary_note, notes,
                      created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                           datetime('now'), datetime('now'))""",
                (trip_id, p["student_id"], p["booking_date"],
                 p["status"], int(p["consent_received"]),
                 p["consent_note"], p["medical_note"],
                 p["dietary_note"], p["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e).upper():
            raise ValidationError(
                f"Student {p['student_id']} is already booked on "
                f"trip #{trip_id}.") from e
        raise
    out = get_booking(new_id)
    assert out is not None
    logger.info(
        "Created booking #%d (trip=%d, student=%s, status=%s)",
        new_id, trip_id, p["student_id"], p["status"])
    return out


def get_booking(booking_id: int) -> Booking | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM trip_bookings WHERE booking_id = ?",
            (booking_id,)).fetchone()
        return _row_booking(r) if r else None


def list_bookings(
    *,
    trip_id: int | None = None,
    student_id: str | None = None,
    status: str | None = None,
    consent_received: bool | None = None,
    active_only: bool = False,
) -> list[Booking]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if trip_id is not None:
        clauses.append("trip_id = ?")
        args.append(trip_id)
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if status:
        if status not in BOOKING_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(BOOKING_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if consent_received is not None:
        clauses.append("consent_received = ?")
        args.append(int(consent_received))
    if active_only:
        ph = ",".join("?" * len(ACTIVE_BOOKING_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(ACTIVE_BOOKING_STATUSES)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM trip_bookings {where} "
           "ORDER BY booking_date DESC, booking_id DESC")
    with _connect() as conn:
        return [_row_booking(r)
                 for r in conn.execute(sql, args).fetchall()]


def update_booking(booking_id: int, d: dict[str, Any]) -> Booking:
    init_db()
    existing = get_booking(booking_id)
    if existing is None:
        raise ValidationError(f"No booking with id {booking_id}")
    merged = {
        "student_id":       existing.student_id,
        "booking_date":     d.get("booking_date",
                                    existing.booking_date),
        "status":           d.get("status", existing.status),
        "consent_received": d.get("consent_received",
                                    existing.consent_received),
        "consent_note":     d.get("consent_note",
                                    existing.consent_note),
        "medical_note":     d.get("medical_note",
                                    existing.medical_note),
        "dietary_note":     d.get("dietary_note",
                                    existing.dietary_note),
        "notes":            d.get("notes", existing.notes),
    }
    p = _validate_booking_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE trip_bookings SET
                  booking_date=?, status=?, consent_received=?,
                  consent_note=?, medical_note=?, dietary_note=?,
                  notes=?, updated_at=datetime('now')
               WHERE booking_id=?""",
            (p["booking_date"], p["status"], int(p["consent_received"]),
             p["consent_note"], p["medical_note"], p["dietary_note"],
             p["notes"], booking_id),
        )
        conn.commit()
    out = get_booking(booking_id)
    assert out is not None
    logger.info("Updated booking #%d (status=%s)",
                booking_id, out.status)
    return out


def set_booking_status(booking_id: int, status: str) -> Booking:
    if status not in BOOKING_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(BOOKING_STATUSES)}")
    return update_booking(booking_id, {"status": status})


def delete_booking(booking_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM trip_bookings WHERE booking_id = ?",
            (booking_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted booking #%d (and payments)",
                        booking_id)
            return True
        return False


# ── Payment CRUD ──────────────────────────────────────────────────

def _paid_total(booking_id: int) -> float:
    with _connect() as conn:
        r = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS s "
            "FROM trip_payments WHERE booking_id = ? AND status='Cleared'",
            (booking_id,)).fetchone()
    return round(float(r["s"]), 2)


def add_payment(booking_id: int, d: dict[str, Any]) -> Payment:
    init_db()
    booking = get_booking(booking_id)
    if booking is None:
        raise ValidationError(f"No booking with id {booking_id}")
    p = _validate_payment_payload(d)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO trip_payments
                 (booking_id, amount, paid_on, method, status,
                  reference, recorded_by, notes,
                  created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (booking_id, p["amount"], p["paid_on"], p["method"],
             p["status"], p["reference"], p["recorded_by"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_payment(new_id)
    assert out is not None
    logger.info(
        "Recorded payment #%d for booking #%d: %s%.2f (%s, %s)",
        new_id, booking_id, CURRENCY_SYMBOL, p["amount"],
        p["method"], p["status"])
    return out


def get_payment(payment_id: int) -> Payment | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM trip_payments WHERE payment_id = ?",
            (payment_id,)).fetchone()
        return _row_payment(r) if r else None


def list_payments(
    *,
    booking_id: int | None = None,
    trip_id: int | None = None,
    student_id: str | None = None,
    method: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[Payment]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if booking_id is not None:
        clauses.append("booking_id = ?")
        args.append(booking_id)
    if trip_id is not None:
        clauses.append("booking_id IN (SELECT booking_id "
                        "  FROM trip_bookings WHERE trip_id = ?)")
        args.append(trip_id)
    if student_id:
        clauses.append("booking_id IN (SELECT booking_id "
                        "  FROM trip_bookings WHERE student_id = ?)")
        args.append(student_id.strip())
    if method:
        if method not in PAYMENT_METHODS:
            raise ValidationError(
                f"Method must be one of: {', '.join(PAYMENT_METHODS)}")
        clauses.append("method = ?")
        args.append(method)
    if status:
        if status not in PAYMENT_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(PAYMENT_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if date_from:
        clauses.append("paid_on >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("paid_on <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM trip_payments {where} "
           "ORDER BY paid_on DESC, payment_id DESC")
    with _connect() as conn:
        return [_row_payment(r)
                 for r in conn.execute(sql, args).fetchall()]


def update_payment(payment_id: int, d: dict[str, Any]) -> Payment:
    init_db()
    existing = get_payment(payment_id)
    if existing is None:
        raise ValidationError(f"No payment with id {payment_id}")
    merged = {
        "amount":      d.get("amount", existing.amount),
        "paid_on":     d.get("paid_on", existing.paid_on),
        "method":      d.get("method", existing.method),
        "status":      d.get("status", existing.status),
        "reference":   d.get("reference", existing.reference),
        "recorded_by": d.get("recorded_by", existing.recorded_by),
        "notes":       d.get("notes", existing.notes),
    }
    p = _validate_payment_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE trip_payments SET
                  amount=?, paid_on=?, method=?, status=?,
                  reference=?, recorded_by=?, notes=?,
                  updated_at=datetime('now')
               WHERE payment_id=?""",
            (p["amount"], p["paid_on"], p["method"], p["status"],
             p["reference"], p["recorded_by"], p["notes"], payment_id),
        )
        conn.commit()
    out = get_payment(payment_id)
    assert out is not None
    logger.info("Updated payment #%d", payment_id)
    return out


def delete_payment(payment_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM trip_payments WHERE payment_id = ?",
            (payment_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted payment #%d", payment_id)
            return True
        return False


# ── Derived state ────────────────────────────────────────────────

def _payment_state(booking: Booking, trip: Trip, paid: float) -> str:
    if (booking.status in ("Cancelled", "Withdrawn")
            and paid > 0):
        return "Refunded" if paid <= 0.001 else "Refunded"
    if trip.cost_per_place <= 0:
        return "Paid" if paid >= 0 else "Unpaid"
    if paid + 0.001 >= trip.cost_per_place:
        return "Paid"
    if trip.deposit > 0 and paid + 0.001 >= trip.deposit:
        return "Deposit"
    if paid > 0:
        return "Partial"
    return "Unpaid"


def view_booking(booking_id: int) -> BookingView | None:
    booking = get_booking(booking_id)
    if booking is None:
        return None
    trip = get_trip(booking.trip_id)
    if trip is None:
        return None
    paid = _paid_total(booking_id)
    from education_system.sixthform_system.modules.domain.students import students as _students
    s = _students.get_student(booking.student_id)
    name = s.full_name if s else "(unknown)"
    return BookingView(
        booking=booking, trip=trip, student_name=name,
        paid=paid,
        balance=round(trip.cost_per_place - paid, 2),
        payment_state=_payment_state(booking, trip, paid),
        payment_count=len(list_payments(booking_id=booking_id)),
    )


def list_booking_views(
    *,
    trip_id: int | None = None,
    student_id: str | None = None,
    status: str | None = None,
    active_only: bool = False,
    payment_state: str | None = None,
) -> list[BookingView]:
    bookings = list_bookings(trip_id=trip_id, student_id=student_id,
                                status=status, active_only=active_only)
    if not bookings:
        return []
        from education_system.sixthform_system.modules.domain.students import students as _students
    names = {s.student_id: s.full_name
              for s in _students.list_students()}
    trips_map: dict[int, Trip] = {}
    # Paid totals in one go.
    with _connect() as conn:
        rows = conn.execute(
            """SELECT booking_id, COALESCE(SUM(amount), 0) AS s,
                       COUNT(*) AS n
                FROM trip_payments
               WHERE status='Cleared'
               GROUP BY booking_id""").fetchall()
        paid_map = {r["booking_id"]: float(r["s"]) for r in rows}
        count_rows = conn.execute(
            """SELECT booking_id, COUNT(*) AS n
                FROM trip_payments GROUP BY booking_id""").fetchall()
        count_map = {r["booking_id"]: r["n"] for r in count_rows}
    out: list[BookingView] = []
    for b in bookings:
        trip = trips_map.get(b.trip_id) or get_trip(b.trip_id)
        if trip is None:
            continue
        trips_map[b.trip_id] = trip
        paid = round(paid_map.get(b.booking_id, 0.0), 2)
        state = _payment_state(b, trip, paid)
        if payment_state and state != payment_state:
            continue
        out.append(BookingView(
            booking=b, trip=trip,
            student_name=names.get(b.student_id, "(unknown)"),
            paid=paid,
            balance=round(trip.cost_per_place - paid, 2),
            payment_state=state,
            payment_count=count_map.get(b.booking_id, 0),
        ))
    return out


def view_trip(trip_id: int) -> TripView | None:
    trip = get_trip(trip_id)
    if trip is None:
        return None
    views = list_booking_views(trip_id=trip_id)
    confirmed = sum(1 for v in views
                      if v.booking.status == "Confirmed")
    interested = sum(1 for v in views
                       if v.booking.status == "Interested")
    waitlist = sum(1 for v in views
                     if v.booking.status == "Waitlist")
    cancelled = sum(1 for v in views
                      if v.booking.status in ("Cancelled", "Withdrawn"))
    total_active = sum(1 for v in views if v.is_active)
    cap_pct = (round(100.0 * total_active / trip.capacity, 1)
                if trip.capacity else None)
    charged = round(sum(trip.cost_per_place for v in views
                         if v.is_active), 2)
    paid = round(sum(v.paid for v in views if v.is_active), 2)
    return TripView(
        trip=trip, confirmed=confirmed, interested=interested,
        waitlist=waitlist, cancelled=cancelled,
        total_active=total_active, capacity_used_pct=cap_pct,
        total_charged=charged, total_paid=paid,
        total_balance=round(charged - paid, 2),
    )


# ── Summary ──────────────────────────────────────────────────────

@dataclass
class Summary:
    total_trips: int
    upcoming_trips: int
    open_for_booking: int
    completed: int
    cancelled: int

    total_bookings: int
    active_bookings: int
    waitlist_count: int
    consent_missing: int

    total_charged: float
    total_paid: float
    total_outstanding: float
    overdue_balance: float

    by_trip_status: dict[str, int]
    by_booking_status: dict[str, int]
    by_payment_state: dict[str, int]
    by_method: dict[str, float]
    next_trip: Trip | None
    top_trips_by_revenue: list[tuple[int, str, float]]


def summary() -> Summary:
    import datetime as _dt
    init_db()
    today = _dt.date.today().isoformat()
    trips_all = list_trips()
    by_ts = {s: 0 for s in TRIP_STATUSES}
    upcoming = 0
    for t in trips_all:
        by_ts[t.status] = by_ts.get(t.status, 0) + 1
        if t.start_date >= today and t.status != "Cancelled":
            upcoming += 1
    next_trip = next(
        (t for t in sorted(trips_all, key=lambda x: x.start_date)
         if t.start_date >= today and t.status != "Cancelled"),
        None,
    )

    views = list_booking_views()
    by_bs = {s: 0 for s in BOOKING_STATUSES}
    by_ps = {s: 0 for s in PAYMENT_STATES}
    consent_missing = 0
    charged = paid = 0.0
    overdue_bal = 0.0
    for v in views:
        by_bs[v.booking.status] = by_bs.get(v.booking.status, 0) + 1
        by_ps[v.payment_state] = by_ps.get(v.payment_state, 0) + 1
        if v.is_active:
            charged += v.trip.cost_per_place
            paid += v.paid
            if (v.trip.payment_due and v.trip.payment_due < today
                    and v.balance > 0):
                overdue_bal += v.balance
            if not v.booking.consent_received:
                consent_missing += 1

    payments = list_payments()
    by_method: dict[str, float] = {m: 0.0 for m in PAYMENT_METHODS}
    for p in payments:
        if p.status == "Cleared":
            by_method[p.method] = by_method.get(p.method, 0.0) + p.amount

    revenue_by_trip: dict[int, float] = {}
    name_by_trip: dict[int, str] = {}
    for v in views:
        if v.booking.status in ("Cancelled", "Withdrawn"):
            continue
        revenue_by_trip[v.trip.trip_id] = (
            revenue_by_trip.get(v.trip.trip_id, 0.0) + v.paid)
        name_by_trip[v.trip.trip_id] = v.trip.name
    top = sorted(revenue_by_trip.items(),
                  key=lambda kv: -kv[1])[:10]
    top_list = [(tid, name_by_trip.get(tid, "?"), round(rev, 2))
                 for tid, rev in top if rev > 0]

    return Summary(
        total_trips=len(trips_all),
        upcoming_trips=upcoming,
        open_for_booking=by_ts.get("Open for Booking", 0),
        completed=by_ts.get("Completed", 0),
        cancelled=by_ts.get("Cancelled", 0),
        total_bookings=len(views),
        active_bookings=sum(1 for v in views if v.is_active),
        waitlist_count=by_bs.get("Waitlist", 0),
        consent_missing=consent_missing,
        total_charged=round(charged, 2),
        total_paid=round(paid, 2),
        total_outstanding=round(charged - paid, 2),
        overdue_balance=round(overdue_bal, 2),
        by_trip_status=by_ts,
        by_booking_status=by_bs,
        by_payment_state=by_ps,
        by_method={k: round(v, 2) for k, v in by_method.items()},
        next_trip=next_trip,
        top_trips_by_revenue=top_list,
    )
