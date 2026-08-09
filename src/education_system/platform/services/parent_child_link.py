"""Parent-child link service.

Manages the mapping between parent/guardian user accounts and student records
across all four education systems.
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS parent_child_links (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_user_id   INTEGER NOT NULL,
    child_student_id TEXT    NOT NULL,
    child_system_key TEXT    NOT NULL,
    relationship     TEXT    NOT NULL DEFAULT 'parent',
    is_active        INTEGER NOT NULL DEFAULT 1,
    created_at       TEXT    NOT NULL,
    UNIQUE (parent_user_id, child_student_id, child_system_key)
);
CREATE INDEX IF NOT EXISTS idx_pcl_parent  ON parent_child_links(parent_user_id);
CREATE INDEX IF NOT EXISTS idx_pcl_child   ON parent_child_links(child_student_id, child_system_key);
CREATE INDEX IF NOT EXISTS idx_pcl_active  ON parent_child_links(is_active);
"""


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_parent_links_db(db_path: str) -> None:
    """Create the parent_child_links table if it does not exist."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
        logger.info("parent_child_links table initialised at %s", db_path)
    finally:
        conn.close()


class ParentChildLinkService:
    """Manage parent-child links stored in *db_path*.

    Typical usage::

        svc = ParentChildLinkService("/path/to/auth.db")
        svc.link_child(parent_user_id=7, child_student_id="STU001",
                       child_system_key="secondary", relationship="parent")
        children = svc.get_children(parent_user_id=7)
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        init_parent_links_db(db_path)

    # ── Internal ────────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        return _connect(self._db_path)

    # ── Public API ──────────────────────────────────────────────────────

    def link_child(
        self,
        parent_user_id: int,
        child_student_id: str,
        child_system_key: str,
        relationship: str = "parent",
    ) -> dict:
        """Create or reactivate a parent-child link.

        Returns the link record as a dict.
        """
        now = datetime.utcnow().isoformat()
        conn = self._conn()
        try:
            # Upsert: insert or reactivate
            conn.execute(
                """
                INSERT INTO parent_child_links
                    (parent_user_id, child_student_id, child_system_key,
                     relationship, is_active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
                ON CONFLICT(parent_user_id, child_student_id, child_system_key)
                DO UPDATE SET is_active = 1,
                              relationship = excluded.relationship
                """,
                (parent_user_id, child_student_id, child_system_key, relationship, now),
            )
            conn.commit()
            row = conn.execute(
                """
                SELECT * FROM parent_child_links
                WHERE parent_user_id = ? AND child_student_id = ? AND child_system_key = ?
                """,
                (parent_user_id, child_student_id, child_system_key),
            ).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def unlink_child(
        self,
        parent_user_id: int,
        child_student_id: str,
        child_system_key: str,
    ) -> bool:
        """Soft-delete a parent-child link.  Returns True if a row was updated."""
        conn = self._conn()
        try:
            cursor = conn.execute(
                """
                UPDATE parent_child_links SET is_active = 0
                WHERE parent_user_id = ? AND child_student_id = ? AND child_system_key = ?
                  AND is_active = 1
                """,
                (parent_user_id, child_student_id, child_system_key),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_children(self, parent_user_id: int) -> list[dict]:
        """Return all active children linked to *parent_user_id*."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """
                SELECT id, parent_user_id, child_student_id, child_system_key,
                       relationship, is_active, created_at
                FROM parent_child_links
                WHERE parent_user_id = ? AND is_active = 1
                ORDER BY child_system_key, child_student_id
                """,
                (parent_user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_parents(self, child_student_id: str, child_system_key: str | None = None) -> list[dict]:
        """Return all active parents linked to *child_student_id*.

        If *child_system_key* is given, filter to that system.
        """
        conn = self._conn()
        try:
            if child_system_key:
                rows = conn.execute(
                    """
                    SELECT * FROM parent_child_links
                    WHERE child_student_id = ? AND child_system_key = ? AND is_active = 1
                    """,
                    (child_student_id, child_system_key),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM parent_child_links
                    WHERE child_student_id = ? AND is_active = 1
                    """,
                    (child_student_id,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def verify_parent_access(
        self,
        parent_user_id: int,
        child_student_id: str,
        child_system_key: str | None = None,
    ) -> bool:
        """Return True if *parent_user_id* has an active link to *child_student_id*."""
        conn = self._conn()
        try:
            if child_system_key:
                row = conn.execute(
                    """
                    SELECT 1 FROM parent_child_links
                    WHERE parent_user_id = ? AND child_student_id = ?
                      AND child_system_key = ? AND is_active = 1
                    LIMIT 1
                    """,
                    (parent_user_id, child_student_id, child_system_key),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT 1 FROM parent_child_links
                    WHERE parent_user_id = ? AND child_student_id = ? AND is_active = 1
                    LIMIT 1
                    """,
                    (parent_user_id, child_student_id),
                ).fetchone()
            return row is not None
        finally:
            conn.close()
