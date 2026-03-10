"""Club routes: student clubs and memberships."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.university_system.api.auth import token_required
from education_system.university_system.api.pagination import get_pagination_params, paginated_response
from education_system.university_system.api.validators import validate_club_create, validate_club_member_create
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

club_bp = Blueprint("clubs", __name__, url_prefix="/api/clubs")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


@club_bp.route("", methods=["GET"])
@token_required
def list_clubs():
    search = request.args.get("search")
    category = request.args.get("category")
    status = request.args.get("status", "active")

    with get_connection() as conn:
        if search:
            pattern = f"%{search}%"
            rows = conn.execute(
                "SELECT * FROM student_clubs WHERE club_name LIKE ? OR description LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if category:
            conditions.append("category = ?")
            params.append(category)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM student_clubs" + where + " ORDER BY club_name LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM student_clubs" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "clubs", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@club_bp.route("/<int:club_id>", methods=["GET"])
@token_required
def get_club(club_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_clubs WHERE club_id = ?", (club_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Club {club_id} not found")
    log_activity("view", "club", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@club_bp.route("", methods=["POST"])
@token_required
def create_club():
    data = request.get_json(silent=True) or {}
    validate_club_create(data)

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM student_clubs WHERE club_name = ?", (data["club_name"],)
        ).fetchone()
    if existing:
        raise ValidationError(f"Club '{data['club_name']}' already exists")

    now = datetime.now().strftime("%Y-%m-%d")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO student_clubs
               (club_name, description, category, president_id, status, created_date)
               VALUES (?, ?, ?, ?, 'active', ?)""",
            (
                data["club_name"],
                data.get("description", ""),
                data.get("category", ""),
                data.get("president_id"),
                now,
            ),
        )
        club_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_clubs WHERE club_id = ?", (club_id,)
        ).fetchone()

    log_activity("create", "club", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@club_bp.route("/<int:club_id>", methods=["PUT"])
@token_required
def update_club(club_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM student_clubs WHERE club_id = ?", (club_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Club {club_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = [
        "club_name", "description", "category", "president_id",
        "treasurer_id", "secretary_id", "status",
    ]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    values.append(club_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE student_clubs SET " + ", ".join(set_clauses) + " WHERE club_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_clubs WHERE club_id = ?", (club_id,)
        ).fetchone()

    log_activity("update", "club", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Members ----

@club_bp.route("/<int:club_id>/members", methods=["GET"])
@token_required
def list_members(club_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM student_clubs WHERE club_id = ?", (club_id,)
        ).fetchone()
        if not existing:
            raise ValidationError(f"Club {club_id} not found")

        rows = conn.execute(
            """SELECT cm.*, s.first_name, s.last_name
               FROM club_members cm
               LEFT JOIN students s ON cm.student_id = s.student_id
               WHERE cm.club_id = ?
               ORDER BY cm.join_date""",
            (club_id,),
        ).fetchall()

    log_activity("view", "club_members", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@club_bp.route("/<int:club_id>/members", methods=["POST"])
@token_required
def add_member(club_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM student_clubs WHERE club_id = ?", (club_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Club {club_id} not found")

    data = request.get_json(silent=True) or {}
    validate_club_member_create(data)

    now = datetime.now().strftime("%Y-%m-%d")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO club_members (club_id, student_id, role, join_date)
               VALUES (?, ?, ?, ?)""",
            (club_id, data["student_id"], data.get("role", "member"), now),
        )
        member_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute(
            "UPDATE student_clubs SET member_count = member_count + 1 WHERE club_id = ?",
            (club_id,),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM club_members WHERE member_id = ?", (member_id,)
        ).fetchone()

    log_activity("create", "club_member", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
