"""Extracted class implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class Database:
    """Thin connection wrapper over the central ``student_records.db``.

    It owns no schema. Every table the portal reads belongs to the wider
    university system, so this class only opens the shared connection and
    exposes query/execute helpers.
    """

    def __init__(self, db_path=None):
        from education_system.systems.university.infrastructure.database.db import get_connection
        self.conn = get_connection()
        self.conn.row_factory = sqlite3.Row
        # Foreign keys are enforced application-wide.
        self.conn.execute("PRAGMA foreign_keys = ON")
        # No create_tables()/seed_if_empty() any more: since migration
        # b4e19d7a3c62 the portal reads the university's own tables
        # (research_publications, ethics_reviews, ip_disclosures,
        # student_supervisions, research_milestones, and the staff /
        # students / external_examiners registers). Schema is owned by
        # Alembic, and demo rows have no place in a shared database.

    def query(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()

    def execute(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        self.conn.commit()
        return cur.lastrowid

    def close(self):
        self.conn.close()
