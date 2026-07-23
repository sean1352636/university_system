"""Gym routes: memberships, classes, bookings, equipment, and PT sessions."""

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

gym_bp = Blueprint("gym", __name__, url_prefix="/api/gym")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- memberships ----

@gym_bp.route("/memberships", methods=["GET"])
@token_required
def list_memberships():
    search = request.args.get("search")
    membership_type = request.args.get("membership_type")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM gym_memberships WHERE user_name LIKE ? OR member_number LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if membership_type:
            conditions.append("membership_type = ?")
            params.append(membership_type)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM gym_memberships" + where + " ORDER BY membership_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM gym_memberships" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "gym_memberships", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@gym_bp.route("/memberships/<int:membership_id>", methods=["GET"])
@token_required
def get_membership(membership_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM gym_memberships WHERE membership_id = ?", (membership_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"memberships {membership_id} not found")
    log_activity("view", "gym_memberships", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@gym_bp.route("/memberships", methods=["POST"])
@token_required
def create_membership():
    data = request.get_json(silent=True) or {}
    for field in ["user_id", "user_name", "membership_type", "monthly_fee"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO gym_memberships
               (user_id, user_name, membership_type, monthly_fee, user_email, user_phone, start_date, end_date, emergency_contact, health_conditions, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["user_id"], data["user_name"], data["membership_type"], data["monthly_fee"], data.get("user_email", ""), data.get("user_phone", ""), data.get("start_date", ""), data.get("end_date", ""), data.get("emergency_contact", ""), data.get("health_conditions", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM gym_memberships WHERE membership_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "gym_memberships", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- classes ----

@gym_bp.route("/classes", methods=["GET"])
@token_required
def list_classes():
    search = request.args.get("search")
    class_type = request.args.get("class_type")
    difficulty_level = request.args.get("difficulty_level")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM gym_classes WHERE class_name LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if class_type:
            conditions.append("class_type = ?")
            params.append(class_type)
        if difficulty_level:
            conditions.append("difficulty_level = ?")
            params.append(difficulty_level)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM gym_classes" + where + " ORDER BY class_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM gym_classes" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "gym_classes", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@gym_bp.route("/classes/<int:class_id>", methods=["GET"])
@token_required
def get_classe(class_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM gym_classes WHERE class_id = ?", (class_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"classes {class_id} not found")
    log_activity("view", "gym_classes", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@gym_bp.route("/classes", methods=["POST"])
@token_required
def create_classe():
    data = request.get_json(silent=True) or {}
    for field in ["class_name", "class_type", "instructor_name", "schedule_day", "start_time"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO gym_classes
               (class_name, class_type, instructor_name, schedule_day, start_time, instructor_id, end_time, location, max_capacity, description, difficulty_level, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["class_name"], data["class_type"], data["instructor_name"], data["schedule_day"], data["start_time"], data.get("instructor_id", ""), data.get("end_time", ""), data.get("location", ""), data.get("max_capacity", ""), data.get("description", ""), data.get("difficulty_level", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM gym_classes WHERE class_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "gym_classes", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- bookings ----

@gym_bp.route("/bookings", methods=["GET"])
@token_required
def list_bookings():
    class_id = request.args.get("class_id")
    member_id = request.args.get("member_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if class_id:
            conditions.append("class_id = ?")
            params.append(class_id)
        if member_id:
            conditions.append("member_id = ?")
            params.append(member_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM gym_class_bookings" + where + " ORDER BY booking_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM gym_class_bookings" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "gym_class_bookings", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@gym_bp.route("/bookings/<int:booking_id>", methods=["GET"])
@token_required
def get_booking(booking_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM gym_class_bookings WHERE booking_id = ?", (booking_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"bookings {booking_id} not found")
    log_activity("view", "gym_class_bookings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@gym_bp.route("/bookings", methods=["POST"])
@token_required
def create_booking():
    data = request.get_json(silent=True) or {}
    for field in ["class_id", "member_id", "booking_date"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO gym_class_bookings
               (class_id, member_id, booking_date, status, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (data["class_id"], data["member_id"], data["booking_date"], data.get("status", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM gym_class_bookings WHERE booking_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "gym_class_bookings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- membership actions ----

@gym_bp.route("/memberships/<int:membership_id>/renew", methods=["POST"])
@token_required
def renew_membership(membership_id: int):
    data = request.get_json(silent=True) or {}
    months = data.get("months", 1)

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM gym_memberships WHERE membership_id = ?", (membership_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"membership {membership_id} not found")

    membership = _row_to_dict(row)
    current_end = datetime.fromisoformat(membership["end_date"])
    new_start = max(current_end, datetime.now())
    from datetime import timedelta
    new_end = new_start + timedelta(days=30 * months)
    total_fee = float(membership["monthly_fee"]) * months

    with transaction() as conn:
        conn.execute(
            "UPDATE gym_memberships SET end_date = ?, status = 'active' WHERE membership_id = ?",
            (new_end.strftime("%Y-%m-%d"), membership_id),
        )

    log_activity("renew", "gym_memberships", user=g.current_user.get("sub"))
    return jsonify({"membership_id": membership_id, "new_end_date": new_end.strftime("%Y-%m-%d"), "total_fee": total_fee})


@gym_bp.route("/memberships/<int:membership_id>/cancel", methods=["POST"])
@token_required
def cancel_membership(membership_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM gym_memberships WHERE membership_id = ?", (membership_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"membership {membership_id} not found")

    with transaction() as conn:
        conn.execute(
            "UPDATE gym_memberships SET status = 'cancelled' WHERE membership_id = ?",
            (membership_id,),
        )

    log_activity("cancel", "gym_memberships", user=g.current_user.get("sub"))
    return jsonify({"membership_id": membership_id, "status": "cancelled"})


# ---- check-in / check-out ----

@gym_bp.route("/check-in", methods=["POST"])
@token_required
def check_in():
    data = request.get_json(silent=True) or {}
    if "member_id" not in data:
        raise ValidationError("Missing required field: member_id")

    member_id = data["member_id"]
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM gym_memberships WHERE membership_id = ?", (member_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"membership {member_id} not found")

    with transaction() as conn:
        conn.execute(
            "INSERT INTO gym_attendance (member_id) VALUES (?)",
            (member_id,),
        )
        attendance_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_activity("check_in", "gym_attendance", user=g.current_user.get("sub"))
    return jsonify({"attendance_id": attendance_id, "member_id": member_id}), 201


@gym_bp.route("/check-out", methods=["POST"])
@token_required
def check_out():
    data = request.get_json(silent=True) or {}
    if "attendance_id" not in data:
        raise ValidationError("Missing required field: attendance_id")

    attendance_id = data["attendance_id"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        conn.execute(
            "UPDATE gym_attendance SET check_out = ? WHERE attendance_id = ?",
            (now, attendance_id),
        )

    log_activity("check_out", "gym_attendance", user=g.current_user.get("sub"))
    return jsonify({"attendance_id": attendance_id, "check_out": now})


# ---- cancel class booking ----

@gym_bp.route("/classes/<int:booking_id>/cancel-booking", methods=["POST"])
@token_required
def cancel_class_booking(booking_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM gym_class_bookings WHERE booking_id = ?", (booking_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"booking {booking_id} not found")

    booking = _row_to_dict(row)
    with transaction() as conn:
        conn.execute(
            "UPDATE gym_class_bookings SET status = 'cancelled' WHERE booking_id = ?",
            (booking_id,),
        )
        conn.execute(
            "UPDATE gym_classes SET current_enrolled = current_enrolled - 1 WHERE class_id = ?",
            (booking["class_id"],),
        )

    log_activity("cancel", "gym_class_bookings", user=g.current_user.get("sub"))
    return jsonify({"booking_id": booking_id, "status": "cancelled"})


# ---- member bookings ----

@gym_bp.route("/members/<int:member_id>/bookings", methods=["GET"])
@token_required
def get_member_bookings(member_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT b.*, c.class_name, c.instructor_name, c.start_time, c.location
               FROM gym_class_bookings b
               JOIN gym_classes c ON b.class_id = c.class_id
               WHERE b.member_id = ? AND b.status = 'confirmed'
               ORDER BY b.booking_date DESC""",
            (member_id,),
        ).fetchall()

    log_activity("view", "gym_class_bookings", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- personal training ----

@gym_bp.route("/personal-training", methods=["POST"])
@token_required
def book_pt_session():
    data = request.get_json(silent=True) or {}
    for field in ["member_id", "trainer_name", "session_date", "session_time"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    session_type = data.get("session_type", "single")
    pt_fees = {"single": 35.00, "package_5": 150.00, "package_10": 280.00}
    fee = pt_fees.get(session_type, pt_fees["single"])
    duration = data.get("duration_minutes", 60)

    import uuid
    booking_ref = f"BK-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO gym_pt_sessions
               (booking_ref, member_id, trainer_name, session_date, session_time,
                duration_minutes, session_type, fee, trainer_id, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (booking_ref, data["member_id"], data["trainer_name"],
             data["session_date"], data["session_time"], duration,
             session_type, fee, data.get("trainer_id", ""),
             data.get("notes", ""), now),
        )
        session_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_activity("create", "gym_pt_sessions", user=g.current_user.get("sub"))
    return jsonify({"session_id": session_id, "booking_ref": booking_ref, "fee": fee}), 201


@gym_bp.route("/members/<int:member_id>/sessions", methods=["GET"])
@token_required
def get_member_pt_sessions(member_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM gym_pt_sessions WHERE member_id = ? ORDER BY session_date DESC",
            (member_id,),
        ).fetchall()

    log_activity("view", "gym_pt_sessions", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- equipment ----

@gym_bp.route("/equipment", methods=["GET"])
@token_required
def list_equipment():
    category = request.args.get("category")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            "SELECT * FROM gym_equipment" + where + " ORDER BY category, equipment_name",
            params,
        ).fetchall()

    log_activity("view", "gym_equipment", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@gym_bp.route("/equipment/<int:equipment_id>/report-issue", methods=["POST"])
@token_required
def report_equipment_issue(equipment_id: int):
    data = request.get_json(silent=True) or {}
    if "issue" not in data:
        raise ValidationError("Missing required field: issue")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM gym_equipment WHERE equipment_id = ?", (equipment_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"equipment {equipment_id} not found")

    with transaction() as conn:
        conn.execute(
            "UPDATE gym_equipment SET status = 'maintenance', notes = ? WHERE equipment_id = ?",
            (data["issue"], equipment_id),
        )

    log_activity("report_issue", "gym_equipment", user=g.current_user.get("sub"))
    return jsonify({"equipment_id": equipment_id, "status": "maintenance", "issue": data["issue"]})


# ---- statistics / reports ----

@gym_bp.route("/statistics", methods=["GET"])
@token_required
def get_membership_stats():
    with get_connection() as conn:
        cursor = conn.execute(
            """SELECT membership_type, COUNT(*), SUM(monthly_fee)
               FROM gym_memberships WHERE status = 'active'
               GROUP BY membership_type"""
        )
        by_type = {row[0]: {"count": row[1], "revenue": row[2]} for row in cursor.fetchall()}

        total_row = conn.execute(
            "SELECT COUNT(*) FROM gym_memberships WHERE status = 'active'"
        ).fetchone()
        total_active = total_row[0] if total_row else 0

    log_activity("view", "gym_statistics", user=g.current_user.get("sub"))
    return jsonify({"by_type": by_type, "total_active": total_active})


@gym_bp.route("/attendance/daily", methods=["GET"])
@token_required
def get_daily_attendance():
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))

    with get_connection() as conn:
        check_in_row = conn.execute(
            "SELECT COUNT(*) FROM gym_attendance WHERE DATE(check_in) = ?", (date,)
        ).fetchone()
        check_ins = check_in_row[0] if check_in_row else 0

        revenue_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE source_type = 'gym' AND DATE(created_at) = ?",
            (date,),
        ).fetchone()
        revenue = revenue_row[0] if revenue_row else 0

    log_activity("view", "gym_attendance", user=g.current_user.get("sub"))
    return jsonify({"date": date, "check_ins": check_ins, "revenue": revenue})
