"""Forgot password service using security question verification.

Allows users to reset their password by providing their username and
correctly answering their 3 security questions. On success a temporary
password is generated and the account is flagged so that the user is
forced to change their password on next login.

Security features:
- Brute-force protection: 5 attempts per user per hour, then 15-min lockout
- Enumeration prevention: generic error messages for all lookup failures
- Bcrypt answer hashing with legacy SHA-256 fallback
- Structured audit logging for SOC/ops monitoring
- Answer policy: minimum length + banned common answers
"""

import json
import logging
import secrets
import string
from datetime import datetime, timedelta
from pathlib import Path
from string import Template

from education_system.shared.auth.db import connect
from education_system.shared.auth.exceptions import AuthError
from education_system.shared.auth.password_manager import hash_password
from education_system.shared.auth.schema import (
    _hash_answer,
    _verify_answer,
    rehash_answer_if_legacy,
    validate_answer,
    BANNED_ANSWERS,
    MIN_ANSWER_LENGTH,
)
from education_system.shared.auth.session_manager import SessionManager

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"

# ── Rate-limiting constants ──────────────────────────────────────────────────
MAX_SQ_ATTEMPTS_PER_USER = 5     # max failed attempts per username within window
MAX_SQ_ATTEMPTS_PER_IP = 15      # max failed attempts per IP within window
MAX_SQ_ATTEMPTS_GLOBAL = 50      # global burst limit within window
SQ_ATTEMPT_WINDOW_MINUTES = 60   # rolling window for attempt counting

# Keep the old name as an alias for tests
MAX_SQ_ATTEMPTS = MAX_SQ_ATTEMPTS_PER_USER

# Generic error shown to the user for all lookup/verification failures.
# Specific reason is logged server-side only.
_GENERIC_VERIFY_ERROR = "Unable to verify your identity. Please try again or contact an administrator."


def _generate_temp_password(length: int = 16) -> str:
    """Generate a random temporary password that meets strength rules."""
    chars = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*"),
    ]
    remaining = length - len(chars)
    pool = string.ascii_letters + string.digits + "!@#$%^&*"
    chars.extend(secrets.choice(pool) for _ in range(remaining))
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


