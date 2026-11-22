"""Constraint-based timetable optimiser for the Sixth Form System.

The live ``timetable_slots`` table is hand-maintained: staff pin one
class group to one (day, period) cell at a time. This module automates
the first draft. Given the existing ``class_groups`` (each with a
teacher, a room and a roster of students), it searches the 5×6 weekly
grid for a clash-free assignment of *N* lessons per group per week.

Hard constraints (never violated by the generator):

* a class group occupies a (day, period) cell at most once;
* a teacher is in at most one place per (day, period);
* a room hosts at most one group per (day, period).

Soft constraint (minimised, not forbidden): **student clashes** — two
groups sharing students should avoid the same cell. The seed data lets
a group exceed its room, so we treat student overlap as a cost the
greedy search tries to drive to zero, reporting any residue.

The result is staged as a **plan** (``optimiser_plans`` +
``optimiser_plan_slots``) rather than written straight to the live
timetable. Staff review it, then ``commit_plan(...)`` copies the
proposed cells into ``timetable_slots``: existing slots are kept or
moved in place, new ones inserted, and a slot is deleted only when no
attendance or register history hangs off it (one that has history is
ended — archived — instead, so the cascade can never take attendance).

The search is deterministic (most-constrained group first, lowest-cost
cell first, ties broken by day/period order) so re-running on the same
data yields the same plan.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.domain.academics.timetable.timetable import (
    DAYS,
    DAY_NUMBERS,
    DEFAULT_PERIOD_TIMES,
    PERIODS,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_TIMETABLE_OPTIMISER_DB

DEFAULT_LESSONS_PER_WEEK = 5
PLAN_STATUSES = ("Draft", "Committed")


@dataclass
class ProposedSlot:
    group_id: int
    group_label: str
    day: int
    period: int
    room: str | None


@dataclass
class PlanResult:
    plan_id: int | None
    name: str
    lessons_per_week: int
    slots: list[ProposedSlot] = field(default_factory=list)
    unplaced: list[str] = field(default_factory=list)
    student_clashes: list[str] = field(default_factory=list)
    teacher_count: int = 0
    group_count: int = 0

    @property
    def placed(self) -> int:
        return len(self.slots)


@dataclass
class CommitResult:
    """What :func:`commit_plan_detailed` did to the live timetable."""
    plan_id: int
    kept: int = 0          # slot already in the planned cell (room/times refreshed)
    moved: int = 0         # empty slot moved in place to a planned cell
    inserted: int = 0      # new slot
    deleted: int = 0       # empty slot no longer needed
    #: Slots with attendance/register history that the plan no longer
    #: uses: ended (archived) rather than deleted, history intact.
    ended: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)   # could not be written

    @property
    def written(self) -> int:
        """Planned cells now live on the timetable."""
        return self.kept + self.moved + self.inserted

    def summary(self) -> str:
        lines = [f"{self.written} planned lesson(s) are now live: "
                 f"{self.kept} unchanged, {self.moved} moved, "
                 f"{self.inserted} new.",
                 f"{self.deleted} unused empty slot(s) removed."]
        if self.ended:
            lines.append(
                f"{len(self.ended)} slot(s) with attendance history were "
                "taken off the timetable but kept (archived), so no "
                "attendance was lost:")
            lines.extend(f"  • {e}" for e in self.ended)
        if self.skipped:
            lines.append(f"{len(self.skipped)} cell(s) could not be written:")
            lines.extend(f"  • {e}" for e in self.skipped)
        return "\n".join(lines)


# ── DB plumbing ──────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS optimiser_plans (
    plan_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'Draft',
    lessons_per_week INTEGER NOT NULL DEFAULT 5,
    stats_json       TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    committed_at     TEXT
);

CREATE TABLE IF NOT EXISTS optimiser_plan_slots (
    plan_slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id      INTEGER NOT NULL,
    group_id     INTEGER NOT NULL,
    day          INTEGER NOT NULL,
    period       INTEGER NOT NULL,
    room         TEXT,
    FOREIGN KEY (plan_id)  REFERENCES optimiser_plans(plan_id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES class_groups(group_id)   ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_optslot_plan ON optimiser_plan_slots(plan_id);
"""

