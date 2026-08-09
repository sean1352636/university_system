"""Reporting: the dashboards and the exports that come off them.

Every figure a screen shows comes from here rather than being computed in a
view, so the admin dashboard, the CLI report and any CSV export of the same
measure can never disagree.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date

from education_system.systems.fe_college.config import (
    ACADEMIC_YEAR,
    ATTENDANCE_AT_RISK_PCT,
    ATTENDANCE_TARGET_PCT,
    COLLEGE_NAME,
)
from education_system.systems.fe_college.domain.finance.funding import (
    band_for_hours,
    earned_income,
)
from education_system.systems.fe_college.domain.students.attendance import (
    AttendanceSummary,
)
from education_system.systems.fe_college.infrastructure.persistence import session
from education_system.systems.fe_college.infrastructure.persistence.repositories import (
    assessment_repository as assessment_repo,
    attendance_repository as attendance_repo,
    course_repository as course_repo,
    finance_repository as finance_repo,
    pastoral_repository as pastoral_repo,
    staff_repository as staff_repo,
    student_repository as student_repo,
)


@dataclass(frozen=True)
class CollegeStats:
    """The headline numbers on the admin dashboard."""

    learners_on_roll: int = 0
    applicants: int = 0
    staff_total: int = 0
    teaching_staff: int = 0
    courses_running: int = 0
    courses_at_risk: int = 0
    attendance: AttendanceSummary = field(default_factory=AttendanceSummary)
    learners_at_risk: int = 0
    open_referrals: int = 0
    safeguarding_open: int = 0
    marking_outstanding: int = 0
    fees_outstanding: float = 0.0
    fees_charged: float = 0.0
    bursary_awarded: float = 0.0
    tutorials_overdue: int = 0

    @property
    def attendance_pct(self) -> float | None:
        return self.attendance.attendance_pct

    @property
    def attendance_band(self) -> str:
        return self.attendance.band

    @property
    def fees_collected_pct(self) -> float | None:
        if self.fees_charged <= 0:
            return None
        return round((self.fees_charged - self.fees_outstanding) / self.fees_charged * 100, 1)


@dataclass(frozen=True)
class StaffStats:
    """The headline numbers on a lecturer's dashboard."""

    staff_name: str = ""
    courses: int = 0
    groups: int = 0
    learners: int = 0
    sessions_per_week: int = 0
    marking_outstanding: int = 0
    assignments_open: int = 0
    attendance: AttendanceSummary = field(default_factory=AttendanceSummary)
    learners_at_risk: int = 0


@dataclass(frozen=True)
class StudentStats:
    """The headline numbers on a learner's own dashboard."""

    student_name: str = ""
    courses: int = 0
    attendance: AttendanceSummary = field(default_factory=AttendanceSummary)
    assignments_due: int = 0
    assignments_overdue: int = 0
    grades_awarded: int = 0
    pass_rate: float | None = None
    targets_open: int = 0
    balance: float = 0.0
    credits_achieved: int = 0
    credits_required: int = 0


# ── Dashboards ──────────────────────────────────────────────────────────────

