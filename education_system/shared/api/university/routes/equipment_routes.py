"""Equipment routes: equipment, checkouts, rentals, facility assets, inventory, maintenance."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import admin_required, token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import (
    validate_equipment_checkout_create,
    validate_equipment_maintenance_create,
)
from education_system.post_18.university_system.core.exceptions import ValidationError
from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity

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
            pattern = f"%{escape_like(search)}%"
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


# ---- Checkout Item (start rental) ----

@equipment_bp.route("/rentals/<int:rental_id>/checkout", methods=["POST"])
@token_required
def checkout_item(rental_id: int):
    """Check out equipment — mark a reserved rental as checked_out."""
    data = request.get_json(silent=True) or {}
    condition = data.get("condition_checkout")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM equipment_rentals WHERE rental_id = ?", (rental_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Rental {rental_id} not found")

    with transaction() as conn:
        conn.execute(
            """UPDATE equipment_rentals
               SET status = 'checked_out', condition_checkout = ?, updated_at = CURRENT_TIMESTAMP
               WHERE rental_id = ?""",
            (condition, rental_id),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM equipment_rentals WHERE rental_id = ?", (rental_id,)
        ).fetchone()

    log_activity("checkout", "equipment_rental", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Return Item ----

@equipment_bp.route("/rentals/<int:rental_id>/return", methods=["POST"])
@token_required
def return_item(rental_id: int):
    """Return equipment and update availability."""
    data = request.get_json(silent=True) or {}
    condition_return = data.get("condition_return", "good")
    late_fee = float(data.get("late_fee", 0))
    damage_fee = float(data.get("damage_fee", 0))

    with get_connection() as conn:
        rental = conn.execute(
            "SELECT item_id, quantity, total_amount FROM equipment_rentals WHERE rental_id = ?",
            (rental_id,),
        ).fetchone()
    if not rental:
        raise ValidationError(f"Rental {rental_id} not found")

    rental_dict = _row_to_dict(rental)
    new_total = (rental_dict["total_amount"] or 0) + late_fee + damage_fee

    with transaction() as conn:
        conn.execute(
            """UPDATE equipment_rentals
               SET status = 'returned', actual_return_date = date('now'), actual_return_time = time('now'),
                   condition_return = ?, late_fee = ?, damage_fee = ?,
                   total_amount = ?, updated_at = CURRENT_TIMESTAMP
               WHERE rental_id = ?""",
            (condition_return, late_fee, damage_fee, new_total, rental_id),
        )
        # Restore availability
        conn.execute(
            """UPDATE equipment_items
               SET quantity_available = quantity_available + ?, updated_at = CURRENT_TIMESTAMP
               WHERE item_id = ?""",
            (rental_dict["quantity"], rental_dict["item_id"]),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM equipment_rentals WHERE rental_id = ?", (rental_id,)
        ).fetchone()

    log_activity("return", "equipment_rental", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Cancel Rental ----

@equipment_bp.route("/rentals/<int:rental_id>/cancel", methods=["POST"])
@token_required
def cancel_rental(rental_id: int):
    """Cancel a rental and restore equipment availability."""
    data = request.get_json(silent=True) or {}
    reason = data.get("reason")

    with get_connection() as conn:
        rental = conn.execute(
            "SELECT item_id, quantity FROM equipment_rentals WHERE rental_id = ?",
            (rental_id,),
        ).fetchone()
    if not rental:
        raise ValidationError(f"Rental {rental_id} not found")

    rental_dict = _row_to_dict(rental)

    with transaction() as conn:
        conn.execute(
            """UPDATE equipment_rentals
               SET status = 'cancelled', notes = ?, updated_at = CURRENT_TIMESTAMP
               WHERE rental_id = ?""",
            (reason, rental_id),
        )
        conn.execute(
            """UPDATE equipment_items
               SET quantity_available = quantity_available + ?, updated_at = CURRENT_TIMESTAMP
               WHERE item_id = ?""",
            (rental_dict["quantity"], rental_dict["item_id"]),
        )

    log_activity("cancel", "equipment_rental", user=g.current_user.get("sub"))
    return jsonify({"rental_id": rental_id, "status": "cancelled", "reason": reason})


# ---- Extend Rental ----

@equipment_bp.route("/rentals/<int:rental_id>/extend", methods=["POST"])
@token_required
def extend_rental(rental_id: int):
    """Extend the due date of a rental."""
    data = request.get_json(silent=True) or {}
    for field in ["new_due_date", "new_due_time"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    new_due_date = data["new_due_date"]
    new_due_time = data["new_due_time"]

    with get_connection() as conn:
        rental = conn.execute(
            "SELECT checkout_date, daily_rate, quantity FROM equipment_rentals WHERE rental_id = ?",
            (rental_id,),
        ).fetchone()
    if not rental:
        raise ValidationError(f"Rental {rental_id} not found")

    rental_dict = _row_to_dict(rental)
    # Recalculate totals
    checkout_date = rental_dict["checkout_date"]
    daily_rate = rental_dict["daily_rate"] or 0
    quantity = rental_dict["quantity"] or 1

    # Calculate days between checkout and new due date using julianday
    with transaction() as conn:
        days_row = conn.execute(
            "SELECT MAX(1, CAST(julianday(?) - julianday(?) AS INTEGER)) as total_days",
            (new_due_date, checkout_date),
        ).fetchone()
        total_days = days_row[0] if days_row else 1
        new_subtotal = daily_rate * total_days * quantity

        conn.execute(
            """UPDATE equipment_rentals
               SET due_date = ?, due_time = ?, total_days = ?,
                   subtotal = ?, total_amount = ? + deposit_amount,
                   updated_at = CURRENT_TIMESTAMP
               WHERE rental_id = ?""",
            (new_due_date, new_due_time, total_days, new_subtotal, new_subtotal, rental_id),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM equipment_rentals WHERE rental_id = ?", (rental_id,)
        ).fetchone()

    log_activity("extend", "equipment_rental", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Get Rentals by Status ----

@equipment_bp.route("/rentals/by-status", methods=["GET"])
@token_required
def get_rentals_by_status():
    """Get rentals filtered by status with item details."""
    status = request.args.get("status")

    with get_connection() as conn:
        if status:
            rows = conn.execute(
                """SELECT r.*, e.item_code, e.name as item_name
                   FROM equipment_rentals r
                   JOIN equipment_items e ON r.item_id = e.item_id
                   WHERE r.status = ?
                   ORDER BY r.due_date ASC""",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT r.*, e.item_code, e.name as item_name
                   FROM equipment_rentals r
                   JOIN equipment_items e ON r.item_id = e.item_id
                   ORDER BY r.checkout_date DESC""",
            ).fetchall()

    log_activity("view", "equipment_rentals_by_status", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- Refund Deposit ----

@equipment_bp.route("/rentals/<int:rental_id>/refund-deposit", methods=["POST"])
@token_required
@admin_required
def refund_deposit(rental_id: int):
    """Refund a deposit for a rental."""
    data = request.get_json(silent=True) or {}
    for field in ["borrower_id", "amount"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    borrower_id = data["borrower_id"]
    amount = float(data["amount"])
    processed_by = g.current_user.get("sub")

    import secrets
    from datetime import datetime as _dt
    # Cryptographically random suffix — guessable refs let an attacker
    # cross-reference or replay a refund identifier.
    ref_number = f"EQD-{_dt.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"

    with transaction() as conn:
        conn.execute(
            """INSERT INTO transactions
               (source_type, reference_id, reference_type, customer_id, amount, transaction_type, payment_method,
                reference_number, status, notes, processed_by)
               VALUES ('equipment', ?, 'rental', ?, ?, 'deposit_refund', 'refund', ?, 'completed', 'Deposit refund', ?)""",
            (rental_id, borrower_id, amount, ref_number, processed_by),
        )
        txn_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_activity("refund_deposit", "equipment_rental", user=g.current_user.get("sub"))
    return jsonify({"transaction_id": txn_id, "rental_id": rental_id, "amount": amount, "reference_number": ref_number})


# ---- Inventory Summary ----

@equipment_bp.route("/inventory/summary", methods=["GET"])
@token_required
def inventory_summary():
    """Get inventory summary statistics."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT
                   COUNT(*) as total_items,
                   SUM(quantity_total) as total_quantity,
                   SUM(quantity_available) as available_quantity,
                   SUM(quantity_total - quantity_available) as rented_quantity
               FROM equipment_items WHERE is_active = 1"""
        ).fetchone()

    log_activity("view", "inventory_summary", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Revenue Report ----

@equipment_bp.route("/reports/revenue", methods=["GET"])
@token_required
@admin_required
def revenue_report():
    """Get equipment rental revenue report."""
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    query = """SELECT
                   COUNT(*) as total_rentals,
                   SUM(total_amount) as total_revenue,
                   AVG(total_amount) as avg_rental_value,
                   SUM(late_fee) as total_late_fees,
                   SUM(damage_fee) as total_damage_fees
               FROM equipment_rentals
               WHERE payment_status = 'paid'"""
    params = []

    if start_date and end_date:
        query += " AND created_at BETWEEN ? AND ?"
        params.extend([start_date, end_date])

    with get_connection() as conn:
        row = conn.execute(query, params).fetchone()

    log_activity("view", "revenue_report", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Popular Items ----

@equipment_bp.route("/reports/popular-items", methods=["GET"])
@token_required
def popular_items():
    """Get most popular equipment items by rental count."""
    limit = int(request.args.get("limit", 10))

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT e.item_id, e.name, e.category,
                      COUNT(r.rental_id) as rental_count,
                      SUM(r.total_amount) as total_revenue
               FROM equipment_items e
               LEFT JOIN equipment_rentals r ON e.item_id = r.item_id
               GROUP BY e.item_id
               ORDER BY rental_count DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

    log_activity("view", "popular_items", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- Overdue Rentals ----

@equipment_bp.route("/rentals/overdue", methods=["GET"])
@token_required
def overdue_rentals():
    """Get all overdue rentals (checked_out past due date)."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT r.*, e.name as item_name, e.item_code
               FROM equipment_rentals r
               JOIN equipment_items e ON r.item_id = e.item_id
               WHERE r.status = 'checked_out' AND r.due_date < date('now')
               ORDER BY r.due_date ASC"""
        ).fetchall()

    log_activity("view", "overdue_rentals", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})
