"""Shared authentication routes.

The handlers for ``auth_bp``. Split out of the former
``delivery/api/auth.py``; the blueprint, the module state and the
decorators live in :mod:`...security.authentication` and are imported
here so there is exactly one copy of each.
"""

import logging
import os
import secrets
from datetime import datetime, timedelta

import jwt
from flask import request, jsonify, g

from education_system.platform.delivery.api.security.authentication import (
    # Rate-limit thresholds. Plain ints, so importing by value is safe; the
    # mutable _rate_limiter is reached only through _rate_limited() below.
    _LOGIN_LIMIT,
    _LOGIN_WINDOW,
    _MFA_IP_LIMIT,
    _MFA_IP_WINDOW,
    _MFA_USER_LIMIT,
    _MFA_USER_WINDOW,
    _REGISTER_LIMIT,
    _REGISTER_WINDOW,
    _auth_db_path,
    _clear_username_login_failures,
    _create_mfa_token,
    _get_jwt_secret,
    _login_tenant_slug,
    _rate_limited,
    _record_username_login_failure,
    _refresh_jti_state,
    _revoke_all_refresh_jtis_for_user,
    _revoke_refresh_jti,
    _username_rate_limited,
    auth_bp,
    decode_token,
    generate_token,
    logger,
    role_required,
    token_required,
)

