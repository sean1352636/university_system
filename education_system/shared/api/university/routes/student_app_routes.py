"""Student app routes: dashboard, preferences, notifications, and quick links."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

student_app_bp = Blueprint("student_app", __name__, url_prefix="/api/student-app")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- preferences ----

@student_app_bp.route("/preferences/<student_id>", methods=["GET"])
@token_required
def get_preferences(student_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_app_preferences WHERE student_id = ?", (student_id,)
        ).fetchone()

    log_activity("view", "student_app_preferences", user=g.current_user.get("sub"))
    if not row:
        return jsonify({"student_id": student_id, "theme": "light",
                        "notifications_enabled": 1, "language": "en"})
    return jsonify(_row_to_dict(row))


@student_app_bp.route("/preferences/<student_id>", methods=["PUT"])
@token_required
def update_preferences(student_id: str):
    data = request.get_json(silent=True) or {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        existing = conn.execute(
            "SELECT id FROM student_app_preferences WHERE student_id = ?", (student_id,)
        ).fetchone()

        if existing:
            allowed = ["theme", "notifications_enabled", "language", "dashboard_layout"]
            sets = ["updated_at = ?"]
            params: list = [now]
            for key in allowed:
                if key in data:
                    sets.append(f"{key} = ?")
                    params.append(data[key])
            params.append(student_id)
            conn.execute(
                f"UPDATE student_app_preferences SET {', '.join(sets)} WHERE student_id = ?",
                params,
            )
        else:
            conn.execute(
                """INSERT INTO student_app_preferences
                   (student_id, theme, notifications_enabled, language, dashboard_layout, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (student_id, data.get("theme", "light"),
                 data.get("notifications_enabled", 1),
                 data.get("language", "en"),
                 data.get("dashboard_layout", ""), now),
            )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_app_preferences WHERE student_id = ?", (student_id,)
        ).fetchone()

    log_activity("update", "student_app_preferences", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- notifications ----

@student_app_bp.route("/notifications", methods=["GET"])
@token_required
def list_notifications():
    student_id = request.args.get("student_id")
    unread_only = request.args.get("unread_only", "false").lower() == "true"
    notification_type = request.args.get("type")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if unread_only:
            conditions.append("is_read = 0")
        if notification_type:
            conditions.append("notification_type = ?")
            params.append(notification_type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM student_app_notifications" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM student_app_notifications" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "student_app_notifications", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@student_app_bp.route("/notifications/<int:notification_id>", methods=["GET"])
@token_required
def get_notification(notification_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_app_notifications WHERE id = ?", (notification_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Notification {notification_id} not found")
    log_activity("view", "student_app_notification", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@student_app_bp.route("/notifications", methods=["POST"])
@token_required
def create_notification():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "title"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO student_app_notifications
               (student_id, notification_type, title, message, expires_at)
               VALUES (?, ?, ?, ?, ?)""",
            (data["student_id"], data.get("notification_type", "announcement"),
             data["title"], data.get("message", ""), data.get("expires_at", "")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_app_notifications WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "student_app_notification", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@student_app_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@token_required
def mark_notification_read(notification_id: int):
    with transaction() as conn:
        conn.execute(
            "UPDATE student_app_notifications SET is_read = 1 WHERE id = ?",
            (notification_id,),
        )

    log_activity("update", "student_app_notification_read", user=g.current_user.get("sub"))
    return jsonify({"message": "Notification marked as read"})


@student_app_bp.route("/notifications/<student_id>/read-all", methods=["POST"])
@token_required
def mark_all_read(student_id: str):
    with transaction() as conn:
        conn.execute(
            "UPDATE student_app_notifications SET is_read = 1 WHERE student_id = ? AND is_read = 0",
            (student_id,),
        )

    log_activity("update", "student_app_notifications_read_all", user=g.current_user.get("sub"))
    return jsonify({"message": "All notifications marked as read"})


# ---- quick links ----

@student_app_bp.route("/quick-links/<student_id>", methods=["GET"])
@token_required
def get_quick_links(student_id: str):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM student_quick_links WHERE student_id = ? AND is_active = 1 ORDER BY display_order",
            (student_id,),
        ).fetchall()

    log_activity("view", "student_quick_links", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@student_app_bp.route("/quick-links", methods=["POST"])
@token_required
def add_quick_link():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "link_title", "link_url"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO student_quick_links
               (student_id, link_title, link_url, display_order)
               VALUES (?, ?, ?, ?)""",
            (data["student_id"], data["link_title"], data["link_url"],
             data.get("display_order", 0)),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_quick_links WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "student_quick_link", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@student_app_bp.route("/quick-links/<int:link_id>", methods=["DELETE"])
@token_required
def remove_quick_link(link_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_quick_links WHERE id = ?", (link_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Quick link {link_id} not found")

    with transaction() as conn:
        conn.execute(
            "UPDATE student_quick_links SET is_active = 0 WHERE id = ?", (link_id,)
        )

    log_activity("delete", "student_quick_link", user=g.current_user.get("sub"))
    return jsonify({"message": "Quick link removed"})


# ---- dashboard & unread count ----

@student_app_bp.route("/dashboard/<student_id>", methods=["GET"])
@token_required
def get_dashboard(student_id: str):
    dashboard = {
        "student_id": student_id,
        "timetable": [],
        "grades": [],
        "notifications": [],
        "deadlines": [],
        "unread_notifications": 0,
    }
    with get_connection() as conn:
        try:
            rows = conn.execute(
                "SELECT * FROM timetable_entries WHERE student_id = ? ORDER BY day, start_time LIMIT 10",
                (student_id,),
            ).fetchall()
            dashboard["timetable"] = [_row_to_dict(r) for r in rows]
        except Exception:
            pass
        try:
            rows = conn.execute(
                "SELECT * FROM grades WHERE student_id = ? ORDER BY date_recorded DESC LIMIT 5",
                (student_id,),
            ).fetchall()
            dashboard["grades"] = [_row_to_dict(r) for r in rows]
        except Exception:
            pass
        unread = conn.execute(
            "SELECT COUNT(*) FROM student_app_notifications WHERE student_id = ? AND is_read = 0",
            (student_id,),
        ).fetchone()[0]
        dashboard["unread_notifications"] = unread
        notifs = conn.execute(
            "SELECT * FROM student_app_notifications WHERE student_id = ? ORDER BY created_at DESC LIMIT 5",
            (student_id,),
        ).fetchall()
        dashboard["notifications"] = [_row_to_dict(r) for r in notifs]

    log_activity("view", "student_app_dashboard", user=g.current_user.get("sub"))
    return jsonify(dashboard)


@student_app_bp.route("/notifications/<student_id>/unread-count", methods=["GET"])
@token_required
def get_unread_count(student_id: str):
    with get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM student_app_notifications WHERE student_id = ? AND is_read = 0",
            (student_id,),
        ).fetchone()[0]

    log_activity("view", "student_app_unread_count", user=g.current_user.get("sub"))
    return jsonify({"student_id": student_id, "unread_count": count})
