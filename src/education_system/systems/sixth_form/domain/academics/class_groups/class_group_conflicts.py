"""Timetable clash detection for Sixth Form class groups.

:mod:`...academics.timetable` already refuses to save a slot into an
occupied room and warns about teacher and student double-bookings. That
check runs at write time, one slot at a time, against the slot being
saved. It cannot answer the questions asked *after* the timetable
exists: is this group clash-free? does this teacher's whole week work?
which of my students are double-booked?

Those are read-time audits over many slots, and running the timetable's
per-slot helpers in a loop is the N+1 trap — a hundred slots is a
hundred queries plus a group and course lookup inside each one. Every
function here loads the slots it needs in a single query and resolves
clashes in memory.

**Effective room and teacher.** A slot may name a room; if it does not,
the group's room applies, and failing that the course's. Teacher is the
group's, else the course's. The timetable's own room check only looks at
``timetable_slots.room``, so a group of lessons that inherit their room
from the course will pass that check and still collide in reality. This
module resolves the full fallback chain, which is why it finds clashes
the write-time check does not.

**Clashes are reported, never fixed.** Nothing here writes. A room
double-booking might be two halves of a split class in one big room, and
only a human knows.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from education_system import paths
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_group_logging as cg_log,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_group_membership as membership,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_group_schedule as schedule_text,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_groups as core,
)

logger = cg_log.get_logger(__name__)

DB_PATH = paths.SIXTH_FORM_CLASS_GROUPS_DB

ValidationError = core.ValidationError
ClassGroup = core.ClassGroup
ScheduleWindow = schedule_text.ScheduleWindow

#: The kinds of collision this module reports.
CLASH_KINDS: tuple[str, ...] = ("room", "teacher", "student")


@dataclass
class SlotView:
    """A timetable slot with its group, course and inherited attributes."""
    slot_id: int
    group_id: int
    group_name: str
    course_id: int
    course_code: str | None
    day: int
    period: int
    room: str | None      # effective: slot -> group -> course
    teacher: str | None   # effective: group -> course
    room_source: str | None
    start: str
    end: str

    @property
    def window(self) -> ScheduleWindow:
        day_name = schedule_text.DAY_NAMES[self.day - 1]
        return ScheduleWindow(day=day_name, start=self.start, end=self.end)

    @property
    def day_name(self) -> str:
        return schedule_text.DAY_NAMES[self.day - 1]

    def __str__(self) -> str:
        return (f"{self.group_name} {self.day_name} P{self.period} "
                f"({self.start}-{self.end})")


@dataclass
class Clash:
    """One collision between two slots, or between a slot and a proposal."""
    kind: str                      # 'room' | 'teacher' | 'student'
    day: str
    period: int
    start: str
    end: str
    group_id: int
    group_name: str
    other_group_id: int | None = None
    other_group_name: str | None = None
    #: The room or teacher in contention; for a student clash, unused.
    resource: str | None = None
    #: Student ids double-booked (student clashes only).
    students: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Feature 27 was specified as returning dicts; this is that shape."""
        return {
            "kind": self.kind, "day": self.day, "period": self.period,
            "start": self.start, "end": self.end,
            "group_id": self.group_id, "group_name": self.group_name,
            "other_group_id": self.other_group_id,
            "other_group_name": self.other_group_name,
            "resource": self.resource, "students": list(self.students),
            "description": str(self),
        }

    def __str__(self) -> str:
        where = f"{self.day} P{self.period} ({self.start}-{self.end})"
        if self.kind == "student":
            names = ", ".join(self.students[:5])
            more = f" +{len(self.students) - 5} more" if len(self.students) > 5 else ""
            return (f"{where}: {len(self.students)} student(s) also in "
                    f"'{self.other_group_name}' — {names}{more}")
        return (f"{where}: {self.kind} '{self.resource}' shared with "
                f"'{self.other_group_name}'")


