"""Incident Log service."""

import logging
from education_system.secondary_school.core.exceptions import IncidentError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

INCIDENT_TYPES = ("accident", "near_miss", "fire", "medical_emergency", "security_breach",
                  "property_damage", "environmental", "violence", "intruder", "other")
SEVERITY_LEVELS = ("minor", "moderate", "serious", "major", "critical")


class IncidentService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def log_incident(self, description, incident_type="accident", severity="minor",
                     location=None, date=None, time=None, people_involved=None,
                     witnesses=None, action_taken=None, reported_by=None,
                     reported_to=None, riddor=False):
        conn = self._conn()
        try:
            sql = """INSERT INTO incidents
                     (incident_type, severity, location, description, people_involved,
                      witnesses, action_taken, reported_by, reported_to,
                      riddor_reportable"""
            params = [incident_type, severity, location, description, people_involved,
                      witnesses, action_taken, reported_by, reported_to, int(riddor)]
            if date:
                sql += ", date"
                params.append(date)
            if time:
                sql += ", time"
                params.append(time)
            placeholders = ", ".join(["?"] * len(params))
            sql += f") VALUES ({placeholders})"
            cursor = conn.execute(sql, params)
            conn.commit()
            return dict(conn.execute("SELECT * FROM incidents WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise IncidentError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_incidents(self, incident_type=None, severity=None, status=None):
        conn = self._conn()
        try:
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
            sql += " ORDER BY date DESC, created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def close_incident(self, incident_id, investigation_notes=None):
        conn = self._conn()
        try:
            if investigation_notes:
                conn.execute("UPDATE incidents SET status = 'closed', investigation_notes = ?, updated_at = datetime('now') WHERE id = ?",
                             (investigation_notes, incident_id))
            else:
                conn.execute("UPDATE incidents SET status = 'closed', updated_at = datetime('now') WHERE id = ?",
                             (incident_id,))
            conn.commit()
        finally:
            conn.close()

    def mark_follow_up_done(self, incident_id):
        conn = self._conn()
        try:
            conn.execute("UPDATE incidents SET follow_up_done = 1, updated_at = datetime('now') WHERE id = ?",
                         (incident_id,))
            conn.commit()
        finally:
            conn.close()

    def delete_incident(self, incident_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM incidents WHERE id = ?", (incident_id,))
            conn.commit()
        finally:
            conn.close()
