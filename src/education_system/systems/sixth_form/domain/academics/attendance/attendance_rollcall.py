"""Emergency roll call for the Sixth Form System.

Sibling to :mod:`attendance`. When the alarm goes, somebody at the
assembly point needs one thing: a list of who is supposed to be in the
building right now. Not who is enrolled — who is *here*, this morning,
minus the ones at a placement, on a trip, off sick, or who went home at
lunch.

Every part of that answer already exists somewhere in this package and
nowhere together:

* today's marks say who was in a lesson (:mod:`attendance`),
* the off-site codes and locations say who is out with permission,
* placement days say who is at an employer
  (:mod:`attendance_placements`),
* entrance kiosk taps say who came through the door
  (:mod:`attendance_kiosk`),
* and departure stamps say who has already left.

:func:`expected_on_site` assembles them. A drill (:func:`start_drill`)
freezes that list at the moment the alarm sounds — because the list must
not change while people are being counted — and then marshals mark
people accounted for by name or by tutor group until
:func:`unaccounted` is empty.

**The frozen list is the point.** A roll call computed live would drop
people as registers were edited during the evacuation, which is exactly
when a name must not silently disappear. The drill keeps its own copy,
and :func:`close_drill` records how long the whole thing took.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_codes as codes,
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

# Why somebody is on the expected list, or why they are not.
IN_LESSON: str = "In lesson"
ON_SITE_TAP: str = "Signed in"
EXPECTED_UNMARKED: str = "Timetabled, unmarked"
OFF_SITE: str = "Off site"
ON_PLACEMENT: str = "On placement"
ABSENT: str = "Absent"
LEFT_EARLY: str = "Left early"
NOT_TIMETABLED: str = "Not timetabled"
# Signed out at reception (:mod:`attendance_signout`) and not back yet.
SIGNED_OUT: str = "Signed out"

PRESENCE_REASONS: tuple[str, ...] = (
    IN_LESSON, ON_SITE_TAP, EXPECTED_UNMARKED, OFF_SITE, ON_PLACEMENT,
    ABSENT, LEFT_EARLY, NOT_TIMETABLED, SIGNED_OUT,
)

# Reasons that put somebody on the "should be at the assembly point" list.
ON_SITE_REASONS: frozenset[str] = frozenset({
    IN_LESSON, ON_SITE_TAP, EXPECTED_UNMARKED,
})

# What a marshal can say about a person.
ACCOUNTED: str = "Accounted for"
MISSING: str = "Not accounted for"
EXCUSED: str = "Confirmed off site"
ROLL_STATES: tuple[str, ...] = (ACCOUNTED, MISSING, EXCUSED)

DRILL: str = "Drill"
EVACUATION: str = "Evacuation"
LOCKDOWN: str = "Lockdown"
KINDS: tuple[str, ...] = (DRILL, EVACUATION, LOCKDOWN)

RUNNING: str = "Running"
CLOSED: str = "Closed"
ABANDONED: str = "Abandoned"
DRILL_STATES: tuple[str, ...] = (RUNNING, CLOSED, ABANDONED)

# Someone marked present in a lesson that ended more than this long ago,
# with nothing since, is a stale signal rather than a sighting.
PRESENCE_STALE_MINUTES: int = 180

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_rollcall_drills (
    drill_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    kind         TEXT NOT NULL DEFAULT 'Drill',
    date         TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    started_by   TEXT,
    closed_at    TEXT,
    closed_by    TEXT,
    state        TEXT NOT NULL DEFAULT 'Running',
    assembly_point TEXT,
    expected     INTEGER NOT NULL DEFAULT 0,
    notes        TEXT,
    snapshot     TEXT NOT NULL,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS attendance_rollcall_marks (
    roll_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    drill_id    INTEGER NOT NULL,
    student_id  TEXT NOT NULL,
    state       TEXT NOT NULL,
    marked_by   TEXT,
    marked_at   TEXT DEFAULT (datetime('now')),
    assembly_point TEXT,
    notes       TEXT,
    UNIQUE(drill_id, student_id),
    FOREIGN KEY (drill_id) REFERENCES attendance_rollcall_drills(drill_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_roll_marks_state
    ON attendance_rollcall_marks(state);
CREATE INDEX IF NOT EXISTS idx_att_roll_drills_date
    ON attendance_rollcall_drills(date);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Presence:
    """One person and where the system thinks they are."""

    student_id: str
    full_name: str
    reason: str
    detail: str | None = None
    room: str | None = None
    slot_id: int | None = None
    last_seen: str | None = None

    @property
    def on_site(self) -> bool:
        return self.reason in ON_SITE_REASONS

    @property
    def label(self) -> str:
        where = f" · {self.room}" if self.room else ""
        return f"{self.student_id} {self.full_name} — {self.reason}{where}"


@dataclass
class RollMark:
    """A marshal's word on one person."""

    roll_id: int
    drill_id: int
    student_id: str
    state: str
    marked_by: str | None
    marked_at: str | None
    assembly_point: str | None
    notes: str | None


