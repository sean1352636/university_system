"""Timetable week cycles (A/B weeks) for Sixth Form Attendance.

Sibling to :mod:`attendance`. The timetable in :mod:`timetable` pins a
class group to a (day, period) cell and recurs it every week. Plenty of
colleges do not run that way: they run a two-week cycle, where Tuesday
period 3 is Further Maths in week A and a free in week B.

Everything downstream of the timetable quietly assumes the weekly
version. Expand a fortnight of "expected lessons" against an A/B
timetable and you get twice the lessons that exist, half of which are
then reported as unmarked — the coverage report fills with lessons
nobody was ever meant to teach, and the true-attendance percentage
halves.

So this module holds two things:

* **The cycle** — how many weeks long it is and which real Monday is
  week A. From those, any date resolves to a week label.
* **The slot map** — which week each timetable slot runs in. A slot with
  no entry runs in *both* weeks, which is what makes this safe to add to
  a college that never asked for it: an unconfigured system is a
  one-week system, and every existing calculation gives the same answer
  it did before.

:func:`filter_slots` is the one function callers need. Give it a list of
slots and a date and it removes the ones that do not run that week.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
)
from education_system.systems.sixth_form.domain.academics.timetable import (
    timetable as tt,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

# A slot marked BOTH runs every week. It is the default, and it is what
# makes a college that has never opened this screen behave exactly as it
# did before the module existed.
BOTH: str = "Both"

# Labels for the weeks of the cycle, in order. Four is more than anyone
# asked for; two is the common case and one is "no cycle at all".
WEEK_LABELS: tuple[str, ...] = ("A", "B", "C", "D")
MAX_CYCLE_WEEKS: int = len(WEEK_LABELS)

DEFAULT_CYCLE_WEEKS: int = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_week_pattern (
    pattern_id  INTEGER PRIMARY KEY CHECK (pattern_id = 1),
    cycle_weeks INTEGER NOT NULL DEFAULT 1,
    anchor_date TEXT NOT NULL,
    updated_at  TEXT DEFAULT (datetime('now')),
    updated_by  TEXT
);

CREATE TABLE IF NOT EXISTS attendance_slot_weeks (
    slot_id    INTEGER PRIMARY KEY,
    week       TEXT NOT NULL DEFAULT 'Both',
    updated_at TEXT DEFAULT (datetime('now')),
    updated_by TEXT,
    FOREIGN KEY (slot_id) REFERENCES timetable_slots(slot_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_slot_weeks_week
    ON attendance_slot_weeks(week);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class WeekPattern:
    """The college's timetable cycle."""

    cycle_weeks: int = DEFAULT_CYCLE_WEEKS
    anchor_date: str = ""
    updated_at: str | None = None
    updated_by: str | None = None

    @property
    def labels(self) -> tuple[str, ...]:
        return WEEK_LABELS[:self.cycle_weeks]

    @property
    def is_cycling(self) -> bool:
        """Whether the timetable actually repeats over more than a week."""
        return self.cycle_weeks > 1

    @property
    def summary(self) -> str:
        if not self.is_cycling:
            return "Single-week timetable — every slot runs every week."
        return (f"{self.cycle_weeks}-week cycle ({'/'.join(self.labels)}), "
                f"week {self.labels[0]} beginning {self.anchor_date}.")


@dataclass
class SlotWeek:
    """Which week of the cycle one timetable slot runs in."""

    slot_id: int
    week: str
    updated_at: str | None = None
    updated_by: str | None = None


@dataclass
class WeekDay:
    """One date and the week label it falls in."""

    date: str
    week: str
    weekday: int        # 1 = Monday, matching `timetable.day`


