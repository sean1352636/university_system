"""Self Assessment — per-student self-evaluation submissions.

A student fills in a self-assessment form at a checkpoint (start of
year, half-term, mock results, UCAS readiness). They rate themselves
across 1–5 Likert dimensions and write free-text reflections. A
member of staff can optionally add reviewer feedback and an
agreed-status.

Cascade: deleting a student wipes their self-assessments.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.systems.sixth_form.infrastructure import paths
from education_system.systems.sixth_form.domain.assessment.self_assessment import (
    self_assessment as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SELF_ASSESSMENT_DB


ASSESSMENT_TYPES: tuple[str, ...] = (
    "Subject Progress",
    "Study Skills",
    "Wellbeing",
    "UCAS Readiness",
    "Mock Reflection",
    "End-of-Term",
    "Mid-Year Review",
    "Career Readiness",
    "Behaviour & Conduct",
    "Other",
)
DEFAULT_ASSESSMENT_TYPE: str = "Subject Progress"

STATUSES: tuple[str, ...] = (
    "Draft", "Submitted", "Under Review",
    "Reviewed", "Acknowledged", "Archived",
)
DEFAULT_STATUS: str = "Draft"
OPEN_STATUSES: tuple[str, ...] = (
    "Draft", "Submitted", "Under Review",
)

# 1–5 Likert scale, with 1 = lowest and 5 = highest.
LIKERT_RANGE: tuple[int, ...] = (1, 2, 3, 4, 5)
_LIKERT_LABELS: dict[int, str] = {
    1: "Very Low",
    2: "Low",
    3: "Average",
    4: "Good",
    5: "Excellent",
}

# Dimensions captured per assessment. Stored as separate columns so
# they're easy to filter / aggregate without JSON gymnastics.
DIMENSIONS: tuple[str, ...] = (
    "effort",
    "organisation",
    "engagement",
    "homework_completion",
    "subject_confidence",
    "behaviour",
    "wellbeing",
    "independence",
)
_DIMENSION_LABELS: dict[str, str] = {
    "effort":              "Effort",
    "organisation":        "Organisation",
    "engagement":          "Engagement",
    "homework_completion": "Homework completion",
    "subject_confidence":  "Subject confidence",
    "behaviour":           "Behaviour & conduct",
    "wellbeing":           "Wellbeing",
    "independence":        "Independence",
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS self_assessments (
    assessment_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id           TEXT NOT NULL,
    assessment_type      TEXT NOT NULL DEFAULT 'Subject Progress',
    subject_name         TEXT,
    period               TEXT,
    assessment_date      TEXT NOT NULL,
    effort               INTEGER,
    organisation         INTEGER,
    engagement           INTEGER,
    homework_completion  INTEGER,
    subject_confidence   INTEGER,
    behaviour            INTEGER,
    wellbeing            INTEGER,
    independence         INTEGER,
    strengths            TEXT,
    areas_to_improve     TEXT,
    action_plan          TEXT,
    support_needed       TEXT,
    proudest_moment      TEXT,
    biggest_challenge    TEXT,
    reviewer             TEXT,
    reviewer_feedback    TEXT,
    reviewed_on          TEXT,
    agreed_actions       TEXT,
    status               TEXT NOT NULL DEFAULT 'Draft',
    notes                TEXT,
    created_at           TEXT DEFAULT (datetime('now')),
    updated_at           TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sa_student ON self_assessments(student_id);
CREATE INDEX IF NOT EXISTS idx_sa_type    ON self_assessments(assessment_type);
CREATE INDEX IF NOT EXISTS idx_sa_status  ON self_assessments(status);
CREATE INDEX IF NOT EXISTS idx_sa_date    ON self_assessments(assessment_date);
"""


@dataclass
class SelfAssessment:
    assessment_id: int
    student_id: str
    assessment_type: str
    subject_name: str | None
    period: str | None
    assessment_date: str
    effort: int | None
    organisation: int | None
    engagement: int | None
    homework_completion: int | None
    subject_confidence: int | None
    behaviour: int | None
    wellbeing: int | None
    independence: int | None
    strengths: str | None
    areas_to_improve: str | None
    action_plan: str | None
    support_needed: str | None
    proudest_moment: str | None
    biggest_challenge: str | None
    reviewer: str | None
    reviewer_feedback: str | None
    reviewed_on: str | None
    agreed_actions: str | None
    status: str
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def is_reviewed(self) -> bool:
        return self.status in ("Reviewed", "Acknowledged", "Archived")

    @property
    def average_score(self) -> float | None:
        scores = [getattr(self, d) for d in DIMENSIONS]
        present = [s for s in scores if s is not None]
        if not present:
            return None
        return round(sum(present) / len(present), 2)

    @property
    def ratings(self) -> dict[str, int | None]:
        return {d: getattr(self, d) for d in DIMENSIONS}


