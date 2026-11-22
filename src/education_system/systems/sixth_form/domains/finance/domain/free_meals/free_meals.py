"""16-19 free meals in further education, for the Sixth Form System.

Three tables:

* ``free_meal_entitlements`` — one row per learner entitlement: the
  eligibility basis, the evidence seen and who verified it, start / end
  dates and the daily allowance (the value of one meal).
* ``free_meal_usage`` — the daily log: for each entitled learner on each
  college day, was the meal taken or not. ``(student_id, meal_date)``
  is unique, so re-recording a day corrects it rather than doubling it.
* ``free_meal_settings`` — college-wide settings (the default daily
  allowance).

The monthly claim report (:func:`monthly_claim`) totals, per learner,
the eligible college days in a month, the days a meal was taken and not
taken, the days nobody recorded, and the value claimed (meals taken x
allowance) — the figures the free-meals return and the catering
reconciliation need.

Free meals are an entitlement, not a reward: nothing here is ever held
on attendance grounds (see ``attendance_bursary.NEVER_HELD``).
"""

from __future__ import annotations

import csv
import datetime as _dt
import logging
from education_system.systems.sixth_form.infrastructure import database as db
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.domains.finance.domain import (
    finance_calendar as fc,
)

logger = logging.getLogger(__name__)

# ``None`` means "wherever the bursary store is" (sixthform.db in
# production): free meals are part of the 16-19 support fund and share
# its database, and a test that redirects bursaries redirects this too.
DB_PATH: Any = None

CURRENCY_SYMBOL: str = "£"

# Qualifying grounds for free meals in further education. CHECK THESE
# AGAINST THE CURRENT ESFA "Free meals in further education funded
# institutions" guide each year — the benefits and income thresholds
# are set there and change.
ELIGIBILITY_BASES: tuple[str, ...] = (
    "Universal Credit (household income under the threshold)",
    "Income Support",
    "Income-based Jobseeker's Allowance",
    "Income-related Employment and Support Allowance",
    "Child Tax Credit (not Working Tax Credit, under the threshold)",
    "Guarantee element of Pension Credit",
    "Support under Part VI of the Immigration and Asylum Act 1999",
    "No recourse to public funds (extended eligibility)",
    "Learner receives a qualifying benefit in own right",
    "Other (recorded in notes)",
)

EVIDENCE_TYPES: tuple[str, ...] = (
    "Benefit award letter",
    "Universal Credit statement",
    "Eligibility checking service result",
    "Local authority confirmation",
    "Home Office / NRPF confirmation",
    "Other",
)