logger = logging.getLogger(__name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate and receive access + refresh tokens.

    Request body:
        {"username": "...", "password": "..."}

    Response:
        {"token": "...", "refresh_token": "...", "user": {...}}
    """
    ip = request.remote_addr or "unknown"
    if _rate_limited(f"login:{ip}", _LOGIN_LIMIT, _LOGIN_WINDOW):
        return jsonify({"error": "Too many login attempts. Try again later."}), 429

    data = request.get_json(silent=True)
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "username and password required"}), 400

    if _username_rate_limited(data["username"]):
        return jsonify({"error": "Too many login attempts for this account. Try again later."}), 429

    try:
        from education_system.platform.identity.auth.core import UserAuth
        from education_system.platform.identity.auth.db import AUTH_DB_FILE
        auth = UserAuth(_auth_db_path or str(AUTH_DB_FILE))
        result = auth.login(data["username"], data["password"])
    except Exception:
        logger.warning("Login failed for '%s'", data.get("username"))
        _record_username_login_failure(data["username"])
        return jsonify({"error": "Invalid credentials"}), 401

    if not result:
        _record_username_login_failure(data["username"])
        return jsonify({"error": "Invalid credentials"}), 401

    # Password matched — clear the per-username failure counter so a
    # successful login (or successful MFA primary step) doesn't leave the
    # account hovering near a lockout from earlier failed attempts.
    _clear_username_login_failures(data["username"])

    # MFA challenge
    tenant_slug, denial = _login_tenant_slug(result["user_id"], data.get("tenant"))
    if denial is not None:
        return denial

    if result.get("mfa_required"):
        mfa_token = _create_mfa_token(result["user_id"], tenant_slug)
        return jsonify({
            "mfa_required": True,
            "mfa_token": mfa_token,
            "user_id": result["user_id"],
            "username": result["username"],
        })

    systems = result.get("systems", [])
    access_token = generate_token(result["user_id"], result["username"], systems, "access", tenant_slug)
    refresh_token = generate_token(result["user_id"], result["username"], systems, "refresh", tenant_slug)

    return jsonify({
        "message": "Login successful.",
        "token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "user_id": result["user_id"],
            "username": result["username"],
            "display_name": result.get("display_name", result["username"]),
            "systems": systems,
            "password_expired": bool(result.get("password_expired")),
            "must_change_password": bool(result.get("must_change_password")),
        },
    })


@auth_bp.route("/mfa/verify", methods=["POST"])
def mfa_verify():
    """Complete MFA challenge.

    Request body:
        {"code": "123456"}
    Headers:
        Authorization: Bearer <mfa_token>
    """
    ip = request.remote_addr or "unknown"
    if _rate_limited(f"mfa:{ip}", _MFA_IP_LIMIT, _MFA_IP_WINDOW):
        return jsonify({"error": "Too many MFA attempts. Try again later."}), 429

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "MFA token required"}), 401

    token = auth_header.split(" ", 1)[1]
    try:
        data = jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])
        if data.get("purpose") != "mfa_verify":
            return jsonify({"error": "Invalid token type"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid or expired MFA token"}), 401

    # Per-user cap: block brute-forcing one account's code even from many IPs.
    if _rate_limited(f"mfa_user:{data.get('user_id')}", _MFA_USER_LIMIT, _MFA_USER_WINDOW):
        return jsonify({"error": "Too many MFA attempts. Try again later."}), 429

    body = request.get_json(silent=True)
    if not body or not body.get("code"):
        return jsonify({"error": "MFA code required"}), 400

    try:
        from education_system.platform.identity.auth.core import UserAuth
        from education_system.platform.identity.auth.db import AUTH_DB_FILE
        auth = UserAuth(_auth_db_path or str(AUTH_DB_FILE))
        result = auth.verify_mfa(data["user_id"], body["code"])
    except Exception as e:
        logger.error("MFA verification failed: %s", e)
        return jsonify({"error": "MFA verification failed"}), 401

    systems = result.get("systems", [])
    # `data` is the decoded MFA token: reuse the tenant chosen at the password
    # step rather than making a multi-tenant user select again.
    mfa_tenant = data.get("tenant_id")
    access_token = generate_token(result["user_id"], result["username"], systems, "access", mfa_tenant)
    refresh_token = generate_token(result["user_id"], result["username"], systems, "refresh", mfa_tenant)

    return jsonify({
        "message": "MFA verified.",
        "token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "user_id": result["user_id"],
            "username": result["username"],
            "systems": systems,
        },
    })


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    """Exchange a refresh token for a new access token.

    Request body:
        {"refresh_token": "..."}
    """
    body = request.get_json(silent=True)
    if not body or not body.get("refresh_token"):
        return jsonify({"error": "refresh_token required"}), 400

    try:
        data = decode_token(body["refresh_token"])
        if data.get("type") != "refresh":
            return jsonify({"error": "Not a refresh token"}), 401
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Refresh token expired, please login again"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid refresh token"}), 401

    # Enforce rotation: the refresh-token's JTI must exist in our store and
    # not yet be revoked. A revoked JTI being presented means either the
    # token was already rotated (replay) or was explicitly logged out — in
    # either case we revoke the entire chain for that user as a defensive
    # measure (refresh-token reuse detection).
    jti = data.get("jti")
    user_id = data.get("user_id")
    if not jti:
        # Legacy refresh tokens (issued before rotation was wired in) have
        # no JTI. Reject them so callers are forced to log in once; the new
        # tokens will then be rotation-tracked.
        return jsonify({"error": "Refresh token must be re-issued, please login again"}), 401

    state = _refresh_jti_state(jti)
    if state is None:
        # Unknown JTI — either DB was reset or token was forged for a user
        # that no longer exists. Reject.
        return jsonify({"error": "Refresh token not recognised"}), 401
    if state.get("revoked"):
        logger.warning(
            "Refresh-token reuse detected for user_id=%s jti=%s — revoking all sessions",
            user_id, jti,
        )
        if user_id is not None:
            _revoke_all_refresh_jtis_for_user(int(user_id))
        return jsonify({"error": "Refresh token has been revoked"}), 401

    systems = data.get("systems", [])
    # Rotation must not silently widen scope: carry the original claim over.
    refresh_tenant = data.get("tenant_id")
    new_access = generate_token(data["user_id"], data["username"], systems, "access", refresh_tenant)
    new_refresh = generate_token(data["user_id"], data["username"], systems, "refresh", refresh_tenant)
    # Mark the old JTI as revoked and link it to the new one (decoded lazily
    # — we need the new JTI from the freshly-issued token).
    try:
        new_payload = jwt.decode(new_refresh, _get_jwt_secret(), algorithms=["HS256"])
        _revoke_refresh_jti(jti, replaced_by=new_payload.get("jti"))
    except Exception:
        _revoke_refresh_jti(jti)

    return jsonify({
        "token": new_access,
        "refresh_token": new_refresh,
    })


@auth_bp.route("/register", methods=["POST"])
@role_required("admin")
def register():
    """Create a new user account (admin only).

    Request body:
        {"username": "...", "password": "...", "email": "...",
         "systems": [{"system_key": "college", "role": "student"}, ...]}
    """
    ip = request.remote_addr or "unknown"
    if _rate_limited(f"register:{ip}", _REGISTER_LIMIT, _REGISTER_WINDOW):
        return jsonify({"error": "Too many registration attempts."}), 429

    data = request.get_json(silent=True)
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "username and password required"}), 400

    systems_list = data.get("systems", [{"system_key": "college", "role": "student"}])
    system_tuples = [(s["system_key"], s.get("role", "student")) for s in systems_list]

    try:
        from education_system.platform.identity.auth.core import UserAuth
        from education_system.platform.identity.auth.db import AUTH_DB_FILE
        auth = UserAuth(_auth_db_path or str(AUTH_DB_FILE))
        user_id = auth.create_user(
            username=data["username"],
            password=data["password"],
            email=data.get("email"),
            systems=system_tuples,
        )
    except Exception as e:
        logger.error("User registration failed: %s", e)
        return jsonify({"error": "Registration failed"}), 400

    return jsonify({"message": "User created.", "user_id": user_id}), 201


@auth_bp.route("/me", methods=["GET"])
@token_required
def get_me():
    """Return current user info from token."""
    return jsonify({"user": g.current_user})


@auth_bp.route("/change-password", methods=["POST"])
@token_required
def change_password():
    """Change the current user's password.

    Request body:
        {"old_password": "...", "new_password": "..."}
    """
    data = request.get_json(silent=True)
    if not data or not data.get("old_password") or not data.get("new_password"):
        return jsonify({"error": "old_password and new_password required"}), 400

    try:
        from education_system.platform.identity.auth.core import UserAuth
        from education_system.platform.identity.auth.db import AUTH_DB_FILE
        auth = UserAuth(_auth_db_path or str(AUTH_DB_FILE))
        auth.change_password(g.current_user["user_id"],
                             data["old_password"], data["new_password"])
    except Exception as e:
        logger.error("Auth update failed: %s", e)
        return jsonify({"error": "Password change failed"}), 400

    return jsonify({"message": "Password changed successfully."})


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """Request a password reset token.

    Request body:
        {"email": "user@example.com"}
    """
    ip = request.remote_addr or "unknown"
    if _rate_limited(f"forgot:{ip}", 3, 3600):
        return jsonify({"error": "Too many reset requests. Try again later."}), 429

    data = request.get_json(silent=True)
    if not data or not data.get("email"):
        return jsonify({"error": "email required"}), 400

    try:
        from education_system.platform.identity.auth.password_reset import PasswordResetService
        from education_system.platform.identity.auth.db import AUTH_DB_FILE
        svc = PasswordResetService(_auth_db_path or str(AUTH_DB_FILE))
        result = svc.request_reset(data["email"])

        # Send the reset email if a token was generated
        if result.get("token"):
            _send_password_reset_email(
                email=result["email"],
                username=result["username"],
                token=result["token"],
                expires_at=result["expires_at"],
            )
    except Exception as e:
        logger.error("Account reset request failed: %s", e)
        # Don't reveal errors to prevent email enumeration

    return jsonify({"message": "If that email exists, a reset link has been sent."})


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    """Reset password using a token.

    Request body:
        {"token": "...", "new_password": "..."}
    """
    data = request.get_json(silent=True)
    if not data or not data.get("token") or not data.get("new_password"):
        return jsonify({"error": "token and new_password required"}), 400

    try:
        from education_system.platform.identity.auth.password_reset import PasswordResetService
        from education_system.platform.identity.auth.db import AUTH_DB_FILE
        svc = PasswordResetService(_auth_db_path or str(AUTH_DB_FILE))
        svc.reset_password(data["token"], data["new_password"])
    except Exception as e:
        logger.error("Account reset failed: %s", e)
        return jsonify({"error": "Password reset failed"}), 400

    return jsonify({"message": "Password reset successful. Please login with your new password."})


# ── Password reset email helper ────────────────────────────────────────

def _send_password_reset_email(email: str, username: str, token: str, expires_at: str):
    """Send a password reset email containing the reset token.

    Uses the shared email config. Falls back silently if email is not
    configured (the token is still returned in the API response for
    development/testing).
    """
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

        from education_system.platform.integrations.email import delivery_mode as _mode
        if _mode.delivery_mode() == "live" and not all([smtp_server, smtp_user, smtp_pass]):
            logger.debug("Email not configured — skipping password reset email")
            return False

        base_url = os.getenv("APP_BASE_URL", "http://localhost:5000")
        reset_link = f"{base_url}/web/reset-password?token={token}"

        body = (
            f"Hello {username},\n\n"
            f"A password reset was requested for your Education System account.\n\n"
            f"Click the link below to reset your password:\n"
            f"  {reset_link}\n\n"
            f"This link expires at {expires_at}.\n\n"
            f"If you did not request this, you can safely ignore this email.\n"
        )

        subject = "Education System — Password Reset"

        def send_live():
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = email
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
            if use_tls:
                server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(sender, [email], msg.as_string())
            server.quit()
            logger.info("Password reset email sent to %s", email)
            return True

        # Follow the shared delivery mode: only "live" opens SMTP; "sandbox"
        # writes the message (with its link) to the sandbox folder.
        from education_system.platform.integrations.email import delivery_mode
        return delivery_mode.deliver(email, subject, body, send_live)
    except Exception as exc:
        logger.debug("Could not send password reset email: %s", exc)
        return False


# ── Email verification endpoints ───────────────────────────────────────

@auth_bp.route("/send-verification", methods=["POST"])
@token_required
def send_verification_email():
    """Send an email verification link to the current user's email.

    Response:
        {"message": "Verification email sent."}
    """
    try:
        from education_system.platform.identity.auth.email_verification import EmailVerificationService
        from education_system.platform.identity.auth.db import AUTH_DB_FILE
        svc = EmailVerificationService(_auth_db_path or str(AUTH_DB_FILE))
        svc.send_verification(g.current_user["user_id"])
    except Exception as e:
        logger.error("Email verification send failed: %s", e)
        return jsonify({"error": "Failed to send verification email"}), 500

    return jsonify({"message": "Verification email sent."})


@auth_bp.route("/verify-email", methods=["POST"])
def verify_email():
    """Verify an email address using a token.

    Request body:
        {"token": "..."}
    """
    data = request.get_json(silent=True)
    if not data or not data.get("token"):
        return jsonify({"error": "token required"}), 400

    try:
        from education_system.platform.identity.auth.email_verification import EmailVerificationService
        from education_system.platform.identity.auth.db import AUTH_DB_FILE
        svc = EmailVerificationService(_auth_db_path or str(AUTH_DB_FILE))
        svc.verify(data["token"])
    except Exception as e:
        logger.error("Email verification failed: %s", e)
        return jsonify({"error": "Email verification failed"}), 400

    return jsonify({"message": "Email verified successfully."})


# ── OAuth2 / social login endpoints ───────────────────────────────────

@auth_bp.route("/oauth/providers", methods=["GET"])
def oauth_providers():
    """List available OAuth providers and their configuration status."""
    try:
        from education_system.platform.identity.auth.oauth_service import OAuthService
        return jsonify({"providers": OAuthService.list_providers()})
    except Exception as e:
        logger.error("OAuth providers list failed: %s", e)
        return jsonify({"providers": []}), 500


@auth_bp.route("/oauth/<provider>/authorize", methods=["GET"])
def oauth_authorize(provider: str):
    """Redirect to OAuth provider's authorization page."""
    try:
        from education_system.platform.identity.auth.oauth_service import OAuthService
        from education_system.platform.identity.auth.db import AUTH_DB_FILE
        svc = OAuthService(_auth_db_path or str(AUTH_DB_FILE))
        url = svc.get_authorization_url(provider)
        return jsonify({"authorize_url": url})
    except Exception as e:
        logger.error("OAuth authorize failed: %s", e)
        return jsonify({"error": "OAuth authorization failed. Please try again."}), 400


@auth_bp.route("/oauth/<provider>/callback", methods=["GET", "POST"])
def oauth_callback(provider: str):
    """Handle OAuth provider callback after user authorization."""
    code = request.args.get("code") or (request.get_json(silent=True) or {}).get("code")
    state = request.args.get("state") or (request.get_json(silent=True) or {}).get("state")

    if not code or not state:
        return jsonify({"error": "code and state required"}), 400

    try:
        from education_system.platform.identity.auth.oauth_service import OAuthService
        from education_system.platform.identity.auth.db import AUTH_DB_FILE
        svc = OAuthService(_auth_db_path or str(AUTH_DB_FILE))
        result = svc.handle_callback(provider, code, state)
    except Exception as e:
        logger.error("OAuth callback failed: %s", e)
        return jsonify({"error": "OAuth authentication failed. Please try again."}), 400

    systems = result.get("systems", [])
    oauth_tenant, denial = _login_tenant_slug(result["user_id"], None)
    if denial is not None:
        return denial
    access_token = generate_token(result["user_id"], result["username"], systems, "access", oauth_tenant)
    refresh_token = generate_token(result["user_id"], result["username"], systems, "refresh", oauth_tenant)

    return jsonify({
        "message": "OAuth login successful.",
        "token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "user_id": result["user_id"],
            "username": result["username"],
            "display_name": result.get("display_name", result["username"]),
            "systems": systems,
            "oauth_provider": result.get("oauth_provider"),
        },
    })


