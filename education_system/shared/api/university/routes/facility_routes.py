"""Facility routes: bookings and maintenance requests."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import admin_required, token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import (
    validate_facility_booking_create,
    validate_maintenance_request_create,
)
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

facility_bp = Blueprint("facilities", __name__, url_prefix="/api/facilities")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Bookings ----

@facility_bp.route("/bookings", methods=["GET"])
@token_required
def list_bookings():
    facility_name = request.args.get("facility_name")
    user_id = request.args.get("user_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params = []
        if facility_name:
            conditions.append("facility_name = ?")
            params.append(facility_name)
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM facility_bookings" + where + " ORDER BY booking_date DESC, start_time LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM facility_bookings" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "facility_bookings", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@facility_bp.route("/bookings", methods=["POST"])
@token_required
def create_booking():
    data = request.get_json(silent=True) or {}
    validate_facility_booking_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO facility_bookings
               (facility_name, user_id, booking_date, start_time, end_time, purpose, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (
                data["facility_name"],
                g.current_user.get("user_id"),
                data["booking_date"],
                data["start_time"],
                data["end_time"],
                data["purpose"],
                now,
            ),
        )
        booking_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM facility_bookings WHERE booking_id = ?", (booking_id,)
        ).fetchone()

    log_activity("create", "facility_booking", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@facility_bp.route("/bookings/<int:booking_id>", methods=["PUT"])
@token_required
def update_booking(booking_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM facility_bookings WHERE booking_id = ?", (booking_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Booking {booking_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = ["facility_name", "booking_date", "start_time", "end_time", "purpose", "status"]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    values.append(booking_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE facility_bookings SET " + ", ".join(set_clauses) + " WHERE booking_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM facility_bookings WHERE booking_id = ?", (booking_id,)
        ).fetchone()

    log_activity("update", "facility_booking", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Maintenance Requests ----

@facility_bp.route("/maintenance", methods=["GET"])
@token_required
def list_maintenance():
    status = request.args.get("status")
    priority = request.args.get("priority")

    with get_connection() as conn:
        conditions = []
        params = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if priority:
            conditions.append("priority = ?")
            params.append(priority)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM maintenance_requests" + where + " ORDER BY reported_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM maintenance_requests" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "maintenance_requests", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@facility_bp.route("/maintenance", methods=["POST"])
@token_required
def create_maintenance():
    data = request.get_json(silent=True) or {}
    validate_maintenance_request_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO maintenance_requests
               (location_type, building_id, room_id, request_type, priority,
                description, reported_by, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)""",
            (
                data["location_type"],
                data.get("building_id"),
                data.get("room_id"),
                data["request_type"],
                data["priority"],
                data["description"],
                data["reported_by"],
                data.get("notes", ""),
            ),
        )
        req_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM maintenance_requests WHERE request_id = ?", (req_id,)
        ).fetchone()

    log_activity("create", "maintenance_request", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@facility_bp.route("/maintenance/<int:request_id>", methods=["PUT"])
@token_required
def update_maintenance(request_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM maintenance_requests WHERE request_id = ?", (request_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Maintenance request {request_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = [
        "priority", "status", "assigned_to", "assigned_date",
        "scheduled_date", "completion_date", "cost", "notes",
    ]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    values.append(request_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE maintenance_requests SET " + ", ".join(set_clauses) + " WHERE request_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM maintenance_requests WHERE request_id = ?", (request_id,)
        ).fetchone()

    log_activity("update", "maintenance_request", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))
