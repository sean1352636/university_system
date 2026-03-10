"""Study Programmes service layer."""

from education_system.college_system.core.exceptions import StudyProgrammeError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class StudyProgrammesService:
    """Service for managing 16-19 study programmes, components, validation, and reporting."""

    PROGRAMME_TYPES = ("level3", "level2", "level1", "entry", "traineeship", "t_level")
    PROGRAMME_STATUSES = ("active", "completed", "withdrawn", "transferred")
    REQUIREMENT_STATUSES = ("not_met", "met", "exempt", "enrolled")
    COMPONENT_TYPES = ("qualification", "work_experience", "enrichment",
                       "tutorial", "maths_english", "pastoral")
    COMPONENT_STATUSES = ("active", "completed", "withdrawn")

    # Minimum planned hours per programme type (ESFA guidance)
    MIN_PLANNED_HOURS = {
        "level3": 540,
        "level2": 540,
        "level1": 540,
        "entry": 540,
        "traineeship": 280,
        "t_level": 900,
    }

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        conn = connect(self._db_path)
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        return conn

    # ----------------------------------------------------------------
    # Programmes CRUD
    # ----------------------------------------------------------------

    def list_programmes(self, status: str | None = None,
                        programme_type: str | None = None,
                        academic_year: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT sp.*, s.first_name, s.last_name, s.student_id AS student_code
                     FROM study_programmes sp
                     LEFT JOIN students s ON sp.student_id = s.id
                     WHERE 1=1"""
            params: list = []
            if status:
                sql += " AND sp.status = ?"
                params.append(status)
            if programme_type:
                sql += " AND sp.programme_type = ?"
                params.append(programme_type)
            if academic_year:
                sql += " AND sp.academic_year = ?"
                params.append(academic_year)
            sql += " ORDER BY sp.created_at DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_programme(self, programme_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT sp.*, s.first_name, s.last_name, s.student_id AS student_code
                   FROM study_programmes sp
                   LEFT JOIN students s ON sp.student_id = s.id
                   WHERE sp.id = ?""",
                (programme_id,),
            ).fetchone()
            return row if row else None
        finally:
            conn.close()

    def create_programme(self, student_id: int, **kwargs) -> dict:
        allowed = {"academic_year", "programme_type", "substantive_qualification",
                    "maths_requirement", "maths_enrollment_id",
                    "english_requirement", "english_enrollment_id",
                    "work_experience_completed", "work_experience_hours",
                    "enrichment_hours", "tutorial_hours",
                    "total_planned_hours", "total_delivered_hours",
                    "is_valid", "validation_notes", "status"}
        fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        fields["student_id"] = student_id
        conn = self._conn()
        try:
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO study_programmes ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM study_programmes WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Study programme created: id=%d student=%d", row["id"], student_id)
            return row
        except Exception as e:
            conn.rollback()
            raise StudyProgrammeError(f"Failed to create programme: {e}") from e
        finally:
            conn.close()

    def update_programme(self, programme_id: int, **kwargs) -> dict:
        allowed = {"academic_year", "programme_type", "substantive_qualification",
                    "maths_requirement", "maths_enrollment_id",
                    "english_requirement", "english_enrollment_id",
                    "work_experience_completed", "work_experience_hours",
                    "enrichment_hours", "tutorial_hours",
                    "total_planned_hours", "total_delivered_hours",
                    "is_valid", "validation_notes", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise StudyProgrammeError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM study_programmes WHERE id = ?", (programme_id,)
            ).fetchone()
            if not existing:
                raise StudyProgrammeError("Programme not found.")
            updates["updated_at"] = "datetime('now')"
            set_parts = []
            vals: list = []
            for k, v in updates.items():
                if k == "updated_at":
                    set_parts.append("updated_at = datetime('now')")
                else:
                    set_parts.append(f"{k} = ?")
                    vals.append(v)
            vals.append(programme_id)
            conn.execute(
                f"UPDATE study_programmes SET {', '.join(set_parts)} WHERE id = ?",
                vals,
            )
            conn.commit()
            logger.info("Study programme updated: id=%d", programme_id)
            return conn.execute(
                "SELECT * FROM study_programmes WHERE id = ?", (programme_id,)
            ).fetchone()
        except StudyProgrammeError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudyProgrammeError(f"Failed to update programme: {e}") from e
        finally:
            conn.close()

    def delete_programme(self, programme_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM study_programmes WHERE id = ?", (programme_id,)
            ).fetchone()
            if not existing:
                raise StudyProgrammeError("Programme not found.")
            conn.execute(
                "DELETE FROM study_programme_components WHERE programme_id = ?",
                (programme_id,),
            )
            conn.execute(
                "DELETE FROM study_programmes WHERE id = ?", (programme_id,)
            )
            conn.commit()
            logger.info("Study programme deleted (cascade): id=%d", programme_id)
            return True
        except StudyProgrammeError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudyProgrammeError(f"Failed to delete programme: {e}") from e
        finally:
            conn.close()

    # ----------------------------------------------------------------
    # Components CRUD
    # ----------------------------------------------------------------

    def list_components(self, programme_id: int | None = None,
                        component_type: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM study_programme_components WHERE 1=1"
            params: list = []
            if programme_id:
                sql += " AND programme_id = ?"
                params.append(programme_id)
            if component_type:
                sql += " AND component_type = ?"
                params.append(component_type)
            sql += " ORDER BY created_at DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_component(self, component_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM study_programme_components WHERE id = ?",
                (component_id,),
            ).fetchone()
            return row if row else None
        finally:
            conn.close()

    def create_component(self, programme_id: int, component_type: str,
                         component_name: str, **kwargs) -> dict:
        allowed = {"planned_hours", "delivered_hours", "status"}
        fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        fields["programme_id"] = programme_id
        fields["component_type"] = component_type
        fields["component_name"] = component_name
        conn = self._conn()
        try:
            # Verify programme exists
            prog = conn.execute(
                "SELECT id FROM study_programmes WHERE id = ?", (programme_id,)
            ).fetchone()
            if not prog:
                raise StudyProgrammeError("Programme not found.")
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO study_programme_components ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM study_programme_components WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Component created: id=%d programme=%d type=%s",
                        row["id"], programme_id, component_type)
            return row
        except StudyProgrammeError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudyProgrammeError(f"Failed to create component: {e}") from e
        finally:
            conn.close()

    def update_component(self, component_id: int, **kwargs) -> dict:
        allowed = {"component_type", "component_name", "planned_hours",
                    "delivered_hours", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise StudyProgrammeError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM study_programme_components WHERE id = ?",
                (component_id,),
            ).fetchone()
            if not existing:
                raise StudyProgrammeError("Component not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE study_programme_components SET {set_parts} WHERE id = ?",
                (*updates.values(), component_id),
            )
            conn.commit()
            logger.info("Component updated: id=%d", component_id)
            return conn.execute(
                "SELECT * FROM study_programme_components WHERE id = ?",
                (component_id,),
            ).fetchone()
        except StudyProgrammeError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudyProgrammeError(f"Failed to update component: {e}") from e
        finally:
            conn.close()

    def delete_component(self, component_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM study_programme_components WHERE id = ?",
                (component_id,),
            ).fetchone()
            if not existing:
                raise StudyProgrammeError("Component not found.")
            conn.execute(
                "DELETE FROM study_programme_components WHERE id = ?",
                (component_id,),
            )
            conn.commit()
            logger.info("Component deleted: id=%d", component_id)
            return True
        except StudyProgrammeError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudyProgrammeError(f"Failed to delete component: {e}") from e
        finally:
            conn.close()

    # ----------------------------------------------------------------
    # Validation
    # ----------------------------------------------------------------

    def validate_programme(self, programme_id: int) -> dict:
        """Validate a study programme against ESFA condition of funding rules.

        Checks:
        - Maths requirement met/exempt/enrolled
        - English requirement met/exempt/enrolled
        - Total planned hours meet minimum for programme type
        - Work experience completed (for applicable types)
        Sets is_valid and validation_notes on the programme.
        """
        conn = self._conn()
        try:
            prog = conn.execute(
                "SELECT * FROM study_programmes WHERE id = ?", (programme_id,)
            ).fetchone()
            if not prog:
                raise StudyProgrammeError("Programme not found.")

            issues: list[str] = []

            # Check maths requirement
            if prog["maths_requirement"] == "not_met":
                issues.append("Maths requirement not met (must be met, exempt, or enrolled)")

            # Check english requirement
            if prog["english_requirement"] == "not_met":
                issues.append("English requirement not met (must be met, exempt, or enrolled)")

            # Check minimum planned hours
            min_hours = self.MIN_PLANNED_HOURS.get(prog["programme_type"], 540)
            if prog["total_planned_hours"] < min_hours:
                issues.append(
                    f"Planned hours ({prog['total_planned_hours']}) below minimum "
                    f"({min_hours}) for {prog['programme_type']}"
                )

            # Check work experience (required for most programme types)
            if prog["programme_type"] in ("level3", "level2", "level1", "t_level"):
                if not prog["work_experience_completed"]:
                    issues.append("Work experience not completed")

            is_valid = 1 if not issues else 0
            notes = "; ".join(issues) if issues else "All conditions met"

            conn.execute(
                """UPDATE study_programmes
                   SET is_valid = ?, validation_notes = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (is_valid, notes, programme_id),
            )
            conn.commit()
            logger.info("Programme validated: id=%d valid=%s", programme_id, bool(is_valid))
            return conn.execute(
                "SELECT * FROM study_programmes WHERE id = ?", (programme_id,)
            ).fetchone()
        except StudyProgrammeError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudyProgrammeError(f"Validation failed: {e}") from e
        finally:
            conn.close()

    # ----------------------------------------------------------------
    # Hours
    # ----------------------------------------------------------------

    def update_delivered_hours(self, programme_id: int) -> dict:
        """Recalculate total_delivered_hours from component delivered_hours."""
        conn = self._conn()
        try:
            prog = conn.execute(
                "SELECT id FROM study_programmes WHERE id = ?", (programme_id,)
            ).fetchone()
            if not prog:
                raise StudyProgrammeError("Programme not found.")
            row = conn.execute(
                """SELECT COALESCE(SUM(delivered_hours), 0) AS total
                   FROM study_programme_components
                   WHERE programme_id = ? AND status != 'withdrawn'""",
                (programme_id,),
            ).fetchone()
            total = row["total"]
            conn.execute(
                """UPDATE study_programmes
                   SET total_delivered_hours = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (total, programme_id),
            )
            conn.commit()
            logger.info("Delivered hours updated: programme=%d total=%d", programme_id, total)
            return conn.execute(
                "SELECT * FROM study_programmes WHERE id = ?", (programme_id,)
            ).fetchone()
        except StudyProgrammeError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudyProgrammeError(f"Failed to update delivered hours: {e}") from e
        finally:
            conn.close()

    def get_hours_summary(self, programme_id: int) -> dict:
        """Breakdown of planned and delivered hours by component type."""
        conn = self._conn()
        try:
            prog = conn.execute(
                "SELECT id, total_planned_hours, total_delivered_hours FROM study_programmes WHERE id = ?",
                (programme_id,),
            ).fetchone()
            if not prog:
                raise StudyProgrammeError("Programme not found.")
            rows = conn.execute(
                """SELECT component_type,
                          COUNT(*) AS count,
                          COALESCE(SUM(planned_hours), 0) AS planned,
                          COALESCE(SUM(delivered_hours), 0) AS delivered
                   FROM study_programme_components
                   WHERE programme_id = ?
                   GROUP BY component_type""",
                (programme_id,),
            ).fetchall()
            return {
                "programme_id": programme_id,
                "total_planned_hours": prog["total_planned_hours"],
                "total_delivered_hours": prog["total_delivered_hours"],
                "by_type": rows,
            }
        finally:
            conn.close()

    # ----------------------------------------------------------------
    # Reporting
    # ----------------------------------------------------------------

    def condition_of_funding_check(self) -> list[dict]:
        """Return programmes where maths or english requirement is not met."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT sp.*, s.first_name, s.last_name, s.student_id AS student_code
                   FROM study_programmes sp
                   LEFT JOIN students s ON sp.student_id = s.id
                   WHERE sp.status = 'active'
                     AND (sp.maths_requirement = 'not_met'
                          OR sp.english_requirement = 'not_met')
                   ORDER BY s.last_name, s.first_name"""
            ).fetchall()
            return rows
        finally:
            conn.close()

    def funding_hours_report(self, academic_year: str | None = None) -> list[dict]:
        """Summary of planned vs delivered hours per programme."""
        conn = self._conn()
        try:
            sql = """SELECT sp.id, sp.student_id, s.first_name, s.last_name,
                            s.student_id AS student_code,
                            sp.programme_type, sp.academic_year,
                            sp.total_planned_hours, sp.total_delivered_hours,
                            sp.is_valid, sp.status
                     FROM study_programmes sp
                     LEFT JOIN students s ON sp.student_id = s.id
                     WHERE 1=1"""
            params: list = []
            if academic_year:
                sql += " AND sp.academic_year = ?"
                params.append(academic_year)
            sql += " ORDER BY s.last_name, s.first_name"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    # ----------------------------------------------------------------
    # Statistics
    # ----------------------------------------------------------------

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            total = conn.execute(
                "SELECT COUNT(*) AS cnt FROM study_programmes"
            ).fetchone()["cnt"]
            active = conn.execute(
                "SELECT COUNT(*) AS cnt FROM study_programmes WHERE status = 'active'"
            ).fetchone()["cnt"]

            # By type
            type_rows = conn.execute(
                """SELECT programme_type, COUNT(*) AS cnt
                   FROM study_programmes GROUP BY programme_type"""
            ).fetchall()
            by_type = {r["programme_type"]: r["cnt"] for r in type_rows}

            # By status
            status_rows = conn.execute(
                """SELECT status, COUNT(*) AS cnt
                   FROM study_programmes GROUP BY status"""
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in status_rows}

            # Valid / invalid
            valid = conn.execute(
                "SELECT COUNT(*) AS cnt FROM study_programmes WHERE is_valid = 1"
            ).fetchone()["cnt"]
            invalid = conn.execute(
                "SELECT COUNT(*) AS cnt FROM study_programmes WHERE is_valid = 0"
            ).fetchone()["cnt"]

            # Average hours
            avgs = conn.execute(
                """SELECT COALESCE(AVG(total_planned_hours), 0) AS avg_planned,
                          COALESCE(AVG(total_delivered_hours), 0) AS avg_delivered
                   FROM study_programmes"""
            ).fetchone()

            # Maths / English met percentages
            if total > 0:
                maths_met = conn.execute(
                    """SELECT COUNT(*) AS cnt FROM study_programmes
                       WHERE maths_requirement IN ('met', 'exempt')"""
                ).fetchone()["cnt"]
                english_met = conn.execute(
                    """SELECT COUNT(*) AS cnt FROM study_programmes
                       WHERE english_requirement IN ('met', 'exempt')"""
                ).fetchone()["cnt"]
                maths_met_pct = round(maths_met / total * 100, 1)
                english_met_pct = round(english_met / total * 100, 1)
            else:
                maths_met_pct = 0.0
                english_met_pct = 0.0

            return {
                "total_programmes": total,
                "active_programmes": active,
                "by_type": by_type,
                "by_status": by_status,
                "valid_programmes": valid,
                "invalid_programmes": invalid,
                "avg_planned_hours": round(avgs["avg_planned"], 1),
                "avg_delivered_hours": round(avgs["avg_delivered"], 1),
                "maths_met_pct": maths_met_pct,
                "english_met_pct": english_met_pct,
            }
        finally:
            conn.close()
