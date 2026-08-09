"""Work-placement attendance for the Sixth Form System.

Sibling to :mod:`attendance`, and the attendance half of
:mod:`work_experience`. That module knows a learner has a placement at
Hendricks Engineering from the 3rd to the 14th; it does not know whether
they turned up on the 7th.

Nobody at the college can know that either, which is the whole
difficulty. The register is taken by somebody who does not work here —
a supervisor on a factory floor — and until they confirm it, the honest
answer for a placement day is *unknown*, not present. A college that
marks placement days `W` on faith and never checks reports 100%
attendance for the learner who went to the beach.

So a placement day moves through three states:

* **Expected** — the placement says today is a working day. The college
  register is coded `W` (work experience, which counts as attending),
  because that is what was arranged.
* **Confirmed** or **Missed** — the supervisor says what actually
  happened, with hours. A missed day recodes the college register to an
  absence, which is the point of asking.
* **Unconfirmed** — expected, in the past, and nobody has said. These
  are the days :func:`awaiting_confirmation` lists, and they are the
  ones that quietly inflate a figure if nobody chases them.

Confirmed hours feed back into ``we_placements.hours_completed``, so the
placement's own progress stays true without anyone typing it twice.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_register as reg,
    attendance_weeks as weeks,
)
from education_system.systems.sixth_form.domain.academics.timetable import (
    timetable as tt,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

EXPECTED: str = "Expected"
CONFIRMED: str = "Confirmed"
MISSED: str = "Missed"
CANCELLED: str = "Cancelled"
DAY_STATES: tuple[str, ...] = (EXPECTED, CONFIRMED, MISSED, CANCELLED)

# The mark a confirmed placement day earns on the college register. `W`
# counts as attending — the learner is being educated, just not here.
PRESENT_CODE: str = "W"
# What a missed day becomes. `N` rather than `O`: the college does not
# yet know whether the absence was justified, and guessing is how an
# unauthorised mark ends up on the wrong learner.
MISSED_CODE: str = "N"
# A day the employer cancelled is not the learner's absence at all.
CANCELLED_CODE: str = "Y"

DEFAULT_HOURS: float = 7.0
MAX_HOURS: float = 24.0

# Working days a placement is assumed to run, unless it says otherwise:
# Monday to Friday, as ``timetable.day`` numbers them.
DEFAULT_DAYS: tuple[int, ...] = (1, 2, 3, 4, 5)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_placement_days (
    day_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    placement_id  INTEGER NOT NULL,
    student_id    TEXT NOT NULL,
    date          TEXT NOT NULL,
    state         TEXT NOT NULL DEFAULT 'Expected',
    hours         REAL,
    arrival_time  TEXT,
    departure_time TEXT,
    confirmed_by  TEXT,
    confirmed_at  TEXT,
    notes         TEXT,
    synced_to_register INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(placement_id, date),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_pl_days_date
    ON attendance_placement_days(date);
CREATE INDEX IF NOT EXISTS idx_att_pl_days_state
    ON attendance_placement_days(state);
CREATE INDEX IF NOT EXISTS idx_att_pl_days_student
    ON attendance_placement_days(student_id, date);

CREATE TABLE IF NOT EXISTS attendance_placement_patterns (
    placement_id INTEGER PRIMARY KEY,
    days         TEXT NOT NULL DEFAULT '1,2,3,4,5',
    hours_per_day REAL NOT NULL DEFAULT 7.0,
    updated_at   TEXT DEFAULT (datetime('now'))
);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class PlacementDay:
    """One day of a placement."""

    day_id: int
    placement_id: int
    student_id: str
    date: str
    state: str
    hours: float | None
    arrival_time: str | None
    departure_time: str | None
    confirmed_by: str | None
    confirmed_at: str | None
    notes: str | None
    synced_to_register: bool
    created_at: str | None

    @property
    def is_decided(self) -> bool:
        return self.state in (CONFIRMED, MISSED, CANCELLED)

    @property
    def counts_as_attended(self) -> bool:
        return self.state == CONFIRMED

    @property
    def label(self) -> str:
        hours = f", {self.hours:g}h" if self.hours else ""
        return f"{self.date} — {self.state}{hours}"


@dataclass
class PlacementPattern:
    """Which days of the week a placement runs, and for how long."""

    placement_id: int
    days: tuple[int, ...] = DEFAULT_DAYS
    hours_per_day: float = DEFAULT_HOURS

    @property
    def label(self) -> str:
        names = ", ".join(tt.day_name(d) for d in self.days)
        return f"{names} · {self.hours_per_day:g}h/day"


@dataclass
class PlacementAttendance:
    """A placement's attendance record."""

    placement_id: int
    student_id: str
    expected: int = 0
    confirmed: int = 0
    missed: int = 0
    cancelled: int = 0
    unconfirmed: int = 0
    hours: float = 0.0

    @property
    def decided(self) -> int:
        return self.confirmed + self.missed

    @property
    def percentage(self) -> float | None:
        """Attendance over the days somebody actually reported on.

        Deliberately not over expected days: an unconfirmed day is
        missing information, and counting it as an absence would punish
        the learner for the employer's admin.
        """
        if self.decided == 0:
            return None
        return round(100.0 * self.confirmed / self.decided, 1)

    @property
    def confirmation_rate(self) -> float | None:
        """How much of the placement anyone has reported on at all."""
        past = self.decided + self.unconfirmed
        if past == 0:
            return None
        return round(100.0 * self.decided / past, 1)


