"""Academic integrity routes: misconduct cases, plagiarism results, AI detection, forensic cases."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import admin_required, token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import validate_misconduct_case_create
from education_system.post_18.university_system.core.exceptions import ValidationError
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

integrity_bp = Blueprint("integrity", __name__, url_prefix="/api/integrity")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Misconduct Cases ----

@integrity_bp.route("/misconduct", methods=["GET"])
@token_required
@admin_required
def list_misconduct_cases():
    status = request.args.get("status")
    severity = request.args.get("severity")
    student_id = request.args.get("student_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM academic_misconduct_cases" + where + " ORDER BY date_filed DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM academic_misconduct_cases" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "misconduct_cases", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@integrity_bp.route("/misconduct/<int:case_id>", methods=["GET"])
@token_required
def get_misconduct_case(case_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM academic_misconduct_cases WHERE id = ?", (case_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Misconduct case {case_id} not found")
    log_activity("view", "misconduct_case", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@integrity_bp.route("/misconduct", methods=["POST"])
@token_required
@admin_required
def create_misconduct_case():
    data = request.get_json(silent=True) or {}
    validate_misconduct_case_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    import uuid
    case_uid = f"MC-{uuid.uuid4().hex[:8].upper()}"

    with transaction() as conn:
        conn.execute(
            """INSERT INTO academic_misconduct_cases
               (case_id, student_name, student_id, student_email, course,
                violation_type, severity, status, date_filed, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'Under Review', ?, ?, ?)""",
            (
                case_uid,
                data["student_name"],
                data["student_id"],
                data.get("student_email"),
                data["course"],
                data["violation_type"],
                data["severity"],
                now,
                data.get("notes", ""),
                now,
            ),
        )
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM academic_misconduct_cases WHERE id = ?", (row_id,)
        ).fetchone()

    log_activity("create", "misconduct_case", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@integrity_bp.route("/misconduct/<int:case_id>", methods=["PUT"])
@token_required
@admin_required
def update_misconduct_case(case_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM academic_misconduct_cases WHERE id = ?", (case_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Misconduct case {case_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = [
        "status", "ruling", "ruling_rationale", "notes",
        "hearing_date", "hearing_time", "hearing_location",
    ]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    set_clauses.append("updated_at = datetime('now')")
    values.append(case_id)

    with transaction() as conn:
        conn.execute(
            "UPDATE academic_misconduct_cases SET " + ", ".join(set_clauses) + " WHERE id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM academic_misconduct_cases WHERE id = ?", (case_id,)
        ).fetchone()

    log_activity("update", "misconduct_case", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Plagiarism Results ----

@integrity_bp.route("/plagiarism", methods=["GET"])
@token_required
def list_plagiarism_results():
    status = request.args.get("status")

    with get_connection() as conn:
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
            "SELECT * FROM plagiarism_results" + where + " ORDER BY check_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM plagiarism_results" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "plagiarism_results", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- AI Detection Results ----

@integrity_bp.route("/ai-detection", methods=["GET"])
@token_required
def list_ai_detection_results():
    with get_connection() as conn:
        page, per_page, offset = get_pagination_params()
        rows = conn.execute(
            "SELECT * FROM ai_detector_results ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
        total_row = conn.execute("SELECT COUNT(*) FROM ai_detector_results").fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "ai_detection_results", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- Forensic Cases ----

@integrity_bp.route("/forensic", methods=["GET"])
@token_required
@admin_required
def list_forensic_cases():
    status = request.args.get("status")
    priority = request.args.get("priority")

    with get_connection() as conn:
        conditions = []
        params: list = []
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
            "SELECT * FROM forensic_cases" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM forensic_cases" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "forensic_cases", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@integrity_bp.route("/forensic/<case_id>", methods=["GET"])
@token_required
def get_forensic_case(case_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM forensic_cases WHERE case_id = ?", (case_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Forensic case {case_id} not found")
    log_activity("view", "forensic_case", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))
