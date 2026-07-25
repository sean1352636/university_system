"""Domain layer for Payroll & Staffing Costs (Nursery System).

Staffing is a nursery's largest cost, and the data to work it out is already in
the system — it just isn't joined up. This module owns one small table,
``staff_pay`` (the pay arrangement per staff member), and **computes**
everything else from what the rota, the absence log and the qualifications
already say:

* hours from ``rota_shifts`` (scheduled and confirmed shifts, ignoring
  cancellations),
* the split between contracted hours and **overtime** above them,
* **agency** usage, flagged on the pay record and priced at the agency rate,
* hours lost to **absence** from ``staff_absences``, and the cover cost that
  follows,
* employer **on-costs** — National Insurance and pension — on top of gross pay.

Nothing is snapshotted, so a change to next week's rota immediately moves the
forecast. ``period_cost`` prices a date range; ``forecast`` projects the coming
weeks from the rota where one exists and from contracted hours where it
doesn't.

Follows the 4-layer pattern: computation + SQLite access here, CLI in
``payroll_cli.py``, Tk GUI in ``payroll_views.py``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import random
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.nursery_system.core.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Payroll & Staffing Costs"
CATEGORY = "Staff & Ratios"

ID_PREFIX = "NPY"
ID_DIGITS = 3

PAY_TYPES = ("hourly", "salaried")
PAY_STATUSES = ("active", "ended")

# Shifts in these states count towards worked hours; 'cancelled' does not.
_WORKING_SHIFT_STATUSES = ("scheduled", "confirmed")

# Weeks a salaried annual figure is spread over when deriving an hourly rate.
WEEKS_PER_YEAR = 52.0

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


class ValidationError(ValueError):
    """Raised for invalid payroll input."""


@dataclass
class PayRecord:
    pay_id: str
    staff_id: str
    pay_type: str
    hourly_rate: float
    annual_salary: float
    contracted_hours: float
    overtime_multiplier: float
    is_agency: bool
    agency_name: str | None
    pension_percent: float
    ni_percent: float
    effective_from: str | None
    status: str
    notes: str | None
    staff_name: str | None = None
    role: str | None = None

    @property
    def effective_hourly_rate(self) -> float:
        """Hourly rate, deriving one from the salary for salaried staff."""
        if self.pay_type == "salaried" and self.contracted_hours > 0:
            weekly = self.annual_salary / WEEKS_PER_YEAR
            return round(weekly / self.contracted_hours, 4)
        return self.hourly_rate

    @property
    def overtime_rate(self) -> float:
        return round(self.effective_hourly_rate * self.overtime_multiplier, 4)

    @property
    def on_cost_percent(self) -> float:
        return self.ni_percent + self.pension_percent


@dataclass
class StaffCost:
    """One staff member's hours and cost over a period."""

    staff_id: str
    staff_name: str | None
    role: str | None
    pay: PayRecord | None
    shifts: int
    contracted_hours: float
    worked_hours: float
    absent_hours: float
    is_agency: bool

    @property
    def has_pay_record(self) -> bool:
        return self.pay is not None

    @property
    def overtime_hours(self) -> float:
        return round(max(self.worked_hours - self.contracted_hours, 0), 2)

    @property
    def basic_hours(self) -> float:
        return round(min(self.worked_hours, self.contracted_hours)
                     if self.contracted_hours else self.worked_hours, 2)

    @property
    def basic_pay(self) -> float:
        if self.pay is None:
            return 0.0
        return round(self.basic_hours * self.pay.effective_hourly_rate, 2)

    @property
    def overtime_pay(self) -> float:
        if self.pay is None:
            return 0.0
        return round(self.overtime_hours * self.pay.overtime_rate, 2)

    @property
    def gross_pay(self) -> float:
        return round(self.basic_pay + self.overtime_pay, 2)

    @property
    def ni_cost(self) -> float:
        if self.pay is None:
            return 0.0
        return round(self.gross_pay * self.pay.ni_percent / 100, 2)

    @property
    def pension_cost(self) -> float:
        if self.pay is None:
            return 0.0
        return round(self.gross_pay * self.pay.pension_percent / 100, 2)

    @property
    def total_cost(self) -> float:
        """Gross pay plus employer on-costs — what the setting actually pays."""
        return round(self.gross_pay + self.ni_cost + self.pension_cost, 2)

    @property
    def absence_cost(self) -> float:
        """What the hours lost to absence would have cost — the cover bill."""
        if self.pay is None:
            return 0.0
        return round(self.absent_hours * self.pay.effective_hourly_rate, 2)


