"""Incident service for the Primary School Management System."""

import logging

from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import IncidentError
from education_system.primary_school.core.sql_safety import validate_identifier  # nosec B608
import traceback

logger = logging.getLogger(__name__)


class IncidentService:
    """CRUD operations for school incidents."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_incident(self, incident_type, description, reported_by,
                        location=None, severity="Minor", pupil_ids=None,
                        staff_ids=None, incident_date=None,
                        incident_time=None, action_taken=None,
                        parent_notified=0, first_aid_given=0):
        """Create a new incident record."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO incidents (
                    incident_type, description, reported_by, location,
                    severity, pupil_ids, staff_ids, incident_date,
                    incident_time, action_taken, parent_notified,
                    first_aid_given, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(?, date('now')),
                          COALESCE(?, time('now')), ?, ?, ?, 'Open',
                          datetime('now'))""",
                (incident_type, description, reported_by, location,
                 severity, pupil_ids, staff_ids, incident_date,
                 incident_time, action_taken, parent_notified,
                 first_aid_given),
            )
            conn.commit()
            incident_id = cursor.lastrowid
            logger.info("Created incident %s: %s (severity=%s)",
                        incident_id, incident_type, severity)
            return {"id": incident_id, "incident_type": incident_type,
                    "severity": severity}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise IncidentError(
                f"Failed to create incident: {e}") from e
        finally:
            conn.close()

    def get_incident(self, incident_id):
        """Get a single incident by ID."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM incidents WHERE id = ?", (incident_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_incidents(self, incident_type=None, severity=None,
                       status="Open", date_from=None, date_to=None):
        """List incidents with optional filters."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM incidents WHERE 1=1"
            params = []
            if incident_type:
                sql += " AND incident_type = ?"
                params.append(incident_type)
            if severity:
                sql += " AND severity = ?"
                params.append(severity)
            if status:
                sql += " AND status = ?"
                params.append(status)
            if date_from:
                sql += " AND incident_date >= ?"
                params.append(date_from)
            if date_to:
                sql += " AND incident_date <= ?"
                params.append(date_to)
            sql += " ORDER BY incident_date DESC, incident_time DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_incident(self, incident_id, **kwargs):
        """Update an incident record."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "incident_type", "description", "location", "severity",
                "pupil_ids", "staff_ids", "action_taken",
                "parent_notified", "first_aid_given", "status",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(incident_id)
            cursor.execute(
                f"UPDATE incidents SET {set_clause}, "
                "updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated incident %s", incident_id)
            return self.get_incident(incident_id)
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise IncidentError(
                f"Failed to update incident: {e}") from e
        finally:
            conn.close()

    def close_incident(self, incident_id, action_taken):
        """Close an incident with a final action taken note."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE incidents
                   SET status = 'Closed', action_taken = ?,
                       closed_at = datetime('now'),
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (action_taken, incident_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                raise IncidentError(
                    f"Incident {incident_id} not found")
            logger.info("Closed incident %s", incident_id)
            return self.get_incident(incident_id)
        except IncidentError:
            raise
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise IncidentError(
                f"Failed to close incident: {e}") from e
        finally:
            conn.close()
