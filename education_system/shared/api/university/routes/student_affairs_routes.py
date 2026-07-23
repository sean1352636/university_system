"""Student affairs routes: accessibility tools, support requests, and accommodations."""

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

student_affairs_bp = Blueprint("student_affairs", __name__, url_prefix="/api/student-affairs")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- support-requests ----

@student_affairs_bp.route("/support-requests", methods=["GET"])
@token_required
def list_support_requests():
    search = request.args.get("search")
    student_id = request.args.get("student_id")
    status = request.args.get("status")
    category = request.args.get("category")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM student_support_requests WHERE title LIKE ? OR description LIKE ?",
                (pattern, pattern),
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
        if category:
            conditions.append("category = ?")
            params.append(category)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM student_support_requests" + where + " ORDER BY request_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM student_support_requests" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "student_support_requests", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@student_affairs_bp.route("/support-requests/<int:request_id>", methods=["GET"])
@token_required
def get_support_request(request_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_support_requests WHERE request_id = ?", (request_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"support-requests {request_id} not found")
    log_activity("view", "student_support_requests", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@student_affairs_bp.route("/support-requests", methods=["POST"])
@token_required
def create_support_request():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "title", "description", "category"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO student_support_requests
               (student_id, title, description, category, priority, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["title"], data["description"], data["category"], data.get("priority", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_support_requests WHERE request_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "student_support_requests", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- tools ----

@student_affairs_bp.route("/tools", methods=["GET"])
@token_required
def list_tools():
    search = request.args.get("search")
    category = request.args.get("category")
    is_active = request.args.get("is_active")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM accessibility_tools WHERE tool_name LIKE ? OR description LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if is_active:
            conditions.append("is_active = ?")
            params.append(is_active)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM accessibility_tools" + where + " ORDER BY tool_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM accessibility_tools" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "accessibility_tools", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@student_affairs_bp.route("/tools/<int:tool_id>", methods=["GET"])
@token_required
def get_tool(tool_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accessibility_tools WHERE tool_id = ?", (tool_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"tools {tool_id} not found")
    log_activity("view", "accessibility_tools", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@student_affairs_bp.route("/tools", methods=["POST"])
@token_required
def create_tool():
    data = request.get_json(silent=True) or {}
    for field in ["tool_name", "category"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO accessibility_tools
               (tool_name, category, description, url, is_active, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["tool_name"], data["category"], data.get("description", ""), data.get("url", ""), data.get("is_active", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM accessibility_tools WHERE tool_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "accessibility_tools", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
