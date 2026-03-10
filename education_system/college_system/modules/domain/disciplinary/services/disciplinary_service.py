"""Disciplinary & Appeals service layer."""

from education_system.college_system.core.exceptions import DisciplinaryError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class DisciplinaryService:
    """Disciplinary & Appeals service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ---- Cases CRUD ----

    def list_cases(self, *, status: str = None, person_type: str = None,
                   limit: int = 200) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM disciplinary_cases WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if person_type:
                sql += " AND person_type = ?"
                params.append(person_type)
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_case(self, case_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM disciplinary_cases WHERE id = ?", (case_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def create_case(self, person_type: str, person_id: int,
                    allegation: str, **kwargs) -> dict:
        conn = self._conn()
        try:
            fields = {
                "person_type": person_type,
                "person_id": person_id,
                "allegation": allegation,
            }
            allowed = {
                "case_reference", "case_type", "reported_by",
                "reported_date", "investigating_officer", "hearing_date",
                "hearing_panel", "hearing_outcome", "sanction",
                "sanction_start_date", "sanction_end_date",
                "appeal_deadline", "status", "notes",
            }
            for k, v in kwargs.items():
                if k in allowed and v is not None:
                    fields[k] = v
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            vals = list(fields.values())
            conn.execute(
                f"INSERT INTO disciplinary_cases ({cols}) VALUES ({placeholders})",
                vals)
            conn.commit()
            row = conn.execute(
                "SELECT * FROM disciplinary_cases WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise DisciplinaryError(f"Failed to create case: {e}") from e
        finally:
            conn.close()

    def update_case(self, case_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {
                "person_type", "person_id", "case_reference", "case_type",
                "allegation", "reported_by", "reported_date",
                "investigating_officer", "hearing_date", "hearing_panel",
                "hearing_outcome", "sanction", "sanction_start_date",
                "sanction_end_date", "appeal_deadline", "status", "notes",
            }
            parts, params = ["updated_at = datetime('now')"], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if len(parts) < 2:
                raise DisciplinaryError("No valid fields to update.")
            params.append(case_id)
            conn.execute(
                f"UPDATE disciplinary_cases SET {', '.join(parts)} WHERE id = ?",
                params)
            conn.commit()
            return self.get_case(case_id)
        except DisciplinaryError:
            raise
        except Exception as e:
            conn.rollback()
            raise DisciplinaryError(f"Failed to update case: {e}") from e
        finally:
            conn.close()

    def delete_case(self, case_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM disciplinary_appeals WHERE case_id = ?",
                         (case_id,))
            conn.execute("DELETE FROM disciplinary_evidence WHERE case_id = ?",
                         (case_id,))
            conn.execute("DELETE FROM disciplinary_cases WHERE id = ?",
                         (case_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise DisciplinaryError(f"Failed to delete case: {e}") from e
        finally:
            conn.close()

    # ---- Hearing ----

    def schedule_hearing(self, case_id: int, hearing_date: str,
                         panel: str = None) -> dict:
        updates = {
            "hearing_date": hearing_date,
            "status": "hearing_scheduled",
        }
        if panel:
            updates["hearing_panel"] = panel
        return self.update_case(case_id, **updates)

    def record_outcome(self, case_id: int, outcome: str, *,
                       sanction: str = None, sanction_start: str = None,
                       sanction_end: str = None,
                       appeal_deadline: str = None) -> dict:
        updates = {
            "hearing_outcome": outcome,
            "status": "hearing_completed",
        }
        if sanction:
            updates["sanction"] = sanction
            updates["status"] = "sanctioned"
        if sanction_start:
            updates["sanction_start_date"] = sanction_start
        if sanction_end:
            updates["sanction_end_date"] = sanction_end
        if appeal_deadline:
            updates["appeal_deadline"] = appeal_deadline
        return self.update_case(case_id, **updates)

    # ---- Evidence CRUD ----

    def list_evidence(self, case_id: int) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT * FROM disciplinary_evidence
                   WHERE case_id = ?
                   ORDER BY submitted_date DESC, created_at DESC""",
                (case_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def add_evidence(self, case_id: int, evidence_type: str,
                     description: str, **kwargs) -> dict:
        conn = self._conn()
        try:
            fields = {
                "case_id": case_id,
                "evidence_type": evidence_type,
                "description": description,
            }
            allowed = {"file_path", "submitted_by", "submitted_date"}
            for k, v in kwargs.items():
                if k in allowed and v is not None:
                    fields[k] = v
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            vals = list(fields.values())
            conn.execute(
                f"INSERT INTO disciplinary_evidence ({cols}) VALUES ({placeholders})",
                vals)
            conn.commit()
            row = conn.execute(
                "SELECT * FROM disciplinary_evidence WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise DisciplinaryError(f"Failed to add evidence: {e}") from e
        finally:
            conn.close()

    def delete_evidence(self, evidence_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM disciplinary_evidence WHERE id = ?",
                         (evidence_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise DisciplinaryError(f"Failed to delete evidence: {e}") from e
        finally:
            conn.close()

    # ---- Appeals CRUD ----

    def list_appeals(self, *, case_id: int = None,
                     status: str = None, limit: int = 200) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM disciplinary_appeals WHERE 1=1"
            params: list = []
            if case_id is not None:
                sql += " AND case_id = ?"
                params.append(case_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_appeal(self, appeal_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM disciplinary_appeals WHERE id = ?",
                (appeal_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def lodge_appeal(self, case_id: int, appellant_id: int,
                     appeal_date: str, grounds: str) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO disciplinary_appeals
                   (case_id, appellant_id, appeal_date, grounds)
                   VALUES (?, ?, ?, ?)""",
                (case_id, appellant_id, appeal_date, grounds))
            conn.commit()
            # Update case status to appealed
            conn.execute(
                "UPDATE disciplinary_cases SET status = 'appealed', "
                "updated_at = datetime('now') WHERE id = ?",
                (case_id,))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM disciplinary_appeals WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise DisciplinaryError(f"Failed to lodge appeal: {e}") from e
        finally:
            conn.close()

    def schedule_appeal_hearing(self, appeal_id: int, hearing_date: str,
                                panel: str = None) -> dict:
        conn = self._conn()
        try:
            parts = ["hearing_date = ?", "status = 'hearing_scheduled'"]
            params: list = [hearing_date]
            if panel:
                parts.append("panel_members = ?")
                params.append(panel)
            params.append(appeal_id)
            conn.execute(
                f"UPDATE disciplinary_appeals SET {', '.join(parts)} WHERE id = ?",
                params)
            conn.commit()
            return self.get_appeal(appeal_id)
        except Exception as e:
            conn.rollback()
            raise DisciplinaryError(
                f"Failed to schedule appeal hearing: {e}") from e
        finally:
            conn.close()

    def record_appeal_outcome(self, appeal_id: int, outcome: str) -> dict:
        conn = self._conn()
        try:
            # Determine appeal status from outcome
            outcome_lower = outcome.lower()
            if "upheld" in outcome_lower:
                status = "upheld"
            elif "reject" in outcome_lower or "dismissed" in outcome_lower:
                status = "rejected"
            elif "modif" in outcome_lower:
                status = "modified"
            else:
                status = "rejected"
            conn.execute(
                """UPDATE disciplinary_appeals
                   SET outcome = ?, status = ?
                   WHERE id = ?""",
                (outcome, status, appeal_id))
            conn.commit()

            # If appeal upheld, close the parent case
            appeal = self.get_appeal(appeal_id)
            if appeal and status == "upheld":
                conn2 = self._conn()
                try:
                    conn2.execute(
                        "UPDATE disciplinary_cases SET status = 'closed', "
                        "updated_at = datetime('now') WHERE id = ?",
                        (appeal["case_id"],))
                    conn2.commit()
                finally:
                    conn2.close()

            return appeal
        except Exception as e:
            conn.rollback()
            raise DisciplinaryError(
                f"Failed to record appeal outcome: {e}") from e
        finally:
            conn.close()

    # ---- Statistics ----

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM disciplinary_cases"
            ).fetchone()[0]

            active = conn.execute(
                "SELECT COUNT(*) FROM disciplinary_cases "
                "WHERE status NOT IN ('closed')"
            ).fetchone()[0]

            by_status = {}
            for row in conn.execute(
                "SELECT status, COUNT(*) as cnt "
                "FROM disciplinary_cases GROUP BY status"
            ).fetchall():
                by_status[row["status"]] = row["cnt"]

            by_type = {}
            for row in conn.execute(
                "SELECT case_type, COUNT(*) as cnt "
                "FROM disciplinary_cases GROUP BY case_type"
            ).fetchall():
                by_type[row["case_type"]] = row["cnt"]

            total_appeals = conn.execute(
                "SELECT COUNT(*) FROM disciplinary_appeals"
            ).fetchone()[0]

            pending_appeals = conn.execute(
                "SELECT COUNT(*) FROM disciplinary_appeals "
                "WHERE status IN ('submitted', 'hearing_scheduled')"
            ).fetchone()[0]

            total_evidence = conn.execute(
                "SELECT COUNT(*) FROM disciplinary_evidence"
            ).fetchone()[0]

            return {
                "total_cases": total,
                "active_cases": active,
                "by_status": by_status,
                "by_type": by_type,
                "total_appeals": total_appeals,
                "pending_appeals": pending_appeals,
                "total_evidence": total_evidence,
            }
        finally:
            conn.close()
