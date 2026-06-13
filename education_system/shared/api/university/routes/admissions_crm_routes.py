"""Admissions CRM routes: prospects, interactions, applications, and campus tours."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

admissions_crm_bp = Blueprint("admissions_crm", __name__, url_prefix="/api/admissions-crm")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- prospects ----

@admissions_crm_bp.route("/prospects", methods=["GET"])
@token_required
def list_prospects():
    search = request.args.get("search")
    status = request.args.get("status")
    intended_major = request.args.get("intended_major")

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
        if intended_major:
            conditions.append("intended_major = ?")
            params.append(intended_major)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM admission_prospects" + where + " ORDER BY prospect_id DESC LIMIT ? OFFSET ?",
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


@admissions_crm_bp.route("/prospects/<int:prospect_id>", methods=["GET"])
@token_required
def get_prospect(prospect_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM admission_prospects WHERE prospect_id = ?", (prospect_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"prospects {prospect_id} not found")
    log_activity("view", "admission_prospects", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@admissions_crm_bp.route("/prospects", methods=["POST"])
@token_required
def create_prospect():
    data = request.get_json(silent=True) or {}
    for field in ["first_name", "last_name", "email"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO admission_prospects
               (first_name, last_name, email, phone, date_of_birth, country, state, city, high_school, intended_major, source, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["first_name"], data["last_name"], data["email"], data.get("phone", ""), data.get("date_of_birth", ""), data.get("country", ""), data.get("state", ""), data.get("city", ""), data.get("high_school", ""), data.get("intended_major", ""), data.get("source", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM admission_prospects WHERE prospect_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "admission_prospects", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- tours ----

@admissions_crm_bp.route("/tours", methods=["GET"])
@token_required
def list_tours():
    tour_guide = request.args.get("tour_guide")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if tour_guide:
            conditions.append("tour_guide = ?")
            params.append(tour_guide)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM campus_tours" + where + " ORDER BY tour_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM campus_tours" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "campus_tours", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@admissions_crm_bp.route("/tours/<int:tour_id>", methods=["GET"])
@token_required
def get_tour(tour_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM campus_tours WHERE tour_id = ?", (tour_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"tours {tour_id} not found")
    log_activity("view", "campus_tours", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@admissions_crm_bp.route("/tours", methods=["POST"])
@token_required
def create_tour():
    data = request.get_json(silent=True) or {}
    for field in ["tour_date", "tour_time", "tour_guide", "max_attendees"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO campus_tours
               (tour_date, tour_time, tour_guide, max_attendees, meeting_point, duration_minutes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["tour_date"], data["tour_time"], data["tour_guide"], data["max_attendees"], data.get("meeting_point", ""), data.get("duration_minutes", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM campus_tours WHERE tour_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "campus_tours", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
