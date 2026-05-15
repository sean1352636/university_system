"""Email-based multi-factor authentication for the Sixth Form System.

This is a thin enrolment-only module — the *actual* login challenge is
handled by the shared universal login (``shared/gui/login_gui.py`` and
``shared/cli/mfa_cli.py``), which already sends an email OTP to
``users.email`` whenever ``mfa_secrets.is_enabled = 1`` for that user.
The university does the same trick (see
``launcher/auth.py::sync_university_mfa_to_shared``) — sixth-form just
needs to flip the flag on the shared row, and the universal login
takes care of the rest.

Enable flow (from sixth-form CLI/GUI)
-------------------------------------
1. User enters an email address (prefilled with their on-file address).
2. We send a confirmation code to that address (rendered from the
   ``mfa_otp.json`` template) and ask them to type it back.
3. On success we write/update **two** rows in the shared ``auth.db``:
     * ``users.email`` is updated to the verified address, so the
       universal login sends the login OTP there
     * ``mfa_secrets`` is upserted with ``is_enabled = 1`` (and a fresh
       TOTP secret, never shown to the user — it just satisfies the
       NOT NULL constraint and lets advanced users with an authenticator
       app use it too)
4. Until the user disables MFA, every subsequent login will demand a
   6-digit code emailed to that address.

A small per-user ``mfa_email_pending`` table in ``sixthform.db`` holds
the in-flight verification code + expiry; it's cleared on success.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import smtplib
import sqlite3
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import pyotp

from education_system.sixthform_system import SYSTEM_NAME
from education_system.sixthform_system.core import paths
from education_system.shared.auth.db import connect as shared_auth_connect

logger = logging.getLogger(__name__)

CODE_TTL_MINUTES = 10
MAX_VERIFY_ATTEMPTS = 5
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TEMPLATE_FILE = paths.EMAIL_TEMPLATES_DIR / "mfa_otp.json"


class MFASetupError(ValueError):
    pass


# ── helpers ─────────────────────────────────────────────────────────


def _current_user(auth: Any) -> tuple[int, str]:
    cu = getattr(auth, "current_user", None) or {}
    uid = cu.get("id") or cu.get("user_id")
    if uid is None:
        raise MFASetupError("No active session — please sign in again.")
    try:
        uid_int = int(uid)
    except (TypeError, ValueError):
        raise MFASetupError("Active session has no usable user id.") from None
    username = cu.get("username") or "(unknown)"
    return uid_int, username


def _shared_db_path(auth: Any) -> str | None:
    return getattr(auth, "_db_path", None) or getattr(auth, "db_path", None)


def _pending_conn() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(paths.STUDENTS_DB))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mfa_email_pending (
            user_id      INTEGER PRIMARY KEY,
            email        TEXT NOT NULL,
            code_hash    TEXT NOT NULL,
            code_expires TEXT NOT NULL,
            attempts     INTEGER NOT NULL DEFAULT 0,
            updated_at   TEXT NOT NULL
        )
        """
    )
    return conn


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.utcnow()


def _render_template(*, code: str, username: str) -> tuple[str, str, str, str]:
    try:
        with _TEMPLATE_FILE.open(encoding="utf-8") as f:
            tpl = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("MFA template load failed (%s) — using fallback", e)
        tpl = {
            "subject": "Your {{system_name}} verification code: {{code}}",
            "body": ("Hi {{username}},\n\nYour code is {{code}}.\n"
                     "It expires in {{expiry_minutes}} minutes."),
            "from_name": "Sixth Form Security",
            "from_address": "no-reply@sixthform.local",
        }
    variables = {
        "code": code,
        "username": username,
        "system_name": SYSTEM_NAME,
        "expiry_minutes": str(CODE_TTL_MINUTES),
    }

    def render(s: str) -> str:
        for k, v in variables.items():
            s = s.replace("{{" + k + "}}", v)
        return s

    return (
        render(tpl.get("subject", "")),
        render(tpl.get("body", "")),
        tpl.get("from_name", "Sixth Form Security"),
        tpl.get("from_address", "no-reply@sixthform.local"),
    )


