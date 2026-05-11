"""Homework & Coursework data layer for the Sixth Form System.

Two tables:

* ``assignments`` — one row per piece of work set to a class group
  (homework, essay, coursework, etc.).
* ``submissions`` — one row per (assignment, student), tracking
  whether the student handed it in, when, and what they scored.

Cascades from ``class_groups`` and ``students`` keep the schema tidy:
delete a group and its assignments + submissions go with it.

The "mark register" model mirrors attendance: ``submission_view``
returns the roster joined to any existing submissions; ``save_submissions``
upserts the lot in one transaction.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.HOMEWORK_DB

ASSIGNMENT_TYPES: tuple[str, ...] = (
    "Homework",
    "Essay",
    "Coursework",
    "Lab Report",
    "Practical",
    "Presentation",
    "Test",
)
DEFAULT_ASSIGNMENT_TYPE: str = "Homework"

SUBMISSION_STATUSES: tuple[str, ...] = (
    "Not Submitted", "Submitted", "Late", "Excused",
)
DEFAULT_SUBMISSION_STATUS: str = "Not Submitted"
SUBMITTED_STATUSES: tuple[str, ...] = ("Submitted", "Late")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id      INTEGER NOT NULL,
    title         TEXT NOT NULL,
    description   TEXT,
    type          TEXT NOT NULL DEFAULT 'Homework',
    set_date      TEXT NOT NULL,
    due_date      TEXT NOT NULL,
    max_marks     INTEGER DEFAULT 100,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (group_id) REFERENCES class_groups(group_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS submissions (
    submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER NOT NULL,
    student_id    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'Not Submitted',
    submitted_at  TEXT,
    marks         INTEGER,
    feedback      TEXT,
    marked_at     TEXT,
    UNIQUE(assignment_id, student_id),
    FOREIGN KEY (assignment_id) REFERENCES assignments(assignment_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id)    REFERENCES students(student_id)       ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_assignments_group   ON assignments(group_id);
CREATE INDEX IF NOT EXISTS idx_assignments_due     ON assignments(due_date);
CREATE INDEX IF NOT EXISTS idx_submissions_assn    ON submissions(assignment_id);
CREATE INDEX IF NOT EXISTS idx_submissions_student ON submissions(student_id);
"""


@dataclass
class Assignment:
    assignment_id: int
    group_id: int
    title: str
    description: str | None
    type: str
    set_date: str
    due_date: str
    max_marks: int | None
    notes: str | None
    created_at: str


@dataclass
class Submission:
    submission_id: int
    assignment_id: int
    student_id: str
    status: str
    submitted_at: str | None
    marks: int | None
    feedback: str | None
    marked_at: str | None


@dataclass
class SubmissionView:
    """One row in the assignment's mark sheet: student + any existing submission."""
    student_id: str
    full_name: str
    submission: Submission | None


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    # FKs reference class_groups + students, so make sure those exist.
    from education_system.sixthform_system.modules.domain.class_groups import class_groups as _cg
    _cg.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Homework schema ready at %s", DB_PATH)


def _row_assn(r: sqlite3.Row) -> Assignment:
    return Assignment(
        assignment_id=r["assignment_id"], group_id=r["group_id"],
        title=r["title"], description=r["description"], type=r["type"],
        set_date=r["set_date"], due_date=r["due_date"],
        max_marks=r["max_marks"], notes=r["notes"],
        created_at=r["created_at"],
    )


def _row_sub(r: sqlite3.Row) -> Submission:
    return Submission(
        submission_id=r["submission_id"],
        assignment_id=r["assignment_id"],
        student_id=r["student_id"],
        status=r["status"],
        submitted_at=r["submitted_at"],
        marks=r["marks"],
        feedback=r["feedback"],
        marked_at=r["marked_at"],
    )


