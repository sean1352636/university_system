"""Personal-statement drafts for the Sixth Form System.

UCAS allows one personal statement of up to **4000 characters** or **47
lines** (whichever comes first). Staff and students iterate through
multiple drafts before submission, so this module stores a *history*
of drafts per student — distinct from the single ``personal_statement``
column on ``ucas_applications`` which holds the *final* version that
goes with the application.

The ``push_to_ucas`` action copies a chosen draft (typically the
Approved one) onto the student's current-cycle UCAS application.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.systems.sixth_form.infrastructure import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.PERSONAL_STATEMENTS_DB

STATUSES: tuple[str, ...] = ("Draft", "In Review", "Approved", "Submitted")
DEFAULT_STATUS: str = "Draft"

# UCAS hard limits.
MAX_CHARS: int = 4000
MAX_LINES: int = 47

_SCHEMA = """
CREATE TABLE IF NOT EXISTS personal_statements (
    statement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    title        TEXT,
    body         TEXT NOT NULL,
    word_count   INTEGER NOT NULL DEFAULT 0,
    char_count   INTEGER NOT NULL DEFAULT 0,
    line_count   INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'Draft',
    feedback     TEXT,
    reviewer     TEXT,
    reviewed_at  TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ps_student ON personal_statements(student_id);
CREATE INDEX IF NOT EXISTS idx_ps_status  ON personal_statements(status);
"""


@dataclass
class PersonalStatement:
    statement_id: int
    student_id: str
    title: str | None
    body: str
    word_count: int
    char_count: int
    line_count: int
    status: str
    feedback: str | None
    reviewer: str | None
    reviewed_at: str | None
    created_at: str
    updated_at: str


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
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Personal-statements schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> PersonalStatement:
    return PersonalStatement(
        statement_id=r["statement_id"], student_id=r["student_id"],
        title=r["title"], body=r["body"],
        word_count=r["word_count"], char_count=r["char_count"],
        line_count=r["line_count"],
        status=r["status"], feedback=r["feedback"],
        reviewer=r["reviewer"], reviewed_at=r["reviewed_at"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Counting helpers ──────────────────────────────────────────────

def compute_counts(body: str) -> tuple[int, int, int]:
    """Return ``(word_count, char_count, line_count)`` for a draft.

    Lines follow UCAS's "newline-terminated" definition: a final
    line without a trailing newline still counts. Words are
    whitespace-split.
    """
    if body is None:
        return 0, 0, 0
    char_count = len(body)
    word_count = len(body.split())
    if not body:
        line_count = 0
    else:
        line_count = body.count("\n") + (0 if body.endswith("\n") else 1)
    return word_count, char_count, line_count


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid personal-statement input."""


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    sid = (data.get("student_id") or "").strip()
    if not sid:
        raise ValidationError("Student ID is required")
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    body = data.get("body") or ""
    if not body.strip():
        raise ValidationError("Body cannot be empty")
    word_count, char_count, line_count = compute_counts(body)
    if char_count > MAX_CHARS:
        raise ValidationError(
            f"Character count {char_count} exceeds UCAS limit of {MAX_CHARS}")
    if line_count > MAX_LINES:
        raise ValidationError(
            f"Line count {line_count} exceeds UCAS limit of {MAX_LINES}")
    out["body"] = body
    out["word_count"] = word_count
    out["char_count"] = char_count
    out["line_count"] = line_count

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    out["title"]    = (data.get("title") or "").strip() or None
    out["feedback"] = (data.get("feedback") or "").strip() or None
    out["reviewer"] = (data.get("reviewer") or "").strip() or None
    reviewed_at = (data.get("reviewed_at") or "").strip()
    out["reviewed_at"] = reviewed_at or None
    return out


# ── CRUD ───────────────────────────────────────────────────────────

def create_statement(data: dict[str, Any]) -> PersonalStatement:
    init_db()
    try:
        p = _validate_payload(data)
    except ValidationError as e:
        logger.warning("create_statement validation failed: %s", e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO personal_statements
                   (student_id, title, body, word_count, char_count,
                    line_count, status, feedback, reviewer, reviewed_at,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["title"], p["body"],
             p["word_count"], p["char_count"], p["line_count"],
             p["status"], p["feedback"], p["reviewer"], p["reviewed_at"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_statement(new_id)
    assert out is not None
    logger.info(
        "Created personal statement #%d for %s "
        "(chars=%d, words=%d, lines=%d, status=%s)",
        new_id, p["student_id"], p["char_count"], p["word_count"],
        p["line_count"], p["status"],
    )
    return out


def get_statement(statement_id: int) -> PersonalStatement | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM personal_statements WHERE statement_id = ?",
            (statement_id,),
        ).fetchone()
        return _row(r) if r else None


def list_statements(
    *,
    student_id: str | None = None,
    status: str | None = None,
) -> list[PersonalStatement]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        f"SELECT * FROM personal_statements {where} "
        "ORDER BY student_id, updated_at DESC"
    )
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def statements_for_student(student_id: str) -> list[PersonalStatement]:
    return list_statements(student_id=student_id)


def update_statement(statement_id: int, data: dict[str, Any]) -> PersonalStatement:
    init_db()
    existing = get_statement(statement_id)
    if existing is None:
        logger.warning("update_statement: unknown id %d", statement_id)
        raise ValidationError(f"No statement with id {statement_id}")
    p = _validate_payload({
        "student_id":  existing.student_id,
        "title":       data.get("title", existing.title),
        "body":        data.get("body", existing.body),
        "status":      data.get("status", existing.status),
        "feedback":    data.get("feedback", existing.feedback),
        "reviewer":    data.get("reviewer", existing.reviewer),
        "reviewed_at": data.get("reviewed_at", existing.reviewed_at),
    })
    with _connect() as conn:
        conn.execute(
            """UPDATE personal_statements SET
                   title = ?, body = ?, word_count = ?, char_count = ?,
                   line_count = ?, status = ?, feedback = ?,
                   reviewer = ?, reviewed_at = ?,
                   updated_at = datetime('now')
               WHERE statement_id = ?""",
            (p["title"], p["body"], p["word_count"], p["char_count"],
             p["line_count"], p["status"], p["feedback"],
             p["reviewer"], p["reviewed_at"], statement_id),
        )
        conn.commit()
    logger.info(
        "Updated personal statement #%d (status=%s, chars=%d)",
        statement_id, p["status"], p["char_count"],
    )
    out = get_statement(statement_id)
    assert out is not None
    return out


def set_status(statement_id: int, status: str,
               *, reviewer: str | None = None) -> PersonalStatement:
    """Convenience: update only the status (and reviewer / reviewed_at
    when moving to In Review / Approved)."""
    init_db()
    existing = get_statement(statement_id)
    if existing is None:
        raise ValidationError(f"No statement with id {statement_id}")
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    payload: dict[str, Any] = {"status": status}
    if status in ("In Review", "Approved"):
        if reviewer:
            payload["reviewer"] = reviewer
        payload["reviewed_at"] = "now"  # signal — we'll convert next
    out = update_statement(statement_id, payload)
    # If we wanted reviewed_at = now(), do it in a second pass so the
    # validator doesn't trip on the literal "now".
    if payload.get("reviewed_at") == "now":
        with _connect() as conn:
            conn.execute(
                "UPDATE personal_statements SET reviewed_at = datetime('now') "
                "WHERE statement_id = ?",
                (statement_id,),
            )
            conn.commit()
        out = get_statement(statement_id)
        assert out is not None
    logger.info("Status of personal statement #%d → %s", statement_id, status)
    return out


def delete_statement(statement_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM personal_statements WHERE statement_id = ?",
            (statement_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted personal statement #%d", statement_id)
            return True
        logger.warning("delete_statement: unknown id %d", statement_id)
        return False


# ── Push to UCAS application ──────────────────────────────────────

def push_to_ucas(
    statement_id: int, *, cycle_year: int | None = None,
) -> int:
    """Copy this draft's body into the student's UCAS application for
    the given cycle year (defaults to the student's most recent app).
    Returns the application_id that was written. Raises if no app exists.

    Also marks the draft as ``Submitted`` if it's currently Approved or
    earlier.
    """
    init_db()
    existing = get_statement(statement_id)
    if existing is None:
        raise ValidationError(f"No statement with id {statement_id}")
    from education_system.systems.sixth_form.domain.progression.ucas import (
        ucas as _ucas,
    )
    app = _ucas.get_application_for_student(
        existing.student_id, cycle_year=cycle_year)
    if app is None:
        raise ValidationError(
            f"{existing.student_id} has no UCAS application"
            + (f" for cycle {cycle_year}" if cycle_year else "")
        )
    _ucas.update_application(
        app.application_id, {"personal_statement": existing.body})
    if existing.status != "Submitted":
        set_status(statement_id, "Submitted")
    logger.info(
        "Pushed personal statement #%d (chars=%d) to UCAS application #%d",
        statement_id, existing.char_count, app.application_id,
    )
    return app.application_id


# ── Summary ───────────────────────────────────────────────────────

@dataclass
class StudentSummary:
    student_id: str
    drafts: int
    latest_status: str | None
    latest_chars: int
    latest_lines: int
    has_submitted: bool


def per_student_summary() -> list[StudentSummary]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT student_id, COUNT(*) AS n,
                      MAX(updated_at) AS latest_at
               FROM personal_statements
               GROUP BY student_id
               ORDER BY student_id"""
        ).fetchall()

    out: list[StudentSummary] = []
    with _connect() as conn:
        for r in rows:
            sid = r["student_id"]
            latest = conn.execute(
                """SELECT * FROM personal_statements
                   WHERE student_id = ? ORDER BY updated_at DESC LIMIT 1""",
                (sid,),
            ).fetchone()
            submitted = conn.execute(
                """SELECT 1 FROM personal_statements
                   WHERE student_id = ? AND status = 'Submitted' LIMIT 1""",
                (sid,),
            ).fetchone() is not None
            out.append(StudentSummary(
                student_id=sid, drafts=r["n"],
                latest_status=latest["status"] if latest else None,
                latest_chars=latest["char_count"] if latest else 0,
                latest_lines=latest["line_count"] if latest else 0,
                has_submitted=submitted,
            ))
    return out
