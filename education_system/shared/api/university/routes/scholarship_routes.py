"""Scholarship routes: listings and applications."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import admin_required, token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import validate_scholarship_application_create
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

scholarship_bp = Blueprint("scholarships", __name__, url_prefix="/api/scholarships")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


@scholarship_bp.route("", methods=["GET"])
@token_required
def list_scholarships():
    search = request.args.get("search")
    active_only = request.args.get("active", "").lower() != "false"

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM scholarships WHERE scholarship_name LIKE ? OR description LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if active_only:
            conditions.append("is_active = 1")

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM scholarships" + where + " ORDER BY deadline DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM scholarships" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "scholarships", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@scholarship_bp.route("/<int:scholarship_id>", methods=["GET"])
@token_required
def get_scholarship(scholarship_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM scholarships WHERE scholarship_id = ?", (scholarship_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Scholarship {scholarship_id} not found")
    log_activity("view", "scholarship", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Applications ----

@scholarship_bp.route("/applications", methods=["GET"])
@token_required
def list_applications():
    student_id = request.args.get("student_id")
    scholarship_id = request.args.get("scholarship_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if student_id:
            conditions.append("sa.student_id = ?")
            params.append(student_id)
        if scholarship_id:
            conditions.append("sa.scholarship_id = ?")
            params.append(scholarship_id)
        if status:
            conditions.append("sa.status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT sa.*, s.scholarship_name"
            " FROM scholarship_applications sa"
            " LEFT JOIN scholarships s ON sa.scholarship_id = s.scholarship_id"
            + where + " ORDER BY sa.application_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM scholarship_applications sa" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "scholarship_applications", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@scholarship_bp.route("/applications", methods=["POST"])
@token_required
def create_application():
    data = request.get_json(silent=True) or {}
    validate_scholarship_application_create(data)

    with get_connection() as conn:
        sch = conn.execute(
            "SELECT 1 FROM scholarships WHERE scholarship_id = ?", (data["scholarship_id"],)
        ).fetchone()
        if not sch:
            raise ValidationError(f"Scholarship {data['scholarship_id']} not found")

        existing = conn.execute(
            "SELECT 1 FROM scholarship_applications WHERE student_id = ? AND scholarship_id = ?",
            (data["student_id"], data["scholarship_id"]),
        ).fetchone()
        if existing:
            raise ValidationError("Student has already applied for this scholarship")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO scholarship_applications
               (student_id, scholarship_id, status, essay, additional_documents)
               VALUES (?, ?, 'pending', ?, ?)""",
            (
                data["student_id"],
                data["scholarship_id"],
                data.get("essay", ""),
                data.get("additional_documents", ""),
            ),
        )
        app_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM scholarship_applications WHERE application_id = ?", (app_id,)
        ).fetchone()

    log_activity("create", "scholarship_application", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@scholarship_bp.route("/applications/<int:application_id>", methods=["PUT"])
@token_required
@admin_required
def update_application(application_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM scholarship_applications WHERE application_id = ?", (application_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Scholarship application {application_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = [
        "status", "reviewer_id", "review_date", "review_notes",
        "decision_date", "award_amount",
    ]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    values.append(application_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE scholarship_applications SET " + ", ".join(set_clauses) + " WHERE application_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM scholarship_applications WHERE application_id = ?", (application_id,)
        ).fetchone()

    log_activity("update", "scholarship_application", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))
