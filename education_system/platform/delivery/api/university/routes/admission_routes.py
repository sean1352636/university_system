"""Admissions routes: prospects and applications."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import admin_required, token_required
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.platform.delivery.api.university.validators import validate_admission_application_create
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

admission_bp = Blueprint("admissions", __name__, url_prefix="/api/admissions")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Prospects ----

@admission_bp.route("/prospects", methods=["GET"])
@token_required
@admin_required
def list_prospects():
    status = request.args.get("status")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM admission_prospects WHERE first_name LIKE ? OR last_name LIKE ? OR email LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM admission_prospects" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM admission_prospects" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "admission_prospects", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@admission_bp.route("/prospects/<int:prospect_id>", methods=["GET"])
@token_required
@admin_required
def get_prospect(prospect_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM admission_prospects WHERE prospect_id = ?", (prospect_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Prospect {prospect_id} not found")
    log_activity("view", "admission_prospect", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Applications ----

@admission_bp.route("/applications", methods=["GET"])
@token_required
@admin_required
def list_applications():
    status = request.args.get("status")
    program = request.args.get("program")
    academic_year = request.args.get("academic_year")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if status:
            conditions.append("aa.status = ?")
            params.append(status)
        if program:
            conditions.append("aa.program_applied = ?")
            params.append(program)
        if academic_year:
            conditions.append("aa.academic_year = ?")
            params.append(academic_year)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT aa.*, ap.first_name, ap.last_name, ap.email"
            " FROM admission_applications aa"
            " LEFT JOIN admission_prospects ap ON aa.prospect_id = ap.prospect_id"
            + where + " ORDER BY aa.submission_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM admission_applications aa" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "admission_applications", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@admission_bp.route("/applications", methods=["POST"])
@token_required
def create_application():
    data = request.get_json(silent=True) or {}
    validate_admission_application_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO admission_applications
               (prospect_id, application_type, program_applied, academic_year, semester, status)
               VALUES (?, ?, ?, ?, ?, 'submitted')""",
            (
                data["prospect_id"],
                data["application_type"],
                data["program_applied"],
                data["academic_year"],
                data["semester"],
            ),
        )
        app_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM admission_applications WHERE application_id = ?", (app_id,)
        ).fetchone()

    log_activity("create", "admission_application", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@admission_bp.route("/applications/<int:application_id>", methods=["PUT"])
@token_required
@admin_required
def update_application(application_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM admission_applications WHERE application_id = ?", (application_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Application {application_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = ["status", "decision", "decision_date", "enrollment_confirmed", "application_fee_paid"]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    values.append(application_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE admission_applications SET " + ", ".join(set_clauses) + " WHERE application_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM admission_applications WHERE application_id = ?", (application_id,)
        ).fetchone()

    log_activity("update", "admission_application", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))
