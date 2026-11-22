"""Schema for exam marking control, module results and board locks.

Owned here, in shared infrastructure, because three slices use it: Academics
(Grade Tracking and the assignment system enter marks), Assessment (the grade
CLI and the exam boards), and the university application layer that holds the
rules. The migration and any runtime bootstrap both call :func:`apply`, so
they cannot drift. Everything is additive and idempotent.

``assessments`` (exams, tests, presentations…) gains the controls assignments
already have: anonymous marking, moderation, release, reassessment links.

``grades`` gains ``raw_score`` (the marker's score before a referral cap),
``result_code`` (``ABS`` absent, ``ABS-MC`` absent with accepted
mitigation), ``capped`` and ``released_at``.

``module_grades`` gains the result's standing: ``status`` (provisional,
awaiting_resit, confirmed), ``locked`` (set when an exam board ratifies),
``outcome`` (pass, fail, compensated, condoned, referred, deferred,
incomplete), ``credits_awarded``, ``board_id``, ``attempt`` and
``is_complete``.

The lock triggers refuse any change to a first-sit mark once its module result
is locked for that student, whichever code path writes it. Resit marks
(components whose ``reassessment_of`` is set) stay editable.
"""

ASSESSMENT_COLUMNS = (
    ("marks_released_at", "TEXT"),
    ("marks_released_by", "TEXT"),
    ("anonymous_marking", "INTEGER DEFAULT 0"),
    ("moderation_required", "INTEGER DEFAULT 0"),
    ("moderation_sample_pct", "REAL DEFAULT 10"),
    ("moderation_status", "TEXT DEFAULT 'not_started'"),
    ("reassessment_of", "INTEGER"),
    ("reassessment_type", "TEXT"),
)

GRADE_COLUMNS = (
    ("raw_score", "REAL"),
    ("result_code", "TEXT"),
    ("capped", "INTEGER DEFAULT 0"),
    ("released_at", "TEXT"),
)

MODULE_GRADE_COLUMNS = (
    ("status", "TEXT DEFAULT 'provisional'"),
    ("locked", "INTEGER DEFAULT 0"),
    ("outcome", "TEXT"),
    ("credits_awarded", "REAL"),
    ("board_id", "INTEGER"),
    ("confirmed_at", "TEXT"),
    ("attempt", "INTEGER DEFAULT 1"),
    ("is_complete", "INTEGER DEFAULT 0"),
)

TABLES = (
    """
    CREATE TABLE IF NOT EXISTS exam_candidate_numbers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_id INTEGER NOT NULL,
        student_id TEXT NOT NULL,
        candidate_number TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (assessment_id, student_id),
        UNIQUE (assessment_id, candidate_number),
        FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS exam_moderation (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_id INTEGER NOT NULL,
        grade_id INTEGER NOT NULL UNIQUE,
        first_mark REAL,
        first_marker TEXT,
        second_mark REAL,
        second_marker TEXT,
        agreed_mark REAL,
        agreed_by TEXT,
        notes TEXT,
        status TEXT NOT NULL DEFAULT 'sampled',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id) ON DELETE CASCADE,
        FOREIGN KEY (grade_id) REFERENCES grades (grade_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS exam_reassessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_assessment_id INTEGER NOT NULL,
        reassessment_assessment_id INTEGER NOT NULL,
        student_id TEXT NOT NULL,
        attempt_type TEXT NOT NULL,
        mark_cap_pct REAL,
        mc_claim_id INTEGER,
        created_at TEXT NOT NULL,
        created_by TEXT,
        UNIQUE (reassessment_assessment_id, student_id),
        FOREIGN KEY (original_assessment_id) REFERENCES assessments (assessment_id) ON DELETE CASCADE,
        FOREIGN KEY (reassessment_assessment_id) REFERENCES assessments (assessment_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS grade_change_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        record_id INTEGER,
        student_id TEXT,
        module_code TEXT,
        old_value TEXT,
        new_value TEXT,
        reason TEXT NOT NULL,
        changed_by TEXT,
        changed_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_grade_change_log_student ON grade_change_log (student_id, module_code)",
    "CREATE INDEX IF NOT EXISTS idx_module_grades_student_module ON module_grades (student_id, module_code)",
)

LOCK_MESSAGE = ("Marks for this module were ratified by an exam board. "
                "Reopen the board to change them.")

# A first-sit exam/test mark is locked when its module result is locked.
_GRADE_LOCKED = (
    "EXISTS (SELECT 1 FROM assessments a JOIN module_grades mg "
    "        ON mg.module_code = a.module_code AND mg.student_id = {row}.student_id "
    "        WHERE a.assessment_id = {row}.assessment_id AND a.reassessment_of IS NULL "
    "          AND mg.locked = 1)"
)
_SUBMISSION_LOCKED = (
    "EXISTS (SELECT 1 FROM assignments a JOIN module_grades mg "
    "        ON mg.module_code = a.module_code AND mg.student_id = {row}.student_id "
    "        WHERE a.id = {row}.assignment_id AND a.reassessment_of IS NULL "
    "          AND mg.locked = 1)"
)


def _trigger(name, timing, table, row, condition):
    return (f"CREATE TRIGGER IF NOT EXISTS {name} {timing} ON {table} FOR EACH ROW "
            f"WHEN {condition.format(row=row)} "
            f"BEGIN SELECT RAISE(ABORT, '{LOCK_MESSAGE}'); END")


TRIGGERS = (
    _trigger("grades_board_lock_insert", "BEFORE INSERT", "grades", "NEW", _GRADE_LOCKED),
    _trigger("grades_board_lock_update", "BEFORE UPDATE OF score, raw_score, result_code",
             "grades", "OLD", _GRADE_LOCKED),
    _trigger("grades_board_lock_delete", "BEFORE DELETE", "grades", "OLD", _GRADE_LOCKED),
    _trigger("submissions_board_lock_update", "BEFORE UPDATE OF grade",
             "assignment_submissions", "OLD", _SUBMISSION_LOCKED),
    _trigger("submissions_board_lock_delete", "BEFORE DELETE",
             "assignment_submissions", "OLD", _SUBMISSION_LOCKED),
)

_REQUIRED_TABLES = ("assessments", "grades", "module_grades", "assignments",
                    "assignment_submissions")


def apply(execute, existing_columns):
    """Bring a database up to this schema.

    ``execute(sql)`` runs one statement; ``existing_columns(table)`` returns a
    table's column names (empty when it does not exist). Does nothing until
    every table it extends exists — the owning bootstraps create those.
    """
    if not all(existing_columns(t) for t in _REQUIRED_TABLES):
        return False
    for table, columns in (("assessments", ASSESSMENT_COLUMNS),
                           ("grades", GRADE_COLUMNS),
                           ("module_grades", MODULE_GRADE_COLUMNS)):
        present = existing_columns(table)
        for name, decl in columns:
            if name not in present:
                execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {decl}')
    # The assignment QA columns (reassessment_of on assignments) are applied by
    # assessment_qa.schema; the submission trigger needs them.
    if "reassessment_of" not in existing_columns("assignments"):
        execute('ALTER TABLE "assignments" ADD COLUMN "reassessment_of" INTEGER')
    for ddl in TABLES + TRIGGERS:
        execute(ddl)
    return True


def apply_to_connection(conn):
    """Convenience wrapper for a sqlite3 connection."""
    def columns(table):
        return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
    applied = apply(conn.execute, columns)
    conn.commit()
    return applied
