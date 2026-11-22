"""Schema for assignment quality assurance.

The DDL lives here so the alembic migration and the runtime bootstrap
(``AssessmentQAService.ensure_schema``) cannot drift. Everything is additive
and idempotent: new columns are only added when missing, new tables use
``IF NOT EXISTS``.

Columns added to ``assignments``:

* ``assessment_kind`` — 'summative' (counts) or 'formative' (practice only).
* ``module_weight_pct`` — share of the module mark. NULL on every assignment
  in a module means "weight equally".
* ``anonymous_marking`` — markers see a candidate number, not a name, until
  grades are released.
* ``word_limit`` / ``word_limit_tolerance_pct`` / ``word_limit_penalty_pct``
  — a submission over limit+tolerance loses ``penalty_pct`` percentage points.
* ``feedback_due_date`` — the turnaround promise to students.
* ``grade_release_date`` — grades stay hidden until this date and are released
  together, for the whole cohort.
* ``moderation_required`` / ``moderation_sample_pct`` / ``moderation_status``
  — second marking of a sample before release.
* ``grades_released_at`` / ``grades_released_by`` — set by a cohort release.
* ``reassessment_of`` / ``reassessment_type`` — a referral or deferral sitting
  of another assignment.

Columns added to ``assignment_submissions``: ``raw_grade`` (the marker's mark
before any word-limit penalty or referral cap), ``word_count``,
``word_penalty_pct``, ``capped`` and ``grade_released_at``.
"""

ASSIGNMENT_COLUMNS = (
    ("assessment_kind", "TEXT DEFAULT 'summative'"),
    ("module_weight_pct", "REAL"),
    ("anonymous_marking", "INTEGER DEFAULT 0"),
    ("word_limit", "INTEGER"),
    ("word_limit_tolerance_pct", "REAL DEFAULT 10"),
    ("word_limit_penalty_pct", "REAL DEFAULT 10"),
    ("feedback_due_date", "TEXT"),
    ("grade_release_date", "TEXT"),
    ("moderation_required", "INTEGER DEFAULT 0"),
    ("moderation_sample_pct", "REAL DEFAULT 10"),
    ("moderation_status", "TEXT DEFAULT 'not_started'"),
    ("grades_released_at", "TEXT"),
    ("grades_released_by", "TEXT"),
    ("reassessment_of", "INTEGER"),
    ("reassessment_type", "TEXT"),
)

SUBMISSION_COLUMNS = (
    ("raw_grade", "REAL"),
    ("word_count", "INTEGER"),
    ("word_penalty_pct", "REAL"),
    ("capped", "INTEGER DEFAULT 0"),
    ("grade_released_at", "TEXT"),
)

TABLES = (
    """
    CREATE TABLE IF NOT EXISTS assignment_candidate_numbers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id INTEGER NOT NULL,
        student_id TEXT NOT NULL,
        candidate_number TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (assignment_id, student_id),
        UNIQUE (assignment_id, candidate_number),
        FOREIGN KEY (assignment_id) REFERENCES assignments (id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS assignment_moderation (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id INTEGER NOT NULL,
        submission_id INTEGER NOT NULL UNIQUE,
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
        FOREIGN KEY (assignment_id) REFERENCES assignments (id) ON DELETE CASCADE,
        FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS assignment_non_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id INTEGER NOT NULL,
        student_id TEXT NOT NULL,
        code TEXT NOT NULL DEFAULT 'NS',
        recorded_at TEXT NOT NULL,
        recorded_by TEXT,
        voided INTEGER NOT NULL DEFAULT 0,
        UNIQUE (assignment_id, student_id),
        FOREIGN KEY (assignment_id) REFERENCES assignments (id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS assignment_reassessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_assignment_id INTEGER NOT NULL,
        reassessment_assignment_id INTEGER NOT NULL,
        student_id TEXT NOT NULL,
        attempt_type TEXT NOT NULL,
        mark_cap_pct REAL,
        mc_claim_id INTEGER,
        created_at TEXT NOT NULL,
        created_by TEXT,
        UNIQUE (reassessment_assignment_id, student_id),
        FOREIGN KEY (original_assignment_id) REFERENCES assignments (id) ON DELETE CASCADE,
        FOREIGN KEY (reassessment_assignment_id) REFERENCES assignments (id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_assignment_moderation_assignment "
    "ON assignment_moderation (assignment_id)",
    "CREATE INDEX IF NOT EXISTS idx_assignment_reassessments_student "
    "ON assignment_reassessments (student_id)",
)


def apply(execute, existing_columns):
    """Bring a database up to this schema.

    ``execute(sql)`` runs one statement; ``existing_columns(table)`` returns
    the set of column names a table currently has (empty if the table is
    missing). Taking callables lets the migration (SQLAlchemy bind) and the
    runtime bootstrap (sqlite3 connection) share this function.
    """
    for table, columns in (("assignments", ASSIGNMENT_COLUMNS),
                           ("assignment_submissions", SUBMISSION_COLUMNS)):
        present = existing_columns(table)
        if not present:
            # The owning bootstrap has not created the table yet; it will
            # pick these columns up on the next run.
            continue
        for name, decl in columns:
            if name not in present:
                execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {decl}')

    if existing_columns("assignments") and existing_columns("assignment_submissions"):
        for ddl in TABLES:
            execute(ddl)
