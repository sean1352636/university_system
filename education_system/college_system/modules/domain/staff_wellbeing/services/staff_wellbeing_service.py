"""Service for managing staff wellbeing."""

from datetime import datetime
from education_system.college_system.core.exceptions import StaffWellbeingError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
import logging

logger = logging.getLogger(__name__)


class StaffWellbeingService:
    """Staff Wellbeing management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_checkin(self, **kwargs) -> dict:
        """Create a new checkin."""
        if not kwargs.get("staff_id"):
            raise ValidationError("staff_id is required.")
        conn = self._conn()
        try:
            # Build INSERT with only non-None values so DB defaults apply
            fields = {k: v for k, v in {
                'staff_id': kwargs.get('staff_id'),
                'checkin_date': kwargs.get('checkin_date'),
                'mood_rating': kwargs.get('mood_rating'),
                'workload_rating': kwargs.get('workload_rating'),
                'stress_level': kwargs.get('stress_level'),
                'notes': kwargs.get('notes'),
                'confidential': kwargs.get('confidential'),
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO wellbeing_checkins ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM wellbeing_checkins WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Checkin created: id=%d", row["id"])
            return dict(row)
        except StaffWellbeingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StaffWellbeingError(f"Failed to create checkin: {e}") from e
        finally:
            conn.close()

    def get_checkin(self, pk: int) -> dict | None:
        """Get checkin by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM wellbeing_checkins WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_checkins(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List checkins with optional filters."""
        sql = "SELECT * FROM wellbeing_checkins WHERE 1=1"
        params: list = []
        for key, val in filters.items():
            if val is not None:
                sql += f" AND {validate_identifier(key)} = ?"  # nosec B608
                params.append(val)
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_checkin(self, pk: int, **kwargs) -> dict:
        """Update checkin record."""
        # Iterate over a literal allowed-column tuple so CodeQL recognises
        # the column names as untainted (py/sql-injection).
        set_parts: list[str] = []
        params: list = []
        for col in ("staff_id", "checkin_date", "mood_rating", "workload_rating", "stress_level", "notes", "confidential"):
            val = kwargs.get(col)
            if val is not None:
                set_parts.append(f"{validate_identifier(col)} = ?")
                params.append(val)
        if not set_parts:
            raise ValidationError("No valid fields to update.")
        set_parts.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        params.append(pk)
        set_clause = ", ".join(set_parts)
        conn = self._conn()
        try:
            conn.execute(f"UPDATE wellbeing_checkins SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Checkin updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM wellbeing_checkins WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_checkin(self, pk: int) -> bool:
        """Delete checkin."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM wellbeing_checkins WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise StaffWellbeingError("Checkin not found.")
            conn.execute("DELETE FROM wellbeing_checkins WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Checkin deleted: pk=%d", pk)
            return True
        except StaffWellbeingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StaffWellbeingError(f"Failed to delete checkin: {e}") from e
        finally:
            conn.close()

    def count_checkins(self, **filters) -> int:
        """Count checkins."""
        sql = "SELECT COUNT(*) as cnt FROM wellbeing_checkins WHERE 1=1"
        params: list = []
        for key, val in filters.items():
            if val is not None:
                sql += f" AND {validate_identifier(key)} = ?"  # nosec B608
                params.append(val)
        conn = self._conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row["cnt"]
        finally:
            conn.close()
