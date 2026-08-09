"""Assessment persistence: assignments, submissions, feedback, exams and IV."""

from __future__ import annotations

import sqlite3
from datetime import date

from education_system.systems.fe_college.domain.exams.access_arrangements import (
    AccessArrangement,
)
from education_system.systems.fe_college.domain.exams.entries import ExamEntry
from education_system.systems.fe_college.domain.exams.models import ExamSeries, ExamSitting
from education_system.systems.fe_college.domain.exams.results import ExamResult
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.domain.teaching.assignments import Assignment
from education_system.systems.fe_college.domain.teaching.feedback import (
    Feedback,
    InternalVerification,
)
from education_system.systems.fe_college.domain.teaching.submissions import (
    Submission,
    SubmissionStats,
)
from education_system.systems.fe_college.infrastructure.persistence import (
    read_only,
    transaction,
)


# ── Assignments ─────────────────────────────────────────────────────────────

def get_assignment(assignment_id: int) -> Assignment | None:
    with read_only() as conn:
        row = conn.execute(
            "SELECT * FROM assignments WHERE assignment_id = ?", (assignment_id,)
        ).fetchone()
    return Assignment.from_row(row) if row else None


def list_assignments(
    *,
    course_id: str | None = None,
    set_by: str | None = None,
    group_id: str | None = None,
    status: str | None = None,
    student_id: str | None = None,
) -> list[Assignment]:
    """List assignments.

    ``student_id`` restricts to assignments on courses the learner is actively
    enrolled on — which is exactly the student portal's "my assignments".
    """
    sql = ["SELECT a.* FROM assignments a"]
    params: list = []
    if student_id:
        sql.append(
            "JOIN enrolments e ON e.course_id = a.course_id "
            "AND e.student_id = ? AND e.status = 'active'"
        )
        params.append(student_id)

    where: list[str] = []
    for column, value in (
        ("a.course_id", course_id),
        ("a.set_by", set_by),
        ("a.group_id", group_id),
        ("a.status", status),
    ):
        if value:
            where.append(f"{column} = ?")
            params.append(value)
    if where:
        sql.append("WHERE " + " AND ".join(where))
    sql.append("ORDER BY a.due_date IS NULL, a.due_date, a.assignment_id DESC")
    with read_only() as conn:
        rows = conn.execute(" ".join(sql), params).fetchall()
    return [Assignment.from_row(r) for r in rows]


def create_assignment(assignment: Assignment) -> Assignment:
    assignment.validate()
    row = assignment.to_row()
    placeholders = ", ".join("?" for _ in row)
    with transaction() as conn:
        cur = conn.execute(
            f"INSERT INTO assignments ({', '.join(row)}) VALUES ({placeholders})",
            list(row.values()),
        )
        assignment.assignment_id = cur.lastrowid
    return assignment


def update_assignment(assignment: Assignment) -> Assignment:
    if assignment.assignment_id is None:
        raise ValidationError("Cannot update an assignment without an ID")
    assignment.validate()
    row = assignment.to_row()
    assignments_sql = ", ".join(f"{col} = ?" for col in row)
    with transaction() as conn:
        conn.execute(
            f"UPDATE assignments SET {assignments_sql} WHERE assignment_id = ?",
            [*row.values(), assignment.assignment_id],
        )
    return assignment


def delete_assignment(assignment_id: int) -> bool:
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM assignments WHERE assignment_id = ?", (assignment_id,)
        )
        return cur.rowcount > 0


# ── Submissions ─────────────────────────────────────────────────────────────

