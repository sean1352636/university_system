"""Notification routes: notifications and preferences."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import validate_notification_create
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

notification_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


@notification_bp.route("", methods=["GET"])
@token_required
def list_notifications():
    user_id = request.args.get("user_id", g.current_user.get("sub"))
    is_read = request.args.get("is_read")
    priority = request.args.get("priority")

    with get_connection() as conn:
        conditions = ["user_id = ?"]
        params: list = [user_id]
        if is_read is not None:
            conditions.append("is_read = ?")
            params.append(int(is_read))
        if priority:
            conditions.append("priority = ?")
            params.append(priority)

        where = " WHERE " + " AND ".join(conditions)
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM notifications" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
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


@notification_bp.route("", methods=["POST"])
@token_required
def create_notification():
    data = request.get_json(silent=True) or {}
    validate_notification_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO notifications
               (user_id, channel, priority, title, message, source_system, source_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data["user_id"],
                data["channel"],
                data["priority"],
                data["title"],
                data["message"],
                data.get("source_system", ""),
                data.get("source_id", ""),
            ),
        )
        notif_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM notifications WHERE notification_id = ?", (notif_id,)
        ).fetchone()

    log_activity("create", "notification", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@notification_bp.route("/<int:notification_id>/read", methods=["POST"])
@token_required
def mark_read(notification_id: int):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            "UPDATE notifications SET is_read = 1, read_at = ? WHERE notification_id = ?",
            (now, notification_id),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM notifications WHERE notification_id = ?", (notification_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Notification {notification_id} not found")

    log_activity("update", "notification_read", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@notification_bp.route("/mark-all-read", methods=["POST"])
@token_required
def mark_all_read():
    user_id = g.current_user.get("sub")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        result = conn.execute(
            "UPDATE notifications SET is_read = 1, read_at = ? WHERE user_id = ? AND is_read = 0",
            (now, user_id),
        )
        count = result.rowcount

    log_activity("update", "notifications_mark_all_read", user=user_id)
    return jsonify({"marked_read": count})


# ---- Preferences ----

@notification_bp.route("/preferences", methods=["GET"])
@token_required
def get_preferences():
    user_id = g.current_user.get("sub")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM notification_preferences WHERE user_id = ?", (user_id,)
        ).fetchone()

    if not row:
        return jsonify({"user_id": user_id, "preferences": None})

    log_activity("view", "notification_preferences", user=user_id)
    return jsonify(_row_to_dict(row))


@notification_bp.route("/preferences", methods=["PUT"])
@token_required
def update_preferences():
    user_id = g.current_user.get("sub")
    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM notification_preferences WHERE user_id = ?", (user_id,)
        ).fetchone()

    if existing:
        set_clauses = []
        values = []
        allowed = [
            "quiet_hours_start", "quiet_hours_end", "daily_digest_enabled",
            "daily_digest_time", "bundle_notifications", "bundle_time_window",
        ]
        for field in allowed:
            if field in data:
                set_clauses.append(field + " = ?")
                values.append(data[field])

        if not set_clauses:
            raise ValidationError("No valid fields to update")

        set_clauses.append("updated_at = ?")
        values.append(now)
        values.append(user_id)

        with transaction() as conn:
            conn.execute(
                "UPDATE notification_preferences SET " + ", ".join(set_clauses) + " WHERE user_id = ?",
                values,
            )
    else:
        with transaction() as conn:
            conn.execute(
                """INSERT INTO notification_preferences
                   (user_id, quiet_hours_start, quiet_hours_end, daily_digest_enabled,
                    daily_digest_time, bundle_notifications, bundle_time_window, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    data.get("quiet_hours_start"),
                    data.get("quiet_hours_end"),
                    data.get("daily_digest_enabled", 0),
                    data.get("daily_digest_time", "08:00"),
                    data.get("bundle_notifications", 1),
                    data.get("bundle_time_window", 300),
                    now,
                    now,
                ),
            )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM notification_preferences WHERE user_id = ?", (user_id,)
        ).fetchone()

    log_activity("update", "notification_preferences", user=user_id)
    return jsonify(_row_to_dict(row))
