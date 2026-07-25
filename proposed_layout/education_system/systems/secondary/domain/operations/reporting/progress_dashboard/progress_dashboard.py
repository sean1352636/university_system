"""Progress Dashboard aggregation layer for the Secondary School System.

Read-only dashboard that pulls from `progress` (reviews + targets) and
`students` to assemble a cohort-wide picture: per-student rows showing
latest review, attendance %, open/met/missed targets and risk; plus
cohort distributions (risk, overall rating, status) and lists of
students needing attention (high risk, overdue targets, no review).

No DB of its own — it is a derived view.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date as _date
from typing import Any

from education_system.systems.secondary.domain.operations.reporting.progress import progress
from education_system.systems.secondary.domain.pastoral import _pupils_bridge as students

logger = logging.getLogger(__name__)


@dataclass
class StudentRow:
    student_id: str
    full_name: str
    latest_review_id: int | None
    latest_period: str | None
    latest_date: str | None
    overall: str | None
    risk: str | None
    status: str | None
    attendance_pct: float | None
    open_targets: int
    met_targets: int
    missed_targets: int
    overdue_targets: int

    @property
    def has_review(self) -> bool:
        return self.latest_review_id is not None

    @property
    def needs_attention(self) -> bool:
        if self.risk in ("High", "Critical"):
            return True
        if self.overdue_targets:
            return True
        if not self.has_review:
            return True
        return False


@dataclass
class Dashboard:
    generated_on: str
    total_students: int
    reviewed_students: int
    unreviewed_students: int
    high_risk_students: int
    overdue_target_students: int
    by_risk: dict[str, int]
    by_overall: dict[str, int]
    by_status: dict[str, int]
    rows: list[StudentRow]
    summary: progress.Summary

    @property
    def review_coverage_pct(self) -> float | None:
        if self.total_students == 0:
            return None
        return round(100.0 * self.reviewed_students / self.total_students, 1)


def _latest_review(reviews: list[progress.Review]) -> progress.Review | None:
    if not reviews:
        return None
    # list_reviews already returns DESC by date — defensive resort.
    return sorted(reviews,
                   key=lambda r: (r.review_date, r.review_id),
                   reverse=True)[0]


def build_dashboard(
    *,
    risk_filter: str | None = None,
    only_unreviewed: bool = False,
    only_overdue: bool = False,
) -> Dashboard:
    """Assemble the full dashboard. Filters are applied to ``rows``
    after row construction — the cohort-wide counters always reflect
    the full student body."""
    today = _date.today().isoformat()
    progress.init_db()

    all_students = students.list_students()
    all_reviews = progress.list_reviews()
    all_targets = progress.list_targets()

    reviews_by_student: dict[str, list[progress.Review]] = {}
    for r in all_reviews:
        reviews_by_student.setdefault(r.student_id, []).append(r)

    review_to_student: dict[int, str] = {r.review_id: r.student_id
                                            for r in all_reviews}
    targets_by_student: dict[str, list[progress.Target]] = {}
    for t in all_targets:
        sid = review_to_student.get(t.review_id)
        if sid is None:
            continue
        targets_by_student.setdefault(sid, []).append(t)

    by_risk = {r: 0 for r in progress.RISK_LEVELS}
    by_overall = {r: 0 for r in progress.RATINGS}
    by_status = {s: 0 for s in progress.REVIEW_STATUSES}
    reviewed = high_risk = overdue_students = 0

    rows: list[StudentRow] = []
    for s in all_students:
        sid = s.student_id
        latest = _latest_review(reviews_by_student.get(sid, []))
        targets = targets_by_student.get(sid, [])
        open_n = sum(1 for t in targets if t.is_open)
        met_n = sum(1 for t in targets if t.status == "Met")
        missed_n = sum(1 for t in targets if t.status == "Missed")
        overdue_n = sum(1 for t in targets
                          if t.is_open and t.due_date and t.due_date < today)

        row = StudentRow(
            student_id=sid,
            full_name=s.full_name,
            latest_review_id=latest.review_id if latest else None,
            latest_period=latest.period if latest else None,
            latest_date=latest.review_date if latest else None,
            overall=latest.overall if latest else None,
            risk=latest.risk_level if latest else None,
            status=latest.status if latest else None,
            attendance_pct=latest.attendance_pct if latest else None,
            open_targets=open_n,
            met_targets=met_n,
            missed_targets=missed_n,
            overdue_targets=overdue_n,
        )

        if latest is not None:
            reviewed += 1
            by_risk[latest.risk_level] = by_risk.get(latest.risk_level, 0) + 1
            by_overall[latest.overall] = by_overall.get(latest.overall, 0) + 1
            by_status[latest.status] = by_status.get(latest.status, 0) + 1
            if latest.risk_level in ("High", "Critical"):
                high_risk += 1
        if overdue_n:
            overdue_students += 1

        rows.append(row)

    if risk_filter:
        rows = [r for r in rows if r.risk == risk_filter]
    if only_unreviewed:
        rows = [r for r in rows if not r.has_review]
    if only_overdue:
        rows = [r for r in rows if r.overdue_targets]

    rows.sort(key=lambda r: (
        # Critical/High first; then overdue count desc; then name.
        {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}.get(r.risk or "", 4),
        -r.overdue_targets,
        r.full_name,
    ))

    return Dashboard(
        generated_on=today,
        total_students=len(all_students),
        reviewed_students=reviewed,
        unreviewed_students=len(all_students) - reviewed,
        high_risk_students=high_risk,
        overdue_target_students=overdue_students,
        by_risk=by_risk,
        by_overall=by_overall,
        by_status=by_status,
        rows=rows,
        summary=progress.summary(),
    )


def students_at_risk() -> list[StudentRow]:
    """Convenience: rows where the latest review is High or Critical risk."""
    d = build_dashboard()
    return [r for r in d.rows if r.risk in ("High", "Critical")]


def students_without_review() -> list[StudentRow]:
    d = build_dashboard(only_unreviewed=True)
    return d.rows


def students_with_overdue_targets() -> list[StudentRow]:
    d = build_dashboard(only_overdue=True)
    return d.rows
