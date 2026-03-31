"""Health & Safety service layer."""

from datetime import datetime
from education_system.college_system.core.exceptions import HealthSafetyError
from education_system.college_system.infrastructure.database.db import connect

from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
import logging

logger = logging.getLogger(__name__)


class HealthSafetyService:
    """Health & Safety service covering incidents, inspections, risk assessments and compliance."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        conn = connect(self._db_path)
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        return conn

    # ── Incidents ─────────────────────────────────────────────────────────

    def list_incidents(self, status=None, incident_type=None, riddor_only=False) -> list[dict]:
        """List incidents with optional filters."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM hs_incidents WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if incident_type:
                sql += " AND incident_type = ?"
                params.append(incident_type)
            if riddor_only:
                sql += " AND riddor_reportable = 1"
            sql += " ORDER BY incident_date DESC, id DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_incident(self, incident_id: int) -> dict | None:
        """Get a single incident by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM hs_incidents WHERE id = ?", (incident_id,)).fetchone()
            return row
        finally:
            conn.close()

    def create_incident(self, incident_date: str, description: str, **kwargs) -> dict:
        """Create a new incident record."""
        conn = self._conn()
        try:
            fields = {"incident_date": incident_date, "description": description}
            allowed = {
                "reported_by", "location", "incident_type", "persons_involved",
                "injury_details", "first_aid_given", "riddor_reportable",
                "riddor_reference", "investigation_notes", "root_cause",
                "corrective_actions", "status",
            }
            for k, v in kwargs.items():
                if k in allowed and v is not None:
                    fields[k] = v
            now = datetime.now().isoformat()
            fields["created_at"] = now
            fields["updated_at"] = now
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO hs_incidents ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM hs_incidents WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Incident created: id=%d", row["id"])
            return row
        except HealthSafetyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HealthSafetyError(f"Failed to create incident: {e}") from e
        finally:
            conn.close()

    def update_incident(self, incident_id: int, **kwargs) -> dict:
        """Update an existing incident."""
        allowed = {
            "incident_date", "reported_by", "location", "incident_type",
            "description", "persons_involved", "injury_details",
            "first_aid_given", "riddor_reportable", "riddor_reference",
            "investigation_notes", "root_cause", "corrective_actions", "status",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise HealthSafetyError("No valid fields to update.")
        updates["updated_at"] = datetime.now().isoformat()
        conn = self._conn()
        try:
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            params = list(updates.values()) + [incident_id]
            conn.execute(f"UPDATE hs_incidents SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Incident updated: id=%d", incident_id)
            row = conn.execute("SELECT * FROM hs_incidents WHERE id = ?", (incident_id,)).fetchone()
            return row
        except HealthSafetyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HealthSafetyError(f"Failed to update incident: {e}") from e
        finally:
            conn.close()

    def delete_incident(self, incident_id: int) -> bool:
        """Delete an incident."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM hs_incidents WHERE id = ?", (incident_id,)).fetchone()
            if not existing:
                raise HealthSafetyError("Incident not found.")
            conn.execute("DELETE FROM hs_incidents WHERE id = ?", (incident_id,))
            conn.commit()
            logger.info("Incident deleted: id=%d", incident_id)
            return True
        except HealthSafetyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HealthSafetyError(f"Failed to delete incident: {e}") from e
        finally:
            conn.close()

    def close_incident(self, incident_id: int, root_cause: str, corrective_actions: str) -> dict:
        """Close an incident with root cause and corrective actions."""
        return self.update_incident(
            incident_id,
            root_cause=root_cause,
            corrective_actions=corrective_actions,
            status="closed",
        )

    # ── Inspections ───────────────────────────────────────────────────────

    def list_inspections(self, status=None, inspection_type=None) -> list[dict]:
        """List inspections with optional filters."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM hs_inspections WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if inspection_type:
                sql += " AND inspection_type = ?"
                params.append(inspection_type)
            sql += " ORDER BY inspection_date DESC, id DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_inspection(self, inspection_id: int) -> dict | None:
        """Get a single inspection by ID."""
        conn = self._conn()
        try:
            return conn.execute("SELECT * FROM hs_inspections WHERE id = ?", (inspection_id,)).fetchone()
        finally:
            conn.close()

    def create_inspection(self, inspection_type: str, inspection_date: str, **kwargs) -> dict:
        """Create a new inspection record."""
        conn = self._conn()
        try:
            fields = {"inspection_type": inspection_type, "inspection_date": inspection_date}
            allowed = {
                "area", "inspector", "next_due_date", "findings",
                "actions_required", "certificate_ref", "status",
            }
            for k, v in kwargs.items():
                if k in allowed and v is not None:
                    fields[k] = v
            fields["created_at"] = datetime.now().isoformat()
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO hs_inspections ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM hs_inspections WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Inspection created: id=%d", row["id"])
            return row
        except HealthSafetyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HealthSafetyError(f"Failed to create inspection: {e}") from e
        finally:
            conn.close()

    def update_inspection(self, inspection_id: int, **kwargs) -> dict:
        """Update an existing inspection."""
        allowed = {
            "inspection_type", "area", "inspector", "inspection_date",
            "next_due_date", "findings", "actions_required",
            "certificate_ref", "status",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise HealthSafetyError("No valid fields to update.")
        conn = self._conn()
        try:
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            params = list(updates.values()) + [inspection_id]
            conn.execute(f"UPDATE hs_inspections SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Inspection updated: id=%d", inspection_id)
            return conn.execute("SELECT * FROM hs_inspections WHERE id = ?", (inspection_id,)).fetchone()
        except HealthSafetyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HealthSafetyError(f"Failed to update inspection: {e}") from e
        finally:
            conn.close()

    def delete_inspection(self, inspection_id: int) -> bool:
        """Delete an inspection."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM hs_inspections WHERE id = ?", (inspection_id,)).fetchone()
            if not existing:
                raise HealthSafetyError("Inspection not found.")
            conn.execute("DELETE FROM hs_inspections WHERE id = ?", (inspection_id,))
            conn.commit()
            logger.info("Inspection deleted: id=%d", inspection_id)
            return True
        except HealthSafetyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HealthSafetyError(f"Failed to delete inspection: {e}") from e
        finally:
            conn.close()

    # ── Risk Assessments ──────────────────────────────────────────────────

    def list_risk_assessments(self, status=None, risk_rating=None) -> list[dict]:
        """List risk assessments with optional filters."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM hs_risk_assessments WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if risk_rating:
                sql += " AND risk_rating = ?"
                params.append(risk_rating)
            sql += " ORDER BY assessment_date DESC, id DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_risk_assessment(self, assessment_id: int) -> dict | None:
        """Get a single risk assessment by ID."""
        conn = self._conn()
        try:
            return conn.execute("SELECT * FROM hs_risk_assessments WHERE id = ?", (assessment_id,)).fetchone()
        finally:
            conn.close()

    def create_risk_assessment(self, activity: str, assessment_date: str, **kwargs) -> dict:
        """Create a new risk assessment."""
        conn = self._conn()
        try:
            fields = {"activity": activity, "assessment_date": assessment_date}
            allowed = {
                "location", "assessor", "hazards", "persons_at_risk",
                "existing_controls", "risk_rating", "additional_controls",
                "review_date", "status",
            }
            for k, v in kwargs.items():
                if k in allowed and v is not None:
                    fields[k] = v
            now = datetime.now().isoformat()
            fields["created_at"] = now
            fields["updated_at"] = now
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO hs_risk_assessments ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM hs_risk_assessments WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Risk assessment created: id=%d", row["id"])
            return row
        except HealthSafetyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HealthSafetyError(f"Failed to create risk assessment: {e}") from e
        finally:
            conn.close()

    def update_risk_assessment(self, assessment_id: int, **kwargs) -> dict:
        """Update an existing risk assessment."""
        allowed = {
            "activity", "location", "assessor", "assessment_date", "hazards",
            "persons_at_risk", "existing_controls", "risk_rating",
            "additional_controls", "review_date", "status",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise HealthSafetyError("No valid fields to update.")
        updates["updated_at"] = datetime.now().isoformat()
        conn = self._conn()
        try:
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            params = list(updates.values()) + [assessment_id]
            conn.execute(f"UPDATE hs_risk_assessments SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Risk assessment updated: id=%d", assessment_id)
            return conn.execute("SELECT * FROM hs_risk_assessments WHERE id = ?", (assessment_id,)).fetchone()
        except HealthSafetyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HealthSafetyError(f"Failed to update risk assessment: {e}") from e
        finally:
            conn.close()

    def delete_risk_assessment(self, assessment_id: int) -> bool:
        """Delete a risk assessment."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM hs_risk_assessments WHERE id = ?", (assessment_id,)).fetchone()
            if not existing:
                raise HealthSafetyError("Risk assessment not found.")
            conn.execute("DELETE FROM hs_risk_assessments WHERE id = ?", (assessment_id,))
            conn.commit()
            logger.info("Risk assessment deleted: id=%d", assessment_id)
            return True
        except HealthSafetyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HealthSafetyError(f"Failed to delete risk assessment: {e}") from e
        finally:
            conn.close()

    # ── Compliance Checks ─────────────────────────────────────────────────

    def list_compliance_checks(self, status=None) -> list[dict]:
        """List compliance checks with optional status filter."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM hs_compliance_checks WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY next_due ASC, id DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_compliance_check(self, check_id: int) -> dict | None:
        """Get a single compliance check by ID."""
        conn = self._conn()
        try:
            return conn.execute("SELECT * FROM hs_compliance_checks WHERE id = ?", (check_id,)).fetchone()
        finally:
            conn.close()

    def create_compliance_check(self, check_type: str, **kwargs) -> dict:
        """Create a new compliance check."""
        conn = self._conn()
        try:
            fields = {"check_type": check_type}
            allowed = {
                "description", "responsible_person", "frequency",
                "last_completed", "next_due", "certificate_ref",
                "provider", "status", "notes",
            }
            for k, v in kwargs.items():
                if k in allowed and v is not None:
                    fields[k] = v
            fields["created_at"] = datetime.now().isoformat()
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO hs_compliance_checks ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM hs_compliance_checks WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Compliance check created: id=%d", row["id"])
            return row
        except HealthSafetyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HealthSafetyError(f"Failed to create compliance check: {e}") from e
        finally:
            conn.close()

    def update_compliance_check(self, check_id: int, **kwargs) -> dict:
        """Update an existing compliance check."""
        allowed = {
            "check_type", "description", "responsible_person", "frequency",
            "last_completed", "next_due", "certificate_ref",
            "provider", "status", "notes",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise HealthSafetyError("No valid fields to update.")
        conn = self._conn()
        try:
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            params = list(updates.values()) + [check_id]
            conn.execute(f"UPDATE hs_compliance_checks SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Compliance check updated: id=%d", check_id)
            return conn.execute("SELECT * FROM hs_compliance_checks WHERE id = ?", (check_id,)).fetchone()
        except HealthSafetyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HealthSafetyError(f"Failed to update compliance check: {e}") from e
        finally:
            conn.close()

    def delete_compliance_check(self, check_id: int) -> bool:
        """Delete a compliance check."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM hs_compliance_checks WHERE id = ?", (check_id,)).fetchone()
            if not existing:
                raise HealthSafetyError("Compliance check not found.")
            conn.execute("DELETE FROM hs_compliance_checks WHERE id = ?", (check_id,))
            conn.commit()
            logger.info("Compliance check deleted: id=%d", check_id)
            return True
        except HealthSafetyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HealthSafetyError(f"Failed to delete compliance check: {e}") from e
        finally:
            conn.close()

    def get_overdue_checks(self) -> list[dict]:
        """Return compliance checks that are overdue."""
        conn = self._conn()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            return conn.execute(
                "SELECT * FROM hs_compliance_checks WHERE next_due < ? AND status != 'expired' ORDER BY next_due ASC",
                (today,),
            ).fetchall()
        finally:
            conn.close()

    # ── Statistics ────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return summary statistics across all H&S tables."""
        conn = self._conn()
        try:
            stats: dict = {}

            # Incidents
            row = conn.execute("SELECT COUNT(*) as cnt FROM hs_incidents").fetchone()
            stats["total_incidents"] = row["cnt"]
            row = conn.execute("SELECT COUNT(*) as cnt FROM hs_incidents WHERE status = 'open'").fetchone()
            stats["open_incidents"] = row["cnt"]
            row = conn.execute("SELECT COUNT(*) as cnt FROM hs_incidents WHERE riddor_reportable = 1").fetchone()
            stats["riddor_count"] = row["cnt"]
            rows = conn.execute(
                "SELECT incident_type, COUNT(*) as cnt FROM hs_incidents GROUP BY incident_type"
            ).fetchall()
            stats["by_type"] = {r["incident_type"]: r["cnt"] for r in rows}

            # Inspections
            row = conn.execute("SELECT COUNT(*) as cnt FROM hs_inspections").fetchone()
            stats["total_inspections"] = row["cnt"]
            row = conn.execute("SELECT COUNT(*) as cnt FROM hs_inspections WHERE status = 'failed'").fetchone()
            stats["failed_inspections"] = row["cnt"]

            # Risk assessments
            row = conn.execute("SELECT COUNT(*) as cnt FROM hs_risk_assessments").fetchone()
            stats["total_risk_assessments"] = row["cnt"]
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM hs_risk_assessments WHERE risk_rating IN ('high', 'very_high')"
            ).fetchone()
            stats["high_risk_count"] = row["cnt"]

            # Compliance
            row = conn.execute("SELECT COUNT(*) as cnt FROM hs_compliance_checks").fetchone()
            stats["total_compliance"] = row["cnt"]
            today = datetime.now().strftime("%Y-%m-%d")
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM hs_compliance_checks WHERE next_due < ? AND status != 'expired'",
                (today,),
            ).fetchone()
            stats["overdue_compliance"] = row["cnt"]

            return stats
        finally:
            conn.close()