@dataclass
class Discrepancy:
    """A placement day and a college register that disagree."""

    student_id: str
    date: str
    placement_state: str
    register_code: str | None
    register_status: str | None
    slot_id: int

    @property
    def label(self) -> str:
        return (f"{self.student_id} {self.date}: placement says "
                f"{self.placement_state}, register says "
                f"{self.register_code or self.register_status or '—'}")


@dataclass
class SyncReport:
    days: int = 0
    marks_written: int = 0
    skipped: list[str] = field(default_factory=list)


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    reg.init_db()
    _work_experience().init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Placement-attendance schema ready at %s", DB_PATH)
    _DB_READY = True


def _work_experience():
    """The placement module. Late-imported to keep attendance importable
    on its own — a college can run registers without work experience."""
    from education_system.systems.sixth_form.domain.progression.work_experience import (  # noqa: E501
        work_experience as _we,
    )
    return _we


def _row(r: sqlite3.Row) -> PlacementDay:
    return PlacementDay(
        day_id=r["day_id"],
        placement_id=r["placement_id"],
        student_id=r["student_id"],
        date=r["date"],
        state=r["state"],
        hours=r["hours"],
        arrival_time=r["arrival_time"],
        departure_time=r["departure_time"],
        confirmed_by=r["confirmed_by"],
        confirmed_at=r["confirmed_at"],
        notes=r["notes"],
        synced_to_register=bool(r["synced_to_register"]),
        created_at=r["created_at"],
    )


# ── Validation ──────────────────────────────────────────────────────

