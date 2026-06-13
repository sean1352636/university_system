"""Grade routes: record, list, update.

Actual ``grades`` table schema:
  grade_id (PK), student_id, assessment_id, score, letter_grade,
  submission_date, comments
"""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.validators import validate_grade_create, validate_grade_update
from education_system.university_system.core.exceptions import GradeNotFoundError, ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

grade_bp = Blueprint("grades", __name__, url_prefix="/api/grades")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


@grade_bp.route("", methods=["GET"])
@token_required
def list_grades():
    student_id = request.args.get("student_id")
    assessment_id = request.args.get("assessment_id")

    clauses = []
    params = []
    if student_id:
        clauses.append("student_id = ?")
        params.append(student_id)
    if assessment_id:
        clauses.append("assessment_id = ?")
        params.append(assessment_id)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM grades" + where, params).fetchall()

    log_activity("view", "grades", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@grade_bp.route("", methods=["POST"])
@token_required
def record_grade():
    data = request.get_json(silent=True) or {}
    validate_grade_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO grades
               (student_id, assessment_id, score, letter_grade, submission_date, comments)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                data["student_id"],
                data.get("assessment_id"),
                data.get("score"),
                data.get("letter_grade", ""),
                now,
                data.get("comments", ""),
            ),
        )

    # Retrieve the newly inserted grade
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM grades WHERE student_id = ? ORDER BY grade_id DESC LIMIT 1",
            (data["student_id"],),
        ).fetchone()

    log_activity("create", "grade", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@grade_bp.route("/<int:grade_id>", methods=["PUT"])
@token_required
def update_grade(grade_id: int):
    data = request.get_json(silent=True) or {}
    validate_grade_update(data)

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM grades WHERE grade_id = ?", (grade_id,)
        ).fetchone()
    if not existing:
        raise GradeNotFoundError(f"Grade {grade_id} not found")

    set_clauses = []
    values = []
    allowed = ["score", "letter_grade", "comments"]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    values.append(grade_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE grades SET " + ", ".join(set_clauses) + " WHERE grade_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM grades WHERE grade_id = ?", (grade_id,)
        ).fetchone()

    log_activity("update", "grade", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))
