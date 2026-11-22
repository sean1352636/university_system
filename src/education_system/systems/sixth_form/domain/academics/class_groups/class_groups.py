"""Class-group data layer for the Sixth Form System.

A *class group* is a teaching set within a course — e.g. Maths Year 12
might have three groups: 12M-1, 12M-2, 12M-3. Each group has a
many-to-many relationship with students through `class_group_students`.

Group-level fields (teacher, room, max_students) override the course's
defaults; leaving them null means "use the course value".

Cascade behaviour:
- Deleting a course removes its class groups (and their memberships).
- Deleting a student removes them from any groups they belong to.
- Hard-deleting a group removes its memberships, slots and — through
  them — attendance, registers and assignments, so :func:`delete_group`
  refuses when any such history exists; :func:`archive_group` hides the
  group instead.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system import paths
from education_system.systems.sixth_form.infrastructure import record_links as _links

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_CLASS_GROUPS_DB

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
    #: When the group was archived (hidden from lists, history kept).
    archived_at: str | None = None


@dataclass
class ClassGroupMember:
    group_id: int
    student_id: str
    joined_at: str


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
    # Ensure the parent tables exist (FKs reference them).
    from education_system.systems.sixth_form.domain.academics.courses import courses as _courses
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    _courses.init_db()
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(class_groups)")}
        if "archived_at" not in cols:
            conn.execute("ALTER TABLE class_groups ADD COLUMN archived_at TEXT")
            logger.info("Class groups: added column archived_at")
        conn.commit()
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
        archived_at=r["archived_at"] if "archived_at" in r.keys() else None,
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
    from education_system.systems.sixth_form.domain.academics.courses import (
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
    include_archived: bool = False,
) -> list[ClassGroup]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if not include_archived:
        clauses.append("archived_at IS NULL")
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


#: Rows that go with a group but are its structure, not its history.
_STRUCTURE_TABLES: frozenset[str] = frozenset({
    "class_group_students", "timetable_slots", "attendance_slot_weeks",
    "optimiser_plan_slots", "class_group_waitlist",
})
#: Tables that hold a class-group id without a foreign key.
_SOFT_REFS: tuple[tuple[str, str], ...] = (
    ("coursework_assignments", "class_group_id"),
    ("lesson_plans", "class_group_id"),
    ("observations", "class_group_id"),
    ("cover_requests", "class_group_id"),
    ("class_resources", "group_id"),
    ("report_card_subjects", "group_id"),
    ("attendance_nudges", "group_id"),
)


class GroupHasHistory(ValidationError):
    """Refused: deleting this class group would destroy recorded history."""

    def __init__(self, group_id: int, counts: dict[str, int]):
        self.group_id = group_id
        self.counts = counts
        super().__init__(
            f"Class group #{group_id} has history that deleting it would "
            f"destroy ({_links.describe(counts)}). Archive the group instead "
            f"— it is hidden from lists and timetables and its history is kept.")


def soft_record_counts(group_id: int) -> dict[str, int]:
    """Rows that hold this group's id without a foreign key — including
    those that hold one of its timetable slots' ids."""
    init_db()
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    with _connect() as conn:
        parts = [_links.soft_counts(conn, _SOFT_REFS, group_id)]
        if _links.has_table(conn, "timetable_slots"):
            slot_ids = [r[0] for r in conn.execute(
                "SELECT slot_id FROM timetable_slots WHERE group_id = ?",
                (group_id,))]
        else:
            slot_ids = []
    parts.extend(_tt.soft_record_counts(sid) for sid in slot_ids)
    return _links.merge(*parts)


def linked_record_counts(group_id: int) -> dict[str, int]:
    """``{table: rows}`` a delete of this group would remove or orphan."""
    init_db()
    with _connect() as conn:
        hard = _links.cascade_counts(conn, "class_groups", "group_id", group_id)
    return _links.merge(hard, soft_record_counts(group_id))


def history_counts(group_id: int) -> dict[str, int]:
    """History (attendance, registers, assignments …) a delete would lose."""
    return {t: n for t, n in linked_record_counts(group_id).items()
            if t not in _STRUCTURE_TABLES}


def delete_group(group_id: int) -> bool:
    """Delete a class group created by mistake.

    Refused with :class:`GroupHasHistory` when attendance, registers,
    assignments or other records would be lost through the cascade — use
    :func:`archive_group` then. Memberships and empty slots go with it.
    """
    init_db()
    history = history_counts(group_id)
    if history:
        logger.warning("delete_group(%d) refused: %s", group_id, history)
        raise GroupHasHistory(group_id, history)
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


def archive_group(group_id: int) -> bool:
    """Hide a group and its timetable slots from lists and timetables,
    keeping its members, attendance and assignments."""
    init_db()
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    _tt.init_db()
    with _connect() as conn:
        stamp = conn.execute("SELECT datetime('now')").fetchone()[0]
        cur = conn.execute(
            "UPDATE class_groups SET archived_at = ? "
            "WHERE group_id = ? AND archived_at IS NULL", (stamp, group_id))
        if cur.rowcount:
            conn.execute(
                "UPDATE timetable_slots SET archived_at = ? "
                "WHERE group_id = ? AND archived_at IS NULL", (stamp, group_id))
        conn.commit()
    if cur.rowcount:
        logger.info("Archived class group #%d", group_id)
    return bool(cur.rowcount)


def restore_group(group_id: int) -> bool:
    """Undo :func:`archive_group` (slots archived with it come back too)."""
    init_db()
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    _tt.init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT archived_at FROM class_groups WHERE group_id = ?",
            (group_id,)).fetchone()
        if row is None or row["archived_at"] is None:
            return False
        conn.execute(
            "UPDATE timetable_slots SET archived_at = NULL "
            "WHERE group_id = ? AND archived_at = ?",
            (group_id, row["archived_at"]))
        conn.execute(
            "UPDATE class_groups SET archived_at = NULL WHERE group_id = ?",
            (group_id,))
        conn.commit()
    logger.info("Restored class group #%d", group_id)
    return True


def delete_or_archive_group(group_id: int) -> str:
    """Delete the group if nothing would be lost, else archive it.
    Returns ``"deleted"``, ``"archived"`` or ``""`` (unknown id)."""
    try:
        return "deleted" if delete_group(group_id) else ""
    except GroupHasHistory:
        return "archived" if archive_group(group_id) else ""


# ── Member management ───────────────────────────────────────────────

def effective_cap(group: ClassGroup) -> int | None:
    """Resolve the group's effective max-students: own override, falling
    back to the parent course's max, or None if neither is set."""
    if group.max_students is not None:
        return group.max_students
    from education_system.systems.sixth_form.domain.academics.courses import (
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
    from education_system.systems.sixth_form.domain.learners.students import (
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


def groups_for_student(student_id: str, *,
                       include_archived: bool = False) -> list[ClassGroup]:
    """Return every (live, unless asked) class group this student belongs to."""
    init_db()
    live = "" if include_archived else " AND cg.archived_at IS NULL"
    with _connect() as conn:
        rows = conn.execute(
            """SELECT cg.* FROM class_groups cg
               JOIN class_group_students cgs ON cgs.group_id = cg.group_id
               WHERE cgs.student_id = ?""" + live + """
               ORDER BY cg.course_id, cg.group_name""",
            (student_id,),
        ).fetchall()
        return [_row(r) for r in rows]
