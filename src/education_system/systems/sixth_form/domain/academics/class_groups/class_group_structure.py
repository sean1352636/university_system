"""Splitting and merging Sixth Form class groups.

Both operations here change the *set* of groups on a course, not just
who is in them, which makes them the two riskiest things in this
package. A split that half-happens leaves a course with a group nobody
meant to create; a merge that half-happens loses a roster.

So both are atomic, both are dry-runnable, and neither deletes anything
by default. :func:`merge_groups` empties the source groups and leaves
them in place unless explicitly asked to remove them — a stale empty
group is a five-second fix, a deleted group with its timetable and
history context gone is not.

Naming is the part that cannot be automated safely. ``12M-1`` splits
into ``12M-1a``/``12M-1b`` by default, but a department with its own
scheme should pass ``names=`` explicitly; the generated names are
checked for collisions before anything is written, because
``class_groups`` has a UNIQUE(course_id, group_name) constraint that
would otherwise surface as an IntegrityError halfway through.
"""

from __future__ import annotations

import string
from dataclasses import dataclass, field
from typing import Any, Sequence

from education_system import paths
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_group_capacity as capacity,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_group_history as history,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_group_logging as cg_log,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_group_membership as membership,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_groups as core,
)

logger = cg_log.get_logger(__name__)

DB_PATH = paths.SIXTH_FORM_CLASS_GROUPS_DB

ValidationError = core.ValidationError
ClassGroup = core.ClassGroup

#: Suffixes appended to the original name when splitting. Letters rather
#: than digits, so '12M-1' becomes '12M-1a' and cannot be mistaken for
#: the sibling set '12M-2'.
_SUFFIXES = string.ascii_lowercase

#: Splitting into more parts than this is almost certainly a typo for a
#: teaching set.
MAX_SPLIT = 8


@dataclass
class SplitPlan:
    """What :func:`split_group` would create, before it creates it."""
    source_group_id: int
    source_group_name: str
    course_id: int
    names: list[str] = field(default_factory=list)
    #: Proposed roster per new group name, in the order students were dealt.
    rosters: dict[str, list[str]] = field(default_factory=dict)
    keep_source: bool = False

    @property
    def total_students(self) -> int:
        return sum(len(r) for r in self.rosters.values())

    def __str__(self) -> str:
        sizes = ", ".join(f"{n} ({len(self.rosters.get(n, []))})"
                          for n in self.names)
        return f"split {self.source_group_name} -> {sizes}"


def _split_names(base: str, into: int,
                 names: Sequence[str] | None) -> list[str]:
    if names is not None:
        out = [str(n or "").strip() for n in names]
        if len(out) != into:
            raise ValidationError(
                f"Expected {into} name(s) for the split, got {len(out)}")
        if any(not n for n in out):
            raise ValidationError("Split group names cannot be blank")
        if len(set(out)) != len(out):
            raise ValidationError("Split group names must be distinct")
        return out
    if into > len(_SUFFIXES):
        raise ValidationError(
            f"Cannot auto-name {into} groups; pass names= explicitly")
    return [f"{base}{_SUFFIXES[i]}" for i in range(into)]


# ── 22. Split one group into several ────────────────────────────────

