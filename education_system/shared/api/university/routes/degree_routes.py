"""Degree program routes: programs, requirements, and prerequisites."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import admin_required, token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import (
    validate_degree_program_create,
    validate_degree_program_update,
    validate_prerequisite_create,
)
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

degree_bp = Blueprint("degrees", __name__, url_prefix="/api/degrees")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Programs ----

@degree_bp.route("/programs", methods=["GET"])
@token_required
def list_programs():
    department = request.args.get("department")
    degree_type = request.args.get("degree_type")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM degree_programs WHERE is_active = 1 AND (program_name LIKE ? OR program_code LIKE ?)",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = ["is_active = 1"]
        params: list = []
        if department:
            conditions.append("department = ?")
            params.append(department)
        if degree_type:
            conditions.append("degree_type = ?")
            params.append(degree_type)

        where = " WHERE " + " AND ".join(conditions)
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM degree_programs" + where + " ORDER BY program_name LIMIT ? OFFSET ?",
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


@degree_bp.route("/programs/<int:program_id>", methods=["GET"])
@token_required
def get_program(program_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM degree_programs WHERE program_id = ?", (program_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Degree program {program_id} not found")
    log_activity("view", "degree_program", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@degree_bp.route("/programs", methods=["POST"])
@token_required
@admin_required
def create_program():
    data = request.get_json(silent=True) or {}
    validate_degree_program_create(data)

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM degree_programs WHERE program_code = ?", (data["program_code"],)
        ).fetchone()
    if existing:
        raise ValidationError(f"Program {data['program_code']} already exists")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO degree_programs
               (program_code, program_name, degree_type, department,
                total_credits_required, min_gpa_required, max_years_allowed, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["program_code"],
                data["program_name"],
                data["degree_type"],
                data.get("department", ""),
                int(data["total_credits_required"]),
                data.get("min_gpa_required", 2.0),
                data.get("max_years_allowed", 4),
                data.get("description", ""),
            ),
        )
        program_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM degree_programs WHERE program_id = ?", (program_id,)
        ).fetchone()

    log_activity("create", "degree_program", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@degree_bp.route("/programs/<int:program_id>", methods=["PUT"])
@token_required
@admin_required
def update_program(program_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM degree_programs WHERE program_id = ?", (program_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Degree program {program_id} not found")

    data = request.get_json(silent=True) or {}
    validate_degree_program_update(data)

    set_clauses = []
    values = []
    allowed = [
        "program_name", "degree_type", "department", "total_credits_required",
        "min_gpa_required", "max_years_allowed", "description", "is_active",
    ]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    values.append(program_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE degree_programs SET " + ", ".join(set_clauses) + " WHERE program_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM degree_programs WHERE program_id = ?", (program_id,)
        ).fetchone()

    log_activity("update", "degree_program", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Requirements ----

@degree_bp.route("/programs/<int:program_id>/requirements", methods=["GET"])
@token_required
def list_requirements(program_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM degree_programs WHERE program_id = ?", (program_id,)
        ).fetchone()
        if not existing:
            raise ValidationError(f"Degree program {program_id} not found")

        rows = conn.execute(
            "SELECT * FROM degree_requirements WHERE program_id = ? ORDER BY display_order",
            (program_id,),
        ).fetchall()

    log_activity("view", "degree_requirements", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- Course Prerequisites ----

@degree_bp.route("/prerequisites", methods=["GET"])
@token_required
def list_prerequisites():
    course_id = request.args.get("course_id")
    if not course_id:
        raise ValidationError("'course_id' query parameter is required")

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM course_prerequisites WHERE course_id = ?", (course_id,)
        ).fetchall()

    log_activity("view", "course_prerequisites", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@degree_bp.route("/prerequisites", methods=["POST"])
@token_required
@admin_required
def create_prerequisite():
    data = request.get_json(silent=True) or {}
    validate_prerequisite_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO course_prerequisites
               (course_id, prerequisite_course_id, is_required, created_at)
               VALUES (?, ?, ?, ?)""",
            (
                data["course_id"],
                data["prerequisite_course_id"],
                data.get("is_required", 1),
                now,
            ),
        )
        prereq_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM course_prerequisites WHERE id = ?", (prereq_id,)
        ).fetchone()

    log_activity("create", "course_prerequisite", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@degree_bp.route("/prerequisites/<int:prereq_id>", methods=["DELETE"])
@token_required
@admin_required
def delete_prerequisite(prereq_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM course_prerequisites WHERE id = ?", (prereq_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Prerequisite {prereq_id} not found")

    with transaction() as conn:
        conn.execute("DELETE FROM course_prerequisites WHERE id = ?", (prereq_id,))

    log_activity("delete", "course_prerequisite", user=g.current_user.get("sub"))
    return jsonify({"message": f"Prerequisite {prereq_id} deleted"})
