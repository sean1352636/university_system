"""Capacity questions for Sixth Form class groups.

``class_groups.effective_cap`` answers "how many can this group hold?"
for one group, and does it by fetching the parent course. That is fine
on a profile screen and quadratic on a directory: a hundred groups is a
hundred course lookups plus a hundred member counts, all against a DB
where a fresh connection is the expensive part.

Everything here goes through :func:`capacity_report`, which resolves the
cap, its source, and the headcount for every group in **one** query.
The single-group helpers (:func:`remaining_capacity`, :func:`is_full`,
:func:`is_over_capacity`) are thin wrappers for callers that genuinely
only want one; anything iterating over groups should call
``capacity_report`` directly rather than looping over them.

**Over-capacity is possible and is not corruption.** ``add_member``
refuses to breach a cap, but a cap can be lowered afterwards, and a
course's default can move under a group that inherits it. So a group
can legitimately hold more students than its cap allows, and
:func:`is_over_capacity` exists to surface those rather than pretend
they cannot happen. :func:`set_capacity` refuses to create the situation
deliberately unless the caller passes ``force=True``.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system import paths
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

#: A group at or below this share of its cap counts as undersubscribed.
#: 0.5 — half empty — is the point at which a set is usually worth
#: merging rather than timetabling on its own.
DEFAULT_UNDERSUBSCRIBED_THRESHOLD = 0.5


@dataclass
class GroupCapacity:
    """A group's roll and its cap, with where the cap came from.

    ``cap_source`` matters when somebody asks why a group is full: a
    ``'course'`` cap is shared with every sibling set and changing it
    moves all of them, a ``'group'`` cap is this group's own override.
    """
    group: ClassGroup
    members: int
    cap: int | None
    cap_source: str | None  # 'group' | 'course' | None (uncapped)

    @property
    def group_id(self) -> int:
        return self.group.group_id

    @property
    def remaining(self) -> int | None:
        """Free places, or None when uncapped. Never negative."""
        if self.cap is None:
            return None
        return max(0, self.cap - self.members)

    @property
    def overflow(self) -> int:
        """How many members are *beyond* the cap (0 when within it)."""
        if self.cap is None:
            return 0
        return max(0, self.members - self.cap)

    @property
    def is_full(self) -> bool:
        return self.cap is not None and self.members >= self.cap

    @property
    def is_over(self) -> bool:
        return self.overflow > 0

    @property
    def fill_ratio(self) -> float | None:
        """Members as a share of cap, or None when uncapped.

        Can exceed 1.0 for an over-filled group — that is the signal, so
        it is deliberately not clamped.
        """
        if self.cap is None or self.cap <= 0:
            return None
        return self.members / self.cap

    def __str__(self) -> str:
        if self.cap is None:
            return f"{self.group.group_name}: {self.members} (uncapped)"
        return (f"{self.group.group_name}: {self.members}/{self.cap}"
                + (f" (+{self.overflow} over)" if self.is_over else ""))


# One pass: cap resolution (group override, else course default) and
# headcount for every group, without a per-group round trip.
_REPORT_SQL = """
    SELECT cg.*,
           COALESCE(cg.max_students, c.max_students) AS eff_cap,
           CASE WHEN cg.max_students IS NOT NULL THEN 'group'
                WHEN c.max_students IS NOT NULL THEN 'course'
                ELSE NULL END AS cap_source,
           (SELECT COUNT(*) FROM class_group_students cgs
             WHERE cgs.group_id = cg.group_id) AS member_count
      FROM class_groups cg
      LEFT JOIN courses c ON c.course_id = cg.course_id
