"""Role-Based Access Control with per-system role assignments."""

import logging

from education_system.shared.auth.db import connect

logger = logging.getLogger(__name__)

# Unified role hierarchy across all systems
ROLE_HIERARCHY = {
    "admin": 100,
    "staff": 75,
    "instructor": 50,
    "teacher": 50,
    "teaching_assistant": 40,
    "parent": 30,
    "student": 25,
}


class RoleManager:
    """Manages roles and permissions using the shared auth database."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def get_role_level(self, role: str) -> int:
        """Get the hierarchy level for a role."""
        return ROLE_HIERARCHY.get(role, 0)

    def has_minimum_role(self, user_role: str, required_role: str) -> bool:
        """Check if user_role meets or exceeds the required_role level."""
        return self.get_role_level(user_role) >= self.get_role_level(required_role)

    def get_user_role_for_system(self, user_id: int, system_key: str) -> str | None:
        """Get the user's role for a specific system."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT role FROM user_systems WHERE user_id = ? AND system_key = ?",
                (user_id, system_key),
            ).fetchone()
            return row["role"] if row else None
        finally:
            conn.close()

    def get_user_systems(self, user_id: int) -> list[dict]:
        """Get all systems a user has access to, with their role in each."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT system_key, role FROM user_systems WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            return [{"system_key": r["system_key"], "role": r["role"]} for r in rows]
        finally:
            conn.close()

    def grant_system_access(self, user_id: int, system_key: str, role: str):
        """Grant a user access to a system with the specified role."""
        if role not in ROLE_HIERARCHY:
            raise ValueError(f"Invalid role: {role}")

        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO user_systems (user_id, system_key, role)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id, system_key) DO UPDATE SET role = ?""",
                (user_id, system_key, role, role),
            )
            conn.commit()
            logger.info("Granted %s access to system '%s' for user_id=%d", role, system_key, user_id)
        finally:
            conn.close()

    def revoke_system_access(self, user_id: int, system_key: str):
        """Revoke a user's access to a system."""
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM user_systems WHERE user_id = ? AND system_key = ?",
                (user_id, system_key),
            )
            conn.commit()
            logger.info("Revoked access to system '%s' for user_id=%d", system_key, user_id)
        finally:
            conn.close()