def college_stats() -> CollegeStats:
    """Everything the admin dashboard shows, in one connection."""
    with session():
        by_status = student_repo.count_by_status()
        staff = staff_repo.list_staff(active_only=True)
        courses = course_repo.list_courses()
        attendance = attendance_repo.college_summary()
        per_student = attendance_repo.summaries_by_student()
        referrals = pastoral_repo.open_referral_counts()
        finance = finance_repo.outstanding_totals()
        bursaries = finance_repo.bursary_totals()
        marking = len(assessment_repo.list_submissions(awaiting_marking=True))
        last_tutorials = pastoral_repo.last_tutorial_dates()
        enrolled_ids = {s.student_id for s in student_repo.list_students(status="enrolled")}

    from education_system.systems.fe_college.domain.pastoral.tutorials import (
        is_tutorial_overdue,
    )

    running = [c for c in courses if c.status in ("recruiting", "running")]
    return CollegeStats(
        learners_on_roll=by_status.get("enrolled", 0),
        applicants=by_status.get("applicant", 0),
        staff_total=len(staff),
        teaching_staff=sum(1 for s in staff if s.can_teach),
        courses_running=len(running),
        courses_at_risk=sum(1 for c in running if c.viability == "at risk"),
        attendance=attendance,
        learners_at_risk=sum(
            1 for sid, s in per_student.items()
            if sid in enrolled_ids
            and s.attendance_pct is not None
            and s.attendance_pct < ATTENDANCE_AT_RISK_PCT
        ),
        open_referrals=sum(referrals.values()),
        safeguarding_open=referrals.get("Safeguarding", 0),
        marking_outstanding=marking,
        fees_outstanding=finance["outstanding"],
        fees_charged=finance["charged"],
        bursary_awarded=bursaries["awarded"],
        tutorials_overdue=sum(
            1 for sid in enrolled_ids if is_tutorial_overdue(last_tutorials.get(sid))
        ),
    )


def staff_stats(staff_id: str) -> StaffStats:
    """Everything a lecturer's dashboard shows."""
    with session():
        member = staff_repo.get(staff_id)
        groups = course_repo.list_groups(teacher_id=staff_id)
        led = course_repo.list_courses(course_leader=staff_id)
        sessions = len(
            [s for s in _sessions_for_staff(staff_id)]
        )
        queue = assessment_repo.marking_queue(staff_id)
        assignments = assessment_repo.list_assignments(set_by=staff_id, status="issued")

        course_ids = {c.course_id for c in led} | {g.course_id for g in groups}
        learners: set[str] = set()
        counts: dict[str, int] = {}
        at_risk = 0
        for course_id in course_ids:
            for learner in student_repo.list_students(course_id=course_id):
                learners.add(learner.student_id)
            summary = attendance_repo.summary_for_course(course_id)
            for mark in ("present", "late", "authorised", "unauthorised", "excused"):
                counts[mark] = counts.get(mark, 0) + getattr(summary, mark)
            per_student = attendance_repo.summaries_by_student(course_id=course_id)
            at_risk += sum(
                1 for s in per_student.values()
                if s.attendance_pct is not None and s.attendance_pct < ATTENDANCE_AT_RISK_PCT
            )

    from education_system.systems.fe_college.domain.students.attendance import (
        summary_from_counts,
    )

    return StaffStats(
        staff_name=member.full_name if member else staff_id,
        courses=len(course_ids),
        groups=len(groups),
        learners=len(learners),
        sessions_per_week=sessions,
        marking_outstanding=len(queue),
        assignments_open=len(assignments),
        attendance=summary_from_counts(counts),
        learners_at_risk=at_risk,
    )


def _sessions_for_staff(staff_id: str):
    from education_system.systems.fe_college.infrastructure.persistence.repositories import (
        timetable_repository,
    )
    return timetable_repository.list_sessions(teacher_id=staff_id)


def student_stats(student_id: str) -> StudentStats:
    """Everything a learner's own dashboard shows."""
    from education_system.systems.fe_college.domain.courses.modules import credit_progress
    from education_system.systems.fe_college.domain.students.grades import pass_rate

    with session():
        student = student_repo.get(student_id)
        enrolments = student_repo.list_enrolments(student_id=student_id, status="active")
        attendance = attendance_repo.summary_for_student(student_id)
        submissions = assessment_repo.list_submissions(student_id=student_id)
        assignments = {
            a.assignment_id: a
            for a in assessment_repo.list_assignments(student_id=student_id)
        }
        targets = student_repo.list_targets(student_id=student_id, open_only=True)
        balance = finance_repo.account_for(student_id).balance
        unit_grades = assessment_repo.grades_for_student(student_id)
        units = []
        for enrolment in enrolments:
            units.extend(course_repo.list_units(enrolment.course_id))

    outstanding = [
        s for s in submissions
        if s.status in ("not_submitted", "referred")
        and s.assignment_id in assignments
        and assignments[s.assignment_id].status == "issued"
    ]
    overdue = [
        s for s in outstanding
        if assignments[s.assignment_id].is_overdue()
    ]
    grades = [s.grade for s in submissions if s.grade]
    progress = credit_progress(units, unit_grades)

    return StudentStats(
        student_name=student.full_name if student else student_id,
        courses=len(enrolments),
        attendance=attendance,
        assignments_due=len(outstanding),
        assignments_overdue=len(overdue),
        grades_awarded=len(grades),
        pass_rate=pass_rate(grades),
        targets_open=len(targets),
        balance=balance,
        credits_achieved=progress.credits_achieved,
        credits_required=progress.credits_required,
    )


