"""LMS routes: courses, quizzes, discussion forums, video lectures, gradebook."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import (
    validate_lms_course_create,
    validate_lms_forum_create,
    validate_lms_quiz_create,
)
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

lms_bp = Blueprint("lms", __name__, url_prefix="/api/lms")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- LMS Courses ----

@lms_bp.route("/courses", methods=["GET"])
@token_required
def list_courses():
    module_code = request.args.get("module_code")
    instructor_id = request.args.get("instructor_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if module_code:
            conditions.append("module_code = ?")
            params.append(module_code)
        if instructor_id:
            conditions.append("instructor_id = ?")
            params.append(instructor_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM lms_courses" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM lms_courses" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "lms_courses", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@lms_bp.route("/courses/<int:course_id>", methods=["GET"])
@token_required
def get_course(course_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM lms_courses WHERE lms_course_id = ?", (course_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"LMS course {course_id} not found")
    log_activity("view", "lms_course", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@lms_bp.route("/courses", methods=["POST"])
@token_required
def create_course():
    data = request.get_json(silent=True) or {}
    validate_lms_course_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO lms_courses
               (module_code, instructor_id, course_description, syllabus_url,
                start_date, end_date, enrollment_limit, is_published)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["module_code"],
                data["instructor_id"],
                data.get("course_description", ""),
                data.get("syllabus_url"),
                data.get("start_date"),
                data.get("end_date"),
                data.get("enrollment_limit", 0),
                data.get("is_published", 0),
            ),
        )
        cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM lms_courses WHERE lms_course_id = ?", (cid,)
        ).fetchone()

    log_activity("create", "lms_course", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@lms_bp.route("/courses/<int:course_id>", methods=["PUT"])
@token_required
def update_course(course_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM lms_courses WHERE lms_course_id = ?", (course_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"LMS course {course_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = [
        "course_description", "syllabus_url", "start_date", "end_date",
        "enrollment_limit", "is_published",
    ]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    set_clauses.append("updated_at = datetime('now')")
    values.append(course_id)

    with transaction() as conn:
        conn.execute(
            "UPDATE lms_courses SET " + ", ".join(set_clauses) + " WHERE lms_course_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM lms_courses WHERE lms_course_id = ?", (course_id,)
        ).fetchone()

    log_activity("update", "lms_course", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Quizzes ----

@lms_bp.route("/courses/<int:course_id>/quizzes", methods=["GET"])
@token_required
def list_quizzes(course_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM lms_quizzes WHERE lms_course_id = ? ORDER BY created_at DESC",
            (course_id,),
        ).fetchall()

    log_activity("view", "lms_quizzes", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@lms_bp.route("/quizzes", methods=["POST"])
@token_required
def create_quiz():
    data = request.get_json(silent=True) or {}
    validate_lms_quiz_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO lms_quizzes
               (lms_course_id, title, description, duration_minutes,
                passing_score, max_attempts, available_from, available_until, is_published)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["lms_course_id"],
                data["title"],
                data.get("description", ""),
                data.get("duration_minutes", 60),
                data.get("passing_score", 70.0),
                data.get("max_attempts", 1),
                data.get("available_from"),
                data.get("available_until"),
                data.get("is_published", 0),
            ),
        )
        qid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM lms_quizzes WHERE quiz_id = ?", (qid,)
        ).fetchone()

    log_activity("create", "lms_quiz", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Discussion Forums ----

@lms_bp.route("/courses/<int:course_id>/forums", methods=["GET"])
@token_required
def list_forums(course_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM lms_discussion_forums WHERE lms_course_id = ? ORDER BY is_pinned DESC, created_at DESC",
            (course_id,),
        ).fetchall()

    log_activity("view", "lms_forums", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@lms_bp.route("/forums", methods=["POST"])
@token_required
def create_forum():
    data = request.get_json(silent=True) or {}
    validate_lms_forum_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO lms_discussion_forums
               (lms_course_id, topic, description, created_by)
               VALUES (?, ?, ?, ?)""",
            (
                data["lms_course_id"],
                data["topic"],
                data.get("description", ""),
                g.current_user.get("sub"),
            ),
        )
        fid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM lms_discussion_forums WHERE forum_id = ?", (fid,)
        ).fetchone()

    log_activity("create", "lms_forum", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Video Lectures ----

@lms_bp.route("/videos", methods=["GET"])
@token_required
def list_videos():
    with get_connection() as conn:
        page, per_page, offset = get_pagination_params()
        rows = conn.execute(
            "SELECT * FROM lms_video_lectures ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
        total_row = conn.execute("SELECT COUNT(*) FROM lms_video_lectures").fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "lms_videos", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- Gradebook ----

@lms_bp.route("/gradebook", methods=["GET"])
@token_required
def list_gradebook():
    course_id = request.args.get("course_id")
    student_id = request.args.get("student_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if course_id:
            conditions.append("lms_course_id = ?")
            params.append(course_id)
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM lms_gradebook" + where + " ORDER BY graded_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM lms_gradebook" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "lms_gradebook", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))
