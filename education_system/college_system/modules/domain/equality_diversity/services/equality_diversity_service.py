"""Equality & Diversity service for protected characteristics, impact assessments, and objectives."""

from education_system.college_system.core.exceptions import EqualityDiversityError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class EqualityDiversityService:
    """Equality & Diversity service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ---- Protected Characteristics ----

    def create_characteristic(self, person_type: str, person_id: int, *,
                              ethnicity: str = None, religion: str = None,
                              sexual_orientation: str = None,
                              gender_identity: str = None,
                              disability_status: str = None,
                              disability_details: str = None,
                              marital_status: str = None,
                              pregnancy_maternity: str = None,
                              preferred_pronouns: str = None,
                              consent_given: int = 1) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO protected_characteristics
                   (person_type, person_id, ethnicity, religion,
                    sexual_orientation, gender_identity, disability_status,
                    disability_details, marital_status, pregnancy_maternity,
                    preferred_pronouns, consent_given)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (person_type, person_id, ethnicity, religion,
                 sexual_orientation, gender_identity, disability_status,
                 disability_details, marital_status, pregnancy_maternity,
                 preferred_pronouns, consent_given))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM protected_characteristics WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise EqualityDiversityError(f"Failed to create record: {e}") from e
        finally:
            conn.close()

    def list_characteristics(self, *, person_type: str = None,
                             person_id: int = None,
                             limit: int = 200) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM protected_characteristics WHERE 1=1"
            params: list = []
            if person_type:
                sql += " AND person_type = ?"
                params.append(person_type)
            if person_id:
                sql += " AND person_id = ?"
                params.append(person_id)
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_characteristic(self, record_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM protected_characteristics WHERE id = ?",
                (record_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_characteristic(self, record_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {
                "ethnicity", "religion", "sexual_orientation",
                "gender_identity", "disability_status", "disability_details",
                "marital_status", "pregnancy_maternity",
                "preferred_pronouns", "consent_given",
            }
            parts, params = ["updated_at = datetime('now')"], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if len(parts) < 2:
                raise EqualityDiversityError("No valid fields to update.")
            params.append(record_id)
            conn.execute(
                f"UPDATE protected_characteristics SET {', '.join(parts)} WHERE id = ?",
                params)
            conn.commit()
            return self.get_characteristic(record_id)
        except EqualityDiversityError:
            raise
        except Exception as e:
            conn.rollback()
            raise EqualityDiversityError(f"Failed to update: {e}") from e
        finally:
            conn.close()

    def delete_characteristic(self, record_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM protected_characteristics WHERE id = ?",
                (record_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise EqualityDiversityError(f"Failed to delete: {e}") from e
        finally:
            conn.close()

    # ---- Equality Impact Assessments ----

    def create_assessment(self, policy_or_practice: str, *,
                          assessor: str = None, assessment_date: str = None,
                          protected_group: str = None,
                          potential_impact: str = None,
                          impact_type: str = "neutral",
                          mitigating_actions: str = None,
                          review_date: str = None,
                          status: str = "active") -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO equality_impact_assessments
                   (policy_or_practice, assessor, assessment_date,
                    protected_group, potential_impact, impact_type,
                    mitigating_actions, review_date, status)
                   VALUES (?, ?, COALESCE(?, date('now')), ?, ?, ?, ?, ?, ?)""",
                (policy_or_practice, assessor, assessment_date,
                 protected_group, potential_impact, impact_type,
                 mitigating_actions, review_date, status))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM equality_impact_assessments WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise EqualityDiversityError(f"Failed to create assessment: {e}") from e
        finally:
            conn.close()

    def list_assessments(self, *, status: str = None,
                         impact_type: str = None,
                         limit: int = 100) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM equality_impact_assessments WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if impact_type:
                sql += " AND impact_type = ?"
                params.append(impact_type)
            sql += " ORDER BY assessment_date DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_assessment(self, assessment_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM equality_impact_assessments WHERE id = ?",
                (assessment_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_assessment(self, assessment_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {
                "policy_or_practice", "assessor", "assessment_date",
                "protected_group", "potential_impact", "impact_type",
                "mitigating_actions", "review_date", "status",
            }
            parts, params = [], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if not parts:
                raise EqualityDiversityError("No valid fields to update.")
            params.append(assessment_id)
            conn.execute(
                f"UPDATE equality_impact_assessments SET {', '.join(parts)} WHERE id = ?",
                params)
            conn.commit()
            return self.get_assessment(assessment_id)
        except EqualityDiversityError:
            raise
        except Exception as e:
            conn.rollback()
            raise EqualityDiversityError(f"Failed to update assessment: {e}") from e
        finally:
            conn.close()

    def delete_assessment(self, assessment_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM equality_impact_assessments WHERE id = ?",
                (assessment_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise EqualityDiversityError(f"Failed to delete assessment: {e}") from e
        finally:
            conn.close()

    # ---- Equality Objectives ----

    def create_objective(self, objective: str, *,
                         protected_group: str = None, target: str = None,
                         progress: str = None, academic_year: str = None,
                         status: str = "active") -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO equality_objectives
                   (objective, protected_group, target, progress,
                    academic_year, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (objective, protected_group, target, progress,
                 academic_year, status))
            conn.commit()
            row = conn.execute(
                "SELECT * FROM equality_objectives WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise EqualityDiversityError(f"Failed to create objective: {e}") from e
        finally:
            conn.close()

    def list_objectives(self, *, status: str = None,
                        academic_year: str = None,
                        limit: int = 100) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM equality_objectives WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if academic_year:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_objective(self, objective_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM equality_objectives WHERE id = ?",
                (objective_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_objective(self, objective_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"objective", "protected_group", "target",
                        "progress", "academic_year", "status"}
            parts, params = ["updated_at = datetime('now')"], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if len(parts) < 2:
                raise EqualityDiversityError("No valid fields to update.")
            params.append(objective_id)
            conn.execute(
                f"UPDATE equality_objectives SET {', '.join(parts)} WHERE id = ?",
                params)
            conn.commit()
            return self.get_objective(objective_id)
        except EqualityDiversityError:
            raise
        except Exception as e:
            conn.rollback()
            raise EqualityDiversityError(f"Failed to update objective: {e}") from e
        finally:
            conn.close()

    def delete_objective(self, objective_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM equality_objectives WHERE id = ?",
                (objective_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise EqualityDiversityError(f"Failed to delete objective: {e}") from e
        finally:
            conn.close()

    # ---- Statistics ----

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            total_chars = conn.execute(
                "SELECT COUNT(*) FROM protected_characteristics").fetchone()[0]
            students = conn.execute(
                "SELECT COUNT(*) FROM protected_characteristics WHERE person_type = 'student'"
            ).fetchone()[0]
            staff = conn.execute(
                "SELECT COUNT(*) FROM protected_characteristics WHERE person_type = 'staff'"
            ).fetchone()[0]
            total_eia = conn.execute(
                "SELECT COUNT(*) FROM equality_impact_assessments").fetchone()[0]
            active_eia = conn.execute(
                "SELECT COUNT(*) FROM equality_impact_assessments WHERE status = 'active'"
            ).fetchone()[0]
            total_obj = conn.execute(
                "SELECT COUNT(*) FROM equality_objectives").fetchone()[0]
            active_obj = conn.execute(
                "SELECT COUNT(*) FROM equality_objectives WHERE status = 'active'"
            ).fetchone()[0]
            disability_count = conn.execute(
                """SELECT COUNT(*) FROM protected_characteristics
                   WHERE disability_status IS NOT NULL AND disability_status != ''
                     AND disability_status != 'none'"""
            ).fetchone()[0]
            return {
                "total_records": total_chars,
                "student_records": students,
                "staff_records": staff,
                "disability_declared": disability_count,
                "total_assessments": total_eia,
                "active_assessments": active_eia,
                "total_objectives": total_obj,
                "active_objectives": active_obj,
            }
        finally:
            conn.close()