# ── Reports ─────────────────────────────────────────────────────────────────

def attendance_report(since: date | None = None) -> list[dict]:
    """Attendance by course, worst first."""
    from education_system.systems.fe_college.services import attendance_service

    return [
        {
            "course_id": cid,
            "title": title,
            "sessions": summary.total,
            "attendance_pct": summary.attendance_pct,
            "punctuality_pct": summary.punctuality_pct,
            "unauthorised": summary.unauthorised,
            "band": summary.band,
        }
        for cid, title, summary in attendance_service.by_course(since)
    ]


def achievement_report(academic_year: str = ACADEMIC_YEAR) -> list[dict]:
    """Retention and achievement by course."""
    from education_system.systems.fe_college.services import enrolment_service

    rows = []
    with session():
        courses = course_repo.list_courses(academic_year=academic_year)
    for course in courses:
        stats = enrolment_service.retention(course.course_id, academic_year)
        if not stats["starts"]:
            continue
        rows.append({
            "course_id": course.course_id,
            "title": course.title,
            "qualification": course.qualification_type,
            **stats,
        })
    return sorted(rows, key=lambda r: r["retention_pct"])


def viability_report(academic_year: str = ACADEMIC_YEAR) -> list[dict]:
    """Recruitment against capacity, worst first."""
    from education_system.systems.fe_college.services import course_service

    return [
        {
            "course_id": c.course_id,
            "title": c.title,
            "area": c.curriculum_area,
            "enrolled": c.enrolled,
            "capacity": c.capacity,
            "fill_pct": c.fill_pct,
            "viability": c.viability,
        }
        for c in course_service.viability_report(academic_year)
    ]


def funding_report(academic_year: str = ACADEMIC_YEAR) -> list[dict]:
    """Estimated funding earned per course, from retention and completion.

    An estimate, not the ESFA return: it applies the national band rates to
    this college's own retention, which is what a curriculum manager needs to
    see the financial cost of a drop-out.
    """
    from education_system.systems.fe_college.services import enrolment_service

    rows = []
    with session():
        courses = course_repo.list_courses(academic_year=academic_year)
    for course in courses:
        stats = enrolment_service.retention(course.course_id, academic_year)
        if not stats["starts"]:
            continue
        band = band_for_hours(course.guided_learning_hours)
        retained_income = stats["retained"] * earned_income(
            band, retained=True, completed=False
        )
        completed_income = stats["completed"] * earned_income(
            band, retained=True, completed=True
        ) - stats["completed"] * earned_income(band, retained=True, completed=False)
        rows.append({
            "course_id": course.course_id,
            "title": course.title,
            "band": band,
            "starts": stats["starts"],
            "retained": stats["retained"],
            "estimated_income": round(retained_income + completed_income, 2),
            "lost_to_withdrawal": round(
                (stats["starts"] - stats["retained"])
                * earned_income(band, retained=True, completed=False), 2
            ),
        })
    return sorted(rows, key=lambda r: r["estimated_income"], reverse=True)


