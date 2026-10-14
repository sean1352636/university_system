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
                "SELECT * FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') WHERE name LIKE ? OR description LIKE ?",
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
            "SELECT * FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar')" + where + " ORDER BY COALESCE(date, date_start) LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar')" + where, params_count
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
            "SELECT * FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') WHERE id = ?", (event_id,)
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
            """INSERT INTO unified_events (
                    source_event_id, title, event_date, start_datetime, end_datetime, description, event_type, created_at, updated_at, created_by, source_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'academic_calendar')""",
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
            "SELECT * FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') WHERE id = ?", (event_id,)
        ).fetchone()

    log_activity("create", "calendar_event", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@calendar_bp.route("/<event_id>", methods=["PUT"])
@token_required
@admin_required
def update_event(event_id: str):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') WHERE id = ?", (event_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Calendar event {event_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    # The API field names are the public contract; unified_events stores them
    # under its own column names.
    COLUMN_FOR_FIELD = {
        "name": "title", "date": "event_date", "date_start": "start_datetime",
        "date_end": "end_datetime", "description": "description",
        "event_type": "event_type",
    }
    for field, column in COLUMN_FOR_FIELD.items():
        if field in data:
            set_clauses.append(column + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_clauses.append("updated_at = ?")
    values.append(now)
    values.append(event_id)

    with transaction() as conn:
        conn.execute(
            "UPDATE unified_events SET " + ", ".join(set_clauses) + " WHERE source_type = 'academic_calendar' AND (source_event_id = ?)",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') WHERE id = ?", (event_id,)
        ).fetchone()

    log_activity("update", "calendar_event", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@calendar_bp.route("/<event_id>", methods=["DELETE"])
@token_required
@admin_required
def delete_event(event_id: str):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') WHERE id = ?", (event_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Calendar event {event_id} not found")

    with transaction() as conn:
        conn.execute("DELETE FROM unified_events WHERE source_type = 'academic_calendar' AND (source_event_id = ?)", (event_id,))

    log_activity("delete", "calendar_event", user=g.current_user.get("sub"))
    return jsonify({"message": f"Calendar event {event_id} deleted"})
