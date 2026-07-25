"""Session token management using the shared auth database."""

import secrets
from datetime import datetime, timedelta
import logging

from education_system.platform.identity.auth.defaults import SESSION_TIMEOUT_MINUTES, MAX_SESSIONS_PER_USER
from education_system.platform.identity.auth.db import connect

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages user sessions with token-based authentication."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_session(self, user_id: int) -> str:
        """Create a new session and return the token.

        Enforces a maximum number of concurrent sessions per user.  When
        the limit is reached, the oldest active session is revoked to make
        room for the new one.
        """
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=SESSION_TIMEOUT_MINUTES)

        conn = self._conn()
        try:
            # Evict expired sessions first
            conn.execute(
                "DELETE FROM sessions WHERE user_id = ? AND (expires_at < ? OR is_active = 0)",
                (user_id, datetime.utcnow().isoformat()),
            )

            # Enforce concurrent session limit
            active = conn.execute(
                "SELECT id FROM sessions WHERE user_id = ? AND is_active = 1 "
                "ORDER BY created_at ASC",
                (user_id,),
            ).fetchall()
            excess = len(active) - MAX_SESSIONS_PER_USER + 1  # +1 for the new session
            if excess > 0:
                ids_to_revoke = [r["id"] for r in active[:excess]]
                placeholders = ",".join("?" * len(ids_to_revoke))
                conn.execute(
                    f"UPDATE sessions SET is_active = 0 WHERE id IN ({placeholders})",  # nosec B608  # IDs are ints from DB
                    ids_to_revoke,
                )
                logger.info(
                    "Evicted %d oldest session(s) for user_id=%d (limit %d)",
                    excess, user_id, MAX_SESSIONS_PER_USER,
                )

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

            # Periodically clean up expired sessions (1 in 20 chance per validation)
            import random
            if random.randint(1, 20) == 1:
                try:
                    conn.execute(
                        "DELETE FROM sessions WHERE expires_at < ? OR is_active = 0",
                        (datetime.utcnow().isoformat(),),
                    )
                    conn.commit()
                except Exception as exc:
                    # Non-critical cleanup, but log so a persistent DB
                    # failure surfaces in operational dashboards instead
                    # of silently letting expired rows accumulate.
                    logger.warning("Session cleanup failed: %s", exc)

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
