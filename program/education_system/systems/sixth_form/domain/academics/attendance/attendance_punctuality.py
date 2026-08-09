"""Punctuality tracking for the Sixth Form System.

Sibling to :mod:`attendance`. Lateness hides inside attendance. A
learner who is present for every lesson and eleven minutes late to
half of them reads as 100% — which is true, and useless. They have
missed most of a week of teaching and nobody has a number for it.

So punctuality is counted on its own terms:

* **Minutes, not marks.** :func:`minutes_lost` totals the actual
  teaching time missed, which is the figure that makes the case. "You
  were late 22 times" invites an argument; "you have missed nine hours
  of lessons this term" does not.
* **A rolling window.** Lateness is a habit, and a habit is best
  measured over the last few weeks rather than the whole year, so a
  learner who fixed it in October is not still being chased in June.
* **Triggers, and what follows.** Crossing the threshold raises a
  :class:`Trigger` — a detention, a conversation, whatever the college
  does — recorded so it happens once rather than every time somebody
  runs the report.

The `U` code matters here. A learner who arrives after the register
closes is present in the room and absent in the data, and they are the
group most likely to be missed by both an attendance report and a
punctuality one. :func:`after_register_closed` finds them.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_codes as codes,
    attendance_thresholds as thresholds,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

# What a trigger asks somebody to do.
CONVERSATION: str = "Conversation"
DETENTION: str = "Detention"
PARENT_CONTACT: str = "Parent contact"
REPORT_CARD: str = "Punctuality report card"
ESCALATE: str = "Escalate to case"
ACTIONS: tuple[str, ...] = (CONVERSATION, DETENTION, PARENT_CONTACT,
                            REPORT_CARD, ESCALATE)

RAISED: str = "Raised"
ACTIONED: str = "Actioned"
SERVED: str = "Served"
WAIVED: str = "Waived"
MISSED: str = "Missed"
TRIGGER_STATES: tuple[str, ...] = (RAISED, ACTIONED, SERVED, WAIVED, MISSED)

# The rolling window lateness is judged over.
DEFAULT_WINDOW_DAYS: int = 28

# The ladder: how many lates in the window earn which response.
ACTION_LADDER: tuple[tuple[int, str], ...] = (
    (3, CONVERSATION),
    (5, DETENTION),
    (8, PARENT_CONTACT),
    (12, ESCALATE),
)

# Minutes late past which an arrival is "significant" rather than a bus.
SIGNIFICANT_MINUTES: int = 10

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_punctuality_triggers (
    trigger_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    raised_on    TEXT NOT NULL,
    window_from  TEXT NOT NULL,
    window_to    TEXT NOT NULL,
    late_count   INTEGER NOT NULL DEFAULT 0,
    minutes_lost INTEGER NOT NULL DEFAULT 0,
    action       TEXT NOT NULL,
    state        TEXT NOT NULL DEFAULT 'Raised',
    due_on       TEXT,
    served_on    TEXT,
    actioned_by  TEXT,
    note         TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_punct_student
    ON attendance_punctuality_triggers(student_id, raised_on);
CREATE INDEX IF NOT EXISTS idx_att_punct_state
    ON attendance_punctuality_triggers(state);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class PunctualityRecord:
    """One learner's lateness over a window."""

    student_id: str
    window_from: str
    window_to: str
    lessons: int = 0
    on_time: int = 0
    late: int = 0
    after_close: int = 0
    minutes_lost: int = 0
    worst_minutes: int = 0
    student_name: str | None = None

    @property
    def late_rate(self) -> float | None:
        if self.lessons == 0:
            return None
        return round(100.0 * self.late / self.lessons, 1)

    @property
    def hours_lost(self) -> float:
        return round(self.minutes_lost / 60.0, 1)

    @property
    def average_minutes(self) -> float | None:
        if self.late == 0:
            return None
        return round(self.minutes_lost / self.late, 1)

    @property
    def label(self) -> str:
        who = self.student_name or self.student_id
        return (f"{who}: {self.late} late, {self.hours_lost}h of teaching "
                f"missed ({self.window_from} → {self.window_to})")


@dataclass
class Trigger:
    """A punctuality threshold somebody crossed, and what follows."""

    trigger_id: int
    student_id: str
    raised_on: str
    window_from: str
    window_to: str
    late_count: int
    minutes_lost: int
    action: str
    state: str
    due_on: str | None
    served_on: str | None
    actioned_by: str | None
    note: str | None
    created_at: str | None

    @property
    def is_open(self) -> bool:
        return self.state in (RAISED, ACTIONED)

    @property
    def label(self) -> str:
        return (f"{self.student_id} · {self.late_count} late "
                f"({self.minutes_lost} min) → {self.action} [{self.state}]")


