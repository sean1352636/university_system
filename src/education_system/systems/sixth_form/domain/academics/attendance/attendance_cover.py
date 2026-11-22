"""Cover registers for Sixth Form Attendance.

Sibling to :mod:`attendance`. A teacher is off; somebody else stands in
front of the class; the register still has to be taken. Without anywhere
to record that, three things go wrong at once:

* The chase list in :mod:`attendance_register` nags the absent teacher
  for a register they were never going to take.
* Whoever *did* take it appears in ``submitted_by`` with no explanation,
  and next term nobody can say why Miss Okafor submitted a Physics
  register she does not teach.
* A cover register is less trustworthy than a normal one — the person
  marking it does not know the faces — and nothing downstream can tell
  the two apart when a mark is later disputed.

So a cover arrangement is a row: which slot, which date, who is out, who
is standing in, and why. From it follow the useful questions —
:func:`unallocated` (which lessons still have nobody), :func:`can_mark`
(whether this person is allowed to touch this register), and
:func:`cover_load` (who has covered the most this term, because that is
how cover gets shared fairly or not at all).

Marks saved through :func:`save_cover_register` carry the ``cover`` data
source, so "was this taken by the usual teacher?" stays answerable
forever, not just while somebody remembers.

One cover store: ``cover_requests`` (:mod:`academics.cover.cover`) is
the record of cover. This table is the register's view of it and is kept
in step both ways — :func:`arrange` / :func:`allocate` / :func:`cancel` /
:func:`delete_cover` write through to ``cover_requests``, and every
cover-request change for a timetabled lesson writes back here (with
``_sync=False`` so neither side bounces the write back). Recording a
staff absence therefore puts the missed lessons on this sheet too.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_register as reg,
)
from education_system.systems.sixth_form.domain.academics.timetable import (
    timetable as tt,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

# Why the usual teacher is not there. Kept short and college-flavoured;
# the free-text note carries anything this list does not.
REASONS: tuple[str, ...] = (
    "Illness",
    "Medical appointment",
    "Training / CPD",
    "Trip",
    "Meeting",
    "Compassionate",
    "Exam duty",
    "Other",
)
DEFAULT_REASON: str = "Other"

# Unallocated is the state that matters: it is the list somebody has to
# clear before first period.
UNALLOCATED: str = "Unallocated"
ALLOCATED: str = "Allocated"
CANCELLED: str = "Cancelled"
STATES: tuple[str, ...] = (UNALLOCATED, ALLOCATED, CANCELLED)

# The data source stamped on marks taken by a covering teacher.
COVER_SOURCE: str = "cover"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_cover (
    cover_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id       INTEGER NOT NULL,
    date          TEXT NOT NULL,
    absent_teacher TEXT,
    cover_teacher TEXT,
    reason        TEXT NOT NULL DEFAULT 'Other',
    room          TEXT,
    state         TEXT NOT NULL DEFAULT 'Unallocated',
    notes         TEXT,
    arranged_by   TEXT,
    arranged_at   TEXT DEFAULT (datetime('now')),
    allocated_at  TEXT,
    cancelled_at  TEXT,
    UNIQUE(slot_id, date),
    FOREIGN KEY (slot_id) REFERENCES timetable_slots(slot_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_cover_date  ON attendance_cover(date);
CREATE INDEX IF NOT EXISTS idx_att_cover_state ON attendance_cover(state);
CREATE INDEX IF NOT EXISTS idx_att_cover_staff ON attendance_cover(cover_teacher);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Cover:
    """One lesson somebody else is taking."""

    cover_id: int
    slot_id: int
    date: str
    absent_teacher: str | None
    cover_teacher: str | None
    reason: str
    room: str | None
    state: str
    notes: str | None
    arranged_by: str | None
    arranged_at: str | None
    allocated_at: str | None
    cancelled_at: str | None

    @property
    def is_allocated(self) -> bool:
        return self.state == ALLOCATED and bool(self.cover_teacher)

    @property
    def is_live(self) -> bool:
        """Whether this arrangement still applies."""
        return self.state != CANCELLED

    @property
    def label(self) -> str:
        who = self.cover_teacher or "unallocated"
        return (f"{self.date} slot #{self.slot_id} — "
                f"{self.absent_teacher or '?'} out ({self.reason}), {who}")


@dataclass
class CoverRow:
    """A cover arrangement with the timetable detail staff recognise."""

    cover: Cover
    day: int
    period: int
    group_id: int
    group_name: str
    room: str | None
    register_state: str        # "Not started" | "Draft" | "Submitted"
    marked: int
    expected: int

    @property
    def is_marked(self) -> bool:
        return self.expected > 0 and self.marked >= self.expected


@dataclass
class CoverLoad:
    """How much cover one person has done."""

    teacher: str
    lessons: int
    dates: int


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
    # FKs onto slots, and every read here joins the register state.
    reg.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Cover schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> Cover:
    return Cover(
        cover_id=r["cover_id"],
        slot_id=r["slot_id"],
        date=r["date"],
        absent_teacher=r["absent_teacher"],
        cover_teacher=r["cover_teacher"],
        reason=r["reason"],
        room=r["room"],
        state=r["state"],
        notes=r["notes"],
        arranged_by=r["arranged_by"],
        arranged_at=r["arranged_at"],
        allocated_at=r["allocated_at"],
        cancelled_at=r["cancelled_at"],
    )


# ── Validation ──────────────────────────────────────────────────────

def validate_reason(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        return DEFAULT_REASON
    for reason in REASONS:
        if s.lower() == reason.lower():
            return reason
    raise ValidationError(f"Reason must be one of: {', '.join(REASONS)}")


def validate_state(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    for state in STATES:
        if s.lower() == state.lower():
            return state
    raise ValidationError(f"State must be one of: {', '.join(STATES)}")


def _validate_teacher(value: Any, label: str) -> str | None:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        return None
    if len(s) > 100:
        raise ValidationError(f"{label} must be 100 characters or fewer")
    return s


def _require_slot(slot_id: int) -> Any:
    slot = tt.get_slot(slot_id)
    if slot is None:
        raise ValidationError(f"No slot with id {slot_id}")
    return slot


def usual_teacher(slot_id: int) -> str | None:
    """Whoever normally teaches this slot.

    Group override first, then the course default — the same resolution
    the timetable's own clash check uses, so cover and clash detection
    never disagree about who owns a lesson.
    """
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    from education_system.systems.sixth_form.domain.academics.courses import (
        courses as _crs,
    )
    slot = tt.get_slot(slot_id)
    if slot is None:
        return None
    group = _cg.get_group(slot.group_id)
    if group is None:
        return None
    if group.teacher:
        return group.teacher
    course = _crs.get_course(group.course_id)
    return course.teacher if course else None


# ── Arranging cover ─────────────────────────────────────────────────

def arrange(
    slot_id: int,
    date: str,
    *,
    absent_teacher: str | None = None,
    cover_teacher: str | None = None,
    reason: str = DEFAULT_REASON,
    room: str | None = None,
    notes: str | None = None,
    actor: str | None = None,
    _sync: bool = True,
) -> Cover:
    """Record that a lesson needs covering.

    ``absent_teacher`` defaults to whoever the timetable says teaches
    the slot, so the common case is two arguments. Leaving
    ``cover_teacher`` out is not an omission — it is the *point* of the
    unallocated state, which is the list somebody works through.

    Re-arranging the same (slot, date) updates the existing row rather
    than adding a second one; a lesson is covered once.
    """
    init_db()
    date = reg._validate_date(date)
    _require_slot(slot_id)
    reason = validate_reason(reason)
    absent = _validate_teacher(absent_teacher, "Absent teacher") or \
        usual_teacher(slot_id)
    cover = _validate_teacher(cover_teacher, "Cover teacher")
    room = _validate_teacher(room, "Room")
    notes = (notes or "").strip() or None
    if cover and absent and cover.strip().lower() == absent.strip().lower():
        raise ValidationError(
            f"{cover} cannot cover their own lesson")
    state = ALLOCATED if cover else UNALLOCATED

    with _connect() as conn:
        conn.execute(
            """INSERT INTO attendance_cover
                   (slot_id, date, absent_teacher, cover_teacher, reason,
                    room, state, notes, arranged_by, allocated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                       CASE WHEN ? IS NULL THEN NULL ELSE datetime('now') END)
               ON CONFLICT(slot_id, date) DO UPDATE SET
                   absent_teacher = excluded.absent_teacher,
                   cover_teacher  = excluded.cover_teacher,
                   reason         = excluded.reason,
                   room           = excluded.room,
                   state          = excluded.state,
                   notes          = COALESCE(excluded.notes,
                                             attendance_cover.notes),
                   arranged_by    = excluded.arranged_by,
                   arranged_at    = datetime('now'),
                   allocated_at   = excluded.allocated_at,
                   cancelled_at   = NULL""",
            (slot_id, date, absent, cover, reason, room, state, notes,
             (actor or "").strip() or None, cover))
        conn.commit()
    logger.info("Cover arranged: slot #%d on %s (%s out, %s covering)",
                slot_id, date, absent or "?", cover or "unallocated")
    out = cover_for(slot_id, date)
    assert out is not None
    if _sync:
        _write_through(out)
    return out


def _write_through(row: Cover) -> None:
    """Mirror a register cover row into cover_requests (the one cover
    store)."""
    try:
        from education_system.systems.sixth_form.domain.academics.cover import (
            cover as _cover,
        )
        if not _cover.same_database(DB_PATH):
            return
        _cover.upsert_for_slot(
            row.slot_id, row.date, absent_teacher=row.absent_teacher,
            cover_teacher=row.cover_teacher, register_reason=row.reason,
            room=row.room, register_state=row.state)
    except Exception:
        logger.exception("Could not mirror register cover #%d to "
                         "cover_requests", row.cover_id)


def allocate(cover_id: int, cover_teacher: str, *,
             actor: str | None = None, _sync: bool = True) -> Cover:
    """Put a name against an unallocated lesson."""
    init_db()
    existing = get_cover(cover_id)
    if existing is None:
        raise ValidationError(f"No cover arrangement with id {cover_id}")
    if existing.state == CANCELLED:
        raise ValidationError(
            f"Cover #{cover_id} was cancelled — re-arrange it instead")
    teacher = _validate_teacher(cover_teacher, "Cover teacher")
    if not teacher:
        raise ValidationError("A cover teacher is required")
    if (existing.absent_teacher and
            teacher.lower() == existing.absent_teacher.lower()):
        raise ValidationError(f"{teacher} cannot cover their own lesson")

    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_cover
                  SET cover_teacher = ?, state = ?,
                      allocated_at = datetime('now'),
                      arranged_by = COALESCE(?, arranged_by)
                WHERE cover_id = ?""",
            (teacher, ALLOCATED, (actor or "").strip() or None, cover_id))
        conn.commit()
    logger.info("Cover #%d allocated to %s", cover_id, teacher)
    out = get_cover(cover_id)
    assert out is not None
    if _sync:
        _write_through(out)
    return out


