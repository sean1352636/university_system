"""Module registration: per course and year credit rules, students' optional
module choices awaiting approval. Registration periods and enrolment status
changes live in ``services/bus/registration_calendar``'s tables.

Shared by migration ``b3d5f7a9c1e4`` and :func:`apply_to_connection`
(``university/application/modules/registration``). Idempotent.
"""

from __future__ import annotations

TABLES = (
    """CREATE TABLE IF NOT EXISTS programme_credit_rules (
        course_code TEXT NOT NULL,
        year_of_study INTEGER NOT NULL CHECK (year_of_study BETWEEN 0 AND 7),
        target_credits INTEGER NOT NULL DEFAULT 120 CHECK (target_credits > 0),
        max_credits INTEGER NOT NULL DEFAULT 140,
        min_optional INTEGER NOT NULL DEFAULT 0,
        max_optional INTEGER,
        needs_approval INTEGER NOT NULL DEFAULT 1,
        updated_by TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (course_code, year_of_study),
        CHECK (max_credits >= target_credits)
    )""",
    """CREATE TABLE IF NOT EXISTS module_choice_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        academic_year TEXT NOT NULL,
        year_of_study INTEGER,
        status TEXT NOT NULL DEFAULT 'submitted'
            CHECK (status IN ('submitted', 'approved', 'rejected', 'withdrawn')),
        submitted_by TEXT,
        submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
        decided_by TEXT,
        decided_at TEXT,
        note TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_module_choice_submissions_student ON "
    "module_choice_submissions (student_id, status)",
    """CREATE TABLE IF NOT EXISTS module_choice_items (
        submission_id INTEGER NOT NULL REFERENCES module_choice_submissions(id)
            ON DELETE CASCADE,
        module_code TEXT NOT NULL,
        result TEXT,
        PRIMARY KEY (submission_id, module_code)
    )""",
)


def apply(execute) -> None:
    for ddl in TABLES:
        execute(ddl)


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
