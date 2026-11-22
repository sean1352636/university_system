"""Subjects catalogue for the Primary School System.

One row per subject taught, with a unique short code, a display name,
the phase it is taught in (EYFS / KS1 / KS2 / All), where it sits in the
curriculum (stored in the ``qualification`` column, kept from the
original schema), the owning subject lead's area, an ``is_core`` flag
(English, Maths, Science) and an ``is_active`` flag for soft-deletion.

Hard delete is only allowed while nothing - timetable, lesson plans,
homework, observations or behaviour logs - points at the subject; see
``is_in_use``.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

KEY_STAGES: tuple[str, ...] = ("EYFS", "KS1", "KS2", "All")
DEFAULT_KEY_STAGE: str = "All"
#: Where the subject sits in the curriculum. Held in the ``qualification``
#: column (the name the original schema gave it); primary has no
#: qualifications.
QUALIFICATIONS: tuple[str, ...] = (
    "National Curriculum", "EYFS Area of Learning", "RE / RSHE",
    "Enrichment", "Other",
)
DEFAULT_QUALIFICATION: str = "National Curriculum"

_CODE_RE = re.compile(r"^[A-Z0-9]{2,8}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS subjects (
    subject_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    code           TEXT NOT NULL UNIQUE,
    name           TEXT NOT NULL,
    key_stage      TEXT NOT NULL DEFAULT 'All',
    qualification  TEXT NOT NULL DEFAULT 'National Curriculum',
    department     TEXT,
    is_core        INTEGER NOT NULL DEFAULT 0,
    is_active      INTEGER NOT NULL DEFAULT 1,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_subjects_active     ON subjects(is_active);
CREATE INDEX IF NOT EXISTS idx_subjects_key_stage  ON subjects(key_stage);
"""