def validate_state(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    for state in DAY_STATES:
        if s.lower() == state.lower():
            return state
    raise ValidationError(f"State must be one of: {', '.join(DAY_STATES)}")


def _validate_hours(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        hours = float(value)
    except (TypeError, ValueError):
        raise ValidationError("Hours must be a number") from None
    if hours < 0 or hours > MAX_HOURS:
        raise ValidationError(f"Hours must be between 0 and {MAX_HOURS:g}")
    return round(hours, 2)


def _require_placement(placement_id: int) -> Any:
    placement = _work_experience().get_placement(placement_id)
    if placement is None:
        raise ValidationError(f"No placement with id {placement_id}")
    return placement


# ── The working pattern ─────────────────────────────────────────────

def set_pattern(placement_id: int, *, days: list[int] | tuple[int, ...],
                hours_per_day: float = DEFAULT_HOURS) -> PlacementPattern:
    """Say which weekdays a placement runs.

    Plenty of sixth-form placements are one day a week for a term rather
    than a solid fortnight, and expecting five days of a Wednesday-only
    placement generates four false absences a week.
    """
    init_db()
    _require_placement(placement_id)
    cleaned = sorted({int(d) for d in days})
    if not cleaned or any(d < 1 or d > 7 for d in cleaned):
        raise ValidationError("Days must be numbers 1 (Mon) to 7 (Sun)")
    hours = _validate_hours(hours_per_day) or DEFAULT_HOURS
    with _connect() as conn:
        conn.execute(
            """INSERT INTO attendance_placement_patterns
                   (placement_id, days, hours_per_day)
               VALUES (?, ?, ?)
               ON CONFLICT(placement_id) DO UPDATE SET
                   days = excluded.days,
                   hours_per_day = excluded.hours_per_day,
                   updated_at = datetime('now')""",
            (placement_id, ",".join(str(d) for d in cleaned), hours))
        conn.commit()
    return get_pattern(placement_id)


def get_pattern(placement_id: int) -> PlacementPattern:
    """The placement's working pattern, defaulting to Monday–Friday."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_placement_patterns WHERE placement_id = ?",
            (placement_id,)).fetchone()
    if r is None:
        return PlacementPattern(placement_id=placement_id)
    days = tuple(int(d) for d in str(r["days"]).split(",") if d.strip())
    return PlacementPattern(placement_id=placement_id,
                            days=days or DEFAULT_DAYS,
                            hours_per_day=r["hours_per_day"])


def expected_dates(placement_id: int, *, date_from: str | None = None,
                   date_to: str | None = None) -> list[str]:
    """Every date this placement should run on."""
    placement = _require_placement(placement_id)
    pattern = get_pattern(placement_id)
    start = _dt.date.fromisoformat(
        core._validate_date(date_from or placement.start_date))
    end = _dt.date.fromisoformat(
        core._validate_date(date_to or placement.end_date))
    start = max(start, _dt.date.fromisoformat(placement.start_date))
    end = min(end, _dt.date.fromisoformat(placement.end_date))
    out: list[str] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() + 1 in pattern.days:
            out.append(cursor.isoformat())
        cursor += _dt.timedelta(days=1)
    return out


# ── Generating the days ─────────────────────────────────────────────

def generate_days(placement_id: int, *,
                  overwrite: bool = False) -> list[PlacementDay]:
    """Create the expected days for a placement.

    Idempotent: a day that already exists is left alone unless
    ``overwrite`` is set, so re-running after extending a placement adds
    the new dates without resetting the confirmations already collected.
    """
    init_db()
    placement = _require_placement(placement_id)
    dates = expected_dates(placement_id)
    if not dates:
        raise ValidationError(
            f"Placement #{placement_id} has no working days in its range")

    with _connect() as conn:
        for date in dates:
            if overwrite:
                conn.execute(
                    """INSERT INTO attendance_placement_days
                           (placement_id, student_id, date, state)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(placement_id, date) DO UPDATE SET
                           state = excluded.state""",
                    (placement_id, placement.student_id, date, EXPECTED))
            else:
                conn.execute(
                    """INSERT OR IGNORE INTO attendance_placement_days
                           (placement_id, student_id, date, state)
                       VALUES (?, ?, ?, ?)""",
                    (placement_id, placement.student_id, date, EXPECTED))
        conn.commit()
    logger.info("Generated %d placement day(s) for #%d", len(dates),
                placement_id)
    return list_days(placement_id=placement_id)


# ── Confirmation ────────────────────────────────────────────────────

def confirm_day(
    placement_id: int,
    date: str,
    *,
    hours: float | None = None,
    arrival_time: str | None = None,
    departure_time: str | None = None,
    confirmed_by: str,
    notes: str | None = None,
    sync_register: bool = True,
) -> PlacementDay:
    """The supervisor says the learner was there.

    ``confirmed_by`` is required and is the supervisor's name — an
    attendance record whose source cannot be named is not evidence of
    anything.
    """
    return _decide(placement_id, date, CONFIRMED, hours=hours,
                   arrival_time=arrival_time, departure_time=departure_time,
                   confirmed_by=confirmed_by, notes=notes,
                   sync_register=sync_register)


def report_missed(
    placement_id: int,
    date: str,
    *,
    confirmed_by: str,
    notes: str | None = None,
    sync_register: bool = True,
) -> PlacementDay:
    """The supervisor says the learner did not turn up."""
    return _decide(placement_id, date, MISSED, hours=0,
                   confirmed_by=confirmed_by, notes=notes,
                   sync_register=sync_register)


def cancel_day(placement_id: int, date: str, *,
               reason: str | None = None,
               confirmed_by: str | None = None,
               sync_register: bool = True) -> PlacementDay:
    """The employer stood the day down. Not the learner's absence."""
    return _decide(placement_id, date, CANCELLED, hours=0,
                   confirmed_by=confirmed_by, notes=reason,
                   sync_register=sync_register)


def _decide(
    placement_id: int,
    date: str,
    state: str,
    *,
    hours: float | None = None,
    arrival_time: str | None = None,
    departure_time: str | None = None,
    confirmed_by: str | None = None,
    notes: str | None = None,
    sync_register: bool = True,
) -> PlacementDay:
    init_db()
    date = core._validate_date(date)
    placement = _require_placement(placement_id)
    state = validate_state(state)
    if state in (CONFIRMED, MISSED) and not (confirmed_by or "").strip():
        raise ValidationError(
            "Say who confirmed this — a placement day with no source is "
            "not evidence")
    hours_value = _validate_hours(hours)
    if state == CONFIRMED and hours_value is None:
        hours_value = get_pattern(placement_id).hours_per_day
    if arrival_time:
        arrival_time = reg._validate_time(arrival_time, "Arrival time")
    if departure_time:
        departure_time = reg._validate_time(departure_time, "Departure time")

    with _connect() as conn:
        conn.execute(
            """INSERT INTO attendance_placement_days
                   (placement_id, student_id, date, state, hours,
                    arrival_time, departure_time, confirmed_by, confirmed_at,
                    notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
               ON CONFLICT(placement_id, date) DO UPDATE SET
                   state = excluded.state,
                   hours = excluded.hours,
                   arrival_time = COALESCE(excluded.arrival_time,
                                           attendance_placement_days.arrival_time),
                   departure_time = COALESCE(excluded.departure_time,
                                             attendance_placement_days.departure_time),
                   confirmed_by = excluded.confirmed_by,
                   confirmed_at = datetime('now'),
                   notes = COALESCE(excluded.notes,
                                    attendance_placement_days.notes)""",
            (placement_id, placement.student_id, date, state, hours_value,
             arrival_time, departure_time,
             (confirmed_by or "").strip() or None,
             (notes or "").strip() or None))
        conn.commit()

    day = get_day(placement_id, date)
    assert day is not None
    if sync_register:
        sync_day_to_register(day)
    if state == CONFIRMED:
        _recalculate_hours(placement_id)
    logger.info("Placement #%d %s: %s by %s", placement_id, date, state,
                confirmed_by or "?")
    return get_day(placement_id, date) or day


def _recalculate_hours(placement_id: int) -> None:
    """Push confirmed hours back onto the placement record.

    Set rather than incremented, so re-confirming a day cannot inflate
    the total and a correction actually corrects.
    """
    total = sum(d.hours or 0.0
                for d in list_days(placement_id=placement_id, state=CONFIRMED))
    try:
        _work_experience().update_placement(
            placement_id, {"hours_completed": round(total, 2)})
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Could not write hours back to placement #%d",
                     placement_id, exc_info=True)


# ── Register synchronisation ────────────────────────────────────────

def code_for_state(state: str) -> str | None:
    """The college mark a placement day implies."""
    return {
        EXPECTED: PRESENT_CODE,
        CONFIRMED: PRESENT_CODE,
        MISSED: MISSED_CODE,
        CANCELLED: CANCELLED_CODE,
    }.get(state)


def sync_day_to_register(day: PlacementDay) -> int:
    """Write a placement day through to the college register.

    The learner still has timetabled lessons on a placement day — the
    college's own register has to say something about them, and `W` is
    what it should say. A missed day recodes those same lessons, which
    is the entire reason for collecting the confirmation.

    Submitted registers and closed dates are left alone; the count
    returned says how many lessons were actually written.
    """
    init_db()
    code = code_for_state(day.state)
    if code is None:
        return 0
    weekday = _dt.date.fromisoformat(day.date).weekday() + 1
    slots = [s for s in tt.list_slots(student_id=day.student_id)
             if s.day == weekday]
    slots = weeks.filter_slots(slots, day.date)
    if not slots:
        return 0

    written = 0
    location = None
    try:
        placement = _work_experience().get_placement(day.placement_id)
        employer = (_work_experience().get_employer(placement.employer_id)
                    if placement else None)
        location = employer.name if employer else None
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Employer lookup failed for placement #%d",
                     day.placement_id, exc_info=True)

    for slot in slots:
        if reg.is_locked(slot.slot_id, day.date):
            continue
        try:
            written += core.save_register(
                slot.slot_id, day.date,
                {day.student_id: {
                    "code": code,
                    "notes": (f"Work placement: {location}" if location
                              else "Work placement"),
                    "is_offsite": day.state in (EXPECTED, CONFIRMED),
                    "offsite_location": location,
                    "data_source": "sync",
                }},
                reason=f"Work placement {day.state.lower()} for {day.date}",
                allow_retro=True)
        except ValidationError as e:
            logger.debug("Placement sync skipped slot #%d on %s: %s",
                         slot.slot_id, day.date, e)

    if written:
        with _connect() as conn:
            conn.execute(
                "UPDATE attendance_placement_days SET synced_to_register = 1 "
                "WHERE day_id = ?", (day.day_id,))
            conn.commit()
    return written


