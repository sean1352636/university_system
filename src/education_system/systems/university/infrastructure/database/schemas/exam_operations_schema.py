"""Schema for running exams: timetable publication, the assessment link,
invigilation, incidents and exam papers.

Shared infrastructure because the Exam Management GUI, the exam CLIs and the
rules in ``university/application`` all use it. The migration and the runtime
bootstraps both call :func:`apply`. Additive and idempotent.

``exams`` gains:

* ``assessment_id`` — the ``assessments`` row this sitting's marks belong to.
  Results are written to ``grades`` against it, so they count in the module
  result and follow the release, moderation and board-lock rules.
* ``status`` (draft/published), ``published_at``, ``published_by`` — a
  timetable is drafted, checked for clashes, then published to students.
  Existing exams default to ``published``: students already have them.

``exam_portal_exams`` (online exams) gains ``assessment_id`` for the same
reason.
"""

EXAM_COLUMNS = (
    ("assessment_id", "INTEGER"),
    ("status", "TEXT DEFAULT 'published'"),
    ("published_at", "TEXT"),
    ("published_by", "TEXT"),
)

PORTAL_COLUMNS = (
    ("assessment_id", "INTEGER"),
)

TABLES = (
    """
    CREATE TABLE IF NOT EXISTS exam_incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER NOT NULL,
        student_id TEXT,
        incident_type TEXT NOT NULL,
        description TEXT NOT NULL,
        minutes_late INTEGER,
        action_taken TEXT,
        occurred_at TEXT NOT NULL,
        reported_by TEXT,
        case_id TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (exam_id) REFERENCES exams (id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS exam_invigilators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER NOT NULL,
        staff_id TEXT NOT NULL,
        staff_name TEXT,
        role TEXT NOT NULL DEFAULT 'invigilator',
        room TEXT,
        created_at TEXT NOT NULL,
        UNIQUE (exam_id, staff_id),
        FOREIGN KEY (exam_id) REFERENCES exams (id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS exam_papers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'draft',
        setter TEXT,
        internal_checker TEXT,
        internal_checked_at TEXT,
        external_examiner TEXT,
        external_approved_at TEXT,
        print_deadline TEXT,
        printed_at TEXT,
        secured_location TEXT,
        notes TEXT,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (exam_id) REFERENCES exams (id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS exam_paper_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        paper_id INTEGER NOT NULL,
        from_status TEXT,
        to_status TEXT NOT NULL,
        actor TEXT,
        notes TEXT,
        changed_at TEXT NOT NULL,
        FOREIGN KEY (paper_id) REFERENCES exam_papers (id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_exam_incidents_exam ON exam_incidents (exam_id)",
    "CREATE INDEX IF NOT EXISTS idx_exam_invigilators_staff ON exam_invigilators (staff_id)",
)


def apply(execute, existing_columns):
    """Bring a database up to this schema. Returns False until ``exams`` exists."""
    present = existing_columns("exams")
    if not present:
        return False
    for name, decl in EXAM_COLUMNS:
        if name not in present:
            execute(f'ALTER TABLE "exams" ADD COLUMN "{name}" {decl}')
    portal = existing_columns("exam_portal_exams")
    if portal:
        for name, decl in PORTAL_COLUMNS:
            if name not in portal:
                execute(f'ALTER TABLE "exam_portal_exams" ADD COLUMN "{name}" {decl}')
    for ddl in TABLES:
        execute(ddl)
    return True


def apply_to_connection(conn):
    def columns(table):
        return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
    applied = apply(conn.execute, columns)
    conn.commit()
    return applied
