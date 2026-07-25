"""Baseline Assessment — diagnostic results per student per subject.

One row per (student, subject, assessment_type) — the initial reading
that the rest of the year's targets and predictions are anchored
against. Typical sources: GCSE results, CAT4, MidYIS / ALIS / Yellis,
an initial subject test in the first weeks of term, or a transition
diagnostic.

The same student can have multiple baseline records per subject (one
for GCSE, one for CAT4, one for the initial test) — they coexist; the
target-setting module decides which to anchor to.

Cascade: deleting a student wipes their baselines.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.systems.sixth_form.infrastructure import paths
from education_system.systems.sixth_form.domain.assessment.baseline_assessment import (
    baseline_assessment as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.BASELINE_ASSESSMENT_DB


ASSESSMENT_TYPES: tuple[str, ...] = (
    "GCSE Result",
    "Average GCSE",
    "Initial Test",
    "CAT4",
    "MidYIS",
    "ALIS",
    "Yellis",
    "Diagnostic",
    "Mock GCSE",
    "Reading Age",
    "Other",
)
DEFAULT_ASSESSMENT_TYPE: str = "Initial Test"

# A-Level scale; baseline tests typically produce a working-at grade.
A_LEVEL_GRADES: tuple[str, ...] = ("A*", "A", "B", "C", "D", "E", "U")
GCSE_GRADES: tuple[str, ...] = (
    "9", "8", "7", "6", "5", "4", "3", "2", "1", "U",
)

CONFIDENCE: tuple[str, ...] = ("Low", "Medium", "High")
DEFAULT_CONFIDENCE: str = "Medium"

# Maps an A-Level letter to its UCAS-style point value, used for
# "average GCSE → expected A-Level" computations and ordering.
_A_LEVEL_POINTS: dict[str, int] = {
    "A*": 6, "A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "U": 0,
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS baseline_records (
    record_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       TEXT NOT NULL,
    subject_name     TEXT,
    assessment_type  TEXT NOT NULL DEFAULT 'Initial Test',
    assessment_date  TEXT,
    raw_score        REAL,
    max_score        REAL,
    percentage       REAL,
    baseline_grade   TEXT,
    standardised_score REAL,
    confidence       TEXT NOT NULL DEFAULT 'Medium',
    is_primary       INTEGER NOT NULL DEFAULT 0,
    assessor         TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ba_student ON baseline_records(student_id);
CREATE INDEX IF NOT EXISTS idx_ba_subject ON baseline_records(subject_name);
CREATE INDEX IF NOT EXISTS idx_ba_type    ON baseline_records(assessment_type);
"""


@dataclass
class BaselineRecord:
    record_id: int
    student_id: str
    subject_name: str | None
    assessment_type: str
    assessment_date: str | None
    raw_score: float | None
    max_score: float | None
    percentage: float | None
    baseline_grade: str | None
    standardised_score: float | None
    confidence: str
    is_primary: bool
    assessor: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def score_label(self) -> str:
        if self.raw_score is not None and self.max_score is not None:
            return f"{self.raw_score:g}/{self.max_score:g}"
        if self.percentage is not None:
            return f"{self.percentage:g}%"
        if self.standardised_score is not None:
            return f"SS {self.standardised_score:g}"
        return self.baseline_grade or "—"


@dataclass
class RecordRow:
    record: BaselineRecord
    student_name: str


@dataclass
class StudentBaselineSummary:
    student_id: str
    total: int
    primary_count: int
    by_subject: dict[str, int]
    average_percentage: float | None
    avg_a_level_points: float | None    # over baseline_grade if letters


