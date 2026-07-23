"""Barber shop routes: services, appointments, staff, and transactions."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.post_18.university_system.core.exceptions import ValidationError
from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

barber_bp = Blueprint("barber", __name__, url_prefix="/api/barber")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- services ----

@barber_bp.route("/services", methods=["GET"])
@token_required
def list_services():
    search = request.args.get("search")
    service_type = request.args.get("service_type")
    is_available = request.args.get("is_available")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM barber_services WHERE name LIKE ? OR description LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if service_type:
            conditions.append("service_type = ?")
            params.append(service_type)
        if is_available:
            conditions.append("is_available = ?")
            params.append(is_available)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM barber_services" + where + " ORDER BY service_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM barber_services" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "barber_services", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@barber_bp.route("/services/<int:service_id>", methods=["GET"])
@token_required
def get_service(service_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM barber_services WHERE service_id = ?", (service_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"services {service_id} not found")
    log_activity("view", "barber_services", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@barber_bp.route("/services", methods=["POST"])
@token_required
def create_service():
    data = request.get_json(silent=True) or {}
    for field in ["name", "service_type", "duration_minutes", "price"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO barber_services
               (name, service_type, duration_minutes, price, description, is_available, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["name"], data["service_type"], data["duration_minutes"], data["price"], data.get("description", ""), data.get("is_available", 1), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM barber_services WHERE service_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "barber_services", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- appointments ----

@barber_bp.route("/appointments", methods=["GET"])
@token_required
def list_appointments():
    search = request.args.get("search")
    customer_id = request.args.get("customer_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM barber_appointments WHERE customer_name LIKE ?",
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
            "SELECT * FROM barber_appointments" + where + " ORDER BY appointment_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM barber_appointments" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "barber_appointments", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@barber_bp.route("/appointments/<int:appointment_id>", methods=["GET"])
@token_required
def get_appointment(appointment_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM barber_appointments WHERE appointment_id = ?", (appointment_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"appointments {appointment_id} not found")
    log_activity("view", "barber_appointments", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@barber_bp.route("/appointments", methods=["POST"])
@token_required
def create_appointment():
    data = request.get_json(silent=True) or {}
    for field in ["customer_id", "customer_name", "service_id", "appointment_date", "appointment_time"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO barber_appointments
               (customer_id, customer_name, service_id, appointment_date, appointment_time, customer_email, customer_phone, service_type, duration_minutes, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["customer_id"], data["customer_name"], data["service_id"], data["appointment_date"], data["appointment_time"], data.get("customer_email", ""), data.get("customer_phone", ""), data.get("service_type", ""), data.get("duration_minutes", ""), data.get("notes", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM barber_appointments WHERE appointment_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "barber_appointments", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- staff ----

@barber_bp.route("/staff", methods=["GET"])
@token_required
def list_staff():
    search = request.args.get("search")
    is_active = request.args.get("is_active")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM barber_staff WHERE name LIKE ?",
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
            "SELECT * FROM barber_staff" + where + " ORDER BY staff_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM barber_staff" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "barber_staff", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@barber_bp.route("/staff/<int:staff_id>", methods=["GET"])
@token_required
def get_staff(staff_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM barber_staff WHERE staff_id = ?", (staff_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"staff {staff_id} not found")
    log_activity("view", "barber_staff", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@barber_bp.route("/staff", methods=["POST"])
@token_required
def create_staff():
    data = request.get_json(silent=True) or {}
    for field in ["name", "specialization"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO barber_staff
               (name, specialization, phone, email, hire_date, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["name"], data["specialization"], data.get("phone", ""), data.get("email", ""), data.get("hire_date", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM barber_staff WHERE staff_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "barber_staff", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- update service ----

@barber_bp.route("/services/<int:service_id>", methods=["PUT"])
@token_required
def update_service(service_id: int):
    data = request.get_json(silent=True) or {}
    set_parts: list[str] = []
    values: list = []
    for col in (
        "description", "duration_minutes", "is_available", "name",
        "price", "service_type",
    ):
        if col in data:
            set_parts.append(f"{col} = ?")
            values.append(data[col])
    if not set_parts:
        raise ValidationError("No valid fields to update")

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM barber_services WHERE service_id = ?", (service_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Service {service_id} not found")

    set_clause = ", ".join(set_parts)
    values.append(service_id)
    with transaction() as conn:
        conn.execute(
            f"UPDATE barber_services SET {set_clause} WHERE service_id = ?", values
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM barber_services WHERE service_id = ?", (service_id,)
        ).fetchone()

    log_activity("update", "barber_services", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- appointment status update ----

@barber_bp.route("/appointments/<int:appointment_id>/status", methods=["PUT"])
@token_required
def update_appointment_status(appointment_id: int):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    valid_statuses = ["scheduled", "checked_in", "in_progress", "completed", "cancelled", "no_show"]
    if not status or status not in valid_statuses:
        raise ValidationError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM barber_appointments WHERE appointment_id = ?", (appointment_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Appointment {appointment_id} not found")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    notes = data.get("notes")
    with transaction() as conn:
        if notes:
            conn.execute(
                "UPDATE barber_appointments SET status = ?, notes = ?, updated_at = ? WHERE appointment_id = ?",
                (status, notes, now, appointment_id),
            )
        else:
            conn.execute(
                "UPDATE barber_appointments SET status = ?, updated_at = ? WHERE appointment_id = ?",
                (status, now, appointment_id),
            )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM barber_appointments WHERE appointment_id = ?", (appointment_id,)
        ).fetchone()

    log_activity("update", "barber_appointments", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- today's appointments ----

@barber_bp.route("/appointments/today", methods=["GET"])
@token_required
def get_todays_appointments():
    today = datetime.now().strftime("%Y-%m-%d")
    status = request.args.get("status")

    with get_connection() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM barber_appointments WHERE appointment_date = ? AND status = ? ORDER BY appointment_time",
                (today, status),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM barber_appointments WHERE appointment_date = ? ORDER BY appointment_time",
                (today,),
            ).fetchall()

    log_activity("view", "barber_appointments", user=g.current_user.get("sub"))
    items = [_row_to_dict(r) for r in rows]
    return jsonify({"items": items, "total": len(items), "date": today})


# ---- staff availability ----

@barber_bp.route("/staff/<int:staff_id>/availability", methods=["GET"])
@token_required
def get_staff_availability(staff_id: int):
    date = request.args.get("date")
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM barber_staff WHERE staff_id = ?", (staff_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Staff {staff_id} not found")

    time_slots = [
        "09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
        "12:00", "12:30", "13:00", "13:30", "14:00", "14:30",
        "15:00", "15:30", "16:00", "16:30", "17:00", "17:30",
    ]

    with get_connection() as conn:
        booked = conn.execute(
            "SELECT appointment_time FROM barber_appointments WHERE staff_id = ? AND appointment_date = ? AND status NOT IN ('cancelled', 'no_show')",
            (staff_id, date),
        ).fetchall()
        booked_times = {r["appointment_time"] for r in booked}

        # Also check blocked slots
        blocked = conn.execute(
            "SELECT start_time, end_time FROM barber_blocked_slots WHERE staff_id = ? AND blocked_date = ?",
            (staff_id, date),
        ).fetchall()
        for b in blocked:
            for slot in time_slots:
                if b["start_time"] <= slot < b["end_time"]:
                    booked_times.add(slot)

    available = [s for s in time_slots if s not in booked_times]

    log_activity("view", "barber_staff", user=g.current_user.get("sub"))
    return jsonify({
        "staff_id": staff_id,
        "date": date,
        "available_slots": available,
        "booked_slots": sorted(booked_times),
    })


# ---- customers ----

@barber_bp.route("/customers", methods=["POST"])
@token_required
def create_customer():
    data = request.get_json(silent=True) or {}
    for field in ["customer_id", "name"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO barber_customer_profiles
               (customer_id, name, email, phone, preferences, allergies, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["customer_id"], data["name"], data.get("email", ""),
             data.get("phone", ""), data.get("preferences", ""),
             data.get("allergies", ""), data.get("notes", ""), now, now),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM barber_customer_profiles WHERE customer_id = ?", (data["customer_id"],)
        ).fetchone()

    log_activity("create", "barber_customer_profiles", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@barber_bp.route("/customers", methods=["GET"])
@token_required
def list_customers():
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM barber_customer_profiles WHERE name LIKE ? OR email LIKE ? OR phone LIKE ? OR customer_id LIKE ? ORDER BY name LIMIT 50",
                (pattern, pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        page, per_page, offset = get_pagination_params()
        rows = conn.execute(
            "SELECT * FROM barber_customer_profiles ORDER BY name LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
        total_row = conn.execute("SELECT COUNT(*) FROM barber_customer_profiles").fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "barber_customer_profiles", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@barber_bp.route("/customers/<customer_id>", methods=["GET"])
@token_required
def get_customer(customer_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM barber_customer_profiles WHERE customer_id = ?", (customer_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Customer {customer_id} not found")
    log_activity("view", "barber_customer_profiles", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- feedback ----

@barber_bp.route("/feedback", methods=["POST"])
@token_required
def create_feedback():
    data = request.get_json(silent=True) or {}
    for field in ["customer_id", "rating"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    rating = data["rating"]
    if not isinstance(rating, int) or rating < 1 or rating > 5:
        raise ValidationError("Rating must be an integer between 1 and 5")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO barber_feedback
               (appointment_id, customer_id, staff_id, rating, comment)
               VALUES (?, ?, ?, ?, ?)""",
            (data.get("appointment_id"), data["customer_id"],
             data.get("staff_id"), rating, data.get("comment", "")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM barber_feedback WHERE feedback_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "barber_feedback", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@barber_bp.route("/feedback", methods=["GET"])
@token_required
def list_feedback():
    customer_id = request.args.get("customer_id")
    staff_id = request.args.get("staff_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if customer_id:
            conditions.append("f.customer_id = ?")
            params.append(customer_id)
        if staff_id:
            conditions.append("f.staff_id = ?")
            params.append(staff_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT f.*, a.service_name, a.appointment_date, s.name as staff_name"
            " FROM barber_feedback f"
            " LEFT JOIN barber_appointments a ON f.appointment_id = a.appointment_id"
            " LEFT JOIN barber_staff s ON f.staff_id = s.staff_id"
            + where + " ORDER BY f.created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM barber_feedback f" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "barber_feedback", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- statistics ----

@barber_bp.route("/statistics", methods=["GET"])
@token_required
def get_statistics():
    today = datetime.now().strftime("%Y-%m-%d")

    with get_connection() as conn:
        # Today's appointment counts
        appt_stats = conn.execute(
            "SELECT status, COUNT(*) as count FROM barber_appointments WHERE appointment_date = ? GROUP BY status",
            (today,),
        ).fetchall()
        appointment_summary = {r["status"]: r["count"] for r in appt_stats}
        total_today = sum(appointment_summary.values())

        # Daily revenue from transactions
        rev_row = conn.execute(
            """SELECT COUNT(*) as transaction_count,
                      COALESCE(SUM(amount), 0) as service_revenue,
                      COALESCE(SUM(tip_amount), 0) as tips,
                      COALESCE(SUM(amount + tip_amount), 0) as total_revenue
               FROM transactions
               WHERE source_type = 'barber' AND DATE(created_at) = ? AND status = 'completed'""",
            (today,),
        ).fetchone()

        # Popular services (last 30 days)
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        popular = conn.execute(
            """SELECT service_name, COUNT(*) as booking_count
               FROM barber_appointments
               WHERE appointment_date >= ? AND status NOT IN ('cancelled')
               GROUP BY service_name ORDER BY booking_count DESC LIMIT 5""",
            (thirty_days_ago,),
        ).fetchall()

        # Average rating
        avg_row = conn.execute(
            "SELECT AVG(rating) as avg_rating, COUNT(*) as review_count FROM barber_feedback"
        ).fetchone()

        # Active staff count
        staff_count = conn.execute(
            "SELECT COUNT(*) FROM barber_staff WHERE is_active = 1"
        ).fetchone()[0]

    log_activity("view", "barber_statistics", user=g.current_user.get("sub"))
    return jsonify({
        "date": today,
        "appointments_today": total_today,
        "appointment_breakdown": appointment_summary,
        "daily_revenue": {
            "transaction_count": rev_row["transaction_count"],
            "service_revenue": rev_row["service_revenue"],
            "tips": rev_row["tips"],
            "total_revenue": rev_row["total_revenue"],
        },
        "popular_services": [_row_to_dict(r) for r in popular],
        "average_rating": round(avg_row["avg_rating"], 2) if avg_row["avg_rating"] else None,
        "total_reviews": avg_row["review_count"],
        "active_staff": staff_count,
    })


# ---- daily revenue ----

@barber_bp.route("/revenue/daily", methods=["GET"])
@token_required
def get_daily_revenue():
    date = request.args.get("date")
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    with get_connection() as conn:
        row = conn.execute(
            """SELECT COUNT(*) as transaction_count,
                      COALESCE(SUM(amount), 0) as service_revenue,
                      COALESCE(SUM(tip_amount), 0) as tips,
                      COALESCE(SUM(amount + tip_amount), 0) as total_revenue
               FROM transactions
               WHERE source_type = 'barber' AND DATE(created_at) = ? AND status = 'completed'""",
            (date,),
        ).fetchone()

    log_activity("view", "barber_revenue", user=g.current_user.get("sub"))
    return jsonify({
        "date": date,
        "transaction_count": row["transaction_count"],
        "service_revenue": row["service_revenue"],
        "tips": row["tips"],
        "total_revenue": row["total_revenue"],
    })


# ---- waitlist ----

@barber_bp.route("/waitlist", methods=["POST"])
@token_required
def add_to_waitlist():
    data = request.get_json(silent=True) or {}
    for field in ["customer_id", "customer_name", "preferred_date"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO barber_waitlist
               (customer_id, customer_name, customer_email, customer_phone,
                preferred_date, preferred_time, service_id, staff_id, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["customer_id"], data["customer_name"],
             data.get("customer_email", ""), data.get("customer_phone", ""),
             data["preferred_date"], data.get("preferred_time", ""),
             data.get("service_id"), data.get("staff_id"),
             data.get("notes", "")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM barber_waitlist WHERE waitlist_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "barber_waitlist", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@barber_bp.route("/waitlist", methods=["GET"])
@token_required
def get_waitlist():
    date = request.args.get("date")
    service_id = request.args.get("service_id")
    status = request.args.get("status", "waiting")

    with get_connection() as conn:
        conditions = ["status = ?"]
        params: list = [status]
        if date:
            conditions.append("preferred_date = ?")
            params.append(date)
        if service_id:
            conditions.append("service_id = ?")
            params.append(service_id)

        where = " WHERE " + " AND ".join(conditions)
        rows = conn.execute(
            "SELECT * FROM barber_waitlist" + where + " ORDER BY created_at",
            params,
        ).fetchall()

    log_activity("view", "barber_waitlist", user=g.current_user.get("sub"))
    items = [_row_to_dict(r) for r in rows]
    return jsonify({"items": items, "total": len(items)})
