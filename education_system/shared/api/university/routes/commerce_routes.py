"""Commerce routes: menu items, restaurant orders, inventory, and staff schedules."""

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

commerce_bp = Blueprint("commerce", __name__, url_prefix="/api/commerce")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- menu ----

@commerce_bp.route("/menu", methods=["GET"])
@token_required
def list_menu():
    search = request.args.get("search")
    category = request.args.get("category")
    available = request.args.get("available")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM menu_items WHERE name LIKE ? OR description LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if available:
            conditions.append("available = ?")
            params.append(available)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM menu_items" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM menu_items" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "menu_items", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@commerce_bp.route("/menu/<int:id>", methods=["GET"])
@token_required
def get_menu(id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM menu_items WHERE id = ?", (id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"menu {id} not found")
    log_activity("view", "menu_items", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@commerce_bp.route("/menu", methods=["POST"])
@token_required
def create_menu():
    data = request.get_json(silent=True) or {}
    for field in ["name", "price", "category"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO menu_items
               (name, price, category, description, ingredients, allergens, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["name"], data["price"], data["category"], data.get("description", ""), data.get("ingredients", ""), data.get("allergens", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM menu_items WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "menu_items", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- orders ----

@commerce_bp.route("/orders", methods=["GET"])
@token_required
def list_orders():
    customer_id = request.args.get("customer_id")
    status = request.args.get("status")

    with get_connection() as conn:
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
            "SELECT * FROM restaurant_orders" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM restaurant_orders" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "restaurant_orders", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@commerce_bp.route("/orders/<int:id>", methods=["GET"])
@token_required
def get_order(id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM restaurant_orders WHERE id = ?", (id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"orders {id} not found")
    log_activity("view", "restaurant_orders", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@commerce_bp.route("/orders", methods=["POST"])
@token_required
def create_order():
    data = request.get_json(silent=True) or {}
    for field in ["customer_id", "items", "total_amount"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO restaurant_orders
               (customer_id, items, total_amount, delivery_address, special_instructions, payment_method, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["customer_id"], data["items"], data["total_amount"], data.get("delivery_address", ""), data.get("special_instructions", ""), data.get("payment_method", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM restaurant_orders WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "restaurant_orders", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
