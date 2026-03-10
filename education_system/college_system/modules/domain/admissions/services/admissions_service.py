"""Admissions service for managing applications, inductions, and withdrawals."""

from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.exceptions import AdmissionsError


class AdmissionsService:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # --- Applications ---

    def create_application(self, applicant_name: str, date_of_birth: str = None,
                           email: str = None, phone: str = None,
                           course_preferences: str = None, previous_school: str = None,
                           gcse_results: str = None, personal_statement: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO applications
                   (applicant_name, date_of_birth, email, phone, course_preferences,
                    previous_school, gcse_results, personal_statement)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (applicant_name, date_of_birth, email, phone, course_preferences,
                 previous_school, gcse_results, personal_statement),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM applications WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise AdmissionsError(f"Failed to create application: {e}")
        finally:
            conn.close()

    def list_applications(self, status: str = None, limit: int = 100) -> list[dict]:
        conn = self._conn()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM applications WHERE status = ? ORDER BY applied_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM applications ORDER BY applied_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_application(self, application_id: int) -> dict:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM applications WHERE id = ?", (application_id,)
            ).fetchone()
            if not row:
                raise AdmissionsError(f"Application {application_id} not found")
            return dict(row)
        finally:
            conn.close()

    def update_application_status(self, application_id: int, status: str,
                                   notes: str = None) -> dict:
        conn = self._conn()
        try:
            parts, params = ["status = ?", "updated_at = datetime('now')"], [status]
            if notes is not None:
                parts.append("notes = ?")
                params.append(notes)
            params.append(application_id)
            conn.execute(
                f"UPDATE applications SET {', '.join(parts)} WHERE id = ?", params
            )
            conn.commit()
            return self.get_application(application_id)
        except AdmissionsError:
            raise
        except Exception as e:
            raise AdmissionsError(f"Failed to update application: {e}")
        finally:
            conn.close()

    # --- Inductions ---

    def create_induction(self, student_id: int, emergency_contact: str = None,
                          medical_info: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO inductions (student_id, emergency_contact, medical_info)
                   VALUES (?, ?, ?)""",
                (student_id, emergency_contact, medical_info),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM inductions WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise AdmissionsError(f"Failed to create induction: {e}")
        finally:
            conn.close()

    def list_inductions(self, status: str = None) -> list[dict]:
        conn = self._conn()
        try:
            if status:
                rows = conn.execute(
                    "SELECT i.*, s.first_name, s.last_name FROM inductions i LEFT JOIN students s ON i.student_id = s.id WHERE i.status = ? ORDER BY i.created_at",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT i.*, s.first_name, s.last_name FROM inductions i LEFT JOIN students s ON i.student_id = s.id ORDER BY i.created_at"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_induction(self, induction_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"status", "consent_form", "learning_agreement", "photo_id",
                        "ict_acceptable_use", "emergency_contact", "medical_info"}
            parts, params = [], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if not parts:
                raise AdmissionsError("No valid fields to update")
            params.append(induction_id)
            conn.execute(f"UPDATE inductions SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            row = conn.execute("SELECT * FROM inductions WHERE id = ?", (induction_id,)).fetchone()
            return dict(row) if row else {}
        except AdmissionsError:
            raise
        except Exception as e:
            raise AdmissionsError(f"Failed to update induction: {e}")
        finally:
            conn.close()

    # --- Withdrawals ---

    def create_withdrawal(self, student_id: int, reason: str,
                           withdrawal_date: str = None, destination: str = None,
                           notes: str = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO withdrawals (student_id, reason, withdrawal_date, destination, notes)
                   VALUES (?, ?, COALESCE(?, date('now')), ?, ?)""",
                (student_id, reason, withdrawal_date, destination, notes),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM withdrawals WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            raise AdmissionsError(f"Failed to create withdrawal: {e}")
        finally:
            conn.close()

    def list_withdrawals(self, limit: int = 100) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT w.*, s.first_name, s.last_name FROM withdrawals w
                   LEFT JOIN students s ON w.student_id = s.id
                   ORDER BY w.withdrawal_date DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_withdrawal(self, withdrawal_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            allowed = {"exit_interview", "destination", "destination_type", "notes"}
            parts, params = [], []
            for k, v in kwargs.items():
                if k in allowed:
                    parts.append(f"{k} = ?")
                    params.append(v)
            if not parts:
                raise AdmissionsError("No valid fields to update")
            params.append(withdrawal_id)
            conn.execute(f"UPDATE withdrawals SET {', '.join(parts)} WHERE id = ?", params)
            conn.commit()
            row = conn.execute("SELECT * FROM withdrawals WHERE id = ?", (withdrawal_id,)).fetchone()
            return dict(row) if row else {}
        except AdmissionsError:
            raise
        except Exception as e:
            raise AdmissionsError(f"Failed to update withdrawal: {e}")
        finally:
            conn.close()
