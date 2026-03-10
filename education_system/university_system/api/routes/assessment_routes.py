"""Assessment routes: module assessments and evaluations."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.university_system.api.auth import token_required
from education_system.university_system.api.pagination import get_pagination_params, paginated_response
from education_system.university_system.api.validators import validate_assessment_create, validate_assessment_update
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

assessment_bp = Blueprint("assessments", __name__, url_prefix="/api/assessments")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


@assessment_bp.route("", methods=["GET"])
@token_required
def list_assessments():
    module_code = request.args.get("module_code")
    assessment_type = request.args.get("type")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if module_code:
            conditions.append("module_code = ?")
            params.append(module_code)
        if assessment_type:
            conditions.append("assessment_type = ?")
            params.append(assessment_type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM assessments" + where + " ORDER BY due_date LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM assessments" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "assessments", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@assessment_bp.route("/<int:assessment_id>", methods=["GET"])
@token_required
def get_assessment(assessment_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM assessments WHERE assessment_id = ?", (assessment_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Assessment {assessment_id} not found")
    log_activity("view", "assessment", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@assessment_bp.route("", methods=["POST"])
@token_required
def create_assessment():
    data = request.get_json(silent=True) or {}
    validate_assessment_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO assessments
               (assessment_name, assessment_type, module_code, max_points, weight,
                due_date, description, duration_minutes, status, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?)""",
            (
                data["assessment_name"],
                data["assessment_type"],
                data["module_code"],
                float(data["max_points"]),
                float(data["weight"]),
                data.get("due_date"),
                data.get("description", ""),
                data.get("duration_minutes", 0),
                now,
            ),
        )
        assessment_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM assessments WHERE assessment_id = ?", (assessment_id,)
        ).fetchone()

    log_activity("create", "assessment", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@assessment_bp.route("/<int:assessment_id>", methods=["PUT"])
@token_required
def update_assessment(assessment_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM assessments WHERE assessment_id = ?", (assessment_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Assessment {assessment_id} not found")

    data = request.get_json(silent=True) or {}
    validate_assessment_update(data)

    set_clauses = []
    values = []
    allowed = [
        "assessment_name", "assessment_type", "max_points", "weight",
        "due_date", "description", "duration_minutes", "status",
    ]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_clauses.append("updated_at = ?")
    values.append(now)
    values.append(assessment_id)

    with transaction() as conn:
        conn.execute(
            "UPDATE assessments SET " + ", ".join(set_clauses) + " WHERE assessment_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM assessments WHERE assessment_id = ?", (assessment_id,)
        ).fetchone()

    log_activity("update", "assessment", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))
