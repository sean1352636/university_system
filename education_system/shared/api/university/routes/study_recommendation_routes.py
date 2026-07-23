"""Study recommendation routes: profiles, recommendations, and study sessions."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.post_18.university_system.core.exceptions import ValidationError
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

study_recommendation_bp = Blueprint("study_recommendation", __name__, url_prefix="/api/study-recommendations")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- profiles ----

@study_recommendation_bp.route("/profiles/<student_id>", methods=["GET"])
@token_required
def get_profile(student_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_profiles WHERE student_id = ?", (student_id,)
        ).fetchone()

    log_activity("view", "study_profile", user=g.current_user.get("sub"))
    if not row:
        return jsonify({"student_id": student_id, "learning_style": "reading",
                        "study_hours_per_week": 0})
    return jsonify(_row_to_dict(row))


@study_recommendation_bp.route("/profiles", methods=["POST"])
@token_required
def create_or_update_profile():
    data = request.get_json(silent=True) or {}
    if "student_id" not in data:
        raise ValidationError("Missing required field: student_id")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        existing = conn.execute(
            "SELECT id FROM study_profiles WHERE student_id = ?", (data["student_id"],)
        ).fetchone()

        if existing:
            allowed = ["learning_style", "study_hours_per_week", "preferred_times",
                        "strengths", "weaknesses"]
            sets = ["updated_at = ?"]
            params: list = [now]
            for key in allowed:
                if key in data:
                    sets.append(f"{key} = ?")
                    params.append(data[key])
            params.append(data["student_id"])
            conn.execute(
                f"UPDATE study_profiles SET {', '.join(sets)} WHERE student_id = ?",
                params,
            )
        else:
            conn.execute(
                """INSERT INTO study_profiles
                   (student_id, learning_style, study_hours_per_week,
                    preferred_times, strengths, weaknesses, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (data["student_id"], data.get("learning_style", "reading"),
                 data.get("study_hours_per_week", 0),
                 data.get("preferred_times", ""),
                 data.get("strengths", ""), data.get("weaknesses", ""), now),
            )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_profiles WHERE student_id = ?", (data["student_id"],)
        ).fetchone()

    log_activity("upsert", "study_profile", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 200


# ---- recommendations ----

@study_recommendation_bp.route("/recommendations", methods=["GET"])
@token_required
def list_recommendations():
    student_id = request.args.get("student_id")
    active_only = request.args.get("active_only", "true").lower() == "true"
    recommendation_type = request.args.get("type")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if active_only:
            conditions.append("is_completed = 0")
        if recommendation_type:
            conditions.append("recommendation_type = ?")
            params.append(recommendation_type)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM study_recommendations" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM study_recommendations" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "study_recommendations", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@study_recommendation_bp.route("/recommendations/<int:rec_id>", methods=["GET"])
@token_required
def get_recommendation(rec_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_recommendations WHERE id = ?", (rec_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Study recommendation {rec_id} not found")
    log_activity("view", "study_recommendation", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@study_recommendation_bp.route("/recommendations", methods=["POST"])
@token_required
def create_recommendation():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "title"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO study_recommendations
               (student_id, module_code, recommendation_type, title,
                description, priority, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data.get("module_code", ""),
             data.get("recommendation_type", "focus_area"),
             data["title"], data.get("description", ""),
             data.get("priority", "medium"), data.get("expires_at", "")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_recommendations WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "study_recommendation", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@study_recommendation_bp.route("/recommendations/<int:rec_id>/complete", methods=["POST"])
@token_required
def complete_recommendation(rec_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM study_recommendations WHERE id = ?", (rec_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Study recommendation {rec_id} not found")

    with transaction() as conn:
        conn.execute(
            "UPDATE study_recommendations SET is_completed = 1 WHERE id = ?", (rec_id,)
        )

    log_activity("update", "study_recommendation_completed", user=g.current_user.get("sub"))
    return jsonify({"message": "Recommendation marked as completed"})


# ---- study sessions ----

@study_recommendation_bp.route("/sessions", methods=["GET"])
@token_required
def list_sessions():
    student_id = request.args.get("student_id")
    module_code = request.args.get("module_code")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if module_code:
            conditions.append("module_code = ?")
            params.append(module_code)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM study_sessions" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM study_sessions" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "study_sessions", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@study_recommendation_bp.route("/sessions/<int:session_id>", methods=["GET"])
@token_required
def get_session(session_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_sessions WHERE id = ?", (session_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Study session {session_id} not found")
    log_activity("view", "study_session", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@study_recommendation_bp.route("/sessions", methods=["POST"])
@token_required
def log_session():
    data = request.get_json(silent=True) or {}
    if "student_id" not in data:
        raise ValidationError("Missing required field: student_id")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO study_sessions
               (student_id, module_code, topic, duration_minutes,
                effectiveness_rating, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data.get("module_code", ""),
             data.get("topic", ""), data.get("duration_minutes", 0),
             data.get("effectiveness_rating"), data.get("notes", "")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM study_sessions WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "study_session", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- stats ----

@study_recommendation_bp.route("/stats/<student_id>", methods=["GET"])
@token_required
def get_stats(student_id: str):
    with get_connection() as conn:
        total_sessions = conn.execute(
            "SELECT COUNT(*) FROM study_sessions WHERE student_id = ?", (student_id,)
        ).fetchone()[0]
        total_minutes = conn.execute(
            "SELECT COALESCE(SUM(duration_minutes), 0) FROM study_sessions WHERE student_id = ?",
            (student_id,),
        ).fetchone()[0]
        avg_effectiveness = conn.execute(
            "SELECT COALESCE(AVG(effectiveness_rating), 0) FROM study_sessions WHERE student_id = ? AND effectiveness_rating IS NOT NULL",
            (student_id,),
        ).fetchone()[0]
        active_recommendations = conn.execute(
            "SELECT COUNT(*) FROM study_recommendations WHERE student_id = ? AND is_completed = 0",
            (student_id,),
        ).fetchone()[0]

    log_activity("view", "study_stats", user=g.current_user.get("sub"))
    return jsonify({
        "student_id": student_id,
        "total_sessions": total_sessions,
        "total_minutes": total_minutes,
        "total_hours": round(total_minutes / 60, 1),
        "avg_effectiveness": round(avg_effectiveness, 1),
        "active_recommendations": active_recommendations,
    })


@study_recommendation_bp.route("/generate/<student_id>", methods=["POST"])
@token_required
def generate_recommendations(student_id: str):
    """Auto-generate recommendations based on weak areas and learning style."""
    recommendations = []

    # Find weak areas from grades
    weak_areas = []
    with get_connection() as conn:
        try:
            rows = conn.execute(
                "SELECT module_code, course, grade, score FROM grades "
                "WHERE student_id = ? AND (score < 50 OR grade IN ('F', 'D', 'D-')) "
                "ORDER BY score ASC",
                (student_id,),
            ).fetchall()
            weak_areas = [_row_to_dict(r) for r in rows]
        except Exception:
            pass

    for area in weak_areas:
        module = area.get("module_code", area.get("course", "this subject"))
        score = float(area.get("score", area.get("grade", 50)))
        rec = {
            "student_id": student_id,
            "module_code": module,
            "recommendation_type": "focus_area",
            "title": f"Review {module}",
            "description": f"Your grade ({area.get('grade', area.get('score', 'N/A'))}) suggests more study is needed.",
            "priority": "high" if score < 40 else "medium",
        }
        recommendations.append(rec)

    # Add learning style tip
    with get_connection() as conn:
        profile_row = conn.execute(
            "SELECT * FROM study_profiles WHERE student_id = ?", (student_id,)
        ).fetchone()
    if profile_row:
        style = _row_to_dict(profile_row).get("learning_style",
                _row_to_dict(profile_row).get("study_style", "reading"))
        tips = {
            "visual": "Try using mind maps, diagrams, and colour-coded notes.",
            "auditory": "Record lectures, use podcasts, and discuss topics with peers.",
            "reading": "Summarise textbook chapters and create revision notes.",
            "kinesthetic": "Use hands-on practice, labs, and real-world applications.",
        }
        recommendations.append({
            "student_id": student_id, "module_code": "",
            "recommendation_type": "technique",
            "title": f"Study technique for {style} learners",
            "description": tips.get(style, "Use varied study methods."),
            "priority": "low",
        })

    # Save to DB
    with transaction() as conn:
        for rec in recommendations:
            conn.execute(
                "INSERT INTO study_recommendations "
                "(student_id, module_code, recommendation_type, title, description, priority) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (rec["student_id"], rec["module_code"], rec["recommendation_type"],
                 rec["title"], rec["description"], rec["priority"]),
            )

    log_activity("generate", "study_recommendations", user=g.current_user.get("sub"))
    return jsonify({"recommendations": recommendations, "count": len(recommendations)})


@study_recommendation_bp.route("/weak-areas/<student_id>", methods=["GET"])
@token_required
def get_weak_areas(student_id: str):
    weak = []
    with get_connection() as conn:
        try:
            rows = conn.execute(
                "SELECT module_code, course, grade, score FROM grades "
                "WHERE student_id = ? AND (score < 50 OR grade IN ('F', 'D', 'D-')) "
                "ORDER BY score ASC",
                (student_id,),
            ).fetchall()
            weak = [_row_to_dict(r) for r in rows]
        except Exception:
            pass

    log_activity("view", "study_weak_areas", user=g.current_user.get("sub"))
    return jsonify({"student_id": student_id, "weak_areas": weak, "count": len(weak)})


@study_recommendation_bp.route("/streak/<student_id>", methods=["GET"])
@token_required
def get_study_streak(student_id: str):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT DATE(studied_at) as study_date FROM study_sessions "
            "WHERE student_id = ? ORDER BY study_date DESC",
            (student_id,),
        ).fetchall()

    streak = len(rows) if rows else 0

    log_activity("view", "study_streak", user=g.current_user.get("sub"))
    return jsonify({"student_id": student_id, "streak_days": streak})
