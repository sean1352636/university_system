"""Enrollment routes: enroll, drop, list.

The actual table is ``student_modules`` with columns:
  id, student_id, module_code, enrollment_date, status,
  module_type, module_name, grade, completion_date
"""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.university_system.api.auth import token_required
from education_system.university_system.api.validators import validate_enrollment_create
from education_system.university_system.core.exceptions import (
    AlreadyEnrolledError,
    CourseNotFoundError,
    StudentNotFoundError,
    ValidationError,
)
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

enrollment_bp = Blueprint("enrollments", __name__, url_prefix="/api/enrollments")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


@enrollment_bp.route("", methods=["GET"])
@token_required
def list_enrollments():
    student_id = request.args.get("student_id")
    module_code = request.args.get("module_code")

    clauses = []
    params = []
    if student_id:
        clauses.append("student_id = ?")
        params.append(student_id)
    if module_code:
        clauses.append("module_code = ?")
        params.append(module_code)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM student_modules" + where, params
        ).fetchall()

    log_activity("view", "enrollments", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@enrollment_bp.route("", methods=["POST"])
@token_required
def enroll():
    data = request.get_json(silent=True) or {}
    validate_enrollment_create(data)

    student_id = data["student_id"]
    module_code = data["module_code"]

    with get_connection() as conn:
        # Verify student exists
        if not conn.execute(
            "SELECT 1 FROM students WHERE student_id = ?", (student_id,)
        ).fetchone():
            raise StudentNotFoundError(student_id)

        # Verify module exists
        if not conn.execute(
            "SELECT 1 FROM modules WHERE module_code = ?", (module_code,)
        ).fetchone():
            raise CourseNotFoundError(f"Module {module_code} not found")

        # Check duplicate
        if conn.execute(
            "SELECT 1 FROM student_modules WHERE student_id = ? AND module_code = ?",
            (student_id, module_code),
        ).fetchone():
            raise AlreadyEnrolledError(
                f"Student {student_id} is already enrolled in {module_code}"
            )

    now = datetime.now().strftime("%Y-%m-%d")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO student_modules
               (student_id, module_code, enrollment_date, status, module_type)
               VALUES (?, ?, ?, ?, ?)""",
            (student_id, module_code, now, "Enrolled", data.get("module_type", "Standard")),
        )

    # Fetch the newly created enrollment
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_modules WHERE student_id = ? AND module_code = ? ORDER BY id DESC LIMIT 1",
            (student_id, module_code),
        ).fetchone()

    log_activity("create", "enrollment", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@enrollment_bp.route("/<int:enrollment_id>", methods=["DELETE"])
@token_required
def drop_enrollment(enrollment_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_modules WHERE id = ?", (enrollment_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Enrollment {enrollment_id} not found")

    with transaction() as conn:
        conn.execute("DELETE FROM student_modules WHERE id = ?", (enrollment_id,))

    log_activity("delete", "enrollment", user=g.current_user.get("sub"))
    return jsonify({"message": f"Enrollment {enrollment_id} dropped"})
