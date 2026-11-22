"""Reading coursework: history, targets, trends, cohorts, grades.

Sibling to :mod:`assignments`. Everything here is read-only analysis
over marks that already exist:

* **Student history** — one timeline across every subject, which is
  the view a tutor actually wants and no single department has.
* **Target comparison** — actual against the target and predicted
  grades already held in ``target_setting`` and ``predicted_grades``,
  with an underperformance flag.
* **Trend tracking** — direction of travel over recent pieces, because
  a single mark says far less than the gradient.
* **Cohort analytics** — mark distribution, per-criterion weak spots,
  and subject/teacher comparison.
* **Non-submission** — students with repeated missing work, ranked so
  a pastoral referral is based on a pattern rather than one bad week.
* **Weighted subject grade** — what ``weight_percent`` was always for:
  a running grade built from the pieces done so far.

Nothing here writes. Every function is safe to call from a report, a
dashboard or a scheduled digest.
"""

from __future__ import annotations

import datetime as _dt
import logging
import statistics
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from education_system.systems.sixth_form.domain.academics.qualifications import (
    grade_scales as _gs,
)

from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments_marking as marking,
)
from education_system.systems.sixth_form.domain.academics.assignments import (
    models as assignments_models,
    store as assignments_store,
    submissions as assignments_submissions,
)

logger = logging.getLogger(__name__)

# No DB_PATH and no init_db here on purpose: this module owns no
# tables and never opens a connection of its own. It reads entirely
# through ``core`` and ``marking``, so pointing those at a database
# points this at the same one.

ValidationError = assignments_models.ValidationError


# ── Vocabularies ──────────────────────────────────────────────────

# A-Level grades in descending order, matching the gradebook and
# target-setting modules so a comparison means something.
GRADE_ORDER: tuple[str, ...] = ("A*", "A", "B", "C", "D", "E", "U")
_GRADE_POINTS: dict[str, int] = {
    "A*": 6, "A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "U": 0,
}

# How far below target counts as underperforming. One grade is noise —
# a bad week, a hard paper. Two is a pattern worth acting on.
UNDERPERFORMANCE_GRADES: int = 1
SERIOUS_UNDERPERFORMANCE_GRADES: int = 2

# Percentage-point change across a run of marks below which the trend
# is called flat rather than rising or falling.
TREND_FLAT_BAND: float = 3.0

# How many recent pieces a trend is computed over.
TREND_WINDOW: int = 5

# Missing pieces before a student appears on the non-submission
# dashboard at each level.
CONCERN_THRESHOLD: int = 2
REFERRAL_THRESHOLD: int = 4


# ── Dataclasses ───────────────────────────────────────────────────

@dataclass
class HistoryEntry:
    """One piece of coursework in a student's timeline."""

    assignment: assignments_models.Assignment
    submission: assignments_models.Submission

    @property
    def percent(self) -> float | None:
        if (self.submission.marks is None
                or not self.assignment.max_marks):
            return None
        return round(100.0 * self.submission.marks
                      / self.assignment.max_marks, 1)

    @property
    def due_date(self) -> str | None:
        return assignments_submissions.effective_due_date(self.submission, self.assignment)

    @property
    def is_missing(self) -> bool:
        return self.submission.status == "Missing"

    @property
    def state(self) -> str:
        if self.submission.marks is not None:
            return "Marked"
        if self.is_missing:
            return "Missing"
        if self.submission.is_done:
            return self.submission.status
        return "Outstanding"


@dataclass
class StudentHistory:
    student_id: str
    student_name: str = ""
    entries: list[HistoryEntry] = field(default_factory=list)

    @property
    def marked(self) -> list[HistoryEntry]:
        return [e for e in self.entries if e.percent is not None]

    @property
    def average_percent(self) -> float | None:
        scored = [e.percent for e in self.marked if e.percent is not None]
        if not scored:
            return None
        return round(sum(scored) / len(scored), 1)

    @property
    def missing_count(self) -> int:
        return sum(1 for e in self.entries if e.is_missing)

    @property
    def subjects(self) -> list[str]:
        return sorted({e.assignment.subject_name for e in self.entries})

    @property
    def message(self) -> str:
        if not self.entries:
            return "No coursework"
        bits = [f"{len(self.entries)} piece(s) across "
                f"{len(self.subjects)} subject(s)"]
        if self.average_percent is not None:
            bits.append(f"averaging {self.average_percent:g}%")
        if self.missing_count:
            bits.append(f"{self.missing_count} missing")
        return "; ".join(bits)


