"""Student management service."""

import json
import sqlite3
from datetime import datetime
import logging
from education_system.secondary_school.core.sql_safety import validate_identifier, escape_like  # nosec B608

from education_system.secondary_school.core.exceptions import StudentError, ValidationError
from education_system.secondary_school.core.defaults import STUDENT_ID_PREFIX
from education_system.secondary_school.infrastructure.database.db import connect
from education_system.secondary_school.infrastructure.validation.validators import (
    validate_email, validate_non_empty,
)

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
                "SELECT student_id FROM students ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row:
                num = int(row["student_id"].replace(STUDENT_ID_PREFIX, "")) + 1
            else:
                num = 1
            return f"{STUDENT_ID_PREFIX}{num:04d}"
        finally:
            conn.close()

    def _key_stage_for_year(self, year_group: str) -> str:
        """Determine key stage from year group."""
        from education_system.secondary_school.infrastructure.database.constants import KS3_YEARS
        return "KS3" if year_group in KS3_YEARS else "KS4"

    def create_student(self, first_name: str, last_name: str,
                       email: str | None = None,
                       date_of_birth: str | None = None, address: str | None = None,
                       year_group: str | None = None, form_group: str | None = None,
                       form_tutor: str | None = None, sen_status: str | None = None,
                       pupil_premium: bool = False,
                       parent_name: str | None = None,
                       parent_email: str | None = None,
                       parent_phone: str | None = None,
                       emergency_contact_name: str | None = None,
                       emergency_contact_phone: str | None = None,
                       user_id: int | None = None) -> dict:
        """Create a new student record."""
        first_name = validate_non_empty(first_name, "First name")
        last_name = validate_non_empty(last_name, "Last name")
        if email:
            email = validate_email(email)
        if parent_email:
            parent_email = validate_email(parent_email)

        year_group = year_group or "7"
        key_stage = self._key_stage_for_year(year_group)
        student_id = self._generate_student_id()

        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO students
                   (student_id, user_id, first_name, last_name, email,
                    date_of_birth, address, year_group, form_group, form_tutor,
                    key_stage, sen_status, pupil_premium,
                    parent_name, parent_email, parent_phone,
                    emergency_contact_name, emergency_contact_phone)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, user_id, first_name, last_name, email,
                 date_of_birth, address, year_group, form_group, form_tutor,
                 key_stage, sen_status or "none", int(pupil_premium),
                 parent_name, parent_email, parent_phone,
                 emergency_contact_name, emergency_contact_phone),
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
        """Get a student by their student ID (e.g., SEC0001)."""
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
                      key_stage: str | None = None, search: str | None = None,
                      limit: int = 200, offset: int = 0) -> list[dict]:
        """List students with optional filters."""
        sql = "SELECT * FROM students WHERE 1=1"
        params: list = []

        if status:
            sql += " AND status = ?"
            params.append(status)
        if year_group:
            sql += " AND year_group = ?"
            params.append(year_group)
        if form_group:
            sql += " AND form_group = ?"
            params.append(form_group)
        if key_stage:
            sql += " AND key_stage = ?"
            params.append(key_stage)
        if search:
            sql += " AND (first_name LIKE ? OR last_name LIKE ? OR student_id LIKE ?)"
            escaped = escape_like(search)
            term = f"%{escaped}%"
            params.extend([term, term, term])

        sql += " ORDER BY year_group, form_group, last_name LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_student(self, student_pk: int, **kwargs) -> dict:
        """Update a student record."""
        allowed = {"first_name", "last_name", "email", "date_of_birth",
                    "address", "year_group", "form_group", "form_tutor", "status",
                    "key_stage", "sen_status", "pupil_premium",
                    "parent_name", "parent_email", "parent_phone",
                    "emergency_contact_name", "emergency_contact_phone", "user_id"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}

        if not updates:
            raise ValidationError("No valid fields to update.")

        if "email" in updates:
            updates["email"] = validate_email(updates["email"])

        # Auto-set key stage if year group changes
        if "year_group" in updates:
            updates["key_stage"] = self._key_stage_for_year(updates["year_group"])

        updates["updated_at"] = datetime.utcnow().isoformat()

        set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
        params = list(updates.values()) + [student_pk]

        conn = self._conn()
        try:
            conn.execute(f"UPDATE students SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
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
            student = conn.execute(
                "SELECT id, user_id FROM students WHERE id = ?", (student_pk,)
            ).fetchone()
            if not student:
                raise StudentError("Student not found.")

            conn.execute("DELETE FROM behaviour_records WHERE student_id = ?", (student_pk,))
            conn.execute("DELETE FROM attendance_records WHERE student_id = ?", (student_pk,))
            conn.execute("DELETE FROM grades WHERE student_id = ?", (student_pk,))
            conn.execute("DELETE FROM enrollments WHERE student_id = ?", (student_pk,))
            conn.execute("DELETE FROM students WHERE id = ?", (student_pk,))

            user_id = student["user_id"]
            if user_id:
                conn.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

            conn.commit()
            logger.info("Student deleted: pk=%d", student_pk)
            return True
        except StudentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudentError(f"Failed to delete student: {e}") from e
        finally:
            conn.close()

    def count_students(self, status: str | None = None,
                       year_group: str | None = None) -> int:
        """Count students with optional filters."""
        conn = self._conn()
        try:
            sql = "SELECT COUNT(*) as cnt FROM students WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if year_group:
                sql += " AND year_group = ?"
                params.append(year_group)
            row = conn.execute(sql, params).fetchone()
            return row["cnt"]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Cross-system transfer helpers
    # ------------------------------------------------------------------

    def fetch_primary_pupils(self, primary_db_path: str) -> list[dict]:
        """Fetch active pupils from the primary school database.

        Returns a list of dicts with pupil info suitable for import selection.
        """
        conn = sqlite3.connect(str(primary_db_path))
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, pupil_id, first_name, last_name, date_of_birth, gender, "
                "address, parent1_name, parent1_email, parent1_phone, "
                "emergency_contact_name, emergency_contact_phone, sen_status "
                "FROM pupils WHERE status = 'Active' ORDER BY last_name, first_name"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def import_from_primary(self, student_pk: int, imported_data: dict,
                            primary_db_path: str) -> None:
        """Store academic transfer history and set previous_system fields.

        Args:
            student_pk: The primary key of the newly created secondary student.
            imported_data: Dict of the primary school pupil record
                           (must contain 'pupil_id').
            primary_db_path: Path to the primary school database file.
        """
        from education_system.shared.transfer.academic_history import extract_primary_history

        # 1) Extract and store academic history
        try:
            history = extract_primary_history(
                str(primary_db_path), imported_data.get('pupil_id', '')
            )
            if history:
                conn = self._conn()
                try:
                    conn.execute(
                        "INSERT INTO academic_transfer_history "
                        "(student_id, source_system, data_json, transferred_at) "
                        "VALUES (?, ?, ?, datetime('now'))",
                        (student_pk, 'primary', json.dumps(history)),
                    )
                    conn.commit()
                finally:
                    conn.close()
        except Exception:
            logger.warning(
                "Failed to extract/store academic transfer history from primary school",
                exc_info=True,
            )

        # 2) Set previous_system fields on the student record
        try:
            conn = self._conn()
            try:
                conn.execute(
                    "UPDATE students SET previous_system = ?, previous_system_id = ? "
                    "WHERE id = ?",
                    ('primary', imported_data.get('pupil_id', ''), student_pk),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            logger.warning(
                "Failed to set previous_system fields on transferred student",
                exc_info=True,
            )

    def mark_primary_as_transferred(self, primary_pupil_pk: int,
                                    primary_db_path: str) -> None:
        """Mark a pupil as 'Transferred' in the primary school database.

        Args:
            primary_pupil_pk: The id (PK) of the pupil in the primary DB.
            primary_db_path: Path to the primary school database file.
        """
        conn = sqlite3.connect(str(primary_db_path))
        try:
            conn.execute(
                "UPDATE pupils SET status = 'Transferred' WHERE id = ?",
                (primary_pupil_pk,),
            )
            conn.commit()
        finally:
            conn.close()

    def notify_transfer(self, student_id: str, imported_data: dict,
                        auth_info, primary_db_path: str) -> None:
        """Send transfer notifications to primary school admins.

        Sends both a cross-system notification and local notifications/emails
        in the primary school database.

        Args:
            student_id: The new secondary student ID (e.g. SEC0002).
            imported_data: Dict of the primary school pupil record.
            auth_info: The auth object or dict for determining the sender.
            primary_db_path: Path to the primary school database file.
        """
        imp_name = (
            f"{imported_data.get('first_name', '')} "
            f"{imported_data.get('last_name', '')}"
        )
        _transfer_title = f"Pupil Transfer: {imp_name} moved to Secondary School"
        _transfer_msg = (
            f"Pupil {imported_data.get('pupil_id', '')} ({imp_name}) "
            f"has been transferred from the Primary School "
            f"to the Secondary School System.\n\n"
            f"New Secondary Student ID: {student_id}\n"
            f"The pupil's primary school record has been "
            f"marked as 'Transferred'."
        )

        # Determine sender user id
        _sender_id = None
        if isinstance(auth_info, dict):
            _sender_id = auth_info.get('id') or auth_info.get('user_id')
        elif hasattr(auth_info, 'current_user') and auth_info.current_user:
            _sender_id = auth_info.current_user.get('user_id')

        # 1) Cross-system notification
        try:
            from education_system.shared.notifications.service import (
                CrossSystemNotificationService,
            )
            _xn_svc = CrossSystemNotificationService()
            _xn_svc.send_to_role(
                sender_user_id=_sender_id or 0,
                sender_system='school',
                target_system='primary',
                target_role='admin',
                title=_transfer_title,
                message=_transfer_msg,
                priority='high',
            )
        except Exception:
            logger.warning(
                "Failed to send cross-system transfer notification "
                "to primary school admins",
                exc_info=True,
            )

        # 2) Primary-local notification + email log
        try:
            from education_system.shared.auth.db import AUTH_DB_FILE
            _auth_conn = sqlite3.connect(str(AUTH_DB_FILE))
            try:
                _auth_conn.row_factory = sqlite3.Row
                _admins = _auth_conn.execute(
                    "SELECT u.username, u.email FROM users u "
                    "JOIN user_systems us ON u.id = us.user_id "
                    "WHERE us.system_key = 'primary' AND us.role = 'admin' "
                    "AND u.is_active = 1"
                ).fetchall()
            finally:
                _auth_conn.close()

            _pri_conn = sqlite3.connect(str(primary_db_path))
            try:
                _pri_conn.row_factory = sqlite3.Row
                for _admin in _admins:
                    _local = _pri_conn.execute(
                        "SELECT id FROM users WHERE username = ?",
                        (_admin['username'],),
                    ).fetchone()
                    if _local:
                        _pri_conn.execute(
                            "INSERT INTO notifications "
                            "(user_id, title, message, notification_type) "
                            "VALUES (?, ?, ?, ?)",
                            (_local['id'], _transfer_title, _transfer_msg, 'Info'),
                        )
                    _admin_email = (
                        _admin['email']
                        or f"{_admin['username']}@primary.school.uk"
                    )
                    _pri_conn.execute(
                        "INSERT INTO email_log "
                        "(to_address, from_address, subject, body, status) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            _admin_email,
                            'system@secondary.school.uk',
                            _transfer_title,
                            _transfer_msg,
                            'Logged',
                        ),
                    )
                _pri_conn.commit()
            finally:
                _pri_conn.close()
        except Exception:
            logger.warning(
                "Failed to send local notifications/emails "
                "to primary school admins",
                exc_info=True,
            )
