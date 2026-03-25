"""Achievement badge routes: badge definitions, awards, and progress."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

achievement_badge_bp = Blueprint("achievement_badge", __name__, url_prefix="/api/achievement-badges")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- badge definitions ----

@achievement_badge_bp.route("/badges", methods=["GET"])
@token_required
def list_badges():
    category = request.args.get("category")
    active_only = request.args.get("active_only", "true").lower() == "true"
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM badge_definitions WHERE name LIKE ? OR description LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if active_only:
            conditions.append("is_active = 1")
        if category:
            conditions.append("category = ?")
            params.append(category)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM badge_definitions" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM badge_definitions" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "badge_definitions", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@achievement_badge_bp.route("/badges/<int:badge_id>", methods=["GET"])
@token_required
def get_badge(badge_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM badge_definitions WHERE id = ?", (badge_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Badge {badge_id} not found")
    log_activity("view", "badge_definition", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@achievement_badge_bp.route("/badges", methods=["POST"])
@token_required
def create_badge():
    data = request.get_json(silent=True) or {}
    if "name" not in data:
        raise ValidationError("Missing required field: name")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO badge_definitions
               (name, description, category, icon_name, criteria, points)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["name"], data.get("description", ""), data.get("category", "academic"),
             data.get("icon_name", ""), data.get("criteria", ""), data.get("points", 0)),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM badge_definitions WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "badge_definition", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- student badges (awards) ----

@achievement_badge_bp.route("/awards", methods=["GET"])
@token_required
def list_awards():
    student_id = request.args.get("student_id")
    badge_id = request.args.get("badge_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if badge_id:
            conditions.append("badge_id = ?")
            params.append(badge_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM student_badges" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM student_badges" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "student_badges", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@achievement_badge_bp.route("/awards/<int:award_id>", methods=["GET"])
@token_required
def get_award(award_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_badges WHERE id = ?", (award_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Badge award {award_id} not found")
    log_activity("view", "student_badge", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@achievement_badge_bp.route("/awards", methods=["POST"])
@token_required
def award_badge():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "badge_id"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO student_badges
               (student_id, badge_id, awarded_at, awarded_by, reason)
               VALUES (?, ?, ?, ?, ?)""",
            (data["student_id"], data["badge_id"], now,
             data.get("awarded_by", ""), data.get("reason", "")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_badges WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "student_badge", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@achievement_badge_bp.route("/awards/<int:award_id>", methods=["DELETE"])
@token_required
def revoke_badge(award_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_badges WHERE id = ?", (award_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Badge award {award_id} not found")

    with transaction() as conn:
        conn.execute("DELETE FROM student_badges WHERE id = ?", (award_id,))

    log_activity("delete", "student_badge", user=g.current_user.get("sub"))
    return jsonify({"message": "Badge revoked"}), 200


# ---- progress ----

@achievement_badge_bp.route("/progress", methods=["GET"])
@token_required
def list_progress():
    student_id = request.args.get("student_id")
    badge_id = request.args.get("badge_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if badge_id:
            conditions.append("badge_id = ?")
            params.append(badge_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            "SELECT * FROM badge_progress" + where + " ORDER BY id DESC",
            params,
        ).fetchall()

    log_activity("view", "badge_progress", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@achievement_badge_bp.route("/progress", methods=["POST"])
@token_required
def update_progress():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "badge_id", "current_progress"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        existing = conn.execute(
            "SELECT id FROM badge_progress WHERE student_id = ? AND badge_id = ?",
            (data["student_id"], data["badge_id"]),
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE badge_progress SET current_progress = ?, last_updated = ? WHERE id = ?",
                (data["current_progress"], now, existing["id"]),
            )
            new_id = existing["id"]
        else:
            conn.execute(
                """INSERT INTO badge_progress
                   (student_id, badge_id, current_progress, target_progress, last_updated)
                   VALUES (?, ?, ?, ?, ?)""",
                (data["student_id"], data["badge_id"], data["current_progress"],
                 data.get("target_progress", 100), now),
            )
            new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM badge_progress WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("update", "badge_progress", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 200


# ---- leaderboard & statistics ----

@achievement_badge_bp.route("/leaderboard", methods=["GET"])
@token_required
def get_leaderboard():
    limit = request.args.get("limit", 20, type=int)
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT student_id, COUNT(*) as badge_count,
                      COALESCE(SUM(bd.points), 0) as total_points
               FROM student_badges sb
               LEFT JOIN badge_definitions bd ON sb.badge_id = bd.id
               GROUP BY student_id
               ORDER BY total_points DESC, badge_count DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

    log_activity("view", "badge_leaderboard", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows]})


@achievement_badge_bp.route("/statistics", methods=["GET"])
@token_required
def get_statistics():
    with get_connection() as conn:
        total_badges = conn.execute("SELECT COUNT(*) FROM badge_definitions").fetchone()[0]
        total_awards = conn.execute("SELECT COUNT(*) FROM student_badges").fetchone()[0]
        unique_earners = conn.execute("SELECT COUNT(DISTINCT student_id) FROM student_badges").fetchone()[0]

    by_category = {}
    with get_connection() as conn:
        for row in conn.execute(
            "SELECT bd.category, COUNT(*) as cnt FROM student_badges sb "
            "JOIN badge_definitions bd ON sb.badge_id = bd.id GROUP BY bd.category"
        ).fetchall():
            by_category[row["category"]] = row["cnt"]

    log_activity("view", "badge_statistics", user=g.current_user.get("sub"))
    return jsonify({
        "total_badges": total_badges,
        "total_awards": total_awards,
        "unique_earners": unique_earners,
        "by_category": by_category,
    })


@achievement_badge_bp.route("/student/<student_id>/count", methods=["GET"])
@token_required
def get_student_badge_count(student_id: str):
    with get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM student_badges WHERE student_id = ?", (student_id,)
        ).fetchone()[0]
        points = conn.execute(
            """SELECT COALESCE(SUM(bd.points), 0) FROM student_badges sb
               JOIN badge_definitions bd ON sb.badge_id = bd.id WHERE sb.student_id = ?""",
            (student_id,),
        ).fetchone()[0]

    log_activity("view", "student_badge_count", user=g.current_user.get("sub"))
    return jsonify({"student_id": student_id, "count": count, "total_points": points})


@achievement_badge_bp.route("/awards/<int:award_id>/toggle-display", methods=["POST"])
@token_required
def toggle_badge_display(award_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT is_displayed FROM student_badges WHERE id = ?", (award_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Badge award {award_id} not found")

    new_val = 0 if row["is_displayed"] == 1 else 1
    with transaction() as conn:
        conn.execute(
            "UPDATE student_badges SET is_displayed = ? WHERE id = ?", (new_val, award_id)
        )

    log_activity("update", "badge_display_toggle", user=g.current_user.get("sub"))
    return jsonify({"id": award_id, "is_displayed": new_val})
