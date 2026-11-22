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
from education_system import paths
from education_system.systems.sixth_form.domain.learners.students.students import A_LEVEL_SUBJECTS
from education_system.systems.sixth_form.infrastructure import record_links as _links

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_COURSES_DB

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
    #: grade_scales qualification type taught on this course; None =
    #: the subject's own type (so an "English Language" course can be the
    #: A level or the GCSE resit).
    qualification_type: str | None = None
    #: Planned teaching hours per learner per year on this course.
    planned_hours: float | None = None
    #: When the course was archived (hidden from lists, history kept);
    #: None = live.
    archived_at: str | None = None


# ── DB plumbing ──────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
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
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(courses)")}
        for col, ddl in (("qualification_type", "TEXT"),
                         ("planned_hours",      "REAL"),
                         ("archived_at",        "TEXT")):
            if col not in cols:
                conn.execute(f"ALTER TABLE courses ADD COLUMN {col} {ddl}")
                logger.info("Courses: added column %s", col)
        conn.commit()
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
        qualification_type=(r["qualification_type"]
                            if "qualification_type" in r.keys() else None),
        planned_hours=(r["planned_hours"]
                       if "planned_hours" in r.keys() else None),
        archived_at=(r["archived_at"]
                     if "archived_at" in r.keys() else None),
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
        from education_system.systems.sixth_form.domain.academics.subjects import subjects as _subjects
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

    from education_system.systems.sixth_form.domain.academics.qualifications import (
        grade_scales as _gs,
    )
    qtype_raw = (data.get("qualification_type") or "").strip()
    if qtype_raw:
        qtype = _gs.canonical_type(qtype_raw)
        if qtype is None:
            raise ValidationError(
                "Qualification type must be blank or one of: "
                + ", ".join(_gs.QUALIFICATION_TYPES))
        out["qualification_type"] = qtype
    else:
        out["qualification_type"] = None
    ph = data.get("planned_hours")
    if ph in (None, "") or (isinstance(ph, str) and not ph.strip()):
        out["planned_hours"] = None
    else:
        try:
            h = float(ph)
        except (TypeError, ValueError):
            raise ValidationError("Planned hours must be a number") from None
        if h < 0 or h > 2000:
            raise ValidationError("Planned hours must be 0-2000")
        out["planned_hours"] = round(h, 1)
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
                     teacher, room, max_students, description,
                     qualification_type, planned_hours)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["course_code"], payload["subject"],
                    payload["title"], payload["year_group"],
                    payload["academic_year"], payload["teacher"],
                    payload["room"], payload["max_students"],
                    payload["description"], payload["qualification_type"],
                    payload["planned_hours"],
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
    include_archived: bool = False,
) -> list[Course]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if not include_archived:
        clauses.append("archived_at IS NULL")
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

    # Older callers don't send these; keep what is stored.
    data = dict(data)
    for key in ("qualification_type", "planned_hours"):
        data.setdefault(key, getattr(existing, key))

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
                    teacher = ?, room = ?, max_students = ?, description = ?,
                    qualification_type = ?, planned_hours = ?
                WHERE course_id = ?
                """,
                (
                    payload["course_code"], payload["subject"],
                    payload["title"], payload["year_group"],
                    payload["academic_year"], payload["teacher"],
                    payload["room"], payload["max_students"],
                    payload["description"], payload["qualification_type"],
                    payload["planned_hours"], course_id,
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


#: Rows that go with a course but are its *structure*, not its history:
#: a course whose only dependants are these can still be deleted.
_STRUCTURE_TABLES: frozenset[str] = frozenset({
    "class_groups", "class_group_students", "timetable_slots",
    "attendance_slot_weeks", "optimiser_plan_slots", "class_group_waitlist",
})
#: Tables that hold a course id without a foreign key.
_SOFT_REFS: tuple[tuple[str, str], ...] = (
    ("coursework_assignments", "course_id"),
    ("lesson_plans", "course_id"),
    ("class_resources", "course_id"),
    ("library_reading_lists", "course_id"),
    ("library_class_sets", "course_id"),
)


class CourseHasHistory(ValidationError):
    """Refused: deleting this course would destroy recorded history."""

    def __init__(self, course_id: int, counts: dict[str, int]):
        self.course_id = course_id
        self.counts = counts
        super().__init__(
            f"Course #{course_id} has history that deleting it would destroy "
            f"({_links.describe(counts)}). Archive the course instead — it "
            f"is hidden from lists and its history is kept.")


def linked_record_counts(course_id: int) -> dict[str, int]:
    """``{table: rows}`` a delete of this course would remove or orphan,
    through its class groups and their timetable slots."""
    init_db()
    with _connect() as conn:
        counts = _links.cascade_counts(conn, "courses", "course_id", course_id)
        group_ids = [r[0] for r in conn.execute(
            "SELECT group_id FROM class_groups WHERE course_id = ?",
            (course_id,))]
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    soft: list[dict[str, int]] = []
    with _connect() as conn:
        soft.append(_links.soft_counts(conn, _SOFT_REFS, course_id))
    for gid in group_ids:
        soft.append(_cg.soft_record_counts(gid))
    return _links.merge(counts, *soft)


def history_counts(course_id: int) -> dict[str, int]:
    """The part of :func:`linked_record_counts` that is history
    (attendance, registers, assignments …) rather than structure."""
    return {t: n for t, n in linked_record_counts(course_id).items()
            if t not in _STRUCTURE_TABLES}


def delete_course(course_id: int) -> bool:
    """Delete a course created by mistake.

    Refused with :class:`CourseHasHistory` when anything recorded against
    it (attendance, registers, assignments, lesson plans …) would be lost
    through the cascade — use :func:`archive_course` then. Its empty
    class groups and timetable slots go with it.
    """
    init_db()
    history = history_counts(course_id)
    if history:
        logger.warning("delete_course(%d) refused: %s", course_id, history)
        raise CourseHasHistory(course_id, history)
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


def archive_course(course_id: int) -> bool:
    """Hide a course (and its class groups and slots) from lists and
    timetables, keeping every record made against it."""
    init_db()
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    _cg.init_db()
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    _tt.init_db()
    with _connect() as conn:
        stamp = conn.execute("SELECT datetime('now')").fetchone()[0]
        cur = conn.execute(
            "UPDATE courses SET archived_at = ? "
            "WHERE course_id = ? AND archived_at IS NULL", (stamp, course_id))
        if cur.rowcount:
            conn.execute(
                "UPDATE class_groups SET archived_at = ? "
                "WHERE course_id = ? AND archived_at IS NULL",
                (stamp, course_id))
            conn.execute(
                "UPDATE timetable_slots SET archived_at = ? "
                "WHERE archived_at IS NULL AND group_id IN "
                "(SELECT group_id FROM class_groups WHERE course_id = ?)",
                (stamp, course_id))
        conn.commit()
    if cur.rowcount:
        logger.info("Archived course #%d", course_id)
    return bool(cur.rowcount)


def restore_course(course_id: int) -> bool:
    """Undo :func:`archive_course`: the course, and the groups and slots
    archived with it (same timestamp), are live again."""
    init_db()
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    _tt.init_db()
    with _connect() as conn:
        row = conn.execute("SELECT archived_at FROM courses WHERE course_id = ?",
                           (course_id,)).fetchone()
        if row is None or row["archived_at"] is None:
            return False
        stamp = row["archived_at"]
        conn.execute(
            "UPDATE timetable_slots SET archived_at = NULL "
            "WHERE archived_at = ? AND group_id IN "
            "(SELECT group_id FROM class_groups WHERE course_id = ?)",
            (stamp, course_id))
        conn.execute(
            "UPDATE class_groups SET archived_at = NULL "
            "WHERE course_id = ? AND archived_at = ?", (course_id, stamp))
        conn.execute("UPDATE courses SET archived_at = NULL WHERE course_id = ?",
                     (course_id,))
        conn.commit()
    logger.info("Restored course #%d", course_id)
    return True


# ── Qualification links ─────────────────────────────────────────────

def effective_qualification_type(course: Course) -> str:
    """The course's own qualification type, else its subject's, else A Level."""
    if course.qualification_type:
        return course.qualification_type
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        return _subjects.qualification_type_for_subject(course.subject) or "A Level"
    except Exception:
        return "A Level"


def learners_on_course(course_id: int, *, status: str | None = "Active") -> list[Any]:
    """Learning aims matching this course's subject and qualification type.

    These are the learners who *should* be in the course's class groups
    — compare with ``class_groups.list_members`` to find anyone missing.
    """
    course = get_course(course_id)
    if course is None:
        raise ValidationError(f"No course with id {course_id}")
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        learning_aims,
    )
    return learning_aims.learners_on(
        subject=course.subject,
        qualification_type=effective_qualification_type(course),
        status=status)
