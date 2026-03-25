"""MFA management routes for authenticated users."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required, token_or_mfa_token_required
from education_system.university_system.infrastructure.auth import MFAService

logger = logging.getLogger(__name__)

mfa_bp = Blueprint("mfa", __name__, url_prefix="/api/mfa")


def _get_mfa_service() -> MFAService:
    return MFAService()


@mfa_bp.route("/status", methods=["GET"])
@token_or_mfa_token_required
def mfa_status():
    """Get MFA enabled status and configured methods for current user."""
    user_id = g.current_user["user_id"]
    svc = _get_mfa_service()

    status = svc.get_mfa_status(user_id)
    methods_result = svc.get_user_mfa_methods(user_id)

    return jsonify({
        "enabled": status.get("mfa_enabled", False) if isinstance(status, dict) else bool(status),
        "methods": methods_result.get("methods", []) if methods_result.get("success") else [],
    })


@mfa_bp.route("/setup/totp", methods=["POST"])
@token_or_mfa_token_required
def setup_totp():
    """Begin TOTP setup — returns secret and provisioning URI."""
    user_id = g.current_user["user_id"]
    username = g.current_user["sub"]
    svc = _get_mfa_service()

    result = svc.setup_totp(user_id, username)
    if not result.get("success"):
        return jsonify({"error": result.get("error", "TOTP setup failed"), "status": 500}), 500

    return jsonify({
        "secret": result.get("secret"),
        "provisioning_uri": result.get("provisioning_uri"),
        "recovery_codes": result.get("recovery_codes", []),
    })


@mfa_bp.route("/setup/totp/verify", methods=["POST"])
@token_or_mfa_token_required
def verify_totp_setup():
    """Verify TOTP code to confirm authenticator setup."""
    data = request.get_json(silent=True) or {}
    code = data.get("code", "").strip()
    if not code:
        return jsonify({"error": "Verification code is required", "status": 400}), 400

    user_id = g.current_user["user_id"]
    svc = _get_mfa_service()

    result = svc.verify_totp(user_id, code)
    if not result.get("success"):
        return jsonify({"error": result.get("error", "Invalid code"), "status": 400}), 400

    return jsonify({"message": "TOTP setup verified successfully"})


@mfa_bp.route("/setup/sms", methods=["POST"])
@token_or_mfa_token_required
def setup_sms():
    """Send OTP to phone number for SMS MFA setup."""
    data = request.get_json(silent=True) or {}
    phone = data.get("phone", "").strip()
    if not phone:
        return jsonify({"error": "Phone number is required", "status": 400}), 400

    user_id = g.current_user["user_id"]
    svc = _get_mfa_service()

    result = svc.generate_sms_otp(user_id, phone)
    if not result.get("success"):
        return jsonify({"error": result.get("error", "Failed to send SMS"), "status": 500}), 500

    resp = {
        "message": result.get("message", "Verification code sent via SMS"),
        "expires_at": result.get("expires_at"),
    }
    if result.get("sms_failed"):
        resp["code"] = result.get("code")
    return jsonify(resp)


@mfa_bp.route("/setup/sms/verify", methods=["POST"])
@token_or_mfa_token_required
def verify_sms_setup():
    """Verify SMS code to confirm SMS MFA setup."""
    data = request.get_json(silent=True) or {}
    code = data.get("code", "").strip()
    if not code:
        return jsonify({"error": "Verification code is required", "status": 400}), 400

    user_id = g.current_user["user_id"]
    svc = _get_mfa_service()

    result = svc.verify_sms_otp(user_id, code)
    if not result.get("success"):
        return jsonify({"error": result.get("error", "Invalid code"), "status": 400}), 400

    return jsonify({"message": "SMS MFA setup verified successfully"})


@mfa_bp.route("/setup/email", methods=["POST"])
@token_or_mfa_token_required
def setup_email():
    """Send OTP to email for email MFA setup."""
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    if not email:
        return jsonify({"error": "Email address is required", "status": 400}), 400

    user_id = g.current_user["user_id"]
    svc = _get_mfa_service()

    result = svc.generate_email_otp(user_id, email)
    if not result.get("success"):
        return jsonify({"error": result.get("error", "Failed to send email"), "status": 500}), 500

    resp = {
        "message": result.get("message", "Verification code sent via email"),
        "expires_at": result.get("expires_at"),
    }
    if result.get("email_failed"):
        resp["code"] = result.get("code")
    return jsonify(resp)


@mfa_bp.route("/setup/email/verify", methods=["POST"])
@token_or_mfa_token_required
def verify_email_setup():
    """Verify email code to confirm email MFA setup."""
    data = request.get_json(silent=True) or {}
    code = data.get("code", "").strip()
    if not code:
        return jsonify({"error": "Verification code is required", "status": 400}), 400

    user_id = g.current_user["user_id"]
    svc = _get_mfa_service()

    result = svc.verify_email_otp(user_id, code)
    if not result.get("success"):
        return jsonify({"error": result.get("error", "Invalid code"), "status": 400}), 400

    return jsonify({"message": "Email MFA setup verified successfully"})


@mfa_bp.route("/recovery-codes", methods=["POST"])
@token_or_mfa_token_required
def generate_recovery_codes():
    """Generate new recovery codes (replaces any existing ones)."""
    user_id = g.current_user["user_id"]
    svc = _get_mfa_service()

    result = svc.generate_recovery_codes(user_id)
    if not result.get("success"):
        return jsonify({"error": result.get("error", "Failed to generate codes"), "status": 500}), 500

    return jsonify({"codes": result.get("codes", [])})


@mfa_bp.route("/enable", methods=["POST"])
@token_or_mfa_token_required
def enable_mfa():
    """Enable MFA for current user."""
    user_id = g.current_user["user_id"]
    svc = _get_mfa_service()

    result = svc.enable_mfa(user_id)
    if not result.get("success"):
        return jsonify({"error": result.get("error", "Failed to enable MFA"), "status": 500}), 500

    return jsonify({"message": "MFA enabled successfully"})


@mfa_bp.route("/disable", methods=["POST"])
@token_required
def disable_mfa():
    """Disable MFA for current user."""
    user_id = g.current_user["user_id"]
    svc = _get_mfa_service()

    result = svc.disable_mfa(user_id)
    if not result.get("success"):
        return jsonify({"error": result.get("error", "Failed to disable MFA"), "status": 500}), 500

    return jsonify({"message": "MFA disabled successfully"})


@mfa_bp.route("/trusted-devices", methods=["GET"])
@token_required
def list_trusted_devices():
    """List trusted devices for current user."""
    user_id = g.current_user["user_id"]
    svc = _get_mfa_service()

    result = svc.get_trusted_devices(user_id)
    if not result.get("success"):
        return jsonify({"error": result.get("error", "Failed to get devices"), "status": 500}), 500

    return jsonify({"devices": result.get("devices", [])})


@mfa_bp.route("/trusted-devices/<device_id>", methods=["DELETE"])
@token_required
def revoke_trusted_device(device_id):
    """Revoke trust for a specific device."""
    user_id = g.current_user["user_id"]
    svc = _get_mfa_service()

    result = svc.revoke_trusted_device(user_id, device_id)
    if not result.get("success"):
        return jsonify({"error": result.get("error", "Failed to revoke device"), "status": 500}), 500

    return jsonify({"message": result.get("message", "Device trust revoked")})