def at_risk_report(threshold_pct: float = ATTENDANCE_AT_RISK_PCT) -> list[dict]:
    """Learners below the attendance threshold, with their tutor."""
    from education_system.systems.fe_college.services import attendance_service

    with session():
        rows = attendance_service.at_risk(threshold_pct)
        tutors = {s.staff_id: s.full_name for s in staff_repo.list_staff()}
    return [
        {
            "student_id": student.student_id,
            "name": student.full_name,
            "tutor_group": student.tutor_group,
            "personal_tutor": tutors.get(student.personal_tutor, student.personal_tutor),
            "attendance_pct": summary.attendance_pct,
            "unauthorised": summary.unauthorised,
            "band": summary.band,
        }
        for student, summary in rows
    ]


def workload_report(department: str | None = None) -> list[dict]:
    """Teaching hours assigned against contracted, per member of staff."""
    from education_system.systems.fe_college.services import staff_service

    return [
        {
            "staff_id": w.staff_id,
            "name": w.staff_name,
            "contracted": w.contracted_hours,
            "assigned": w.assigned_hours,
            "variance": w.variance,
            "utilisation_pct": w.utilisation_pct,
            "band": w.band,
        }
        for w in staff_service.workloads(department)
    ]


def finance_report() -> list[dict]:
    """Outstanding balance per learner, largest debt first."""
    with session():
        fees = finance_repo.list_fees(outstanding_only=True)
        learners = {s.student_id: s for s in student_repo.list_students()}

    per_student: dict[str, float] = {}
    overdue: dict[str, float] = {}
    for fee in fees:
        per_student[fee.student_id] = per_student.get(fee.student_id, 0.0) + fee.balance
        if fee.is_overdue():
            overdue[fee.student_id] = overdue.get(fee.student_id, 0.0) + fee.balance

    rows = [
        {
            "student_id": sid,
            "name": learners[sid].full_name if sid in learners else sid,
            "outstanding": round(balance, 2),
            "overdue": round(overdue.get(sid, 0.0), 2),
        }
        for sid, balance in per_student.items() if balance > 0
    ]
    return sorted(rows, key=lambda r: r["outstanding"], reverse=True)


# The report name the interfaces offer -> the function that builds it.
REPORTS = {
    "attendance": ("Attendance by course", attendance_report),
    "achievement": ("Retention & achievement", achievement_report),
    "viability": ("Course viability", viability_report),
    "funding": ("Estimated funding", funding_report),
    "at_risk": ("Learners at risk", at_risk_report),
    "workload": ("Staff workload", workload_report),
    "finance": ("Outstanding fees", finance_report),
}


def run(name: str, **kwargs) -> list[dict]:
    """Run a named report."""
    entry = REPORTS.get(name)
    if entry is None:
        raise ValueError(
            f"Unknown report '{name}' — expected one of {', '.join(sorted(REPORTS))}"
        )
    return entry[1](**kwargs)


def to_csv(rows: list[dict]) -> str:
    """Render report rows as CSV text.

    Returns an explanatory line rather than an empty string for an empty
    report, so an exported file is never a zero-byte puzzle.
    """
    if not rows:
        return "No data\n"
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def export(name: str, path=None, **kwargs):
    """Run a report and write it to ``path`` (default: the exports directory).

    Returns the path written.
    """
    from pathlib import Path

    from education_system.paths import FE_COLLEGE_EXPORTS_DIR, ensure_fe_college_directories

    rows = run(name, **kwargs)
    if path is None:
        ensure_fe_college_directories()
        path = FE_COLLEGE_EXPORTS_DIR / f"{name}_{date.today().isoformat()}.csv"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_csv(rows), encoding="utf-8")
    return path


def header() -> str:
    """The banner line the CLI reports print."""
    return f"{COLLEGE_NAME} — {ACADEMIC_YEAR}"


__all__ = [
    "REPORTS",
    "CollegeStats",
    "StaffStats",
    "StudentStats",
    "achievement_report",
    "at_risk_report",
    "attendance_report",
    "college_stats",
    "export",
    "finance_report",
    "funding_report",
    "header",
    "run",
    "staff_stats",
    "student_stats",
    "to_csv",
    "viability_report",
    "workload_report",
]
