"""Personal-statement drafts for the Sixth Form System.

UCAS allows one personal statement of up to **4000 characters** or **47
lines** (whichever comes first). Staff and students iterate through
multiple drafts before submission, so this module stores a *history*
of drafts per student — distinct from the single ``personal_statement``
column on ``ucas_applications`` which holds the *final* version that
goes with the application.

The ``push_to_ucas`` action copies a chosen draft (typically the
Approved one) onto the student's current-cycle UCAS application.

**Two formats.** From 2026 entry UCAS replaced the free-form statement
with three questions, answered separately (``format = 'three_question'``):

1. Why do you want to study this course or subject?
2. How have your qualifications and studies helped you to prepare for
   this course or subject?
3. What else have you done to prepare outside of education, and why are
   these experiences useful?

Each answer needs at least :data:`MIN_ANSWER_CHARS` (350) characters; the
4,000-character and 47-line limits apply to the three together. The
answers live in ``answer_1..3``; ``body`` holds them composed under their
questions, so everything that reads ``body`` (the UCAS push, the
"statement only on the application" check, exports) keeps working.
Older records keep ``format = 'single'`` and the old rules.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_PERSONAL_STATEMENTS_DB

STATUSES: tuple[str, ...] = ("Draft", "In Review", "Approved", "Submitted")
DEFAULT_STATUS: str = "Draft"

# UCAS hard limits.
MAX_CHARS: int = 4000
MAX_LINES: int = 47

FORMAT_SINGLE = "single"
FORMAT_THREE = "three_question"
FORMATS: tuple[str, ...] = (FORMAT_THREE, FORMAT_SINGLE)
FORMAT_LABELS: dict[str, str] = {
    FORMAT_THREE: "Three questions (2026 entry onward)",
    FORMAT_SINGLE: "Single statement (before 2026 entry)",
}
#: First UCAS entry year using the three-question format.
FIRST_THREE_QUESTION_CYCLE = 2026
#: UCAS minimum per answer in the three-question format.
MIN_ANSWER_CHARS: int = 350
QUESTIONS: tuple[str, str, str] = (
    "Why do you want to study this course or subject?",
    "How have your qualifications and studies helped you to prepare for "
    "this course or subject?",
    "What else have you done to prepare outside of education, and why are "
    "these experiences useful?",
)
#: Statuses at which a three-question statement must meet the minimums —
#: a draft can be short while it is being written, not once it is signed off.
_COMPLETE_STATUSES = ("Approved", "Submitted")

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
    format: str = FORMAT_SINGLE
    answer_1: str | None = None
    answer_2: str | None = None
    answer_3: str | None = None

    @property
    def answers(self) -> tuple[str, str, str]:
        return (self.answer_1 or "", self.answer_2 or "", self.answer_3 or "")

    @property
    def is_three_question(self) -> bool:
        return self.format == FORMAT_THREE


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
        # Three-question format (2026 entry onward). Existing rows take the
        # default and stay single-format statements.
        cols = {r["name"] for r in conn.execute(
            "PRAGMA table_info(personal_statements)")}
        for col, ddl in (("format", f"TEXT NOT NULL DEFAULT '{FORMAT_SINGLE}'"),
                         ("answer_1", "TEXT"), ("answer_2", "TEXT"),
                         ("answer_3", "TEXT")):
            if col not in cols:
                conn.execute(
                    f"ALTER TABLE personal_statements ADD COLUMN {col} {ddl}")
        conn.commit()
    logger.debug("Personal-statements schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> PersonalStatement:
    keys = r.keys()
    return PersonalStatement(
        format=r["format"] if "format" in keys and r["format"] else FORMAT_SINGLE,
        answer_1=r["answer_1"] if "answer_1" in keys else None,
        answer_2=r["answer_2"] if "answer_2" in keys else None,
        answer_3=r["answer_3"] if "answer_3" in keys else None,
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


def compute_three_counts(answers) -> tuple[int, int, int]:
    """``(words, chars, lines)`` across three answers, as UCAS counts them:
    the limits apply to the answers together, not to the composed body."""
    words = chars = lines = 0
    for a in answers:
        w, c, l = compute_counts(a or "")
        words += w
        chars += c
        lines += l
    return words, chars, lines


def compose_body(answers) -> str:
    """The three answers under their questions — what ``body`` stores."""
    return "\n\n".join(f"{i}. {q}\n{(a or '').strip()}"
                        for i, (q, a) in enumerate(zip(QUESTIONS, answers), 1))


def default_format(cycle_year: int | None = None) -> str:
    """The format a new statement for *cycle_year* should use."""
    if cycle_year is None:
        from education_system.systems.sixth_form.domain.progression.university import (
            workflow as _wf,
        )
        cycle_year = _wf.default_cycle_year()
    return FORMAT_THREE if int(cycle_year) >= FIRST_THREE_QUESTION_CYCLE else FORMAT_SINGLE


def check_answers(answers, *, require_minimum: bool = True) -> list[str]:
    """Every UCAS rule a set of three answers breaks, as sentences."""
    issues: list[str] = []
    _w, chars, lines = compute_three_counts(answers)
    if require_minimum:
        for i, a in enumerate(answers, 1):
            n = len(a or "")
            if n < MIN_ANSWER_CHARS:
                issues.append(f"Question {i} has {n} characters — UCAS needs at "
                              f"least {MIN_ANSWER_CHARS}.")
    if chars > MAX_CHARS:
        issues.append(f"The three answers total {chars} characters — the UCAS "
                      f"limit is {MAX_CHARS}.")
    if lines > MAX_LINES:
        issues.append(f"The three answers total {lines} lines — the UCAS limit "
                      f"is {MAX_LINES}.")
    return issues


def check_statement(statement: "PersonalStatement") -> list[str]:
    """The rules this statement breaks *for submission* (format-aware)."""
    if statement.is_three_question:
        return check_answers(statement.answers, require_minimum=True)
    issues = []
    if statement.char_count > MAX_CHARS:
        issues.append(f"{statement.char_count} characters — the limit is {MAX_CHARS}.")
    if statement.line_count > MAX_LINES:
        issues.append(f"{statement.line_count} lines — the limit is {MAX_LINES}.")
    return issues


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

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    answers = tuple((data.get(f"answer_{i}") or "").strip() for i in (1, 2, 3))
    fmt = (data.get("format") or "").strip() or (
        FORMAT_THREE if any(a.strip() for a in answers) else FORMAT_SINGLE)
    if fmt not in FORMATS:
        raise ValidationError(f"Format must be one of: {', '.join(FORMATS)}")
    out["format"] = fmt

    if fmt == FORMAT_THREE:
        if not any(a.strip() for a in answers):
            raise ValidationError("Answer at least one of the three questions")
        issues = check_answers(
            answers, require_minimum=status in _COMPLETE_STATUSES)
        if issues:
            if status in _COMPLETE_STATUSES and any("at least" in i for i in issues):
                issues.append(f"(A statement can only be {status} once every "
                              "answer meets the minimum.)")
            raise ValidationError(" ".join(issues))
        body = compose_body(answers)
        word_count, char_count, line_count = compute_three_counts(answers)
        out["answer_1"], out["answer_2"], out["answer_3"] = (
            a.strip() or None for a in answers)
    else:
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
        out["answer_1"] = out["answer_2"] = out["answer_3"] = None
    out["body"] = body
    out["word_count"] = word_count
    out["char_count"] = char_count
    out["line_count"] = line_count

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
                    format, answer_1, answer_2, answer_3,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["title"], p["body"],
             p["word_count"], p["char_count"], p["line_count"],
             p["status"], p["feedback"], p["reviewer"], p["reviewed_at"],
             p["format"], p["answer_1"], p["answer_2"], p["answer_3"]),
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
    fmt = data.get("format", existing.format) or FORMAT_SINGLE
    if (fmt == FORMAT_THREE and "body" in data
            and not any(f"answer_{i}" in data for i in (1, 2, 3))):
        # The composed body is derived from the answers; replacing it
        # wholesale would leave the answers and the body disagreeing.
        raise ValidationError(
            "This statement uses the three-question format — replace its "
            "answers rather than the body.")
    p = _validate_payload({
        "student_id":  existing.student_id,
        "title":       data.get("title", existing.title),
        "body":        data.get("body", existing.body),
        "status":      data.get("status", existing.status),
        "feedback":    data.get("feedback", existing.feedback),
        "reviewer":    data.get("reviewer", existing.reviewer),
        "reviewed_at": data.get("reviewed_at", existing.reviewed_at),
        "format":      fmt,
        "answer_1":    data.get("answer_1", existing.answer_1),
        "answer_2":    data.get("answer_2", existing.answer_2),
        "answer_3":    data.get("answer_3", existing.answer_3),
    })
    with _connect() as conn:
        conn.execute(
            """UPDATE personal_statements SET
                   title = ?, body = ?, word_count = ?, char_count = ?,
                   line_count = ?, status = ?, feedback = ?,
                   reviewer = ?, reviewed_at = ?,
                   format = ?, answer_1 = ?, answer_2 = ?, answer_3 = ?,
                   updated_at = datetime('now')
               WHERE statement_id = ?""",
            (p["title"], p["body"], p["word_count"], p["char_count"],
             p["line_count"], p["status"], p["feedback"],
             p["reviewer"], p["reviewed_at"],
             p["format"], p["answer_1"], p["answer_2"], p["answer_3"],
             statement_id),
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
    issues = check_statement(existing)
    if issues:
        raise ValidationError(
            "Not ready for UCAS: " + " ".join(issues))
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
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


# ── Statements living on a UCAS application ───────────────────────
#
# There are two places a personal statement can be: a *draft* in this
# table, and the single ``personal_statement`` column on the student's
# UCAS application. ``push_to_ucas`` above copies the first into the
# second, and until now nothing came back — so a statement written in
# the UCAS applications screen was invisible here, which reads exactly
# like a screen that has lost its data.
#
# It is not lost, it just never was a draft. These two functions make it
# visible and let it be adopted as one.


@dataclass
class UcasStatement:
    """A personal statement that exists only on a UCAS application.

    Not a row in this table and deliberately not made to look like one —
    it has an ``application_id`` rather than a ``statement_id``, because
    it has no draft history, no reviewer and no feedback until somebody
    imports it.
    """
    application_id: int
    student_id: str
    cycle_year: int
    body: str
    word_count: int
    char_count: int
    line_count: int
    app_status: str
    updated_at: str


def _normalised(body: str | None) -> str:
    """Body text reduced to what a comparison should care about."""
    return " ".join((body or "").split())


def ucas_only_statements(
    *, student_id: str | None = None,
) -> list[UcasStatement]:
    """Statements on UCAS applications that are not already drafts here.

    A draft pushed to an application appears in both places; listing it
    twice would suggest two different statements. So anything whose text
    already matches one of that student's drafts is filtered out, and
    what remains is exactly the set that would otherwise be invisible.
    """
    init_db()
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    apps = _ucas.list_applications(student_id=student_id)
    if not apps:
        return []

    known: dict[str, set[str]] = {}
    for draft in list_statements(student_id=student_id):
        known.setdefault(draft.student_id, set()).add(
            _normalised(draft.body))

    out: list[UcasStatement] = []
    for app in apps:
        body = app.personal_statement or ""
        if not body.strip():
            continue
        if _normalised(body) in known.get(app.student_id, ()):
            continue
        words, chars, lines = compute_counts(body)
        out.append(UcasStatement(
            application_id=app.application_id,
            student_id=app.student_id,
            cycle_year=app.cycle_year,
            body=body,
            word_count=words, char_count=chars, line_count=lines,
            app_status=app.status,
            updated_at=app.updated_at,
        ))
    out.sort(key=lambda s: (s.student_id, s.cycle_year))
    logger.debug("ucas_only_statements(student_id=%r) -> %d",
                 student_id, len(out))
    return out


def import_from_ucas(
    application_id: int, *, title: str | None = None,
    status: str = DEFAULT_STATUS,
) -> PersonalStatement:
    """Adopt an application's personal statement as a draft here.

    The reverse of :func:`push_to_ucas`. The application keeps its copy —
    this is not a move, because the application's copy is the one that
    goes to UCAS and nothing here should be able to empty it.
    """
    init_db()
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    app = _ucas.get_application(application_id)
    if app is None:
        raise ValidationError(f"No UCAS application with id {application_id}")
    if not (app.personal_statement or "").strip():
        raise ValidationError(
            f"UCAS application #{application_id} has no personal statement "
            "on it to import.")
    out = create_statement({
        "student_id": app.student_id,
        "title": title or f"From UCAS application #{application_id} "
                          f"(cycle {app.cycle_year})",
        "body": app.personal_statement,
        "status": status,
    })
    logger.info(
        "Imported personal statement from UCAS application #%d as draft #%d",
        application_id, out.statement_id)
    return out


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
