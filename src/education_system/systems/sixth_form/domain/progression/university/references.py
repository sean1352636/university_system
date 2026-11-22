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

**Structured references (2026 entry onward).** UCAS replaced the single
free-text reference with three sections — a general statement about the
school or college, any extenuating circumstances affecting the
applicant, and supportive information about the applicant — plus the
predicted grades. A structured reference (``structure =
'three_section'``) keeps each section in its own column and goes through
a sign-off workflow rather than a single status:

    Draft → Subject contributions → Tutor review → HoSF approval
          → Approved → Sent

Subject teachers write contributions (``reference_contributions``), the
tutor compiles them into the supportive section and signs, the head of
sixth form approves (and must not be the tutor who signed), and sending
marks the reference ``Submitted`` exactly as the old flow did — so the
UCAS workflow stage, the demotion of older references and every report
keep working. The predicted grades are read from the predicted-grades
domain and frozen onto the reference at approval, so the reference sent
says what was predicted when it was signed. The general statement is the
same for every applicant and is kept per cycle in
``reference_centre_statements``; a new structured reference starts with it.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_REFERENCES_DB

STATUSES: tuple[str, ...] = ("Requested", "Drafting", "Submitted")
DEFAULT_STATUS: str = "Requested"

SOFT_CHAR_LIMIT: int = 4000  # UCAS reference soft cap

STRUCTURE_SINGLE = "single"
STRUCTURE_THREE = "three_section"

#: (column, heading) for the three UCAS sections, in order.
SECTIONS: tuple[tuple[str, str], ...] = (
    ("section_general", "Section 1 — General statement about the school/college"),
    ("section_extenuating", "Section 2 — Extenuating circumstances"),
    ("section_supportive", "Section 3 — Supportive information about the applicant"),
)

SIGNOFF_STAGES: tuple[str, ...] = (
    "Draft", "Subject contributions", "Tutor review", "HoSF approval",
    "Approved", "Sent",
)
#: Stages at which the sections are frozen.
_FROZEN_STAGES = ("Approved", "Sent")

CONTRIBUTION_STATUSES: tuple[str, ...] = ("Requested", "Submitted", "Not required")

_STRUCTURED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("structure", f"TEXT NOT NULL DEFAULT '{STRUCTURE_SINGLE}'"),
    ("cycle_year", "INTEGER"),
    ("section_general", "TEXT"),
    ("section_extenuating", "TEXT"),
    ("section_supportive", "TEXT"),
    ("signoff_stage", "TEXT"),
    ("tutor_signed_by", "TEXT"),
    ("tutor_signed_at", "TEXT"),
    ("approved_by", "TEXT"),
    ("approved_at", "TEXT"),
    ("sent_by", "TEXT"),
    ("sent_at", "TEXT"),
    ("predicted_grades_json", "TEXT"),
    ("returned_reason", "TEXT"),
)

_STRUCTURED_SCHEMA = """
CREATE TABLE IF NOT EXISTS reference_contributions (
    contribution_id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_id    INTEGER NOT NULL,
    subject         TEXT NOT NULL,
    teacher         TEXT,
    body            TEXT,
    status          TEXT NOT NULL DEFAULT 'Requested',
    requested_at    TEXT DEFAULT (datetime('now')),
    submitted_at    TEXT,
    FOREIGN KEY (reference_id)
        REFERENCES academic_references(reference_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_refcontrib_ref ON reference_contributions(reference_id);

CREATE TABLE IF NOT EXISTS reference_centre_statements (
    cycle_year  INTEGER PRIMARY KEY,
    body        TEXT NOT NULL,
    updated_by  TEXT,
    updated_at  TEXT DEFAULT (datetime('now'))
);
"""

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
    paths.ensure_sixth_form_directories()
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
        cols = {r["name"] for r in conn.execute(
            "PRAGMA table_info(academic_references)")}
        for col, ddl in _STRUCTURED_COLUMNS:
            if col not in cols:
                conn.execute(
                    f"ALTER TABLE academic_references ADD COLUMN {col} {ddl}")
        conn.executescript(_STRUCTURED_SCHEMA)
        conn.commit()
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
    from education_system.systems.sixth_form.domain.learners.students import (
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
    _guard_structured_edit(reference_id, existing, data)
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


def _guard_structured_edit(reference_id: int, existing: Reference,
                           data: dict[str, Any]) -> None:
    """A structured reference's body is composed from its sections and
    its Submitted status comes from the sign-off workflow, so the
    single-text editors may change its referee, title and notes but not
    those two."""
    with _connect() as conn:
        r = conn.execute(
            "SELECT structure, signoff_stage FROM academic_references "
            "WHERE reference_id = ?", (reference_id,)).fetchone()
    if not r or r["structure"] != STRUCTURE_THREE:
        return
    if "body" in data and (data["body"] or None) != (existing.body or None):
        raise ValidationError(
            "This is a three-section reference — edit its sections in the "
            "Structured references screen.")
    if (data.get("status") == "Submitted" and existing.status != "Submitted"
            and r["signoff_stage"] != "Sent"):
        raise ValidationError(
            "A three-section reference is submitted by sending it after head "
            "of sixth form approval.")


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


# ── Structured references (three sections + sign-off) ────────────

def _actor(name: str | None) -> str:
    """Who is doing this: the name given, else the signed-in user."""
    if name and name.strip():
        return name.strip()
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access as _access,
        )
        p = _access.current()
        who = (getattr(p, "staff_name", None) or getattr(p, "username", None) or "").strip()
        if who and who.lower() != "anonymous":
            return who
    except Exception:
        logger.debug("No signed-in principal for reference sign-off", exc_info=True)
    raise ValidationError("Say who is signing (no signed-in user is known).")


