"""Target-grade data layer for the Secondary School System.

One row per (pupil, subject). Each row holds:

* ``target_grade``           — the headline working target (1–9 GCSE
                                or KS3 grade label).
* ``minimum_grade``          — floor / "must achieve".
* ``aspirational_grade``     — stretch target.
* ``source``                 — where the target came from (e.g. CAT4,
                                MidYIS, Teacher, Baseline).

The grade strings are validated as 1–3 chars from a permissive set so
both KS3 working grades ("WT", "WA", "GD") and GCSE 9–1 (or legacy
letter grades) are accepted.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

GRADE_SOURCES: tuple[str, ...] = (
    "CAT4", "MidYIS", "YELLIS", "KS2", "Baseline",
    "Teacher", "FFT", "Other")
DEFAULT_SOURCE: str = "Teacher"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_GRADE_RE = re.compile(r"^[A-Za-z0-9*+\-]{1,3}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS target_grades (
    target_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id           TEXT NOT NULL,
    subject_id         INTEGER NOT NULL,
    target_grade       TEXT NOT NULL,
    minimum_grade      TEXT,
    aspirational_grade TEXT,
    source             TEXT NOT NULL DEFAULT 'Teacher',
    set_by             TEXT,
    set_date           TEXT NOT NULL DEFAULT (date('now')),
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    UNIQUE (pupil_id, subject_id),
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
);

CREATE INDEX IF NOT EXISTS idx_tg_pupil ON target_grades(pupil_id);
CREATE INDEX IF NOT EXISTS idx_tg_subject ON target_grades(subject_id);
"""


