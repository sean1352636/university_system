"""Assessment commands — assignments, marking and results."""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.domain.teaching.assignments import (
    ASSIGNMENT_STATUSES,
    Assignment,
)
from education_system.systems.fe_college.domain.teaching.feedback import IV_OUTCOMES
from education_system.systems.fe_college.interfaces.cli import shell as sh


# ── Staff ───────────────────────────────────────────────────────────────────

def assignments(ctl) -> None:
    """Assignments this member of staff has set."""
    if not ctl.staff_id:
        sh.note("Your account is not linked to a staff record.")
        return

    sh.header("My assignments")
    items = ctl.assessment.list_assignments(set_by=ctl.staff_id)
    rows = []
    for a in items:
        detail = (
            ctl.assessment.assignment_detail(a.assignment_id)
            if a.status != "draft" else None
        )
        stats = detail.stats if detail else None
        rows.append({
            "title": a.title,
            "course": a.course_id,
            "unit": a.unit_id,
            "status": a.status,
            "due": a.due_date,
            "in": f"{stats.submitted}/{stats.expected}" if stats else sh.DASH,
            "marked": stats.marked if stats else sh.DASH,
            "missing": stats.missing if stats else sh.DASH,
        })
    sh.table(
        [("title", "Assignment"), ("course", "Course"), ("unit", "Unit"),
         ("status", "Status"), ("due", "Due"), ("in", "Handed in"),
         ("marked", "Marked"), ("missing", "Missing")],
        rows,
        empty="You have not set any assignments.",
    )


def create_assignment(ctl) -> None:
    """Draft a new assignment."""
    if not ctl.staff_id:
        sh.note("Your account is not linked to a staff record.")
        return
    courses = ctl.my_courses()
    if not courses:
        sh.note("You are not assigned to any courses.")
        return
    course = sh.choose_object(
        "Course", courses, lambda c: f"{c.course_id} — {c.title}"
    )
    if course is sh.CANCEL:
        return

    units = [u.unit_id for u in ctl.courses.units(course.course_id)]
    result = sh.form(f"New assignment on {course.course_id}", [
        ("title", "Title", "text"),
        ("unit_id", "Unit", "choice", units),
        ("status", "Status", "choice", ASSIGNMENT_STATUSES),
        ("issue_date", "Hand-out date", "date"),
        ("due_date", "Hand-in date", "date"),
        ("criteria", "Criteria (e.g. P1, P2, M1)", "text"),
        ("max_marks", "Maximum marks", "int"),
        ("brief", "Brief", "text"),
    ], initial={"status": "draft", "issue_date": date.today(),
                "due_date": date.today() + timedelta(weeks=3), "max_marks": 100})
    if result is sh.CANCEL:
        return

    try:
        created = ctl.assessment.create_assignment(Assignment(
            assignment_id=None,
            course_id=course.course_id,
            title=result["title"],
            unit_id=result["unit_id"],
            status=result["status"] or "draft",
            set_by=ctl.staff_id,
            issue_date=result["issue_date"],
            due_date=result["due_date"],
            criteria=result["criteria"],
            max_marks=result["max_marks"],
            brief=result["brief"],
        ))
    except ValidationError as exc:
        sh.error(str(exc))
        return

    sh.success(f"Created '{created.title}'")
    if created.status == "draft" and sh.confirm("Issue it to learners now?"):
        try:
            ctl.assessment.issue_assignment(created.assignment_id)
        except ValidationError as exc:
            sh.error(str(exc))
            return
        sh.success("Issued — hand-in tracking has started.")


def issue(ctl) -> None:
    """Issue a drafted assignment to learners."""
    if not ctl.staff_id:
        sh.note("Your account is not linked to a staff record.")
        return
    drafts = ctl.assessment.list_assignments(set_by=ctl.staff_id, status="draft")
    if not drafts:
        sh.note("You have no drafted assignments.")
        return
    assignment = sh.choose_object(
        "Assignment", drafts, lambda a: f"{a.course_id} · {a.title}"
    )
    if assignment is sh.CANCEL:
        return
    try:
        ctl.assessment.issue_assignment(assignment.assignment_id)
    except ValidationError as exc:
        sh.error(str(exc))
        return
    sh.success(f"Issued '{assignment.title}' to everyone on {assignment.course_id}")


