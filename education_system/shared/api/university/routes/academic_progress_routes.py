"""Academic progress routes: study plans, tasks, flashcards, and concept explanations."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.post_18.university_system.core.exceptions import ValidationError
from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

academic_progress_bp = Blueprint("academic_progress", __name__, url_prefix="/api/academic-progress")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- plans ----

@academic_progress_bp.route("/plans", methods=["GET"])
@token_required
def list_plans():
    search = request.args.get("search")
    student_id = request.args.get("student_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM study_plans WHERE plan_name LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM study_plans" + where + " ORDER BY plan_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM study_plans" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "study_plans", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@academic_progress_bp.route("/plans/<int:plan_id>", methods=["GET"])
@token_required
def get_plan(plan_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_plans WHERE plan_id = ?", (plan_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"plans {plan_id} not found")
    log_activity("view", "study_plans", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@academic_progress_bp.route("/plans", methods=["POST"])
@token_required
def create_plan():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "course_id", "plan_name"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO study_plans
               (student_id, course_id, plan_name, start_date, end_date, total_hours, difficulty_level, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["course_id"], data["plan_name"], data.get("start_date", ""), data.get("end_date", ""), data.get("total_hours", ""), data.get("difficulty_level", ""), data.get("status", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_plans WHERE plan_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "study_plans", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- tasks ----

@academic_progress_bp.route("/tasks", methods=["GET"])
@token_required
def list_tasks():
    search = request.args.get("search")
    plan_id = request.args.get("plan_id")
    completed = request.args.get("completed")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM study_plan_tasks WHERE task_title LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if plan_id:
            conditions.append("plan_id = ?")
            params.append(plan_id)
        if completed:
            conditions.append("completed = ?")
            params.append(completed)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM study_plan_tasks" + where + " ORDER BY task_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM study_plan_tasks" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "study_plan_tasks", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@academic_progress_bp.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def get_task(task_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_plan_tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"tasks {task_id} not found")
    log_activity("view", "study_plan_tasks", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@academic_progress_bp.route("/tasks", methods=["POST"])
@token_required
def create_task():
    data = request.get_json(silent=True) or {}
    for field in ["plan_id", "task_title"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO study_plan_tasks
               (plan_id, task_title, task_description, scheduled_date, duration_minutes, priority, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["plan_id"], data["task_title"], data.get("task_description", ""), data.get("scheduled_date", ""), data.get("duration_minutes", ""), data.get("priority", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_plan_tasks WHERE task_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "study_plan_tasks", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- flashcards ----

@academic_progress_bp.route("/flashcards", methods=["GET"])
@token_required
def list_flashcards():
    search = request.args.get("search")
    student_id = request.args.get("student_id")
    course_id = request.args.get("course_id")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM flashcards WHERE question LIKE ? OR answer LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if course_id:
            conditions.append("course_id = ?")
            params.append(course_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM flashcards" + where + " ORDER BY flashcard_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM flashcards" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "flashcards", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@academic_progress_bp.route("/flashcards/<int:flashcard_id>", methods=["GET"])
@token_required
def get_flashcard(flashcard_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM flashcards WHERE flashcard_id = ?", (flashcard_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"flashcards {flashcard_id} not found")
    log_activity("view", "flashcards", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@academic_progress_bp.route("/flashcards", methods=["POST"])
@token_required
def create_flashcard():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "deck_name", "question", "answer"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO flashcards
               (student_id, deck_name, question, answer, course_id, difficulty_rating, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["deck_name"], data["question"], data["answer"], data.get("course_id", ""), data.get("difficulty_rating", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM flashcards WHERE flashcard_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "flashcards", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
