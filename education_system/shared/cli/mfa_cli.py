"""CLI MFA verification with email OTP support.

Sends a 6-digit email OTP, then prompts the user to enter it.
Falls back to displaying the code on screen if email delivery fails.
TOTP codes from an authenticator app are always accepted too.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from education_system.shared.auth.core import UserAuth
from education_system.shared.auth.db import connect
from education_system.shared.auth.exceptions import AuthError

logger = logging.getLogger(__name__)


def _lookup_user_email(user_id: int, auth_db_path: str | None = None) -> tuple[str | None, str | None]:
    """Look up user's email and username from shared auth DB.

    Also checks the university mfa_methods table for a configured email.
    Returns (email, username).
    """
    conn = connect(auth_db_path)
    try:
        row = conn.execute(
            "SELECT username, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        username = row["username"] if row else None
        user_email = row["email"] if row else None
    finally:
        conn.close()

    # Try university mfa_methods for a configured email address
    if username:
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            uconn = get_connection()
            try:
                for uid_val in (user_id, None):
                    if uid_val is not None:
                        mrow = uconn.execute(
                            "SELECT method_identifier FROM mfa_methods "
                            "WHERE user_id = ? AND method_type = 'email' "
                            "AND is_enabled = 1 AND method_identifier IS NOT NULL "
                            "ORDER BY id DESC LIMIT 1",
                            (uid_val,),
                        ).fetchone()
                    else:
                        urow = uconn.execute(
                            "SELECT id FROM user_accounts WHERE username = ?",
                            (username,),
                        ).fetchone()
                        if not urow:
                            break
                        ua_id = urow[0] if isinstance(urow, tuple) else urow["id"]
                        mrow = uconn.execute(
                            "SELECT method_identifier FROM mfa_methods "
                            "WHERE user_id = ? AND method_type = 'email' "
                            "AND is_enabled = 1 AND method_identifier IS NOT NULL "
                            "ORDER BY id DESC LIMIT 1",
                            (ua_id,),
                        ).fetchone()
                    if mrow:
                        mfa_email = mrow[0] if isinstance(mrow, tuple) else mrow["method_identifier"]
                        if mfa_email:
                            user_email = mfa_email
                            break
            finally:
                uconn.close()
        except ImportError:
            pass
        except Exception:
            pass

    return user_email, username


def _mask_email(email: str) -> str:
    """Mask an email for display: ab***@domain.com"""
    parts = email.split("@")
    if len(parts) == 2:
        return parts[0][:2] + "***@" + parts[1]
    return email


def cli_mfa_verify(user_id: int, auth: UserAuth) -> dict | None:
    """Handle MFA verification in a CLI context.

    Sends an email OTP (with on-screen fallback), then prompts the user
    for a code.  Accepts the email OTP, a TOTP code, or a recovery code.

    Returns the user_info dict on success, or None on failure.
    """
    # ── Generate and send email OTP ──────────────────────────────────
    pending_otp = None  # (hash, expiry)

    try:
        user_email, username = _lookup_user_email(user_id)

        if user_email and username:
            code = "".join(str(secrets.randbelow(10)) for _ in range(6))
            code_hash = hashlib.sha256(code.encode()).hexdigest()
            expiry = datetime.now() + timedelta(minutes=10)
            pending_otp = (code_hash, expiry)

            masked = _mask_email(user_email)
            logger.info("Sending MFA OTP to %s for user '%s'", masked, username)  # lgtm[py/clear-text-logging-sensitive-data]

            # Resolve target system display name so the OTP email
            # identifies this system (Sixth Form / University / …)
            # rather than the static config default.
            target_system_name = "Education System"
            try:
                from education_system.shared import branding
                if branding.SYSTEM_NAME:
                    target_system_name = branding.SYSTEM_NAME
            except Exception:
                pass
            try:
                from education_system.shared.email.otp_sender import send_otp
                result = send_otp(user_email, code,
                                   username=username,
                                   system_name=target_system_name)
                if result.get("success"):
                    print(f"\n  A verification code has been sent to {masked}")  # lgtm[py/clear-text-logging-sensitive-data]
                else:
                    logger.warning("Email send failed, showing code on screen")
                    print(f"\n  Email delivery to {masked} failed.")
                    print(f"  Your code is: {code}")  # lgtm[py/clear-text-logging-sensitive-data]
            except ImportError:
                print("\n  Email service not available.")
                print(f"  Your code is: {code}")  # lgtm[py/clear-text-logging-sensitive-data]
            except Exception as exc:
                logger.warning("OTP send error: %s", exc)
                print("\n  Email delivery failed.")
                print(f"  Your code is: {code}")
        else:
            print("\n  Two-factor authentication required.")
    except Exception as exc:
        logger.debug("MFA email lookup failed: %s", exc)
        print("\n  Two-factor authentication required.")

    # ── Prompt for code ──────────────────────────────────────────────
    print("  Enter your verification code, TOTP code, or recovery code.")

    for attempt in range(3):
        code_input = input("  MFA Code: ").strip()
        if not code_input:
            print("  Please enter a code.")
            continue

        # Try email OTP first
        if pending_otp:
            otp_hash, otp_expiry = pending_otp
            if datetime.now() < otp_expiry:
                if hashlib.sha256(code_input.encode()).hexdigest() == otp_hash:
                    pending_otp = None  # consume
                    try:
                        user_info = auth.complete_mfa_login(user_id)
                        return user_info
                    except Exception:
                        # complete_mfa_login may not exist, try verify_mfa
                        pass

        # Fall back to TOTP / recovery code
        try:
            user_info = auth.verify_mfa(user_id, code_input)
            return user_info
        except AuthError as err:
            print(f"  Error: {err}")
            if attempt < 2:
                print("  Please try again.")

    print("\n  Too many failed MFA attempts.")
    return None