# One query for every slot plus the group/course fallbacks. Everything in
# this module starts here rather than re-querying per slot.
_SLOT_SQL = """
    SELECT t.slot_id, t.group_id, t.day, t.period,
           t.start_time, t.end_time,
           t.room AS slot_room,
           cg.group_name, cg.course_id,
           cg.room     AS group_room,
           cg.teacher  AS group_teacher,
           c.course_code,
           c.room      AS course_room,
           c.teacher   AS course_teacher
      FROM timetable_slots t
      JOIN class_groups cg ON cg.group_id = t.group_id
      LEFT JOIN courses  c ON c.course_id = cg.course_id
"""


def _slot_view(r: sqlite3.Row) -> SlotView | None:
    day = int(r["day"])
    if not 1 <= day <= len(schedule_text.DAY_NAMES):
        return None
    start, end = r["start_time"], r["end_time"]
    if not start or not end:
        fallback = schedule_text.PERIOD_TIMES.get(int(r["period"]))
        if fallback is None:
            return None
        start, end = fallback
    room = r["slot_room"] or r["group_room"] or r["course_room"]
    room_source = ("slot" if r["slot_room"] else
                   "group" if r["group_room"] else
                   "course" if r["course_room"] else None)
    return SlotView(
        slot_id=r["slot_id"], group_id=r["group_id"],
        group_name=r["group_name"], course_id=r["course_id"],
        course_code=r["course_code"], day=day, period=int(r["period"]),
        room=room, teacher=(r["group_teacher"] or r["course_teacher"]),
        room_source=room_source, start=start, end=end,
    )


def all_slots(*, course_id: int | None = None,
              group_ids: Sequence[int] | None = None) -> list[SlotView]:
    """Every timetable slot, with inherited room and teacher resolved."""
    core.init_db()
    from education_system.systems.sixth_form.domain.academics.timetable \
        import timetable as _tt
    _tt.init_db()

    clauses: list[str] = []
    args: list[Any] = []
    if course_id is not None:
        clauses.append("cg.course_id = ?")
        args.append(int(course_id))
    if group_ids is not None:
        if not group_ids:
            return []
        marks = ",".join("?" * len(group_ids))
        clauses.append(f"t.group_id IN ({marks})")
        args.extend(int(g) for g in group_ids)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"{_SLOT_SQL} {where} ORDER BY t.day, t.period, cg.group_name"
    with membership._txn() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [v for v in (_slot_view(r) for r in rows) if v is not None]


def _same_time(a: SlotView, b: SlotView) -> bool:
    """Whether two slots collide.

    Same day and period is a collision by definition — that is what a
    period *is*, and two slots in one period clash even if somebody has
    typed odd times on them. Otherwise fall back to comparing clock
    times, which catches lessons placed in different periods that
    nonetheless overlap.
    """
    if a.day != b.day:
        return False
    if a.period == b.period:
        return True
    return a.window.overlaps(b.window)


def _norm(value: str | None) -> str | None:
    v = (value or "").strip().lower()
    return v or None


# ── 27. Everything wrong with one group's timetable ─────────────────

