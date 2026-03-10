"""Transport service for managing student transport records."""

from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.exceptions import TransportError


class TransportService:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_record(self, student_id: int, transport_type: str = "bus_pass",
                       route: str = None, pass_number: str = None,
                       provider: str = None, eligible: int = 0,
                       start_date: str = None, end_date: str = None,
                       cost: float = 0, status: str = "active",
                       notes: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO transport_records
                   (student_id, transport_type, route, pass_number,
                    provider, eligible, start_date, end_date,
                    cost, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, transport_type, route, pass_number,
                 provider, eligible, start_date, end_date,
                 cost, status, notes),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM transport_records WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise TransportError(f"Failed to create transport record: {e}")
        finally:
            conn.close()

    def list_records(self, transport_type: str = None, status: str = None) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT tr.*, s.first_name, s.last_name FROM transport_records tr
                       LEFT JOIN students s ON tr.student_id = s.id WHERE 1=1"""
            params = []
            if transport_type:
                query += " AND tr.transport_type = ?"
                params.append(transport_type)
            if status:
                query += " AND tr.status = ?"
                params.append(status)
            query += " ORDER BY s.last_name"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_record(self, record_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT tr.*, s.first_name, s.last_name FROM transport_records tr
                   LEFT JOIN students s ON tr.student_id = s.id WHERE tr.id = ?""",
                (record_id,),
            ).fetchone()
            if not row:
                raise TransportError(f"Record {record_id} not found")
            return dict(row)
        finally:
            conn.close()

    def update_record(self, record_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"transport_type", "route", "pass_number", "provider",
                        "eligible", "start_date", "end_date", "cost",
                        "status", "notes"}
            parts, params = [], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if len(parts) < 1:
                raise TransportError("No valid fields to update")
            params.append(record_id)
            conn.execute(f"UPDATE transport_records SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            return self.get_record(record_id)
        except TransportError:
            raise
        except Exception as e:
            raise TransportError(f"Failed to update record: {e}")
        finally:
            conn.close()

    def get_student_transport(self, student_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM transport_records WHERE student_id = ? AND status = 'active'",
                (student_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def delete_record(self, record_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM transport_records WHERE id = ?", (record_id,))
            conn.commit()
            return True
        finally:
            conn.close()
