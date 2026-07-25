"""Email-based MFA — same wiring the sixth-form system uses.

This module is enrolment-only. The actual login challenge is run by
the shared universal login (``shared/gui/login_gui.py`` and
``shared/cli/login_cli.py``) which already sends an email OTP to
``users.email`` whenever ``mfa_secrets.is_enabled = 1``. To enable
email MFA we therefore need to:

1. Verify the user owns the email address (send a 6-digit code, ask
   them to type it back).
2. Write the verified address into ``users.email`` and flip
   ``mfa_secrets.is_enabled`` to 1 (with a fresh base32 TOTP secret to
   satisfy the NOT NULL column — never shown to the user; the email
   flow drives every subsequent challenge).

After that, every sign-in automatically triggers the email OTP.

Pending verification state (in-flight code + expiry + attempts) lives
in a small ``email_mfa_pending`` table next to ``mfa_secrets``. Codes
are bcrypt-hashed; nothing is stored in plain text. Email delivery
uses the shared SMTP config (``load_email_config``) — when SMTP isn't
configured we raise a clear ``MFAError`` instead of silently dropping
the message.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
import smtplib
import sqlite3
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import bcrypt as _bcrypt
import pyotp

from education_system.platform.identity.auth.db import connect
from education_system.platform.identity.auth.exceptions import MFAError

logger = logging.getLogger(__name__)

CODE_LENGTH = 6
CODE_TTL_MINUTES = 10
MAX_ATTEMPTS_PER_CODE = 5
SEND_COOLDOWN_SECONDS = 30
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Lives in the shared auth DB so it sits next to mfa_secrets and the
# universal login can see / reason about it if it ever needs to.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS email_mfa_pending (
    user_id      INTEGER PRIMARY KEY,
    email        TEXT NOT NULL,
    code_hash    TEXT NOT NULL,
    expires_at   TEXT NOT NULL,
    attempts     INTEGER NOT NULL DEFAULT 0,
    sent_at      TEXT NOT NULL
);
"""
_SCHEMA_READY = False


def _ensure_schema(conn: sqlite3.Connection) -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    conn.executescript(_SCHEMA)
    _SCHEMA_READY = True


# ── Email rendering / sending (mirrors sixth-form's _send_email) ────

_TEMPLATE_FALLBACK = {
    "subject": "Your {{system_name}} verification code: {{code}}",
    "body": (
        "Hi {{username}},\n\n"
        "Use the verification code below to finish setting up multi-factor "
        "authentication on {{system_name}}:\n\n"
        "    {{code}}\n\n"
        "This code expires in {{expiry_minutes}} minutes and can only be "
        "used once.\n\n"
        "If you didn't ask for this code, you can safely ignore this email — "
        "your account stays locked without it.\n\n"
        "For your security, never share this code with anyone.\n\n"
        "Thanks,\nThe {{system_name}} Security Team"
    ),
    "from_name": "Education System Security",
    "from_address": "no-reply@education.local",
}


def _render(template_path: Path | None, *, code: str, username: str,
            system_name: str) -> tuple[str, str, str, str]:
    tpl: dict[str, Any] = dict(_TEMPLATE_FALLBACK)
    if template_path is not None:
        try:
            with template_path.open(encoding="utf-8") as f:
                loaded = json.load(f)
            tpl.update({k: v for k, v in loaded.items() if isinstance(v, str)})
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("MFA template %s load failed (%s) — using fallback",
                           template_path, exc)
    variables = {
        "code": code,
        "username": username,
        "system_name": system_name,
        "expiry_minutes": str(CODE_TTL_MINUTES),
    }

    def render(s: str) -> str:
        for k, v in variables.items():
            s = s.replace("{{" + k + "}}", v)
        return s

    return (
        render(tpl["subject"]),
        render(tpl["body"]),
        tpl["from_name"],
        tpl["from_address"],
    )