def list_submissions(
    *,
    assignment_id: int | None = None,
    student_id: str | None = None,
    course_id: str | None = None,
    awaiting_marking: bool = False,
) -> list[Submission]:
    sql = ["SELECT s.* FROM submissions s"]
    params: list = []
    if course_id:
        sql.append("JOIN assignments a ON a.assignment_id = s.assignment_id AND a.course_id = ?")
        params.append(course_id)

    where: list[str] = []
    if assignment_id is not None:
        where.append("s.assignment_id = ?")
        params.append(assignment_id)
    if student_id:
        where.append("s.student_id = ?")
        params.append(student_id)
    if awaiting_marking:
        where.append(
            "s.status IN ('submitted', 'late', 'resubmitted') "
            "AND (s.grade IS NULL OR s.grade = '')"
        )
    if where:
        sql.append("WHERE " + " AND ".join(where))
    sql.append("ORDER BY s.submitted_at DESC, s.student_id")
    with read_only() as conn:
        rows = conn.execute(" ".join(sql), params).fetchall()
    return [Submission.from_row(r) for r in rows]


def get_submission(assignment_id: int, student_id: str) -> Submission | None:
    with read_only() as conn:
        row = conn.execute(
            "SELECT * FROM submissions WHERE assignment_id = ? AND student_id = ?",
            (assignment_id, student_id),
        ).fetchone()
    return Submission.from_row(row) if row else None


def save_submission(submission: Submission, max_marks: int | None = None) -> Submission:
    """Insert or update one submission (UPSERT on assignment + student)."""
    submission.validate(max_marks)
    row = submission.to_row()
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    updates = ", ".join(
        f"{c} = excluded.{c}" for c in row if c not in ("assignment_id", "student_id")
    )
    try:
        with transaction() as conn:
            conn.execute(
                f"INSERT INTO submissions ({columns}) VALUES ({placeholders}) "
                f"ON CONFLICT(assignment_id, student_id) DO UPDATE SET {updates}",
                list(row.values()),
            )
    except sqlite3.IntegrityError as exc:
        raise ValidationError(f"Could not save submission: {exc}") from exc
    return submission


def submission_stats(assignment_id: int) -> SubmissionStats:
    """Hand-in position for one assignment, in two queries.

    ``expected`` counts learners actively enrolled on the assignment's course,
    which is the honest denominator: a learner who withdrew in October should
    not depress a December submission rate.
    """
    with read_only() as conn:
        expected_row = conn.execute(
            "SELECT COUNT(*) FROM enrolments e "
            "JOIN assignments a ON a.course_id = e.course_id "
            "WHERE a.assignment_id = ? AND e.status = 'active'",
            (assignment_id,),
        ).fetchone()
        rows = conn.execute(
            "SELECT status, grade FROM submissions WHERE assignment_id = ?",
            (assignment_id,),
        ).fetchall()

    expected = expected_row[0] if expected_row else 0
    submitted = sum(
        1 for r in rows if r["status"] in ("submitted", "late", "marked", "resubmitted", "referred")
    )
    return SubmissionStats(
        expected=expected,
        submitted=submitted,
        late=sum(1 for r in rows if r["status"] == "late"),
        marked=sum(1 for r in rows if r["grade"]),
        referred=sum(1 for r in rows if r["status"] == "referred"),
        missing=max(0, expected - submitted),
    )


def grades_for_student(student_id: str) -> dict[str, str]:
    """Awarded grade per unit for a learner, for credit-progress arithmetic."""
    with read_only() as conn:
        rows = conn.execute(
            "SELECT a.unit_id, s.grade FROM submissions s "
            "JOIN assignments a ON a.assignment_id = s.assignment_id "
            "WHERE s.student_id = ? AND s.grade IS NOT NULL AND s.grade <> '' "
            "AND a.unit_id IS NOT NULL AND a.unit_id <> ''",
            (student_id,),
        ).fetchall()
    return {r["unit_id"]: r["grade"] for r in rows}


def marking_queue(staff_id: str) -> list[Submission]:
    """Unmarked submissions on assignments this member of staff set."""
    with read_only() as conn:
        rows = conn.execute(
            "SELECT s.* FROM submissions s "
            "JOIN assignments a ON a.assignment_id = s.assignment_id "
            "WHERE a.set_by = ? AND s.status IN ('submitted', 'late', 'resubmitted') "
            "AND (s.grade IS NULL OR s.grade = '') "
            "ORDER BY s.submitted_at",
            (staff_id,),
        ).fetchall()
    return [Submission.from_row(r) for r in rows]


