"""Tutor-group data layer for the Sixth Form System.

Pastoral form groups — distinct from class groups (which are subject-
based teaching sets). The key constraint is *one tutor group per
student*, enforced by `tutor_group_students.student_id` being the
primary key of the membership table.

Cascade rules:
* Delete a tutor group  → membership rows vanish.
* Delete a student      → their membership row vanishes.

The ``assign_student`` helper is move-aware: if the student is already
in some other tutor group, that membership is replaced atomically.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.systems.sixth_form.infrastructure import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.TUTOR_GROUPS_DB

YEAR_GROUPS: tuple[int, ...] = (12, 13)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tutor_groups (
    tutor_group_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE,
    year_group     INTEGER NOT NULL,
    tutor          TEXT,
    co_tutor       TEXT,
    room           TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tutor_group_students (
    student_id     TEXT PRIMARY KEY,
    tutor_group_id INTEGER NOT NULL,
    joined_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (tutor_group_id)
        REFERENCES tutor_groups(tutor_group_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id)
        REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tg_year  ON tutor_groups(year_group);
CREATE INDEX IF NOT EXISTS idx_tg_tutor ON tutor_groups(tutor);
CREATE INDEX IF NOT EXISTS idx_tgs_grp  ON tutor_group_students(tutor_group_id);
"""


@dataclass
class TutorGroup:
    tutor_group_id: int
    name: str
    year_group: int
    tutor: str | None
    co_tutor: str | None
    room: str | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class Membership:
    student_id: str
    tutor_group_id: int
    joined_at: str