@dataclass
class PatternInsight:
    """When lateness happens, which is usually the answer to why."""

    by_weekday: dict[int, int] = field(default_factory=dict)
    by_period: dict[int, int] = field(default_factory=dict)

    @property
    def worst_weekday(self) -> int | None:
        return (max(self.by_weekday, key=lambda k: self.by_weekday[k])
                if self.by_weekday else None)

    @property
    def worst_period(self) -> int | None:
        return (max(self.by_period, key=lambda k: self.by_period[k])
                if self.by_period else None)

    @property
    def first_period_share(self) -> float | None:
        """How much lateness is period 1 — a transport problem, usually."""
        total = sum(self.by_period.values())
        if not total:
            return None
        return round(100.0 * self.by_period.get(1, 0) / total, 1)


@dataclass
class SweepResult:
    checked: int = 0
    raised: int = 0
    skipped_existing: int = 0
    triggers: list[Trigger] = field(default_factory=list)


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
    codes.init_db()
    thresholds.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Punctuality schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> Trigger:
    return Trigger(
        trigger_id=r["trigger_id"], student_id=r["student_id"],
        raised_on=r["raised_on"], window_from=r["window_from"],
        window_to=r["window_to"], late_count=r["late_count"],
        minutes_lost=r["minutes_lost"], action=r["action"], state=r["state"],
        due_on=r["due_on"], served_on=r["served_on"],
        actioned_by=r["actioned_by"], note=r["note"],
        created_at=r["created_at"])


