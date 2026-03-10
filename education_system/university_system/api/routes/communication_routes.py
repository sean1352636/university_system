"""Communication routes: messages, emails, newsletters, SMS, group messages."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.university_system.api.auth import admin_required, token_required
from education_system.university_system.api.pagination import get_pagination_params, paginated_response
from education_system.university_system.api.validators import validate_message_create, validate_newsletter_create
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

communication_bp = Blueprint("communication", __name__, url_prefix="/api/communication")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Messages ----

@communication_bp.route("/messages", methods=["GET"])
@token_required
def list_messages():
    sender_id = request.args.get("sender_id")
    recipient_id = request.args.get("recipient_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if sender_id:
            conditions.append("sender_id = ?")
            params.append(sender_id)
        if recipient_id:
            conditions.append("recipient_id = ?")
            params.append(recipient_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM messages" + where + " ORDER BY sent_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM messages" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "messages", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@communication_bp.route("/messages/<int:message_id>", methods=["GET"])
@token_required
def get_message(message_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM messages WHERE id = ?", (message_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Message {message_id} not found")
    log_activity("view", "message", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@communication_bp.route("/messages", methods=["POST"])
@token_required
def create_message():
    data = request.get_json(silent=True) or {}
    validate_message_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO messages
               (sender_id, recipient_id, subject, content, sent_at, reply_to)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                g.current_user.get("user_id"),
                data["recipient_id"],
                data["subject"],
                data.get("content", ""),
                now,
                data.get("reply_to"),
            ),
        )
        msg_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM messages WHERE id = ?", (msg_id,)
        ).fetchone()

    log_activity("create", "message", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@communication_bp.route("/messages/<int:message_id>/read", methods=["PUT"])
@token_required
def mark_message_read(message_id: int):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            "UPDATE messages SET is_read = 1, read_at = ? WHERE id = ?",
            (now, message_id),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM messages WHERE id = ?", (message_id,)
        ).fetchone()

    log_activity("update", "message_read", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Emails (sent log) ----

@communication_bp.route("/emails", methods=["GET"])
@token_required
@admin_required
def list_emails():
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM emails" + where + " ORDER BY sent_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM emails" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "emails", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- Email Templates ----

@communication_bp.route("/email-templates", methods=["GET"])
@token_required
def list_email_templates():
    template_type = request.args.get("template_type")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if template_type:
            conditions.append("template_type = ?")
            params.append(template_type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            "SELECT * FROM email_templates" + where + " ORDER BY template_name",
            params,
        ).fetchall()

    log_activity("view", "email_templates", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- Newsletters ----

@communication_bp.route("/newsletters", methods=["GET"])
@token_required
def list_newsletters():
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM newsletters" + where + " ORDER BY created_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM newsletters" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "newsletters", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@communication_bp.route("/newsletters", methods=["POST"])
@token_required
@admin_required
def create_newsletter():
    data = request.get_json(silent=True) or {}
    validate_newsletter_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO newsletters
               (title, content, target_audience, created_date, created_by, status)
               VALUES (?, ?, ?, ?, ?, 'draft')""",
            (
                data["title"],
                data["content"],
                data.get("target_audience"),
                now,
                g.current_user.get("sub"),
            ),
        )
        nid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM newsletters WHERE newsletter_id = ?", (nid,)
        ).fetchone()

    log_activity("create", "newsletter", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- SMS Messages (read-only log) ----

@communication_bp.route("/sms", methods=["GET"])
@token_required
@admin_required
def list_sms():
    with get_connection() as conn:
        page, per_page, offset = get_pagination_params()
        rows = conn.execute(
            "SELECT * FROM sms_messages ORDER BY sent_at DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
        total_row = conn.execute("SELECT COUNT(*) FROM sms_messages").fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "sms_messages", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- Group Messages ----

@communication_bp.route("/group-messages", methods=["GET"])
@token_required
def list_group_messages():
    group_type = request.args.get("group_type")
    group_id = request.args.get("group_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if group_type:
            conditions.append("group_type = ?")
            params.append(group_type)
        if group_id:
            conditions.append("group_id = ?")
            params.append(group_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM group_messages" + where + " ORDER BY sent_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM group_messages" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "group_messages", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))
