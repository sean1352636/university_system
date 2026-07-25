"""Gradebook data layer for the Secondary School System.

One row per recorded mark for a pupil in a subject. Entries are tagged
with an assessment name, type and term so the same gradebook can hold
formative quizzes, summative tests, mocks, classwork, etc. Marks
support both numeric (with max_marks) and grade-string records.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

ASSESSMENT_TYPES: tuple[str, ...] = (
    "Test", "Quiz", "Essay", "Mock", "Coursework", "Project",
    "Classwork", "Homework", "Other")
DEFAULT_TYPE: str = "Test"

TERMS: tuple[str, ...] = ("Autumn", "Spring", "Summer", "Ongoing")
DEFAULT_TERM: str = "Autumn"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_GRADE_RE = re.compile(r"^[A-Za-z0-9*+\-]{1,3}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gradebook_entries (
    entry_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id          TEXT NOT NULL,
    subject_id        INTEGER NOT NULL,
    assessment_name   TEXT NOT NULL,
    assessment_type   TEXT NOT NULL DEFAULT 'Test',
    term              TEXT NOT NULL DEFAULT 'Autumn',
    assessment_date   TEXT NOT NULL DEFAULT (date('now')),
    marks_awarded     REAL,
    max_marks         REAL,
    mark_pct          REAL,
    grade             TEXT,
    teacher           TEXT,
    comments          TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    UNIQUE (pupil_id, subject_id, assessment_name, assessment_date),
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
);

CREATE INDEX IF NOT EXISTS idx_gb_pupil ON gradebook_entries(pupil_id);
CREATE INDEX IF NOT EXISTS idx_gb_subject
    ON gradebook_entries(subject_id);
CREATE INDEX IF NOT EXISTS idx_gb_term ON gradebook_entries(term);
"""


