"""Extracted class implementation."""

from .. import election_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})

from education_system.systems.university.infrastructure.database.schemas.student_union_elections_schema import (
    ensure_election_tables,
)


class Database:
    """Adapter between the standalone UI's vocabulary and the central tables.

    Methods are intentionally thin and lean on direct SQL inside dashboard
    code; this class owns connection handling, schema bootstrap, and
    settings only. Mappings used throughout the file:

        positions  → elections (id, title = position, department,
                                nomination/voting windows, status,
                                description)
        candidates → election_candidates joined with students for the
                     display name; ``election_candidates.student_id``
                     is the link to the real student record
        votes      → election_votes (voter_id is a student_id)
        settings   → union_voting_settings (key, value) — created here,
                     used for the global "election_open" toggle that
                     gates the Voter Dashboard
    """

    def __init__(self):
        self.db_path = str(DEFAULT_DB_PATH)
        self._ensure_schema()

    def connect(self):
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self):
        """Idempotent: make sure the canonical `elections` table (and its
        candidate/ballot tables) exist with every column the screens use,
        create the settings table, install the per-voter uniqueness index.
        Safe to call repeatedly."""
        conn = self.connect()
        try:
            try:
                ensure_election_tables(conn.cursor())
                conn.commit()
            except sqlite3.OperationalError:
                pass
            stmts = (
                # Free-form key/value settings used by this GUI.
                "CREATE TABLE IF NOT EXISTS union_voting_settings ("
                "  key TEXT PRIMARY KEY, value TEXT)",
                # One vote per voter per election.
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "  idx_election_votes_uniq "
                "  ON election_votes(election_id, voter_id)",
            )
            for stmt in stmts:
                try:
                    conn.execute(stmt)
                    conn.commit()
                except sqlite3.OperationalError:
                    pass  # column/index already present
            # Default the global toggle to open.
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO union_voting_settings "
                    "(key, value) VALUES ('election_open', '1')")
                conn.commit()
            except sqlite3.OperationalError:
                pass
        finally:
            conn.close()

    def get_setting(self, key):
        conn = self.connect()
        try:
            r = conn.execute(
                "SELECT value FROM union_voting_settings WHERE key=?",
                (key,)).fetchone()
            return r[0] if r else None
        finally:
            conn.close()

    def set_setting(self, key, value):
        conn = self.connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO union_voting_settings "
                "(key, value) VALUES (?, ?)",
                (key, value))
            conn.commit()
        finally:
            conn.close()
