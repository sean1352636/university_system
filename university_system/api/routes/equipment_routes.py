"""Equipment routes: equipment, checkouts, rentals, facility assets, inventory, maintenance."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from university_system.api.auth import admin_required, token_required
from university_system.api.pagination import get_pagination_params, paginated_response
from university_system.api.validators import (
    validate_equipment_checkout_create,
    validate_equipment_maintenance_create,
)
from university_system.core.exceptions import ValidationError
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

equipment_bp = Blueprint("equipment", __name__, url_prefix="/api/equipment")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Equipment ----

@equipment_bp.route("", methods=["GET"])
@token_required
def list_equipment():
    equipment_type = request.args.get("equipment_type")
    status = request.args.get("status")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{search}%"
            rows = conn.execute(
                "SELECT * FROM equipment WHERE name LIKE ? OR brand LIKE ? OR model LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if equipment_type:
            conditions.append("equipment_type = ?")
            params.append(equipment_type)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM equipment" + where + " ORDER BY name LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM equipment" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "equipment", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@equipment_bp.route("/<int:equipment_id>", methods=["GET"])
@token_required
def get_equipment(equipment_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM equipment WHERE id = ?", (equipment_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Equipment {equipment_id} not found")
    log_activity("view", "equipment_item", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Checkouts ----

@equipment_bp.route("/checkouts", methods=["GET"])
@token_required
def list_checkouts():
    borrower_id = request.args.get("borrower_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if borrower_id:
            conditions.append("borrower_id = ?")
            params.append(borrower_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM equipment_checkouts" + where + " ORDER BY checkout_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM equipment_checkouts" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "equipment_checkouts", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@equipment_bp.route("/checkouts", methods=["POST"])
@token_required
def create_checkout():
    data = request.get_json(silent=True) or {}
    validate_equipment_checkout_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO equipment_checkouts
               (equipment_id, borrower_id, club_id, checkout_date,
                expected_return, condition_out, notes, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'checked_out')""",
            (
                data["equipment_id"],
                data["borrower_id"],
                data.get("club_id"),
                data["checkout_date"],
                data["expected_return"],
                data.get("condition_out"),
                data.get("notes", ""),
            ),
        )
        cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM equipment_checkouts WHERE checkout_id = ?", (cid,)
        ).fetchone()

    log_activity("create", "equipment_checkout", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Rentals ----

@equipment_bp.route("/rentals", methods=["GET"])
@token_required
def list_rentals():
    status = request.args.get("status")
    borrower_id = request.args.get("borrower_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if borrower_id:
            conditions.append("borrower_id = ?")
            params.append(borrower_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM equipment_rentals" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM equipment_rentals" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "equipment_rentals", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- Facility Assets ----

@equipment_bp.route("/assets", methods=["GET"])
@token_required
def list_facility_assets():
    building_id = request.args.get("building_id")
    asset_type = request.args.get("asset_type")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if building_id:
            conditions.append("building_id = ?")
            params.append(building_id)
        if asset_type:
            conditions.append("asset_type = ?")
            params.append(asset_type)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM facility_assets" + where + " ORDER BY asset_name LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM facility_assets" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "facility_assets", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- Inventory ----

@equipment_bp.route("/inventory", methods=["GET"])
@token_required
def list_inventory():
    with get_connection() as conn:
        page, per_page, offset = get_pagination_params()
        rows = conn.execute(
            "SELECT * FROM inventory ORDER BY item_name LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
        total_row = conn.execute("SELECT COUNT(*) FROM inventory").fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "inventory", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- Maintenance ----

@equipment_bp.route("/maintenance", methods=["GET"])
@token_required
def list_maintenance():
    item_id = request.args.get("item_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if item_id:
            conditions.append("item_id = ?")
            params.append(item_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM equipment_maintenance" + where + " ORDER BY performed_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM equipment_maintenance" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "equipment_maintenance", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@equipment_bp.route("/maintenance", methods=["POST"])
@token_required
@admin_required
def create_maintenance():
    data = request.get_json(silent=True) or {}
    validate_equipment_maintenance_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO equipment_maintenance
               (item_id, maintenance_type, description, cost,
                performed_date, next_maintenance_date, performed_by, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["item_id"],
                data["maintenance_type"],
                data.get("description", ""),
                data.get("cost", 0),
                data["performed_date"],
                data.get("next_maintenance_date"),
                data.get("performed_by"),
                data.get("notes", ""),
            ),
        )
        mid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM equipment_maintenance WHERE maintenance_id = ?", (mid,)
        ).fetchone()

    log_activity("create", "equipment_maintenance", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
