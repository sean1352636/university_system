"""AI study routes: study plans, tasks, flashcards, and concept explanations."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

ai_study_bp = Blueprint("ai_study", __name__, url_prefix="/api/ai-study")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- plans ----

@ai_study_bp.route("/plans", methods=["GET"])
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


@ai_study_bp.route("/plans/<int:plan_id>", methods=["GET"])
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

@ai_study_bp.route("/plans", methods=["POST"])
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
               (student_id, course_id, plan_name, start_date, end_date, total_hours, difficulty_level, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["course_id"], data["plan_name"], data.get("start_date", ""), data.get("end_date", ""), data.get("total_hours", ""), data.get("difficulty_level", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_plans WHERE plan_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "study_plans", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- concept-explanations ----

@ai_study_bp.route("/concept-explanations", methods=["GET"])
@token_required
def list_concept_explanations():
    search = request.args.get("search")
    student_id = request.args.get("student_id")
    course_id = request.args.get("course_id")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM concept_explanations WHERE concept_name LIKE ?",
                (pattern),
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
            "SELECT * FROM concept_explanations" + where + " ORDER BY explanation_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM concept_explanations" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "concept_explanations", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@ai_study_bp.route("/concept-explanations/<int:explanation_id>", methods=["GET"])
@token_required
def get_concept_explanation(explanation_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM concept_explanations WHERE explanation_id = ?", (explanation_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"concept-explanations {explanation_id} not found")
    log_activity("view", "concept_explanations", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@ai_study_bp.route("/concept-explanations", methods=["POST"])
@token_required
def create_concept_explanation():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "concept_name", "explanation"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO concept_explanations
               (student_id, concept_name, explanation, course_id, difficulty_level, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["concept_name"], data["explanation"], data.get("course_id", ""), data.get("difficulty_level", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM concept_explanations WHERE explanation_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "concept_explanations", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- generate study plan ----

@ai_study_bp.route("/plans/generate", methods=["POST"])
@token_required
def generate_plan():
    """Generate a personalized study plan based on exam date."""
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "exam_date"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    student_id = data["student_id"]
    course_id = data.get("course_id")
    exam_date = data["exam_date"]
    hours_per_day = data.get("hours_per_day", 2)

    import random
    from datetime import timedelta

    exam_datetime = datetime.strptime(exam_date, "%Y-%m-%d")
    days_until_exam = (exam_datetime - datetime.now()).days
    if days_until_exam < 0:
        raise ValidationError("Exam date must be in the future")

    total_hours = days_until_exam * hours_per_day

    topics = [
        "Review lecture notes",
        "Practice problems",
        "Read textbook chapters",
        "Watch tutorial videos",
        "Create summary notes",
        "Practice past exams",
        "Review key concepts",
        "Memorize formulas/definitions",
        "Group study session",
        "Final review",
    ]

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO study_plans
               (student_id, course_id, plan_name, start_date, end_date, total_hours, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                student_id,
                course_id,
                f"Exam Prep - {exam_date}",
                datetime.now().strftime("%Y-%m-%d"),
                exam_date,
                total_hours,
                now,
            ),
        )
        plan_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        tasks_generated = 0
        for day in range(days_until_exam):
            scheduled = (datetime.now() + timedelta(days=day)).strftime("%Y-%m-%d")
            if day < days_until_exam * 0.3:
                priority = "Low"
                selected = topics[:4]
            elif day < days_until_exam * 0.7:
                priority = "Medium"
                selected = topics[4:8]
            else:
                priority = "High"
                selected = topics[6:]
            topic = random.choice(selected)
            duration = hours_per_day * 60
            conn.execute(
                """INSERT INTO study_plan_tasks
                   (plan_id, task_title, task_description, scheduled_date, duration_minutes, priority)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (plan_id, topic, f"Spend {hours_per_day} hour(s) on {topic.lower()}", scheduled, duration, priority),
            )
            tasks_generated += 1

    log_activity("create", "study_plan_generate", user=g.current_user.get("sub"),
                 details={"plan_id": plan_id, "student_id": student_id, "exam_date": exam_date})
    return jsonify({
        "plan_id": plan_id,
        "total_hours": total_hours,
        "days_until_exam": days_until_exam,
        "tasks_generated": tasks_generated,
    }), 201


# ---- complete task ----