_DB_READY = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.academics.class_groups import class_groups as _cg
    _cg.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True
    logger.debug("Timetable-optimiser schema ready at %s", DB_PATH)


# ── Demand loading ───────────────────────────────────────────────────

@dataclass
class _Group:
    group_id: int
    label: str
    teacher: str | None
    room: str | None
    students: frozenset[str]


def _load_groups(conn: sqlite3.Connection) -> list[_Group]:
    rows = conn.execute(
        """
        SELECT g.group_id, g.group_name, g.teacher,
               COALESCE(g.room, c.room) AS room, c.title, c.course_code
          FROM class_groups g
          JOIN courses c ON c.course_id = g.course_id
         WHERE g.archived_at IS NULL AND c.archived_at IS NULL
         ORDER BY g.group_id
        """
    ).fetchall()
    groups: list[_Group] = []
    for r in rows:
        srows = conn.execute(
            "SELECT student_id FROM class_group_students WHERE group_id=?",
            (r["group_id"],),
        ).fetchall()
        label = f"{r['course_code']} · {r['group_name']}"
        groups.append(_Group(
            group_id=r["group_id"], label=label, teacher=r["teacher"],
            room=r["room"], students=frozenset(s["student_id"] for s in srows)))
    return groups


# ── The solver ───────────────────────────────────────────────────────

_CELLS: list[tuple[int, int]] = [(d, p) for d in DAY_NUMBERS for p in PERIODS]


def generate(*, lessons_per_week: int = DEFAULT_LESSONS_PER_WEEK,
             name: str = "Auto plan") -> PlanResult:
    """Build a clash-free draft assignment (without persisting).

    Greedy + most-constrained-first. Each group needs ``lessons_per_week``
    distinct cells; for each we pick the lowest-cost free cell where the
    teacher and room are unused, preferring cells with no student overlap.
    """
    init_db()
    with _connect() as conn:
        groups = _load_groups(conn)

    if lessons_per_week < 1 or lessons_per_week > len(_CELLS):
        raise ValueError(
            f"lessons_per_week must be 1..{len(_CELLS)}")

    # Occupancy maps keyed by (day, period).
    teacher_busy: dict[tuple[int, int], set[str]] = {c: set() for c in _CELLS}
    room_busy: dict[tuple[int, int], set[str]] = {c: set() for c in _CELLS}
    students_in_cell: dict[tuple[int, int], set[str]] = {c: set() for c in _CELLS}

    # Most-constrained first: bigger rosters + a fixed room/teacher are
    # harder to place, so schedule them while the grid is empty.
    order = sorted(groups, key=lambda g: (-len(g.students), g.group_id))

    slots: list[ProposedSlot] = []
    unplaced: list[str] = []
    clash_notes: list[str] = []

    for g in order:
        used_cells: set[tuple[int, int]] = set()
        for _ in range(lessons_per_week):
            best: tuple[tuple[int, ...], tuple[int, int]] | None = None
            for cell in _CELLS:
                if cell in used_cells:
                    continue
                if g.teacher and g.teacher in teacher_busy[cell]:
                    continue
                if g.room and g.room in room_busy[cell]:
                    continue
                overlap = len(g.students & students_in_cell[cell])
                # cost: minimise student overlap, then keep the week
                # spread (prefer empty cells), then natural cell order.
                cost = (overlap, len(students_in_cell[cell]))
                if best is None or cost < best[0]:
                    best = (cost, cell)
                    if cost == (0, 0):
                        break  # perfect cell, stop scanning
            if best is None:
                unplaced.append(f"{g.label} (period {_+1} of {lessons_per_week})")
                continue
            (overlap, _), cell = best
            used_cells.add(cell)
            if g.teacher:
                teacher_busy[cell].add(g.teacher)
            if g.room:
                room_busy[cell].add(g.room)
            if overlap:
                clash_notes.append(
                    f"{g.label} shares {overlap} student(s) at "
                    f"{DAYS[cell[0]-1]} P{cell[1]}")
            students_in_cell[cell] |= g.students
            slots.append(ProposedSlot(
                group_id=g.group_id, group_label=g.label,
                day=cell[0], period=cell[1], room=g.room))

    teachers = {g.teacher for g in groups if g.teacher}
    return PlanResult(
        plan_id=None, name=name, lessons_per_week=lessons_per_week,
        slots=slots, unplaced=unplaced, student_clashes=clash_notes,
        teacher_count=len(teachers), group_count=len(groups))


