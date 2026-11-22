"""Health services routes: appointments and records.

Health data is special-category data, so every route goes through
``_health_access``: the health team sees every student, a student sees only
their own, and everyone else (including lecturers and generic staff) sees
nothing unless they have opened that student's record with break-glass
access (``POST /break-glass``). Every look is audited, fail closed.
"""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.api.university.pastoral._health_access import (
    audit_health_view,
    deny_unless_health_team,
    deny_unless_may_view_health,
    health_caller,
    health_scope,
    is_health_team,
    own_student_id,
    unseal,
)
from education_system.platform.delivery.api.university.auth import token_required
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.platform.delivery.api.university.validators import validate_health_appointment_create
from education_system.systems.university.infrastructure.exceptions import StudentNotFoundError, ValidationError
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

# Named "health_services", not "health": the platform owns a "health"
# blueprint for the liveness check (platform/delivery/api/health.py) and
# Flask rejects two blueprints sharing a name. That clash stopped the
# standalone university API server from starting at all.
health_bp = Blueprint("health_services", __name__, url_prefix="/api/health-services")

#: Statuses that free the slot again.
_INACTIVE_STATUSES = ("cancelled", "canceled", "no_show", "no-show", "rescheduled")
#: What a student may do to their own appointment: move it, or cancel it.
_STUDENT_EDITABLE = ("appointment_date", "appointment_time", "reason")
_STAFF_EDITABLE = (
    "appointment_type", "appointment_date", "appointment_time",
    "provider", "reason", "status", "notes",
)
_STATUSES = ("scheduled", "confirmed", "completed", "cancelled", "no_show", "rescheduled")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


def _clash(conn, *, student_id, provider, date, time, exclude_id=None):
    """A reason the slot cannot be booked, or ``None``.

    A student cannot hold two appointments at the same time, and a named
    provider cannot see two students at once.
    """
    marks = ",".join("?" * len(_INACTIVE_STATUSES))
    base = ("SELECT id FROM health_appointments WHERE appointment_date = ? "
            "AND appointment_time = ? AND LOWER(COALESCE(status, 'scheduled')) "
            f"NOT IN ({marks})")  # nosec B608 - placeholders only
    params = [date, time, *_INACTIVE_STATUSES]
    if exclude_id is not None:
        base += " AND id <> ?"
        params.append(exclude_id)
    if conn.execute(base + " AND student_id = ?", [*params, str(student_id)]).fetchone():
        return "The student already has an appointment at that time"
    if provider and conn.execute(base + " AND provider = ?", [*params, provider]).fetchone():
        return f"{provider} is already booked at that time"
    return None


# ---- Appointments ----

@health_bp.route("/appointments", methods=["GET"])
@token_required
def list_appointments():
    scope, denial = health_scope()
    if denial is not None:
        return denial
    student_id = request.args.get("student_id")
    if scope is not None:
        if student_id and str(student_id) != scope:
            return jsonify({"error": "Forbidden", "status": 403,
                            "message": "You can only see your own appointments"}), 403
        student_id = scope
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

    denial = audit_health_view("appointments", student_id=student_id)
    if denial is not None:
        return denial
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
    appt = _row_to_dict(row)
    denial = deny_unless_may_view_health(appt.get("student_id"), "appointment",
                                         record_id=appointment_id)
    if denial is not None:
        return denial
    log_activity("view", "health_appointment", user=g.current_user.get("sub"))
    return jsonify(appt)


