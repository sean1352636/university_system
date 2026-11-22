"""The one definition of the student ``peer_reviews`` table.

Three files each created this table their own way on ``student_records.db``:

* ``attendance_warning_schemas`` made ``reviewer_id`` an INTEGER foreign key
  to ``users.id`` and ``reviewee_submission_id`` NOT NULL. That is the
  definition the established database got, and no code ever wrote a review
  that satisfied it: reviewers are students, identified by student number,
  and no writer filled ``reviewee_submission_id``. Allocating reviewers failed
  with a foreign key error from both the CLI and the GUI.
* The assignment CLI bootstrap made ``submission_id`` and ``review_date``
  NOT NULL.
* The assignment GUI bootstrap had neither submission column.

Reviewer and reviewee are students (``students.student_id``). The reviewed
work is ``submission_id``. ``reviewee_submission_id`` is kept, nullable, so
older rows and readers still work, and the rebuild copies it into
``submission_id`` where that is empty.

Allocation lives here, not in ``peer_review_assignments``: that name was
shared with the Staff HR teaching peer review (now ``hr_peer_review_assignments``),
and its established schema (``session_id`` NOT NULL, a UNIQUE text
``assignment_id``) belongs to neither use.
"""

from __future__ import annotations

PEER_REVIEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("assignment_id", "INTEGER NOT NULL"),
    ("reviewer_id", "TEXT NOT NULL"),
    ("reviewee_id", "TEXT"),
    ("submission_id", "INTEGER"),
    ("reviewee_submission_id", "INTEGER"),
    ("score", "REAL"),
    ("overall_score", "REAL"),
    ("feedback", "TEXT"),
    ("review_text", "TEXT"),
    ("rubric_scores", "TEXT"),
    ("is_anonymous", "INTEGER DEFAULT 1"),
    ("status", "TEXT DEFAULT 'pending'"),
    ("review_date", "TIMESTAMP"),
    ("submitted_at", "TIMESTAMP"),
    ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
)

_CONSTRAINTS = (
    "FOREIGN KEY (assignment_id) REFERENCES assignments (id) ON DELETE CASCADE",
    "FOREIGN KEY (reviewer_id) REFERENCES students (student_id)",
    "FOREIGN KEY (reviewee_id) REFERENCES students (student_id)",
    "FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id) ON DELETE CASCADE",
    "FOREIGN KEY (reviewee_submission_id) REFERENCES assignment_submissions (id) ON DELETE CASCADE",
)

INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_peer_reviews_reviewer ON peer_reviews (reviewer_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_peer_reviews_assignment ON peer_reviews (assignment_id)",
)


def create_peer_reviews_sql(table: str = "peer_reviews") -> str:
    """CREATE TABLE IF NOT EXISTS for the canonical table (or a rebuild copy)."""
    body = ",\n    ".join([f"{name} {decl}" for name, decl in PEER_REVIEW_COLUMNS] + list(_CONSTRAINTS))
    return f"CREATE TABLE IF NOT EXISTS {table} (\n    {body}\n)"


def needs_rebuild(create_sql: str | None) -> bool:
    """Does an existing table's DDL carry a constraint no writer can satisfy?"""
    if not create_sql:
        return False
    sql = " ".join(create_sql.split()).lower()
    return ("references users" in sql
            or "reviewee_submission_id integer not null" in sql
            or "submission_id integer not null" in sql
            or "review_date text not null" in sql
            or "reviewee_id text not null" in sql)


def ensure_peer_reviews_table(cursor) -> None:
    """Create the table if missing (runtime bootstraps). Never rebuilds — the
    migration does that, once, with foreign keys suspended."""
    cursor.execute(create_peer_reviews_sql())
    for ddl in INDEXES:
        cursor.execute(ddl)