def _send_email(to_email: str, code: str, username: str) -> None:
    try:
        from education_system.shared.email.config import load_email_config
    except Exception as e:
        raise MFASetupError(
            "Email is not configured on this server — ask an "
            "administrator to set up SMTP before enabling email MFA."
        ) from e

    cfg = load_email_config() or {}
    smtp_server = cfg.get("smtp_server")
    smtp_port = int(cfg.get("smtp_port") or 587)
    smtp_user = cfg.get("smtp_username")
    smtp_pass = cfg.get("smtp_password")
    use_tls = bool(cfg.get("use_tls", True))

    subject, body, tpl_from_name, tpl_from_addr = _render_template(
        code=code, username=username,
    )
    from_email = cfg.get("sender_email") or smtp_user or tpl_from_addr
    from_name = cfg.get("sender_name") or tpl_from_name

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg.attach(MIMEText(body, "plain"))

    if not all([smtp_server, smtp_user, smtp_pass]):
        logger.warning(
            "SMTP not configured; MFA code for %s would have been: %s",
            to_email, code,
        )
        raise MFASetupError(
            "SMTP is not configured — the verification email could "
            "not be sent. (The code has been written to the system "
            "log for development use.)"
        )

    try:
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
        if use_tls:
            server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
    except Exception as e:
        logger.warning("MFA email send failed to %s: %s", to_email, e)
        raise MFASetupError(
            f"Could not send the verification email: {e}"
        ) from e

    logger.info("MFA OTP email sent to %s", to_email)


# ── public API ──────────────────────────────────────────────────────


def is_enabled(auth: Any) -> bool:
    """True iff this user has ``mfa_secrets.is_enabled = 1`` in the
    shared auth DB. That's the flag the universal login already keys on.
    """
    uid, _ = _current_user(auth)
    conn = shared_auth_connect(_shared_db_path(auth))
    try:
        row = conn.execute(
            "SELECT is_enabled FROM mfa_secrets WHERE user_id = ?", (uid,)
        ).fetchone()
        return bool(row and row["is_enabled"])
    finally:
        conn.close()


def get_email(auth: Any) -> str | None:
    """The email that will receive the login OTP — i.e. the user's
    on-file ``users.email`` in shared auth."""
    uid, _ = _current_user(auth)
    conn = shared_auth_connect(_shared_db_path(auth))
    try:
        row = conn.execute(
            "SELECT email FROM users WHERE id = ?", (uid,)
        ).fetchone()
        return row["email"] if row and row["email"] else None
    finally:
        conn.close()


def send_code(auth: Any, email: str) -> None:
    """Issue a fresh 6-digit code for ``email`` and email it.

    Persists the hash + expiry against the current user so
    :func:`confirm_code` can verify it. Overwrites any pending code.
    """
    uid, username = _current_user(auth)
    email = (email or "").strip().lower()
    if not email:
        raise MFASetupError("Enter the email address to send the code to.")
    if not _EMAIL_RE.match(email):
        raise MFASetupError("That doesn't look like a valid email address.")

    code = "".join(secrets.choice("0123456789") for _ in range(6))
    expires = (_now() + timedelta(minutes=CODE_TTL_MINUTES)).isoformat()
    now_iso = _now().isoformat()

    conn = _pending_conn()
    try:
        conn.execute(
            """
            INSERT INTO mfa_email_pending
                (user_id, email, code_hash, code_expires, attempts, updated_at)
            VALUES (?, ?, ?, ?, 0, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                email        = excluded.email,
                code_hash    = excluded.code_hash,
                code_expires = excluded.code_expires,
                attempts     = 0,
                updated_at   = excluded.updated_at
            """,
            (uid, email, _hash_code(code), expires, now_iso),
        )
        conn.commit()
    finally:
        conn.close()

    _send_email(email, code, username)


