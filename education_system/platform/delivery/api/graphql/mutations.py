"""GraphQL mutation resolvers for the education system.

Uses direct sqlite3 queries against each system's database.
Input types are defined here alongside the mutation functions.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

import strawberry

from .resolvers import _get_connection, _row_to_grade, _row_to_attendance, _row_to_enrollment
from .types import AttendanceType, EnrollmentType, GradeType, StudentType


# ---------------------------------------------------------------------------
# Input types
# ---------------------------------------------------------------------------

@strawberry.input
class StudentInput:
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    enrollment_date: Optional[str] = None
    major: Optional[str] = None
    status: Optional[str] = "active"


@strawberry.input
class GradeInput:
    student_id: str
    course_id: str
    assignment_name: Optional[str] = None
    score: Optional[float] = None
    max_score: Optional[float] = None
    letter_grade: Optional[str] = None
    grade_date: Optional[str] = None


@strawberry.input
class AttendanceInput:
    student_id: str
    course_id: Optional[str] = None
    date: Optional[str] = None
    status: str = "present"
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper: generate system-appropriate student ID
# ---------------------------------------------------------------------------

def _make_student_id(system: str) -> str:
    """Generate a new student/pupil ID appropriate to the system."""
    prefix_map = {
        "university": "UNI",
        "sixth_form": "COL",
        "secondary": "SCH",
        "primary": "PRI",
    }
    prefix = prefix_map.get(system.lower(), "STU")
    short = uuid.uuid4().hex[:6].upper()
    return f"{prefix}{short}"


def _now_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _today_str() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Student mutations
# ---------------------------------------------------------------------------

def resolve_create_student(system: str, input: StudentInput) -> StudentType:
    """Insert a new student record and return the created StudentType."""
    conn = _get_connection(system)
    try:
        c = conn.cursor()
        key = system.lower()
        student_id = _make_student_id(system)
        enrollment_date = input.enrollment_date or _today_str()
        now = _now_str()

        if key == "primary":
            c.execute(
                """INSERT INTO pupils
                   (pupil_id, first_name, last_name, date_of_birth, status,
                    admission_date, year_group, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    student_id, input.first_name, input.last_name,
                    input.date_of_birth, input.status or "active",
                    enrollment_date, input.major, now, now,
                ),
            )
            row_id = c.lastrowid
            conn.commit()
            row = c.execute(
                "SELECT * FROM pupils WHERE id = ?", (row_id,)
            ).fetchone()
        else:
            if key == "university":
                c.execute(
                    """INSERT INTO students
                       (student_id, first_name, last_name, email_address,
                        course, status, enrollment_date, registration_datetime)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        student_id, input.first_name, input.last_name,
                        input.email, input.major,
                        input.status or "active", enrollment_date, now,
                    ),
                )
            else:
                # college / school share the same schema
                c.execute(
                    """INSERT INTO students
                       (student_id, first_name, last_name, email, phone,
                        date_of_birth, major, status, enrollment_date,
                        created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        student_id, input.first_name, input.last_name,
                        input.email, input.phone, input.date_of_birth,
                        input.major, input.status or "active",
                        enrollment_date, now, now,
                    ),
                )
            row_id = c.lastrowid
            conn.commit()
            row = c.execute(
                "SELECT * FROM students WHERE id = ?", (row_id,)
            ).fetchone()

        from .resolvers import _row_to_student
        return _row_to_student(row, system)
    finally:
        conn.close()


