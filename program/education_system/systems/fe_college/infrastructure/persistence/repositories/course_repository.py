"""Course persistence: courses, units, entry requirements and class groups."""

from __future__ import annotations

import sqlite3

from education_system.systems.fe_college.domain.courses.entry_requirements import (
    EntryRequirement,
)
from education_system.systems.fe_college.domain.courses.models import Course
from education_system.systems.fe_college.domain.courses.modules import Unit
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.domain.teaching.classes import ClassGroup
from education_system.systems.fe_college.infrastructure.persistence import (
    read_only,
    transaction,
)

# Courses are almost always wanted with their live headcount, so the enrolled
# count is joined in rather than fetched per row by the caller.
_COURSE_SELECT = """
    SELECT c.*,
           (SELECT COUNT(*) FROM enrolments e
             WHERE e.course_id = c.course_id AND e.status = 'active') AS enrolled
    FROM courses c
"""


# ── Courses ─────────────────────────────────────────────────────────────────

def get(course_id: str) -> Course | None:
    with read_only() as conn:
        row = conn.execute(
            _COURSE_SELECT + " WHERE c.course_id = ?", (course_id,)
        ).fetchone()
    return Course.from_row(row) if row else None


def list_courses(
    *,
    curriculum_area: str | None = None,
    status: str | None = None,
    academic_year: str | None = None,
    level: str | None = None,
    course_leader: str | None = None,
    enrollable_only: bool = False,
    query: str = "",
) -> list[Course]:
    where: list[str] = []
    params: list = []
    if curriculum_area:
        where.append("c.curriculum_area = ?")
        params.append(curriculum_area)
    if status:
        where.append("c.status = ?")
        params.append(status)
    if academic_year:
        where.append("c.academic_year = ?")
        params.append(academic_year)
    if level:
        where.append("c.level = ?")
        params.append(level)
    if course_leader:
        where.append("c.course_leader = ?")
        params.append(course_leader)
    if enrollable_only:
        where.append("c.status IN ('recruiting', 'running')")
    if query:
        where.append("(c.course_id LIKE ? OR c.title LIKE ? OR c.awarding_body LIKE ?)")
        like = f"%{query}%"
        params.extend([like] * 3)

    sql = _COURSE_SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY c.curriculum_area, c.level, c.title"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    courses = [Course.from_row(r) for r in rows]
    # ``is_full`` needs the joined headcount, so a full-course filter can only
    # be applied after the model is built.
    return [c for c in courses if c.is_enrollable] if enrollable_only else courses


def create(course: Course) -> Course:
    course.validate()
    row = course.to_row()
    placeholders = ", ".join("?" for _ in row)
    try:
        with transaction() as conn:
            conn.execute(
                f"INSERT INTO courses ({', '.join(row)}) VALUES ({placeholders})",
                list(row.values()),
            )
    except sqlite3.IntegrityError as exc:
        if "PRIMARY KEY" in str(exc) or "courses.course_id" in str(exc):
            raise ValidationError(
                f"A course with code {course.course_id} already exists"
            ) from exc
        if "FOREIGN KEY" in str(exc):
            raise ValidationError(
                f"Course leader '{course.course_leader}' is not a known staff member"
            ) from exc
        raise ValidationError(f"Could not save course: {exc}") from exc
    return course


def update(course: Course) -> Course:
    course.validate()
    row = course.to_row()
    assignments = ", ".join(f"{col} = ?" for col in row if col != "course_id")
    values = [v for k, v in row.items() if k != "course_id"]
    try:
        with transaction() as conn:
            cur = conn.execute(
                f"UPDATE courses SET {assignments} WHERE course_id = ?",
                [*values, course.course_id],
            )
            if cur.rowcount == 0:
                raise ValidationError(f"No course with code {course.course_id}")
    except sqlite3.IntegrityError as exc:
        raise ValidationError(f"Could not save course: {exc}") from exc
    return course


def delete(course_id: str) -> bool:
    """Delete a course and everything that hangs off it.

    Enrolments, units, sessions and assignments cascade. Callers that care
    about losing enrolment history should archive the course instead — the
    service layer makes that the default and this the explicit choice.
    """
    with transaction() as conn:
        cur = conn.execute("DELETE FROM courses WHERE course_id = ?", (course_id,))
        return cur.rowcount > 0


def set_status(course_id: str, status: str) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE courses SET status = ? WHERE course_id = ?", (status, course_id)
        )


def academic_years() -> list[str]:
    with read_only() as conn:
        rows = conn.execute(
            "SELECT DISTINCT academic_year FROM courses "
            "WHERE academic_year IS NOT NULL AND academic_year <> '' "
            "ORDER BY academic_year DESC"
        ).fetchall()
    return [r[0] for r in rows]


def enrolment_counts() -> dict[str, int]:
    """Active enrolments per course — one query for the whole dashboard."""
    with read_only() as conn:
        rows = conn.execute(
            "SELECT course_id, COUNT(*) AS n FROM enrolments "
            "WHERE status = 'active' GROUP BY course_id"
        ).fetchall()
    return {r["course_id"]: r["n"] for r in rows}


# ── Units ───────────────────────────────────────────────────────────────────

