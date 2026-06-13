"""Campus event routes: events and registrations."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import validate_event_create, validate_event_registration_create
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

event_bp = Blueprint("events", __name__, url_prefix="/api/events")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


@event_bp.route("", methods=["GET"])
@token_required
def list_events():
    category = request.args.get("category")
    search = request.args.get("search")
    upcoming = request.args.get("upcoming")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM events WHERE cancelled = 0 AND (title LIKE ? OR description LIKE ?)",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = ["cancelled = 0"]
        params: list = []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if upcoming:
            conditions.append("start_datetime >= ?")
            params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        where = " WHERE " + " AND ".join(conditions)
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM events" + where + " ORDER BY start_datetime LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM events" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "events", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@event_bp.route("/<int:event_id>", methods=["GET"])
@token_required
def get_event(event_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM events WHERE event_id = ?", (event_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Event {event_id} not found")
    log_activity("view", "event", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@event_bp.route("", methods=["POST"])
@token_required
def create_event():
    data = request.get_json(silent=True) or {}
    validate_event_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO events
               (title, description, category, start_datetime, end_datetime,
                location, building, room, organizer_id, organizer_name,
                organizer_type, max_capacity, registration_required,
                registration_deadline, tags, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["title"],
                data.get("description", ""),
                data["category"],
                data["start_datetime"],
                data["end_datetime"],
                data["location"],
                data.get("building", ""),
                data.get("room", ""),
                data.get("organizer_id"),
                data.get("organizer_name", ""),
                data.get("organizer_type", ""),
                data.get("max_capacity"),
                data.get("registration_required", 0),
                data.get("registration_deadline"),
                data.get("tags", ""),
                now,
                now,
            ),
        )
        event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM events WHERE event_id = ?", (event_id,)
        ).fetchone()

    log_activity("create", "event", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@event_bp.route("/<int:event_id>", methods=["PUT"])
@token_required
def update_event(event_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM events WHERE event_id = ?", (event_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Event {event_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = [
        "title", "description", "category", "start_datetime", "end_datetime",
        "location", "building", "room", "max_capacity", "registration_required",
        "registration_deadline", "tags", "cancelled",
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

    values.append(event_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE events SET " + ", ".join(set_clauses) + " WHERE event_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM events WHERE event_id = ?", (event_id,)
        ).fetchone()

    log_activity("update", "event", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Registrations ----

@event_bp.route("/<int:event_id>/registrations", methods=["GET"])
@token_required
def list_registrations(event_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM events WHERE event_id = ?", (event_id,)
        ).fetchone()
        if not existing:
            raise ValidationError(f"Event {event_id} not found")

        rows = conn.execute(
            "SELECT * FROM event_registrations WHERE event_id = ? ORDER BY registration_date DESC",
            (event_id,),
        ).fetchall()

    log_activity("view", "event_registrations", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@event_bp.route("/<int:event_id>/registrations", methods=["POST"])
@token_required
def create_registration(event_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM events WHERE event_id = ?", (event_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Event {event_id} not found")

    data = request.get_json(silent=True) or {}

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO event_registrations
               (event_id, user_id, user_type, registration_date, attendance_status)
               VALUES (?, ?, ?, ?, 'registered')""",
            (
                event_id,
                data.get("user_id", g.current_user.get("user_id")),
                data.get("user_type", g.current_user.get("role")),
                now,
            ),
        )
        reg_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM event_registrations WHERE registration_id = ?", (reg_id,)
        ).fetchone()

    log_activity("create", "event_registration", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
