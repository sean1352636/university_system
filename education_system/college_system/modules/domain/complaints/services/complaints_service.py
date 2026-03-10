"""Complaints service for managing complaints and responses."""

from education_system.college_system.core.exceptions import ComplaintError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class ComplaintService:
    """Complaints management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ---- Complaints ----

    def create_complaint(self, complainant_name: str, subject: str,
                         description: str, *,
                         complainant_type: str = "parent",
                         complainant_email: str = None,
                         complainant_phone: str = None,
                         complaint_date: str = None,
                         category: str = "general",
                         stage: str = "informal",
                         assigned_to: int = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO complaints
                   (complainant_name, complainant_type, complainant_email,
                    complainant_phone, complaint_date, category, subject,
                    description, stage, assigned_to)
                   VALUES (?, ?, ?, ?, COALESCE(?, date('now')), ?, ?, ?, ?, ?)""",
                (complainant_name, complainant_type, complainant_email,
                 complainant_phone, complaint_date, category, subject,
                 description, stage, assigned_to))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM complaints WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise ComplaintError(f"Failed to create complaint: {e}") from e
        finally:
            conn.close()

    def list_complaints(self, *, status: str = None, stage: str = None,
                        category: str = None, search: str = None,
                        limit: int = 200) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM complaints WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if stage:
                sql += " AND stage = ?"
                params.append(stage)
            if category:
                sql += " AND category = ?"
                params.append(category)
            if search:
                sql += (" AND (complainant_name LIKE ? OR subject LIKE ?"
                        " OR description LIKE ?)")
                term = f"%{search}%"
                params.extend([term, term, term])
            sql += " ORDER BY complaint_date DESC, created_at DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_complaint(self, complaint_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM complaints WHERE id = ?", (complaint_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_complaint(self, complaint_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {
                "complainant_name", "complainant_type", "complainant_email",
                "complainant_phone", "category", "subject", "description",
                "stage", "assigned_to", "investigation_notes", "outcome",
                "resolution", "resolved_date", "appeal_lodged", "status",
            }
            parts, params = ["updated_at = datetime('now')"], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if len(parts) < 2:
                raise ComplaintError("No valid fields to update.")
            params.append(complaint_id)
            conn.execute(
                f"UPDATE complaints SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            return self.get_complaint(complaint_id)
        except ComplaintError:
            raise
        except Exception as e:
            conn.rollback()
            raise ComplaintError(f"Failed to update complaint: {e}") from e
        finally:
            conn.close()

    def escalate(self, complaint_id: int) -> dict:
        """Escalate a complaint to the next stage."""
        stages = ["informal", "formal_stage_1", "formal_stage_2", "panel_hearing", "appeal"]
        rec = self.get_complaint(complaint_id)
        if not rec:
            raise ComplaintError("Complaint not found.")
        current = rec.get("stage", "informal")
        try:
            idx = stages.index(current)
        except ValueError:
            idx = -1
        if idx >= len(stages) - 1:
            raise ComplaintError(f"Cannot escalate beyond '{current}'.")
        return self.update_complaint(complaint_id, stage=stages[idx + 1])

    def resolve(self, complaint_id: int, outcome: str,
                resolution: str = None) -> dict:
        """Mark a complaint as resolved."""
        return self.update_complaint(
            complaint_id, status="resolved", outcome=outcome,
            resolution=resolution, resolved_date="date('now')")

    def delete_complaint(self, complaint_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM complaint_responses WHERE complaint_id = ?",
                         (complaint_id,))
            conn.execute("DELETE FROM complaints WHERE id = ?", (complaint_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise ComplaintError(f"Failed to delete complaint: {e}") from e
        finally:
            conn.close()

    # ---- Responses ----

    def add_response(self, complaint_id: int, response_text: str, *,
                     responder_id: int = None,
                     response_date: str = None,
                     response_type: str = "investigation") -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO complaint_responses
                   (complaint_id, responder_id, response_date,
                    response_text, response_type)
                   VALUES (?, ?, COALESCE(?, date('now')), ?, ?)""",
                (complaint_id, responder_id, response_date,
                 response_text, response_type))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM complaint_responses WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise ComplaintError(f"Failed to add response: {e}") from e
        finally:
            conn.close()

    def list_responses(self, complaint_id: int) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT cr.*, u.username AS responder_name
                   FROM complaint_responses cr
                   LEFT JOIN users u ON cr.responder_id = u.id
                   WHERE cr.complaint_id = ?
                   ORDER BY cr.response_date, cr.created_at""",
                (complaint_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_response(self, response_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM complaint_responses WHERE id = ?",
                         (response_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise ComplaintError(f"Failed to delete response: {e}") from e
        finally:
            conn.close()

    # ---- Statistics ----

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
            open_count = conn.execute(
                "SELECT COUNT(*) FROM complaints WHERE status = 'open'"
            ).fetchone()[0]
            investigating = conn.execute(
                "SELECT COUNT(*) FROM complaints WHERE status = 'investigating'"
            ).fetchone()[0]
            resolved = conn.execute(
                "SELECT COUNT(*) FROM complaints WHERE status = 'resolved'"
            ).fetchone()[0]
            appealed = conn.execute(
                "SELECT COUNT(*) FROM complaints WHERE appeal_lodged = 1"
            ).fetchone()[0]
            by_category = {}
            for row in conn.execute(
                "SELECT category, COUNT(*) as cnt FROM complaints GROUP BY category"
            ).fetchall():
                by_category[row["category"]] = row["cnt"]
            by_stage = {}
            for row in conn.execute(
                "SELECT stage, COUNT(*) as cnt FROM complaints GROUP BY stage"
            ).fetchall():
                by_stage[row["stage"]] = row["cnt"]
            return {
                "total": total, "open": open_count,
                "investigating": investigating, "resolved": resolved,
                "appealed": appealed,
                "by_category": by_category, "by_stage": by_stage,
            }
        finally:
            conn.close()