@dataclass
class Summary:
    total_records: int
    by_type: dict[str, int]
    by_subject: dict[str, int]
    by_grade: dict[str, int]
    average_percentage: float | None
    distinct_students: int
    primary_count: int


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
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Baseline-assessment schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> BaselineRecord:
    return BaselineRecord(
        record_id=r["record_id"], student_id=r["student_id"],
        subject_name=r["subject_name"],
        assessment_type=r["assessment_type"],
        assessment_date=r["assessment_date"],
        raw_score=r["raw_score"], max_score=r["max_score"],
        percentage=r["percentage"],
        baseline_grade=r["baseline_grade"],
        standardised_score=r["standardised_score"],
        confidence=r["confidence"],
        is_primary=bool(r["is_primary"]),
        assessor=r["assessor"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str, *,
                    required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_number(value: Any, label: str, *,
                      min_val: float | None = None,
                      max_val: float | None = None) -> float | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number") from None
    if min_val is not None and f < min_val:
        raise ValidationError(f"{label} must be at least {min_val}")
    if max_val is not None and f > max_val:
        raise ValidationError(f"{label} must be at most {max_val}")
    return f


def _validate_student(value: Any) -> str:
    sid = _require(value, "Student").strip()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_subject(value: Any) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    name = str(value).strip()
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        names = {x.name for x in _subjects.list_subjects()}
        if names and name not in names:
            return name  # tolerate non-catalogue (e.g. EPQ, GCSE)
    except Exception:
        pass
    return name


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(payload.get("student_id"))
    out["subject_name"] = _validate_subject(payload.get("subject_name"))

    atype = (payload.get("assessment_type")
              or DEFAULT_ASSESSMENT_TYPE).strip()
    if atype not in ASSESSMENT_TYPES:
        raise ValidationError(
            f"Assessment type must be one of: "
            f"{', '.join(ASSESSMENT_TYPES)}")
    out["assessment_type"] = atype

    out["assessment_date"] = _validate_date(
        payload.get("assessment_date"), "Assessment date")

    out["raw_score"] = _validate_number(payload.get("raw_score"),
                                            "Raw score", min_val=0)
    out["max_score"] = _validate_number(payload.get("max_score"),
                                            "Max score", min_val=0)
    if (out["raw_score"] is not None and out["max_score"] is not None
            and out["raw_score"] > out["max_score"]):
        raise ValidationError(
            f"Raw score ({out['raw_score']}) exceeds max "
            f"({out['max_score']})")

    pct = _validate_number(payload.get("percentage"),
                            "Percentage", min_val=0, max_val=100)
    # Auto-derive percentage if raw/max provided and pct missing.
    if pct is None and out["raw_score"] is not None and out["max_score"]:
        pct = round(100.0 * out["raw_score"] / out["max_score"], 1)
    out["percentage"] = pct

    out["standardised_score"] = _validate_number(
        payload.get("standardised_score"),
        "Standardised score", min_val=0, max_val=200)

    grade = (payload.get("baseline_grade") or "").strip()
    if grade and (grade not in A_LEVEL_GRADES
                    and grade not in GCSE_GRADES):
        # Tolerate other free-text grade scales (e.g. distinction),
        # cap length to avoid garbage.
        if len(grade) > 8:
            raise ValidationError(
                "Baseline grade should be a short label "
                "(e.g. A, B, 9, 7, Distinction)")
    out["baseline_grade"] = grade or None

    confidence = (payload.get("confidence")
                    or DEFAULT_CONFIDENCE).strip()
    if confidence not in CONFIDENCE:
        raise ValidationError(
            f"Confidence must be one of: {', '.join(CONFIDENCE)}")
    out["confidence"] = confidence

    out["is_primary"] = bool(payload.get("is_primary"))
    out["assessor"] = (payload.get("assessor") or "").strip() or None
    out["notes"]    = (payload.get("notes") or "").strip() or None
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def create_record(payload: dict[str, Any]) -> BaselineRecord:
    init_db()
    p = _validate_payload(payload)
    with _connect() as conn:
        if p["is_primary"] and p["subject_name"]:
            # Only one primary per (student, subject)
            conn.execute(
                "UPDATE baseline_records SET is_primary = 0 "
                "WHERE student_id = ? AND subject_name = ?",
                (p["student_id"], p["subject_name"]))
        cur = conn.execute(
            """INSERT INTO baseline_records
                   (student_id, subject_name, assessment_type,
                    assessment_date, raw_score, max_score, percentage,
                    baseline_grade, standardised_score, confidence,
                    is_primary, assessor, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["subject_name"], p["assessment_type"],
             p["assessment_date"], p["raw_score"], p["max_score"],
             p["percentage"], p["baseline_grade"],
             p["standardised_score"], p["confidence"],
             1 if p["is_primary"] else 0, p["assessor"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_record(new_id)
    assert out is not None
    logger.info(
        "Created baseline #%d for %s subject=%s type=%s grade=%s",
        new_id, p["student_id"], p["subject_name"] or "—",
        p["assessment_type"], p["baseline_grade"] or "—")
    return out


def get_record(record_id: int) -> BaselineRecord | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM baseline_records WHERE record_id = ?",
            (record_id,)).fetchone()
        return _row(r) if r else None


def get_primary(student_id: str, subject_name: str
                 ) -> BaselineRecord | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM baseline_records "
            "WHERE student_id = ? AND subject_name = ? "
            "AND is_primary = 1 "
            "ORDER BY record_id DESC LIMIT 1",
            (student_id.strip(), subject_name.strip())).fetchone()
        return _row(r) if r else None


def list_records(
    *,
    student_id: str | None = None,
    subject_name: str | None = None,
    assessment_type: str | None = None,
    grade: str | None = None,
    primary_only: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[BaselineRecord]:
    init_db()
    clauses, args = [], []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if subject_name:
        clauses.append("subject_name = ?")
        args.append(subject_name.strip())
    if assessment_type:
        if assessment_type not in ASSESSMENT_TYPES:
            raise ValidationError(
                f"Type must be one of: "
                f"{', '.join(ASSESSMENT_TYPES)}")
        clauses.append("assessment_type = ?")
        args.append(assessment_type)
    if grade:
        clauses.append("baseline_grade = ?")
        args.append(grade.strip())
    if primary_only:
        clauses.append("is_primary = 1")
    if date_from:
        clauses.append("assessment_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("assessment_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM baseline_records {where} "
           "ORDER BY student_id ASC, "
           "CASE WHEN subject_name IS NULL THEN 1 ELSE 0 END, "
           "subject_name ASC, "
           "is_primary DESC, assessment_date DESC, record_id ASC")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def list_records_with_detail(**kwargs) -> list[RecordRow]:
    rows = list_records(**kwargs)
    if not rows:
        return []
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name
              for s in _students.list_students()}
    return [RecordRow(record=r,
                       student_name=names.get(r.student_id,
                                                "(unknown)"))
            for r in rows]


def update_record(record_id: int,
                   payload: dict[str, Any]) -> BaselineRecord:
    init_db()
    existing = get_record(record_id)
    if existing is None:
        raise ValidationError(f"No baseline record #{record_id}")
    merged = {
        "student_id":         existing.student_id,
        "subject_name":       payload.get("subject_name",
                                           existing.subject_name),
        "assessment_type":    payload.get("assessment_type",
                                           existing.assessment_type),
        "assessment_date":    payload.get("assessment_date",
                                           existing.assessment_date),
        "raw_score":          payload.get("raw_score",
                                           existing.raw_score),
        "max_score":          payload.get("max_score",
                                           existing.max_score),
        "percentage":         payload.get("percentage",
                                           existing.percentage),
        "baseline_grade":     payload.get("baseline_grade",
                                           existing.baseline_grade),
        "standardised_score": payload.get("standardised_score",
                                           existing.standardised_score),
        "confidence":         payload.get("confidence",
                                           existing.confidence),
        "is_primary":         payload.get("is_primary",
                                           existing.is_primary),
        "assessor":           payload.get("assessor",
                                           existing.assessor),
        "notes":              payload.get("notes", existing.notes),
    }
    p = _validate_payload(merged)
    with _connect() as conn:
        if p["is_primary"] and p["subject_name"]:
            conn.execute(
                "UPDATE baseline_records SET is_primary = 0 "
                "WHERE student_id = ? AND subject_name = ? "
                "AND record_id <> ?",
                (p["student_id"], p["subject_name"], record_id))
        conn.execute(
            """UPDATE baseline_records SET
                   subject_name = ?, assessment_type = ?,
                   assessment_date = ?, raw_score = ?, max_score = ?,
                   percentage = ?, baseline_grade = ?,
                   standardised_score = ?, confidence = ?,
                   is_primary = ?, assessor = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE record_id = ?""",
            (p["subject_name"], p["assessment_type"],
             p["assessment_date"], p["raw_score"], p["max_score"],
             p["percentage"], p["baseline_grade"],
             p["standardised_score"], p["confidence"],
             1 if p["is_primary"] else 0, p["assessor"], p["notes"],
             record_id),
        )
        conn.commit()
    out = get_record(record_id)
    assert out is not None
    return out


def set_primary(record_id: int) -> BaselineRecord:
    return update_record(record_id, {"is_primary": True})


def delete_record(record_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM baseline_records WHERE record_id = ?",
            (record_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted baseline #%d", record_id)
            return True
        return False


# ── Per-student lookups ───────────────────────────────────────────

def records_for_student(student_id: str
                          ) -> list[BaselineRecord]:
    return list_records(student_id=student_id)


def student_summary(student_id: str) -> StudentBaselineSummary:
    init_db()
    rows = records_for_student(student_id)
    by_subject: dict[str, int] = {}
    pct_sum = 0.0
    pct_count = 0
    point_sum = 0
    point_count = 0
    primary = 0
    for r in rows:
        key = r.subject_name or "(none)"
        by_subject[key] = by_subject.get(key, 0) + 1
        if r.percentage is not None:
            pct_sum += r.percentage
            pct_count += 1
        if r.baseline_grade and r.baseline_grade in _A_LEVEL_POINTS:
            point_sum += _A_LEVEL_POINTS[r.baseline_grade]
            point_count += 1
        if r.is_primary:
            primary += 1
    return StudentBaselineSummary(
        student_id=student_id,
        total=len(rows),
        primary_count=primary,
        by_subject=by_subject,
        average_percentage=(round(pct_sum / pct_count, 1)
                              if pct_count else None),
        avg_a_level_points=(round(point_sum / point_count, 2)
                                if point_count else None),
    )


# ── Summary ───────────────────────────────────────────────────────

def summary() -> Summary:
    init_db()
    rows = list_records()
    by_type = {t: 0 for t in ASSESSMENT_TYPES}
    by_subject: dict[str, int] = {}
    by_grade: dict[str, int] = {}
    pct_sum = 0.0
    pct_count = 0
    primary = 0
    students: set[str] = set()
    for r in rows:
        by_type[r.assessment_type] = by_type.get(
            r.assessment_type, 0) + 1
        if r.subject_name:
            by_subject[r.subject_name] = by_subject.get(
                r.subject_name, 0) + 1
        if r.baseline_grade:
            by_grade[r.baseline_grade] = by_grade.get(
                r.baseline_grade, 0) + 1
        if r.percentage is not None:
            pct_sum += r.percentage
            pct_count += 1
        if r.is_primary:
            primary += 1
        students.add(r.student_id)
    return Summary(
        total_records=len(rows),
        by_type=by_type,
        by_subject=dict(sorted(by_subject.items(),
                                 key=lambda kv: kv[1],
                                 reverse=True)),
        by_grade=dict(sorted(by_grade.items())),
        average_percentage=(round(pct_sum / pct_count, 1)
                              if pct_count else None),
        distinct_students=len(students),
        primary_count=primary,
    )


# ── Helpers exposed for target_setting integration ────────────────

def a_level_points(grade: str | None) -> int | None:
    if grade is None:
        return None
    return _A_LEVEL_POINTS.get(grade.strip())
