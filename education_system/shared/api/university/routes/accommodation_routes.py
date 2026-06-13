"""Accommodation routes: disability/accessibility services."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import admin_required, token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import validate_accommodation_request_create
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

accommodation_bp = Blueprint("accommodations", __name__, url_prefix="/api/accommodations")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Active Accommodations ----

@accommodation_bp.route("", methods=["GET"])
@token_required
def list_accommodations():
    student_id = request.args.get("student_id")
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
            "SELECT * FROM accommodations" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM accommodations" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "accommodations", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@accommodation_bp.route("/<int:accommodation_id>", methods=["GET"])
@token_required
def get_accommodation(accommodation_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accommodations WHERE id = ?", (accommodation_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Accommodation {accommodation_id} not found")
    log_activity("view", "accommodation", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Requests ----

@accommodation_bp.route("/requests", methods=["GET"])
@token_required
def list_requests():
    student_id = request.args.get("student_id")
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
            "SELECT * FROM accommodation_requests" + where + " ORDER BY requested_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM accommodation_requests" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "accommodation_requests", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@accommodation_bp.route("/requests", methods=["POST"])
@token_required
def create_request():
    data = request.get_json(silent=True) or {}
    validate_accommodation_request_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO accommodation_requests
               (student_id, accommodation_type, description, status,
                student_name, student_email)
               VALUES (?, ?, ?, 'pending', ?, ?)""",
            (
                data["student_id"],
                data["accommodation_type"],
                data.get("description", ""),
                data.get("student_name", ""),
                data.get("student_email", ""),
            ),
        )
        req_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accommodation_requests WHERE request_id = ?", (req_id,)
        ).fetchone()

    log_activity("create", "accommodation_request", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@accommodation_bp.route("/requests/<int:request_id>", methods=["PUT"])
@token_required
@admin_required
def update_request(request_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM accommodation_requests WHERE request_id = ?", (request_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Accommodation request {request_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = ["status", "reviewed_by", "review_date", "review_notes", "reviewer_notes"]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    values.append(request_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE accommodation_requests SET " + ", ".join(set_clauses) + " WHERE request_id = ?",
            values,
        )

    # If approved, create the accommodation record
    if data.get("status") == "approved":
        with get_connection() as conn:
            req = conn.execute(
                "SELECT * FROM accommodation_requests WHERE request_id = ?", (request_id,)
            ).fetchone()
        if req:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with transaction() as conn:
                conn.execute(
                    """INSERT INTO accommodations
                       (student_id, accommodation_type, description, status,
                        approved_by, approval_date, created_at, updated_at)
                       VALUES (?, ?, ?, 'active', ?, ?, ?, ?)""",
                    (
                        req["student_id"],
                        req["accommodation_type"],
                        req["description"],
                        data.get("reviewed_by", g.current_user.get("sub")),
                        now,
                        now,
                        now,
                    ),
                )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accommodation_requests WHERE request_id = ?", (request_id,)
        ).fetchone()

    log_activity("update", "accommodation_request", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))
