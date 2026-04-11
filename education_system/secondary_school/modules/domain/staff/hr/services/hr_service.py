"""HR service for staff management."""

import logging
from education_system.secondary_school.core.exceptions import HRError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

CONTRACT_TYPES = ("permanent", "fixed_term", "part_time", "supply", "volunteer")
LEAVE_TYPES = ("annual", "sick", "maternity", "paternity", "compassionate", "unpaid", "training")
LEAVE_STATUSES = ("pending", "approved", "rejected", "cancelled")
JOB_TITLES = (
    "Teacher", "Head of Department", "Head of Year", "Deputy Head",
    "Headteacher", "Teaching Assistant", "SENCO", "Librarian",
    "Office Admin", "IT Technician", "Caretaker", "Receptionist",
)


class HRService:
    """Manage staff records and leave."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def _next_staff_id(self, conn) -> str:
        row = conn.execute("SELECT COUNT(*) as cnt FROM staff_hr").fetchone()
        return f"STF{(row['cnt'] + 1):04d}"

    # ── Staff CRUD ──

    def create_staff(self, first_name: str, last_name: str, title: str = "Mr",
                     email: str | None = None, phone: str | None = None,
                     address: str | None = None, department: str | None = None,
                     job_title: str = "Teacher", contract_type: str = "permanent",
                     salary: float | None = None, start_date: str | None = None,
                     dbs_check_date: str | None = None, dbs_certificate: str | None = None,
                     emergency_contact_name: str | None = None,
                     emergency_contact_phone: str | None = None,
                     notes: str | None = None) -> dict:
        conn = self._conn()
        try:
            staff_id = self._next_staff_id(conn)
            cursor = conn.execute(
                """INSERT INTO staff_hr
                   (staff_id, first_name, last_name, title, email, phone, address,
                    department, job_title, contract_type, salary, start_date,
                    dbs_check_date, dbs_certificate,
                    emergency_contact_name, emergency_contact_phone, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (staff_id, first_name, last_name, title, email, phone, address,
                 department, job_title, contract_type, salary, start_date,
                 dbs_check_date, dbs_certificate,
                 emergency_contact_name, emergency_contact_phone, notes),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM staff_hr WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise HRError(f"Failed to create staff record: {e}") from e
        finally:
            conn.close()

    def list_staff(self, status: str | None = None,
                   department: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM staff_hr WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if department:
                sql += " AND department = ?"
                params.append(department)
            sql += " ORDER BY last_name, first_name"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_staff(self, staff_hr_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM staff_hr WHERE id = ?", (staff_hr_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_staff(self, staff_hr_id: int, **kwargs) -> dict:
        set_parts: list[str] = []
        values: list = []
        for col in (
            "address", "annual_leave_entitlement", "annual_leave_used",
            "contract_type", "dbs_certificate", "dbs_check_date",
            "department", "email", "emergency_contact_name",
            "emergency_contact_phone", "end_date", "first_name",
            "job_title", "last_name", "notes", "phone", "salary",
            "sick_days_used", "start_date", "status", "title",
        ):
            if col in kwargs:
                set_parts.append(f"{col} = ?")
                values.append(kwargs[col])
        if not set_parts:
            raise HRError("No valid fields to update.")
        set_clause = ", ".join(set_parts)
        values.append(staff_hr_id)
        conn = self._conn()
        try:
            conn.execute(
                f"UPDATE staff_hr SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            row = conn.execute("SELECT * FROM staff_hr WHERE id = ?", (staff_hr_id,)).fetchone()
            return dict(row)
        except HRError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HRError(f"Failed to update staff: {e}") from e
        finally:
            conn.close()

    def delete_staff(self, staff_hr_id: int):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM staff_leave WHERE staff_hr_id = ?", (staff_hr_id,))
            conn.execute("DELETE FROM staff_hr WHERE id = ?", (staff_hr_id,))
            conn.commit()
        finally:
            conn.close()

    # ── Leave ──

    def request_leave(self, staff_hr_id: int, leave_type: str,
                      start_date: str, end_date: str, days: int = 1,
                      reason: str | None = None) -> dict:
        if leave_type not in LEAVE_TYPES:
            raise HRError(f"Invalid leave type: {leave_type}")
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO staff_leave
                   (staff_hr_id, leave_type, start_date, end_date, days, reason)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (staff_hr_id, leave_type, start_date, end_date, days, reason),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM staff_leave WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise HRError(f"Failed to request leave: {e}") from e
        finally:
            conn.close()

    def list_leave(self, staff_hr_id: int | None = None,
                   status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT sl.*, sh.first_name, sh.last_name, sh.staff_id as sid
                     FROM staff_leave sl JOIN staff_hr sh ON sl.staff_hr_id = sh.id
                     WHERE 1=1"""
            params: list = []
            if staff_hr_id:
                sql += " AND sl.staff_hr_id = ?"
                params.append(staff_hr_id)
            if status:
                sql += " AND sl.status = ?"
                params.append(status)
            sql += " ORDER BY sl.start_date DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def approve_leave(self, leave_id: int, approved_by: str):
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE staff_leave SET status = 'approved', approved_by = ? WHERE id = ?",
                (approved_by, leave_id),
            )
            conn.commit()
        finally:
            conn.close()

    def reject_leave(self, leave_id: int):
        conn = self._conn()
        try:
            conn.execute("UPDATE staff_leave SET status = 'rejected' WHERE id = ?", (leave_id,))
            conn.commit()
        finally:
            conn.close()