def split_group(group_id: int,
                into: int = 2,
                *,
                names: Sequence[str] | None = None,
                dry_run: bool = True,
                keep_source: bool = False,
                actor: str | None = None,
                reason: str | None = None) -> tuple[SplitPlan,
                                                    list[ClassGroup]]:
    """Divide a group's roster across ``into`` new groups.

    Students are dealt round-robin in join order, so the new sets come
    out within one of each other in size. Teacher, room, schedule and
    notes are copied from the source; ``max_students`` is *not* — a cap
    sized for one group is wrong for each half, so the new groups
    inherit the course default and the caller can set caps afterwards
    with :func:`class_group_capacity.set_capacity`.

    By default the source group is emptied and deleted once its students
    are re-seated, since a split usually replaces it. ``keep_source=True``
    keeps it as one of the parts instead — then only ``into - 1`` new
    groups are created and the source keeps its share.

    Returns ``(plan, created_groups)``. With ``dry_run=True`` (the
    default) the created list is empty and nothing is written.
    """
    try:
        n = int(into)
    except (TypeError, ValueError):
        raise ValidationError("'into' must be a whole number") from None
    if n < 2:
        raise ValidationError("A split must produce at least 2 groups")
    if n > MAX_SPLIT:
        raise ValidationError(
            f"Refusing to split into {n} groups (the limit is {MAX_SPLIT})")

    source = membership._require_group(group_id)
    roster = core.list_members(source.group_id)
    if not roster:
        raise ValidationError(
            f"'{source.group_name}' has no students to split")
    if len(roster) < n:
        raise ValidationError(
            f"'{source.group_name}' has {len(roster)} student(s); "
            f"cannot split into {n} groups")

    part_names = _split_names(source.group_name, n, names)
    if keep_source:
        # The source keeps its own name and takes the first share.
        part_names[0] = source.group_name

    # Collision check up front — UNIQUE(course_id, group_name) would
    # otherwise fail partway through creating the new groups.
    existing = {g.group_name for g in core.list_groups(
        course_id=source.course_id)}
    if keep_source:
        existing.discard(source.group_name)
    clashes = [nm for nm in part_names if nm in existing]
    if clashes:
        raise ValidationError(
            f"Course #{source.course_id} already has group(s) named "
            + ", ".join(repr(c) for c in clashes))

    plan = SplitPlan(
        source_group_id=source.group_id,
        source_group_name=source.group_name,
        course_id=source.course_id,
        names=part_names,
        keep_source=keep_source,
    )
    for i, sid in enumerate(roster):
        plan.rosters.setdefault(part_names[i % n], []).append(sid)
    for nm in part_names:
        plan.rosters.setdefault(nm, [])

    cg_log.group_event(
        logger, "split_group plan for #%d (%s): %s%s",
        source.group_id, source.group_name, plan,
        "" if dry_run else " (applying)",
        group_id=source.group_id, actor=actor,
    )
    if dry_run:
        return plan, []

    note = reason or f"split of '{source.group_name}'"
    created: list[ClassGroup] = []
    to_create = part_names[1:] if keep_source else part_names

    # Group creation goes through core.create_group so course validation
    # and the UNIQUE constraint are enforced exactly once, in one place.
    for nm in to_create:
        created.append(core.create_group({
            "course_id": source.course_id,
            "group_name": nm,
            "teacher": source.teacher,
            "room": source.room,
            "schedule": source.schedule,
            "notes": source.notes,
            "max_students": None,   # inherit the course default
        }))

    by_name = {g.group_name: g for g in created}
    if keep_source:
        by_name[source.group_name] = source

    with cg_log.operation(logger, "split_group",
                          group_id=source.group_id, actor=actor) as op:
        with membership._txn() as conn:
            for nm, students in plan.rosters.items():
                target = by_name[nm]
                if target.group_id == source.group_id:
                    continue  # already there
                conn.executemany(
                    "DELETE FROM class_group_students "
                    "WHERE group_id = ? AND student_id = ?",
                    [(source.group_id, sid) for sid in students],
                )
                conn.executemany(
                    "INSERT INTO class_group_students "
                    "(group_id, student_id) VALUES (?, ?)",
                    [(target.group_id, sid) for sid in students],
                )
                history.record_many(
                    source.group_id, students, "transfer_out", actor=actor,
                    reason=note, related_group_id=target.group_id, conn=conn)
                history.record_many(
                    target.group_id, students, "transfer_in", actor=actor,
                    reason=note, related_group_id=source.group_id, conn=conn)
        op["parts"] = len(part_names)

    if not keep_source:
        # Empty by construction now; delete_group also clears any
        # membership rows a concurrent write may have added.
        # A source group with attendance/registers/assignments is archived
        # rather than deleted, so that history survives the split.
        outcome = core.delete_or_archive_group(source.group_id) or "deleted"
        cg_log.group_event(
            logger, "%s source class group #%d (%s) after splitting it",
            outcome.capitalize(), source.group_id, source.group_name,
            group_id=source.group_id, actor=actor,
        )

    cg_log.group_event(
        logger, "Split class group '%s' into %s (%d student(s))",
        source.group_name, ", ".join(part_names), len(roster),
        group_id=source.group_id, actor=actor,
    )
    return plan, created


# ── 23. Merge several groups into one ───────────────────────────────

