"""Social matching routes: profiles, matches, and interests."""

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

social_matching_bp = Blueprint("social_matching", __name__, url_prefix="/api/social-matching")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- profiles ----

@social_matching_bp.route("/profiles", methods=["GET"])
@token_required
def list_profiles():
    search = request.args.get("search")
    student_id = request.args.get("student_id")
    is_active = request.args.get("is_active")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM social_profiles WHERE display_name LIKE ? OR bio LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if is_active:
            conditions.append("is_active = ?")
            params.append(is_active)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM social_profiles" + where + " ORDER BY profile_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM social_profiles" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "social_profiles", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@social_matching_bp.route("/profiles/<int:profile_id>", methods=["GET"])
@token_required
def get_profile(profile_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM social_profiles WHERE profile_id = ?", (profile_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"profiles {profile_id} not found")
    log_activity("view", "social_profiles", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@social_matching_bp.route("/profiles", methods=["POST"])
@token_required
def create_profile():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "display_name"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO social_profiles
               (student_id, display_name, bio, interests, personality_type, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["display_name"], data.get("bio", ""), data.get("interests", ""), data.get("personality_type", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM social_profiles WHERE profile_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "social_profiles", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- matches ----

@social_matching_bp.route("/matches", methods=["GET"])
@token_required
def list_matches():
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM social_matches" + where + " ORDER BY match_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM social_matches" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "social_matches", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@social_matching_bp.route("/matches/<int:match_id>", methods=["GET"])
@token_required
def get_matche(match_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM social_matches WHERE match_id = ?", (match_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"matches {match_id} not found")
    log_activity("view", "social_matches", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@social_matching_bp.route("/matches", methods=["POST"])
@token_required
def create_matche():
    data = request.get_json(silent=True) or {}
    for field in ["profile_id_1", "profile_id_2", "compatibility_score"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO social_matches
               (profile_id_1, profile_id_2, compatibility_score, match_reasons, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["profile_id_1"], data["profile_id_2"], data["compatibility_score"], data.get("match_reasons", ""), data.get("status", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM social_matches WHERE match_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "social_matches", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
