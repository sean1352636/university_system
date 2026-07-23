"""Financial aid routes: applications, aid packages, and payment plans."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import admin_required, token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import (
    validate_aid_package_update,
    validate_financial_aid_application_create,
)
from education_system.post_18.university_system.core.exceptions import ValidationError
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

financial_aid_bp = Blueprint("financial_aid", __name__, url_prefix="/api/financial-aid")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Applications ----

@financial_aid_bp.route("/applications", methods=["GET"])
@token_required
def list_applications():
    student_id = request.args.get("student_id")
    status = request.args.get("status")
    academic_year = request.args.get("academic_year")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if academic_year:
            conditions.append("academic_year = ?")
            params.append(academic_year)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM financial_aid_applications" + where + " ORDER BY application_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM financial_aid_applications" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "financial_aid_applications", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@financial_aid_bp.route("/applications", methods=["POST"])
@token_required
def create_application():
    data = request.get_json(silent=True) or {}
    validate_financial_aid_application_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO financial_aid_applications
               (student_id, academic_year, status, family_income,
                household_size, special_circumstances, submitted_by)
               VALUES (?, ?, 'pending', ?, ?, ?, ?)""",
            (
                data["student_id"],
                data["academic_year"],
                data.get("family_income"),
                data.get("household_size"),
                data.get("special_circumstances", ""),
                g.current_user.get("user_id"),
            ),
        )
        app_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM financial_aid_applications WHERE application_id = ?", (app_id,)
        ).fetchone()

    log_activity("create", "financial_aid_application", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@financial_aid_bp.route("/applications/<int:application_id>", methods=["PUT"])
@token_required
@admin_required
def update_application(application_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM financial_aid_applications WHERE application_id = ?",
            (application_id,),
        ).fetchone()
    if not existing:
        raise ValidationError(f"Application {application_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = ["status", "reviewed_by", "review_date", "review_notes"]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    values.append(application_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE financial_aid_applications SET " + ", ".join(set_clauses) + " WHERE application_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM financial_aid_applications WHERE application_id = ?",
            (application_id,),
        ).fetchone()

    log_activity("update", "financial_aid_application", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Aid Packages ----

@financial_aid_bp.route("/packages", methods=["GET"])
@token_required
def list_packages():
    student_id = request.args.get("student_id")
    academic_year = request.args.get("academic_year")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if academic_year:
            conditions.append("academic_year = ?")
            params.append(academic_year)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            "SELECT * FROM aid_packages" + where + " ORDER BY created_at DESC", params
        ).fetchall()

    log_activity("view", "aid_packages", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@financial_aid_bp.route("/packages/<int:package_id>", methods=["GET"])
@token_required
def get_package(package_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM aid_packages WHERE package_id = ?", (package_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Aid package {package_id} not found")
    log_activity("view", "aid_package", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@financial_aid_bp.route("/packages/<int:package_id>", methods=["PUT"])
@token_required
def update_package(package_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM aid_packages WHERE package_id = ?", (package_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Aid package {package_id} not found")

    data = request.get_json(silent=True) or {}
    validate_aid_package_update(data)

    set_clauses = []
    values = []
    allowed = ["package_status", "response_date"]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    values.append(package_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE aid_packages SET " + ", ".join(set_clauses) + " WHERE package_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM aid_packages WHERE package_id = ?", (package_id,)
        ).fetchone()

    log_activity("update", "aid_package", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Payment Plans ----

@financial_aid_bp.route("/payment-plans", methods=["GET"])
@token_required
def list_payment_plans():
    student_id = request.args.get("student_id")
    if not student_id:
        raise ValidationError("'student_id' query parameter is required")

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM student_payment_plans WHERE student_id = ? ORDER BY start_date DESC",
            (student_id,),
        ).fetchall()

    log_activity("view", "payment_plans", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@financial_aid_bp.route("/payment-plans/<int:plan_id>/installments", methods=["GET"])
@token_required
def list_installments(plan_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM payment_plan_installments WHERE payment_plan_id = ? ORDER BY due_date",
            (plan_id,),
        ).fetchall()

    log_activity("view", "payment_plan_installments", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})
