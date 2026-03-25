"""Notification center routes: notifications, preferences, channels, and digests."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

notification_center_bp = Blueprint("notification_center", __name__, url_prefix="/api/notification-center")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- notifications ----

@notification_center_bp.route("/notifications", methods=["GET"])
@token_required
def list_notifications():
    search = request.args.get("search")
    user_id = request.args.get("user_id")
    channel = request.args.get("channel")
    priority = request.args.get("priority")
    is_read = request.args.get("is_read")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM notifications WHERE title LIKE ? OR message LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if channel:
            conditions.append("channel = ?")
            params.append(channel)
        if priority:
            conditions.append("priority = ?")
            params.append(priority)
        if is_read:
            conditions.append("is_read = ?")
            params.append(is_read)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM notifications" + where + " ORDER BY notification_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM notifications" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "notifications", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@notification_center_bp.route("/notifications/<int:notification_id>", methods=["GET"])
@token_required
def get_notification(notification_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM notifications WHERE notification_id = ?", (notification_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"notifications {notification_id} not found")
    log_activity("view", "notifications", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@notification_center_bp.route("/notifications", methods=["POST"])
@token_required
def create_notification():
    data = request.get_json(silent=True) or {}
    for field in ["user_id", "title", "message"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO notifications
               (user_id, title, message, channel, priority, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["user_id"], data["title"], data["message"], data.get("channel", ""), data.get("priority", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM notifications WHERE notification_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "notifications", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- preferences ----

@notification_center_bp.route("/preferences", methods=["GET"])
@token_required
def list_preferences():
    user_id = request.args.get("user_id")
    channel = request.args.get("channel")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if channel:
            conditions.append("channel = ?")
            params.append(channel)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM notification_preferences" + where + " ORDER BY preference_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM notification_preferences" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "notification_preferences", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@notification_center_bp.route("/preferences/<int:preference_id>", methods=["GET"])
@token_required
def get_preference(preference_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM notification_preferences WHERE preference_id = ?", (preference_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"preferences {preference_id} not found")
    log_activity("view", "notification_preferences", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@notification_center_bp.route("/preferences", methods=["POST"])
@token_required
def create_preference():
    data = request.get_json(silent=True) or {}
    for field in ["user_id", "channel"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO notification_preferences
               (user_id, channel, push_enabled, email_enabled, sms_enabled, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["user_id"], data["channel"], data.get("push_enabled", ""), data.get("email_enabled", ""), data.get("sms_enabled", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM notification_preferences WHERE preference_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "notification_preferences", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
