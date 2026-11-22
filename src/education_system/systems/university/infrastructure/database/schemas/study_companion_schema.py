"""AI Study Companion: study plans, flashcards, explanations, reminders.

Shared by migration ``d8f0a2c4e6b9`` and :func:`apply_to_connection`
(``study_hub/services/planning.AIStudyService``). Idempotent.

The four base tables used to be created by ``AIStudyService.__init__`` on
every construction, which also wrote an activity-log row each time. They are
declared here once, with the columns the companion now needs:

* ``study_plans`` gains the exam it prepares for (``exam_date``,
  ``exam_id``), the daily budget it was built with (``hours_per_day``),
  ``notes`` and a lifecycle (``status`` Active / Paused / Completed /
  Archived, with ``completed_at`` / ``archived_at`` / ``updated_at``).
* ``study_plan_tasks`` gains the module and topic a task is about, its kind
  (learn / practice / review / flashcards / deadline / final), a ``status``
  (pending / done / skipped — ``completed`` stays in step for old readers),
  and where a rescheduled task was first placed.
* ``flashcards`` gains SM-2 state (``ease_factor``, ``interval_days``,
  ``repetitions``, ``lapses``, ``last_quality``), where a card came from
  (``source`` manual / claude / extracted / explanation / mistake,
  ``source_ref``) and ``suspended``.
* ``concept_explanations`` records who wrote it (``source`` claude /
  course_materials, ``model``) and when it was rated.
* ``flashcard_reviews`` — every review, so accuracy and retention can be
  worked out over time instead of from two counters.
* ``study_companion_settings`` — a student's reminder and sharing choices.
* ``study_companion_reminders`` — one row per student, day and kind, so a
  reminder is sent once however often the companion is opened.

``student_id`` carries no foreign key: staff use the companion under their
username (they have no ``students`` row). The owner is resolved and checked
in code instead (``study_hub/services/study_context.owner_id``).
"""

from __future__ import annotations

PLAN_STATUSES = ("Active", "Paused", "Completed", "Archived")
TASK_STATUSES = ("pending", "done", "skipped")
TASK_KINDS = ("learn", "practice", "review", "flashcards", "deadline", "final", "custom")
CARD_SOURCES = ("manual", "claude", "extracted", "explanation", "mistake")
EXPLANATION_SOURCES = ("claude", "course_materials", "template")

