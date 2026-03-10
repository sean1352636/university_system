"""First aid incident management service."""

from datetime import datetime, date

from education_system.college_system.core.exceptions import FirstAidError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)

_SEVERITIES = ("minor", "moderate", "severe", "emergency")
_STATUSES = ("open", "treated", "referred", "closed")


class FirstAidService:
    """Service for managing first aid incidents."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def report_incident(self, reported_by: int, student_id: int | None = None,
                        description: str = "", location: str | None = None,
                        severity: str = "minor",
                        incident_time: str | None = None) -> dict:
        """Report a new first aid incident."""
        if not description or not description.strip():
            raise FirstAidError("Description is required.")
        if severity not in _SEVERITIES:
            raise FirstAidError(f"Severity must be one of: {', '.join(_SEVERITIES)}")

        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO first_aid_incidents
                   (reported_by, student_id, description, location, severity, incident_time)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (reported_by, student_id, description.strip(), location,
                 severity, incident_time),
            )
            conn.commit()
            incident_id = cursor.lastrowid
            logger.info("First aid incident reported: id=%d severity=%s",
                        incident_id, severity)
            return self.get_incident(incident_id)
        except FirstAidError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FirstAidError(f"Failed to report incident: {e}") from e
        finally:
            conn.close()

    def list_incidents(self, status: str | None = None,
                       limit: int = 50) -> list[dict]:
        """List all incidents, newest first."""
        conn = self._conn()
        try:
            sql = """SELECT fi.*, s.student_id as sid, s.first_name, s.last_name
                     FROM first_aid_incidents fi
                     LEFT JOIN students s ON fi.student_id = s.id"""
            params: list = []
            if status:
                sql += " WHERE fi.status = ?"
                params.append(status)
            sql += " ORDER BY fi.created_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_incident(self, incident_id: int) -> dict:
        """Get a single incident with student name."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT fi.*, s.student_id as sid, s.first_name, s.last_name
                   FROM first_aid_incidents fi
                   LEFT JOIN students s ON fi.student_id = s.id
                   WHERE fi.id = ?""",
                (incident_id,),
            ).fetchone()
            if not row:
                raise FirstAidError("Incident not found.")
            return dict(row)
        finally:
            conn.close()

    def update_incident(self, incident_id: int, **kwargs) -> dict:
        """Update an incident (treatment, status, treated_by, parent_notified, notes)."""
        allowed = {"treatment", "status", "treated_by", "parent_notified", "notes"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            raise FirstAidError("No valid fields to update.")
        if "status" in updates and updates["status"] not in _STATUSES:
            raise FirstAidError(f"Status must be one of: {', '.join(_STATUSES)}")

        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values())
            vals.extend([datetime.now().isoformat(), incident_id])
            conn.execute(
                f"UPDATE first_aid_incidents SET {sets}, updated_at = ? WHERE id = ?",
                vals,
            )
            conn.commit()
            logger.info("First aid incident updated: id=%d", incident_id)
            return self.get_incident(incident_id)
        except FirstAidError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FirstAidError(f"Failed to update incident: {e}") from e
        finally:
            conn.close()

    def get_student_incidents(self, student_id: int) -> list[dict]:
        """Get all incidents for a student."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT fi.*, s.student_id as sid, s.first_name, s.last_name
                   FROM first_aid_incidents fi
                   LEFT JOIN students s ON fi.student_id = s.id
                   WHERE fi.student_id = ?
                   ORDER BY fi.created_at DESC""",
                (student_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