@auth_bp.route("/oauth/linked", methods=["GET"])
@token_required
def oauth_linked_providers():
    """List OAuth providers linked to the current user's account."""
    try:
        from education_system.platform.identity.auth.oauth_service import OAuthService
        from education_system.platform.identity.auth.db import AUTH_DB_FILE
        svc = OAuthService(_auth_db_path or str(AUTH_DB_FILE))
        providers = svc.get_linked_providers(g.current_user["user_id"])
        return jsonify({"linked_providers": providers})
    except Exception as e:
        logger.error("OAuth linked providers list failed: %s", e)
        return jsonify({"linked_providers": []}), 500


@auth_bp.route("/oauth/<provider>/unlink", methods=["POST"])
@token_required
def oauth_unlink(provider: str):
    """Unlink an OAuth provider from the current user's account."""
    try:
        from education_system.platform.identity.auth.oauth_service import OAuthService
        from education_system.platform.identity.auth.db import AUTH_DB_FILE
        svc = OAuthService(_auth_db_path or str(AUTH_DB_FILE))
        if svc.unlink_account(g.current_user["user_id"], provider):
            return jsonify({"message": f"{provider} account unlinked."})
        return jsonify({"error": f"No {provider} account linked."}), 404
    except Exception as e:
        logger.error("OAuth unlink failed: %s", e)
        return jsonify({"error": "Failed to unlink account"}), 500


