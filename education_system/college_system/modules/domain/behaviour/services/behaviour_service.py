"""Behaviour service for managing conduct records."""

from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.exceptions import BehaviourError


class BehaviourService:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def record_incident(self, student_id: int, recorded_by: int,
                         type: str = "concern", description: str = None,
                         category: str = "other", points: int = 0,
                         action_taken: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO behaviour_records
                   (student_id, recorded_by, type, description, category, points, action_taken)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (student_id, recorded_by, type, description, category, points, action_taken),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM behaviour_records WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise BehaviourError(f"Failed to record incident: {e}")
        finally:
            conn.close()

    def list_records(self, student_id: int = None, type: str = None,
                      limit: int = 100) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT br.*, s.first_name, s.last_name
                       FROM behaviour_records br
                       LEFT JOIN students s ON br.student_id = s.id WHERE 1=1"""
            params = []
            if student_id:
                query += " AND br.student_id = ?"
                params.append(student_id)
            if type:
                query += " AND br.type = ?"
                params.append(type)
            query += " ORDER BY br.incident_date DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_record(self, record_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT br.*, s.first_name, s.last_name
                   FROM behaviour_records br
                   LEFT JOIN students s ON br.student_id = s.id
                   WHERE br.id = ?""",
                (record_id,),
            ).fetchone()
            if not row:
                raise BehaviourError(f"Record {record_id} not found")
            return dict(row)
        finally:
            conn.close()

    def update_record(self, record_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"action_taken", "parent_notified", "status",
                        "category", "points", "description"}
            parts, params = [], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if not parts:
                raise BehaviourError("No valid fields to update")
            params.append(record_id)
            conn.execute(
                f"UPDATE behaviour_records SET {', '.join(parts)} WHERE id = ?", params
            )
            conn.commit()
            return self.get_record(record_id)
        except BehaviourError:
            raise
        except Exception as e:
            raise BehaviourError(f"Failed to update record: {e}")
        finally:
            conn.close()

    def get_student_records(self, student_id: int) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM behaviour_records WHERE student_id = ? ORDER BY incident_date DESC",
                (student_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def count_by_type(self, student_id: int) -> dict:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT type, COUNT(*) as count
                   FROM behaviour_records WHERE student_id = ?
                   GROUP BY type""",
                (student_id,),
            ).fetchall()
            return {r["type"]: r["count"] for r in rows}
        finally:
            conn.close()