# ── Persistence ──────────────────────────────────────────────────────

def save_plan(result: PlanResult, *, notes: str = "") -> int:
    """Persist a generated plan as a Draft and return its plan_id."""
    init_db()
    stats = {
        "placed": result.placed, "unplaced": len(result.unplaced),
        "student_clashes": len(result.student_clashes),
        "groups": result.group_count, "teachers": result.teacher_count,
    }
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO optimiser_plans (name, status, lessons_per_week, stats_json, notes) "
            "VALUES (?, 'Draft', ?, ?, ?)",
            (result.name, result.lessons_per_week, json.dumps(stats), notes or None),
        )
        plan_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO optimiser_plan_slots (plan_id, group_id, day, period, room) "
            "VALUES (?,?,?,?,?)",
            [(plan_id, s.group_id, s.day, s.period, s.room) for s in result.slots],
        )
        conn.commit()
    result.plan_id = plan_id
    logger.info("Saved optimiser plan %d (%d slots)", plan_id, result.placed)
    return plan_id


def list_plans() -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM optimiser_plans ORDER BY plan_id DESC"
        ).fetchall()
    out = []
    for r in rows:
        out.append({
            "plan_id": r["plan_id"], "name": r["name"], "status": r["status"],
            "lessons_per_week": r["lessons_per_week"],
            "stats": json.loads(r["stats_json"] or "{}"),
            "created_at": r["created_at"], "committed_at": r["committed_at"],
        })
    return out


