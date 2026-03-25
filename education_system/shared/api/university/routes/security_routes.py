"""Security desk routes: tickets and incident management."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import validate_security_ticket_create
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

security_bp = Blueprint("security", __name__, url_prefix="/api/security")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


@security_bp.route("/tickets", methods=["GET"])
@token_required
def list_tickets():
    status = request.args.get("status")
    priority = request.args.get("priority")
    ticket_type = request.args.get("type")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if priority:
            conditions.append("priority = ?")
            params.append(priority)
        if ticket_type:
            conditions.append("type = ?")
            params.append(ticket_type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM security_desk_tickets" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM security_desk_tickets" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "security_tickets", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@security_bp.route("/tickets/<ticket_id>", methods=["GET"])
@token_required
def get_ticket(ticket_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM security_desk_tickets WHERE id = ?", (ticket_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Ticket {ticket_id} not found")
    log_activity("view", "security_ticket", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@security_bp.route("/tickets", methods=["POST"])
@token_required
def create_ticket():
    data = request.get_json(silent=True) or {}
    validate_security_ticket_create(data)

    ticket_id = str(uuid.uuid4())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO security_desk_tickets
               (id, type, category, priority, status, subject, description,
                location, user_id, user_name, user_email, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'Open', ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ticket_id,
                data["type"],
                data.get("category", ""),
                data.get("priority", "Normal"),
                data["subject"],
                data["description"],
                data.get("location", ""),
                data.get("user_id", g.current_user.get("sub")),
                data.get("user_name", ""),
                data.get("user_email", ""),
                now,
                now,
            ),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM security_desk_tickets WHERE id = ?", (ticket_id,)
        ).fetchone()

    log_activity("create", "security_ticket", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@security_bp.route("/tickets/<ticket_id>", methods=["PUT"])
@token_required
def update_ticket(ticket_id: str):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM security_desk_tickets WHERE id = ?", (ticket_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Ticket {ticket_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = [
        "status", "priority", "category", "subject", "description",
        "location", "admin_notes",
    ]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_clauses.append("updated_at = ?")
    values.append(now)

    values.append(ticket_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE security_desk_tickets SET " + ", ".join(set_clauses) + " WHERE id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM security_desk_tickets WHERE id = ?", (ticket_id,)
        ).fetchone()

    log_activity("update", "security_ticket", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))