@health_bp.route("/appointments", methods=["POST"])
@token_required
def create_appointment():
    data = request.get_json(silent=True) or {}
    team = is_health_team()
    if not team:
        own = own_student_id()
        if own is None:
            return jsonify({"error": "Forbidden", "status": 403,
                            "message": "Only students and the health team can book"}), 403
        if data.get("student_id") and str(data["student_id"]) != own:
            return jsonify({"error": "Forbidden", "status": 403,
                            "message": "You can only book appointments for yourself"}), 403
        data["student_id"] = own
        # Clinical notes are written by the health team, not the patient.
        data.pop("notes", None)
    validate_health_appointment_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        clash = _clash(conn, student_id=data["student_id"], provider=data.get("provider"),
                       date=data["appointment_date"], time=data["appointment_time"])
        if clash:
            raise ValidationError(clash)
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
            "SELECT * FROM health_appointments WHERE id = ?", (appointment_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Appointment {appointment_id} not found")
    existing = _row_to_dict(existing)
    denial = deny_unless_may_view_health(existing.get("student_id"), "appointment",
                                         record_id=appointment_id)
    if denial is not None:
        return denial

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    team = is_health_team()
    if team:
        allowed = _STAFF_EDITABLE
    else:
        # The student themselves: they may move the appointment or cancel it,
        # never mark it completed / no-show or write clinical notes.
        current = str(existing.get("status") or "scheduled").lower()
        if current not in ("scheduled", "confirmed"):
            raise ValidationError(f"This appointment is {current} and can no longer be changed")
        status = data.get("status")
        if status is not None and str(status).lower() not in ("cancelled", "canceled"):
            return jsonify({"error": "Forbidden", "status": 403,
                            "message": "You can only cancel or move your appointment"}), 403
        refused = sorted(set(data) - set(_STUDENT_EDITABLE) - {"status"})
        if refused:
            return jsonify({"error": "Forbidden", "status": 403,
                            "message": "You cannot change: " + ", ".join(refused)}), 403
        allowed = (*_STUDENT_EDITABLE, "status")
        if status is not None:
            data["status"] = "cancelled"

    if "status" in data and str(data["status"]).lower() not in _STATUSES:
        raise ValidationError("Invalid status. Must be one of: " + ", ".join(_STATUSES))

    set_clauses = []
    values = []
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    values.append(appointment_id)
    with transaction() as conn:
        moving = "appointment_date" in data or "appointment_time" in data or "provider" in data
        cancelling = str(data.get("status", "")).lower() in _INACTIVE_STATUSES
        if moving and not cancelling:
            clash = _clash(
                conn, student_id=existing["student_id"],
                provider=data.get("provider", existing.get("provider")),
                date=data.get("appointment_date", existing.get("appointment_date")),
                time=data.get("appointment_time", existing.get("appointment_time")),
                exclude_id=appointment_id)
            if clash:
                raise ValidationError(clash)
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
    scope, denial = health_scope()
    student_id = request.args.get("student_id")
    if denial is not None:
        # Outside the team: allowed only for a student opened with break-glass.
        if not student_id:
            return denial
        denial = deny_unless_may_view_health(student_id, "records")
        if denial is not None:
            return denial
    elif scope is not None:
        if student_id and str(student_id) != scope:
            return jsonify({"error": "Forbidden", "status": 403,
                            "message": "You can only see your own health records"}), 403
        student_id = scope
    if not student_id:
        raise ValidationError("'student_id' query parameter is required")

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, student_id, record_type, record_date, description, provider, confidential, created_at FROM health_records WHERE student_id = ? ORDER BY record_date DESC",
            (student_id,),
        ).fetchall()

    denial = audit_health_view("records", student_id=student_id)
    if denial is not None:
        return denial
    log_activity("view", "health_records", user=g.current_user.get("sub"))
    items = unseal(rows, "health_records")
    return jsonify({"items": items, "total": len(items)})


# ---- Break-glass ----

@health_bp.route("/break-glass", methods=["POST"])
@token_required
def open_with_break_glass():
    """Emergency access to one student's health data by someone outside the
    health team. Needs a written reason; logged, and the health
    administrators are e-mailed."""
    from education_system.systems.university.domains.health.application.health import access

    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")
    if not student_id:
        raise ValidationError("Missing required field: student_id")
    who = health_caller()
    if who is None:
        return deny_unless_health_team("open a record")
    try:
        emails = access.break_glass(who, student_id, data.get("reason", ""))
    except ValueError as exc:
        raise ValidationError(str(exc)) from None
    except PermissionError as exc:
        return jsonify({"error": "Forbidden", "message": str(exc), "status": 403}), 403

    sent = 0
    try:
        from education_system.systems.university.infrastructure.email.email_service.core import (
            send_email,
        )
        for address, subject, body in emails:
            try:
                send_email(address, subject, body, category="health")
                sent += 1
            except Exception as exc:  # the access itself is already recorded
                logger.warning("break-glass notice to %s failed: %s", address, exc)
    except ImportError as exc:
        logger.warning("break-glass notices not sent, email unavailable: %s", exc)

    log_activity("break_glass", "health_record", user=g.current_user.get("sub"))
    return jsonify({"student_id": str(student_id),
                    "minutes": access.BREAK_GLASS_MINUTES,
                    "administrators_notified": sent}), 201
