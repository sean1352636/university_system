"""GraphQL query resolvers for the education system.

Each resolver connects directly to the appropriate system database via
sqlite3 (no service-layer imports), keeping the GraphQL layer self-contained.

Supported system keys are ``nursery``, ``primary``, ``secondary``,
``sixth_form`` and ``university``. Runtime databases are resolved through the
canonical ``var/data`` layout and may be overridden explicitly for an
isolated deployment or test.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Optional

from .types import (
    AttendanceType,
    CourseType,
    EnrollmentType,
    GradeType,
    StudentType,
    TimetableType,
)

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

from education_system.paths import VAR_DIR


_DB_PATHS: dict[str, Path] = {
    "nursery": VAR_DIR / "data" / "nursery" / "nursery.db",
    "primary": VAR_DIR / "data" / "primary" / "primary.db",
    "secondary": VAR_DIR / "data" / "secondary" / "secondary.db",
    "sixth_form": VAR_DIR / "data" / "sixth_form" / "sixthform.db",
    "university": VAR_DIR / "data" / "university" / "db_files" / "student_records.db",
}


def _get_db_path(system: str) -> Path:
    """Return the absolute path to the database for *system*.

    Raises ValueError for unknown system keys.
    """
    key = system.lower().strip()
    if key not in _DB_PATHS:
        raise ValueError(
            f"Unknown system '{system}'. Valid keys: {', '.join(_DB_PATHS)}"
        )
    path = _DB_PATHS[key]
    if not path.is_file():
        raise FileNotFoundError(f"Database for system '{key}' does not exist: {path}")
    return path


def configure_database_path(system: str, path: str | Path) -> None:
    """Override a system database path, primarily for isolated deployments/tests."""
    key = system.lower().strip()
    if key not in _DB_PATHS:
        raise ValueError(f"Unknown system '{system}'")
    _DB_PATHS[key] = Path(path).resolve()


def _get_connection(system: str) -> sqlite3.Connection:
    """Open a sqlite3 connection for *system* with Row factory set."""
    conn = sqlite3.connect(str(_get_db_path(system)))
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone() is not None


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------

def _row_to_student(row: sqlite3.Row, system: str) -> StudentType:
    """Map a DB row to StudentType, handling per-system column differences."""
    d = dict(row)
    # Normalise primary key
    sid = d.get("student_id") or d.get("pupil_id") or ""
    # Numeric PK
    pk = d.get("id") or 0
    # For university the numeric PK isn't a separate column — synthesise it
    if not pk:
        pk = hash(sid) & 0x7FFFFFFF

    return StudentType(
        id=int(pk),
        student_id=str(sid),
        first_name=d.get("first_name") or "",
        last_name=d.get("last_name") or "",
        email=d.get("email") or d.get("email_address"),
        phone=d.get("phone"),
        date_of_birth=d.get("date_of_birth") or d.get("dob"),
        enrollment_date=d.get("enrollment_date") or d.get("registration_datetime") or d.get("admission_date"),
        major=(
            d.get("major")
            or d.get("course")
            or d.get("program")
            or d.get("year_group")
            or d.get("class_name")
            or d.get("form_group")
            or d.get("room")
        ),
        status=d.get("status"),
        gpa=None,  # not stored directly in any system DB
        system_key=system,
    )


def resolve_students(
    system: str,
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
) -> List[StudentType]:
    """Return a paginated list of students/pupils for the given system."""
    conn = _get_connection(system)
    try:
        c = conn.cursor()
        key = system.lower()
        table = "pupils" if key in {"nursery", "primary", "secondary"} else "students"
        id_col = "pupil_id" if table == "pupils" else "student_id"

        if search:
            pattern = f"%{search}%"
            sql = (
                f"SELECT * FROM {table} "
                f"WHERE first_name LIKE ? OR last_name LIKE ? OR {id_col} LIKE ? "
                f"ORDER BY last_name, first_name "
                f"LIMIT ? OFFSET ?"
            )
            rows = c.execute(sql, (pattern, pattern, pattern, limit, offset)).fetchall()
        else:
            sql = (
                f"SELECT * FROM {table} "
                f"ORDER BY last_name, first_name "
                f"LIMIT ? OFFSET ?"
            )
            rows = c.execute(sql, (limit, offset)).fetchall()

        return [_row_to_student(r, system) for r in rows]
    finally:
        conn.close()


def resolve_student(system: str, student_id: str) -> Optional[StudentType]:
    """Return a single student by their student/pupil ID."""
    conn = _get_connection(system)
    try:
        c = conn.cursor()
        key = system.lower()
        table = "pupils" if key in {"nursery", "primary", "secondary"} else "students"
        id_col = "pupil_id" if table == "pupils" else "student_id"
        row = c.execute(
            f"SELECT * FROM {table} WHERE {id_col} = ?", (student_id,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_student(row, system)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Courses / Subjects
# ---------------------------------------------------------------------------

def _row_to_course(row: sqlite3.Row, system: str) -> CourseType:
    d = dict(row)
    pk = d.get("id") or 0
    return CourseType(
        id=int(pk),
        course_code=d.get("course_code") or d.get("code") or d.get("subject_code"),
        course_name=d.get("course_name") or d.get("name") or d.get("title") or "",
        description=d.get("description"),
        credits=_to_int(d.get("credits") or d.get("credit_hours")),
        department=d.get("department"),
        instructor=d.get("instructor") or d.get("teacher"),
        max_enrollment=_to_int(d.get("max_enrollment") or d.get("capacity")),
        current_enrollment=_to_int(d.get("current_enrollment")),
        semester=d.get("semester") or d.get("term"),
        status=d.get("status"),
    )


def _to_int(val) -> Optional[int]:
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def resolve_courses(
    system: str,
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
) -> List[CourseType]:
    conn = _get_connection(system)
    try:
        c = conn.cursor()
        key = system.lower()
        # School systems use subjects; post-16/university systems use courses.
        table = "subjects" if key in ("nursery", "secondary", "primary") else "courses"
        if not _table_exists(conn, table):
            return []
        name_col = "title"  # all tables use "title" for display name except university

        if key == "university":
            name_col = "name"

        if search:
            pattern = f"%{search}%"
            sql = (
                f"SELECT * FROM {table} "
                f"WHERE {name_col} LIKE ? "
                f"ORDER BY {name_col} "
                f"LIMIT ? OFFSET ?"
            )
            rows = c.execute(sql, (pattern, limit, offset)).fetchall()
        else:
            sql = (
                f"SELECT * FROM {table} "
                f"ORDER BY {name_col} "
                f"LIMIT ? OFFSET ?"
            )
            rows = c.execute(sql, (limit, offset)).fetchall()

        return [_row_to_course(r, system) for r in rows]
    finally:
        conn.close()


def resolve_course(system: str, course_id: str) -> Optional[CourseType]:
    conn = _get_connection(system)
    try:
        c = conn.cursor()
        key = system.lower()
        table = "subjects" if key in ("nursery", "secondary", "primary") else "courses"
        if not _table_exists(conn, table):
            return None
        row = c.execute(
            f"SELECT * FROM {table} WHERE id = ?", (course_id,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_course(row, system)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Grades
# ---------------------------------------------------------------------------

def _row_to_grade(row: sqlite3.Row, system: str) -> GradeType:
    d = dict(row)
    pk = d.get("id") or d.get("grade_id") or d.get("entry_id") or 0
    sid = d.get("student_id") or ""
    cid = (
        d.get("course_id")
        or d.get("subject_id")
        or d.get("module_code")
        or d.get("lms_course_id")
        or d.get("assessment_id")
    )
    return GradeType(
        id=int(pk),
        student_id=str(sid),
        course_id=str(cid) if cid is not None else None,
        assignment_name=(
            d.get("assignment_name")
            or d.get("assessment_name")
            or d.get("assignment_type")
            or d.get("grade_type")
        ),
        score=_to_float(d.get("score")),
        max_score=_to_float(d.get("max_score")),
        letter_grade=d.get("letter_grade") or d.get("grade"),
        grade_date=(
            d.get("grade_date")
            or d.get("graded_at")
            or d.get("recorded_at")
            or d.get("submission_date")
        ),
    )


def _to_float(val) -> Optional[float]:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def resolve_grades(
    system: str,
    student_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[GradeType]:
    conn = _get_connection(system)
    try:
        c = conn.cursor()
        key = system.lower()

        # Determine the grades table and student column.
        if key == "university":
            table = "grades"
            sid_col = "student_id"
        elif key == "sixth_form":
            table = "grades"
            sid_col = "student_id"
        elif key == "secondary":
            table = "grades"
            sid_col = "student_id"
        else:
            # nursery/primary — use assessments when the feature is available
            table = "assessments"
            sid_col = "pupil_id"

        if not _table_exists(conn, table):
            return []

        if student_id:
            rows = c.execute(
                f"SELECT * FROM {table} WHERE {sid_col} = ? LIMIT ? OFFSET ?",
                (student_id, limit, offset),
            ).fetchall()
        else:
            rows = c.execute(
                f"SELECT * FROM {table} LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()

        return [_row_to_grade(r, system) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------

def _row_to_attendance(row: sqlite3.Row, system: str) -> AttendanceType:
    d = dict(row)
    pk = d.get("id") or 0
    sid = d.get("student_id") or d.get("pupil_id") or ""
    cid = d.get("course_id") or d.get("subject_id") or d.get("module_code")
    return AttendanceType(
        id=int(pk),
        student_id=str(sid),
        course_id=str(cid) if cid is not None else None,
        date=d.get("date"),
        status=d.get("status"),
        notes=d.get("notes") or d.get("note") or d.get("reason"),
    )


def resolve_attendance(
    system: str,
    student_id: Optional[str] = None,
    date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[AttendanceType]:
    conn = _get_connection(system)
    try:
        c = conn.cursor()
        key = system.lower()

        if key in ("nursery", "secondary", "primary", "sixth_form"):
            table = "attendance_records"
            sid_col = "pupil_id" if key in {"nursery", "primary", "secondary"} else "student_id"
        else:
            # university + college both use "attendance"
            table = "attendance"
            sid_col = "student_id"

        params: list = []
        wheres: list[str] = []

        if student_id:
            wheres.append(f"{sid_col} = ?")
            params.append(student_id)
        if date:
            wheres.append("date = ?")
            params.append(date)

        where_clause = f"WHERE {' AND '.join(wheres)}" if wheres else ""
        params.extend([limit, offset])

        rows = c.execute(
            f"SELECT * FROM {table} {where_clause} ORDER BY date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()

        return [_row_to_attendance(r, system) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Enrollments
# ---------------------------------------------------------------------------

def _row_to_enrollment(row: sqlite3.Row) -> EnrollmentType:
    d = dict(row)
    pk = d.get("id") or d.get("enrollment_id") or 0
    sid = d.get("student_id") or ""
    cid = str(d.get("course_id") or d.get("subject_id") or d.get("lms_course_id") or "")
    return EnrollmentType(
        id=int(pk),
        student_id=str(sid),
        course_id=cid,
        enrollment_date=d.get("enrollment_date") or d.get("enrolled_at") or d.get("enrolled_date"),
        status=d.get("status"),
        grade=d.get("grade"),
    )


def resolve_enrollments(
    system: str,
    student_id: Optional[str] = None,
    course_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[EnrollmentType]:
    conn = _get_connection(system)
    try:
        c = conn.cursor()
        key = system.lower()

        if key in {"nursery", "primary"}:
            table = "lms_student_enrollment"
            sid_col = "student_id"
            cid_col = "lms_course_id"
        elif key in ("secondary", "sixth_form"):
            table = "enrollments"
            sid_col = "student_id"
            cid_col = "course_id" if key == "sixth_form" else "subject_id"
        else:
            # university — no simple enrollments table; use grades as proxy
            table = "enrollments"
            sid_col = "student_id"
            cid_col = "course_id"

        if not _table_exists(conn, table):
            return []

        params: list = []
        wheres: list[str] = []

        if student_id:
            wheres.append(f"{sid_col} = ?")
            params.append(student_id)
        if course_id:
            wheres.append(f"{cid_col} = ?")
            params.append(course_id)

        where_clause = f"WHERE {' AND '.join(wheres)}" if wheres else ""
        params.extend([limit, offset])

        rows = c.execute(
            f"SELECT * FROM {table} {where_clause} LIMIT ? OFFSET ?",
            params,
        ).fetchall()

        return [_row_to_enrollment(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Timetable
# ---------------------------------------------------------------------------

def _row_to_timetable(row: sqlite3.Row, system: str) -> TimetableType:
    d = dict(row)
    pk = d.get("id") or 0
    cid = d.get("course_id") or d.get("subject_id") or d.get("subject_code") or d.get("lms_course_id")
    instructor = (
        d.get("instructor_name")
        or d.get("instructor")
        or d.get("teacher")
    )
    return TimetableType(
        id=int(pk),
        course_id=str(cid) if cid is not None else None,
        day_of_week=d.get("day_of_week") or d.get("days_of_week"),
        start_time=d.get("start_time"),
        end_time=d.get("end_time"),
        room=d.get("room") or d.get("classroom"),
        instructor=instructor,
    )


def resolve_timetable(
    system: str,
    course_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[TimetableType]:
    conn = _get_connection(system)
    try:
        c = conn.cursor()
        key = system.lower()

        if key == "university":
            table = "course_schedule"
            cid_col = "course_id"
        else:
            table = "timetable_slots"
            cid_col = "course_id" if key == "sixth_form" else "subject_id"

        if not _table_exists(conn, table):
            return []

        if course_id:
            rows = c.execute(
                f"SELECT * FROM {table} WHERE {cid_col} = ? LIMIT ? OFFSET ?",
                (course_id, limit, offset),
            ).fetchall()
        else:
            rows = c.execute(
                f"SELECT * FROM {table} LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()

        return [_row_to_timetable(r, system) for r in rows]
    finally:
        conn.close()