def get_centre_statement(cycle_year: int) -> str | None:
    """The cycle's general statement about the college (section 1)."""
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT body FROM reference_centre_statements WHERE cycle_year=?",
                         (cycle_year,)).fetchone()
    return r["body"] if r else None


def set_centre_statement(cycle_year: int, body: str, *,
                         updated_by: str | None = None) -> None:
    init_db()
    body = (body or "").strip()
    if not body:
        raise ValidationError("The general statement cannot be empty")
    if len(body) > SOFT_CHAR_LIMIT:
        raise ValidationError(f"The general statement is over {SOFT_CHAR_LIMIT} characters")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO reference_centre_statements (cycle_year, body, updated_by, updated_at)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(cycle_year) DO UPDATE SET body=excluded.body,
                   updated_by=excluded.updated_by, updated_at=datetime('now')""",
            (int(cycle_year), body, updated_by))
        conn.commit()
    logger.info("Reference centre statement saved for cycle %s", cycle_year)


def predicted_grades_section(student_id: str) -> list[dict[str, Any]]:
    """Current predictions for the student, from the predicted-grades
    domain (read-only), one dict per subject."""
    from education_system.systems.sixth_form.domain.assessment.predicted_grades import (
        predicted_grades as _predicted,
    )
    return [{"subject": p.subject, "grade": p.grade, "confidence": p.confidence,
             "predicted_by": p.predicted_by, "predicted_at": p.predicted_at}
            for p in sorted(_predicted.predictions_for_student(student_id),
                            key=lambda p: p.subject)]


def _format_grades(grades: list[dict[str, Any]]) -> str:
    if not grades:
        return "(no predicted grades recorded)"
    return "\n".join(f"{g['subject']}: {g['grade']}" for g in grades)


def section_counts(sections: dict[str, str | None]) -> tuple[int, int, int]:
    """``(words, chars, lines)`` across the three sections — what the UCAS
    4,000-character limit is measured against (headings excluded)."""
    words = chars = lines = 0
    for col, _h in SECTIONS:
        w, c, l = compute_counts(sections.get(col) or "")
        words, chars, lines = words + w, chars + c, lines + l
    return words, chars, lines


def compose_structured_body(sections: dict[str, str | None],
                            grades: list[dict[str, Any]] | None = None) -> str:
    """The sections (and grades, when known) as one text — what ``body``
    holds so the older screens and the UCAS stage see the reference."""
    parts = [f"{heading}\n{(sections.get(col) or '').strip() or '(none)'}"
             for col, heading in SECTIONS]
    if grades is not None:
        parts.append(f"Predicted grades\n{_format_grades(grades)}")
    return "\n\n".join(parts)


def get_structured(reference_id: int) -> dict[str, Any] | None:
    """A structured reference with its contributions and grades."""
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM academic_references WHERE reference_id=?",
                         (reference_id,)).fetchone()
        if r is None:
            return None
        contribs = [dict(c) for c in conn.execute(
            "SELECT * FROM reference_contributions WHERE reference_id=? "
            "ORDER BY subject", (reference_id,))]
    out = dict(r)
    out["contributions"] = contribs
    import json as _json
    if out.get("predicted_grades_json"):
        out["predicted_grades"] = _json.loads(out["predicted_grades_json"])
        out["predicted_grades_frozen"] = True
    else:
        try:
            out["predicted_grades"] = predicted_grades_section(out["student_id"])
        except Exception:
            logger.debug("Predicted grades unavailable", exc_info=True)
            out["predicted_grades"] = []
        out["predicted_grades_frozen"] = False
    out["counts"] = section_counts(out)
    return out


def _require_structured(reference_id: int) -> dict[str, Any]:
    ref = get_structured(reference_id)
    if ref is None:
        raise ValidationError(f"No reference with id {reference_id}")
    if ref.get("structure") != STRUCTURE_THREE:
        raise ValidationError(
            f"Reference #{reference_id} is a single-text reference — edit it "
            "in the References directory.")
    return ref


def _write_structured(reference_id: int, fields: dict[str, Any]) -> None:
    """Write structured columns, then refresh the composed body/counts
    and the legacy status from them."""
    with _connect() as conn:
        if fields:
            sets = ", ".join(f"{k}=?" for k in fields)
            conn.execute(f"UPDATE academic_references SET {sets}, "
                         "updated_at=datetime('now') WHERE reference_id=?",
                         (*fields.values(), reference_id))
        r = dict(conn.execute("SELECT * FROM academic_references WHERE reference_id=?",
                              (reference_id,)).fetchone())
        import json as _json
        grades = (_json.loads(r["predicted_grades_json"])
                  if r.get("predicted_grades_json") else None)
        body = compose_structured_body(r, grades)
        words, chars, lines = section_counts(r)
        stage = r.get("signoff_stage") or "Draft"
        has_text = any((r.get(c) or "").strip() for c, _h in SECTIONS)
        status = ("Submitted" if stage == "Sent"
                  else ("Drafting" if has_text or stage != "Draft" else "Requested"))
        conn.execute(
            "UPDATE academic_references SET body=?, word_count=?, char_count=?, "
            "line_count=?, status=? WHERE reference_id=?",
            (body, words, chars, lines, status, reference_id))
        conn.commit()


def start_structured(student_id: str, referee: str, *, referee_role: str | None = None,
                     cycle_year: int | None = None, title: str | None = None) -> dict[str, Any]:
    """Create a three-section reference at Draft, section 1 prefilled."""
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    if _students.get_student((student_id or "").strip()) is None:
        raise ValidationError(f"No student with id {student_id}")
    if not (referee or "").strip():
        raise ValidationError("Referee is required")
    if cycle_year is None:
        from education_system.systems.sixth_form.domain.progression.university import (
            workflow as _wf,
        )
        cycle_year = _wf.default_cycle_year()
    general = get_centre_statement(int(cycle_year))
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO academic_references
                   (student_id, referee, referee_role, title, status, requested_at,
                    structure, cycle_year, section_general, signoff_stage,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, 'Requested', ?, ?, ?, ?, 'Draft',
                       datetime('now'), datetime('now'))""",
            (student_id.strip(), referee.strip(), (referee_role or "").strip() or None,
             (title or "").strip() or f"UCAS reference {cycle_year}", _now_iso(),
             STRUCTURE_THREE, int(cycle_year), general))
        conn.commit()
        new_id = cur.lastrowid
    _write_structured(new_id, {})
    logger.info("Started structured reference #%d for %s (cycle %s)",
                new_id, student_id, cycle_year)
    out = get_structured(new_id)
    assert out is not None
    return out


