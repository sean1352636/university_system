"""Chat routes: messaging rooms and messages."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from university_system.api.auth import token_required
from university_system.api.pagination import get_pagination_params, paginated_response
from university_system.api.validators import validate_chat_message_create, validate_chat_room_create
from university_system.core.exceptions import ValidationError
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Rooms ----

@chat_bp.route("/rooms", methods=["GET"])
@token_required
def list_rooms():
    room_type = request.args.get("room_type")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{search}%"
            rows = conn.execute(
                "SELECT * FROM chat_rooms WHERE is_active = 1 AND (name LIKE ? OR description LIKE ?)",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = ["is_active = 1"]
        params: list = []
        if room_type:
            conditions.append("room_type = ?")
            params.append(room_type)

        where = " WHERE " + " AND ".join(conditions)
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM chat_rooms" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM chat_rooms" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "chat_rooms", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@chat_bp.route("/rooms/<int:room_id>", methods=["GET"])
@token_required
def get_room(room_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM chat_rooms WHERE id = ?", (room_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Chat room {room_id} not found")
    log_activity("view", "chat_room", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@chat_bp.route("/rooms", methods=["POST"])
@token_required
def create_room():
    data = request.get_json(silent=True) or {}
    validate_chat_room_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO chat_rooms
               (name, description, room_type, created_by, created_at, max_members)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                data["name"],
                data.get("description", ""),
                data["room_type"],
                g.current_user.get("user_id"),
                now,
                data.get("max_members", 50),
            ),
        )
        room_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM chat_rooms WHERE id = ?", (room_id,)
        ).fetchone()

    log_activity("create", "chat_room", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Messages ----

@chat_bp.route("/rooms/<int:room_id>/messages", methods=["GET"])
@token_required
def list_messages(room_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM chat_rooms WHERE id = ?", (room_id,)
        ).fetchone()
        if not existing:
            raise ValidationError(f"Chat room {room_id} not found")

        page, per_page, offset = get_pagination_params()
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE room_id = ? ORDER BY sent_at DESC LIMIT ? OFFSET ?",
            (room_id, per_page, offset),
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM chat_messages WHERE room_id = ?", (room_id,)
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "chat_messages", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@chat_bp.route("/rooms/<int:room_id>/messages", methods=["POST"])
@token_required
def create_message(room_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM chat_rooms WHERE id = ?", (room_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Chat room {room_id} not found")

    data = request.get_json(silent=True) or {}
    validate_chat_message_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO chat_messages (room_id, sender_id, content, sent_at)
               VALUES (?, ?, ?, ?)""",
            (room_id, g.current_user.get("user_id"), data["content"], now),
        )
        msg_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM chat_messages WHERE id = ?", (msg_id,)
        ).fetchone()

    log_activity("create", "chat_message", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