"""


def _capacity_row(r: sqlite3.Row) -> GroupCapacity:
    return GroupCapacity(
        group=core._row(r),
        members=int(r["member_count"]),
        cap=None if r["eff_cap"] is None else int(r["eff_cap"]),
        cap_source=r["cap_source"],
    )


def capacity_report(*,
                    course_id: int | None = None,
                    group_ids: list[int] | None = None,
                    teacher: str | None = None) -> list[GroupCapacity]:
    """Roll and cap for every matching group, in one query.

    This is the batched primitive the rest of the module is built on.
    Prefer it over looping the single-group helpers.
    """
    core.init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if course_id is not None:
        clauses.append("cg.course_id = ?")
        args.append(int(course_id))
    if group_ids is not None:
        if not group_ids:
            return []
        marks = ",".join("?" * len(group_ids))
        clauses.append(f"cg.group_id IN ({marks})")
        args.extend(int(g) for g in group_ids)
    if teacher:
        clauses.append("cg.teacher LIKE ?")
        args.append(f"%{teacher.strip()}%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"{_REPORT_SQL} {where} ORDER BY cg.course_id, cg.group_name"
    with membership._txn() as conn:
        return [_capacity_row(r) for r in conn.execute(sql, args).fetchall()]


def capacity_of(group_id: int) -> GroupCapacity:
    """The capacity picture for one group.

    Raises :class:`ValidationError` for an unknown group, so callers get
    the same failure they would from ``core.get_group`` rather than a
    silently empty result.
    """
    rows = capacity_report(group_ids=[int(group_id)])
    if not rows:
        cg_log.rejected(logger, "capacity_of: unknown class group #%s",
                        group_id, group_id=group_id)
        raise ValidationError(f"No class group with id {group_id}")
    return rows[0]


# ── 11. Remaining capacity ──────────────────────────────────────────

def remaining_capacity(group_id: int) -> int | None:
    """Free places in this group, or None when it is uncapped.

    None and 0 mean opposite things — "room for anyone" and "room for
    nobody" — so callers must not treat a falsy return as full. Use
    :func:`is_full` for that question.
    """
    return capacity_of(group_id).remaining


# ── 12. Full? ───────────────────────────────────────────────────────

def is_full(group_id: int) -> bool:
    """Whether this group has no free places. Uncapped groups are never full."""
    return capacity_of(group_id).is_full


# ── 13. Over capacity? ──────────────────────────────────────────────

def is_over_capacity(group_id: int) -> bool:
    """Whether this group holds *more* than its cap allows.

    Distinct from :func:`is_full`: full is the normal end state, over is
    a data-quality problem that arose from a cap being lowered under an
    existing roll.
    """
    return capacity_of(group_id).is_over


# ── 14. Full groups ─────────────────────────────────────────────────

def list_full_groups(course_id: int | None = None,
                     *,
                     include_over: bool = True) -> list[GroupCapacity]:
    """Every group with no free places, fullest first.

    Set ``include_over=False`` to get exactly-at-cap groups only, which
    is what a "these are healthy" view wants; the default includes
    over-filled groups because a "cannot take more" view wants both.
    """
    rows = [gc for gc in capacity_report(course_id=course_id) if gc.is_full]
    if not include_over:
        rows = [gc for gc in rows if not gc.is_over]
    rows.sort(key=lambda gc: (-(gc.fill_ratio or 0), gc.group.group_name))
    return rows


def list_over_capacity(course_id: int | None = None) -> list[GroupCapacity]:
    """Groups holding more students than their cap allows, worst first.

    The companion to :func:`is_over_capacity` for a whole course —
    the list a head of department should be shown after lowering a
    course default.
    """
    rows = [gc for gc in capacity_report(course_id=course_id) if gc.is_over]
    rows.sort(key=lambda gc: (-gc.overflow, gc.group.group_name))
    if rows:
        cg_log.group_event(
            logger, "%d class group(s) are over capacity: %s",
            len(rows), ", ".join(str(gc) for gc in rows[:10]),
            level=30,  # WARNING — this is a data-quality finding
        )
    return rows


# ── 15. Undersubscribed groups ──────────────────────────────────────

def list_undersubscribed(
        threshold: float = DEFAULT_UNDERSUBSCRIBED_THRESHOLD,
        *,
        course_id: int | None = None,
        include_empty: bool = True) -> list[GroupCapacity]:
    """Groups filled to ``threshold`` or less of their cap, emptiest first.

    Uncapped groups are excluded — with no cap there is no share to
    compare against, and silently treating them as 0% would put every
    uncapped group at the top of a merge-candidates list.
    """
    if not 0 < threshold <= 1:
        raise ValidationError(
            f"Threshold must be between 0 (exclusive) and 1, got {threshold}")
    rows = [gc for gc in capacity_report(course_id=course_id)
            if gc.fill_ratio is not None and gc.fill_ratio <= threshold]
    if not include_empty:
        rows = [gc for gc in rows if gc.members > 0]
    rows.sort(key=lambda gc: (gc.fill_ratio or 0, gc.group.group_name))
    return rows


# ── 18. Change a cap ────────────────────────────────────────────────

def set_capacity(group_id: int,
                 max_students: int | None,
                 *,
                 actor: str | None = None,
                 force: bool = False) -> ClassGroup:
    """Set or clear this group's own cap.

    ``None`` clears the override, so the group falls back to the
    course's default — which may itself be lower than the current roll,
    hence the same check applies either way.

    Refuses to set a cap below the group's current headcount: that would
    manufacture an over-capacity group and leave whoever set it with no
    indication of which students are now surplus. Pass ``force=True``
    when that is genuinely intended (a cap cut that the roster will be
    trimmed to afterwards); it is logged at WARNING.
    """
    current = capacity_of(group_id)
    group = current.group

    if max_students is None:
        new_cap: int | None = None
    else:
        try:
            new_cap = int(max_students)
        except (TypeError, ValueError):
            raise ValidationError(
                "Max students must be a whole number or None") from None
        if new_cap <= 0 or new_cap > 1000:
            raise ValidationError("Max students must be between 1 and 1000")

    # Resolve what the cap would actually become, since clearing the
    # override hands the decision to the course.
    effective_after = new_cap
    if new_cap is None:
        from education_system.systems.sixth_form.domain.academics.courses \
            import courses as _courses
        course = _courses.get_course(group.course_id)
        effective_after = course.max_students if course else None

    if (effective_after is not None
            and current.members > effective_after and not force):
        cg_log.rejected(
            logger,
            "set_capacity refused: class group #%d (%s) holds %d student(s), "
            "cap would become %d",
            group.group_id, group.group_name, current.members,
            effective_after, group_id=group.group_id, actor=actor,
        )
        raise ValidationError(
            f"'{group.group_name}' holds {current.members} student(s); a cap "
            f"of {effective_after} would put it over capacity. Remove "
            f"{current.members - effective_after} student(s) first, or pass "
            f"force=True to accept an over-full group.")

    with membership._txn() as conn:
        conn.execute(
            "UPDATE class_groups SET max_students = ? WHERE group_id = ?",
            (new_cap, group.group_id),
        )

    level = 30 if (effective_after is not None
                   and current.members > effective_after) else 20
    cg_log.group_event(
        logger,
        "Capacity for class group #%d (%s) set to %s (was %s, %s source); "
        "roll is %d",
        group.group_id, group.group_name,
        new_cap if new_cap is not None else "course default",
        current.cap, current.cap_source, current.members,
        group_id=group.group_id, actor=actor, level=level,
    )
    updated = core.get_group(group.group_id)
    assert updated is not None
    return updated


def course_capacity_summary(course_id: int) -> dict[str, Any]:
    """Totals across every group on a course — the header for a directory.

    One query via :func:`capacity_report`; safe to call on every refresh.
    """
    rows = capacity_report(course_id=course_id)
    capped = [gc for gc in rows if gc.cap is not None]
    total_cap = sum(gc.cap for gc in capped) if capped else None
    total_members = sum(gc.members for gc in rows)
    return {
        "course_id": int(course_id),
        "groups": len(rows),
        "members": total_members,
        "capacity": total_cap,
        "places_left": (None if total_cap is None
                        else max(0, total_cap - total_members)),
        "uncapped_groups": len(rows) - len(capped),
        "full": sum(1 for gc in rows if gc.is_full),
        "over": sum(1 for gc in rows if gc.is_over),
        "undersubscribed": sum(
            1 for gc in rows if gc.fill_ratio is not None
            and gc.fill_ratio <= DEFAULT_UNDERSUBSCRIBED_THRESHOLD),
        "smallest": min(rows, key=lambda gc: gc.members) if rows else None,
        "largest": max(rows, key=lambda gc: gc.members) if rows else None,
    }