def merge_groups(group_ids: Sequence[int],
                 into_group_id: int,
                 *,
                 dry_run: bool = True,
                 delete_empty: bool = False,
                 force: bool = False,
                 actor: str | None = None,
                 reason: str | None = None) -> dict[str, Any]:
    """Move every source group's roster into one destination group.

    All groups must belong to the same course — merging across courses
    would put students in a set for a subject they do not take, and
    there is no sensible automatic answer, so it raises.

    Refuses when the destination cannot hold everyone, rather than
    filling it and stranding the rest across half-emptied sources. Pass
    ``force=True`` to merge into an over-capacity group deliberately
    (a cap can be raised afterwards with
    :func:`class_group_capacity.set_capacity`).

    Sources are emptied but kept unless ``delete_empty=True``.

    Returns a summary dict: the destination, per-source counts, and the
    resulting roll.
    """
    dest = membership._require_group(into_group_id,
                                     "destination class group")
    sources = []
    seen: set[int] = set()
    for gid in group_ids or ():
        g = membership._require_group(gid, "source class group")
        if g.group_id == dest.group_id or g.group_id in seen:
            continue
        seen.add(g.group_id)
        sources.append(g)
    if not sources:
        raise ValidationError(
            "No source class groups to merge (after removing the "
            "destination and duplicates)")

    wrong_course = [g for g in sources if g.course_id != dest.course_id]
    if wrong_course:
        raise ValidationError(
            "All groups in a merge must belong to the same course; "
            + ", ".join(f"'{g.group_name}' is on course #{g.course_id}"
                        for g in wrong_course)
            + f" but '{dest.group_name}' is on course #{dest.course_id}")

    dest_cap = capacity.capacity_of(dest.group_id)
    dest_members = set(core.list_members(dest.group_id))
    incoming: dict[int, list[str]] = {}
    arriving: set[str] = set()
    for g in sources:
        roster = core.list_members(g.group_id)
        incoming[g.group_id] = roster
        arriving.update(s for s in roster if s not in dest_members)

    final_roll = len(dest_members) + len(arriving)
    over = (dest_cap.cap is not None and final_roll > dest_cap.cap)
    if over and not force:
        cg_log.rejected(
            logger,
            "merge refused: '%s' would hold %d student(s), cap is %d",
            dest.group_name, final_roll, dest_cap.cap,
            group_id=dest.group_id, actor=actor,
        )
        raise ValidationError(
            f"Merging would put {final_roll} student(s) in "
            f"'{dest.group_name}', which is capped at {dest_cap.cap}. "
            f"Raise the cap first, or pass force=True.")

    summary: dict[str, Any] = {
        "destination_group_id": dest.group_id,
        "destination_group_name": dest.group_name,
        "course_id": dest.course_id,
        "sources": {g.group_id: {"name": g.group_name,
                                 "students": len(incoming[g.group_id])}
                    for g in sources},
        "already_in_destination": sorted(
            s for roster in incoming.values() for s in roster
            if s in dest_members),
        "arriving": sorted(arriving),
        "roll_before": len(dest_members),
        "roll_after": final_roll,
        "capacity": dest_cap.cap,
        "over_capacity": over,
        "deleted_sources": [],
        "applied": False,
    }

    if dry_run:
        cg_log.group_event(
            logger, "merge_groups plan: %d source(s) -> #%d (%s), roll %d -> %d",
            len(sources), dest.group_id, dest.group_name,
            len(dest_members), final_roll,
            group_id=dest.group_id, actor=actor,
        )
        return summary

    note = reason or (f"merge into '{dest.group_name}'")
    with cg_log.operation(logger, "merge_groups",
                          group_id=dest.group_id, actor=actor) as op:
        with membership._txn() as conn:
            for g in sources:
                roster = incoming[g.group_id]
                if not roster:
                    continue
                new_here = [s for s in roster if s not in dest_members]
                conn.execute(
                    "DELETE FROM class_group_students WHERE group_id = ?",
                    (g.group_id,),
                )
                if new_here:
                    conn.executemany(
                        "INSERT INTO class_group_students "
                        "(group_id, student_id) VALUES (?, ?)",
                        [(dest.group_id, s) for s in new_here],
                    )
                    dest_members.update(new_here)
                history.record_many(
                    g.group_id, roster, "transfer_out", actor=actor,
                    reason=note, related_group_id=dest.group_id, conn=conn)
                history.record_many(
                    dest.group_id, new_here, "transfer_in", actor=actor,
                    reason=note, related_group_id=g.group_id, conn=conn)
        op["sources"] = len(sources)

    if delete_empty:
        for g in sources:
            # Groups with recorded history are archived, not deleted.
            outcome = core.delete_or_archive_group(g.group_id)
            if outcome:
                summary["deleted_sources"].append(g.group_id)
                cg_log.group_event(
                    logger, "%s merged-away class group #%d (%s)",
                    outcome.capitalize(), g.group_id, g.group_name,
                    group_id=g.group_id, actor=actor)

    summary["applied"] = True
    cg_log.group_event(
        logger,
        "Merged %d class group(s) into #%d (%s); roll is now %d%s",
        len(sources), dest.group_id, dest.group_name, final_roll,
        " (OVER CAPACITY)" if over else "",
        group_id=dest.group_id, actor=actor, level=30 if over else 20,
    )
    return summary
