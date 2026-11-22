"""Trips & Payments: educational visits, places, consent and the money.

Kept from the old Trips & Payments window:

* Trips with name (now *title*), destination, start and end dates, year
  group, cost per place, deposit, capacity, payment due date, status
  (Planning, Open for Booking, Closed for Booking, Confirmed, In Progress,
  Completed, Cancelled), lead staff, description and notes.
* Bookings - one per pupil per trip - with booking date, status (Interested,
  Confirmed, Waitlist, Cancelled, Withdrawn, Attended, No-Show), consent,
  consent / medical / dietary notes and notes.
* Payments against a booking with date, amount, method, status (Cleared,
  Pending, Failed, Refunded), reference, recorded by and notes. A booking's
  payment state (Unpaid, Partial, Deposit, Paid, Refunded) is worked out from
  the cleared payments.
* The summary: trips by status, bookings, waitlist, consent missing, money
  charged / paid / outstanding / overdue, payments by method, top trips.

New:

* **Money in pence.** Every amount is a whole number of pence
  (:func:`pence` reads "12.50"; :func:`money` shows it).
* **Timings, staff and type.** Depart / return times, accompanying staff,
  the group invited, residential / overseas / adventurous flags, the
  staff:pupil ratio and :func:`ratio_check`.
* **EVC approval.** draft -> submitted -> approved / declined, decided by
  :data:`TRIP_EDITORS`. A trip needs a risk assessment (text or a file) to be
  submitted, and a reviewed one to be approved; it can't open for booking,
  run or complete until approved. Changing the dates, destination, flags or
  risk assessment after approval sends it back for approval.
* **Schedule.** A deposit with its due date, any number of instalments, and
  the final balance by the payment due date; :func:`due_by` says what should
  have been paid by a day.
* **Places.** Invite a form, year group or teaching group; capacity is held
  by Confirmed and Attended places, extra confirmations go on the waiting
  list, and a released place goes to the first pupil waiting.
* **Consent.** Yes / no, date, who gave it, medical and dietary notes; a
  pupil can't be marked as departing without consent. Consent requests are
  e-mailed through the outbox.
* **Charging policy (DfE).** A trip is a *voluntary contribution* or
  *chargeable* (chargeable needs a basis, e.g. board and lodging on a
  residential visit). No pupil can be withdrawn for not paying a voluntary
  contribution. Remissions (pupil premium, hardship ...) reduce what a family
  is asked for; refunds are recorded as their own ledger lines.
* **Arrears.** :func:`arrears` lists what is behind the schedule;
  :func:`send_reminders` e-mails families through the outbox.
* **On the day.** Departed / returned headcount (:func:`headcount`), and
  :func:`mark_attendance` puts code V (educational visit) on the registers.
* **Families and teachers.** :func:`for_family` is what the portal shows;
  :func:`trips_for_pupil`, :func:`on_trip` and the list functions are open
  to all staff.

Every change is in ``trip_audit`` and the activity log (ids only - never
names or amounts).
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime as _dt
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.pupils.domain import pupils as P  # registers the FK target
from education_system.systems.secondary.core.permissions.access import STAFF_ROLES, TRIP_EDITORS, Principal
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.core.academic_calendar.school_year import year_of
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

CURRENCY_SYMBOL = "£"
MAX_PENCE = 10_000_00 * 10      # £100,000 - a typing slip, not a trip

YEAR_GROUPS: tuple[str, ...] = ("Open", "Year 7", "Year 8", "Year 9", "Year 10", "Year 11",
                                "Mixed")
DEFAULT_YEAR_GROUP = "Open"
TRIP_STATUSES: tuple[str, ...] = (
    "Planning", "Open for Booking", "Closed for Booking", "Confirmed", "In Progress",
    "Completed", "Cancelled")
DEFAULT_TRIP_STATUS = "Planning"
OPEN_TRIP_STATUSES: tuple[str, ...] = (
    "Open for Booking", "Closed for Booking", "Confirmed", "In Progress", "Planning")
#: Statuses a trip can only reach once the EVC has approved it.
NEEDS_APPROVAL = frozenset({"Open for Booking", "Closed for Booking", "Confirmed",
                            "In Progress", "Completed"})
APPROVALS: tuple[str, ...] = ("draft", "submitted", "approved", "declined")
APPROVAL_LABELS = {"draft": "Draft", "submitted": "Submitted to EVC", "approved": "Approved",
                   "declined": "Declined"}

BOOKING_STATUSES: tuple[str, ...] = (
    "Interested", "Confirmed", "Waitlist", "Cancelled", "Withdrawn", "Attended", "No-Show")
DEFAULT_BOOKING_STATUS = "Interested"
ACTIVE_BOOKING_STATUSES: tuple[str, ...] = ("Interested", "Confirmed", "Waitlist", "Attended")
#: Statuses that hold a place (count against capacity).
PLACE_STATUSES = frozenset({"Confirmed", "Attended"})
#: Statuses a family is asked to pay for.
PAYING_STATUSES = frozenset({"Interested", "Confirmed", "Attended"})
RELEASED = frozenset({"Cancelled", "Withdrawn"})

PAYMENT_METHODS: tuple[str, ...] = (
    "Cash", "Card", "Bank Transfer", "Cheque", "Online Portal", "Bursary", "Voucher",
    "Adjustment", "Other")
DEFAULT_METHOD = "Card"
PAYMENT_STATUSES: tuple[str, ...] = ("Cleared", "Pending", "Failed", "Refunded")
DEFAULT_PAYMENT_STATUS = "Cleared"
PAYMENT_KINDS: tuple[str, ...] = ("Payment", "Refund")
PAYMENT_STATES: tuple[str, ...] = ("Unpaid", "Partial", "Deposit", "Paid", "Refunded",
                                   "Waived")

VOLUNTARY = "Voluntary contribution"
CHARGEABLE = "Chargeable"
CHARGING: tuple[str, ...] = (VOLUNTARY, CHARGEABLE)
#: What the DfE charging guidance lets a school charge for.
CHARGE_BASES: tuple[str, ...] = (
    "Board and lodging on a residential visit",
    "Optional extra mostly outside school hours",
    "Activity outside school hours not part of the curriculum",
    "Other (explained in the notes)")
REMISSION_REASONS: tuple[str, ...] = (
    "Pupil premium", "Free school meals / benefits (board and lodging remission)",
    "Hardship fund", "Bursary", "Sibling discount", "Other")
#: Words that mean "because they haven't paid" - never a reason on a
#: voluntary-contribution trip.
_NON_PAYMENT = ("non-payment", "non payment", "nonpayment", "unpaid", "not paid",
                "hasn't paid", "has not paid", "no payment", "arrears", "owes")
CONSENT_CHOICES: tuple[str, ...] = ("Yes", "No")
#: Pupils per adult when the trip doesn't set its own ratio.
DEFAULT_RATIOS = {"adventurous": 6, "overseas": 8, "residential": 8, "day": 10}
#: Fields that, changed after approval, send the trip back to the EVC.
_REAPPROVE = ("start_date", "end_date", "destination", "residential", "overseas",
              "adventurous", "ratio")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS trips (
    trip_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    title               TEXT NOT NULL,
    destination         TEXT,
    start_date          TEXT NOT NULL,
    end_date            TEXT,
    depart_time         TEXT,
    return_time         TEXT,
    leader              TEXT,
    staff               TEXT,
    year_group          TEXT NOT NULL DEFAULT 'Open',
    group_label         TEXT,
    capacity            INTEGER CHECK (capacity IS NULL OR capacity BETWEEN 0 AND 5000),
    cost_pence          INTEGER NOT NULL DEFAULT 0 CHECK (cost_pence >= 0),
    deposit_pence       INTEGER NOT NULL DEFAULT 0 CHECK (deposit_pence >= 0),
    deposit_due         TEXT,
    payment_due         TEXT,
    consent_due         TEXT,
    charging            TEXT NOT NULL DEFAULT 'Voluntary contribution'
                        CHECK (charging IN ('Voluntary contribution', 'Chargeable')),
    charge_basis        TEXT,
    residential         INTEGER NOT NULL DEFAULT 0 CHECK (residential IN (0, 1)),
    overseas            INTEGER NOT NULL DEFAULT 0 CHECK (overseas IN (0, 1)),
    adventurous         INTEGER NOT NULL DEFAULT 0 CHECK (adventurous IN (0, 1)),
    ratio               INTEGER CHECK (ratio IS NULL OR ratio BETWEEN 1 AND 50),
    status              TEXT NOT NULL DEFAULT 'Planning',
    approval            TEXT NOT NULL DEFAULT 'draft'
                        CHECK (approval IN ('draft', 'submitted', 'approved', 'declined')),
    submitted_by        TEXT,
    submitted_at        TEXT,
    approved_by         TEXT,
    approved_at         TEXT,
    approval_note       TEXT,
    risk_assessment     TEXT,
    risk_file           TEXT,
    risk_reviewed_by    TEXT,
    risk_reviewed_on    TEXT,
    description         TEXT,
    notes               TEXT,
    attendance_marked_at TEXT,
    created_by          TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by          TEXT,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_trips_start ON trips (start_date);
CREATE INDEX IF NOT EXISTS ix_trips_status ON trips (status);
CREATE TABLE IF NOT EXISTS trip_instalments (
    instalment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id        INTEGER NOT NULL REFERENCES trips (trip_id) ON DELETE CASCADE,
    label          TEXT NOT NULL,
    due_date       TEXT NOT NULL,
    amount_pence   INTEGER NOT NULL CHECK (amount_pence > 0)
);
CREATE INDEX IF NOT EXISTS ix_trip_instalments_trip ON trip_instalments (trip_id, due_date);
CREATE TABLE IF NOT EXISTS trip_bookings (
    booking_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id           INTEGER NOT NULL REFERENCES trips (trip_id) ON DELETE CASCADE,
    pupil_id          INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    booking_date      TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'Interested',
    consent           TEXT CHECK (consent IS NULL OR consent IN ('Yes', 'No')),
    consent_date      TEXT,
    consent_by        TEXT,
    consent_note      TEXT,
    medical_note      TEXT,
    dietary_note      TEXT,
    notes             TEXT,
    remission_pence   INTEGER NOT NULL DEFAULT 0 CHECK (remission_pence >= 0),
    remission_reason  TEXT,
    departed          INTEGER NOT NULL DEFAULT 0 CHECK (departed IN (0, 1)),
    departed_at       TEXT,
    returned          INTEGER NOT NULL DEFAULT 0 CHECK (returned IN (0, 1)),
    returned_at       TEXT,
    last_reminder_at  TEXT,
    created_by        TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (trip_id, pupil_id)
);
CREATE INDEX IF NOT EXISTS ix_trip_bookings_pupil ON trip_bookings (pupil_id);
CREATE INDEX IF NOT EXISTS ix_trip_bookings_status ON trip_bookings (trip_id, status);
CREATE TABLE IF NOT EXISTS trip_payments (
    payment_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id    INTEGER NOT NULL REFERENCES trip_bookings (booking_id) ON DELETE CASCADE,
    kind          TEXT NOT NULL DEFAULT 'Payment' CHECK (kind IN ('Payment', 'Refund')),
    amount_pence  INTEGER NOT NULL CHECK (amount_pence > 0),
    paid_on       TEXT NOT NULL,
    method        TEXT NOT NULL DEFAULT 'Card',
    status        TEXT NOT NULL DEFAULT 'Cleared',
    reference     TEXT,
    received_by   TEXT,
    notes         TEXT,
    created_by    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_trip_payments_booking ON trip_payments (booking_id);
CREATE INDEX IF NOT EXISTS ix_trip_payments_date ON trip_payments (paid_on);
CREATE TABLE IF NOT EXISTS trip_audit (
    audit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id     INTEGER,
    booking_id  INTEGER,
    pupil_id    INTEGER,
    action      TEXT NOT NULL,
    detail      TEXT,
    actor       TEXT NOT NULL,
    at          TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("trips", _SCHEMA)


# ── Money ────────────────────────────────────────────────────────────

def pence(value: Any, label: str = "Amount", problems: list[str] | None = None, *,
          required: bool = False, allow_zero: bool = True) -> int | None:
    """``"12.50"`` / ``"£12.50"`` / ``12`` -> 1250. Never goes through a float.
    An int is taken as pence already."""
    out = problems if problems is not None else []
    if isinstance(value, bool):
        value = None
    if isinstance(value, int):
        n = value
    else:
        text = str(value or "").strip().replace(CURRENCY_SYMBOL, "").replace(",", "")
        if not text:
            if required:
                out.append(f"{label} is required")
            if problems is None and out:
                raise ValidationError(out)
            return None
        try:
            d = Decimal(text)
        except InvalidOperation:
            out.append(f"{label} must be an amount like 12.50")
            if problems is None:
                raise ValidationError(out) from None
            return None
        if d != d.quantize(Decimal("0.01")):
            out.append(f"{label} can't have fractions of a penny")
        n = int((d * 100).to_integral_value())
    if n < 0:
        out.append(f"{label} can't be negative")
    elif n == 0 and not allow_zero:
        out.append(f"{label} must be more than {CURRENCY_SYMBOL}0.00")
    elif n > MAX_PENCE:
        out.append(f"{label} is too large")
    if problems is None and out:
        raise ValidationError(out)
    return n


def money(p: int | None) -> str:
    """1250 -> "£12.50"; -300 -> "-£3.00"."""
    if p is None:
        return "-"
    sign = "-" if p < 0 else ""
    return f"{sign}{CURRENCY_SYMBOL}{abs(p) // 100:,}.{abs(p) % 100:02d}"


def plain(p: int | None) -> str:
    """1250 -> "12.50" (form fields, CSV)."""
    if p is None:
        return ""
    sign = "-" if p < 0 else ""
    return f"{sign}{abs(p) // 100}.{abs(p) % 100:02d}"


# ── Records ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Trip:
    trip_id: int
    title: str
    destination: str | None
    start_date: str
    end_date: str | None
    depart_time: str | None
    return_time: str | None
    leader: str | None
    staff: str | None
    year_group: str
    group_label: str | None
    capacity: int | None
    cost_pence: int
    deposit_pence: int
    deposit_due: str | None
    payment_due: str | None
    consent_due: str | None
    charging: str
    charge_basis: str | None
    residential: int
    overseas: int
    adventurous: int
    ratio: int | None
    status: str
    approval: str
    submitted_by: str | None
    submitted_at: str | None
    approved_by: str | None
    approved_at: str | None
    approval_note: str | None
    risk_assessment: str | None
    risk_file: str | None
    risk_reviewed_by: str | None
    risk_reviewed_on: str | None
    description: str | None
    notes: str | None
    attendance_marked_at: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    places_taken: int = 0
    waiting: int = 0
    bookings: int = 0

    @property
    def name(self) -> str:      # the old field name
        return self.title

    @property
    def last_day(self) -> str:
        return self.end_date or self.start_date

    @property
    def is_voluntary(self) -> bool:
        return self.charging == VOLUNTARY

    @property
    def approved(self) -> bool:
        return self.approval == "approved"

    @property
    def flags(self) -> str:
        return ", ".join(n for n, v in (("residential", self.residential),
                                        ("overseas", self.overseas),
                                        ("adventurous", self.adventurous)) if v) or "day visit"

    @property
    def pupils_per_adult(self) -> int:
        if self.ratio:
            return self.ratio
        for k in ("adventurous", "overseas", "residential"):
            if getattr(self, k):
                return DEFAULT_RATIOS[k]
        return DEFAULT_RATIOS["day"]

    @property
    def staff_names(self) -> list[str]:
        names = [x.strip() for x in (self.staff or "").replace(";", ",").split(",")]
        lead = (self.leader or "").strip()
        out = [lead] if lead else []
        return out + [n for n in names if n and n.lower() != lead.lower()]

    @property
    def places_left(self) -> int | None:
        return None if self.capacity is None else max(0, self.capacity - self.places_taken)

    @property
    def period(self) -> str:
        if self.end_date and self.end_date != self.start_date:
            return f"{self.start_date} to {self.end_date}"
        return self.start_date


@dataclass(frozen=True)
class Instalment:
    instalment_id: int
    trip_id: int
    label: str
    due_date: str
    amount_pence: int


@dataclass(frozen=True)
class Booking:
    booking_id: int
    trip_id: int
    pupil_id: int
    booking_date: str
    status: str
    consent: str | None
    consent_date: str | None
    consent_by: str | None
    consent_note: str | None
    medical_note: str | None
    dietary_note: str | None
    notes: str | None
    remission_pence: int
    remission_reason: str | None
    departed: int
    departed_at: str | None
    returned: int
    returned_at: str | None
    last_reminder_at: str | None
    created_by: str | None
    created_at: str
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0
    form_group: str | None = None
    fsm_eligible: bool = False
    trip_title: str = ""
    trip_start: str = ""
    trip_status: str = ""
    charging: str = VOLUNTARY
    cost_pence: int = 0
    paid_pence: int = 0
    refunded_pence: int = 0

    @property
    def consent_received(self) -> bool:     # the old flag
        return self.consent == "Yes"

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_BOOKING_STATUSES

    @property
    def charge_pence(self) -> int:
        """What the family is asked for (cost less any remission)."""
        if self.status not in PAYING_STATUSES:
            return 0
        return max(0, self.cost_pence - self.remission_pence)

    @property
    def balance_pence(self) -> int:
        return self.charge_pence - self.paid_pence

    @property
    def payment_state(self) -> str:
        if self.status in RELEASED:
            return "Refunded" if self.refunded_pence and self.paid_pence <= 0 else (
                "Unpaid" if self.paid_pence <= 0 else "Partial")
        charge = max(0, self.cost_pence - self.remission_pence)
        if charge == 0 and self.cost_pence > 0:
            return "Waived"
        if self.paid_pence >= charge:
            return "Paid"
        if self.paid_pence <= 0:
            return "Refunded" if self.refunded_pence else "Unpaid"
        return "Partial"


@dataclass(frozen=True)
class Payment:
    payment_id: int
    booking_id: int
    kind: str
    amount_pence: int
    paid_on: str
    method: str
    status: str
    reference: str | None
    received_by: str | None
    notes: str | None
    created_by: str | None
    created_at: str
    updated_at: str
    trip_id: int = 0
    pupil_id: int = 0
    pupil_name: str = ""
    trip_title: str = ""

    @property
    def signed_pence(self) -> int:
        """Money in (+) or out (-), counting cleared lines only."""
        if self.status != "Cleared":
            return 0
        return -self.amount_pence if self.kind == "Refund" else self.amount_pence

    @property
    def recorded_by(self) -> str | None:     # the old name
        return self.received_by


_TRIP_SELECT = """
SELECT t.*,
  (SELECT COUNT(*) FROM trip_bookings b WHERE b.trip_id = t.trip_id
     AND b.status IN ('Confirmed', 'Attended')) AS places_taken,
  (SELECT COUNT(*) FROM trip_bookings b WHERE b.trip_id = t.trip_id
     AND b.status = 'Waitlist') AS waiting,
  (SELECT COUNT(*) FROM trip_bookings b WHERE b.trip_id = t.trip_id) AS bookings
