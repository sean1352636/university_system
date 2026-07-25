"""Assessment records data layer.

One row per (pupil, academic_year, term, subject). Each row carries a
primary-school attainment grade (BLW / WTS / EXS / GDS) and an optional
numeric score (0-100). Multiple entries per pupil per year are
supported — one per term per subject — so the same pupil can have an
Autumn / Spring / Summer arc for the same subject.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.domain.learners.pupils import (
    pupils as pupils_data,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    Pupil, ValidationError, YEAR_GROUPS,
    _connect as _pupils_connect, _DOB_RE,
)

logger = logging.getLogger(__name__)

TERMS: tuple[str, ...] = ("Autumn", "Spring", "Summer")
GRADES: tuple[str, ...] = ("BLW", "WTS", "EXS", "GDS")
GRADE_LABELS: dict[str, str] = {
    "BLW": "Below — working below expected standard",
    "WTS": "Working Towards expected standard",
    "EXS": "Expected Standard",
    "GDS": "Greater Depth Standard",
}
# Numeric order for averaging/sorting.
GRADE_RANK: dict[str, int] = {"BLW": 1, "WTS": 2, "EXS": 3, "GDS": 4}

_ACADEMIC_YEAR_RE = re.compile(r"^\d{4}(-\d{2}|-\d{4})?$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS assessment_records (
    assessment_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id        TEXT NOT NULL,
    academic_year   TEXT NOT NULL,
    term            TEXT NOT NULL,
    subject         TEXT NOT NULL,
    grade           TEXT NOT NULL,
    score           REAL,
    assessed_on     TEXT,
    comment         TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(pupil_id, academic_year, term, subject),
    FOREIGN KEY(pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_assess_pupil    ON assessment_records(pupil_id);
CREATE INDEX IF NOT EXISTS idx_assess_year     ON assessment_records(academic_year);
CREATE INDEX IF NOT EXISTS idx_assess_subject  ON assessment_records(subject);
"""


