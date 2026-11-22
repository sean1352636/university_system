"""Course evaluation surveys: one survey per course (programme) and academic
year on ``course_evaluations``, the course team who may read the results,
invitations (eligibility, one response each, response rate and reminders),
comment screening and the course leader's response to students.

Shared by migration ``c6f8b0d2e4a7`` and :func:`apply_to_connection`
(``university/application/evaluation/course``). Idempotent.

Anonymity
---------
Who has answered is recorded only on ``course_eval_invitations.responded``
(no time). ``evaluation_responses.student_id`` and the legacy
``evaluations.student_id`` used to hold the student id itself next to the
ratings and comments; :func:`anonymise_legacy` replaces each with a random
``tok-`` token (marking the matching invitation answered) and keeps
submission dates to the day.
"""

from __future__ import annotations

import secrets

COLUMNS = (
    ("course_evaluations", "course_code", "TEXT"),
    ("course_evaluations", "min_responses", "INTEGER DEFAULT 5"),
    ("course_evaluations", "opened_by", "TEXT"),
    ("course_evaluations", "closed_at", "TEXT"),
)

TABLES = (
    """CREATE TABLE IF NOT EXISTS course_team (
        course_code TEXT NOT NULL,
        username TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('leader', 'member')),
        added_by TEXT,
        added_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (course_code, username)
    )""",
    """CREATE TABLE IF NOT EXISTS course_eval_invitations (
        evaluation_id INTEGER NOT NULL REFERENCES course_evaluations(evaluation_id),
        student_id TEXT NOT NULL,
        invited_at TEXT NOT NULL DEFAULT (date('now')),
        reminded_at TEXT,
        responded INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (evaluation_id, student_id)
    )""",
    """CREATE TABLE IF NOT EXISTS course_eval_comment_reviews (
        answer_id INTEGER PRIMARY KEY REFERENCES evaluation_answers(answer_id),
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'released', 'withheld')),
        reviewed_by TEXT,
        reviewed_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS course_eval_responses_to_students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        evaluation_id INTEGER NOT NULL REFERENCES course_evaluations(evaluation_id),
        summary TEXT NOT NULL,
        actions TEXT,
        you_said TEXT,
        we_did TEXT,
        published INTEGER NOT NULL DEFAULT 0,
        author TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        published_at TEXT
    )""",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_course_team_leader ON course_team (course_code) "
    "WHERE role = 'leader'",
)


def _columns(execute, table):
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def _token():
    return f"tok-{secrets.token_hex(16)}"


def link_legacy(execute) -> None:
    """Surveys created against a course code before ``course_code`` existed
    (``module_code`` = 'CS') become that course's surveys. They had no real
    window or invitations, so they are closed; their answers are kept."""
    if not _columns(execute, "courses"):
        return
    execute("UPDATE course_evaluations SET course_code = module_code, is_active = 0, "
            "closed_at = COALESCE(closed_at, datetime('now')) WHERE course_code IS NULL "
            "AND module_code IN (SELECT COALESCE(NULLIF(course_code, ''), code) FROM courses)")


def anonymise_legacy(execute) -> None:
    """Replace stored student ids with random tokens."""
    rows = execute("SELECT r.response_id, r.evaluation_id, r.student_id, e.course_code FROM "
                   "evaluation_responses r LEFT JOIN course_evaluations e ON "
                   "e.evaluation_id = r.evaluation_id WHERE r.student_id IS NOT NULL AND "
                   "r.student_id NOT LIKE 'tok-%'").fetchall()
    known = set()
    if rows and _columns(execute, "students"):
        known = {str(r[0]) for r in execute("SELECT student_id FROM students").fetchall()}
    for response_id, evaluation_id, student, course in rows:
        if course and str(student) in known:
            execute("INSERT OR IGNORE INTO course_eval_invitations (evaluation_id, student_id) "
                    "VALUES (?, ?)", (evaluation_id, str(student)))
            execute("UPDATE course_eval_invitations SET responded = 1 WHERE evaluation_id = ? "
                    "AND student_id = ?", (evaluation_id, str(student)))
        execute("UPDATE evaluation_responses SET student_id = ?, submitted_at = "
                "substr(submitted_at, 1, 10), response_date = substr(response_date, 1, 10) "
                "WHERE response_id = ?", (_token(), response_id))
    legacy = _columns(execute, "evaluations")
    if {"student_id", "submitted_at"} <= legacy:
        for (row_id,) in execute("SELECT id FROM evaluations WHERE student_id IS NOT NULL AND "
                                 "CAST(student_id AS TEXT) NOT LIKE 'tok-%'").fetchall():
            execute("UPDATE evaluations SET student_id = ?, submitted_at = "
                    "substr(submitted_at, 1, 10) WHERE id = ?", (_token(), row_id))


def apply(execute) -> None:
    if not _columns(execute, "course_evaluations"):
        return
    for table, column, decl in COLUMNS:
        existing = _columns(execute, table)
        if existing and column not in existing:
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {decl}')
    for ddl in TABLES:
        execute(ddl)
    link_legacy(execute)
    if _columns(execute, "evaluation_responses"):
        anonymise_legacy(execute)


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
