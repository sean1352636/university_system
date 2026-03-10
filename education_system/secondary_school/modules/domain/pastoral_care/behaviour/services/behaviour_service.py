"""Behaviour management service."""

from datetime import datetime
import logging

from education_system.secondary_school.core.exceptions import BehaviourError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class BehaviourService:
    """Service for managing behaviour records (merits, sanctions, incidents)."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def add_record(self, student_id: int, record_type: str, category: str,
                   description: str | None = None, points: int = 0,
                   sanction: str | None = None, recorded_by: str | None = None,
                   incident_date: str | None = None) -> dict:
        """Add a behaviour record (positive or negative)."""
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO behaviour_records
                   (student_id, type, category, description, points,
                    sanction, recorded_by, incident_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, record_type, category, description, points,
                 sanction, recorded_by,
                 incident_date or datetime.now().strftime("%Y-%m-%d")),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM behaviour_records WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise BehaviourError(f"Failed to add behaviour record: {e}") from e
        finally:
            conn.close()

    def get_student_records(self, student_id: int, record_type: str | None = None,
                            limit: int = 100) -> list[dict]:
        sql = "SELECT * FROM behaviour_records WHERE student_id = ?"
        params: list = [student_id]

        if record_type:
            sql += " AND type = ?"
            params.append(record_type)

        sql += " ORDER BY incident_date DESC, created_at DESC LIMIT ?"
        params.append(limit)

        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_student_points(self, student_id: int) -> dict:
        """Get total positive and negative points for a student."""
        conn = self._conn()
        try:
            pos = conn.execute(
                "SELECT COALESCE(SUM(points), 0) as pts FROM behaviour_records WHERE student_id = ? AND type = 'positive'",
                (student_id,),
            ).fetchone()["pts"]

            neg = conn.execute(
                "SELECT COALESCE(SUM(points), 0) as pts FROM behaviour_records WHERE student_id = ? AND type = 'negative'",
                (student_id,),
            ).fetchone()["pts"]

            return {"positive": pos, "negative": neg, "net": pos - neg}
        finally:
            conn.close()

    def resolve_record(self, record_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE behaviour_records SET resolved = 1 WHERE id = ?", (record_id,)
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def mark_parent_notified(self, record_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE behaviour_records SET parent_notified = 1 WHERE id = ?", (record_id,)
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def get_recent_incidents(self, days: int = 7, limit: int = 50) -> list[dict]:
        """Get recent negative behaviour incidents across the school."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT b.*, s.student_id as sid, s.first_name, s.last_name,
                          s.year_group, s.form_group
                   FROM behaviour_records b JOIN students s ON b.student_id = s.id
                   WHERE b.type = 'negative'
                     AND b.incident_date >= date('now', ?)
                   ORDER BY b.incident_date DESC LIMIT ?""",
                (f"-{days} days", limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