# ── Device management endpoints ───────────────────────────────────────

@auth_bp.route("/logout", methods=["POST"])
@token_required
def logout():
    """End this session by revoking its refresh token.

    The portal has always called this endpoint, but it did not exist — the
    request 404'd, the browser cleared its own storage, and the refresh
    token stayed valid for its full lifetime. Anyone holding a copy could
    keep minting access tokens from an account that had "signed out".

    Send the refresh token in the body to revoke just this session::

        {"refresh_token": "..."}

    ``all_devices: true`` revokes every refresh token for the user instead,
    which is the right response to a suspected compromise.

    Access tokens are stateless and are not revoked here — they expire on
    their own. Cutting the refresh chain is what actually ends the session.
    Always returns 200: the client has already discarded its credentials by
    the time it calls this, so a failure to revoke must not leave the UI
    stuck on a page it can no longer authenticate.
    """
    data = request.get_json(silent=True) or {}
    user_id = g.current_user.get("user_id")

    if data.get("all_devices"):
        try:
            _revoke_all_refresh_jtis_for_user(user_id)
            return jsonify({"message": "Signed out of all devices."})
        except Exception:
            logger.warning("Logout: could not revoke all sessions for %s", user_id)
            return jsonify({"message": "Signed out."})

    refresh_token = data.get("refresh_token")
    if refresh_token:
        try:
            payload = jwt.decode(
                refresh_token, _get_jwt_secret(), algorithms=["HS256"],
                options={"verify_exp": False},   # revoking an expired token is fine
            )
            jti = payload.get("jti")
            # Only the owner may revoke it; a token from another account is
            # not this caller's session to end.
            if jti and payload.get("user_id") == user_id:
                _revoke_refresh_jti(jti)
                return jsonify({"message": "Signed out."})
        except jwt.InvalidTokenError:
            logger.info("Logout with an undecodable refresh token for %s", user_id)

    return jsonify({"message": "Signed out."})


@auth_bp.route("/devices", methods=["GET"])
@token_required
def list_devices():
    """List trusted devices for the current user."""
    try:
        from education_system.platform.identity.auth.device_manager import DeviceManager
        from education_system.platform.identity.auth.db import AUTH_DB_FILE
        mgr = DeviceManager(_auth_db_path or str(AUTH_DB_FILE))
        devices = mgr.list_devices(g.current_user["user_id"])
        return jsonify({"devices": devices})
    except Exception as e:
        logger.error("Device list failed: %s", e)
        return jsonify({"devices": []}), 500


@auth_bp.route("/devices/revoke-all", methods=["POST"])
@token_required
def revoke_all_devices():
    """Revoke all trusted devices for the current user."""
    try:
        from education_system.platform.identity.auth.device_manager import DeviceManager
        from education_system.platform.identity.auth.db import AUTH_DB_FILE
        mgr = DeviceManager(_auth_db_path or str(AUTH_DB_FILE))
        count = mgr.revoke_all_devices(g.current_user["user_id"])
        return jsonify({"message": f"Revoked {count} trusted device(s)."})
    except Exception as e:
        logger.error("Device revoke failed: %s", e)
        return jsonify({"error": "Failed to revoke devices"}), 500
