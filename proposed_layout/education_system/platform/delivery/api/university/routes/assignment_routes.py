"""Assignment routes: CRUD for assignments and submissions."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import token_required
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.platform.delivery.api.university.validators import (
    validate_assignment_create,
    validate_assignment_update,
    validate_submission_create,
)
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

assignment_bp = Blueprint("assignments", __name__, url_prefix="/api/assignments")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


def _get_assignment_or_404(assignment_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM assignments WHERE assignment_id = ?", (assignment_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Assignment {assignment_id} not found")
    return _row_to_dict(row)


@assignment_bp.route("", methods=["GET"])
@token_required
def list_assignments():
    module_code = request.args.get("module_code")

    with get_connection() as conn:
        if module_code:
            page, per_page, offset = get_pagination_params()
            rows = conn.execute(
                "SELECT * FROM assignments WHERE module_code = ? ORDER BY due_date LIMIT ? OFFSET ?",
                (module_code, per_page, offset),
            ).fetchall()
            total_row = conn.execute(
                "SELECT COUNT(*) FROM assignments WHERE module_code = ?", (module_code,)
            ).fetchone()
        else:
            page, per_page, offset = get_pagination_params()
            rows = conn.execute(
                "SELECT * FROM assignments ORDER BY due_date LIMIT ? OFFSET ?",
                (per_page, offset),
            ).fetchall()
            total_row = conn.execute("SELECT COUNT(*) FROM assignments").fetchone()

        total = total_row[0] if total_row else 0

    log_activity("view", "assignments", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@assignment_bp.route("/<int:assignment_id>", methods=["GET"])
@token_required
def get_assignment(assignment_id: int):
    assignment = _get_assignment_or_404(assignment_id)
    log_activity("view", "assignment", user=g.current_user.get("sub"))
    return jsonify(assignment)


@assignment_bp.route("", methods=["POST"])
@token_required
def create_assignment():
    data = request.get_json(silent=True) or {}
    validate_assignment_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO assignments
               (module_code, title, description, due_date, max_score,
                assignment_type, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["module_code"],
                data["title"],
                data.get("description", ""),
                data["due_date"],
                data.get("max_score", 100),
                data.get("assignment_type", "homework"),
                data.get("status", "active"),
                now,
                now,
            ),
        )
        assignment_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_activity("create", "assignment", user=g.current_user.get("sub"))
    return jsonify(_get_assignment_or_404(assignment_id)), 201


@assignment_bp.route("/<int:assignment_id>", methods=["PUT"])
@token_required
def update_assignment(assignment_id: int):
    _get_assignment_or_404(assignment_id)
    data = request.get_json(silent=True) or {}
    validate_assignment_update(data)

    set_clauses = []
    values = []
    allowed = [
        "title", "description", "due_date", "max_score",
        "assignment_type", "status",
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

    values.append(assignment_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE assignments SET " + ", ".join(set_clauses) + " WHERE assignment_id = ?",
            values,
        )

    log_activity("update", "assignment", user=g.current_user.get("sub"))
    return jsonify(_get_assignment_or_404(assignment_id))


@assignment_bp.route("/<int:assignment_id>/submissions", methods=["GET"])
@token_required
def list_submissions(assignment_id: int):
    _get_assignment_or_404(assignment_id)

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM assignment_submissions WHERE assignment_id = ? ORDER BY submitted_at DESC",
            (assignment_id,),
        ).fetchall()

    log_activity("view", "assignment_submissions", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@assignment_bp.route("/<int:assignment_id>/submissions", methods=["POST"])
@token_required
def create_submission(assignment_id: int):
    _get_assignment_or_404(assignment_id)
    data = request.get_json(silent=True) or {}
    validate_submission_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO assignment_submissions
               (assignment_id, student_id, content, file_path, submitted_at, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                assignment_id,
                data["student_id"],
                data.get("content", ""),
                data.get("file_path", ""),
                now,
                data.get("status", "submitted"),
            ),
        )
        submission_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM assignment_submissions WHERE submission_id = ?", (submission_id,)
        ).fetchone()

    log_activity("create", "assignment_submission", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
