"""User management service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.infrastructure.auth.password_manager import hash_password
from education_system.primary_school.core.exceptions import UserManagementError
from education_system.primary_school.core.sql_safety import validate_identifier
import traceback

logger = logging.getLogger(__name__)


class UserService:
    """CRUD operations for user accounts."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_user(self, username, password, role, display_name=None, email=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            hashed = hash_password(password)
            cursor.execute(
                """INSERT INTO users (username, password_hash, role, display_name, email)
                VALUES (?, ?, ?, ?, ?)""",
                (username, hashed, role, display_name, email),
            )
            conn.commit()
            user_id = cursor.lastrowid
            logger.info("Created user: %s (role=%s)", username, role)
            return {"id": user_id, "username": username, "role": role}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise UserManagementError(f"Failed to create user: {e}") from e
        finally:
            conn.close()

    def get_user(self, user_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_users(self, role=None, is_active=1):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM users WHERE 1=1"
            params = []
            if role:
                sql += " AND role = ?"
                params.append(role)
            if is_active is not None:
                sql += " AND is_active = ?"
                params.append(is_active)
            sql += " ORDER BY username"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_user(self, user_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {"display_name", "email", "role", "is_active"}
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(user_id)
            cursor.execute(
                f"UPDATE users SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated user id=%s", user_id)
            return self.get_user(user_id)
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise UserManagementError(f"Failed to update user: {e}") from e
        finally:
            conn.close()

    def reset_password(self, user_id, new_password):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            hashed = hash_password(new_password)
            cursor.execute(
                "UPDATE users SET password_hash = ?, updated_at = datetime('now') WHERE id = ?",
                (hashed, user_id),
            )
            conn.commit()
            logger.info("Reset password for user id=%s", user_id)
            return cursor.rowcount > 0
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise UserManagementError(f"Failed to reset password: {e}") from e
        finally:
            conn.close()

    def delete_user(self, user_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted user id=%s", user_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise UserManagementError(f"Failed to delete user: {e}") from e
        finally:
            conn.close()
