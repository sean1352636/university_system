"""JWT utilities with access + refresh token support.

Improvement #6: JWT Refresh Tokens
"""

import secrets
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import jwt
except ImportError:
    jwt = None

_REFRESH_SCHEMA = """
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    role TEXT,
    system_key TEXT,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0,
    replaced_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_refresh_token ON refresh_tokens(token);
CREATE INDEX IF NOT EXISTS idx_refresh_user ON refresh_tokens(user_id);
"""


class JWTManager:
    """Manages access and refresh JWT tokens.

    Usage:
        jwt_mgr = JWTManager(secret="my-secret", db_path="auth.db")
        tokens = jwt_mgr.create_token_pair(user_id=1, username="admin", role="admin")
        new_tokens = jwt_mgr.refresh(tokens["refresh_token"])
        payload = jwt_mgr.decode(tokens["access_token"])
    """

    def __init__(self, secret: str, db_path: str | None = None,
                 access_expiry_minutes: int = 60, refresh_expiry_days: int = 30):
        if jwt is None:
            raise ImportError("PyJWT is required. Install with: pip install PyJWT")
        self.secret = secret
        self.access_expiry_minutes = access_expiry_minutes
        self.refresh_expiry_days = refresh_expiry_days
        self._db_path = db_path
        if db_path:
            self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_REFRESH_SCHEMA)
        finally:
            conn.close()

    def create_access_token(self, user_id: int, username: str, role: str = "student", **extra) -> str:
        """Create a short-lived access token."""
        now = datetime.utcnow()
        payload = {"sub": user_id, "username": username, "role": role,
                    "iat": now, "exp": now + timedelta(minutes=self.access_expiry_minutes),
                    "type": "access", **extra}
        return jwt.encode(payload, self.secret, algorithm="HS256")

    def create_refresh_token(self, user_id: int, username: str,
                              role: str = "student", system_key: str | None = None) -> str:
        """Create a long-lived, opaque refresh token stored in the DB."""
        token = secrets.token_urlsafe(48)
        now = datetime.utcnow()
        expires = now + timedelta(days=self.refresh_expiry_days)

        if self._db_path:
            conn = self._connect()
            try:
                conn.execute(
                    """INSERT INTO refresh_tokens
                       (token, user_id, username, role, system_key, issued_at, expires_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (token, user_id, username, role, system_key, now.isoformat(), expires.isoformat()))
                conn.commit()
            finally:
                conn.close()
        return token

    def create_token_pair(self, user_id: int, username: str, role: str = "student",
                          system_key: str | None = None, **extra) -> dict:
        """Create both access and refresh tokens."""
        return {
            "access_token": self.create_access_token(user_id, username, role, **extra),
            "refresh_token": self.create_refresh_token(user_id, username, role, system_key),
            "token_type": "bearer",
            "expires_in": self.access_expiry_minutes * 60,
        }

    def decode(self, token: str) -> dict | None:
        """Decode and verify an access token."""
        try:
            return jwt.decode(token, self.secret, algorithms=["HS256"])
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

    def refresh(self, refresh_token: str) -> dict | None:
        """Exchange a refresh token for a new token pair (with rotation)."""
        if not self._db_path:
            return None
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM refresh_tokens WHERE token = ? AND revoked = 0",
                (refresh_token,)).fetchone()
            if not row:
                return None
            if datetime.utcnow() > datetime.fromisoformat(row["expires_at"]):
                conn.execute("UPDATE refresh_tokens SET revoked = 1 WHERE token = ?", (refresh_token,))
                conn.commit()
                return None

            new_pair = self.create_token_pair(
                user_id=row["user_id"], username=row["username"],
                role=row["role"] or "student", system_key=row["system_key"])

            conn.execute("UPDATE refresh_tokens SET revoked = 1, replaced_by = ? WHERE token = ?",
                         (new_pair["refresh_token"], refresh_token))
            conn.commit()
            return new_pair
        finally:
            conn.close()

    def revoke(self, refresh_token: str) -> bool:
        """Revoke a refresh token (e.g., on logout)."""
        if not self._db_path:
            return False
        conn = self._connect()
        try:
            cursor = conn.execute(
                "UPDATE refresh_tokens SET revoked = 1 WHERE token = ? AND revoked = 0",
                (refresh_token,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def revoke_all_for_user(self, user_id: int) -> int:
        """Revoke all refresh tokens for a user."""
        if not self._db_path:
            return 0
        conn = self._connect()
        try:
            cursor = conn.execute(
                "UPDATE refresh_tokens SET revoked = 1 WHERE user_id = ? AND revoked = 0",
                (user_id,))
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def cleanup_expired(self) -> int:
        """Remove expired/revoked refresh tokens."""
        if not self._db_path:
            return 0
        conn = self._connect()
        try:
            cursor = conn.execute(
                "DELETE FROM refresh_tokens WHERE expires_at < ? OR revoked = 1",
                (datetime.utcnow().isoformat(),))
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