def list_units(course_id: str) -> list[Unit]:
    with read_only() as conn:
        rows = conn.execute(
            "SELECT * FROM units WHERE course_id = ? ORDER BY sequence, unit_id",
            (course_id,),
        ).fetchall()
    return [Unit.from_row(r) for r in rows]


def get_unit(unit_id: str, course_id: str) -> Unit | None:
    with read_only() as conn:
        row = conn.execute(
            "SELECT * FROM units WHERE unit_id = ? AND course_id = ?",
            (unit_id, course_id),
        ).fetchone()
    return Unit.from_row(row) if row else None


def add_unit(unit: Unit) -> Unit:
    unit.validate()
    row = unit.to_row()
    placeholders = ", ".join("?" for _ in row)
    try:
        with transaction() as conn:
            conn.execute(
                f"INSERT INTO units ({', '.join(row)}) VALUES ({placeholders})",
                list(row.values()),
            )
    except sqlite3.IntegrityError as exc:
        if "PRIMARY KEY" in str(exc):
            raise ValidationError(
                f"Unit {unit.unit_id} is already on course {unit.course_id}"
            ) from exc
        raise ValidationError(f"Could not save unit: {exc}") from exc
    return unit


def update_unit(unit: Unit) -> Unit:
    unit.validate()
    row = unit.to_row()
    assignments = ", ".join(
        f"{col} = ?" for col in row if col not in ("unit_id", "course_id")
    )
    values = [v for k, v in row.items() if k not in ("unit_id", "course_id")]
    with transaction() as conn:
        conn.execute(
            f"UPDATE units SET {assignments} WHERE unit_id = ? AND course_id = ?",
            [*values, unit.unit_id, unit.course_id],
        )
    return unit


def delete_unit(unit_id: str, course_id: str) -> bool:
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM units WHERE unit_id = ? AND course_id = ?", (unit_id, course_id)
        )
        return cur.rowcount > 0


# ── Entry requirements ──────────────────────────────────────────────────────

def get_entry_requirement(course_id: str) -> EntryRequirement | None:
    with read_only() as conn:
        row = conn.execute(
            "SELECT * FROM entry_requirements WHERE course_id = ?", (course_id,)
        ).fetchone()
    return EntryRequirement.from_row(row) if row else None


def save_entry_requirement(requirement: EntryRequirement) -> EntryRequirement:
    requirement.validate()
    row = requirement.to_row()
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    updates = ", ".join(f"{c} = excluded.{c}" for c in row if c != "course_id")
    with transaction() as conn:
        conn.execute(
            f"INSERT INTO entry_requirements ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(course_id) DO UPDATE SET {updates}",
            list(row.values()),
        )
    return requirement


# ── Class groups ────────────────────────────────────────────────────────────

_GROUP_SELECT = """
    SELECT g.*,
           (SELECT COUNT(*) FROM group_members m
             WHERE m.group_id = g.group_id) AS members
    FROM class_groups g
"""


def list_groups(*, course_id: str | None = None,
                teacher_id: str | None = None) -> list[ClassGroup]:
    where, params = [], []
    if course_id:
        where.append("g.course_id = ?")
        params.append(course_id)
    if teacher_id:
        where.append("g.teacher_id = ?")
        params.append(teacher_id)
    sql = _GROUP_SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY g.course_id, g.name"
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [ClassGroup.from_row(r) for r in rows]


def get_group(group_id: str) -> ClassGroup | None:
    with read_only() as conn:
        row = conn.execute(_GROUP_SELECT + " WHERE g.group_id = ?", (group_id,)).fetchone()
    return ClassGroup.from_row(row) if row else None


def create_group(group: ClassGroup) -> ClassGroup:
    group.validate()
    row = group.to_row()
    placeholders = ", ".join("?" for _ in row)
    try:
        with transaction() as conn:
            conn.execute(
                f"INSERT INTO class_groups ({', '.join(row)}) VALUES ({placeholders})",
                list(row.values()),
            )
    except sqlite3.IntegrityError as exc:
        if "PRIMARY KEY" in str(exc):
            raise ValidationError(
                f"A class group with code {group.group_id} already exists"
            ) from exc
        raise ValidationError(f"Could not save class group: {exc}") from exc
    return group


def set_group_members(group_id: str, student_ids: list[str]) -> None:
    """Replace a group's membership."""
    with transaction() as conn:
        conn.execute("DELETE FROM group_members WHERE group_id = ?", (group_id,))
        if student_ids:
            conn.executemany(
                "INSERT INTO group_members (group_id, student_id) VALUES (?, ?)",
                [(group_id, sid) for sid in student_ids],
            )


def group_members(group_id: str) -> list[str]:
    with read_only() as conn:
        rows = conn.execute(
            "SELECT student_id FROM group_members WHERE group_id = ?", (group_id,)
        ).fetchall()
    return [r[0] for r in rows]


__all__ = [
    "academic_years",
    "add_unit",
    "create",
    "create_group",
    "delete",
    "delete_unit",
    "enrolment_counts",
    "get",
    "get_entry_requirement",
    "get_group",
    "get_unit",
    "group_members",
    "list_courses",
    "list_groups",
    "list_units",
    "save_entry_requirement",
    "set_group_members",
    "set_status",
    "update",
    "update_unit",
]
