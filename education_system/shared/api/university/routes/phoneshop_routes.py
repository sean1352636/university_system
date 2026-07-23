"""Phone shop routes: products, orders, and warranties."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.post_18.university_system.core.exceptions import ValidationError
from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

phoneshop_bp = Blueprint("phoneshop", __name__, url_prefix="/api/phoneshop")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- products ----

@phoneshop_bp.route("/products", methods=["GET"])
@token_required
def list_products():
    search = request.args.get("search")
    category = request.args.get("category")
    is_active = request.args.get("is_active")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM phoneshop_products WHERE name LIKE ? OR brand LIKE ? OR model LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if is_active:
            conditions.append("is_active = ?")
            params.append(is_active)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM phoneshop_products" + where + " ORDER BY product_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM phoneshop_products" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "phoneshop_products", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@phoneshop_bp.route("/products/<int:product_id>", methods=["GET"])
@token_required
def get_product(product_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM phoneshop_products WHERE product_id = ?", (product_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"products {product_id} not found")
    log_activity("view", "phoneshop_products", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@phoneshop_bp.route("/products", methods=["POST"])
@token_required
def create_product():
    data = request.get_json(silent=True) or {}
    for field in ["name", "brand", "model", "category", "price"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO phoneshop_products
               (name, brand, model, category, price, sku, description, cost_price, stock_quantity, specifications, warranty_months, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["name"], data["brand"], data["model"], data["category"], data["price"], data.get("sku", ""), data.get("description", ""), data.get("cost_price", ""), data.get("stock_quantity", ""), data.get("specifications", ""), data.get("warranty_months", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM phoneshop_products WHERE product_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "phoneshop_products", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- orders ----

@phoneshop_bp.route("/orders", methods=["GET"])
@token_required
def list_orders():
    search = request.args.get("search")
    customer_id = request.args.get("customer_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM phoneshop_orders WHERE customer_name LIKE ? OR order_number LIKE ?",
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
            "SELECT * FROM phoneshop_orders" + where + " ORDER BY order_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM phoneshop_orders" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "phoneshop_orders", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@phoneshop_bp.route("/orders/<int:order_id>", methods=["GET"])
@token_required
def get_order(order_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM phoneshop_orders WHERE order_id = ?", (order_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"orders {order_id} not found")
    log_activity("view", "phoneshop_orders", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@phoneshop_bp.route("/orders", methods=["POST"])
@token_required
def create_order():
    data = request.get_json(silent=True) or {}
    for field in ["customer_id", "customer_name", "total_amount"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO phoneshop_orders
               (customer_id, customer_name, total_amount, customer_email, customer_phone, shipping_address, payment_method, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["customer_id"], data["customer_name"], data["total_amount"], data.get("customer_email", ""), data.get("customer_phone", ""), data.get("shipping_address", ""), data.get("payment_method", ""), data.get("notes", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM phoneshop_orders WHERE order_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "phoneshop_orders", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- warranties ----

@phoneshop_bp.route("/warranties", methods=["GET"])
@token_required
def list_warranties():
    search = request.args.get("search")
    customer_id = request.args.get("customer_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM phoneshop_warranties WHERE serial_number LIKE ?",
                (pattern),
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
            "SELECT * FROM phoneshop_warranties" + where + " ORDER BY warranty_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM phoneshop_warranties" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "phoneshop_warranties", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@phoneshop_bp.route("/warranties/<int:warranty_id>", methods=["GET"])
@token_required
def get_warrantie(warranty_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM phoneshop_warranties WHERE warranty_id = ?", (warranty_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"warranties {warranty_id} not found")
    log_activity("view", "phoneshop_warranties", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@phoneshop_bp.route("/warranties", methods=["POST"])
@token_required
def create_warrantie():
    data = request.get_json(silent=True) or {}
    for field in ["order_item_id", "product_id", "customer_id", "start_date", "end_date"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO phoneshop_warranties
               (order_item_id, product_id, customer_id, start_date, end_date, serial_number, warranty_type, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["order_item_id"], data["product_id"], data["customer_id"], data["start_date"], data["end_date"], data.get("serial_number", ""), data.get("warranty_type", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM phoneshop_warranties WHERE warranty_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "phoneshop_warranties", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- product updates ----

@phoneshop_bp.route("/products/<int:product_id>", methods=["PUT"])
@token_required
def update_product(product_id: int):
    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No update data provided")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    allowed = ["name", "brand", "model", "category", "price", "sku", "description",
               "cost_price", "stock_quantity", "min_stock_level", "specifications",
               "warranty_months", "is_active", "image_url"]
    sets = []
    params: list = []
    for key in allowed:
        if key in data:
            sets.append(f"{key} = ?")
            params.append(data[key])
    if not sets:
        raise ValidationError("No valid fields to update")

    sets.append("updated_at = ?")
    params.append(now)
    params.append(product_id)

    with transaction() as conn:
        conn.execute(
            "UPDATE phoneshop_products SET " + ", ".join(sets) + " WHERE product_id = ?",
            params,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM phoneshop_products WHERE product_id = ?", (product_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Product {product_id} not found")

    log_activity("update", "phoneshop_products", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- order status updates ----

@phoneshop_bp.route("/orders/<int:order_id>/status", methods=["PUT"])
@token_required
def update_order_status(order_id: int):
    data = request.get_json(silent=True) or {}
    if "status" not in data:
        raise ValidationError("Missing required field: status")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        cur = conn.execute(
            "UPDATE phoneshop_orders SET status = ?, updated_at = ? WHERE order_id = ?",
            (data["status"], now, order_id),
        )
    if cur.rowcount == 0:
        raise ValidationError(f"Order {order_id} not found")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM phoneshop_orders WHERE order_id = ?", (order_id,)
        ).fetchone()

    log_activity("update", "phoneshop_orders", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- cancel order ----

@phoneshop_bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
@token_required
def cancel_order(order_id: int):
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        row = conn.execute(
            "SELECT order_id FROM phoneshop_orders WHERE order_id = ?", (order_id,)
        ).fetchone()
        if not row:
            raise ValidationError(f"Order {order_id} not found")

        # Restore stock from order items
        items = conn.execute(
            "SELECT product_id, quantity FROM phoneshop_order_items WHERE order_id = ?",
            (order_id,),
        ).fetchall()
        for item in items:
            conn.execute(
                "UPDATE phoneshop_products SET stock_quantity = stock_quantity + ? WHERE product_id = ?",
                (item["quantity"], item["product_id"]),
            )

        conn.execute(
            "UPDATE phoneshop_orders SET status = 'cancelled', notes = ?, updated_at = ? WHERE order_id = ?",
            (reason, now, order_id),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM phoneshop_orders WHERE order_id = ?", (order_id,)
        ).fetchone()

    log_activity("cancel", "phoneshop_orders", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- customer orders ----

@phoneshop_bp.route("/customers/<customer_id>/orders", methods=["GET"])
@token_required
def get_customer_orders(customer_id: str):
    page, per_page, offset = get_pagination_params()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM phoneshop_orders WHERE customer_id = ? ORDER BY order_id DESC LIMIT ? OFFSET ?",
            (customer_id, per_page, offset),
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM phoneshop_orders WHERE customer_id = ?", (customer_id,)
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "phoneshop_orders", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- low stock ----

@phoneshop_bp.route("/products/low-stock", methods=["GET"])
@token_required
def get_low_stock_products():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM phoneshop_products WHERE stock_quantity <= min_stock_level AND is_active = 1 ORDER BY stock_quantity ASC"
        ).fetchall()

    log_activity("view", "phoneshop_products", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- payments ----

@phoneshop_bp.route("/orders/<int:order_id>/payment", methods=["POST"])
@token_required
def record_payment(order_id: int):
    data = request.get_json(silent=True) or {}
    for field in ["amount", "payment_method"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        order_row = conn.execute(
            "SELECT customer_id FROM phoneshop_orders WHERE order_id = ?", (order_id,)
        ).fetchone()
        if not order_row:
            raise ValidationError(f"Order {order_id} not found")

        conn.execute(
            """INSERT INTO transactions
               (source_type, reference_id, reference_type, customer_id, transaction_type, amount, payment_method, reference_number, processed_by, created_at)
               VALUES ('phone_shop', ?, 'order', ?, 'payment', ?, ?, ?, ?, ?)""",
            (order_id, order_row["customer_id"], data["amount"], data["payment_method"],
             data.get("reference_number", ""), g.current_user.get("sub"), now),
        )
        conn.execute(
            "UPDATE phoneshop_orders SET payment_status = 'completed', status = 'confirmed', payment_method = ?, updated_at = ? WHERE order_id = ?",
            (data["payment_method"], now, order_id),
        )
        txn_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_activity("payment", "phoneshop_orders", user=g.current_user.get("sub"))
    return jsonify({"transaction_id": txn_id, "order_id": order_id, "status": "completed"}), 201


# ---- refunds ----

@phoneshop_bp.route("/orders/<int:order_id>/refund", methods=["POST"])
@token_required
def process_refund(order_id: int):
    data = request.get_json(silent=True) or {}
    if "amount" not in data:
        raise ValidationError("Missing required field: amount")

    reason = data.get("reason", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        order_row = conn.execute(
            "SELECT customer_id, payment_method FROM phoneshop_orders WHERE order_id = ?", (order_id,)
        ).fetchone()
        if not order_row:
            raise ValidationError(f"Order {order_id} not found")

        conn.execute(
            """INSERT INTO transactions
               (source_type, reference_id, reference_type, customer_id, transaction_type, amount, payment_method, reference_number, processed_by, created_at)
               VALUES ('phone_shop', ?, 'order', ?, 'refund', ?, ?, ?, ?, ?)""",
            (order_id, order_row["customer_id"], -data["amount"],
             order_row["payment_method"] or "", reason, g.current_user.get("sub"), now),
        )
        conn.execute(
            "UPDATE phoneshop_orders SET payment_status = 'refunded', status = 'refunded', updated_at = ? WHERE order_id = ?",
            (now, order_id),
        )
        txn_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_activity("refund", "phoneshop_orders", user=g.current_user.get("sub"))
    return jsonify({"transaction_id": txn_id, "order_id": order_id, "status": "refunded"}), 201


# ---- statistics / reports ----

@phoneshop_bp.route("/reports/sales-summary", methods=["GET"])
@token_required
def get_sales_summary():
    with get_connection() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) as total_orders,
                COALESCE(SUM(CASE WHEN status NOT IN ('cancelled','refunded') THEN total_amount ELSE 0 END), 0) as total_revenue,
                COALESCE(AVG(CASE WHEN status NOT IN ('cancelled','refunded') THEN total_amount ELSE NULL END), 0) as avg_order_value,
                COALESCE(SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END), 0) as pending_orders,
                COALESCE(SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END), 0) as completed_orders
            FROM phoneshop_orders
        """).fetchone()

    log_activity("view", "phoneshop_reports", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@phoneshop_bp.route("/reports/inventory-summary", methods=["GET"])
@token_required
def get_inventory_summary():
    with get_connection() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) as total_products,
                COALESCE(SUM(stock_quantity), 0) as total_stock,
                COALESCE(SUM(stock_quantity * price), 0) as total_value,
                COALESCE(SUM(CASE WHEN stock_quantity <= min_stock_level THEN 1 ELSE 0 END), 0) as low_stock_count
            FROM phoneshop_products WHERE is_active = 1
        """).fetchone()

    log_activity("view", "phoneshop_reports", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@phoneshop_bp.route("/reports/top-products", methods=["GET"])
@token_required
def get_top_products():
    limit = request.args.get("limit", 10, type=int)
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT p.product_id, p.name, p.brand, p.model,
                   SUM(oi.quantity) as total_sold, SUM(oi.subtotal) as total_revenue
            FROM phoneshop_products p
            JOIN phoneshop_order_items oi ON p.product_id = oi.product_id
            JOIN phoneshop_orders o ON oi.order_id = o.order_id
            WHERE o.status NOT IN ('cancelled','refunded')
            GROUP BY p.product_id
            ORDER BY total_sold DESC
            LIMIT ?
        """, (limit,)).fetchall()

    log_activity("view", "phoneshop_reports", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})
