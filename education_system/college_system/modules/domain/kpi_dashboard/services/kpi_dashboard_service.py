"""Service for managing kpi dashboard."""

from datetime import datetime
from education_system.college_system.core.exceptions import KPIDashboardError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
import logging

logger = logging.getLogger(__name__)


class KPIDashboardService:
    """KPI Dashboard management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_target(self, **kwargs) -> dict:
        """Create a new target."""
        if not kwargs.get("academic_year"):
            raise ValidationError("academic_year is required.")
        if not kwargs.get("kpi_name"):
            raise ValidationError("kpi_name is required.")
        conn = self._conn()
        try:
            # Build INSERT with only non-None values so DB defaults apply
            fields = {k: v for k, v in {
                'academic_year': kwargs.get('academic_year'),
                'kpi_name': kwargs.get('kpi_name'),
                'kpi_category': kwargs.get('kpi_category'),
                'target_value': kwargs.get('target_value'),
                'actual_value': kwargs.get('actual_value'),
                'national_benchmark': kwargs.get('national_benchmark'),
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO kpi_targets ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM kpi_targets WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Target created: id=%d", row["id"])
            return dict(row)
        except KPIDashboardError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise KPIDashboardError(f"Failed to create target: {e}") from e
        finally:
            conn.close()

    def get_target(self, pk: int) -> dict | None:
        """Get target by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM kpi_targets WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_targets(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List targets with optional filters."""
        sql = "SELECT * FROM kpi_targets WHERE 1=1"
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

    def update_target(self, pk: int, **kwargs) -> dict:
        """Update target record."""
        allowed = {"academic_year", "kpi_name", "kpi_category", "target_value", "actual_value", "national_benchmark"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE kpi_targets SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Target updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM kpi_targets WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_target(self, pk: int) -> bool:
        """Delete target."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM kpi_targets WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise KPIDashboardError("Target not found.")
            conn.execute("DELETE FROM kpi_targets WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Target deleted: pk=%d", pk)
            return True
        except KPIDashboardError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise KPIDashboardError(f"Failed to delete target: {e}") from e
        finally:
            conn.close()

    def count_targets(self, **filters) -> int:
        """Count targets."""
        sql = "SELECT COUNT(*) as cnt FROM kpi_targets WHERE 1=1"
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
