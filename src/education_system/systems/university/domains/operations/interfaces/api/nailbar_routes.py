"""Nail bar routes: treatments, technicians, appointments, and preferences."""

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

nailbar_bp = Blueprint("nailbar", __name__, url_prefix="/api/nailbar")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- treatments ----

@nailbar_bp.route("/treatments", methods=["GET"])
@token_required
def list_treatments():
    search = request.args.get("search")
    category = request.args.get("category")
    is_available = request.args.get("is_available")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM nailbar_treatments WHERE name LIKE ? OR description LIKE ?",
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
            "SELECT * FROM nailbar_treatments" + where + " ORDER BY treatment_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM nailbar_treatments" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "nailbar_treatments", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@nailbar_bp.route("/treatments/<int:treatment_id>", methods=["GET"])
@token_required
def get_treatment(treatment_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM nailbar_treatments WHERE treatment_id = ?", (treatment_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"treatments {treatment_id} not found")
    log_activity("view", "nailbar_treatments", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@nailbar_bp.route("/treatments", methods=["POST"])
@token_required
def create_treatment():
    data = request.get_json(silent=True) or {}
    for field in ["name", "category", "duration_minutes", "price"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO nailbar_treatments
               (name, category, duration_minutes, price, description, is_available, requires_appointment, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["name"], data["category"], data["duration_minutes"], data["price"], data.get("description", ""), data.get("is_available", ""), data.get("requires_appointment", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM nailbar_treatments WHERE treatment_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "nailbar_treatments", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- appointments ----

@nailbar_bp.route("/appointments", methods=["GET"])
@token_required
def list_appointments():
    search = request.args.get("search")
    customer_id = request.args.get("customer_id")
    technician_id = request.args.get("technician_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM nailbar_appointments WHERE customer_name LIKE ? OR booking_reference LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if customer_id:
            conditions.append("customer_id = ?")
            params.append(customer_id)
        if technician_id:
            conditions.append("technician_id = ?")
            params.append(technician_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM nailbar_appointments" + where + " ORDER BY appointment_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM nailbar_appointments" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "nailbar_appointments", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@nailbar_bp.route("/appointments/<int:appointment_id>", methods=["GET"])
@token_required
def get_appointment(appointment_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM nailbar_appointments WHERE appointment_id = ?", (appointment_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"appointments {appointment_id} not found")
    log_activity("view", "nailbar_appointments", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@nailbar_bp.route("/appointments", methods=["POST"])
@token_required
def create_appointment():
    data = request.get_json(silent=True) or {}
    for field in ["customer_id", "customer_name", "appointment_date", "appointment_time"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO nailbar_appointments
               (customer_id, customer_name, appointment_date, appointment_time, customer_email, customer_phone, technician_id, technician_name, special_requests, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["customer_id"], data["customer_name"], data["appointment_date"], data["appointment_time"], data.get("customer_email", ""), data.get("customer_phone", ""), data.get("technician_id", ""), data.get("technician_name", ""), data.get("special_requests", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM nailbar_appointments WHERE appointment_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "nailbar_appointments", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- technicians ----

@nailbar_bp.route("/technicians", methods=["GET"])
@token_required
def list_technicians():
    search = request.args.get("search")
    is_active = request.args.get("is_active")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM nailbar_technicians WHERE name LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if is_active:
            conditions.append("is_active = ?")
            params.append(is_active)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM nailbar_technicians" + where + " ORDER BY technician_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM nailbar_technicians" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "nailbar_technicians", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@nailbar_bp.route("/technicians/<int:technician_id>", methods=["GET"])
@token_required
def get_technician(technician_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM nailbar_technicians WHERE technician_id = ?", (technician_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"technicians {technician_id} not found")
    log_activity("view", "nailbar_technicians", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@nailbar_bp.route("/technicians", methods=["POST"])
@token_required
def create_technician():
    data = request.get_json(silent=True) or {}
    for field in ["name", "employee_id"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO nailbar_technicians
               (name, employee_id, specialties, phone, email, certification, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["name"], data["employee_id"], data.get("specialties", ""), data.get("phone", ""), data.get("email", ""), data.get("certification", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM nailbar_technicians WHERE technician_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "nailbar_technicians", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- update treatment ----

@nailbar_bp.route("/treatments/<int:treatment_id>", methods=["PUT"])
@token_required
def update_treatment(treatment_id: int):
    data = request.get_json(silent=True) or {}
    set_parts: list[str] = []
    params: list = []
    for col in (
        "category", "description", "duration_minutes", "is_available",
        "name", "price",
    ):
        if col in data:
            set_parts.append(f"{col} = ?")
            params.append(data[col])
    if not set_parts:
        raise ValidationError("No valid fields to update")

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM nailbar_treatments WHERE treatment_id = ?", (treatment_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Treatment {treatment_id} not found")

    set_clause = ", ".join(set_parts)
    params.append(treatment_id)

    with transaction() as conn:
        conn.execute(
            f"UPDATE nailbar_treatments SET {set_clause} WHERE treatment_id = ?",
            params,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM nailbar_treatments WHERE treatment_id = ?", (treatment_id,)
        ).fetchone()

    log_activity("update", "nailbar_treatments", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- update appointment status ----

@nailbar_bp.route("/appointments/<int:appointment_id>/status", methods=["PUT"])
@token_required
def update_appointment_status(appointment_id: int):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    valid_statuses = ["booked", "confirmed", "checked_in", "in_progress", "completed", "cancelled", "no_show"]
    if status not in valid_statuses:
        raise ValidationError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM nailbar_appointments WHERE appointment_id = ?", (appointment_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Appointment {appointment_id} not found")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    notes = data.get("notes")

    with transaction() as conn:
        if notes:
            conn.execute(
                "UPDATE nailbar_appointments SET status = ?, notes = ?, updated_at = ? WHERE appointment_id = ?",
                (status, notes, now, appointment_id),
            )
        else:
            conn.execute(
                "UPDATE nailbar_appointments SET status = ?, updated_at = ? WHERE appointment_id = ?",
                (status, now, appointment_id),
            )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM nailbar_appointments WHERE appointment_id = ?", (appointment_id,)
        ).fetchone()

    log_activity("update", "nailbar_appointments", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- today's appointments ----

@nailbar_bp.route("/appointments/today", methods=["GET"])
@token_required
def get_todays_appointments():
    today = datetime.now().strftime("%Y-%m-%d")
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM nailbar_appointments WHERE appointment_date = ? ORDER BY appointment_time",
            (today,),
        ).fetchall()

    log_activity("view", "nailbar_appointments", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows), "date": today})


# ---- technician availability ----

@nailbar_bp.route("/technicians/<int:technician_id>/availability", methods=["GET"])
@token_required
def get_technician_availability(technician_id: int):
    date = request.args.get("date")
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    with get_connection() as conn:
        tech = conn.execute(
            "SELECT * FROM nailbar_technicians WHERE technician_id = ?", (technician_id,)
        ).fetchone()
    if not tech:
        raise ValidationError(f"Technician {technician_id} not found")

    time_slots = [
        "09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
        "12:00", "12:30", "13:00", "13:30", "14:00", "14:30",
        "15:00", "15:30", "16:00", "16:30", "17:00", "17:30", "18:00",
    ]

    with get_connection() as conn:
        booked = conn.execute(
            """SELECT appointment_time FROM nailbar_appointments
               WHERE technician_id = ? AND appointment_date = ?
               AND status NOT IN ('cancelled', 'no_show')""",
            (technician_id, date),
        ).fetchall()

    booked_times = {row["appointment_time"] for row in booked}
    available = [slot for slot in time_slots if slot not in booked_times]

    log_activity("view", "nailbar_technicians", user=g.current_user.get("sub"))
    return jsonify({
        "technician_id": technician_id,
        "technician_name": _row_to_dict(tech).get("name"),
        "date": date,
        "available_slots": available,
        "booked_slots": list(booked_times),
    })


# ---- appointments by date ----

@nailbar_bp.route("/appointments/by-date", methods=["GET"])
@token_required
def get_appointments_by_date():
    date = request.args.get("date")
    if not date:
        raise ValidationError("Missing required query parameter: date")

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM nailbar_appointments WHERE appointment_date = ? ORDER BY appointment_time",
            (date,),
        ).fetchall()

    log_activity("view", "nailbar_appointments", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows), "date": date})


# ---- customer appointments ----

@nailbar_bp.route("/customers/<customer_id>/appointments", methods=["GET"])
@token_required
def get_customer_appointments(customer_id: str):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM nailbar_appointments WHERE customer_id = ? ORDER BY appointment_date DESC, appointment_time DESC",
            (customer_id,),
        ).fetchall()

    log_activity("view", "nailbar_appointments", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows), "customer_id": customer_id})


# ---- process payment ----

@nailbar_bp.route("/payments", methods=["POST"])
@token_required
def process_payment():
    data = request.get_json(silent=True) or {}
    for field in ["appointment_id", "amount", "payment_method", "customer_id"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    appointment_id = data["appointment_id"]
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM nailbar_appointments WHERE appointment_id = ?", (appointment_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Appointment {appointment_id} not found")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    amount = data["amount"]
    payment_method = data["payment_method"]
    customer_id = data["customer_id"]
    tip_amount = data.get("tip_amount", 0)
    reference_number = data.get("reference_number")
    processed_by = g.current_user.get("sub")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO transactions
               (source_type, reference_id, reference_type, customer_id, amount, payment_method,
                tip_amount, reference_number, processed_by)
               VALUES ('nail_bar', ?, 'appointment', ?, ?, ?, ?, ?, ?)""",
            (appointment_id, customer_id, amount, payment_method, tip_amount,
             reference_number, processed_by),
        )
        transaction_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute(
            "UPDATE nailbar_appointments SET payment_status = 'paid', payment_method = ?, updated_at = ? WHERE appointment_id = ?",
            (payment_method, now, appointment_id),
        )

        # Update customer loyalty
        try:
            loyalty_points = int(amount)
            today = datetime.now().strftime("%Y-%m-%d")
            conn.execute(
                """INSERT INTO nailbar_customer_preferences (customer_id, visit_count, loyalty_points, last_visit)
                   VALUES (?, 1, ?, ?)
                   ON CONFLICT(customer_id) DO UPDATE SET
                       visit_count = visit_count + 1,
                       loyalty_points = loyalty_points + ?,
                       last_visit = ?""",
                (customer_id, loyalty_points, today, loyalty_points, today),
            )
        except Exception:
            pass

    log_activity("create", "nailbar_payment", user=g.current_user.get("sub"))
    return jsonify({"transaction_id": transaction_id, "appointment_id": appointment_id, "status": "paid"}), 201


# ---- daily revenue ----

@nailbar_bp.route("/revenue/daily", methods=["GET"])
@token_required
def get_daily_revenue():
    date = request.args.get("date")
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    with get_connection() as conn:
        row = conn.execute(
            """SELECT
                   COUNT(*) as transaction_count,
                   SUM(amount) as service_revenue,
                   SUM(tip_amount) as tips,
                   SUM(amount + tip_amount) as total_revenue
               FROM transactions
               WHERE source_type = 'nail_bar' AND DATE(created_at) = ? AND status = 'completed'""",
            (date,),
        ).fetchone()

    result = {
        "date": date,
        "transaction_count": row["transaction_count"] or 0 if row else 0,
        "service_revenue": row["service_revenue"] or 0 if row else 0,
        "tips": row["tips"] or 0 if row else 0,
        "total_revenue": row["total_revenue"] or 0 if row else 0,
    }

    log_activity("view", "nailbar_revenue", user=g.current_user.get("sub"))
    return jsonify(result)


# ---- statistics / dashboard ----

@nailbar_bp.route("/statistics", methods=["GET"])
@token_required
def get_statistics():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    today = datetime.now().strftime("%Y-%m-%d")

    if not start_date:
        start_date = today
    if not end_date:
        end_date = today

    with get_connection() as conn:
        # Summary from transactions
        summary_row = conn.execute(
            """SELECT
                   COUNT(*) as total_appointments,
                   SUM(amount) as service_revenue,
                   SUM(tip_amount) as total_tips,
                   AVG(amount) as avg_service_value
               FROM transactions
               WHERE source_type = 'nail_bar' AND DATE(created_at) BETWEEN ? AND ? AND status = 'completed'""",
            (start_date, end_date),
        ).fetchone()

        # Breakdown by treatment
        treatment_rows = conn.execute(
            """SELECT
                   at.treatment_name,
                   COUNT(*) as count,
                   SUM(at.price) as revenue
               FROM nailbar_appointment_treatments at
               JOIN nailbar_appointments a ON at.appointment_id = a.appointment_id
               WHERE DATE(a.created_at) BETWEEN ? AND ?
                   AND a.payment_status = 'paid'
               GROUP BY at.treatment_name
               ORDER BY count DESC""",
            (start_date, end_date),
        ).fetchall()

        # Breakdown by technician
        technician_rows = conn.execute(
            """SELECT
                   a.technician_name,
                   COUNT(*) as appointments,
                   SUM(t.amount) as revenue,
                   SUM(t.tip_amount) as tips
               FROM transactions t
               JOIN nailbar_appointments a ON t.reference_id = a.appointment_id AND t.reference_type = 'appointment'
               WHERE t.source_type = 'nail_bar' AND DATE(t.created_at) BETWEEN ? AND ?
                   AND t.status = 'completed' AND a.technician_name IS NOT NULL
               GROUP BY a.technician_id, a.technician_name
               ORDER BY revenue DESC""",
            (start_date, end_date),
        ).fetchall()

        # Today's appointment counts by status
        status_rows = conn.execute(
            """SELECT status, COUNT(*) as count
               FROM nailbar_appointments
               WHERE appointment_date = ?
               GROUP BY status""",
            (today,),
        ).fetchall()

    summary = {
        "total_appointments": summary_row["total_appointments"] or 0 if summary_row else 0,
        "service_revenue": summary_row["service_revenue"] or 0 if summary_row else 0,
        "total_tips": summary_row["total_tips"] or 0 if summary_row else 0,
        "avg_service_value": round(summary_row["avg_service_value"] or 0, 2) if summary_row else 0,
    }

    log_activity("view", "nailbar_statistics", user=g.current_user.get("sub"))
    return jsonify({
        "period": {"start": start_date, "end": end_date},
        "summary": summary,
        "by_treatment": [_row_to_dict(r) for r in treatment_rows],
        "by_technician": [_row_to_dict(r) for r in technician_rows],
        "today_by_status": {row["status"]: row["count"] for row in status_rows},
        "generated_at": datetime.now().isoformat(),
    })
