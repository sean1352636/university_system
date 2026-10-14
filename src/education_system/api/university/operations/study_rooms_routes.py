"""Study rooms routes: rooms and bookings."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import token_required
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

study_rooms_bp = Blueprint("study_rooms", __name__, url_prefix="/api/study-rooms")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- rooms ----

@study_rooms_bp.route("/rooms", methods=["GET"])
@token_required
def list_rooms():
    search = request.args.get("search")
    status = request.args.get("status")
    is_bookable = request.args.get("is_bookable")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM study_rooms WHERE room_name LIKE ? OR location LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if is_bookable:
            conditions.append("is_bookable = ?")
            params.append(is_bookable)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM study_rooms" + where + " ORDER BY room_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM study_rooms" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "study_rooms", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@study_rooms_bp.route("/rooms/<int:room_id>", methods=["GET"])
@token_required
def get_room(room_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_rooms WHERE room_id = ?", (room_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"rooms {room_id} not found")
    log_activity("view", "study_rooms", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@study_rooms_bp.route("/rooms", methods=["POST"])
@token_required
def create_room():
    data = request.get_json(silent=True) or {}
    for field in ["room_name", "capacity", "location"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO study_rooms
               (room_name, capacity, location, amenities, is_bookable, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["room_name"], data["capacity"], data["location"], data.get("amenities", ""), data.get("is_bookable", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_rooms WHERE room_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "study_rooms", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- bookings ----

@study_rooms_bp.route("/bookings", methods=["GET"])
@token_required
def list_bookings():
    room_id = request.args.get("room_id")
    student_id = request.args.get("student_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if room_id:
            conditions.append("room_id = ?")
            params.append(room_id)
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM study_room_bookings" + where + " ORDER BY booking_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM study_room_bookings" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "study_room_bookings", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@study_rooms_bp.route("/bookings/<int:booking_id>", methods=["GET"])
@token_required
def get_booking(booking_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_room_bookings WHERE booking_id = ?", (booking_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"bookings {booking_id} not found")
    log_activity("view", "study_room_bookings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@study_rooms_bp.route("/bookings", methods=["POST"])
@token_required
def create_booking():
    data = request.get_json(silent=True) or {}
    for field in ["room_id", "student_id", "booking_date", "start_time", "end_time"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO study_room_bookings
               (room_id, student_id, booking_date, start_time, end_time, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["room_id"], data["student_id"], data["booking_date"], data["start_time"], data["end_time"], data.get("notes", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_room_bookings WHERE booking_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "study_room_bookings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