def cancel(cover_id: int, *, reason: str | None = None,
           actor: str | None = None, _sync: bool = True) -> Cover:
    """Stand the cover down — the teacher came in after all."""
    init_db()
    existing = get_cover(cover_id)
    if existing is None:
        raise ValidationError(f"No cover arrangement with id {cover_id}")
    note = (reason or "").strip()
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_cover
                  SET state = ?, cancelled_at = datetime('now'),
                      notes = CASE WHEN ? = '' THEN notes
                                   ELSE COALESCE(notes || '; ', '') || ? END
                WHERE cover_id = ?""",
            (CANCELLED, note, f"Cancelled: {note}", cover_id))
        conn.commit()
    logger.info("Cover #%d cancelled (%s) by %s",
                cover_id, note or "no reason given", actor or "?")
    out = get_cover(cover_id)
    assert out is not None
    if _sync:
        _write_through(out)
    return out


def delete_cover(cover_id: int, *, _sync: bool = True) -> bool:
    """Remove an arrangement outright — for one entered by mistake.

    Prefer :func:`cancel` for anything that was ever real: who was asked
    to cover what is worth keeping even when it did not happen.
    """
    init_db()
    existing = get_cover(cover_id) if _sync else None
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM attendance_cover WHERE cover_id = ?", (cover_id,))
        conn.commit()
    if existing is not None and cur.rowcount:
        # Entered by mistake here means entered by mistake there too.
        try:
            from education_system.systems.sixth_form.domain.academics.cover import (
                cover as _cover,
            )
            req = (_cover.request_for_slot(existing.slot_id, existing.date)
                   if _cover.same_database(DB_PATH) else None)
            if req is not None:
                _cover.delete_request(req.cover_id, _sync=False)
        except Exception:
            logger.exception("Could not remove cover request for register "
                             "cover #%d", cover_id)
    return bool(cur.rowcount)


# ── Reads ───────────────────────────────────────────────────────────

def get_cover(cover_id: int) -> Cover | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_cover WHERE cover_id = ?",
            (cover_id,)).fetchone()
    return _row(r) if r else None


def cover_for(slot_id: int, date: str) -> Cover | None:
    """The live arrangement for one register, if there is one."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_cover WHERE slot_id = ? AND date = ?",
            (slot_id, reg._validate_date(date))).fetchone()
    return _row(r) if r else None