@dataclass
class TargetComparison:
    """Actual attainment against the target already on record."""

    student_id: str
    subject_name: str
    target_grade: str | None = None
    predicted_grade: str | None = None
    actual_grade: str | None = None
    actual_percent: float | None = None
    pieces: int = 0
    qualification_type: str | None = None

    @property
    def grades_below_target(self) -> int | None:
        """How many grades short of target, or None if not comparable.

        Counted on the subject's own scale (a BTEC Merit target against
        a Pass is one grade), A*-U when the type is unknown.
        """
        if not self.target_grade or not self.actual_grade:
            return None
        target = grade_points(self.target_grade, self.qualification_type)
        actual = grade_points(self.actual_grade, self.qualification_type)
        if target is None or actual is None:
            return None
        return max(0, target - actual)

    @property
    def is_underperforming(self) -> bool:
        gap = self.grades_below_target
        return gap is not None and gap >= UNDERPERFORMANCE_GRADES

    @property
    def is_serious(self) -> bool:
        gap = self.grades_below_target
        return gap is not None and gap >= SERIOUS_UNDERPERFORMANCE_GRADES

    @property
    def message(self) -> str:
        if not self.target_grade:
            return f"{self.subject_name}: no target set"
        if not self.actual_grade:
            return (f"{self.subject_name}: target {self.target_grade}, "
                    f"nothing marked yet")
        gap = self.grades_below_target
        if not gap:
            return (f"{self.subject_name}: {self.actual_grade} "
                    f"at or above target {self.target_grade}")
        word = "grade" if gap == 1 else "grades"
        return (f"{self.subject_name}: {self.actual_grade} is {gap} "
                f"{word} below target {self.target_grade}")


@dataclass
class Trend:
    """Direction of travel across a student's recent marks."""

    student_id: str
    subject_name: str | None = None
    percents: list[float] = field(default_factory=list)
    change: float = 0.0

    @property
    def sample(self) -> int:
        return len(self.percents)

    @property
    def direction(self) -> str:
        if self.sample < 2:
            return "Insufficient data"
        if abs(self.change) <= TREND_FLAT_BAND:
            return "Flat"
        return "Improving" if self.change > 0 else "Declining"

    @property
    def is_declining(self) -> bool:
        return self.direction == "Declining"

    @property
    def message(self) -> str:
        if self.sample < 2:
            return "Not enough marked work to show a trend"
        scope = self.subject_name or "all subjects"
        return (f"{scope}: {self.direction.lower()}, "
                f"{self.change:+g} points across {self.sample} piece(s)")


@dataclass
class Distribution:
    """Mark distribution for one assignment or cohort."""

    count: int = 0
    mean: float | None = None
    median: float | None = None
    lowest: float | None = None
    highest: float | None = None
    spread: float | None = None
    by_grade: dict[str, int] = field(default_factory=dict)
    # Scale the grade buckets are on (None = the college's A*-U letters).
    qualification_type: str | None = None

    @property
    def message(self) -> str:
        if not self.count:
            return "Nothing marked"
        return (f"{self.count} marked, mean {self.mean:g}%, "
                f"median {self.median:g}%, range {self.lowest:g}–"
                f"{self.highest:g}%")


@dataclass
class CriterionWeakness:
    """How a cohort performed on one rubric criterion."""

    criterion_id: int
    label: str
    max_marks: float
    scored: int = 0
    average: float | None = None

    @property
    def facility(self) -> float | None:
        if self.average is None or not self.max_marks:
            return None
        return round(100.0 * self.average / self.max_marks, 1)


@dataclass
class NonSubmitter:
    """A student's missing-work record."""

    student_id: str
    student_name: str
    missing: int = 0
    total: int = 0
    subjects: list[str] = field(default_factory=list)
    latest: str | None = None

    @property
    def rate(self) -> float:
        if not self.total:
            return 0.0
        return round(100.0 * self.missing / self.total, 1)

    @property
    def needs_referral(self) -> bool:
        return self.missing >= REFERRAL_THRESHOLD

    @property
    def level(self) -> str:
        if self.needs_referral:
            return "Referral"
        if self.missing >= CONCERN_THRESHOLD:
            return "Concern"
        return "Monitor"

    @property
    def message(self) -> str:
        return (f"{self.missing}/{self.total} missing ({self.rate:g}%) "
                f"across {len(self.subjects)} subject(s) — "
                f"{self.level.lower()}")


