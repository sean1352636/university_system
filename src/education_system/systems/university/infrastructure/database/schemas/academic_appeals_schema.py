"""Academic appeals: the appeal record behind an ``institutional_cases`` row.

Used by :mod:`application.cases.appeals`. Idempotent, additive only; there is
no migration (the tables are created on first use by :func:`apply_to_connection`).

* ``academic_appeals`` — one per appeal case: the student, the grounds, what is
  appealed (a module result, a board decision or a progression outcome — plain
  ids, since those rows live in tables owned by other slices), the stage and
  its deadline, the handler, the outcome, the issues considered, the final
  decision date and the Completion of Procedures letter.
* ``academic_appeal_actions`` — what an upheld appeal sets in motion: a
  re-mark, an uncapped resit, or the board reconvening.
"""

from __future__ import annotations

TABLES = (
    """CREATE TABLE IF NOT EXISTS academic_appeals (
        appeal_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id TEXT NOT NULL UNIQUE REFERENCES institutional_cases(case_id),
        student_id TEXT NOT NULL,
        stage TEXT NOT NULL DEFAULT 'submitted' CHECK (stage IN
            ('submitted', 'eligibility', 'investigation', 'outcome', 'review', 'closed')),
        grounds TEXT NOT NULL,
        statement TEXT NOT NULL,
        module_code TEXT,
        assessment_name TEXT,
        current_result TEXT,
        module_grade_id INTEGER,
        board_id INTEGER,
        board_decision_id INTEGER,
        progression_outcome_id INTEGER,
        results_released_on TEXT,
        submission_deadline TEXT,
        late INTEGER NOT NULL DEFAULT 0,
        late_reason TEXT,
        submitted_at TEXT NOT NULL,
        submitted_by TEXT NOT NULL,
        stage_entered_at TEXT NOT NULL,
        stage_due TEXT,
        target_close_date TEXT,
        handler TEXT,
        eligibility_decision TEXT,
        eligibility_reason TEXT,
        outcome TEXT CHECK (outcome IS NULL OR outcome IN
            ('upheld', 'partly_upheld', 'not_upheld', 'ineligible', 'withdrawn')),
        outcome_rationale TEXT,
        outcome_at TEXT,
        issues_considered TEXT,
        review_requested_at TEXT,
        review_reason TEXT,
        review_outcome TEXT,
        review_rationale TEXT,
        review_decided_at TEXT,
        final_decision_date TEXT,
        cop_issued_at TEXT,
        cop_path TEXT,
        closed_at TEXT,
        ticket_id INTEGER,
        last_reminder_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS academic_appeal_actions (
        action_id INTEGER PRIMARY KEY AUTOINCREMENT,
        appeal_id INTEGER NOT NULL REFERENCES academic_appeals(appeal_id),
        action_type TEXT NOT NULL CHECK (action_type IN
            ('remark', 'uncapped_resit', 'board_reconvene')),
        student_id TEXT NOT NULL,
        module_code TEXT,
        board_id INTEGER,
        assigned_to TEXT,
        details TEXT,
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN
            ('open', 'in_progress', 'completed', 'failed', 'cancelled')),
        result TEXT,
        correction_id INTEGER,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        completed_by TEXT,
        completed_at TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_academic_appeals_student ON academic_appeals(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_academic_appeals_stage ON academic_appeals(stage, stage_due)",
    "CREATE INDEX IF NOT EXISTS idx_academic_appeal_actions_lookup ON "
    "academic_appeal_actions(student_id, module_code, action_type, status)",
)


def apply(execute) -> None:
    for ddl in TABLES:
        execute(ddl)


_APPLIED: set[str] = set()


def apply_to_connection(conn) -> None:
    """:func:`apply` on an open connection, once per database file.

    Inside a caller's open transaction it applies without committing (and is
    not remembered), so it can never commit half of someone else's work.
    In-memory databases are never remembered.
    """
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