ENTITLEMENT_STATUSES: tuple[str, ...] = ("Active", "Suspended", "Ended")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS free_meal_entitlements (
    entitlement_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id           TEXT NOT NULL,
    academic_year        TEXT,
    eligibility_basis    TEXT NOT NULL,
    evidence_type        TEXT,
    evidence_reference   TEXT,
    evidence_verified_by TEXT,
    evidence_verified_on TEXT,
    start_date           TEXT NOT NULL,
    end_date             TEXT,
    daily_allowance      REAL NOT NULL,
    status               TEXT NOT NULL DEFAULT 'Active',
    notes                TEXT,
    created_at           TEXT DEFAULT (datetime('now')),
    updated_at           TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS free_meal_usage (
    usage_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    entitlement_id  INTEGER NOT NULL,
    student_id      TEXT NOT NULL,
    meal_date       TEXT NOT NULL,
    taken           INTEGER NOT NULL,
    amount          REAL NOT NULL DEFAULT 0,
    recorded_by     TEXT,
    note            TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE (student_id, meal_date),
    FOREIGN KEY (entitlement_id)
        REFERENCES free_meal_entitlements(entitlement_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS free_meal_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_by TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_fme_student ON free_meal_entitlements(student_id);
CREATE INDEX IF NOT EXISTS idx_fmu_date    ON free_meal_usage(meal_date);
CREATE INDEX IF NOT EXISTS idx_fmu_ent     ON free_meal_usage(entitlement_id);
"""


class ValidationError(ValueError):
    pass


@dataclass
class Entitlement:
    entitlement_id: int
    student_id: str
    academic_year: str | None
    eligibility_basis: str
    evidence_type: str | None
    evidence_reference: str | None
    evidence_verified_by: str | None
    evidence_verified_on: str | None
    start_date: str
    end_date: str | None
    daily_allowance: float
    status: str
    notes: str | None
    created_at: str | None

    def covers(self, date: str) -> bool:
        if self.status != "Active":
            return False
        if date < self.start_date:
            return False
        return self.end_date is None or date <= self.end_date

    @property
    def evidence_verified(self) -> bool:
        return bool(self.evidence_verified_by)


@dataclass
class Usage:
    usage_id: int
    entitlement_id: int
    student_id: str
    meal_date: str
    taken: bool
    amount: float
    recorded_by: str | None
    note: str | None


@dataclass
class ClaimLine:
    student_id: str
    student_name: str
    entitlement_id: int
    daily_allowance: float
    eligible_days: int
    taken_days: int
    not_taken_days: int
    unrecorded_days: int
    value_claimed: float


@dataclass
class ClaimReport:
    month: str
    date_from: str
    date_to: str
    lines: list[ClaimLine] = field(default_factory=list)

    @property
    def learners(self) -> int:
        return len(self.lines)

    @property
    def meals_taken(self) -> int:
        return sum(l.taken_days for l in self.lines)

    @property
    def eligible_days(self) -> int:
        return sum(l.eligible_days for l in self.lines)

    @property
    def unrecorded_days(self) -> int:
        return sum(l.unrecorded_days for l in self.lines)

    @property
    def total_claimed(self) -> float:
        return round(sum(l.value_claimed for l in self.lines), 2)

    @property
    def take_up_pct(self) -> float | None:
        recorded = sum(l.taken_days + l.not_taken_days for l in self.lines)
        return (round(100.0 * self.meals_taken / recorded, 1)
                if recorded else None)


# ── DB plumbing ────────────────────────────────────────────────────

def _path() -> str:
    if DB_PATH:
        return str(DB_PATH)
    from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
        bursaries,
    )
    return str(bursaries.DB_PATH)


def _connect() -> db.Connection:
    paths.ensure_sixth_form_directories()
    conn = db.connect(_path())
    conn.row_factory = db.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_READY: set[str] = set()


def init_db() -> None:
    key = _path()
    if key in _READY:
        return
    from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
        bursaries,
    )
    if key == str(bursaries.DB_PATH):
        # Same database as the bursary store: let it build students/staff.
        bursaries.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _READY.add(key)


def _row_ent(r: db.Row) -> Entitlement:
    return Entitlement(
        entitlement_id=r["entitlement_id"], student_id=r["student_id"],
        academic_year=r["academic_year"],
        eligibility_basis=r["eligibility_basis"],
        evidence_type=r["evidence_type"],
        evidence_reference=r["evidence_reference"],
        evidence_verified_by=r["evidence_verified_by"],
        evidence_verified_on=r["evidence_verified_on"],
        start_date=r["start_date"], end_date=r["end_date"],
        daily_allowance=r["daily_allowance"], status=r["status"],
        notes=r["notes"], created_at=r["created_at"])


def _row_use(r: db.Row) -> Usage:
    return Usage(usage_id=r["usage_id"], entitlement_id=r["entitlement_id"],
                 student_id=r["student_id"], meal_date=r["meal_date"],
                 taken=bool(r["taken"]), amount=r["amount"],
                 recorded_by=r["recorded_by"], note=r["note"])


# ── Validation ────────────────────────────────────────────────────

def _date(v: Any, label: str, *, required: bool = False) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    try:
        return _dt.date.fromisoformat(str(v).strip()).isoformat()
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD") from None


def _money(v: Any, label: str) -> float:
    try:
        d = Decimal(str(v))
    except (InvalidOperation, TypeError):
        raise ValidationError(f"{label} must be a number") from None
    if d <= 0:
        raise ValidationError(f"{label} must be more than zero")
    if d > 50:
        raise ValidationError(f"{label} looks wrong (over £50 a day)")
    return float(d.quantize(Decimal("0.01")))


def _student(v: Any) -> str:
    sid = (v or "").strip() if isinstance(v, str) else ""
    if not sid:
        raise ValidationError("Student ID is required")
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


# ── Settings ───────────────────────────────────────────────────────

def get_default_allowance() -> float | None:
    """The college's daily free-meal allowance, or None until it is set.

    Deliberately not shipped with a figure: the ESFA sets the funding
    rate, and the college sets its own allowance from it.
    """
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT value FROM free_meal_settings "
                         "WHERE key = 'daily_allowance'").fetchone()
    return float(r["value"]) if r and r["value"] else None


def set_default_allowance(amount: float, *, by: str) -> float:
    init_db()
    if not (by or "").strip():
        raise ValidationError("Changing the allowance must name who did it")
    value = _money(amount, "Daily allowance")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO free_meal_settings (key, value, updated_by)
               VALUES ('daily_allowance', ?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                   updated_by = excluded.updated_by,
                   updated_at = datetime('now')""",
            (str(value), by.strip()))
        conn.commit()
    logger.info("Free-meal daily allowance set to %.2f by %s", value, by)
    return value


# ── Entitlements ──────────────────────────────────────────────────

def create_entitlement(d: dict[str, Any]) -> Entitlement:
    """Record a learner's free-meal entitlement."""
    init_db()
    sid = _student(d.get("student_id"))
    basis = (d.get("eligibility_basis") or "").strip()
    if basis not in ELIGIBILITY_BASES:
        raise ValidationError(
            "Eligibility basis must be one of: " + "; ".join(ELIGIBILITY_BASES))
    ev_type = (d.get("evidence_type") or "").strip() or None
    if ev_type and ev_type not in EVIDENCE_TYPES:
        raise ValidationError(
            f"Evidence type must be one of: {', '.join(EVIDENCE_TYPES)}")
    start = _date(d.get("start_date") or _dt.date.today().isoformat(),
                  "Start date", required=True)
    assert start is not None
    end = _date(d.get("end_date"), "End date")
    year = fc.normalise_year(d.get("academic_year") or fc.academic_year_for(
        start))
    if not end:
        end = fc.year_bounds(year)[1]
    if end < start:
        raise ValidationError("End date cannot be before start date")
    allowance = d.get("daily_allowance")
    if allowance in (None, ""):
        allowance = get_default_allowance()
        if allowance is None:
            raise ValidationError(
                "Set the college's daily free-meal allowance first, or give "
                "this entitlement its own")
    value = _money(allowance, "Daily allowance")
    verified_by = (d.get("evidence_verified_by") or "").strip() or None
    verified_on = _date(d.get("evidence_verified_on"), "Verified on") or (
        _dt.date.today().isoformat() if verified_by else None)
    with _connect() as conn:
        overlap = conn.execute(
            """SELECT entitlement_id FROM free_meal_entitlements
                WHERE student_id = ? AND status = 'Active'
                  AND start_date <= ? AND COALESCE(end_date, '9999') >= ?""",
            (sid, end, start)).fetchone()
        if overlap:
            raise ValidationError(
                f"{sid} already has an active entitlement "
                f"(#{overlap['entitlement_id']}) over those dates")
        cur = conn.execute(
            """INSERT INTO free_meal_entitlements
                   (student_id, academic_year, eligibility_basis,
                    evidence_type, evidence_reference, evidence_verified_by,
                    evidence_verified_on, start_date, end_date,
                    daily_allowance, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?)""",
            (sid, year, basis, ev_type,
             (d.get("evidence_reference") or "").strip() or None,
             verified_by, verified_on, start, end, value,
             (d.get("notes") or "").strip() or None))
        conn.commit()
        new_id = int(cur.lastrowid)
    logger.info("Free-meal entitlement #%d for %s from %s", new_id, sid,
                start)
    out = get_entitlement(new_id)
    assert out is not None
    return out


def get_entitlement(entitlement_id: int) -> Entitlement | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM free_meal_entitlements WHERE entitlement_id = ?",
            (entitlement_id,)).fetchone()
    return _row_ent(r) if r else None


def list_entitlements(*, student_id: str | None = None,
                      active_on: str | None = None,
                      academic_year: str | None = None,
                      status: str | None = None) -> list[Entitlement]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if academic_year:
        clauses.append("academic_year = ?")
        args.append(fc.normalise_year(academic_year))
    if status:
        if status not in ENTITLEMENT_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(ENTITLEMENT_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM free_meal_entitlements {where} "
            "ORDER BY student_id, start_date", args).fetchall()
    out = [_row_ent(r) for r in rows]
    if active_on:
        day = _date(active_on, "Date", required=True)
        assert day is not None
        out = [e for e in out if e.covers(day)]
    return out


def update_entitlement(entitlement_id: int,
                       d: dict[str, Any]) -> Entitlement:
    """Change evidence, dates, allowance, status or notes."""
    existing = get_entitlement(entitlement_id)
    if existing is None:
        raise ValidationError(f"No entitlement #{entitlement_id}")
    merged = {**vars(existing), **{k: v for k, v in d.items()
                                   if k in vars(existing)}}
    if merged["eligibility_basis"] not in ELIGIBILITY_BASES:
        raise ValidationError("Unknown eligibility basis")
    if merged["evidence_type"] and \
            merged["evidence_type"] not in EVIDENCE_TYPES:
        raise ValidationError("Unknown evidence type")
    if merged["status"] not in ENTITLEMENT_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(ENTITLEMENT_STATUSES)}")
    start = _date(merged["start_date"], "Start date", required=True)
    end = _date(merged["end_date"], "End date")
    if end and start and end < start:
        raise ValidationError("End date cannot be before start date")
    allowance = _money(merged["daily_allowance"], "Daily allowance")
    if merged["evidence_verified_by"] and not merged["evidence_verified_on"]:
        merged["evidence_verified_on"] = _dt.date.today().isoformat()
    with _connect() as conn:
        conn.execute(
            """UPDATE free_meal_entitlements SET eligibility_basis=?,
                   evidence_type=?, evidence_reference=?,
                   evidence_verified_by=?, evidence_verified_on=?,
                   start_date=?, end_date=?, daily_allowance=?, status=?,
                   notes=?, updated_at=datetime('now')
               WHERE entitlement_id=?""",
            (merged["eligibility_basis"], merged["evidence_type"] or None,
             merged["evidence_reference"] or None,
             (merged["evidence_verified_by"] or "").strip() or None,
             merged["evidence_verified_on"] or None, start, end, allowance,
             merged["status"], merged["notes"] or None, entitlement_id))
        conn.commit()
    out = get_entitlement(entitlement_id)
    assert out is not None
    return out


