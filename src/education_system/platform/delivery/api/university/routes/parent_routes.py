"""Parent portal routes: accounts, student links, messages, conferences, documents, notifications."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import token_required
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.platform.delivery.api.university.validators import (
    validate_parent_conference_create,
    validate_parent_message_create,
)
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

parent_bp = Blueprint("parents", __name__, url_prefix="/api/parents")

SENSITIVE_FIELDS = {"two_factor_secret"}


def _row_to_dict(row, exclude: set | None = None) -> dict:
    if row is None:
        return {}
    d = {k: row[k] for k in row.keys()}
    if exclude:
        for f in exclude:
            d.pop(f, None)
    return d


# ---- Accounts ----

@parent_bp.route("/accounts", methods=["GET"])
@token_required
def list_accounts():
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM parent_accounts WHERE first_name LIKE ? OR last_name LIKE ? OR email LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r, SENSITIVE_FIELDS) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        page, per_page, offset = get_pagination_params()
        rows = conn.execute(
            "SELECT * FROM parent_accounts ORDER BY last_name, first_name LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
        total_row = conn.execute("SELECT COUNT(*) FROM parent_accounts").fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "parent_accounts", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r, SENSITIVE_FIELDS) for r in rows], total, page, per_page
    ))


@parent_bp.route("/accounts/<parent_id>", methods=["GET"])
@token_required
def get_account(parent_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM parent_accounts WHERE parent_id = ?", (parent_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Parent account {parent_id} not found")
    log_activity("view", "parent_account", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row, SENSITIVE_FIELDS))


# ---- Student Links ----

@parent_bp.route("/accounts/<parent_id>/students", methods=["GET"])
@token_required
def list_student_links(parent_id: str):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM parent_student_links WHERE parent_id = ?", (parent_id,)
        ).fetchall()

    log_activity("view", "parent_student_links", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- Messages ----

@parent_bp.route("/messages", methods=["GET"])
@token_required
def list_messages():
    parent_id = request.args.get("parent_id")
    student_id = request.args.get("student_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if parent_id:
            conditions.append("parent_id = ?")
            params.append(parent_id)
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM parent_messages" + where + " ORDER BY created_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM parent_messages" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "parent_messages", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@parent_bp.route("/messages", methods=["POST"])
@token_required
def create_message():
    data = request.get_json(silent=True) or {}
    validate_parent_message_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO parent_messages
               (parent_id, teacher_id, student_id, message_content, created_date,
                is_from_parent, message_type)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data["parent_id"],
                data.get("teacher_id"),
                data.get("student_id"),
                data["message_content"],
                now,
                data.get("is_from_parent", 1),
                data.get("message_type", "individual"),
            ),
        )
        msg_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM parent_messages WHERE id = ?", (msg_id,)
        ).fetchone()

    log_activity("create", "parent_message", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Conferences ----

@parent_bp.route("/conferences", methods=["GET"])
@token_required
def list_conferences():
    parent_id = request.args.get("parent_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if parent_id:
            conditions.append("parent_id = ?")
            params.append(parent_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM parent_conferences" + where + " ORDER BY datetime DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM parent_conferences" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "parent_conferences", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@parent_bp.route("/conferences", methods=["POST"])
@token_required
def create_conference():
    data = request.get_json(silent=True) or {}
    validate_parent_conference_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO parent_conferences
               (parent_id, teacher_id, student_id, datetime, location,
                meeting_type, meeting_link, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'scheduled', ?)""",
            (
                data["parent_id"],
                data["teacher_id"],
                data.get("student_id"),
                data["datetime"],
                data.get("location"),
                data.get("meeting_type", "in_person"),
                data.get("meeting_link"),
                data.get("notes", ""),
            ),
        )
        conf_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM parent_conferences WHERE conference_id = ?", (conf_id,)
        ).fetchone()

    log_activity("create", "parent_conference", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Documents ----

@parent_bp.route("/documents", methods=["GET"])
@token_required
def list_documents():
    parent_id = request.args.get("parent_id")
    student_id = request.args.get("student_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if parent_id:
            conditions.append("parent_id = ?")
            params.append(parent_id)
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            "SELECT * FROM parent_documents" + where + " ORDER BY upload_date DESC",
            params,
        ).fetchall()

    log_activity("view", "parent_documents", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- Notifications ----

@parent_bp.route("/notifications", methods=["GET"])
@token_required
def list_notifications():
    parent_id = request.args.get("parent_id")
    if not parent_id:
        raise ValidationError("parent_id query parameter is required")

    with get_connection() as conn:
        page, per_page, offset = get_pagination_params()
        rows = conn.execute(
            "SELECT * FROM parent_notifications WHERE parent_id = ? ORDER BY created_date DESC LIMIT ? OFFSET ?",
            (parent_id, per_page, offset),
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM parent_notifications WHERE parent_id = ?", (parent_id,)
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "parent_notifications", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@parent_bp.route("/notifications/<int:notification_id>/read", methods=["PUT"])
@token_required
def mark_notification_read(notification_id: int):
    with transaction() as conn:
        conn.execute(
            "UPDATE parent_notifications SET read_status = 1 WHERE id = ?",
            (notification_id,),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM parent_notifications WHERE id = ?", (notification_id,)
        ).fetchone()

    log_activity("update", "parent_notification", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))
