"""UCAS Applications service."""

from education_system.college_system.core.exceptions import UCASError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class UCASService:
    """UCAS Applications service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_application(self, student_id: int, academic_year: str | None = None,
                           ucas_id: str | None = None, notes: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO ucas_applications (student_id, academic_year, ucas_id, notes)
                   VALUES (?, ?, ?, ?)""",
                (student_id, academic_year, ucas_id, notes),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM ucas_applications WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise UCASError(f"Failed to create application: {e}") from e
        finally:
            conn.close()

    def list_applications(self, academic_year: str | None = None,
                          status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT a.*, s.first_name, s.last_name, s.student_id as sid FROM ucas_applications a JOIN students s ON a.student_id = s.id WHERE 1=1"
            params: list = []
            if academic_year:
                sql += " AND a.academic_year = ?"
                params.append(academic_year)
            if status:
                sql += " AND a.application_status = ?"
                params.append(status)
            sql += " ORDER BY a.created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_application(self, app_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM ucas_applications WHERE id = ?", (app_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_application(self, app_id: int, **updates) -> dict:
        set_parts: list[str] = []
        vals: list = []
        for col in ("application_status", "notes", "personal_statement_status",
                    "predicted_tariff", "reference_status", "ucas_id"):
            if col in updates and updates[col] is not None:
                set_parts.append(f"{col} = ?")
                vals.append(updates[col])
        if not set_parts:
            raise UCASError("No valid fields to update.")
        conn = self._conn()
        try:
            sets = ", ".join(set_parts)
            vals.append(app_id)
            conn.execute(f"UPDATE ucas_applications SET {sets}, updated_at = datetime('now') WHERE id = ?", vals)
            conn.commit()
            return self.get_application(app_id)
        except Exception as e:
            conn.rollback()
            raise UCASError(f"Failed to update application: {e}") from e
        finally:
            conn.close()

    def submit_application(self, app_id: int) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE ucas_applications SET application_status = 'submitted', submitted_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
                (app_id,),
            )
            conn.commit()
            return self.get_application(app_id)
        except Exception as e:
            conn.rollback()
            raise UCASError(f"Failed to submit application: {e}") from e
        finally:
            conn.close()

    def add_choice(self, application_id: int, university_name: str, course_title: str,
                   ucas_code: str | None = None, choice_number: int | None = None,
                   notes: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO ucas_choices
                   (application_id, university_name, course_title, ucas_code, choice_number, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (application_id, university_name, course_title, ucas_code, choice_number, notes),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM ucas_choices WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise UCASError(f"Failed to add choice: {e}") from e
        finally:
            conn.close()

    def list_choices(self, application_id: int) -> list[dict]:
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM ucas_choices WHERE application_id = ? ORDER BY choice_number",
                (application_id,)).fetchall()]
        finally:
            conn.close()

    def update_choice(self, choice_id: int, **updates) -> dict:
        allowed = {"offer_type", "offer_conditions", "offer_status", "is_firm", "is_insurance", "reply_deadline", "notes"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [choice_id]
            conn.execute(f"UPDATE ucas_choices SET {sets} WHERE id = ?", vals)
            conn.commit()
            row = conn.execute("SELECT * FROM ucas_choices WHERE id = ?", (choice_id,)).fetchone()
            return dict(row) if row else {}
        except Exception as e:
            conn.rollback()
            raise UCASError(f"Failed to update choice: {e}") from e
        finally:
            conn.close()

    def set_firm_insurance(self, application_id: int, firm_id: int, insurance_id: int | None = None) -> None:
        conn = self._conn()
        try:
            conn.execute("UPDATE ucas_choices SET is_firm = 0, is_insurance = 0 WHERE application_id = ?", (application_id,))
            conn.execute("UPDATE ucas_choices SET is_firm = 1 WHERE id = ?", (firm_id,))
            if insurance_id:
                conn.execute("UPDATE ucas_choices SET is_insurance = 1 WHERE id = ?", (insurance_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise UCASError(f"Failed to set firm/insurance: {e}") from e
        finally:
            conn.close()

    def get_statistics(self) -> dict:
        conn = self._conn()
        try:
            total = conn.execute("SELECT COUNT(*) as c FROM ucas_applications").fetchone()["c"]
            submitted = conn.execute("SELECT COUNT(*) as c FROM ucas_applications WHERE application_status = 'submitted'").fetchone()["c"]
            offers = conn.execute("SELECT COUNT(DISTINCT application_id) as c FROM ucas_choices WHERE offer_status = 'offer'").fetchone()["c"]
            return {"total": total, "submitted": submitted, "with_offers": offers}
        finally:
            conn.close()