# ── Feedback & internal verification ────────────────────────────────────────

def list_feedback(submission_id: int) -> list[Feedback]:
    with read_only() as conn:
        rows = conn.execute(
            "SELECT * FROM feedback WHERE submission_id = ? ORDER BY given_at DESC",
            (submission_id,),
        ).fetchall()
    return [Feedback.from_row(r) for r in rows]


def add_feedback(item: Feedback) -> Feedback:
    item.validate()
    row = item.to_row()
    placeholders = ", ".join("?" for _ in row)
    with transaction() as conn:
        cur = conn.execute(
            f"INSERT INTO feedback ({', '.join(row)}) VALUES ({placeholders})",
            list(row.values()),
        )
        item.feedback_id = cur.lastrowid
    return item


def add_verification(iv: InternalVerification) -> InternalVerification:
    iv.validate()
    row = iv.to_row()
    placeholders = ", ".join("?" for _ in row)
    with transaction() as conn:
        cur = conn.execute(
            f"INSERT INTO internal_verification ({', '.join(row)}) VALUES ({placeholders})",
            list(row.values()),
        )
        iv.iv_id = cur.lastrowid
    return iv


def verification_counts(staff_id: str) -> tuple[int, int]:
    """(marked, verified) counts for one assessor, for the sampling check."""
    with read_only() as conn:
        marked = conn.execute(
            "SELECT COUNT(*) FROM submissions WHERE marked_by = ? "
            "AND grade IS NOT NULL AND grade <> ''",
            (staff_id,),
        ).fetchone()[0]
        verified = conn.execute(
            "SELECT COUNT(DISTINCT v.submission_id) FROM internal_verification v "
            "JOIN submissions s ON s.submission_id = v.submission_id "
            "WHERE s.marked_by = ?",
            (staff_id,),
        ).fetchone()[0]
    return marked, verified


# ── Exams ───────────────────────────────────────────────────────────────────

def list_series(academic_year: str | None = None) -> list[ExamSeries]:
    sql = "SELECT * FROM exam_series"
    params: list = []
    if academic_year:
        sql += " WHERE academic_year = ?"
        params.append(academic_year)
    sql += " ORDER BY entry_deadline IS NULL, entry_deadline"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [ExamSeries.from_row(r) for r in rows]


def save_series(series: ExamSeries) -> ExamSeries:
    series.validate()
    row = series.to_row()
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    updates = ", ".join(f"{c} = excluded.{c}" for c in row if c != "series_id")
    with transaction() as conn:
        conn.execute(
            f"INSERT INTO exam_series ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(series_id) DO UPDATE SET {updates}",
            list(row.values()),
        )
    return series


_SITTING_SELECT = """
    SELECT s.*,
           (SELECT COUNT(*) FROM exam_entries e
             WHERE e.sitting_id = s.sitting_id
               AND e.status IN ('entered', 'late_entry')) AS entered
    FROM exam_sittings s
"""


def list_sittings(series_id: str | None = None) -> list[ExamSitting]:
    sql = _SITTING_SELECT
    params: list = []
    if series_id:
        sql += " WHERE s.series_id = ?"
        params.append(series_id)
    sql += " ORDER BY s.exam_date IS NULL, s.exam_date, s.start_time"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [ExamSitting.from_row(r) for r in rows]


def create_sitting(sitting: ExamSitting) -> ExamSitting:
    sitting.validate()
    row = sitting.to_row()
    placeholders = ", ".join("?" for _ in row)
    with transaction() as conn:
        cur = conn.execute(
            f"INSERT INTO exam_sittings ({', '.join(row)}) VALUES ({placeholders})",
            list(row.values()),
        )
        sitting.sitting_id = cur.lastrowid
    return sitting