# ── DB plumbing ────────────────────────────────────────────────────

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
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Tutor-groups schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_group(r: sqlite3.Row) -> TutorGroup:
    return TutorGroup(
        tutor_group_id=r["tutor_group_id"], name=r["name"],
        year_group=r["year_group"], tutor=r["tutor"],
        co_tutor=r["co_tutor"], room=r["room"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for any invalid tutor-group input."""


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_group_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["name"] = _require(data.get("name"), "Group name").strip()

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

    out["tutor"]    = (data.get("tutor")    or "").strip() or None
    out["co_tutor"] = (data.get("co_tutor") or "").strip() or None
    out["room"]     = (data.get("room")     or "").strip() or None
    out["notes"]    = (data.get("notes")    or "").strip() or None
    return out


# ── Group CRUD ────────────────────────────────────────────────────

def create_group(data: dict[str, Any]) -> TutorGroup:
    init_db()
    try:
        p = _validate_group_payload(data)
    except ValidationError as e:
        logger.warning("create_group validation failed: %s", e)
        raise
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO tutor_groups
                       (name, year_group, tutor, co_tutor, room, notes,
                        created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                (p["name"], p["year_group"], p["tutor"], p["co_tutor"],
                 p["room"], p["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            logger.warning("create_group: duplicate name %s", p["name"])
            raise ValidationError(
                f"Tutor group '{p['name']}' already exists") from e
        logger.exception("create_group DB error")
        raise ValidationError(f"Database error: {e}") from e
    out = get_group(new_id)
    assert out is not None
    logger.info(
        "Created tutor group #%d (%s, Year %d, tutor=%s)",
        new_id, out.name, out.year_group, out.tutor or "—",
    )
    return out


def get_group(tutor_group_id: int) -> TutorGroup | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM tutor_groups WHERE tutor_group_id = ?",
            (tutor_group_id,),
        ).fetchone()
        return _row_group(r) if r else None


def get_group_by_name(name: str) -> TutorGroup | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM tutor_groups WHERE name = ?", (name.strip(),),
        ).fetchone()
        return _row_group(r) if r else None


def list_groups(
    *,
    year_group: int | None = None,
    tutor_like: str | None = None,
) -> list[TutorGroup]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if year_group is not None:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year group must be one of "
                f"{', '.join(str(y) for y in YEAR_GROUPS)}")
        clauses.append("year_group = ?")
        args.append(year_group)
    if tutor_like:
        clauses.append("(tutor LIKE ? OR co_tutor LIKE ?)")
        q = f"%{tutor_like.strip()}%"
        args.extend([q, q])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM tutor_groups {where} "
           "ORDER BY year_group, name")
    with _connect() as conn:
        return [_row_group(r) for r in conn.execute(sql, args).fetchall()]


def update_group(tutor_group_id: int, data: dict[str, Any]) -> TutorGroup:
    init_db()
    existing = get_group(tutor_group_id)
    if existing is None:
        logger.warning("update_group: unknown id %d", tutor_group_id)
        raise ValidationError(f"No tutor group with id {tutor_group_id}")
    p = _validate_group_payload({
        "name":       data.get("name", existing.name),
        "year_group": data.get("year_group", existing.year_group),
        "tutor":      data.get("tutor", existing.tutor),
        "co_tutor":   data.get("co_tutor", existing.co_tutor),
        "room":       data.get("room", existing.room),
        "notes":      data.get("notes", existing.notes),
    })
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE tutor_groups SET
                       name = ?, year_group = ?, tutor = ?, co_tutor = ?,
                       room = ?, notes = ?, updated_at = datetime('now')
                   WHERE tutor_group_id = ?""",
                (p["name"], p["year_group"], p["tutor"], p["co_tutor"],
                 p["room"], p["notes"], tutor_group_id),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            raise ValidationError(
                f"Tutor group '{p['name']}' already exists") from e
        logger.exception("update_group DB error")
        raise ValidationError(f"Database error: {e}") from e
    out = get_group(tutor_group_id)
    assert out is not None
    logger.info("Updated tutor group #%d (%s)", tutor_group_id, out.name)
    return out


def delete_group(tutor_group_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM tutor_groups WHERE tutor_group_id = ?",
            (tutor_group_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted tutor group #%d", tutor_group_id)
            return True
        logger.warning("delete_group: unknown id %d", tutor_group_id)
        return False


# ── Membership ────────────────────────────────────────────────────

def assign_student(student_id: str, tutor_group_id: int) -> Membership:
    """Move-aware: places the student into ``tutor_group_id``,
    replacing any existing membership."""
    init_db()
    sid = student_id.strip()
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    if get_group(tutor_group_id) is None:
        raise ValidationError(f"No tutor group with id {tutor_group_id}")

    with _connect() as conn:
        # SQLite UPSERT on the primary key — clean move semantics.
        conn.execute(
            """INSERT INTO tutor_group_students
                   (student_id, tutor_group_id, joined_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(student_id) DO UPDATE SET
                   tutor_group_id = excluded.tutor_group_id,
                   joined_at      = datetime('now')""",
            (sid, tutor_group_id),
        )
        conn.commit()
        r = conn.execute(
            "SELECT * FROM tutor_group_students WHERE student_id = ?",
            (sid,),
        ).fetchone()
    out = Membership(
        student_id=r["student_id"], tutor_group_id=r["tutor_group_id"],
        joined_at=r["joined_at"],
    )
    logger.info(
        "Assigned student %s to tutor group #%d",
        out.student_id, out.tutor_group_id,
    )
    return out


def unassign_student(student_id: str) -> bool:
    """Remove the student from whatever tutor group they're in."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM tutor_group_students WHERE student_id = ?",
            (student_id.strip(),),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Unassigned student %s from tutor group",
                        student_id)
            return True
        return False


def membership_for_student(student_id: str) -> Membership | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM tutor_group_students WHERE student_id = ?",
            (student_id.strip(),),
        ).fetchone()
        if not r:
            return None
        return Membership(
            student_id=r["student_id"],
            tutor_group_id=r["tutor_group_id"],
            joined_at=r["joined_at"],
        )


def group_for_student(student_id: str) -> TutorGroup | None:
    m = membership_for_student(student_id)
    return get_group(m.tutor_group_id) if m else None


def list_members(tutor_group_id: int) -> list[str]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT student_id FROM tutor_group_students "
            "WHERE tutor_group_id = ? ORDER BY joined_at, student_id",
            (tutor_group_id,),
        ).fetchall()
        return [r["student_id"] for r in rows]


def count_members(tutor_group_id: int) -> int:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT COUNT(*) AS n FROM tutor_group_students "
            "WHERE tutor_group_id = ?",
            (tutor_group_id,),
        ).fetchone()
        return int(r["n"])


def unassigned_students() -> list[str]:
    """Student IDs that aren't in any tutor group."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT student_id FROM students
               WHERE student_id NOT IN
                   (SELECT student_id FROM tutor_group_students)
               ORDER BY student_id"""
        ).fetchall()
        return [r["student_id"] for r in rows]


# ── Summary ───────────────────────────────────────────────────────

@dataclass
class GroupRow:
    group: TutorGroup
    member_count: int


def list_groups_with_counts(**kwargs) -> list[GroupRow]:
    return [GroupRow(group=g, member_count=count_members(g.tutor_group_id))
            for g in list_groups(**kwargs)]


@dataclass
class Summary:
    total_groups: int
    by_year: dict[int, int]
    total_students: int
    assigned_students: int
    unassigned_students: int


def summary() -> Summary:
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    init_db()
    groups = list_groups()
    by_year: dict[int, int] = {}
    for g in groups:
        by_year[g.year_group] = by_year.get(g.year_group, 0) + 1
    total_students = len(_students.list_students())
    unassigned = len(unassigned_students())
    return Summary(
        total_groups=len(groups),
        by_year=by_year,
        total_students=total_students,
        assigned_students=total_students - unassigned,
        unassigned_students=unassigned,
    )
