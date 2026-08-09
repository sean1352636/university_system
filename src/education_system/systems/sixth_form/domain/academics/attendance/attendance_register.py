"""Register-taking lifecycle for the Sixth Form System.

Sibling to :mod:`attendance`. That module owns the rows; this one owns
the *act of taking a register* — everything a teacher does between
opening the roster and walking away from it:

* **Bulk marking** — set the whole roster, or a selection of it, in one
  action. The common case is "everyone is here bar two".
* **Draft vs submitted** — a register is Draft until someone submits it.
  Submitting locks the rows; editing afterwards means reopening with a
  reason, which is recorded.
* **Chase list** — which timetabled slots have no submitted register
  yet, so nobody's period 3 quietly goes unrecorded.
* **Copy forward** — prefill from the last time this group met, because
  an ongoing absence is still an absence tomorrow.
* **Arrival / departure stamps** — record the clock time a student
  walked in and derive the late minutes from the slot's start, rather
  than asking staff to do the subtraction; and record an early leave
  without pretending the student was absent.
* **Range marking** — a week of known absence (study leave, hospital)
  applied across every slot the student actually had.
* **Undo** — every write snapshots the prior state first, so the last
  save can be rolled back exactly.
* **Dirty detection** — a digest of what is stored versus what is on
  screen, so the UI can warn before unsaved marks are thrown away.

Locking is enforced in :mod:`attendance` itself (its write functions
call :func:`assert_unlocked` here), so a submitted register cannot be
edited through the plain data layer either.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_weeks as weeks,
    attendance_window as window,
)
from education_system.systems.sixth_form.domain.academics.timetable import (
    timetable as tt,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

# A register is Draft while it is being filled in and Submitted once
# the teacher signs it off. Only Draft registers accept writes.
STATES: tuple[str, ...] = ("Draft", "Submitted")
DEFAULT_STATE: str = "Draft"

# Single-key shorthand shared by the GUI (keyboard marking) and the CLI
# (bulk prompts) so both speak the same language.
STATUS_KEYS: dict[str, str] = {
    "p": "Present",
    "l": "Late",
    "a": "Absent",
    "u": "Authorised",
}

# Minutes after the slot start before an arrival counts as Late. Zero
# means "the bell is the bell"; raise it if the college runs a grace.
LATE_GRACE_MINUTES: int = 0

# How many undo steps are kept per (slot, date). Older ones are pruned
# on write — this is an undo buffer, not an audit log.
MAX_SNAPSHOTS: int = 10

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS register_sessions (
    session_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id       INTEGER NOT NULL,
    date          TEXT NOT NULL,
    state         TEXT NOT NULL DEFAULT 'Draft',
    submitted_at  TEXT,
    submitted_by  TEXT,
    reopened_at   TEXT,
    reopened_by   TEXT,
    reopen_reason TEXT,
    notes         TEXT,
    updated_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(slot_id, date),
    FOREIGN KEY (slot_id) REFERENCES timetable_slots(slot_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS register_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id     INTEGER NOT NULL,
    date        TEXT NOT NULL,
    taken_at    TEXT DEFAULT (datetime('now')),
    taken_by    TEXT,
    payload     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reg_sess_date  ON register_sessions(date);
CREATE INDEX IF NOT EXISTS idx_reg_sess_state ON register_sessions(state);
CREATE INDEX IF NOT EXISTS idx_reg_snap_key   ON register_snapshots(slot_id, date);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class RegisterSession:
    """The header row for one (slot, date) register."""
    session_id: int
    slot_id: int
    date: str
    state: str
    submitted_at: str | None
    submitted_by: str | None
    reopened_at: str | None
    reopened_by: str | None
    reopen_reason: str | None
    notes: str | None
    updated_at: str | None

    @property
    def is_submitted(self) -> bool:
        return self.state == "Submitted"


@dataclass
class MissingRegister:
    """A timetabled slot whose register has not been submitted."""
    slot_id: int
    group_id: int
    date: str
    day: int
    period: int
    room: str | None
    state: str          # "Not started" | "Draft"
    marked: int         # rows already recorded
    expected: int       # students on the roster


@dataclass
class CopyResult:
    source_date: str | None
    copied: int
    skipped: int


@dataclass
class RangeResult:
    dates: list[str] = field(default_factory=list)
    written: int = 0
    skipped_locked: int = 0
    skipped_no_slot: int = 0
    # Dates the retro-marking window has already closed. Counted rather
    # than raised, for the same reason a locked Monday is: one dead date
    # should not cost you the rest of the range.
    skipped_closed: list[str] = field(default_factory=list)


@dataclass
class UndoResult:
    restored: int
    deleted: int
    snapshot_at: str | None


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
    # Sessions FK onto slots, and everything here reads attendance rows.
    core.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Register-session schema ready at %s", DB_PATH)
    _DB_READY = True


def _session_row(r: sqlite3.Row) -> RegisterSession:
    return RegisterSession(
        session_id=r["session_id"],
        slot_id=r["slot_id"],
        date=r["date"],
        state=r["state"],
        submitted_at=r["submitted_at"],
        submitted_by=r["submitted_by"],
        reopened_at=r["reopened_at"],
        reopened_by=r["reopened_by"],
        reopen_reason=r["reopen_reason"],
        notes=r["notes"],
        updated_at=r["updated_at"],
    )


# ── Validation helpers ──────────────────────────────────────────────

def _validate_date(value: Any, label: str = "Date") -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        raise ValidationError(f"{label} is required")
    if not core._DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date: {s}") from None
    return s


def _validate_time(value: Any, label: str) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        raise ValidationError(f"{label} is required")
    if not _TIME_RE.match(s):
        raise ValidationError(f"{label} must be HH:MM (24-hour)")
    h, m = s.split(":")
    return f"{int(h):02d}:{m}"


def _require_slot(slot_id: int) -> Any:
    slot = tt.get_slot(slot_id)
    if slot is None:
        raise ValidationError(f"No slot with id {slot_id}")
    return slot


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def slot_window(slot_id: int) -> tuple[str, str]:
    """The slot's start/end times, falling back to the period defaults.

    Slots may be saved without explicit times, but late minutes have to
    be measured against *something*.
    """
    slot = _require_slot(slot_id)
    default = tt.DEFAULT_PERIOD_TIMES.get(slot.period, ("09:00", "09:55"))
    return (slot.start_time or default[0], slot.end_time or default[1])


def status_for_key(key: str) -> str:
    """Map a single-key shorthand (``p``/``l``/``a``/``u``) to a status."""
    status = STATUS_KEYS.get((key or "").strip().lower())
    if status is None:
        raise ValidationError(
            "Key must be one of: "
            + ", ".join(f"{k}={v}" for k, v in STATUS_KEYS.items()))
    return status


# ── Session state ───────────────────────────────────────────────────

def get_session(slot_id: int, date: str) -> RegisterSession | None:
    init_db()
    date = _validate_date(date)
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM register_sessions WHERE slot_id = ? AND date = ?",
            (slot_id, date),
        ).fetchone()
    return _session_row(r) if r else None


def touch_session(slot_id: int, date: str) -> RegisterSession:
    """Ensure a Draft session header exists for this register."""
    init_db()
    date = _validate_date(date)
    with _connect() as conn:
        conn.execute(
            """INSERT INTO register_sessions (slot_id, date, state)
               VALUES (?, ?, 'Draft')
               ON CONFLICT(slot_id, date) DO UPDATE SET
                   updated_at = datetime('now')""",
            (slot_id, date),
        )
        conn.commit()
    session = get_session(slot_id, date)
    assert session is not None
    return session


def is_locked(slot_id: int, date: str) -> bool:
    session = get_session(slot_id, date)
    return bool(session and session.is_submitted)


def assert_unlocked(slot_id: int, date: str) -> None:
    """Raise if the register has been submitted.

    Called by every write path, including :mod:`attendance`'s own, so
    there is no way to amend a signed-off register without reopening it.
    """
    if is_locked(slot_id, date):
        raise ValidationError(
            f"Register for slot #{slot_id} on {date} has been submitted — "
            "reopen it before making changes")


def _roster(slot_id: int, date: str) -> list[core.RegisterEntry]:
    return core.register_view(slot_id, date)


def submit_register(
    slot_id: int,
    date: str,
    *,
    submitted_by: str | None = None,
    notes: str | None = None,
    allow_incomplete: bool = False,
) -> RegisterSession:
    """Sign off a register and lock its rows.

    Refuses while any student on the roster is unmarked — an
    unsubmitted register and an all-present one must stay tellable
    apart. ``allow_incomplete`` is the deliberate override.
    """
    init_db()
    date = _validate_date(date)
    _require_slot(slot_id)
    session = get_session(slot_id, date)
    if session and session.is_submitted:
        raise ValidationError(
            f"Register for slot #{slot_id} on {date} is already submitted")

    entries = _roster(slot_id, date)
    if not entries:
        raise ValidationError(
            f"Slot #{slot_id} has no students on its roster — nothing to submit")
    missing = [e.student_id for e in entries if e.record is None]
    if missing and not allow_incomplete:
        shown = ", ".join(missing[:5])
        more = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""
        raise ValidationError(
            f"{len(missing)} student(s) still unmarked: {shown}{more}")

    with _connect() as conn:
        conn.execute(
            """INSERT INTO register_sessions
                   (slot_id, date, state, submitted_at, submitted_by, notes)
               VALUES (?, ?, 'Submitted', datetime('now'), ?, ?)
               ON CONFLICT(slot_id, date) DO UPDATE SET
                   state        = 'Submitted',
                   submitted_at = datetime('now'),
                   submitted_by = excluded.submitted_by,
                   notes        = COALESCE(excluded.notes, register_sessions.notes),
                   updated_at   = datetime('now')""",
            (slot_id, date, (submitted_by or "").strip() or None,
             (notes or "").strip() or None),
        )
        conn.commit()
    logger.info("Submitted register: slot #%d, %s, by %s",
                slot_id, date, submitted_by or "?")
    out = get_session(slot_id, date)
    assert out is not None
    return out


def reopen_register(
    slot_id: int,
    date: str,
    *,
    reason: str,
    reopened_by: str | None = None,
) -> RegisterSession:
    """Unlock a submitted register. The reason is mandatory and kept."""
    init_db()
    date = _validate_date(date)
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("A reason is required to reopen a register")
    session = get_session(slot_id, date)
    if session is None or not session.is_submitted:
        raise ValidationError(
            f"Register for slot #{slot_id} on {date} is not submitted")

    with _connect() as conn:
        conn.execute(
            """UPDATE register_sessions
                  SET state = 'Draft', reopened_at = datetime('now'),
                      reopened_by = ?, reopen_reason = ?,
                      updated_at = datetime('now')
                WHERE slot_id = ? AND date = ?""",
            ((reopened_by or "").strip() or None, reason, slot_id, date),
        )
        conn.commit()
    logger.info("Reopened register: slot #%d, %s (%s)", slot_id, date, reason)
    out = get_session(slot_id, date)
    assert out is not None
    return out


def list_sessions(
    *,
    slot_id: int | None = None,
    date: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    state: str | None = None,
) -> list[RegisterSession]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if slot_id is not None:
        clauses.append("slot_id = ?")
        args.append(slot_id)
    if date:
        clauses.append("date = ?")
        args.append(_validate_date(date))
    if date_from:
        clauses.append("date >= ?")
        args.append(_validate_date(date_from, "From date"))
    if date_to:
        clauses.append("date <= ?")
        args.append(_validate_date(date_to, "To date"))
    if state:
        if state not in STATES:
            raise ValidationError(f"State must be one of: {', '.join(STATES)}")
        clauses.append("state = ?")
        args.append(state)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM register_sessions {where} "
            "ORDER BY date DESC, slot_id", args).fetchall()
    return [_session_row(r) for r in rows]


# ── Chase list: registers nobody has submitted ──────────────────────

def _dates_in(date_from: str, date_to: str) -> list[str]:
    start = _dt.date.fromisoformat(date_from)
    end = _dt.date.fromisoformat(date_to)
    if end < start:
        raise ValidationError("From date must be on or before To date")
    span = (end - start).days
    if span > 366:
        raise ValidationError("Date range is limited to 366 days")
    return [(start + _dt.timedelta(days=i)).isoformat()
            for i in range(span + 1)]


def unsubmitted_registers(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    group_id: int | None = None,
) -> list[MissingRegister]:
    """Timetabled slots in the window with no submitted register.

    Expected sessions come from the timetable (a slot on day *n* recurs
    every week), so a slot that was never opened shows up as
    "Not started" rather than silently not existing.
    """
    init_db()
    today = _dt.date.today().isoformat()
    date_from = _validate_date(date_from or today, "From date")
    date_to = _validate_date(date_to or today, "To date")
    dates = _dates_in(date_from, date_to)

    slots = tt.list_slots()
    if group_id is not None:
        slots = [s for s in slots if s.group_id == group_id]
    if not slots:
        return []

    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as cg,
    )
    roster_size = {s.group_id: cg.count_members(s.group_id) for s in slots}

    sessions = {
        (s.slot_id, s.date): s
        for s in list_sessions(date_from=date_from, date_to=date_to)
    }
    with _connect() as conn:
        marked = {
            (r["slot_id"], r["date"]): r["n"]
            for r in conn.execute(
                "SELECT slot_id, date, COUNT(*) AS n FROM attendance_records "
                "WHERE voided = 0 AND date >= ? AND date <= ? "
                "GROUP BY slot_id, date",
                (date_from, date_to),
            ).fetchall()
        }

    pattern = weeks.get_pattern()
    week_map = weeks.week_map() if pattern.is_cycling else {}

    out: list[MissingRegister] = []
    for day_str in dates:
        # date.weekday() is Mon=0; timetable days are Mon=1..Fri=5.
        day = _dt.date.fromisoformat(day_str).weekday() + 1
        for slot in slots:
            if slot.day != day:
                continue
            # A week-B slot is not missing a register on a week-A Tuesday.
            if not weeks.slot_runs_on(slot.slot_id, day_str,
                                      pattern=pattern, mapping=week_map):
                continue
            session = sessions.get((slot.slot_id, day_str))
            if session and session.is_submitted:
                continue
            n_marked = marked.get((slot.slot_id, day_str), 0)
            out.append(MissingRegister(
                slot_id=slot.slot_id,
                group_id=slot.group_id,
                date=day_str,
                day=slot.day,
                period=slot.period,
                room=slot.room,
                state="Draft" if (session or n_marked) else "Not started",
                marked=n_marked,
                expected=roster_size.get(slot.group_id, 0),
            ))
    out.sort(key=lambda m: (m.date, m.period, m.slot_id))
    return out


# ── Bulk marking ────────────────────────────────────────────────────

def _payload_from(entry: core.RegisterEntry, status: str) -> dict[str, Any]:
    """Restate an entry under a new status, keeping what still applies."""
    record = entry.record
    return {
        "status": status,
        # Late minutes only mean anything on a Late mark.
        "minutes_late": (record.minutes_late
                         if (record and status == "Late") else None),
        "notes": record.notes if record else None,
    }


def mark_all(
    slot_id: int,
    date: str,
    status: str,
    *,
    student_ids: list[str] | None = None,
    actor: str | None = None,
    reason: str | None = None,
) -> int:
    """Set every student on the roster (or just ``student_ids``) to ``status``.

    Notes survive the change; late minutes are dropped unless the new
    status is Late. Returns the number of rows written.
    """
    init_db()
    date = _validate_date(date)
    status = core._validate_status(status)
    entries = _roster(slot_id, date)
    if student_ids is not None:
        wanted = set(student_ids)
        unknown = wanted - {e.student_id for e in entries}
        if unknown:
            raise ValidationError(
                "Not on this roster: " + ", ".join(sorted(unknown)))
        entries = [e for e in entries if e.student_id in wanted]
    if not entries:
        raise ValidationError("No students to mark")

    payload = {e.student_id: _payload_from(e, status) for e in entries}
    return core.save_register(slot_id, date, payload, actor=actor,
                              reason=reason)


def mark_by_key(
    slot_id: int,
    date: str,
    key: str,
    *,
    student_ids: list[str] | None = None,
    actor: str | None = None,
    reason: str | None = None,
) -> int:
    """:func:`mark_all` driven by the keyboard shorthand."""
    return mark_all(slot_id, date, status_for_key(key),
                    student_ids=student_ids, actor=actor, reason=reason)


# ── Copy forward from the previous session ──────────────────────────

def previous_register_date(slot_id: int, before: str) -> str | None:
    """The most recent date before ``before`` on which this slot was marked."""
    init_db()
    before = _validate_date(before)
    with _connect() as conn:
        r = conn.execute(
            "SELECT MAX(date) AS d FROM attendance_records "
            "WHERE voided = 0 AND slot_id = ? AND date < ?",
            (slot_id, before)).fetchone()
    return r["d"] if r and r["d"] else None


def previous_register_payload(
    slot_id: int,
    date: str,
    *,
    overwrite: bool = False,
) -> tuple[str | None, dict[str, dict[str, Any]]]:
    """Build (source_date, payload) prefilling ``date`` from the last session.

    Without ``overwrite`` only students with no mark yet are included,
    so copying forward never stomps on marks already taken today.
    """
    init_db()
    date = _validate_date(date)
    source = previous_register_date(slot_id, date)
    if source is None:
        return None, {}

    entries = _roster(slot_id, date)
    previous = {e.student_id: e.record
                for e in _roster(slot_id, source)}
    payload: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if entry.record is not None and not overwrite:
            continue
        prior = previous.get(entry.student_id)
        if prior is None:
            continue
        payload[entry.student_id] = {
            "status": prior.status,
            # Carry the mark code, not just the coarse status: an
            # ongoing illness copied forward as a bare Absent would be
            # re-derived as N ("no reason yet"), throwing away the very
            # reason that made it worth copying.
            "code": prior.code,
            "reason_id": prior.reason_id,
            "is_offsite": prior.is_offsite,
            "offsite_location": prior.offsite_location,
            "minutes_late": None,   # yesterday's lateness is not today's
            "notes": prior.notes,
        }
        # The authorisation stamp is deliberately *not* copied. Yesterday
        # being signed off says nothing about today, and inheriting a
        # signature nobody gave is the one thing the stamp exists to stop.
    return source, payload


def copy_previous_register(
    slot_id: int,
    date: str,
    *,
    overwrite: bool = False,
    actor: str | None = None,
    reason: str | None = None,
) -> CopyResult:
    """Persist the copy-forward prefill. Returns what was and wasn't copied."""
    source, payload = previous_register_payload(
        slot_id, date, overwrite=overwrite)
    if source is None:
        return CopyResult(source_date=None, copied=0, skipped=0)
    roster = _roster(slot_id, date)
    skipped = len(roster) - len(payload)
    if not payload:
        return CopyResult(source_date=source, copied=0, skipped=skipped)
    copied = core.save_register(slot_id, date, payload, actor=actor,
                                reason=reason)
    logger.info("Copied register slot #%d from %s to %s (%d row(s))",
                slot_id, source, date, copied)
    return CopyResult(source_date=source, copied=copied, skipped=skipped)


