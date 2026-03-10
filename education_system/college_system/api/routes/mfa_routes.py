"""MFA API routes."""

from flask import Blueprint, jsonify, request, g

from education_system.college_system.api.auth import (
    token_required, mfa_token_required, generate_token,
)
from education_system.college_system.api.validators import get_json_body, require_fields
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.infrastructure.auth.mfa_service import MFAService

mfa_bp = Blueprint("mfa", __name__, url_prefix="/api/auth/mfa")

_db_path = None


def init_mfa_routes(db_path=None):
    global _db_path
    _db_path = db_path


@mfa_bp.route("/verify", methods=["POST"])
@mfa_token_required
def verify_mfa():
    data = get_json_body()
    require_fields(data, "code")

    auth = UserAuth(_db_path)
    user_info = auth.verify_mfa(g.mfa_user_id, data["code"])
    token = generate_token(user_info["user_id"], user_info["username"], user_info["role"])

    return jsonify({
        "message": "MFA verification successful.",
        "token": token,
        "user": {
            "user_id": user_info["user_id"],
            "username": user_info["username"],
            "role": user_info["role"],
        },
    })


@mfa_bp.route("/setup", methods=["POST"])
@token_required
def setup_mfa():
    svc = MFAService(_db_path)
    result = svc.setup_totp(g.current_user["user_id"], g.current_user["username"])
    return jsonify({
        "message": "MFA setup complete.",
        "secret": result["secret"],
        "provisioning_uri": result["provisioning_uri"],
        "recovery_codes": result["recovery_codes"],
    })


@mfa_bp.route("/disable", methods=["POST"])
@token_required
def disable_mfa():
    svc = MFAService(_db_path)
    svc.disable_mfa(g.current_user["user_id"])
    return jsonify({"message": "MFA disabled."})


@mfa_bp.route("/status", methods=["GET"])
@token_required
def mfa_status():
    svc = MFAService(_db_path)
    enabled = svc.is_mfa_enabled(g.current_user["user_id"])
    return jsonify({"mfa_enabled": enabled})


@mfa_bp.route("/recovery-count", methods=["GET"])
@token_required
def recovery_count():
    svc = MFAService(_db_path)
    count = svc.get_remaining_recovery_codes(g.current_user["user_id"])
    return jsonify({"remaining_codes": count})