def validate_action(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    for action in ACTIONS:
        if s.lower() == action.lower():
            return action
    raise ValidationError(f"Action must be one of: {', '.join(ACTIONS)}")


def _window(date_to: str | None, days: int) -> tuple[str, str]:
    end = core._validate_date(date_to or _dt.date.today().isoformat())
    start = (_dt.date.fromisoformat(end)
             - _dt.timedelta(days=max(1, days))).isoformat()
    return start, end


# ── Measuring ───────────────────────────────────────────────────────

def record_for(
    student_id: str,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> PunctualityRecord:
    """One learner's punctuality over a window."""
    init_db()
    if date_from is None:
        date_from, date_to = _window(date_to, window_days)
    else:
        date_from = core._validate_date(date_from)
        date_to = core._validate_date(date_to or _dt.date.today().isoformat())

    out = PunctualityRecord(student_id=student_id.strip(),
                            window_from=date_from, window_to=date_to)
    for record in core.list_records(student_id=student_id,
                                    date_from=date_from, date_to=date_to):
        if not codes.counts_as_present(record.code) and record.code != "U":
            continue
        out.lessons += 1
        minutes = record.minutes_late or 0
        if record.code == "U":
            out.after_close += 1
        if minutes > 0 or record.code in ("L", "U"):
            out.late += 1
            out.minutes_lost += minutes
            out.worst_minutes = max(out.worst_minutes, minutes)
        else:
            out.on_time += 1
    return out


def minutes_lost(student_id: str, *, window_days: int = DEFAULT_WINDOW_DAYS
                 ) -> int:
    """Teaching minutes this learner has missed by arriving late."""
    return record_for(student_id, window_days=window_days).minutes_lost


def league(
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    date_to: str | None = None,
    group_id: int | None = None,
    minimum_lates: int = 1,
    with_names: bool = True,
) -> list[PunctualityRecord]:
    """Everybody's punctuality, worst first.

    Not for display to learners — a league table of lateness is a
    motivational disaster. For the person deciding who to speak to on
    Monday.
    """
    init_db()
    date_from, date_to = _window(date_to, window_days)

    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    wanted: set[str] | None = None
    if group_id is not None:
        from education_system.systems.sixth_form.domain.academics.class_groups import (  # noqa: E501
            class_groups as _cg,
        )
        wanted = set(_cg.list_members(group_id))

    index = {s.student_id: s.full_name for s in _students.list_students()}
    out: list[PunctualityRecord] = []
    for student_id in sorted(index):
        if wanted is not None and student_id not in wanted:
            continue
        entry = record_for(student_id, date_from=date_from, date_to=date_to)
        if entry.late < max(0, minimum_lates):
            continue
        if with_names:
            entry.student_name = index.get(student_id)
        out.append(entry)
    out.sort(key=lambda r: (-r.minutes_lost, -r.late))
    return out


def after_register_closed(*, date_from: str | None = None,
                          date_to: str | None = None) -> list[Any]:
    """Marks coded `U` — in the room, but counted as absent.

    The group nobody looks at: an attendance report treats them as
    absent and a punctuality report often treats them as present. They
    are the learners for whom being fifteen minutes earlier would change
    their recorded attendance entirely, which makes them the easiest
    intervention in the college.
    """
    return core.list_records(code="U", date_from=date_from, date_to=date_to)


def patterns(*, window_days: int = DEFAULT_WINDOW_DAYS,
             student_id: str | None = None,
             date_to: str | None = None) -> PatternInsight:
    """When lateness happens.

    Period 1 lateness is a transport or a getting-up problem; period 5
    lateness is a lunch problem; Monday lateness is a weekend problem.
    They need different answers, and this is how you tell them apart.
    """
    init_db()
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as tt,
    )
    date_from, date_to = _window(date_to, window_days)
    slots = {s.slot_id: s for s in tt.list_slots()}
    out = PatternInsight()
    for record in core.list_records(student_id=student_id,
                                    date_from=date_from, date_to=date_to):
        if not (record.minutes_late or record.code in ("L", "U")):
            continue
        weekday = _dt.date.fromisoformat(record.date).weekday() + 1
        out.by_weekday[weekday] = out.by_weekday.get(weekday, 0) + 1
        slot = slots.get(record.slot_id)
        if slot is not None:
            out.by_period[slot.period] = out.by_period.get(slot.period, 0) + 1
    return out


# ── Triggers ────────────────────────────────────────────────────────

def action_for(late_count: int) -> str | None:
    """The most serious response this many lates has earned."""
    action = None
    for count, candidate in ACTION_LADDER:
        if late_count >= count:
            action = candidate
    return action


def raise_trigger(
    student_id: str,
    *,
    action: str | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    date_to: str | None = None,
    due_on: str | None = None,
    note: str | None = None,
) -> Trigger:
    """Raise a punctuality trigger against a learner."""
    init_db()
    entry = record_for(student_id, window_days=window_days, date_to=date_to)
    chosen = (validate_action(action) if action
              else action_for(entry.late) or CONVERSATION)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_punctuality_triggers
                   (student_id, raised_on, window_from, window_to,
                    late_count, minutes_lost, action, state, due_on, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (entry.student_id, _dt.date.today().isoformat(),
             entry.window_from, entry.window_to, entry.late,
             entry.minutes_lost, chosen, RAISED,
             core._validate_date(due_on) if due_on else None,
             (note or "").strip() or None))
        conn.commit()
        trigger_id = int(cur.lastrowid or 0)
    logger.info("Punctuality trigger #%d for %s: %s (%d late)", trigger_id,
                entry.student_id, chosen, entry.late)
    out = get_trigger(trigger_id)
    assert out is not None
    return out


def sweep(
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    date_to: str | None = None,
    group_id: int | None = None,
    dry_run: bool = False,
) -> SweepResult:
    """Raise triggers for everybody who has crossed a rung.

    Only raises a trigger the learner has not already got for the same
    action in the current window — otherwise a daily run issues the same
    detention every morning, which is how a sanction stops meaning
    anything.
    """
    init_db()
    result = SweepResult()
    minutes_trigger = thresholds.value_of(thresholds.LATE_MINUTES_TRIGGER,
                                          default=60.0)
    count_trigger = thresholds.value_of(thresholds.LATE_COUNT_TRIGGER,
                                        default=5.0)

    for entry in league(window_days=window_days, date_to=date_to,
                        group_id=group_id, minimum_lates=1,
                        with_names=False):
        result.checked += 1
        by_count = count_trigger is not None and entry.late >= count_trigger
        by_minutes = (minutes_trigger is not None
                      and entry.minutes_lost >= minutes_trigger)
        if not (by_count or by_minutes):
            continue
        action = action_for(entry.late) or DETENTION
        if _has_open_trigger(entry.student_id, action, entry.window_from):
            result.skipped_existing += 1
            continue
        if dry_run:
            result.raised += 1
            continue
        trigger = raise_trigger(
            entry.student_id, action=action, window_days=window_days,
            date_to=date_to,
            note=f"{entry.late} late arrival(s), {entry.hours_lost}h lost")
        result.raised += 1
        result.triggers.append(trigger)
    logger.info("Punctuality sweep: %d checked, %d raised, %d already open",
                result.checked, result.raised, result.skipped_existing)
    return result


def _has_open_trigger(student_id: str, action: str,
                      window_from: str) -> bool:
    with _connect() as conn:
        r = conn.execute(
            """SELECT COUNT(*) AS n FROM attendance_punctuality_triggers
                WHERE student_id = ? AND action = ? AND state IN (?, ?)
                  AND window_to >= ?""",
            (student_id, action, RAISED, ACTIONED, window_from)).fetchone()
    return bool(r["n"])


def action_trigger(trigger_id: int, *, actioned_by: str,
                   due_on: str | None = None,
                   note: str | None = None) -> Trigger:
    """Somebody has set the sanction up — a detention is now booked."""
    init_db()
    if get_trigger(trigger_id) is None:
        raise ValidationError(f"No trigger with id {trigger_id}")
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_punctuality_triggers
                  SET state = ?, actioned_by = ?, due_on = COALESCE(?, due_on),
                      note = COALESCE(?, note)
                WHERE trigger_id = ?""",
            (ACTIONED, (actioned_by or "").strip() or None,
             core._validate_date(due_on) if due_on else None,
             (note or "").strip() or None, trigger_id))
        conn.commit()
    out = get_trigger(trigger_id)
    assert out is not None
    return out


def serve(trigger_id: int, *, on: str | None = None,
          actioned_by: str | None = None) -> Trigger:
    """The learner did it — detention served, conversation had."""
    init_db()
    if get_trigger(trigger_id) is None:
        raise ValidationError(f"No trigger with id {trigger_id}")
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_punctuality_triggers
                  SET state = ?, served_on = ?, actioned_by = COALESCE(?,
                      actioned_by)
                WHERE trigger_id = ?""",
            (SERVED, core._validate_date(on or _dt.date.today().isoformat()),
             (actioned_by or "").strip() or None, trigger_id))
        conn.commit()
    out = get_trigger(trigger_id)
    assert out is not None
    return out


