"""Populating a class group from the course cohort.

Feature 10 was specified as "everyone on the course who isn't in a group
yet". There is no such list. ``courses`` has no student column and there
is no course-enrolment table — a sixth-form :mod:`enrolments` row is
college-level (``student_id``, ``academic_year``, ``year_group``), not
per-subject. The nearest honest definition of "on this course" is
therefore:

    students enrolled for the course's ``academic_year`` in the course's
    ``year_group``, whose ``enrolments.status`` is active, minus anyone
    already in any class group belonging to that course.

That is a *cohort*, not a course roster, and it is wider than what the
caller probably means — a Year 12 maths group's candidate pool this way
is every Year 12 student, not just the mathematicians. So:

* the default is :func:`preview_intake`, which returns the candidates
  and writes nothing;
* :func:`bulk_enrol_from_course` requires ``confirm=True`` before it
  will insert anything;
* :func:`candidates_for_course` accepts a ``subject_filter`` that
  narrows the cohort using the three ``subject_1..3`` option columns on
  the student record, which is the only per-subject signal the schema
  actually carries.

When a real course-enrolment table lands, :func:`candidates_for_course`
is the single function to rewrite; everything else works off its output.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Iterator
from contextlib import contextmanager

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
BulkResult = membership.BulkResult

#: Enrolment statuses that count as "currently on roll". Withdrawn and
#: Completed learners are excluded from an intake by default — putting a
#: leaver into a teaching set is the bug this guards against.
ACTIVE_ENROLMENT_STATUSES: tuple[str, ...] = ("Enrolled", "Pending")


@dataclass
class Candidate:
    """A student eligible to be added to a group for a given course."""
    student_id: str
    full_name: str
    year_group: int
    academic_year: str
    enrolment_status: str
    student_status: str
    subjects: list[str]
    #: Groups this student already holds *for this course*. Non-empty
    #: means they are placed and should not appear in an intake.
    existing_group_ids: list[int]

    @property
    def is_unplaced(self) -> bool:
        return not self.existing_group_ids


@contextmanager
def _read() -> Iterator[sqlite3.Connection]:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _init() -> None:
    core.init_db()
    # The cohort query joins enrolments, which lives in the same file but
    # is created by its own module.
    from education_system.systems.sixth_form.domain.admissions.enrolments \
        import enrolments as _enrolments
    _enrolments.init_db()


def _require_course(course_id: int):
    from education_system.systems.sixth_form.domain.academics.courses import (
        courses as _courses,
    )
    try:
        cid = int(course_id)
    except (TypeError, ValueError):
        raise ValidationError("Course ID must be a whole number") from None
    course = _courses.get_course(cid)
    if course is None:
        cg_log.rejected(logger, "Unknown course #%s for intake", cid)
        raise ValidationError(f"No course with id {cid}")
    return course


def candidates_for_course(course_id: int,
                          *,
                          subject_filter: str | None = None,
                          include_placed: bool = False,
                          statuses: tuple[str, ...] =
                          ACTIVE_ENROLMENT_STATUSES,
                          active_students_only: bool = True,
                          ) -> list[Candidate]:
    """Students who could join a class group for this course.

    One query, not a per-student lookup: the cohort, their existing
    placements for this course, and their option choices all come back
    together.

    ``subject_filter`` matches case-insensitively against the student's
    three option columns. Use it whenever you can — without it the
    cohort is the entire year group.
    """
    _init()
    course = _require_course(course_id)
    if not statuses:
        raise ValidationError("At least one enrolment status is required")

    status_marks = ",".join("?" * len(statuses))
    args: list[Any] = [course.course_id, course.academic_year,
                       int(course.year_group), *statuses]

    sql = f"""
        SELECT s.student_id, s.first_name, s.middle_name, s.last_name,
               s.status AS student_status,
               s.subject_1, s.subject_2, s.subject_3,
               e.year_group, e.academic_year,
               e.status AS enrolment_status,
               (SELECT GROUP_CONCAT(cg.group_id)
                  FROM class_group_students cgs
                  JOIN class_groups cg ON cg.group_id = cgs.group_id
                 WHERE cgs.student_id = s.student_id
                   AND cg.course_id = ?) AS placed_in
          FROM enrolments e
          JOIN students s ON s.student_id = e.student_id
         WHERE e.academic_year = ?
           AND e.year_group = ?
           AND e.status IN ({status_marks})
         ORDER BY s.last_name COLLATE NOCASE, s.first_name COLLATE NOCASE
    """
    with _read() as conn:
        rows = conn.execute(sql, args).fetchall()

    wanted = (subject_filter or "").strip().lower()
    out: list[Candidate] = []
    for r in rows:
        if active_students_only and \
                (r["student_status"] or "").strip().lower() != "active":
            continue
        subjects = [s for s in (r["subject_1"], r["subject_2"],
                                r["subject_3"]) if s]
        if wanted and not any(wanted == s.strip().lower() for s in subjects):
            continue
        placed = [int(g) for g in (r["placed_in"] or "").split(",") if g]
        if placed and not include_placed:
            continue
        parts = [r["first_name"], r["middle_name"] or "", r["last_name"]]
        out.append(Candidate(
            student_id=r["student_id"],
            full_name=" ".join(p for p in parts if p).strip(),
            year_group=int(r["year_group"]),
            academic_year=r["academic_year"],
            enrolment_status=r["enrolment_status"],
            student_status=r["student_status"],
            subjects=subjects,
            existing_group_ids=placed,
        ))

    cg_log.group_event(
        logger,
        "Intake candidates for course #%d (%s %s, Y%d): %d "
        "(subject filter: %s)",
        course.course_id, course.course_code, course.academic_year,
        course.year_group, len(out), subject_filter or "none",
        level=10,  # DEBUG — this runs on every preview refresh
    )
    return out


def preview_intake(group_id: int,
                   *,
                   subject_filter: str | None = None,
                   limit: int | None = None) -> dict[str, Any]:
    """What :func:`bulk_enrol_from_course` would do, without doing it.

    Returns the candidate list, how many the group can actually take,
    and who would be left over — everything a confirmation dialog needs
    to show before somebody commits to a thirty-student write.
    """
    _init()
    group = membership._require_group(group_id)
    course = _require_course(group.course_id)
    candidates = candidates_for_course(
        course.course_id, subject_filter=subject_filter)

    cap = core.effective_cap(group)
    current = core.count_members(group.group_id)
    headroom = None if cap is None else max(0, cap - current)

    take = len(candidates)
    if limit is not None:
        take = min(take, max(0, int(limit)))
    if headroom is not None:
        take = min(take, headroom)

    return {
        "group_id": group.group_id,
        "group_name": group.group_name,
        "course_id": course.course_id,
        "course_code": course.course_code,
        "academic_year": course.academic_year,
        "year_group": course.year_group,
        "subject_filter": subject_filter,
        "candidates": candidates,
        "current_members": current,
        "capacity": cap,
        "headroom": headroom,
        "would_add": candidates[:take],
        "would_skip": candidates[take:],
    }


def bulk_enrol_from_course(group_id: int,
                           *,
                           confirm: bool = False,
                           subject_filter: str | None = None,
                           limit: int | None = None,
                           actor: str | None = None,
                           reason: str | None = None) -> BulkResult:
    """Fill a class group from its course's unplaced cohort.

    Requires ``confirm=True``. Without it this raises rather than
    writing, because the candidate set is a whole year group unless
    ``subject_filter`` narrows it, and an accidental run would put every
    Year 12 student into one maths set. Call :func:`preview_intake`
    first and show the user what they are about to do.

    Delegates the write to :func:`class_group_membership.add_members_bulk`,
    so capacity, duplicates and the audit trail are handled in exactly
    one place.
    """
    _init()
    group = membership._require_group(group_id)
    if not confirm:
        raise ValidationError(
            "bulk_enrol_from_course writes to the roster and needs "
            "confirm=True; call preview_intake() first to see the "
            f"{len(candidates_for_course(group.course_id, subject_filter=subject_filter))} "
            "candidate(s) it would add")

    plan = preview_intake(group_id, subject_filter=subject_filter,
                          limit=limit)
    to_add = [c.student_id for c in plan["would_add"]]

    if not to_add:
        cg_log.group_event(
            logger,
            "Intake for class group #%d (%s) found no unplaced candidates",
            group.group_id, group.group_name,
            group_id=group.group_id, actor=actor,
        )
        return BulkResult(group_id=group.group_id, action="intake")

    result = membership.add_members_bulk(
        group.group_id, to_add,
        actor=actor,
        reason=reason or f"cohort intake for course #{group.course_id}",
        action="intake",
    )
    for c in plan["would_skip"]:
        result.skipped.append(
            membership.Skip(c.student_id, "beyond capacity or limit"))

    cg_log.group_event(
        logger,
        "Cohort intake added %d student(s) to class group #%d (%s) "
        "from course #%d; %d not taken",
        result.count, group.group_id, group.group_name,
        group.course_id, result.skipped_count,
        group_id=group.group_id, actor=actor,
    )
    return result


def unplaced_for_course(course_id: int,
                        *,
                        subject_filter: str | None = None) -> list[str]:
    """Just the ids — the cheap form for a "who's missing?" count."""
    return [c.student_id for c in
            candidates_for_course(course_id, subject_filter=subject_filter)]