@dataclass
class PatternSummary:
    """How the timetable is split across the cycle."""

    cycle_weeks: int
    total_slots: int
    both: int
    by_week: dict[str, int]

    @property
    def assigned(self) -> int:
        return sum(self.by_week.values())


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def _monday_of(date: str) -> _dt.date:
    d = _dt.date.fromisoformat(core._validate_date(date))
    return d - _dt.timedelta(days=d.weekday())


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    # The slot map FKs onto timetable_slots.
    tt.init_db()
    core.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO attendance_week_pattern "
            "(pattern_id, cycle_weeks, anchor_date) VALUES (1, ?, ?)",
            (DEFAULT_CYCLE_WEEKS,
             (_dt.date.today()
              - _dt.timedelta(days=_dt.date.today().weekday())).isoformat()))
        conn.commit()
    logger.debug("Week-pattern schema ready at %s", DB_PATH)
    _DB_READY = True


# ── The cycle ───────────────────────────────────────────────────────

def get_pattern() -> WeekPattern:
    """The configured cycle, defaulting to a plain one-week timetable."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_week_pattern WHERE pattern_id = 1"
        ).fetchone()
    if r is None:                              # pragma: no cover - defensive
        return WeekPattern(anchor_date=_dt.date.today().isoformat())
    return WeekPattern(
        cycle_weeks=r["cycle_weeks"],
        anchor_date=r["anchor_date"],
        updated_at=r["updated_at"],
        updated_by=r["updated_by"],
    )


def set_pattern(
    *,
    cycle_weeks: int,
    anchor_date: str | None = None,
    actor: str | None = None,
) -> WeekPattern:
    """Configure the cycle.

    ``anchor_date`` is any date inside the first week of the cycle — the
    Monday of that week becomes week A. Left out, it keeps whatever is
    already set, so changing a two-week cycle to a three-week one does
    not silently shunt every existing week label along by one.
    """
    init_db()
    try:
        weeks = int(cycle_weeks)
    except (TypeError, ValueError):
        raise ValidationError("Cycle weeks must be a whole number") from None
    if not (1 <= weeks <= MAX_CYCLE_WEEKS):
        raise ValidationError(
            f"Cycle weeks must be between 1 and {MAX_CYCLE_WEEKS}")

    current = get_pattern()
    anchor = _monday_of(anchor_date) if anchor_date else _monday_of(
        current.anchor_date or _dt.date.today().isoformat())

    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_week_pattern
                  SET cycle_weeks = ?, anchor_date = ?,
                      updated_at = datetime('now'), updated_by = ?
                WHERE pattern_id = 1""",
            (weeks, anchor.isoformat(), (actor or "").strip() or None))
        conn.commit()
    logger.info("Week pattern set: %d-week cycle anchored on %s by %s",
                weeks, anchor.isoformat(), actor or "?")
    return get_pattern()


def reset_pattern(*, actor: str | None = None) -> WeekPattern:
    """Go back to a single-week timetable."""
    return set_pattern(cycle_weeks=1, actor=actor)


def is_cycling() -> bool:
    """Whether anything in this module can change an answer."""
    return get_pattern().is_cycling


def week_for_date(date: str, *, pattern: WeekPattern | None = None) -> str:
    """The week label a date falls in.

    Counted in whole weeks from the anchor Monday, so every day of a
    given week gets the same label — including the weekend, which
    matters when somebody asks what week next Saturday's revision
    session is in.
    """
    pattern = pattern or get_pattern()
    if not pattern.is_cycling:
        return pattern.labels[0]
    anchor = _monday_of(pattern.anchor_date)
    target = _monday_of(date)
    weeks = (target - anchor).days // 7
    return pattern.labels[weeks % pattern.cycle_weeks]


def week_calendar(date_from: str, date_to: str) -> list[WeekDay]:
    """Each date in the window with its week label."""
    pattern = get_pattern()
    start = _dt.date.fromisoformat(core._validate_date(date_from))
    end = _dt.date.fromisoformat(core._validate_date(date_to))
    if end < start:
        raise ValidationError("From date must be on or before To date")
    if (end - start).days > 366:
        raise ValidationError("Date range is limited to 366 days")
    out: list[WeekDay] = []
    cursor = start
    while cursor <= end:
        iso = cursor.isoformat()
        out.append(WeekDay(date=iso,
                           week=week_for_date(iso, pattern=pattern),
                           weekday=cursor.weekday() + 1))
        cursor += _dt.timedelta(days=1)
    return out


