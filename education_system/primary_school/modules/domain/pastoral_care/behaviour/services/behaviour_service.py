"""Behaviour management service for the Primary School Management System."""

import logging
from datetime import date

from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import BehaviourError
from education_system.primary_school.core.sql_safety import validate_identifier
import traceback

logger = logging.getLogger(__name__)


class BehaviourService:
    """CRUD operations for behaviour records."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def record_behaviour(self, pupil_id, type, category=None, description=None,
                         points=1, action_taken=None, recorded_by=None,
                         incident_date=None):
        """Record a behaviour incident (positive or negative)."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO behaviour_records (
                    pupil_id, type, category, description, points,
                    action_taken, recorded_by, incident_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pupil_id, type, category, description, points,
                    action_taken, recorded_by,
                    incident_date or date.today().isoformat(),
                ),
            )
            conn.commit()
            record_id = cursor.lastrowid
            logger.info(
                "Recorded %s behaviour for pupil %s (id=%s)",
                type, pupil_id, record_id,
            )
            return record_id
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise BehaviourError(f"Failed to record behaviour: {e}") from e
        finally:
            conn.close()

    def get_records(self, pupil_id=None, type=None, date_from=None,
                    date_to=None):
        """Retrieve behaviour records with optional filters."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM behaviour_records WHERE 1=1"
            params = []
            if pupil_id:
                sql += " AND pupil_id = ?"
                params.append(pupil_id)
            if type:
                sql += " AND type = ?"
                params.append(type)
            if date_from:
                sql += " AND incident_date >= ?"
                params.append(date_from)
            if date_to:
                sql += " AND incident_date <= ?"
                params.append(date_to)
            sql += " ORDER BY incident_date DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_record(self, record_id, **kwargs):
        """Update a behaviour record."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "type", "category", "description", "points",
                "action_taken", "recorded_by", "incident_date",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values()) + [record_id]
            cursor.execute(
                f"UPDATE behaviour_records SET {set_clause} WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated behaviour record: %s", record_id)
            return cursor.rowcount > 0
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise BehaviourError(f"Failed to update record: {e}") from e
        finally:
            conn.close()

    def delete_record(self, record_id):
        """Delete a behaviour record."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM behaviour_records WHERE id = ?", (record_id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted behaviour record: %s", record_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise BehaviourError(f"Failed to delete record: {e}") from e
        finally:
            conn.close()

    def get_pupil_summary(self, pupil_id):
        """Get positive/negative counts and total points for a pupil."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT
                    COALESCE(SUM(CASE WHEN type = 'Positive' THEN 1 ELSE 0 END), 0) AS positive_count,
                    COALESCE(SUM(CASE WHEN type = 'Negative' THEN 1 ELSE 0 END), 0) AS negative_count,
                    COALESCE(SUM(points), 0) AS total_points
                FROM behaviour_records
                WHERE pupil_id = ?""",
                (pupil_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else {
                "positive_count": 0, "negative_count": 0, "total_points": 0,
            }
        finally:
            conn.close()
