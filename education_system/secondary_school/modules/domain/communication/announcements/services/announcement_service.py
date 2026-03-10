"""Announcements service."""

import logging
from education_system.secondary_school.core.exceptions import AnnouncementError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

AUDIENCES = ("all", "staff", "students", "year_group", "admin")
PRIORITIES = ("low", "normal", "high", "urgent")


class AnnouncementService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create(self, title, body, audience="all", year_group=None,
               priority="normal", created_by=None, expires_at=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO announcements (title, body, audience, year_group, priority, created_by, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (title, body, audience, year_group, priority, created_by, expires_at))
            conn.commit()
            row = conn.execute("SELECT * FROM announcements WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise AnnouncementError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_announcements(self, audience=None, published_only=True):
        conn = self._conn()
        try:
            sql = "SELECT * FROM announcements WHERE 1=1"
            params = []
            if published_only:
                sql += " AND published = 1"
            if audience and audience != "All":
                sql += " AND (audience = ? OR audience = 'all')"
                params.append(audience)
            sql += " ORDER BY CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def delete(self, announcement_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM announcements WHERE id = ?", (announcement_id,))
            conn.commit()
        finally:
            conn.close()

    def toggle_publish(self, announcement_id):
        conn = self._conn()
        try:
            row = conn.execute("SELECT published FROM announcements WHERE id = ?", (announcement_id,)).fetchone()
            if row:
                conn.execute("UPDATE announcements SET published = ? WHERE id = ?",
                             (0 if row["published"] else 1, announcement_id))
                conn.commit()
        finally:
            conn.close()