@dataclass
class PeriodCost:
    date_from: str
    date_to: str
    staff: list[StaffCost] = field(default_factory=list)

    @property
    def worked_hours(self) -> float:
        return round(sum(s.worked_hours for s in self.staff), 2)

    @property
    def overtime_hours(self) -> float:
        return round(sum(s.overtime_hours for s in self.staff), 2)

    @property
    def absent_hours(self) -> float:
        return round(sum(s.absent_hours for s in self.staff), 2)

    @property
    def gross_pay(self) -> float:
        return round(sum(s.gross_pay for s in self.staff), 2)

    @property
    def on_costs(self) -> float:
        return round(sum(s.ni_cost + s.pension_cost for s in self.staff), 2)

    @property
    def total_cost(self) -> float:
        return round(sum(s.total_cost for s in self.staff), 2)

    @property
    def agency_cost(self) -> float:
        return round(sum(s.total_cost for s in self.staff if s.is_agency), 2)

    @property
    def overtime_cost(self) -> float:
        return round(sum(s.overtime_pay for s in self.staff), 2)

    @property
    def missing_pay_records(self) -> list[str]:
        return [s.staff_id for s in self.staff if not s.has_pay_record]


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for payroll")
        raise


# ── Validation helpers ───────────────────────────────────────────────────────

def _opt(value: Any) -> str | None:
    v = "" if value is None else str(value).strip()
    return v or None


def _today() -> str:
    return _dt.date.today().isoformat()


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "y", "yes", "true", "on")
    return bool(value)


def _check_date(value: Any, label: str, *, required: bool = True) -> str | None:
    v = _opt(value)
    if v is None:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if not _DATE_RE.match(v):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(v)
    except ValueError as e:
        raise ValidationError(f"{label} is not a real date") from e
    return v


def _number(value: Any, label: str, *, default: float = 0.0,
            minimum: float | None = 0.0) -> float:
    v = _opt(value)
    if v is None:
        return default
    try:
        out = float(v)
    except ValueError as e:
        raise ValidationError(f"{label} must be a number") from e
    if minimum is not None and out < minimum:
        raise ValidationError(f"{label} cannot be less than {minimum:g}")
    return out


def shift_hours(start_time: str | None, end_time: str | None) -> float:
    """Length of a shift in hours; 0 when either end is missing or malformed."""
    if not start_time or not end_time:
        return 0.0
    if not (_TIME_RE.match(start_time) and _TIME_RE.match(end_time)):
        return 0.0
    start = _dt.datetime.strptime(start_time, "%H:%M")
    end = _dt.datetime.strptime(end_time, "%H:%M")
    if end <= start:
        return 0.0
    return round((end - start).total_seconds() / 3600, 2)


def generate_pay_id() -> str:
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {r[0] for r in conn.execute(
                "SELECT pay_id FROM staff_pay").fetchall()}
    except sqlite3.Error:
        logger.exception("Could not read existing pay ids")
        raise
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        candidate = f"{ID_PREFIX}{n}"
        if candidate not in existing:
            return candidate
    raise RuntimeError("Could not allocate a unique pay id")


# ── Pay records ──────────────────────────────────────────────────────────────

_PAY_SELECT = """
SELECT p.*, TRIM(s.first_name || ' ' || s.last_name) AS staff_name,
       s.role AS role
FROM staff_pay p
LEFT JOIN staff s ON s.staff_id = p.staff_id
"""