@dataclass
class Drill:
    """One roll call."""

    drill_id: int
    kind: str
    date: str
    started_at: str
    started_by: str | None
    closed_at: str | None
    closed_by: str | None
    state: str
    assembly_point: str | None
    expected: int
    notes: str | None
    snapshot: list[Presence] = field(default_factory=list)

    @property
    def is_running(self) -> bool:
        return self.state == RUNNING

    @property
    def duration_seconds(self) -> int | None:
        if not self.closed_at:
            return None
        try:
            started = _dt.datetime.fromisoformat(self.started_at)
            closed = _dt.datetime.fromisoformat(self.closed_at)
        except ValueError:                  # pragma: no cover - defensive
            return None
        return int((closed - started).total_seconds())

    @property
    def label(self) -> str:
        return f"#{self.drill_id} {self.kind} {self.date} {self.started_at[-8:]}"


@dataclass
class RollCallStatus:
    """Where a running roll call has got to."""

    drill: Drill
    accounted: list[str] = field(default_factory=list)
    excused: list[str] = field(default_factory=list)
    missing: list[Presence] = field(default_factory=list)

    @property
    def counted(self) -> int:
        return len(self.accounted) + len(self.excused)

    @property
    def outstanding(self) -> int:
        return len(self.missing)

    @property
    def complete(self) -> bool:
        return self.outstanding == 0

    @property
    def summary(self) -> str:
        return (f"{self.counted}/{self.drill.expected} accounted for, "
                f"{self.outstanding} outstanding")


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
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Roll-call schema ready at %s", DB_PATH)
    _DB_READY = True


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _now_time() -> str:
    return _dt.datetime.now().strftime("%H:%M")


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


# ── Who is on site ──────────────────────────────────────────────────

def _placement_ids(date: str) -> dict[str, str]:
    """Learners out at an employer today, if work experience is in use."""
    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (  # noqa: E501
            attendance_placements as _placements,
        )
        return {d.student_id: "Work placement"
                for d in _placements.on_placement(date)}
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Placement lookup unavailable for roll call",
                     exc_info=True)
        return {}


def _signed_out(date: str, at_time: str | None) -> dict[str, Any]:
    """Learners signed out of site and not back, from the sign-out log."""
    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (  # noqa: E501
            attendance_signout as _signout,
        )
        return _signout.off_site_index(date=date, at_time=at_time)
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Sign-out lookup unavailable for roll call",
                     exc_info=True)
        return {}


def _signout_note(trip: Any) -> str:
    back = (f", due back {trip.expected_back}" if trip.expected_back
            else "" if trip.returning else ", left for the day")
    why = trip.reason + (f" ({trip.detail})" if trip.detail else "")
    return f"Signed out {trip.out_time}: {why}{back}"