def is_covered(slot_id: int, date: str) -> bool:
    """Whether somebody other than the usual teacher is taking this."""
    cover = cover_for(slot_id, date)
    return bool(cover and cover.is_live)


def list_cover(
    *,
    date: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    slot_id: int | None = None,
    cover_teacher: str | None = None,
    absent_teacher: str | None = None,
    state: str | None = None,
    include_cancelled: bool = False,
) -> list[Cover]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if state:
        clauses.append("state = ?")
        args.append(validate_state(state))
    elif not include_cancelled:
        clauses.append("state != ?")
        args.append(CANCELLED)
    if date:
        clauses.append("date = ?")
        args.append(reg._validate_date(date))
    if date_from:
        clauses.append("date >= ?")
        args.append(reg._validate_date(date_from, "From date"))
    if date_to:
        clauses.append("date <= ?")
        args.append(reg._validate_date(date_to, "To date"))
    if slot_id is not None:
        clauses.append("slot_id = ?")
        args.append(slot_id)
    if cover_teacher:
        clauses.append("LOWER(cover_teacher) = ?")
        args.append(cover_teacher.strip().lower())
    if absent_teacher:
        clauses.append("LOWER(absent_teacher) = ?")
        args.append(absent_teacher.strip().lower())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_cover {where} "
            "ORDER BY date, slot_id", args).fetchall()
    return [_row(r) for r in rows]


