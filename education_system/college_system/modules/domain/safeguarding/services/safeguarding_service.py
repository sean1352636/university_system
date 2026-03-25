"""Safeguarding service for managing concerns and referrals."""

from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.exceptions import SafeguardingError


class SafeguardingService:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def report_concern(self, student_id: int, reported_by: int, category: str,
                        description: str, risk_level: str = "low",
                        actions_taken: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO safeguarding_concerns
                   (student_id, reported_by, category, description, risk_level, actions_taken)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (student_id, reported_by, category, description, risk_level, actions_taken),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM safeguarding_concerns WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise SafeguardingError(f"Failed to report concern: {e}")
        finally:
            conn.close()

    def list_concerns(self, status: str = None, risk_level: str = None,
                       limit: int = 100) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT sc.*, s.first_name, s.last_name
                       FROM safeguarding_concerns sc
                       LEFT JOIN students s ON sc.student_id = s.id WHERE 1=1"""
            params = []
            if status:
                query += " AND sc.status = ?"
                params.append(status)
            if risk_level:
                query += " AND sc.risk_level = ?"
                params.append(risk_level)
            query += " ORDER BY sc.concern_date DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_concern(self, concern_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT sc.*, s.first_name, s.last_name
                   FROM safeguarding_concerns sc
                   LEFT JOIN students s ON sc.student_id = s.id
                   WHERE sc.id = ?""",
                (concern_id,),
            ).fetchone()
            if not row:
                raise SafeguardingError(f"Concern {concern_id} not found")
            return dict(row)
        finally:
            conn.close()

    def update_concern(self, concern_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"status", "risk_level", "assigned_to", "actions_taken",
                        "referral_agency", "parent_informed", "confidential"}
            parts, params = ["updated_at = datetime('now')"], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if len(parts) < 2:
                raise SafeguardingError("No valid fields to update")
            params.append(concern_id)
            conn.execute(
                f"UPDATE safeguarding_concerns SET {', '.join(parts)} WHERE id = ?", params
            )
            conn.commit()
            return self.get_concern(concern_id)
        except SafeguardingError:
            raise
        except Exception as e:
            raise SafeguardingError(f"Failed to update concern: {e}")
        finally:
            conn.close()

    def delete_concern(self, concern_id: int) -> bool:
        """Delete a safeguarding concern by ID."""
        conn = self._conn()
        try:
            result = conn.execute(
                "DELETE FROM safeguarding_concerns WHERE id = ?", (concern_id,)
            )
            conn.commit()
            if result.rowcount == 0:
                raise SafeguardingError(f"Concern {concern_id} not found.")
            return True
        except SafeguardingError:
            raise
        except Exception as e:
            conn.rollback()
            raise SafeguardingError(f"Failed to delete concern: {e}")
        finally:
            conn.close()

    def get_student_concerns(self, student_id: int) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM safeguarding_concerns WHERE student_id = ? ORDER BY concern_date DESC",
                (student_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