# ── Validation ─────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for any invalid homework / submission input."""


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(s: str, label: str) -> str:
    s = (s or "").strip()
    if not s:
        raise ValidationError(f"{label} is required")
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_datetime_opt(s: str | None) -> str | None:
    if s in (None, "") or (isinstance(s, str) and not s.strip()):
        return None
    s = s.strip()
    if not _DATETIME_RE.match(s):
        raise ValidationError("submitted_at must be YYYY-MM-DD [HH:MM[:SS]]")
    return s


def _validate_assignment_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    gid_raw = _require(data.get("group_id"), "Class group")
    try:
        gid = int(gid_raw)
    except (TypeError, ValueError):
        raise ValidationError("Class group must be selected") from None
        from education_system.sixthform_system.modules.domain.class_groups import class_groups as _cg
    if _cg.get_group(gid) is None:
        raise ValidationError(f"No class group with id {gid}")
    out["group_id"] = gid

    out["title"] = _require(data.get("title"), "Title").strip()

    a_type = (data.get("type") or DEFAULT_ASSIGNMENT_TYPE).strip()
    if a_type not in ASSIGNMENT_TYPES:
        raise ValidationError(
            f"Type must be one of: {', '.join(ASSIGNMENT_TYPES)}")
    out["type"] = a_type

    set_d = _validate_date(data.get("set_date"), "Set date")
    due_d = _validate_date(data.get("due_date"), "Due date")
    if due_d < set_d:
        raise ValidationError("Due date cannot be before set date")
    out["set_date"] = set_d
    out["due_date"] = due_d

    mx_raw = data.get("max_marks")
    if mx_raw in (None, ""):
        out["max_marks"] = None
    else:
        try:
            mx = int(mx_raw)
        except (TypeError, ValueError):
            raise ValidationError(
                "Max marks must be a whole number or blank") from None
        if mx <= 0 or mx > 1000:
            raise ValidationError("Max marks must be between 1 and 1000")
        out["max_marks"] = mx

    out["description"] = (data.get("description") or "").strip() or None
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def _validate_submission_payload(
    data: dict[str, Any], *, max_marks: int | None,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    status = (data.get("status") or DEFAULT_SUBMISSION_STATUS).strip()
    if status not in SUBMISSION_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(SUBMISSION_STATUSES)}")
    out["status"] = status

    out["submitted_at"] = _validate_datetime_opt(data.get("submitted_at"))

    mk_raw = data.get("marks")
    if mk_raw in (None, ""):
        out["marks"] = None
    else:
        try:
            mk = int(mk_raw)
        except (TypeError, ValueError):
            raise ValidationError("Marks must be a whole number") from None
        if mk < 0:
            raise ValidationError("Marks must be ≥ 0")
        if max_marks is not None and mk > max_marks:
            raise ValidationError(
                f"Marks ({mk}) exceed max for this assignment ({max_marks})")
        out["marks"] = mk

    out["feedback"] = (data.get("feedback") or "").strip() or None
    return out


# ── Assignment CRUD ────────────────────────────────────────────────

