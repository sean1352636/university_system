"""Integrity auditing for Sixth Form class groups.

Class-group data goes wrong quietly. A course is deleted and its groups
cascade away, but a group whose ``course_id`` was written before the FK
existed just dangles. A cap is lowered and a group is silently over
capacity. Somebody adds a student to two sets of the same course. A
schedule is typed into the group card and the timetable never built.
None of these raise; all of them surface as a confused teacher in
September.

:func:`audit_all_groups` is the batched pass that finds them all, and
:func:`validate_group_integrity` is the same pass scoped to one group.
That direction matters: the audit is the primitive, and the single-group
check is derived from it. Writing it the other way round — looping the
single check over every group — is what makes an audit take a minute on
a real dataset, because each of these checks is one query for *all*
groups or one query per group, and there is no version of the second
that is acceptable.

Findings are strings, deliberately. They are read by humans in a report,
and a structured finding type would need a code registry that nothing
else consumes. Each is prefixed with a severity marker so a caller can
filter without parsing: ``ERROR`` for broken data, ``WARN`` for
suspicious data, ``INFO`` for incomplete-but-normal.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any, Sequence

from education_system import paths
from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_group_capacity as capacity,
)
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

ERROR = "ERROR"
WARN = "WARN"
INFO = "INFO"
SEVERITIES: tuple[str, ...] = (ERROR, WARN, INFO)


@dataclass
class AuditResult:
    """Findings for every group examined, plus the totals."""
    findings: dict[int, list[str]] = field(default_factory=dict)
    group_names: dict[int, str] = field(default_factory=dict)
    groups_checked: int = 0

    def counts(self) -> dict[str, int]:
        out = {ERROR: 0, WARN: 0, INFO: 0}
        for items in self.findings.values():
            for f in items:
                for sev in SEVERITIES:
                    if f.startswith(sev):
                        out[sev] += 1
                        break
        return out

    def at_least(self, severity: str) -> dict[int, list[str]]:
        """Findings at ``severity`` or worse, dropping groups left clean."""
        if severity not in SEVERITIES:
            raise ValidationError(
                f"Unknown severity {severity!r}; expected "
                f"{', '.join(SEVERITIES)}")
        keep = SEVERITIES[:SEVERITIES.index(severity) + 1]
        out: dict[int, list[str]] = {}
        for gid, items in self.findings.items():
            hits = [f for f in items if f.startswith(keep)]
            if hits:
                out[gid] = hits
        return out

    @property
    def clean(self) -> bool:
        return not self.findings

    def __str__(self) -> str:
        c = self.counts()
        return (f"{self.groups_checked} group(s) checked: "
                f"{c[ERROR]} error(s), {c[WARN]} warning(s), "
                f"{c[INFO]} note(s) across {len(self.findings)} group(s)")


# ── 26. Students in two sets of the same course ─────────────────────

def duplicate_memberships(course_id: int | None = None
                          ) -> dict[str, list[int]]:
    """Students holding more than one class group on the same course.

    Nothing in this package creates these — ``add_members_bulk`` and the
    allocation planner both refuse — but ``core.add_member`` does not
    forbid it, so an import or a hand edit can. They matter because
    every allocation strategy has to pick one of the placements
    arbitrarily, and because the student is timetabled twice.

    With ``course_id`` omitted, checks every course. One query either
    way. Returns ``{student_id: [group_id, ...]}``, group ids sorted.
    """
    core.init_db()
    sql = """
        SELECT cgs.student_id, cg.course_id, cgs.group_id
          FROM class_group_students cgs
          JOIN class_groups cg ON cg.group_id = cgs.group_id
    """
    args: list[Any] = []
    if course_id is not None:
        sql += " WHERE cg.course_id = ?"
        args.append(int(course_id))
    with membership._txn() as conn:
        rows = conn.execute(sql, args).fetchall()

    # Keyed by (student, course): the same student in two groups on two
    # *different* courses is normal and must not be reported.
    seen: dict[tuple[str, int], list[int]] = {}
    for r in rows:
        seen.setdefault((r["student_id"], r["course_id"]), []).append(
            r["group_id"])
    out: dict[str, list[int]] = {}
    for (sid, _cid), gids in seen.items():
        if len(gids) > 1:
            out.setdefault(sid, []).extend(sorted(gids))
    for sid in out:
        out[sid] = sorted(set(out[sid]))

    if out:
        cg_log.group_event(
            logger,
            "%d student(s) hold more than one class group on the same "
            "course: %s", len(out), ", ".join(sorted(out)[:10]), level=30,
        )
    return out


# ── The batched audit ───────────────────────────────────────────────

def _gather(group_ids: Sequence[int] | None,
            course_id: int | None) -> dict[str, Any]:
    """Run every cross-group query once, scoped to the groups of interest."""
    core.init_db()
    scope_sql = ""
    scope_args: list[Any] = []
    if group_ids is not None:
        marks = ",".join("?" * len(group_ids))
        scope_sql = f" AND cg.group_id IN ({marks})"
        scope_args = [int(g) for g in group_ids]
    elif course_id is not None:
        scope_sql = " AND cg.course_id = ?"
        scope_args = [int(course_id)]

    with membership._txn() as conn:
        # Membership rows whose student no longer exists. The FK forbids
        # this now, but it was added after some data existed.
        orphan_members: dict[int, list[str]] = {}
        for r in conn.execute(
            "SELECT cgs.group_id, cgs.student_id FROM class_group_students cgs "
            "JOIN class_groups cg ON cg.group_id = cgs.group_id "
            "LEFT JOIN students s ON s.student_id = cgs.student_id "
            f"WHERE s.student_id IS NULL{scope_sql}", scope_args,
        ).fetchall():
            orphan_members.setdefault(r["group_id"], []).append(r["student_id"])

        # Groups pointing at a course that is gone.
        orphan_course = {
            r["group_id"]: r["course_id"] for r in conn.execute(
                "SELECT cg.group_id, cg.course_id FROM class_groups cg "
                "LEFT JOIN courses c ON c.course_id = cg.course_id "
                f"WHERE c.course_id IS NULL{scope_sql}", scope_args,
            ).fetchall()
        }

        # Slot counts per group, so "schedule typed but no timetable" is
        # one query rather than one per group.
        slot_counts: dict[int, int] = {}
        try:
            for r in conn.execute(
                "SELECT cgs.group_id, COUNT(*) AS n FROM timetable_slots cgs "
                "JOIN class_groups cg ON cg.group_id = cgs.group_id "
                f"WHERE 1=1{scope_sql} GROUP BY cgs.group_id", scope_args,
            ).fetchall():
                slot_counts[r["group_id"]] = int(r["n"])
        except sqlite3.OperationalError:
            # Timetable schema not created yet in this DB — not a fault.
            slot_counts = {}

        # Live waitlist entries, to spot a queue in front of a free seat.
        waiting: dict[int, int] = {}
        try:
            for r in conn.execute(
                "SELECT w.group_id, COUNT(*) AS n FROM class_group_waitlist w "
                "JOIN class_groups cg ON cg.group_id = w.group_id "
                f"WHERE w.status = 'waiting'{scope_sql} GROUP BY w.group_id",
                scope_args,
            ).fetchall():
                waiting[r["group_id"]] = int(r["n"])
        except sqlite3.OperationalError:
            waiting = {}

        # Effective-teacher fallback needs the course's teacher; one
        # query rather than a get_course() per group inside _check.
        course_teachers: dict[int, str | None] = {
            r["course_id"]: r["teacher"] for r in conn.execute(
                "SELECT course_id, teacher FROM courses").fetchall()
        }

    return {
        "course_teachers": course_teachers,
        "orphan_members": orphan_members,
        "orphan_course": orphan_course,
        "slot_counts": slot_counts,
        "waiting": waiting,
        "duplicates": duplicate_memberships(course_id),
    }


def _check(gc: capacity.GroupCapacity, data: dict[str, Any],
           dupe_groups: set[int]) -> list[str]:
    """Findings for one group, using the pre-gathered cross-group data."""
    g = gc.group
    out: list[str] = []

    if g.group_id in data["orphan_course"]:
        out.append(f"{ERROR}: course #{data['orphan_course'][g.group_id]} "
                   f"does not exist")
    orphans = data["orphan_members"].get(g.group_id)
    if orphans:
        out.append(f"{ERROR}: {len(orphans)} membership row(s) reference a "
                   f"missing student ({', '.join(sorted(orphans)[:5])})")
    if not (g.group_name or "").strip():
        out.append(f"{ERROR}: group name is blank")
    elif g.group_name != g.group_name.strip():
        out.append(f"{WARN}: group name has leading or trailing whitespace "
                   f"({g.group_name!r})")

    if gc.is_over:
        out.append(f"{ERROR}: over capacity — {gc.members} student(s) against "
                   f"a cap of {gc.cap} (from the {gc.cap_source})")

    if g.group_id in dupe_groups:
        out.append(f"{WARN}: holds student(s) who are also in another group "
                   f"on the same course")

    if not (g.teacher or "").strip():
        # Only a problem if the course has none either.
        course_teacher = data["course_teachers"].get(g.course_id)
        if not (course_teacher or "").strip():
            out.append(f"{WARN}: no teacher on the group or its course")

    report = schedule_text.parse_report(g.schedule)
    slots = data["slot_counts"].get(g.group_id, 0)
    if report.unparsed:
        out.append(f"{WARN}: schedule text could not be read "
                   f"({'; '.join(report.unparsed)})")
    if report.windows and not slots:
        out.append(f"{INFO}: schedule says {report} but no timetable slots "
                   f"exist")
    elif slots and not report.raw:
        out.append(f"{INFO}: {slots} timetable slot(s) but the schedule field "
                   f"is empty")

    if gc.members == 0:
        out.append(f"{INFO}: no students")
    queued = data["waiting"].get(g.group_id, 0)
    if queued and not gc.is_full:
        out.append(f"{WARN}: {queued} student(s) waitlisted while "
                   f"{gc.remaining} place(s) are free")

    if not (g.room or "").strip():
        out.append(f"{INFO}: no room set on the group")

    return out


# ── 32. Audit everything ────────────────────────────────────────────

def audit_all_groups(*,
                     course_id: int | None = None,
                     min_severity: str | None = None) -> AuditResult:
    """Check every class group and return the findings per group.

    A fixed number of queries regardless of how many groups exist — this
    is the batched primitive, and :func:`validate_group_integrity` is
    the single-group view of it.

    ``min_severity`` filters the result to that level or worse, e.g.
    ``audit_all_groups(min_severity=ERROR)`` for a launch-time check
    that should stay quiet unless something is actually broken.
    """
    groups = capacity.capacity_report(course_id=course_id)
    data = _gather(None, course_id)
    dupe_groups = {gid for gids in data["duplicates"].values() for gid in gids}

    result = AuditResult(groups_checked=len(groups))
    for gc in groups:
        result.group_names[gc.group_id] = gc.group.group_name
        found = _check(gc, data, dupe_groups)
        if found:
            result.findings[gc.group_id] = found

    if min_severity:
        result.findings = result.at_least(min_severity)

    counts = result.counts()
    cg_log.group_event(
        logger, "audit_all_groups: %s", result,
        level=30 if counts[ERROR] else 20,
    )
    return result


# ── 31. Audit one group ─────────────────────────────────────────────

def validate_group_integrity(group_id: int) -> list[str]:
    """Findings for one class group, worst first.

    Same checks as :func:`audit_all_groups`, scoped so the cross-group
    queries only load what this group needs. Returns an empty list for a
    healthy group.
    """
    gid = membership._require_group(group_id).group_id
    rows = capacity.capacity_report(group_ids=[gid])
    data = _gather([gid], None)
    dupe_groups = {g for gids in data["duplicates"].values() for g in gids}
    found = _check(rows[0], data, dupe_groups)
    order = {ERROR: 0, WARN: 1, INFO: 2}
    found.sort(key=lambda f: order.get(f.split(":", 1)[0], 3))
    if found:
        cg_log.group_event(
            logger, "validate_group_integrity on #%d: %s",
            gid, "; ".join(found), group_id=gid,
            level=30 if any(f.startswith(ERROR) for f in found) else 20,
        )
    return found
