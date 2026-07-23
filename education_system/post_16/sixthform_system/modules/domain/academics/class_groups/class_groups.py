"""Class-group data layer for the Sixth Form System.

A *class group* is a teaching set within a course — e.g. Maths Year 12
might have three groups: 12M-1, 12M-2, 12M-3. Each group has a
many-to-many relationship with students through `class_group_students`.

Group-level fields (teacher, room, max_students) override the course's
defaults; leaving them null means "use the course value".

Cascade behaviour:
- Deleting a course removes its class groups (and their memberships).
- Deleting a student removes them from any groups they belong to.
- Hard-deleting a group removes its memberships.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.post_16.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.CLASS_GROUPS_DB

_SCHEMA = """
CREATE TABLE IF NOT EXISTS class_groups (
    group_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id    INTEGER NOT NULL,
    group_name   TEXT NOT NULL,
    teacher      TEXT,
    room         TEXT,
    schedule     TEXT,
    max_students INTEGER,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(course_id, group_name),
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS class_group_students (
    group_id   INTEGER NOT NULL,
    student_id TEXT NOT NULL,
    joined_at  TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (group_id, student_id),
    FOREIGN KEY (group_id)   REFERENCES class_groups(group_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)   ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_class_groups_course  ON class_groups(course_id);
CREATE INDEX IF NOT EXISTS idx_cgs_student ON class_group_students(student_id);
"""


@dataclass
class ClassGroup:
    group_id: int
    course_id: int
    group_name: str
    teacher: str | None
    room: str | None
    schedule: str | None
    max_students: int | None
    notes: str | None
    created_at: str


@dataclass
class ClassGroupMember:
    group_id: int
    student_id: str
    joined_at: str


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
    # Ensure the parent tables exist (FKs reference them).
    from education_system.post_16.sixthform_system.modules.domain.academics.courses import courses as _courses
    from education_system.post_16.sixthform_system.modules.domain.students.students import students as _students
    _courses.init_db()
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Class-groups schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> ClassGroup:
    return ClassGroup(
        group_id=r["group_id"],
        course_id=r["course_id"],
        group_name=r["group_name"],
        teacher=r["teacher"],
        room=r["room"],
        schedule=r["schedule"],
        max_students=r["max_students"],
        notes=r["notes"],
        created_at=r["created_at"],
    )


# ── Validation ──────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for any invalid class-group input."""


def _require(value: str | None, label: str) -> str:
    if not value or not str(value).strip():
        raise ValidationError(f"{label} is required")
    return str(value).strip()


def _validate_group_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    cid_raw = data.get("course_id")
    if cid_raw in (None, ""):
        raise ValidationError("Course is required")
    try:
        cid = int(cid_raw)
    except (TypeError, ValueError):
        raise ValidationError("Course ID must be a whole number") from None

    # Course must exist.
    from education_system.post_16.sixthform_system.modules.domain.academics.courses import (
        courses as _courses,
    )
    if _courses.get_course(cid) is None:
        raise ValidationError(f"No course with id {cid}")
    out["course_id"] = cid

    out["group_name"] = _require(data.get("group_name"), "Group name")

    out["teacher"]  = (data.get("teacher")  or "").strip() or None
    out["room"]     = (data.get("room")     or "").strip() or None
    out["schedule"] = (data.get("schedule") or "").strip() or None
    out["notes"]    = (data.get("notes")    or "").strip() or None

    mx_raw = data.get("max_students")
    if mx_raw in (None, ""):
        out["max_students"] = None
    else:
        try:
            mx = int(mx_raw)
        except (TypeError, ValueError):
            raise ValidationError(
                "Max students must be a whole number or blank") from None
        if mx <= 0 or mx > 1000:
            raise ValidationError("Max students must be between 1 and 1000")
        out["max_students"] = mx
    return out


# ── Group CRUD ──────────────────────────────────────────────────────

def create_group(data: dict[str, Any]) -> ClassGroup:
    init_db()
    try:
        payload = _validate_group_payload(data)
    except ValidationError as e:
        logger.warning("create_group validation failed: %s", e)
        raise

    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO class_groups
                   (course_id, group_name, teacher, room, schedule,
                    max_students, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (payload["course_id"], payload["group_name"],
                 payload["teacher"], payload["room"], payload["schedule"],
                 payload["max_students"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            logger.warning(
                "create_group: duplicate name '%s' for course #%d",
                payload["group_name"], payload["course_id"],
            )
            raise ValidationError(
                f"Group '{payload['group_name']}' already exists for this course"
            ) from e
        logger.exception("create_group DB error")
        raise ValidationError(f"Database error: {e}") from e

    g = get_group(new_id)
    assert g is not None
    logger.info(
        "Created class group #%d (%s, course #%d)",
        new_id, g.group_name, g.course_id,
    )
    return g


def get_group(group_id: int) -> ClassGroup | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM class_groups WHERE group_id = ?", (group_id,)
        ).fetchone()
        return _row(row) if row else None


def list_groups(
    *,
    course_id: int | None = None,
    teacher: str | None = None,
    search: str | None = None,
) -> list[ClassGroup]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if course_id is not None:
        clauses.append("course_id = ?")
        args.append(course_id)
    if teacher:
        q = f"%{teacher.strip()}%"
        clauses.append("teacher LIKE ?")
        args.append(q)
    if search:
        q = f"%{search.strip()}%"
        clauses.append("(group_name LIKE ? OR room LIKE ? OR schedule LIKE ?)")
        args.extend([q, q, q])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT * FROM class_groups "
        f"{where} ORDER BY course_id, group_name"
    )
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def update_group(group_id: int, data: dict[str, Any]) -> ClassGroup:
    init_db()
    existing = get_group(group_id)
    if existing is None:
        logger.warning("update_group: unknown id %d", group_id)
        raise ValidationError(f"No class group with id {group_id}")

    try:
        payload = _validate_group_payload(data)
    except ValidationError as e:
        logger.warning("update_group(%d) validation failed: %s", group_id, e)
        raise

    # If max_students is lowered below current member count, refuse.
    current_members = count_members(group_id)
    if payload["max_students"] is not None and \
       payload["max_students"] < current_members:
        raise ValidationError(
            f"Cannot set max to {payload['max_students']}: group already has "
            f"{current_members} member(s)"
        )

    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE class_groups SET
                       course_id = ?, group_name = ?, teacher = ?, room = ?,
                       schedule = ?, max_students = ?, notes = ?
                   WHERE group_id = ?""",
                (payload["course_id"], payload["group_name"],
                 payload["teacher"], payload["room"], payload["schedule"],
                 payload["max_students"], payload["notes"], group_id),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            logger.warning(
                "update_group(%d): duplicate name", group_id)
            raise ValidationError(
                f"Group '{payload['group_name']}' already exists for this course"
            ) from e
        logger.exception("update_group DB error")
        raise ValidationError(f"Database error: {e}") from e

    g = get_group(group_id)
    assert g is not None
    logger.info("Updated class group #%d (%s)", group_id, g.group_name)
    return g


def delete_group(group_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM class_groups WHERE group_id = ?", (group_id,)
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted class group #%d", group_id)
            return True
        logger.warning("delete_group: unknown id %d", group_id)
        return False


# ── Member management ───────────────────────────────────────────────

def effective_cap(group: ClassGroup) -> int | None:
    """Resolve the group's effective max-students: own override, falling
    back to the parent course's max, or None if neither is set."""
    if group.max_students is not None:
        return group.max_students
    from education_system.post_16.sixthform_system.modules.domain.academics.courses import (
        courses as _courses,
    )
    course = _courses.get_course(group.course_id)
    return course.max_students if course is not None else None


def count_members(group_id: int) -> int:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM class_group_students WHERE group_id = ?",
            (group_id,),
        ).fetchone()
        return int(row["n"])


def list_members(group_id: int) -> list[str]:
    """Returns the student_ids in this group, sorted by join order."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT student_id FROM class_group_students "
            "WHERE group_id = ? ORDER BY joined_at, student_id",
            (group_id,),
        ).fetchall()
        return [r["student_id"] for r in rows]


def add_member(group_id: int, student_id: str) -> ClassGroupMember:
    init_db()
    group = get_group(group_id)
    if group is None:
        logger.warning("add_member: unknown group #%d", group_id)
        raise ValidationError(f"No class group with id {group_id}")
    from education_system.post_16.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    student = _students.get_student(student_id)
    if student is None:
        logger.warning("add_member: unknown student %s", student_id)
        raise ValidationError(f"No student with id {student_id}")

    cap = effective_cap(group)
    if cap is not None and count_members(group_id) >= cap:
        logger.warning(
            "add_member: group #%d at capacity (%d)", group_id, cap)
        raise ValidationError(
            f"Group is at capacity ({cap}); cannot add another student")

    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO class_group_students (group_id, student_id) "
                "VALUES (?, ?)",
                (group_id, student_id),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        if "PRIMARY KEY" in str(e) or "UNIQUE" in str(e):
            logger.warning(
                "add_member: %s already in group #%d", student_id, group_id)
            raise ValidationError(
                f"{student_id} is already a member of this group") from e
        logger.exception("add_member DB error")
        raise ValidationError(f"Database error: {e}") from e

    logger.info(
        "Added student %s to class group #%d (%s)",
        student_id, group_id, group.group_name,
    )
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM class_group_students "
            "WHERE group_id = ? AND student_id = ?",
            (group_id, student_id),
        ).fetchone()
    return ClassGroupMember(
        group_id=row["group_id"],
        student_id=row["student_id"],
        joined_at=row["joined_at"],
    )


def remove_member(group_id: int, student_id: str) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM class_group_students "
            "WHERE group_id = ? AND student_id = ?",
            (group_id, student_id),
        )
        conn.commit()
        if cur.rowcount:
            logger.info(
                "Removed student %s from class group #%d",
                student_id, group_id,
            )
            return True
        logger.warning(
            "remove_member: %s not in group #%d", student_id, group_id)
        return False


def groups_for_student(student_id: str) -> list[ClassGroup]:
    """Return every class group this student belongs to."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT cg.* FROM class_groups cg
               JOIN class_group_students cgs ON cgs.group_id = cg.group_id
               WHERE cgs.student_id = ?
               ORDER BY cg.course_id, cg.group_name""",
            (student_id,),
        ).fetchall()
        return [_row(r) for r in rows]
