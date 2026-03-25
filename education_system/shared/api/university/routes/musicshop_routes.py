"""Music shop routes: products, orders, and wishlists."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

musicshop_bp = Blueprint("musicshop", __name__, url_prefix="/api/musicshop")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- products ----

@musicshop_bp.route("/products", methods=["GET"])
@token_required
def list_products():
    search = request.args.get("search")
    category = request.args.get("category")
    format = request.args.get("format")
    is_active = request.args.get("is_active")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM musicshop_products WHERE title LIKE ? OR artist LIKE ? OR genre LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if format:
            conditions.append("format = ?")
            params.append(format)
        if is_active:
            conditions.append("is_active = ?")
            params.append(is_active)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM musicshop_products" + where + " ORDER BY product_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM musicshop_products" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "musicshop_products", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@musicshop_bp.route("/products/<int:product_id>", methods=["GET"])
@token_required
def get_product(product_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM musicshop_products WHERE product_id = ?", (product_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"products {product_id} not found")
    log_activity("view", "musicshop_products", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@musicshop_bp.route("/products", methods=["POST"])
@token_required
def create_product():
    data = request.get_json(silent=True) or {}
    for field in ["title", "category", "price"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO musicshop_products
               (title, category, price, sku, artist, genre, format, label, release_year, condition, description, cost_price, stock_quantity, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["title"], data["category"], data["price"], data.get("sku", ""), data.get("artist", ""), data.get("genre", ""), data.get("format", ""), data.get("label", ""), data.get("release_year", ""), data.get("condition", ""), data.get("description", ""), data.get("cost_price", ""), data.get("stock_quantity", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM musicshop_products WHERE product_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "musicshop_products", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- orders ----

@musicshop_bp.route("/orders", methods=["GET"])
@token_required
def list_orders():
    search = request.args.get("search")
    customer_id = request.args.get("customer_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM musicshop_orders WHERE customer_name LIKE ? OR order_number LIKE ?",
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
            "SELECT * FROM musicshop_orders" + where + " ORDER BY order_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM musicshop_orders" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "musicshop_orders", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@musicshop_bp.route("/orders/<int:order_id>", methods=["GET"])
@token_required
def get_order(order_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM musicshop_orders WHERE order_id = ?", (order_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"orders {order_id} not found")
    log_activity("view", "musicshop_orders", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@musicshop_bp.route("/orders", methods=["POST"])
@token_required
def create_order():
    data = request.get_json(silent=True) or {}
    for field in ["customer_id", "customer_name", "total_amount"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO musicshop_orders
               (customer_id, customer_name, total_amount, customer_email, customer_phone, shipping_address, payment_method, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["customer_id"], data["customer_name"], data["total_amount"], data.get("customer_email", ""), data.get("customer_phone", ""), data.get("shipping_address", ""), data.get("payment_method", ""), data.get("notes", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM musicshop_orders WHERE order_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "musicshop_orders", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- product updates ----

@musicshop_bp.route("/products/<int:product_id>", methods=["PUT"])
@token_required
def update_product(product_id: int):
    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No update data provided")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    allowed = ["title", "category", "price", "sku", "artist", "genre", "format",
               "label", "release_year", "condition", "description", "cost_price",
               "stock_quantity", "min_stock_level", "is_rare", "is_active", "image_url"]
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
            "UPDATE musicshop_products SET " + ", ".join(sets) + " WHERE product_id = ?",
            params,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM musicshop_products WHERE product_id = ?", (product_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Product {product_id} not found")

    log_activity("update", "musicshop_products", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- order status updates ----

@musicshop_bp.route("/orders/<int:order_id>/status", methods=["PUT"])
@token_required
def update_order_status(order_id: int):
    data = request.get_json(silent=True) or {}
    if "status" not in data:
        raise ValidationError("Missing required field: status")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        cur = conn.execute(
            "UPDATE musicshop_orders SET status = ?, updated_at = ? WHERE order_id = ?",
            (data["status"], now, order_id),
        )
    if cur.rowcount == 0:
        raise ValidationError(f"Order {order_id} not found")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM musicshop_orders WHERE order_id = ?", (order_id,)
        ).fetchone()

    log_activity("update", "musicshop_orders", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- cancel order ----

@musicshop_bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
@token_required
def cancel_order(order_id: int):
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        row = conn.execute(
            "SELECT order_id FROM musicshop_orders WHERE order_id = ?", (order_id,)
        ).fetchone()
        if not row:
            raise ValidationError(f"Order {order_id} not found")

        # Restore stock from order items
        items = conn.execute(
            "SELECT product_id, quantity FROM musicshop_order_items WHERE order_id = ?",
            (order_id,),
        ).fetchall()
        for item in items:
            conn.execute(
                "UPDATE musicshop_products SET stock_quantity = stock_quantity + ? WHERE product_id = ?",
                (item["quantity"], item["product_id"]),
            )

        conn.execute(
            "UPDATE musicshop_orders SET status = 'cancelled', notes = ?, updated_at = ? WHERE order_id = ?",
            (reason, now, order_id),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM musicshop_orders WHERE order_id = ?", (order_id,)
        ).fetchone()

    log_activity("cancel", "musicshop_orders", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- customer orders ----

@musicshop_bp.route("/customers/<customer_id>/orders", methods=["GET"])
@token_required
def get_customer_orders(customer_id: str):
    page, per_page, offset = get_pagination_params()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM musicshop_orders WHERE customer_id = ? ORDER BY order_id DESC LIMIT ? OFFSET ?",
            (customer_id, per_page, offset),
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM musicshop_orders WHERE customer_id = ?", (customer_id,)
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "musicshop_orders", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- low stock ----

@musicshop_bp.route("/products/low-stock", methods=["GET"])
@token_required
def get_low_stock_products():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM musicshop_products WHERE stock_quantity <= min_stock_level AND is_active = 1 ORDER BY stock_quantity ASC"
        ).fetchall()

    log_activity("view", "musicshop_products", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- payments ----

@musicshop_bp.route("/orders/<int:order_id>/payment", methods=["POST"])
@token_required
def record_payment(order_id: int):
    data = request.get_json(silent=True) or {}
    for field in ["amount", "payment_method"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        order_row = conn.execute(
            "SELECT customer_id FROM musicshop_orders WHERE order_id = ?", (order_id,)
        ).fetchone()
        if not order_row:
            raise ValidationError(f"Order {order_id} not found")

        conn.execute(
            """INSERT INTO transactions
               (source_type, reference_id, reference_type, customer_id, transaction_type, amount, payment_method, reference_number, processed_by, created_at)
               VALUES ('music_shop', ?, 'order', ?, 'payment', ?, ?, ?, ?, ?)""",
            (order_id, order_row["customer_id"], data["amount"], data["payment_method"],
             data.get("reference_number", ""), g.current_user.get("sub"), now),
        )
        conn.execute(
            "UPDATE musicshop_orders SET payment_status = 'completed', status = 'confirmed', payment_method = ?, updated_at = ? WHERE order_id = ?",
            (data["payment_method"], now, order_id),
        )
        txn_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_activity("payment", "musicshop_orders", user=g.current_user.get("sub"))
    return jsonify({"transaction_id": txn_id, "order_id": order_id, "status": "completed"}), 201


# ---- refunds ----

@musicshop_bp.route("/orders/<int:order_id>/refund", methods=["POST"])
@token_required
def process_refund(order_id: int):
    data = request.get_json(silent=True) or {}
    if "amount" not in data:
        raise ValidationError("Missing required field: amount")

    reason = data.get("reason", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        order_row = conn.execute(
            "SELECT customer_id, payment_method FROM musicshop_orders WHERE order_id = ?", (order_id,)
        ).fetchone()
        if not order_row:
            raise ValidationError(f"Order {order_id} not found")

        conn.execute(
            """INSERT INTO transactions
               (source_type, reference_id, reference_type, customer_id, transaction_type, amount, payment_method, reference_number, processed_by, created_at)
               VALUES ('music_shop', ?, 'order', ?, 'refund', ?, ?, ?, ?, ?)""",
            (order_id, order_row["customer_id"], -data["amount"],
             order_row["payment_method"] or "", reason, g.current_user.get("sub"), now),
        )
        conn.execute(
            "UPDATE musicshop_orders SET payment_status = 'refunded', status = 'refunded', updated_at = ? WHERE order_id = ?",
            (now, order_id),
        )
        txn_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_activity("refund", "musicshop_orders", user=g.current_user.get("sub"))
    return jsonify({"transaction_id": txn_id, "order_id": order_id, "status": "refunded"}), 201


# ---- statistics / reports ----

@musicshop_bp.route("/reports/sales-summary", methods=["GET"])
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
            FROM musicshop_orders
        """).fetchone()

    log_activity("view", "musicshop_reports", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@musicshop_bp.route("/reports/inventory-summary", methods=["GET"])
@token_required
def get_inventory_summary():
    with get_connection() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) as total_products,
                COALESCE(SUM(stock_quantity), 0) as total_stock,
                COALESCE(SUM(stock_quantity * price), 0) as total_value,
                COALESCE(SUM(CASE WHEN stock_quantity <= min_stock_level THEN 1 ELSE 0 END), 0) as low_stock_count,
                COALESCE(SUM(CASE WHEN is_rare = 1 THEN 1 ELSE 0 END), 0) as rare_items_count
            FROM musicshop_products WHERE is_active = 1
        """).fetchone()

    log_activity("view", "musicshop_reports", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@musicshop_bp.route("/reports/top-products", methods=["GET"])
@token_required
def get_top_products():
    limit = request.args.get("limit", 10, type=int)
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT p.product_id, p.title, p.artist, p.genre,
                   SUM(oi.quantity) as total_sold, SUM(oi.subtotal) as total_revenue
            FROM musicshop_products p
            JOIN musicshop_order_items oi ON p.product_id = oi.product_id
            JOIN musicshop_orders o ON oi.order_id = o.order_id
            WHERE o.status NOT IN ('cancelled','refunded')
            GROUP BY p.product_id
            ORDER BY total_sold DESC
            LIMIT ?
        """, (limit,)).fetchall()

    log_activity("view", "musicshop_reports", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@musicshop_bp.route("/reports/sales-by-genre", methods=["GET"])
@token_required
def get_sales_by_genre():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT p.genre, COUNT(oi.item_id) as items_sold, SUM(oi.subtotal) as revenue
            FROM musicshop_order_items oi
            JOIN musicshop_products p ON oi.product_id = p.product_id
            JOIN musicshop_orders o ON oi.order_id = o.order_id
            WHERE o.status NOT IN ('cancelled','refunded') AND p.genre IS NOT NULL AND p.genre != ''
            GROUP BY p.genre
            ORDER BY revenue DESC
        """).fetchall()

    log_activity("view", "musicshop_reports", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- wishlists ----

@musicshop_bp.route("/wishlists/<customer_id>", methods=["GET"])
@token_required
def get_wishlist(customer_id: str):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT p.* FROM musicshop_products p
            JOIN musicshop_wishlists w ON p.product_id = w.product_id
            WHERE w.customer_id = ?
            ORDER BY w.added_at DESC
        """, (customer_id,)).fetchall()

    log_activity("view", "musicshop_wishlists", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@musicshop_bp.route("/wishlists/<customer_id>", methods=["POST"])
@token_required
def add_to_wishlist(customer_id: str):
    data = request.get_json(silent=True) or {}
    if "product_id" not in data:
        raise ValidationError("Missing required field: product_id")

    with transaction() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO musicshop_wishlists (customer_id, product_id) VALUES (?, ?)",
            (customer_id, data["product_id"]),
        )

    log_activity("create", "musicshop_wishlists", user=g.current_user.get("sub"))
    return jsonify({"customer_id": customer_id, "product_id": data["product_id"], "status": "added"}), 201


@musicshop_bp.route("/wishlists/<customer_id>/<int:product_id>", methods=["DELETE"])
@token_required
def remove_from_wishlist(customer_id: str, product_id: int):
    with transaction() as conn:
        conn.execute(
            "DELETE FROM musicshop_wishlists WHERE customer_id = ? AND product_id = ?",
            (customer_id, product_id),
        )

    log_activity("delete", "musicshop_wishlists", user=g.current_user.get("sub"))
    return jsonify({"customer_id": customer_id, "product_id": product_id, "status": "removed"})
