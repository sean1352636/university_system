"""Pupil self-assessment data layer for the Secondary School System.

One row per (pupil, subject, term, academic_year). Captures the
pupil's own 1–5 ratings for confidence / effort / enjoyment, free-text
strengths / areas to improve / goals, plus an optional teacher review
with reviewer + comments and a status workflow:

    Draft → Submitted → Reviewed
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

TERMS: tuple[str, ...] = ("Autumn", "Spring", "Summer", "Ongoing")
DEFAULT_TERM: str = "Autumn"

STATUSES: tuple[str, ...] = ("Draft", "Submitted", "Reviewed")
DEFAULT_STATUS: str = "Draft"

MIN_RATING = 1
MAX_RATING = 5

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_AY_RE = re.compile(r"^\d{4}/\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS self_assessments (
    assessment_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id           TEXT NOT NULL,
    subject_id         INTEGER NOT NULL,
    academic_year      TEXT NOT NULL,
    term               TEXT NOT NULL DEFAULT 'Autumn',
    assessment_date    TEXT NOT NULL DEFAULT (date('now')),
    confidence_level   INTEGER,
    effort_level       INTEGER,
    enjoyment_level    INTEGER,
    strengths          TEXT,
    areas_to_improve   TEXT,
    goals              TEXT,
    status             TEXT NOT NULL DEFAULT 'Draft',
    reviewed_by        TEXT,
    reviewer_comments  TEXT,
    reviewed_date      TEXT,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    UNIQUE (pupil_id, subject_id, academic_year, term),
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
);

CREATE INDEX IF NOT EXISTS idx_sa_pupil
    ON self_assessments(pupil_id);
CREATE INDEX IF NOT EXISTS idx_sa_subject
    ON self_assessments(subject_id);
"""


