"""Forgot password service using security question verification.

Allows users to reset their password by providing their username and
correctly answering their 3 security questions. On success a temporary
password is generated and the account is flagged so that the user is
forced to change their password on next login.
"""

import hashlib
import json
import logging
import os
import secrets
import string
from datetime import datetime
from pathlib import Path
from string import Template

from education_system.shared.auth.db import connect
from education_system.shared.auth.exceptions import AuthError
from education_system.shared.auth.password_manager import hash_password
from education_system.shared.auth.session_manager import SessionManager

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"


def _hash_answer(answer: str) -> str:
    """Hash a security-question answer (case-insensitive)."""
    return hashlib.sha256(answer.strip().lower().encode()).hexdigest()


def _generate_temp_password(length: int = 16) -> str:
    """Generate a random temporary password that meets strength rules."""
    # Guarantee at least one of each required character class
    chars = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*"),
    ]
    remaining = length - len(chars)
    pool = string.ascii_letters + string.digits + "!@#$%^&*"
    chars.extend(secrets.choice(pool) for _ in range(remaining))
    # Shuffle so the guaranteed chars aren't always at the front
    result = list(chars)
    secrets.SystemRandom().shuffle(result)
    return "".join(result)


def _load_email_template(name: str) -> dict | None:
    """Load a JSON email template by name from the shared templates dir."""
    path = _TEMPLATES_DIR / f"{name}.json"
    if not path.exists():
        logger.warning("Email template not found: %s", path)
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load email template %s: %s", name, exc)
        return None


def _render_template(template: dict, **kwargs) -> tuple[str, str | None]:
    """Render a JSON email template. Returns (subject, body).

    Templates use $variable placeholder syntax (string.Template).
    If the template has an ``html_body`` key it is also rendered.
    """
    subject = Template(template.get("subject", "")).safe_substitute(**kwargs)
    body = Template(template.get("body", "")).safe_substitute(**kwargs)
    html_body = None
    if "html_body" in template:
        html_body = Template(template["html_body"]).safe_substitute(**kwargs)
    return subject, body, html_body


