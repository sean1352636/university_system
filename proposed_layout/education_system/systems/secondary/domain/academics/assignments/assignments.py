"""Assessed-assignment data layer for the Secondary School System.

Distinct from short-cycle ``homework``: this module tracks larger,
graded pieces of work — coursework, NEAs (non-exam assessments),
controlled assessments, projects, mocks. Each assignment carries a
weighting against the final grade and a max-marks total; per-pupil
submissions store marks_awarded and an optional moderation status.
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

ASSIGNMENT_TYPES: tuple[str, ...] = (
    "Coursework", "NEA", "Controlled Assessment", "Project", "Mock",
    "Other")
DEFAULT_TYPE: str = "Coursework"

ASSIGNMENT_STATUSES: tuple[str, ...] = (
    "Draft", "Set", "InProgress", "Submitted", "Marked", "Returned")
DEFAULT_STATUS: str = "Draft"

SUBMISSION_STATUSES: tuple[str, ...] = (
    "Pending", "Submitted", "Late", "Missing", "Marked", "Returned",
    "Resubmit")
DEFAULT_SUB_STATUS: str = "Pending"

MODERATION_STATUSES: tuple[str, ...] = (
    "Not moderated", "Pending", "Sampled", "Confirmed", "Adjusted")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS assignments (
    assignment_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT NOT NULL,
    subject_id       INTEGER NOT NULL,
    year_group       TEXT NOT NULL,
    form_group       TEXT,
    type             TEXT NOT NULL DEFAULT 'Coursework',
    weight_pct       REAL,
    max_marks        REAL,
    set_date         TEXT NOT NULL DEFAULT (date('now')),
    due_date         TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'Draft',
    description      TEXT,
    criteria         TEXT,
    set_by           TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
);

CREATE TABLE IF NOT EXISTS assignment_submissions (
    submission_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id    INTEGER NOT NULL,
    pupil_id         TEXT NOT NULL,
    submitted_date   TEXT,
    status           TEXT NOT NULL DEFAULT 'Pending',
    marks_awarded    REAL,
    grade            TEXT,
    moderation_status TEXT,
    moderator        TEXT,
    feedback         TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    UNIQUE (assignment_id, pupil_id),
    FOREIGN KEY (assignment_id) REFERENCES assignments(assignment_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_asn_due ON assignments(due_date);
CREATE INDEX IF NOT EXISTS idx_asn_year ON assignments(year_group);
CREATE INDEX IF NOT EXISTS idx_asn_sub_pupil
    ON assignment_submissions(pupil_id);
"""


@dataclass
class Assignment:
    assignment_id: int
    title: str
    subject_id: int
    year_group: str
    form_group: str | None
    type: str
    weight_pct: float | None
    max_marks: float | None
    set_date: str
    due_date: str
    status: str
    description: str | None
    criteria: str | None
    set_by: str | None
    notes: str | None
    subject_code: str | None = None
    subject_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class AssignmentSubmission:
    submission_id: int
    assignment_id: int
    pupil_id: str
    submitted_date: str | None
    status: str
    marks_awarded: float | None
    grade: str | None
    moderation_status: str | None
    moderator: str | None
    feedback: str | None
    created_at: str | None = None
    updated_at: str | None = None

    def mark_pct(self, max_marks: float | None) -> float | None:
        if self.marks_awarded is None or not max_marks:
            return None
        return round(100.0 * self.marks_awarded / max_marks, 2)


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
        logger.exception("Failed to initialise assignments tables")
        raise
    logger.info("Secondary assignments tables ready")
    _DB_READY = True


