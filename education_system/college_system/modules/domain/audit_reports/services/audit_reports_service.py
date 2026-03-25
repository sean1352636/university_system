"""Service for managing audit & compliance reports."""

from datetime import datetime
from education_system.college_system.core.exceptions import AuditReportError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier
import logging

logger = logging.getLogger(__name__)


class AuditReportService:
    """Audit & Compliance Reports management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_report(self, **kwargs) -> dict:
        """Create a new report."""
        if not kwargs.get("report_type"):
            raise ValidationError("report_type is required.")
        if not kwargs.get("title"):
            raise ValidationError("title is required.")
        conn = self._conn()
        try:
            # Build INSERT with only non-None values so DB defaults apply
            fields = {k: v for k, v in {
                'report_type': kwargs.get('report_type'),
                'title': kwargs.get('title'),
                'generated_by': kwargs.get('generated_by'),
                'result_summary': kwargs.get('result_summary'),
                'findings': kwargs.get('findings'),
                'status': kwargs.get('status'),
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO audit_report_records ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM audit_report_records WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Report created: id=%d", row["id"])
            return dict(row)
        except AuditReportError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AuditReportError(f"Failed to create report: {e}") from e
        finally:
            conn.close()

    def get_report(self, pk: int) -> dict | None:
        """Get report by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM audit_report_records WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_reports(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List reports with optional filters."""
        sql = "SELECT * FROM audit_report_records WHERE 1=1"
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

    def update_report(self, pk: int, **kwargs) -> dict:
        """Update report record."""
        allowed = {"report_type", "title", "generated_by", "result_summary", "findings", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE audit_report_records SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Report updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM audit_report_records WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_report(self, pk: int) -> bool:
        """Delete report."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM audit_report_records WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise AuditReportError("Report not found.")
            conn.execute("DELETE FROM audit_report_records WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Report deleted: pk=%d", pk)
            return True
        except AuditReportError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AuditReportError(f"Failed to delete report: {e}") from e
        finally:
            conn.close()

    def count_reports(self, **filters) -> int:
        """Count reports."""
        sql = "SELECT COUNT(*) as cnt FROM audit_report_records WHERE 1=1"
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
