"""CLI MFA verification with email OTP support.

Sends a 6-digit email OTP, then prompts the user to enter it.
Falls back to displaying the code on screen if email delivery fails.
TOTP codes from an authenticator app are always accepted too.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from education_system.platform.identity.auth.core import UserAuth
from education_system.platform.identity.auth.db import connect
from education_system.platform.identity.auth.exceptions import AuthError

logger = logging.getLogger(__name__)


def _lookup_user_email(user_id: int, auth_db_path: str | None = None,
                       current_user: dict | None = None) -> tuple[str | None, str | None]:
    """Resolve the address to send the current user's OTP to.

    Starts from the account being logged in — ``current_user`` is the dict
    ``UserAuth.login`` returned for this attempt — and falls back to the
    shared auth DB when a detail is missing. Returns (email, username).
    """
    details = current_user or {}
    username = details.get("username")
    user_email = details.get("email")

    if not (username and user_email):
        conn = connect(auth_db_path)
        try:
            row = conn.execute(
                "SELECT username, email FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            username = username or (row["username"] if row else None)
            user_email = user_email or (row["email"] if row else None)
        finally:
            conn.close()

    # Try university mfa_methods for a configured email address.
    #
    # ``user_id`` is a **shared auth.db** id and must never be used to read
    # the university's tables: the two are different id spaces, and they
    # collide. ``admin`` is 19 in auth.db, and university ``users.id`` 19 is
    # a student — so looking the shared id up here routed the admin's login
    # OTP through that student's MFA row. Resolve by username instead, the
    # same way ``shared_mfa_identity`` and ``session_user.build_session_user``
    # cross the boundary.
    if username:
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            uconn = get_connection()
            try:
                for table in ("users", "user_accounts"):
                    urow = uconn.execute(
                        f"SELECT id FROM {table} WHERE username = ?",  # nosec B608 - fixed table names
                        (username,),
                    ).fetchone()
                    if not urow:
                        continue
                    local_id = urow[0] if isinstance(urow, tuple) else urow["id"]
                    mrow = uconn.execute(
                        "SELECT method_identifier FROM mfa_methods "
                        "WHERE user_id = ? AND method_type = 'email' "
                        "AND is_enabled = 1 AND method_identifier IS NOT NULL "
                        "ORDER BY id DESC LIMIT 1",
                        (local_id,),
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
            logger.debug("University MFA email lookup failed for %r", username, exc_info=True)

    return user_email, username


def _mask_email(email: str) -> str:
    """Mask an email for display: ab***@domain.com"""
    parts = email.split("@")
    if len(parts) == 2:
        return parts[0][:2] + "***@" + parts[1]
    return email


def cli_mfa_verify(user_id: int, auth: UserAuth,
                   current_user: dict | None = None) -> dict | None:
    """Handle MFA verification in a CLI context.

    Sends an email OTP (with on-screen fallback), then prompts the user
    for a code.  Accepts the email OTP, a TOTP code, or a recovery code.

    ``current_user`` is the details of the account being logged in, so the
    code is addressed to that user rather than to whoever an id lookup
    happens to land on.

    Returns the user_info dict on success, or None on failure.
    """
    # ── Generate and send email OTP ──────────────────────────────────
    pending_otp = None  # (hash, expiry)

    try:
        user_email, username = _lookup_user_email(user_id, current_user=current_user)

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
                from education_system.platform import branding
                if branding.SYSTEM_NAME:
                    target_system_name = branding.SYSTEM_NAME
            except Exception:
                pass
            try:
                from education_system.platform.integrations.email.otp_sender import send_otp
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