def clash_check(group_id: int,
                *,
                kinds: Iterable[str] = CLASH_KINDS,
                _slots: Sequence[SlotView] | None = None) -> list[Clash]:
    """Every room, teacher and student collision affecting one group.

    Two queries total regardless of how many slots the group has: one
    for the slots, one for the shared-student counts.

    Returns :class:`Clash` objects; call ``.as_dict()`` on each for the
    plain-dict form.

    ``_slots`` lets a caller checking many groups load the timetable
    once and pass it in — see :func:`course_clash_summary`.
    """
    wanted = {k for k in kinds}
    unknown = wanted - set(CLASH_KINDS)
    if unknown:
        raise ValidationError(
            f"Unknown clash kind(s): {', '.join(sorted(unknown))}; "
            f"expected {', '.join(CLASH_KINDS)}")
    group = membership._require_group(group_id)

    everything = list(_slots) if _slots is not None else all_slots()
    mine = [s for s in everything if s.group_id == group.group_id]
    if not mine:
        return []
    others = [s for s in everything if s.group_id != group.group_id]

    clashes: list[Clash] = []
    student_pairs: set[tuple[int, int, int]] = set()

    for slot in mine:
        for other in others:
            if not _same_time(slot, other):
                continue
            if "room" in wanted and slot.room and other.room \
                    and _norm(slot.room) == _norm(other.room):
                clashes.append(Clash(
                    kind="room", day=slot.day_name, period=slot.period,
                    start=slot.start, end=slot.end,
                    group_id=slot.group_id, group_name=slot.group_name,
                    other_group_id=other.group_id,
                    other_group_name=other.group_name, resource=slot.room))
            if "teacher" in wanted and slot.teacher and other.teacher \
                    and _norm(slot.teacher) == _norm(other.teacher):
                clashes.append(Clash(
                    kind="teacher", day=slot.day_name, period=slot.period,
                    start=slot.start, end=slot.end,
                    group_id=slot.group_id, group_name=slot.group_name,
                    other_group_id=other.group_id,
                    other_group_name=other.group_name,
                    resource=slot.teacher))
            if "student" in wanted:
                student_pairs.add((slot.day, slot.period, other.group_id))

    if student_pairs:
        shared = _shared_students(group.group_id,
                                  {g for _, _, g in student_pairs})
        for slot in mine:
            for other in others:
                if not _same_time(slot, other):
                    continue
                ids = shared.get(other.group_id)
                if ids:
                    clashes.append(Clash(
                        kind="student", day=slot.day_name, period=slot.period,
                        start=slot.start, end=slot.end,
                        group_id=slot.group_id, group_name=slot.group_name,
                        other_group_id=other.group_id,
                        other_group_name=other.group_name,
                        students=sorted(ids)))

    if clashes:
        cg_log.group_event(
            logger, "clash_check on class group #%d (%s): %d clash(es) — %s",
            group.group_id, group.group_name, len(clashes),
            "; ".join(str(c) for c in clashes[:5]),
            group_id=group.group_id, level=30,
        )
    return clashes


def _shared_students(group_id: int,
                     other_ids: set[int]) -> dict[int, set[str]]:
    """Students in ``group_id`` who are also in each of ``other_ids``.

    One query for all the other groups at once.
    """
    if not other_ids:
        return {}
    marks = ",".join("?" * len(other_ids))
    sql = f"""
        SELECT b.group_id AS other_id, a.student_id
          FROM class_group_students a
          JOIN class_group_students b ON b.student_id = a.student_id
         WHERE a.group_id = ? AND b.group_id IN ({marks})
    """
    with membership._txn() as conn:
        rows = conn.execute(sql, [int(group_id), *sorted(other_ids)]).fetchall()
    out: dict[int, set[str]] = {}
    for r in rows:
        out.setdefault(r["other_id"], set()).add(r["student_id"])
    return out


# ── 28. Is this teacher free? ───────────────────────────────────────

def teacher_conflicts(teacher: str,
                      schedule: str | Iterable[ScheduleWindow] | None = None,
                      *,
                      exclude_group_id: int | None = None
                      ) -> list[ClassGroup]:
    """Groups this teacher already teaches at the given times.

    ``schedule`` may be a free-text string (parsed by
    :func:`class_group_schedule.parse_schedule`) or ready-made windows.
    Pass it when checking a *proposed* commitment — "can Ms Diaz take
    Mon P3?".

    With ``schedule`` omitted, this instead returns the groups where the
    teacher is already double-booked against themselves, which is the
    audit form.

    Matching is on the effective teacher: the group's own, else the
    course's.
    """
    name = _norm(teacher)
    if not name:
        raise ValidationError("A teacher name is required")

    theirs = [s for s in all_slots()
              if _norm(s.teacher) == name
              and s.group_id != exclude_group_id]
    if not theirs:
        return []

    if schedule is None:
        hits = {s.group_id for a in theirs for s in theirs
                if a.slot_id != s.slot_id and _same_time(a, s)}
    else:
        windows = _as_windows(schedule)
        if not windows:
            return []
        hits = {s.group_id for s in theirs
                if any(s.window.overlaps(w) for w in windows)}

    groups = [g for g in (core.get_group(g) for g in sorted(hits))
              if g is not None]
    if groups:
        cg_log.group_event(
            logger, "teacher_conflicts for %r: %d group(s) — %s",
            teacher, len(groups), ", ".join(g.group_name for g in groups),
            level=30,
        )
    return groups


