"""Course data layer for the Sixth Form System.

A *course* is a specific teaching offering: subject + year group +
academic year + teacher + room. Distinct from enrolment (which links
a student to a year-group cohort) — courses are about *what is being
taught*, enrolments are about *who is in the school*.

Subjects are constrained to the same `A_LEVEL_SUBJECTS` list students
can choose from, so the two CRUD areas stay consistent.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.post_16.sixthform_system.core import paths
from education_system.post_16.sixthform_system.modules.domain.students.students.students import A_LEVEL_SUBJECTS

logger = logging.getLogger(__name__)

DB_PATH = paths.COURSES_DB

YEAR_GROUPS: tuple[int, ...] = (12, 13)
DEFAULT_MAX_STUDENTS: int = 25

_ACADEMIC_YEAR_RE = re.compile(r"^\d{4}/\d{2}$")
_COURSE_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{1,31}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    course_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code    TEXT NOT NULL UNIQUE,
    subject        TEXT NOT NULL,
    title          TEXT NOT NULL,
    year_group     INTEGER NOT NULL,
    academic_year  TEXT NOT NULL,
    teacher        TEXT,
    room           TEXT,
    max_students   INTEGER NOT NULL DEFAULT 25,
    description    TEXT,
    created_at     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_courses_subject  ON courses(subject);
CREATE INDEX IF NOT EXISTS idx_courses_year     ON courses(academic_year);
CREATE INDEX IF NOT EXISTS idx_courses_yg       ON courses(year_group);
"""


@dataclass
class Course:
    course_id: int
    course_code: str
    subject: str
    title: str
    year_group: int
    academic_year: str
    teacher: str | None
    room: str | None
    max_students: int
    description: str | None
    created_at: str


# ── DB plumbing ──────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Courses schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> Course:
    return Course(
        course_id=r["course_id"],
        course_code=r["course_code"],
        subject=r["subject"],
        title=r["title"],
        year_group=r["year_group"],
        academic_year=r["academic_year"],
        teacher=r["teacher"],
        room=r["room"],
        max_students=r["max_students"],
        description=r["description"],
        created_at=r["created_at"],
    )


# ── Validation ──────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for any invalid course-form input."""


def _require(value: str | None, label: str) -> str:
    if not value or not str(value).strip():
        raise ValidationError(f"{label} is required")
    return str(value).strip()


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    code = _require(data.get("course_code"), "Course code").upper()
    if not _COURSE_CODE_RE.match(code):
        raise ValidationError(
            "Course code must be 2-32 chars: uppercase letters, digits, hyphens "
            "(e.g. 'MATH-12-2025')"
        )
    out["course_code"] = code

    subject = _require(data.get("subject"), "Subject")
    # Validate against the live subjects table (source of truth) but
    # tolerate the table not existing yet — fall back to the seed list.
    try:
        from education_system.post_16.sixthform_system.modules.domain.academics.subjects import subjects as _subjects
        if not _subjects.is_valid_subject(subject):
            raise ValidationError(f"Unknown subject: {subject}")
    except ImportError:
        if subject not in A_LEVEL_SUBJECTS:
            raise ValidationError(f"Unknown subject: {subject}")
    out["subject"] = subject

    out["title"] = _require(data.get("title"), "Title")

    yg_raw = data.get("year_group")
    if yg_raw in (None, ""):
        raise ValidationError("Year group is required")
    try:
        yg = int(yg_raw)
    except (TypeError, ValueError):
        raise ValidationError("Year group must be a whole number") from None
    if yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of {', '.join(str(y) for y in YEAR_GROUPS)}")
    out["year_group"] = yg

    year = _require(data.get("academic_year"), "Academic year")
    if not _ACADEMIC_YEAR_RE.match(year):
        raise ValidationError("Academic year must look like '2025/26'")
    out["academic_year"] = year

    out["teacher"] = (data.get("teacher") or "").strip() or None
    out["room"]    = (data.get("room") or "").strip() or None

    mx_raw = data.get("max_students")
    if mx_raw in (None, ""):
        mx = DEFAULT_MAX_STUDENTS
    else:
        try:
            mx = int(mx_raw)
        except (TypeError, ValueError):
            raise ValidationError("Max students must be a whole number") from None
        if mx <= 0 or mx > 1000:
            raise ValidationError("Max students must be between 1 and 1000")
    out["max_students"] = mx

    out["description"] = (data.get("description") or "").strip() or None
    return out