def mark_missed(trigger_id: int, *, note: str | None = None) -> Trigger:
    """The learner did not turn up to the sanction, which is its own event."""
    init_db()
    if get_trigger(trigger_id) is None:
        raise ValidationError(f"No trigger with id {trigger_id}")
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_punctuality_triggers SET state = ?, "
            "note = COALESCE(?, note) WHERE trigger_id = ?",
            (MISSED, (note or "").strip() or None, trigger_id))
        conn.commit()
    out = get_trigger(trigger_id)
    assert out is not None
    return out


def waive(trigger_id: int, *, reason: str,
          actioned_by: str | None = None) -> Trigger:
    """Cancel a sanction — the lateness had a reason nobody knew about."""
    init_db()
    if get_trigger(trigger_id) is None:
        raise ValidationError(f"No trigger with id {trigger_id}")
    note = (reason or "").strip()
    if not note:
        raise ValidationError("A reason is required to waive a trigger")
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_punctuality_triggers SET state = ?, note = ?, "
            "actioned_by = COALESCE(?, actioned_by) WHERE trigger_id = ?",
            (WAIVED, note, (actioned_by or "").strip() or None, trigger_id))
        conn.commit()
    out = get_trigger(trigger_id)
    assert out is not None
    return out


# ── Reads ───────────────────────────────────────────────────────────

def get_trigger(trigger_id: int) -> Trigger | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_punctuality_triggers "
            "WHERE trigger_id = ?", (trigger_id,)).fetchone()
    return _row(r) if r else None


def list_triggers(*, student_id: str | None = None, state: str | None = None,
                  action: str | None = None, open_only: bool = False,
                  limit: int = 200) -> list[Trigger]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if open_only:
        clauses.append("state IN (?, ?)")
        args.extend([RAISED, ACTIONED])
    elif state:
        if state not in TRIGGER_STATES:
            raise ValidationError(
                f"State must be one of: {', '.join(TRIGGER_STATES)}")
        clauses.append("state = ?")
        args.append(state)
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if action:
        clauses.append("action = ?")
        args.append(validate_action(action))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_punctuality_triggers {where} "
            "ORDER BY raised_on DESC, trigger_id DESC LIMIT ?",
            args).fetchall()
    return [_row(r) for r in rows]


def outstanding(*, action: str | None = None) -> list[Trigger]:
    """Sanctions raised and not yet served."""
    return list_triggers(open_only=True, action=action)


def college_summary(*, window_days: int = DEFAULT_WINDOW_DAYS,
                    date_to: str | None = None) -> dict[str, Any]:
    """The college-level picture — the number for a governors' report."""
    entries = league(window_days=window_days, date_to=date_to,
                     minimum_lates=0, with_names=False)
    total_minutes = sum(e.minutes_lost for e in entries)
    late_learners = sum(1 for e in entries if e.late)
    return {
        "learners": len(entries),
        "learners_late": late_learners,
        "late_marks": sum(e.late for e in entries),
        "after_register_closed": sum(e.after_close for e in entries),
        "minutes_lost": total_minutes,
        "hours_lost": round(total_minutes / 60.0, 1),
        "teaching_days_lost": round(total_minutes / 60.0 / 5, 1),
        "worst": entries[0].student_id if entries else None,
    }
