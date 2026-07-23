"""Scholarship finder routes: opportunities, profiles, and applications."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.post_18.university_system.core.exceptions import ValidationError
from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

scholarship_finder_bp = Blueprint("scholarship_finder", __name__, url_prefix="/api/scholarship-finder")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- opportunities ----

@scholarship_finder_bp.route("/opportunities", methods=["GET"])
@token_required
def list_opportunities():
    search = request.args.get("search")
    academic_level = request.args.get("academic_level")
    award_type = request.args.get("award_type")
    is_active = request.args.get("is_active")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM scholarship_opportunities WHERE scholarship_name LIKE ? OR organization LIKE ? OR description LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if academic_level:
            conditions.append("academic_level = ?")
            params.append(academic_level)
        if award_type:
            conditions.append("award_type = ?")
            params.append(award_type)
        if is_active:
            conditions.append("is_active = ?")
            params.append(is_active)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM scholarship_opportunities" + where + " ORDER BY scholarship_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM scholarship_opportunities" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "scholarship_opportunities", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@scholarship_finder_bp.route("/opportunities/<int:scholarship_id>", methods=["GET"])
@token_required
def get_opportunitie(scholarship_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM scholarship_opportunities WHERE scholarship_id = ?", (scholarship_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"opportunities {scholarship_id} not found")
    log_activity("view", "scholarship_opportunities", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@scholarship_finder_bp.route("/opportunities", methods=["POST"])
@token_required
def create_opportunitie():
    data = request.get_json(silent=True) or {}
    for field in ["scholarship_name", "organization", "award_amount_min"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO scholarship_opportunities
               (scholarship_name, organization, award_amount_min, award_amount_max, award_type, description, eligibility_criteria, academic_level, application_deadline, application_url, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["scholarship_name"], data["organization"], data["award_amount_min"], data.get("award_amount_max", ""), data.get("award_type", ""), data.get("description", ""), data.get("eligibility_criteria", ""), data.get("academic_level", ""), data.get("application_deadline", ""), data.get("application_url", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM scholarship_opportunities WHERE scholarship_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "scholarship_opportunities", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- applications ----

@scholarship_finder_bp.route("/applications", methods=["GET"])
@token_required
def list_applications():
    scholarship_id = request.args.get("scholarship_id")
    student_id = request.args.get("student_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if scholarship_id:
            conditions.append("scholarship_id = ?")
            params.append(scholarship_id)
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
            "SELECT * FROM student_scholarship_applications" + where + " ORDER BY application_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM student_scholarship_applications" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "student_scholarship_applications", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@scholarship_finder_bp.route("/applications/<int:application_id>", methods=["GET"])
@token_required
def get_application(application_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_scholarship_applications WHERE application_id = ?", (application_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"applications {application_id} not found")
    log_activity("view", "student_scholarship_applications", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@scholarship_finder_bp.route("/applications", methods=["POST"])
@token_required
def create_application():
    data = request.get_json(silent=True) or {}
    for field in ["scholarship_id", "student_id"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO student_scholarship_applications
               (scholarship_id, student_id, deadline_date, notes, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (data["scholarship_id"], data["student_id"], data.get("deadline_date", ""), data.get("notes", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_scholarship_applications WHERE application_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "student_scholarship_applications", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
