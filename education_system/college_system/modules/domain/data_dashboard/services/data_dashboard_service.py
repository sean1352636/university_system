"""Service for managing data dashboard."""

from datetime import datetime
from education_system.college_system.core.exceptions import DataDashboardError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
import logging

logger = logging.getLogger(__name__)


class DataDashboardService:
    """Data Dashboard management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_widget(self, **kwargs) -> dict:
        """Create a new widget."""
        if not kwargs.get("user_id"):
            raise ValidationError("user_id is required.")
        if not kwargs.get("widget_type"):
            raise ValidationError("widget_type is required.")
        conn = self._conn()
        try:
            # Build INSERT with only non-None values so DB defaults apply
            # Iterate over a literal column tuple so user-supplied keys
            # never flow into the SQL identifier positions (py/sql-injection).
            _insert_cols: list[str] = []
            _insert_phs: list[str] = []
            _insert_vals: list = []
            for col in ('user_id', 'widget_type', 'config', 'display_order', 'is_visible'):
                val = kwargs.get(col)
                if val is not None:
                    _insert_cols.append(col)
                    _insert_phs.append('?')
                    _insert_vals.append(val)
            cols_sql = ', '.join(_insert_cols)
            ph_sql = ', '.join(_insert_phs)
            conn.execute(
                f"INSERT INTO dashboard_widgets ({cols_sql}) VALUES ({ph_sql})",
                _insert_vals,
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM dashboard_widgets WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Widget created: id=%d", row["id"])
            return dict(row)
        except DataDashboardError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise DataDashboardError(f"Failed to create widget: {e}") from e
        finally:
            conn.close()

    def get_widget(self, pk: int) -> dict | None:
        """Get widget by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM dashboard_widgets WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_widgets(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List widgets with optional filters."""
        sql = "SELECT * FROM dashboard_widgets WHERE 1=1"
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

    def update_widget(self, pk: int, **kwargs) -> dict:
        """Update widget record."""
        # Iterate over a literal allowed-column tuple so CodeQL recognises
        # the column names as untainted (py/sql-injection).
        set_parts: list[str] = []
        params: list = []
        for col in ("user_id", "widget_type", "config", "display_order", "is_visible"):
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
            conn.execute(f"UPDATE dashboard_widgets SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Widget updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM dashboard_widgets WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_widget(self, pk: int) -> bool:
        """Delete widget."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM dashboard_widgets WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise DataDashboardError("Widget not found.")
            conn.execute("DELETE FROM dashboard_widgets WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Widget deleted: pk=%d", pk)
            return True
        except DataDashboardError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise DataDashboardError(f"Failed to delete widget: {e}") from e
        finally:
            conn.close()

    def count_widgets(self, **filters) -> int:
        """Count widgets."""
        sql = "SELECT COUNT(*) as cnt FROM dashboard_widgets WHERE 1=1"
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