def create_assignment(data: dict[str, Any]) -> Assignment:
    init_db()
    try:
        payload = _validate_assignment_payload(data)
    except ValidationError as e:
        logger.warning("create_assignment validation failed: %s", e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO assignments
               (group_id, title, description, type, set_date, due_date,
                max_marks, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (payload["group_id"], payload["title"], payload["description"],
             payload["type"], payload["set_date"], payload["due_date"],
             payload["max_marks"], payload["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    a = get_assignment(new_id)
    assert a is not None
    logger.info(
        "Created assignment #%d (%s, group #%d, due %s)",
        new_id, a.title, a.group_id, a.due_date,
    )
    return a


def get_assignment(assignment_id: int) -> Assignment | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM assignments WHERE assignment_id = ?",
            (assignment_id,),
        ).fetchone()
        return _row_assn(r) if r else None


def list_assignments(
    *,
    group_id: int | None = None,
    type: str | None = None,
    due_from: str | None = None,
    due_to: str | None = None,
    search: str | None = None,
) -> list[Assignment]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if group_id is not None:
        clauses.append("group_id = ?")
        args.append(group_id)
    if type:
        if type not in ASSIGNMENT_TYPES:
            raise ValidationError(
                f"Type must be one of: {', '.join(ASSIGNMENT_TYPES)}")
        clauses.append("type = ?")
        args.append(type)
    if due_from:
        clauses.append("due_date >= ?")
        args.append(_validate_date(due_from, "due_from"))
    if due_to:
        clauses.append("due_date <= ?")
        args.append(_validate_date(due_to, "due_to"))
    if search:
        q = f"%{search.strip()}%"
        clauses.append("(title LIKE ? OR description LIKE ?)")
        args.extend([q, q])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM assignments {where} "
           "ORDER BY due_date DESC, assignment_id DESC")
    with _connect() as conn:
        return [_row_assn(r) for r in conn.execute(sql, args).fetchall()]


def update_assignment(assignment_id: int, data: dict[str, Any]) -> Assignment:
    init_db()
    existing = get_assignment(assignment_id)
    if existing is None:
        logger.warning("update_assignment: unknown id %d", assignment_id)
        raise ValidationError(f"No assignment with id {assignment_id}")
    try:
        payload = _validate_assignment_payload(data)
    except ValidationError as e:
        logger.warning(
            "update_assignment(%d) validation failed: %s", assignment_id, e)
        raise

    # If max_marks is lowered below an existing student's marks, refuse.
    if payload["max_marks"] is not None:
        with _connect() as conn:
            row = conn.execute(
                "SELECT MAX(marks) AS m FROM submissions "
                "WHERE assignment_id = ? AND marks IS NOT NULL",
                (assignment_id,),
            ).fetchone()
        if row and row["m"] is not None and row["m"] > payload["max_marks"]:
            raise ValidationError(
                f"Cannot set max to {payload['max_marks']}: at least one "
                f"submission already has {row['m']} marks"
            )

    with _connect() as conn:
        conn.execute(
            """UPDATE assignments SET
                  group_id = ?, title = ?, description = ?, type = ?,
                  set_date = ?, due_date = ?, max_marks = ?, notes = ?
               WHERE assignment_id = ?""",
            (payload["group_id"], payload["title"], payload["description"],
             payload["type"], payload["set_date"], payload["due_date"],
             payload["max_marks"], payload["notes"], assignment_id),
        )
        conn.commit()
    a = get_assignment(assignment_id)
    assert a is not None
    logger.info("Updated assignment #%d (%s)", assignment_id, a.title)
    return a


def delete_assignment(assignment_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM assignments WHERE assignment_id = ?",
            (assignment_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted assignment #%d", assignment_id)
            return True
        logger.warning("delete_assignment: unknown id %d", assignment_id)
        return False


# ── Submission roster & bulk save ──────────────────────────────────

def submission_view(assignment_id: int) -> list[SubmissionView]:
    """Roster (all class-group members) joined to any existing submission."""
    init_db()
    a = get_assignment(assignment_id)
    if a is None:
        raise ValidationError(f"No assignment with id {assignment_id}")
        from education_system.sixthform_system.modules.domain.class_groups import class_groups
        from education_system.sixthform_system.modules.domain.students import students as _cg
        from education_system.sixthform_system.modules.domain.students import students as _students
    members = _cg.list_members(a.group_id)
    student_index = {s.student_id: s for s in _students.list_students()
                     if s.student_id in members}

    with _connect() as conn:
        rows = {
            r["student_id"]: _row_sub(r)
            for r in conn.execute(
                "SELECT * FROM submissions WHERE assignment_id = ?",
                (assignment_id,),
            ).fetchall()
        }

    out: list[SubmissionView] = []
    for sid in members:
        student = student_index.get(sid)
        out.append(SubmissionView(
            student_id=sid,
            full_name=student.full_name if student else "(unknown)",
            submission=rows.get(sid),
        ))
    return out


def save_submissions(
    assignment_id: int, entries: dict[str, dict[str, Any]],
) -> int:
    """Upsert submission rows for an assignment in one transaction.

    ``entries`` maps ``student_id`` → ``{"status", "submitted_at", "marks", "feedback"}``.
    Missing students are left untouched. Returns the number of rows written.
    """
    init_db()
    assn = get_assignment(assignment_id)
    if assn is None:
        raise ValidationError(f"No assignment with id {assignment_id}")

    # Pre-validate all before writing.
    cleaned: list[tuple[str, dict[str, Any]]] = []
    for sid, payload in entries.items():
        cleaned.append((sid, _validate_submission_payload(
            payload, max_marks=assn.max_marks)))

    written = 0
    try:
        with _connect() as conn:
            for sid, p in cleaned:
                marked_at = "datetime('now')" if p.get("marks") is not None else "marked_at"
                conn.execute(
                    f"""INSERT INTO submissions
                          (assignment_id, student_id, status,
                           submitted_at, marks, feedback,
                           marked_at)
                       VALUES (?, ?, ?, ?, ?, ?,
                               CASE WHEN ? IS NOT NULL THEN datetime('now')
                                    ELSE NULL END)
                       ON CONFLICT(assignment_id, student_id) DO UPDATE SET
                          status       = excluded.status,
                          submitted_at = excluded.submitted_at,
                          marks        = excluded.marks,
                          feedback     = excluded.feedback,
                          marked_at    = CASE
                              WHEN excluded.marks IS NOT NULL
                                  THEN datetime('now')
                              ELSE submissions.marked_at
                          END""",
                    (
                        assignment_id, sid, p["status"],
                        p["submitted_at"], p["marks"], p["feedback"],
                        p["marks"],
                    ),
                )
                written += 1
            conn.commit()
    except sqlite3.Error as e:
        logger.exception("save_submissions DB error")
        raise ValidationError(f"Database error: {e}") from e

    logger.info(
        "Saved %d submission(s) for assignment #%d", written, assignment_id,
    )
    return written


def get_submission(submission_id: int) -> Submission | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM submissions WHERE submission_id = ?",
            (submission_id,),
        ).fetchone()
        return _row_sub(r) if r else None


def list_submissions(
    *,
    assignment_id: int | None = None,
    student_id: str | None = None,
    group_id: int | None = None,
    status: str | None = None,
) -> list[Submission]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if assignment_id is not None:
        clauses.append("assignment_id = ?")
        args.append(assignment_id)
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id)
    if status:
        if status not in SUBMISSION_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(SUBMISSION_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if group_id is not None:
        clauses.append(
            "assignment_id IN (SELECT assignment_id FROM assignments "
            "WHERE group_id = ?)"
        )
        args.append(group_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM submissions {where} "
           "ORDER BY assignment_id DESC, student_id")
    with _connect() as conn:
        return [_row_sub(r) for r in conn.execute(sql, args).fetchall()]


def update_submission(submission_id: int, data: dict[str, Any]) -> Submission:
    init_db()
    existing = get_submission(submission_id)
    if existing is None:
        logger.warning("update_submission: unknown id %d", submission_id)
        raise ValidationError(f"No submission with id {submission_id}")
    assn = get_assignment(existing.assignment_id)
    p = _validate_submission_payload(
        {
            "status": data.get("status", existing.status),
            "submitted_at": data.get("submitted_at", existing.submitted_at),
            "marks": data.get("marks", existing.marks),
            "feedback": data.get("feedback", existing.feedback),
        },
        max_marks=assn.max_marks if assn else None,
    )
    with _connect() as conn:
        conn.execute(
            """UPDATE submissions SET
                  status = ?, submitted_at = ?, marks = ?, feedback = ?,
                  marked_at = CASE WHEN ? IS NOT NULL THEN datetime('now')
                                   ELSE marked_at END
               WHERE submission_id = ?""",
            (p["status"], p["submitted_at"], p["marks"], p["feedback"],
             p["marks"], submission_id),
        )
        conn.commit()
    logger.info(
        "Updated submission #%d (student=%s, status=%s, marks=%s)",
        submission_id, existing.student_id, p["status"], p["marks"],
    )
    out = get_submission(submission_id)
    assert out is not None
    return out


def delete_submission(submission_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM submissions WHERE submission_id = ?",
            (submission_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted submission #%d", submission_id)
            return True
        logger.warning("delete_submission: unknown id %d", submission_id)
        return False


# ── Summaries ──────────────────────────────────────────────────────

@dataclass
class StudentSummary:
    total: int           # number of assignments set to their group
    submitted: int       # Submitted or Late
    not_submitted: int
    late: int
    excused: int
    marked: int          # submissions with marks recorded
    avg_pct: float | None  # average percentage of marks/max_marks

    @property
    def submission_rate(self) -> float | None:
        if self.total == 0:
            return None
        return round(100.0 * self.submitted / self.total, 1)


def per_student_summary_for_group(
    group_id: int,
    *,
    type: str | None = None,
    due_from: str | None = None,
    due_to: str | None = None,
) -> dict[str, StudentSummary]:
    """Per-student summary for every member of the group, scoped to a
    type / date range if given."""
    init_db()
    from education_system.sixthform_system.modules.domain.class_groups import class_groups as _cg
    members = _cg.list_members(group_id)
    if not members:
        return {}

    # Fetch the relevant assignments for this group up front.
    assns = list_assignments(
        group_id=group_id, type=type, due_from=due_from, due_to=due_to)
    if not assns:
        return {sid: StudentSummary(0, 0, 0, 0, 0, 0, None) for sid in members}
    assn_ids = [a.assignment_id for a in assns]
    placeholders = ",".join("?" * len(assn_ids))

    by_student: dict[str, dict[str, Any]] = {
        sid: {"total": len(assns), "submitted": 0, "not_submitted": 0,
              "late": 0, "excused": 0,
              "marked": 0, "weighted_total": 0.0}
        for sid in members
    }

    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT s.student_id, s.status, s.marks, a.max_marks
                FROM submissions s
                JOIN assignments a ON a.assignment_id = s.assignment_id
                WHERE s.assignment_id IN ({placeholders})""",
            assn_ids,
        ).fetchall()

    # Default rows for students with no submission: count as Not Submitted.
    seen: set[tuple[str, int]] = set()  # (student_id, assignment_id)
    for r in rows:
        sid = r["student_id"]
        st = r["status"]
        if sid not in by_student:
            continue
        d = by_student[sid]
        if st in SUBMITTED_STATUSES:
            d["submitted"] += 1
        elif st == "Excused":
            d["excused"] += 1
            d["total"] -= 1  # excused removes from denominator
        else:
            d["not_submitted"] += 1
        if st == "Late":
            d["late"] += 1
        if r["marks"] is not None and r["max_marks"]:
            d["marked"] += 1
            d["weighted_total"] += (r["marks"] / r["max_marks"])

    out: dict[str, StudentSummary] = {}
    for sid, d in by_student.items():
        avg = round(100.0 * d["weighted_total"] / d["marked"], 1) \
              if d["marked"] else None
        # Any assignments with no row at all count as Not Submitted.
        accounted = (d["submitted"] + d["not_submitted"] + d["excused"])
        missing = max(0, len(assns) - accounted - d["excused"])
        d["not_submitted"] += missing
        out[sid] = StudentSummary(
            total=d["total"], submitted=d["submitted"],
            not_submitted=d["not_submitted"], late=d["late"],
            excused=d["excused"], marked=d["marked"], avg_pct=avg,
        )
    return out
