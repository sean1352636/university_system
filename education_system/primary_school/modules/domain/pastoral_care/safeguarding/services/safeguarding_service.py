"""Safeguarding service for the Primary School Management System."""

import logging
from datetime import date

from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import SafeguardingError
from education_system.primary_school.core.sql_safety import validate_identifier  # nosec B608
import traceback

logger = logging.getLogger(__name__)


class SafeguardingService:
    """CRUD operations for safeguarding concerns."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def record_concern(self, pupil_id, concern_type, description,
                       severity="Low", reported_by="", reported_date=None,
                       action_taken=None):
        """Record a safeguarding concern."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO safeguarding_concerns (
                    pupil_id, concern_type, description, severity,
                    reported_by, reported_date, action_taken, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Open')""",
                (
                    pupil_id, concern_type, description, severity,
                    reported_by, reported_date or date.today().isoformat(),
                    action_taken,
                ),
            )
            conn.commit()
            concern_id = cursor.lastrowid
            logger.info(
                "Recorded safeguarding concern for pupil %s (id=%s, severity=%s)",
                pupil_id, concern_id, severity,
            )
            return concern_id
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise SafeguardingError(f"Failed to record concern: {e}") from e
        finally:
            conn.close()

    def get_concerns(self, pupil_id=None, status="Open", severity=None):
        """Retrieve safeguarding concerns with optional filters."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM safeguarding_concerns WHERE 1=1"
            params = []
            if pupil_id:
                sql += " AND pupil_id = ?"
                params.append(pupil_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            if severity:
                sql += " AND severity = ?"
                params.append(severity)
            sql += " ORDER BY reported_date DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_concern(self, concern_id, **kwargs):
        """Update a safeguarding concern."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "concern_type", "description", "severity", "reported_by",
                "reported_date", "action_taken", "status", "outcome",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values()) + [concern_id]
            cursor.execute(
                f"UPDATE safeguarding_concerns SET {set_clause} WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated safeguarding concern: %s", concern_id)
            return cursor.rowcount > 0
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise SafeguardingError(f"Failed to update concern: {e}") from e
        finally:
            conn.close()

    def close_concern(self, concern_id, outcome):
        """Close a safeguarding concern with an outcome."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE safeguarding_concerns
                SET status = 'Closed', outcome = ?
                WHERE id = ?""",
                (outcome, concern_id),
            )
            conn.commit()
            logger.info("Closed safeguarding concern: %s", concern_id)
            return cursor.rowcount > 0
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise SafeguardingError(f"Failed to close concern: {e}") from e
        finally:
            conn.close()

    def get_open_count(self):
        """Get count of open safeguarding concerns."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM safeguarding_concerns WHERE status = 'Open'"
            )
            return cursor.fetchone()[0]
        finally:
            conn.close()