FROM trips t
"""
_PAID = ("COALESCE((SELECT SUM(CASE WHEN p.kind = 'Refund' THEN -p.amount_pence "
         "ELSE p.amount_pence END) FROM trip_payments p WHERE p.booking_id = b.booking_id "
         "AND p.status = 'Cleared'), 0)")
_REFUNDED = ("COALESCE((SELECT SUM(p.amount_pence) FROM trip_payments p WHERE "
             "p.booking_id = b.booking_id AND p.status = 'Cleared' AND p.kind = 'Refund'), 0)")
_BOOKING_SELECT = f"""
SELECT b.*, p.legal_last_name, p.legal_first_name, p.preferred_name, p.admission_no,
       p.year_group AS pupil_year, p.form_group, p.fsm_eligible, t.title AS trip_title,
       t.start_date AS trip_start, t.status AS trip_status, t.charging, t.cost_pence,
       {_PAID} AS paid_pence, {_REFUNDED} AS refunded_pence
FROM trip_bookings b JOIN pupils p USING (pupil_id) JOIN trips t USING (trip_id)
"""
_PAYMENT_SELECT = """
SELECT x.*, b.trip_id, b.pupil_id, p.legal_last_name, p.legal_first_name, p.preferred_name,
       t.title AS trip_title
FROM trip_payments x JOIN trip_bookings b USING (booking_id) JOIN pupils p USING (pupil_id)
JOIN trips t ON t.trip_id = b.trip_id
"""
_TRIP_BASE = tuple(f for f in Trip.__dataclass_fields__
                   if f not in ("places_taken", "waiting", "bookings"))
_BOOKING_BASE = tuple(f for f in Booking.__dataclass_fields__ if f not in (
    "pupil_name", "admission_no", "pupil_year", "form_group", "fsm_eligible", "trip_title",
    "trip_start", "trip_status", "charging", "cost_pence", "paid_pence", "refunded_pence"))
_PAYMENT_BASE = tuple(f for f in Payment.__dataclass_fields__ if f not in (
    "trip_id", "pupil_id", "pupil_name", "trip_title"))


def _name(r) -> str:
    return f"{r['legal_last_name']}, {r['preferred_name'] or r['legal_first_name']}"


def _trip_row(r) -> Trip:
    return Trip(**{k: r[k] for k in _TRIP_BASE}, places_taken=r["places_taken"],
                waiting=r["waiting"], bookings=r["bookings"])


def _booking_row(r) -> Booking:
    return Booking(**{k: r[k] for k in _BOOKING_BASE}, pupil_name=_name(r),
                   admission_no=r["admission_no"], pupil_year=r["pupil_year"],
                   form_group=r["form_group"], fsm_eligible=bool(r["fsm_eligible"]),
                   trip_title=r["trip_title"], trip_start=r["trip_start"],
                   trip_status=r["trip_status"], charging=r["charging"],
                   cost_pence=r["cost_pence"], paid_pence=r["paid_pence"],
                   refunded_pence=r["refunded_pence"])


def _payment_row(r) -> Payment:
    return Payment(**{k: r[k] for k in _PAYMENT_BASE}, trip_id=r["trip_id"],
                   pupil_id=r["pupil_id"], pupil_name=_name(r), trip_title=r["trip_title"])


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    """The finance office / EVC: approvals, places, payments."""
    return actor.role in TRIP_EDITORS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"trips.{action}", target=target, outcome="denied", principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only staff can see trips.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only the finance office / educational visits "
                                     "coordinator can do that.")


def _me(actor: Principal) -> set[str]:
    from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
    return BH._me(actor)


def is_leader(actor: Principal, t: Trip) -> bool:
    """The trip's leader (by login, name or e-mail) or whoever set it up."""
    if actor.role not in STAFF_ROLES:
        return False
    if actor.username and (t.created_by or "").lower() == actor.username.lower():
        return True
    return bool(t.leader) and t.leader.strip().lower() in _me(actor)