# ── Arrival / departure stamps ──────────────────────────────────────

def _write_stamp(
    slot_id: int,
    date: str,
    student_id: str,
    *,
    status: str | None = None,
    minutes_late: int | None = None,
    set_minutes: bool = False,
    arrival_time: str | None = None,
    departure_time: str | None = None,
    note: str | None = None,
    actor: str | None = None,
) -> core.AttendanceRecord:
    """Upsert the clock columns, which ``save_register`` does not touch."""
    assert_unlocked(slot_id, date)
    # A clock stamp is a claim about a moment that has to be recent to
    # mean anything — "she arrived at 09:12" typed six weeks later is a
    # reconstruction, so it goes through the same gate as any other edit.
    window.assert_open(date, actor=actor, slot_id=slot_id,
                       source="arrival/departure stamp")
    entry = next((e for e in _roster(slot_id, date)
                  if e.student_id == student_id), None)
    if entry is None:
        raise ValidationError(
            f"{student_id} is not on the roster for slot #{slot_id}")
    take_snapshot(slot_id, date, taken_by=actor)

    existing = entry.record
    new_status = status or (existing.status if existing else core.DEFAULT_STATUS)
    new_notes = existing.notes if existing else None
    if note and note not in (new_notes or ""):
        new_notes = f"{new_notes}; {note}" if new_notes else note
    # A stamp that decides the lateness owns the minutes column outright;
    # anything else leaves whatever is already there alone.
    minutes_sql = ("excluded.minutes_late" if set_minutes else
                   "COALESCE(excluded.minutes_late, "
                   "attendance_records.minutes_late)")
    with _connect() as conn:
        conn.execute(
            f"""INSERT INTO attendance_records
                   (slot_id, student_id, date, status, minutes_late, notes,
                    arrival_time, departure_time)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(slot_id, student_id, date) DO UPDATE SET
                   status         = excluded.status,
                   minutes_late   = {minutes_sql},
                   notes          = excluded.notes,
                   arrival_time   = COALESCE(excluded.arrival_time,
                                             attendance_records.arrival_time),
                   departure_time = COALESCE(excluded.departure_time,
                                             attendance_records.departure_time),
                   recorded_at    = datetime('now')""",
            (slot_id, student_id, date, new_status, minutes_late, new_notes,
             arrival_time, departure_time),
        )
        conn.commit()
    touch_session(slot_id, date)
    out = next((r for r in core.list_records(slot_id=slot_id, date=date,
                                             student_id=student_id)), None)
    assert out is not None
    return out


