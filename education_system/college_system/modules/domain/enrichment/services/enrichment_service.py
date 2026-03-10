"""Service for managing enrichment."""

from datetime import datetime
from education_system.college_system.core.exceptions import EnrichmentError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
import logging

logger = logging.getLogger(__name__)


class EnrichmentService:
    """Enrichment management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_activity(self, **kwargs) -> dict:
        """Create a new activity."""
        if not kwargs.get("name"):
            raise ValidationError("name is required.")
        if not kwargs.get("activity_type"):
            raise ValidationError("activity_type is required.")
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO enrichment_activities (name, activity_type, lead_staff_id, day_of_week, time_slot, location, capacity, description, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (kwargs.get('name'), kwargs.get('activity_type'), kwargs.get('lead_staff_id'), kwargs.get('day_of_week'), kwargs.get('time_slot'), kwargs.get('location'), kwargs.get('capacity'), kwargs.get('description'), kwargs.get('status'),),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM enrichment_activities WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Activity created: id=%d", row["id"])
            return dict(row)
        except EnrichmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise EnrichmentError(f"Failed to create activity: {e}") from e
        finally:
            conn.close()

    def get_activity(self, pk: int) -> dict | None:
        """Get activity by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM enrichment_activities WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_activities(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List activities with optional filters."""
        sql = "SELECT * FROM enrichment_activities WHERE 1=1"
        params: list = []
        for key, val in filters.items():
            if val is not None:
                sql += f" AND {key} = ?"
                params.append(val)
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_activity(self, pk: int, **kwargs) -> dict:
        """Update activity record."""
        allowed = {"name", "activity_type", "lead_staff_id", "day_of_week", "time_slot", "location", "capacity", "description", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE enrichment_activities SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Activity updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM enrichment_activities WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_activity(self, pk: int) -> bool:
        """Delete activity."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM enrichment_activities WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise EnrichmentError("Activity not found.")
            conn.execute("DELETE FROM enrichment_activities WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Activity deleted: pk=%d", pk)
            return True
        except EnrichmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise EnrichmentError(f"Failed to delete activity: {e}") from e
        finally:
            conn.close()

    def count_activities(self, **filters) -> int:
        """Count activities."""
        sql = "SELECT COUNT(*) as cnt FROM enrichment_activities WHERE 1=1"
        params: list = []
        for key, val in filters.items():
            if val is not None:
                sql += f" AND {key} = ?"
                params.append(val)
        conn = self._conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row["cnt"]
        finally:
            conn.close()
