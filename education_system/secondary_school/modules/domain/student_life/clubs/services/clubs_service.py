"""Clubs & Extracurricular service."""

import logging
from education_system.secondary_school.core.exceptions import ClubsError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

CATEGORIES = ("sport", "arts", "music", "drama", "academic", "stem", "community", "general")


class ClubsService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_club(self, name, category="general", description=None, day_of_week=None,
                    start_time=None, end_time=None, location=None, teacher=None,
                    max_members=None, year_groups=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO clubs (name, category, description, day_of_week, start_time,
                   end_time, location, teacher, max_members, year_groups)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, category, description, day_of_week, start_time, end_time,
                 location, teacher, max_members, year_groups))
            conn.commit()
            return dict(conn.execute("SELECT * FROM clubs WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise ClubsError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_clubs(self, status="active"):
        conn = self._conn()
        try:
            sql = "SELECT * FROM clubs WHERE 1=1"
            params = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY name"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def delete_club(self, club_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM club_members WHERE club_id = ?", (club_id,))
            conn.execute("DELETE FROM clubs WHERE id = ?", (club_id,))
            conn.commit()
        finally:
            conn.close()

    def add_member(self, club_id, student_id):
        conn = self._conn()
        try:
            conn.execute("INSERT INTO club_members (club_id, student_id) VALUES (?, ?)",
                         (club_id, student_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise ClubsError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_members(self, club_id):
        conn = self._conn()
        try:
            sql = """SELECT cm.*, s.first_name, s.last_name, s.student_id as stu_code, s.year_group
                     FROM club_members cm
                     JOIN students s ON cm.student_id = s.id
                     WHERE cm.club_id = ? AND cm.status = 'active'
                     ORDER BY s.last_name"""
            return [dict(r) for r in conn.execute(sql, (club_id,)).fetchall()]
        finally:
            conn.close()

    def remove_member(self, member_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM club_members WHERE id = ?", (member_id,))
            conn.commit()
        finally:
            conn.close()

    def member_count(self, club_id):
        conn = self._conn()
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM club_members WHERE club_id = ? AND status = 'active'",
                               (club_id,)).fetchone()
            return row["cnt"]
        finally:
            conn.close()
