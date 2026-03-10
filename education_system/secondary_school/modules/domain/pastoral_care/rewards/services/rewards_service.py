"""Rewards & Merits service."""

import logging
from education_system.secondary_school.core.exceptions import RewardsError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

REWARD_TYPES = ("merit", "commendation", "certificate", "headteacher_award", "house_point")
REWARD_CATEGORIES = ("academic", "effort", "behaviour", "attendance", "community",
                     "sport", "arts", "leadership", "kindness", "general")


class RewardsService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def award(self, student_id, reason, reward_type="merit", category="general",
              points=1, awarded_by=None, certificate=False):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO rewards
                   (student_id, reward_type, category, points, reason,
                    awarded_by, certificate_issued)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (student_id, reward_type, category, points, reason,
                 awarded_by, int(certificate)))
            conn.commit()
            return dict(conn.execute("SELECT * FROM rewards WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise RewardsError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_rewards(self, student_id=None, reward_type=None, category=None):
        conn = self._conn()
        try:
            sql = """SELECT r.*, s.first_name, s.last_name, s.student_id AS stu_code, s.year_group
                     FROM rewards r JOIN students s ON r.student_id = s.id WHERE 1=1"""
            params = []
            if student_id:
                sql += " AND r.student_id = ?"
                params.append(student_id)
            if reward_type:
                sql += " AND r.reward_type = ?"
                params.append(reward_type)
            if category:
                sql += " AND r.category = ?"
                params.append(category)
            sql += " ORDER BY r.awarded_date DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def delete_reward(self, reward_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM rewards WHERE id = ?", (reward_id,))
            conn.commit()
        finally:
            conn.close()

    def student_totals(self):
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT s.first_name, s.last_name, s.year_group,
                          SUM(r.points) as total_points, COUNT(*) as total_awards
                   FROM rewards r JOIN students s ON r.student_id = s.id
                   GROUP BY r.student_id ORDER BY total_points DESC"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def leaderboard(self, year_group=None, limit=20):
        conn = self._conn()
        try:
            sql = """SELECT s.first_name, s.last_name, s.year_group,
                            SUM(r.points) as total_points
                     FROM rewards r JOIN students s ON r.student_id = s.id WHERE 1=1"""
            params = []
            if year_group:
                sql += " AND s.year_group = ?"
                params.append(year_group)
            sql += " GROUP BY r.student_id ORDER BY total_points DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()