@dataclass
class WeightedGrade:
    """A running subject grade from the weighted pieces so far."""

    student_id: str
    subject_name: str
    percent: float | None = None
    grade: str | None = None
    weight_counted: float = 0.0
    weight_total: float = 0.0
    pieces: int = 0
    contributions: list[tuple[str, float, float]] = field(
        default_factory=list)
    qualification_type: str | None = None

    @property
    def is_complete(self) -> bool:
        return (self.weight_total > 0
                 and abs(self.weight_counted - self.weight_total) < 0.001)

    @property
    def message(self) -> str:
        if self.percent is None:
            return f"{self.subject_name}: nothing weighted yet"
        head = (f"{self.subject_name}: {self.percent:g}% "
                f"({self.grade}) from {self.pieces} piece(s)")
        if not self.is_complete:
            head += (f", {self.weight_counted:g}% of "
                     f"{self.weight_total:g}% weight marked")
        return head


# ── Helpers ───────────────────────────────────────────────────────

def _student_names() -> dict[str, str]:
    try:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        return {s.student_id: s.full_name
                for s in _students.list_students()}
    except Exception:
        logger.debug("Student names unavailable", exc_info=True)
        return {}


def percent_to_grade(percent: float | None,
                     qualification_type: str | None = None) -> str | None:
    """Working grade for a percentage on the subject's scale.

    A*-E letter scales use the college's own boundaries (marking
    defaults); BTEC, T Level, GCSE … use their grade_scales boundaries.
    """
    if _uses_letter_boundaries(qualification_type):
        return marking.pct_to_letter(percent)
    return _gs.percent_to_grade(percent, qualification_type)


def _uses_letter_boundaries(qualification_type: str | None) -> bool:
    try:
        return (_gs.scale_for(qualification_type).key
                in _gs.LETTER_BOUNDARY_SCALES)
    except ValueError:
        return True


def grade_points(grade: str | None,
                 qualification_type: str | None = None) -> int | None:
    """Points on the scale (A level = the old A*6..U0); None if off-scale."""
    if not grade:
        return None
    try:
        points = _gs.grade_points(grade, qualification_type)
    except ValueError:
        points = None
    return points if points is not None else _GRADE_POINTS.get(grade)


def grade_order(qualification_type: str | None = None) -> tuple[str, ...]:
    """Grade buckets best first for a scale (A*-U when unknown)."""
    if _uses_letter_boundaries(qualification_type):
        return GRADE_ORDER
    return _gs.grades_for(qualification_type)


@lru_cache(maxsize=2048)
def qualification_type_of(student_id: str | None,
                          subject_name: str | None) -> str | None:
    """Type a learner takes the subject as; with no learner, the
    subject catalogue's qualification. None = unknown (A*-U)."""
    if not subject_name:
        return None
    try:
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            learning_aims,
        )
        return learning_aims.qualification_type_for(student_id, subject_name)
    except Exception:
        logger.debug("Qualification type unavailable for %s / %s",
                     student_id, subject_name, exc_info=True)
        return None


def _sorted_history(entries: list[HistoryEntry]) -> list[HistoryEntry]:
    """Oldest first, by the date the work was actually assessed."""
    def key(e: HistoryEntry) -> str:
        return (e.submission.marked_on or e.due_date
                or e.assignment.set_date or "")
    return sorted(entries, key=key)


# ── Student history (item 43) ─────────────────────────────────────