def list_cover_with_detail(**kwargs: Any) -> list[CoverRow]:
    """:func:`list_cover` joined to the timetable and register state.

    This is the cover sheet somebody prints at 08:15: which room, which
    group, and — the column that matters by lunchtime — whether the
    register actually got taken.
    """
    init_db()
    covers = list_cover(**kwargs)
    if not covers:
        return []
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    slots = {s.slot_id: s for s in tt.list_slots()}
    groups = {g.group_id: g for g in _cg.list_groups()}

    keys = {(c.slot_id, c.date) for c in covers}
    with _connect() as conn:
        marked = {
            (r["slot_id"], r["date"]): r["n"]
            for r in conn.execute(
                "SELECT slot_id, date, COUNT(*) AS n FROM attendance_records "
                "WHERE voided = 0 GROUP BY slot_id, date").fetchall()
            if (r["slot_id"], r["date"]) in keys
        }
        states = {
            (r["slot_id"], r["date"]): r["state"]
            for r in conn.execute(
                "SELECT slot_id, date, state FROM register_sessions"
            ).fetchall()
            if (r["slot_id"], r["date"]) in keys
        }

    out: list[CoverRow] = []
    for cover in covers:
        slot = slots.get(cover.slot_id)
        group = groups.get(slot.group_id) if slot else None
        expected = (_cg.count_members(slot.group_id) if slot else 0)
        n_marked = marked.get((cover.slot_id, cover.date), 0)
        out.append(CoverRow(
            cover=cover,
            day=slot.day if slot else 0,
            period=slot.period if slot else 0,
            group_id=slot.group_id if slot else 0,
            group_name=group.group_name if group else "(unknown)",
            room=cover.room or (slot.room if slot else None),
            register_state=states.get(
                (cover.slot_id, cover.date),
                "Draft" if n_marked else "Not started"),
            marked=n_marked,
            expected=expected,
        ))
    return out


