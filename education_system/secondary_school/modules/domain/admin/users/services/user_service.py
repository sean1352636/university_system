"""User management service."""

import logging
from education_system.secondary_school.core.exceptions import UserManagementError
from education_system.secondary_school.infrastructure.database.db import connect
from education_system.secondary_school.infrastructure.auth.password_manager import hash_password

logger = logging.getLogger(__name__)

ROLES = ("admin", "teacher", "student")


class UserService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def list_users(self, role=None):
        conn = self._conn()
        try:
            sql = "SELECT id, username, role, email, is_active, created_at FROM users WHERE 1=1"
            params = []
            if role:
                sql += " AND role = ?"
                params.append(role)
            sql += " ORDER BY username"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def create_user(self, username, password, role="student", email=None):
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, role, email) VALUES (?, ?, ?, ?)",
                (username, hash_password(password), role, email))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise UserManagementError(f"Failed to create user: {e}") from e
        finally:
            conn.close()

    def reset_password(self, user_id, new_password):
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE users SET password_hash = ?, failed_login_attempts = 0, locked_until = NULL WHERE id = ?",
                (hash_password(new_password), user_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise UserManagementError(f"Failed to reset password: {e}") from e
        finally:
            conn.close()

    def toggle_active(self, user_id):
        conn = self._conn()
        try:
            row = conn.execute("SELECT is_active FROM users WHERE id = ?", (user_id,)).fetchone()
            if row:
                conn.execute("UPDATE users SET is_active = ? WHERE id = ?",
                             (0 if row["is_active"] else 1, user_id))
                conn.commit()
        finally:
            conn.close()

    def update_role(self, user_id, new_role):
        conn = self._conn()
        try:
            conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise UserManagementError(f"Failed to update role: {e}") from e
        finally:
            conn.close()

    def delete_user(self, user_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
        finally:
            conn.close()