def next_date_in_week(week: str, *, after: str | None = None) -> str:
    """The next Monday whose week carries ``week``.

    Answers "when is week B next?", which is the question staff actually
    ask when they are told a lesson only runs in one of them.
    """
    pattern = get_pattern()
    week = validate_week(week, allow_both=False)
    if week not in pattern.labels:
        raise ValidationError(
            f"Week {week} is not part of a {pattern.cycle_weeks}-week cycle")
    start = _monday_of(after or _dt.date.today().isoformat())
    for offset in range(pattern.cycle_weeks):
        candidate = start + _dt.timedelta(weeks=offset)
        if week_for_date(candidate.isoformat(), pattern=pattern) == week:
            return candidate.isoformat()
    # Unreachable while the label came from `pattern.labels`.
    raise ValidationError(f"No week {week} found in the cycle")  # pragma: no cover


# ── The slot map ────────────────────────────────────────────────────

def validate_week(value: Any, *, allow_both: bool = True) -> str:
    """Normalise ``'a'`` / ``'B'`` / ``'both'`` to a stored week value."""
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        raise ValidationError("Week is required")
    if s.lower() == BOTH.lower():
        if not allow_both:
            raise ValidationError("A specific week is required here")
        return BOTH
    upper = s.upper()
    if upper in WEEK_LABELS:
        return upper
    allowed = ", ".join((*WEEK_LABELS, BOTH) if allow_both else WEEK_LABELS)
    raise ValidationError(f"Week must be one of: {allowed}")


def _require_slot(slot_id: int) -> Any:
    slot = tt.get_slot(slot_id)
    if slot is None:
        raise ValidationError(f"No slot with id {slot_id}")
    return slot


def set_slot_week(slot_id: int, week: str, *,
                  actor: str | None = None) -> SlotWeek:
    """Pin one timetable slot to a week of the cycle."""
    init_db()
    _require_slot(slot_id)
    week = validate_week(week)
    pattern = get_pattern()
    if week != BOTH and week not in pattern.labels:
        raise ValidationError(
            f"Week {week} is not part of the current "
            f"{pattern.cycle_weeks}-week cycle "
            f"({'/'.join(pattern.labels)})")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO attendance_slot_weeks (slot_id, week, updated_by)
               VALUES (?, ?, ?)
               ON CONFLICT(slot_id) DO UPDATE SET
                   week = excluded.week,
                   updated_at = datetime('now'),
                   updated_by = excluded.updated_by""",
            (slot_id, week, (actor or "").strip() or None))
        conn.commit()
    logger.info("Slot #%d pinned to week %s", slot_id, week)
    out = get_slot_week(slot_id)
    assert out is not None
    return out


def get_slot_week(slot_id: int) -> SlotWeek | None:
    """The stored entry for a slot, or ``None`` when it runs every week."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_slot_weeks WHERE slot_id = ?",
            (slot_id,)).fetchone()
    if r is None:
        return None
    return SlotWeek(slot_id=r["slot_id"], week=r["week"],
                    updated_at=r["updated_at"], updated_by=r["updated_by"])


def week_of_slot(slot_id: int) -> str:
    """The week a slot runs in — :data:`BOTH` when nobody has said."""
    entry = get_slot_week(slot_id)
    return entry.week if entry else BOTH