@dataclass
class SelfAssessment:
    assessment_id: int
    pupil_id: str
    subject_id: int
    academic_year: str
    term: str
    assessment_date: str
    confidence_level: int | None
    effort_level: int | None
    enjoyment_level: int | None
    strengths: str | None
    areas_to_improve: str | None
    goals: str | None
    status: str
    reviewed_by: str | None
    reviewer_comments: str | None
    reviewed_date: str | None
    notes: str | None
    subject_code: str | None = None
    subject_name: str | None = None
    pupil_name: str | None = None
    pupil_year: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def average_rating(self) -> float | None:
        vals = [v for v in (self.confidence_level,
                             self.effort_level,
                             self.enjoyment_level) if v is not None]
        return round(sum(vals) / len(vals), 2) if vals else None


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
        logger.exception("Failed to initialise self_assessments table")
        raise
    logger.info("Secondary self_assessments table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> SelfAssessment:
    keys = r.keys()
    return SelfAssessment(
        assessment_id=r["assessment_id"], pupil_id=r["pupil_id"],
        subject_id=r["subject_id"],
        academic_year=r["academic_year"], term=r["term"],
        assessment_date=r["assessment_date"],
        confidence_level=r["confidence_level"],
        effort_level=r["effort_level"],
        enjoyment_level=r["enjoyment_level"],
        strengths=r["strengths"],
        areas_to_improve=r["areas_to_improve"],
        goals=r["goals"], status=r["status"],
        reviewed_by=r["reviewed_by"],
        reviewer_comments=r["reviewer_comments"],
        reviewed_date=r["reviewed_date"], notes=r["notes"],
        subject_code=r["subject_code"] if "subject_code" in keys else None,
        subject_name=r["subject_name"] if "subject_name" in keys else None,
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_date(value: Any, label: str, *,
                   required: bool = True) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        if required:
            return _dt.date.today().isoformat()
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _opt_rating(value, label):
    if value in (None, "") or (isinstance(value, str)
                                and not value.strip()):
        return None
    try:
        v = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a whole number") from None
    if v < MIN_RATING or v > MAX_RATING:
        raise ValidationError(
            f"{label} must be between {MIN_RATING} and {MAX_RATING}")
    return v


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

    sid_raw = data.get("subject_id")
    if sid_raw in (None, ""):
        raise ValidationError("Subject is required")
    try:
        out["subject_id"] = int(sid_raw)
    except (TypeError, ValueError):
        raise ValidationError("Subject ID must be a number") from None
    from education_system.secondarysch_system.modules.domain.academics.subjects import (
        subjects as subjects_data,
    )
    if subjects_data.get(out["subject_id"]) is None:
        raise ValidationError(f"No subject #{out['subject_id']}")

    ay = (data.get("academic_year") or "").strip()
    if not ay:
        raise ValidationError("Academic year is required (e.g. 2025/26)")
    if not _AY_RE.match(ay):
        raise ValidationError(
            "Academic year must be in form YYYY/YY (e.g. 2025/26)")
    out["academic_year"] = ay

    term = (data.get("term") or DEFAULT_TERM).strip()
    if term not in TERMS:
        raise ValidationError(
            f"Term must be one of {', '.join(TERMS)}")
    out["term"] = term

    out["assessment_date"] = _validate_date(
        data.get("assessment_date"), "Assessment date")

    out["confidence_level"] = _opt_rating(
        data.get("confidence_level"), "Confidence level")
    out["effort_level"]     = _opt_rating(
        data.get("effort_level"), "Effort level")
    out["enjoyment_level"]  = _opt_rating(
        data.get("enjoyment_level"), "Enjoyment level")

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status

    out["strengths"]         = (data.get("strengths") or "").strip() or None
    out["areas_to_improve"]  = (data.get("areas_to_improve") or "").strip() or None
    out["goals"]             = (data.get("goals") or "").strip() or None
    out["reviewed_by"]       = (data.get("reviewed_by") or "").strip() or None
    out["reviewer_comments"] = (data.get("reviewer_comments") or "").strip() or None
    out["reviewed_date"]     = _validate_date(
        data.get("reviewed_date"), "Reviewed date", required=False)
    out["notes"]             = (data.get("notes") or "").strip() or None

    if out["status"] == "Reviewed":
        if not out["reviewed_by"]:
            raise ValidationError(
                "Reviewer is required when status is Reviewed")
        if not out["reviewed_date"]:
            out["reviewed_date"] = _dt.date.today().isoformat()
    if (out["reviewed_date"]
            and out["reviewed_date"] < out["assessment_date"]):
        raise ValidationError(
            "Reviewed date cannot be before assessment date")
    if out["status"] == "Submitted" and all(
            out[k] is None for k in ("confidence_level",
                                      "effort_level",
                                      "enjoyment_level")):
        raise ValidationError(
            "At least one rating is required to submit")
    return out


def upsert(data: dict[str, Any]) -> SelfAssessment:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT assessment_id FROM self_assessments "
                "WHERE pupil_id = ? AND subject_id = ? "
                "  AND academic_year = ? AND term = ?",
                (payload["pupil_id"], payload["subject_id"],
                 payload["academic_year"], payload["term"]),
            ).fetchone()
            cols = ("assessment_date", "confidence_level",
                    "effort_level", "enjoyment_level",
                    "strengths", "areas_to_improve", "goals",
                    "status", "reviewed_by", "reviewer_comments",
                    "reviewed_date", "notes")
            if row:
                conn.execute(
                    "UPDATE self_assessments SET "
                    + ", ".join(f"{c} = ?" for c in cols)
                    + ", updated_at = datetime('now') "
                    "WHERE assessment_id = ?",
                    (*(payload[c] for c in cols),
                     row["assessment_id"]),
                )
                aid = row["assessment_id"]
                action = "updated"
            else:
                cur = conn.execute(
                    "INSERT INTO self_assessments "
                    "(pupil_id, subject_id, academic_year, term, "
                    + ", ".join(cols) + ") VALUES ("
                    + ", ".join(["?"] * (4 + len(cols))) + ")",
                    (payload["pupil_id"], payload["subject_id"],
                     payload["academic_year"], payload["term"],
                     *(payload[c] for c in cols)),
                )
                aid = cur.lastrowid
                action = "inserted"
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to upsert self-assessment for pupil %s subject %d "
            "year %s term %s",
            payload["pupil_id"], payload["subject_id"],
            payload["academic_year"], payload["term"])
        raise
    logger.info(
        "Self-assessment %s: pupil=%s subject=#%d %s/%s status=%s",
        action, payload["pupil_id"], payload["subject_id"],
        payload["academic_year"], payload["term"],
        payload["status"])
    rec = get(aid)
    assert rec is not None
    return rec


def get(assessment_id: int) -> SelfAssessment | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT a.*, s.code AS subject_code,
                          s.name AS subject_name,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM self_assessments a
                   LEFT JOIN subjects s ON s.subject_id = a.subject_id
                   LEFT JOIN pupils p ON p.pupil_id = a.pupil_id
                   WHERE a.assessment_id = ?""",
                (assessment_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", assessment_id)
        raise
    return _row(r) if r else None


def get_for(pupil_id: str, subject_id: int,
            academic_year: str,
            term: str = DEFAULT_TERM) -> SelfAssessment | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT a.*, s.code AS subject_code,
                          s.name AS subject_name,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM self_assessments a
                   LEFT JOIN subjects s ON s.subject_id = a.subject_id
                   LEFT JOIN pupils p ON p.pupil_id = a.pupil_id
                   WHERE a.pupil_id = ? AND a.subject_id = ?
                     AND a.academic_year = ? AND a.term = ?""",
                ((pupil_id or "").strip(), int(subject_id),
                 (academic_year or "").strip(), term),
            ).fetchone()
    except sqlite3.Error:
        logger.exception(
            "get_for(%s, %s, %s, %s) failed",
            pupil_id, subject_id, academic_year, term)
        raise
    return _row(r) if r else None


