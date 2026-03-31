"""Funding/ILR management service — funding records, evidence, rules, resits."""

from education_system.college_system.core.exceptions import FundingError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class FundingService:
    """Service for managing ILR funding records, evidence, rules, and resit tracking."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # -- Funding Records --

    def create_funding_record(self, student_id: int, learning_aim: str | None = None,
                              aim_type: str | None = None, funding_model: str = "16-19",
                              planned_hours: int = 0, start_date: str | None = None,
                              planned_end_date: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO funding_records
                   (student_id, learning_aim, aim_type, funding_model,
                    planned_hours, start_date, planned_end_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (student_id, learning_aim, aim_type, funding_model,
                 planned_hours, start_date, planned_end_date),
            )
            conn.commit()
            logger.info("Funding record created: student=%d aim=%s", student_id, learning_aim)
            row = conn.execute("SELECT * FROM funding_records WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise FundingError(f"Failed to create funding record: {e}") from e
        finally:
            conn.close()

    def list_funding_records(self, student_id: int | None = None,
                             status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM funding_records WHERE 1=1"
            params: list = []
            if student_id:
                sql += " AND student_id = ?"
                params.append(student_id)
            if status:
                sql += " AND completion_status = ?"
                params.append(status)
            sql += " ORDER BY created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_funding_record(self, record_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM funding_records WHERE id = ?", (record_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_funding_record(self, record_id: int, **updates) -> dict:
        allowed = {"learning_aim", "aim_type", "funding_model", "planned_hours",
                    "actual_hours", "start_date", "planned_end_date", "outcome"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise FundingError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM funding_records WHERE id = ?", (record_id,)).fetchone()
            if not existing:
                raise FundingError("Funding record not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE funding_records SET {set_parts} WHERE id = ?",  # nosec B608
                         (*updates.values(), record_id))
            conn.commit()
            logger.info("Funding record updated: id=%d", record_id)
            row = conn.execute("SELECT * FROM funding_records WHERE id = ?", (record_id,)).fetchone()
            return dict(row)
        except FundingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FundingError(f"Failed to update funding record: {e}") from e
        finally:
            conn.close()

    def complete_funding_record(self, record_id: int, outcome: str = "achieved") -> dict:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM funding_records WHERE id = ?", (record_id,)).fetchone()
            if not existing:
                raise FundingError("Funding record not found.")
            conn.execute(
                """UPDATE funding_records
                   SET completion_status = 'completed', outcome = ?, actual_end_date = date('now')
                   WHERE id = ?""",
                (outcome, record_id),
            )
            conn.commit()
            logger.info("Funding record completed: id=%d outcome=%s", record_id, outcome)
            row = conn.execute("SELECT * FROM funding_records WHERE id = ?", (record_id,)).fetchone()
            return dict(row)
        except FundingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FundingError(f"Failed to complete record: {e}") from e
        finally:
            conn.close()

    def withdraw_funding_record(self, record_id: int) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM funding_records WHERE id = ?", (record_id,)).fetchone()
            if not existing:
                raise FundingError("Funding record not found.")
            conn.execute(
                """UPDATE funding_records
                   SET completion_status = 'withdrawn', actual_end_date = date('now')
                   WHERE id = ?""",
                (record_id,),
            )
            conn.commit()
            logger.info("Funding record withdrawn: id=%d", record_id)
            row = conn.execute("SELECT * FROM funding_records WHERE id = ?", (record_id,)).fetchone()
            return dict(row)
        except FundingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FundingError(f"Failed to withdraw record: {e}") from e
        finally:
            conn.close()

    def get_hours_summary(self, student_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT COALESCE(SUM(planned_hours), 0) as total_planned,
                          COALESCE(SUM(actual_hours), 0) as total_actual
                   FROM funding_records WHERE student_id = ?""",
                (student_id,),
            ).fetchone()
            return {"student_id": student_id, "total_planned": row["total_planned"],
                    "total_actual": row["total_actual"]}
        finally:
            conn.close()

    def export_ilr_data(self) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT fr.*, s.student_id as sid, s.first_name, s.last_name
                   FROM funding_records fr
                   JOIN students s ON fr.student_id = s.id
                   ORDER BY s.last_name, s.first_name"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # -- Evidence --

    def add_evidence(self, funding_record_id: int, evidence_type: str = "other",
                     file_path: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO funding_evidence (funding_record_id, evidence_type, file_path)
                   VALUES (?, ?, ?)""",
                (funding_record_id, evidence_type, file_path),
            )
            conn.commit()
            logger.info("Evidence added: record=%d type=%s", funding_record_id, evidence_type)
            row = conn.execute("SELECT * FROM funding_evidence WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise FundingError(f"Failed to add evidence: {e}") from e
        finally:
            conn.close()

    def list_evidence(self, funding_record_id: int | None = None) -> list[dict]:
        conn = self._conn()
        try:
            if funding_record_id:
                rows = conn.execute(
                    "SELECT * FROM funding_evidence WHERE funding_record_id = ? ORDER BY created_at DESC",
                    (funding_record_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM funding_evidence ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def verify_evidence(self, evidence_id: int, verified_by: int) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM funding_evidence WHERE id = ?", (evidence_id,)).fetchone()
            if not existing:
                raise FundingError("Evidence not found.")
            conn.execute(
                "UPDATE funding_evidence SET verified = 1, verified_by = ?, verified_date = date('now') WHERE id = ?",
                (verified_by, evidence_id),
            )
            conn.commit()
            logger.info("Evidence verified: id=%d", evidence_id)
            row = conn.execute("SELECT * FROM funding_evidence WHERE id = ?", (evidence_id,)).fetchone()
            return dict(row)
        except FundingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FundingError(f"Failed to verify evidence: {e}") from e
        finally:
            conn.close()

    def get_unverified_evidence(self) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM funding_evidence WHERE verified = 0 ORDER BY created_at"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # -- Rules --

    def create_rule(self, rule_code: str, description: str | None = None,
                    rule_type: str = "eligibility", applies_to: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO funding_rules (rule_code, description, rule_type, applies_to)
                   VALUES (?, ?, ?, ?)""",
                (rule_code, description, rule_type, applies_to),
            )
            conn.commit()
            logger.info("Funding rule created: code=%s", rule_code)
            row = conn.execute("SELECT * FROM funding_rules WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise FundingError(f"Failed to create rule: {e}") from e
        finally:
            conn.close()

    def list_rules(self, active_only: bool = True) -> list[dict]:
        conn = self._conn()
        try:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM funding_rules WHERE is_active = 1 ORDER BY rule_code"
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM funding_rules ORDER BY rule_code").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_rule(self, rule_id: int, **updates) -> dict:
        allowed = {"description", "rule_type", "applies_to", "is_active"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise FundingError("No valid fields to update.")
        conn = self._conn()
        try:
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE funding_rules SET {set_parts} WHERE id = ?",  # nosec B608
                         (*updates.values(), rule_id))
            conn.commit()
            row = conn.execute("SELECT * FROM funding_rules WHERE id = ?", (rule_id,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise FundingError(f"Failed to update rule: {e}") from e
        finally:
            conn.close()

    def check_student_eligibility(self, student_id: int) -> dict:
        conn = self._conn()
        try:
            records = conn.execute(
                "SELECT * FROM funding_records WHERE student_id = ?", (student_id,)
            ).fetchall()
            rules = conn.execute(
                "SELECT * FROM funding_rules WHERE is_active = 1"
            ).fetchall()
            return {
                "student_id": student_id,
                "funding_records": len(records),
                "active_rules": len(rules),
                "eligible": len(records) > 0,
            }
        finally:
            conn.close()

    # -- Resits --

    def create_resit(self, student_id: int, subject: str,
                     gcse_grade_on_entry: str | None = None,
                     current_level: str | None = None,
                     target_grade: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO resit_tracking
                   (student_id, subject, gcse_grade_on_entry, current_level, target_grade)
                   VALUES (?, ?, ?, ?, ?)""",
                (student_id, subject, gcse_grade_on_entry, current_level, target_grade),
            )
            conn.commit()
            logger.info("Resit created: student=%d subject=%s", student_id, subject)
            row = conn.execute("SELECT * FROM resit_tracking WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise FundingError(f"Failed to create resit: {e}") from e
        finally:
            conn.close()

    def list_resits(self, student_id: int | None = None,
                    subject: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM resit_tracking WHERE 1=1"
            params: list = []
            if student_id:
                sql += " AND student_id = ?"
                params.append(student_id)
            if subject:
                sql += " AND subject = ?"
                params.append(subject)
            sql += " ORDER BY created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_resit(self, resit_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM resit_tracking WHERE id = ?", (resit_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_resit(self, resit_id: int, **updates) -> dict:
        allowed = {"current_level", "target_grade", "exam_entries_count",
                    "latest_result", "status", "notes"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise FundingError("No valid fields to update.")
        conn = self._conn()
        try:
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE resit_tracking SET {set_parts}, updated_at = datetime('now') WHERE id = ?",
                (*updates.values(), resit_id),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM resit_tracking WHERE id = ?", (resit_id,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise FundingError(f"Failed to update resit: {e}") from e
        finally:
            conn.close()

    def get_resit_summary(self) -> dict:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT subject,
                          COUNT(*) as total,
                          SUM(CASE WHEN status = 'achieved' THEN 1 ELSE 0 END) as achieved,
                          SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active
                   FROM resit_tracking GROUP BY subject"""
            ).fetchall()
            return {"subjects": [dict(r) for r in rows]}
        finally:
            conn.close()
