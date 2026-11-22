"""Progression outcomes at assessment boards, and data-driven classification rules.

Applied at runtime by :func:`apply_to_connection` (idempotent, additive only;
no Alembic revision so parallel work keeps a single head).

* ``board_progression_outcomes`` — one progression decision per student per
  progression/award board (progress, progress with trailing credit, resit,
  repeat year, withdraw/terminate, exit award). Recorded while the board is
  open, ratified with the board, released to the student, then rolled over
  (year of study advanced, or the registration it permits recorded). A new
  decision for the same student supersedes the old one, which is kept.
* ``classification_rule_sets`` — named, versioned classification schemes
  (UG honours, integrated masters, PGT, default) with their weights, bands,
  borderline zone and rule, and exit awards, held as JSON.
* ``classification_rule_bindings`` — which rule set applies to a regulation
  version (``programme_versions.version_id``) or, failing that, a programme
  code. Unbound students keep the built-in default (today's behaviour).
"""

from __future__ import annotations

OUTCOMES = ("progress", "progress_trailing", "resit", "repeat_year", "withdraw", "exit_award")
OUTCOME_STATUSES = ("provisional", "ratified", "under_correction", "superseded", "rolled_over")
SCHEMES = ("default", "ug_honours", "integrated_masters", "pgt")

TABLES = (
    """CREATE TABLE IF NOT EXISTS board_progression_outcomes (
        outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
        board_id INTEGER NOT NULL REFERENCES assessment_boards(board_id),
        student_id TEXT NOT NULL,
        academic_year TEXT NOT NULL,
        outcome TEXT NOT NULL CHECK (outcome IN ('progress', 'progress_trailing', 'resit',
                                                 'repeat_year', 'withdraw', 'exit_award')),
        from_year INTEGER,
        to_year INTEGER,
        trailing_modules TEXT,
        trailing_credits REAL,
        resit_modules TEXT,
        exit_award TEXT,
        exit_classification TEXT,
        proposed_outcome TEXT,
        rationale TEXT NOT NULL,
        decided_by TEXT NOT NULL,
        decided_at TEXT NOT NULL DEFAULT (datetime('now')),
        decision_id INTEGER,
        status TEXT NOT NULL DEFAULT 'provisional'
            CHECK (status IN ('provisional', 'ratified', 'under_correction', 'superseded',
                              'rolled_over')),
        supersedes_outcome_id INTEGER REFERENCES board_progression_outcomes(outcome_id),
        ratified_at TEXT,
        ratified_by TEXT,
        released INTEGER NOT NULL DEFAULT 0,
        released_at TEXT,
        released_by TEXT,
        rolled_over_at TEXT,
        rolled_over_by TEXT,
        rollover_note TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_progression_outcomes_student "
    "ON board_progression_outcomes(student_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_progression_outcomes_board "
    "ON board_progression_outcomes(board_id, status)",
    """CREATE TABLE IF NOT EXISTS classification_rule_sets (
        rule_set_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        scheme TEXT NOT NULL CHECK (scheme IN ('default', 'ug_honours', 'integrated_masters',
                                               'pgt')),
        config_json TEXT NOT NULL,
        notes TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        retired INTEGER NOT NULL DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS classification_rule_bindings (
        binding_id INTEGER PRIMARY KEY AUTOINCREMENT,
        version_id INTEGER UNIQUE,
        programme_code TEXT UNIQUE,
        rule_set_id INTEGER NOT NULL REFERENCES classification_rule_sets(rule_set_id),
        bound_by TEXT NOT NULL,
        bound_at TEXT NOT NULL DEFAULT (datetime('now')),
        CHECK (version_id IS NOT NULL OR programme_code IS NOT NULL)
    )""",
)


def _exists(execute, table) -> bool:
    return execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                   (table,)).fetchone() is not None


def apply(execute) -> None:
    """Create the tables. Outcomes need the board tables to exist first."""
    for ddl in TABLES:
        if "board_progression_outcomes" in ddl and not _exists(execute, "assessment_boards"):
            continue
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
    if key and _exists(conn.execute, "board_progression_outcomes"):
        _APPLIED.add(key)
