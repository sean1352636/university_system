"""Assessment use cases: setting work, marking it, and exam entries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.domain.exams.entries import (
    ExamEntry,
    entry_fee,
)
from education_system.systems.fe_college.domain.exams.models import ExamSeries, ExamSitting
from education_system.systems.fe_college.domain.exams.results import ExamResult
from education_system.systems.fe_college.domain.students.grades import (
    GradeOutcome,
    grades_for,
    high_grade_rate,
    pass_rate,
    validate_grade,
)
from education_system.systems.fe_college.domain.students.models import (
    Student,
    ValidationError,
)
from education_system.systems.fe_college.domain.teaching.assignments import Assignment
from education_system.systems.fe_college.domain.teaching.feedback import (
    Feedback,
    InternalVerification,
)
from education_system.systems.fe_college.domain.teaching.submissions import (
    Submission,
    SubmissionStats,
)
from education_system.systems.fe_college.infrastructure.persistence import session
from education_system.systems.fe_college.infrastructure.persistence.repositories import (
    assessment_repository as repo,
    course_repository as course_repo,
    student_repository as student_repo,
)


@dataclass
class MarkingRow:
    """One line in the marking queue."""

    submission: Submission
    student: Student
    assignment: Assignment

    @property
    def is_late(self) -> bool:
        return self.submission.is_late(self.assignment.due_date)


@dataclass(frozen=True)
class AssignmentDetail:
    """An assignment with its hand-in position and marking rows."""

    assignment: Assignment
    stats: SubmissionStats
    rows: list[MarkingRow]
    valid_grades: tuple[str, ...]


# ── Assignments ─────────────────────────────────────────────────────────────

def list_assignments(**filters) -> list[Assignment]:
    return repo.list_assignments(**filters)


def get_assignment(assignment_id: int) -> Assignment | None:
    return repo.get_assignment(assignment_id)


def create_assignment(assignment: Assignment) -> Assignment:
    with session():
        if course_repo.get(assignment.course_id) is None:
            raise ValidationError(f"No course with code {assignment.course_id}")
        return repo.create_assignment(assignment)


def update_assignment(assignment: Assignment) -> Assignment:
    return repo.update_assignment(assignment)


def issue_assignment(assignment_id: int) -> Assignment:
    """Issue a draft assignment to learners.

    Creates a ``not_submitted`` row for every actively enrolled learner, so the
    hand-in position is visible from the moment it is issued rather than only
    once someone submits.
    """
    with session():
        assignment = repo.get_assignment(assignment_id)
        if assignment is None:
            raise ValidationError(f"No assignment with ID {assignment_id}")
        if assignment.due_date is None:
            raise ValidationError("Set a hand-in date before issuing the assignment")
        assignment.status = "issued"
        if assignment.issue_date is None:
            assignment.issue_date = date.today()
        repo.update_assignment(assignment)

        existing = {s.student_id for s in repo.list_submissions(assignment_id=assignment_id)}
        for learner in student_repo.list_students(course_id=assignment.course_id):
            if learner.student_id in existing:
                continue
            repo.save_submission(Submission(
                submission_id=None,
                assignment_id=assignment_id,
                student_id=learner.student_id,
                status="not_submitted",
            ), max_marks=assignment.max_marks)
        return assignment


def delete_assignment(assignment_id: int) -> bool:
    return repo.delete_assignment(assignment_id)


def assignment_detail(assignment_id: int) -> AssignmentDetail | None:
    """Everything the marking screen shows for one assignment."""
    with session():
        assignment = repo.get_assignment(assignment_id)
        if assignment is None:
            return None
        course = course_repo.get(assignment.course_id)
        submissions = repo.list_submissions(assignment_id=assignment_id)
        learners = {
            s.student_id: s
            for s in student_repo.list_students(course_id=assignment.course_id)
        }
        stats = repo.submission_stats(assignment_id)

    rows = [
        MarkingRow(submission=sub, student=learners[sub.student_id], assignment=assignment)
        for sub in submissions if sub.student_id in learners
    ]
    rows.sort(key=lambda r: (bool(r.submission.grade), r.student.last_name))
    return AssignmentDetail(
        assignment=assignment,
        stats=stats,
        rows=rows,
        valid_grades=grades_for(course.qualification_type) if course else (),
    )


# ── Submissions & marking ───────────────────────────────────────────────────

def submit(assignment_id: int, student_id: str, *,
           on: date | None = None, file_ref: str = "") -> Submission:
    """Record a learner handing work in, flagging it late where it is."""
    with session():
        assignment = repo.get_assignment(assignment_id)
        if assignment is None:
            raise ValidationError(f"No assignment with ID {assignment_id}")
        if assignment.status != "issued":
            raise ValidationError(
                f"{assignment.title} is {assignment.status} and is not accepting work"
            )
        submitted_on = on or date.today()
        existing = repo.get_submission(assignment_id, student_id)
        is_resubmission = bool(existing and existing.status == "referred")

        submission = Submission(
            submission_id=existing.submission_id if existing else None,
            assignment_id=assignment_id,
            student_id=student_id,
            status=(
                "resubmitted" if is_resubmission
                else ("late" if assignment.due_date and submitted_on > assignment.due_date
                      else "submitted")
            ),
            submitted_at=submitted_on,
            is_resubmission=is_resubmission,
            file_ref=file_ref,
        )
        return repo.save_submission(submission, max_marks=assignment.max_marks)


def mark(assignment_id: int, student_id: str, grade: str, *,
         marked_by: str, marks: int | None = None,
         feedback_text: str = "", on: date | None = None) -> Submission:
    """Award a grade against a submission.

    The grade is validated against the course's qualification scale, so a BTEC
    unit cannot be awarded a GCSE grade.
    """
    with session():
        assignment = repo.get_assignment(assignment_id)
        if assignment is None:
            raise ValidationError(f"No assignment with ID {assignment_id}")
        course = course_repo.get(assignment.course_id)
        if course is not None:
            validate_grade(grade, course.qualification_type)

        existing = repo.get_submission(assignment_id, student_id)
        if existing is None:
            raise ValidationError(f"{student_id} has no submission against this assignment")

        existing.grade = grade
        existing.marks = marks
        existing.marked_by = marked_by
        existing.marked_at = on or date.today()
        existing.status = "referred" if grade == "Referred" else "marked"
        if feedback_text:
            existing.feedback = feedback_text
        saved = repo.save_submission(existing, max_marks=assignment.max_marks)

        if feedback_text and saved.submission_id:
            repo.add_feedback(Feedback(
                feedback_id=None,
                submission_id=saved.submission_id,
                author_id=marked_by,
                body=feedback_text,
                feedback_type="Summative",
                given_at=on or date.today(),
            ))
        return saved


def marking_queue(staff_id: str) -> list[MarkingRow]:
    """Work waiting to be marked by one member of staff, oldest first."""
    with session():
        submissions = repo.marking_queue(staff_id)
        if not submissions:
            return []
        assignments = {
            a.assignment_id: a for a in repo.list_assignments(set_by=staff_id)
        }
        learners = {s.student_id: s for s in student_repo.list_students()}
    return [
        MarkingRow(
            submission=sub,
            student=learners[sub.student_id],
            assignment=assignments[sub.assignment_id],
        )
        for sub in submissions
        if sub.student_id in learners and sub.assignment_id in assignments
    ]


def submissions_for(student_id: str) -> list[Submission]:
    return repo.list_submissions(student_id=student_id)


def feedback_for(submission_id: int) -> list[Feedback]:
    return repo.list_feedback(submission_id)


def verify(submission_id: int, verifier_id: str, outcome: str,
           comments: str = "") -> InternalVerification:
    """Record an internal verification decision on a marked submission."""
    return repo.add_verification(InternalVerification(
        iv_id=None,
        submission_id=submission_id,
        verifier_id=verifier_id,
        outcome=outcome,
        comments=comments,
        verified_at=date.today(),
    ))


# ── Results & outcomes ──────────────────────────────────────────────────────

def outcomes_for(student_id: str) -> list[GradeOutcome]:
    """A learner's grade against target for every active course."""
    with session():
        enrolments = student_repo.list_enrolments(student_id=student_id, status="active")
        courses = {c.course_id: c for c in course_repo.list_courses()}
    return [
        GradeOutcome(
            student_id=student_id,
            course_id=e.course_id,
            qualification_type=(
                courses[e.course_id].qualification_type if e.course_id in courses else ""
            ),
            target_grade=e.predicted_grade,
            predicted_grade=e.predicted_grade,
            actual_grade=e.final_grade,
        )
        for e in enrolments
    ]


