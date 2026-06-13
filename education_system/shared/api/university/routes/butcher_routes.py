"""Butcher shop routes: products, orders, and inventory."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

butcher_bp = Blueprint("butcher", __name__, url_prefix="/api/butcher")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- products ----

@butcher_bp.route("/products", methods=["GET"])
@token_required
def list_products():
    search = request.args.get("search")
    category = request.args.get("category")
    is_available = request.args.get("is_available")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM butcher_products WHERE name LIKE ? OR description LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if is_available:
            conditions.append("is_available = ?")
            params.append(is_available)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM butcher_products" + where + " ORDER BY product_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM butcher_products" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "butcher_products", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@butcher_bp.route("/products/<int:product_id>", methods=["GET"])
@token_required
def get_product(product_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM butcher_products WHERE product_id = ?", (product_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"products {product_id} not found")
    log_activity("view", "butcher_products", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@butcher_bp.route("/products", methods=["POST"])
@token_required
def create_product():
    data = request.get_json(silent=True) or {}
    for field in ["name", "category", "price_per_unit"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO butcher_products
               (name, category, price_per_unit, description, unit_type, stock_quantity, origin, storage_temp, shelf_life_days, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["name"], data["category"], data["price_per_unit"], data.get("description", ""), data.get("unit_type", ""), data.get("stock_quantity", ""), data.get("origin", ""), data.get("storage_temp", ""), data.get("shelf_life_days", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM butcher_products WHERE product_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "butcher_products", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- orders ----

@butcher_bp.route("/orders", methods=["GET"])
@token_required
def list_orders():
    search = request.args.get("search")
    customer_id = request.args.get("customer_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM butcher_orders WHERE customer_name LIKE ? OR order_number LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if customer_id:
            conditions.append("customer_id = ?")
            params.append(customer_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM butcher_orders" + where + " ORDER BY order_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM butcher_orders" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "butcher_orders", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@butcher_bp.route("/orders/<int:order_id>", methods=["GET"])
@token_required
def get_order(order_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM butcher_orders WHERE order_id = ?", (order_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"orders {order_id} not found")
    log_activity("view", "butcher_orders", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@butcher_bp.route("/orders", methods=["POST"])
@token_required
def create_order():
    data = request.get_json(silent=True) or {}
    for field in ["customer_id", "customer_name"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO butcher_orders
               (customer_id, customer_name, customer_email, customer_phone, order_type, special_instructions, pickup_date, pickup_time, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["customer_id"], data["customer_name"], data.get("customer_email", ""), data.get("customer_phone", ""), data.get("order_type", ""), data.get("special_instructions", ""), data.get("pickup_date", ""), data.get("pickup_time", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM butcher_orders WHERE order_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "butcher_orders", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
