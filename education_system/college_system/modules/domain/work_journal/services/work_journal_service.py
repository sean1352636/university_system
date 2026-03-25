"""Service for managing work journal."""

from datetime import datetime
from education_system.college_system.core.exceptions import WorkJournalError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier
import logging

logger = logging.getLogger(__name__)


class WorkJournalService:
    """Work Journal management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_placement(self, **kwargs) -> dict:
        """Create a new placement."""
        if not kwargs.get("student_id"):
            raise ValidationError("student_id is required.")
        if not kwargs.get("employer_name"):
            raise ValidationError("employer_name is required.")
        if not kwargs.get("start_date"):
            raise ValidationError("start_date is required.")
        conn = self._conn()
        try:
            # Build INSERT with only non-None values so DB defaults apply
            fields = {k: v for k, v in {
                'student_id': kwargs.get('student_id'),
                'employer_name': kwargs.get('employer_name'),
                'role_title': kwargs.get('role_title'),
                'start_date': kwargs.get('start_date'),
                'end_date': kwargs.get('end_date'),
                'supervisor_name': kwargs.get('supervisor_name'),
                'dbs_confirmed': kwargs.get('dbs_confirmed'),
                'risk_assessment': kwargs.get('risk_assessment'),
                'status': kwargs.get('status'),
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO work_placements ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM work_placements WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Placement created: id=%d", row["id"])
            return dict(row)
        except WorkJournalError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise WorkJournalError(f"Failed to create placement: {e}") from e
        finally:
            conn.close()

    def get_placement(self, pk: int) -> dict | None:
        """Get placement by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM work_placements WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_placements(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List placements with optional filters."""
        sql = "SELECT * FROM work_placements WHERE 1=1"
        params: list = []
        for key, val in filters.items():
            if val is not None:
                sql += f" AND {validate_identifier(key)} = ?"
                params.append(val)
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_placement(self, pk: int, **kwargs) -> dict:
        """Update placement record."""
        allowed = {"student_id", "employer_name", "role_title", "start_date", "end_date", "supervisor_name", "dbs_confirmed", "risk_assessment", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE work_placements SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Placement updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM work_placements WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_placement(self, pk: int) -> bool:
        """Delete placement."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM work_placements WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise WorkJournalError("Placement not found.")
            conn.execute("DELETE FROM work_placements WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Placement deleted: pk=%d", pk)
            return True
        except WorkJournalError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise WorkJournalError(f"Failed to delete placement: {e}") from e
        finally:
            conn.close()

    def count_placements(self, **filters) -> int:
        """Count placements."""
        sql = "SELECT COUNT(*) as cnt FROM work_placements WHERE 1=1"
        params: list = []
        for key, val in filters.items():
            if val is not None:
                sql += f" AND {validate_identifier(key)} = ?"
                params.append(val)
        conn = self._conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row["cnt"]
        finally:
            conn.close()