def record_arrival(
    slot_id: int,
    date: str,
    student_id: str,
    arrival_time: str,
    *,
    actor: str | None = None,
) -> core.AttendanceRecord:
    """Stamp when a student walked in and derive the lateness from it.

    Staff record a clock time — the minutes late come from the slot's
    start time, so nobody is doing arithmetic in a doorway.
    """
    init_db()
    date = _validate_date(date)
    arrival_time = _validate_time(arrival_time, "Arrival time")
    start, end = slot_window(slot_id)
    if _minutes(arrival_time) > _minutes(end):
        raise ValidationError(
            f"Arrival {arrival_time} is after the lesson ends ({end})")
    late = max(0, _minutes(arrival_time) - _minutes(start))
    status = "Late" if late > LATE_GRACE_MINUTES else "Present"
    return _write_stamp(
        slot_id, date, student_id,
        status=status, minutes_late=late if status == "Late" else None,
        set_minutes=True, arrival_time=arrival_time, actor=actor)


def record_departure(
    slot_id: int,
    date: str,
    student_id: str,
    departure_time: str,
    *,
    reason: str | None = None,
    actor: str | None = None,
) -> core.AttendanceRecord:
    """Stamp an early leave.

    The student was here, so the status stays Present/Late — the
    departure is carried on the row rather than faked as an absence.
    """
    init_db()
    date = _validate_date(date)
    departure_time = _validate_time(departure_time, "Departure time")
    start, end = slot_window(slot_id)
    if _minutes(departure_time) < _minutes(start):
        raise ValidationError(
            f"Departure {departure_time} is before the lesson starts ({start})")
    if _minutes(departure_time) > _minutes(end):
        raise ValidationError(
            f"Departure {departure_time} is after the lesson ends ({end}) — "
            "that is not an early leave")
    note = f"Left early at {departure_time}"
    reason = (reason or "").strip()
    if reason:
        note += f" ({reason})"
    return _write_stamp(slot_id, date, student_id,
                        departure_time=departure_time, note=note, actor=actor)


