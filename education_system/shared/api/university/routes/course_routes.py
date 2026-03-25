"""Course routes: CRUD and waitlist management."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import validate_course_create, validate_course_update
from education_system.university_system.core.exceptions import CourseNotFoundError, ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

course_bp = Blueprint("courses", __name__, url_prefix="/api/courses")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


def _get_course_or_404(course_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM courses WHERE course_id = ?", (course_id,)
        ).fetchone()
    if not row:
        raise CourseNotFoundError(f"Course {course_id} not found")
    return _row_to_dict(row)


@course_bp.route("", methods=["GET"])
@token_required
def list_courses():
    search = request.args.get("search")
    department = request.args.get("department")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM courses WHERE course_code LIKE ? OR course_name LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        if department:
            rows = conn.execute(
                "SELECT * FROM courses WHERE department = ?", (department,)
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        page, per_page, offset = get_pagination_params()
        rows = conn.execute(
            "SELECT * FROM courses LIMIT ? OFFSET ?", (per_page, offset)
        ).fetchall()
        total_row = conn.execute("SELECT COUNT(*) FROM courses").fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "courses", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@course_bp.route("/<int:course_id>", methods=["GET"])
@token_required
def get_course(course_id: int):
    course = _get_course_or_404(course_id)
    log_activity("view", "course", user=g.current_user.get("sub"))
    return jsonify(course)


@course_bp.route("", methods=["POST"])
@token_required
def create_course():
    data = request.get_json(silent=True) or {}
    validate_course_create(data)

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM courses WHERE course_code = ?", (data["course_code"],)
        ).fetchone()
    if existing:
        raise ValidationError(f"Course {data['course_code']} already exists")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO courses
               (course_code, course_name, description, department, credits,
                max_capacity, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["course_code"],
                data["course_name"],
                data.get("description", ""),
                data.get("department", ""),
                data.get("credits", 0),
                data.get("max_capacity", 30),
                data.get("status", "active"),
                now,
                now,
            ),
        )
        course_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    log_activity("create", "course", user=g.current_user.get("sub"))
    return jsonify(_get_course_or_404(course_id)), 201


@course_bp.route("/<int:course_id>", methods=["PUT"])
@token_required
def update_course(course_id: int):
    _get_course_or_404(course_id)
    data = request.get_json(silent=True) or {}
    validate_course_update(data)

    set_clauses = []
    values = []
    allowed = [
        "course_name", "description", "department", "credits",
        "max_capacity", "status",
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

    values.append(course_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE courses SET " + ", ".join(set_clauses) + " WHERE course_id = ?",
            values,
        )

    log_activity("update", "course", user=g.current_user.get("sub"))
    return jsonify(_get_course_or_404(course_id))


@course_bp.route("/<int:course_id>/waitlist", methods=["GET"])
@token_required
def course_waitlist(course_id: int):
    _get_course_or_404(course_id)

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT cw.*, s.first_name, s.last_name
               FROM course_waitlist cw
               LEFT JOIN students s ON cw.student_id = s.student_id
               WHERE cw.course_id = ?
               ORDER BY cw.position""",
            (course_id,),
        ).fetchall()

    log_activity("view", "course_waitlist", user=g.current_user.get("sub"))
    return jsonify({"course_id": course_id, "waitlist": [_row_to_dict(r) for r in rows]})