def resolve_update_student(
    system: str, student_id: str, input: StudentInput
) -> StudentType:
    """Update an existing student record and return the updated StudentType."""
    conn = _get_connection(system)
    try:
        c = conn.cursor()
        key = system.lower()
        now = _now_str()

        if key == "primary":
            c.execute(
                """UPDATE pupils
                   SET first_name=?, last_name=?, date_of_birth=?,
                       year_group=?, status=?, updated_at=?
                   WHERE pupil_id=?""",
                (
                    input.first_name, input.last_name, input.date_of_birth,
                    input.major, input.status, now, student_id,
                ),
            )
            conn.commit()
            row = c.execute(
                "SELECT * FROM pupils WHERE pupil_id = ?", (student_id,)
            ).fetchone()
        elif key == "university":
            c.execute(
                """UPDATE students
                   SET first_name=?, last_name=?, email_address=?,
                       course=?, status=?
                   WHERE student_id=?""",
                (
                    input.first_name, input.last_name, input.email,
                    input.major, input.status, student_id,
                ),
            )
            conn.commit()
            row = c.execute(
                "SELECT * FROM students WHERE student_id = ?", (student_id,)
            ).fetchone()
        else:
            c.execute(
                """UPDATE students
                   SET first_name=?, last_name=?, email=?, phone=?,
                       date_of_birth=?, major=?, status=?, updated_at=?
                   WHERE student_id=?""",
                (
                    input.first_name, input.last_name, input.email,
                    input.phone, input.date_of_birth, input.major,
                    input.status, now, student_id,
                ),
            )
            conn.commit()
            row = c.execute(
                "SELECT * FROM students WHERE student_id = ?", (student_id,)
            ).fetchone()

        if row is None:
            raise ValueError(f"Student '{student_id}' not found in {system}")

        from .resolvers import _row_to_student
        return _row_to_student(row, system)
    finally:
        conn.close()


def resolve_delete_student(system: str, student_id: str) -> bool:
    """Delete a student record. Returns True on success."""
    conn = _get_connection(system)
    try:
        c = conn.cursor()
        key = system.lower()
        if key == "primary":
            c.execute("DELETE FROM pupils WHERE pupil_id = ?", (student_id,))
        else:
            c.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
        conn.commit()
        return c.rowcount > 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Enrollment mutations
# ---------------------------------------------------------------------------

def resolve_create_enrollment(
    system: str, student_id: str, course_id: str
) -> EnrollmentType:
    """Enroll a student in a course/subject."""
    conn = _get_connection(system)
    try:
        c = conn.cursor()
        key = system.lower()
        now = _now_str()

        if key == "primary":
            c.execute(
                """INSERT INTO lms_student_enrollment
                   (lms_course_id, student_id, enrolled_at)
                   VALUES (?, ?, ?)""",
                (course_id, student_id, now),
            )
            row_id = c.lastrowid
            conn.commit()
            row = c.execute(
                "SELECT * FROM lms_student_enrollment WHERE enrollment_id = ?",
                (row_id,),
            ).fetchone()
        elif key in ("secondary", "sixth_form"):
            cid_col = "subject_id" if key == "secondary" else "course_id"
            c.execute(
                f"""INSERT INTO enrollments
                    (student_id, {cid_col}, status, enrolled_at)
                    VALUES (?, ?, 'active', ?)""",
                (student_id, course_id, now),
            )
            row_id = c.lastrowid
            conn.commit()
            row = c.execute(
                "SELECT * FROM enrollments WHERE id = ?", (row_id,)
            ).fetchone()
        else:
            # university — insert into enrollments if table exists, else raise
            c.execute(
                """INSERT INTO enrollments
                   (student_id, course_id, enrollment_date, status)
                   VALUES (?, ?, ?, 'active')""",
                (student_id, course_id, now),
            )
            row_id = c.lastrowid
            conn.commit()
            row = c.execute(
                "SELECT * FROM enrollments WHERE id = ?", (row_id,)
            ).fetchone()

        return _row_to_enrollment(row)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Grade mutations
# ---------------------------------------------------------------------------