def confirmed_off_site(*, date: str | None = None,
                       at_time: str | None = None) -> list[Presence]:
    """Who the sign-out log says is off site — the "Confirmed off site"
    list a marshal reads instead of searching for them."""
    date = core._validate_date(date or _dt.date.today().isoformat())
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name for s in _students.list_students()}
    return [Presence(student_id=sid, full_name=names.get(sid, sid),
                     reason=SIGNED_OUT, detail=_signout_note(trip),
                     last_seen=trip.out_time)
            for sid, trip in _signed_out(date, at_time).items()]


def _entrance_taps(date: str) -> dict[str, str]:
    """Learners who came through a door terminal today."""
    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (  # noqa: E501
            attendance_kiosk as _kiosk,
        )
        taps: dict[str, str] = {}
        for event in _kiosk.list_events(date=date, outcome=_kiosk.ON_SITE,
                                        limit=2000):
            if event.student_id:
                taps[event.student_id] = event.time
        return taps
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Kiosk lookup unavailable for roll call", exc_info=True)
        return {}


def expected_on_site(*, date: str | None = None,
                     at_time: str | None = None) -> list[Presence]:
    """Everyone the system believes is in the building.

    Built from today's marks rather than from enrolment, so the answer
    reflects the morning that actually happened. Each person carries the
    reason they are on the list — a marshal holding it needs to know
    whether a name is there because somebody saw them in period 2 or
    because the timetable says they should be somewhere.
    """
    init_db()
    date = core._validate_date(date or _dt.date.today().isoformat())
    now = at_time or _now_time()
    now_minutes = _minutes(reg._validate_time(now, "Time"))

    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    students = {s.student_id: s for s in _students.list_students()}
    placements = _placement_ids(date)
    taps = _entrance_taps(date)
    signed_out = _signed_out(date, now)

    records = core.list_records(date=date)
    by_student: dict[str, list[Any]] = {}
    for record in records:
        by_student.setdefault(record.student_id, []).append(record)

    weekday = _dt.date.fromisoformat(date).weekday() + 1
    out: list[Presence] = []

    for student_id, student in students.items():
        if getattr(student, "status", "Active") not in ("Active", None):
            continue

        if student_id in placements:
            out.append(Presence(student_id=student_id,
                                full_name=student.full_name,
                                reason=ON_PLACEMENT,
                                detail=placements[student_id]))
            continue

        # Signed out at reception and not back: off site, whatever the
        # morning's registers say.
        if student_id in signed_out:
            trip = signed_out[student_id]
            out.append(Presence(
                student_id=student_id, full_name=student.full_name,
                reason=SIGNED_OUT, detail=_signout_note(trip),
                last_seen=trip.out_time))
            continue

        marks = by_student.get(student_id, [])
        latest = None
        for record in marks:
            if latest is None or (record.recorded_at or "") > \
                    (latest.recorded_at or ""):
                latest = record

        # Somebody who went home is not at the assembly point.
        departed = next((r for r in marks if r.departure_time), None)
        if departed is not None and \
                _minutes(departed.departure_time) <= now_minutes:
            out.append(Presence(
                student_id=student_id, full_name=student.full_name,
                reason=LEFT_EARLY,
                detail=f"Left at {departed.departure_time}",
                last_seen=departed.departure_time))
            continue

        offsite = next((r for r in marks
                        if r.is_offsite or codes.implies_offsite(r.code)),
                       None)
        if offsite is not None:
            out.append(Presence(
                student_id=student_id, full_name=student.full_name,
                reason=OFF_SITE,
                detail=offsite.offsite_location or
                (codes.get_code(offsite.code).label
                 if codes.get_code(offsite.code) else None),
                slot_id=offsite.slot_id))
            continue

        attending = [r for r in marks if codes.counts_as_present(r.code)
                     or r.status in core.ATTENDING_STATUSES]
        if attending:
            recent = attending[-1]
            room = None
            slot = tt.get_slot(recent.slot_id)
            if slot is not None:
                room = slot.room
                _start, end = reg.slot_window(recent.slot_id)
                stale = now_minutes - _minutes(end) > PRESENCE_STALE_MINUTES
            else:
                stale = False
            if not stale:
                out.append(Presence(
                    student_id=student_id, full_name=student.full_name,
                    reason=IN_LESSON, room=room, slot_id=recent.slot_id,
                    detail=f"Marked {recent.code or recent.status}",
                    last_seen=recent.arrival_time))
                continue

        if student_id in taps:
            out.append(Presence(
                student_id=student_id, full_name=student.full_name,
                reason=ON_SITE_TAP, detail="Signed in at the door",
                last_seen=taps[student_id]))
            continue

        if marks:
            # Marked, and not as attending: an absence.
            out.append(Presence(
                student_id=student_id, full_name=student.full_name,
                reason=ABSENT,
                detail=f"Marked {latest.code or latest.status}"
                if latest else None))
            continue

        # No mark either way. If they are timetabled today they should
        # be here, and an unmarked register is not evidence they are not.
        slots = [s for s in tt.list_slots(student_id=student_id)
                 if s.day == weekday]
        if weeks.filter_slots(slots, date):
            out.append(Presence(
                student_id=student_id, full_name=student.full_name,
                reason=EXPECTED_UNMARKED,
                detail="Timetabled today, no register taken"))
        else:
            out.append(Presence(
                student_id=student_id, full_name=student.full_name,
                reason=NOT_TIMETABLED))

    out.sort(key=lambda p: (p.reason, p.full_name))
    return out


