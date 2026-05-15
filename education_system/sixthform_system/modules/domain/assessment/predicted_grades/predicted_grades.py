"""Predicted-grade data layer for the Sixth Form System.

One row per ``(student, subject)`` — the A-Level letter a teacher
expects the student to achieve, plus a confidence level and free-text
notes / predicted-by.

The UNIQUE constraint on ``(student_id, subject)`` lets ``save`` upsert:
re-saving for the same pair updates the existing row rather than
inserting a duplicate. Subjects are validated against the live
``subjects`` table; grades against the gradebook's ``LETTER_GRADES``.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.sixthform_system.core import paths
from education_system.sixthform_system.modules.domain.assessment.gradebook.gradebook import LETTER_GRADES
from education_system.sixthform_system.modules.domain.assessment.predicted_grades import predicted_grades as data

logger = logging.getLogger(__name__)

DB_PATH = paths.PREDICTED_GRADES_DB

CONFIDENCE_LEVELS: tuple[str, ...] = ("High", "Medium", "Low")
DEFAULT_CONFIDENCE: str = "Medium"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS predicted_grades (
    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    subject       TEXT NOT NULL,
    grade         TEXT NOT NULL,
    confidence    TEXT NOT NULL DEFAULT 'Medium',
    notes         TEXT,
    predicted_by  TEXT,
    predicted_at  TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(student_id, subject),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pred_student ON predicted_grades(student_id);
CREATE INDEX IF NOT EXISTS idx_pred_subject ON predicted_grades(subject);
CREATE INDEX IF NOT EXISTS idx_pred_grade   ON predicted_grades(grade);
"""


@dataclass
class Prediction:
    prediction_id: int
    student_id: str
    subject: str
    grade: str
    confidence: str
    notes: str | None
    predicted_by: str | None
    predicted_at: str
    updated_at: str


