"""Health services routes: appointments and records."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.university_system.api.auth import token_required
from education_system.university_system.api.pagination import get_pagination_params, paginated_response
from education_system.university_system.api.validators import validate_health_appointment_create
from education_system.university_system.core.exceptions import StudentNotFoundError, ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

health_bp = Blueprint("health", __name__, url_prefix="/api/health-services")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Appointments ----

@health_bp.route("/appointments", methods=["GET"])
@token_required
def list_appointments():
    student_id = request.args.get("student_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM health_appointments" + where + " ORDER BY appointment_date DESC, appointment_time DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM health_appointments" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "health_appointments", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@health_bp.route("/appointments/<int:appointment_id>", methods=["GET"])
@token_required
def get_appointment(appointment_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM health_appointments WHERE id = ?", (appointment_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Appointment {appointment_id} not found")
    log_activity("view", "health_appointment", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@health_bp.route("/appointments", methods=["POST"])
@token_required
def create_appointment():
    data = request.get_json(silent=True) or {}
    validate_health_appointment_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO health_appointments
               (student_id, appointment_type, appointment_date, appointment_time,
                provider, reason, status, notes, scheduled_at)
               VALUES (?, ?, ?, ?, ?, ?, 'scheduled', ?, ?)""",
            (
                data["student_id"],
                data["appointment_type"],
                data["appointment_date"],
                data["appointment_time"],
                data.get("provider", ""),
                data.get("reason", ""),
                data.get("notes", ""),
                now,
            ),
        )
        appt_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM health_appointments WHERE id = ?", (appt_id,)
        ).fetchone()

    log_activity("create", "health_appointment", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@health_bp.route("/appointments/<int:appointment_id>", methods=["PUT"])
@token_required
def update_appointment(appointment_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM health_appointments WHERE id = ?", (appointment_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Appointment {appointment_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = [
        "appointment_type", "appointment_date", "appointment_time",
        "provider", "reason", "status", "notes",
    ]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    values.append(appointment_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE health_appointments SET " + ", ".join(set_clauses) + " WHERE id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM health_appointments WHERE id = ?", (appointment_id,)
        ).fetchone()

    log_activity("update", "health_appointment", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Records ----

@health_bp.route("/records", methods=["GET"])
@token_required
def list_records():
    student_id = request.args.get("student_id")
    if not student_id:
        raise ValidationError("'student_id' query parameter is required")

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, student_id, record_type, record_date, description, provider, confidential, created_at FROM health_records WHERE student_id = ? ORDER BY record_date DESC",
            (student_id,),
        ).fetchall()

    log_activity("view", "health_records", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})
