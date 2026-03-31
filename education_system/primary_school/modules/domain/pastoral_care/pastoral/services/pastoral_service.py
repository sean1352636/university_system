"""Pastoral notes service for the Primary School Management System."""

import logging

from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import PastoralError
from education_system.primary_school.core.sql_safety import validate_identifier  # nosec B608
import traceback

logger = logging.getLogger(__name__)


class PastoralService:
    """CRUD operations for pastoral notes."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_note(self, pupil_id, note_type, subject, details,
                    recorded_by=None, follow_up_required=0,
                    follow_up_date=None):
        """Create a pastoral note."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO pastoral_notes (
                    pupil_id, note_type, subject, details,
                    recorded_by, follow_up_required, follow_up_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    pupil_id, note_type, subject, details,
                    recorded_by, follow_up_required, follow_up_date,
                ),
            )
            conn.commit()
            note_id = cursor.lastrowid
            logger.info(
                "Created pastoral note for pupil %s (id=%s, type=%s)",
                pupil_id, note_id, note_type,
            )
            return note_id
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise PastoralError(f"Failed to create pastoral note: {e}") from e
        finally:
            conn.close()

    def get_notes(self, pupil_id=None, note_type=None, status=None):
        """Retrieve pastoral notes with optional filters."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM pastoral_notes WHERE 1=1"
            params = []
            if pupil_id:
                sql += " AND pupil_id = ?"
                params.append(pupil_id)
            if note_type:
                sql += " AND note_type = ?"
                params.append(note_type)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY created_at DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_note(self, note_id, **kwargs):
        """Update a pastoral note."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "note_type", "subject", "details", "recorded_by",
                "follow_up_required", "follow_up_date", "status",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values()) + [note_id]
            cursor.execute(
                f"UPDATE pastoral_notes SET {set_clause} WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated pastoral note: %s", note_id)
            return cursor.rowcount > 0
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise PastoralError(f"Failed to update pastoral note: {e}") from e
        finally:
            conn.close()

    def delete_note(self, note_id):
        """Delete a pastoral note."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM pastoral_notes WHERE id = ?", (note_id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted pastoral note: %s", note_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise PastoralError(f"Failed to delete pastoral note: {e}") from e
        finally:
            conn.close()
