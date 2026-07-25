"""Academic calendar routes: university calendar events."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import admin_required, token_required
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.platform.delivery.api.university.validators import validate_calendar_event_create
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

calendar_bp = Blueprint("calendar", __name__, url_prefix="/api/calendar")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


@calendar_bp.route("", methods=["GET"])
@token_required
def list_events():
    event_type = request.args.get("event_type")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM academic_calendar_events WHERE name LIKE ? OR description LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM academic_calendar_events" + where + " ORDER BY COALESCE(date, date_start) LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM academic_calendar_events" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "calendar_events", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@calendar_bp.route("/<event_id>", methods=["GET"])
@token_required
def get_event(event_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM academic_calendar_events WHERE id = ?", (event_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Calendar event {event_id} not found")
    log_activity("view", "calendar_event", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@calendar_bp.route("", methods=["POST"])
@token_required
@admin_required
def create_event():
    data = request.get_json(silent=True) or {}
    validate_calendar_event_create(data)

    event_id = str(uuid.uuid4())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO academic_calendar_events
               (id, name, date, date_start, date_end, description, event_type,
                date_added, last_modified, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id,
                data["name"],
                data.get("date"),
                data.get("date_start"),
                data.get("date_end"),
                data.get("description", ""),
                data["event_type"],
                now,
                now,
                g.current_user.get("sub"),
            ),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM academic_calendar_events WHERE id = ?", (event_id,)
        ).fetchone()

    log_activity("create", "calendar_event", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@calendar_bp.route("/<event_id>", methods=["PUT"])
@token_required
@admin_required
def update_event(event_id: str):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM academic_calendar_events WHERE id = ?", (event_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Calendar event {event_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = ["name", "date", "date_start", "date_end", "description", "event_type"]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_clauses.append("last_modified = ?")
    values.append(now)
    values.append(event_id)

    with transaction() as conn:
        conn.execute(
            "UPDATE academic_calendar_events SET " + ", ".join(set_clauses) + " WHERE id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM academic_calendar_events WHERE id = ?", (event_id,)
        ).fetchone()

    log_activity("update", "calendar_event", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@calendar_bp.route("/<event_id>", methods=["DELETE"])
@token_required
@admin_required
def delete_event(event_id: str):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM academic_calendar_events WHERE id = ?", (event_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Calendar event {event_id} not found")

    with transaction() as conn:
        conn.execute("DELETE FROM academic_calendar_events WHERE id = ?", (event_id,))

    log_activity("delete", "calendar_event", user=g.current_user.get("sub"))
    return jsonify({"message": f"Calendar event {event_id} deleted"})
