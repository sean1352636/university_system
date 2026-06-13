"""Mentorship routes: relationships and sessions."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import validate_mentorship_create, validate_mentorship_session_create
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

mentorship_bp = Blueprint("mentorship", __name__, url_prefix="/api/mentorship")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Relationships ----

@mentorship_bp.route("/relationships", methods=["GET"])
@token_required
def list_relationships():
    mentor_id = request.args.get("mentor_id")
    mentee_id = request.args.get("mentee_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if mentor_id:
            conditions.append("mentor_id = ?")
            params.append(mentor_id)
        if mentee_id:
            conditions.append("mentee_id = ?")
            params.append(mentee_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM mentorship_relationships" + where + " ORDER BY start_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM mentorship_relationships" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "mentorship_relationships", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@mentorship_bp.route("/relationships/<int:relationship_id>", methods=["GET"])
@token_required
def get_relationship(relationship_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM mentorship_relationships WHERE relationship_id = ?",
            (relationship_id,),
        ).fetchone()
    if not row:
        raise ValidationError(f"Mentorship relationship {relationship_id} not found")
    log_activity("view", "mentorship_relationship", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@mentorship_bp.route("/relationships", methods=["POST"])
@token_required
def create_relationship():
    data = request.get_json(silent=True) or {}
    validate_mentorship_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO mentorship_relationships
               (mentor_id, mentee_id, skill_area, start_date, status, notes)
               VALUES (?, ?, ?, date('now'), 'active', ?)""",
            (
                data["mentor_id"],
                data["mentee_id"],
                data["skill_area"],
                data.get("notes", ""),
            ),
        )
        rel_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM mentorship_relationships WHERE relationship_id = ?", (rel_id,)
        ).fetchone()

    log_activity("create", "mentorship_relationship", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@mentorship_bp.route("/relationships/<int:relationship_id>", methods=["PUT"])
@token_required
def update_relationship(relationship_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM mentorship_relationships WHERE relationship_id = ?",
            (relationship_id,),
        ).fetchone()
    if not existing:
        raise ValidationError(f"Mentorship relationship {relationship_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = ["status", "end_date", "mentor_rating", "mentee_rating", "notes"]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    values.append(relationship_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE mentorship_relationships SET " + ", ".join(set_clauses) + " WHERE relationship_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM mentorship_relationships WHERE relationship_id = ?",
            (relationship_id,),
        ).fetchone()

    log_activity("update", "mentorship_relationship", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Sessions ----

@mentorship_bp.route("/relationships/<int:relationship_id>/sessions", methods=["GET"])
@token_required
def list_sessions(relationship_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM mentorship_sessions WHERE relationship_id = ? ORDER BY session_date DESC",
            (relationship_id,),
        ).fetchall()

    log_activity("view", "mentorship_sessions", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@mentorship_bp.route("/sessions", methods=["POST"])
@token_required
def create_session():
    data = request.get_json(silent=True) or {}
    validate_mentorship_session_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO mentorship_sessions
               (relationship_id, session_date, duration_minutes, notes,
                mentor_feedback, mentee_feedback, progress_rating)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data["relationship_id"],
                data["session_date"],
                data["duration_minutes"],
                data.get("notes", ""),
                data.get("mentor_feedback", ""),
                data.get("mentee_feedback", ""),
                data.get("progress_rating"),
            ),
        )
        session_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM mentorship_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()

    log_activity("create", "mentorship_session", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