def minutes_missed(record: core.AttendanceRecord) -> int:
    """How much of the lesson an early leaver was absent for."""
    if not record.departure_time:
        return 0
    _start, end = slot_window(record.slot_id)
    return max(0, _minutes(end) - _minutes(record.departure_time))


def left_early(record: core.AttendanceRecord) -> bool:
    return bool(record.departure_time)


def list_early_leavers(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[core.AttendanceRecord]:
    init_db()
    clauses = ["voided = 0", "departure_time IS NOT NULL"]
    args: list[Any] = []
    if date_from:
        clauses.append("date >= ?")
        args.append(_validate_date(date_from, "From date"))
    if date_to:
        clauses.append("date <= ?")
        args.append(_validate_date(date_to, "To date"))
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM attendance_records "
            f"WHERE {' AND '.join(clauses)} ORDER BY date DESC, slot_id",
            args).fetchall()
    return [core._row(r) for r in rows]


# ── Range marking ───────────────────────────────────────────────────

def mark_range(
    *,
    date_from: str,
    date_to: str,
    status: str,
    student_ids: list[str] | None = None,
    group_id: int | None = None,
    slot_ids: list[int] | None = None,
    notes: str | None = None,
    actor: str | None = None,
    reason: str | None = None,
) -> RangeResult:
    """Mark a whole date range in one go — a week of known absence.

    Only writes where the student actually had a lesson: each date maps
    to its weekday and only slots timetabled on that day are touched.
    Submitted registers are skipped rather than failing the batch, so
    one locked Monday doesn't cost you the rest of the week; dates the
    retro-marking window has closed are skipped the same way, and named
    in ``skipped_closed`` so the caller can say which.
    """
    init_db()
    date_from = _validate_date(date_from, "From date")
    date_to = _validate_date(date_to, "To date")
    status = core._validate_status(status)
    notes = (notes or "").strip() or None

    slots = tt.list_slots()
    if slot_ids is not None:
        wanted = set(slot_ids)
        slots = [s for s in slots if s.slot_id in wanted]
        if not slots:
            raise ValidationError("None of those slot ids exist")
    elif group_id is not None:
        slots = [s for s in slots if s.group_id == group_id]
    if not slots:
        raise ValidationError("No timetabled slots to mark")

    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as cg,
    )
    members = {s.slot_id: set(cg.list_members(s.group_id)) for s in slots}
    if student_ids is not None:
        wanted_students = set(student_ids)
        if not wanted_students:
            raise ValidationError("No students given")
    else:
        wanted_students = None

    result = RangeResult()
    for day_str in _dates_in(date_from, date_to):
        day = _dt.date.fromisoformat(day_str).weekday() + 1
        todays = weeks.filter_slots([s for s in slots if s.day == day],
                                    day_str)
        if not todays:
            result.skipped_no_slot += 1
            continue
        if not window.evaluate(day_str, reason=reason).allowed:
            result.skipped_closed.append(day_str)
            continue
        result.dates.append(day_str)
        for slot in todays:
            roster = members[slot.slot_id]
            targets = (roster if wanted_students is None
                       else roster & wanted_students)
            if not targets:
                continue
            if is_locked(slot.slot_id, day_str):
                result.skipped_locked += len(targets)
                continue
            payload = {
                sid: {"status": status, "minutes_late": None, "notes": notes}
                for sid in sorted(targets)
            }
            result.written += core.save_register(
                slot.slot_id, day_str, payload, actor=actor, reason=reason)
    logger.info("Range mark %s..%s status=%s: %d row(s), %d locked, "
                "%d date(s) closed",
                date_from, date_to, status, result.written,
                result.skipped_locked, len(result.skipped_closed))
    return result


