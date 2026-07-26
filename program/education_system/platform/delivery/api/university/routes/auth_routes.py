"""Authentication routes: login, logout, refresh, current user, MFA verification."""

from __future__ import annotations

import logging

from flask import Blueprint, current_app, g, jsonify, request

from education_system.platform.delivery.api.university.auth import (
    blacklist_token,
    create_access_token,
    create_mfa_token,
    create_refresh_token,
    decode_token,
    is_token_blacklisted,
    mfa_token_required,
    token_required,
)
from education_system.platform.delivery.api.university.validators import validate_login
from education_system.systems.university.infrastructure.auth import UserAuth, MFAService

try:
    from education_system.systems.university.infrastructure.auth.mfa_integration import integrate_mfa_check
except ImportError:
    integrate_mfa_check = None
from education_system.systems.university.infrastructure.shared_context import get_auth
from education_system.systems.university.infrastructure.activity_logger import log_activity, log_login

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    validate_login(data)

    auth = get_auth()
    # login() raises InvalidCredentialsError / AuthenticationError on failure
    result = auth.login(data["username"], data["password"])

    if result == "password_reset_required":
        return jsonify({
            "message": "Password reset required",
            "password_reset_required": True,
        }), 200

    if isinstance(result, dict) and result.get("requires_2fa"):
        # Legacy 2FA: user_accounts.two_fa_enabled = 1
        # Issue an mfa_token so the client can call /api/auth/mfa/verify
        config = current_app.config["API_CONFIG"]
        legacy_user = {
            "username": result["username"],
            "id": result["user_id"],
            "role": result.get("role", "student"),
        }
        # Look up role from users table if not in result
        if "role" not in result:
            try:
                legacy_auth = get_auth()
                u = legacy_auth.get_user_by_id(result["user_id"])
                if u:
                    legacy_user["role"] = u.get("role", "student")
            except Exception:
                pass
        mfa_token = create_mfa_token(legacy_user, config)

        # Get configured MFA methods for this user
        try:
            mfa_svc = MFAService()
            methods_result = mfa_svc.get_user_mfa_methods(result["user_id"])
            methods = methods_result.get("methods", []) if methods_result.get("success") else []
            # If no methods in mfa_methods table, they have legacy TOTP
            if not methods:
                methods = [{"type": "totp", "identifier": None, "is_primary": True}]
        except Exception:
            methods = [{"type": "totp", "identifier": None, "is_primary": True}]

        try:
            auth.logout()
        except Exception:
            pass

        return jsonify({
            "mfa_required": True,
            "mfa_token": mfa_token,
            "mfa_methods": methods,
            "message": "Two-factor authentication required",
        }), 200

    # Successful password auth – check MFA requirement
    user = auth.get_current_user()
    config = current_app.config["API_CONFIG"]

    try:
        if integrate_mfa_check is not None:
            device_id = data.get("device_id")
            trust_token = data.get("trust_token")
            mfa_result = integrate_mfa_check(
                user["id"], user["role"],
                device_id=device_id, trust_token=trust_token,
            )
        else:
            mfa_result = {"action": "allow"}
    except Exception:
        mfa_result = {"action": "allow"}

    action = mfa_result.get("action", "allow")

    if action in ("require_mfa", "require_setup"):
        # User must complete MFA — return a short-lived mfa_token
        mfa_token = create_mfa_token(user, config)
        mfa_data = mfa_result.get("data", {})
        methods = mfa_data.get("methods", [])

        # Log the user out of shared context
        try:
            auth.logout()
        except Exception:
            pass

        resp = {
            "mfa_required": True,
            "mfa_token": mfa_token,
            "mfa_methods": methods,
            "message": mfa_result.get("message", "MFA verification required"),
        }
        if action == "require_setup":
            resp["mfa_setup_required"] = True
        return jsonify(resp), 200

    if action == "locked":
        try:
            auth.logout()
        except Exception:
            pass
        return jsonify({
            "error": mfa_result.get("message", "Account temporarily locked due to too many failed attempts"),
            "status": 429,
        }), 429

    # action == "allow" or "grace" — complete login
    access_token = create_access_token(user, config)
    refresh_token = create_refresh_token(user, config)

    log_login(user["username"], success=True)

    try:
        auth.logout()
    except Exception:
        pass

    resp = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "username": user["username"],
            "role": user["role"],
            "user_id": user["id"],
        },
    }
    if action == "grace":
        resp["mfa_grace_period"] = True
        resp["mfa_grace_message"] = mfa_result.get("message", "")
    return jsonify(resp)