def course_results(course_id: str) -> dict[str, float | int | None]:
    """Pass rate and high-grade rate for a course, from its awarded grades."""
    with session():
        assignments = repo.list_assignments(course_id=course_id)
        grades: list[str] = []
        for assignment in assignments:
            grades.extend(
                s.grade for s in repo.list_submissions(assignment_id=assignment.assignment_id)
                if s.grade
            )
    return {
        "graded": len(grades),
        "pass_rate": pass_rate(grades),
        "high_grade_rate": high_grade_rate(grades),
    }


# ── Exams ───────────────────────────────────────────────────────────────────

def exam_series(academic_year: str | None = None) -> list[ExamSeries]:
    return repo.list_series(academic_year)


def save_series(series: ExamSeries) -> ExamSeries:
    return repo.save_series(series)


def sittings(series_id: str | None = None) -> list[ExamSitting]:
    return repo.list_sittings(series_id)


def create_sitting(sitting: ExamSitting) -> ExamSitting:
    return repo.create_sitting(sitting)


def enter_candidate(sitting_id: int, student_id: str, *,
                    base_fee: float = 0.0,
                    entry_type: str = "First entry",
                    on: date | None = None) -> ExamEntry:
    """Enter a learner for a sitting, applying the late fee where it is due."""
    entered_on = on or date.today()
    with session():
        sitting = next(
            (s for s in repo.list_sittings() if s.sitting_id == sitting_id), None
        )
        if sitting is None:
            raise ValidationError(f"No sitting with ID {sitting_id}")
        series = next(
            (s for s in repo.list_series() if s.series_id == sitting.series_id), None
        )
        if series is None:
            raise ValidationError(f"Sitting {sitting_id} has no exam series")
        if not series.accepts_entries(entered_on):
            raise ValidationError(
                f"{series.name} is not accepting entries (status: {series.status})"
            )
        if sitting.seats and sitting.entered >= sitting.seats:
            raise ValidationError(f"{sitting.label} is full ({sitting.seats} seats)")

        late = series.is_late_entry(entered_on)
        arrangements = repo.list_arrangements(student_id=student_id, approved_only=True)
        return repo.add_entry(ExamEntry(
            entry_id=None,
            sitting_id=sitting_id,
            student_id=student_id,
            status="late_entry" if late else "entered",
            entry_type=entry_type,
            entered_on=entered_on,
            fee=entry_fee(base_fee, is_late=late, is_resit=entry_type == "Resit"),
            access_arrangement_id=(
                arrangements[0].arrangement_id if arrangements else None
            ),
        ))