@dataclass
class TargetGrade:
    target_id: int
    pupil_id: str
    subject_id: int
    target_grade: str
    minimum_grade: str | None
    aspirational_grade: str | None
    source: str
    set_by: str | None
    set_date: str
    notes: str | None
    subject_code: str | None = None
    subject_name: str | None = None
    pupil_name: str | None = None
    pupil_year: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.secondarysch_system.modules.domain.academics.subjects import (
        subjects as subjects_data,
    )
    subjects_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise target_grades table")
        raise
    logger.info("Secondary target_grades table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> TargetGrade:
    keys = r.keys()
    return TargetGrade(
        target_id=r["target_id"], pupil_id=r["pupil_id"],
        subject_id=r["subject_id"], target_grade=r["target_grade"],
        minimum_grade=r["minimum_grade"],
        aspirational_grade=r["aspirational_grade"],
        source=r["source"], set_by=r["set_by"],
        set_date=r["set_date"], notes=r["notes"],
        subject_code=r["subject_code"] if "subject_code" in keys else None,
        subject_name=r["subject_name"] if "subject_name" in keys else None,
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_grade(value: Any, label: str, *,
                    required: bool = True) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if not _GRADE_RE.match(s):
        raise ValidationError(
            f"{label} must be 1–3 chars (letters/digits/* + -)")
    return s


def _validate_date(value: Any, label: str = "Set date") -> str:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return _dt.date.today().isoformat()
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    from education_system.secondarysch_system.modules.domain.pupils.pupils import (
        pupils as pupils_data,
    )
    if pupils_data.get_pupil(pid) is None:
        raise ValidationError(f"No pupil with id {pid}")
    out["pupil_id"] = pid

    sid = data.get("subject_id")
    if sid in (None, ""):
        raise ValidationError("Subject is required")
    try:
        out["subject_id"] = int(sid)
    except (TypeError, ValueError):
        raise ValidationError("Subject ID must be a number") from None
    from education_system.secondarysch_system.modules.domain.academics.subjects import (
        subjects as subjects_data,
    )
    if subjects_data.get(out["subject_id"]) is None:
        raise ValidationError(f"No subject #{out['subject_id']}")

    out["target_grade"]       = _validate_grade(
        data.get("target_grade"), "Target grade")
    out["minimum_grade"]      = _validate_grade(
        data.get("minimum_grade"), "Minimum grade", required=False)
    out["aspirational_grade"] = _validate_grade(
        data.get("aspirational_grade"), "Aspirational grade",
        required=False)

    src = (data.get("source") or DEFAULT_SOURCE).strip()
    if src not in GRADE_SOURCES:
        raise ValidationError(
            f"Source must be one of {', '.join(GRADE_SOURCES)}")
    out["source"]   = src
    out["set_by"]   = (data.get("set_by") or "").strip() or None
    out["set_date"] = _validate_date(data.get("set_date"))
    out["notes"]    = (data.get("notes") or "").strip() or None
    return out


def upsert(data: dict[str, Any]) -> TargetGrade:
    """Insert or update the (pupil, subject) target grade."""
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT target_id FROM target_grades "
                "WHERE pupil_id = ? AND subject_id = ?",
                (payload["pupil_id"], payload["subject_id"]),
            ).fetchone()
            if row:
                conn.execute(
                    """UPDATE target_grades SET
                           target_grade = ?, minimum_grade = ?,
                           aspirational_grade = ?, source = ?,
                           set_by = ?, set_date = ?, notes = ?,
                           updated_at = datetime('now')
                       WHERE target_id = ?""",
                    (payload["target_grade"], payload["minimum_grade"],
                     payload["aspirational_grade"], payload["source"],
                     payload["set_by"], payload["set_date"],
                     payload["notes"], row["target_id"]),
                )
                tid = row["target_id"]
                action = "updated"
            else:
                cur = conn.execute(
                    """INSERT INTO target_grades
                           (pupil_id, subject_id, target_grade,
                            minimum_grade, aspirational_grade,
                            source, set_by, set_date, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (payload["pupil_id"], payload["subject_id"],
                     payload["target_grade"], payload["minimum_grade"],
                     payload["aspirational_grade"], payload["source"],
                     payload["set_by"], payload["set_date"],
                     payload["notes"]),
                )
                tid = cur.lastrowid
                action = "inserted"
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to upsert target for pupil %s subject %d",
            payload["pupil_id"], payload["subject_id"])
        raise
    rec = get(tid)
    assert rec is not None
    logger.info("Target %s: pupil=%s subject=#%d target=%s source=%s",
                action, rec.pupil_id, rec.subject_id,
                rec.target_grade, rec.source)
    return rec


def get(target_id: int) -> TargetGrade | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT t.*, s.code AS subject_code, s.name AS subject_name,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM target_grades t
                   LEFT JOIN subjects s ON s.subject_id = t.subject_id
                   LEFT JOIN pupils p ON p.pupil_id = t.pupil_id
                   WHERE t.target_id = ?""",
                (target_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", target_id)
        raise
    return _row(r) if r else None


def get_for(pupil_id: str, subject_id: int) -> TargetGrade | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT t.*, s.code AS subject_code, s.name AS subject_name,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM target_grades t
                   LEFT JOIN subjects s ON s.subject_id = t.subject_id
                   LEFT JOIN pupils p ON p.pupil_id = t.pupil_id
                   WHERE t.pupil_id = ? AND t.subject_id = ?""",
                ((pupil_id or "").strip(), int(subject_id)),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_for(%s, %s) failed", pupil_id, subject_id)
        raise
    return _row(r) if r else None


def list_targets(*, year_group: str | None = None,
                 subject_id: int | None = None,
                 pupil_id: str | None = None,
                 source: str | None = None) -> list[TargetGrade]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("p.year_group = ?")
        params.append(year_group)
    if subject_id is not None:
        where.append("t.subject_id = ?")
        params.append(int(subject_id))
    if pupil_id:
        where.append("t.pupil_id = ?")
        params.append(pupil_id.strip())
    if source:
        if source not in GRADE_SOURCES:
            raise ValidationError(
                f"Source filter must be one of "
                f"{', '.join(GRADE_SOURCES)}")
        where.append("t.source = ?")
        params.append(source)
    sql = ("""SELECT t.*, s.code AS subject_code, s.name AS subject_name,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM target_grades t
              LEFT JOIN subjects s ON s.subject_id = t.subject_id
              LEFT JOIN pupils p ON p.pupil_id = t.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY p.year_group, p.last_name, s.name"
    try:
        with _connect() as conn:
            return [_row(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_targets failed")
        raise


def delete(target_id: int) -> bool:
    init_db()
    existing = get(target_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM target_grades WHERE target_id = ?",
                (target_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete target #%d", target_id)
        raise
    if deleted:
        logger.info("Deleted target #%d (pupil %s subject #%d)",
                    target_id, existing.pupil_id, existing.subject_id)
    return deleted


def distribution(*, year_group: str | None = None,
                 subject_id: int | None = None) -> dict[str, int]:
    rows = list_targets(year_group=year_group, subject_id=subject_id)
    return dict(Counter(r.target_grade for r in rows))
