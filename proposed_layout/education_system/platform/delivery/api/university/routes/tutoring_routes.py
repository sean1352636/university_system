"""Tutoring routes: peer tutoring offers."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import token_required
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.platform.delivery.api.university.validators import validate_tutoring_offer_create
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

tutoring_bp = Blueprint("tutoring", __name__, url_prefix="/api/tutoring")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


@tutoring_bp.route("/offers", methods=["GET"])
@token_required
def list_offers():
    subject = request.args.get("subject")
    search = request.args.get("search")
    tutor_id = request.args.get("tutor_id")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM tutoring_offers WHERE status = 'available' AND (subject LIKE ? OR topic LIKE ? OR description LIKE ?)",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if subject:
            conditions.append("subject = ?")
            params.append(subject)
        if tutor_id:
            conditions.append("tutor_id = ?")
            params.append(tutor_id)
        else:
            conditions.append("status = 'available'")

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM tutoring_offers" + where + " ORDER BY rating DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM tutoring_offers" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "tutoring_offers", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@tutoring_bp.route("/offers/<int:offer_id>", methods=["GET"])
@token_required
def get_offer(offer_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM tutoring_offers WHERE offer_id = ?", (offer_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Tutoring offer {offer_id} not found")
    log_activity("view", "tutoring_offer", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@tutoring_bp.route("/offers", methods=["POST"])
@token_required
def create_offer():
    data = request.get_json(silent=True) or {}
    validate_tutoring_offer_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO tutoring_offers
               (tutor_id, subject, topic, hourly_rate, availability,
                experience_level, description, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'available')""",
            (
                data["tutor_id"],
                data["subject"],
                data.get("topic", ""),
                data.get("hourly_rate", 0),
                data.get("availability", ""),
                data.get("experience_level", ""),
                data.get("description", ""),
            ),
        )
        offer_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM tutoring_offers WHERE offer_id = ?", (offer_id,)
        ).fetchone()

    log_activity("create", "tutoring_offer", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@tutoring_bp.route("/offers/<int:offer_id>", methods=["PUT"])
@token_required
def update_offer(offer_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM tutoring_offers WHERE offer_id = ?", (offer_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Tutoring offer {offer_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = [
        "subject", "topic", "hourly_rate", "availability",
        "experience_level", "description", "status",
    ]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    values.append(offer_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE tutoring_offers SET " + ", ".join(set_clauses) + " WHERE offer_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM tutoring_offers WHERE offer_id = ?", (offer_id,)
        ).fetchone()

    log_activity("update", "tutoring_offer", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))