def list_entries(*, sitting_id: int | None = None,
                 student_id: str | None = None) -> list[ExamEntry]:
    where, params = [], []
    if sitting_id is not None:
        where.append("sitting_id = ?")
        params.append(sitting_id)
    if student_id:
        where.append("student_id = ?")
        params.append(student_id)
    sql = "SELECT * FROM exam_entries"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY student_id"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [ExamEntry.from_row(r) for r in rows]


def add_entry(entry: ExamEntry) -> ExamEntry:
    entry.validate()
    row = entry.to_row()
    placeholders = ", ".join("?" for _ in row)
    try:
        with transaction() as conn:
            cur = conn.execute(
                f"INSERT INTO exam_entries ({', '.join(row)}) VALUES ({placeholders})",
                list(row.values()),
            )
            entry.entry_id = cur.lastrowid
    except sqlite3.IntegrityError as exc:
        # SQLite names the violated columns rather than the index.
        if "exam_entries.sitting_id" in str(exc) or "exam_entries.student_id" in str(exc):
            raise ValidationError(
                f"{entry.student_id} is already entered for this sitting"
            ) from exc
        raise ValidationError(f"Could not create exam entry: {exc}") from exc
    return entry


def list_results(*, student_id: str | None = None,
                 entry_id: int | None = None) -> list[ExamResult]:
    where, params = [], []
    if student_id:
        where.append("student_id = ?")
        params.append(student_id)
    if entry_id is not None:
        where.append("entry_id = ?")
        params.append(entry_id)
    sql = "SELECT * FROM exam_results"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY released_on DESC, unit_id"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [ExamResult.from_row(r) for r in rows]


def save_result(result: ExamResult) -> ExamResult:
    result.validate()
    row = result.to_row()
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    updates = ", ".join(f"{c} = excluded.{c}" for c in row if c != "entry_id")
    with transaction() as conn:
        conn.execute(
            f"INSERT INTO exam_results ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(entry_id) DO UPDATE SET {updates}",
            list(row.values()),
        )
    return result


# ── Access arrangements ─────────────────────────────────────────────────────

def list_arrangements(student_id: str | None = None,
                      approved_only: bool = False) -> list[AccessArrangement]:
    where, params = [], []
    if student_id:
        where.append("student_id = ?")
        params.append(student_id)
    if approved_only:
        where.append("status = 'approved'")
    sql = "SELECT * FROM access_arrangements"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY student_id, arrangement_type"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [AccessArrangement.from_row(r) for r in rows]


def save_arrangement(arrangement: AccessArrangement) -> AccessArrangement:
    arrangement.validate()
    row = arrangement.to_row()
    if arrangement.arrangement_id is None:
        placeholders = ", ".join("?" for _ in row)
        with transaction() as conn:
            cur = conn.execute(
                f"INSERT INTO access_arrangements ({', '.join(row)}) VALUES ({placeholders})",
                list(row.values()),
            )
            arrangement.arrangement_id = cur.lastrowid
    else:
        assignments = ", ".join(f"{col} = ?" for col in row)
        with transaction() as conn:
            conn.execute(
                f"UPDATE access_arrangements SET {assignments} WHERE arrangement_id = ?",
                [*row.values(), arrangement.arrangement_id],
            )
    return arrangement


__all__ = [
    "add_entry",
    "add_feedback",
    "add_verification",
    "create_assignment",
    "create_sitting",
    "delete_assignment",
    "get_assignment",
    "get_submission",
    "grades_for_student",
    "list_arrangements",
    "list_assignments",
    "list_entries",
    "list_feedback",
    "list_results",
    "list_series",
    "list_sittings",
    "list_submissions",
    "marking_queue",
    "save_arrangement",
    "save_result",
    "save_series",
    "save_submission",
    "submission_stats",
    "update_assignment",
    "verification_counts",
]