# ── 29. Is this room free? ──────────────────────────────────────────

def room_conflicts(room: str,
                   schedule: str | Iterable[ScheduleWindow] | None = None,
                   *,
                   exclude_group_id: int | None = None) -> list[ClassGroup]:
    """Groups already using this room at the given times.

    Same shape as :func:`teacher_conflicts`, and the same two modes.
    Resolves the room fallback chain (slot, then group, then course), so
    it catches collisions the timetable's own write-time check misses.
    """
    name = _norm(room)
    if not name:
        raise ValidationError("A room is required")

    here = [s for s in all_slots()
            if _norm(s.room) == name and s.group_id != exclude_group_id]
    if not here:
        return []

    if schedule is None:
        hits = {s.group_id for a in here for s in here
                if a.slot_id != s.slot_id and _same_time(a, s)}
    else:
        windows = _as_windows(schedule)
        if not windows:
            return []
        hits = {s.group_id for s in here
                if any(s.window.overlaps(w) for w in windows)}

    groups = [g for g in (core.get_group(g) for g in sorted(hits))
              if g is not None]
    if groups:
        cg_log.group_event(
            logger, "room_conflicts for %r: %d group(s) — %s",
            room, len(groups), ", ".join(g.group_name for g in groups),
            level=30,
        )
    return groups


def _as_windows(
        schedule: str | Iterable[ScheduleWindow]) -> list[ScheduleWindow]:
    if isinstance(schedule, str):
        return schedule_text.parse_schedule(schedule)
    return list(schedule)


# ── 30. Is this student double-booked? ──────────────────────────────

def student_timetable_clashes(
        student_id: str) -> list[tuple[ClassGroup, ClassGroup]]:
    """Pairs of this student's groups that meet at the same time.

    Each colliding pair is returned once, with the lower group id first,
    so a caller can render them without de-duplicating.

    One query: the student's groups joined to their slots on both sides.
    """
    sid = core._require(student_id, "Student ID")
    core.init_db()
    from education_system.systems.sixth_form.domain.academics.timetable \
        import timetable as _tt
    _tt.init_db()

    with membership._txn() as conn:
        rows = conn.execute(
            f"{_SLOT_SQL} JOIN class_group_students cgs "
            "  ON cgs.group_id = t.group_id "
            "WHERE cgs.student_id = ? ORDER BY t.day, t.period",
            (sid,),
        ).fetchall()
    slots = [v for v in (_slot_view(r) for r in rows) if v is not None]

    seen: set[tuple[int, int]] = set()
    pairs: list[tuple[ClassGroup, ClassGroup]] = []
    cache: dict[int, ClassGroup | None] = {}

    def group(gid: int) -> ClassGroup | None:
        if gid not in cache:
            cache[gid] = core.get_group(gid)
        return cache[gid]

    for i, a in enumerate(slots):
        for b in slots[i + 1:]:
            if a.group_id == b.group_id or not _same_time(a, b):
                continue
            key = (min(a.group_id, b.group_id), max(a.group_id, b.group_id))
            if key in seen:
                continue
            seen.add(key)
            ga, gb = group(key[0]), group(key[1])
            if ga and gb:
                pairs.append((ga, gb))

    if pairs:
        cg_log.student_event(
            logger, "%s is double-booked across %d group pair(s): %s",
            sid, len(pairs),
            "; ".join(f"{a.group_name}/{b.group_name}" for a, b in pairs),
            student_id=sid, level=30,
        )
    return pairs


def course_clash_summary(course_id: int) -> dict[str, list[Clash]]:
    """Every clash affecting any group on a course, keyed by group name.

    The whole-course form of :func:`clash_check`, for a department
    reviewing its own timetable before term.
    """
    everything = all_slots()
    out: dict[str, list[Clash]] = {}
    for group in core.list_groups(course_id=int(course_id)):
        found = clash_check(group.group_id, _slots=everything)
        if found:
            out[group.group_name] = found
    return out