def marking_queue(ctl) -> None:
    """Work waiting to be marked."""
    if not ctl.staff_id:
        sh.note("Your account is not linked to a staff record.")
        return

    sh.header("Marking queue", "Oldest first.")
    queue = ctl.assessment.marking_queue(ctl.staff_id)
    sh.table(
        [("student", "Learner"), ("assignment", "Assignment"),
         ("submitted", "Submitted"), ("late", "Late")],
        [
            {
                "student": row.student.full_name,
                "assignment": row.assignment.title,
                "submitted": row.submission.submitted_at,
                "late": row.is_late,
            }
            for row in queue
        ],
        empty="Nothing is waiting — the queue is clear.",
        limit=40,
    )


def mark(ctl) -> None:
    """Grade a piece of work from the queue."""
    if not ctl.staff_id:
        sh.note("Your account is not linked to a staff record.")
        return
    queue = ctl.assessment.marking_queue(ctl.staff_id)
    if not queue:
        sh.note("Nothing is waiting to be marked.")
        return

    row = sh.choose_object(
        "Which piece of work?", queue[:30],
        lambda r: f"{r.student.full_name} — {r.assignment.title}"
                  f"{'  (late)' if r.is_late else ''}",
    )
    if row is sh.CANCEL:
        return

    detail = ctl.assessment.assignment_detail(row.assignment.assignment_id)
    grades = list(detail.valid_grades) if detail else []
    if "Referred" not in grades:
        grades.append("Referred")

    sh.section(f"{row.student.full_name} — {row.assignment.title}")
    sh.key_values([
        ("Criteria", ", ".join(row.assignment.criteria_list) or sh.DASH),
        ("Maximum marks", row.assignment.max_marks),
        ("Submitted", row.submission.submitted_at),
        ("Resubmission", row.submission.is_resubmission),
    ])
    if row.submission.is_capped:
        sh.warn("This is a resubmission — awarding-body rules cap it at a Pass.")

    grade = sh.choose("Grade", grades)
    if grade is sh.CANCEL:
        return
    marks = sh.ask_int("Marks (blank for none)")
    if marks is sh.CANCEL:
        return
    feedback = sh.prompt("Feedback")
    if feedback is sh.CANCEL:
        return

    try:
        ctl.assessment.mark(
            row.assignment.assignment_id, row.student.student_id, grade,
            marked_by=ctl.staff_id, marks=marks or None, feedback_text=feedback,
        )
    except ValidationError as exc:
        sh.error(str(exc))
        return
    sh.success(f"{row.student.full_name}: {grade}")


def verify(ctl) -> None:
    """Internally verify someone else's marking."""
    if not ctl.staff_id:
        sh.note("Your account is not linked to a staff record.")
        return
    all_assignments = ctl.assessment.list_assignments()
    if not all_assignments:
        sh.note("There are no assignments to verify against.")
        return

    assignment = sh.choose_object(
        "Assignment", all_assignments[:40], lambda a: f"{a.course_id} · {a.title}"
    )
    if assignment is sh.CANCEL:
        return
    detail = ctl.assessment.assignment_detail(assignment.assignment_id)
    candidates = [
        r for r in (detail.rows if detail else [])
        if r.submission.grade and r.submission.marked_by != ctl.staff_id
    ]
    if not candidates:
        sh.note("Nothing marked by someone else on that assignment.")
        return

    row = sh.choose_object(
        "Whose work?", candidates,
        lambda r: f"{r.student.full_name} — {r.submission.grade} "
                  f"(marked by {r.submission.marked_by})",
    )
    if row is sh.CANCEL:
        return
    outcome = sh.choose("Outcome", list(IV_OUTCOMES))
    if outcome is sh.CANCEL:
        return
    comments = sh.prompt("Comments")
    if comments is sh.CANCEL:
        return

    try:
        ctl.assessment.verify(
            row.submission.submission_id, ctl.staff_id, outcome, comments
        )
    except ValidationError as exc:
        sh.error(str(exc))
        return
    sh.success(f"Verified {row.student.full_name}: {outcome}")


# ── Learner ─────────────────────────────────────────────────────────────────

def my_assignments(ctl) -> None:
    """A learner's own assignments."""
    if not ctl.student_id:
        sh.note("Your account is not linked to a learner record.")
        return

    sh.header("My assignments")
    items = [
        a for a in ctl.assessment.list_assignments(student_id=ctl.student_id)
        if a.status != "draft"
    ]
    submissions = {
        s.assignment_id: s for s in ctl.assessment.submissions_for(ctl.student_id)
    }
    sh.table(
        [("title", "Assignment"), ("course", "Course"), ("due", "Due"),
         ("days", "Days left"), ("status", "My status"), ("grade", "Grade")],
        [
            {
                "title": a.title,
                "course": a.course_id,
                "due": a.due_date,
                "days": a.days_remaining(),
                "status": (
                    submissions[a.assignment_id].status.replace("_", " ")
                    if a.assignment_id in submissions else "not handed in"
                ),
                "grade": (
                    submissions[a.assignment_id].grade
                    if a.assignment_id in submissions else None
                ),
            }
            for a in items
        ],
        empty="Nothing has been set on your courses.",
    )