@dataclass
class PredictionView:
    """One row in a bulk prediction sheet — student + any existing row."""
    student_id: str
    full_name: str
    prediction: Prediction | None


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
    from education_system.sixthform_system.modules.domain.students.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Predicted-grades schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> Prediction:
    return Prediction(
        prediction_id=r["prediction_id"],
        student_id=r["student_id"],
        subject=r["subject"],
        grade=r["grade"],
        confidence=r["confidence"],
        notes=r["notes"],
        predicted_by=r["predicted_by"],
        predicted_at=r["predicted_at"],
        updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid prediction input."""


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    sid = _require(data.get("student_id"), "Student ID").strip()
    from education_system.sixthform_system.modules.domain.students.students import students as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    subject = _require(data.get("subject"), "Subject").strip()
    try:
        from education_system.sixthform_system.modules.domain.academics.subjects import subjects as _subjects
        if not _subjects.is_valid_subject(subject):
            raise ValidationError(f"Unknown subject: {subject}")
    except ImportError:
        pass  # fall through — subjects module not initialised
    out["subject"] = subject

    grade = _require(data.get("grade"), "Grade").strip()
    if grade not in LETTER_GRADES:
        raise ValidationError(
            f"Grade must be one of: {', '.join(LETTER_GRADES)}")
    out["grade"] = grade

    confidence = (data.get("confidence") or DEFAULT_CONFIDENCE).strip()
    if confidence not in CONFIDENCE_LEVELS:
        raise ValidationError(
            f"Confidence must be one of: {', '.join(CONFIDENCE_LEVELS)}")
    out["confidence"] = confidence

    out["notes"]        = (data.get("notes") or "").strip() or None
    out["predicted_by"] = (data.get("predicted_by") or "").strip() or None
    return out


# ── CRUD / upsert ─────────────────────────────────────────────────

def save_prediction(data: dict[str, Any]) -> Prediction:
    """Upsert a prediction keyed on ``(student_id, subject)``."""
    init_db()
    try:
        p = _validate_payload(data)
    except ValidationError as e:
        logger.warning("save_prediction validation failed: %s", e)
        raise

    with _connect() as conn:
        conn.execute(
            """INSERT INTO predicted_grades
                   (student_id, subject, grade, confidence, notes,
                    predicted_by, predicted_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
               ON CONFLICT(student_id, subject) DO UPDATE SET
                   grade        = excluded.grade,
                   confidence   = excluded.confidence,
                   notes        = excluded.notes,
                   predicted_by = excluded.predicted_by,
                   updated_at   = datetime('now')""",
            (p["student_id"], p["subject"], p["grade"], p["confidence"],
             p["notes"], p["predicted_by"]),
        )
        conn.commit()

    pred = get_for_student_subject(p["student_id"], p["subject"])
    assert pred is not None
    logger.info(
        "Saved predicted grade for %s in %s: %s (%s confidence)",
        pred.student_id, pred.subject, pred.grade, pred.confidence,
    )
    return pred


def get_prediction(prediction_id: int) -> Prediction | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM predicted_grades WHERE prediction_id = ?",
            (prediction_id,),
        ).fetchone()
        return _row(r) if r else None


def get_for_student_subject(student_id: str, subject: str) -> Prediction | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM predicted_grades "
            "WHERE student_id = ? AND subject = ?",
            (student_id.strip(), subject.strip()),
        ).fetchone()
        return _row(r) if r else None


def list_predictions(
    *,
    student_id: str | None = None,
    subject: str | None = None,
    grade: str | None = None,
    confidence: str | None = None,
) -> list[Prediction]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if subject:
        clauses.append("subject = ?")
        args.append(subject.strip())
    if grade:
        if grade not in LETTER_GRADES:
            raise ValidationError(
                f"Grade must be one of: {', '.join(LETTER_GRADES)}")
        clauses.append("grade = ?")
        args.append(grade)
    if confidence:
        if confidence not in CONFIDENCE_LEVELS:
            raise ValidationError(
                f"Confidence must be one of: {', '.join(CONFIDENCE_LEVELS)}")
        clauses.append("confidence = ?")
        args.append(confidence)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        f"SELECT * FROM predicted_grades {where} "
        "ORDER BY student_id, subject"
    )
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def predictions_for_student(student_id: str) -> list[Prediction]:
    return list_predictions(student_id=student_id)


def update_prediction(prediction_id: int, data: dict[str, Any]) -> Prediction:
    """Update grade / confidence / notes for an existing prediction.

    ``student_id`` and ``subject`` are immutable through this entry point —
    use ``save_prediction`` with the new pair instead.
    """
    init_db()
    existing = get_prediction(prediction_id)
    if existing is None:
        logger.warning("update_prediction: unknown id %d", prediction_id)
        raise ValidationError(f"No prediction with id {prediction_id}")

    payload = _validate_payload({
        "student_id": existing.student_id,
        "subject": existing.subject,
        "grade":      data.get("grade", existing.grade),
        "confidence": data.get("confidence", existing.confidence),
        "notes":      data.get("notes", existing.notes),
        "predicted_by": data.get("predicted_by", existing.predicted_by),
    })

    with _connect() as conn:
        conn.execute(
            """UPDATE predicted_grades SET
                   grade = ?, confidence = ?, notes = ?,
                   predicted_by = ?, updated_at = datetime('now')
               WHERE prediction_id = ?""",
            (payload["grade"], payload["confidence"], payload["notes"],
             payload["predicted_by"], prediction_id),
        )
        conn.commit()

    out = get_prediction(prediction_id)
    assert out is not None
    logger.info(
        "Updated prediction #%d (%s in %s -> %s)",
        prediction_id, out.student_id, out.subject, out.grade,
    )
    return out


def delete_prediction(prediction_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM predicted_grades WHERE prediction_id = ?",
            (prediction_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted prediction #%d", prediction_id)
            return True
        logger.warning("delete_prediction: unknown id %d", prediction_id)
        return False


# ── Bulk-by-group flow ────────────────────────────────────────────

def _subject_for_group(group_id: int) -> str | None:
    """Resolve the subject taught in this group via its course."""
    from education_system.sixthform_system.modules.domain.academics.class_groups import class_groups
    from education_system.sixthform_system.modules.domain.academics.class_groups import class_groups as _cg
    from education_system.sixthform_system.modules.domain.academics.courses import courses as _crs
    g = _cg.get_group(group_id)
    if g is None:
        return None
    c = _crs.get_course(g.course_id)
    return c.subject if c else None


def group_prediction_view(group_id: int) -> tuple[str | None, list[PredictionView]]:
    """Return (subject, roster) for a class group.

    Each PredictionView pairs a member with their existing prediction
    *for the group's subject* — None means "not predicted yet".
    """
    init_db()
    from education_system.sixthform_system.modules.domain.academics.class_groups import class_groups
    from education_system.sixthform_system.modules.domain.students.students import students as _students
    members = _cg.list_members(group_id)
    if not members:
        return _subject_for_group(group_id), []
    subject = _subject_for_group(group_id)
    student_index = {s.student_id: s for s in _students.list_students()
                     if s.student_id in members}

    if subject is None:
        out = [
            PredictionView(sid, student_index[sid].full_name
                           if sid in student_index else "(unknown)", None)
            for sid in members
        ]
        return None, out

    with _connect() as conn:
        rows = {
            r["student_id"]: _row(r)
            for r in conn.execute(
                "SELECT * FROM predicted_grades WHERE subject = ? "
                "AND student_id IN (" +
                ",".join("?" for _ in members) + ")",
                (subject, *members),
            ).fetchall()
        }
    return subject, [
        PredictionView(
            student_id=sid,
            full_name=(student_index[sid].full_name
                       if sid in student_index else "(unknown)"),
            prediction=rows.get(sid),
        )
        for sid in members
    ]


def save_group_predictions(
    group_id: int,
    entries: dict[str, dict[str, Any]],
) -> int:
    """Bulk-save predictions for a class group's subject.

    ``entries`` maps ``student_id`` → ``{"grade", "confidence", "notes",
    "predicted_by"}``. Missing students are left alone; entries with a
    blank grade are skipped so the sheet can be partially filled.
    Returns the number of rows written.
    """
    init_db()
    subject = _subject_for_group(group_id)
    if subject is None:
        raise ValidationError(
            f"No course / subject resolved for group #{group_id}")

    cleaned: list[dict[str, Any]] = []
    for sid, payload in entries.items():
        grade = (payload.get("grade") or "").strip()
        if not grade:
            continue  # skip blanks — partial save is fine
        cleaned.append({
            "student_id": sid,
            "subject": subject,
            "grade": grade,
            "confidence": payload.get("confidence") or DEFAULT_CONFIDENCE,
            "notes": payload.get("notes"),
            "predicted_by": payload.get("predicted_by"),
        })

    written = 0
    for entry in cleaned:
        try:
            save_prediction(entry)
            written += 1
        except ValidationError as e:
            logger.warning(
                "save_group_predictions: skipping %s/%s — %s",
                entry["student_id"], subject, e,
            )
            raise  # bubble up so the GUI/CLI can show which row broke

    logger.info(
        "Bulk-saved %d prediction(s) for group #%d (%s)",
        written, group_id, subject,
    )
    return written
