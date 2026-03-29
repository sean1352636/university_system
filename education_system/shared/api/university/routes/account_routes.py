"""Account settings routes: profile, password, preferences, sessions."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.validators import (
    validate_password_change,
    validate_preferences_update,
    validate_profile_update,
)
from education_system.college_system.core.sql_safety import validate_identifier
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

account_bp = Blueprint("account", __name__, url_prefix="/api/account")


@account_bp.route("/profile", methods=["GET"])
@token_required
def get_profile():
    """Return full profile for the current user."""
    user_id = g.current_user["user_id"]
    username = g.current_user["sub"]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, username, email, first_name, last_name, phone, role, "
            "is_active, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

        if not row:
            return jsonify({"error": "User not found", "status": 404}), 404

        cols = ["id", "username", "email", "first_name", "last_name",
                "phone", "role", "is_active", "created_at"]
        profile = dict(zip(cols, row))

        # Supplement with user_accounts data if available
        try:
            acct = conn.execute(
                "SELECT last_login, two_fa_enabled FROM user_accounts WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if acct:
                profile["last_login"] = acct[0]
                profile["two_fa_enabled"] = bool(acct[1])
        except Exception:
            pass

    return jsonify({"profile": profile})


@account_bp.route("/profile", methods=["PUT"])
@token_required
def update_profile():
    """Update own profile (first_name, last_name, email, phone)."""
    data = request.get_json(silent=True) or {}
    validate_profile_update(data)

    user_id = g.current_user["user_id"]
    allowed = {"first_name", "last_name", "email", "phone"}
    updates = {k: v for k, v in data.items() if k in allowed and v is not None}

    if not updates:
        return jsonify({"error": "No valid fields to update", "status": 400}), 400

    set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
    values = list(updates.values()) + [user_id]

    with get_connection() as conn:
        conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)

    log_activity("update", "profile", user=g.current_user.get("sub"))
    return jsonify({"message": "Profile updated successfully"})


@account_bp.route("/password", methods=["PUT"])
@token_required
def change_password():
    """Change own password (requires current_password + new_password)."""
    data = request.get_json(silent=True) or {}
    validate_password_change(data)

    username = g.current_user["sub"]

    try:
        auth = UserAuth()
        # Verify current password
        auth.login(username, data["current_password"])
        auth.logout()
    except Exception:
        return jsonify({"error": "Current password is incorrect", "status": 400}), 400

    try:
        auth = UserAuth()
        auth.change_password(username, data["new_password"])
    except Exception as exc:
        logger.error("Credential update failed: %s", exc)
        return jsonify({"error": "Internal server error", "status": 500}), 500

    log_activity("change_password", "account", user=username)
    return jsonify({"message": "Password changed successfully"})


@account_bp.route("/preferences", methods=["GET"])
@token_required
def get_preferences():
    """Read user preferences."""
    user_id = g.current_user["user_id"]

    prefs = {
        "theme": "light",
        "language": "en",
        "timezone": "UTC",
        "email_notifications": True,
        "sms_notifications": False,
    }

    with get_connection() as conn:
        try:
            rows = conn.execute(
                "SELECT pref_key, pref_value FROM user_preferences WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            for row in rows:
                prefs[row[0]] = row[1]
        except Exception:
            pass

    return jsonify({"preferences": prefs})


@account_bp.route("/preferences", methods=["PUT"])
@token_required
def update_preferences():
    """Update user preferences."""
    data = request.get_json(silent=True) or {}
    validate_preferences_update(data)

    user_id = g.current_user["user_id"]
    allowed = {"theme", "language", "timezone", "email_notifications", "sms_notifications"}
    updates = {k: v for k, v in data.items() if k in allowed}

    if not updates:
        return jsonify({"error": "No valid preferences to update", "status": 400}), 400

    with get_connection() as conn:
        # Ensure table exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                pref_key TEXT NOT NULL,
                pref_value TEXT,
                UNIQUE(user_id, pref_key)
            )
        """)

        for key, value in updates.items():
            conn.execute(
                "INSERT INTO user_preferences (user_id, pref_key, pref_value) "
                "VALUES (?, ?, ?) ON CONFLICT(user_id, pref_key) "
                "DO UPDATE SET pref_value = excluded.pref_value",
                (user_id, key, str(value)),
            )

    log_activity("update", "preferences", user=g.current_user.get("sub"))
    return jsonify({"message": "Preferences updated successfully"})


@account_bp.route("/sessions", methods=["GET"])
@token_required
def get_sessions():
    """Return recent login history from login_attempts table."""
    user_id = g.current_user["user_id"]
    username = g.current_user["sub"]

    sessions = []
    with get_connection() as conn:
        try:
            rows = conn.execute(
                "SELECT ip_address, user_agent, login_time, success "
                "FROM login_attempts WHERE username = ? "
                "ORDER BY login_time DESC LIMIT 20",
                (username,),
            ).fetchall()
            for row in rows:
                sessions.append({
                    "ip_address": row[0],
                    "user_agent": row[1],
                    "login_time": row[2],
                    "success": bool(row[3]),
                })
        except Exception:
            pass

    return jsonify({"sessions": sessions})
