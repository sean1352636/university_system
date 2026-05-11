"""Grades reporting for the Sixth Form System.

Read-only reporting layer aggregating from three existing modules:

* ``predicted_grades``  — teacher-set A-Level predictions per
                           (student, subject)
* ``mock_exams``         — practice papers and per-student grades
* ``exam_results``       — board-awarded grades

A-Level grades use ``LETTER_GRADES`` from the gradebook
``("A*", "A", "B", "C", "D", "E", "U")``. We map each to a point
value so we can average and compare:

    A* → 6, A → 5, B → 4, C → 3, D → 2, E → 1, U → 0

Reports
-------
* ``cohort_grade_report``     — distribution + pass rates across all
                                 predicted, mock, and exam grades.
* ``per_student_grade_report``— each subject the student has data
                                 for, with predicted / latest mock /
                                 best exam grade side by side.
* ``per_subject_report``      — distribution + average grade points
                                 for one subject (split by source).
* ``compare_predicted_vs_actual`` — per-student delta in grade
                                 points (positive = beat prediction).
* ``alerts``                  — students with mock grades much lower
                                 than predictions, or below a target.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from education_system.sixthform_system.modules.domain.exam_results import exam_results
from education_system.sixthform_system.modules.domain.gradebook import gradebook
from education_system.sixthform_system.modules.domain.mock_exams import mock_exams
from education_system.sixthform_system.core import paths
from education_system.sixthform_system.modules.domain.predicted_grades import predicted_grades
from education_system.sixthform_system.modules.domain.students import students as _exam
from education_system.sixthform_system.modules.domain.gradebook import gradebook as _gb
from education_system.sixthform_system.modules.domain.mock_exams import mock_exams as _mocks
from education_system.sixthform_system.modules.domain.predicted_grades import predicted_grades as _pred
from education_system.sixthform_system.modules.domain.students import students as _students
logger = logging.getLogger(__name__)

LETTER_GRADES: tuple[str, ...] = _gb.LETTER_GRADES   # ("A*", ..., "U")
PASS_GRADES: tuple[str, ...] = ("A*", "A", "B", "C", "D", "E")
TOP_GRADES: tuple[str, ...] = ("A*", "A", "B", "C")  # commonly the "A*–C" rate

GRADE_POINTS: dict[str, int] = {
    "A*": 6, "A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "U": 0,
}

SOURCES: tuple[str, ...] = ("Predicted", "Mock", "Actual")


# ── Validation / helpers ───────────────────────────────────────────

class ValidationError(ValueError):
    pass


def init_db() -> None:
    _pred.init_db()
    _mocks.init_db()
    _exam.init_db()


def _grade_point(g: str | None) -> int | None:
    if g is None:
        return None
    return GRADE_POINTS.get(g)


def _avg_points(grades: list[str]) -> float | None:
    pts = [_grade_point(g) for g in grades
            if _grade_point(g) is not None]
    pts_clean = [p for p in pts if p is not None]
    if not pts_clean:
        return None
    return round(sum(pts_clean) / len(pts_clean), 2)


# ── Result types ───────────────────────────────────────────────────

@dataclass
class GradeDistribution:
    """Counts by letter grade. ``total`` is sum across the dict."""
    by_grade: dict[str, int] = field(
        default_factory=lambda: {g: 0 for g in LETTER_GRADES})

    @property
    def total(self) -> int:
        return sum(self.by_grade.values())

    @property
    def pass_count(self) -> int:
        return sum(self.by_grade.get(g, 0) for g in PASS_GRADES)

    @property
    def top_count(self) -> int:
        return sum(self.by_grade.get(g, 0) for g in TOP_GRADES)

    @property
    def pass_pct(self) -> float | None:
        if self.total == 0:
            return None
        return round(100.0 * self.pass_count / self.total, 1)

    @property
    def top_pct(self) -> float | None:
        if self.total == 0:
            return None
        return round(100.0 * self.top_count / self.total, 1)

    @property
    def average_points(self) -> float | None:
        if self.total == 0:
            return None
        pts = sum(GRADE_POINTS.get(g, 0) * n
                    for g, n in self.by_grade.items())
        return round(pts / self.total, 2)


@dataclass
class CohortReport:
    predicted: GradeDistribution
    mock: GradeDistribution
    actual: GradeDistribution
    predicted_subjects: int
    mock_papers: int
    actual_papers: int
    year_filter: int | None
    subject_filter: str | None


@dataclass
class SubjectRow:
    subject: str
    predicted_grade: str | None
    latest_mock_grade: str | None
    best_actual_grade: str | None
    delta_actual_vs_pred: int | None  # grade-point delta
    delta_mock_vs_pred: int | None


@dataclass
class StudentReport:
    student_id: str
    full_name: str
    subjects: list[SubjectRow]
    avg_predicted: float | None
    avg_mock: float | None
    avg_actual: float | None
    notes: list[str]


@dataclass
class SubjectReport:
    subject: str
    predicted: GradeDistribution
    mock: GradeDistribution
    actual: GradeDistribution
    top_predicted: list[tuple[str, str, str]]  # student_id, name, grade
    bottom_predicted: list[tuple[str, str, str]]


@dataclass
class PredVsActualRow:
    student_id: str
    full_name: str
    subject: str
    predicted_grade: str
    actual_grade: str
    delta: int  # actual_pts - pred_pts (positive = beat prediction)


@dataclass
class AlertRow:
    student_id: str
    full_name: str
    subject: str
    predicted: str | None
    latest_mock: str | None
    reasons: list[str] = field(default_factory=list)


# ── Internal aggregation ───────────────────────────────────────────

def _latest_mock_per_subject(student_id: str) -> dict[str, str]:
    """Return {subject: latest_grade} for a student across all mocks
    they sat. Mock results have a date on the parent mock; we trust
    list_mocks ordering (which is most-recent first per module's
    convention) and pick the first hit per subject. If module doesn't
    sort, we sort by mock id descending here."""
    from education_system.sixthform_system.modules.domain.mock_exams import mock_exams as _me
    init_db()
    out: dict[str, str] = {}
    mocks = sorted(_me.list_mocks(),
                    key=lambda m: m.mock_id, reverse=True)
    for m in mocks:
        if m.subject in out:
            continue
        rows = _me.list_results(mock_id=m.mock_id,
                                  student_id=student_id)
        if not rows:
            continue
        r = rows[0]
        eff = _me.effective_grade(r, m.max_marks)
        if eff:
            out[m.subject] = eff
    return out


def _best_actual_per_subject(student_id: str) -> dict[str, str]:
    """Return {subject: best (lowest-index) grade} across exam_results."""
    rows = _exam.list_results(student_id=student_id)
    out: dict[str, str] = {}
    for r in rows:
        g = r.result.grade
        if g not in LETTER_GRADES:
            continue
        prev = out.get(r.subject)
        if (prev is None or
                LETTER_GRADES.index(g) <
                LETTER_GRADES.index(prev)):
            out[r.subject] = g
    return out


# ── Cohort report ──────────────────────────────────────────────────

def cohort_grade_report(
    *,
    year: int | None = None,
    subject: str | None = None,
) -> CohortReport:
    init_db()

    pred_rows = _pred.list_predictions(subject=subject)
    pred_dist = GradeDistribution()
    for p in pred_rows:
        g = p.grade
        if g in LETTER_GRADES:
            pred_dist.by_grade[g] += 1

    mock_dist = GradeDistribution()
    from education_system.sixthform_system.modules.domain.mock_exams import mock_exams as _me
    mocks = _me.list_mocks(subject=subject)
    mock_papers = 0
    for m in mocks:
        results = _me.list_results(mock_id=m.mock_id)
        if not results:
            continue
        mock_papers += 1
        for r in results:
            eff = _me.effective_grade(r, m.max_marks)
            if eff in LETTER_GRADES:
                mock_dist.by_grade[eff] += 1

    actual_rows = _exam.list_results(subject=subject, year=year)
    actual_dist = GradeDistribution()
    for r in actual_rows:
        g = r.result.grade
        if g in LETTER_GRADES:
            actual_dist.by_grade[g] += 1

    return CohortReport(
        predicted=pred_dist, mock=mock_dist, actual=actual_dist,
        predicted_subjects=len(pred_rows),
        mock_papers=mock_papers,
        actual_papers=len(actual_rows),
        year_filter=year, subject_filter=subject,
    )


# ── Per-student report ─────────────────────────────────────────────

def per_student_grade_report(student_id: str) -> StudentReport:
    init_db()
    student = _students.get_student(student_id)
    if student is None:
        raise ValidationError(f"No student with id {student_id}")

    preds = _pred.list_predictions(student_id=student_id)
    pred_map = {p.subject: p.grade for p in preds}
    latest_mocks = _latest_mock_per_subject(student_id)
    best_actual = _best_actual_per_subject(student_id)

    subjects = sorted(
        set(pred_map) | set(latest_mocks) | set(best_actual))
    rows: list[SubjectRow] = []
    pred_pts: list[int] = []
    mock_pts: list[int] = []
    actual_pts: list[int] = []
    notes: list[str] = []

    for sub in subjects:
        p_grade = pred_map.get(sub)
        m_grade = latest_mocks.get(sub)
        a_grade = best_actual.get(sub)
        p_pt = _grade_point(p_grade)
        m_pt = _grade_point(m_grade)
        a_pt = _grade_point(a_grade)
        delta_actual = (a_pt - p_pt) if (a_pt is not None
                                            and p_pt is not None) else None
        delta_mock   = (m_pt - p_pt) if (m_pt is not None
                                            and p_pt is not None) else None
        rows.append(SubjectRow(
            subject=sub,
            predicted_grade=p_grade,
            latest_mock_grade=m_grade,
            best_actual_grade=a_grade,
            delta_actual_vs_pred=delta_actual,
            delta_mock_vs_pred=delta_mock,
        ))
        if p_pt is not None:
            pred_pts.append(p_pt)
        if m_pt is not None:
            mock_pts.append(m_pt)
        if a_pt is not None:
            actual_pts.append(a_pt)
        if delta_mock is not None and delta_mock <= -2:
            notes.append(f"{sub}: mock {m_grade} is "
                          f"{abs(delta_mock)} grades below "
                          f"prediction {p_grade}")
        if delta_actual is not None and delta_actual <= -1:
            notes.append(f"{sub}: actual {a_grade} below prediction "
                          f"{p_grade}")

    def _avg(pts: list[int]) -> float | None:
        return round(sum(pts) / len(pts), 2) if pts else None

    return StudentReport(
        student_id=student.student_id,
        full_name=student.full_name,
        subjects=rows,
        avg_predicted=_avg(pred_pts),
        avg_mock=_avg(mock_pts),
        avg_actual=_avg(actual_pts),
        notes=notes,
    )


# ── Per-subject report ─────────────────────────────────────────────

def per_subject_report(subject: str,
                          *, year: int | None = None,
                          top_n: int = 5) -> SubjectReport:
    init_db()
    if not subject or not subject.strip():
        raise ValidationError("subject is required")
    subject = subject.strip()

    # Predicted
    preds = _pred.list_predictions(subject=subject)
    pred_dist = GradeDistribution()
    pred_with_name: list[tuple[str, str, str, int]] = []
    name_map = {s.student_id: s.full_name
                 for s in _students.list_students()}
    for p in preds:
        if p.grade in LETTER_GRADES:
            pred_dist.by_grade[p.grade] += 1
            pred_with_name.append((
                p.student_id,
                name_map.get(p.student_id, p.student_id),
                p.grade,
                LETTER_GRADES.index(p.grade),
            ))

    # Mock
            from education_system.sixthform_system.modules.domain.mock_exams import mock_exams as _me
    mock_dist = GradeDistribution()
    for m in _me.list_mocks(subject=subject):
        results = _me.list_results(mock_id=m.mock_id)
        for r in results:
            eff = _me.effective_grade(r, m.max_marks)
            if eff in LETTER_GRADES:
                mock_dist.by_grade[eff] += 1

    # Actual
    actual_rows = _exam.list_results(subject=subject, year=year)
    actual_dist = GradeDistribution()
    for r in actual_rows:
        g = r.result.grade
        if g in LETTER_GRADES:
            actual_dist.by_grade[g] += 1

    pred_with_name.sort(key=lambda t: t[3])  # by grade index ascending
    top = [(sid, n, g) for sid, n, g, _ in pred_with_name[:top_n]]
    bottom = [(sid, n, g) for sid, n, g, _ in pred_with_name[-top_n:]]
    bottom.reverse()  # worst first

    return SubjectReport(
        subject=subject,
        predicted=pred_dist, mock=mock_dist, actual=actual_dist,
        top_predicted=top, bottom_predicted=bottom,
    )


# ── Predicted vs actual ────────────────────────────────────────────

def compare_predicted_vs_actual(
    *,
    year: int | None = None,
    subject: str | None = None,
) -> list[PredVsActualRow]:
    init_db()
    preds = _pred.list_predictions(subject=subject)
    pred_map: dict[tuple[str, str], str] = {
        (p.student_id, p.subject): p.grade for p in preds
        if p.grade in LETTER_GRADES
    }
    if not pred_map:
        return []

    actuals = _exam.list_results(subject=subject, year=year)
    # Group actuals by (student, subject) keeping best grade.
    best: dict[tuple[str, str], str] = {}
    for r in actuals:
        g = r.result.grade
        if g not in LETTER_GRADES:
            continue
        key = (r.student_id, r.subject)
        if (key not in best or
                LETTER_GRADES.index(g) <
                LETTER_GRADES.index(best[key])):
            best[key] = g

    name_map = {s.student_id: s.full_name
                 for s in _students.list_students()}

    out: list[PredVsActualRow] = []
    for key, p_grade in pred_map.items():
        a_grade = best.get(key)
        if a_grade is None:
            continue
        p_pt = _grade_point(p_grade)
        a_pt = _grade_point(a_grade)
        if p_pt is None or a_pt is None:
            continue
        sid, sub = key
        out.append(PredVsActualRow(
            student_id=sid,
            full_name=name_map.get(sid, sid),
            subject=sub,
            predicted_grade=p_grade,
            actual_grade=a_grade,
            delta=a_pt - p_pt,
        ))
    out.sort(key=lambda r: (r.delta, r.subject, r.full_name.lower()))
    return out


# ── Alerts ─────────────────────────────────────────────────────────

def alerts(
    *,
    mock_below_pred_by: int = 2,
    min_target_pred_points: int | None = None,
) -> list[AlertRow]:
    """Return students whose latest mock is at least `mock_below_pred_by`
    grade points below their prediction, or whose prediction itself
    is below `min_target_pred_points`."""
    init_db()
    preds = _pred.list_predictions()
    name_map = {s.student_id: s.full_name
                 for s in _students.list_students()}

    # Group preds by student to fetch latest mocks once per student.
    by_student: dict[str, list] = {}
    for p in preds:
        by_student.setdefault(p.student_id, []).append(p)

    out: list[AlertRow] = []
    for sid, plist in by_student.items():
        latest = _latest_mock_per_subject(sid)
        for p in plist:
            reasons: list[str] = []
            p_pt = _grade_point(p.grade)
            m_grade = latest.get(p.subject)
            m_pt = _grade_point(m_grade)
            if (p_pt is not None and m_pt is not None
                    and (p_pt - m_pt) >= mock_below_pred_by):
                reasons.append(
                    f"mock {m_grade} is "
                    f"{p_pt - m_pt} grade(s) below "
                    f"prediction {p.grade}")
            if (min_target_pred_points is not None
                    and p_pt is not None
                    and p_pt < min_target_pred_points):
                reasons.append(
                    f"predicted {p.grade} below target "
                    f"({min_target_pred_points} pts = "
                    f"{_grade_for_points(min_target_pred_points)})")
            if reasons:
                out.append(AlertRow(
                    student_id=sid,
                    full_name=name_map.get(sid, sid),
                    subject=p.subject,
                    predicted=p.grade,
                    latest_mock=m_grade,
                    reasons=reasons,
                ))
    out.sort(key=lambda a: (a.full_name.lower(), a.subject))
    return out


def _grade_for_points(pts: int) -> str:
    """Find the highest grade whose point value is <= pts."""
    for g in LETTER_GRADES:
        if GRADE_POINTS.get(g, 0) <= pts:
            return g
    return "U"
