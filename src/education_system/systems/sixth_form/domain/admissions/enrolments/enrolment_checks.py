"""Warnings at enrolment time, and the class / tutor group sizes behind
them.

:func:`check_enrolment` looks at one learner's enrolment for a year and
returns everything that will need sorting before they can start
properly: subjects with no class group (none set up, or all full), class
groups over their cap, timetable clashes between their groups, a tutor
group over the size limit, no ID check or unconfirmed right to study, a
visa expiring, and condition-of-funding gaps (when the funding module is
installed). Nothing here changes a record.

The tutor-group size limit is the ``tutor_group_size_limit`` enrolment
setting (:mod:`course_changes`, default 25).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from education_system.systems.sixth_form.domain.admissions.enrolments import (
    course_changes as _cc,
    enrolments as _enrolments,
)

logger = logging.getLogger(__name__)

#: Warning kinds, for screens that group or colour them.
KINDS: tuple[str, ...] = (
    "enrolment", "class group missing", "class group full",
    "class group over capacity", "timetable clash", "tutor group",
    "identity", "right to study", "visa", "funding",
)


@dataclass
class EnrolmentWarning:
    kind: str
    message: str

    def __str__(self) -> str:
        return self.message


def _cg():
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups,
    )
    return class_groups


def _capacity():
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_group_capacity,
    )
    return class_group_capacity


def _enrolment_for(student_id: str, academic_year: str | None
                   ) -> _enrolments.Enrolment | None:
    year = academic_year or _enrolments.current_academic_year()
    rows = _enrolments.list_enrolments(student_id=student_id,
                                       academic_year=year)
    live = [e for e in rows if e.is_live]
    return (live or rows or [None])[0]


# ── Class groups ────────────────────────────────────────────────────

def _subject_warnings(e: _enrolments.Enrolment) -> list[EnrolmentWarning]:
    out: list[EnrolmentWarning] = []
    cap = _capacity()
    aims = _enrolments.aims_for_enrolment(e)
    if not aims:
        out.append(EnrolmentWarning(
            "enrolment", f"No active learning aims for {e.academic_year} — "
                         "nothing to place in class groups"))
    for aim in aims:
        placed = _cc.subject_groups(e.student_id, aim.subject)
        if placed:
            for g in placed:
                gc = cap.capacity_of(g.group_id)
                if gc.is_over:
                    out.append(EnrolmentWarning(
                        "class group over capacity",
                        f"{aim.subject}: class group {gc} is over its cap"))
            continue
        courses = _cc.subject_courses(aim.subject, e.academic_year,
                                      e.year_group, aim.qualification_type)
        groups = [g for c in courses
                  for g in _cg().list_groups(course_id=c.course_id)]
        if not groups:
            out.append(EnrolmentWarning(
                "class group missing",
                f"{aim.label}: no class group is set up for Year "
                f"{e.year_group} in {e.academic_year}"))
        elif all(cap.capacity_of(g.group_id).is_full for g in groups):
            out.append(EnrolmentWarning(
                "class group full",
                f"{aim.label}: every class group is full ("
                + ", ".join(str(cap.capacity_of(g.group_id))
                            for g in groups) + ")"))
        else:
            out.append(EnrolmentWarning(
                "class group missing",
                f"{aim.label}: not placed in a class group yet (space is "
                "available)"))
    return out


def _clash_warnings(student_id: str) -> list[EnrolmentWarning]:
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_group_conflicts as _conflicts,
    )
    return [EnrolmentWarning(
        "timetable clash",
        f"Timetable clash: {a.group_name} and {b.group_name} meet at the "
        "same time")
        for a, b in _conflicts.student_timetable_clashes(student_id)]


# ── Tutor groups ────────────────────────────────────────────────────

@dataclass
class TutorGroupSize:
    tutor_group_id: int
    name: str
    year_group: int
    tutor: str | None
    members: int
    limit: int

    @property
    def over(self) -> bool:
        return self.members > self.limit

    def __str__(self) -> str:
        return (f"{self.name}: {self.members}/{self.limit}"
                + (" (over the limit)" if self.over else ""))


def tutor_group_sizes() -> list[TutorGroupSize]:
    """Every tutor group with its size against the limit."""
    from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
        tutor_groups as _tg,
    )
    limit = _cc.get_setting(_cc.TUTOR_GROUP_LIMIT)
    return [TutorGroupSize(r.group.tutor_group_id, r.group.name,
                           r.group.year_group, r.group.tutor, r.member_count,
                           limit)
            for r in _tg.list_groups_with_counts()]


def _tutor_warnings(e: _enrolments.Enrolment) -> list[EnrolmentWarning]:
    from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
        tutor_groups as _tg,
    )
    if not e.tutor_group:
        return [EnrolmentWarning("tutor group", "No tutor group set on the "
                                                "enrolment")]
    g = _tg.get_group_by_name(e.tutor_group)
    if g is None:
        return []
    limit = _cc.get_setting(_cc.TUTOR_GROUP_LIMIT)
    n = _tg.count_members(g.tutor_group_id)
    if n > limit:
        return [EnrolmentWarning(
            "tutor group", f"Tutor group {g.name} has {n} learners — over "
                           f"the limit of {limit}")]
    return []


# ── Identity, right to study, funding ───────────────────────────────

def _identity_warnings(student_id: str) -> list[EnrolmentWarning]:
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        identity_checks as _idc,
    )
    s = _idc.check_status(student_id,
                          within_days=_cc.get_setting(_cc.VISA_WARNING_DAYS))
    out = []
    if not s.id_checked:
        out.append(EnrolmentWarning("identity", "No ID check recorded"))
    if not s.has_photo:
        out.append(EnrolmentWarning("identity", "No photo on file"))
    if s.right_to_study == "unknown":
        out.append(EnrolmentWarning("right to study",
                                    "Right to study not confirmed"))
    elif s.right_to_study in ("no", "restricted"):
        out.append(EnrolmentWarning("right to study",
                                    "Right to study needs checking"))
    if s.visa:
        out.append(EnrolmentWarning(
            "visa", f"Visa {s.visa}"
                    + (f" ({s.visa_expiry})" if s.visa_expiry else "")))
    return out


def funding_gaps(enrolment_id: int) -> list[str] | None:
    """Condition-of-funding gaps for an enrolment from
    :mod:`enrolments.funding` (empty when met or when the condition does
    not apply), or None when that module is not installed."""
    try:
        from education_system.systems.sixth_form.domain.admissions.enrolments import (
            funding as _funding,
        )
    except ImportError:
        return None
    return [f"{g.area}: needs {g.requirement}"
            + (f" (best grade {g.best_grade})" if g.best_grade else "")
            + (f" — {g.status}" if g.status else "")
            for g in _funding.condition_of_funding_gaps(int(enrolment_id))]


def _funding_warnings(enrolment_id: int) -> list[EnrolmentWarning]:
    gaps = funding_gaps(enrolment_id)
    return [EnrolmentWarning("funding", f"Condition of funding: {g}")
            for g in gaps or []]


# ── The check ───────────────────────────────────────────────────────

def check_enrolment(student_id: str, academic_year: str | None = None
                    ) -> list[EnrolmentWarning]:
    """Every warning for the learner's enrolment in the year (default:
    the current one). A check that cannot run becomes a warning itself,
    so this never raises for a bad area."""
    e = _enrolment_for(student_id, academic_year)
    year = academic_year or _enrolments.current_academic_year()
    if e is None:
        return [EnrolmentWarning("enrolment",
                                 f"{student_id} has no enrolment in {year}")]
    out: list[EnrolmentWarning] = []
    if not e.is_live:
        out.append(EnrolmentWarning(
            "enrolment", f"The {year} enrolment is {e.status}"
                         + (" (archived)" if e.is_archived else "")))
    for label, fn, args in (
            ("class groups", _subject_warnings, (e,)),
            ("timetable", _clash_warnings, (student_id,)),
            ("tutor group", _tutor_warnings, (e,)),
            ("identity", _identity_warnings, (student_id,)),
            ("funding", _funding_warnings, (e.enrolment_id,))):
        try:
            out += fn(*args)
        except Exception as exc:  # noqa: BLE001 — reported, never blocks
            logger.exception("Enrolment check %s for %s", label, student_id)
            out.append(EnrolmentWarning("enrolment",
                                        f"Could not check {label}: {exc}"))
    return out


# ── Reports ─────────────────────────────────────────────────────────

@dataclass
class ClassSizeRow:
    course_code: str
    subject: str
    year_group: int
    group_id: int
    group_name: str
    members: int
    cap: int | None
    remaining: int | None
    full: bool
    over: bool


def class_size_report(academic_year: str | None = None) -> list[ClassSizeRow]:
    """Every live class group on the year's courses, with roll and cap."""
    from education_system.systems.sixth_form.domain.academics.courses import (
        courses as _courses,
    )
    year = academic_year or _enrolments.current_academic_year()
    cap = _capacity()
    out: list[ClassSizeRow] = []
    for c in _courses.list_courses(academic_year=year):
        for gc in cap.capacity_report(course_id=c.course_id):
            if gc.group.archived_at:
                continue
            out.append(ClassSizeRow(
                c.course_code, c.subject, c.year_group, gc.group_id,
                gc.group.group_name, gc.members, gc.cap, gc.remaining,
                gc.is_full, gc.is_over))
    return out


@dataclass
class TimetableRow:
    day: str
    period: int
    start: str
    end: str
    group_name: str
    course_code: str | None
    room: str | None
    teacher: str | None


def learner_timetable(student_id: str) -> list[TimetableRow]:
    """The learner's week from their class groups' timetable slots,
    in day/period order."""
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_group_conflicts as _conflicts,
    )
    groups = [g.group_id for g in _cg().groups_for_student(student_id)]
    if not groups:
        return []
    return [TimetableRow(s.day_name, s.period, s.start, s.end, s.group_name,
                         s.course_code, s.room, s.teacher)
            for s in sorted(_conflicts.all_slots(group_ids=groups),
                            key=lambda s: (s.day, s.period, s.start))]
