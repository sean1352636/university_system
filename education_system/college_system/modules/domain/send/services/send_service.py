"""SEND/ALS service for managing special educational needs."""

from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.exceptions import SENDError


class SENDService:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # --- SEND Records ---

    def create_record(self, student_id: int, send_status: str = "none",
                       primary_need: str = "other", ehcp_review_date: str = None,
                       support_plan: str = None, exam_access: str = None,
                       extra_time_percent: int = 0, reader: int = 0,
                       scribe: int = 0, rest_breaks: int = 0,
                       funding_band: str = None, notes: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO send_records
                   (student_id, send_status, primary_need, ehcp_review_date,
                    support_plan, exam_access, extra_time_percent, reader,
                    scribe, rest_breaks, funding_band, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, send_status, primary_need, ehcp_review_date,
                 support_plan, exam_access, extra_time_percent, reader,
                 scribe, rest_breaks, funding_band, notes),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM send_records WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise SENDError(f"Failed to create SEND record: {e}")
        finally:
            conn.close()

    def list_records(self, active_only: bool = True) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT sr.*, s.first_name, s.last_name FROM send_records sr
                       LEFT JOIN students s ON sr.student_id = s.id"""
            if active_only:
                query += " WHERE sr.send_status != 'none'"
            query += " ORDER BY sr.created_at DESC"
            rows = conn.execute(query).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_record(self, record_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT sr.*, s.first_name, s.last_name FROM send_records sr
                   LEFT JOIN students s ON sr.student_id = s.id WHERE sr.id = ?""",
                (record_id,),
            ).fetchone()
            if not row:
                raise SENDError(f"SEND record {record_id} not found")
            return dict(row)
        finally:
            conn.close()

    def update_record(self, record_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"send_status", "primary_need", "ehcp_review_date",
                        "support_plan", "exam_access", "extra_time_percent",
                        "reader", "scribe", "rest_breaks", "funding_band", "notes"}
            parts, params = ["updated_at = datetime('now')"], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if len(parts) < 2:
                raise SENDError("No valid fields to update")
            params.append(record_id)
            conn.execute(f"UPDATE send_records SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            return self.get_record(record_id)
        except SENDError:
            raise
        except Exception as e:
            raise SENDError(f"Failed to update record: {e}")
        finally:
            conn.close()

    def delete_record(self, record_id: int) -> bool:
        """Delete a SEND record by ID."""
        conn = self._conn()
        try:
            result = conn.execute(
                "DELETE FROM send_records WHERE id = ?", (record_id,)
            )
            conn.commit()
            if result.rowcount == 0:
                raise SENDError(f"SEND record {record_id} not found.")
            return True
        except SENDError:
            raise
        except Exception as e:
            conn.rollback()
            raise SENDError(f"Failed to delete SEND record: {e}")
        finally:
            conn.close()

    def get_student_record(self, student_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM send_records WHERE student_id = ? AND send_status != 'none'",
                (student_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