def unallocated(*, date_from: str | None = None,
                date_to: str | None = None) -> list[Cover]:
    """Lessons that still have nobody standing in front of them."""
    today = _dt.date.today().isoformat()
    return list_cover(state=UNALLOCATED,
                      date_from=date_from or today,
                      date_to=date_to)


def unallocated_count(**kwargs: Any) -> int:
    return len(unallocated(**kwargs))


def today_sheet(date: str | None = None) -> list[CoverRow]:
    """Everything being covered today, in period order."""
    day = date or _dt.date.today().isoformat()
    rows = list_cover_with_detail(date=day)
    rows.sort(key=lambda r: (r.period, r.cover.slot_id))
    return rows


def unmarked_cover(*, date: str | None = None) -> list[CoverRow]:
    """Covered lessons whose register nobody has taken.

    The register most likely to go missing is the one whose usual
    teacher is not in the building, which is exactly why this list is
    separate from the general chase list.
    """
    return [row for row in today_sheet(date)
            if row.cover.is_live and not row.is_marked]


# ── Who may mark ────────────────────────────────────────────────────

def who_should_mark(slot_id: int, date: str) -> str | None:
    """The person responsible for this register today.

    The allocated cover teacher when there is one, otherwise whoever
    normally teaches the slot.
    """
    cover = cover_for(slot_id, date)
    if cover and cover.is_live and cover.cover_teacher:
        return cover.cover_teacher
    return usual_teacher(slot_id)


def can_mark(slot_id: int, date: str, teacher: str | None) -> bool:
    """Whether ``teacher`` may take this register.

    Deliberately permissive in one direction: an *unallocated* cover
    lesson can be marked by anyone, because the alternative is a lesson
    that stays unmarked while somebody hunts for the person whose name
    should have been on it. An allocated one belongs to the cover
    teacher and to the usual teacher, and to nobody else.
    """
    name = (teacher or "").strip().lower()
    if not name:
        return False
    cover = cover_for(slot_id, date)
    usual = (usual_teacher(slot_id) or "").strip().lower()
    if cover is None or not cover.is_live:
        # No cover arranged: the usual teacher, or anyone if the
        # timetable does not name one.
        return not usual or name == usual
    if not cover.cover_teacher:
        return True
    return name in {cover.cover_teacher.strip().lower(), usual} - {""}


def assert_can_mark(slot_id: int, date: str, teacher: str | None) -> None:
    if not can_mark(slot_id, date, teacher):
        owner = who_should_mark(slot_id, date)
        raise ValidationError(
            f"{teacher or 'That account'} is not down to take slot "
            f"#{slot_id} on {date}"
            + (f" — {owner} is" if owner else ""))


def save_cover_register(
    slot_id: int,
    date: str,
    entries: dict[str, dict[str, Any]],
    *,
    cover_teacher: str,
    reason: str | None = None,
    allow_retro: bool = False,
) -> int:
    """Save a register as the covering teacher.

    Checks the person is actually down to take it, stamps every mark
    with the ``cover`` data source, and records them as the actor. A
    payload that names its own ``data_source`` is left alone — a kiosk
    check-in during a covered lesson is still a kiosk check-in.
    """
    init_db()
    date = reg._validate_date(date)
    teacher = _validate_teacher(cover_teacher, "Cover teacher")
    if not teacher:
        raise ValidationError("A cover teacher is required")
    assert_can_mark(slot_id, date, teacher)

    stamped = {
        sid: {**payload,
              "data_source": payload.get("data_source") or COVER_SOURCE}
        for sid, payload in entries.items()
    }
    written = core.save_register(slot_id, date, stamped, actor=teacher,
                                 reason=reason, allow_retro=allow_retro)
    logger.info("Cover register saved: slot #%d on %s by %s (%d row(s))",
                slot_id, date, teacher, written)
    return written