def save_sections(reference_id: int, *, general: str | None = None,
                  extenuating: str | None = None,
                  supportive: str | None = None) -> dict[str, Any]:
    """Edit any of the three sections. ``None`` leaves a section alone."""
    ref = _require_structured(reference_id)
    if ref.get("signoff_stage") in _FROZEN_STAGES:
        raise ValidationError(
            f"The reference is {ref['signoff_stage']} — return it to draft to edit it.")
    fields: dict[str, Any] = {}
    for col, value in (("section_general", general),
                       ("section_extenuating", extenuating),
                       ("section_supportive", supportive)):
        if value is not None:
            fields[col] = value.strip() or None
    merged = {**ref, **fields}
    _w, chars, _l = section_counts(merged)
    if chars > SOFT_CHAR_LIMIT:
        raise ValidationError(
            f"The three sections total {chars} characters — the UCAS limit is "
            f"{SOFT_CHAR_LIMIT}.")
    if ref.get("signoff_stage") == "HoSF approval":
        # Changed after the tutor signed: the signature no longer covers it.
        fields.update(signoff_stage="Tutor review", tutor_signed_by=None,
                      tutor_signed_at=None)
    _write_structured(reference_id, fields)
    out = get_structured(reference_id)
    assert out is not None
    return out


def request_contributions(reference_id: int,
                          items: list[tuple[str, str | None]] | None = None) -> list[dict[str, Any]]:
    """Ask subject teachers for input. Defaults to the student's subjects."""
    ref = _require_structured(reference_id)
    if ref.get("signoff_stage") not in ("Draft", "Subject contributions"):
        raise ValidationError("Contributions can only be requested before tutor review.")
    if items is None:
        from education_system.systems.sixth_form.domain.learners.students import students as _students
        st = _students.get_student(ref["student_id"])
        items = [(subj, None) for subj in (st.subjects if st else [])]
    have = {c["subject"].lower() for c in ref["contributions"]}
    new = [(s.strip(), (t or "").strip() or None) for s, t in items
           if s and s.strip() and s.strip().lower() not in have]
    if not new and not ref["contributions"]:
        raise ValidationError("No subjects to ask — give at least one subject.")
    with _connect() as conn:
        conn.executemany(
            "INSERT INTO reference_contributions (reference_id, subject, teacher) "
            "VALUES (?, ?, ?)", [(reference_id, s, t) for s, t in new])
        conn.commit()
    _write_structured(reference_id, {"signoff_stage": "Subject contributions"})
    out = get_structured(reference_id)
    assert out is not None
    return out["contributions"]