def on_site_list(*, date: str | None = None,
                 at_time: str | None = None) -> list[Presence]:
    """Just the people who should be at the assembly point."""
    return [p for p in expected_on_site(date=date, at_time=at_time)
            if p.on_site]


def head_count(*, date: str | None = None) -> dict[str, int]:
    """Today's whereabouts, counted by reason."""
    out: dict[str, int] = {}
    for presence in expected_on_site(date=date):
        out[presence.reason] = out.get(presence.reason, 0) + 1
    return out


# ── Drills ──────────────────────────────────────────────────────────

def validate_kind(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        return DRILL
    for kind in KINDS:
        if s.lower() == kind.lower():
            return kind
    raise ValidationError(f"Kind must be one of: {', '.join(KINDS)}")


def validate_roll_state(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    for state in ROLL_STATES:
        if s.lower() == state.lower():
            return state
    raise ValidationError(f"State must be one of: {', '.join(ROLL_STATES)}")


def _presence_to_dict(p: Presence) -> dict[str, Any]:
    return {"student_id": p.student_id, "full_name": p.full_name,
            "reason": p.reason, "detail": p.detail, "room": p.room,
            "slot_id": p.slot_id, "last_seen": p.last_seen}


def _presence_from_dict(d: dict[str, Any]) -> Presence:
    return Presence(student_id=d.get("student_id", ""),
                    full_name=d.get("full_name", ""),
                    reason=d.get("reason", EXPECTED_UNMARKED),
                    detail=d.get("detail"), room=d.get("room"),
                    slot_id=d.get("slot_id"), last_seen=d.get("last_seen"))


def _drill_row(r: sqlite3.Row) -> Drill:
    return Drill(
        drill_id=r["drill_id"],
        kind=r["kind"],
        date=r["date"],
        started_at=r["started_at"],
        started_by=r["started_by"],
        closed_at=r["closed_at"],
        closed_by=r["closed_by"],
        state=r["state"],
        assembly_point=r["assembly_point"],
        expected=r["expected"],
        notes=r["notes"],
        snapshot=[_presence_from_dict(d)
                  for d in json.loads(r["snapshot"] or "[]")],
    )


def start_drill(
    *,
    kind: str = DRILL,
    started_by: str | None = None,
    assembly_point: str | None = None,
    notes: str | None = None,
    date: str | None = None,
    at_time: str | None = None,
) -> Drill:
    """Sound the alarm and freeze the list.

    The snapshot is taken now and never recomputed. A register edited
    during the evacuation must not remove a name from the list somebody
    is holding — that is the one failure mode a roll call cannot have.
    """
    init_db()
    kind = validate_kind(kind)
    date = core._validate_date(date or _dt.date.today().isoformat())
    running = current_drill()
    if running is not None:
        raise ValidationError(
            f"Roll call {running.label} is still running — close it first")

    snapshot = on_site_list(date=date, at_time=at_time)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_rollcall_drills
                   (kind, date, started_at, started_by, state,
                    assembly_point, expected, notes, snapshot)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (kind, date, _now(), (started_by or "").strip() or None, RUNNING,
             (assembly_point or "").strip() or None, len(snapshot),
             (notes or "").strip() or None,
             json.dumps([_presence_to_dict(p) for p in snapshot],
                        separators=(",", ":"))))
        conn.commit()
        drill_id = int(cur.lastrowid or 0)
    logger.warning("Roll call started: %s #%d, %d person(s) expected on site",
                   kind, drill_id, len(snapshot))
    # Anyone the snapshot still expects but who has since signed out
    # (the snapshot and the sign-out log are read a moment apart) is
    # pre-marked Confirmed off site from the log, so no marshal goes
    # looking for them. A marshal can still overrule it.
    away = _signed_out(date, at_time)
    for presence in snapshot:
        trip = away.get(presence.student_id)
        if trip is not None:
            account_for(drill_id, [presence.student_id], state=EXCUSED,
                        marked_by="Sign-out log", notes=_signout_note(trip))
    out = get_drill(drill_id)
    assert out is not None
    return out


def get_drill(drill_id: int) -> Drill | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_rollcall_drills WHERE drill_id = ?",
            (drill_id,)).fetchone()
    return _drill_row(r) if r else None


