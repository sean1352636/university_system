"""Feedback routes: submissions, votes, responses, and status updates."""

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

feedback_system_bp = Blueprint("feedback_system", __name__, url_prefix="/api/feedback")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- submissions ----

@feedback_system_bp.route("/submissions", methods=["GET"])
@token_required
def list_submissions():
    search = request.args.get("search")
    user_id = request.args.get("user_id")
    category_id = request.args.get("category_id")
    status = request.args.get("status")
    type = request.args.get("type")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM feedback_submissions WHERE title LIKE ? OR description LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if category_id:
            conditions.append("category_id = ?")
            params.append(category_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if type:
            conditions.append("type = ?")
            params.append(type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM feedback_submissions" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
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


@feedback_system_bp.route("/submissions/<int:id>", methods=["GET"])
@token_required
def get_submission(id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM feedback_submissions WHERE id = ?", (id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"submissions {id} not found")
    log_activity("view", "feedback_submissions", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@feedback_system_bp.route("/submissions", methods=["POST"])
@token_required
def create_submission():
    data = request.get_json(silent=True) or {}
    for field in ["user_id", "title", "description", "type"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO feedback_submissions
               (user_id, title, description, type, category_id, is_anonymous, priority, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["user_id"], data["title"], data["description"], data["type"], data.get("category_id", ""), data.get("is_anonymous", 0), data.get("priority", "medium"), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM feedback_submissions WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "feedback_submissions", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- categories ----

@feedback_system_bp.route("/categories", methods=["GET"])
@token_required
def list_categories():
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM feedback_categories WHERE name LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM feedback_categories" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM feedback_categories" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "feedback_categories", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@feedback_system_bp.route("/categories/<int:id>", methods=["GET"])
@token_required
def get_categorie(id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM feedback_categories WHERE id = ?", (id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"categories {id} not found")
    log_activity("view", "feedback_categories", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@feedback_system_bp.route("/categories", methods=["POST"])
@token_required
def create_categorie():
    data = request.get_json(silent=True) or {}
    for field in ["name"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO feedback_categories
               (name, description, icon, created_at)
               VALUES (?, ?, ?, ?)""",
            (data["name"], data.get("description", ""), data.get("icon", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM feedback_categories WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "feedback_categories", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- responses ----

@feedback_system_bp.route("/responses", methods=["GET"])
@token_required
def list_responses():
    submission_id = request.args.get("submission_id")
    responder_id = request.args.get("responder_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if submission_id:
            conditions.append("submission_id = ?")
            params.append(submission_id)
        if responder_id:
            conditions.append("responder_id = ?")
            params.append(responder_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM feedback_responses" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM feedback_responses" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "feedback_responses", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@feedback_system_bp.route("/responses/<int:id>", methods=["GET"])
@token_required
def get_response(id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM feedback_responses WHERE id = ?", (id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"responses {id} not found")
    log_activity("view", "feedback_responses", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@feedback_system_bp.route("/responses", methods=["POST"])
@token_required
def create_response():
    data = request.get_json(silent=True) or {}
    for field in ["submission_id", "responder_id", "responder_name", "response_text"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO feedback_responses
               (submission_id, responder_id, responder_name, response_text, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (data["submission_id"], data["responder_id"], data["responder_name"], data["response_text"], now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM feedback_responses WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "feedback_responses", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- votes ----

@feedback_system_bp.route("/items/<int:id>/vote", methods=["POST"])
@token_required
def upvote_submission(id: int):
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id") or g.current_user.get("sub")
    if not user_id:
        raise ValidationError("Missing required field: user_id")

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM feedback_votes WHERE submission_id = ? AND user_id = ?",
            (id, user_id),
        ).fetchone()

    if existing:
        return jsonify({"message": "Already voted", "voted": False}), 409

    with transaction() as conn:
        conn.execute(
            "INSERT INTO feedback_votes (submission_id, user_id, vote_type, created_at) VALUES (?, ?, 'upvote', ?)",
            (id, user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.execute(
            "UPDATE feedback_submissions SET votes = votes + 1, updated_at = ? WHERE id = ?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), id),
        )

    log_activity("create", "feedback_vote", user=g.current_user.get("sub"))
    return jsonify({"message": "Vote added", "voted": True}), 201


@feedback_system_bp.route("/items/<int:id>/vote", methods=["DELETE"])
@token_required
def remove_vote(id: int):
    user_id = request.args.get("user_id") or g.current_user.get("sub")
    if not user_id:
        raise ValidationError("Missing required field: user_id")

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM feedback_votes WHERE submission_id = ? AND user_id = ?",
            (id, user_id),
        ).fetchone()

    if not existing:
        return jsonify({"message": "Vote not found", "removed": False}), 404

    with transaction() as conn:
        conn.execute(
            "DELETE FROM feedback_votes WHERE submission_id = ? AND user_id = ?",
            (id, user_id),
        )
        conn.execute(
            "UPDATE feedback_submissions SET votes = votes - 1, updated_at = ? WHERE id = ?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), id),
        )

    log_activity("delete", "feedback_vote", user=g.current_user.get("sub"))
    return jsonify({"message": "Vote removed", "removed": True})


# ---- status updates ----

@feedback_system_bp.route("/items/<int:id>/status", methods=["PUT"])
@token_required
def update_submission_status(id: int):
    data = request.get_json(silent=True) or {}
    if "status" not in data:
        raise ValidationError("Missing required field: status")

    updated_by = data.get("updated_by") or g.current_user.get("sub")
    notes = data.get("notes")
    new_status = data["status"]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT status FROM feedback_submissions WHERE id = ?", (id,)
        ).fetchone()

    if not row:
        raise ValidationError(f"Submission {id} not found")

    old_status = row["status"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        conn.execute(
            "UPDATE feedback_submissions SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, now, id),
        )
        conn.execute(
            """INSERT INTO feedback_status_updates
               (submission_id, old_status, new_status, updated_by, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (id, old_status, new_status, updated_by, notes, now),
        )

    log_activity("update", "feedback_status", user=g.current_user.get("sub"))
    return jsonify({"message": "Status updated", "old_status": old_status, "new_status": new_status})


# ---- trending & implemented ----

@feedback_system_bp.route("/items/trending", methods=["GET"])
@token_required
def get_trending():
    limit = request.args.get("limit", 10, type=int)

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT fs.id, fs.title, fs.description, fs.votes, fs.status,
                      fs.created_at, fs.updated_at,
                      fc.name as category, fc.icon as category_icon,
                      COUNT(fr.id) as response_count
               FROM feedback_submissions fs
               JOIN feedback_categories fc ON fs.category_id = fc.id
               LEFT JOIN feedback_responses fr ON fs.id = fr.submission_id
               WHERE fs.type = 'suggestion'
                 AND fs.status NOT IN ('Declined', 'Implemented')
               GROUP BY fs.id
               ORDER BY fs.votes DESC, fs.updated_at DESC, response_count DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

    log_activity("view", "feedback_trending", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@feedback_system_bp.route("/items/implemented", methods=["GET"])
@token_required
def get_implemented():
    limit = request.args.get("limit", 20, type=int)

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT fs.id, fs.title, fs.description, fs.votes, fs.created_at,
                      fc.name as category, fc.icon as category_icon,
                      fi.implementation_date, fi.users_affected,
                      fi.satisfaction_increase, fi.cost_savings,
                      fi.description as impact_description
               FROM feedback_submissions fs
               JOIN feedback_categories fc ON fs.category_id = fc.id
               LEFT JOIN feedback_impacts fi ON fs.id = fi.submission_id
               WHERE fs.status = 'Implemented'
               ORDER BY fi.implementation_date DESC, fs.votes DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

    log_activity("view", "feedback_implemented", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- user-specific ----

@feedback_system_bp.route("/students/<student_id>/submissions", methods=["GET"])
@token_required
def get_user_submissions(student_id: str):
    page, per_page, offset = get_pagination_params()

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM feedback_submissions WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (student_id, per_page, offset),
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM feedback_submissions WHERE user_id = ?",
            (student_id,),
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "feedback_user_submissions", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@feedback_system_bp.route("/students/<student_id>/votes", methods=["GET"])
@token_required
def get_user_votes(student_id: str):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT submission_id FROM feedback_votes WHERE user_id = ?",
            (student_id,),
        ).fetchall()

    submission_ids = [r["submission_id"] for r in rows]
    log_activity("view", "feedback_user_votes", user=g.current_user.get("sub"))
    return jsonify({"submission_ids": submission_ids, "total": len(submission_ids)})


# ---- statistics ----

@feedback_system_bp.route("/statistics", methods=["GET"])
@token_required
def get_statistics():
    with get_connection() as conn:
        total_submissions = conn.execute(
            "SELECT COUNT(*) FROM feedback_submissions"
        ).fetchone()[0]

        by_type = conn.execute(
            "SELECT type, COUNT(*) as count FROM feedback_submissions GROUP BY type"
        ).fetchall()
        total_feedback = 0
        total_suggestions = 0
        for row in by_type:
            if row["type"] == "feedback":
                total_feedback = row["count"]
            elif row["type"] == "suggestion":
                total_suggestions = row["count"]

        total_votes = conn.execute(
            "SELECT COUNT(*) FROM feedback_votes"
        ).fetchone()[0]

        total_responses = conn.execute(
            "SELECT COUNT(*) FROM feedback_responses"
        ).fetchone()[0]

        by_status_rows = conn.execute(
            "SELECT status, COUNT(*) as count FROM feedback_submissions GROUP BY status"
        ).fetchall()
        by_status = {row["status"]: row["count"] for row in by_status_rows}

        by_category_rows = conn.execute(
            """SELECT fc.name, COUNT(fs.id) as count
               FROM feedback_categories fc
               LEFT JOIN feedback_submissions fs ON fc.id = fs.category_id
               GROUP BY fc.name"""
        ).fetchall()
        by_category = {row["name"]: row["count"] for row in by_category_rows}

        avg_row = conn.execute(
            "SELECT AVG(votes) FROM feedback_submissions"
        ).fetchone()
        average_votes = round(avg_row[0], 2) if avg_row[0] else 0

    stats = {
        "total_submissions": total_submissions,
        "total_feedback": total_feedback,
        "total_suggestions": total_suggestions,
        "total_votes": total_votes,
        "total_responses": total_responses,
        "by_status": by_status,
        "by_category": by_category,
        "implemented_count": by_status.get("Implemented", 0),
        "average_votes": average_votes,
    }

    log_activity("view", "feedback_statistics", user=g.current_user.get("sub"))
    return jsonify(stats)


# ---- search ----

@feedback_system_bp.route("/search", methods=["GET"])
@token_required
def search_submissions():
    q = request.args.get("q", "")
    limit = request.args.get("limit", 50, type=int)

    if not q:
        return jsonify({"items": [], "total": 0})

    pattern = f"%{escape_like(q)}%"
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT fs.id, fs.type, fs.title, fs.description, fs.status,
                      fs.votes, fs.created_at,
                      fc.name as category, fc.icon as category_icon
               FROM feedback_submissions fs
               JOIN feedback_categories fc ON fs.category_id = fc.id
               WHERE fs.title LIKE ? OR fs.description LIKE ?
               ORDER BY fs.votes DESC, fs.created_at DESC
               LIMIT ?""",
            (pattern, pattern, limit),
        ).fetchall()

    log_activity("view", "feedback_search", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- delete ----

@feedback_system_bp.route("/items/<int:id>", methods=["DELETE"])
@token_required
def delete_submission(id: int):
    user_id = request.args.get("user_id") or g.current_user.get("sub")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT user_id FROM feedback_submissions WHERE id = ?", (id,)
        ).fetchone()

    if not row:
        raise ValidationError(f"Submission {id} not found")

    if row["user_id"] != user_id:
        return jsonify({"message": "Not authorized to delete this submission"}), 403

    with transaction() as conn:
        conn.execute("DELETE FROM feedback_submissions WHERE id = ?", (id,))

    log_activity("delete", "feedback_submission", user=g.current_user.get("sub"))
    return jsonify({"message": "Submission deleted", "id": id})