def _send_email(to_email: str, code: str, *, username: str,
                system_name: str, template_path: Path | None) -> None:
    """Send the verification email. Raises ``MFAError`` on any failure.

    Matches the sixth-form delivery path: pulls SMTP creds from the
    shared email config, builds a plain-text MIMEMultipart message,
    sends via ``smtplib``. No silent fallbacks — the caller wants to
    know whether the user actually got a code.
    """
    try:
        from education_system.platform.integrations.email.config import load_email_config
    except Exception as exc:
        raise MFAError(
            "Email is not configured on this server — ask an "
            "administrator to set up SMTP before enabling email MFA."
        ) from exc

    cfg = load_email_config() or {}
    smtp_server = cfg.get("smtp_server")
    smtp_port = int(cfg.get("smtp_port") or 587)
    smtp_user = cfg.get("smtp_username")
    smtp_pass = cfg.get("smtp_password")
    use_tls = bool(cfg.get("use_tls", True))

    subject, body, tpl_from_name, tpl_from_addr = _render(
        template_path, code=code, username=username, system_name=system_name,
    )
    from_email = cfg.get("sender_email") or smtp_user or tpl_from_addr
    from_name = cfg.get("sender_name") or tpl_from_name

    if not all([smtp_server, smtp_user, smtp_pass]):
        logger.warning(
            "SMTP not configured; MFA code for %s would have been: %s",
            to_email, code,
        )
        raise MFAError(
            "SMTP is not configured — the verification email could not be "
            "sent. (The code has been written to the system log for "
            "development use.)"
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
        if use_tls:
            server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
    except Exception as exc:
        logger.warning("MFA email send failed to %s: %s", to_email, exc)
        raise MFAError(
            f"Could not send the verification email: {exc}"
        ) from exc

    logger.info("MFA OTP email sent to %s", to_email)


# ── Helpers ─────────────────────────────────────────────────────────

def _generate_code() -> str:
    digits = "0123456789"
    return "".join(secrets.choice(digits) for _ in range(CODE_LENGTH))


def _hash_code(code: str) -> str:
    return _bcrypt.hashpw(code.encode("utf-8"),
                          _bcrypt.gensalt()).decode("utf-8")


def _verify_code_hash(code: str, code_hash: str) -> bool:
    try:
        return _bcrypt.checkpw(code.encode("utf-8"),
                               code_hash.encode("utf-8"))
    except (ValueError, AttributeError):
        return False


def _validate_email(email: str) -> str:
    e = (email or "").strip()
    if not e:
        raise MFAError("Email address is required.")
    if not _EMAIL_RE.match(e):
        raise MFAError("That doesn't look like a valid email address.")
    return e


# ── Service ─────────────────────────────────────────────────────────

class EmailMFAService:
    """Enrolment helper for email-based MFA.

    Stateless besides what's persisted in the shared auth DB and the
    in-flight ``email_mfa_pending`` row. Same shape as the existing
    TOTP ``MFAService`` so callers can pick either flavour.
    """

    def __init__(self, db_path: str | None = None, *,
                 template_path: Path | None = None,
                 system_name: str = "Education System"):
        self._db_path = db_path
        self._template_path = template_path
        self._system_name = system_name

    def _conn(self) -> sqlite3.Connection:
        conn = connect(self._db_path)
        _ensure_schema(conn)
        return conn

    # ── Status -----------------------------------------------------

    def is_enabled(self, user_id: int) -> bool:
        """True iff the user is already MFA-enabled in the shared auth
        DB (i.e. the universal login will challenge them at next sign-in)."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT is_enabled FROM mfa_secrets WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return bool(row and row["is_enabled"])
        finally:
            conn.close()

    def get_email(self, user_id: int) -> str | None:
        """The email the login OTP will be delivered to — i.e. the
        user's on-file ``users.email``."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT email FROM users WHERE id = ?", (user_id,),
            ).fetchone()
            return row["email"] if row and row["email"] else None
        finally:
            conn.close()

    def set_email(self, user_id: int, email: str) -> str:
        """Update ``users.email`` directly.

        Note: this does **not** enable MFA — the universal login will
        only challenge once ``mfa_secrets.is_enabled = 1``, which only
        happens after ``verify_code`` succeeds. Changing the address
        also invalidates any in-flight verification.
        """
        email = _validate_email(email)
        conn = self._conn()
        try:
            cur = conn.execute(
                "UPDATE users SET email = ?, updated_at = datetime('now') "
                "WHERE id = ?",
                (email, user_id),
            )
            if cur.rowcount == 0:
                raise MFAError(f"No user with id {user_id}.")
            conn.execute(
                "DELETE FROM email_mfa_pending WHERE user_id = ?",
                (user_id,),
            )
            conn.commit()
        finally:
            conn.close()
        logger.info("MFA email updated on users.email for user_id=%d", user_id)
        return email

    # ── Send / verify ─────────────────────────────────────────────

    def send_code(self, user_id: int, *, override_email: str | None = None,
                  username: str | None = None,
                  system_name: str | None = None) -> dict:
        """Issue a fresh 6-digit code and email it.

        If ``override_email`` is given, the code is sent there (used
        when the user is still choosing an address). Otherwise we
        use the user's on-file ``users.email``. Returns the address
        the code was sent to. Raises ``MFAError`` on any failure
        (no silent successes).
        """
        target = (override_email.strip() if override_email
                  else (self.get_email(user_id) or ""))
        target = _validate_email(target)

        # Resolve username for the email body if the caller didn't provide.
        if not username:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT username FROM users WHERE id = ?", (user_id,),
                ).fetchone()
                username = row["username"] if row else "User"
            finally:
                conn.close()

        # Cooldown — stops the user from spamming Send.
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT sent_at FROM email_mfa_pending WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        finally:
            conn.close()
        if existing:
            try:
                last = datetime.fromisoformat(existing["sent_at"])
            except ValueError:
                last = None
            if last is not None:
                age = (datetime.utcnow() - last).total_seconds()
                if age < SEND_COOLDOWN_SECONDS:
                    wait = int(SEND_COOLDOWN_SECONDS - age) + 1
                    raise MFAError(
                        f"A code was just sent. Please wait {wait}s "
                        "before requesting another.")

        code = _generate_code()
        expires_at = (datetime.utcnow()
                      + timedelta(minutes=CODE_TTL_MINUTES)).isoformat()
        sent_at = datetime.utcnow().isoformat()
        code_hash = _hash_code(code)

        # Persist the pending verification BEFORE sending so we can't
        # leak a code that we then forget about.
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO email_mfa_pending "
                "(user_id, email, code_hash, expires_at, attempts, sent_at) "
                "VALUES (?, ?, ?, ?, 0, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET "
                "  email = excluded.email, "
                "  code_hash = excluded.code_hash, "
                "  expires_at = excluded.expires_at, "
                "  attempts = 0, "
                "  sent_at = excluded.sent_at",
                (user_id, target, code_hash, expires_at, sent_at),
            )
            conn.commit()
        finally:
            conn.close()

        _send_email(
            target, code,
            username=username,
            system_name=system_name or self._system_name,
            template_path=self._template_path,
        )

        logger.info("Email-MFA code issued for user_id=%d (sent_to=%s)",
                    user_id, target)
        return {"sent_to": target, "delivered": True}

    def verify_code(self, user_id: int, code: str) -> bool:
        """Verify and consume a code. On success: writes ``users.email``,
        enables MFA in ``mfa_secrets``, clears the pending row.

        Returns True only on the matching, non-expired path. Any
        other state (wrong code, expired, locked out, missing) raises
        ``MFAError`` with a user-facing message.
        """
        code = (code or "").strip()
        if not code:
            raise MFAError("Code is required.")

        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT email, code_hash, expires_at, attempts "
                "FROM email_mfa_pending WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                raise MFAError(
                    "No verification code is pending — send a new code first.")
            try:
                expires = datetime.fromisoformat(row["expires_at"])
            except ValueError:
                expires = datetime.utcnow() - timedelta(seconds=1)
            if datetime.utcnow() > expires:
                conn.execute(
                    "DELETE FROM email_mfa_pending WHERE user_id = ?",
                    (user_id,))
                conn.commit()
                raise MFAError("That code has expired — request a new one.")
            if row["attempts"] >= MAX_ATTEMPTS_PER_CODE:
                conn.execute(
                    "DELETE FROM email_mfa_pending WHERE user_id = ?",
                    (user_id,))
                conn.commit()
                raise MFAError(
                    "Too many failed attempts on this code. Request a new one.")

            if not _verify_code_hash(code, row["code_hash"]):
                new_attempts = row["attempts"] + 1
                conn.execute(
                    "UPDATE email_mfa_pending SET attempts = ? "
                    "WHERE user_id = ?",
                    (new_attempts, user_id),
                )
                conn.commit()
                remaining = MAX_ATTEMPTS_PER_CODE - new_attempts
                logger.warning(
                    "Email-MFA wrong code for user_id=%d (attempt %d/%d)",
                    user_id, new_attempts, MAX_ATTEMPTS_PER_CODE)
                if remaining <= 0:
                    raise MFAError(
                        "Too many failed attempts on this code. "
                        "Request a new one.")
                raise MFAError(
                    f"Wrong code. {remaining} attempt(s) remaining.")

            # ── Match — commit the side effects ──────────────────
            verified_email = row["email"]
            conn.execute(
                "DELETE FROM email_mfa_pending WHERE user_id = ?",
                (user_id,))

            # 1) Make sure users.email matches what we verified — that's
            #    where the universal login will send future OTPs.
            conn.execute(
                "UPDATE users SET email = ?, updated_at = datetime('now') "
                "WHERE id = ?",
                (verified_email, user_id),
            )

            # 2) Enable MFA in shared auth. The TOTP secret is required by
            #    the NOT NULL schema; the user never sees it — the email
            #    flow is what runs at every sign-in. (Same trick the
            #    sixth-form module uses.)
            existing = conn.execute(
                "SELECT id FROM mfa_secrets WHERE user_id = ?", (user_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE mfa_secrets SET is_enabled = 1 "
                    "WHERE user_id = ?", (user_id,),
                )
            else:
                conn.execute(
                    "INSERT INTO mfa_secrets (user_id, totp_secret, is_enabled) "
                    "VALUES (?, ?, 1)",
                    (user_id, pyotp.random_base32()),
                )
            conn.commit()
        finally:
            conn.close()

        logger.info(
            "Email-MFA verification succeeded for user_id=%d; "
            "users.email updated and mfa_secrets.is_enabled = 1", user_id)
        return True

    # ── Disable ───────────────────────────────────────────────────

    def disable(self, user_id: int) -> bool:
        """Turn MFA off in the shared auth DB and bin any in-flight
        verification. The universal login will stop demanding a code
        at next sign-in.
        """
        conn = self._conn()
        try:
            cur = conn.execute(
                "DELETE FROM mfa_secrets WHERE user_id = ?", (user_id,))
            conn.execute(
                "DELETE FROM mfa_recovery_codes WHERE user_id = ?",
                (user_id,))
            conn.execute(
                "DELETE FROM email_mfa_pending WHERE user_id = ?",
                (user_id,))
            conn.commit()
            removed = cur.rowcount > 0
        finally:
            conn.close()
        if removed:
            logger.info("Email-MFA disabled for user_id=%d", user_id)
        return removed
