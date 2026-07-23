"""Car rental routes: vehicles, rentals, and maintenance."""

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

carrental_bp = Blueprint("carrental", __name__, url_prefix="/api/carrental")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- vehicles ----

@carrental_bp.route("/vehicles", methods=["GET"])
@token_required
def list_vehicles():
    search = request.args.get("search")
    category = request.args.get("category")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM carrental_vehicles WHERE make LIKE ? OR model LIKE ? OR registration_number LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM carrental_vehicles" + where + " ORDER BY vehicle_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM carrental_vehicles" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "carrental_vehicles", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@carrental_bp.route("/vehicles/<int:vehicle_id>", methods=["GET"])
@token_required
def get_vehicle(vehicle_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM carrental_vehicles WHERE vehicle_id = ?", (vehicle_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"vehicles {vehicle_id} not found")
    log_activity("view", "carrental_vehicles", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@carrental_bp.route("/vehicles", methods=["POST"])
@token_required
def create_vehicle():
    data = request.get_json(silent=True) or {}
    for field in ["registration_number", "make", "model", "category", "daily_rate"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO carrental_vehicles
               (registration_number, make, model, category, daily_rate, year, color, seats, transmission, fuel_type, mileage, features, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["registration_number"], data["make"], data["model"], data["category"], data["daily_rate"], data.get("year", ""), data.get("color", ""), data.get("seats", ""), data.get("transmission", ""), data.get("fuel_type", ""), data.get("mileage", ""), data.get("features", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM carrental_vehicles WHERE vehicle_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "carrental_vehicles", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- rentals ----

@carrental_bp.route("/rentals", methods=["GET"])
@token_required
def list_rentals():
    search = request.args.get("search")
    customer_id = request.args.get("customer_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM carrental_rentals WHERE customer_name LIKE ? OR rental_number LIKE ?",
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
            "SELECT * FROM carrental_rentals" + where + " ORDER BY rental_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM carrental_rentals" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "carrental_rentals", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@carrental_bp.route("/rentals/<int:rental_id>", methods=["GET"])
@token_required
def get_rental(rental_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM carrental_rentals WHERE rental_id = ?", (rental_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"rentals {rental_id} not found")
    log_activity("view", "carrental_rentals", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@carrental_bp.route("/rentals", methods=["POST"])
@token_required
def create_rental():
    data = request.get_json(silent=True) or {}
    for field in ["vehicle_id", "customer_id", "customer_name", "pickup_date", "return_date"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO carrental_rentals
               (vehicle_id, customer_id, customer_name, pickup_date, return_date, customer_email, customer_phone, license_number, pickup_time, return_time, pickup_location, return_location, daily_rate, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["vehicle_id"], data["customer_id"], data["customer_name"], data["pickup_date"], data["return_date"], data.get("customer_email", ""), data.get("customer_phone", ""), data.get("license_number", ""), data.get("pickup_time", ""), data.get("return_time", ""), data.get("pickup_location", ""), data.get("return_location", ""), data.get("daily_rate", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM carrental_rentals WHERE rental_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "carrental_rentals", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- vehicle updates ----

@carrental_bp.route("/vehicles/<int:vehicle_id>", methods=["PUT"])
@token_required
def update_vehicle(vehicle_id: int):
    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No update data provided")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    allowed = ["registration_number", "make", "model", "year", "category", "color",
               "seats", "transmission", "fuel_type", "daily_rate", "mileage",
               "status", "features", "insurance_info", "image_path"]
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
    params.append(vehicle_id)

    with transaction() as conn:
        conn.execute(
            "UPDATE carrental_vehicles SET " + ", ".join(sets) + " WHERE vehicle_id = ?",
            params,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM carrental_vehicles WHERE vehicle_id = ?", (vehicle_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Vehicle {vehicle_id} not found")

    log_activity("update", "carrental_vehicles", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- rental status updates ----

@carrental_bp.route("/rentals/<int:rental_id>/status", methods=["PUT"])
@token_required
def update_rental_status(rental_id: int):
    data = request.get_json(silent=True) or {}
    if "status" not in data:
        raise ValidationError("Missing required field: status")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        cur = conn.execute(
            "UPDATE carrental_rentals SET status = ?, updated_at = ? WHERE rental_id = ?",
            (data["status"], now, rental_id),
        )
    if cur.rowcount == 0:
        raise ValidationError(f"Rental {rental_id} not found")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM carrental_rentals WHERE rental_id = ?", (rental_id,)
        ).fetchone()

    log_activity("update", "carrental_rentals", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- start rental (pickup) ----

@carrental_bp.route("/rentals/<int:rental_id>/start", methods=["PUT"])
@token_required
def start_rental(rental_id: int):
    data = request.get_json(silent=True) or {}
    for field in ["pickup_mileage", "fuel_level_pickup"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        cur = conn.execute(
            """UPDATE carrental_rentals
               SET status = 'active', pickup_mileage = ?, fuel_level_pickup = ?,
                   condition_notes = ?, updated_at = ?
               WHERE rental_id = ?""",
            (data["pickup_mileage"], data["fuel_level_pickup"],
             data.get("condition_notes", ""), now, rental_id),
        )
    if cur.rowcount == 0:
        raise ValidationError(f"Rental {rental_id} not found")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM carrental_rentals WHERE rental_id = ?", (rental_id,)
        ).fetchone()

    log_activity("start", "carrental_rentals", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- complete rental (return) ----

@carrental_bp.route("/rentals/<int:rental_id>/complete", methods=["PUT"])
@token_required
def complete_rental(rental_id: int):
    data = request.get_json(silent=True) or {}
    for field in ["return_mileage", "fuel_level_return"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    now_date = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M")
    late_fee = data.get("late_fee", 0)
    damage_fee = data.get("damage_fee", 0)
    fuel_fee = data.get("fuel_fee", 0)

    with transaction() as conn:
        rental_row = conn.execute(
            "SELECT vehicle_id, total_amount FROM carrental_rentals WHERE rental_id = ?",
            (rental_id,),
        ).fetchone()
        if not rental_row:
            raise ValidationError(f"Rental {rental_id} not found")

        new_total = (rental_row["total_amount"] or 0) + late_fee + damage_fee + fuel_fee
        conn.execute(
            """UPDATE carrental_rentals
               SET status = 'completed', actual_return_date = ?, actual_return_time = ?,
                   return_mileage = ?, fuel_level_return = ?, late_fee = ?,
                   damage_fee = ?, fuel_fee = ?, total_amount = ?, updated_at = ?
               WHERE rental_id = ?""",
            (now_date, now_time, data["return_mileage"], data["fuel_level_return"],
             late_fee, damage_fee, fuel_fee, new_total, now, rental_id),
        )
        conn.execute(
            "UPDATE carrental_vehicles SET status = 'available', mileage = ?, updated_at = ? WHERE vehicle_id = ?",
            (data["return_mileage"], now, rental_row["vehicle_id"]),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM carrental_rentals WHERE rental_id = ?", (rental_id,)
        ).fetchone()

    log_activity("complete", "carrental_rentals", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- cancel rental ----

@carrental_bp.route("/rentals/<int:rental_id>/cancel", methods=["POST"])
@token_required
def cancel_rental(rental_id: int):
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        rental_row = conn.execute(
            "SELECT vehicle_id FROM carrental_rentals WHERE rental_id = ?", (rental_id,)
        ).fetchone()
        if not rental_row:
            raise ValidationError(f"Rental {rental_id} not found")

        conn.execute(
            "UPDATE carrental_rentals SET status = 'cancelled', condition_notes = ?, updated_at = ? WHERE rental_id = ?",
            (reason, now, rental_id),
        )
        conn.execute(
            "UPDATE carrental_vehicles SET status = 'available', updated_at = ? WHERE vehicle_id = ?",
            (now, rental_row["vehicle_id"]),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM carrental_rentals WHERE rental_id = ?", (rental_id,)
        ).fetchone()

    log_activity("cancel", "carrental_rentals", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- customer rentals ----

@carrental_bp.route("/customers/<customer_id>/rentals", methods=["GET"])
@token_required
def get_customer_rentals(customer_id: str):
    page, per_page, offset = get_pagination_params()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM carrental_rentals WHERE customer_id = ? ORDER BY rental_id DESC LIMIT ? OFFSET ?",
            (customer_id, per_page, offset),
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM carrental_rentals WHERE customer_id = ?", (customer_id,)
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "carrental_rentals", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- vehicle availability ----

@carrental_bp.route("/vehicles/available", methods=["GET"])
@token_required
def get_available_vehicles():
    category = request.args.get("category")
    with get_connection() as conn:
        if category:
            rows = conn.execute(
                "SELECT * FROM carrental_vehicles WHERE status = 'available' AND category = ? ORDER BY make, model",
                (category,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM carrental_vehicles WHERE status = 'available' ORDER BY make, model"
            ).fetchall()

    log_activity("view", "carrental_vehicles", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- payments ----

@carrental_bp.route("/rentals/<int:rental_id>/payment", methods=["POST"])
@token_required
def record_payment(rental_id: int):
    data = request.get_json(silent=True) or {}
    for field in ["amount", "payment_method"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        rental_row = conn.execute(
            "SELECT customer_id FROM carrental_rentals WHERE rental_id = ?", (rental_id,)
        ).fetchone()
        if not rental_row:
            raise ValidationError(f"Rental {rental_id} not found")

        conn.execute(
            """INSERT INTO transactions
               (source_type, reference_id, reference_type, customer_id, transaction_type, amount, payment_method, reference_number, status, processed_by, created_at)
               VALUES ('car_rental', ?, 'rental', ?, 'payment', ?, ?, ?, 'completed', ?, ?)""",
            (rental_id, rental_row["customer_id"], data["amount"], data["payment_method"],
             data.get("reference_number", ""), g.current_user.get("sub"), now),
        )
        conn.execute(
            "UPDATE carrental_rentals SET payment_status = 'paid', payment_method = ?, updated_at = ? WHERE rental_id = ?",
            (data["payment_method"], now, rental_id),
        )
        txn_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_activity("payment", "carrental_rentals", user=g.current_user.get("sub"))
    return jsonify({"transaction_id": txn_id, "rental_id": rental_id, "status": "completed"}), 201


# ---- refunds ----

@carrental_bp.route("/rentals/<int:rental_id>/refund", methods=["POST"])
@token_required
def process_refund(rental_id: int):
    data = request.get_json(silent=True) or {}
    if "amount" not in data:
        raise ValidationError("Missing required field: amount")

    reason = data.get("reason", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        rental_row = conn.execute(
            "SELECT customer_id FROM carrental_rentals WHERE rental_id = ?", (rental_id,)
        ).fetchone()
        if not rental_row:
            raise ValidationError(f"Rental {rental_id} not found")

        conn.execute(
            """INSERT INTO transactions
               (source_type, reference_id, reference_type, customer_id, transaction_type, amount, payment_method, reference_number, status, notes, processed_by, created_at)
               VALUES ('car_rental', ?, 'rental', ?, 'refund', ?, 'refund', ?, 'completed', ?, ?, ?)""",
            (rental_id, rental_row["customer_id"], data["amount"],
             data.get("reference_number", ""), reason, g.current_user.get("sub"), now),
        )
        txn_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_activity("refund", "carrental_rentals", user=g.current_user.get("sub"))
    return jsonify({"transaction_id": txn_id, "rental_id": rental_id, "status": "refunded"}), 201


# ---- statistics / reports ----

@carrental_bp.route("/reports/fleet-summary", methods=["GET"])
@token_required
def get_fleet_summary():
    with get_connection() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) as total_vehicles,
                COALESCE(SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END), 0) as available,
                COALESCE(SUM(CASE WHEN status = 'rented' THEN 1 ELSE 0 END), 0) as rented,
                COALESCE(SUM(CASE WHEN status = 'maintenance' THEN 1 ELSE 0 END), 0) as maintenance
            FROM carrental_vehicles
        """).fetchone()

    log_activity("view", "carrental_reports", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@carrental_bp.route("/reports/revenue", methods=["GET"])
@token_required
def get_revenue_report():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    query = """
        SELECT
            COUNT(*) as total_rentals,
            COALESCE(SUM(total_amount), 0) as total_revenue,
            COALESCE(AVG(total_amount), 0) as avg_rental_value,
            COALESCE(SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END), 0) as completed_rentals
        FROM carrental_rentals
        WHERE payment_status = 'paid'
    """
    params: list = []
    if start_date and end_date:
        query += " AND created_at BETWEEN ? AND ?"
        params.extend([start_date, end_date])

    with get_connection() as conn:
        row = conn.execute(query, params).fetchone()

    log_activity("view", "carrental_reports", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@carrental_bp.route("/reports/popular-vehicles", methods=["GET"])
@token_required
def get_popular_vehicles():
    limit = request.args.get("limit", 10, type=int)
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT v.vehicle_id, v.make, v.model, v.category,
                   COUNT(r.rental_id) as rental_count,
                   COALESCE(SUM(r.total_amount), 0) as total_revenue
            FROM carrental_vehicles v
            LEFT JOIN carrental_rentals r ON v.vehicle_id = r.vehicle_id
            GROUP BY v.vehicle_id
            ORDER BY rental_count DESC
            LIMIT ?
        """, (limit,)).fetchall()

    log_activity("view", "carrental_reports", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- maintenance ----

@carrental_bp.route("/maintenance", methods=["GET"])
@token_required
def list_maintenance():
    vehicle_id = request.args.get("vehicle_id", type=int)
    with get_connection() as conn:
        if vehicle_id:
            rows = conn.execute(
                "SELECT * FROM carrental_maintenance WHERE vehicle_id = ? ORDER BY service_date DESC",
                (vehicle_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM carrental_maintenance ORDER BY service_date DESC"
            ).fetchall()

    log_activity("view", "carrental_maintenance", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@carrental_bp.route("/maintenance", methods=["POST"])
@token_required
def create_maintenance():
    data = request.get_json(silent=True) or {}
    for field in ["vehicle_id", "maintenance_type", "service_date"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO carrental_maintenance
               (vehicle_id, maintenance_type, description, cost, service_date, next_service_date, mileage_at_service, performed_by, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["vehicle_id"], data["maintenance_type"], data.get("description", ""),
             data.get("cost", 0), data["service_date"], data.get("next_service_date", ""),
             data.get("mileage_at_service", ""), data.get("performed_by", ""),
             data.get("notes", ""), now),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM carrental_maintenance WHERE maintenance_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "carrental_maintenance", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
