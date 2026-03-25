"""Rewards management service for the Primary School Management System."""

import logging
from datetime import date

from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import RewardsError
from education_system.primary_school.core.sql_safety import validate_identifier
import traceback

logger = logging.getLogger(__name__)


class RewardsService:
    """CRUD operations for rewards."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def award_reward(self, pupil_id, reward_type, reason=None, awarded_by=None,
                     house=None, points=1, award_date=None):
        """Award a reward to a pupil."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO rewards (
                    pupil_id, reward_type, reason, awarded_by,
                    house, points, award_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    pupil_id, reward_type, reason, awarded_by,
                    house, points, award_date or date.today().isoformat(),
                ),
            )
            conn.commit()
            reward_id = cursor.lastrowid
            logger.info(
                "Awarded %s to pupil %s (id=%s)", reward_type, pupil_id, reward_id,
            )
            return reward_id
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise RewardsError(f"Failed to award reward: {e}") from e
        finally:
            conn.close()

    def get_rewards(self, pupil_id=None, reward_type=None, house=None,
                    date_from=None, date_to=None):
        """Retrieve rewards with optional filters."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM rewards WHERE 1=1"
            params = []
            if pupil_id:
                sql += " AND pupil_id = ?"
                params.append(pupil_id)
            if reward_type:
                sql += " AND reward_type = ?"
                params.append(reward_type)
            if house:
                sql += " AND house = ?"
                params.append(house)
            if date_from:
                sql += " AND award_date >= ?"
                params.append(date_from)
            if date_to:
                sql += " AND award_date <= ?"
                params.append(date_to)
            sql += " ORDER BY award_date DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_reward(self, reward_id, **kwargs):
        """Update a reward record."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "reward_type", "reason", "awarded_by", "house",
                "points", "award_date",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values()) + [reward_id]
            cursor.execute(
                f"UPDATE rewards SET {set_clause} WHERE id = ?", values,
            )
            conn.commit()
            logger.info("Updated reward: %s", reward_id)
            return cursor.rowcount > 0
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise RewardsError(f"Failed to update reward: {e}") from e
        finally:
            conn.close()

    def delete_reward(self, reward_id):
        """Delete a reward record."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM rewards WHERE id = ?", (reward_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted reward: %s", reward_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise RewardsError(f"Failed to delete reward: {e}") from e
        finally:
            conn.close()

    def get_house_points_summary(self):
        """Get total points per house."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT house, COALESCE(SUM(points), 0) AS total_points
                FROM rewards
                WHERE house IS NOT NULL
                GROUP BY house
                ORDER BY total_points DESC""",
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_pupil_rewards_summary(self, pupil_id):
        """Get count per reward type for a pupil."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT reward_type, COUNT(*) AS count,
                    COALESCE(SUM(points), 0) AS total_points
                FROM rewards
                WHERE pupil_id = ?
                GROUP BY reward_type
                ORDER BY count DESC""",
                (pupil_id,),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