def student_history(student_id: str, *,
                     subject_name: str | None = None,
                     include_unmarked: bool = True,
                     date_from: str | None = None,
                     date_to: str | None = None) -> StudentHistory:
    """One student's coursework across every subject, oldest first.

    The view a tutor wants and no single department has: three subjects
    each seeing one weak piece looks very different from one subject
    seeing three.
    """
    assignments_store.init_db()
    sid = str(student_id).strip()
    names = _student_names()
    out = StudentHistory(student_id=sid,
                          student_name=names.get(sid, sid))
    for sub in assignments_store.list_submissions(student_id=sid):
        a = assignments_store.get_assignment(sub.assignment_id)
        if a is None:
            continue
        if subject_name and a.subject_name != subject_name:
            continue
        if not include_unmarked and sub.marks is None:
            continue
        when = a.due_date or a.set_date
        if date_from and when and when < date_from:
            continue
        if date_to and when and when > date_to:
            continue
        out.entries.append(HistoryEntry(assignment=a, submission=sub))
    out.entries = _sorted_history(out.entries)
    return out


def subject_breakdown(student_id: str) -> dict[str, StudentHistory]:
    """A student's history split by subject."""
    whole = student_history(student_id)
    out: dict[str, StudentHistory] = {}
    for entry in whole.entries:
        subject = entry.assignment.subject_name
        bucket = out.setdefault(subject, StudentHistory(
            student_id=whole.student_id,
            student_name=whole.student_name))
        bucket.entries.append(entry)
    return dict(sorted(out.items()))


# ── Target comparison (item 44) ───────────────────────────────────

def _target_grade(student_id: str, subject_name: str) -> str | None:
    try:
        from education_system.systems.sixth_form.domain.assessment.target_setting import (
            target_setting as _targets,
        )
        target = _targets.get_target_for(student_id, subject_name)
        return target.mte_grade if target else None
    except Exception:
        logger.debug("Target unavailable for %s / %s",
                      student_id, subject_name, exc_info=True)
        return None


def _predicted_grade(student_id: str, subject_name: str) -> str | None:
    try:
        from education_system.systems.sixth_form.domain.assessment.predicted_grades import (
            predicted_grades as _predicted,
        )
        row = _predicted.get_for_student_subject(student_id,
                                                 subject_name)
        return row.grade if row else None
    except Exception:
        logger.debug("Prediction unavailable for %s / %s",
                      student_id, subject_name, exc_info=True)
        return None


def target_comparison(student_id: str,
                       subject_name: str) -> TargetComparison:
    """Coursework attainment against the target already on record.

    Reads ``target_setting`` and ``predicted_grades`` rather than
    holding its own targets — a second copy of a student's target is a
    second thing to be wrong.
    """
    assignments_store.init_db()
    sid = str(student_id).strip()
    history = student_history(sid, subject_name=subject_name)
    marked = history.marked
    out = TargetComparison(
        student_id=sid, subject_name=subject_name,
        target_grade=_target_grade(sid, subject_name),
        predicted_grade=_predicted_grade(sid, subject_name),
        pieces=len(marked),
        qualification_type=qualification_type_of(sid, subject_name))
    if marked:
        out.actual_percent = history.average_percent
        out.actual_grade = percent_to_grade(out.actual_percent,
                                            out.qualification_type)
    return out


def student_target_report(student_id: str) -> list[TargetComparison]:
    """Every subject this student has coursework in."""
    return [target_comparison(student_id, subject)
            for subject in student_history(student_id).subjects]


def underperformers(*, subject_name: str | None = None,
                     serious_only: bool = False
                     ) -> list[TargetComparison]:
    """Students whose coursework sits below their target.

    Ranked by the size of the gap, so intervention starts with the
    students furthest behind rather than the first alphabetically.
    """
    assignments_store.init_db()
    students: set[str] = set()
    for a in assignments_store.list_assignments(subject_name=subject_name):
        for sub in assignments_store.list_submissions(assignment_id=a.assignment_id):
            students.add(sub.student_id)
    out: list[TargetComparison] = []
    for sid in sorted(students):
        subjects = ([subject_name] if subject_name
                    else student_history(sid).subjects)
        for subject in subjects:
            comparison = target_comparison(sid, subject)
            if serious_only and not comparison.is_serious:
                continue
            if not serious_only and not comparison.is_underperforming:
                continue
            out.append(comparison)
    return sorted(out,
                   key=lambda c: -(c.grades_below_target or 0))


# ── Trend tracking (item 46) ──────────────────────────────────────