def resolve_record_grade(system: str, input: GradeInput) -> GradeType:
    """Insert a grade record and return the created GradeType."""
    conn = _get_connection(system)
    try:
        c = conn.cursor()
        key = system.lower()
        grade_date = input.grade_date or _today_str()

        if key == "primary":
            c.execute(
                """INSERT INTO assessments
                   (pupil_id, subject_code, score, max_score,
                    assessment_type, assessment_date, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    input.student_id, input.course_id,
                    input.score, input.max_score,
                    input.assignment_name, grade_date, _now_str(),
                ),
            )
            row_id = c.lastrowid
            conn.commit()
            row = c.execute(
                "SELECT * FROM assessments WHERE id = ?", (row_id,)
            ).fetchone()
        elif key == "secondary":
            c.execute(
                """INSERT INTO grades
                   (student_id, subject_id, assessment_name, score, grade,
                    assessment_type, graded_at, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    input.student_id, input.course_id,
                    input.assignment_name, input.score,
                    input.letter_grade, input.assignment_name,
                    grade_date, _now_str(),
                ),
            )
            row_id = c.lastrowid
            conn.commit()
            row = c.execute(
                "SELECT * FROM grades WHERE id = ?", (row_id,)
            ).fetchone()
        elif key == "sixth_form":
            c.execute(
                """INSERT INTO grades
                   (student_id, course_id, score, letter_grade,
                    grade_type, recorded_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    input.student_id, input.course_id,
                    input.score, input.letter_grade,
                    input.assignment_name, _now_str(), _now_str(),
                ),
            )
            row_id = c.lastrowid
            conn.commit()
            row = c.execute(
                "SELECT * FROM grades WHERE id = ?", (row_id,)
            ).fetchone()
        else:
            # university — grades tied to assessment_id; use a simple insert
            c.execute(
                """INSERT INTO grades
                   (student_id, score, letter_grade, submission_date)
                   VALUES (?, ?, ?, ?)""",
                (
                    input.student_id, input.score,
                    input.letter_grade, grade_date,
                ),
            )
            row_id = c.lastrowid
            conn.commit()
            row = c.execute(
                "SELECT * FROM grades WHERE grade_id = ?", (row_id,)
            ).fetchone()

        return _row_to_grade(row, system)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Attendance mutations
# ---------------------------------------------------------------------------

def resolve_record_attendance(system: str, input: AttendanceInput) -> AttendanceType:
    """Insert an attendance record and return the created AttendanceType."""
    conn = _get_connection(system)
    try:
        c = conn.cursor()
        key = system.lower()
        att_date = input.date or _today_str()
        now = _now_str()

        if key == "primary":
            c.execute(
                """INSERT INTO attendance_records
                   (pupil_id, date, status, note, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (input.student_id, att_date, input.status, input.notes, now),
            )
            row_id = c.lastrowid
            conn.commit()
            row = c.execute(
                "SELECT * FROM attendance_records WHERE id = ?", (row_id,)
            ).fetchone()
        elif key == "secondary":
            c.execute(
                """INSERT INTO attendance_records
                   (student_id, subject_id, date, status, note, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    input.student_id, input.course_id,
                    att_date, input.status, input.notes, now,
                ),
            )
            row_id = c.lastrowid
            conn.commit()
            row = c.execute(
                "SELECT * FROM attendance_records WHERE id = ?", (row_id,)
            ).fetchone()
        elif key == "sixth_form":
            c.execute(
                """INSERT INTO attendance
                   (student_id, course_id, date, status, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (input.student_id, input.course_id, att_date, input.status, input.notes),
            )
            row_id = c.lastrowid
            conn.commit()
            row = c.execute(
                "SELECT * FROM attendance WHERE id = ?", (row_id,)
            ).fetchone()
        else:
            # university
            c.execute(
                """INSERT INTO attendance
                   (student_id, module_code, date, status, reason)
                   VALUES (?, ?, ?, ?, ?)""",
                (input.student_id, input.course_id, att_date, input.status, input.notes),
            )
            row_id = c.lastrowid
            conn.commit()
            row = c.execute(
                "SELECT * FROM attendance WHERE id = ?", (row_id,)
            ).fetchone()

        return _row_to_attendance(row, system)
    finally:
        conn.close()