# ── Undo ────────────────────────────────────────────────────────────

# Every column an undo has to put back. Anything omitted here would be
# silently reset to its default by the restore, so this list has to
# track the columns in ``attendance._ADDED_COLUMNS``.
_SNAPSHOT_COLUMNS: tuple[str, ...] = (
    "student_id", "status", "minutes_late", "notes",
    "arrival_time", "departure_time", "code", "reason_id", "session",
    "authorised_by", "authorised_at", "authorisation_note",
    "is_offsite", "offsite_location", "data_source",
    "voided", "voided_by", "voided_at", "void_reason",
)

# NOT NULL columns need a value even when restoring a snapshot taken
# before that column existed.
_SNAPSHOT_DEFAULTS: dict[str, Any] = {
    "is_offsite": 0, "voided": 0, "data_source": "manual",
}


def _current_rows(conn: sqlite3.Connection, slot_id: int,
                  date: str) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(
        f"SELECT {', '.join(_SNAPSHOT_COLUMNS)} FROM attendance_records "
        "WHERE slot_id = ? AND date = ? ORDER BY student_id",
        (slot_id, date)).fetchall()]


def take_snapshot(slot_id: int, date: str,
                  *, taken_by: str | None = None) -> int:
    """Freeze the register's current state so the next write is undoable."""
    init_db()
    date = _validate_date(date)
    with _connect() as conn:
        payload = json.dumps(_current_rows(conn, slot_id, date))
        cur = conn.execute(
            "INSERT INTO register_snapshots (slot_id, date, taken_by, payload) "
            "VALUES (?, ?, ?, ?)",
            (slot_id, date, (taken_by or "").strip() or None, payload))
        # Keep the buffer bounded — this is undo, not an audit trail.
        conn.execute(
            """DELETE FROM register_snapshots
                WHERE slot_id = ? AND date = ? AND snapshot_id NOT IN (
                    SELECT snapshot_id FROM register_snapshots
                     WHERE slot_id = ? AND date = ?
                     ORDER BY snapshot_id DESC LIMIT ?)""",
            (slot_id, date, slot_id, date, MAX_SNAPSHOTS))
        conn.commit()
        return int(cur.lastrowid or 0)


