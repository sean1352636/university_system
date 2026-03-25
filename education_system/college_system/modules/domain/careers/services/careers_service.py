"""Careers service for managing careers activities, UCAS, and work experience."""

from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.exceptions import CareersError


class CareersService:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # --- Careers Activities ---

    def create_activity(self, student_id: int, activity_type: str = "encounter",
                         description: str = None,
                         activity_date: str = None,
                         gatsby_benchmark: int = None,
                         provider: str = None,
                         duration_minutes: int = None,
                         recorded_by: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO careers_activities
                   (student_id, activity_type, description,
                    activity_date, gatsby_benchmark, provider,
                    duration_minutes, recorded_by)
                   VALUES (?, ?, ?, COALESCE(?, date('now')), ?, ?, ?, ?)""",
                (student_id, activity_type, description,
                 activity_date, gatsby_benchmark, provider,
                 duration_minutes, recorded_by),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM careers_activities WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise CareersError(f"Failed to create activity: {e}")
        finally:
            conn.close()

    def list_activities(self, student_id: int = None, activity_type: str = None,
                         limit: int = 100) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT ca.*, s.first_name, s.last_name FROM careers_activities ca
                       LEFT JOIN students s ON ca.student_id = s.id WHERE 1=1"""
            params = []
            if student_id:
                query += " AND ca.student_id = ?"
                params.append(student_id)
            if activity_type:
                query += " AND ca.activity_type = ?"
                params.append(activity_type)
            query += " ORDER BY ca.activity_date DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_record(self, record_id: int) -> bool:
        """Delete a careers activity by ID."""
        conn = self._conn()
        try:
            result = conn.execute(
                "DELETE FROM careers_activities WHERE id = ?", (record_id,)
            )
            conn.commit()
            if result.rowcount == 0:
                raise CareersError(f"Careers record {record_id} not found.")
            return True
        except CareersError:
            raise
        except Exception as e:
            conn.rollback()
            raise CareersError(f"Failed to delete careers record: {e}")
        finally:
            conn.close()

    # --- UCAS Records ---

    def create_ucas_record(self, student_id: int, ucas_id: str = None,
                            personal_statement_status: str = "not_started",
                            reference_status: str = "not_started",
                            predicted_grades: str = None,
                            choices: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO ucas_records
                   (student_id, ucas_id, personal_statement_status,
                    reference_status, predicted_grades, choices)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (student_id, ucas_id, personal_statement_status,
                 reference_status, predicted_grades, choices),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM ucas_records WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise CareersError(f"Failed to create UCAS record: {e}")
        finally:
            conn.close()

    def get_ucas_record(self, student_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM ucas_records WHERE student_id = ?", (student_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_ucas_records(self, application_status: str = None) -> list[dict]:
        conn = self._conn()
        try:
            query = """SELECT ur.*, s.first_name, s.last_name FROM ucas_records ur
                       LEFT JOIN students s ON ur.student_id = s.id WHERE 1=1"""
            params = []
            if application_status:
                query += " AND ur.application_status = ?"
                params.append(application_status)
            query += " ORDER BY s.last_name"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_ucas_record(self, record_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"ucas_id", "personal_statement_status", "reference_status",
                        "predicted_grades", "choices", "application_status",
                        "firm_choice", "insurance_choice"}
            parts, params = ["updated_at = datetime('now')"], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if len(parts) < 2:
                raise CareersError("No valid fields to update")
            params.append(record_id)
            conn.execute(f"UPDATE ucas_records SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            row = conn.execute("SELECT * FROM ucas_records WHERE id = ?", (record_id,)).fetchone()
            return dict(row) if row else {}
        except CareersError:
            raise
        except Exception as e:
            raise CareersError(f"Failed to update UCAS record: {e}")
        finally:
            conn.close()

    # --- Work Experience ---

    def create_work_experience(self, student_id: int, employer_name: str,
                                 employer_contact: str = None,
                                 placement_address: str = None,
                                 start_date: str = None,
                                 end_date: str = None,
                                 hours_per_week: int = None,
                                 role: str = None,
                                 dbs_checked: int = 0,
                                 risk_assessment: int = 0,
                                 insurance_confirmed: int = 0,
                                 status: str = "planned") -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO work_experience
                   (student_id, employer_name, employer_contact, placement_address,
                    start_date, end_date, hours_per_week, role,
                    dbs_checked, risk_assessment, insurance_confirmed, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, employer_name, employer_contact, placement_address,
                 start_date, end_date, hours_per_week, role,
                 dbs_checked, risk_assessment, insurance_confirmed, status),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM work_experience WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise CareersError(f"Failed to create work experience: {e}")
        finally:
            conn.close()

    def list_work_experience(self, student_id: int = None) -> list[dict]:
        conn = self._conn()
        try:
            if student_id:
                rows = conn.execute(
                    """SELECT we.*, s.first_name, s.last_name FROM work_experience we
                       LEFT JOIN students s ON we.student_id = s.id
                       WHERE we.student_id = ? ORDER BY we.start_date DESC""",
                    (student_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT we.*, s.first_name, s.last_name FROM work_experience we
                       LEFT JOIN students s ON we.student_id = s.id
                       ORDER BY we.start_date DESC"""
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_work_experience(self, record_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"employer_name", "employer_contact", "placement_address",
                        "start_date", "end_date", "hours_per_week", "role",
                        "dbs_checked", "risk_assessment", "insurance_confirmed",
                        "status", "student_evaluation", "employer_evaluation"}
            parts, params = [], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if not parts:
                raise CareersError("No valid fields to update")
            params.append(record_id)
            conn.execute(f"UPDATE work_experience SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            row = conn.execute("SELECT * FROM work_experience WHERE id = ?", (record_id,)).fetchone()
            return dict(row) if row else {}
        except CareersError:
            raise
        except Exception as e:
            raise CareersError(f"Failed to update work experience: {e}")
        finally:
            conn.close()