@dataclass
class GradebookEntry:
    entry_id: int
    pupil_id: str
    subject_id: int
    assessment_name: str
    assessment_type: str
    term: str
    assessment_date: str
    marks_awarded: float | None
    max_marks: float | None
    mark_pct: float | None
    grade: str | None
    teacher: str | None
    comments: str | None
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
    from education_system.systems.secondary.domain.academics.subjects import (
        subjects as subjects_data,
    )
    subjects_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise gradebook table")
        raise
    logger.info("Secondary gradebook table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> GradebookEntry:
    keys = r.keys()
    return GradebookEntry(
        entry_id=r["entry_id"], pupil_id=r["pupil_id"],
        subject_id=r["subject_id"],
        assessment_name=r["assessment_name"],
        assessment_type=r["assessment_type"], term=r["term"],
        assessment_date=r["assessment_date"],
        marks_awarded=r["marks_awarded"], max_marks=r["max_marks"],
        mark_pct=r["mark_pct"], grade=r["grade"],
        teacher=r["teacher"], comments=r["comments"],
        subject_code=r["subject_code"] if "subject_code" in keys else None,
        subject_name=r["subject_name"] if "subject_name" in keys else None,
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_date(value: Any, label: str) -> str:
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
    from education_system.systems.secondary.domain.learners.pupils import (
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
    from education_system.systems.secondary.domain.academics.subjects import (
        subjects as subjects_data,
    )
    if subjects_data.get(out["subject_id"]) is None:
        raise ValidationError(f"No subject #{out['subject_id']}")

    name = (data.get("assessment_name") or "").strip()
    if not name:
        raise ValidationError("Assessment name is required")
    if len(name) > 80:
        raise ValidationError(
            "Assessment name must be 80 characters or fewer")
    out["assessment_name"] = name

    atype = (data.get("assessment_type") or DEFAULT_TYPE).strip()
    if atype not in ASSESSMENT_TYPES:
        raise ValidationError(
            f"Assessment type must be one of "
            f"{', '.join(ASSESSMENT_TYPES)}")
    out["assessment_type"] = atype

    term = (data.get("term") or DEFAULT_TERM).strip()
    if term not in TERMS:
        raise ValidationError(
            f"Term must be one of {', '.join(TERMS)}")
    out["term"] = term
    out["assessment_date"] = _validate_date(
        data.get("assessment_date"), "Assessment date")

    def _opt_float(value, label, *, mn, mx):
        if value in (None, "") or (isinstance(value, str)
                                    and not value.strip()):
            return None
        try:
            v = float(value)
        except (TypeError, ValueError):
            raise ValidationError(f"{label} must be a number") from None
        if v < mn or v > mx:
            raise ValidationError(
                f"{label} must be between {mn} and {mx}")
        return v

    out["max_marks"] = _opt_float(data.get("max_marks"),
                                    "Max marks", mn=0, mx=10000)
    marks = _opt_float(data.get("marks_awarded"),
                        "Marks awarded", mn=0, mx=10000)
    if (marks is not None and out["max_marks"] is not None
            and marks > out["max_marks"]):
        raise ValidationError(
            f"Marks awarded ({marks}) exceeds max marks "
            f"({out['max_marks']})")
    out["marks_awarded"] = marks

    if marks is not None and out["max_marks"]:
        out["mark_pct"] = round(100.0 * marks / out["max_marks"], 2)
    else:
        out["mark_pct"] = None

    grade = (data.get("grade") or "").strip()
    if grade:
        if not _GRADE_RE.match(grade):
            raise ValidationError(
                "Grade must be 1–3 chars (letters/digits/* + -)")
        out["grade"] = grade
    else:
        out["grade"] = None

    out["teacher"]  = (data.get("teacher") or "").strip() or None
    out["comments"] = (data.get("comments") or "").strip() or None
    if (out["marks_awarded"] is None and out["grade"] is None):
        raise ValidationError(
            "Either marks_awarded (with max_marks) or grade must be set")
    return out


def upsert_entry(data: dict[str, Any]) -> GradebookEntry:
    """Insert or update on (pupil, subject, assessment_name, date)."""
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT entry_id FROM gradebook_entries "
                "WHERE pupil_id = ? AND subject_id = ? "
                "  AND assessment_name = ? AND assessment_date = ?",
                (payload["pupil_id"], payload["subject_id"],
                 payload["assessment_name"], payload["assessment_date"]),
            ).fetchone()
            if row:
                conn.execute(
                    """UPDATE gradebook_entries SET
                           assessment_type = ?, term = ?,
                           marks_awarded = ?, max_marks = ?,
                           mark_pct = ?, grade = ?, teacher = ?,
                           comments = ?, updated_at = datetime('now')
                       WHERE entry_id = ?""",
                    (payload["assessment_type"], payload["term"],
                     payload["marks_awarded"], payload["max_marks"],
                     payload["mark_pct"], payload["grade"],
                     payload["teacher"], payload["comments"],
                     row["entry_id"]),
                )
                eid = row["entry_id"]
                action = "updated"
            else:
                cur = conn.execute(
                    """INSERT INTO gradebook_entries
                           (pupil_id, subject_id, assessment_name,
                            assessment_type, term, assessment_date,
                            marks_awarded, max_marks, mark_pct,
                            grade, teacher, comments)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (payload["pupil_id"], payload["subject_id"],
                     payload["assessment_name"],
                     payload["assessment_type"], payload["term"],
                     payload["assessment_date"],
                     payload["marks_awarded"], payload["max_marks"],
                     payload["mark_pct"], payload["grade"],
                     payload["teacher"], payload["comments"]),
                )
                eid = cur.lastrowid
                action = "inserted"
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to upsert gradebook entry for %s / %d / %r",
            payload["pupil_id"], payload["subject_id"],
            payload["assessment_name"])
        raise
    logger.info(
        "Gradebook %s: pupil=%s subject=#%d %r [%s] marks=%s pct=%s grade=%s",
        action, payload["pupil_id"], payload["subject_id"],
        payload["assessment_name"], payload["term"],
        payload["marks_awarded"], payload["mark_pct"], payload["grade"])
    rec = get_entry(eid)
    assert rec is not None
    return rec


def get_entry(entry_id: int) -> GradebookEntry | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT e.*, s.code AS subject_code,
                          s.name AS subject_name,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM gradebook_entries e
                   LEFT JOIN subjects s ON s.subject_id = e.subject_id
                   LEFT JOIN pupils p ON p.pupil_id = e.pupil_id
                   WHERE e.entry_id = ?""",
                (entry_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_entry(%s) failed", entry_id)
        raise
    return _row(r) if r else None


def list_entries(*, pupil_id: str | None = None,
                 subject_id: int | None = None,
                 year_group: str | None = None,
                 term: str | None = None,
                 assessment_type: str | None = None,
                 date_from: str | None = None,
                 date_to: str | None = None) -> list[GradebookEntry]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if pupil_id:
        where.append("e.pupil_id = ?")
        params.append(pupil_id.strip())
    if subject_id is not None:
        where.append("e.subject_id = ?")
        params.append(int(subject_id))
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("p.year_group = ?")
        params.append(year_group)
    if term:
        if term not in TERMS:
            raise ValidationError(
                f"Term filter must be one of {', '.join(TERMS)}")
        where.append("e.term = ?")
        params.append(term)
    if assessment_type:
        if assessment_type not in ASSESSMENT_TYPES:
            raise ValidationError(
                f"Type filter must be one of "
                f"{', '.join(ASSESSMENT_TYPES)}")
        where.append("e.assessment_type = ?")
        params.append(assessment_type)
    if date_from:
        where.append("e.assessment_date >= ?")
        params.append(_validate_date(date_from, "From date"))
    if date_to:
        where.append("e.assessment_date <= ?")
        params.append(_validate_date(date_to, "To date"))
    sql = ("""SELECT e.*, s.code AS subject_code,
                     s.name AS subject_name,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM gradebook_entries e
              LEFT JOIN subjects s ON s.subject_id = e.subject_id
              LEFT JOIN pupils p ON p.pupil_id = e.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY e.assessment_date DESC, e.entry_id DESC"
    try:
        with _connect() as conn:
            return [_row(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_entries failed")
        raise


def delete_entry(entry_id: int) -> bool:
    init_db()
    existing = get_entry(entry_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM gradebook_entries WHERE entry_id = ?",
                (entry_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete gradebook entry #%d",
                         entry_id)
        raise
    if deleted:
        logger.info("Deleted gradebook entry #%d (pupil %s %r)",
                    entry_id, existing.pupil_id,
                    existing.assessment_name)
    return deleted


def pupil_subject_summary(pupil_id: str,
                          subject_id: int) -> dict[str, Any]:
    """Average mark % and recent grade for a pupil in one subject."""
    rows = list_entries(pupil_id=pupil_id, subject_id=subject_id)
    pcts = [r.mark_pct for r in rows if r.mark_pct is not None]
    avg = round(sum(pcts) / len(pcts), 2) if pcts else None
    latest_grade: str | None = None
    for r in rows:  # already sorted DESC by date
        if r.grade:
            latest_grade = r.grade
            break
    by_term = Counter(r.term for r in rows)
    return {
        "pupil_id":     (pupil_id or "").strip(),
        "subject_id":   subject_id,
        "count":        len(rows),
        "avg_pct":      avg,
        "latest_grade": latest_grade,
        "by_term":      {t: by_term.get(t, 0) for t in TERMS},
        "entries":      rows,
    }


def assessment_summary(subject_id: int, assessment_name: str,
                       assessment_date: str) -> dict[str, Any]:
    """Cohort stats for one specific assessment row across pupils."""
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                """SELECT e.*, s.code AS subject_code,
                          s.name AS subject_name,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM gradebook_entries e
                   LEFT JOIN subjects s ON s.subject_id = e.subject_id
                   LEFT JOIN pupils p ON p.pupil_id = e.pupil_id
                   WHERE e.subject_id = ?
                     AND e.assessment_name = ?
                     AND e.assessment_date = ?
                   ORDER BY e.mark_pct DESC, e.pupil_id""",
                (int(subject_id), assessment_name.strip(),
                 _validate_date(assessment_date, "Assessment date")),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("assessment_summary failed")
        raise
    entries = [_row(r) for r in rows]
    pcts = [e.mark_pct for e in entries if e.mark_pct is not None]
    avg = round(sum(pcts) / len(pcts), 2) if pcts else None
    grade_dist = Counter(e.grade for e in entries if e.grade)
    return {
        "subject_id":   subject_id,
        "name":         assessment_name,
        "date":         assessment_date,
        "count":        len(entries),
        "avg_pct":      avg,
        "max_pct":      max(pcts) if pcts else None,
        "min_pct":      min(pcts) if pcts else None,
        "grades":       dict(grade_dist),
        "entries":      entries,
    }
