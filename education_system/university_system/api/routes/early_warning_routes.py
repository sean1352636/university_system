"""Early warning routes: student risk profiles and interventions."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from education_system.university_system.api.auth import admin_required, token_required
from education_system.university_system.api.pagination import get_pagination_params, paginated_response
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

early_warning_bp = Blueprint("early_warning", __name__, url_prefix="/api/early-warning")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Risk Profiles ----

@early_warning_bp.route("/profiles", methods=["GET"])
@token_required
@admin_required
def list_profiles():
    risk_level = request.args.get("risk_level")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if risk_level:
            conditions.append("risk_level = ?")
            params.append(risk_level)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM early_warning_profiles" + where + " ORDER BY overall_risk_score DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM early_warning_profiles" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "early_warning_profiles", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@early_warning_bp.route("/profiles/<student_id>", methods=["GET"])
@token_required
def get_profile(student_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM early_warning_profiles WHERE student_id = ?", (student_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Early warning profile for student {student_id} not found")
    log_activity("view", "early_warning_profile", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Interventions ----

@early_warning_bp.route("/interventions", methods=["GET"])
@token_required
def list_interventions():
    student_id = request.args.get("student_id")
    status = request.args.get("status")
    priority = request.args.get("priority")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if priority:
            conditions.append("priority = ?")
            params.append(priority)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM early_warning_interventions" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM early_warning_interventions" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "early_warning_interventions", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@early_warning_bp.route("/interventions", methods=["POST"])
@token_required
@admin_required
def create_intervention():
    data = request.get_json(silent=True) or {}
    required = ["student_id", "trigger_type", "intervention_type", "priority"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO early_warning_interventions
               (student_id, trigger_type, intervention_type, priority,
                status, assigned_to, description, scheduled_date, notes)
               VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?)""",
            (
                data["student_id"],
                data["trigger_type"],
                data["intervention_type"],
                data["priority"],
                data.get("assigned_to"),
                data.get("description", ""),
                data.get("scheduled_date"),
                data.get("notes", ""),
            ),
        )
        intervention_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM early_warning_interventions WHERE intervention_id = ?",
            (intervention_id,),
        ).fetchone()

    log_activity("create", "early_warning_intervention", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@early_warning_bp.route("/interventions/<int:intervention_id>", methods=["PUT"])
@token_required
def update_intervention(intervention_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM early_warning_interventions WHERE intervention_id = ?",
            (intervention_id,),
        ).fetchone()
    if not existing:
        raise ValidationError(f"Intervention {intervention_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = [
        "status", "assigned_to", "description", "scheduled_date",
        "completed_date", "outcome", "notes",
    ]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    set_clauses.append("updated_at = datetime('now')")
    values.append(intervention_id)

    with transaction() as conn:
        conn.execute(
            "UPDATE early_warning_interventions SET " + ", ".join(set_clauses) + " WHERE intervention_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM early_warning_interventions WHERE intervention_id = ?",
            (intervention_id,),
        ).fetchone()

    log_activity("update", "early_warning_intervention", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))
