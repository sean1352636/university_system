"""Safeguarding service."""

import logging
from education_system.secondary_school.core.exceptions import SafeguardingError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

CONCERN_TYPES = ("welfare", "child_protection", "neglect", "physical", "emotional",
                 "sexual", "radicalisation", "online_safety", "peer_on_peer", "other")
SEVERITY_LEVELS = ("low", "medium", "high", "critical")


class SafeguardingService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def log_concern(self, student_id, reported_by, concern_type="welfare",
                    severity="low", description="", action_taken=None,
                    referred_to=None, incident_date=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO safeguarding_concerns
                   (student_id, reported_by, concern_type, severity, description,
                    action_taken, referred_to, incident_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(?, date('now')))""",
                (student_id, reported_by, concern_type, severity, description,
                 action_taken, referred_to, incident_date))
            conn.commit()
            row = conn.execute("SELECT * FROM safeguarding_concerns WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise SafeguardingError(f"Failed to log concern: {e}") from e
        finally:
            conn.close()

    def list_concerns(self, is_resolved=None):
        conn = self._conn()
        try:
            sql = """SELECT sc.*, s.student_id as sid, s.first_name, s.last_name, s.year_group
                     FROM safeguarding_concerns sc JOIN students s ON sc.student_id = s.id WHERE 1=1"""
            params = []
            if is_resolved is not None:
                sql += " AND sc.is_resolved = ?"
                params.append(int(is_resolved))
            sql += " ORDER BY sc.incident_date DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def resolve_concern(self, concern_id, outcome=None):
        conn = self._conn()
        try:
            conn.execute("UPDATE safeguarding_concerns SET is_resolved = 1, outcome = ?, updated_at = datetime('now') WHERE id = ?",
                         (outcome, concern_id))
            conn.commit()
        finally:
            conn.close()

    def update_concern(self, concern_id, **kwargs):
        allowed = {"action_taken", "referred_to", "outcome", "severity"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        conn = self._conn()
        try:
            s = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE safeguarding_concerns SET {s}, updated_at = datetime('now') WHERE id = ?",
                         (*updates.values(), concern_id))
            conn.commit()
        finally:
            conn.close()

    def delete_concern(self, concern_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM safeguarding_concerns WHERE id = ?", (concern_id,))
            conn.commit()
        finally:
            conn.close()