def plan_slots(plan_id: int) -> list[ProposedSlot]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT s.group_id, s.day, s.period, s.room,
                   g.group_name, c.course_code
              FROM optimiser_plan_slots s
              JOIN class_groups g ON g.group_id = s.group_id
              JOIN courses c      ON c.course_id = g.course_id
             WHERE s.plan_id=?
             ORDER BY s.day, s.period
            """,
            (plan_id,),
        ).fetchall()
    return [ProposedSlot(
        group_id=r["group_id"],
        group_label=f"{r['course_code']} · {r['group_name']}",
        day=r["day"], period=r["period"], room=r["room"]) for r in rows]


def delete_plan(plan_id: int) -> None:
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM optimiser_plans WHERE plan_id=?", (plan_id,))
        conn.commit()


def commit_plan(plan_id: int, *, replace_existing: bool = True) -> int:
    """Write a plan into the live timetable; returns the number of planned
    cells now live. See :func:`commit_plan_detailed` for the full outcome."""
    return commit_plan_detailed(
        plan_id, replace_existing=replace_existing).written


def commit_plan_detailed(plan_id: int, *,
                         replace_existing: bool = True) -> CommitResult:
    """Write a plan's proposed cells into the live ``timetable_slots``.

    Per group in the plan:

    1. a slot (live or archived) already in a planned cell is kept and
       its room / default times refreshed;
    2. remaining planned cells reuse the group's other live slots that
       have **no** attendance/register history, moved in place;
    3. anything still unplaced is inserted;
    4. with ``replace_existing``, leftover live slots are deleted when
       they have no history, and *ended* (archived) when they do — a
       slot with registers is never deleted or moved, because that would
       cascade away or re-label its attendance.
    """
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    init_db()
    _tt.init_db()
    slots = plan_slots(plan_id)
    if not slots:
        raise ValueError(f"Plan {plan_id} has no slots")
    result = CommitResult(plan_id=plan_id)
    by_group: dict[int, list[ProposedSlot]] = {}
    for s in slots:
        by_group.setdefault(s.group_id, []).append(s)

    # Read every affected slot (and whether it has history) before writing.
    existing: dict[int, list[sqlite3.Row]] = {}
    has_history: dict[int, bool] = {}
    with _connect() as conn:
        for gid in by_group:
            rows = conn.execute(
                "SELECT * FROM timetable_slots WHERE group_id=? "
                "ORDER BY day, period", (gid,)).fetchall()
            existing[gid] = rows
            for r in rows:
                has_history[r["slot_id"]] = bool(_tt.history_counts(r["slot_id"]))

    def times(period: int) -> tuple[str | None, str | None]:
        return DEFAULT_PERIOD_TIMES.get(period, (None, None))

    with _connect() as conn:
        for gid, planned in by_group.items():
            rows = existing[gid]
            label = planned[0].group_label
            by_cell = {(r["day"], r["period"]): r for r in rows}
            used: set[int] = set()
            todo: list[ProposedSlot] = []
            for p in planned:
                r = by_cell.get((p.day, p.period))
                if r is None:
                    todo.append(p)
                    continue
                start, end = times(p.period)
                conn.execute(
                    "UPDATE timetable_slots SET room=?, start_time=?, end_time=?, "
                    "archived_at=NULL WHERE slot_id=?",
                    (p.room, start, end, r["slot_id"]))
                used.add(r["slot_id"])
                result.kept += 1
            spare = [r for r in rows if r["slot_id"] not in used
                     and r["archived_at"] is None
                     and not has_history[r["slot_id"]]]
            for p in todo:
                start, end = times(p.period)
                try:
                    if spare:
                        r = spare.pop(0)
                        conn.execute(
                            "UPDATE timetable_slots SET day=?, period=?, room=?, "
                            "start_time=?, end_time=? WHERE slot_id=?",
                            (p.day, p.period, p.room, start, end, r["slot_id"]))
                        used.add(r["slot_id"])
                        result.moved += 1
                    else:
                        conn.execute(
                            "INSERT INTO timetable_slots (group_id, day, period, "
                            "start_time, end_time, room) VALUES (?,?,?,?,?,?)",
                            (gid, p.day, p.period, start, end, p.room))
                        result.inserted += 1
                except sqlite3.IntegrityError as e:
                    logger.warning("Skipped clashing slot for group %s at %s/%s: %s",
                                   gid, p.day, p.period, e)
                    result.skipped.append(
                        f"{label} {DAYS[p.day - 1]} P{p.period}: {e}")
            if not replace_existing:
                continue
            for r in rows:
                if r["slot_id"] in used or r["archived_at"] is not None:
                    continue
                cell = f"{label} {DAYS[r['day'] - 1]} P{r['period']} (slot #{r['slot_id']})"
                if has_history[r["slot_id"]]:
                    conn.execute(
                        "UPDATE timetable_slots SET archived_at=datetime('now') "
                        "WHERE slot_id=?", (r["slot_id"],))
                    result.ended.append(cell)
                else:
                    conn.execute("DELETE FROM timetable_slots WHERE slot_id=?",
                                 (r["slot_id"],))
                    result.deleted += 1
        conn.execute(
            "UPDATE optimiser_plans SET status='Committed', committed_at=datetime('now') "
            "WHERE plan_id=?", (plan_id,))
        conn.commit()
    logger.info("Committed plan %d → %d live slots (kept %d, moved %d, new %d, "
                "deleted %d, ended %d, skipped %d)", plan_id, result.written,
                result.kept, result.moved, result.inserted, result.deleted,
                len(result.ended), len(result.skipped))
    return result