def submit_contribution(contribution_id: int, body: str, *,
                        teacher: str | None = None) -> dict[str, Any]:
    init_db()
    if not (body or "").strip():
        raise ValidationError("The contribution is empty")
    with _connect() as conn:
        c = conn.execute("SELECT * FROM reference_contributions WHERE contribution_id=?",
                         (contribution_id,)).fetchone()
        if c is None:
            raise ValidationError(f"No contribution with id {contribution_id}")
        ref = conn.execute("SELECT signoff_stage FROM academic_references WHERE reference_id=?",
                           (c["reference_id"],)).fetchone()
        if ref and ref["signoff_stage"] in _FROZEN_STAGES:
            raise ValidationError("The reference has been approved — too late to contribute.")
        conn.execute(
            "UPDATE reference_contributions SET body=?, teacher=COALESCE(?, teacher), "
            "status='Submitted', submitted_at=datetime('now') WHERE contribution_id=?",
            (body.strip(), (teacher or "").strip() or None, contribution_id))
        conn.commit()
        return dict(conn.execute("SELECT * FROM reference_contributions WHERE contribution_id=?",
                                 (contribution_id,)).fetchone())


def set_contribution_not_required(contribution_id: int) -> None:
    init_db()
    with _connect() as conn:
        cur = conn.execute("UPDATE reference_contributions SET status='Not required' "
                           "WHERE contribution_id=? AND status='Requested'", (contribution_id,))
        conn.commit()
    if not cur.rowcount:
        raise ValidationError("Only an outstanding contribution can be marked not required.")


def move_to_tutor_review(reference_id: int) -> dict[str, Any]:
    """All contributions are in: hand the reference to the tutor."""
    ref = _require_structured(reference_id)
    if ref.get("signoff_stage") not in ("Draft", "Subject contributions"):
        raise ValidationError(f"The reference is already at {ref['signoff_stage']}.")
    waiting = [c["subject"] for c in ref["contributions"] if c["status"] == "Requested"]
    if waiting:
        raise ValidationError("Still waiting for: " + ", ".join(waiting)
                              + " (or mark them not required).")
    _write_structured(reference_id, {"signoff_stage": "Tutor review"})
    out = get_structured(reference_id)
    assert out is not None
    return out


def tutor_sign_off(reference_id: int, tutor: str | None = None) -> dict[str, Any]:
    ref = _require_structured(reference_id)
    if ref.get("signoff_stage") == "Subject contributions":
        ref = move_to_tutor_review(reference_id)
    if ref.get("signoff_stage") not in ("Draft", "Tutor review"):
        raise ValidationError(f"The reference is at {ref['signoff_stage']}, not tutor review.")
    if not (ref.get("section_supportive") or "").strip():
        raise ValidationError("Section 3 (supportive information) must be written first.")
    who = _actor(tutor)
    _write_structured(reference_id, {"signoff_stage": "HoSF approval",
                                     "tutor_signed_by": who,
                                     "tutor_signed_at": _now_iso(),
                                     "returned_reason": None})
    logger.info("Reference #%d signed by tutor %s", reference_id, who)
    out = get_structured(reference_id)
    assert out is not None
    return out