@auth_bp.route("/logout", methods=["POST"])
@token_required
def logout():
    token = g.get("raw_token")
    if token:
        blacklist_token(token)
    log_activity("logout", "session", user=g.current_user.get("sub"))
    return jsonify({"message": "Successfully logged out"})


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    data = request.get_json(silent=True) or {}
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        return jsonify({"error": "Missing refresh_token", "status": 400}), 400

    if is_token_blacklisted(refresh_token):
        return jsonify({"error": "Token has been revoked", "status": 401}), 401

    config = current_app.config["API_CONFIG"]
    try:
        payload = decode_token(refresh_token, config)
    except Exception:
        return jsonify({"error": "Invalid or expired refresh token", "status": 401}), 401

    if payload.get("type") != "refresh":
        return jsonify({"error": "Invalid token type", "status": 401}), 401

    user_stub = {
        "username": payload["sub"],
        "id": payload["user_id"],
        "role": payload.get("role", "student"),
    }
    new_access = create_access_token(user_stub, config)
    return jsonify({"access_token": new_access})


@auth_bp.route("/mfa/verify", methods=["POST"])
@mfa_token_required
def mfa_verify():
    """Verify an MFA code during login and issue access tokens on success."""
    data = request.get_json(silent=True) or {}
    code = data.get("code", "").strip()
    method = data.get("method", "totp")

    if not code:
        return jsonify({"error": "MFA code is required", "status": 400}), 400

    user = g.mfa_user
    user_id = user["user_id"]

    try:
        mfa_service = MFAService()
        device_id = data.get("device_id")

        if method == "totp":
            result = mfa_service.verify_totp(user_id, code, device_id=device_id)
        elif method == "sms":
            result = mfa_service.verify_sms_otp(user_id, code, device_id=device_id)
        elif method == "email":
            result = mfa_service.verify_email_otp(user_id, code, device_id=device_id)
        elif method == "recovery":
            result = mfa_service.verify_recovery_code(user_id, code, device_id=device_id)
        else:
            return jsonify({"error": f"Unsupported MFA method: {method}", "status": 400}), 400

        if not result.get("success"):
            return jsonify({
                "error": "Invalid MFA code",
                "status": 401,
            }), 401

    except Exception:
        logger.exception("MFA verification error")
        return jsonify({"error": "MFA verification failed", "status": 500}), 500

    # MFA passed — issue real tokens
    config = current_app.config["API_CONFIG"]
    user_stub = {
        "username": user["sub"],
        "id": user["user_id"],
        "role": user["role"],
    }
    access_token = create_access_token(user_stub, config)
    refresh_token = create_refresh_token(user_stub, config)

    log_login(user["sub"], success=True)

    resp = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "username": user["sub"],
            "role": user["role"],
            "user_id": user["user_id"],
        },
    }
    if result.get("trust_token"):
        resp["trust_token"] = result["trust_token"]
    return jsonify(resp)


@auth_bp.route("/mfa/send-code", methods=["POST"])
@mfa_token_required
def mfa_send_code():
    """Send an OTP code via SMS or email during MFA login."""
    data = request.get_json(silent=True) or {}
    method = data.get("method", "sms")
    user = g.mfa_user
    user_id = user["user_id"]

    try:
        mfa_service = MFAService()

        if method == "sms":
            phone = data.get("phone")
            # Look up registered phone if not provided
            if not phone:
                methods_result = mfa_service.get_user_mfa_methods(user_id)
                if methods_result.get("success"):
                    for m in methods_result.get("methods", []):
                        if m["type"] == "sms" and m.get("identifier"):
                            phone = m["identifier"]
                            break
            if not phone:
                return jsonify({"error": "No phone number registered for SMS MFA", "status": 400}), 400
            result = mfa_service.generate_sms_otp(user_id, phone)
        elif method == "email":
            email = data.get("email")
            # Look up registered email if not provided
            if not email:
                methods_result = mfa_service.get_user_mfa_methods(user_id)
                if methods_result.get("success"):
                    for m in methods_result.get("methods", []):
                        if m["type"] == "email" and m.get("identifier"):
                            email = m["identifier"]
                            break
            if not email:
                return jsonify({"error": "No email address registered for email MFA", "status": 400}), 400
            result = mfa_service.generate_email_otp(user_id, email)
        else:
            return jsonify({"error": "Method must be 'sms' or 'email'", "status": 400}), 400

        if not result.get("success"):
            logger.warning("MFA send-code failed for user %s", user_id)
            return jsonify({"error": "Failed to send code", "status": 500}), 500

        resp = {
            "message": result.get("message", "Verification code sent"),
            "expires_at": result.get("expires_at"),
        }
        # Include fallback code when delivery failed (dev/mock provider)
        if result.get("email_failed") or result.get("sms_failed"):
            resp["code"] = result.get("code")
        return jsonify(resp)

    except Exception:
        logger.exception("MFA send-code error")
        return jsonify({"error": "Failed to send verification code", "status": 500}), 500


@auth_bp.route("/me", methods=["GET"])
@token_required
def me():
    user = g.current_user
    return jsonify({
        "username": user.get("sub"),
        "user_id": user.get("user_id"),
        "role": user.get("role"),
    })
