"""Homework data layer for the Primary School System.

Two tables:

* ``homework_assignments``  — one row per homework task. Links to a
                               subject and a year/form. Lifecycle is
                               Draft → Set → Closed.
* ``homework_submissions``  — one row per pupil per assignment. Holds
                               the pupil's submitted_date, status
                               (Pending / Submitted / Late / Missing /
                               Graded / Excused), grade, mark_pct, and
                               teacher feedback.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

ASSIGNMENT_STATUSES: tuple[str, ...] = ("Draft", "Set", "Closed")
DEFAULT_ASSIGNMENT_STATUS: str = "Draft"

SUBMISSION_STATUSES: tuple[str, ...] = (
    "Pending", "Submitted", "Late", "Missing", "Graded", "Excused")
DEFAULT_SUBMISSION_STATUS: str = "Pending"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS homework_assignments (
    assignment_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT NOT NULL,
    subject_id       INTEGER NOT NULL,
    year_group       TEXT NOT NULL,
    form_group       TEXT,
    set_by           TEXT,
    set_date         TEXT NOT NULL DEFAULT (date('now')),
    due_date         TEXT NOT NULL,
    points           INTEGER,
    status           TEXT NOT NULL DEFAULT 'Draft',
    instructions     TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
);

CREATE TABLE IF NOT EXISTS homework_submissions (
    submission_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id    INTEGER NOT NULL,
    pupil_id         TEXT NOT NULL,
    submitted_date   TEXT,
    status           TEXT NOT NULL DEFAULT 'Pending',
    grade            TEXT,
    mark_pct         REAL,
    feedback         TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    UNIQUE (assignment_id, pupil_id),
    FOREIGN KEY (assignment_id) REFERENCES homework_assignments(assignment_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_hw_due
    ON homework_assignments(due_date);
CREATE INDEX IF NOT EXISTS idx_hw_year
    ON homework_assignments(year_group);
CREATE INDEX IF NOT EXISTS idx_hwsub_pupil
    ON homework_submissions(pupil_id);
"""


@dataclass
class Assignment:
    assignment_id: int
    title: str
    subject_id: int
    year_group: str
    form_group: str | None
    set_by: str | None
    set_date: str
    due_date: str
    points: int | None
    status: str
    instructions: str | None
    notes: str | None
    subject_code: str | None = None
    subject_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class Submission:
    submission_id: int
    assignment_id: int
    pupil_id: str
    submitted_date: str | None
    status: str
    grade: str | None
    mark_pct: float | None
    feedback: str | None
    created_at: str | None = None
    updated_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.primary.domain.academics.subjects import (
        subjects as subjects_data,
    )
    subjects_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise homework tables")
        raise
    logger.info("Secondary homework tables ready")
    _DB_READY = True