def confirm_code(auth: Any, code: str) -> bool:
    """Verify a pending code and, on success, enable MFA in shared auth.

    Returns ``False`` for a plain mismatch (callers show "try again"),
    ``True`` once verification *and* the shared-auth side-effects are
    committed. Raises ``MFASetupError`` for lockout / expiry / no
    pending code.
    """
    if not code or not code.strip():
        raise MFASetupError("Enter the 6-digit code from your email.")
    uid, _ = _current_user(auth)

    conn = _pending_conn()
    try:
        row = conn.execute(
            "SELECT * FROM mfa_email_pending WHERE user_id = ?", (uid,)
        ).fetchone()
        if not row:
            raise MFASetupError(
                "No verification code is pending — send a new code first.")
        if row["attempts"] >= MAX_VERIFY_ATTEMPTS:
            raise MFASetupError(
                "Too many failed attempts. Send a fresh code and try again.")
        try:
            expires = datetime.fromisoformat(row["code_expires"])
        except ValueError:
            expires = _now() - timedelta(seconds=1)
        if _now() > expires:
            raise MFASetupError(
                "That code has expired. Send a new code and try again.")
        if _hash_code(code) != row["code_hash"]:
            conn.execute(
                "UPDATE mfa_email_pending SET attempts = attempts + 1, "
                "updated_at = ? WHERE user_id = ?",
                (_now().isoformat(), uid),
            )
            conn.commit()
            return False
        verified_email = row["email"]
        conn.execute(
            "DELETE FROM mfa_email_pending WHERE user_id = ?", (uid,)
        )
        conn.commit()
    finally:
        conn.close()

    _enable_in_shared_auth(auth, uid, verified_email)
    logger.info("Email MFA enabled for user_id=%d (sixth-form)", uid)
    return True


def disable(auth: Any) -> None:
    """Turn MFA off in the shared auth DB. The universal login will
    stop demanding a code at next sign-in."""
    uid, _ = _current_user(auth)
    sconn = shared_auth_connect(_shared_db_path(auth))
    try:
        cur = sconn.execute(
            "DELETE FROM mfa_secrets WHERE user_id = ?", (uid,)
        )
        sconn.execute(
            "DELETE FROM mfa_recovery_codes WHERE user_id = ?", (uid,)
        )
        sconn.commit()
    finally:
        sconn.close()
    # Also bin any in-flight verification.
    pconn = _pending_conn()
    try:
        pconn.execute("DELETE FROM mfa_email_pending WHERE user_id = ?", (uid,))
        pconn.commit()
    finally:
        pconn.close()
    if cur.rowcount == 0:
        raise MFASetupError("MFA is not set up for this user.")
    logger.info("Email MFA disabled for user_id=%d (sixth-form)", uid)


# ── side-effects on the shared auth DB ──────────────────────────────


def _enable_in_shared_auth(auth: Any, user_id: int, verified_email: str) -> None:
    """Wire the user up in ``auth.db`` so the universal login challenges
    them at next sign-in:

    * ``users.email`` ← verified address (universal login sends the
      OTP here)
    * ``mfa_secrets`` upserted with ``is_enabled = 1`` and a fresh
      base32 TOTP secret (NOT NULL in the schema; never shown to the
      user — they're using the email OTP flow)
    """
    conn = shared_auth_connect(_shared_db_path(auth))
    try:
        conn.execute(
            "UPDATE users SET email = ? WHERE id = ?",
            (verified_email, user_id),
        )
        existing = conn.execute(
            "SELECT id FROM mfa_secrets WHERE user_id = ?", (user_id,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE mfa_secrets SET is_enabled = 1 WHERE user_id = ?",
                (user_id,),
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


# ── back-compat aliases used by older callers ───────────────────────


def is_verified(auth: Any) -> bool:  # pragma: no cover
    return is_enabled(auth)


def remaining_recovery_codes(auth: Any) -> int:  # pragma: no cover
    return 0
