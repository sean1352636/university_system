"""Housing routes: applications, rooms, buildings, and assignments."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import (
    validate_housing_application_create,
    validate_housing_application_update,
)
from education_system.post_18.university_system.core.exceptions import ValidationError
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

housing_bp = Blueprint("housing", __name__, url_prefix="/api/housing")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Buildings ----

@housing_bp.route("/buildings", methods=["GET"])
@token_required
def list_buildings():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM housing_buildings ORDER BY building_name"
        ).fetchall()

    log_activity("view", "housing_buildings", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- Rooms ----

@housing_bp.route("/rooms", methods=["GET"])
@token_required
def list_rooms():
    building_id = request.args.get("building_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params = []
        if building_id:
            conditions.append("building_id = ?")
            params.append(building_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM housing_rooms" + where + " ORDER BY room_number LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM housing_rooms" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "housing_rooms", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@housing_bp.route("/rooms/<room_id>", methods=["GET"])
@token_required
def get_room(room_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM housing_rooms WHERE room_id = ?", (room_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Room {room_id} not found")
    log_activity("view", "housing_room", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Applications ----

@housing_bp.route("/applications", methods=["GET"])
@token_required
def list_applications():
    student_id = request.args.get("student_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params = []
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
            "SELECT * FROM housing_applications" + where + " ORDER BY application_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM housing_applications" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "housing_applications", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@housing_bp.route("/applications", methods=["POST"])
@token_required
def create_application():
    data = request.get_json(silent=True) or {}
    validate_housing_application_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    app_id = str(uuid.uuid4())
    with transaction() as conn:
        conn.execute(
            """INSERT INTO housing_applications
               (application_id, student_id, application_date, preferred_building_id,
                preferred_room_type, requested_move_in_date, requested_duration_months,
                special_requirements, status, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'submitted', ?, ?, ?)""",
            (
                app_id,
                data["student_id"],
                now,
                data.get("preferred_building_id"),
                data["preferred_room_type"],
                data["requested_move_in_date"],
                int(data["requested_duration_months"]),
                data.get("special_requirements", ""),
                data.get("notes", ""),
                now,
                now,
            ),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM housing_applications WHERE application_id = ?", (app_id,)
        ).fetchone()

    log_activity("create", "housing_application", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@housing_bp.route("/applications/<application_id>", methods=["PUT"])
@token_required
def update_application(application_id: str):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM housing_applications WHERE application_id = ?", (application_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Application {application_id} not found")

    data = request.get_json(silent=True) or {}
    validate_housing_application_update(data)

    set_clauses = []
    values = []
    allowed = [
        "status", "preferred_building_id", "preferred_room_type",
        "requested_move_in_date", "requested_duration_months",
        "special_requirements", "notes", "reviewed_by", "review_date",
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
    values.append(application_id)

    with transaction() as conn:
        conn.execute(
            "UPDATE housing_applications SET " + ", ".join(set_clauses) + " WHERE application_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM housing_applications WHERE application_id = ?", (application_id,)
        ).fetchone()

    log_activity("update", "housing_application", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Assignments ----

@housing_bp.route("/assignments", methods=["GET"])
@token_required
def list_assignments():
    student_id = request.args.get("student_id")

    with get_connection() as conn:
        if student_id:
            rows = conn.execute(
                """SELECT ha.*, hr.room_number, hr.room_type, hb.building_name
                   FROM housing_assignments ha
                   LEFT JOIN housing_rooms hr ON ha.room_id = hr.room_id
                   LEFT JOIN housing_buildings hb ON hr.building_id = hb.building_id
                   WHERE ha.student_id = ?
                   ORDER BY ha.move_in_date DESC""",
                (student_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT ha.*, hr.room_number, hr.room_type, hb.building_name
                   FROM housing_assignments ha
                   LEFT JOIN housing_rooms hr ON ha.room_id = hr.room_id
                   LEFT JOIN housing_buildings hb ON hr.building_id = hb.building_id
                   ORDER BY ha.move_in_date DESC"""
            ).fetchall()

    log_activity("view", "housing_assignments", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})