@ai_study_bp.route("/tasks/<int:task_id>/complete", methods=["PUT"])
@token_required
def complete_task(task_id: int):
    """Mark a study task as completed."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_plan_tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"task {task_id} not found")

    with transaction() as conn:
        conn.execute(
            "UPDATE study_plan_tasks SET completed = 1, completed_at = ? WHERE task_id = ?",
            (datetime.now().isoformat(), task_id),
        )

    log_activity("update", "study_task_complete", user=g.current_user.get("sub"),
                 details={"task_id": task_id, "status": "completed"})
    return jsonify({"task_id": task_id, "completed": True})


# ---- flashcards: due ----

@ai_study_bp.route("/flashcards/due", methods=["GET"])
@token_required
def get_due_flashcards():
    """Get flashcards due for review (spaced repetition)."""
    student_id = request.args.get("student_id")
    if not student_id:
        raise ValidationError("Missing required query parameter: student_id")

    deck_name = request.args.get("deck_name")
    today = datetime.now().strftime("%Y-%m-%d")

    with get_connection() as conn:
        query = "SELECT * FROM flashcards WHERE student_id = ? AND (next_review IS NULL OR next_review <= ?)"
        params: list = [student_id, today]
        if deck_name:
            query += " AND deck_name = ?"
            params.append(deck_name)
        query += " ORDER BY next_review LIMIT 20"
        rows = conn.execute(query, params).fetchall()

    log_activity("view", "flashcards_due", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- flashcards: review ----

@ai_study_bp.route("/flashcards/<int:flashcard_id>/review", methods=["POST"])
@token_required
def review_flashcard(flashcard_id: int):
    """Review a flashcard and update spaced repetition schedule."""
    data = request.get_json(silent=True) or {}
    if "correct" not in data:
        raise ValidationError("Missing required field: correct")

    correct = bool(data["correct"])

    with get_connection() as conn:
        card = conn.execute(
            "SELECT review_count, correct_count FROM flashcards WHERE flashcard_id = ?",
            (flashcard_id,),
        ).fetchone()
    if not card:
        raise ValidationError(f"flashcard {flashcard_id} not found")

    from datetime import timedelta

    review_count = card["review_count"] + 1
    correct_count = card["correct_count"] + (1 if correct else 0)

    if correct:
        intervals = [1, 3, 7, 14, 30, 60, 120]
        idx = min(review_count, len(intervals) - 1)
        days_until_next = intervals[idx]
    else:
        days_until_next = 1

    next_review = (datetime.now() + timedelta(days=days_until_next)).strftime("%Y-%m-%d")

    with transaction() as conn:
        conn.execute(
            """UPDATE flashcards
               SET review_count = ?, correct_count = ?, last_reviewed = ?, next_review = ?
               WHERE flashcard_id = ?""",
            (review_count, correct_count, datetime.now().isoformat(), next_review, flashcard_id),
        )

    log_activity("update", "flashcard_review", user=g.current_user.get("sub"),
                 details={"flashcard_id": flashcard_id, "correct": correct, "next_review": next_review})
    return jsonify({
        "next_review": next_review,
        "days_until_next": days_until_next,
        "review_count": review_count,
    })


# ---- flashcards: decks ----

@ai_study_bp.route("/flashcards/decks", methods=["GET"])
@token_required
def get_flashcard_decks():
    """Get all flashcard decks for a student with statistics."""
    student_id = request.args.get("student_id")
    if not student_id:
        raise ValidationError("Missing required query parameter: student_id")

    today = datetime.now().strftime("%Y-%m-%d")
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT
                   deck_name,
                   course_id,
                   COUNT(*) as total_cards,
                   SUM(CASE WHEN next_review <= ? THEN 1 ELSE 0 END) as due_count,
                   AVG(CAST(correct_count AS FLOAT) / NULLIF(review_count, 0)) * 100 as accuracy
               FROM flashcards
               WHERE student_id = ?
               GROUP BY deck_name, course_id
               ORDER BY deck_name""",
            (today, student_id),
        ).fetchall()

    log_activity("view", "flashcard_decks", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- concept-explanations: rate ----

@ai_study_bp.route("/concept-explanations/<int:explanation_id>/rate", methods=["PUT"])
@token_required
def rate_explanation(explanation_id: int):
    """Rate the helpfulness of a concept explanation (1-5)."""
    data = request.get_json(silent=True) or {}
    if "rating" not in data:
        raise ValidationError("Missing required field: rating")

    rating = data["rating"]
    if not isinstance(rating, int) or not 1 <= rating <= 5:
        raise ValidationError("Rating must be an integer between 1 and 5")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM concept_explanations WHERE explanation_id = ?", (explanation_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"concept-explanation {explanation_id} not found")

    with transaction() as conn:
        conn.execute(
            "UPDATE concept_explanations SET helpful_rating = ? WHERE explanation_id = ?",
            (rating, explanation_id),
        )

    log_activity("update", "concept_explanation_rating", user=g.current_user.get("sub"),
                 details={"explanation_id": explanation_id, "rating": rating})
    return jsonify({"explanation_id": explanation_id, "helpful_rating": rating})


# ---- students: explanation history ----

@ai_study_bp.route("/students/<student_id>/history", methods=["GET"])
@token_required
def get_explanation_history(student_id: str):
    """Get all concept explanations for a student."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM concept_explanations WHERE student_id = ? ORDER BY created_at DESC LIMIT 50",
            (student_id,),
        ).fetchall()

    log_activity("view", "explanation_history", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- students: study analytics ----

@ai_study_bp.route("/students/<student_id>/analytics", methods=["GET"])
@token_required
def get_study_analytics(student_id: str):
    """Get comprehensive study analytics for a student."""
    with get_connection() as conn:
        plan_stats = conn.execute(
            """SELECT
                   COUNT(*) as total_plans,
                   SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active_plans,
                   SUM(total_hours) as planned_hours
               FROM study_plans
               WHERE student_id = ?""",
            (student_id,),
        ).fetchone()

        task_stats = conn.execute(
            """SELECT
                   COUNT(*) as total_tasks,
                   SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed_tasks,
                   SUM(duration_minutes) as total_minutes
               FROM study_plan_tasks spt
               JOIN study_plans sp ON spt.plan_id = sp.plan_id
               WHERE sp.student_id = ?""",
            (student_id,),
        ).fetchone()

        flashcard_stats = conn.execute(
            """SELECT
                   COUNT(*) as total_cards,
                   COUNT(DISTINCT deck_name) as total_decks,
                   AVG(CAST(correct_count AS FLOAT) / NULLIF(review_count, 0)) * 100 as avg_accuracy
               FROM flashcards
               WHERE student_id = ?""",
            (student_id,),
        ).fetchone()

    log_activity("view", "study_analytics", user=g.current_user.get("sub"))
    return jsonify({
        "study_plans": _row_to_dict(plan_stats),
        "tasks": _row_to_dict(task_stats),
        "flashcards": _row_to_dict(flashcard_stats),
    })
