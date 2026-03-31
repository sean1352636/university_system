"""Service for managing emergency management."""

from datetime import datetime
from education_system.college_system.core.exceptions import EmergencyError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
import logging

logger = logging.getLogger(__name__)


class EmergencyService:
    """Emergency Management management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_drill(self, **kwargs) -> dict:
        """Create a new drill."""
        if not kwargs.get("drill_type"):
            raise ValidationError("drill_type is required.")
        if not kwargs.get("scheduled_date"):
            raise ValidationError("scheduled_date is required.")
        conn = self._conn()
        try:
            # Build INSERT with only non-None values so DB defaults apply
            fields = {k: v for k, v in {
                'drill_type': kwargs.get('drill_type'),
                'scheduled_date': kwargs.get('scheduled_date'),
                'actual_date': kwargs.get('actual_date'),
                'duration_minutes': kwargs.get('duration_minutes'),
                'outcome': kwargs.get('outcome'),
                'notes': kwargs.get('notes'),
                'status': kwargs.get('status'),
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO emergency_drills ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM emergency_drills WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Drill created: id=%d", row["id"])
            return dict(row)
        except EmergencyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise EmergencyError(f"Failed to create drill: {e}") from e
        finally:
            conn.close()

    def get_drill(self, pk: int) -> dict | None:
        """Get drill by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM emergency_drills WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_drills(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List drills with optional filters."""
        sql = "SELECT * FROM emergency_drills WHERE 1=1"
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

    def update_drill(self, pk: int, **kwargs) -> dict:
        """Update drill record."""
        allowed = {"drill_type", "scheduled_date", "actual_date", "duration_minutes", "outcome", "notes", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE emergency_drills SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Drill updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM emergency_drills WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_drill(self, pk: int) -> bool:
        """Delete drill."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM emergency_drills WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise EmergencyError("Drill not found.")
            conn.execute("DELETE FROM emergency_drills WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Drill deleted: pk=%d", pk)
            return True
        except EmergencyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise EmergencyError(f"Failed to delete drill: {e}") from e
        finally:
            conn.close()

    def count_drills(self, **filters) -> int:
        """Count drills."""
        sql = "SELECT COUNT(*) as cnt FROM emergency_drills WHERE 1=1"
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