def _row_assignment(r: sqlite3.Row) -> Assignment:
    keys = r.keys()
    return Assignment(
        assignment_id=r["assignment_id"], title=r["title"],
        subject_id=r["subject_id"], year_group=r["year_group"],
        form_group=r["form_group"], set_by=r["set_by"],
        set_date=r["set_date"], due_date=r["due_date"],
        points=r["points"], status=r["status"],
        instructions=r["instructions"], notes=r["notes"],
        subject_code=r["subject_code"] if "subject_code" in keys else None,
        subject_name=r["subject_name"] if "subject_name" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_submission(r: sqlite3.Row) -> Submission:
    return Submission(
        submission_id=r["submission_id"],
        assignment_id=r["assignment_id"],
        pupil_id=r["pupil_id"],
        submitted_date=r["submitted_date"], status=r["status"],
        grade=r["grade"], mark_pct=r["mark_pct"],
        feedback=r["feedback"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation helpers ────────────────────────────────────────────

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
    from education_system.systems.primary.domain.academics.subjects import (
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

    set_date = _validate_date(data.get("set_date") or _dt.date.today().isoformat(),
                               "Set date")
    due_date = _validate_date(data.get("due_date"), "Due date")
    if due_date < set_date:
        raise ValidationError("Due date cannot be before set date")
    out["set_date"] = set_date
    out["due_date"] = due_date

    pts = data.get("points")
    if pts in (None, ""):
        out["points"] = None
    else:
        try:
            n = int(pts)
        except (TypeError, ValueError):
            raise ValidationError("Points must be a whole number") from None
        if n < 0 or n > 1000:
            raise ValidationError("Points must be between 0 and 1000")
        out["points"] = n

    status = (data.get("status") or DEFAULT_ASSIGNMENT_STATUS).strip()
    if status not in ASSIGNMENT_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(ASSIGNMENT_STATUSES)}")
    out["status"] = status

    out["set_by"]       = (data.get("set_by") or "").strip() or None
    out["instructions"] = (data.get("instructions") or "").strip() or None
    out["notes"]        = (data.get("notes") or "").strip() or None
    return out


def _validate_submission(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    out["pupil_id"] = pid

    out["submitted_date"] = _validate_date(
        data.get("submitted_date"), "Submitted date", required=False)

    status = (data.get("status") or DEFAULT_SUBMISSION_STATUS).strip()
    if status not in SUBMISSION_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(SUBMISSION_STATUSES)}")
    out["status"] = status

    out["grade"] = (data.get("grade") or "").strip() or None

    pct = data.get("mark_pct")
    if pct in (None, "") or (isinstance(pct, str) and not pct.strip()):
        out["mark_pct"] = None
    else:
        try:
            v = float(pct)
        except (TypeError, ValueError):
            raise ValidationError(
                "Mark % must be a number between 0 and 100") from None
        if v < 0 or v > 100:
            raise ValidationError("Mark % must be between 0 and 100")
        out["mark_pct"] = v

    out["feedback"] = (data.get("feedback") or "").strip() or None
    return out


# ── Assignment CRUD ───────────────────────────────────────────────

def create_assignment(data: dict[str, Any]) -> Assignment:
    init_db()
    payload = _validate_assignment(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO homework_assignments
                       (title, subject_id, year_group, form_group,
                        set_by, set_date, due_date, points, status,
                        instructions, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["title"], payload["subject_id"],
                 payload["year_group"], payload["form_group"],
                 payload["set_by"], payload["set_date"],
                 payload["due_date"], payload["points"],
                 payload["status"], payload["instructions"],
                 payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create homework assignment")
        raise
    rec = get_assignment(new_id)
    assert rec is not None
    logger.info("Created homework assignment #%d '%s' (Yr%s due %s status=%s)",
                rec.assignment_id, rec.title, rec.year_group,
                rec.due_date, rec.status)
    return rec


def get_assignment(assignment_id: int) -> Assignment | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT a.*, s.code AS subject_code, s.name AS subject_name
                   FROM homework_assignments a
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
                     teacher: str | None = None,
                     due_from: str | None = None,
                     due_to: str | None = None) -> list[Assignment]:
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
                f"Status filter must be one of {', '.join(ASSIGNMENT_STATUSES)}")
        where.append("a.status = ?")
        params.append(status)
    if teacher:
        where.append("a.set_by = ?")
        params.append(teacher.strip())
    if due_from:
        where.append("a.due_date >= ?")
        params.append(_validate_date(due_from, "From due date"))
    if due_to:
        where.append("a.due_date <= ?")
        params.append(_validate_date(due_to, "To due date"))
    sql = ("""SELECT a.*, s.code AS subject_code, s.name AS subject_name
              FROM homework_assignments a
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
        raise ValidationError(f"No homework assignment #{assignment_id}")
    merged = {
        "title":        data.get("title", existing.title),
        "subject_id":   data.get("subject_id", existing.subject_id),
        "year_group":   data.get("year_group", existing.year_group),
        "form_group":   data.get("form_group", existing.form_group),
        "set_by":       data.get("set_by", existing.set_by),
        "set_date":     data.get("set_date", existing.set_date),
        "due_date":     data.get("due_date", existing.due_date),
        "points":       data.get("points", existing.points),
        "status":       data.get("status", existing.status),
        "instructions": data.get("instructions", existing.instructions),
        "notes":        data.get("notes", existing.notes),
    }
    payload = _validate_assignment(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE homework_assignments SET
                       title = ?, subject_id = ?, year_group = ?,
                       form_group = ?, set_by = ?, set_date = ?,
                       due_date = ?, points = ?, status = ?,
                       instructions = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE assignment_id = ?""",
                (payload["title"], payload["subject_id"],
                 payload["year_group"], payload["form_group"],
                 payload["set_by"], payload["set_date"],
                 payload["due_date"], payload["points"],
                 payload["status"], payload["instructions"],
                 payload["notes"], assignment_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update assignment #%d", assignment_id)
        raise
    rec = get_assignment(assignment_id)
    assert rec is not None
    logger.info("Updated homework assignment #%d (status %s)",
                rec.assignment_id, rec.status)
    return rec


def set_assignment_status(assignment_id: int,
                          new_status: str) -> Assignment:
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
                "DELETE FROM homework_assignments WHERE assignment_id = ?",
                (assignment_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete assignment #%d", assignment_id)
        raise
    if deleted:
        logger.info("Deleted homework assignment #%d '%s' "
                    "(cascade: submissions)",
                    assignment_id, existing.title)
    return deleted


def assignment_status_counts() -> dict[str, int]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM homework_assignments "
                "GROUP BY status").fetchall()
    except sqlite3.Error:
        logger.exception("assignment_status_counts failed")
        raise
    counts = {s: 0 for s in ASSIGNMENT_STATUSES}
    for r in rows:
        counts[r["status"]] = r["n"]
    return counts


# ── Submissions ───────────────────────────────────────────────────

def seed_submissions(assignment_id: int) -> int:
    """Create a Pending submission for every pupil matching the
    assignment's year_group (and form_group, if set). Idempotent —
    pupils that already have a submission row are skipped."""
    init_db()
    a = get_assignment(assignment_id)
    if a is None:
        raise ValidationError(f"No homework assignment #{assignment_id}")
    from education_system.systems.primary.domain.learners.pupils import (
        pupils as pupils_data,
    )
    pupils = pupils_data.list_pupils()
    pupils = [p for p in pupils if p.year_group == a.year_group]
    if a.form_group:
        pupils = [p for p in pupils if p.form_group == a.form_group]
    added = 0
    try:
        with _connect() as conn:
            for p in pupils:
                row = conn.execute(
                    "SELECT submission_id FROM homework_submissions "
                    "WHERE assignment_id = ? AND pupil_id = ?",
                    (assignment_id, p.pupil_id),
                ).fetchone()
                if row:
                    continue
                conn.execute(
                    "INSERT INTO homework_submissions "
                    "(assignment_id, pupil_id, status) VALUES (?, ?, ?)",
                    (assignment_id, p.pupil_id, DEFAULT_SUBMISSION_STATUS),
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
                      data: dict[str, Any]) -> Submission:
    """Insert or update a pupil's submission for an assignment."""
    init_db()
    a = get_assignment(assignment_id)
    if a is None:
        raise ValidationError(f"No homework assignment #{assignment_id}")
    payload = _validate_submission(data)
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT submission_id FROM homework_submissions "
                "WHERE assignment_id = ? AND pupil_id = ?",
                (assignment_id, payload["pupil_id"]),
            ).fetchone()
            if row:
                conn.execute(
                    """UPDATE homework_submissions SET
                           submitted_date = ?, status = ?, grade = ?,
                           mark_pct = ?, feedback = ?,
                           updated_at = datetime('now')
                       WHERE submission_id = ?""",
                    (payload["submitted_date"], payload["status"],
                     payload["grade"], payload["mark_pct"],
                     payload["feedback"], row["submission_id"]),
                )
                sid = row["submission_id"]
                action = "updated"
            else:
                cur = conn.execute(
                    """INSERT INTO homework_submissions
                           (assignment_id, pupil_id, submitted_date,
                            status, grade, mark_pct, feedback)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (assignment_id, payload["pupil_id"],
                     payload["submitted_date"], payload["status"],
                     payload["grade"], payload["mark_pct"],
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
    logger.info("Submission %s: assignment=#%d pupil=%s status=%s",
                action, assignment_id, payload["pupil_id"],
                payload["status"])
    rec = get_submission(sid)
    assert rec is not None
    return rec


def get_submission(submission_id: int) -> Submission | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM homework_submissions WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_submission(%s) failed", submission_id)
        raise
    return _row_submission(r) if r else None


def list_submissions(assignment_id: int) -> list[Submission]:
    init_db()
    try:
        with _connect() as conn:
            return [_row_submission(r) for r in conn.execute(
                "SELECT * FROM homework_submissions "
                "WHERE assignment_id = ? ORDER BY pupil_id",
                (assignment_id,),
            ).fetchall()]
    except sqlite3.Error:
        logger.exception("list_submissions(%s) failed", assignment_id)
        raise


def list_for_pupil(pupil_id: str, *,
                   status: str | None = None) -> list[Submission]:
    init_db()
    pid = (pupil_id or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    where = ["pupil_id = ?"]
    params: list[Any] = [pid]
    if status:
        if status not in SUBMISSION_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(SUBMISSION_STATUSES)}")
        where.append("status = ?")
        params.append(status)
    sql = ("SELECT * FROM homework_submissions WHERE "
           + " AND ".join(where)
           + " ORDER BY updated_at DESC")
    try:
        with _connect() as conn:
            return [_row_submission(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_for_pupil(%s) failed", pupil_id)
        raise


def delete_submission(submission_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM homework_submissions WHERE submission_id = ?",
                (submission_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete submission #%d", submission_id)
        raise
    if deleted:
        logger.info("Deleted homework submission #%d", submission_id)
    return deleted


def submission_summary(assignment_id: int) -> dict[str, Any]:
    init_db()
    a = get_assignment(assignment_id)
    if a is None:
        raise ValidationError(f"No homework assignment #{assignment_id}")
    rows = list_submissions(assignment_id)
    counts = Counter(r.status for r in rows)
    marked = [r.mark_pct for r in rows if r.mark_pct is not None]
    avg_pct = round(sum(marked) / len(marked), 2) if marked else None
    return {
        "assignment":   a,
        "total":        len(rows),
        "by_status":    {s: counts.get(s, 0) for s in SUBMISSION_STATUSES},
        "avg_mark_pct": avg_pct,
        "marked":       len(marked),
    }