def student_trend(student_id: str, *,
                   subject_name: str | None = None,
                   window: int = TREND_WINDOW) -> Trend:
    """Direction of travel across the most recent marked pieces.

    Compares the first and second half of the window rather than
    fitting a line: with four or five data points a mean-of-halves is
    more honest about how little data there is.
    """
    history = student_history(str(student_id).strip(),
                               subject_name=subject_name)
    scored = [e.percent for e in history.marked
              if e.percent is not None][-max(2, window):]
    trend = Trend(student_id=history.student_id,
                   subject_name=subject_name, percents=scored)
    if len(scored) < 2:
        return trend
    half = len(scored) // 2
    earlier = scored[:half] or scored[:1]
    later = scored[-half:] or scored[-1:]
    trend.change = round(
        sum(later) / len(later) - sum(earlier) / len(earlier), 1)
    return trend


def declining_students(*, subject_name: str | None = None,
                        window: int = TREND_WINDOW
                        ) -> list[Trend]:
    """Everyone whose recent coursework is going the wrong way."""
    assignments_store.init_db()
    students: set[str] = set()
    for a in assignments_store.list_assignments(subject_name=subject_name):
        for sub in assignments_store.list_submissions(assignment_id=a.assignment_id):
            students.add(sub.student_id)
    out = [student_trend(sid, subject_name=subject_name, window=window)
           for sid in sorted(students)]
    return sorted((t for t in out if t.is_declining),
                   key=lambda t: t.change)


# ── Cohort analytics (item 45) ────────────────────────────────────

def _distribution(percents: list[float],
                  qualification_type: str | None = None) -> Distribution:
    if not percents:
        return Distribution(qualification_type=qualification_type)
    grades: dict[str, int] = {g: 0 for g in grade_order(qualification_type)}
    for p in percents:
        grade = percent_to_grade(p, qualification_type)
        if grade:
            grades[grade] = grades.get(grade, 0) + 1
    return Distribution(
        count=len(percents),
        mean=round(sum(percents) / len(percents), 1),
        median=round(statistics.median(percents), 1),
        lowest=round(min(percents), 1),
        highest=round(max(percents), 1),
        spread=round(max(percents) - min(percents), 1),
        by_grade={g: n for g, n in grades.items() if n},
        qualification_type=qualification_type,
    )


def assignment_distribution(assignment_id: int) -> Distribution:
    """Mark distribution for one assignment."""
    assignments_store.init_db()
    a = assignments_store.get_assignment(assignment_id)
    if a is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    if not a.max_marks:
        return Distribution()
    percents = [round(100.0 * s.marks / a.max_marks, 1)
                for s in assignments_store.list_submissions(
                    assignment_id=assignment_id)
                if s.marks is not None]
    return _distribution(percents, qualification_type_of(None, a.subject_name))


def cohort_distribution(*, subject_name: str | None = None,
                         year_group: str | None = None,
                         teacher: str | None = None) -> Distribution:
    """Mark distribution across many assignments."""
    assignments_store.init_db()
    percents: list[float] = []
    for a in assignments_store.list_assignments(subject_name=subject_name,
                                    year_group=year_group,
                                    teacher_like=teacher):
        if not a.max_marks:
            continue
        for sub in assignments_store.list_submissions(assignment_id=a.assignment_id):
            if sub.marks is not None:
                percents.append(round(100.0 * sub.marks
                                       / a.max_marks, 1))
    # One subject has one scale; across subjects the A*-U letters stand.
    return _distribution(percents, qualification_type_of(None, subject_name)
                         if subject_name else None)


def criterion_weaknesses(assignment_id: int
                          ) -> list[CriterionWeakness]:
    """Per-criterion performance, weakest first.

    A cohort that scores well overall but collapses on one assessment
    objective has a teaching gap the total mark hides.
    """
    assignments_store.init_db()
    out: list[CriterionWeakness] = []
    for criterion in marking.list_criteria(assignment_id):
        scores: list[float] = []
        for sub in assignments_store.list_submissions(assignment_id=assignment_id):
            for mark in marking.list_criterion_marks(sub.submission_id):
                if (mark.criterion_id == criterion.criterion_id
                        and mark.marks is not None):
                    scores.append(mark.marks)
        entry = CriterionWeakness(
            criterion_id=criterion.criterion_id,
            label=criterion.label, max_marks=criterion.max_marks,
            scored=len(scores))
        if scores:
            entry.average = round(sum(scores) / len(scores), 2)
        out.append(entry)
    return sorted(out, key=lambda c: (c.facility is None,
                                       c.facility or 0))


