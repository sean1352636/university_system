"""Alumni routes: profiles, events, and donations."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import validate_alumni_donation_create, validate_alumni_update
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

alumni_bp = Blueprint("alumni", __name__, url_prefix="/api/alumni")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Profiles ----

@alumni_bp.route("", methods=["GET"])
@token_required
def list_alumni():
    search = request.args.get("search")
    graduation_year = request.args.get("graduation_year")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM alumni WHERE first_name LIKE ? OR last_name LIKE ? OR current_employer LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if graduation_year:
            conditions.append("graduation_year = ?")
            params.append(graduation_year)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM alumni" + where + " ORDER BY last_name, first_name LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM alumni" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "alumni", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@alumni_bp.route("/<alumni_id>", methods=["GET"])
@token_required
def get_alumni(alumni_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM alumni WHERE alumni_id = ?", (alumni_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Alumni {alumni_id} not found")
    log_activity("view", "alumni_profile", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@alumni_bp.route("/<alumni_id>", methods=["PUT"])
@token_required
def update_alumni(alumni_id: str):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM alumni WHERE alumni_id = ?", (alumni_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Alumni {alumni_id} not found")

    data = request.get_json(silent=True) or {}
    validate_alumni_update(data)

    set_clauses = []
    values = []
    allowed = [
        "email_address", "current_employer", "job_title", "industry",
        "address", "city", "country", "phone", "linkedin_url", "bio", "skills",
    ]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    values.append(alumni_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE alumni SET " + ", ".join(set_clauses) + " WHERE alumni_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM alumni WHERE alumni_id = ?", (alumni_id,)
        ).fetchone()

    log_activity("update", "alumni_profile", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Events ----

@alumni_bp.route("/events", methods=["GET"])
@token_required
def list_events():
    page, per_page, offset = get_pagination_params()

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_events ORDER BY event_date DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
        total_row = conn.execute("SELECT COUNT(*) FROM alumni_events").fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "alumni_events", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- Donations ----

@alumni_bp.route("/donations", methods=["GET"])
@token_required
def list_donations():
    alumni_id = request.args.get("alumni_id")

    with get_connection() as conn:
        if alumni_id:
            rows = conn.execute(
                "SELECT * FROM alumni_donations WHERE alumni_id = ? ORDER BY donation_date DESC",
                (alumni_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM alumni_donations ORDER BY donation_date DESC"
            ).fetchall()

    log_activity("view", "alumni_donations", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@alumni_bp.route("/donations", methods=["POST"])
@token_required
def create_donation():
    data = request.get_json(silent=True) or {}
    validate_alumni_donation_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO alumni_donations
               (alumni_id, donation_amount, donation_type, fund_designation,
                payment_method, is_recurring, recurrence_frequency)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data["alumni_id"],
                float(data["donation_amount"]),
                data["donation_type"],
                data.get("fund_designation", ""),
                data.get("payment_method", ""),
                data.get("is_recurring", 0),
                data.get("recurrence_frequency", ""),
            ),
        )
        donation_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM alumni_donations WHERE donation_id = ?", (donation_id,)
        ).fetchone()

    log_activity("create", "alumni_donation", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