def sync_placement(placement_id: int, *,
                   states: tuple[str, ...] = (CONFIRMED, MISSED, CANCELLED)
                   ) -> SyncReport:
    """Push every decided day of a placement into the college register."""
    report = SyncReport()
    for day in list_days(placement_id=placement_id):
        if day.state not in states:
            continue
        report.days += 1
        written = sync_day_to_register(day)
        report.marks_written += written
        if not written:
            report.skipped.append(day.date)
    return report


# ── Reads ───────────────────────────────────────────────────────────

def get_day(placement_id: int, date: str) -> PlacementDay | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_placement_days "
            "WHERE placement_id = ? AND date = ?",
            (placement_id, core._validate_date(date))).fetchone()
    return _row(r) if r else None


def list_days(
    *,
    placement_id: int | None = None,
    student_id: str | None = None,
    state: str | None = None,
    date: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[PlacementDay]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if placement_id is not None:
        clauses.append("placement_id = ?")
        args.append(placement_id)
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if state:
        clauses.append("state = ?")
        args.append(validate_state(state))
    if date:
        clauses.append("date = ?")
        args.append(core._validate_date(date))
    if date_from:
        clauses.append("date >= ?")
        args.append(core._validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(core._validate_date(date_to))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_placement_days {where} "
            "ORDER BY date, placement_id", args).fetchall()
    return [_row(r) for r in rows]


def awaiting_confirmation(*, as_at: str | None = None,
                          older_than_days: int = 0) -> list[PlacementDay]:
    """Past placement days nobody has reported on.

    The chase list. A placement whose supervisor never confirms anything
    is not a placement anybody can vouch for, and this is where that
    becomes visible instead of being assumed away.
    """
    today = core._validate_date(as_at or _dt.date.today().isoformat())
    cutoff = (_dt.date.fromisoformat(today)
              - _dt.timedelta(days=max(0, int(older_than_days)))).isoformat()
    return [d for d in list_days(state=EXPECTED, date_to=cutoff)]


def attendance_for(placement_id: int) -> PlacementAttendance:
    """One placement's record."""
    placement = _require_placement(placement_id)
    days = list_days(placement_id=placement_id)
    today = _dt.date.today().isoformat()
    out = PlacementAttendance(placement_id=placement_id,
                              student_id=placement.student_id,
                              expected=len(days))
    for day in days:
        if day.state == CONFIRMED:
            out.confirmed += 1
            out.hours += day.hours or 0.0
        elif day.state == MISSED:
            out.missed += 1
        elif day.state == CANCELLED:
            out.cancelled += 1
        elif day.date <= today:
            out.unconfirmed += 1
    out.hours = round(out.hours, 2)
    return out


def attendance_for_student(student_id: str) -> PlacementAttendance:
    """Every placement a learner has had, added together."""
    days = list_days(student_id=student_id)
    today = _dt.date.today().isoformat()
    out = PlacementAttendance(placement_id=0, student_id=student_id,
                              expected=len(days))
    for day in days:
        if day.state == CONFIRMED:
            out.confirmed += 1
            out.hours += day.hours or 0.0
        elif day.state == MISSED:
            out.missed += 1
        elif day.state == CANCELLED:
            out.cancelled += 1
        elif day.date <= today:
            out.unconfirmed += 1
    out.hours = round(out.hours, 2)
    return out


def discrepancies(*, date_from: str | None = None,
                  date_to: str | None = None) -> list[Discrepancy]:
    """Days where the placement and the college register disagree.

    Usually one of two stories: a learner marked absent at college who
    was at their placement all along (the register was never synced), or
    one marked `W` whose supervisor says they never arrived. Both are
    worth a phone call, and neither shows up anywhere else.
    """
    init_db()
    out: list[Discrepancy] = []
    for day in list_days(date_from=date_from, date_to=date_to):
        expected_code = code_for_state(day.state)
        if expected_code is None:
            continue
        records = core.list_records(student_id=day.student_id, date=day.date)
        for record in records:
            if record.code == expected_code:
                continue
            # An authorised absence recorded by the college for a
            # separate reason is not a contradiction worth chasing.
            if day.state == MISSED and record.code in ("I", "M", "C"):
                continue
            out.append(Discrepancy(
                student_id=day.student_id, date=day.date,
                placement_state=day.state, register_code=record.code,
                register_status=record.status, slot_id=record.slot_id))
    return out


def on_placement(date: str | None = None) -> list[PlacementDay]:
    """Who is out on placement today.

    Read by :mod:`attendance_rollcall`: somebody at a factory is not
    missing from the fire drill, they are simply not on site.
    """
    day = core._validate_date(date or _dt.date.today().isoformat())
    return [d for d in list_days(date=day)
            if d.state in (EXPECTED, CONFIRMED)]


def delete_day(placement_id: int, date: str) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM attendance_placement_days "
            "WHERE placement_id = ? AND date = ?",
            (placement_id, core._validate_date(date)))
        conn.commit()
    return bool(cur.rowcount)