def _render_template(template: dict, **kwargs) -> tuple[str, str, str | None]:
    """Render a JSON email template. Returns (subject, body, html_body)."""
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

    # ------------------------------------------------------------------
    #  Audit logging
    # ------------------------------------------------------------------

    def _audit(self, event_type: str, username: str | None = None,
               user_id: int | None = None, detail: str | None = None,
               ip_address: str | None = None):
        """Write a structured event to the local security_audit_log and
        forward to the centralized AuditService for single-pane-of-glass
        monitoring.
        """
        # Local auth-DB log (always, for the forgot-password tests)
        try:
            conn = self._conn()
            try:
                conn.execute(
                    "INSERT INTO security_audit_log "
                    "(event_type, username, user_id, detail, ip_address) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (event_type, username, user_id, detail, ip_address),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            logger.debug("Local audit log write failed: %s", exc)

        # Forward to centralized AuditService (best-effort)
        try:
            from education_system.shared.audit.audit_service import AuditService
            audit = AuditService()
            audit.log_security(
                action=event_type,
                system_key="shared",
                username=username,
                user_id=user_id,
                details=detail,
                ip_address=ip_address,
            )
        except Exception:
            pass  # Centralized audit unavailable — local log is authoritative

    # ------------------------------------------------------------------
    #  Rate limiting
    # ------------------------------------------------------------------

    def _check_rate_limit(self, conn, username: str,
                          ip_address: str | None = None) -> str | None:
        """Check per-user, per-IP, and global burst rate limits.

        Returns a reason string if the request should be BLOCKED, or
        None if allowed.
        """
        cutoff = (datetime.utcnow() - timedelta(minutes=SQ_ATTEMPT_WINDOW_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")

        # Per-user limit
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM sq_verification_attempts "
            "WHERE username = ? AND success = 0 AND created_at > ?",
            (username, cutoff),
        ).fetchone()
        if row["cnt"] >= MAX_SQ_ATTEMPTS_PER_USER:
            return f"per-user limit ({MAX_SQ_ATTEMPTS_PER_USER})"

        # Per-IP limit
        if ip_address:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM sq_verification_attempts "
                "WHERE ip_address = ? AND success = 0 AND created_at > ?",
                (ip_address, cutoff),
            ).fetchone()
            if row["cnt"] >= MAX_SQ_ATTEMPTS_PER_IP:
                return f"per-IP limit ({MAX_SQ_ATTEMPTS_PER_IP})"

        # Global burst limit
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM sq_verification_attempts "
            "WHERE success = 0 AND created_at > ?",
            (cutoff,),
        ).fetchone()
        if row["cnt"] >= MAX_SQ_ATTEMPTS_GLOBAL:
            return f"global burst limit ({MAX_SQ_ATTEMPTS_GLOBAL})"

        return None

    def _record_attempt(self, conn, username: str, success: bool,
                        ip_address: str | None = None):
        """Record a security-question verification attempt.

        Uses the *caller's* connection so the rate-limit check within
        the same transaction sees the latest state.
        """
        conn.execute(
            "INSERT INTO sq_verification_attempts "
            "(username, success, ip_address) VALUES (?, ?, ?)",
            (username, 1 if success else 0, ip_address),
        )
        conn.commit()

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def get_questions_for_user(self, username: str) -> list[dict]:
        """Return the security questions (without answers) for a user.

        Returns a list of ``{"id": int, "question": str}`` dicts.
        Raises AuthError with a *generic* message on any failure to
        prevent username/account enumeration.
        """
        conn = self._conn()
        try:
            user = conn.execute(
                "SELECT id FROM users WHERE username = ? AND is_active = 1",
                (username.strip(),),
            ).fetchone()
            if not user:
                logger.info("SQ lookup: unknown username '%s'", username)
                self._audit("sq_lookup_unknown_user", username=username)
                raise AuthError(_GENERIC_VERIFY_ERROR)

            rows = conn.execute(
                "SELECT id, question FROM security_questions WHERE user_id = ? ORDER BY id",
                (user["id"],),
            ).fetchall()
            if not rows:
                logger.info("SQ lookup: no questions for user '%s'", username)
                self._audit("sq_lookup_no_questions", username=username, user_id=user["id"])
                raise AuthError(_GENERIC_VERIFY_ERROR)

            self._audit("sq_lookup_success", username=username, user_id=user["id"])
            return [{"id": r["id"], "question": r["question"]} for r in rows]
        finally:
            conn.close()

    def verify_answers_and_reset(
        self, username: str, answers: dict[int, str],
        ip_address: str | None = None,
    ) -> dict:
        """Verify security question answers and reset the password.

        Args:
            username: The user's username.
            answers: Mapping of question ID → user's answer string.
            ip_address: Optional client IP for audit/rate-limit tracking.

        Returns:
            Dict with ``temp_password``, ``username``, ``display_name``,
            ``email``, and ``user_id`` on success.

        Raises:
            AuthError with a generic message on any failure.
        """
        conn = self._conn()
        try:
            # Rate-limit check (per-user, per-IP, global)
            limit_reason = self._check_rate_limit(conn, username, ip_address)
            if limit_reason:
                logger.warning(
                    "SQ verification rate-limited for user '%s': %s",
                    username, limit_reason,
                )
                self._audit("sq_rate_limited", username=username,
                            detail=limit_reason, ip_address=ip_address)
                raise AuthError(
                    "Too many failed attempts. Please wait before trying again."
                )

            user = conn.execute(
                "SELECT id, username, display_name, email FROM users "
                "WHERE username = ? AND is_active = 1",
                (username.strip(),),
            ).fetchone()
            if not user:
                logger.info("SQ verify: unknown username '%s'", username)
                self._record_attempt(conn, username, success=False, ip_address=ip_address)
                self._audit("sq_verify_unknown_user", username=username, ip_address=ip_address)
                raise AuthError(_GENERIC_VERIFY_ERROR)

            rows = conn.execute(
                "SELECT id, answer_hash FROM security_questions WHERE user_id = ?",
                (user["id"],),
            ).fetchall()
            stored = {r["id"]: r["answer_hash"] for r in rows}

            if not stored:
                logger.info("SQ verify: no questions for user '%s'", username)
                self._record_attempt(conn, username, success=False, ip_address=ip_address)
                self._audit("sq_verify_no_questions", username=username,
                            user_id=user["id"], ip_address=ip_address)
                raise AuthError(_GENERIC_VERIFY_ERROR)

            # Verify every stored question
            legacy_rehashes = []
            for qid, expected_hash in stored.items():
                user_answer = answers.get(qid, "")
                if not _verify_answer(user_answer, expected_hash):
                    logger.warning(
                        "SQ verification failed for user '%s' (q_id=%d)",
                        username, qid,
                    )
                    self._record_attempt(conn, username, success=False, ip_address=ip_address)
                    self._audit("sq_verify_failed", username=username,
                                user_id=user["id"], detail=f"failed_question={qid}",
                                ip_address=ip_address)
                    raise AuthError(_GENERIC_VERIFY_ERROR)
                # Queue legacy SHA-256 → bcrypt rehash
                new_hash = rehash_answer_if_legacy(user_answer, expected_hash)
                if new_hash:
                    legacy_rehashes.append((qid, new_hash))

            # Opportunistic rehash of legacy SHA-256 answer hashes to bcrypt
            for qid, new_hash in legacy_rehashes:
                conn.execute(
                    "UPDATE security_questions SET answer_hash = ?, "
                    "updated_at = datetime('now') WHERE id = ?",
                    (new_hash, qid),
                )
            if legacy_rehashes:
                conn.commit()
                logger.info(
                    "Rehashed %d legacy SHA-256 answer(s) to bcrypt for user '%s'",
                    len(legacy_rehashes), username,
                )

            # All correct — generate temp password and reset
            self._record_attempt(conn, username, success=True, ip_address=ip_address)

            temp_pw = _generate_temp_password()
            pw_hash = hash_password(temp_pw)

            old_hash_row = conn.execute(
                "SELECT password_hash FROM users WHERE id = ?", (user["id"],)
            ).fetchone()
            if old_hash_row:
                conn.execute(
                    "INSERT INTO password_history (user_id, password_hash) VALUES (?, ?)",
                    (user["id"], old_hash_row["password_hash"]),
                )

            conn.execute(
                "UPDATE users SET password_hash = ?, password_changed_at = NULL, "
                "failed_login_attempts = 0, locked_until = NULL, "
                "updated_at = datetime('now') WHERE id = ?",
                (pw_hash, user["id"]),
            )
            conn.commit()

            SessionManager(self._db_path).invalidate_user_sessions(user["id"])

            logger.info(
                "Account reset via security questions for user '%s' (id=%d)",
                username, user["id"],
            )
            self._audit("sq_reset_success", username=username,
                        user_id=user["id"], ip_address=ip_address)

            result = {
                "temp_password": temp_pw,
                "user_id": user["id"],
                "username": user["username"],
                "display_name": user["display_name"] or user["username"],
                "email": user["email"],
            }

            self._send_notifications(result)
            return result
        finally:
            conn.close()

    def set_security_questions(
        self, user_id: int, questions: list[tuple[str, str]],
    ):
        """Set or replace security questions for a user.

        Validates answers against policy (minimum length, banned answers).
        """
        if len(questions) < 3:
            raise AuthError("At least 3 security questions are required.")

        for question, answer in questions:
            if not question.strip():
                raise AuthError("Questions cannot be empty.")
            valid, msg = validate_answer(answer)
            if not valid:
                raise AuthError(msg)

        conn = self._conn()
        try:
            conn.execute("DELETE FROM security_questions WHERE user_id = ?", (user_id,))
            for question, answer in questions:
                conn.execute(
                    "INSERT INTO security_questions (user_id, question, answer_hash) "
                    "VALUES (?, ?, ?)",
                    (user_id, question.strip(), _hash_answer(answer)),
                )
            conn.commit()
            logger.info("Security questions updated for user_id=%d", user_id)
            self._audit("sq_questions_updated", user_id=user_id)
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
            self._send_admin_notification(svc, reset_info, now)
            self._send_student_notification(svc, reset_info, now)
        except Exception as exc:
            logger.warning("Failed to send account reset notification emails: %s", exc)

    def _send_admin_notification(self, svc, reset_info: dict, timestamp: str):
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
        from education_system.shared.email.config import load_email_config
        cfg = load_email_config()
        admin_email = cfg.get("sender_email", "")
        if admin_email:
            result = svc.send_email(admin_email, subject, body, html_body=html_body)
            if result.get("success"):
                logger.info("Admin notification sent for account reset of '%s'", reset_info["username"])
            else:
                logger.warning("Failed to send admin notification: %s", result.get("error"))

    def _send_student_notification(self, svc, reset_info: dict, timestamp: str):
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
