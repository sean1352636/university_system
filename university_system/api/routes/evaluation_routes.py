"""Evaluation routes: feedback submissions, evaluation templates, surveys, course evaluations."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from university_system.api.auth import admin_required, token_required
from university_system.api.pagination import get_pagination_params, paginated_response
from university_system.api.validators import (
    validate_course_evaluation_create,
    validate_feedback_create,
)
from university_system.core.exceptions import ValidationError
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

evaluation_bp = Blueprint("evaluations", __name__, url_prefix="/api/evaluations")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Feedback Submissions ----

@evaluation_bp.route("/feedback", methods=["GET"])
@token_required
def list_feedback():
    status = request.args.get("status")
    category_id = request.args.get("category_id")
    feedback_type = request.args.get("type")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if category_id:
            conditions.append("category_id = ?")
            params.append(category_id)
        if feedback_type:
            conditions.append("type = ?")
            params.append(feedback_type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM feedback_submissions" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM feedback_submissions" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "feedback_submissions", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@evaluation_bp.route("/feedback", methods=["POST"])
@token_required
def create_feedback():
    data = request.get_json(silent=True) or {}
    validate_feedback_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO feedback_submissions
               (user_id, category_id, type, title, description, is_anonymous, priority)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("user_id", g.current_user.get("sub")),
                data["category_id"],
                data["type"],
                data["title"],
                data["description"],
                data.get("is_anonymous", 0),
                data.get("priority", "Normal"),
            ),
        )
        fid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM feedback_submissions WHERE id = ?", (fid,)
        ).fetchone()

    log_activity("create", "feedback_submission", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Evaluation Templates ----

@evaluation_bp.route("/templates", methods=["GET"])
@token_required
def list_templates():
    template_type = request.args.get("template_type")

    with get_connection() as conn:
        conditions = ["is_active = 1"]
        params: list = []
        if template_type:
            conditions.append("template_type = ?")
            params.append(template_type)

        where = " WHERE " + " AND ".join(conditions)
        rows = conn.execute(
            "SELECT * FROM evaluation_templates" + where + " ORDER BY template_name",
            params,
        ).fetchall()

    log_activity("view", "evaluation_templates", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@evaluation_bp.route("/templates/<int:template_id>", methods=["GET"])
@token_required
def get_template(template_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM evaluation_templates WHERE template_id = ?", (template_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Template {template_id} not found")
    log_activity("view", "evaluation_template", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Survey Responses ----

@evaluation_bp.route("/surveys", methods=["GET"])
@token_required
def list_survey_responses():
    survey_id = request.args.get("survey_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if survey_id:
            conditions.append("survey_id = ?")
            params.append(survey_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM survey_responses" + where + " ORDER BY submission_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM survey_responses" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "survey_responses", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


# ---- Course Evaluations ----

@evaluation_bp.route("/course-evaluations", methods=["GET"])
@token_required
def list_course_evaluations():
    module_code = request.args.get("module_code")
    academic_year = request.args.get("academic_year")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if module_code:
            conditions.append("module_code = ?")
            params.append(module_code)
        if academic_year:
            conditions.append("academic_year = ?")
            params.append(academic_year)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM course_evaluations" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM course_evaluations" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "course_evaluations", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@evaluation_bp.route("/course-evaluations", methods=["POST"])
@token_required
@admin_required
def create_course_evaluation():
    data = request.get_json(silent=True) or {}
    validate_course_evaluation_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO course_evaluations
               (module_code, academic_year, semester, instructor_id,
                template_id, start_date, end_date, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["module_code"],
                data["academic_year"],
                data["semester"],
                data["instructor_id"],
                data["template_id"],
                data["start_date"],
                data["end_date"],
                data.get("is_active", 1),
            ),
        )
        eid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM course_evaluations WHERE evaluation_id = ?", (eid,)
        ).fetchone()

    log_activity("create", "course_evaluation", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
