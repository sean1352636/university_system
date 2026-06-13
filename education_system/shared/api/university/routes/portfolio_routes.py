"""Portfolio routes: portfolios, items, badges, and skills."""

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

portfolio_bp = Blueprint("portfolio", __name__, url_prefix="/api/portfolio")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- portfolios ----

@portfolio_bp.route("/portfolios", methods=["GET"])
@token_required
def list_portfolios():
    search = request.args.get("search")
    student_id = request.args.get("student_id")
    is_public = request.args.get("is_public")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM portfolios WHERE title LIKE ? OR headline LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if is_public:
            conditions.append("is_public = ?")
            params.append(is_public)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM portfolios" + where + " ORDER BY portfolio_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM portfolios" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "portfolios", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@portfolio_bp.route("/portfolios/<int:portfolio_id>", methods=["GET"])
@token_required
def get_portfolio(portfolio_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM portfolios WHERE portfolio_id = ?", (portfolio_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"portfolios {portfolio_id} not found")
    log_activity("view", "portfolios", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@portfolio_bp.route("/portfolios", methods=["POST"])
@token_required
def create_portfolio():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "title"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO portfolios
               (student_id, title, bio, headline, profile_image_url, is_public, linkedin_url, github_url, personal_website, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["title"], data.get("bio", ""), data.get("headline", ""), data.get("profile_image_url", ""), data.get("is_public", ""), data.get("linkedin_url", ""), data.get("github_url", ""), data.get("personal_website", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM portfolios WHERE portfolio_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "portfolios", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- items ----

@portfolio_bp.route("/items", methods=["GET"])
@token_required
def list_items():
    search = request.args.get("search")
    portfolio_id = request.args.get("portfolio_id")
    category = request.args.get("category")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM portfolio_items WHERE title LIKE ? OR description LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if portfolio_id:
            conditions.append("portfolio_id = ?")
            params.append(portfolio_id)
        if category:
            conditions.append("category = ?")
            params.append(category)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM portfolio_items" + where + " ORDER BY item_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM portfolio_items" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "portfolio_items", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@portfolio_bp.route("/items/<int:item_id>", methods=["GET"])
@token_required
def get_item(item_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM portfolio_items WHERE item_id = ?", (item_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"items {item_id} not found")
    log_activity("view", "portfolio_items", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@portfolio_bp.route("/items", methods=["POST"])
@token_required
def create_item():
    data = request.get_json(silent=True) or {}
    for field in ["portfolio_id", "category", "title"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO portfolio_items
               (portfolio_id, category, title, description, organization, role, start_date, end_date, technologies, achievements, url, is_featured, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["portfolio_id"], data["category"], data["title"], data.get("description", ""), data.get("organization", ""), data.get("role", ""), data.get("start_date", ""), data.get("end_date", ""), data.get("technologies", ""), data.get("achievements", ""), data.get("url", ""), data.get("is_featured", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM portfolio_items WHERE item_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "portfolio_items", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- skills ----

@portfolio_bp.route("/skills", methods=["GET"])
@token_required
def list_skills():
    search = request.args.get("search")
    student_id = request.args.get("student_id")
    skill_category = request.args.get("skill_category")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM student_skills WHERE skill_name LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if skill_category:
            conditions.append("skill_category = ?")
            params.append(skill_category)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM student_skills" + where + " ORDER BY skill_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM student_skills" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "student_skills", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@portfolio_bp.route("/skills/<int:skill_id>", methods=["GET"])
@token_required
def get_skill(skill_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_skills WHERE skill_id = ?", (skill_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"skills {skill_id} not found")
    log_activity("view", "student_skills", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@portfolio_bp.route("/skills", methods=["POST"])
@token_required
def create_skill():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "skill_name"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO student_skills
               (student_id, skill_name, skill_category, proficiency_level, years_experience, is_featured, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["skill_name"], data.get("skill_category", ""), data.get("proficiency_level", ""), data.get("years_experience", ""), data.get("is_featured", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_skills WHERE skill_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "student_skills", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
