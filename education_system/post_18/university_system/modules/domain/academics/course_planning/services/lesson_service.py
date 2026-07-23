"""
Lesson / timetable planner — table-level persistence helpers.

Plain, Tkinter-free CRUD over the two module-private tables the Lesson
Planner GUI (``lesson_planner.py``) persists to in the shared
``student_records.db``:

* ``lesson_plans``   — one row per scheduled lesson (PK ``id``)
* ``lesson_courses`` — one row per planner-local course (PK ``code``)

The GUI holds everything in memory and bulk-rewrites both tables on every
save (DELETE-all + re-INSERT). The CLI instead does per-row CRUD here so
both front-ends share the exact same rows. Column names mirror the GUI's
``_ensure_schema`` verbatim.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from education_system.post_18.university_system.infrastructure.database.db import (
    get_connection,
    transaction,
)

# Exact column order for each table (matches lesson_planner._LESSON_FIELDS /
# _COURSE_FIELDS plus the audit columns written by the GUI).
LESSON_FIELDS = ("course", "title", "instructor", "type", "day",
                 "start", "end", "room", "notes")
COURSE_FIELDS = ("code", "name", "dept", "credits", "semester", "description")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------- #
# Lessons  (lesson_plans)
# --------------------------------------------------------------------------- #
def list_lessons(search: Optional[str] = None) -> list[dict[str, Any]]:
    """Return all lesson rows (optionally filtered by a case-insensitive
    substring across the text columns), ordered day then start."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, course, title, instructor, type, day, start, end, "
            "room, notes, updated_at, updated_by "
            "FROM lesson_plans ORDER BY day, start, id"
        ).fetchall()
    lessons = [dict(r) for r in rows]
    if search:
        needle = search.lower()
        lessons = [
            row for row in lessons
            if any(needle in str(v).lower() for v in row.values())
        ]
    return lessons


def get_lesson(lesson_id: int) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, course, title, instructor, type, day, start, end, "
            "room, notes, updated_at, updated_by "
            "FROM lesson_plans WHERE id = ?",
            (lesson_id,),
        ).fetchone()
    return dict(row) if row else None


def add_lesson(
    course: str,
    title: str,
    instructor: str = "",
    type: str = "",
    day: str = "",
    start: str = "",
    end: str = "",
    room: str = "",
    notes: str = "",
    updated_by: str = "",
) -> int:
    """Insert a lesson row and return its new id."""
    now = _now()
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO lesson_plans (course, title, instructor, type, day, "
            "start, end, room, notes, updated_at, updated_by) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (course, title, instructor, type, day, start, end, room, notes,
             now, updated_by),
        )
        return int(cur.lastrowid)


def update_lesson(lesson_id: int, updated_by: str = "", **fields: Any) -> bool:
    """Update the given columns of a lesson row. Only keys in
    ``LESSON_FIELDS`` are honoured. Returns True if a row changed."""
    sets = [(k, v) for k, v in fields.items()
            if k in LESSON_FIELDS and v is not None]
    if not sets:
        return False
    columns = ", ".join(f"{k} = ?" for k, _ in sets)
    params = [v for _, v in sets]
    params.extend([_now(), updated_by, lesson_id])
    with transaction() as conn:
        cur = conn.execute(
            f"UPDATE lesson_plans SET {columns}, updated_at = ?, updated_by = ? "
            "WHERE id = ?",
            params,
        )
        return cur.rowcount > 0


def delete_lesson(lesson_id: int) -> bool:
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM lesson_plans WHERE id = ?", (lesson_id,))
        return cur.rowcount > 0


# --------------------------------------------------------------------------- #
# Courses  (lesson_courses)
# --------------------------------------------------------------------------- #
def list_courses() -> list[dict[str, Any]]:
    """Return planner-local course rows ordered by code."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT code, name, dept, credits, semester, description, "
            "updated_at, updated_by FROM lesson_courses ORDER BY code"
        ).fetchall()
    return [dict(r) for r in rows]


def get_course(code: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT code, name, dept, credits, semester, description, "
            "updated_at, updated_by FROM lesson_courses WHERE code = ?",
            (code,),
        ).fetchone()
    return dict(row) if row else None


def add_course(
    code: str,
    name: str,
    dept: str = "",
    credits: str = "",
    semester: str = "",
    description: str = "",
    updated_by: str = "",
) -> str:
    """Insert a planner-local course. Raises ValueError if the code exists."""
    if get_course(code) is not None:
        raise ValueError(f"Course code '{code}' already exists.")
    now = _now()
    with transaction() as conn:
        conn.execute(
            "INSERT INTO lesson_courses (code, name, dept, credits, semester, "
            "description, updated_at, updated_by) VALUES (?,?,?,?,?,?,?,?)",
            (code, name, dept, credits, semester, description, now, updated_by),
        )
    return code


def update_course(code: str, updated_by: str = "", **fields: Any) -> bool:
    """Update the given columns of a course row (keyed by code). Only keys in
    ``COURSE_FIELDS`` other than ``code`` are honoured."""
    sets = [(k, v) for k, v in fields.items()
            if k in COURSE_FIELDS and k != "code" and v is not None]
    if not sets:
        return False
    columns = ", ".join(f"{k} = ?" for k, _ in sets)
    params = [v for _, v in sets]
    params.extend([_now(), updated_by, code])
    with transaction() as conn:
        cur = conn.execute(
            f"UPDATE lesson_courses SET {columns}, updated_at = ?, "
            "updated_by = ? WHERE code = ?",
            params,
        )
        return cur.rowcount > 0


def delete_course(code: str) -> bool:
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM lesson_courses WHERE code = ?", (code,))
        return cur.rowcount > 0


# --------------------------------------------------------------------------- #
# Read-only summary / validation
# --------------------------------------------------------------------------- #
def contact_hours_by_course() -> list[dict[str, Any]]:
    """Sum planned weekly contact hours per course code from the lesson rows.

    Mirrors the GUI's ``_validate_hours`` arithmetic: hours = end_hour -
    start_hour, summed per course (the leading code before ' - ' is used as
    the key so 'CS101 - Intro' groups with a bare 'CS101')."""
    hours: dict[str, dict[str, Any]] = {}
    for lesson in list_lessons():
        try:
            sh = int(str(lesson.get("start", "")).split(":")[0])
            eh = int(str(lesson.get("end", "")).split(":")[0])
        except (ValueError, IndexError):
            continue
        raw = str(lesson.get("course", "") or "")
        code = raw.split(" - ", 1)[0].strip() or raw.strip()
        if not code:
            continue
        entry = hours.setdefault(code, {"course": code, "lessons": 0, "hours": 0})
        entry["lessons"] += 1
        entry["hours"] += max(0, eh - sh)
    return sorted(hours.values(), key=lambda e: e["course"])
