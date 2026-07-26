"""Value Added — per-student per-subject prior-attainment residual.

One row per (student, subject, exam_session) with the headline points:

* ``prior_attainment``     — average GCSE points (or other baseline)
* ``expected_grade``       — statistically expected A-Level grade given
                              the prior attainment (often via ALPS
                              indicator)
* ``target_grade``         — school's Minimum Target Expected
* ``predicted_grade``      — teacher's current prediction
* ``actual_grade``         — final awarded grade (once results in)
* ``alps_indicator``       — 1-9 ALPS-style scale (1 = best, 9 = worst)
* ``va_score``             — actual_points − expected_points
                              (auto-computed when both are set)

The UNIQUE constraint on ``(student_id, subject_name, exam_session)``
prevents accidentally creating two VA records for the same student in
the same subject for the same session.

Cascade: deleting a student wipes their VA rows.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.systems.sixth_form.infrastructure import paths
from education_system.systems.sixth_form.domain.assessment.value_added import (
    value_added as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.VALUE_ADDED_DB


# Standard A-Level grade scale plus UCAS-style point values.
A_LEVEL_GRADES: tuple[str, ...] = ("A*", "A", "B", "C", "D", "E", "U")
_POINTS: dict[str, int] = {
    "A*": 6, "A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "U": 0,
}

# ALPS-style indicator (1-9, 1 = top decile, 9 = bottom).
ALPS_INDICATORS: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 8, 9)

# Status to mark how settled the row is in the cycle.
STATUSES: tuple[str, ...] = (
    "Provisional", "Confirmed", "Results In", "Archived",
)
DEFAULT_STATUS: str = "Provisional"

YEAR_GROUPS: tuple[str, ...] = ("Year 12", "Year 13", "Mixed")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SESSION_RE = re.compile(
    r"^(Summer|Autumn|Winter|January|June|November)\s+\d{4}$"
)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS value_added_records (
    record_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id         TEXT NOT NULL,
    subject_name       TEXT NOT NULL,
    exam_session       TEXT NOT NULL,
    year_group         TEXT,
    prior_attainment   REAL,
    expected_grade     TEXT,
    target_grade       TEXT,
    predicted_grade    TEXT,
    actual_grade       TEXT,
    va_score           REAL,
    alps_indicator     INTEGER,
    status             TEXT NOT NULL DEFAULT 'Provisional',
    teacher            TEXT,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE,
    UNIQUE (student_id, subject_name, exam_session)
);

CREATE INDEX IF NOT EXISTS idx_va_student ON value_added_records(student_id);
CREATE INDEX IF NOT EXISTS idx_va_subject ON value_added_records(subject_name);
CREATE INDEX IF NOT EXISTS idx_va_session ON value_added_records(exam_session);
CREATE INDEX IF NOT EXISTS idx_va_status  ON value_added_records(status);
"""


@dataclass
class VARecord:
    record_id: int
    student_id: str
    subject_name: str
    exam_session: str
    year_group: str | None
    prior_attainment: float | None
    expected_grade: str | None
    target_grade: str | None
    predicted_grade: str | None
    actual_grade: str | None
    va_score: float | None
    alps_indicator: int | None
    status: str
    teacher: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def expected_points(self) -> int | None:
        return (_POINTS.get(self.expected_grade)
                if self.expected_grade else None)

    @property
    def actual_points(self) -> int | None:
        return (_POINTS.get(self.actual_grade)
                if self.actual_grade else None)

    @property
    def target_points(self) -> int | None:
        return (_POINTS.get(self.target_grade)
                if self.target_grade else None)

    @property
    def predicted_points(self) -> int | None:
        return (_POINTS.get(self.predicted_grade)
                if self.predicted_grade else None)

    @property
    def predicted_vs_target(self) -> int | None:
        if self.predicted_points is None or self.target_points is None:
            return None
        return self.predicted_points - self.target_points

    @property
    def actual_vs_expected(self) -> int | None:
        if self.actual_points is None or self.expected_points is None:
            return None
        return self.actual_points - self.expected_points

    @property
    def actual_vs_target(self) -> int | None:
        if self.actual_points is None or self.target_points is None:
            return None
        return self.actual_points - self.target_points

    @property
    def va_label(self) -> str:
        v = self.va_score
        if v is None:
            return "—"
        return f"{v:+.2f}"


