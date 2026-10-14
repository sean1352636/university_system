"""Deciding which class group a student goes in.

Placement is the part of class-group admin that is done in a
spreadsheet and then typed back in. The functions here produce the same
decisions as a plan object, so the decision can be reviewed before it
becomes thirty writes.

**Everything is dry-run by default.** :func:`auto_allocate`,
:func:`balance_groups` and :func:`rebalance_by_attainment` all return an
:class:`AllocationPlan` and touch nothing until called with
``dry_run=False``, or until the returned plan is passed to
:func:`apply_plan`. A placement algorithm that writes on the first call
is one that cannot be shown to a head of department first.

**Two kinds of plan, two ways to apply them.** A plan that only *adds*
students (:func:`auto_allocate`) is applied group by group through
``add_members_bulk``. A plan that *reshuffles* an existing intake
(:func:`balance_groups`, :func:`rebalance_by_attainment`) cannot be:
applying it one move at a time hits caps that only exist because the
move that would free the place has not happened yet, so the run fails
halfway through in an order-dependent way. Those are applied as a single
atomic re-seat — every affected membership row is rewritten inside one
transaction — which is why :func:`apply_plan` checks ``plan.is_reshuffle``
rather than treating all plans alike.

Nothing here invents attainment data. :func:`rebalance_by_attainment`
takes an explicit ``scores`` mapping, and only falls back to primary
baseline records when the caller does not supply one.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from education_system import paths
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_group_capacity as capacity,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_group_history as history,
)
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_group_intake as intake,
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
Skip = membership.Skip
GroupCapacity = capacity.GroupCapacity


@dataclass
class Placement:
    """One student landing in one group.

    ``from_group_id`` is None for a student who was not in any group on
    this course — the difference between an intake and a move, and what
    decides which history action gets written.
    """
    student_id: str
    group_id: int
    group_name: str
    from_group_id: int | None = None
    #: Whatever the strategy ranked on, kept for the preview table.
    score: float | None = None

    @property
    def is_move(self) -> bool:
        return self.from_group_id is not None and \
            self.from_group_id != self.group_id

    @property
    def is_noop(self) -> bool:
        return self.from_group_id == self.group_id


@dataclass
class AllocationPlan:
    """What an allocation strategy proposes, and whether it happened."""
    course_id: int
    strategy: str
    placements: list[Placement] = field(default_factory=list)
    unplaced: list[Skip] = field(default_factory=list)
    applied: bool = False

    @property
    def moves(self) -> list[Placement]:
        """Placements that actually change something."""
        return [p for p in self.placements if not p.is_noop]

    @property
    def is_reshuffle(self) -> bool:
        """Whether any placement takes a student out of an existing group.

        Decides how :func:`apply_plan` writes the plan — see the module
        docstring.
        """
        return any(p.is_move for p in self.placements)

    def by_group(self) -> dict[int, list[str]]:
        """The shape feature 20 was specified to return."""
        out: dict[int, list[str]] = {}
        for p in self.placements:
            out.setdefault(p.group_id, []).append(p.student_id)
        return out

    def summary(self) -> str:
        parts = [f"{self.strategy}: {len(self.moves)} change(s)"]
        if self.unplaced:
            parts.append(f"{len(self.unplaced)} unplaced")
        if not self.applied:
            parts.append("(not applied)")
        return ", ".join(parts)

    def __str__(self) -> str:
        return self.summary()


# ── Shared helpers ──────────────────────────────────────────────────

def _course_groups(course_id: int) -> list[GroupCapacity]:
    rows = capacity.capacity_report(course_id=course_id)
    if not rows:
        cg_log.rejected(
            logger, "No class groups exist for course #%s", course_id)
        raise ValidationError(
            f"Course #{course_id} has no class groups to allocate into")
    return rows


def _placements_of_course(course_id: int) -> dict[str, int]:
    """student_id -> group_id, for every student in a group on this course.

    One query. A student in two groups on the same course is a data
    fault (:func:`duplicate_placements` reports them); the lowest
    group_id wins here so the plan stays deterministic.
    """
    core.init_db()
    with membership._txn() as conn:
        rows = conn.execute(
            """SELECT cgs.student_id, cgs.group_id
                 FROM class_group_students cgs
                 JOIN class_groups cg ON cg.group_id = cgs.group_id
                WHERE cg.course_id = ?
                ORDER BY cgs.group_id""",
            (int(course_id),),
        ).fetchall()
    out: dict[str, int] = {}
    for r in rows:
        out.setdefault(r["student_id"], r["group_id"])
    return out


def duplicate_placements(course_id: int) -> dict[str, list[int]]:
    """Students holding more than one group on the same course.

    Delegates to :func:`class_group_validation.duplicate_memberships`,
    which is the canonical implementation — every allocation strategy
    has to pick one of a student's placements arbitrarily, so this is
    worth checking before trusting a plan.
    """
    from education_system.systems.sixth_form.domain.academics.class_groups \
        import class_group_validation as _validation
    return _validation.duplicate_memberships(int(course_id))


# ── 25. Who has no group yet ────────────────────────────────────────

def unassigned_students(course_id: int,
                        *,
                        subject_filter: str | None = None) -> list[str]:
    """Cohort members with no class group on this course.

    Thin wrapper over :func:`class_group_intake.candidates_for_course`,
    which already excludes anyone placed — see that module's docstring
    for why "on this course" means the year-group cohort rather than a
    course roster, and why ``subject_filter`` is worth passing.
    """
    return intake.unplaced_for_course(
        course_id, subject_filter=subject_filter)


# ── 19. Where should this student go? ───────────────────────────────

def suggest_group_for_student(course_id: int,
                              student_id: str,
                              *,
                              prefer: str = "emptiest") -> ClassGroup | None:
    """The best group on this course for one student, or None if none fit.

    ``prefer='emptiest'`` (the default) levels group sizes; ``'fullest'``
    packs groups so spare sets can be collapsed. Groups the student is
    already in are excluded, so this never suggests a no-op.

    Returns None rather than raising when every group is full — "there is
    nowhere to put them" is an answer the caller has to handle either
    way, and an exception would make the common case the error path.
    """
    sid = core._require(student_id, "Student ID")
    if prefer not in ("emptiest", "fullest"):
        raise ValidationError(
            f"Unknown preference {prefer!r}; expected 'emptiest' or 'fullest'")
    groups = _course_groups(course_id)
    held = {gid for s, gid in _placements_of_course(course_id).items()
            if s == sid}

    open_groups = [gc for gc in groups
                   if gc.group_id not in held and not gc.is_full]
    if not open_groups:
        cg_log.rejected(
            logger, "No class group on course #%s can take %s "
                    "(%d group(s), all full or already joined)",
            course_id, sid, len(groups), student_id=sid,
        )
        return None

    # Uncapped groups sort as if empty for 'emptiest' and as if infinite
    # for 'fullest', so a cap-less group is the natural overflow.
    def key(gc: GroupCapacity) -> tuple:
        ratio = gc.fill_ratio
        if prefer == "emptiest":
            return (ratio if ratio is not None else -1.0,
                    gc.members, gc.group.group_name)
        return (-(ratio if ratio is not None else 2.0),
                -gc.members, gc.group.group_name)

    best = min(open_groups, key=key)
    cg_log.student_event(
        logger, "Suggested class group #%d (%s) for %s (%s, %s)",
        best.group_id, best.group.group_name, sid, prefer, best,
        student_id=sid, group_id=best.group_id, level=10,
    )
    return best.group


# ── 20. Fill the groups ─────────────────────────────────────────────

def auto_allocate(course_id: int,
                  student_ids: Iterable[str] | None = None,
                  *,
                  dry_run: bool = True,
                  actor: str | None = None,
                  subject_filter: str | None = None) -> AllocationPlan:
    """Spread unplaced students across a course's groups, evenly.

    With ``student_ids`` omitted, allocates everyone
    :func:`unassigned_students` returns. Each student goes to the
    emptiest group with room, recomputed after every placement, so the
    result is level rather than merely round-robin over an uneven start.

    Returns a plan; writes nothing unless ``dry_run=False``.
    """
    groups = _course_groups(course_id)
    if student_ids is None:
        ids = unassigned_students(course_id, subject_filter=subject_filter)
    else:
        ids = membership._clean_ids(student_ids)

    plan = AllocationPlan(course_id=int(course_id), strategy="auto_allocate")
    if not ids:
        return plan

    placed = _placements_of_course(course_id)
    # Working headcounts, so we can level without re-querying per student.
    load = {gc.group_id: gc.members for gc in groups}
    caps = {gc.group_id: gc.cap for gc in groups}
    names = {gc.group_id: gc.group.group_name for gc in groups}

    def room(gid: int) -> bool:
        cap = caps[gid]
        return cap is None or load[gid] < cap

    for sid in ids:
        if sid in placed:
            plan.unplaced.append(
                Skip(sid, f"already in group #{placed[sid]} on this course"))
            continue
        options = [gid for gid in load if room(gid)]
        if not options:
            plan.unplaced.append(Skip(sid, "every group is full"))
            continue
        # Emptiest by share of cap, then by headcount, then by name so
        # two identical groups always resolve the same way.
        target = min(options, key=lambda g: (
            (load[g] / caps[g]) if caps[g] else -1.0, load[g], names[g]))
        load[target] += 1
        plan.placements.append(
            Placement(student_id=sid, group_id=target,
                      group_name=names[target], from_group_id=None))

    cg_log.group_event(
        logger, "auto_allocate for course #%s: %d placement(s), %d unplaced%s",
        course_id, len(plan.placements), len(plan.unplaced),
        "" if dry_run else " (applying)", actor=actor,
    )
    if not dry_run:
        apply_plan(plan, actor=actor)
    return plan


# ── 21. Level the groups ────────────────────────────────────────────

def balance_groups(course_id: int,
                   *,
                   dry_run: bool = True,
                   tolerance: int = 1,
                   actor: str | None = None) -> AllocationPlan:
    """Even out group sizes on a course by moving students between them.

    Moves from the largest group to the smallest, repeatedly, until the
    spread is within ``tolerance``. Students are taken from the end of
    the largest group's join order, so the longest-standing members of a
    set stay put.

    A cap is respected on the receiving side, so a course whose groups
    are all at cap cannot be balanced and returns an empty plan rather
    than an impossible one.
    """
    if tolerance < 0:
        raise ValidationError("Tolerance cannot be negative")
    groups = _course_groups(course_id)
    plan = AllocationPlan(course_id=int(course_id), strategy="balance_groups")
    if len(groups) < 2:
        return plan

    # Roster per group, in join order — the tail is what moves.
    rosters: dict[int, list[str]] = {}
    with membership._txn() as conn:
        for gc in groups:
            rosters[gc.group_id] = [r["student_id"] for r in conn.execute(
                "SELECT student_id FROM class_group_students "
                "WHERE group_id = ? ORDER BY joined_at, student_id",
                (gc.group_id,)).fetchall()]

    caps = {gc.group_id: gc.cap for gc in groups}
    names = {gc.group_id: gc.group.group_name for gc in groups}
    origin = {sid: gid for gid, roster in rosters.items() for sid in roster}

    # Bounded: each iteration reduces the spread by moving one student
    # from max to min, and stops as soon as it cannot.
    guard = sum(len(r) for r in rosters.values()) + len(groups)
    while guard > 0:
        guard -= 1
        biggest = max(rosters, key=lambda g: (len(rosters[g]), names[g]))
        smallest = min(rosters, key=lambda g: (len(rosters[g]), names[g]))
        if biggest == smallest:
            break
        if len(rosters[biggest]) - len(rosters[smallest]) <= tolerance:
            break
        if not rosters[biggest]:
            break
        cap = caps[smallest]
        if cap is not None and len(rosters[smallest]) >= cap:
            # The smallest group cannot grow, so no further levelling is
            # possible — every other group is at least as large.
            break
        mover = rosters[biggest].pop()
        rosters[smallest].append(mover)

    for gid, roster in rosters.items():
        for sid in roster:
            if origin.get(sid) != gid:
                plan.placements.append(Placement(
                    student_id=sid, group_id=gid, group_name=names[gid],
                    from_group_id=origin.get(sid)))

    cg_log.group_event(
        logger, "balance_groups for course #%s: %d move(s), sizes %s",
        course_id, len(plan.moves),
        {names[g]: len(r) for g, r in rosters.items()}, actor=actor,
    )
    if not dry_run:
        apply_plan(plan, actor=actor)
    return plan


# ── 24. Set by prior attainment ─────────────────────────────────────

def baseline_scores(course_id: int) -> dict[str, float]:
    """Primary baseline scores for a course's subject, as a fallback source.

    Prefers ``standardised_score`` and falls back to ``percentage``.
    Returns only the students who actually have a primary record — a
    missing score is not a zero, and treating it as one would seed every
    unassessed student into the bottom set.
    """
    from education_system.systems.sixth_form.domain.academics.courses import (
        courses as _courses,
    )
    from education_system.systems.sixth_form.domain.assessment \
        .baseline_assessment import baseline_assessment as _baseline

    course = _courses.get_course(int(course_id))
    if course is None:
        raise ValidationError(f"No course with id {course_id}")
    _baseline.init_db()

    with membership._txn() as conn:
        rows = conn.execute(
            """SELECT student_id, standardised_score, percentage
                 FROM baseline_records
                WHERE is_primary = 1
                  AND (subject_name = ? OR subject_name IS NULL)""",
            (course.subject,),
        ).fetchall()
    out: dict[str, float] = {}
    for r in rows:
        value = r["standardised_score"]
        if value is None:
            value = r["percentage"]
        if value is not None:
            out[r["student_id"]] = float(value)
    return out


def rebalance_by_attainment(course_id: int,
                            scores: dict[str, float] | None = None,
                            *,
                            dry_run: bool = True,
                            descending: bool = True,
                            snake: bool = False,
                            actor: str | None = None) -> AllocationPlan:
    """Re-seat a course's students across its groups by prior attainment.

    Two distributions:

    * **Setting** (default) — rank order is cut into bands, so group one
      is the top band. This is what "setting by ability" means and what
      a department usually wants.
    * **Snake** (``snake=True``) — serpentine dealing, which makes every
      group an equally mixed-ability set. The opposite intent; it is here
      because the same ranking answers both questions.

    Students with no score keep their current group and are reported in
    ``unplaced``. They are *not* ranked as zero — see
    :func:`baseline_scores`.

    Group order for banding is by ``group_name``, so the naming scheme
    decides which band is which. Always review the returned plan before
    applying it.
    """
    groups = _course_groups(course_id)
    groups = sorted(groups, key=lambda gc: gc.group.group_name)
    plan = AllocationPlan(course_id=int(course_id),
                          strategy="rebalance_by_attainment"
                                   + (" (snake)" if snake else " (setting)"))

    placed = _placements_of_course(course_id)
    if not placed:
        return plan
    if scores is None:
        scores = baseline_scores(course_id)

    ranked = [s for s in placed if s in scores]
    for sid in sorted(placed):
        if sid not in scores:
            plan.unplaced.append(Skip(sid, "no attainment score; left in place"))
    if not ranked:
        cg_log.rejected(
            logger,
            "rebalance_by_attainment for course #%s: no scores for any of "
            "the %d placed student(s); nothing to do",
            course_id, len(placed), actor=actor)
        return plan

    ranked.sort(key=lambda s: (-scores[s] if descending else scores[s], s))

    caps = [gc.cap for gc in groups]
    names = [gc.group.group_name for gc in groups]
    ids = [gc.group_id for gc in groups]
    n_groups = len(groups)
    buckets: list[list[str]] = [[] for _ in range(n_groups)]

    def can_take(i: int) -> bool:
        return caps[i] is None or len(buckets[i]) < caps[i]

    if snake:
        order: list[int] = []
        forward = True
        while len(order) < len(ranked):
            lane = range(n_groups) if forward else range(n_groups - 1, -1, -1)
            order.extend(lane)
            forward = not forward
        cursor = 0
        for sid in ranked:
            # Skip past full groups rather than overfilling one.
            for _ in range(len(order)):
                i = order[cursor % len(order)]
                cursor += 1
                if can_take(i):
                    buckets[i].append(sid)
                    break
            else:
                plan.unplaced.append(Skip(sid, "every group is full"))
    else:
        i = 0
        # Band sizes: even split, with the remainder going to the earlier
        # (higher-attaining) bands, bounded by each group's cap.
        target = [len(ranked) // n_groups] * n_groups
        for k in range(len(ranked) % n_groups):
            target[k] += 1
        leftover: list[str] = []
        for sid in ranked:
            while i < n_groups and (len(buckets[i]) >= target[i]
                                    or not can_take(i)):
                i += 1
            if i >= n_groups:
                leftover.append(sid)
                continue
            buckets[i].append(sid)
        # The band cursor only moves forward, so a group capped below its
        # band size pushes students past groups that still have room.
        # Spill them back into the nearest band that can take them —
        # otherwise a course with exactly as many places as students
        # reports some of them unplaced.
        for sid in leftover:
            for j in range(n_groups):
                if can_take(j):
                    buckets[j].append(sid)
                    break
            else:
                plan.unplaced.append(Skip(sid, "every group is full"))

    for idx, bucket in enumerate(buckets):
        for sid in bucket:
            plan.placements.append(Placement(
                student_id=sid, group_id=ids[idx], group_name=names[idx],
                from_group_id=placed.get(sid), score=scores.get(sid)))

    cg_log.group_event(
        logger,
        "rebalance_by_attainment for course #%s: %d move(s) across %d group(s), "
        "%d student(s) without a score",
        course_id, len(plan.moves), n_groups, len(plan.unplaced), actor=actor,
    )
    if not dry_run:
        apply_plan(plan, actor=actor)
    return plan


# ── Applying a plan ─────────────────────────────────────────────────

def apply_plan(plan: AllocationPlan,
               *,
               actor: str | None = None,
               reason: str | None = None) -> AllocationPlan:
    """Write a plan to the roster. Returns the same plan, marked applied.

    An additions-only plan goes through ``add_members_bulk`` per group.
    A reshuffle is applied as one atomic re-seat instead — see the
    module docstring for why moving students one at a time cannot work.
    """
    if plan.applied:
        raise ValidationError(
            f"This {plan.strategy} plan has already been applied")
    moves = plan.moves
    if not moves:
        plan.applied = True
        return plan

    note = reason or f"{plan.strategy} on course #{plan.course_id}"

    if not plan.is_reshuffle:
        for gid, sids in _group_ids_to_students(moves).items():
            result = membership.add_members_bulk(
                gid, sids, actor=actor, reason=note)
            plan.unplaced.extend(result.skipped)
        plan.applied = True
        return plan

    with cg_log.operation(logger, f"apply_plan:{plan.strategy}",
                          actor=actor) as op:
        with membership._txn() as conn:
            # Re-check membership inside the transaction: the plan was
            # computed from an earlier read, and a concurrent edit would
            # otherwise be silently overwritten.
            affected = sorted({p.student_id for p in moves})
            marks = ",".join("?" * len(affected))
            current = {
                r["student_id"]: r["group_id"] for r in conn.execute(
                    f"""SELECT cgs.student_id, cgs.group_id
                          FROM class_group_students cgs
                          JOIN class_groups cg ON cg.group_id = cgs.group_id
                         WHERE cg.course_id = ?
                           AND cgs.student_id IN ({marks})""",
                    [plan.course_id, *affected]).fetchall()
            }
            stale = [p for p in moves
                     if current.get(p.student_id) != p.from_group_id]
            if stale:
                raise ValidationError(
                    f"The roster changed since this plan was built "
                    f"({len(stale)} student(s) are no longer where the plan "
                    f"expects, e.g. {stale[0].student_id}). Rebuild the plan "
                    f"and review it again.")

            conn.executemany(
                "DELETE FROM class_group_students "
                "WHERE group_id = ? AND student_id = ?",
                [(p.from_group_id, p.student_id) for p in moves],
            )
            conn.executemany(
                "INSERT INTO class_group_students (group_id, student_id) "
                "VALUES (?, ?)",
                [(p.group_id, p.student_id) for p in moves],
            )
            for p in moves:
                history.record(p.from_group_id, p.student_id, "transfer_out",
                               actor=actor, reason=note,
                               related_group_id=p.group_id, conn=conn)
                history.record(p.group_id, p.student_id, "transfer_in",
                               actor=actor, reason=note,
                               related_group_id=p.from_group_id, conn=conn)
        op["moved"] = len(moves)

    for p in moves:
        cg_log.student_event(
            logger, "%s: moved %s from class group #%s to #%d (%s)",
            plan.strategy, p.student_id, p.from_group_id, p.group_id,
            p.group_name, student_id=p.student_id, group_id=p.group_id,
            actor=actor,
        )
    plan.applied = True
    return plan


def _group_ids_to_students(
        placements: Sequence[Placement]) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for p in placements:
        out.setdefault(p.group_id, []).append(p.student_id)
    return out
