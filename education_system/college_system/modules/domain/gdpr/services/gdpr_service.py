"""Service for managing gdpr & data protection."""

from datetime import datetime
from education_system.college_system.core.exceptions import GDPRError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
import logging

logger = logging.getLogger(__name__)


class GDPRService:
    """GDPR & Data Protection management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_subject(self, **kwargs) -> dict:
        """Create a new subject."""
        if not kwargs.get("user_id"):
            raise ValidationError("user_id is required.")
        conn = self._conn()
        try:
            # Build INSERT with only non-None values so DB defaults apply
            fields = {k: v for k, v in {
                'user_id': kwargs.get('user_id'),
                'consent_marketing': kwargs.get('consent_marketing'),
                'consent_analytics': kwargs.get('consent_analytics'),
                'consent_third_party': kwargs.get('consent_third_party'),
                'erasure_requested': kwargs.get('erasure_requested'),
                'erasure_completed_at': kwargs.get('erasure_completed_at'),
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO data_subjects ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM data_subjects WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Subject created: id=%d", row["id"])
            return dict(row)
        except GDPRError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise GDPRError(f"Failed to create subject: {e}") from e
        finally:
            conn.close()

    def get_subject(self, pk: int) -> dict | None:
        """Get subject by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM data_subjects WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_subjects(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List subjects with optional filters."""
        sql = "SELECT * FROM data_subjects WHERE 1=1"
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

    def update_subject(self, pk: int, **kwargs) -> dict:
        """Update subject record."""
        # Iterate over a literal allowed-column tuple so CodeQL recognises
        # the column names as untainted (py/sql-injection).
        set_parts: list[str] = []
        params: list = []
        for col in ("user_id", "consent_marketing", "consent_analytics", "consent_third_party", "erasure_requested", "erasure_completed_at"):
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
            conn.execute(f"UPDATE data_subjects SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Subject updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM data_subjects WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_subject(self, pk: int) -> bool:
        """Delete subject."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM data_subjects WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise GDPRError("Subject not found.")
            conn.execute("DELETE FROM data_subjects WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Subject deleted: pk=%d", pk)
            return True
        except GDPRError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise GDPRError(f"Failed to delete subject: {e}") from e
        finally:
            conn.close()

    def count_subjects(self, **filters) -> int:
        """Count subjects."""
        sql = "SELECT COUNT(*) as cnt FROM data_subjects WHERE 1=1"
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