def compare_subjects(*, year_group: str | None = None
                      ) -> dict[str, Distribution]:
    """Mark distribution per subject, weakest mean first."""
    assignments_store.init_db()
    subjects = sorted({a.subject_name for a in
                       assignments_store.list_assignments(year_group=year_group)})
    out = {s: cohort_distribution(subject_name=s,
                                   year_group=year_group)
           for s in subjects}
    return dict(sorted(out.items(),
                        key=lambda kv: (kv[1].mean is None,
                                         kv[1].mean or 0)))


def compare_teachers(*, subject_name: str | None = None
                      ) -> dict[str, Distribution]:
    """Mark distribution per teacher.

    Presented without comment: a difference between two teachers'
    distributions has many innocent explanations (different sets,
    different pieces) and is a question to ask, not an answer.
    """
    assignments_store.init_db()
    buckets: dict[str, list[float]] = {}
    for a in assignments_store.list_assignments(subject_name=subject_name):
        if not a.max_marks:
            continue
        who = a.teacher or "(unassigned)"
        for sub in assignments_store.list_submissions(assignment_id=a.assignment_id):
            if sub.marks is not None:
                buckets.setdefault(who, []).append(
                    round(100.0 * sub.marks / a.max_marks, 1))
    qtype = qualification_type_of(None, subject_name) if subject_name else None
    out = {who: _distribution(values, qtype)
           for who, values in buckets.items()}
    return dict(sorted(out.items(),
                        key=lambda kv: -(kv[1].mean or 0)))


def cohort_summary(*, subject_name: str | None = None,
                    year_group: str | None = None) -> dict[str, Any]:
    """The headline numbers a head of department opens with."""
    assignments_store.init_db()
    assignments = assignments_store.list_assignments(subject_name=subject_name,
                                         year_group=year_group)
    total = marked = missing = 0
    for a in assignments:
        for sub in assignments_store.list_submissions(assignment_id=a.assignment_id):
            total += 1
            if sub.marks is not None:
                marked += 1
            if sub.status == "Missing":
                missing += 1
    distribution = cohort_distribution(subject_name=subject_name,
                                        year_group=year_group)
    return {
        "assignments": len(assignments),
        "submissions": total,
        "marked": marked,
        "missing": missing,
        "marked_percent": (round(100.0 * marked / total, 1)
                            if total else None),
        "distribution": distribution,
    }


# ── Non-submission dashboard (item 47) ────────────────────────────

def non_submitters(*, subject_name: str | None = None,
                    year_group: str | None = None,
                    minimum: int = CONCERN_THRESHOLD
                    ) -> list[NonSubmitter]:
    """Students with repeated missing work, worst first.

    A referral should rest on a pattern, so this counts across subjects
    and reports the rate as well as the raw number — two missing out of
    three is a very different conversation from two out of twenty.
    """
    assignments_store.init_db()
    names = _student_names()
    buckets: dict[str, NonSubmitter] = {}
    for a in assignments_store.list_assignments(subject_name=subject_name,
                                    year_group=year_group):
        for sub in assignments_store.list_submissions(assignment_id=a.assignment_id):
            entry = buckets.setdefault(sub.student_id, NonSubmitter(
                student_id=sub.student_id,
                student_name=names.get(sub.student_id,
                                        sub.student_id)))
            entry.total += 1
            if sub.status == "Missing":
                entry.missing += 1
                if a.subject_name not in entry.subjects:
                    entry.subjects.append(a.subject_name)
                due = assignments_submissions.effective_due_date(sub, a)
                if due and (entry.latest is None or due > entry.latest):
                    entry.latest = due
    out = [e for e in buckets.values() if e.missing >= minimum]
    return sorted(out, key=lambda e: (-e.missing, -e.rate))


def referral_candidates(**kwargs: Any) -> list[NonSubmitter]:
    """Only those over the referral threshold."""
    return [e for e in non_submitters(minimum=REFERRAL_THRESHOLD,
                                       **kwargs)
            if e.needs_referral]