def entries(sitting_id: int | None = None,
            student_id: str | None = None) -> list[ExamEntry]:
    return repo.list_entries(sitting_id=sitting_id, student_id=student_id)


def results_for(student_id: str) -> list[ExamResult]:
    return repo.list_results(student_id=student_id)


def record_result(result: ExamResult) -> ExamResult:
    return repo.save_result(result)


def arrangements(student_id: str | None = None) -> list:
    return repo.list_arrangements(student_id=student_id)


def save_arrangement(arrangement) -> object:
    return repo.save_arrangement(arrangement)


def exam_duration(sitting: ExamSitting, student_id: str) -> int:
    """A sitting's duration for one candidate, with extra time applied."""
    from education_system.systems.fe_college.domain.exams.access_arrangements import (
        adjusted_duration,
    )

    approved = repo.list_arrangements(student_id=student_id, approved_only=True)
    return adjusted_duration(sitting.duration_minutes, approved)


__all__ = [
    "AssignmentDetail",
    "MarkingRow",
    "arrangements",
    "assignment_detail",
    "course_results",
    "create_assignment",
    "create_sitting",
    "delete_assignment",
    "enter_candidate",
    "entries",
    "exam_duration",
    "exam_series",
    "feedback_for",
    "get_assignment",
    "issue_assignment",
    "list_assignments",
    "mark",
    "marking_queue",
    "outcomes_for",
    "record_result",
    "results_for",
    "save_arrangement",
    "save_series",
    "sittings",
    "submissions_for",
    "submit",
    "update_assignment",
    "verify",
]
