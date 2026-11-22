"""Attendance analytics for the Sixth Form System.

Sibling to :mod:`attendance`. The reports in
:mod:`attendance_report` count what happened. This module tries to say
what it *means*, which is a different and more careful job.

Five questions, each of which a college is regularly asked and rarely
able to answer with its own data:

* **Does attendance affect grades here?** (:func:`attainment_correlation`)
  Not "does it in general" — does it in this college, this year, in this
  subject. The answer is the single most persuasive thing anybody can
  put in front of a sixth-former, and it is much more persuasive when it
  is their own college's number.
* **Is it one subject or all of them?**
  (:func:`subject_comparison`) A learner at 82% overall who is at 98% in
  three subjects and 40% in a fourth does not have an attendance
  problem; they have a problem with that subject, and the two need
  completely different conversations.
* **Where will this end up?** (:func:`forecast`) Projected end-of-year
  attendance, and the headroom left — how many more sessions can be
  missed before a threshold is crossed.
* **Are we better than last year?** (:func:`benchmark`) Same point in
  the year, previous year, plus any target the college has set.
* **When does absence happen?** (:func:`heatmap`) By week and period.
  Bad Friday afternoons are real, and they are a timetabling decision
  rather than a pastoral one.

**Correlation is reported with its sample size and never as causation.**
A subject with eleven learners produces a correlation coefficient that
means nothing, and this module says so rather than letting somebody put
it on a slide.
"""

from __future__ import annotations