def approve(reference_id: int, approver: str | None = None) -> dict[str, Any]:
    """Head of sixth form approval. Freezes the predicted grades."""
    ref = _require_structured(reference_id)
    if ref.get("signoff_stage") != "HoSF approval":
        raise ValidationError("Only a reference the tutor has signed can be approved.")
    who = _actor(approver)
    if who.lower() == (ref.get("tutor_signed_by") or "").lower():
        raise ValidationError("The approver must be someone other than the tutor who signed.")
    import json as _json
    grades = predicted_grades_section(ref["student_id"])
    _write_structured(reference_id, {"signoff_stage": "Approved", "approved_by": who,
                                     "approved_at": _now_iso(),
                                     "predicted_grades_json": _json.dumps(grades)})
    logger.info("Reference #%d approved by %s", reference_id, who)
    out = get_structured(reference_id)
    assert out is not None
    return out


def send(reference_id: int, sender: str | None = None) -> dict[str, Any]:
    """Mark the approved reference as sent to UCAS (status Submitted)."""
    ref = _require_structured(reference_id)
    if ref.get("signoff_stage") != "Approved":
        raise ValidationError("Only an approved reference can be sent.")
    who = _actor(sender)
    now = _now_iso()
    _write_structured(reference_id, {"signoff_stage": "Sent", "sent_by": who,
                                     "sent_at": now, "submitted_at": now})
    sent = get_reference(reference_id)
    assert sent is not None
    _demote_other_submitted(sent)
    logger.info("Reference #%d sent by %s", reference_id, who)
    out = get_structured(reference_id)
    assert out is not None
    return out


def return_to_draft(reference_id: int, reason: str) -> dict[str, Any]:
    """Send it back. Clears the signatures and unfreezes the grades."""
    ref = _require_structured(reference_id)
    if ref.get("signoff_stage") == "Sent":
        raise ValidationError("A sent reference cannot be returned — start a new one.")
    if not (reason or "").strip():
        raise ValidationError("Give a reason for returning it")
    _write_structured(reference_id, {"signoff_stage": "Draft", "tutor_signed_by": None,
                                     "tutor_signed_at": None, "approved_by": None,
                                     "approved_at": None, "predicted_grades_json": None,
                                     "returned_reason": reason.strip()})
    out = get_structured(reference_id)
    assert out is not None
    return out


def list_structured(*, stage: str | None = None,
                    cycle_year: int | None = None) -> list[dict[str, Any]]:
    """Structured references with student names and contribution counts."""
    init_db()
    clauses, args = ["r.structure = ?"], [STRUCTURE_THREE]
    if stage:
        clauses.append("COALESCE(r.signoff_stage, 'Draft') = ?"); args.append(stage)
    if cycle_year is not None:
        clauses.append("r.cycle_year = ?"); args.append(cycle_year)
    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT r.reference_id, r.student_id, r.referee, r.cycle_year,
                       COALESCE(r.signoff_stage, 'Draft') AS signoff_stage,
                       r.tutor_signed_by, r.approved_by, r.sent_at, r.char_count,
                       s.first_name || ' ' || s.last_name AS student_name,
                       (SELECT COUNT(*) FROM reference_contributions c
                         WHERE c.reference_id = r.reference_id) AS n_contrib,
                       (SELECT COUNT(*) FROM reference_contributions c
                         WHERE c.reference_id = r.reference_id
                           AND c.status = 'Requested') AS n_waiting
                  FROM academic_references r
                  LEFT JOIN students s ON s.student_id = r.student_id
                 WHERE {' AND '.join(clauses)}
                 ORDER BY r.updated_at DESC""", args).fetchall()
    return [dict(r) for r in rows]


def outstanding_contributions(teacher: str | None = None) -> list[dict[str, Any]]:
    init_db()
    args: list[Any] = []
    extra = ""
    if teacher:
        extra = " AND c.teacher LIKE ?"
        args.append(f"%{teacher.strip()}%")
    with _connect() as conn:
        return [dict(r) for r in conn.execute(
            f"""SELECT c.*, r.student_id,
                       s.first_name || ' ' || s.last_name AS student_name
                  FROM reference_contributions c
                  JOIN academic_references r ON r.reference_id = c.reference_id
                  LEFT JOIN students s ON s.student_id = r.student_id
                 WHERE c.status = 'Requested'{extra}
                 ORDER BY c.requested_at""", args)]
