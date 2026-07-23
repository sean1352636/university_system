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
proposed cells into ``timetable_slots`` (replacing existing slots for
the affected groups).

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

from education_system.post_16.sixthform_system.core import paths
from education_system.post_16.sixthform_system.modules.domain.academics.timetable.timetable import (
    DAYS,
    DAY_NUMBERS,
    DEFAULT_PERIOD_TIMES,
    PERIODS,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.TIMETABLE_OPTIMISER_DB

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


# ── DB plumbing ──────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
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
    from education_system.post_16.sixthform_system.modules.domain.academics.class_groups import class_groups as _cg
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
    """Write a plan's proposed cells into the live ``timetable_slots``.

    For every group in the plan, existing live slots are cleared (when
    ``replace_existing``) before the proposed cells are inserted with
    the default period times. Returns the number of live slots written.
    """
    init_db()
    slots = plan_slots(plan_id)
    if not slots:
        raise ValueError(f"Plan {plan_id} has no slots")
    group_ids = {s.group_id for s in slots}
    with _connect() as conn:
        if replace_existing:
            conn.executemany(
                "DELETE FROM timetable_slots WHERE group_id=?",
                [(gid,) for gid in group_ids],
            )
        written = 0
        for s in slots:
            start, end = DEFAULT_PERIOD_TIMES.get(s.period, (None, None))
            try:
                conn.execute(
                    "INSERT INTO timetable_slots (group_id, day, period, start_time, end_time, room) "
                    "VALUES (?,?,?,?,?,?)",
                    (s.group_id, s.day, s.period, start, end, s.room),
                )
                written += 1
            except sqlite3.IntegrityError:
                logger.warning("Skipped clashing slot for group %s at %s/%s",
                               s.group_id, s.day, s.period)
        conn.execute(
            "UPDATE optimiser_plans SET status='Committed', committed_at=datetime('now') "
            "WHERE plan_id=?", (plan_id,))
        conn.commit()
    logger.info("Committed plan %d → %d live slots", plan_id, written)
    return written