# ── CRUD ────────────────────────────────────────────────────────────

def create_course(data: dict[str, Any]) -> Course:
    init_db()
    try:
        payload = _validate_payload(data)
    except ValidationError as e:
        logger.warning("create_course validation failed: %s", e)
        raise

    try:
        with _connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO courses
                    (course_code, subject, title, year_group, academic_year,
                     teacher, room, max_students, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["course_code"], payload["subject"],
                    payload["title"], payload["year_group"],
                    payload["academic_year"], payload["teacher"],
                    payload["room"], payload["max_students"],
                    payload["description"],
                ),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            logger.warning(
                "create_course: duplicate code %s", payload["course_code"])
            raise ValidationError(
                f"Course code '{payload['course_code']}' is already in use"
            ) from e
        logger.exception("create_course DB error")
        raise ValidationError(f"Database error: {e}") from e

    course = get_course(new_id)
    assert course is not None
    logger.info(
        "Created course #%d (%s — %s, Year %d, %s)",
        new_id, course.course_code, course.subject,
        course.year_group, course.academic_year,
    )
    return course


def get_course(course_id: int) -> Course | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM courses WHERE course_id = ?", (course_id,)
        ).fetchone()
        return _row(row) if row else None


def get_course_by_code(course_code: str) -> Course | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM courses WHERE course_code = ?",
            (course_code.strip().upper(),),
        ).fetchone()
        return _row(row) if row else None


def list_courses(
    *,
    subject: str | None = None,
    year_group: int | None = None,
    academic_year: str | None = None,
    search: str | None = None,
) -> list[Course]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if subject:
        clauses.append("subject = ?")
        args.append(subject)
    if year_group is not None:
        clauses.append("year_group = ?")
        args.append(year_group)
    if academic_year:
        clauses.append("academic_year = ?")
        args.append(academic_year)
    if search:
        q = f"%{search.strip()}%"
        clauses.append("(course_code LIKE ? OR title LIKE ? OR teacher LIKE ?)")
        args.extend([q, q, q])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT * FROM courses "
        f"{where} ORDER BY academic_year DESC, year_group, subject, course_code"
    )
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def update_course(course_id: int, data: dict[str, Any]) -> Course:
    init_db()
    existing = get_course(course_id)
    if existing is None:
        logger.warning("update_course: unknown id %d", course_id)
        raise ValidationError(f"No course with id {course_id}")

    try:
        payload = _validate_payload(data)
    except ValidationError as e:
        logger.warning("update_course(%d) validation failed: %s", course_id, e)
        raise

    try:
        with _connect() as conn:
            conn.execute(
                """
                UPDATE courses SET
                    course_code = ?, subject = ?, title = ?,
                    year_group = ?, academic_year = ?,
                    teacher = ?, room = ?, max_students = ?, description = ?
                WHERE course_id = ?
                """,
                (
                    payload["course_code"], payload["subject"],
                    payload["title"], payload["year_group"],
                    payload["academic_year"], payload["teacher"],
                    payload["room"], payload["max_students"],
                    payload["description"], course_id,
                ),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            logger.warning(
                "update_course(%d): duplicate code %s",
                course_id, payload["course_code"],
            )
            raise ValidationError(
                f"Course code '{payload['course_code']}' is already in use"
            ) from e
        logger.exception("update_course DB error")
        raise ValidationError(f"Database error: {e}") from e

    course = get_course(course_id)
    assert course is not None
    logger.info("Updated course #%d (%s)", course_id, course.course_code)
    return course


def delete_course(course_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM courses WHERE course_id = ?", (course_id,)
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted course #%d", course_id)
            return True
        logger.warning("delete_course: unknown id %d", course_id)
        return False