@dataclass
class RecordRow:
    record: VARecord
    student_name: str


@dataclass
class StudentSummary:
    student_id: str
    total: int
    average_va: float | None
    by_subject: dict[str, float]    # subject → avg VA in that subject


@dataclass
class Summary:
    total_records: int
    by_status: dict[str, int]
    by_session: dict[str, int]
    by_subject: dict[str, int]
    distinct_students: int
    average_va: float | None        # mean of va_score across all
    average_alps: float | None
    positive_va: int                # rows with va_score > 0
    negative_va: int
    above_target: int               # actual >= target
    below_target: int


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
    logger.debug("Value-added schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> VARecord:
    return VARecord(
        record_id=r["record_id"], student_id=r["student_id"],
        subject_name=r["subject_name"],
        exam_session=r["exam_session"],
        year_group=r["year_group"],
        prior_attainment=r["prior_attainment"],
        expected_grade=r["expected_grade"],
        target_grade=r["target_grade"],
        predicted_grade=r["predicted_grade"],
        actual_grade=r["actual_grade"],
        va_score=r["va_score"],
        alps_indicator=r["alps_indicator"],
        status=r["status"], teacher=r["teacher"],
        notes=r["notes"],
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


def _validate_student(value: Any) -> str:
    sid = _require(value, "Student").strip()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_subject(value: Any) -> str:
    name = _require(value, "Subject").strip()
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        names = {x.name for x in _subjects.list_subjects()}
        if names and name not in names:
            # Tolerate non-catalogue (e.g. EPQ, GCSE Resit)
            return name
    except Exception:
        pass
    return name


def _validate_session(value: Any) -> str:
    s = _require(value, "Exam session").strip()
    if not _SESSION_RE.match(s):
        raise ValidationError(
            "Exam session must be 'Summer YYYY', 'Autumn YYYY', "
            "'January YYYY', 'June YYYY', or 'November YYYY'")
    return s


def _validate_grade(value: Any, label: str, *,
                     required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if s not in A_LEVEL_GRADES:
        raise ValidationError(
            f"{label} must be one of: {', '.join(A_LEVEL_GRADES)}")
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


def _validate_alps(value: Any) -> int | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(
            "ALPS indicator must be a whole number") from None
    if n not in ALPS_INDICATORS:
        raise ValidationError(
            "ALPS indicator must be 1..9")
    return n


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(payload.get("student_id"))
    out["subject_name"] = _validate_subject(payload.get("subject_name"))
    out["exam_session"] = _validate_session(payload.get("exam_session"))

    year = (payload.get("year_group") or "").strip()
    if year and year not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of: "
            f"{', '.join(YEAR_GROUPS)}")
    out["year_group"] = year or None

    out["prior_attainment"] = _validate_number(
        payload.get("prior_attainment"), "Prior attainment",
        min_val=0, max_val=10)
    out["expected_grade"]  = _validate_grade(
        payload.get("expected_grade"), "Expected grade")
    out["target_grade"]    = _validate_grade(
        payload.get("target_grade"), "Target grade")
    out["predicted_grade"] = _validate_grade(
        payload.get("predicted_grade"), "Predicted grade")
    out["actual_grade"]    = _validate_grade(
        payload.get("actual_grade"), "Actual grade")

    out["alps_indicator"] = _validate_alps(payload.get("alps_indicator"))

    status = (payload.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    out["teacher"] = (payload.get("teacher") or "").strip() or None
    out["notes"]   = (payload.get("notes") or "").strip() or None

    # Compute va_score automatically if not explicitly supplied.
    supplied_va = payload.get("va_score")
    if supplied_va in (None, ""):
        if (out["actual_grade"] and out["expected_grade"]):
            out["va_score"] = float(
                _POINTS[out["actual_grade"]]
                - _POINTS[out["expected_grade"]])
        else:
            out["va_score"] = None
    else:
        out["va_score"] = _validate_number(
            supplied_va, "VA score", min_val=-10, max_val=10)

    if out["actual_grade"] and status == "Provisional":
        # Auto-promote to Results In when actual grade lands.
        out["status"] = "Results In"

    return out


# ── CRUD ──────────────────────────────────────────────────────────

def create_record(payload: dict[str, Any]) -> VARecord:
    init_db()
    p = _validate_payload(payload)
    with _connect() as conn:
        if conn.execute(
                "SELECT 1 FROM value_added_records "
                "WHERE student_id = ? AND subject_name = ? "
                "AND exam_session = ?",
                (p["student_id"], p["subject_name"],
                  p["exam_session"])).fetchone():
            raise ValidationError(
                f"VA record for {p['student_id']} × "
                f"{p['subject_name']!r} × {p['exam_session']!r} "
                "already exists — edit instead")
        cur = conn.execute(
            """INSERT INTO value_added_records
                   (student_id, subject_name, exam_session,
                    year_group, prior_attainment, expected_grade,
                    target_grade, predicted_grade, actual_grade,
                    va_score, alps_indicator, status, teacher,
                    notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["subject_name"], p["exam_session"],
             p["year_group"], p["prior_attainment"],
             p["expected_grade"], p["target_grade"],
             p["predicted_grade"], p["actual_grade"],
             p["va_score"], p["alps_indicator"], p["status"],
             p["teacher"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_record(new_id)
    assert out is not None
    logger.info(
        "Created VA #%d for %s × %s × %s (va=%s)",
        new_id, p["student_id"], p["subject_name"],
        p["exam_session"], p["va_score"])
    return out


def get_record(record_id: int) -> VARecord | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM value_added_records "
            "WHERE record_id = ?",
            (record_id,)).fetchone()
        return _row(r) if r else None


def get_record_for(student_id: str, subject_name: str,
                    exam_session: str) -> VARecord | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM value_added_records "
            "WHERE student_id = ? AND subject_name = ? "
            "AND exam_session = ?",
            (student_id.strip(), subject_name.strip(),
              exam_session.strip())).fetchone()
        return _row(r) if r else None


def list_records(
    *,
    student_id: str | None = None,
    subject_name: str | None = None,
    exam_session: str | None = None,
    year_group: str | None = None,
    status: str | None = None,
    teacher_like: str | None = None,
    positive_only: bool = False,
    negative_only: bool = False,
    min_alps: int | None = None,
    max_alps: int | None = None,
) -> list[VARecord]:
    init_db()
    clauses, args = [], []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if subject_name:
        clauses.append("subject_name = ?")
        args.append(subject_name.strip())
    if exam_session:
        clauses.append("exam_session = ?")
        args.append(exam_session.strip())
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year group must be one of: "
                f"{', '.join(YEAR_GROUPS)}")
        clauses.append("year_group = ?")
        args.append(year_group)
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if teacher_like:
        clauses.append("teacher LIKE ?")
        args.append(f"%{teacher_like.strip()}%")
    if positive_only:
        clauses.append("va_score IS NOT NULL AND va_score > 0")
    if negative_only:
        clauses.append("va_score IS NOT NULL AND va_score < 0")
    if min_alps is not None:
        clauses.append("alps_indicator IS NOT NULL "
                       "AND alps_indicator >= ?")
        args.append(int(min_alps))
    if max_alps is not None:
        clauses.append("alps_indicator IS NOT NULL "
                       "AND alps_indicator <= ?")
        args.append(int(max_alps))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM value_added_records {where} "
           "ORDER BY exam_session DESC, student_id ASC, "
           "subject_name ASC")
    with _connect() as conn:
        return [_row(r)
                for r in conn.execute(sql, args).fetchall()]


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
                   payload: dict[str, Any]) -> VARecord:
    init_db()
    existing = get_record(record_id)
    if existing is None:
        raise ValidationError(f"No VA record #{record_id}")
    merged = {
        "student_id":        existing.student_id,
        "subject_name":      existing.subject_name,
        "exam_session":      existing.exam_session,
        "year_group":        payload.get("year_group",
                                          existing.year_group),
        "prior_attainment":  payload.get("prior_attainment",
                                          existing.prior_attainment),
        "expected_grade":    payload.get("expected_grade",
                                          existing.expected_grade),
        "target_grade":      payload.get("target_grade",
                                          existing.target_grade),
        "predicted_grade":   payload.get("predicted_grade",
                                          existing.predicted_grade),
        "actual_grade":      payload.get("actual_grade",
                                          existing.actual_grade),
        # Pass va_score as None when changing actual/expected so it
        # auto-recomputes; otherwise carry forward.
        "va_score":          payload.get(
            "va_score",
            None if (
                ("actual_grade" in payload
                  and payload["actual_grade"] != existing.actual_grade)
                or ("expected_grade" in payload
                     and payload["expected_grade"]
                         != existing.expected_grade))
            else existing.va_score),
        "alps_indicator":    payload.get("alps_indicator",
                                          existing.alps_indicator),
        "status":            payload.get("status", existing.status),
        "teacher":           payload.get("teacher",
                                          existing.teacher),
        "notes":             payload.get("notes", existing.notes),
    }
    p = _validate_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE value_added_records SET
                   year_group = ?, prior_attainment = ?,
                   expected_grade = ?, target_grade = ?,
                   predicted_grade = ?, actual_grade = ?,
                   va_score = ?, alps_indicator = ?, status = ?,
                   teacher = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE record_id = ?""",
            (p["year_group"], p["prior_attainment"],
             p["expected_grade"], p["target_grade"],
             p["predicted_grade"], p["actual_grade"],
             p["va_score"], p["alps_indicator"], p["status"],
             p["teacher"], p["notes"], record_id),
        )
        conn.commit()
    out = get_record(record_id)
    assert out is not None
    return out


def set_actual_grade(record_id: int, grade: str) -> VARecord:
    """Record the final awarded grade. VA score auto-recomputes."""
    return update_record(record_id, {"actual_grade": grade})


def set_predicted_grade(record_id: int, grade: str) -> VARecord:
    return update_record(record_id, {"predicted_grade": grade})


def set_status(record_id: int, status: str) -> VARecord:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_record(record_id, {"status": status})


def delete_record(record_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM value_added_records WHERE record_id = ?",
            (record_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted VA record #%d", record_id)
            return True
        return False


# ── Per-student lookups ───────────────────────────────────────────

def records_for_student(student_id: str) -> list[VARecord]:
    return list_records(student_id=student_id)


def student_summary(student_id: str) -> StudentSummary:
    init_db()
    rows = records_for_student(student_id)
    by_subject_sum: dict[str, list[float]] = {}
    va_sum = 0.0
    va_count = 0
    for r in rows:
        if r.va_score is None:
            continue
        va_sum += r.va_score
        va_count += 1
        by_subject_sum.setdefault(r.subject_name, []).append(
            r.va_score)
    by_subject = {sub: round(sum(vals) / len(vals), 2)
                    for sub, vals in by_subject_sum.items()}
    return StudentSummary(
        student_id=student_id,
        total=len(rows),
        average_va=(round(va_sum / va_count, 2)
                      if va_count else None),
        by_subject=by_subject,
    )


# ── Summary ───────────────────────────────────────────────────────

def summary() -> Summary:
    init_db()
    rows = list_records()
    by_status = {s: 0 for s in STATUSES}
    by_session: dict[str, int] = {}
    by_subject: dict[str, int] = {}
    va_sum = 0.0
    va_count = 0
    alps_sum = 0
    alps_count = 0
    positive = 0
    negative = 0
    above_target = 0
    below_target = 0
    students: set[str] = set()
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        by_session[r.exam_session] = by_session.get(
            r.exam_session, 0) + 1
        by_subject[r.subject_name] = by_subject.get(
            r.subject_name, 0) + 1
        if r.va_score is not None:
            va_sum += r.va_score
            va_count += 1
            if r.va_score > 0:
                positive += 1
            elif r.va_score < 0:
                negative += 1
        if r.alps_indicator is not None:
            alps_sum += r.alps_indicator
            alps_count += 1
        delta = r.actual_vs_target
        if delta is not None:
            if delta >= 0:
                above_target += 1
            else:
                below_target += 1
        students.add(r.student_id)
    return Summary(
        total_records=len(rows),
        by_status=by_status,
        by_session=dict(sorted(by_session.items(), reverse=True)),
        by_subject=dict(sorted(by_subject.items(),
                                 key=lambda kv: kv[1],
                                 reverse=True)),
        distinct_students=len(students),
        average_va=(round(va_sum / va_count, 2)
                      if va_count else None),
        average_alps=(round(alps_sum / alps_count, 2)
                        if alps_count else None),
        positive_va=positive,
        negative_va=negative,
        above_target=above_target,
        below_target=below_target,
    )


# ── Helpers ───────────────────────────────────────────────────────

def grade_points(grade: str | None) -> int | None:
    if grade is None:
        return None
    return _POINTS.get(grade.strip())