def verify_evidence(entitlement_id: int, *, verified_by: str,
                    evidence_type: str,
                    reference: str | None = None) -> Entitlement:
    if not (verified_by or "").strip():
        raise ValidationError("Evidence must be verified by a named person")
    return update_entitlement(entitlement_id, {
        "evidence_type": evidence_type,
        "evidence_reference": reference,
        "evidence_verified_by": verified_by.strip(),
        "evidence_verified_on": _dt.date.today().isoformat(),
    })


def end_entitlement(entitlement_id: int, *, on: str | None = None,
                    reason: str | None = None) -> Entitlement:
    existing = get_entitlement(entitlement_id)
    if existing is None:
        raise ValidationError(f"No entitlement #{entitlement_id}")
    day = _date(on or _dt.date.today().isoformat(), "End date", required=True)
    note = existing.notes or ""
    if reason:
        note = (note + " | " if note else "") + f"Ended {day}: {reason}"
    return update_entitlement(entitlement_id, {
        "end_date": day, "status": "Ended", "notes": note or None})


# ── Daily usage ───────────────────────────────────────────────────

def entitlement_on(student_id: str, day: str) -> Entitlement | None:
    for e in list_entitlements(student_id=student_id):
        if e.covers(day):
            return e
    return None


def record_usage(student_id: str, meal_date: str, *, taken: bool,
                 recorded_by: str, note: str | None = None) -> Usage:
    """Log one learner's meal for one day (re-recording corrects it)."""
    init_db()
    if not (recorded_by or "").strip():
        raise ValidationError("Meal records must name who recorded them")
    day = _date(meal_date, "Meal date", required=True)
    assert day is not None
    if _dt.date.fromisoformat(day).weekday() >= 5:
        raise ValidationError(f"{day} is a weekend")
    ent = entitlement_on(student_id.strip(), day)
    if ent is None:
        raise ValidationError(
            f"{student_id} has no active free-meal entitlement on {day}")
    amount = ent.daily_allowance if taken else 0.0
    with _connect() as conn:
        conn.execute(
            """INSERT INTO free_meal_usage
                   (entitlement_id, student_id, meal_date, taken, amount,
                    recorded_by, note)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(student_id, meal_date) DO UPDATE SET
                   entitlement_id = excluded.entitlement_id,
                   taken = excluded.taken, amount = excluded.amount,
                   recorded_by = excluded.recorded_by,
                   note = COALESCE(excluded.note, free_meal_usage.note),
                   updated_at = datetime('now')""",
            (ent.entitlement_id, ent.student_id, day, 1 if taken else 0,
             amount, recorded_by.strip(), (note or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM free_meal_usage WHERE student_id=? AND meal_date=?",
            (ent.student_id, day)).fetchone()
    return _row_use(r)


def record_day(meal_date: str, *, taken_ids: set[str] | list[str],
               recorded_by: str) -> dict[str, int]:
    """Record a whole day: every learner entitled that day is marked
    taken if their id is in *taken_ids*, otherwise not taken."""
    day = _date(meal_date, "Meal date", required=True)
    assert day is not None
    taken = {t.strip() for t in taken_ids}
    counts = {"taken": 0, "not_taken": 0}
    entitled = list_entitlements(active_on=day)
    unknown = taken - {e.student_id for e in entitled}
    if unknown:
        raise ValidationError(
            "Not entitled on that day: " + ", ".join(sorted(unknown)))
    for ent in entitled:
        was = ent.student_id in taken
        record_usage(ent.student_id, day, taken=was, recorded_by=recorded_by)
        counts["taken" if was else "not_taken"] += 1
    return counts


def day_sheet(meal_date: str) -> list[tuple[Entitlement, Usage | None]]:
    """Everyone entitled on a day, with what (if anything) is recorded."""
    day = _date(meal_date, "Meal date", required=True)
    assert day is not None
    recorded = {u.student_id: u for u in list_usage(date_from=day,
                                                    date_to=day)}
    return [(e, recorded.get(e.student_id))
            for e in list_entitlements(active_on=day)]


def list_usage(*, student_id: str | None = None,
               date_from: str | None = None,
               date_to: str | None = None) -> list[Usage]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if date_from:
        clauses.append("meal_date >= ?")
        args.append(_date(date_from, "From", required=True))
    if date_to:
        clauses.append("meal_date <= ?")
        args.append(_date(date_to, "To", required=True))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM free_meal_usage {where} "
            "ORDER BY meal_date, student_id", args).fetchall()
    return [_row_use(r) for r in rows]


# ── Monthly claim ─────────────────────────────────────────────────

def monthly_claim(month: str) -> ClaimReport:
    """The claim for one month (``"2026-10"``)."""
    init_db()
    try:
        m_from, m_to = fc.month_bounds(month)
    except ValueError as exc:
        raise ValidationError(str(exc)) from None
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name for s in _students.list_students()}
    usage = list_usage(date_from=m_from, date_to=m_to)
    by_ent: dict[int, list[Usage]] = {}
    for u in usage:
        by_ent.setdefault(u.entitlement_id, []).append(u)
    report = ClaimReport(month=month.strip(), date_from=m_from, date_to=m_to)
    for ent in list_entitlements():
        lo = max(m_from, ent.start_date)
        hi = min(m_to, ent.end_date or m_to)
        if lo > hi and not by_ent.get(ent.entitlement_id):
            continue
        days = fc.weekdays_between(lo, hi) if lo <= hi else []
        if ent.status != "Active":
            days = []
        recs = by_ent.get(ent.entitlement_id, [])
        taken = [u for u in recs if u.taken]
        not_taken = [u for u in recs if not u.taken]
        recorded_days = {u.meal_date for u in recs}
        today = _dt.date.today().isoformat()
        unrecorded = [d for d in days
                      if d not in recorded_days and d <= today]
        if not days and not recs:
            continue
        report.lines.append(ClaimLine(
            student_id=ent.student_id,
            student_name=names.get(ent.student_id, "?"),
            entitlement_id=ent.entitlement_id,
            daily_allowance=ent.daily_allowance,
            eligible_days=len(days), taken_days=len(taken),
            not_taken_days=len(not_taken), unrecorded_days=len(unrecorded),
            value_claimed=round(sum(u.amount for u in taken), 2)))
    report.lines.sort(key=lambda l: l.student_id)
    return report


