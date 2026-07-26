"""Secure password reset token generation and validation."""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from education_system.platform.identity.auth.db import connect
from education_system.platform.identity.auth.password_manager import hash_password, validate_password_strength
from education_system.platform.identity.auth.exceptions import AuthError

logger = logging.getLogger(__name__)

_TOKEN_EXPIRY_MINUTES = 30


class PasswordResetService:
    """Manages password reset tokens and execution."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def request_reset(self, email: str) -> dict:
        """Generate a password reset token for the given email.

        Returns a dict with token and user info, or raises AuthError.
        The caller is responsible for sending the token to the user
        (e.g. via email).
        """
        conn = self._conn()
        try:
            user = conn.execute(
                "SELECT id, username, email, is_active FROM users WHERE email = ? AND is_active = 1",
                (email.strip().lower(),),
            ).fetchone()

            if not user:
                # Don't reveal whether email exists
                logger.info("Password reset requested for unknown email")
                return {"sent": True}

            # Generate secure token
            raw_token = secrets.token_urlsafe(48)
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            expires_at = (datetime.utcnow() + timedelta(minutes=_TOKEN_EXPIRY_MINUTES)).isoformat()

            # Store hashed token (invalidate any previous tokens)
            conn.execute(
                "DELETE FROM password_reset_tokens WHERE user_id = ?",
                (user["id"],),
            )
            conn.execute(
                "INSERT INTO password_reset_tokens (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
                (user["id"], token_hash, expires_at),
            )
            conn.commit()

            logger.info("Password reset token generated for user_id=%d", user["id"])
            return {
                "sent": True,
                "token": raw_token,
                "user_id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "expires_at": expires_at,
            }
        finally:
            conn.close()

    def validate_token(self, token: str) -> dict:
        """Validate a reset token. Returns user info if valid."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT prt.user_id, prt.expires_at, u.username, u.email
                   FROM password_reset_tokens prt
                   JOIN users u ON u.id = prt.user_id
                   WHERE prt.token_hash = ? AND u.is_active = 1""",
                (token_hash,),
            ).fetchone()

            if not row:
                raise AuthError("Invalid or expired reset token.")

            if datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():
                conn.execute(
                    "DELETE FROM password_reset_tokens WHERE token_hash = ?",
                    (token_hash,),
                )
                conn.commit()
                raise AuthError("Reset token has expired. Please request a new one.")

            return {
                "user_id": row["user_id"],
                "username": row["username"],
                "email": row["email"],
            }
        finally:
            conn.close()

    def reset_password(self, token: str, new_password: str) -> bool:
        """Reset password using a valid token."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        is_valid, msg = validate_password_strength(new_password)
        if not is_valid:
            raise AuthError(msg)

        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT prt.user_id, prt.expires_at
                   FROM password_reset_tokens prt
                   JOIN users u ON u.id = prt.user_id
                   WHERE prt.token_hash = ? AND u.is_active = 1""",
                (token_hash,),
            ).fetchone()

            if not row:
                raise AuthError("Invalid or expired reset token.")

            if datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():
                conn.execute("DELETE FROM password_reset_tokens WHERE token_hash = ?", (token_hash,))
                conn.commit()
                raise AuthError("Reset token has expired.")

            new_hash = hash_password(new_password)
            conn.execute(
                "UPDATE users SET password_hash = ?, password_changed_at = datetime('now'), "
                "failed_login_attempts = 0, locked_until = NULL WHERE id = ?",
                (new_hash, row["user_id"]),
            )
            # Save to password history
            conn.execute(
                "INSERT INTO password_history (user_id, password_hash) VALUES (?, ?)",
                (row["user_id"], new_hash),
            )
            # Delete the used token
            conn.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (row["user_id"],))
            conn.commit()

            # Invalidate all sessions
            from education_system.platform.identity.auth.session_manager import SessionManager
            SessionManager(self._db_path).invalidate_user_sessions(row["user_id"])

            logger.info("Password reset completed for user_id=%d", row["user_id"])
            return True
        finally:
            conn.close()
