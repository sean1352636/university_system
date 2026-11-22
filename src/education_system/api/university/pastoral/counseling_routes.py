"""Counseling routes: mental health appointments, resources, counseling appointments, crisis resources.

Appointments are special-category data: the counselling team (counsellors
and the health team, ``access.AREA_ROLES["counselling"]``) sees all of them, a student sees and
books only their own (see ``_health_access``). The notes are sealed at rest.
Resources and crisis lines are open to anyone signed in.
"""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from education_system.api.university.pastoral._health_access import (
    audit_health_view,
    health_scope,
    is_health_team,
    own_student_id,
    seal,
    unseal,
)
from education_system.platform.delivery.api.university.auth import admin_required, token_required
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.platform.delivery.api.university.validators import (
    validate_counseling_appointment_create,
    validate_mental_health_appointment_create,
)
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

counseling_bp = Blueprint("counseling", __name__, url_prefix="/api/counseling")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


def _student_filter():
    """``(student_id filter, denial)`` for an appointment list."""
    scope, denial = health_scope(area="counselling")
    if denial is not None:
        return None, denial
    requested = request.args.get("student_id")
    if scope is not None and requested and str(requested) != scope:
        return None, (jsonify({"error": "Forbidden", "status": 403,
                               "message": "You can only see your own appointments"}), 403)
    return (scope if scope is not None else requested), None


def _book_for(data: dict):
    """Confine a non-team caller's booking to themselves; a 403 otherwise."""
    if is_health_team(area="counselling"):
        return None
    own = own_student_id()
    if own is None or str(data.get("student_id") or own) != own:
        return jsonify({"error": "Forbidden", "status": 403,
                        "message": "You can only book appointments for yourself"}), 403
    data["student_id"] = own
    return None


# ---- Mental Health Appointments ----

@counseling_bp.route("/mental-health/appointments", methods=["GET"])
@token_required
def list_mental_health_appointments():
    student_id, denial = _student_filter()
    if denial is not None:
        return denial
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
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
            "SELECT * FROM mental_health_appointments" + where + " ORDER BY appointment_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM mental_health_appointments" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    denial = audit_health_view("mental_health_appointments", student_id=student_id)
    if denial is not None:
        return denial
    log_activity("view", "mental_health_appointments", user=g.current_user.get("sub"))
    return jsonify(paginated_response(unseal(rows, "mental_health_appointments"), total, page, per_page))


@counseling_bp.route("/mental-health/appointments", methods=["POST"])
@token_required
def create_mental_health_appointment():
    data = request.get_json(silent=True) or {}
    denial = _book_for(data)
    if denial is not None:
        return denial
    validate_mental_health_appointment_create(data)
    notes = seal("mental_health_appointments", {"notes": data.get("notes", "")})["notes"]

    with transaction() as conn:
        conn.execute(
            """INSERT INTO mental_health_appointments
               (student_id, counselor_id, appointment_type, appointment_date,
                appointment_time, duration_minutes, is_anonymous, mode, location, notes, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled')""",
            (
                data["student_id"],
                data.get("counselor_id"),
                data["appointment_type"],
                data["appointment_date"],
                data["appointment_time"],
                data.get("duration_minutes", 50),
                data.get("is_anonymous", 0),
                data.get("mode", "in-person"),
                data.get("location"),
                notes,
            ),
        )
        aid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM mental_health_appointments WHERE appointment_id = ?", (aid,)
        ).fetchone()

    log_activity("create", "mental_health_appointment", user=g.current_user.get("sub"))
    return jsonify(unseal([row], "mental_health_appointments")[0]), 201


# ---- Mental Health Resources ----

@counseling_bp.route("/mental-health/resources", methods=["GET"])
@token_required
def list_mental_health_resources():
    category = request.args.get("category")
    content_type = request.args.get("content_type")

    with get_connection() as conn:
        conditions = ["is_published = 1"]
        params: list = []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if content_type:
            conditions.append("content_type = ?")
            params.append(content_type)

        where = " WHERE " + " AND ".join(conditions)
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM mental_health_resources" + where + " ORDER BY view_count DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM mental_health_resources" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "mental_health_resources", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- Counseling Appointments ----

@counseling_bp.route("/appointments", methods=["GET"])
@token_required
def list_counseling_appointments():
    student_id, denial = _student_filter()
    if denial is not None:
        return denial
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
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
            "SELECT * FROM counseling_appointments" + where + " ORDER BY appointment_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM counseling_appointments" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    denial = audit_health_view("counseling_appointments", student_id=student_id)
    if denial is not None:
        return denial
    log_activity("view", "counseling_appointments", user=g.current_user.get("sub"))
    return jsonify(paginated_response(unseal(rows, "counseling_appointments"), total, page, per_page))


@counseling_bp.route("/appointments", methods=["POST"])
@token_required
def create_counseling_appointment():
    data = request.get_json(silent=True) or {}
    denial = _book_for(data)
    if denial is not None:
        return denial
    validate_counseling_appointment_create(data)
    notes = seal("counseling_appointments", {"notes": data.get("notes", "")})["notes"]

    with transaction() as conn:
        conn.execute(
            """INSERT INTO counseling_appointments
               (student_id, appointment_date, appointment_time, counselor_name,
                appointment_type, status, notes)
               VALUES (?, ?, ?, ?, ?, 'Scheduled', ?)""",
            (
                data["student_id"],
                data["appointment_date"],
                data["appointment_time"],
                data.get("counselor_name"),
                data.get("appointment_type"),
                notes,
            ),
        )
        aid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM counseling_appointments WHERE appointment_id = ?", (aid,)
        ).fetchone()

    log_activity("create", "counseling_appointment", user=g.current_user.get("sub"))
    return jsonify(unseal([row], "counseling_appointments")[0]), 201


# ---- Crisis Resources ----

@counseling_bp.route("/crisis-resources", methods=["GET"])
@token_required
def list_crisis_resources():
    resource_type = request.args.get("resource_type")

    with get_connection() as conn:
        conditions = ["is_active = 1"]
        params: list = []
        if resource_type:
            conditions.append("resource_type = ?")
            params.append(resource_type)

        where = " WHERE " + " AND ".join(conditions)
        rows = conn.execute(
            "SELECT * FROM crisis_resources" + where + " ORDER BY resource_name",
            params,
        ).fetchall()

    log_activity("view", "crisis_resources", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})
