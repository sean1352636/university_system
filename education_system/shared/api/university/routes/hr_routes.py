"""HR routes: staff, departments, instructors, leave, shifts, timesheets, appraisals."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import admin_required, token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import (
    validate_leave_request_create,
    validate_shift_create,
    validate_timesheet_create,
)
from education_system.post_18.university_system.core.exceptions import ValidationError
from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

hr_bp = Blueprint("hr", __name__, url_prefix="/api/hr")

SENSITIVE_STAFF_FIELDS = {"password_hash", "salt"}


def _row_to_dict(row, exclude: set | None = None) -> dict:
    if row is None:
        return {}
    d = {k: row[k] for k in row.keys()}
    if exclude:
        for f in exclude:
            d.pop(f, None)
    return d


# ---- Staff ----

@hr_bp.route("/staff", methods=["GET"])
@token_required
@admin_required
def list_staff():
    role = request.args.get("role")
    status = request.args.get("status")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM staff WHERE name LIKE ? OR email LIKE ? OR username LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r, SENSITIVE_STAFF_FIELDS) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if role:
            conditions.append("role = ?")
            params.append(role)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM staff" + where + " ORDER BY name LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM staff" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "staff", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r, SENSITIVE_STAFF_FIELDS) for r in rows], total, page, per_page
    ))


@hr_bp.route("/staff/<int:staff_id>", methods=["GET"])
@token_required
def get_staff(staff_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM staff WHERE id = ?", (staff_id,)).fetchone()
    if not row:
        raise ValidationError(f"Staff {staff_id} not found")
    log_activity("view", "staff_member", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row, SENSITIVE_STAFF_FIELDS))


# ---- Departments ----

@hr_bp.route("/departments", methods=["GET"])
@token_required
def list_departments():
    with get_connection() as conn:
        page, per_page, offset = get_pagination_params()
        rows = conn.execute(
            "SELECT * FROM departments WHERE is_active = 1 ORDER BY name LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM departments WHERE is_active = 1"
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "departments", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@hr_bp.route("/departments/<int:dept_id>", methods=["GET"])
@token_required
def get_department(dept_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM departments WHERE dept_id = ?", (dept_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Department {dept_id} not found")
    log_activity("view", "department", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Instructors ----

@hr_bp.route("/instructors", methods=["GET"])
@token_required
def list_instructors():
    department = request.args.get("department")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM instructors WHERE is_active = 1 AND (first_name LIKE ? OR last_name LIKE ? OR email LIKE ?)",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = ["is_active = 1"]
        params: list = []
        if department:
            conditions.append("department = ?")
            params.append(department)

        where = " WHERE " + " AND ".join(conditions)
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM instructors" + where + " ORDER BY last_name, first_name LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM instructors" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "instructors", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- Leave Requests ----

@hr_bp.route("/leave-requests", methods=["GET"])
@token_required
def list_leave_requests():
    user_id = request.args.get("user_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM leave_requests" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM leave_requests" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "leave_requests", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@hr_bp.route("/leave-requests", methods=["POST"])
@token_required
def create_leave_request():
    data = request.get_json(silent=True) or {}
    validate_leave_request_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO leave_requests
               (user_id, leave_type_id, start_date, end_date, total_days, reason, status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
            (
                data["user_id"],
                data["leave_type_id"],
                data["start_date"],
                data["end_date"],
                data["total_days"],
                data.get("reason", ""),
            ),
        )
        req_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM leave_requests WHERE request_id = ?", (req_id,)
        ).fetchone()

    log_activity("create", "leave_request", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@hr_bp.route("/leave-requests/<int:request_id>", methods=["PUT"])
@token_required
@admin_required
def update_leave_request(request_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM leave_requests WHERE request_id = ?", (request_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Leave request {request_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = ["status", "approved_by", "approved_date", "rejection_reason"]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    set_clauses.append("updated_at = datetime('now')")
    values.append(request_id)

    with transaction() as conn:
        conn.execute(
            "UPDATE leave_requests SET " + ", ".join(set_clauses) + " WHERE request_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM leave_requests WHERE request_id = ?", (request_id,)
        ).fetchone()

    log_activity("update", "leave_request", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Shifts ----

@hr_bp.route("/shifts", methods=["GET"])
@token_required
def list_shifts():
    staff_id = request.args.get("staff_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if staff_id:
            conditions.append("staff_id = ?")
            params.append(staff_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM shifts" + where + " ORDER BY shift_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM shifts" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "shifts", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@hr_bp.route("/shifts", methods=["POST"])
@token_required
@admin_required
def create_shift():
    data = request.get_json(silent=True) or {}
    validate_shift_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO shifts
               (staff_id, shift_date, start_time, end_time, position, notes, status)
               VALUES (?, ?, ?, ?, ?, ?, 'scheduled')""",
            (
                data["staff_id"],
                data["shift_date"],
                data["start_time"],
                data["end_time"],
                data.get("position", "general"),
                data.get("notes", ""),
            ),
        )
        shift_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM shifts WHERE id = ?", (shift_id,)).fetchone()

    log_activity("create", "shift", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Timesheets ----

@hr_bp.route("/timesheets", methods=["GET"])
@token_required
def list_timesheets():
    user_id = request.args.get("user_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM timesheets" + where + " ORDER BY week_start DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM timesheets" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "timesheets", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@hr_bp.route("/timesheets", methods=["POST"])
@token_required
def create_timesheet():
    data = request.get_json(silent=True) or {}
    validate_timesheet_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO timesheets
               (user_id, week_start, week_end, total_hours, regular_hours, overtime_hours, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, 'draft', ?)""",
            (
                data["user_id"],
                data["week_start"],
                data["week_end"],
                data.get("total_hours", 0),
                data.get("regular_hours", 0),
                data.get("overtime_hours", 0),
                data.get("notes", ""),
            ),
        )
        ts_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM timesheets WHERE timesheet_id = ?", (ts_id,)
        ).fetchone()

    log_activity("create", "timesheet", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@hr_bp.route("/timesheets/<int:timesheet_id>", methods=["PUT"])
@token_required
def update_timesheet(timesheet_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM timesheets WHERE timesheet_id = ?", (timesheet_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Timesheet {timesheet_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = [
        "total_hours", "regular_hours", "overtime_hours", "status",
        "approved_by", "approved_date", "rejection_reason", "notes",
    ]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    set_clauses.append("updated_at = datetime('now')")
    values.append(timesheet_id)

    with transaction() as conn:
        conn.execute(
            "UPDATE timesheets SET " + ", ".join(set_clauses) + " WHERE timesheet_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM timesheets WHERE timesheet_id = ?", (timesheet_id,)
        ).fetchone()

    log_activity("update", "timesheet", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Appraisals ----

@hr_bp.route("/appraisals", methods=["GET"])
@token_required
def list_appraisals():
    user_id = request.args.get("user_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM appraisal_records" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM appraisal_records" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "appraisals", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))