def current_drill() -> Drill | None:
    """The roll call in progress, if there is one."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_rollcall_drills WHERE state = ? "
            "ORDER BY drill_id DESC LIMIT 1", (RUNNING,)).fetchone()
    return _drill_row(r) if r else None


def list_drills(*, date_from: str | None = None, date_to: str | None = None,
                kind: str | None = None, state: str | None = None,
                limit: int = 50) -> list[Drill]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if date_from:
        clauses.append("date >= ?")
        args.append(core._validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(core._validate_date(date_to))
    if kind:
        clauses.append("kind = ?")
        args.append(validate_kind(kind))
    if state:
        if state not in DRILL_STATES:
            raise ValidationError(
                f"State must be one of: {', '.join(DRILL_STATES)}")
        clauses.append("state = ?")
        args.append(state)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_rollcall_drills {where} "
            "ORDER BY drill_id DESC LIMIT ?", args).fetchall()
    return [_drill_row(r) for r in rows]


# ── Marshalling ─────────────────────────────────────────────────────

def account_for(
    drill_id: int,
    student_ids: list[str] | str,
    *,
    state: str = ACCOUNTED,
    marked_by: str | None = None,
    assembly_point: str | None = None,
    notes: str | None = None,
) -> int:
    """Tick people off the list.

    Takes a list because that is how it happens: a marshal counts a
    tutor group and reports twenty-two names at once.
    """
    init_db()
    drill = get_drill(drill_id)
    if drill is None:
        raise ValidationError(f"No roll call with id {drill_id}")
    if not drill.is_running:
        raise ValidationError(
            f"Roll call {drill.label} is {drill.state.lower()} — reopen it "
            "to change anything")
    state = validate_roll_state(state)
    ids = [student_ids] if isinstance(student_ids, str) else list(student_ids)
    if not ids:
        raise ValidationError("No students given")

    with _connect() as conn:
        conn.executemany(
            """INSERT INTO attendance_rollcall_marks
                   (drill_id, student_id, state, marked_by, assembly_point,
                    notes)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(drill_id, student_id) DO UPDATE SET
                   state = excluded.state,
                   marked_by = excluded.marked_by,
                   marked_at = datetime('now'),
                   assembly_point = COALESCE(
                       excluded.assembly_point,
                       attendance_rollcall_marks.assembly_point),
                   notes = COALESCE(excluded.notes,
                                    attendance_rollcall_marks.notes)""",
            [(drill_id, str(sid).strip(), state,
              (marked_by or "").strip() or None,
              (assembly_point or "").strip() or None,
              (notes or "").strip() or None) for sid in ids])
        conn.commit()
    return len(ids)


def account_for_group(drill_id: int, group_id: int, *,
                      marked_by: str | None = None,
                      assembly_point: str | None = None) -> int:
    """Tick off a whole class or tutor group at once."""
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    members = _cg.list_members(group_id)
    if not members:
        raise ValidationError(f"Group #{group_id} has no members")
    drill = get_drill(drill_id)
    if drill is None:
        raise ValidationError(f"No roll call with id {drill_id}")
    # Only tick off the ones who were expected — marking somebody
    # accounted for who was never on site reads as a false all-clear.
    expected = {p.student_id for p in drill.snapshot}
    present = [sid for sid in members if sid in expected]
    if not present:
        return 0
    return account_for(drill_id, present, marked_by=marked_by,
                       assembly_point=assembly_point)


def mark_missing(drill_id: int, student_id: str, *,
                 marked_by: str | None = None,
                 notes: str | None = None) -> int:
    """Say explicitly that somebody is not at the assembly point."""
    return account_for(drill_id, [student_id], state=MISSING,
                       marked_by=marked_by, notes=notes)


def excuse(drill_id: int, student_id: str, *,
           reason: str, marked_by: str | None = None) -> int:
    """Confirm somebody is legitimately not here — found off site."""
    return account_for(drill_id, [student_id], state=EXCUSED,
                       marked_by=marked_by, notes=reason)


def list_marks(drill_id: int, *, state: str | None = None) -> list[RollMark]:
    init_db()
    clauses = ["drill_id = ?"]
    args: list[Any] = [drill_id]
    if state:
        clauses.append("state = ?")
        args.append(validate_roll_state(state))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_rollcall_marks "
            f"WHERE {' AND '.join(clauses)} ORDER BY marked_at, student_id",
            args).fetchall()
    return [RollMark(roll_id=r["roll_id"], drill_id=r["drill_id"],
                     student_id=r["student_id"], state=r["state"],
                     marked_by=r["marked_by"], marked_at=r["marked_at"],
                     assembly_point=r["assembly_point"], notes=r["notes"])
            for r in rows]


def status(drill_id: int) -> RollCallStatus:
    """Where the count has got to — and, crucially, who is still missing."""
    drill = get_drill(drill_id)
    if drill is None:
        raise ValidationError(f"No roll call with id {drill_id}")
    marks = {m.student_id: m for m in list_marks(drill_id)}
    out = RollCallStatus(drill=drill)
    # "Confirmed off site" reads the sign-out log: somebody on the list
    # who signed out (with no marshal's word either way) is off site.
    away = (_signed_out(drill.date, None) if drill.is_running else {})
    for presence in drill.snapshot:
        mark = marks.get(presence.student_id)
        if mark is None and presence.student_id in away:
            out.excused.append(presence.student_id)
            continue
        if mark is None or mark.state == MISSING:
            out.missing.append(presence)
        elif mark.state == EXCUSED:
            out.excused.append(presence.student_id)
        else:
            out.accounted.append(presence.student_id)
    return out


def unaccounted(drill_id: int) -> list[Presence]:
    """The list that matters. Empty means everybody is out."""
    return status(drill_id).missing


def close_drill(drill_id: int, *, closed_by: str | None = None,
                notes: str | None = None,
                allow_incomplete: bool = False) -> Drill:
    """Call the all-clear.

    Refuses while anybody is unaccounted for, unless somebody
    deliberately overrides — a roll call closed with names outstanding
    has to be a decision a person made, not a button somebody drifted
    into.
    """
    init_db()
    drill = get_drill(drill_id)
    if drill is None:
        raise ValidationError(f"No roll call with id {drill_id}")
    if not drill.is_running:
        raise ValidationError(f"Roll call {drill.label} is already closed")
    outstanding = unaccounted(drill_id)
    if outstanding and not allow_incomplete:
        shown = ", ".join(p.student_id for p in outstanding[:5])
        more = (f" (+{len(outstanding) - 5} more)"
                if len(outstanding) > 5 else "")
        raise ValidationError(
            f"{len(outstanding)} person(s) still unaccounted for: "
            f"{shown}{more}")

    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_rollcall_drills
                  SET state = ?, closed_at = ?, closed_by = ?,
                      notes = COALESCE(?, notes)
                WHERE drill_id = ?""",
            (CLOSED, _now(), (closed_by or "").strip() or None,
             (notes or "").strip() or None, drill_id))
        conn.commit()
    out = get_drill(drill_id)
    assert out is not None
    logger.warning("Roll call #%d closed in %ss (%d outstanding)",
                   drill_id, out.duration_seconds, len(outstanding))
    return out


