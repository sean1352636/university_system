"""HR service for the Primary School Management System."""

import logging

from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import HRError
from education_system.primary_school.core.sql_safety import validate_identifier, escape_like
import traceback

logger = logging.getLogger(__name__)

STAFF_ID_PREFIX = "STF"


class HRService:
    """CRUD operations for staff HR records."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def _generate_staff_id(self):
        """Auto-generate a staff ID like STF0001."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT staff_id FROM staff ORDER BY staff_id DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if row:
                last_num = int(row["staff_id"].replace(STAFF_ID_PREFIX, ""))
                return f"{STAFF_ID_PREFIX}{last_num + 1:04d}"
            return f"{STAFF_ID_PREFIX}0001"
        finally:
            conn.close()

    def create_staff(self, first_name, last_name, role="Teacher", email=None,
                     phone=None, class_teacher_of=None, department=None,
                     **kwargs):
        """Create a new staff record."""
        staff_id = self._generate_staff_id()
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO staff (
                    staff_id, first_name, last_name, role, email, phone,
                    class_teacher_of, department, start_date, qualifications,
                    dbs_check_date, dbs_number, emergency_contact_name,
                    emergency_contact_phone, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    staff_id, first_name, last_name, role, email, phone,
                    class_teacher_of, department,
                    kwargs.get("start_date"),
                    kwargs.get("qualifications"),
                    kwargs.get("dbs_check_date"),
                    kwargs.get("dbs_number"),
                    kwargs.get("emergency_contact_name"),
                    kwargs.get("emergency_contact_phone"),
                    kwargs.get("notes"),
                ),
            )
            conn.commit()
            logger.info(
                "Created staff: %s %s (%s, role=%s)",
                first_name, last_name, staff_id, role,
            )
            return {
                "staff_id": staff_id, "first_name": first_name,
                "last_name": last_name, "role": role,
            }
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise HRError(f"Failed to create staff: {e}") from e
        finally:
            conn.close()

    def get_staff(self, staff_id):
        """Get a staff record by ID."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM staff WHERE staff_id = ?", (staff_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_staff(self, role=None, status="Active", search=None):
        """List staff with optional filters."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM staff WHERE 1=1"
            params = []
            if role:
                sql += " AND role = ?"
                params.append(role)
            if status:
                sql += " AND status = ?"
                params.append(status)
            if search:
                sql += " AND (first_name LIKE ? OR last_name LIKE ? OR staff_id LIKE ?)"
                escaped = escape_like(search)
                term = f"%{escaped}%"
                params.extend([term, term, term])
            sql += " ORDER BY last_name, first_name"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_staff(self, staff_id, **kwargs):
        """Update a staff record."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "first_name", "last_name", "role", "email", "phone",
                "class_teacher_of", "department", "start_date",
                "qualifications", "dbs_check_date", "dbs_number",
                "emergency_contact_name", "emergency_contact_phone",
                "notes", "status", "leaving_date",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values()) + [staff_id]
            cursor.execute(
                f"UPDATE staff SET {set_clause} WHERE staff_id = ?", values,
            )
            conn.commit()
            logger.info("Updated staff: %s", staff_id)
            return self.get_staff(staff_id)
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise HRError(f"Failed to update staff: {e}") from e
        finally:
            conn.close()

    def delete_staff(self, staff_id):
        """Delete a staff record."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM staff WHERE staff_id = ?", (staff_id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted staff: %s", staff_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise HRError(f"Failed to delete staff: {e}") from e
        finally:
            conn.close()

    def record_leave(self, staff_id, leave_type, start_date, end_date,
                     reason=None):
        """Record a leave request for a staff member."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO staff_leave (
                    staff_id, leave_type, start_date, end_date,
                    reason, status
                ) VALUES (?, ?, ?, ?, ?, 'Pending')""",
                (staff_id, leave_type, start_date, end_date, reason),
            )
            conn.commit()
            leave_id = cursor.lastrowid
            logger.info(
                "Recorded leave for staff %s (id=%s, type=%s)",
                staff_id, leave_id, leave_type,
            )
            return leave_id
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise HRError(f"Failed to record leave: {e}") from e
        finally:
            conn.close()

    def get_leave(self, staff_id=None, status=None):
        """Get leave records with optional filters."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM staff_leave WHERE 1=1"
            params = []
            if staff_id:
                sql += " AND staff_id = ?"
                params.append(staff_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY start_date DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def approve_leave(self, leave_id, approved_by):
        """Approve a leave request."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE staff_leave
                SET status = 'Approved', approved_by = ?
                WHERE id = ?""",
                (approved_by, leave_id),
            )
            conn.commit()
            logger.info(
                "Approved leave %s by %s", leave_id, approved_by,
            )
            return cursor.rowcount > 0
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise HRError(f"Failed to approve leave: {e}") from e
        finally:
            conn.close()