def _pay_row(r: sqlite3.Row) -> PayRecord:
    keys = r.keys()
    return PayRecord(
        pay_id=r["pay_id"], staff_id=r["staff_id"], pay_type=r["pay_type"],
        hourly_rate=float(r["hourly_rate"]),
        annual_salary=float(r["annual_salary"]),
        contracted_hours=float(r["contracted_hours"]),
        overtime_multiplier=float(r["overtime_multiplier"]),
        is_agency=bool(r["is_agency"]), agency_name=r["agency_name"],
        pension_percent=float(r["pension_percent"]),
        ni_percent=float(r["ni_percent"]),
        effective_from=r["effective_from"], status=r["status"],
        notes=r["notes"],
        staff_name=r["staff_name"] if "staff_name" in keys else None,
        role=r["role"] if "role" in keys else None,
    )


def list_pay_records(*, status: str | None = None) -> list[PayRecord]:
    _ensure_schema()
    sql = _PAY_SELECT
    params: tuple[Any, ...] = ()
    if status:
        sql += " WHERE p.status = ?"
        params = (status,)
    sql += " ORDER BY staff_name"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_pay_records failed")
        raise
    return [_pay_row(r) for r in rows]


def get_pay_record(staff_id: str) -> PayRecord | None:
    """The pay arrangement for a staff member (one live record each)."""
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(_PAY_SELECT + " WHERE p.staff_id = ?",
                               (staff_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_pay_record(%s) failed", staff_id)
        raise
    return _pay_row(row) if row else None


def _validate_pay(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pay_type = str(data.get("pay_type") or "hourly").strip().lower()
    if pay_type not in PAY_TYPES:
        raise ValidationError("Pay type must be one of: " + ", ".join(PAY_TYPES))
    out["pay_type"] = pay_type
    out["hourly_rate"] = _number(data.get("hourly_rate"), "Hourly rate")
    out["annual_salary"] = _number(data.get("annual_salary"), "Annual salary")
    out["contracted_hours"] = _number(data.get("contracted_hours"),
                                      "Contracted hours")
    if out["contracted_hours"] > 168:
        raise ValidationError("Contracted hours cannot exceed 168 in a week")
    out["overtime_multiplier"] = _number(data.get("overtime_multiplier"),
                                         "Overtime multiplier", default=1.5,
                                         minimum=1.0)
    out["is_agency"] = _as_bool(data.get("is_agency"))
    out["agency_name"] = _opt(data.get("agency_name"))
    if out["is_agency"] and not out["agency_name"]:
        raise ValidationError("Give the agency's name for agency staff")
    out["pension_percent"] = _number(data.get("pension_percent"),
                                     "Pension %", default=3.0)
    out["ni_percent"] = _number(data.get("ni_percent"), "NI %", default=13.8)

    if pay_type == "hourly" and out["hourly_rate"] <= 0:
        raise ValidationError("An hourly rate is required for hourly staff")
    if pay_type == "salaried":
        if out["annual_salary"] <= 0:
            raise ValidationError("An annual salary is required for salaried "
                                  "staff")
        if out["contracted_hours"] <= 0:
            raise ValidationError(
                "Salaried staff need contracted hours so an hourly rate can be "
                "derived")

    out["effective_from"] = _check_date(
        data.get("effective_from") or _today(), "Effective from")
    status = str(data.get("status") or "active").strip().lower()
    if status not in PAY_STATUSES:
        raise ValidationError("Status must be one of: " + ", ".join(PAY_STATUSES))
    out["status"] = status
    out["notes"] = _opt(data.get("notes"))
    return out


def set_pay(staff_id: str, data: dict[str, Any]) -> PayRecord:
    """Create or replace a staff member's pay arrangement."""
    _ensure_schema()
    sid = _opt(staff_id)
    if not sid:
        raise ValidationError("Staff ID is required")
    payload = _validate_pay(data)
    existing = get_pay_record(sid)
    pay_id = existing.pay_id if existing else generate_pay_id()
    try:
        with connect() as conn:
            if not conn.execute("SELECT 1 FROM staff WHERE staff_id = ?",
                                (sid,)).fetchone():
                raise ValidationError(f"No staff member with id {sid}")
            if existing:
                conn.execute(
                    """
                    UPDATE staff_pay SET
                        pay_type = ?, hourly_rate = ?, annual_salary = ?,
                        contracted_hours = ?, overtime_multiplier = ?,
                        is_agency = ?, agency_name = ?, pension_percent = ?,
                        ni_percent = ?, effective_from = ?, status = ?, notes = ?
                    WHERE staff_id = ?
                    """,
                    (payload["pay_type"], payload["hourly_rate"],
                     payload["annual_salary"], payload["contracted_hours"],
                     payload["overtime_multiplier"], int(payload["is_agency"]),
                     payload["agency_name"], payload["pension_percent"],
                     payload["ni_percent"], payload["effective_from"],
                     payload["status"], payload["notes"], sid))
            else:
                conn.execute(
                    """
                    INSERT INTO staff_pay (
                        pay_id, staff_id, pay_type, hourly_rate, annual_salary,
                        contracted_hours, overtime_multiplier, is_agency,
                        agency_name, pension_percent, ni_percent,
                        effective_from, status, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (pay_id, sid, payload["pay_type"], payload["hourly_rate"],
                     payload["annual_salary"], payload["contracted_hours"],
                     payload["overtime_multiplier"], int(payload["is_agency"]),
                     payload["agency_name"], payload["pension_percent"],
                     payload["ni_percent"], payload["effective_from"],
                     payload["status"], payload["notes"]))
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("Could not save pay record for %s", sid)
        raise ValidationError(f"Could not save pay record — {e}") from e
    out = get_pay_record(sid)
    assert out is not None
    logger.info("Saved pay record for staff %s (%s)", sid, payload["pay_type"])
    return out


def delete_pay_record(staff_id: str) -> bool:
    _ensure_schema()
    try:
        with connect() as conn:
            cur = conn.execute("DELETE FROM staff_pay WHERE staff_id = ?",
                               (staff_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting pay record for %s", staff_id)
        raise
    if deleted:
        logger.info("Deleted pay record for staff %s", staff_id)
    return deleted


def staff_without_pay() -> list[tuple[str, str]]:
    """Employed staff with no pay arrangement — every cost figure understates."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, TRIM(first_name || ' ' || last_name) "
                "FROM staff WHERE (end_date IS NULL OR end_date = '') "
                "AND staff_id NOT IN (SELECT staff_id FROM staff_pay) "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("staff_without_pay failed")
        raise
    return [(r[0], r[1]) for r in rows]


# ── Hours from the rota and the absence log ──────────────────────────────────

def rota_hours(date_from: str, date_to: str) -> dict[str, tuple[int, float]]:
    """``staff_id -> (shift count, hours)`` from the rota over a date range."""
    _ensure_schema()
    marks = ", ".join("?" * len(_WORKING_SHIFT_STATUSES))
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, start_time, end_time FROM rota_shifts "
                "WHERE shift_date >= ? AND shift_date <= ? "
                f"AND status IN ({marks})",  # noqa: S608 — fixed-length marks
                (date_from, date_to, *_WORKING_SHIFT_STATUSES)).fetchall()
    except sqlite3.Error:
        logger.exception("rota_hours failed")
        raise
    out: dict[str, tuple[int, float]] = {}
    for r in rows:
        count, hours = out.get(r["staff_id"], (0, 0.0))
        out[r["staff_id"]] = (count + 1,
                              round(hours + shift_hours(r["start_time"],
                                                        r["end_time"]), 2))
    return out


def absence_hours(date_from: str, date_to: str) -> dict[str, float]:
    """``staff_id -> hours lost`` to absence, priced off the rota it displaced.

    Reads the Staff Absence module's own database, which is optional — a
    missing table means "nobody was off", not an error.
    """
    try:
        from education_system.nursery_system.modules.domain.staff_absence import (
            staff_absence as _absence,
        )
        absences = _absence.list_absences()
    except Exception:  # noqa: BLE001 — module or table missing
        logger.debug("Staff absence data unavailable for payroll",
                     exc_info=True)
        return {}

    windows: dict[str, list[tuple[str, str]]] = {}
    for a in absences:
        start = a.absence_date
        end = a.actual_return or a.expected_return or date_to
        if end < date_from or start > date_to:
            continue
        windows.setdefault(a.staff_id, []).append(
            (max(start, date_from), min(end, date_to)))
    if not windows:
        return {}

    _ensure_schema()
    marks = ", ".join("?" * len(_WORKING_SHIFT_STATUSES))
    out: dict[str, float] = {}
    try:
        with connect() as conn:
            for staff_id, spans in windows.items():
                total = 0.0
                for start, end in spans:
                    rows = conn.execute(
                        "SELECT start_time, end_time FROM rota_shifts "
                        "WHERE staff_id = ? AND shift_date >= ? "
                        f"AND shift_date <= ? AND status IN ({marks})",  # noqa: S608
                        (staff_id, start, end, *_WORKING_SHIFT_STATUSES)
                    ).fetchall()
                    total += sum(shift_hours(r["start_time"], r["end_time"])
                                 for r in rows)
                if total:
                    out[staff_id] = round(total, 2)
    except sqlite3.Error:
        logger.exception("absence_hours failed")
        raise
    return out


def _employed_staff() -> dict[str, tuple[str, str | None]]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, TRIM(first_name || ' ' || last_name) AS name, "
                "role FROM staff WHERE end_date IS NULL OR end_date = ''"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("_employed_staff failed")
        raise
    return {r["staff_id"]: (r["name"], r["role"]) for r in rows}


def _weeks_between(date_from: str, date_to: str) -> float:
    days = (_dt.date.fromisoformat(date_to)
            - _dt.date.fromisoformat(date_from)).days + 1
    return max(days / 7, 0.0)


# ── The costed period ────────────────────────────────────────────────────────

def period_cost(date_from: str, date_to: str, *,
                fall_back_to_contract: bool = False) -> PeriodCost:
    """Hours and cost for every employed staff member over a date range.

    ``fall_back_to_contract`` prices staff who have no rota entries at their
    contracted hours instead of zero — which is what a forecast wants, and what
    an actual-hours payroll run does not.
    """
    start = _check_date(date_from, "From date")
    end = _check_date(date_to, "To date")
    assert start is not None and end is not None
    if end < start:
        raise ValidationError("'To date' cannot be before 'from date'")

    staff = _employed_staff()
    rota = rota_hours(start, end)
    absent = absence_hours(start, end)
    pay_records = {p.staff_id: p for p in list_pay_records(status="active")}
    weeks = _weeks_between(start, end)

    rows: list[StaffCost] = []
    for staff_id, (name, role) in sorted(staff.items(),
                                         key=lambda kv: kv[1][0]):
        pay = pay_records.get(staff_id)
        shifts, worked = rota.get(staff_id, (0, 0.0))
        contracted = round((pay.contracted_hours if pay else 0.0) * weeks, 2)
        if fall_back_to_contract and shifts == 0 and contracted:
            worked = contracted
        rows.append(StaffCost(
            staff_id=staff_id, staff_name=name, role=role, pay=pay,
            shifts=shifts, contracted_hours=contracted, worked_hours=worked,
            absent_hours=absent.get(staff_id, 0.0),
            is_agency=bool(pay and pay.is_agency),
        ))
    return PeriodCost(date_from=start, date_to=end, staff=rows)


def week_cost(week_start: str) -> PeriodCost:
    """Cost for the seven days starting ``week_start``."""
    start = _check_date(week_start, "Week start")
    assert start is not None
    end = (_dt.date.fromisoformat(start) + _dt.timedelta(days=6)).isoformat()
    return period_cost(start, end)


def month_cost(year: int, month: int) -> PeriodCost:
    """Cost for a calendar month."""
    try:
        first = _dt.date(year, month, 1)
    except ValueError as e:
        raise ValidationError("Not a real year and month") from e
    last_day = (_dt.date(year + (month == 12), month % 12 + 1, 1)
                - _dt.timedelta(days=1))
    return period_cost(first.isoformat(), last_day.isoformat())


def forecast(weeks: int = 4, *, start_day: str | None = None
             ) -> list[PeriodCost]:
    """Project staffing cost week by week from the rota, then the contract.

    Weeks the rota already covers are priced from it; beyond that, staff are
    priced at their contracted hours, which is the best available estimate.
    """
    if weeks <= 0:
        raise ValidationError("Forecast must cover at least one week")
    if weeks > 52:
        raise ValidationError("Forecast cannot exceed 52 weeks")
    start = _check_date(start_day or _today(), "Start day")
    assert start is not None
    base = _dt.date.fromisoformat(start)
    out: list[PeriodCost] = []
    for i in range(weeks):
        week_start = (base + _dt.timedelta(days=7 * i)).isoformat()
        week_end = (base + _dt.timedelta(days=7 * i + 6)).isoformat()
        out.append(period_cost(week_start, week_end,
                               fall_back_to_contract=True))
    return out


def forecast_total(weeks: int = 4, *, start_day: str | None = None
                   ) -> dict[str, Any]:
    """Headline numbers for a multi-week staffing-cost projection."""
    periods = forecast(weeks, start_day=start_day)
    total = round(sum(p.total_cost for p in periods), 2)
    return {
        "weeks": len(periods),
        "from": periods[0].date_from if periods else None,
        "to": periods[-1].date_to if periods else None,
        "total_cost": total,
        "average_weekly_cost": round(total / len(periods), 2) if periods else 0.0,
        "gross_pay": round(sum(p.gross_pay for p in periods), 2),
        "on_costs": round(sum(p.on_costs for p in periods), 2),
        "overtime_cost": round(sum(p.overtime_cost for p in periods), 2),
        "agency_cost": round(sum(p.agency_cost for p in periods), 2),
        "worked_hours": round(sum(p.worked_hours for p in periods), 2),
        "weekly": [{"from": p.date_from, "to": p.date_to,
                    "hours": p.worked_hours, "cost": p.total_cost}
                   for p in periods],
    }


# ── Pickers / summary ────────────────────────────────────────────────────────

def list_staff_choices() -> list[tuple[str, str]]:
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name, role FROM staff "
                "WHERE end_date IS NULL OR end_date = '' "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_staff_choices failed")
        raise
    return [(r["staff_id"],
             f"{r['first_name']} {r['last_name']} ({r['staff_id']})"
             + (f" — {r['role']}" if r["role"] else ""))
            for r in rows]


def summary(*, on_day: str | None = None) -> dict[str, Any]:
    """Headline numbers for the payroll board — this week and the next four."""
    day = _check_date(on_day or _today(), "Date")
    assert day is not None
    monday = (_dt.date.fromisoformat(day)
              - _dt.timedelta(days=_dt.date.fromisoformat(day).weekday()))
    this_week = week_cost(monday.isoformat())
    ahead = forecast_total(4, start_day=(monday
                                         + _dt.timedelta(days=7)).isoformat())
    records = list_pay_records()
    return {
        "week_start": this_week.date_from,
        "staff_on_payroll": sum(1 for r in records if r.status == "active"),
        "agency_staff": sum(1 for r in records if r.is_agency),
        "missing_pay_records": len(staff_without_pay()),
        "week_hours": this_week.worked_hours,
        "week_overtime_hours": this_week.overtime_hours,
        "week_absent_hours": this_week.absent_hours,
        "week_gross": this_week.gross_pay,
        "week_on_costs": this_week.on_costs,
        "week_total": this_week.total_cost,
        "week_agency_cost": this_week.agency_cost,
        "week_overtime_cost": this_week.overtime_cost,
        "forecast_4_weeks": ahead["total_cost"],
        "forecast_weekly_average": ahead["average_weekly_cost"],
    }
