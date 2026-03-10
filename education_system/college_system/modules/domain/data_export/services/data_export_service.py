"""Data Export & ILR service."""

from education_system.college_system.core.exceptions import DataExportError
from education_system.college_system.infrastructure.database.db import connect

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DataExportService:
    """Data Export & ILR service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ── Export Jobs ──────────────────────────────────────────────────

    def create_job(self, export_type: str, **kwargs) -> dict:
        """Create a new export job."""
        conn = self._conn()
        try:
            fields = {"export_type": export_type}
            for key in ("academic_year", "description", "parameters",
                        "file_path", "created_by", "status"):
                if key in kwargs and kwargs[key] is not None:
                    fields[key] = kwargs[key]
            if "parameters" in fields and isinstance(fields["parameters"], dict):
                fields["parameters"] = json.dumps(fields["parameters"])
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            vals = list(fields.values())
            conn.execute(
                f"INSERT INTO export_jobs ({cols}) VALUES ({placeholders})", vals
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM export_jobs WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise DataExportError(f"Failed to create export job: {e}") from e
        finally:
            conn.close()

    def list_jobs(self, export_type: str | None = None,
                  status: str | None = None,
                  academic_year: str | None = None) -> list[dict]:
        """List export jobs with optional filters."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM export_jobs WHERE 1=1"
            params: list = []
            if export_type is not None:
                sql += " AND export_type = ?"
                params.append(export_type)
            if status is not None:
                sql += " AND status = ?"
                params.append(status)
            if academic_year is not None:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            sql += " ORDER BY created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_job(self, job_id: int) -> dict | None:
        """Get a single export job by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM export_jobs WHERE id = ?", (job_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_job(self, job_id: int, **kwargs) -> dict:
        """Update an export job."""
        updates = {k: v for k, v in kwargs.items() if v is not None}
        if not updates:
            raise DataExportError("No valid fields to update.")
        if "parameters" in updates and isinstance(updates["parameters"], dict):
            updates["parameters"] = json.dumps(updates["parameters"])
        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [job_id]
            conn.execute(
                f"UPDATE export_jobs SET {sets} WHERE id = ?", vals
            )
            conn.commit()
            return self.get_job(job_id)
        except Exception as e:
            conn.rollback()
            raise DataExportError(f"Failed to update export job: {e}") from e
        finally:
            conn.close()

    def delete_job(self, job_id: int) -> bool:
        """Delete an export job."""
        conn = self._conn()
        try:
            conn.execute("DELETE FROM export_jobs WHERE id = ?", (job_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise DataExportError(f"Failed to delete export job: {e}") from e
        finally:
            conn.close()

    def start_job(self, job_id: int) -> dict:
        """Mark a job as running with started_at timestamp."""
        conn = self._conn()
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "UPDATE export_jobs SET status = 'running', started_at = ? WHERE id = ?",
                (now, job_id),
            )
            conn.commit()
            return self.get_job(job_id)
        except Exception as e:
            conn.rollback()
            raise DataExportError(f"Failed to start export job: {e}") from e
        finally:
            conn.close()

    def complete_job(self, job_id: int, record_count: int, file_path: str,
                     errors: int = 0, warnings: int = 0,
                     log: str | None = None) -> dict:
        """Mark a job as completed with results."""
        conn = self._conn()
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "UPDATE export_jobs SET status = 'completed', completed_at = ?, "
                "record_count = ?, file_path = ?, validation_errors = ?, "
                "validation_warnings = ?, validation_log = ? WHERE id = ?",
                (now, record_count, file_path, errors, warnings, log, job_id),
            )
            conn.commit()
            return self.get_job(job_id)
        except Exception as e:
            conn.rollback()
            raise DataExportError(f"Failed to complete export job: {e}") from e
        finally:
            conn.close()

    def fail_job(self, job_id: int, log: str | None = None) -> dict:
        """Mark a job as failed."""
        conn = self._conn()
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "UPDATE export_jobs SET status = 'failed', completed_at = ?, "
                "validation_log = ? WHERE id = ?",
                (now, log, job_id),
            )
            conn.commit()
            return self.get_job(job_id)
        except Exception as e:
            conn.rollback()
            raise DataExportError(f"Failed to mark export job as failed: {e}") from e
        finally:
            conn.close()

    # ── Export Templates ─────────────────────────────────────────────

    def create_template(self, template_name: str, export_type: str,
                        **kwargs) -> dict:
        """Create a new export template."""
        conn = self._conn()
        try:
            fields = {
                "template_name": template_name,
                "export_type": export_type,
            }
            for key in ("field_mapping", "filters", "is_active"):
                if key in kwargs and kwargs[key] is not None:
                    fields[key] = kwargs[key]
            if "field_mapping" in fields and isinstance(fields["field_mapping"], (dict, list)):
                fields["field_mapping"] = json.dumps(fields["field_mapping"])
            if "filters" in fields and isinstance(fields["filters"], (dict, list)):
                fields["filters"] = json.dumps(fields["filters"])
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            vals = list(fields.values())
            conn.execute(
                f"INSERT INTO export_templates ({cols}) VALUES ({placeholders})", vals
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM export_templates WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise DataExportError(f"Failed to create template: {e}") from e
        finally:
            conn.close()

    def list_templates(self, export_type: str | None = None,
                       active: bool | None = None) -> list[dict]:
        """List export templates with optional filters."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM export_templates WHERE 1=1"
            params: list = []
            if export_type is not None:
                sql += " AND export_type = ?"
                params.append(export_type)
            if active is not None:
                sql += " AND is_active = ?"
                params.append(1 if active else 0)
            sql += " ORDER BY created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_template(self, template_id: int) -> dict | None:
        """Get a single template by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM export_templates WHERE id = ?", (template_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_template(self, template_id: int, **kwargs) -> dict:
        """Update an export template."""
        updates = {k: v for k, v in kwargs.items() if v is not None}
        if not updates:
            raise DataExportError("No valid fields to update.")
        if "field_mapping" in updates and isinstance(updates["field_mapping"], (dict, list)):
            updates["field_mapping"] = json.dumps(updates["field_mapping"])
        if "filters" in updates and isinstance(updates["filters"], (dict, list)):
            updates["filters"] = json.dumps(updates["filters"])
        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [template_id]
            conn.execute(
                f"UPDATE export_templates SET {sets} WHERE id = ?", vals
            )
            conn.commit()
            return self.get_template(template_id)
        except Exception as e:
            conn.rollback()
            raise DataExportError(f"Failed to update template: {e}") from e
        finally:
            conn.close()

    def delete_template(self, template_id: int) -> bool:
        """Delete an export template."""
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM export_templates WHERE id = ?", (template_id,)
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise DataExportError(f"Failed to delete template: {e}") from e
        finally:
            conn.close()

    def toggle_active(self, template_id: int) -> dict:
        """Toggle a template's is_active flag."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE export_templates SET is_active = CASE WHEN is_active = 1 "
                "THEN 0 ELSE 1 END WHERE id = ?",
                (template_id,),
            )
            conn.commit()
            return self.get_template(template_id)
        except Exception as e:
            conn.rollback()
            raise DataExportError(f"Failed to toggle template active state: {e}") from e
        finally:
            conn.close()

    # ── Statistics ───────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get aggregate statistics for export jobs and templates."""
        conn = self._conn()
        try:
            total_jobs = conn.execute(
                "SELECT COUNT(*) FROM export_jobs"
            ).fetchone()[0]

            status_rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM export_jobs GROUP BY status"
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in status_rows}

            type_rows = conn.execute(
                "SELECT export_type, COUNT(*) as cnt FROM export_jobs GROUP BY export_type"
            ).fetchall()
            by_type = {r["export_type"]: r["cnt"] for r in type_rows}

            total_templates = conn.execute(
                "SELECT COUNT(*) FROM export_templates"
            ).fetchone()[0]

            active_templates = conn.execute(
                "SELECT COUNT(*) FROM export_templates WHERE is_active = 1"
            ).fetchone()[0]

            return {
                "total_jobs": total_jobs,
                "by_status": by_status,
                "by_type": by_type,
                "total_templates": total_templates,
                "active_templates": active_templates,
            }
        finally:
            conn.close()