class ForgotPasswordService:
    """Forgot password via security question verification."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def get_questions_for_user(self, username: str) -> list[dict]:
        """Return the security questions (without answers) for a user.

        Returns a list of ``{"id": int, "question": str}`` dicts.
        Raises AuthError if the user doesn't exist or has no questions.
        """
        conn = self._conn()
        try:
            user = conn.execute(
                "SELECT id FROM users WHERE username = ? AND is_active = 1",
                (username.strip(),),
            ).fetchone()
            if not user:
                raise AuthError("No account found with that username.")

            rows = conn.execute(
                "SELECT id, question FROM security_questions WHERE user_id = ? ORDER BY id",
                (user["id"],),
            ).fetchall()
            if not rows:
                raise AuthError(
                    "No security questions are set up for this account. "
                    "Please contact an administrator."
                )
            return [{"id": r["id"], "question": r["question"]} for r in rows]
        finally:
            conn.close()

    def verify_answers_and_reset(
        self, username: str, answers: dict[int, str],
    ) -> dict:
        """Verify security question answers and reset the password.

        Args:
            username: The user's username.
            answers: Mapping of question ID → user's answer string.

        Returns:
            Dict with ``temp_password``, ``username``, ``display_name``,
            ``email``, and ``user_id`` on success.

        Raises:
            AuthError if any answer is wrong or the user doesn't exist.
        """
        conn = self._conn()
        try:
            user = conn.execute(
                "SELECT id, username, display_name, email FROM users "
                "WHERE username = ? AND is_active = 1",
                (username.strip(),),
            ).fetchone()
            if not user:
                raise AuthError("No account found with that username.")

            # Fetch all security questions for this user
            rows = conn.execute(
                "SELECT id, answer_hash FROM security_questions WHERE user_id = ?",
                (user["id"],),
            ).fetchall()
            stored = {r["id"]: r["answer_hash"] for r in rows}

            if not stored:
                raise AuthError("No security questions configured for this account.")

            # Verify every stored question was answered correctly
            for qid, expected_hash in stored.items():
                user_answer = answers.get(qid, "")
                if _hash_answer(user_answer) != expected_hash:
                    logger.warning(
                        "Security question verification failed for user '%s' (q_id=%d)",
                        username, qid,
                    )
                    raise AuthError("One or more answers are incorrect.")

            # All correct — generate temp password and reset
            temp_pw = _generate_temp_password()
            pw_hash = hash_password(temp_pw)

            # Save old hash to password history
            old_hash_row = conn.execute(
                "SELECT password_hash FROM users WHERE id = ?", (user["id"],)
            ).fetchone()
            if old_hash_row:
                conn.execute(
                    "INSERT INTO password_history (user_id, password_hash) VALUES (?, ?)",
                    (user["id"], old_hash_row["password_hash"]),
                )

            # Update password and mark as expired (password_changed_at = NULL forces change)
            conn.execute(
                "UPDATE users SET password_hash = ?, password_changed_at = NULL, "
                "failed_login_attempts = 0, locked_until = NULL, "
                "updated_at = datetime('now') WHERE id = ?",
                (pw_hash, user["id"]),
            )
            conn.commit()

            # Invalidate all existing sessions
            SessionManager(self._db_path).invalidate_user_sessions(user["id"])

            logger.info(
                "Password reset via security questions for user '%s' (id=%d)",
                username, user["id"],
            )

            result = {
                "temp_password": temp_pw,
                "user_id": user["id"],
                "username": user["username"],
                "display_name": user["display_name"] or user["username"],
                "email": user["email"],
            }

            # Send notification emails (best-effort, don't block on failure)
            self._send_notifications(result)

            return result
        finally:
            conn.close()

    def set_security_questions(
        self, user_id: int, questions: list[tuple[str, str]],
    ):
        """Set or replace security questions for a user.

        Args:
            user_id: The user's ID.
            questions: List of (question_text, answer) tuples. Minimum 3.
        """
        if len(questions) < 3:
            raise AuthError("At least 3 security questions are required.")

        conn = self._conn()
        try:
            conn.execute("DELETE FROM security_questions WHERE user_id = ?", (user_id,))
            for question, answer in questions:
                if not question.strip() or not answer.strip():
                    raise AuthError("Questions and answers cannot be empty.")
                conn.execute(
                    "INSERT INTO security_questions (user_id, question, answer_hash) "
                    "VALUES (?, ?, ?)",
                    (user_id, question.strip(), _hash_answer(answer)),
                )
            conn.commit()
            logger.info("Security questions updated for user_id=%d", user_id)
        finally:
            conn.close()

    def has_security_questions(self, username: str) -> bool:
        """Check whether a user has security questions configured."""
        conn = self._conn()
        try:
            user = conn.execute(
                "SELECT id FROM users WHERE username = ? AND is_active = 1",
                (username.strip(),),
            ).fetchone()
            if not user:
                return False
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM security_questions WHERE user_id = ?",
                (user["id"],),
            ).fetchone()
            return row["cnt"] >= 3
        finally:
            conn.close()

    # ------------------------------------------------------------------
    #  Email notifications
    # ------------------------------------------------------------------

    def _send_notifications(self, reset_info: dict):
        """Send admin and student notification emails after a reset."""
        try:
            from education_system.shared.email.email_service import EmailService
            svc = EmailService()
            if not svc.is_configured:
                logger.info("SMTP not configured — skipping reset notification emails")
                return

            now = datetime.now().strftime("%Y-%m-%d %H:%M")

            # 1. Notify admin
            self._send_admin_notification(svc, reset_info, now)

            # 2. Notify the user
            self._send_student_notification(svc, reset_info, now)

        except Exception as exc:
            logger.warning("Failed to send password reset notification emails: %s", exc)

    def _send_admin_notification(self, svc, reset_info: dict, timestamp: str):
        """Email admin that a user's password was reset via security questions."""
        template = _load_email_template("password_reset_admin_notification")
        if not template:
            return

        subject, body, html_body = _render_template(
            template,
            username=reset_info["username"],
            display_name=reset_info["display_name"],
            email=reset_info.get("email", "N/A"),
            user_id=str(reset_info["user_id"]),
            reset_time=timestamp,
            system_name="Education System",
        )

        # Send to the configured sender (admin) email
        from education_system.shared.email.config import load_email_config
        cfg = load_email_config()
        admin_email = cfg.get("sender_email", "")
        if admin_email:
            result = svc.send_email(admin_email, subject, body, html_body=html_body)
            if result.get("success"):
                logger.info("Admin notification sent for password reset of '%s'", reset_info["username"])
            else:
                logger.warning("Failed to send admin notification: %s", result.get("error"))

    def _send_student_notification(self, svc, reset_info: dict, timestamp: str):
        """Email the user confirming their password was reset."""
        user_email = reset_info.get("email")
        if not user_email:
            return

        template = _load_email_template("password_reset_student_notification")
        if not template:
            return

        subject, body, html_body = _render_template(
            template,
            username=reset_info["username"],
            display_name=reset_info["display_name"],
            email=user_email,
            reset_time=timestamp,
            system_name="Education System",
        )

        result = svc.send_email(user_email, subject, body, html_body=html_body)
        if result.get("success"):
            logger.info("Student notification sent to '%s' for password reset", user_email)
        else:
            logger.warning("Failed to send student notification: %s", result.get("error"))
