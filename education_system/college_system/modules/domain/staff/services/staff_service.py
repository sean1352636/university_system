"""Staff management service."""

from datetime import datetime

from education_system.college_system.core.exceptions import StaffError, ValidationError
from education_system.college_system.core.defaults import STAFF_ID_PREFIX
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.infrastructure.validation.validators import (
    validate_email, validate_non_empty,
)

import logging

logger = logging.getLogger(__name__)


class StaffService:
    """Service for managing staff records."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def _generate_staff_id(self) -> str:
        """Generate the next sequential staff ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT staff_id FROM staff ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row:
                num = int(row["staff_id"].replace(STAFF_ID_PREFIX, "")) + 1
            else:
                num = 1
            return f"{STAFF_ID_PREFIX}{num:04d}"
        finally:
            conn.close()

    def create_staff(self, first_name: str, last_name: str,
                     title: str | None = None, email: str | None = None,
                     phone: str | None = None, subject_area: str | None = None,
                     form_group: str | None = None,
                     user_id: int | None = None) -> dict:
        """Create a new staff record."""
        first_name = validate_non_empty(first_name, "First name")
        last_name = validate_non_empty(last_name, "Last name")
        if email:
            email = validate_email(email)

        staff_id = self._generate_staff_id()
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO staff
                   (staff_id, user_id, first_name, last_name, title, email,
                    phone, subject_area, form_group)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (staff_id, user_id, first_name, last_name, title or "",
                 email, phone, subject_area, form_group),
            )
            conn.commit()
            logger.info("Staff created: %s (%s %s)", staff_id, first_name, last_name)
            return self.get_staff_by_staff_id(staff_id)
        except Exception as e:
            conn.rollback()
            raise StaffError(f"Failed to create staff: {e}") from e
        finally:
            conn.close()

    def get_staff(self, staff_pk: int) -> dict | None:
        """Get a staff member by primary key."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM staff WHERE id = ?", (staff_pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_staff_by_staff_id(self, staff_id: str) -> dict | None:
        """Get a staff member by their staff ID (e.g., STF0001)."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM staff WHERE staff_id = ?", (staff_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_staff(self, status: str | None = None,
                   search: str | None = None,
                   limit: int = 100, offset: int = 0) -> list[dict]:
        """List staff with optional filters."""
        sql = "SELECT * FROM staff WHERE 1=1"
        params = []

        if status:
            sql += " AND status = ?"
            params.append(status)
        if search:
            sql += " AND (first_name LIKE ? OR last_name LIKE ? OR staff_id LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term])

        sql += " ORDER BY staff_id LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_staff(self, staff_pk: int, **kwargs) -> dict:
        """Update a staff record."""
        allowed = {"first_name", "last_name", "title", "email", "phone",
                    "subject_area", "form_group", "status", "user_id"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}

        if not updates:
            raise ValidationError("No valid fields to update.")

        if "email" in updates:
            updates["email"] = validate_email(updates["email"])

        updates["updated_at"] = datetime.utcnow().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [staff_pk]

        conn = self._conn()
        try:
            conn.execute(f"UPDATE staff SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Staff updated: pk=%d", staff_pk)
            result = self.get_staff(staff_pk)
            if not result:
                raise StaffError("Staff member not found.")
            return result
        finally:
            conn.close()

    def delete_staff(self, staff_pk: int) -> bool:
        """Permanently delete a staff member and all related data."""
        conn = self._conn()
        try:
            staff = conn.execute(
                "SELECT id, user_id FROM staff WHERE id = ?", (staff_pk,)
            ).fetchone()
            if not staff:
                raise StaffError("Staff member not found.")

            # Build display name to clear from courses
            full = conn.execute(
                "SELECT title, first_name, last_name FROM staff WHERE id = ?",
                (staff_pk,),
            ).fetchone()
            if full:
                title = full["title"] or ""
                display_name = f"{title} {full['first_name'][0]}. {full['last_name']}".strip()
                conn.execute(
                    "UPDATE courses SET teacher = NULL, instructor = NULL WHERE teacher = ?",
                    (display_name,),
                )

            # Delete the staff record
            conn.execute("DELETE FROM staff WHERE id = ?", (staff_pk,))

            # Delete linked user account and its data
            user_id = staff["user_id"]
            if user_id:
                conn.execute("UPDATE messages SET sender_deleted = 1 WHERE sender_id = ?", (user_id,))
                conn.execute("UPDATE messages SET recipient_deleted = 1 WHERE recipient_id = ?", (user_id,))
                conn.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM mfa_recovery_codes WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM mfa_secrets WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

            conn.commit()
            logger.info("Staff deleted: pk=%d (user_id=%s)", staff_pk, staff["user_id"])
            return True
        except StaffError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            logger.error("Staff deletion failed: pk=%d: %s", staff_pk, e)
            raise StaffError(f"Failed to delete staff: {e}") from e
        finally:
            conn.close()

    def assign_courses(self, staff_pk: int, course_ids: list[int]) -> int:
        """Assign a staff member as teacher on the given courses.

        Updates the courses.teacher field with the staff member's display name.
        Returns the number of courses updated.
        """
        staff = self.get_staff(staff_pk)
        if not staff:
            raise StaffError("Staff member not found.")

        title = staff.get("title") or ""
        display_name = f"{title} {staff['first_name'][0]}. {staff['last_name']}".strip()

        conn = self._conn()
        try:
            updated = 0
            for cid in course_ids:
                cursor = conn.execute(
                    "UPDATE courses SET teacher = ?, instructor = ?, updated_at = datetime('now') WHERE id = ?",
                    (display_name, display_name, cid),
                )
                updated += cursor.rowcount
            conn.commit()
            return updated
        finally:
            conn.close()

    def get_assigned_courses(self, staff_pk: int) -> list[dict]:
        """Get courses assigned to a staff member."""
        staff = self.get_staff(staff_pk)
        if not staff:
            return []

        title = staff.get("title") or ""
        display_name = f"{title} {staff['first_name'][0]}. {staff['last_name']}".strip()

        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM courses WHERE teacher = ? AND status = 'active'",
                (display_name,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_form_tutors(self) -> list[dict]:
        """Get all active staff members who have a form group assigned."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT * FROM staff
                   WHERE status = 'active' AND form_group IS NOT NULL AND form_group != ''
                   ORDER BY form_group"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_form_groups(self) -> list[str]:
        """Get all distinct form groups from staff and students."""
        conn = self._conn()
        try:
            groups = set()
            # From staff
            rows = conn.execute(
                "SELECT DISTINCT form_group FROM staff WHERE form_group IS NOT NULL AND form_group != ''"
            ).fetchall()
            for r in rows:
                groups.add(r["form_group"])
            # From students
            rows = conn.execute(
                "SELECT DISTINCT form_group FROM students WHERE form_group IS NOT NULL AND form_group != ''"
            ).fetchall()
            for r in rows:
                groups.add(r["form_group"])
            # Add defaults if empty
            if not groups:
                groups = {"12A", "12B", "12C", "13A", "13B", "13C"}
            return sorted(groups)
        finally:
            conn.close()

    def count_staff(self, status: str | None = None) -> int:
        """Count total staff, optionally filtered by status."""
        conn = self._conn()
        try:
            if status:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM staff WHERE status = ?", (status,)
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) as cnt FROM staff").fetchone()
            return row["cnt"]
        finally:
            conn.close()
