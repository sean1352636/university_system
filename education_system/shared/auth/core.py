"""Core authentication class for the unified Education System auth."""

from datetime import datetime, timedelta
import logging

from education_system.shared.auth.exceptions import AuthError
from education_system.shared.auth.defaults import MAX_LOGIN_ATTEMPTS, LOCKOUT_DURATION_MINUTES
from education_system.shared.auth.db import connect
from education_system.shared.auth.password_manager import (
    hash_password,
    verify_password,
    validate_password_strength,
)
from education_system.shared.auth.session_manager import SessionManager
from education_system.shared.auth.role_manager import RoleManager

logger = logging.getLogger(__name__)


class UserAuth:
    """Unified authentication facade for all Education System subsystems."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path
        self.session_manager = SessionManager(db_path)
        self.role_manager = RoleManager(db_path)
        self._current_user: dict | None = None
        self._current_token: str | None = None

    def _conn(self):
        return connect(self._db_path)

    @property
    def current_user(self) -> dict | None:
        return self._current_user

    @property
    def is_logged_in(self) -> bool:
        return self._current_user is not None

    def login(self, username: str, password: str) -> dict:
        """Authenticate a user against the shared auth database.

        Returns a user info dict on success. Raises AuthError on failure.
        The returned dict includes the list of systems the user can access.
        """
        conn = self._conn()
        try:
            user = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()

            if not user:
                logger.warning("Login failed: unknown user '%s'", username)
                raise AuthError("Invalid username or password.")

            if not user["is_active"]:
                logger.warning("Login attempt on deactivated account: '%s'", username)
                raise AuthError("Account is deactivated.")

            # Check lockout
            if user["locked_until"]:
                locked_until = datetime.fromisoformat(user["locked_until"])
                if locked_until > datetime.utcnow():
                    logger.warning("Login attempt on locked account: '%s'", username)
                    raise AuthError("Account locked due to too many failed attempts.")
                else:
                    conn.execute(
                        "UPDATE users SET locked_until = NULL, failed_login_attempts = 0 WHERE id = ?",
                        (user["id"],),
                    )
                    conn.commit()

            legacy_salt = user["legacy_salt"] if "legacy_salt" in user.keys() else None
            if not verify_password(password, user["password_hash"], legacy_salt=legacy_salt):
                attempts = user["failed_login_attempts"] + 1
                updates = {"failed_login_attempts": attempts}
                if attempts >= MAX_LOGIN_ATTEMPTS:
                    lockout = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                    updates["locked_until"] = lockout.isoformat()

                set_parts = ", ".join(f"{k} = ?" for k in updates)
                conn.execute(
                    f"UPDATE users SET {set_parts} WHERE id = ?",
                    (*updates.values(), user["id"]),
                )
                conn.commit()
                logger.warning("Login failed: wrong password for '%s' (attempt %d)", username, attempts)
                raise AuthError("Invalid username or password.")

            # If verified via legacy PBKDF2, re-hash with bcrypt transparently
            if legacy_salt:
                new_hash = hash_password(password)
                conn.execute(
                    "UPDATE users SET password_hash = ?, legacy_salt = NULL WHERE id = ?",
                    (new_hash, user["id"]),
                )
                logger.info("Re-hashed legacy PBKDF2 password to bcrypt for user '%s'", username)

            # Reset failed attempts and update last_login
            conn.execute(
                "UPDATE users SET failed_login_attempts = 0, locked_until = NULL, "
                "last_login = datetime('now') WHERE id = ?",
                (user["id"],),
            )
            conn.commit()

            # Fetch systems the user has access to
            systems = conn.execute(
                "SELECT system_key, role FROM user_systems WHERE user_id = ?",
                (user["id"],),
            ).fetchall()

        finally:
            conn.close()

        # Check MFA
        try:
            from education_system.shared.auth.mfa_service import MFAService
            mfa_svc = MFAService(self._db_path)
            if mfa_svc.is_mfa_enabled(user["id"]):
                return {
                    "mfa_required": True,
                    "user_id": user["id"],
                    "username": user["username"],
                }
        except ImportError:
            pass

        # Create session
        token = self.session_manager.create_session(user["id"])

        self._current_user = {
            "user_id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"] or user["username"],
            "email": user["email"],
            "systems": [
                {"system_key": s["system_key"], "role": s["role"]}
                for s in systems
            ],
        }
        self._current_token = token
        logger.info("User '%s' logged in", user["username"])

        return self._current_user

    def verify_mfa(self, user_id: int, code: str) -> dict:
        """Complete login after MFA verification."""
        from education_system.shared.auth.mfa_service import MFAService
        mfa_svc = MFAService(self._db_path)

        if not mfa_svc.verify_totp(user_id, code):
            if not mfa_svc.verify_recovery_code(user_id, code):
                logger.warning("MFA verification failed for user_id=%d", user_id)
                raise AuthError("Invalid MFA code.")

        conn = self._conn()
        try:
            user = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if not user:
                raise AuthError("User not found.")

            systems = conn.execute(
                "SELECT system_key, role FROM user_systems WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        finally:
            conn.close()

        token = self.session_manager.create_session(user["id"])

        self._current_user = {
            "user_id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"] or user["username"],
            "email": user["email"],
            "systems": [
                {"system_key": s["system_key"], "role": s["role"]}
                for s in systems
            ],
        }
        self._current_token = token
        logger.info("MFA verified for user '%s'", user["username"])

        return self._current_user

    def complete_mfa_login(self, user_id: int) -> dict:
        """Complete login after MFA was already verified externally (e.g. email OTP).

        Same as verify_mfa but without re-checking the code.
        """
        conn = self._conn()
        try:
            user = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if not user:
                raise AuthError("User not found.")

            systems = conn.execute(
                "SELECT system_key, role FROM user_systems WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        finally:
            conn.close()

        token = self.session_manager.create_session(user["id"])

        self._current_user = {
            "user_id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"] or user["username"],
            "email": user["email"],
            "systems": [
                {"system_key": s["system_key"], "role": s["role"]}
                for s in systems
            ],
        }
        self._current_token = token
        logger.info("MFA login completed for user '%s' (external verification)", user["username"])

        return self._current_user

    def get_role_for_system(self, system_key: str) -> str | None:
        """Get the current user's role for a specific system."""
        if not self._current_user:
            return None
        for s in self._current_user.get("systems", []):
            if s["system_key"] == system_key:
                return s["role"]
        return None

    def logout(self):
        """Logout the current user."""
        logger.info(
            "User logged out: %s",
            self._current_user.get("username", "?") if self._current_user else "unknown",
        )
        if self._current_token:
            self.session_manager.invalidate_session(self._current_token)
        self._current_user = None
        self._current_token = None

    def create_user(
        self, username: str, password: str, display_name: str | None = None,
        email: str | None = None, systems: list[tuple[str, str]] | None = None,
    ) -> int:
        """Create a new user account. Returns the user ID.

        *systems* is a list of (system_key, role) tuples.
        """
        is_valid, msg = validate_password_strength(password)
        if not is_valid:
            raise AuthError(msg)

        pw_hash = hash_password(password)
        conn = self._conn()
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, display_name, email) VALUES (?, ?, ?, ?)",
                (username, pw_hash, display_name, email),
            )
            user_id = cursor.lastrowid
            if systems:
                for system_key, role in systems:
                    conn.execute(
                        "INSERT INTO user_systems (user_id, system_key, role) VALUES (?, ?, ?)",
                        (user_id, system_key, role),
                    )
            conn.commit()
            logger.info("User created: '%s' (id=%d)", username, user_id)
            return user_id
        except Exception as e:
            conn.rollback()
            if "UNIQUE" in str(e):
                raise AuthError(f"Username '{username}' already exists.") from e
            raise AuthError(f"Failed to create user: {e}") from e
        finally:
            conn.close()

    def change_password(self, user_id: int, old_password: str, new_password: str):
        """Change a user's password."""
        conn = self._conn()
        try:
            user = conn.execute(
                "SELECT password_hash, legacy_salt FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if not user:
                raise AuthError("User not found.")

            legacy_salt = user["legacy_salt"] if "legacy_salt" in user.keys() else None
            if not verify_password(old_password, user["password_hash"], legacy_salt=legacy_salt):
                raise AuthError("Current password is incorrect.")

            is_valid, msg = validate_password_strength(new_password)
            if not is_valid:
                raise AuthError(msg)

            new_hash = hash_password(new_password)
            conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = datetime('now') WHERE id = ?",
                (new_hash, user_id),
            )
            conn.commit()
            logger.info("Password changed for user_id=%d", user_id)

            self.session_manager.invalidate_user_sessions(user_id)
        finally:
            conn.close()

    def get_user_by_id(self, user_id: int) -> dict | None:
        """Get user info by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT id, username, display_name, email, is_active, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
