"""Academics routes: degree programs and academic assessments."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import token_required
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

academics_domain_bp = Blueprint("academics_domain", __name__, url_prefix="/api/academics")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- programs ----

@academics_domain_bp.route("/programs", methods=["GET"])
@token_required
def list_programs():
    search = request.args.get("search")
    degree_level = request.args.get("degree_level")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM degree_programs WHERE program_name LIKE ? OR department LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if degree_level:
            conditions.append("degree_level = ?")
            params.append(degree_level)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM degree_programs" + where + " ORDER BY program_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM degree_programs" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "degree_programs", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@academics_domain_bp.route("/programs/<int:program_id>", methods=["GET"])
@token_required
def get_program(program_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM degree_programs WHERE program_id = ?", (program_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"programs {program_id} not found")
    log_activity("view", "degree_programs", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@academics_domain_bp.route("/programs", methods=["POST"])
@token_required
def create_program():
    data = request.get_json(silent=True) or {}
    for field in ["program_name", "degree_level", "department"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO degree_programs
               (program_name, degree_level, department, total_credits, description, duration_years, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["program_name"], data["degree_level"], data["department"], data.get("total_credits", ""), data.get("description", ""), data.get("duration_years", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM degree_programs WHERE program_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "degree_programs", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
