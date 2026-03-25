"""Communication log service for the Primary School Management System."""

import logging
from datetime import date

from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import CommunicationLogError
from education_system.primary_school.core.sql_safety import validate_identifier
import traceback

logger = logging.getLogger(__name__)


class CommunicationLogService:
    """CRUD operations for communication log entries."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_entry(self, pupil_id, contact_type, contact_with=None,
                     subject=None, details=None, outcome=None,
                     follow_up_required=0, follow_up_date=None,
                     recorded_by=None):
        """Create a new communication log entry."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO communication_log (
                    pupil_id, contact_type, contact_with, subject,
                    details, outcome, follow_up_required, follow_up_date,
                    recorded_by, status, contact_date, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open',
                          date('now'), datetime('now'))""",
                (pupil_id, contact_type, contact_with, subject,
                 details, outcome, follow_up_required, follow_up_date,
                 recorded_by),
            )
            conn.commit()
            entry_id = cursor.lastrowid
            logger.info("Created communication log entry %s for pupil %s: %s",
                        entry_id, pupil_id, contact_type)
            return {"id": entry_id, "pupil_id": pupil_id,
                    "contact_type": contact_type}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise CommunicationLogError(
                f"Failed to create communication log entry: {e}") from e
        finally:
            conn.close()

    def get_entries(self, pupil_id=None, contact_type=None,
                    date_from=None, date_to=None):
        """Get communication log entries with optional filters."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM communication_log WHERE 1=1"
            params = []
            if pupil_id:
                sql += " AND pupil_id = ?"
                params.append(pupil_id)
            if contact_type:
                sql += " AND contact_type = ?"
                params.append(contact_type)
            if date_from:
                sql += " AND contact_date >= ?"
                params.append(date_from)
            if date_to:
                sql += " AND contact_date <= ?"
                params.append(date_to)
            sql += " ORDER BY contact_date DESC, created_at DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_entry(self, entry_id, **kwargs):
        """Update a communication log entry."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "contact_type", "contact_with", "subject", "details",
                "outcome", "follow_up_required", "follow_up_date",
                "status",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(entry_id)
            cursor.execute(
                f"UPDATE communication_log SET {set_clause}, "
                "updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated communication log entry %s", entry_id)
            return cursor.rowcount > 0
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise CommunicationLogError(
                f"Failed to update communication log entry: {e}") from e
        finally:
            conn.close()

    def delete_entry(self, entry_id):
        """Delete a communication log entry."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM communication_log WHERE id = ?", (entry_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info("Deleted communication log entry %s", entry_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise CommunicationLogError(
                f"Failed to delete communication log entry: {e}") from e
        finally:
            conn.close()

    def get_follow_ups_due(self):
        """Get entries where follow-up is required and due date is today or past."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            today = date.today().isoformat()
            cursor.execute(
                """SELECT * FROM communication_log
                   WHERE follow_up_required = 1
                     AND follow_up_date <= ?
                     AND status != 'Closed'
                   ORDER BY follow_up_date""",
                (today,),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