BASE_TABLES = (
    """CREATE TABLE IF NOT EXISTS study_plans (
        plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        course_id TEXT,
        plan_name TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        total_hours INTEGER DEFAULT 0,
        difficulty_level TEXT DEFAULT 'Medium',
        status TEXT DEFAULT 'Active',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS study_plan_tasks (
        task_id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER NOT NULL,
        task_title TEXT NOT NULL,
        task_description TEXT,
        scheduled_date TEXT NOT NULL,
        duration_minutes INTEGER DEFAULT 60,
        priority TEXT DEFAULT 'Medium',
        completed BOOLEAN DEFAULT 0,
        completed_at TEXT,
        created_at TEXT,
        FOREIGN KEY (plan_id) REFERENCES study_plans(plan_id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS flashcards (
        flashcard_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        course_id TEXT,
        deck_name TEXT NOT NULL,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        difficulty_rating INTEGER DEFAULT 0,
        last_reviewed TEXT,
        next_review TEXT,
        review_count INTEGER DEFAULT 0,
        correct_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS concept_explanations (
        explanation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        course_id TEXT,
        concept_name TEXT NOT NULL,
        explanation TEXT NOT NULL,
        difficulty_level TEXT DEFAULT 'Beginner',
        helpful_rating INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
)

COLUMNS = (
    ("study_plans", "exam_date", "TEXT"),
    ("study_plans", "exam_id", "INTEGER"),
    ("study_plans", "hours_per_day", "REAL"),
    ("study_plans", "notes", "TEXT"),
    ("study_plans", "updated_at", "TEXT"),
    ("study_plans", "completed_at", "TEXT"),
    ("study_plans", "archived_at", "TEXT"),
    ("study_plan_tasks", "created_at", "TEXT"),
    ("study_plan_tasks", "module_code", "TEXT"),
    ("study_plan_tasks", "topic", "TEXT"),
    ("study_plan_tasks", "task_kind", "TEXT DEFAULT 'custom'"),
    ("study_plan_tasks", "status", "TEXT DEFAULT 'pending'"),
    ("study_plan_tasks", "original_date", "TEXT"),
    ("study_plan_tasks", "rescheduled_count", "INTEGER DEFAULT 0"),
    ("study_plan_tasks", "notes", "TEXT"),
    ("study_plan_tasks", "updated_at", "TEXT"),
    ("flashcards", "ease_factor", "REAL DEFAULT 2.5"),
    ("flashcards", "interval_days", "INTEGER DEFAULT 0"),
    ("flashcards", "repetitions", "INTEGER DEFAULT 0"),
    ("flashcards", "lapses", "INTEGER DEFAULT 0"),
    ("flashcards", "last_quality", "INTEGER"),
    ("flashcards", "source", "TEXT DEFAULT 'manual'"),
    ("flashcards", "source_ref", "TEXT"),
    ("flashcards", "suspended", "INTEGER DEFAULT 0"),
    ("flashcards", "updated_at", "TEXT"),
    ("concept_explanations", "source", "TEXT DEFAULT 'template'"),
    ("concept_explanations", "model", "TEXT"),
    ("concept_explanations", "rated_at", "TEXT"),
)

TABLES = (
    """CREATE TABLE IF NOT EXISTS flashcard_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        flashcard_id INTEGER NOT NULL REFERENCES flashcards(flashcard_id) ON DELETE CASCADE,
        student_id TEXT NOT NULL,
        quality INTEGER NOT NULL CHECK (quality BETWEEN 0 AND 5),
        interval_days INTEGER NOT NULL,
        ease_factor REAL NOT NULL,
        reviewed_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS study_companion_settings (
        student_id TEXT PRIMARY KEY,
        reminders_enabled INTEGER NOT NULL DEFAULT 1,
        email_reminders INTEGER NOT NULL DEFAULT 0,
        share_with_tutor INTEGER NOT NULL DEFAULT 1,
        daily_card_limit INTEGER NOT NULL DEFAULT 20
            CHECK (daily_card_limit BETWEEN 1 AND 500),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS study_companion_reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        reminder_date TEXT NOT NULL,
        kind TEXT NOT NULL,
        summary TEXT,
        sent_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (student_id, reminder_date, kind)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_study_plans_student ON study_plans(student_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_study_plan_tasks_plan ON "
    "study_plan_tasks(plan_id, scheduled_date)",
    "CREATE INDEX IF NOT EXISTS idx_flashcards_student_due ON "
    "flashcards(student_id, next_review)",
    "CREATE INDEX IF NOT EXISTS idx_concept_explanations_student ON "
    "concept_explanations(student_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_flashcard_reviews_card ON "
    "flashcard_reviews(flashcard_id, reviewed_at)",
    "CREATE INDEX IF NOT EXISTS idx_flashcard_reviews_student ON "
    "flashcard_reviews(student_id, reviewed_at)",
)


def _columns(execute, table):
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def apply(execute) -> None:
    for ddl in BASE_TABLES:
        execute(ddl)
    for table, column, decl in COLUMNS:
        existing = _columns(execute, table)
        if existing and column not in existing:
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {decl}')
    # Bring the new state columns into step with the old ones, once.
    execute("UPDATE study_plan_tasks SET status = 'done' "
            "WHERE completed = 1 AND COALESCE(status, 'pending') = 'pending'")
    execute("UPDATE study_plans SET exam_date = end_date WHERE exam_date IS NULL")
    for ddl in TABLES:
        execute(ddl)


_APPLIED: set[str] = set()


def apply_to_connection(conn) -> None:
    """:func:`apply` on an open connection, once per database file.

    Inside a caller's open transaction it applies without committing (and is
    not remembered), so it can never commit half of someone else's work; the
    caller's commit or rollback decides. In-memory databases are never
    remembered: a connection id can be reused by a new database.
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