import datetime as _dt
import logging
import math
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_calendar as calendar,
    attendance_codes as codes,
    attendance_thresholds as thresholds,
)
from education_system.systems.sixth_form.domain.academics.timetable import (
    timetable as tt,
)
from education_system import paths
from education_system.systems.sixth_form.domain.academics.qualifications import (
    grade_scales as _gs,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

# Below this many learners, a correlation is noise with a decimal point.
MIN_SAMPLE: int = 20

# Strength bands for a correlation coefficient, so nobody has to
# remember what 0.31 means.
STRONG: str = "Strong"
MODERATE: str = "Moderate"
WEAK: str = "Weak"
NEGLIGIBLE: str = "Negligible"
INSUFFICIENT: str = "Not enough data"

# UK A-level grade points, for turning grades into something averageable.
# The fallback when a grade's qualification type is unknown; known types
# go through grade_scales (see grade_points).
GRADE_POINTS: dict[str, float] = {
    "A*": 6.0, "A": 5.0, "B": 4.0, "C": 3.0, "D": 2.0, "E": 1.0, "U": 0.0,
    # BTEC and applied equivalents.
    "D*": 6.0, "DD": 5.0, "M": 3.0, "P": 1.5, "F": 0.0,
}

DEFAULT_WINDOW_DAYS: int = 42


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Correlation:
    """A relationship between attendance and attainment, with its caveats."""

    sample: int
    coefficient: float | None
    scope: str = "College"
    mean_attendance: float | None = None
    mean_points: float | None = None
    grades_per_10_points: float | None = None

    @property
    def strength(self) -> str:
        if self.coefficient is None or self.sample < MIN_SAMPLE:
            return INSUFFICIENT
        magnitude = abs(self.coefficient)
        if magnitude >= 0.5:
            return STRONG
        if magnitude >= 0.3:
            return MODERATE
        if magnitude >= 0.1:
            return WEAK
        return NEGLIGIBLE

    @property
    def reliable(self) -> bool:
        return self.sample >= MIN_SAMPLE and self.coefficient is not None

    @property
    def label(self) -> str:
        if not self.reliable:
            return (f"{self.scope}: not enough data "
                    f"({self.sample} learner(s); {MIN_SAMPLE} needed)")
        direction = "higher" if (self.coefficient or 0) > 0 else "lower"
        detail = ""
        if self.grades_per_10_points is not None:
            detail = (f" — about {abs(self.grades_per_10_points):.1f} of a "
                      f"grade per 10 percentage points of attendance")
        return (f"{self.scope}: {self.strength.lower()} relationship "
                f"(r={self.coefficient:.2f}, n={self.sample}); better "
                f"attendance goes with {direction} grades{detail}")


@dataclass
class SubjectAttendance:
    """One learner's attendance in one subject, against their own average."""

    subject: str
    group_id: int
    sessions: int
    attending: int
    percentage: float | None
    overall_percentage: float | None = None

    @property
    def gap(self) -> float | None:
        """Points below (negative) or above the learner's own average."""
        if self.percentage is None or self.overall_percentage is None:
            return None
        return round(self.percentage - self.overall_percentage, 1)

    @property
    def is_outlier(self) -> bool:
        gap = self.gap
        return gap is not None and gap <= -10.0

    @property
    def label(self) -> str:
        pct = "—" if self.percentage is None else f"{self.percentage:.1f}%"
        gap = "" if self.gap is None else f" ({self.gap:+.1f} vs their average)"
        return f"{self.subject}: {pct}{gap}"


@dataclass
class Forecast:
    """Where a learner's attendance is heading."""

    student_id: str
    current_pct: float | None
    sessions_so_far: int
    sessions_remaining: int
    projected_pct: float | None
    headroom_sessions: int
    target_pct: float

    @property
    def will_meet_target(self) -> bool | None:
        if self.projected_pct is None:
            return None
        return self.projected_pct >= self.target_pct

    @property
    def label(self) -> str:
        if self.current_pct is None:
            return f"{self.student_id}: no attendance data"
        projected = ("—" if self.projected_pct is None
                     else f"{self.projected_pct:.1f}%")
        return (f"{self.student_id}: {self.current_pct:.1f}% now, {projected} "
                f"projected; can miss {self.headroom_sessions} more session(s)"
                f" and hold {self.target_pct:g}%")


@dataclass
class Benchmark:
    """This year against last year, and against target."""

    scope: str
    current_pct: float | None
    previous_pct: float | None
    target_pct: float | None
    current_window: tuple[str, str] | None = None
    previous_window: tuple[str, str] | None = None
    learners: int = 0

    @property
    def change(self) -> float | None:
        if self.current_pct is None or self.previous_pct is None:
            return None
        return round(self.current_pct - self.previous_pct, 1)

    @property
    def against_target(self) -> float | None:
        if self.current_pct is None or self.target_pct is None:
            return None
        return round(self.current_pct - self.target_pct, 1)

    @property
    def label(self) -> str:
        current = ("—" if self.current_pct is None
                   else f"{self.current_pct:.1f}%")
        change = ("" if self.change is None
                  else f", {self.change:+.1f} on last year")
        target = ("" if self.against_target is None
                  else f", {self.against_target:+.1f} against target")
        return f"{self.scope}: {current}{change}{target}"


@dataclass
class HeatCell:
    """One cell of the week-by-period grid."""

    weekday: int
    period: int
    sessions: int = 0
    attending: int = 0

    @property
    def percentage(self) -> float | None:
        if self.sessions == 0:
            return None
        return round(100.0 * self.attending / self.sessions, 1)


@dataclass
class Heatmap:
    """Attendance by weekday and period."""

    cells: dict[tuple[int, int], HeatCell] = field(default_factory=dict)
    date_from: str = ""
    date_to: str = ""

    def cell(self, weekday: int, period: int) -> HeatCell | None:
        return self.cells.get((weekday, period))

    @property
    def worst(self) -> HeatCell | None:
        usable = [c for c in self.cells.values()
                  if c.percentage is not None and c.sessions >= 10]
        return min(usable, key=lambda c: c.percentage or 100) if usable else None

    @property
    def best(self) -> HeatCell | None:
        usable = [c for c in self.cells.values()
                  if c.percentage is not None and c.sessions >= 10]
        return max(usable, key=lambda c: c.percentage or 0) if usable else None

    def rows(self) -> list[tuple[int, list[HeatCell | None]]]:
        """The grid, as weekday rows of period cells — for printing."""
        periods = sorted({p for _d, p in self.cells})
        out: list[tuple[int, list[HeatCell | None]]] = []
        for weekday in sorted({d for d, _p in self.cells}):
            out.append((weekday,
                        [self.cells.get((weekday, p)) for p in periods]))
        return out


# ── Maths ───────────────────────────────────────────────────────────

def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson's r, or ``None`` when it is not defined.

    Written out rather than pulled from a library: this package has no
    numeric dependency and should not grow one for twelve lines.
    """
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 0 or var_y <= 0:
        return None
    return round(cov / math.sqrt(var_x * var_y), 3)


def _slope(xs: list[float], ys: list[float]) -> float | None:
    """Least-squares slope — grade points per point of attendance."""
    n = len(xs)
    if n < 2:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator <= 0:
        return None
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    return numerator / denominator


def grade_points(grade: str | None,
                 qualification_type: str | None = None) -> float | None:
    """Turn a grade into something averageable.

    With a known qualification type the grade's position on that scale
    is stretched onto the A-level 0-6 range (A level itself is unchanged:
    A* 6 … U 0; a BTEC Diploma DM sits where its rank puts it), so a
    college with BTEC, T Level and A level learners correlates on one
    footing. Without a type, the old flat lookup.
    """
    if not grade:
        return None
    g = str(grade).strip()
    if qualification_type:
        try:
            scale = _gs.scale_for(qualification_type)
        except ValueError:
            scale = None
        if scale is not None and _gs.is_valid_grade(g, qualification_type):
            points = _gs.grade_points(g, qualification_type)
            top = _gs.grade_points(scale.grades[0], qualification_type)
            if points is not None and top:
                return round(6.0 * points / top, 3)
    return GRADE_POINTS.get(g, GRADE_POINTS.get(g.upper()))


def _qualification_type(student_id: str, subject: str | None,
                        recorded: str | None = None) -> str | None:
    if recorded:
        return recorded
    if not subject or subject == "Unknown":
        return None
    try:
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            learning_aims,
        )
        return learning_aims.qualification_type_for(student_id, subject)
    except Exception:
        logger.debug("Qualification type unavailable for %s / %s",
                     student_id, subject, exc_info=True)
        return None


# ── Attainment correlation ──────────────────────────────────────────

def _grades_for_period(*, date_from: str, date_to: str
                       ) -> dict[str, list[tuple[str, float]]]:
    """``student_id`` → [(subject, points)], from whatever grade source
    this installation has."""
    out: dict[str, list[tuple[str, float]]] = {}
    for module_path, attr in (
        ("education_system.systems.sixth_form.domain.assessment.exam_results",
         "exam_results"),
        ("education_system.systems.sixth_form.domain.assessment.mock_exams",
         "mock_exams"),
    ):
        try:
            module = __import__(module_path, fromlist=[attr])
            source = getattr(module, attr)
            lister = (getattr(source, "list_results", None)
                      or getattr(source, "list_entries", None))
            if lister is None:
                continue
            mock_subjects: dict[int, str] = {}
            if attr == "mock_exams":
                mock_subjects = {m.mock_id: m.subject
                                 for m in source.list_mocks()}
            for row in lister():
                # exam_results rows carry the result (grade, type) inside
                # ``row.result``; mock rows carry a grade and a mock id.
                result = getattr(row, "result", None)
                grade = (getattr(row, "grade", None)
                         or getattr(result, "grade", None))
                student_id = getattr(row, "student_id", None)
                if not grade or not student_id:
                    continue
                subject = (getattr(row, "subject", None)
                           or mock_subjects.get(getattr(row, "mock_id", None))
                           or "Unknown")
                qtype = _qualification_type(
                    student_id, subject,
                    getattr(result, "qualification_type", None))
                points = grade_points(grade, qtype)
                if points is None:
                    continue
                out.setdefault(student_id, []).append((subject, points))
            if out:
                return out
        except Exception:                   # pragma: no cover - optional dep
            logger.debug("Grade source %s unavailable", module_path,
                         exc_info=True)
    return out


def attainment_correlation(
    *,
    date_from: str,
    date_to: str,
    subject: str | None = None,
) -> Correlation:
    """Does attendance track attainment in this college?

    Pairs each learner's attendance over the window with their average
    grade points, and reports the correlation with its sample size. The
    slope is translated into "grades per 10 percentage points", which is
    the only form of this number anybody has ever found persuasive.
    """
    date_from = core._validate_date(date_from)
    date_to = core._validate_date(date_to)
    grades = _grades_for_period(date_from=date_from, date_to=date_to)
    if not grades:
        return Correlation(sample=0, coefficient=None,
                           scope=subject or "College")

    attendance_values: list[float] = []
    point_values: list[float] = []
    for student_id, rows in grades.items():
        relevant = [p for s, p in rows
                    if subject is None
                    or s.strip().lower() == subject.strip().lower()]
        if not relevant:
            continue
        summary = core.summary_for_student(student_id, date_from=date_from,
                                           date_to=date_to)
        if summary.total == 0 or summary.percentage is None:
            continue
        attendance_values.append(summary.percentage)
        point_values.append(sum(relevant) / len(relevant))

    sample = len(attendance_values)
    coefficient = _pearson(attendance_values, point_values)
    slope = _slope(attendance_values, point_values)
    return Correlation(
        sample=sample, coefficient=coefficient,
        scope=subject or "College",
        mean_attendance=(round(sum(attendance_values) / sample, 1)
                         if sample else None),
        mean_points=(round(sum(point_values) / sample, 2)
                     if sample else None),
        grades_per_10_points=(round(slope * 10, 2)
                              if slope is not None else None))


def correlation_by_subject(*, date_from: str, date_to: str,
                           minimum: int = MIN_SAMPLE) -> list[Correlation]:
    """The same question per subject, strongest relationship first."""
    grades = _grades_for_period(date_from=date_from, date_to=date_to)
    subjects = {s for rows in grades.values() for s, _p in rows}
    out = [attainment_correlation(date_from=date_from, date_to=date_to,
                                  subject=subject)
           for subject in sorted(subjects)]
    out = [c for c in out if c.sample >= max(1, minimum)]
    out.sort(key=lambda c: -(abs(c.coefficient or 0)))
    return out


# ── Subject comparison ──────────────────────────────────────────────

def subject_comparison(
    student_id: str,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> list[SubjectAttendance]:
    """One learner's attendance broken down by subject.

    The question this answers — "is it everything, or is it one class?" —
    changes the conversation completely, and a single percentage cannot
    answer it.
    """
    date_to = core._validate_date(date_to or _dt.date.today().isoformat())
    date_from = core._validate_date(
        date_from or (_dt.date.fromisoformat(date_to)
                      - _dt.timedelta(days=window_days)).isoformat())

    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    from education_system.systems.sixth_form.domain.academics.courses import (
        courses as _courses,
    )
    overall = core.summary_for_student(student_id, date_from=date_from,
                                       date_to=date_to)

    groups = {g.group_id: g for g in _cg.list_groups()}
    courses = {c.course_id: c for c in _courses.list_courses()}
    slot_group = {s.slot_id: s.group_id for s in tt.list_slots()}

    tally: dict[int, list[int]] = {}
    for record in core.list_records(student_id=student_id,
                                    date_from=date_from, date_to=date_to):
        group_id = slot_group.get(record.slot_id)
        if group_id is None:
            continue
        entry = tally.setdefault(group_id, [0, 0])
        if not codes.counts_toward_possible(record.code):
            continue
        entry[0] += 1
        if codes.counts_as_present(record.code) or \
                record.status in core.ATTENDING_STATUSES:
            entry[1] += 1

    out: list[SubjectAttendance] = []
    for group_id, (sessions, attending) in tally.items():
        group = groups.get(group_id)
        course = courses.get(group.course_id) if group else None
        subject = (course.subject if course else None) or (
            group.group_name if group else f"Group {group_id}")
        percentage = (round(100.0 * attending / sessions, 1)
                      if sessions else None)
        out.append(SubjectAttendance(
            subject=subject, group_id=group_id, sessions=sessions,
            attending=attending, percentage=percentage,
            overall_percentage=overall.percentage))
    out.sort(key=lambda s: (s.percentage if s.percentage is not None else 101))
    return out


def subject_outliers(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    gap_points: float = 10.0,
) -> list[tuple[str, SubjectAttendance]]:
    """Learners whose attendance collapses in exactly one subject.

    Almost always something specific and fixable — a clash, a
    relationship with a teacher, a subject they have quietly given up on
    — and completely invisible in an overall percentage.
    """
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    out: list[tuple[str, SubjectAttendance]] = []
    for student in _students.list_students():
        if getattr(student, "status", "Active") not in ("Active", None):
            continue
        for entry in subject_comparison(student.student_id,
                                        date_from=date_from, date_to=date_to,
                                        window_days=window_days):
            gap = entry.gap
            if gap is not None and gap <= -abs(gap_points):
                out.append((student.student_id, entry))
    out.sort(key=lambda item: item[1].gap or 0)
    return out


# ── Forecast ────────────────────────────────────────────────────────

def sessions_remaining(*, until: str | None = None,
                       student_id: str | None = None,
                       year_group: int | None = None) -> int:
    """Teaching sessions left between today and the end of the year."""
    today = _dt.date.today().isoformat()
    end = core._validate_date(until or _academic_year_end(today))
    if end <= today:
        return 0
    if student_id is None:
        return calendar.teaching_sessions(today, end, year_group=year_group)
    # A learner's own remaining lessons, from their timetable.
    days = calendar.teaching_days(today, end, year_group=year_group)
    slots = tt.list_slots(student_id=student_id)
    by_day: dict[int, int] = {}
    for slot in slots:
        by_day[slot.day] = by_day.get(slot.day, 0) + 1
    return sum(by_day.get(_dt.date.fromisoformat(d).weekday() + 1, 0)
               for d in days)


def _academic_year_end(date: str) -> str:
    target = _dt.date.fromisoformat(date)
    year = target.year if target.month < 9 else target.year + 1
    return f"{year}-07-31"


def forecast(
    student_id: str,
    *,
    date_from: str | None = None,
    until: str | None = None,
    target_pct: float | None = None,
) -> Forecast:
    """Where this learner ends up if nothing changes.

    Projection assumes the current rate continues, which is the
    assumption worth challenging in the conversation — the point of
    showing it is that it is not fixed.
    """
    target = (target_pct if target_pct is not None
              else thresholds.value_of(thresholds.TARGET_ATTENDANCE,
                                       default=95.0))
    assert target is not None
    today = _dt.date.today().isoformat()
    date_from = core._validate_date(date_from or _academic_year_start(today))
    summary = core.summary_for_student(student_id, date_from=date_from,
                                       date_to=today)
    remaining = sessions_remaining(until=until, student_id=student_id)

    if summary.total == 0 or summary.percentage is None:
        return Forecast(student_id=student_id, current_pct=None,
                        sessions_so_far=0, sessions_remaining=remaining,
                        projected_pct=None, headroom_sessions=remaining,
                        target_pct=target)

    rate = summary.attending / summary.total
    projected_attending = summary.attending + rate * remaining
    projected_total = summary.total + remaining
    projected = (round(100.0 * projected_attending / projected_total, 1)
                 if projected_total else None)

    # Headroom: with perfect attendance from here, how many sessions can
    # still be missed and stay above target.
    ratio = target / 100.0
    allowance = math.floor((summary.attending + remaining)
                           - ratio * projected_total)
    return Forecast(student_id=student_id, current_pct=summary.percentage,
                    sessions_so_far=summary.total,
                    sessions_remaining=remaining, projected_pct=projected,
                    headroom_sessions=max(0, int(allowance)),
                    target_pct=target)


def _academic_year_start(date: str) -> str:
    target = _dt.date.fromisoformat(date)
    year = target.year if target.month >= 9 else target.year - 1
    return f"{year}-09-01"


def forecast_cohort(*, group_id: int | None = None,
                    target_pct: float | None = None,
                    at_risk_only: bool = True) -> list[Forecast]:
    """Everybody's projection, those heading below target first."""
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    wanted: set[str] | None = None
    if group_id is not None:
        from education_system.systems.sixth_form.domain.academics.class_groups import (  # noqa: E501
            class_groups as _cg,
        )
        wanted = set(_cg.list_members(group_id))

    out: list[Forecast] = []
    for student in _students.list_students():
        if wanted is not None and student.student_id not in wanted:
            continue
        if getattr(student, "status", "Active") not in ("Active", None):
            continue
        projection = forecast(student.student_id, target_pct=target_pct)
        if at_risk_only and projection.will_meet_target is not False:
            continue
        out.append(projection)
    out.sort(key=lambda f: (f.projected_pct
                            if f.projected_pct is not None else 101))
    return out


# ── Benchmarking ────────────────────────────────────────────────────

def benchmark(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    group_id: int | None = None,
    year_group: int | None = None,
    scope: str | None = None,
) -> Benchmark:
    """This year against the same window last year, and against target.

    Same window, not same elapsed days: comparing September-to-March
    with a full previous year makes every college look like it is
    improving.
    """
    date_to = core._validate_date(date_to or _dt.date.today().isoformat())
    date_from = core._validate_date(date_from or _academic_year_start(date_to))
    previous_from = _shift_year(date_from)
    previous_to = _shift_year(date_to)

    current, learners = _window_percentage(date_from, date_to,
                                           group_id=group_id)
    previous, _ = _window_percentage(previous_from, previous_to,
                                     group_id=group_id)
    return Benchmark(
        scope=scope or (f"Group {group_id}" if group_id else "College"),
        current_pct=current, previous_pct=previous,
        target_pct=thresholds.value_of(thresholds.TARGET_ATTENDANCE,
                                       year_group=year_group, default=95.0),
        current_window=(date_from, date_to),
        previous_window=(previous_from, previous_to), learners=learners)


def _shift_year(date: str) -> str:
    target = _dt.date.fromisoformat(date)
    try:
        return target.replace(year=target.year - 1).isoformat()
    except ValueError:                      # 29 February
        return target.replace(year=target.year - 1, day=28).isoformat()


def _window_percentage(date_from: str, date_to: str, *,
                       group_id: int | None = None
                       ) -> tuple[float | None, int]:
    if group_id is not None:
        summary = core.summary_for_group(group_id, date_from=date_from,
                                         date_to=date_to)
        from education_system.systems.sixth_form.domain.academics.class_groups import (  # noqa: E501
            class_groups as _cg,
        )
        return summary.percentage, _cg.count_members(group_id)

    sessions = attending = 0
    learners: set[str] = set()
    for record in core.list_records(date_from=date_from, date_to=date_to):
        if not codes.counts_toward_possible(record.code):
            continue
        learners.add(record.student_id)
        sessions += 1
        if codes.counts_as_present(record.code) or \
                record.status in core.ATTENDING_STATUSES:
            attending += 1
    percentage = (round(100.0 * attending / sessions, 1) if sessions else None)
    return percentage, len(learners)


def benchmark_by_group(*, date_from: str | None = None,
                       date_to: str | None = None) -> list[Benchmark]:
    """Every teaching group against its own last year, worst change first."""
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    out = [benchmark(date_from=date_from, date_to=date_to,
                     group_id=group.group_id, scope=group.group_name)
           for group in _cg.list_groups()]
    out = [b for b in out if b.current_pct is not None]
    out.sort(key=lambda b: (b.change if b.change is not None else 0))
    return out


# ── Heatmap ─────────────────────────────────────────────────────────

def heatmap(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    group_id: int | None = None,
    student_id: str | None = None,
    window_days: int = 90,
) -> Heatmap:
    """Attendance by weekday and period.

    Friday period 6 is almost always the worst cell in the grid, and
    seeing it is the first step to doing something about it — which is
    usually a timetabling decision, not a pastoral one.
    """
    date_to = core._validate_date(date_to or _dt.date.today().isoformat())
    date_from = core._validate_date(
        date_from or (_dt.date.fromisoformat(date_to)
                      - _dt.timedelta(days=window_days)).isoformat())
    out = Heatmap(date_from=date_from, date_to=date_to)
    slots = {s.slot_id: s for s in tt.list_slots()}

    for record in core.list_records(student_id=student_id, group_id=group_id,
                                    date_from=date_from, date_to=date_to):
        slot = slots.get(record.slot_id)
        if slot is None or not codes.counts_toward_possible(record.code):
            continue
        weekday = _dt.date.fromisoformat(record.date).weekday() + 1
        key = (weekday, slot.period)
        cell = out.cells.setdefault(key, HeatCell(weekday=weekday,
                                                  period=slot.period))
        cell.sessions += 1
        if codes.counts_as_present(record.code) or \
                record.status in core.ATTENDING_STATUSES:
            cell.attending += 1
    return out


def weekday_profile(*, date_from: str | None = None,
                    date_to: str | None = None) -> dict[int, float | None]:
    """Attendance by day of the week — the Monday and Friday question."""
    grid = heatmap(date_from=date_from, date_to=date_to)
    tally: dict[int, HeatCell] = {}
    for cell in grid.cells.values():
        entry = tally.setdefault(cell.weekday,
                                 HeatCell(weekday=cell.weekday, period=0))
        entry.sessions += cell.sessions
        entry.attending += cell.attending
    return {day: cell.percentage for day, cell in sorted(tally.items())}


def period_profile(*, date_from: str | None = None,
                   date_to: str | None = None) -> dict[int, float | None]:
    """Attendance by period — the after-lunch question."""
    grid = heatmap(date_from=date_from, date_to=date_to)
    tally: dict[int, HeatCell] = {}
    for cell in grid.cells.values():
        entry = tally.setdefault(cell.period,
                                 HeatCell(weekday=0, period=cell.period))
        entry.sessions += cell.sessions
        entry.attending += cell.attending
    return {period: cell.percentage for period, cell in sorted(tally.items())}


# ── One-call summary ────────────────────────────────────────────────

def learner_insight(student_id: str) -> dict[str, Any]:
    """Everything this module can say about one learner.

    Assembled for a tutor about to have a conversation, so the useful
    facts arrive together rather than from five screens.
    """
    projection = forecast(student_id)
    subjects = subject_comparison(student_id)
    return {
        "student_id": student_id,
        "forecast": projection,
        "subjects": subjects,
        "worst_subject": subjects[0] if subjects else None,
        "is_single_subject_problem": bool(
            subjects and subjects[0].is_outlier
            and not any(s.is_outlier for s in subjects[1:])),
        "weekday_profile": weekday_profile(),
        "headroom": projection.headroom_sessions,
    }
