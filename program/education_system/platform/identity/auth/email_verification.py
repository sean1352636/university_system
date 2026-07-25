"""Email verification service for user accounts.

Generates time-limited verification tokens and marks accounts as verified
once the token is confirmed. Tokens are hashed (SHA-256) before storage.
"""

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta

from education_system.platform.identity.auth.db import connect
from education_system.platform.identity.auth.exceptions import AuthError

logger = logging.getLogger(__name__)

_TOKEN_EXPIRY_HOURS = 24


class EmailVerificationService:
    """Manages email verification tokens and status."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def send_verification(self, user_id: int) -> dict:
        """Generate a verification token and send it to the user's email.

        Returns a dict with the token (for dev/testing) and email.
        """
        conn = self._conn()
        try:
            user = conn.execute(
                "SELECT id, username, email, email_verified FROM users WHERE id = ? AND is_active = 1",
                (user_id,),
            ).fetchone()

            if not user:
                raise AuthError("User not found.")
            if not user["email"]:
                raise AuthError("No email address on file.")
            if user["email_verified"]:
                raise AuthError("Email is already verified.")

            # Invalidate previous tokens
            conn.execute(
                "DELETE FROM email_verification_tokens WHERE user_id = ?",
                (user_id,),
            )

            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            expires_at = (datetime.utcnow() + timedelta(hours=_TOKEN_EXPIRY_HOURS)).isoformat()

            conn.execute(
                "INSERT INTO email_verification_tokens (user_id, token_hash, email, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (user_id, token_hash, user["email"], expires_at),
            )
            conn.commit()
        finally:
            conn.close()

        self._send_email(user["email"], user["username"], raw_token, expires_at)

        logger.info("Verification email sent for user_id=%d", user_id)
        return {"sent": True, "email": user["email"], "token": raw_token}

    def verify(self, token: str) -> dict:
        """Verify an email using the provided token.

        Marks the user's email as verified and deletes the token.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT evt.user_id, evt.email, evt.expires_at, u.username
                   FROM email_verification_tokens evt
                   JOIN users u ON u.id = evt.user_id
                   WHERE evt.token_hash = ? AND u.is_active = 1""",
                (token_hash,),
            ).fetchone()

            if not row:
                raise AuthError("Invalid or expired verification token.")

            if datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():
                conn.execute(
                    "DELETE FROM email_verification_tokens WHERE token_hash = ?",
                    (token_hash,),
                )
                conn.commit()
                raise AuthError("Verification token has expired. Please request a new one.")

            conn.execute(
                "UPDATE users SET email_verified = 1, updated_at = datetime('now') WHERE id = ?",
                (row["user_id"],),
            )
            conn.execute(
                "DELETE FROM email_verification_tokens WHERE user_id = ?",
                (row["user_id"],),
            )
            conn.commit()

            logger.info("Email verified for user_id=%d (%s)", row["user_id"], row["email"])
            return {
                "user_id": row["user_id"],
                "username": row["username"],
                "email": row["email"],
            }
        finally:
            conn.close()

    def is_verified(self, user_id: int) -> bool:
        """Check whether a user's email is verified."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT email_verified FROM users WHERE id = ?", (user_id,),
            ).fetchone()
            return bool(row and row["email_verified"])
        finally:
            conn.close()

    @staticmethod
    def _send_email(email: str, username: str, token: str, expires_at: str):
        """Send the verification email.  Fails silently if email is not configured."""
        try:
            from education_system.platform.integrations.email.config import load_email_config
            from email.mime.text import MIMEText
            import smtplib

            cfg = load_email_config()
            smtp_server = cfg.get("smtp_server", "")
            smtp_port = cfg.get("smtp_port", 587)
            smtp_user = cfg.get("smtp_username", "")
            smtp_pass = cfg.get("smtp_password", "")
            use_tls = cfg.get("use_tls", True)
            sender = cfg.get("sender_email", smtp_user)

            if not all([smtp_server, smtp_user, smtp_pass]):
                logger.debug("Email not configured — skipping verification email")
                return

            base_url = os.getenv("APP_BASE_URL", "http://localhost:5000")
            verify_link = f"{base_url}/web/verify-email?token={token}"

            body = (
                f"Hello {username},\n\n"
                f"Please verify your email address by clicking the link below:\n"
                f"  {verify_link}\n\n"
                f"This link expires at {expires_at}.\n\n"
                f"If you did not create this account, you can safely ignore this email.\n"
            )

            msg = MIMEText(body)
            msg["Subject"] = "Education System — Email Verification"
            msg["From"] = sender
            msg["To"] = email

            server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
            if use_tls:
                server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(sender, [email], msg.as_string())
            server.quit()
            logger.info("Verification email sent to %s", email)
        except Exception as exc:
            logger.debug("Could not send verification email: %s", exc)