@dataclass
class AssessmentRecord:
    assessment_id: int
    pupil_id: str
    academic_year: str
    term: str
    subject: str
    grade: str
    score: float | None
    assessed_on: str | None
    comment: str | None
    created_at: str | None = None
    updated_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    pupils_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise assessment_records table")
        raise
    logger.info("Primary assessment_records table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> AssessmentRecord:
    return AssessmentRecord(
        assessment_id=r["assessment_id"],
        pupil_id=r["pupil_id"],
        academic_year=r["academic_year"],
        term=r["term"],
        subject=r["subject"],
        grade=r["grade"],
        score=r["score"],
        assessed_on=r["assessed_on"],
        comment=r["comment"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    out["pupil_id"] = pid
    ay = (data.get("academic_year") or "").strip()
    if not ay:
        raise ValidationError("Academic year is required (e.g. 2025-26)")
    if not _ACADEMIC_YEAR_RE.match(ay):
        raise ValidationError("Academic year must look like 2025 or 2025-26")
    out["academic_year"] = ay
    term = (data.get("term") or "").strip().title()
    if not term:
        raise ValidationError("Term is required")
    if term not in TERMS:
        raise ValidationError(f"Term must be one of {', '.join(TERMS)}")
    out["term"] = term
    subj = (data.get("subject") or "").strip()
    if not subj:
        raise ValidationError("Subject is required")
    if len(subj) > 64:
        raise ValidationError("Subject must be 64 characters or fewer")
    out["subject"] = subj
    grade = (data.get("grade") or "").strip().upper()
    if not grade:
        raise ValidationError("Grade is required")
    if grade not in GRADES:
        raise ValidationError(f"Grade must be one of {', '.join(GRADES)}")
    out["grade"] = grade
    score_raw = data.get("score")
    if score_raw in (None, ""):
        out["score"] = None
    else:
        try:
            score = float(score_raw)
        except (TypeError, ValueError) as e:
            raise ValidationError("Score must be a number") from e
        if not (0.0 <= score <= 100.0):
            raise ValidationError("Score must be between 0 and 100")
        out["score"] = score
    assessed_on = (data.get("assessed_on") or "").strip()
    if assessed_on and not _DOB_RE.match(assessed_on):
        raise ValidationError("Assessed-on date must be YYYY-MM-DD")
    out["assessed_on"] = assessed_on or None
    out["comment"] = (data.get("comment") or "").strip() or None
    return out


def create(data: dict[str, Any]) -> AssessmentRecord:
    init_db()
    payload = _validate(data)
    if pupils_data.get_pupil(payload["pupil_id"]) is None:
        raise ValidationError(f"No pupil with id {payload['pupil_id']}")
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT assessment_id FROM assessment_records "
                "WHERE pupil_id = ? AND academic_year = ? AND term = ? "
                "AND subject = ?",
                (payload["pupil_id"], payload["academic_year"],
                 payload["term"], payload["subject"]),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"An assessment for pupil {payload['pupil_id']} in "
                    f"{payload['academic_year']} {payload['term']} "
                    f"{payload['subject']!r} already exists "
                    f"(#{dup['assessment_id']})")
            cur = conn.execute(
                """INSERT INTO assessment_records
                       (pupil_id, academic_year, term, subject, grade,
                        score, assessed_on, comment)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["pupil_id"], payload["academic_year"],
                 payload["term"], payload["subject"], payload["grade"],
                 payload["score"], payload["assessed_on"], payload["comment"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create assessment record")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info("Created assessment #%d (pupil %s, %s %s, %s -> %s)",
                rec.assessment_id, rec.pupil_id, rec.academic_year,
                rec.term, rec.subject, rec.grade)
    return rec


def get(assessment_id: int) -> AssessmentRecord | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM assessment_records WHERE assessment_id = ?",
                (assessment_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get assessment(%s) failed", assessment_id)
        raise
    return _row(r) if r else None


def update(assessment_id: int, data: dict[str, Any]) -> AssessmentRecord:
    init_db()
    existing = get(assessment_id)
    if existing is None:
        raise ValidationError(f"No assessment record #{assessment_id}")
    merged = {
        "pupil_id":      data.get("pupil_id", existing.pupil_id),
        "academic_year": data.get("academic_year", existing.academic_year),
        "term":          data.get("term", existing.term),
        "subject":       data.get("subject", existing.subject),
        "grade":         data.get("grade", existing.grade),
        "score":         data.get("score", existing.score),
        "assessed_on":   data.get("assessed_on", existing.assessed_on),
        "comment":       data.get("comment", existing.comment),
    }
    payload = _validate(merged)
    if pupils_data.get_pupil(payload["pupil_id"]) is None:
        raise ValidationError(f"No pupil with id {payload['pupil_id']}")
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT assessment_id FROM assessment_records "
                "WHERE pupil_id = ? AND academic_year = ? AND term = ? "
                "AND subject = ? AND assessment_id <> ?",
                (payload["pupil_id"], payload["academic_year"],
                 payload["term"], payload["subject"], assessment_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"Another assessment for that pupil / year / term / "
                    f"subject already exists (#{dup['assessment_id']})")
            conn.execute(
                """UPDATE assessment_records SET
                       pupil_id = ?, academic_year = ?, term = ?,
                       subject = ?, grade = ?, score = ?,
                       assessed_on = ?, comment = ?,
                       updated_at = datetime('now')
                   WHERE assessment_id = ?""",
                (payload["pupil_id"], payload["academic_year"],
                 payload["term"], payload["subject"], payload["grade"],
                 payload["score"], payload["assessed_on"], payload["comment"],
                 assessment_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update assessment #%d", assessment_id)
        raise
    rec = get(assessment_id)
    assert rec is not None
    logger.info("Updated assessment #%d", assessment_id)
    return rec


def delete(assessment_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM assessment_records WHERE assessment_id = ?",
                (assessment_id,),
            )
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete assessment #%d", assessment_id)
        raise
    if deleted:
        logger.info("Deleted assessment record #%d", assessment_id)
    return deleted


def list_records(
    *, academic_year: str | None = None,
    term: str | None = None,
    subject: str | None = None,
    grade: str | None = None,
    pupil_id: str | None = None,
    year_group: str | None = None,
) -> list[tuple[AssessmentRecord, Pupil | None]]:
    init_db()
    if term is not None and term not in TERMS:
        raise ValidationError(f"Term filter must be one of {', '.join(TERMS)}")
    if grade is not None and grade not in GRADES:
        raise ValidationError(
            f"Grade filter must be one of {', '.join(GRADES)}")
    if year_group is not None and year_group not in YEAR_GROUPS:
        raise ValidationError(
            f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
    where: list[str] = []
    params: list[Any] = []
    if academic_year:
        where.append("academic_year = ?")
        params.append(academic_year.strip())
    if term:
        where.append("term = ?")
        params.append(term)
    if subject:
        where.append("subject = ?")
        params.append(subject.strip())
    if grade:
        where.append("grade = ?")
        params.append(grade)
    if pupil_id:
        where.append("pupil_id = ?")
        params.append(pupil_id.strip())
    sql = "SELECT * FROM assessment_records"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY academic_year DESC, term, subject, pupil_id"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    out: list[tuple[AssessmentRecord, Pupil | None]] = []
    for r in rows:
        rec = _row(r)
        p = pupils_data.get_pupil(rec.pupil_id)
        if year_group and (p is None or p.year_group != year_group):
            continue
        out.append((rec, p))
    return out


def list_for_pupil(pupil_id: str) -> list[AssessmentRecord]:
    init_db()
    if pupils_data.get_pupil(pupil_id) is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM assessment_records WHERE pupil_id = ? "
                "ORDER BY academic_year DESC, term, subject",
                (pupil_id,),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_for_pupil(%s) failed", pupil_id)
        raise
    return [_row(r) for r in rows]


def known_years() -> list[str]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT academic_year FROM assessment_records "
                "ORDER BY academic_year DESC"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("known_years failed")
        raise
    return [r["academic_year"] for r in rows]


def known_subjects() -> list[str]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT subject FROM assessment_records "
                "ORDER BY subject COLLATE NOCASE"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("known_subjects failed")
        raise
    return [r["subject"] for r in rows]


def grade_summary(
    *, academic_year: str | None = None,
    term: str | None = None,
    subject: str | None = None,
) -> dict[str, Any]:
    init_db()
    records = list_records(
        academic_year=academic_year, term=term, subject=subject,
    )
    total = len(records)
    by_grade = {g: 0 for g in GRADES}
    score_total = 0.0
    score_count = 0
    for rec, _p in records:
        by_grade[rec.grade] = by_grade.get(rec.grade, 0) + 1
        if rec.score is not None:
            score_total += rec.score
            score_count += 1
    avg = (score_total / score_count) if score_count else None
    above_exs = by_grade["EXS"] + by_grade["GDS"]
    return {
        "total": total,
        "by_grade": by_grade,
        "at_or_above_exs": above_exs,
        "at_or_above_exs_pct": (above_exs / total * 100.0) if total else 0.0,
        "average_score": avg,
    }
