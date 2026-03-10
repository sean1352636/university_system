"""Student support service — interventions, risk register, documents."""

from education_system.college_system.core.exceptions import StudentSupportError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class StudentSupportService:
    """Service for managing student support interventions, risk register, and documents."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # -- Interventions --

    def create_intervention(self, student_id: int, staff_id: int,
                            intervention_type: str = "academic",
                            targets: str | None = None,
                            sessions_planned: int = 0) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO support_interventions
                   (student_id, staff_id, intervention_type, targets, sessions_planned)
                   VALUES (?, ?, ?, ?, ?)""",
                (student_id, staff_id, intervention_type, targets, sessions_planned),
            )
            conn.commit()
            logger.info("Intervention created: student=%d type=%s", student_id, intervention_type)
            row = conn.execute(
                "SELECT * FROM support_interventions WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise StudentSupportError(f"Failed to create intervention: {e}") from e
        finally:
            conn.close()

    def list_interventions(self, student_id: int | None = None,
                           status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM support_interventions WHERE 1=1"
            params: list = []
            if student_id:
                sql += " AND student_id = ?"
                params.append(student_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_intervention(self, intervention_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM support_interventions WHERE id = ?", (intervention_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_intervention(self, intervention_id: int, **updates) -> dict:
        allowed = {"intervention_type", "targets", "sessions_planned",
                    "outcome", "impact_rating", "status"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise StudentSupportError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM support_interventions WHERE id = ?", (intervention_id,)
            ).fetchone()
            if not existing:
                raise StudentSupportError("Intervention not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE support_interventions SET {set_parts}, updated_at = datetime('now') WHERE id = ?",
                (*updates.values(), intervention_id),
            )
            conn.commit()
            logger.info("Intervention updated: id=%d", intervention_id)
            row = conn.execute(
                "SELECT * FROM support_interventions WHERE id = ?", (intervention_id,)
            ).fetchone()
            return dict(row)
        except StudentSupportError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentSupportError(f"Failed to update intervention: {e}") from e
        finally:
            conn.close()

    def record_session_attended(self, intervention_id: int) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT * FROM support_interventions WHERE id = ?", (intervention_id,)
            ).fetchone()
            if not existing:
                raise StudentSupportError("Intervention not found.")
            new_count = existing["sessions_attended"] + 1
            conn.execute(
                """UPDATE support_interventions
                   SET sessions_attended = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (new_count, intervention_id),
            )
            conn.commit()
            logger.info("Session attended recorded: intervention=%d count=%d", intervention_id, new_count)
            row = conn.execute(
                "SELECT * FROM support_interventions WHERE id = ?", (intervention_id,)
            ).fetchone()
            return dict(row)
        except StudentSupportError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentSupportError(f"Failed to record session: {e}") from e
        finally:
            conn.close()

    def get_intervention_impact_report(self) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT intervention_type,
                          COUNT(*) as total,
                          SUM(CASE WHEN impact_rating = 'significant' THEN 1 ELSE 0 END) as significant,
                          SUM(CASE WHEN impact_rating = 'some' THEN 1 ELSE 0 END) as some_impact,
                          SUM(CASE WHEN impact_rating = 'none' THEN 1 ELSE 0 END) as no_impact,
                          SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
                   FROM support_interventions
                   GROUP BY intervention_type
                   ORDER BY intervention_type"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # -- Risk Register --

    def create_risk(self, student_id: int, risk_type: str, risk_level: str,
                    identified_by: int, mitigations: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO risk_register
                   (student_id, risk_type, risk_level, identified_by, mitigations)
                   VALUES (?, ?, ?, ?, ?)""",
                (student_id, risk_type, risk_level, identified_by, mitigations),
            )
            conn.commit()
            logger.info("Risk created: student=%d type=%s level=%s", student_id, risk_type, risk_level)
            row = conn.execute("SELECT * FROM risk_register WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise StudentSupportError(f"Failed to create risk: {e}") from e
        finally:
            conn.close()

    def list_risks(self, student_id: int | None = None,
                   status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM risk_register WHERE 1=1"
            params: list = []
            if student_id:
                sql += " AND student_id = ?"
                params.append(student_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY CASE risk_level WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_risk(self, risk_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM risk_register WHERE id = ?", (risk_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_risk(self, risk_id: int, **updates) -> dict:
        allowed = {"risk_type", "risk_level", "mitigations", "status"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise StudentSupportError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM risk_register WHERE id = ?", (risk_id,)).fetchone()
            if not existing:
                raise StudentSupportError("Risk not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE risk_register SET {set_parts}, updated_at = datetime('now') WHERE id = ?",
                (*updates.values(), risk_id),
            )
            conn.commit()
            logger.info("Risk updated: id=%d", risk_id)
            row = conn.execute("SELECT * FROM risk_register WHERE id = ?", (risk_id,)).fetchone()
            return dict(row)
        except StudentSupportError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentSupportError(f"Failed to update risk: {e}") from e
        finally:
            conn.close()

    def resolve_risk(self, risk_id: int) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM risk_register WHERE id = ?", (risk_id,)).fetchone()
            if not existing:
                raise StudentSupportError("Risk not found.")
            conn.execute(
                """UPDATE risk_register
                   SET status = 'resolved', resolved_date = date('now'), updated_at = datetime('now')
                   WHERE id = ?""",
                (risk_id,),
            )
            conn.commit()
            logger.info("Risk resolved: id=%d", risk_id)
            row = conn.execute("SELECT * FROM risk_register WHERE id = ?", (risk_id,)).fetchone()
            return dict(row)
        except StudentSupportError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentSupportError(f"Failed to resolve risk: {e}") from e
        finally:
            conn.close()

    def escalate_risk(self, risk_id: int) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM risk_register WHERE id = ?", (risk_id,)).fetchone()
            if not existing:
                raise StudentSupportError("Risk not found.")
            conn.execute(
                """UPDATE risk_register
                   SET status = 'escalated', updated_at = datetime('now')
                   WHERE id = ?""",
                (risk_id,),
            )
            conn.commit()
            logger.info("Risk escalated: id=%d", risk_id)
            row = conn.execute("SELECT * FROM risk_register WHERE id = ?", (risk_id,)).fetchone()
            return dict(row)
        except StudentSupportError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentSupportError(f"Failed to escalate risk: {e}") from e
        finally:
            conn.close()

    def get_student_risk_profile(self, student_id: int) -> dict:
        conn = self._conn()
        try:
            risks = conn.execute(
                "SELECT * FROM risk_register WHERE student_id = ? ORDER BY created_at DESC",
                (student_id,),
            ).fetchall()
            interventions = conn.execute(
                "SELECT * FROM support_interventions WHERE student_id = ? ORDER BY created_at DESC",
                (student_id,),
            ).fetchall()
            documents = conn.execute(
                "SELECT * FROM student_documents WHERE student_id = ? ORDER BY created_at DESC",
                (student_id,),
            ).fetchall()
            open_risks = [dict(r) for r in risks if r["status"] in ("open", "monitoring", "escalated")]
            return {
                "student_id": student_id,
                "total_risks": len(risks),
                "open_risks": len(open_risks),
                "risks": [dict(r) for r in risks],
                "interventions": [dict(r) for r in interventions],
                "documents": [dict(r) for r in documents],
            }
        finally:
            conn.close()

    # -- Documents --

    def upload_document(self, student_id: int, document_type: str, title: str,
                        uploaded_by: int, file_path: str | None = None,
                        expiry_date: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO student_documents
                   (student_id, document_type, title, file_path, uploaded_by, expiry_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (student_id, document_type, title, file_path, uploaded_by, expiry_date),
            )
            conn.commit()
            logger.info("Document uploaded: student=%d type=%s title=%s", student_id, document_type, title)
            row = conn.execute("SELECT * FROM student_documents WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise StudentSupportError(f"Failed to upload document: {e}") from e
        finally:
            conn.close()

    def list_documents(self, student_id: int | None = None) -> list[dict]:
        conn = self._conn()
        try:
            if student_id:
                rows = conn.execute(
                    "SELECT * FROM student_documents WHERE student_id = ? ORDER BY created_at DESC",
                    (student_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM student_documents ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_document(self, doc_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM student_documents WHERE id = ?", (doc_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def verify_document(self, doc_id: int, verified_by: int) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM student_documents WHERE id = ?", (doc_id,)).fetchone()
            if not existing:
                raise StudentSupportError("Document not found.")
            conn.execute(
                "UPDATE student_documents SET verified = 1, verified_by = ? WHERE id = ?",
                (verified_by, doc_id),
            )
            conn.commit()
            logger.info("Document verified: id=%d by=%d", doc_id, verified_by)
            row = conn.execute("SELECT * FROM student_documents WHERE id = ?", (doc_id,)).fetchone()
            return dict(row)
        except StudentSupportError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentSupportError(f"Failed to verify document: {e}") from e
        finally:
            conn.close()

    def get_expiring_documents(self, days: int = 30) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT d.*, s.first_name, s.last_name, s.student_id as sid
                   FROM student_documents d
                   JOIN students s ON d.student_id = s.id
                   WHERE d.expiry_date IS NOT NULL
                   AND d.expiry_date <= date('now', '+' || ? || ' days')
                   AND d.expiry_date >= date('now')
                   ORDER BY d.expiry_date""",
                (days,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