def submit_cover_register(
    slot_id: int,
    date: str,
    *,
    cover_teacher: str,
    notes: str | None = None,
    allow_incomplete: bool = False,
) -> Any:
    """Sign a covered register off, as the person who took it."""
    init_db()
    date = reg._validate_date(date)
    assert_can_mark(slot_id, date, cover_teacher)
    return reg.submit_register(slot_id, date, submitted_by=cover_teacher,
                               notes=notes,
                               allow_incomplete=allow_incomplete)


# ── Reporting ───────────────────────────────────────────────────────

def cover_load(*, date_from: str | None = None,
               date_to: str | None = None) -> list[CoverLoad]:
    """How many lessons each person has covered, busiest first.

    Cover is shared fairly or it is not, and the only way to know which
    is to count it.
    """
    init_db()
    clauses = ["state = ?", "cover_teacher IS NOT NULL"]
    args: list[Any] = [ALLOCATED]
    if date_from:
        clauses.append("date >= ?")
        args.append(reg._validate_date(date_from, "From date"))
    if date_to:
        clauses.append("date <= ?")
        args.append(reg._validate_date(date_to, "To date"))
    with _connect() as conn:
        rows = conn.execute(
            "SELECT cover_teacher AS t, COUNT(*) AS lessons, "
            "COUNT(DISTINCT date) AS dates FROM attendance_cover "
            f"WHERE {' AND '.join(clauses)} "
            "GROUP BY LOWER(cover_teacher) ORDER BY lessons DESC, t",
            args).fetchall()
    return [CoverLoad(teacher=r["t"], lessons=r["lessons"], dates=r["dates"])
            for r in rows]


def absence_load(*, date_from: str | None = None,
                 date_to: str | None = None) -> list[CoverLoad]:
    """The same count from the other side — whose lessons needed cover."""
    init_db()
    clauses = ["state != ?", "absent_teacher IS NOT NULL"]
    args: list[Any] = [CANCELLED]
    if date_from:
        clauses.append("date >= ?")
        args.append(reg._validate_date(date_from, "From date"))
    if date_to:
        clauses.append("date <= ?")
        args.append(reg._validate_date(date_to, "To date"))
    with _connect() as conn:
        rows = conn.execute(
            "SELECT absent_teacher AS t, COUNT(*) AS lessons, "
            "COUNT(DISTINCT date) AS dates FROM attendance_cover "
            f"WHERE {' AND '.join(clauses)} "
            "GROUP BY LOWER(absent_teacher) ORDER BY lessons DESC, t",
            args).fetchall()
    return [CoverLoad(teacher=r["t"], lessons=r["lessons"], dates=r["dates"])
            for r in rows]


def reason_breakdown(*, date_from: str | None = None,
                     date_to: str | None = None) -> dict[str, int]:
    """Cover lessons by reason over a window."""
    init_db()
    clauses = ["state != ?"]
    args: list[Any] = [CANCELLED]
    if date_from:
        clauses.append("date >= ?")
        args.append(reg._validate_date(date_from, "From date"))
    if date_to:
        clauses.append("date <= ?")
        args.append(reg._validate_date(date_to, "To date"))
    with _connect() as conn:
        rows = conn.execute(
            "SELECT reason, COUNT(*) AS n FROM attendance_cover "
            f"WHERE {' AND '.join(clauses)} GROUP BY reason "
            "ORDER BY n DESC", args).fetchall()
    return {r["reason"]: r["n"] for r in rows}


def marks_taken_under_cover(*, date_from: str | None = None,
                            date_to: str | None = None) -> int:
    """How many marks in the window were taken by a covering teacher."""
    return len(core.list_records(data_source=COVER_SOURCE,
                                 date_from=date_from, date_to=date_to))
