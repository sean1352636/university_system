"""Campus services routes: buildings, rooms, room bookings, tours, campus events, resource bookings."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from university_system.api.auth import admin_required, token_required
from university_system.api.pagination import get_pagination_params, paginated_response
from university_system.api.validators import (
    validate_campus_tour_create,
    validate_resource_booking_create,
    validate_room_booking_create,
)
from university_system.core.exceptions import ValidationError
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

campus_bp = Blueprint("campus", __name__, url_prefix="/api/campus")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Buildings ----

@campus_bp.route("/buildings", methods=["GET"])
@token_required
def list_buildings():
    building_type = request.args.get("building_type")

    with get_connection() as conn:
        conditions = ["is_active = 1"]
        params: list = []
        if building_type:
            conditions.append("building_type = ?")
            params.append(building_type)

        where = " WHERE " + " AND ".join(conditions)
        rows = conn.execute(
            "SELECT * FROM buildings" + where + " ORDER BY building_name",
            params,
        ).fetchall()

    log_activity("view", "buildings", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@campus_bp.route("/buildings/<int:building_id>", methods=["GET"])
@token_required
def get_building(building_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM buildings WHERE building_id = ?", (building_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Building {building_id} not found")
    log_activity("view", "building", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Rooms ----

@campus_bp.route("/rooms", methods=["GET"])
@token_required
def list_rooms():
    building_id = request.args.get("building_id")
    room_type = request.args.get("room_type")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = ["is_active = 1"]
        params: list = []
        if building_id:
            conditions.append("building_id = ?")
            params.append(building_id)
        if room_type:
            conditions.append("room_type = ?")
            params.append(room_type)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = " WHERE " + " AND ".join(conditions)
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM rooms" + where + " ORDER BY room_number LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM rooms" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "rooms", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- Room Bookings ----

@campus_bp.route("/room-bookings", methods=["GET"])
@token_required
def list_room_bookings():
    room_id = request.args.get("room_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if room_id:
            conditions.append("room_id = ?")
            params.append(room_id)
        if status:
            conditions.append("booking_status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM room_bookings" + where + " ORDER BY start_datetime DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM room_bookings" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "room_bookings", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@campus_bp.route("/room-bookings", methods=["POST"])
@token_required
def create_room_booking():
    data = request.get_json(silent=True) or {}
    validate_room_booking_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO room_bookings
               (room_id, booked_by, booking_type, purpose, start_datetime,
                end_datetime, expected_attendees, booking_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed')""",
            (
                data["room_id"],
                g.current_user.get("sub"),
                data["booking_type"],
                data.get("purpose", ""),
                data["start_datetime"],
                data["end_datetime"],
                data.get("expected_attendees"),
            ),
        )
        booking_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM room_bookings WHERE booking_id = ?", (booking_id,)
        ).fetchone()

    log_activity("create", "room_booking", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Campus Tours ----

@campus_bp.route("/tours", methods=["GET"])
@token_required
def list_tours():
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
            "SELECT * FROM campus_tours" + where + " ORDER BY tour_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM campus_tours" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "campus_tours", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@campus_bp.route("/tours", methods=["POST"])
@token_required
@admin_required
def create_tour():
    data = request.get_json(silent=True) or {}
    validate_campus_tour_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO campus_tours
               (tour_date, tour_time, tour_guide, max_attendees, meeting_point,
                duration_minutes, status)
               VALUES (?, ?, ?, ?, ?, ?, 'scheduled')""",
            (
                data["tour_date"],
                data["tour_time"],
                data.get("tour_guide"),
                data.get("max_attendees", 20),
                data.get("meeting_point"),
                data.get("duration_minutes", 90),
            ),
        )
        tour_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM campus_tours WHERE tour_id = ?", (tour_id,)
        ).fetchone()

    log_activity("create", "campus_tour", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Campus Events ----

@campus_bp.route("/events", methods=["GET"])
@token_required
def list_campus_events():
    event_type = request.args.get("event_type")
    status = request.args.get("status")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{search}%"
            rows = conn.execute(
                "SELECT * FROM campus_events WHERE event_name LIKE ? OR description LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM campus_events" + where + " ORDER BY event_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM campus_events" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "campus_events", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- Resource Bookings ----

@campus_bp.route("/resource-bookings", methods=["GET"])
@token_required
def list_resource_bookings():
    resource_id = request.args.get("resource_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if resource_id:
            conditions.append("resource_id = ?")
            params.append(resource_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            "SELECT * FROM resource_bookings" + where + " ORDER BY start_time DESC",
            params,
        ).fetchall()

    log_activity("view", "resource_bookings", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@campus_bp.route("/resource-bookings", methods=["POST"])
@token_required
def create_resource_booking():
    data = request.get_json(silent=True) or {}
    validate_resource_booking_create(data)

    import uuid
    booking_id = str(uuid.uuid4())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO resource_bookings
               (id, resource_id, event_id, start_time, end_time, status, notes, date_added)
               VALUES (?, ?, ?, ?, ?, 'confirmed', ?, ?)""",
            (
                booking_id,
                data["resource_id"],
                data.get("event_id"),
                data["start_time"],
                data["end_time"],
                data.get("notes", ""),
                now,
            ),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM resource_bookings WHERE id = ?", (booking_id,)
        ).fetchone()

    log_activity("create", "resource_booking", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Space Utilization ----

@campus_bp.route("/space-utilization", methods=["GET"])
@token_required
def list_space_utilization():
    room_id = request.args.get("room_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if room_id:
            conditions.append("room_id = ?")
            params.append(room_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM space_utilization" + where + " ORDER BY measurement_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM space_utilization" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "space_utilization", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))
