"""Session token management using the shared auth database."""

import secrets
from datetime import datetime, timedelta
import logging

from education_system.shared.auth.defaults import SESSION_TIMEOUT_MINUTES
from education_system.shared.auth.db import connect

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages user sessions with token-based authentication."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_session(self, user_id: int) -> str:
        """Create a new session and return the token."""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=SESSION_TIMEOUT_MINUTES)

        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
                (user_id, token, expires_at.isoformat()),
            )
            conn.commit()
            logger.debug("Session created for user_id=%d", user_id)
        finally:
            conn.close()

        return token

    def validate_session(self, token: str) -> dict | None:
        """Validate a session token. Returns user info if valid, None otherwise."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT s.user_id, s.expires_at, u.username
                   FROM sessions s JOIN users u ON s.user_id = u.id
                   WHERE s.token = ? AND s.is_active = 1""",
                (token,),
            ).fetchone()

            if not row:
                return None

            if datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():
                self.invalidate_session(token)
                return None

            return {
                "user_id": row["user_id"],
                "username": row["username"],
            }
        finally:
            conn.close()

    def invalidate_session(self, token: str):
        """Invalidate a session token."""
        conn = self._conn()
        try:
            conn.execute("UPDATE sessions SET is_active = 0 WHERE token = ?", (token,))
            conn.commit()
        finally:
            conn.close()

    def invalidate_user_sessions(self, user_id: int):
        """Invalidate all sessions for a user."""
        conn = self._conn()
        try:
            conn.execute("UPDATE sessions SET is_active = 0 WHERE user_id = ?", (user_id,))
            conn.commit()
        finally:
            conn.close()

    def cleanup_expired(self):
        """Remove expired sessions from the database."""
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM sessions WHERE expires_at < ? OR is_active = 0",
                (datetime.utcnow().isoformat(),),
            )
            conn.commit()
        finally:
            conn.close()