@dataclass
class Subject:
    subject_id: int
    code: str
    name: str
    key_stage: str
    qualification: str
    department: str | None
    is_core: bool
    is_active: bool
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise subjects table")
        raise
    logger.info("Primary subjects table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> Subject:
    return Subject(
        subject_id=r["subject_id"],
        code=r["code"],
        name=r["name"],
        key_stage=r["key_stage"],
        qualification=r["qualification"],
        department=r["department"],
        is_core=bool(r["is_core"]),
        is_active=bool(r["is_active"]),
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    code = (data.get("code") or "").strip().upper()
    if not code:
        raise ValidationError("Code is required")
    if not _CODE_RE.match(code):
        raise ValidationError(
            "Code must be 2–8 uppercase letters or digits (e.g. MATH, ENGL)")
    out["code"] = code
    name = (data.get("name") or "").strip()
    if not name:
        raise ValidationError("Name is required")
    if len(name) > 64:
        raise ValidationError("Name must be 64 characters or fewer")
    out["name"] = name
    ks = (data.get("key_stage") or DEFAULT_KEY_STAGE).strip()
    if ks not in KEY_STAGES:
        raise ValidationError(
            f"Key stage must be one of {', '.join(KEY_STAGES)}")
    out["key_stage"] = ks
    qual = (data.get("qualification") or DEFAULT_QUALIFICATION).strip()
    if qual not in QUALIFICATIONS:
        raise ValidationError(
            f"Qualification must be one of {', '.join(QUALIFICATIONS)}")
    out["qualification"] = qual
    out["department"] = (data.get("department") or "").strip() or None
    out["is_core"]    = bool(data.get("is_core"))
    is_active = data.get("is_active")
    out["is_active"]  = True if is_active is None else bool(is_active)
    out["notes"]      = (data.get("notes") or "").strip() or None
    return out


def create(data: dict[str, Any]) -> Subject:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT subject_id FROM subjects WHERE code = ?",
                (payload["code"],),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A subject with code {payload['code']!r} already exists")
            cur = conn.execute(
                """INSERT INTO subjects
                       (code, name, key_stage, qualification, department,
                        is_core, is_active, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["code"], payload["name"], payload["key_stage"],
                 payload["qualification"], payload["department"],
                 1 if payload["is_core"] else 0,
                 1 if payload["is_active"] else 0,
                 payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create subject %s", payload["code"])
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info("Created subject #%d %s (%s, %s)",
                rec.subject_id, rec.code, rec.qualification, rec.key_stage)
    return rec


def get(subject_id: int) -> Subject | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM subjects WHERE subject_id = ?", (subject_id,)
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get subject(%s) failed", subject_id)
        raise
    return _row(r) if r else None


def get_by_code(code: str) -> Subject | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM subjects WHERE code = ?",
                ((code or "").strip().upper(),),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_by_code(%s) failed", code)
        raise
    return _row(r) if r else None


def list_all(*, key_stage: str | None = None,
             qualification: str | None = None,
             active_only: bool = False) -> list[Subject]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if key_stage:
        if key_stage not in KEY_STAGES:
            raise ValidationError(
                f"Key-stage filter must be one of {', '.join(KEY_STAGES)}")
        where.append("(key_stage = ? OR key_stage = 'Both')")
        params.append(key_stage)
    if qualification:
        if qualification not in QUALIFICATIONS:
            raise ValidationError(
                f"Qualification filter must be one of "
                f"{', '.join(QUALIFICATIONS)}")
        where.append("qualification = ?")
        params.append(qualification)
    if active_only:
        where.append("is_active = 1")
    sql = "SELECT * FROM subjects"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY name COLLATE NOCASE"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list subjects failed")
        raise
    return [_row(r) for r in rows]


def update(subject_id: int, data: dict[str, Any]) -> Subject:
    init_db()
    existing = get(subject_id)
    if existing is None:
        raise ValidationError(f"No subject #{subject_id}")
    merged = {
        "code":          data.get("code", existing.code),
        "name":          data.get("name", existing.name),
        "key_stage":     data.get("key_stage", existing.key_stage),
        "qualification": data.get("qualification", existing.qualification),
        "department":    data.get("department", existing.department),
        "is_core":       data.get("is_core", existing.is_core),
        "is_active":     data.get("is_active", existing.is_active),
        "notes":         data.get("notes", existing.notes),
    }
    payload = _validate(merged)
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT subject_id FROM subjects "
                "WHERE code = ? AND subject_id <> ?",
                (payload["code"], subject_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A subject with code {payload['code']!r} already exists")
            conn.execute(
                """UPDATE subjects SET
                       code = ?, name = ?, key_stage = ?,
                       qualification = ?, department = ?,
                       is_core = ?, is_active = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE subject_id = ?""",
                (payload["code"], payload["name"], payload["key_stage"],
                 payload["qualification"], payload["department"],
                 1 if payload["is_core"] else 0,
                 1 if payload["is_active"] else 0,
                 payload["notes"], subject_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update subject #%d", subject_id)
        raise
    rec = get(subject_id)
    assert rec is not None
    logger.info("Updated subject #%d %s", rec.subject_id, rec.code)
    return rec


def toggle_active(subject_id: int) -> Subject:
    init_db()
    existing = get(subject_id)
    if existing is None:
        raise ValidationError(f"No subject #{subject_id}")
    new_val = 0 if existing.is_active else 1
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE subjects SET is_active = ?, "
                "updated_at = datetime('now') WHERE subject_id = ?",
                (new_val, subject_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to toggle subject #%d", subject_id)
        raise
    rec = get(subject_id)
    assert rec is not None
    logger.info("Toggled subject #%d %s -> active=%s",
                rec.subject_id, rec.code, rec.is_active)
    return rec


#: Tables that point at a subject by ``subject_id``.
_SUBJECT_USERS: tuple[str, ...] = (
    "timetable_slots", "lesson_plans", "homework_assignments",
    "observations", "behaviour_incidents",
)


def is_in_use(subject_id: int) -> bool:
    """True if the timetable, a lesson plan, homework, an observation or a
    behaviour log references this subject."""
    init_db()
    try:
        with _connect() as conn:
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            for table in _SUBJECT_USERS:
                if table in tables and conn.execute(
                        f"SELECT 1 FROM {table} WHERE subject_id = ? LIMIT 1",  # noqa: S608 - fixed table names
                        (subject_id,)).fetchone():
                    return True
            return False
    except sqlite3.Error:
        logger.exception("is_in_use(%s) failed", subject_id)
        raise


def delete(subject_id: int) -> bool:
    init_db()
    existing = get(subject_id)
    if existing is None:
        return False
    if is_in_use(subject_id):
        raise ValidationError(
            f"Subject {existing.code} is used by the timetable, lesson "
            f"plans, homework or records — deactivate it instead of deleting")
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM subjects WHERE subject_id = ?", (subject_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete subject #%d", subject_id)
        raise
    if deleted:
        logger.info("Deleted subject #%d %s", subject_id, existing.code)
    return deleted


def counts() -> dict[str, int]:
    init_db()
    try:
        with _connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM subjects WHERE is_active = 1"
            ).fetchone()[0]
            core = conn.execute(
                "SELECT COUNT(*) FROM subjects WHERE is_core = 1"
            ).fetchone()[0]
    except sqlite3.Error:
        logger.exception("subject counts failed")
        raise
    return {"total": total, "active": active,
            "inactive": total - active, "core": core}