def hand_in(ctl) -> None:
    """Record that a learner has handed work in."""
    if not ctl.student_id:
        sh.note("Your account is not linked to a learner record.")
        return

    submissions = {
        s.assignment_id: s for s in ctl.assessment.submissions_for(ctl.student_id)
    }
    outstanding = [
        a for a in ctl.assessment.list_assignments(student_id=ctl.student_id)
        if a.status == "issued"
        and (a.assignment_id not in submissions
             or submissions[a.assignment_id].status in ("not_submitted", "referred"))
    ]
    if not outstanding:
        sh.note("You have nothing outstanding.")
        return

    assignment = sh.choose_object(
        "Assignment", outstanding,
        lambda a: f"{a.course_id} · {a.title} (due {sh.fmt(a.due_date)})"
                  f"{'  OVERDUE' if a.is_overdue() else ''}",
    )
    if assignment is sh.CANCEL:
        return

    existing = submissions.get(assignment.assignment_id)
    if existing is not None and existing.status == "referred":
        sh.warn("This is a resubmission — it will be capped at a Pass.")
    elif assignment.is_overdue():
        sh.warn("This is past its hand-in date and will be recorded as late.")

    if not sh.confirm(f"Record that you have handed in '{assignment.title}'?"):
        return
    try:
        ctl.assessment.submit(assignment.assignment_id, ctl.student_id)
    except ValidationError as exc:
        sh.error(str(exc))
        return
    sh.success(f"Handed in: {assignment.title}")


def my_results(ctl) -> None:
    """A learner's grades and credit progress."""
    if not ctl.student_id:
        sh.note("Your account is not linked to a learner record.")
        return

    stats = ctl.reports.student_stats(ctl.student_id)
    sh.header("My results")
    sh.key_values([
        ("Grades awarded", stats.grades_awarded),
        ("Pass rate", sh.pct(stats.pass_rate)),
        ("Credits", f"{stats.credits_achieved} of {stats.credits_required}"),
    ])

    submissions = [s for s in ctl.assessment.submissions_for(ctl.student_id) if s.grade]
    assignments = {
        a.assignment_id: a
        for a in ctl.assessment.list_assignments(student_id=ctl.student_id)
    }
    sh.section("Coursework")
    sh.table(
        [("assignment", "Assignment"), ("course", "Course"), ("unit", "Unit"),
         ("grade", "Grade"), ("marks", "Marks"), ("marked", "Marked")],
        [
            {
                "assignment": assignments[s.assignment_id].title
                if s.assignment_id in assignments else f"#{s.assignment_id}",
                "course": assignments[s.assignment_id].course_id
                if s.assignment_id in assignments else None,
                "unit": assignments[s.assignment_id].unit_id
                if s.assignment_id in assignments else None,
                "grade": s.grade,
                "marks": s.marks,
                "marked": s.marked_at,
            }
            for s in submissions
        ],
        empty="Nothing of yours has been marked yet.",
    )

    profile = ctl.students.profile(ctl.student_id)
    if profile:
        sh.section("Credit progress")
        for enrolment in profile.enrolments:
            if not enrolment.is_active:
                continue
            progress = ctl.courses.learner_credit(ctl.student_id, enrolment.course_id)
            sh.key_values([
                (enrolment.course_id,
                 f"{progress.credits_achieved}/{progress.credits_required} credits "
                 f"({sh.pct(progress.pct)})"
                 + (f" · outstanding: {', '.join(progress.mandatory_outstanding)}"
                    if progress.mandatory_outstanding else " · all mandatory units passed")),
            ])

    results = ctl.assessment.results_for(ctl.student_id)
    if results:
        sh.section("Exam results")
        sh.table(
            [("unit", "Unit"), ("grade", "Grade"), ("marks", "Marks"),
             ("status", "Status"), ("released", "Released")],
            [
                {"unit": r.unit_id, "grade": r.grade, "marks": r.marks,
                 "status": r.status, "released": r.released_on}
                for r in results
            ],
        )


__all__ = [
    "assignments", "create_assignment", "hand_in", "issue", "mark",
    "marking_queue", "my_assignments", "my_results", "verify",
]