def clear_slot_week(slot_id: int) -> bool:
    """Put a slot back to running every week."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM attendance_slot_weeks WHERE slot_id = ?", (slot_id,))
        conn.commit()
    return bool(cur.rowcount)


def list_slot_weeks(*, week: str | None = None) -> list[SlotWeek]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if week:
        clauses.append("week = ?")
        args.append(validate_week(week))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_slot_weeks {where} ORDER BY slot_id",
            args).fetchall()
    return [SlotWeek(slot_id=r["slot_id"], week=r["week"],
                     updated_at=r["updated_at"], updated_by=r["updated_by"])
            for r in rows]


def week_map() -> dict[int, str]:
    """``slot_id`` → week, for slots that have been pinned to one.

    Read once and consulted per date; the callers that filter a whole
    term's worth of lessons should not be issuing a query per slot.
    """
    return {entry.slot_id: entry.week for entry in list_slot_weeks()}


def assign_group(group_id: int, week: str, *,
                 actor: str | None = None) -> int:
    """Pin every slot belonging to one class group to a week."""
    init_db()
    week = validate_week(week)
    slots = tt.list_slots(group_id=group_id)
    if not slots:
        raise ValidationError(f"Group #{group_id} has no timetable slots")
    for slot in slots:
        set_slot_week(slot.slot_id, week, actor=actor)
    return len(slots)


def clear_all(*, actor: str | None = None) -> int:
    """Unpin every slot. The timetable goes back to running weekly."""
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM attendance_slot_weeks")
        conn.commit()
    logger.info("Cleared %d slot week assignment(s) (%s)",
                cur.rowcount, actor or "?")
    return int(cur.rowcount)


# ── The bit everything else calls ───────────────────────────────────

def slot_runs_on(slot_id: int, date: str, *,
                 pattern: WeekPattern | None = None,
                 mapping: dict[int, str] | None = None) -> bool:
    """Whether a slot happens on a given date's week.

    Says nothing about the day of the week — the caller has already
    matched that. On a single-week timetable this is always ``True``.
    """
    pattern = pattern or get_pattern()
    if not pattern.is_cycling:
        return True
    week = (mapping.get(slot_id, BOTH) if mapping is not None
            else week_of_slot(slot_id))
    return week == BOTH or week == week_for_date(date, pattern=pattern)


def filter_slots(slots: Sequence[Any], date: str, *,
                 pattern: WeekPattern | None = None,
                 mapping: dict[int, str] | None = None) -> list[Any]:
    """Drop the slots that do not run in ``date``'s week.

    The single call every timetable-expanding function needs. Returns
    the list untouched on a one-week timetable, so callers can apply it
    unconditionally without paying for a college that does not cycle.
    """
    pattern = pattern or get_pattern()
    if not pattern.is_cycling:
        return list(slots)
    mapping = week_map() if mapping is None else mapping
    label = week_for_date(date, pattern=pattern)
    return [s for s in slots
            if mapping.get(getattr(s, "slot_id", s), BOTH) in (BOTH, label)]


def filter_slot_ids(slot_ids: Iterable[int], date: str) -> list[int]:
    """:func:`filter_slots` for bare ids."""
    pattern = get_pattern()
    if not pattern.is_cycling:
        return list(slot_ids)
    mapping = week_map()
    label = week_for_date(date, pattern=pattern)
    return [sid for sid in slot_ids
            if mapping.get(sid, BOTH) in (BOTH, label)]


# ── Reporting ───────────────────────────────────────────────────────

def summary() -> PatternSummary:
    """How the timetable is divided across the cycle."""
    init_db()
    pattern = get_pattern()
    slots = tt.list_slots()
    mapping = week_map()
    by_week = {label: 0 for label in pattern.labels}
    both = 0
    for slot in slots:
        week = mapping.get(slot.slot_id, BOTH)
        if week == BOTH:
            both += 1
        elif week in by_week:
            by_week[week] += 1
    return PatternSummary(cycle_weeks=pattern.cycle_weeks,
                          total_slots=len(slots), both=both, by_week=by_week)


def orphaned_assignments() -> list[SlotWeek]:
    """Slots pinned to a week the cycle no longer has.

    Shortening a three-week cycle to two leaves any week-C slot pinned
    to nothing. Those slots still run — :func:`slot_runs_on` treats an
    unrecognised label as "never this week" — so they need saying out
    loud rather than quietly vanishing from every register list.
    """
    pattern = get_pattern()
    live = set(pattern.labels) | {BOTH}
    return [entry for entry in list_slot_weeks() if entry.week not in live]


def describe(date: str) -> str:
    """One line for a CLI header or a tooltip."""
    pattern = get_pattern()
    if not pattern.is_cycling:
        return f"{date}: single-week timetable."
    return (f"{date}: week {week_for_date(date, pattern=pattern)} of "
            f"{pattern.cycle_weeks}.")