def snapshot_count(slot_id: int, date: str) -> int:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT COUNT(*) AS n FROM register_snapshots "
            "WHERE slot_id = ? AND date = ?",
            (slot_id, _validate_date(date))).fetchone()
    return int(r["n"])


def undo_last_save(slot_id: int, date: str) -> UndoResult:
    """Roll the register back to the state before the last write.

    Rows that the undone save created are deleted, rows it changed are
    put back verbatim. The snapshot is consumed, so repeated calls walk
    back through the buffer one save at a time.
    """
    init_db()
    date = _validate_date(date)
    assert_unlocked(slot_id, date)
    with _connect() as conn:
        snap = conn.execute(
            "SELECT * FROM register_snapshots WHERE slot_id = ? AND date = ? "
            "ORDER BY snapshot_id DESC LIMIT 1", (slot_id, date)).fetchone()
        if snap is None:
            raise ValidationError(
                f"Nothing to undo for slot #{slot_id} on {date}")
        rows = json.loads(snap["payload"])
        keep = {r["student_id"] for r in rows}

        placeholders = ",".join("?" * len(keep)) if keep else None
        if placeholders:
            deleted = conn.execute(
                "DELETE FROM attendance_records WHERE slot_id = ? AND date = ? "
                f"AND student_id NOT IN ({placeholders})",
                (slot_id, date, *sorted(keep))).rowcount
        else:
            deleted = conn.execute(
                "DELETE FROM attendance_records WHERE slot_id = ? AND date = ?",
                (slot_id, date)).rowcount

        # Restore every snapshotted column, not just the marks — an undo
        # that quietly cleared an authorisation or un-voided a row would
        # be worse than no undo at all.
        restorable = [c for c in _SNAPSHOT_COLUMNS if c != "student_id"]
        columns = ", ".join(restorable)
        placeholders = ", ".join("?" * len(restorable))
        updates = ", ".join(f"{c} = excluded.{c}" for c in restorable)
        insert_sql = (
            f"INSERT INTO attendance_records (slot_id, student_id, date, "
            f"{columns}) VALUES (?, ?, ?, {placeholders}) "
            f"ON CONFLICT(slot_id, student_id, date) DO UPDATE SET "
            f"{updates}, recorded_at = datetime('now')"
        )
        for r in rows:
            conn.execute(
                insert_sql,
                (slot_id, r["student_id"], date,
                 *(r.get(c, _SNAPSHOT_DEFAULTS.get(c))
                   if r.get(c) is not None
                   else _SNAPSHOT_DEFAULTS.get(c)
                   for c in restorable)))
        conn.execute("DELETE FROM register_snapshots WHERE snapshot_id = ?",
                     (snap["snapshot_id"],))
        conn.commit()
        taken_at = snap["taken_at"]
    logger.info("Undid last save: slot #%d, %s (%d restored, %d removed)",
                slot_id, date, len(rows), deleted)
    return UndoResult(restored=len(rows), deleted=deleted, snapshot_at=taken_at)