def _row_assignment(r: sqlite3.Row) -> Assignment:
    keys = r.keys()
    return Assignment(
        assignment_id=r["assignment_id"], title=r["title"],
        subject_id=r["subject_id"], year_group=r["year_group"],
        form_group=r["form_group"], type=r["type"],
        weight_pct=r["weight_pct"], max_marks=r["max_marks"],
        set_date=r["set_date"], due_date=r["due_date"],
        status=r["status"], description=r["description"],
        criteria=r["criteria"], set_by=r["set_by"], notes=r["notes"],
        subject_code=r["subject_code"] if "subject_code" in keys else None,
        subject_name=r["subject_name"] if "subject_name" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_submission(r: sqlite3.Row) -> AssignmentSubmission:
    return AssignmentSubmission(
        submission_id=r["submission_id"],
        assignment_id=r["assignment_id"],
        pupil_id=r["pupil_id"],
        submitted_date=r["submitted_date"], status=r["status"],
        marks_awarded=r["marks_awarded"], grade=r["grade"],
        moderation_status=r["moderation_status"],
        moderator=r["moderator"],
        feedback=r["feedback"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_date(value: Any, label: str, *,
                   required: bool = True) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
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


def _validate_assignment(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    title = (data.get("title") or "").strip()
    if not title:
        raise ValidationError("Title is required")
    if len(title) > 120:
        raise ValidationError("Title must be 120 characters or fewer")
    out["title"] = title

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

    yg = (data.get("year_group") or "").strip()
    if not yg:
        raise ValidationError("Year group is required")
    if yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of {', '.join(YEAR_GROUPS)}")
    out["year_group"] = yg
    out["form_group"] = (data.get("form_group") or "").strip() or None

    atype = (data.get("type") or DEFAULT_TYPE).strip()
    if atype not in ASSIGNMENT_TYPES:
        raise ValidationError(
            f"Type must be one of {', '.join(ASSIGNMENT_TYPES)}")
    out["type"] = atype

    def _optional_float(value, label, *, mn, mx):
        if value in (None, "") or (isinstance(value, str)
                                    and not value.strip()):
            return None
        try:
            v = float(value)
        except (TypeError, ValueError):
            raise ValidationError(f"{label} must be a number") from None
        if v < mn or v > mx:
            raise ValidationError(f"{label} must be between {mn} and {mx}")
        return v

    out["weight_pct"] = _optional_float(data.get("weight_pct"),
                                         "Weight %", mn=0, mx=100)
    out["max_marks"] = _optional_float(data.get("max_marks"),
                                        "Max marks", mn=0, mx=10000)

    set_date = _validate_date(data.get("set_date") or
                                _dt.date.today().isoformat(), "Set date")
    due_date = _validate_date(data.get("due_date"), "Due date")
    if due_date < set_date:
        raise ValidationError("Due date cannot be before set date")
    out["set_date"] = set_date
    out["due_date"] = due_date

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in ASSIGNMENT_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(ASSIGNMENT_STATUSES)}")
    out["status"] = status

    out["description"] = (data.get("description") or "").strip() or None
    out["criteria"]    = (data.get("criteria") or "").strip() or None
    out["set_by"]      = (data.get("set_by") or "").strip() or None
    out["notes"]       = (data.get("notes") or "").strip() or None
    return out


def _validate_submission(data: dict[str, Any],
                          max_marks: float | None
                          ) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    out["pupil_id"] = pid
    out["submitted_date"] = _validate_date(
        data.get("submitted_date"), "Submitted date", required=False)

    status = (data.get("status") or DEFAULT_SUB_STATUS).strip()
    if status not in SUBMISSION_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(SUBMISSION_STATUSES)}")
    out["status"] = status

    marks = data.get("marks_awarded")
    if marks in (None, "") or (isinstance(marks, str)
                                and not marks.strip()):
        out["marks_awarded"] = None
    else:
        try:
            v = float(marks)
        except (TypeError, ValueError):
            raise ValidationError(
                "Marks awarded must be a number") from None
        if v < 0:
            raise ValidationError("Marks awarded cannot be negative")
        if max_marks is not None and v > max_marks:
            raise ValidationError(
                f"Marks awarded ({v}) exceeds max marks ({max_marks})")
        out["marks_awarded"] = v

    out["grade"] = (data.get("grade") or "").strip() or None

    mod = (data.get("moderation_status") or "").strip()
    if mod and mod not in MODERATION_STATUSES:
        raise ValidationError(
            f"Moderation status must be one of "
            f"{', '.join(MODERATION_STATUSES)}")
    out["moderation_status"] = mod or None
    out["moderator"] = (data.get("moderator") or "").strip() or None
    out["feedback"]  = (data.get("feedback") or "").strip() or None
    return out


# ── Assignment CRUD ───────────────────────────────────────────────

def create_assignment(data: dict[str, Any]) -> Assignment:
    init_db()
    payload = _validate_assignment(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO assignments
                       (title, subject_id, year_group, form_group, type,
                        weight_pct, max_marks, set_date, due_date,
                        status, description, criteria, set_by, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["title"], payload["subject_id"],
                 payload["year_group"], payload["form_group"],
                 payload["type"], payload["weight_pct"],
                 payload["max_marks"], payload["set_date"],
                 payload["due_date"], payload["status"],
                 payload["description"], payload["criteria"],
                 payload["set_by"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create assignment")
        raise
    rec = get_assignment(new_id)
    assert rec is not None
    logger.info("Created assignment #%d '%s' (%s, Yr%s due %s)",
                rec.assignment_id, rec.title, rec.type,
                rec.year_group, rec.due_date)
    return rec


def get_assignment(assignment_id: int) -> Assignment | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT a.*, s.code AS subject_code, s.name AS subject_name
                   FROM assignments a
                   LEFT JOIN subjects s ON s.subject_id = a.subject_id
                   WHERE a.assignment_id = ?""",
                (assignment_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_assignment(%s) failed", assignment_id)
        raise
    return _row_assignment(r) if r else None


def list_assignments(*, year_group: str | None = None,
                     subject_id: int | None = None,
                     status: str | None = None,
                     type: str | None = None) -> list[Assignment]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("a.year_group = ?")
        params.append(year_group)
    if subject_id is not None:
        where.append("a.subject_id = ?")
        params.append(int(subject_id))
    if status:
        if status not in ASSIGNMENT_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(ASSIGNMENT_STATUSES)}")
        where.append("a.status = ?")
        params.append(status)
    if type:
        if type not in ASSIGNMENT_TYPES:
            raise ValidationError(
                f"Type filter must be one of "
                f"{', '.join(ASSIGNMENT_TYPES)}")
        where.append("a.type = ?")
        params.append(type)
    sql = ("""SELECT a.*, s.code AS subject_code, s.name AS subject_name
              FROM assignments a
              LEFT JOIN subjects s ON s.subject_id = a.subject_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY a.due_date DESC, a.assignment_id DESC"
    try:
        with _connect() as conn:
            return [_row_assignment(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_assignments failed")
        raise


def update_assignment(assignment_id: int,
                      data: dict[str, Any]) -> Assignment:
    init_db()
    existing = get_assignment(assignment_id)
    if existing is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    merged = {
        "title": data.get("title", existing.title),
        "subject_id": data.get("subject_id", existing.subject_id),
        "year_group": data.get("year_group", existing.year_group),
        "form_group": data.get("form_group", existing.form_group),
        "type": data.get("type", existing.type),
        "weight_pct": data.get("weight_pct", existing.weight_pct),
        "max_marks":  data.get("max_marks", existing.max_marks),
        "set_date":   data.get("set_date", existing.set_date),
        "due_date":   data.get("due_date", existing.due_date),
        "status":     data.get("status", existing.status),
        "description": data.get("description", existing.description),
        "criteria":   data.get("criteria", existing.criteria),
        "set_by":     data.get("set_by", existing.set_by),
        "notes":      data.get("notes", existing.notes),
    }
    payload = _validate_assignment(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE assignments SET
                       title = ?, subject_id = ?, year_group = ?,
                       form_group = ?, type = ?, weight_pct = ?,
                       max_marks = ?, set_date = ?, due_date = ?,
                       status = ?, description = ?, criteria = ?,
                       set_by = ?, notes = ?, updated_at = datetime('now')
                   WHERE assignment_id = ?""",
                (payload["title"], payload["subject_id"],
                 payload["year_group"], payload["form_group"],
                 payload["type"], payload["weight_pct"],
                 payload["max_marks"], payload["set_date"],
                 payload["due_date"], payload["status"],
                 payload["description"], payload["criteria"],
                 payload["set_by"], payload["notes"], assignment_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update assignment #%d", assignment_id)
        raise
    rec = get_assignment(assignment_id)
    assert rec is not None
    logger.info("Updated assignment #%d (status %s)",
                rec.assignment_id, rec.status)
    return rec


def set_status(assignment_id: int, new_status: str) -> Assignment:
    return update_assignment(assignment_id, {"status": new_status})


def delete_assignment(assignment_id: int) -> bool:
    init_db()
    existing = get_assignment(assignment_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            cur = conn.execute(
                "DELETE FROM assignments WHERE assignment_id = ?",
                (assignment_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete assignment #%d", assignment_id)
        raise
    if deleted:
        logger.info("Deleted assignment #%d '%s' (cascade: submissions)",
                    assignment_id, existing.title)
    return deleted


def status_counts() -> dict[str, int]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM assignments "
                "GROUP BY status").fetchall()
    except sqlite3.Error:
        logger.exception("assignments status_counts failed")
        raise
    counts = {s: 0 for s in ASSIGNMENT_STATUSES}
    for r in rows:
        counts[r["status"]] = r["n"]
    return counts


# ── Submissions ───────────────────────────────────────────────────

def seed_submissions(assignment_id: int) -> int:
    init_db()
    a = get_assignment(assignment_id)
    if a is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    from education_system.systems.secondary.domain.learners.pupils import (
        pupils as pupils_data,
    )
    pupils = [p for p in pupils_data.list_pupils()
              if p.year_group == a.year_group
              and (not a.form_group or p.form_group == a.form_group)]
    added = 0
    try:
        with _connect() as conn:
            for p in pupils:
                row = conn.execute(
                    "SELECT submission_id FROM assignment_submissions "
                    "WHERE assignment_id = ? AND pupil_id = ?",
                    (assignment_id, p.pupil_id),
                ).fetchone()
                if row:
                    continue
                conn.execute(
                    "INSERT INTO assignment_submissions "
                    "(assignment_id, pupil_id, status) VALUES (?, ?, ?)",
                    (assignment_id, p.pupil_id, DEFAULT_SUB_STATUS),
                )
                added += 1
            conn.commit()
    except sqlite3.Error:
        logger.exception("seed_submissions(%d) failed", assignment_id)
        raise
    logger.info("Seeded %d submission row(s) for assignment #%d",
                added, assignment_id)
    return added


def upsert_submission(assignment_id: int,
                      data: dict[str, Any]) -> AssignmentSubmission:
    init_db()
    a = get_assignment(assignment_id)
    if a is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    payload = _validate_submission(data, a.max_marks)
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT submission_id FROM assignment_submissions "
                "WHERE assignment_id = ? AND pupil_id = ?",
                (assignment_id, payload["pupil_id"]),
            ).fetchone()
            if row:
                conn.execute(
                    """UPDATE assignment_submissions SET
                           submitted_date = ?, status = ?,
                           marks_awarded = ?, grade = ?,
                           moderation_status = ?, moderator = ?,
                           feedback = ?, updated_at = datetime('now')
                       WHERE submission_id = ?""",
                    (payload["submitted_date"], payload["status"],
                     payload["marks_awarded"], payload["grade"],
                     payload["moderation_status"], payload["moderator"],
                     payload["feedback"], row["submission_id"]),
                )
                sid = row["submission_id"]
                action = "updated"
            else:
                cur = conn.execute(
                    """INSERT INTO assignment_submissions
                           (assignment_id, pupil_id, submitted_date,
                            status, marks_awarded, grade,
                            moderation_status, moderator, feedback)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (assignment_id, payload["pupil_id"],
                     payload["submitted_date"], payload["status"],
                     payload["marks_awarded"], payload["grade"],
                     payload["moderation_status"], payload["moderator"],
                     payload["feedback"]),
                )
                sid = cur.lastrowid
                action = "inserted"
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to upsert submission for assignment %d pupil %s",
            assignment_id, payload["pupil_id"])
        raise
    logger.info("Assignment submission %s: assignment=#%d pupil=%s "
                "status=%s marks=%s",
                action, assignment_id, payload["pupil_id"],
                payload["status"], payload["marks_awarded"])
    rec = get_submission(sid)
    assert rec is not None
    return rec


def get_submission(submission_id: int) -> AssignmentSubmission | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM assignment_submissions "
                "WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_submission(%s) failed", submission_id)
        raise
    return _row_submission(r) if r else None


def list_submissions(assignment_id: int) -> list[AssignmentSubmission]:
    init_db()
    try:
        with _connect() as conn:
            return [_row_submission(r) for r in conn.execute(
                "SELECT * FROM assignment_submissions "
                "WHERE assignment_id = ? ORDER BY pupil_id",
                (assignment_id,),
            ).fetchall()]
    except sqlite3.Error:
        logger.exception("list_submissions(%s) failed", assignment_id)
        raise


def delete_submission(submission_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM assignment_submissions "
                "WHERE submission_id = ?", (submission_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete submission #%d", submission_id)
        raise
    if deleted:
        logger.info("Deleted assignment submission #%d", submission_id)
    return deleted


def submission_summary(assignment_id: int) -> dict[str, Any]:
    init_db()
    a = get_assignment(assignment_id)
    if a is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    rows = list_submissions(assignment_id)
    by_status = Counter(r.status for r in rows)
    marks = [r.marks_awarded for r in rows if r.marks_awarded is not None]
    avg_marks = round(sum(marks) / len(marks), 2) if marks else None
    avg_pct = (round(100.0 * avg_marks / a.max_marks, 2)
                if avg_marks is not None and a.max_marks else None)
    return {
        "assignment":   a,
        "total":        len(rows),
        "marked":       len(marks),
        "by_status":    {s: by_status.get(s, 0) for s in SUBMISSION_STATUSES},
        "avg_marks":    avg_marks,
        "avg_pct":      avg_pct,
        "max_marks":    a.max_marks,
    }