def abandon_drill(drill_id: int, *, reason: str,
                  actor: str | None = None) -> Drill:
    """Stop a roll call that should not have started — a false alarm."""
    init_db()
    drill = get_drill(drill_id)
    if drill is None:
        raise ValidationError(f"No roll call with id {drill_id}")
    note = (reason or "").strip()
    if not note:
        raise ValidationError("A reason is required to abandon a roll call")
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_rollcall_drills
                  SET state = ?, closed_at = ?, closed_by = ?, notes = ?
                WHERE drill_id = ?""",
            (ABANDONED, _now(), (actor or "").strip() or None, note, drill_id))
        conn.commit()
    out = get_drill(drill_id)
    assert out is not None
    return out


def reopen_drill(drill_id: int, *, reason: str) -> Drill:
    """Put a closed roll call back into progress — somebody turned up."""
    init_db()
    drill = get_drill(drill_id)
    if drill is None:
        raise ValidationError(f"No roll call with id {drill_id}")
    if drill.is_running:
        raise ValidationError(f"Roll call {drill.label} is already running")
    note = (reason or "").strip()
    if not note:
        raise ValidationError("A reason is required to reopen a roll call")
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_rollcall_drills
                  SET state = ?, closed_at = NULL, closed_by = NULL,
                      notes = COALESCE(notes || '; ', '') || ?
                WHERE drill_id = ?""",
            (RUNNING, f"Reopened: {note}", drill_id))
        conn.commit()
    out = get_drill(drill_id)
    assert out is not None
    return out


# ── Reporting ───────────────────────────────────────────────────────

def drill_report(drill_id: int) -> dict[str, Any]:
    """The write-up: how long, how many, and who was missing.

    A drill nobody writes up teaches nobody anything, and the fire
    officer asks for the times.
    """
    state = status(drill_id)
    drill = state.drill
    return {
        "drill_id": drill.drill_id,
        "kind": drill.kind,
        "date": drill.date,
        "started_at": drill.started_at,
        "closed_at": drill.closed_at,
        "duration_seconds": drill.duration_seconds,
        "assembly_point": drill.assembly_point,
        "expected": drill.expected,
        "accounted": len(state.accounted),
        "excused": len(state.excused),
        "missing": [{"student_id": p.student_id, "name": p.full_name,
                     "last_known": p.room or p.detail}
                    for p in state.missing],
        "started_by": drill.started_by,
        "closed_by": drill.closed_by,
        "notes": drill.notes,
    }


def drill_history(*, limit: int = 20) -> list[dict[str, Any]]:
    """Past drills with their times, for the annual safety return."""
    return [drill_report(d.drill_id)
            for d in list_drills(limit=limit) if d.state != RUNNING]