def can_manage(actor: Principal, t: Trip) -> bool:
    """Change the trip's details: editors, or its leader while it's not yet
    approved."""
    return is_editor(actor) or (is_leader(actor, t) and t.approval in ("draft", "declined"))


def can_run_day(actor: Principal, t: Trip) -> bool:
    """Consent and the departure / return register: editors and the leader."""
    return is_editor(actor) or is_leader(actor, t)


def _staff_name(actor: Principal) -> str:
    from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
    return BH._staff_name(actor)


def _audit(conn, action: str, actor: Principal, *, trip_id: int | None = None,
           booking_id: int | None = None, pupil_id: int | None = None, **detail: Any) -> None:
    conn.execute("INSERT INTO trip_audit (trip_id, booking_id, pupil_id, action, detail, actor)"
                 " VALUES (?, ?, ?, ?, ?, ?)",
                 (trip_id, booking_id, pupil_id, action,
                  json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(trip_id: int | None = None, *, booking_id: int | None = None,
            pupil_id: int | None = None, limit: int = 300) -> list[dict[str, Any]]:
    sql, where, params = "SELECT * FROM trip_audit", [], []
    for col, val in (("trip_id", trip_id), ("booking_id", booking_id), ("pupil_id", pupil_id)):
        if val is not None:
            where.append(f"{col} = ?")
            params.append(int(val))
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [{"at": r["at"], "trip_id": r["trip_id"], "booking_id": r["booking_id"],
                 "pupil_id": r["pupil_id"], "action": r["action"], "actor": r["actor"],
                 "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


# ── Cleaning ─────────────────────────────────────────────────────────

def _date(value: Any, label: str, problems: list[str]) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return _dt.date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def _time(value: Any, label: str, problems: list[str]) -> str | None:
    v = str(value or "").strip()
    if not v:
        return None
    try:
        return _dt.time.fromisoformat(v).strftime("%H:%M")
    except ValueError:
        problems.append(f"{label} must be a time (HH:MM)")
        return None


def _choice(value: Any, options: tuple[str, ...], label: str, problems: list[str],
            default: str | None) -> str | None:
    v = str(value or "").strip()
    if not v:
        return default
    hit = next((o for o in options if o.lower() == v.lower()), None)
    if hit is None:
        problems.append(f"{label} must be one of {', '.join(options)}")
        return default
    return hit


def _text(value: Any, limit: int) -> str | None:
    return (str(value or "").strip()[:limit]) or None


def _flag(value: Any) -> int:
    if isinstance(value, str):
        return 1 if value.strip().lower() in ("1", "true", "yes", "y", "on") else 0
    return 1 if value else 0


def _pupil(ref: Any) -> P.Pupil | None:
    if ref in (None, ""):
        return None
    if isinstance(ref, int) or str(ref).strip().isdigit():
        return P.get_pupil(int(ref))
    return P.find_by_reference(str(ref).strip())


TRIP_FIELDS = ("title", "destination", "start_date", "end_date", "depart_time", "return_time",
               "leader", "staff", "year_group", "group_label", "capacity", "cost_pence",
               "deposit_pence", "deposit_due", "payment_due", "consent_due", "charging",
               "charge_basis", "residential", "overseas", "adventurous", "ratio", "status",
               "description", "notes")
_MONEY_KEYS = {"cost_pence": ("cost", "cost_per_place"), "deposit_pence": ("deposit",)}


def _incoming(data: dict[str, Any]) -> dict[str, Any]:
    """Accept the old names (name, cost_per_place, deposit, lead_staff_id)."""
    d = dict(data)
    if "name" in d and "title" not in d:
        d["title"] = d.pop("name")
    if "lead_staff_id" in d and "leader" not in d:
        d["leader"] = d.pop("lead_staff_id")
    for key, olds in _MONEY_KEYS.items():
        for old in olds:
            if old in d and key not in d:
                d[key] = pence(d.pop(old), key.replace("_pence", "").title())
    return d


def _clean_trip(data: dict[str, Any], current: Trip | None, schedule_total: int = 0
                ) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in TRIP_FIELDS} if current else {}
    merged.update({k: v for k, v in _incoming(data).items() if k in TRIP_FIELDS})
    out: dict[str, Any] = {}
    title = " ".join(str(merged.get("title") or "").split())
    if not title:
        problems.append("Title is required")
    out["title"] = title[:120]
    out["destination"] = _text(merged.get("destination"), 200)
    for k, label in (("start_date", "Start date"), ("end_date", "End date"),
                     ("deposit_due", "Deposit due"), ("payment_due", "Payment due"),
                     ("consent_due", "Consent due")):
        out[k] = _date(merged.get(k), label, problems)
    if out["start_date"] is None and not any(p.startswith("Start date") for p in problems):
        problems.append("Start date is required")
    s, e = out["start_date"], out["end_date"]
    if s and e and e < s:
        problems.append("End date cannot be before start date")
    for k, label in (("payment_due", "Payment due"), ("deposit_due", "Deposit due"),
                     ("consent_due", "Consent due")):
        if out[k] and s and out[k] > s:
            problems.append(f"{label} must be on or before the trip starts")
    if out["deposit_due"] and out["payment_due"] and out["deposit_due"] > out["payment_due"]:
        problems.append("The deposit can't be due after the final payment")
    out["depart_time"] = _time(merged.get("depart_time"), "Depart time", problems)
    out["return_time"] = _time(merged.get("return_time"), "Return time", problems)
    if (out["depart_time"] and out["return_time"] and (not e or e == s)
            and out["return_time"] <= out["depart_time"]):
        problems.append("A day trip must return after it departs")
    out["leader"] = _text(merged.get("leader"), 80)
    out["staff"] = _text(merged.get("staff"), 500)
    out["year_group"] = _choice(merged.get("year_group"), YEAR_GROUPS, "Year group", problems,
                                DEFAULT_YEAR_GROUP)
    out["group_label"] = _text(merged.get("group_label"), 120)
    cap = merged.get("capacity")
    if cap in (None, "") or (isinstance(cap, str) and not cap.strip()):
        out["capacity"] = None
    else:
        try:
            out["capacity"] = int(str(cap).strip())
            if not 0 <= out["capacity"] <= 5000:
                problems.append("Capacity must be 0..5000")
        except ValueError:
            problems.append("Capacity must be a whole number")
            out["capacity"] = None
    out["cost_pence"] = pence(merged.get("cost_pence"), "Cost per pupil", problems) or 0
    out["deposit_pence"] = pence(merged.get("deposit_pence"), "Deposit", problems) or 0
    if out["deposit_pence"] > out["cost_pence"]:
        problems.append("Deposit cannot exceed the cost per place")
    if out["deposit_pence"] + schedule_total > out["cost_pence"]:
        problems.append("The deposit and instalments add up to more than the cost")
    if out["deposit_pence"] and not out["deposit_due"]:
        out["deposit_due"] = out["payment_due"]
    out["charging"] = _choice(merged.get("charging"), CHARGING, "Charging", problems, VOLUNTARY)
    out["charge_basis"] = _choice(merged.get("charge_basis"), CHARGE_BASES, "Charge basis",
                                  problems, None)
    if out["charging"] == CHARGEABLE and out["cost_pence"] and not out["charge_basis"]:
        problems.append("A chargeable trip needs its basis (DfE charging policy): e.g. board "
                        "and lodging on a residential visit - otherwise ask for a voluntary "
                        "contribution")
    if out["charging"] == VOLUNTARY:
        out["charge_basis"] = None
    for k in ("residential", "overseas", "adventurous"):
        out[k] = _flag(merged.get(k))
    if out["residential"] and s and (not e or e == s):
        problems.append("A residential trip runs overnight - give an end date after the start")
    r = merged.get("ratio")
    if r in (None, "") or (isinstance(r, str) and not r.strip()):
        out["ratio"] = None
    else:
        try:
            out["ratio"] = int(str(r).strip())
            if not 1 <= out["ratio"] <= 50:
                problems.append("Ratio must be 1..50 pupils per adult")
        except ValueError:
            problems.append("Ratio must be a whole number of pupils per adult")
            out["ratio"] = None
    out["status"] = _choice(merged.get("status"), TRIP_STATUSES, "Status", problems,
                            DEFAULT_TRIP_STATUS)
    out["description"] = _text(merged.get("description"), 2000)
    out["notes"] = _text(merged.get("notes"), 4000)
    return out, problems


# ── Reading ──────────────────────────────────────────────────────────

def get(trip_id: int) -> Trip:
    with database.connect() as conn:
        r = conn.execute(_TRIP_SELECT + " WHERE t.trip_id = ?", (int(trip_id),)).fetchone()
    if r is None:
        raise NotFound(f"No trip #{trip_id}")
    return _trip_row(r)


def get_trip(trip_id: int) -> Trip | None:
    """The old lookup: None when there is no such trip."""
    try:
        return get(trip_id)
    except NotFound:
        return None


def list_trips(*, status: str | None = None, year_group: str | None = None,
               open_only: bool = False, upcoming: bool = False, approval: str | None = None,
               date_from: str | None = None, date_to: str | None = None,
               search: str | None = None, academic_year: str | None = None) -> list[Trip]:
    where, params = [], []
    for col, val in (("t.status", status), ("t.year_group", year_group),
                     ("t.approval", approval)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if open_only:
        where.append(f"t.status IN ({', '.join('?' * len(OPEN_TRIP_STATUSES))})")
        params += list(OPEN_TRIP_STATUSES)
    if upcoming:
        where.append("COALESCE(t.end_date, t.start_date) >= ? AND t.status != 'Cancelled'")
        params.append(_today().isoformat())
    if date_from:
        where.append("COALESCE(t.end_date, t.start_date) >= ?")
        params.append(date_from)
    if date_to:
        where.append("t.start_date <= ?")
        params.append(date_to)
    for term in (search or "").split():
        where.append("(t.title LIKE ? OR t.destination LIKE ? OR t.leader LIKE ?)")
        params += [f"%{term}%"] * 3
    sql = _TRIP_SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY t.start_date, t.trip_id"
    with database.connect() as conn:
        rows = [_trip_row(r) for r in conn.execute(sql, params)]
    if academic_year:
        rows = [t for t in rows if year_of(t.start_date) == academic_year]
    return rows


def list_instalments(trip_id: int) -> list[Instalment]:
    with database.connect() as conn:
        return [Instalment(**dict(r)) for r in conn.execute(
            "SELECT * FROM trip_instalments WHERE trip_id = ? ORDER BY due_date, "
            "instalment_id", (int(trip_id),))]


def schedule(trip: int | Trip) -> list[dict[str, Any]]:
    """The payment plan: deposit, instalments, then the balance by the
    payment due date. {'label', 'due', 'amount_pence', 'cumulative_pence'}."""
    t = trip if isinstance(trip, Trip) else get(trip)
    rows: list[tuple[str, str | None, int]] = []
    if t.deposit_pence:
        rows.append(("Deposit", t.deposit_due or t.payment_due, t.deposit_pence))
    rows += [(i.label, i.due_date, i.amount_pence) for i in list_instalments(t.trip_id)]
    rest = t.cost_pence - sum(a for _l, _d, a in rows)
    if rest > 0:
        rows.append(("Balance", t.payment_due or t.start_date, rest))
    rows.sort(key=lambda x: x[1] or "9999")
    out, total = [], 0
    for label, due, amount in rows:
        total += amount
        out.append({"label": label, "due": due, "amount_pence": amount,
                    "cumulative_pence": total})
    return out


def due_by(trip: int | Trip, day: _dt.date | str | None = None, *,
           remission_pence: int = 0) -> int:
    """What a family should have paid by *day* (less any remission, taken off
    the last payments first)."""
    t = trip if isinstance(trip, Trip) else get(trip)
    iso = str(day or _today().isoformat())
    scheduled = sum(x["amount_pence"] for x in schedule(t) if x["due"] and x["due"] <= iso)
    return max(0, min(scheduled, t.cost_pence - remission_pence))


def get_booking(booking_id: int) -> Booking:
    with database.connect() as conn:
        r = conn.execute(_BOOKING_SELECT + " WHERE b.booking_id = ?",
                         (int(booking_id),)).fetchone()
    if r is None:
        raise NotFound(f"No booking #{booking_id}")
    return _booking_row(r)


def list_bookings(trip_id: int | None = None, *, pupil_id: int | None = None,
                  status: str | None = None, consent_missing: bool = False,
                  payment_state: str | None = None, active_only: bool = False
                  ) -> list[Booking]:
    """Bookings (the old Bookings tab): trip, status, payment state and
    consent-missing filters."""
    where, params = [], []
    for col, val in (("b.trip_id", trip_id), ("b.pupil_id", pupil_id), ("b.status", status)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if active_only or consent_missing:
        where.append(f"b.status IN ({', '.join('?' * len(ACTIVE_BOOKING_STATUSES))})")
        params += list(ACTIVE_BOOKING_STATUSES)
    if consent_missing:
        where.append("COALESCE(b.consent, '') != 'Yes'")
    sql = _BOOKING_SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY t.start_date, p.legal_last_name COLLATE NOCASE, p.legal_first_name"
    with database.connect() as conn:
        rows = [_booking_row(r) for r in conn.execute(sql, params)]
    if payment_state:
        rows = [b for b in rows if b.payment_state == payment_state]
    return rows


def list_booking_views(trip_id: int | None = None, student_id: Any = None, **kw: Any
                       ) -> list[Booking]:
    """The old name (student_id = pupil id)."""
    return list_bookings(trip_id, pupil_id=int(student_id) if student_id else None, **kw)


def waiting_list(trip_id: int) -> list[Booking]:
    """Pupils waiting, first come first served (payment never jumps the queue)."""
    return sorted(list_bookings(trip_id, status="Waitlist"), key=lambda b: b.booking_id)


def get_payment(payment_id: int) -> Payment:
    with database.connect() as conn:
        r = conn.execute(_PAYMENT_SELECT + " WHERE x.payment_id = ?",
                         (int(payment_id),)).fetchone()
    if r is None:
        raise NotFound(f"No payment #{payment_id}")
    return _payment_row(r)


def list_payments(*, booking_id: int | None = None, trip_id: int | None = None,
                  pupil_id: int | None = None, method: str | None = None,
                  status: str | None = None, kind: str | None = None,
                  date_from: str | None = None, date_to: str | None = None) -> list[Payment]:
    """The old Payments tab filters (trip, pupil, method, status, from, to)."""
    where, params = [], []
    for col, val in (("x.booking_id", booking_id), ("b.trip_id", trip_id),
                     ("b.pupil_id", pupil_id), ("x.method", method), ("x.status", status),
                     ("x.kind", kind)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if date_from:
        where.append("x.paid_on >= ?")
        params.append(date_from)
    if date_to:
        where.append("x.paid_on <= ?")
        params.append(date_to)
    sql = _PAYMENT_SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY x.paid_on DESC, x.payment_id DESC"
    with database.connect() as conn:
        return [_payment_row(r) for r in conn.execute(sql, params)]


def trips_for_pupil(pupil_id: int) -> list[Booking]:
    """Every booking a pupil has (teachers can see this)."""
    return list_bookings(pupil_id=pupil_id)


def pupil_ledger(pupil_id: int) -> dict[str, Any]:
    """A pupil's trips money: bookings, every payment line, totals."""
    books = list_bookings(pupil_id=pupil_id)
    pays = list_payments(pupil_id=pupil_id)
    return {"bookings": books, "payments": sorted(pays, key=lambda x: (x.paid_on,
                                                                       x.payment_id)),
            "charged_pence": sum(b.charge_pence for b in books),
            "paid_pence": sum(b.paid_pence for b in books),
            "balance_pence": sum(b.balance_pence for b in books if b.is_active)}


def on_trip(day: _dt.date | str | None = None) -> list[Booking]:
    """Pupils away on a trip on *day*: departed (or holding a place before the
    register is taken) on a trip that covers the day and isn't cancelled."""
    iso = str(day or _today().isoformat())
    out = []
    for t in list_trips(date_from=iso, date_to=iso):
        if t.status == "Cancelled" or not t.approved:
            continue
        rows = list_bookings(t.trip_id)
        went = [b for b in rows if b.departed]
        out += went or [b for b in rows if b.status in PLACE_STATUSES]
    return out


def trips_led_by(actor: Principal) -> list[Trip]:
    _require_staff(actor, "list")
    return [t for t in list_trips() if is_leader(actor, t)]


# ── Trips ────────────────────────────────────────────────────────────

def _status_problems(t_status: str, approval: str) -> list[str]:
    if t_status in NEEDS_APPROVAL and approval != "approved":
        return [f"The trip must be approved by the EVC before it can be "
                f"'{t_status}'"]
    return []


def create_trip(data: dict[str, Any], *, actor: Principal) -> Trip:
    """The old New trip. Staff may propose a trip (it starts as a draft);
    the finance office sets everything."""
    _require_staff(actor, "create")
    c, problems = _clean_trip(data, None)
    if not is_editor(actor):
        c["leader"] = c["leader"] or _staff_name(actor)
    problems += _status_problems(c["status"], "draft")
    if problems:
        activity_log.record("trips.create", outcome="invalid", principal=actor,
                            problems=len(problems))
        raise ValidationError(problems)
    with database.connect() as conn:
        tid = conn.execute(
            f"INSERT INTO trips ({', '.join(TRIP_FIELDS)}, created_by, updated_by) VALUES "
            f"({', '.join('?' * len(TRIP_FIELDS))}, ?, ?)",
            (*(c[k] for k in TRIP_FIELDS), actor.username, actor.username)).lastrowid
        _audit(conn, "create", actor, trip_id=tid)
    activity_log.record("trips.create", target=f"trip:{tid}", principal=actor)
    return get(tid)


def update_trip(trip_id: int, changes: dict[str, Any], *, actor: Principal) -> Trip:
    """The old Edit trip. Changing the dates, destination, type or ratio of an
    approved trip sends it back to the EVC."""
    cur = get(trip_id)
    if not can_manage(actor, cur):
        _deny(actor, "update", f"trip:{cur.trip_id}",
              "Only the finance office, or the trip leader before approval, can change it.")
    inst = sum(i.amount_pence for i in list_instalments(cur.trip_id))
    c, problems = _clean_trip(changes, cur, inst)
    changed = [k for k in TRIP_FIELDS if c[k] != getattr(cur, k)]
    reapprove = cur.approved and any(k in changed for k in _REAPPROVE)
    approval = "submitted" if reapprove else cur.approval
    if "status" in changed:
        problems += _status_problems(c["status"], approval)
    if "status" in changed and not is_editor(actor):
        problems.append("Only the finance office changes a trip's status")
    if c["capacity"] is not None and c["capacity"] < cur.places_taken:
        problems.append(f"{cur.places_taken} places are already taken - capacity can't be "
                        "lower")
    if problems:
        raise ValidationError(problems)
    if not changed:
        return cur
    with database.connect() as conn:
        vals = {k: c[k] for k in changed}
        conn.execute("UPDATE trips SET " + ", ".join(f"{k} = ?" for k in vals)
                     + ", approval = ?, updated_by = ?, updated_at = datetime('now') "
                       "WHERE trip_id = ?",
                     (*vals.values(), approval, actor.username, cur.trip_id))
        _audit(conn, "update", actor, trip_id=cur.trip_id, fields=changed,
               reapproval=reapprove or None)
    activity_log.record("trips.update", target=f"trip:{cur.trip_id}", principal=actor,
                        fields=",".join(changed))
    return get(cur.trip_id)


def set_trip_status(trip_id: int, status: str, *, actor: Principal) -> Trip:
    """The old Change status (finance office)."""
    t = get(trip_id)
    _require_editor(actor, "status", f"trip:{t.trip_id}")
    return update_trip(t.trip_id, {"status": status}, actor=actor)


def refunds_due(trip_id: int) -> list[Booking]:
    """After a cancellation (of the trip or a place): bookings still holding money."""
    t = get(trip_id)
    return [b for b in list_bookings(trip_id) if b.paid_pence > 0 and (
        t.status == "Cancelled" or b.status in RELEASED)]


def delete_trip(trip_id: int, *, actor: Principal) -> bool:
    """The old Delete trip (bookings and payments go with it) - refused while
    money is held: cancel it and refund first."""
    t = get(trip_id)
    if not (is_editor(actor) or (is_leader(actor, t) and t.approval == "draft"
                                 and not t.bookings)):
        _deny(actor, "delete", f"trip:{t.trip_id}", "Only the finance office can delete "
                                                    "a trip.")
    held = [b for b in list_bookings(trip_id) if b.paid_pence > 0]
    if held:
        raise ValidationError([f"{len(held)} booking(s) still hold money - cancel the trip "
                               "and record the refunds first"])
    with database.connect() as conn:
        conn.execute("DELETE FROM trips WHERE trip_id = ?", (t.trip_id,))
        _audit(conn, "delete", actor, trip_id=t.trip_id)
    activity_log.record("trips.delete", target=f"trip:{t.trip_id}", principal=actor)
    return True


# ── Schedule ─────────────────────────────────────────────────────────

def add_instalment(trip_id: int, data: dict[str, Any], *, actor: Principal) -> Instalment:
    t = get(trip_id)
    if not can_manage(actor, t):
        _deny(actor, "instalment", f"trip:{t.trip_id}", "Only the finance office can change "
                                                        "the payment schedule.")
    problems: list[str] = []
    label = _text(data.get("label"), 60) or f"Instalment {len(list_instalments(trip_id)) + 1}"
    due = _date(data.get("due_date"), "Due date", problems)
    if not due and not any(p.startswith("Due date") for p in problems):
        problems.append("Due date is required")
    amount = pence(data.get("amount_pence", data.get("amount")), "Amount", problems,
                   required=True, allow_zero=False)
    if due and due > t.start_date:
        problems.append("An instalment must be due on or before the trip starts")
    if amount and t.deposit_pence + sum(i.amount_pence for i in list_instalments(trip_id)) \
            + amount > t.cost_pence:
        problems.append(f"That takes the schedule over the cost ({money(t.cost_pence)})")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        iid = conn.execute("INSERT INTO trip_instalments (trip_id, label, due_date, "
                           "amount_pence) VALUES (?, ?, ?, ?)",
                           (t.trip_id, label, due, amount)).lastrowid
        _audit(conn, "instalment", actor, trip_id=t.trip_id, instalment=iid)
    activity_log.record("trips.instalment", target=f"trip:{t.trip_id}", principal=actor)
    return next(i for i in list_instalments(trip_id) if i.instalment_id == iid)


def delete_instalment(instalment_id: int, *, actor: Principal) -> bool:
    with database.connect() as conn:
        r = conn.execute("SELECT trip_id FROM trip_instalments WHERE instalment_id = ?",
                         (int(instalment_id),)).fetchone()
    if r is None:
        raise NotFound(f"No instalment #{instalment_id}")
    t = get(r["trip_id"])
    if not can_manage(actor, t):
        _deny(actor, "instalment", f"trip:{t.trip_id}", "Only the finance office can change "
                                                        "the payment schedule.")
    with database.connect() as conn:
        conn.execute("DELETE FROM trip_instalments WHERE instalment_id = ?",
                     (int(instalment_id),))
        _audit(conn, "instalment_delete", actor, trip_id=t.trip_id,
               instalment=int(instalment_id))
    return True


# ── EVC approval and risk assessment ────────────────────────────────

def record_risk_assessment(trip_id: int, *, actor: Principal, text: str | None = None,
                           file_path: str | None = None, reviewed_by: str | None = None,
                           reviewed_on: str | None = None) -> Trip:
    """The risk assessment (text and / or the path of the uploaded file) and
    who reviewed it. A new assessment on an approved trip needs re-approval."""
    t = get(trip_id)
    if not can_manage(actor, t) and not (is_leader(actor, t)):
        _deny(actor, "risk", f"trip:{t.trip_id}", "Only the trip leader or the finance "
                                                  "office can record the risk assessment.")
    problems: list[str] = []
    body = _text(text, 20000) if text is not None else t.risk_assessment
    path = _text(file_path, 500) if file_path is not None else t.risk_file
    if path and not Path(path).expanduser().is_file():
        problems.append(f"No file at {path}")
    if not body and not path:
        problems.append("Give the risk assessment as text or the path of the file")
    who = _text(reviewed_by, 80) if reviewed_by is not None else t.risk_reviewed_by
    on = _date(reviewed_on, "Reviewed on", problems) if reviewed_on else (
        _today().isoformat() if who and reviewed_by else t.risk_reviewed_on)
    if on and on > _today().isoformat():
        problems.append("The review date can't be in the future")
    if problems:
        raise ValidationError(problems)
    changed = body != t.risk_assessment or path != t.risk_file
    approval = "submitted" if t.approved and changed else t.approval
    if changed and not reviewed_by:
        who, on = None, None        # a new assessment needs a fresh review
    with database.connect() as conn:
        conn.execute("UPDATE trips SET risk_assessment = ?, risk_file = ?, risk_reviewed_by = ?,"
                     " risk_reviewed_on = ?, approval = ?, updated_by = ?, "
                     "updated_at = datetime('now') WHERE trip_id = ?",
                     (body, path, who, on, approval, actor.username, t.trip_id))
        _audit(conn, "risk", actor, trip_id=t.trip_id, changed=changed, reviewed=bool(who))
    activity_log.record("trips.risk", target=f"trip:{t.trip_id}", principal=actor)
    return get(t.trip_id)


def approval_problems(t: Trip, *, for_approval: bool = False) -> list[str]:
    out = []
    if not t.leader:
        out.append("Name the trip leader")
    if not (t.risk_assessment or t.risk_file):
        out.append("Add the risk assessment")
    elif (for_approval or t.residential or t.overseas or t.adventurous) and not (
            t.risk_reviewed_by and t.risk_reviewed_on):
        out.append("The risk assessment must be reviewed (by whom, when)")
    if t.status == "Cancelled":
        out.append("The trip is cancelled")
    if t.start_date < _today().isoformat() and t.approval != "approved":
        out.append("The trip has already started")
    return out


def submit_for_approval(trip_id: int, *, actor: Principal, note: str | None = None) -> Trip:
    t = get(trip_id)
    if not (is_editor(actor) or is_leader(actor, t)):
        _deny(actor, "submit", f"trip:{t.trip_id}", "Only the trip leader or the finance "
                                                    "office can submit it.")
    problems = approval_problems(t)
    if t.approval == "approved":
        problems.append("Already approved")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE trips SET approval = 'submitted', submitted_by = ?, "
                     "submitted_at = datetime('now'), approval_note = COALESCE(?, approval_note)"
                     ", updated_at = datetime('now') WHERE trip_id = ?",
                     (actor.username, _text(note, 1000), t.trip_id))
        _audit(conn, "submit", actor, trip_id=t.trip_id)
    activity_log.record("trips.submit", target=f"trip:{t.trip_id}", principal=actor)
    return get(t.trip_id)


def decide_approval(trip_id: int, decision: str, *, actor: Principal,
                    note: str | None = None) -> Trip:
    """The EVC approves or declines a submitted trip (declining needs a reason)."""
    t = get(trip_id)
    _require_editor(actor, "approve", f"trip:{t.trip_id}")
    dec = str(decision or "").strip().lower()
    problems: list[str] = []
    if dec not in ("approved", "declined"):
        problems.append("Choose approved or declined")
    if t.approval != "submitted":
        problems.append("Only a submitted trip can be decided "
                        f"(this one is {APPROVAL_LABELS[t.approval].lower()})")
    if dec == "approved":
        problems += approval_problems(t, for_approval=True)
    if dec == "declined" and not (note and note.strip()):
        problems.append("Say why it is declined")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE trips SET approval = ?, approved_by = ?, approved_at = "
                     "datetime('now'), approval_note = ?, updated_at = datetime('now') "
                     "WHERE trip_id = ?",
                     (dec, actor.username, _text(note, 1000) or t.approval_note, t.trip_id))
        _audit(conn, dec, actor, trip_id=t.trip_id)
    activity_log.record(f"trips.{dec}", target=f"trip:{t.trip_id}", principal=actor)
    return get(t.trip_id)


def approve(trip_id: int, *, actor: Principal, note: str | None = None) -> Trip:
    return decide_approval(trip_id, "approved", actor=actor, note=note)


def decline(trip_id: int, *, actor: Principal, note: str) -> Trip:
    return decide_approval(trip_id, "declined", actor=actor, note=note)


def awaiting_approval() -> list[Trip]:
    return list_trips(approval="submitted")


# ── Payments ─────────────────────────────────────────────────────────

def _clean_payment(data: dict[str, Any], problems: list[str], current: Payment | None = None
                   ) -> dict[str, Any]:
    merged = {k: getattr(current, k) for k in ("amount_pence", "paid_on", "method", "status",
                                               "reference", "received_by", "notes")} \
        if current else {}
    merged.update(data)
    if "amount" in data and "amount_pence" not in data:
        merged["amount_pence"] = data["amount"]
    if "recorded_by" in data and "received_by" not in data:
        merged["received_by"] = data["recorded_by"]
    out: dict[str, Any] = {}
    out["amount_pence"] = pence(merged.get("amount_pence"), "Amount", problems, required=True,
                                allow_zero=False)
    out["paid_on"] = _date(merged.get("paid_on"), "Paid on", problems) or _today().isoformat()
    if out["paid_on"] > _today().isoformat():
        problems.append("Paid on can't be in the future")
    out["method"] = _choice(merged.get("method"), PAYMENT_METHODS, "Method", problems,
                            DEFAULT_METHOD)
    out["status"] = _choice(merged.get("status"), PAYMENT_STATUSES, "Status", problems,
                            DEFAULT_PAYMENT_STATUS)
    out["reference"] = _text(merged.get("reference"), 120)
    out["received_by"] = _text(merged.get("received_by"), 80)
    out["notes"] = _text(merged.get("notes"), 1000)
    if out["method"] in ("Cheque", "Bank Transfer", "Online Portal") and not out["reference"]:
        problems.append(f"A {out['method'].lower()} payment needs its reference")
    return out


def add_payment(booking_id: int, data: dict[str, Any], *, actor: Principal) -> Payment:
    """The old Record payment. A cleared payment can't take the booking past
    what the family is asked for."""
    b = get_booking(booking_id)
    _require_editor(actor, "payment", b.admission_no)
    problems: list[str] = []
    c = _clean_payment(data, problems)
    c["received_by"] = c["received_by"] or _staff_name(actor)
    if b.status in RELEASED:
        problems.append("The place was cancelled - record a refund instead")
    if not problems and c["status"] == "Cleared" and c["amount_pence"] > b.balance_pence:
        problems.append(f"That's more than the balance ({money(max(0, b.balance_pence))})")
    if problems:
        raise ValidationError(problems)
    return _insert_payment(b, "Payment", c, actor)


def _insert_payment(b: Booking, kind: str, c: dict[str, Any], actor: Principal) -> Payment:
    with database.connect() as conn:
        pid = conn.execute(
            "INSERT INTO trip_payments (booking_id, kind, amount_pence, paid_on, method, status,"
            " reference, received_by, notes, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (b.booking_id, kind, c["amount_pence"], c["paid_on"], c["method"], c["status"],
             c["reference"], c["received_by"], c["notes"], actor.username)).lastrowid
        _audit(conn, kind.lower(), actor, trip_id=b.trip_id, booking_id=b.booking_id,
               pupil_id=b.pupil_id, payment=pid)
    activity_log.record(f"trips.{kind.lower()}", target=b.admission_no, principal=actor,
                        trip=b.trip_id, payment=pid)
    return get_payment(pid)


def refund(booking_id: int, data: dict[str, Any], *, actor: Principal) -> Payment:
    """Money back to the family (its own line in the ledger); no more than
    has been paid. *data*: amount (blank = everything paid), method, reference,
    notes (why)."""
    b = get_booking(booking_id)
    _require_editor(actor, "refund", b.admission_no)
    problems: list[str] = []
    d = dict(data)
    if d.get("amount") in (None, "") and d.get("amount_pence") in (None, ""):
        d["amount_pence"] = b.paid_pence
    c = _clean_payment({**d, "status": "Cleared"}, problems)
    c["received_by"] = c["received_by"] or _staff_name(actor)
    if b.paid_pence <= 0:
        problems.append("Nothing has been paid on this booking")
    elif c["amount_pence"] and c["amount_pence"] > b.paid_pence:
        problems.append(f"Only {money(b.paid_pence)} has been paid")
    if not c["notes"]:
        problems.append("Say why (e.g. trip cancelled, place cancelled, overpaid)")
    if problems:
        raise ValidationError(problems)
    return _insert_payment(b, "Refund", c, actor)


def update_payment(payment_id: int, changes: dict[str, Any], *, actor: Principal) -> Payment:
    """The old Edit payment."""
    cur = get_payment(payment_id)
    b = get_booking(cur.booking_id)
    _require_editor(actor, "payment_edit", b.admission_no)
    problems: list[str] = []
    c = _clean_payment(changes, problems, cur)
    before = cur.signed_pence
    after = 0 if c["status"] != "Cleared" else (
        -c["amount_pence"] if cur.kind == "Refund" else (c["amount_pence"] or 0))
    paid_after = b.paid_pence - before + after
    if not problems and paid_after > max(0, b.cost_pence - b.remission_pence) and \
            cur.kind == "Payment" and after > before:
        problems.append("That takes the booking over what the family is asked for")
    if not problems and paid_after < 0:
        problems.append("That refunds more than was paid")
    if problems:
        raise ValidationError(problems)
    changed = [k for k, v in c.items() if v != getattr(cur, k)]
    if not changed:
        return cur
    with database.connect() as conn:
        conn.execute("UPDATE trip_payments SET " + ", ".join(f"{k} = ?" for k in changed)
                     + ", updated_at = datetime('now') WHERE payment_id = ?",
                     (*(c[k] for k in changed), cur.payment_id))
        _audit(conn, "payment_edit", actor, trip_id=b.trip_id, booking_id=b.booking_id,
               pupil_id=b.pupil_id, payment=cur.payment_id, fields=changed)
    activity_log.record("trips.payment_edit", target=b.admission_no, principal=actor,
                        payment=cur.payment_id)
    return get_payment(cur.payment_id)


def delete_payment(payment_id: int, *, actor: Principal) -> bool:
    """The old Delete payment (a mistaken entry; the audit keeps the trail)."""
    cur = get_payment(payment_id)
    b = get_booking(cur.booking_id)
    _require_editor(actor, "payment_delete", b.admission_no)
    if cur.kind == "Payment" and b.paid_pence - cur.signed_pence < 0:
        raise ValidationError(["A refund was made against this payment - delete the refund "
                               "first"])
    with database.connect() as conn:
        conn.execute("DELETE FROM trip_payments WHERE payment_id = ?", (cur.payment_id,))
        _audit(conn, "payment_delete", actor, trip_id=b.trip_id, booking_id=b.booking_id,
               pupil_id=b.pupil_id, payment=cur.payment_id, kind=cur.kind)
    activity_log.record("trips.payment_delete", target=b.admission_no, principal=actor,
                        payment=cur.payment_id)
    return True


def set_remission(booking_id: int, amount: Any, *, actor: Principal,
                  reason: str | None = None) -> Booking:
    """Reduce what a family is asked for (pupil premium, hardship, the
    remissions policy for board and lodging ...)."""
    b = get_booking(booking_id)
    _require_editor(actor, "remission", b.admission_no)
    problems: list[str] = []
    n = pence(amount, "Remission", problems) or 0
    why = _choice(reason, REMISSION_REASONS, "Reason", problems, None) if reason else None
    if n > b.cost_pence:
        problems.append(f"The remission can't be more than the cost ({money(b.cost_pence)})")
    if n and not why:
        problems.append("Choose the reason for the remission")
    if n and b.paid_pence > b.cost_pence - n:
        problems.append(f"The family has paid {money(b.paid_pence)} - refund the difference "
                        "first")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE trip_bookings SET remission_pence = ?, remission_reason = ?, "
                     "updated_at = datetime('now') WHERE booking_id = ?",
                     (n, why if n else None, b.booking_id))
        _audit(conn, "remission", actor, trip_id=b.trip_id, booking_id=b.booking_id,
               pupil_id=b.pupil_id)
    activity_log.record("trips.remission", target=b.admission_no, principal=actor,
                        trip=b.trip_id)
    return get_booking(b.booking_id)


# ── Places, consent, arrears, the day, families, summary ─────────────
# These live in trips_places / trips_ops (file size) and are part of this
# module's API: ``trips.invite(...)`` loads them on first use (PEP 562), so
# either module can be imported first.

_PARTS: dict[str, str] = {
    "_booking_status": "trips_places",
    "_booking_problems": "trips_places",
    "create_booking": "trips_places",
    "_consent_value": "trips_places",
    "invite": "trips_places",
    "update_booking": "trips_places",
    "_promote": "trips_places",
    "set_booking_status": "trips_places",
    "confirm_place": "trips_places",
    "delete_booking": "trips_places",
    "record_consent": "trips_places",
    "consent_missing": "trips_places",
    "arrears": "trips_ops",
    "_send": "trips_ops",
    "_first": "trips_ops",
    "send_reminders": "trips_ops",
    "send_consent_requests": "trips_ops",
    "ratio_check": "trips_ops",
    "_register": "trips_ops",
    "mark_departed": "trips_ops",
    "mark_returned": "trips_ops",
    "headcount": "trips_ops",
    "mark_attendance": "trips_ops",
    "readiness": "trips_ops",
    "for_family": "trips_ops",
    "summary": "trips_ops",
    "export_bookings_csv": "trips_ops",
    "export_payments_csv": "trips_ops",
}


def __getattr__(name: str) -> Any:
    part = _PARTS.get(name)
    if part is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(f"{__package__}.{part}"), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *_PARTS})
