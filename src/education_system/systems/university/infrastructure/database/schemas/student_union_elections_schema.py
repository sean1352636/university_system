"""The one Student Union election table: ``elections``.

``elections`` is canonical. Its original columns were ``id, title,
description, start_date, end_date, status``; the election screens also need
the department, the nomination and voting windows and a creation time, so
those are added here (additively — existing rows keep their data).

Conventions every reader/writer follows:

* ``title`` holds the position being elected (e.g. "President");
* ``start_date`` / ``end_date`` mirror the voting window, so they are always
  written together with ``voting_start`` / ``voting_end``;
* ``election_candidates``, ``election_votes`` and ``ranked_votes`` declare
  ``FOREIGN KEY (election_id) REFERENCES elections (id)``.

``union_elections`` is legacy. Fresh databases no longer create it; where it
already exists its rows are folded into ``elections`` (same ids, so child
rows still match) by :func:`fold_legacy_union_elections`.
"""
from __future__ import annotations

ELECTIONS_DDL = """
CREATE TABLE IF NOT EXISTS elections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    start_date TEXT,
    end_date TEXT,
    status TEXT DEFAULT 'active',
    department TEXT,
    nomination_start TEXT,
    nomination_end TEXT,
    voting_start TEXT,
    voting_end TEXT,
    created_at TEXT
)
"""

# Columns added to databases whose ``elections`` predates the screens' needs.
ELECTION_EXTRA_COLUMNS = (
    "department", "nomination_start", "nomination_end",
    "voting_start", "voting_end", "created_at",
)

ELECTION_CANDIDATES_DDL = """
CREATE TABLE IF NOT EXISTS election_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    election_id INTEGER,
    student_id TEXT,
    manifesto TEXT,
    votes INTEGER DEFAULT 0,
    candidate_name TEXT,
    nomination_date TEXT,
    FOREIGN KEY (election_id) REFERENCES elections (id),
    FOREIGN KEY (student_id) REFERENCES students (student_id)
)
"""

ELECTION_VOTES_DDL = """
CREATE TABLE IF NOT EXISTS election_votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    election_id INTEGER,
    voter_id TEXT,
    candidate_id INTEGER,
    vote_time TEXT,
    student_id TEXT,
    vote_date TEXT,
    FOREIGN KEY (election_id) REFERENCES elections (id),
    FOREIGN KEY (voter_id) REFERENCES students (student_id),
    FOREIGN KEY (candidate_id) REFERENCES election_candidates (id)
)
"""

RANKED_VOTES_DDL = """
CREATE TABLE IF NOT EXISTS ranked_votes (
    vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
    election_id INTEGER,
    voter_id TEXT,
    candidate_preferences TEXT,  -- comma-separated candidate ids, preference order
    vote_time TEXT,
    FOREIGN KEY (election_id) REFERENCES elections (id),
    FOREIGN KEY (voter_id) REFERENCES students (student_id)
)
"""


# Columns the live tables carry (and voting_methods.candidates reads) that
# older code-created tables lack; added additively.
CHILD_EXTRA_COLUMNS = {
    "election_candidates": ("candidate_name", "nomination_date"),
    "election_votes": ("student_id", "vote_date"),
}


def _table_exists(cursor, name: str) -> bool:
    return cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone() is not None


def ensure_elections_table(cursor) -> None:
    """Create ``elections`` with every column, or add the missing ones. Idempotent."""
    cursor.execute(ELECTIONS_DDL)
    have = {row[1] for row in cursor.execute("PRAGMA table_info(elections)").fetchall()}
    for column in ELECTION_EXTRA_COLUMNS:
        if column not in have:
            # db-audit: ignore[DBW001] - column names come from the fixed tuple above
            cursor.execute(f"ALTER TABLE elections ADD COLUMN {column} TEXT")


def ensure_election_tables(cursor) -> None:
    """``elections`` plus its candidate/ballot tables, all keyed to ``elections(id)``."""
    ensure_elections_table(cursor)
    cursor.execute(ELECTION_CANDIDATES_DDL)
    cursor.execute(ELECTION_VOTES_DDL)
    cursor.execute(RANKED_VOTES_DDL)
    for table, columns in CHILD_EXTRA_COLUMNS.items():
        # db-audit: ignore[DBW001] - table names come from the fixed mapping above
        have = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()}
        for column in columns:
            if column not in have:
                # db-audit: ignore[DBW001] - fixed table/column names from the mapping above
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")


def fold_legacy_union_elections(cursor) -> int:
    """Copy any ``union_elections`` rows into ``elections`` (same ids). Idempotent.

    Also back-fills the nomination/voting/department columns on rows an
    earlier fold copied before those columns existed. Returns rows inserted.
    The legacy table itself is left in place.
    """
    if not _table_exists(cursor, "union_elections"):
        return 0
    ensure_elections_table(cursor)
    legacy = {row[1] for row in cursor.execute("PRAGMA table_info(union_elections)").fetchall()}
    description = ("COALESCE(u.description, u.department)" if "description" in legacy
                   else "u.department")
    created_at = "u.created_at" if "created_at" in legacy else "NULL"
    # db-audit: ignore[DBW001] - interpolated fragments are fixed column expressions
    cursor.execute(f"""
        INSERT INTO elections (id, title, description, start_date, end_date, status,
                               department, nomination_start, nomination_end,
                               voting_start, voting_end, created_at)
        SELECT u.election_id,
               COALESCE(NULLIF(TRIM(u.position), ''), 'Election ' || u.election_id),
               {description}, u.voting_start, u.voting_end, COALESCE(u.status, 'upcoming'),
               u.department, u.nomination_start, u.nomination_end,
               u.voting_start, u.voting_end, {created_at}
        FROM union_elections u
        WHERE NOT EXISTS (SELECT 1 FROM elections e WHERE e.id = u.election_id)
    """)
    inserted = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
    cursor.execute("""
        UPDATE elections SET
            department = COALESCE(department,
                (SELECT u.department FROM union_elections u WHERE u.election_id = elections.id)),
            nomination_start = COALESCE(nomination_start,
                (SELECT u.nomination_start FROM union_elections u WHERE u.election_id = elections.id)),
            nomination_end = COALESCE(nomination_end,
                (SELECT u.nomination_end FROM union_elections u WHERE u.election_id = elections.id)),
            voting_start = COALESCE(voting_start, start_date),
            voting_end = COALESCE(voting_end, end_date)
        WHERE id IN (SELECT election_id FROM union_elections)
          AND (nomination_start IS NULL OR voting_start IS NULL)
    """)
    return inserted


def sync_voting_window(cursor) -> None:
    """Keep ``start_date``/``end_date`` and ``voting_start``/``voting_end`` paired.

    Rows written by the older CLI only set start/end dates; rows written by
    the election screens set the voting window. Fill whichever side is blank.
    """
    cursor.execute("""
        UPDATE elections SET
            voting_start = COALESCE(voting_start, start_date),
            voting_end = COALESCE(voting_end, end_date),
            start_date = COALESCE(start_date, voting_start),
            end_date = COALESCE(end_date, voting_end)
        WHERE (voting_start IS NULL AND start_date IS NOT NULL)
           OR (voting_end IS NULL AND end_date IS NOT NULL)
           OR (start_date IS NULL AND voting_start IS NOT NULL)
           OR (end_date IS NULL AND voting_end IS NOT NULL)
    """)
