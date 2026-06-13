"""UCAS academic references for the Sixth Form System.

A *reference* is the teacher-written endorsement that goes with a
UCAS application. Workflow: ``Requested`` → ``Drafting`` → ``Submitted``.
The body is optional while the reference is Requested (the teacher
hasn't started writing yet) and required at the point of submission.

Multiple references per student are allowed so staff can keep iterative
drafts, but only one can be marked ``Submitted`` at a time per student
— the ``set_status`` helper auto-demotes any previously-submitted
reference to ``Drafting`` if a new one is promoted.

Cascade: deleting a student wipes their references.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.sixthform_system.core import paths
from education_system.sixthform_system.modules.domain.progression.references import references as data

logger = logging.getLogger(__name__)

DB_PATH = paths.REFERENCES_DB

STATUSES: tuple[str, ...] = ("Requested", "Drafting", "Submitted")
DEFAULT_STATUS: str = "Requested"

SOFT_CHAR_LIMIT: int = 4000  # UCAS reference soft cap

_SCHEMA = """
CREATE TABLE IF NOT EXISTS academic_references (
    reference_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    referee      TEXT NOT NULL,
    referee_role TEXT,
    title        TEXT,
    body         TEXT,
    word_count   INTEGER NOT NULL DEFAULT 0,
    char_count   INTEGER NOT NULL DEFAULT 0,
    line_count   INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'Requested',
    requested_at TEXT,
    submitted_at TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ref_student ON academic_references(student_id);
CREATE INDEX IF NOT EXISTS idx_ref_status  ON academic_references(status);
CREATE INDEX IF NOT EXISTS idx_ref_referee ON academic_references(referee);
"""


@dataclass
class Reference:
    reference_id: int
    student_id: str
    referee: str
    referee_role: str | None
    title: str | None
    body: str | None
    word_count: int
    char_count: int
    line_count: int
    status: str
    requested_at: str | None
    submitted_at: str | None
    notes: str | None
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
    from education_system.sixthform_system.modules.domain.students.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("References schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> Reference:
    return Reference(
        reference_id=r["reference_id"], student_id=r["student_id"],
        referee=r["referee"], referee_role=r["referee_role"],
        title=r["title"], body=r["body"],
        word_count=r["word_count"], char_count=r["char_count"],
        line_count=r["line_count"],
        status=r["status"], requested_at=r["requested_at"],
        submitted_at=r["submitted_at"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Counting helpers ──────────────────────────────────────────────

def compute_counts(body: str | None) -> tuple[int, int, int]:
    if not body:
        return 0, 0, 0
    chars = len(body)
    words = len(body.split())
    lines = body.count("\n") + (0 if body.endswith("\n") else 1)
    return words, chars, lines


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid reference input."""


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    sid = (data.get("student_id") or "").strip()
    if not sid:
        raise ValidationError("Student ID is required")
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    referee = (data.get("referee") or "").strip()
    if not referee:
        raise ValidationError("Referee is required")
    out["referee"] = referee

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    body = data.get("body")
    if body is not None and not isinstance(body, str):
        body = str(body)
    if status == "Submitted" and not (body and body.strip()):
        raise ValidationError(
            "Body is required before a reference can be marked Submitted")
    words, chars, lines = compute_counts(body)
    if chars > SOFT_CHAR_LIMIT:
        raise ValidationError(
            f"Body length {chars} exceeds soft limit of {SOFT_CHAR_LIMIT} "
            "characters"
        )
    out["body"] = body or None
    out["word_count"] = words
    out["char_count"] = chars
    out["line_count"] = lines

    out["referee_role"] = (data.get("referee_role") or "").strip() or None
    out["title"]        = (data.get("title") or "").strip() or None
    out["notes"]        = (data.get("notes") or "").strip() or None

    out["requested_at"] = (data.get("requested_at") or "").strip() or None
    out["submitted_at"] = (data.get("submitted_at") or "").strip() or None
    return out


# ── CRUD ───────────────────────────────────────────────────────────

def create_reference(data: dict[str, Any]) -> Reference:
    init_db()
    try:
        p = _validate_payload(data)
    except ValidationError as e:
        logger.warning("create_reference validation failed: %s", e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO academic_references
                   (student_id, referee, referee_role, title, body,
                    word_count, char_count, line_count, status,
                    requested_at, submitted_at, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["referee"], p["referee_role"],
             p["title"], p["body"], p["word_count"], p["char_count"],
             p["line_count"], p["status"],
             p["requested_at"] or _now_iso() if p["status"] == "Requested"
                else p["requested_at"],
             p["submitted_at"] or _now_iso() if p["status"] == "Submitted"
                else p["submitted_at"],
             p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_reference(new_id)
    assert out is not None
    logger.info(
        "Created reference #%d for %s (referee=%s, status=%s, chars=%d)",
        new_id, p["student_id"], p["referee"], p["status"], p["char_count"],
    )
    if p["status"] == "Submitted":
        _demote_other_submitted(out)
    return out


def _now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_reference(reference_id: int) -> Reference | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM academic_references WHERE reference_id = ?",
            (reference_id,),
        ).fetchone()
        return _row(r) if r else None


def list_references(
    *,
    student_id: str | None = None,
    referee: str | None = None,
    status: str | None = None,
) -> list[Reference]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if referee:
        q = f"%{referee.strip()}%"
        clauses.append("referee LIKE ?")
        args.append(q)
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        f"SELECT * FROM academic_references {where} "
        "ORDER BY student_id, updated_at DESC"
    )
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def references_for_student(student_id: str) -> list[Reference]:
    return list_references(student_id=student_id)


def update_reference(reference_id: int, data: dict[str, Any]) -> Reference:
    init_db()
    existing = get_reference(reference_id)
    if existing is None:
        logger.warning("update_reference: unknown id %d", reference_id)
        raise ValidationError(f"No reference with id {reference_id}")
    p = _validate_payload({
        "student_id":   existing.student_id,
        "referee":      data.get("referee", existing.referee),
        "referee_role": data.get("referee_role", existing.referee_role),
        "title":        data.get("title", existing.title),
        "body":         data.get("body", existing.body),
        "status":       data.get("status", existing.status),
        "requested_at": data.get("requested_at", existing.requested_at),
        "submitted_at": data.get("submitted_at", existing.submitted_at),
        "notes":        data.get("notes", existing.notes),
    })
    # Auto-stamp submitted_at when transitioning into Submitted.
    if existing.status != "Submitted" and p["status"] == "Submitted" \
            and not p["submitted_at"]:
        p["submitted_at"] = _now_iso()
    with _connect() as conn:
        conn.execute(
            """UPDATE academic_references SET
                   referee = ?, referee_role = ?, title = ?, body = ?,
                   word_count = ?, char_count = ?, line_count = ?,
                   status = ?, requested_at = ?, submitted_at = ?,
                   notes = ?, updated_at = datetime('now')
               WHERE reference_id = ?""",
            (p["referee"], p["referee_role"], p["title"], p["body"],
             p["word_count"], p["char_count"], p["line_count"],
             p["status"], p["requested_at"], p["submitted_at"],
             p["notes"], reference_id),
        )
        conn.commit()
    out = get_reference(reference_id)
    assert out is not None
    logger.info(
        "Updated reference #%d (status=%s, chars=%d)",
        reference_id, out.status, out.char_count,
    )
    if out.status == "Submitted" and existing.status != "Submitted":
        _demote_other_submitted(out)
    return out


def set_status(reference_id: int, status: str) -> Reference:
    """Shortcut: change just the status. Submitted triggers auto-demote
    of any *other* previously-submitted reference for the same student."""
    init_db()
    existing = get_reference(reference_id)
    if existing is None:
        raise ValidationError(f"No reference with id {reference_id}")
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_reference(reference_id, {"status": status})


def _demote_other_submitted(submitted: Reference) -> None:
    """When a reference is marked Submitted, any *other* Submitted
    reference for the same student goes back to Drafting so the
    student always has at most one Submitted reference."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT reference_id FROM academic_references
               WHERE student_id = ? AND status = 'Submitted'
                 AND reference_id != ?""",
            (submitted.student_id, submitted.reference_id),
        ).fetchall()
    for r in rows:
        with _connect() as conn:
            conn.execute(
                """UPDATE academic_references
                   SET status = 'Drafting',
                       updated_at = datetime('now')
                   WHERE reference_id = ?""",
                (r["reference_id"],),
            )
            conn.commit()
        logger.info(
            "Auto-demoted reference #%d from Submitted to Drafting "
            "(new Submitted is #%d)",
            r["reference_id"], submitted.reference_id,
        )