@dataclass
class AssessmentRow:
    assessment: SelfAssessment
    student_name: str


@dataclass
class StudentSummary:
    student_id: str
    total: int
    open_count: int
    average_score: float | None      # mean across this student's
                                      # most-recent ratings
    by_type: dict[str, int]
    most_recent: str | None


@dataclass
class Summary:
    total: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    open_count: int
    awaiting_review: int             # status in Submitted/Under Review
    distinct_students: int
    average_per_dimension: dict[str, float | None]


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
    logger.debug("Self-assessment schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> SelfAssessment:
    return SelfAssessment(
        assessment_id=r["assessment_id"],
        student_id=r["student_id"],
        assessment_type=r["assessment_type"],
        subject_name=r["subject_name"],
        period=r["period"],
        assessment_date=r["assessment_date"],
        effort=r["effort"],
        organisation=r["organisation"],
        engagement=r["engagement"],
        homework_completion=r["homework_completion"],
        subject_confidence=r["subject_confidence"],
        behaviour=r["behaviour"],
        wellbeing=r["wellbeing"],
        independence=r["independence"],
        strengths=r["strengths"],
        areas_to_improve=r["areas_to_improve"],
        action_plan=r["action_plan"],
        support_needed=r["support_needed"],
        proudest_moment=r["proudest_moment"],
        biggest_challenge=r["biggest_challenge"],
        reviewer=r["reviewer"],
        reviewer_feedback=r["reviewer_feedback"],
        reviewed_on=r["reviewed_on"],
        agreed_actions=r["agreed_actions"],
        status=r["status"], notes=r["notes"],
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


def _validate_likert(value: Any, label: str) -> int | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(
            f"{label} must be a whole number 1-5") from None
    if n not in LIKERT_RANGE:
        raise ValidationError(
            f"{label} must be 1..5 (1=Very Low, 5=Excellent)")
    return n


def _validate_student(value: Any) -> str:
    sid = _require(value, "Student").strip()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["student_id"] = _validate_student(payload.get("student_id"))

    atype = (payload.get("assessment_type")
              or DEFAULT_ASSESSMENT_TYPE).strip()
    if atype not in ASSESSMENT_TYPES:
        raise ValidationError(
            f"Type must be one of: {', '.join(ASSESSMENT_TYPES)}")
    out["assessment_type"] = atype

    status = (payload.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    out["assessment_date"] = _validate_date(
        payload.get("assessment_date"), "Assessment date",
        required=False) or _dt.date.today().isoformat()

    out["subject_name"] = (payload.get("subject_name")
                              or "").strip() or None
    out["period"]       = (payload.get("period") or "").strip() or None

    for dim in DIMENSIONS:
        out[dim] = _validate_likert(payload.get(dim),
                                       _DIMENSION_LABELS[dim])

    out["strengths"]         = (payload.get("strengths")
                                   or "").strip() or None
    out["areas_to_improve"]  = (payload.get("areas_to_improve")
                                   or "").strip() or None
    out["action_plan"]       = (payload.get("action_plan")
                                   or "").strip() or None
    out["support_needed"]    = (payload.get("support_needed")
                                   or "").strip() or None
    out["proudest_moment"]   = (payload.get("proudest_moment")
                                   or "").strip() or None
    out["biggest_challenge"] = (payload.get("biggest_challenge")
                                   or "").strip() or None
    out["reviewer"]          = (payload.get("reviewer")
                                   or "").strip() or None
    out["reviewer_feedback"] = (payload.get("reviewer_feedback")
                                   or "").strip() or None
    out["reviewed_on"]       = _validate_date(
        payload.get("reviewed_on"), "Reviewed on")
    out["agreed_actions"]    = (payload.get("agreed_actions")
                                   or "").strip() or None
    out["notes"]             = (payload.get("notes")
                                   or "").strip() or None

    today = _dt.date.today().isoformat()
    if (status in ("Reviewed", "Acknowledged")
            and not out["reviewed_on"]):
        out["reviewed_on"] = today
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def create_assessment(payload: dict[str, Any]) -> SelfAssessment:
    init_db()
    p = _validate_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO self_assessments
                   (student_id, assessment_type, subject_name,
                    period, assessment_date,
                    effort, organisation, engagement,
                    homework_completion, subject_confidence,
                    behaviour, wellbeing, independence,
                    strengths, areas_to_improve, action_plan,
                    support_needed, proudest_moment,
                    biggest_challenge, reviewer, reviewer_feedback,
                    reviewed_on, agreed_actions, status, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["assessment_type"],
             p["subject_name"], p["period"], p["assessment_date"],
             p["effort"], p["organisation"], p["engagement"],
             p["homework_completion"], p["subject_confidence"],
             p["behaviour"], p["wellbeing"], p["independence"],
             p["strengths"], p["areas_to_improve"],
             p["action_plan"], p["support_needed"],
             p["proudest_moment"], p["biggest_challenge"],
             p["reviewer"], p["reviewer_feedback"],
             p["reviewed_on"], p["agreed_actions"], p["status"],
             p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_assessment(new_id)
    assert out is not None
    logger.info(
        "Created self-assessment #%d for %s (%s, status=%s)",
        new_id, p["student_id"], p["assessment_type"],
        p["status"])
    return out


def get_assessment(assessment_id: int) -> SelfAssessment | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM self_assessments "
            "WHERE assessment_id = ?",
            (assessment_id,)).fetchone()
        return _row(r) if r else None


def list_assessments(
    *,
    student_id: str | None = None,
    assessment_type: str | None = None,
    subject_name: str | None = None,
    period: str | None = None,
    status: str | None = None,
    reviewer_like: str | None = None,
    open_only: bool = False,
    awaiting_review: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[SelfAssessment]:
    init_db()
    clauses, args = [], []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if assessment_type:
        if assessment_type not in ASSESSMENT_TYPES:
            raise ValidationError(
                f"Type must be one of: "
                f"{', '.join(ASSESSMENT_TYPES)}")
        clauses.append("assessment_type = ?")
        args.append(assessment_type)
    if subject_name:
        clauses.append("subject_name = ?")
        args.append(subject_name.strip())
    if period:
        clauses.append("period = ?")
        args.append(period.strip())
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if reviewer_like:
        clauses.append("reviewer LIKE ?")
        args.append(f"%{reviewer_like.strip()}%")
    if open_only:
        ph = ",".join("?" * len(OPEN_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(OPEN_STATUSES)
    if awaiting_review:
        clauses.append(
            "status IN ('Submitted', 'Under Review')")
    if date_from:
        clauses.append("assessment_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("assessment_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM self_assessments {where} "
           "ORDER BY CASE status "
           "  WHEN 'Submitted'     THEN 0 "
           "  WHEN 'Under Review'  THEN 1 "
           "  WHEN 'Draft'         THEN 2 "
           "  WHEN 'Reviewed'      THEN 3 "
           "  WHEN 'Acknowledged'  THEN 4 "
           "  WHEN 'Archived'      THEN 5 "
           "  ELSE 6 END, "
           "assessment_date DESC, assessment_id DESC")
    with _connect() as conn:
        return [_row(r)
                for r in conn.execute(sql, args).fetchall()]


def list_assessments_with_detail(**kwargs) -> list[AssessmentRow]:
    rows = list_assessments(**kwargs)
    if not rows:
        return []
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name
              for s in _students.list_students()}
    return [AssessmentRow(assessment=a,
                            student_name=names.get(a.student_id,
                                                     "(unknown)"))
            for a in rows]


def update_assessment(assessment_id: int,
                       payload: dict[str, Any]) -> SelfAssessment:
    init_db()
    existing = get_assessment(assessment_id)
    if existing is None:
        raise ValidationError(
            f"No self-assessment #{assessment_id}")
    merged = {
        "student_id":          existing.student_id,
        "assessment_type":     payload.get("assessment_type",
                                            existing.assessment_type),
        "subject_name":        payload.get("subject_name",
                                            existing.subject_name),
        "period":              payload.get("period",
                                            existing.period),
        "assessment_date":     payload.get("assessment_date",
                                            existing.assessment_date),
        "status":              payload.get("status",
                                            existing.status),
        "reviewer":            payload.get("reviewer",
                                            existing.reviewer),
        "reviewer_feedback":   payload.get("reviewer_feedback",
                                            existing.reviewer_feedback),
        "reviewed_on":         payload.get("reviewed_on",
                                            existing.reviewed_on),
        "agreed_actions":      payload.get("agreed_actions",
                                            existing.agreed_actions),
        "notes":               payload.get("notes", existing.notes),
        "strengths":           payload.get("strengths",
                                            existing.strengths),
        "areas_to_improve":    payload.get("areas_to_improve",
                                            existing.areas_to_improve),
        "action_plan":         payload.get("action_plan",
                                            existing.action_plan),
        "support_needed":      payload.get("support_needed",
                                            existing.support_needed),
        "proudest_moment":     payload.get("proudest_moment",
                                            existing.proudest_moment),
        "biggest_challenge":   payload.get("biggest_challenge",
                                            existing.biggest_challenge),
    }
    for dim in DIMENSIONS:
        merged[dim] = payload.get(dim, getattr(existing, dim))
    p = _validate_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE self_assessments SET
                   assessment_type = ?, subject_name = ?, period = ?,
                   assessment_date = ?,
                   effort = ?, organisation = ?, engagement = ?,
                   homework_completion = ?, subject_confidence = ?,
                   behaviour = ?, wellbeing = ?, independence = ?,
                   strengths = ?, areas_to_improve = ?,
                   action_plan = ?, support_needed = ?,
                   proudest_moment = ?, biggest_challenge = ?,
                   reviewer = ?, reviewer_feedback = ?,
                   reviewed_on = ?, agreed_actions = ?,
                   status = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE assessment_id = ?""",
            (p["assessment_type"], p["subject_name"], p["period"],
             p["assessment_date"],
             p["effort"], p["organisation"], p["engagement"],
             p["homework_completion"], p["subject_confidence"],
             p["behaviour"], p["wellbeing"], p["independence"],
             p["strengths"], p["areas_to_improve"],
             p["action_plan"], p["support_needed"],
             p["proudest_moment"], p["biggest_challenge"],
             p["reviewer"], p["reviewer_feedback"],
             p["reviewed_on"], p["agreed_actions"], p["status"],
             p["notes"], assessment_id),
        )
        conn.commit()
    out = get_assessment(assessment_id)
    assert out is not None
    return out


def submit(assessment_id: int) -> SelfAssessment:
    return update_assessment(assessment_id, {"status": "Submitted"})


def record_review(assessment_id: int, *,
                   reviewer: str | None = None,
                   feedback: str | None = None,
                   agreed_actions: str | None = None,
                   reviewed_on: str | None = None) -> SelfAssessment:
    """Stamp reviewer feedback and flip status to Reviewed."""
    payload: dict[str, Any] = {
        "status": "Reviewed",
        "reviewed_on": reviewed_on
            or _dt.date.today().isoformat(),
    }
    if reviewer is not None:
        payload["reviewer"] = reviewer
    if feedback is not None:
        payload["reviewer_feedback"] = feedback
    if agreed_actions is not None:
        payload["agreed_actions"] = agreed_actions
    return update_assessment(assessment_id, payload)


def acknowledge(assessment_id: int) -> SelfAssessment:
    return update_assessment(assessment_id,
                                {"status": "Acknowledged"})


def set_status(assessment_id: int, status: str) -> SelfAssessment:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_assessment(assessment_id, {"status": status})


def delete_assessment(assessment_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM self_assessments WHERE assessment_id = ?",
            (assessment_id,))
        conn.commit()
        if cur.rowcount:
            logger.info(
                "Deleted self-assessment #%d", assessment_id)
            return True
        return False


# ── Per-student lookups ───────────────────────────────────────────

def assessments_for_student(student_id: str) -> list[SelfAssessment]:
    return list_assessments(student_id=student_id)


def student_summary(student_id: str) -> StudentSummary:
    init_db()
    rows = assessments_for_student(student_id)
    by_type: dict[str, int] = {}
    open_count = 0
    most_recent_score: float | None = None
    most_recent: str | None = None
    for i, a in enumerate(rows):
        by_type[a.assessment_type] = by_type.get(
            a.assessment_type, 0) + 1
        if a.is_open:
            open_count += 1
        if i == 0:
            # First row is the newest because of the ORDER BY in
            # list_assessments.
            most_recent_score = a.average_score
            most_recent = a.assessment_date
    return StudentSummary(
        student_id=student_id,
        total=len(rows),
        open_count=open_count,
        average_score=most_recent_score,
        by_type=by_type,
        most_recent=most_recent,
    )


# ── Summary ───────────────────────────────────────────────────────

def summary() -> Summary:
    init_db()
    rows = list_assessments()
    by_status = {s: 0 for s in STATUSES}
    by_type = {t: 0 for t in ASSESSMENT_TYPES}
    open_count = 0
    awaiting = 0
    students: set[str] = set()
    sums = {d: 0 for d in DIMENSIONS}
    counts = {d: 0 for d in DIMENSIONS}
    for a in rows:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        by_type[a.assessment_type] = by_type.get(
            a.assessment_type, 0) + 1
        students.add(a.student_id)
        if a.is_open:
            open_count += 1
        if a.status in ("Submitted", "Under Review"):
            awaiting += 1
        for d in DIMENSIONS:
            v = getattr(a, d)
            if v is not None:
                sums[d] += v
                counts[d] += 1
    averages = {d: (round(sums[d] / counts[d], 2)
                      if counts[d] else None)
                for d in DIMENSIONS}
    return Summary(
        total=len(rows),
        by_status=by_status,
        by_type=by_type,
        open_count=open_count,
        awaiting_review=awaiting,
        distinct_students=len(students),
        average_per_dimension=averages,
    )


# ── Helpers ───────────────────────────────────────────────────────

def likert_label(score: int | None) -> str:
    if score is None:
        return "—"
    return _LIKERT_LABELS.get(score, str(score))


def dimension_label(key: str) -> str:
    return _DIMENSION_LABELS.get(key, key)
