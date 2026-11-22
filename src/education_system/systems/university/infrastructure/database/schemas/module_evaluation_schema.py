"""Module evaluation surveys: the survey window, question sources and
per-lecturer questions, invitations (response rate and reminders), comment
screening and the module leader's response.

Shared by migration ``b5e7a9c1d3f6`` and :func:`apply_to_connection`
(``university/application/evaluation/module``). Idempotent.

Anonymity
---------
Who has responded is recorded only on ``eval_form_invitations.responded``
(no time). A response row carries a random token in ``student_hash`` — the
column used to hold an unsalted SHA-256 of the student id, which anyone with
the database could reverse by hashing every id. :func:`rehash_legacy`
converts those: the matching invitation is marked responded and the hash is
replaced with a random token. Submission times are kept to the day.
"""

from __future__ import annotations

import hashlib
import secrets

COLUMNS = (
    ("evaluation_forms", "opens_at", "TEXT"),
    ("evaluation_forms", "min_responses", "INTEGER DEFAULT 5"),
    ("evaluation_forms", "opened_by", "TEXT"),
    ("eval_form_questions", "scope", "TEXT DEFAULT 'module'"),
    ("eval_form_questions", "staff_username", "TEXT"),
    ("eval_form_questions", "source", "TEXT DEFAULT 'standard'"),
)

TABLES = (
    """CREATE TABLE IF NOT EXISTS eval_form_invitations (
        form_id INTEGER NOT NULL REFERENCES evaluation_forms(id),
        student_id TEXT NOT NULL,
        invited_at TEXT NOT NULL DEFAULT (date('now')),
        reminded_at TEXT,
        responded INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (form_id, student_id)
    )""",
    """CREATE TABLE IF NOT EXISTS eval_form_comment_reviews (
        answer_id INTEGER PRIMARY KEY REFERENCES eval_form_answers(id),
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'released', 'withheld')),
        reviewed_by TEXT,
        reviewed_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS eval_form_responses_to_students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        form_id INTEGER NOT NULL REFERENCES evaluation_forms(id),
        summary TEXT NOT NULL,
        actions TEXT,
        you_said TEXT,
        we_did TEXT,
        published INTEGER NOT NULL DEFAULT 0,
        author TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        published_at TEXT
    )""",
)


def _columns(execute, table):
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def rehash_legacy(execute) -> None:
    """Replace unsalted student-id hashes with random tokens, recording the
    response on the student's invitation instead."""
    if not _columns(execute, "eval_form_responses") or not _columns(execute, "students"):
        return
    rows = execute("SELECT id, form_id, student_hash FROM eval_form_responses WHERE "
                   "length(student_hash) = 64 AND student_hash NOT LIKE 'tok-%'").fetchall()
    if not rows:
        return
    by_hash = {hashlib.sha256(str(sid).encode("utf-8")).hexdigest(): sid
               for (sid,) in execute("SELECT student_id FROM students").fetchall()}
    for response_id, form_id, digest in rows:
        student = by_hash.get(digest)
        if student:
            execute("INSERT OR IGNORE INTO eval_form_invitations (form_id, student_id) "
                    "VALUES (?, ?)", (form_id, student))
            execute("UPDATE eval_form_invitations SET responded = 1 WHERE form_id = ? AND "
                    "student_id = ?", (form_id, student))
        execute("UPDATE eval_form_responses SET student_hash = ?, submitted_at = "
                "substr(submitted_at, 1, 10) WHERE id = ?",
                (f"tok-{secrets.token_hex(16)}", response_id))


def window_legacy(execute) -> None:
    """Forms created before surveys had a window ran for ever. Give each one
    the window it implied: from creation to the end of its academic year
    (31 August of the year the academic year ends)."""
    for form_id, year, created in execute(
            "SELECT id, academic_year, created_at FROM evaluation_forms "
            "WHERE opens_at IS NULL").fetchall():
        try:
            end_year = int(str(year)[:4]) + 1
        except ValueError:
            continue
        execute("UPDATE evaluation_forms SET opens_at = ?, closes_at = COALESCE(closes_at, ?) "
                "WHERE id = ?", (created or f"{end_year - 1}-09-01 00:00:00",
                                 f"{end_year}-08-31 23:59:59", form_id))


def apply(execute) -> None:
    for table, column, decl in COLUMNS:
        existing = _columns(execute, table)
        if existing and column not in existing:
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {decl}')
    if _columns(execute, "evaluation_forms"):
        for ddl in TABLES:
            execute(ddl)
        rehash_legacy(execute)
        window_legacy(execute)


_APPLIED: set[str] = set()


def apply_to_connection(conn) -> None:
    """:func:`apply` once per database file. Inside a caller's open
    transaction it applies without committing or caching."""
    try:
        key = conn.execute("PRAGMA database_list").fetchone()[2]
    except Exception:
        key = None
    if key and key in _APPLIED:
        return
    busy = conn.in_transaction
    apply(conn.execute)
    if busy:
        return
    conn.commit()
    if key:
        _APPLIED.add(key)
