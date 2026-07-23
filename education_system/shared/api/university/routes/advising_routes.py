"""Advising routes: academic advising appointments."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import validate_advising_appointment_create
from education_system.post_18.university_system.core.exceptions import ValidationError
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

advising_bp = Blueprint("advising", __name__, url_prefix="/api/advising")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


@advising_bp.route("/appointments", methods=["GET"])
@token_required
def list_appointments():
    student_id = request.args.get("student_id")
    advisor_id = request.args.get("advisor_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if advisor_id:
            conditions.append("advisor_id = ?")
            params.append(advisor_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM advising_appointments" + where + " ORDER BY appointment_date DESC, appointment_time DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM advising_appointments" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "advising_appointments", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@advising_bp.route("/appointments/<int:appointment_id>", methods=["GET"])
@token_required
def get_appointment(appointment_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM advising_appointments WHERE appointment_id = ?",
            (appointment_id,),
        ).fetchone()
    if not row:
        raise ValidationError(f"Advising appointment {appointment_id} not found")
    log_activity("view", "advising_appointment", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@advising_bp.route("/appointments", methods=["POST"])
@token_required
def create_appointment():
    data = request.get_json(silent=True) or {}
    validate_advising_appointment_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO advising_appointments
               (student_id, advisor_id, appointment_date, appointment_time,
                duration_minutes, appointment_type, topic, notes, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'scheduled')""",
            (
                data["student_id"],
                data["advisor_id"],
                data["appointment_date"],
                data["appointment_time"],
                data.get("duration_minutes", 30),
                data["appointment_type"],
                data.get("topic", ""),
                data.get("notes", ""),
            ),
        )
        appt_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM advising_appointments WHERE appointment_id = ?", (appt_id,)
        ).fetchone()

    log_activity("create", "advising_appointment", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@advising_bp.route("/appointments/<int:appointment_id>", methods=["PUT"])
@token_required
def update_appointment(appointment_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM advising_appointments WHERE appointment_id = ?",
            (appointment_id,),
        ).fetchone()
    if not existing:
        raise ValidationError(f"Advising appointment {appointment_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = [
        "appointment_date", "appointment_time", "duration_minutes",
        "appointment_type", "topic", "notes", "status",
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
            "UPDATE advising_appointments SET " + ", ".join(set_clauses) + " WHERE appointment_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM advising_appointments WHERE appointment_id = ?",
            (appointment_id,),
        ).fetchone()

    log_activity("update", "advising_appointment", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))
