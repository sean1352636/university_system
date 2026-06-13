"""Exam routes: scheduling and accommodations."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import validate_exam_create, validate_exam_update
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

exam_bp = Blueprint("exams", __name__, url_prefix="/api/exams")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


@exam_bp.route("", methods=["GET"])
@token_required
def list_exams():
    module_code = request.args.get("module_code")
    upcoming = request.args.get("upcoming")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if module_code:
            conditions.append("module_code = ?")
            params.append(module_code)
        if upcoming:
            conditions.append("date >= ?")
            params.append(datetime.now().strftime("%Y-%m-%d"))

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM exams" + where + " ORDER BY date, start_time LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM exams" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "exams", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@exam_bp.route("/<int:exam_id>", methods=["GET"])
@token_required
def get_exam(exam_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()
    if not row:
        raise ValidationError(f"Exam {exam_id} not found")
    log_activity("view", "exam", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@exam_bp.route("", methods=["POST"])
@token_required
def create_exam():
    data = request.get_json(silent=True) or {}
    validate_exam_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO exams
               (module_code, module_name, date, start_time, end_time,
                room, instructor_id, instructor_name, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["module_code"],
                data.get("module_name", ""),
                data["date"],
                data["start_time"],
                data["end_time"],
                data.get("room", ""),
                data.get("instructor_id"),
                data.get("instructor_name", ""),
                now,
                now,
            ),
        )
        exam_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()

    log_activity("create", "exam", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@exam_bp.route("/<int:exam_id>", methods=["PUT"])
@token_required
def update_exam(exam_id: int):
    with get_connection() as conn:
        existing = conn.execute("SELECT 1 FROM exams WHERE id = ?", (exam_id,)).fetchone()
    if not existing:
        raise ValidationError(f"Exam {exam_id} not found")

    data = request.get_json(silent=True) or {}
    validate_exam_update(data)

    set_clauses = []
    values = []
    allowed = [
        "module_code", "module_name", "date", "start_time", "end_time",
        "room", "instructor_id", "instructor_name",
    ]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_clauses.append("updated_at = ?")
    values.append(now)
    values.append(exam_id)

    with transaction() as conn:
        conn.execute(
            "UPDATE exams SET " + ", ".join(set_clauses) + " WHERE id = ?", values
        )

    with get_connection() as conn:
        row = conn.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()

    log_activity("update", "exam", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Accommodations ----

@exam_bp.route("/<int:exam_id>/accommodations", methods=["GET"])
@token_required
def list_accommodations(exam_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM exam_accommodations WHERE exam_id = ?", (exam_id,)
        ).fetchall()

    log_activity("view", "exam_accommodations", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})