# ── Dirty detection ─────────────────────────────────────────────────

def _digest(items: list[tuple[str, str, str, str]]) -> str:
    blob = json.dumps(sorted(items), separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def register_digest(slot_id: int, date: str) -> str:
    """Fingerprint of the register as stored."""
    init_db()
    date = _validate_date(date)
    with _connect() as conn:
        rows = _current_rows(conn, slot_id, date)
    return _digest([
        (r["student_id"], r["status"],
         "" if r["minutes_late"] is None else str(r["minutes_late"]),
         r["notes"] or "")
        for r in rows
    ])


def payload_digest(payload: dict[str, dict[str, Any]]) -> str:
    """Fingerprint of an on-screen register, comparable to the stored one.

    The UI compares this against :func:`register_digest` to know whether
    there are unsaved marks — cheaper and more honest than tracking a
    dirty flag through every widget.
    """
    items: list[tuple[str, str, str, str]] = []
    for sid, values in payload.items():
        minutes = values.get("minutes_late")
        items.append((
            str(sid),
            str(values.get("status") or ""),
            "" if minutes in (None, "") else str(int(minutes)),  # type: ignore[arg-type]
            str(values.get("notes") or ""),
        ))
    return _digest(items)


def has_unsaved_changes(slot_id: int, date: str,
                        payload: dict[str, dict[str, Any]]) -> bool:
    return payload_digest(payload) != register_digest(slot_id, date)