def delete_reference(reference_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM academic_references WHERE reference_id = ?",
            (reference_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted reference #%d", reference_id)
            return True
        logger.warning("delete_reference: unknown id %d", reference_id)
        return False


# ── Summary ───────────────────────────────────────────────────────

@dataclass
class StudentRefSummary:
    student_id: str
    drafts: int
    latest_status: str | None
    has_submitted: bool
    last_referee: str | None


def per_student_summary() -> list[StudentRefSummary]:
    init_db()
    with _connect() as conn:
        sids = [r["student_id"] for r in conn.execute(
            "SELECT DISTINCT student_id FROM academic_references "
            "ORDER BY student_id"
        ).fetchall()]
    out: list[StudentRefSummary] = []
    with _connect() as conn:
        for sid in sids:
            n = conn.execute(
                "SELECT COUNT(*) AS n FROM academic_references "
                "WHERE student_id = ?", (sid,)
            ).fetchone()["n"]
            latest = conn.execute(
                "SELECT * FROM academic_references "
                "WHERE student_id = ? ORDER BY updated_at DESC LIMIT 1",
                (sid,),
            ).fetchone()
            sub = conn.execute(
                "SELECT 1 FROM academic_references "
                "WHERE student_id = ? AND status = 'Submitted' LIMIT 1",
                (sid,),
            ).fetchone() is not None
            out.append(StudentRefSummary(
                student_id=sid, drafts=n,
                latest_status=latest["status"] if latest else None,
                has_submitted=sub,
                last_referee=latest["referee"] if latest else None,
            ))
    return out
