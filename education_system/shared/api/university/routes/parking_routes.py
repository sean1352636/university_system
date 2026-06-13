"""Parking routes: permits, spaces, and vehicles."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import validate_parking_permit_create, validate_vehicle_create
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

parking_bp = Blueprint("parking", __name__, url_prefix="/api/parking")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Permits ----

@parking_bp.route("/permits", methods=["GET"])
@token_required
def list_permits():
    user_id = request.args.get("user_id")
    zone = request.args.get("zone")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if zone:
            conditions.append("zone = ?")
            params.append(zone)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM parking_permits" + where + " ORDER BY start_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM parking_permits" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "parking_permits", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@parking_bp.route("/permits/<permit_id>", methods=["GET"])
@token_required
def get_permit(permit_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM parking_permits WHERE permit_id = ?", (permit_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Permit {permit_id} not found")
    log_activity("view", "parking_permit", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@parking_bp.route("/permits", methods=["POST"])
@token_required
def create_permit():
    data = request.get_json(silent=True) or {}
    validate_parking_permit_create(data)

    permit_id = str(uuid.uuid4())
    now = datetime.now().strftime("%Y-%m-%d")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO parking_permits
               (permit_id, user_id, full_name, email, zone, permit_type,
                start_date, end_date, active_status, vehicle_id, issue_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)""",
            (
                permit_id,
                data["user_id"],
                data.get("full_name", ""),
                data.get("email", ""),
                data["zone"],
                data["permit_type"],
                data["start_date"],
                data["end_date"],
                data.get("vehicle_id"),
                now,
            ),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM parking_permits WHERE permit_id = ?", (permit_id,)
        ).fetchone()

    log_activity("create", "parking_permit", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Spaces ----

@parking_bp.route("/spaces", methods=["GET"])
@token_required
def list_spaces():
    lot_id = request.args.get("lot_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if lot_id:
            conditions.append("lot_id = ?")
            params.append(lot_id)
        if status:
            conditions.append("occupancy_status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            "SELECT * FROM parking_spaces" + where + " ORDER BY space_number", params
        ).fetchall()

    log_activity("view", "parking_spaces", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- Vehicles ----

@parking_bp.route("/vehicles", methods=["GET"])
@token_required
def list_vehicles():
    owner_id = request.args.get("owner_id")

    with get_connection() as conn:
        if owner_id:
            rows = conn.execute(
                "SELECT * FROM vehicles WHERE owner_id = ?", (owner_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM vehicles ORDER BY license_plate").fetchall()

    log_activity("view", "vehicles", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@parking_bp.route("/vehicles", methods=["POST"])
@token_required
def create_vehicle():
    data = request.get_json(silent=True) or {}
    validate_vehicle_create(data)

    vehicle_id = str(uuid.uuid4())
    with transaction() as conn:
        conn.execute(
            """INSERT INTO vehicles
               (vehicle_id, license_plate, make, model, year, color,
                vehicle_type, owner_id, registration_state)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                vehicle_id,
                data["license_plate"],
                data.get("make", ""),
                data.get("model", ""),
                data.get("year"),
                data.get("color", ""),
                data.get("vehicle_type", ""),
                data["owner_id"],
                data.get("registration_state", ""),
            ),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM vehicles WHERE vehicle_id = ?", (vehicle_id,)
        ).fetchone()

    log_activity("create", "vehicle", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