def student_non_submission(student_id: str) -> NonSubmitter:
    """One student's missing-work record."""
    assignments_store.init_db()
    sid = str(student_id).strip()
    names = _student_names()
    entry = NonSubmitter(student_id=sid,
                          student_name=names.get(sid, sid))
    for sub in assignments_store.list_submissions(student_id=sid):
        a = assignments_store.get_assignment(sub.assignment_id)
        if a is None:
            continue
        entry.total += 1
        if sub.status == "Missing":
            entry.missing += 1
            if a.subject_name not in entry.subjects:
                entry.subjects.append(a.subject_name)
            due = assignments_submissions.effective_due_date(sub, a)
            if due and (entry.latest is None or due > entry.latest):
                entry.latest = due
    return entry


# ── Weighted subject grade (item 50) ──────────────────────────────

def weighted_grade(student_id: str, subject_name: str, *,
                    include_unmarked: bool = False) -> WeightedGrade:
    """A running subject grade from the weighted pieces so far.

    This is what ``weight_percent`` was always for. Only pieces
    carrying a weight count: a formative exercise with no weight should
    not move a student's subject grade.

    The result is rescaled to the weight actually marked, so a student
    halfway through the year sees where they stand rather than a figure
    dragged down by work not yet done.
    """
    assignments_store.init_db()
    sid = str(student_id).strip()
    out = WeightedGrade(student_id=sid, subject_name=subject_name)

    # The denominator is the subject's whole weighted scheme, not just
    # the pieces this student happens to be enrolled on. Otherwise a
    # student who has done one of four assessments reads as "complete"
    # simply because the other three were never assigned to them.
    out.weight_total = round(sum(
        a.weight_percent or 0
        for a in assignments_store.list_assignments(subject_name=subject_name)
        if a.weight_percent), 4)

    history = student_history(sid, subject_name=subject_name)
    for entry in history.entries:
        weight = entry.assignment.weight_percent
        if not weight:
            continue
        percent = entry.percent
        if percent is None:
            if include_unmarked:
                out.contributions.append(
                    (entry.assignment.title, weight, 0.0))
            continue
        out.weight_counted = round(out.weight_counted + weight, 4)
        out.pieces += 1
        out.contributions.append(
            (entry.assignment.title, weight, percent))
    if out.weight_counted > 0:
        scored = sum(w * p for _t, w, p in out.contributions
                     if p is not None)
        denominator = (out.weight_total if include_unmarked
                        else out.weight_counted)
        if denominator:
            out.percent = round(scored / denominator, 1)
            out.qualification_type = qualification_type_of(sid, subject_name)
            out.grade = percent_to_grade(out.percent,
                                         out.qualification_type)
    return out


def student_weighted_grades(student_id: str) -> list[WeightedGrade]:
    """Every subject this student carries weighted coursework in."""
    return [weighted_grade(student_id, subject)
            for subject in student_history(student_id).subjects]


def subject_weighted_grades(subject_name: str, *,
                             year_group: str | None = None
                             ) -> list[WeightedGrade]:
    """The whole set's running grades, highest first."""
    assignments_store.init_db()
    students: set[str] = set()
    for a in assignments_store.list_assignments(subject_name=subject_name,
                                    year_group=year_group):
        for sub in assignments_store.list_submissions(assignment_id=a.assignment_id):
            students.add(sub.student_id)
    out = [weighted_grade(sid, subject_name) for sid in sorted(students)]
    return sorted((g for g in out if g.percent is not None),
                   key=lambda g: -(g.percent or 0))


def weight_audit(subject_name: str, *,
                  year_group: str | None = None) -> dict[str, Any]:
    """Do a subject's weighted pieces add up to 100%?

    A department whose weights total 85% is not wrong exactly — the
    grade is rescaled — but it usually means a planned piece was never
    written, which is worth knowing before results day.
    """
    assignments_store.init_db()
    weighted = [a for a in assignments_store.list_assignments(
        subject_name=subject_name, year_group=year_group)
        if a.weight_percent]
    total = round(sum(a.weight_percent or 0 for a in weighted), 4)
    return {
        "subject_name": subject_name,
        "weighted_assignments": len(weighted),
        "total_weight": total,
        "balanced": abs(total - 100.0) < 0.001,
        "assignments": [(a.assignment_id, a.title, a.weight_percent)
                         for a in weighted],
    }