def list_assessments(*, year_group: str | None = None,
                     pupil_id: str | None = None,
                     subject_id: int | None = None,
                     academic_year: str | None = None,
                     term: str | None = None,
                     status: str | None = None
                     ) -> list[SelfAssessment]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("p.year_group = ?")
        params.append(year_group)
    if pupil_id:
        where.append("a.pupil_id = ?")
        params.append(pupil_id.strip())
    if subject_id is not None:
        where.append("a.subject_id = ?")
        params.append(int(subject_id))
    if academic_year:
        where.append("a.academic_year = ?")
        params.append(academic_year.strip())
    if term:
        if term not in TERMS:
            raise ValidationError(
                f"Term filter must be one of {', '.join(TERMS)}")
        where.append("a.term = ?")
        params.append(term)
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status filter must be one of {', '.join(STATUSES)}")
        where.append("a.status = ?")
        params.append(status)
    sql = ("""SELECT a.*, s.code AS subject_code,
                     s.name AS subject_name,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM self_assessments a
              LEFT JOIN subjects s ON s.subject_id = a.subject_id
              LEFT JOIN pupils p ON p.pupil_id = a.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY a.academic_year DESC, a.assessment_date DESC, "
            "p.last_name, s.name")
    try:
        with _connect() as conn:
            return [_row(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_assessments failed")
        raise


def set_status(assessment_id: int, status: str,
               *, reviewer: str | None = None,
               reviewer_comments: str | None = None
               ) -> SelfAssessment:
    payload: dict[str, Any] = {"status": status}
    if reviewer is not None:
        payload["reviewed_by"] = reviewer
    if reviewer_comments is not None:
        payload["reviewer_comments"] = reviewer_comments
    init_db()
    existing = get(assessment_id)
    if existing is None:
        raise ValidationError(f"No self-assessment #{assessment_id}")
    merged = {k: getattr(existing, k) for k in (
        "pupil_id", "subject_id", "academic_year", "term",
        "assessment_date", "confidence_level", "effort_level",
        "enjoyment_level", "strengths", "areas_to_improve",
        "goals", "status", "reviewed_by", "reviewer_comments",
        "reviewed_date", "notes")}
    merged.update(payload)
    return upsert({**merged, "assessment_id": assessment_id})


def delete(assessment_id: int) -> bool:
    init_db()
    existing = get(assessment_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM self_assessments WHERE assessment_id = ?",
                (assessment_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete self-assessment #%d", assessment_id)
        raise
    if deleted:
        logger.info("Deleted self-assessment #%d (pupil %s)",
                    assessment_id, existing.pupil_id)
    return deleted


def pupil_summary(pupil_id: str,
                   academic_year: str | None = None
                   ) -> dict[str, Any]:
    rows = list_assessments(pupil_id=pupil_id,
                              academic_year=academic_year)

    def _avg(attr: str) -> float | None:
        vals = [getattr(r, attr) for r in rows
                if getattr(r, attr) is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    return {
        "pupil_id":         (pupil_id or "").strip(),
        "academic_year":    academic_year,
        "count":            len(rows),
        "avg_confidence":   _avg("confidence_level"),
        "avg_effort":       _avg("effort_level"),
        "avg_enjoyment":    _avg("enjoyment_level"),
        "by_status":        dict(Counter(r.status for r in rows)),
        "assessments":      rows,
    }


def cohort_summary(*, year_group: str | None = None,
                   academic_year: str | None = None,
                   term: str | None = None) -> dict[str, Any]:
    rows = list_assessments(year_group=year_group,
                              academic_year=academic_year,
                              term=term)

    def _avg(attr: str) -> float | None:
        vals = [getattr(r, attr) for r in rows
                if getattr(r, attr) is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    return {
        "count":          len(rows),
        "avg_confidence": _avg("confidence_level"),
        "avg_effort":     _avg("effort_level"),
        "avg_enjoyment":  _avg("enjoyment_level"),
        "by_status":      dict(Counter(r.status for r in rows)),
        "by_term":        dict(Counter(r.term for r in rows)),
    }
