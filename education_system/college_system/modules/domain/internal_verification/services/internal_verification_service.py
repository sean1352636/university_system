"""Internal Verification service layer."""

from education_system.college_system.core.exceptions import InternalVerificationError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class InternalVerificationService:
    """Service for managing IV plans, samples, and observations."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        conn = connect(self._db_path)
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        return conn

    # ── Plans CRUD ───────────────────────────────────────────────

    def list_plans(self, status: str | None = None,
                   course_id: int | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT p.*, c.title AS course_name
                     FROM iv_plans p
                     LEFT JOIN courses c ON c.id = p.course_id
                     WHERE 1=1"""
            params: list = []
            if status:
                sql += " AND p.status = ?"
                params.append(status)
            if course_id:
                sql += " AND p.course_id = ?"
                params.append(course_id)
            sql += " ORDER BY p.created_at DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_plan(self, plan_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT p.*, c.title AS course_name
                   FROM iv_plans p
                   LEFT JOIN courses c ON c.id = p.course_id
                   WHERE p.id = ?""", (plan_id,)
            ).fetchone()
            return row
        finally:
            conn.close()

    def create_plan(self, course_id: int, academic_year: str | None = None,
                    lead_iv_id: int | None = None,
                    sampling_strategy: str | None = None,
                    sample_size_pct: int = 25,
                    status: str = "active", **kwargs) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO iv_plans
                   (course_id, academic_year, lead_iv_id, sampling_strategy,
                    sample_size_pct, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (course_id, academic_year, lead_iv_id, sampling_strategy,
                 sample_size_pct, status),
            )
            conn.commit()
            logger.info("IV plan created for course %d", course_id)
            row = conn.execute(
                "SELECT * FROM iv_plans WHERE id = last_insert_rowid()"
            ).fetchone()
            return row
        except Exception as e:
            conn.rollback()
            raise InternalVerificationError(f"Failed to create plan: {e}") from e
        finally:
            conn.close()

    def update_plan(self, plan_id: int, **kwargs) -> dict:
        allowed = {"course_id", "academic_year", "lead_iv_id",
                    "sampling_strategy", "sample_size_pct", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise InternalVerificationError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM iv_plans WHERE id = ?", (plan_id,)
            ).fetchone()
            if not existing:
                raise InternalVerificationError(f"Plan {plan_id} not found.")
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [plan_id]
            conn.execute(
                f"UPDATE iv_plans SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                vals,
            )
            conn.commit()
            logger.info("IV plan %d updated", plan_id)
            return self.get_plan(plan_id)
        except InternalVerificationError:
            raise
        except Exception as e:
            conn.rollback()
            raise InternalVerificationError(f"Failed to update plan: {e}") from e
        finally:
            conn.close()

    def delete_plan(self, plan_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM iv_plans WHERE id = ?", (plan_id,)
            ).fetchone()
            if not existing:
                raise InternalVerificationError(f"Plan {plan_id} not found.")
            conn.execute("DELETE FROM iv_observations WHERE plan_id = ?", (plan_id,))
            conn.execute("DELETE FROM iv_samples WHERE plan_id = ?", (plan_id,))
            conn.execute("DELETE FROM iv_plans WHERE id = ?", (plan_id,))
            conn.commit()
            logger.info("IV plan %d deleted (cascaded)", plan_id)
            return True
        except InternalVerificationError:
            raise
        except Exception as e:
            conn.rollback()
            raise InternalVerificationError(f"Failed to delete plan: {e}") from e
        finally:
            conn.close()

    # ── Samples CRUD ─────────────────────────────────────────────

    def list_samples(self, plan_id: int | None = None,
                     status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT s.*
                     FROM iv_samples s
                     WHERE 1=1"""
            params: list = []
            if plan_id:
                sql += " AND s.plan_id = ?"
                params.append(plan_id)
            if status:
                sql += " AND s.status = ?"
                params.append(status)
            sql += " ORDER BY s.created_at DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_sample(self, sample_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM iv_samples WHERE id = ?", (sample_id,)
            ).fetchone()
            return row
        finally:
            conn.close()

    def create_sample(self, plan_id: int, assignment_title: str,
                      assessor_id: int | None = None,
                      verifier_id: int | None = None,
                      sample_date: str | None = None,
                      student_ids: str | None = None,
                      status: str = "pending", **kwargs) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO iv_samples
                   (plan_id, assignment_title, assessor_id, verifier_id,
                    sample_date, student_ids, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (plan_id, assignment_title, assessor_id, verifier_id,
                 sample_date, student_ids, status),
            )
            conn.commit()
            logger.info("IV sample created for plan %d: %s", plan_id, assignment_title)
            row = conn.execute(
                "SELECT * FROM iv_samples WHERE id = last_insert_rowid()"
            ).fetchone()
            return row
        except Exception as e:
            conn.rollback()
            raise InternalVerificationError(f"Failed to create sample: {e}") from e
        finally:
            conn.close()

    def update_sample(self, sample_id: int, **kwargs) -> dict:
        allowed = {"plan_id", "assignment_title", "assessor_id", "verifier_id",
                    "sample_date", "student_ids", "assessment_decisions_agreed",
                    "feedback_quality", "grading_accurate", "action_required",
                    "action_completed", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise InternalVerificationError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM iv_samples WHERE id = ?", (sample_id,)
            ).fetchone()
            if not existing:
                raise InternalVerificationError(f"Sample {sample_id} not found.")
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [sample_id]
            conn.execute(f"UPDATE iv_samples SET {sets} WHERE id = ?", vals)
            conn.commit()
            logger.info("IV sample %d updated", sample_id)
            return self.get_sample(sample_id)
        except InternalVerificationError:
            raise
        except Exception as e:
            conn.rollback()
            raise InternalVerificationError(f"Failed to update sample: {e}") from e
        finally:
            conn.close()

    def delete_sample(self, sample_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM iv_samples WHERE id = ?", (sample_id,)
            ).fetchone()
            if not existing:
                raise InternalVerificationError(f"Sample {sample_id} not found.")
            conn.execute("DELETE FROM iv_samples WHERE id = ?", (sample_id,))
            conn.commit()
            logger.info("IV sample %d deleted", sample_id)
            return True
        except InternalVerificationError:
            raise
        except Exception as e:
            conn.rollback()
            raise InternalVerificationError(f"Failed to delete sample: {e}") from e
        finally:
            conn.close()

    def complete_sample(self, sample_id: int, decisions_agreed: int,
                        feedback_quality: str, grading_accurate: int,
                        action_required: str | None = None) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM iv_samples WHERE id = ?", (sample_id,)
            ).fetchone()
            if not existing:
                raise InternalVerificationError(f"Sample {sample_id} not found.")
            new_status = "action_required" if action_required else "completed"
            conn.execute(
                """UPDATE iv_samples
                   SET assessment_decisions_agreed = ?,
                       feedback_quality = ?,
                       grading_accurate = ?,
                       action_required = ?,
                       status = ?
                   WHERE id = ?""",
                (decisions_agreed, feedback_quality, grading_accurate,
                 action_required, new_status, sample_id),
            )
            conn.commit()
            logger.info("IV sample %d completed (status=%s)", sample_id, new_status)
            return self.get_sample(sample_id)
        except InternalVerificationError:
            raise
        except Exception as e:
            conn.rollback()
            raise InternalVerificationError(f"Failed to complete sample: {e}") from e
        finally:
            conn.close()

    # ── Observations CRUD ────────────────────────────────────────

    def list_observations(self, plan_id: int | None = None,
                          status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT o.*
                     FROM iv_observations o
                     WHERE 1=1"""
            params: list = []
            if plan_id:
                sql += " AND o.plan_id = ?"
                params.append(plan_id)
            if status:
                sql += " AND o.status = ?"
                params.append(status)
            sql += " ORDER BY o.created_at DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_observation(self, observation_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM iv_observations WHERE id = ?", (observation_id,)
            ).fetchone()
            return row
        finally:
            conn.close()

    def create_observation(self, plan_id: int,
                           assessor_id: int | None = None,
                           observer_id: int | None = None,
                           observation_date: str | None = None,
                           assessment_type: str | None = None,
                           feedback: str | None = None,
                           actions: str | None = None,
                           grade: str | None = None,
                           status: str = "scheduled", **kwargs) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO iv_observations
                   (plan_id, assessor_id, observer_id, observation_date,
                    assessment_type, feedback, actions, grade, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (plan_id, assessor_id, observer_id, observation_date,
                 assessment_type, feedback, actions, grade, status),
            )
            conn.commit()
            logger.info("IV observation created for plan %d", plan_id)
            row = conn.execute(
                "SELECT * FROM iv_observations WHERE id = last_insert_rowid()"
            ).fetchone()
            return row
        except Exception as e:
            conn.rollback()
            raise InternalVerificationError(f"Failed to create observation: {e}") from e
        finally:
            conn.close()

    def update_observation(self, observation_id: int, **kwargs) -> dict:
        allowed = {"plan_id", "assessor_id", "observer_id", "observation_date",
                    "assessment_type", "feedback", "actions", "grade", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise InternalVerificationError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM iv_observations WHERE id = ?", (observation_id,)
            ).fetchone()
            if not existing:
                raise InternalVerificationError(f"Observation {observation_id} not found.")
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [observation_id]
            conn.execute(f"UPDATE iv_observations SET {sets} WHERE id = ?", vals)
            conn.commit()
            logger.info("IV observation %d updated", observation_id)
            return self.get_observation(observation_id)
        except InternalVerificationError:
            raise
        except Exception as e:
            conn.rollback()
            raise InternalVerificationError(f"Failed to update observation: {e}") from e
        finally:
            conn.close()

    def delete_observation(self, observation_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM iv_observations WHERE id = ?", (observation_id,)
            ).fetchone()
            if not existing:
                raise InternalVerificationError(f"Observation {observation_id} not found.")
            conn.execute("DELETE FROM iv_observations WHERE id = ?", (observation_id,))
            conn.commit()
            logger.info("IV observation %d deleted", observation_id)
            return True
        except InternalVerificationError:
            raise
        except Exception as e:
            conn.rollback()
            raise InternalVerificationError(f"Failed to delete observation: {e}") from e
        finally:
            conn.close()

    def complete_observation(self, observation_id: int, feedback: str,
                             grade: str, actions: str | None = None) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM iv_observations WHERE id = ?", (observation_id,)
            ).fetchone()
            if not existing:
                raise InternalVerificationError(f"Observation {observation_id} not found.")
            conn.execute(
                """UPDATE iv_observations
                   SET feedback = ?, grade = ?, actions = ?, status = 'completed'
                   WHERE id = ?""",
                (feedback, grade, actions, observation_id),
            )
            conn.commit()
            logger.info("IV observation %d completed", observation_id)
            return self.get_observation(observation_id)
        except InternalVerificationError:
            raise
        except Exception as e:
            conn.rollback()
            raise InternalVerificationError(f"Failed to complete observation: {e}") from e
        finally:
            conn.close()

    # ── Statistics ───────────────────────────────────────────────

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            plans = conn.execute("SELECT COUNT(*) AS cnt FROM iv_plans").fetchone()
            active = conn.execute(
                "SELECT COUNT(*) AS cnt FROM iv_plans WHERE status = 'active'"
            ).fetchone()
            samples_total = conn.execute(
                "SELECT COUNT(*) AS cnt FROM iv_samples"
            ).fetchone()
            samples_done = conn.execute(
                "SELECT COUNT(*) AS cnt FROM iv_samples WHERE status = 'completed'"
            ).fetchone()
            samples_action = conn.execute(
                "SELECT COUNT(*) AS cnt FROM iv_samples WHERE action_required IS NOT NULL AND action_required != ''"
            ).fetchone()
            action_completed = conn.execute(
                "SELECT COUNT(*) AS cnt FROM iv_samples WHERE action_completed = 1"
            ).fetchone()
            obs_total = conn.execute(
                "SELECT COUNT(*) AS cnt FROM iv_observations"
            ).fetchone()
            obs_done = conn.execute(
                "SELECT COUNT(*) AS cnt FROM iv_observations WHERE status = 'completed'"
            ).fetchone()
            grading_total = conn.execute(
                "SELECT COUNT(*) AS cnt FROM iv_samples WHERE status IN ('completed', 'action_required')"
            ).fetchone()
            grading_accurate = conn.execute(
                "SELECT COUNT(*) AS cnt FROM iv_samples WHERE status IN ('completed', 'action_required') AND grading_accurate = 1"
            ).fetchone()

            sa = samples_action["cnt"] or 0
            ac = action_completed["cnt"] or 0
            gt = grading_total["cnt"] or 0
            ga = grading_accurate["cnt"] or 0

            return {
                "total_plans": plans["cnt"],
                "active_plans": active["cnt"],
                "total_samples": samples_total["cnt"],
                "samples_completed": samples_done["cnt"],
                "samples_with_actions": sa,
                "action_completion_rate": round(ac / sa * 100, 1) if sa > 0 else 0.0,
                "total_observations": obs_total["cnt"],
                "observations_completed": obs_done["cnt"],
                "grading_accuracy_rate": round(ga / gt * 100, 1) if gt > 0 else 0.0,
            }
        finally:
            conn.close()