def export_claim_csv(month: str, *, folder: Path | None = None) -> Path:
    """Write the monthly claim to a CSV under the sixth form data dir."""
    report = monthly_claim(month)
    out_dir = folder or (paths.SIXTH_FORM_DATA_DIR / "finance_reports"
                         / "free_meals")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"free_meals_claim_{report.month}.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Student ID", "Name", "Entitlement", "Daily allowance",
                    "Eligible days", "Meals taken", "Not taken",
                    "Unrecorded", "Value claimed"])
        for l in report.lines:
            w.writerow([l.student_id, l.student_name, l.entitlement_id,
                        f"{l.daily_allowance:.2f}", l.eligible_days,
                        l.taken_days, l.not_taken_days, l.unrecorded_days,
                        f"{l.value_claimed:.2f}"])
        w.writerow([])
        w.writerow(["Total", "", "", "", report.eligible_days,
                    report.meals_taken, "", report.unrecorded_days,
                    f"{report.total_claimed:.2f}"])
    logger.info("Free-meals claim for %s written to %s", report.month, path)
    return path


@dataclass
class Summary:
    active_entitlements: int
    unverified_evidence: int
    month: str
    meals_this_month: int
    claimed_this_month: float
    unrecorded_this_month: int


def summary(on: str | None = None) -> Summary:
    day = on or _dt.date.today().isoformat()
    active = list_entitlements(active_on=day)
    report = monthly_claim(day[:7])
    return Summary(
        active_entitlements=len(active),
        unverified_evidence=sum(1 for e in active if not e.evidence_verified),
        month=day[:7], meals_this_month=report.meals_taken,
        claimed_this_month=report.total_claimed,
        unrecorded_this_month=report.unrecorded_days)
