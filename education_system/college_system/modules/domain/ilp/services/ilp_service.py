"""Individual Learning Plans service."""

from education_system.college_system.core.exceptions import ILPError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class ILPService:
    """Individual Learning Plans service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_plan(self, student_id: int, academic_year: str | None = None,
                    plan_type: str = "standard", long_term_goal: str | None = None,
                    support_needs: str | None = None, review_frequency: str = "half-termly",
                    created_by: int | None = None, notes: str | None = None) -> dict:
        """Create a new ILP for a student."""
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO ilp_plans
                   (student_id, academic_year, plan_type, long_term_goal,
                    support_needs, review_frequency, created_by, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, academic_year, plan_type, long_term_goal,
                 support_needs, review_frequency, created_by, notes),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM ilp_plans WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise ILPError(f"Failed to create ILP: {e}") from e
        finally:
            conn.close()

    def list_plans(self, student_id: int | None = None, status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM ilp_plans WHERE 1=1"
            params: list = []
            if student_id:
                sql += " AND student_id = ?"
                params.append(student_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_plan(self, plan_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM ilp_plans WHERE id = ?", (plan_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_plan(self, plan_id: int, **updates) -> dict:
        allowed = {"long_term_goal", "support_needs", "review_frequency", "next_review_date", "status", "notes"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise ILPError("No valid fields to update.")
        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [plan_id]
            conn.execute(f"UPDATE ilp_plans SET {sets}, updated_at = datetime('now') WHERE id = ?", vals)
            conn.commit()
            return self.get_plan(plan_id)
        except Exception as e:
            conn.rollback()
            raise ILPError(f"Failed to update ILP: {e}") from e
        finally:
            conn.close()

    def add_target(self, plan_id: int, target_description: str,
                   subject_area: str | None = None, current_grade: str | None = None,
                   target_grade: str | None = None, success_criteria: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO ilp_targets
                   (plan_id, subject_area, target_description, success_criteria,
                    current_grade, target_grade)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (plan_id, subject_area, target_description, success_criteria,
                 current_grade, target_grade),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM ilp_targets WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise ILPError(f"Failed to add target: {e}") from e
        finally:
            conn.close()

    def list_targets(self, plan_id: int) -> list[dict]:
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM ilp_targets WHERE plan_id = ? ORDER BY id", (plan_id,)).fetchall()]
        finally:
            conn.close()

    def update_target(self, target_id: int, **updates) -> dict:
        allowed = {"target_description", "success_criteria", "current_grade", "target_grade", "status", "evidence"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        conn = self._conn()
        try:
            if updates.get("status") == "completed":
                updates["completed_at"] = "datetime('now')"
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [target_id]
            conn.execute(f"UPDATE ilp_targets SET {sets} WHERE id = ?", vals)
            conn.commit()
            row = conn.execute("SELECT * FROM ilp_targets WHERE id = ?", (target_id,)).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise ILPError(f"Failed to update target: {e}") from e
        finally:
            conn.close()

    def add_review(self, plan_id: int, review_date: str, reviewer_id: int | None = None,
                   summary: str | None = None, student_voice: str | None = None,
                   actions_agreed: str | None = None, next_review_date: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO ilp_reviews
                   (plan_id, reviewer_id, review_date, summary, student_voice,
                    actions_agreed, next_review_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (plan_id, reviewer_id, review_date, summary, student_voice,
                 actions_agreed, next_review_date),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM ilp_reviews WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise ILPError(f"Failed to add review: {e}") from e
        finally:
            conn.close()

    def list_reviews(self, plan_id: int) -> list[dict]:
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM ilp_reviews WHERE plan_id = ? ORDER BY review_date DESC",
                (plan_id,)).fetchall()]
        finally:
            conn.close()

    def get_due_reviews(self) -> list[dict]:
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                """SELECT p.*, s.first_name, s.last_name, s.student_id as sid
                   FROM ilp_plans p JOIN students s ON p.student_id = s.id
                   WHERE p.status = 'active'
                   AND p.next_review_date <= date('now')
                   ORDER BY p.next_review_date""").fetchall()]
        finally:
            conn.close()

