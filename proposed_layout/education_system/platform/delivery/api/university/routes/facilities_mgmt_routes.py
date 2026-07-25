"""Facilities management routes: work orders, inspections, and space management."""

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

facilities_mgmt_bp = Blueprint("facilities_mgmt", __name__, url_prefix="/api/facilities")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- work-orders ----

@facilities_mgmt_bp.route("/work-orders", methods=["GET"])
@token_required
def list_work_orders():
    search = request.args.get("search")
    status = request.args.get("status")
    priority = request.args.get("priority")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM facility_work_orders WHERE description LIKE ? OR location LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
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
            "SELECT * FROM facility_work_orders" + where + " ORDER BY order_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM facility_work_orders" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "facility_work_orders", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@facilities_mgmt_bp.route("/work-orders/<int:order_id>", methods=["GET"])
@token_required
def get_work_order(order_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM facility_work_orders WHERE order_id = ?", (order_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"work-orders {order_id} not found")
    log_activity("view", "facility_work_orders", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@facilities_mgmt_bp.route("/work-orders", methods=["POST"])
@token_required
def create_work_order():
    data = request.get_json(silent=True) or {}
    for field in ["location", "description", "priority"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO facility_work_orders
               (location, description, priority, requested_by, assigned_to, category, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["location"], data["description"], data["priority"], data.get("requested_by", ""), data.get("assigned_to", ""), data.get("category", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM facility_work_orders WHERE order_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "facility_work_orders", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- inspections ----

@facilities_mgmt_bp.route("/inspections", methods=["GET"])
@token_required
def list_inspections():
    search = request.args.get("search")
    status = request.args.get("status")
    inspector_id = request.args.get("inspector_id")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM facility_inspections WHERE location LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if inspector_id:
            conditions.append("inspector_id = ?")
            params.append(inspector_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM facility_inspections" + where + " ORDER BY inspection_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM facility_inspections" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "facility_inspections", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@facilities_mgmt_bp.route("/inspections/<int:inspection_id>", methods=["GET"])
@token_required
def get_inspection(inspection_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM facility_inspections WHERE inspection_id = ?", (inspection_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"inspections {inspection_id} not found")
    log_activity("view", "facility_inspections", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@facilities_mgmt_bp.route("/inspections", methods=["POST"])
@token_required
def create_inspection():
    data = request.get_json(silent=True) or {}
    for field in ["location", "inspector_id", "inspection_date"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO facility_inspections
               (location, inspector_id, inspection_date, notes, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["location"], data["inspector_id"], data["inspection_date"], data.get("notes", ""), data.get("status", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM facility_inspections WHERE inspection_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "facility_inspections", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
