"""Staff HR routes: staff records, contracts, leave, and performance reviews."""

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

staff_hr_bp = Blueprint("staff_hr", __name__, url_prefix="/api/staff-hr")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- staff ----

@staff_hr_bp.route("/staff", methods=["GET"])
@token_required
def list_staff():
    search = request.args.get("search")
    department = request.args.get("department")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM staff_records WHERE first_name LIKE ? OR last_name LIKE ? OR email LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if department:
            conditions.append("department = ?")
            params.append(department)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM staff_records" + where + " ORDER BY staff_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM staff_records" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "staff_records", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@staff_hr_bp.route("/staff/<int:staff_id>", methods=["GET"])
@token_required
def get_staff(staff_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM staff_records WHERE staff_id = ?", (staff_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"staff {staff_id} not found")
    log_activity("view", "staff_records", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@staff_hr_bp.route("/staff", methods=["POST"])
@token_required
def create_staff():
    data = request.get_json(silent=True) or {}
    for field in ["first_name", "last_name", "email", "department"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO staff_records
               (first_name, last_name, email, department, phone, position, hire_date, salary, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["first_name"], data["last_name"], data["email"], data["department"], data.get("phone", ""), data.get("position", ""), data.get("hire_date", ""), data.get("salary", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM staff_records WHERE staff_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "staff_records", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- leave-requests ----

@staff_hr_bp.route("/leave-requests", methods=["GET"])
@token_required
def list_leave_requests():
    staff_id = request.args.get("staff_id")
    status = request.args.get("status")
    leave_type = request.args.get("leave_type")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if staff_id:
            conditions.append("staff_id = ?")
            params.append(staff_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if leave_type:
            conditions.append("leave_type = ?")
            params.append(leave_type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM staff_leave_requests" + where + " ORDER BY request_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM staff_leave_requests" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "staff_leave_requests", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@staff_hr_bp.route("/leave-requests/<int:request_id>", methods=["GET"])
@token_required
def get_leave_request(request_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM staff_leave_requests WHERE request_id = ?", (request_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"leave-requests {request_id} not found")
    log_activity("view", "staff_leave_requests", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@staff_hr_bp.route("/leave-requests", methods=["POST"])
@token_required
def create_leave_request():
    data = request.get_json(silent=True) or {}
    for field in ["staff_id", "leave_type", "start_date", "end_date"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO staff_leave_requests
               (staff_id, leave_type, start_date, end_date, reason, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["staff_id"], data["leave_type"], data["start_date"], data["end_date"], data.get("reason", ""), data.get("notes", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM staff_leave_requests WHERE request_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "staff_leave_requests", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
