"""Student management service."""

import json
import sqlite3
from datetime import datetime

from education_system.college_system.core.exceptions import StudentError, ValidationError
from education_system.college_system.core.defaults import STUDENT_ID_PREFIX
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.infrastructure.validation.validators import (
    validate_email, validate_non_empty, validate_student_id,
)

from education_system.college_system.core.sql_safety import validate_identifier, escape_like  # nosec B608
import logging

logger = logging.getLogger(__name__)


class StudentService:
    """Service for managing student records."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def _generate_student_id(self) -> str:
        """Generate the next sequential student ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT MAX(CAST(REPLACE(student_id, ?, '') AS INTEGER)) AS max_num FROM students",
                (STUDENT_ID_PREFIX,),
            ).fetchone()
            num = (row["max_num"] or 0) + 1
            return f"{STUDENT_ID_PREFIX}{num:04d}"
        finally:
            conn.close()

    def create_student(self, first_name: str, last_name: str,
                       email: str | None = None, phone: str | None = None,
                       date_of_birth: str | None = None, address: str | None = None,
                       year_group: str | None = None, form_group: str | None = None,
                       form_tutor: str | None = None, user_id: int | None = None) -> dict:
        """Create a new student record."""
        first_name = validate_non_empty(first_name, "First name")
        last_name = validate_non_empty(last_name, "Last name")
        if email:
            email = validate_email(email)

        student_id = self._generate_student_id()
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO students
                   (student_id, user_id, first_name, last_name, email, phone,
                    date_of_birth, address, year_group, form_group, form_tutor)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, user_id, first_name, last_name, email, phone,
                 date_of_birth, address, year_group or "12", form_group, form_tutor),
            )
            conn.commit()
            logger.info("Student created: %s (%s %s)", student_id, first_name, last_name)
            return self.get_student_by_student_id(student_id)
        except Exception as e:
            conn.rollback()
            raise StudentError(f"Failed to create student: {e}") from e
        finally:
            conn.close()

    def get_student(self, student_pk: int) -> dict | None:
        """Get a student by primary key."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM students WHERE id = ?", (student_pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_student_by_student_id(self, student_id: str) -> dict | None:
        """Get a student by their student ID (e.g., STU0001)."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM students WHERE student_id = ?", (student_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_students(self, status: str | None = None,
                      year_group: str | None = None, form_group: str | None = None,
                      search: str | None = None, limit: int = 100,
                      offset: int = 0) -> list[dict]:
        """List students with optional filters."""
        sql = "SELECT * FROM students WHERE 1=1"
        params = []

        if status:
            sql += " AND status = ?"
            params.append(status)
        if year_group:
            sql += " AND year_group = ?"
            params.append(year_group)
        if form_group:
            sql += " AND form_group = ?"
            params.append(form_group)
        if search:
            sql += " AND (first_name LIKE ? OR last_name LIKE ? OR student_id LIKE ?)"
            escaped = escape_like(search)
            term = f"%{escaped}%"
            params.extend([term, term, term])

        sql += " ORDER BY student_id LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_student(self, student_pk: int, **kwargs) -> dict:
        """Update a student record."""
        # Iterate over a literal allowed-column tuple so CodeQL recognises
        # the column names as untainted (py/sql-injection).
        set_parts: list[str] = []
        params: list = []
        for col in ("first_name", "last_name", "email", "phone", "date_of_birth",
                    "address", "year_group", "form_group", "form_tutor", "status",
                    "user_id"):
            val = kwargs.get(col)
            if val is None:
                continue
            if col == "email":
                val = validate_email(val)
            set_parts.append(f"{validate_identifier(col)} = ?")
            params.append(val)

        if not set_parts:
            raise ValidationError("No valid fields to update.")

        set_parts.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        params.append(student_pk)
        set_clause = ", ".join(set_parts)

        conn = self._conn()
        try:
            conn.execute(f"UPDATE students SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Student updated: pk=%d", student_pk)
            result = self.get_student(student_pk)
            if not result:
                raise StudentError("Student not found.")
            return result
        finally:
            conn.close()

    def delete_student(self, student_pk: int) -> bool:
        """Permanently delete a student and all related data."""
        conn = self._conn()
        try:
            # Check student exists and get user_id for cleanup
            student = conn.execute(
                "SELECT id, user_id FROM students WHERE id = ?", (student_pk,)
            ).fetchone()
            if not student:
                raise StudentError("Student not found.")

            # Delete related records
            conn.execute("DELETE FROM submissions WHERE student_id = ?", (student_pk,))
            conn.execute("DELETE FROM attendance_records WHERE student_id = ?", (student_pk,))
            conn.execute("DELETE FROM grades WHERE student_id = ?", (student_pk,))
            conn.execute("DELETE FROM waitlist WHERE student_id = ?", (student_pk,))
            conn.execute("DELETE FROM enrollments WHERE student_id = ?", (student_pk,))

            # Delete the student record
            conn.execute("DELETE FROM students WHERE id = ?", (student_pk,))

            # Delete linked user account and its data
            user_id = student["user_id"]
            if user_id:
                conn.execute("UPDATE messages SET sender_deleted = 1 WHERE sender_id = ?", (user_id,))
                conn.execute("UPDATE messages SET recipient_deleted = 1 WHERE recipient_id = ?", (user_id,))
                conn.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM mfa_recovery_codes WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM mfa_secrets WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

            conn.commit()
            logger.info("Student deleted: pk=%d (user_id=%s)", student_pk, student["user_id"])
            return True
        except StudentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            logger.error("Student deletion failed: pk=%d: %s", student_pk, e)
            raise StudentError(f"Failed to delete student: {e}") from e
        finally:
            conn.close()

    def get_student_profile(self, student_pk: int) -> dict | None:
        """Get a comprehensive student profile with enrollment info."""
        student = self.get_student(student_pk)
        if not student:
            return None

        conn = self._conn()
        try:
            enrollments = conn.execute(
                """SELECT e.*, c.course_code, c.title
                   FROM enrollments e JOIN courses c ON e.course_id = c.id
                   WHERE e.student_id = ? AND e.status = 'enrolled'""",
                (student_pk,),
            ).fetchall()

            grades = conn.execute(
                """SELECT g.*, c.course_code, c.title, c.credits
                   FROM grades g JOIN courses c ON g.course_id = c.id
                   WHERE g.student_id = ?""",
                (student_pk,),
            ).fetchall()

            student["enrollments"] = [dict(e) for e in enrollments]
            student["grades"] = [dict(g) for g in grades]
            return student
        finally:
            conn.close()

    def count_students(self, status: str | None = None,
                       search: str | None = None) -> int:
        """Count total students, optionally filtered by status and/or search term."""
        sql = "SELECT COUNT(*) as cnt FROM students WHERE 1=1"
        params: list = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if search:
            sql += " AND (first_name LIKE ? OR last_name LIKE ? OR student_id LIKE ?)"
            escaped = escape_like(search)
            term = f"%{escaped}%"
            params.extend([term, term, term])
        conn = self._conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row["cnt"]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Cross-system transfer helpers
    # ------------------------------------------------------------------

    def fetch_secondary_students(self, secondary_db_path: str) -> list[dict]:
        """Fetch active students from the secondary school database.

        Returns a list of dicts with student info suitable for import selection.
        """
        conn = sqlite3.connect(str(secondary_db_path))
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, student_id, first_name, last_name, date_of_birth, "
                "address, parent_phone, sen_status "
                "FROM students WHERE status = 'active' ORDER BY last_name, first_name"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def import_from_secondary(self, student_pk: int, imported_data: dict,
                              secondary_db_path: str) -> None:
        """Store academic transfer history and set previous_system fields.

        Args:
            student_pk: The primary key of the newly created college student.
            imported_data: Dict of the secondary school student record
                           (must contain 'id' and optionally 'student_id').
            secondary_db_path: Path to the secondary school database file.
        """
        from education_system.shared.transfer.academic_history import extract_secondary_history

        # 1) Extract and store academic history
        try:
            history = extract_secondary_history(
                str(secondary_db_path), imported_data['id']
            )
            if history:
                conn = self._conn()
                try:
                    conn.execute(
                        "INSERT INTO academic_transfer_history "
                        "(student_id, source_system, data_json, transferred_at) "
                        "VALUES (?, ?, ?, datetime('now'))",
                        (student_pk, 'school', json.dumps(history)),
                    )
                    conn.commit()
                finally:
                    conn.close()
        except Exception:
            logger.warning(
                "Failed to extract/store academic transfer history from secondary school",
                exc_info=True,
            )

        # 2) Set previous_system fields on the student record
        try:
            conn = self._conn()
            try:
                conn.execute(
                    "UPDATE students SET previous_system = ?, previous_system_id = ? "
                    "WHERE id = ?",
                    ('school', imported_data.get('student_id', ''), student_pk),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            logger.warning(
                "Failed to set previous_system fields on transferred student",
                exc_info=True,
            )

    def mark_secondary_as_transferred(self, secondary_student_pk: int,
                                      secondary_db_path: str) -> None:
        """Mark a student as 'transferred' in the secondary school database.

        Args:
            secondary_student_pk: The id (PK) of the student in the secondary DB.
            secondary_db_path: Path to the secondary school database file.
        """
        conn = sqlite3.connect(str(secondary_db_path))
        try:
            conn.execute(
                "UPDATE students SET status = 'transferred' WHERE id = ?",
                (secondary_student_pk,),
            )
            conn.commit()
        finally:
            conn.close()

    def notify_transfer(self, student_id: str, imported_data: dict,
                        auth_info, secondary_db_path: str) -> None:
        """Send transfer notifications to secondary school admins.

        Sends both a cross-system notification and local notifications/emails
        in the secondary school database.

        Args:
            student_id: The new college student ID (e.g. SFC0002).
            imported_data: Dict of the secondary school student record.
            auth_info: The auth object or dict for determining the sender.
            secondary_db_path: Path to the secondary school database file.
        """
        imp_name = (
            f"{imported_data.get('first_name', '')} "
            f"{imported_data.get('last_name', '')}"
        )
        _transfer_title = f"Student Transfer: {imp_name} moved to College"
        _transfer_msg = (
            f"Student {imported_data.get('student_id', '')} ({imp_name}) "
            f"has been transferred from the Secondary School "
            f"to the College System.\n\n"
            f"New College Student ID: {student_id}\n"
            f"The student's secondary school record has been "
            f"marked as 'transferred'."
        )

        # Determine sender user id
        _sender_id = None
        if auth_info and hasattr(auth_info, 'current_user') and auth_info.current_user:
            _sender_id = auth_info.current_user.get('user_id')

        # 1) Cross-system notification
        try:
            from education_system.shared.notifications.service import (
                CrossSystemNotificationService,
            )
            _xn_svc = CrossSystemNotificationService()
            _xn_svc.send_to_role(
                sender_user_id=_sender_id or 0,
                sender_system='college',
                target_system='school',
                target_role='admin',
                title=_transfer_title,
                message=_transfer_msg,
                priority='high',
            )
        except Exception:
            logger.warning(
                "Failed to send cross-system transfer notification "
                "to secondary school admins",
                exc_info=True,
            )

        # 2) Secondary-local notification + email
        try:
            from education_system.shared.auth.db import AUTH_DB_FILE
            _auth_conn = sqlite3.connect(str(AUTH_DB_FILE))
            try:
                _auth_conn.row_factory = sqlite3.Row
                _admins = _auth_conn.execute(
                    "SELECT u.username FROM users u "
                    "JOIN user_systems us ON u.id = us.user_id "
                    "WHERE us.system_key = 'school' AND us.role = 'admin' "
                    "AND u.is_active = 1"
                ).fetchall()
            finally:
                _auth_conn.close()

            _sec_conn = sqlite3.connect(str(secondary_db_path))
            try:
                _sec_conn.row_factory = sqlite3.Row
                _admin_ids = []
                for _admin in _admins:
                    _local = _sec_conn.execute(
                        "SELECT id FROM users WHERE username = ?",
                        (_admin['username'],),
                    ).fetchone()
                    if _local:
                        _admin_ids.append(_local['id'])
                        _sec_conn.execute(
                            "INSERT INTO notifications (user_id, title, message) "
                            "VALUES (?, ?, ?)",
                            (_local['id'], _transfer_title, _transfer_msg),
                        )
                # Also insert into emails table
                _msg_sender = _admin_ids[0] if _admin_ids else 1
                for _aid in _admin_ids:
                    _sec_conn.execute(
                        "INSERT INTO emails (sender_id, recipient_id, subject, body) "
                        "VALUES (?, ?, ?, ?)",
                        (_msg_sender, _aid, _transfer_title, _transfer_msg),
                    )
                _sec_conn.commit()
            finally:
                _sec_conn.close()
        except Exception:
            logger.warning(
                "Failed to send local notifications/emails "
                "to secondary school admins",
                exc_info=True,
            )
