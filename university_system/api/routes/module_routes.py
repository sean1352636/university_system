"""Module (course/subject) CRUD routes.

Actual ``modules`` table schema:
  module_id (PK), module_name, description, credits, semester, year,
  instructor, department, prerequisites, is_active, created_at,
  updated_at, module_code, module_type
"""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from university_system.api.auth import token_required
from university_system.api.pagination import get_pagination_params, paginated_response
from university_system.api.validators import validate_module_create, validate_module_update
from university_system.core.exceptions import CourseNotFoundError, ValidationError
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

module_bp = Blueprint("modules", __name__, url_prefix="/api/modules")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


def _get_module_or_404(module_code: str) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM modules WHERE module_code = ?", (module_code,)
        ).fetchone()
    if not row:
        raise CourseNotFoundError(f"Module {module_code} not found")
    return _row_to_dict(row)


@module_bp.route("", methods=["GET"])
@token_required
def list_modules():
    department = request.args.get("department")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{search}%"
            rows = conn.execute(
                "SELECT * FROM modules WHERE module_code LIKE ? OR module_name LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        if department:
            rows = conn.execute(
                "SELECT * FROM modules WHERE department = ?", (department,)
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        page, per_page, offset = get_pagination_params()
        rows = conn.execute(
            "SELECT * FROM modules LIMIT ? OFFSET ?", (per_page, offset)
        ).fetchall()
        total_row = conn.execute("SELECT COUNT(*) FROM modules").fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "modules", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@module_bp.route("/<module_code>", methods=["GET"])
@token_required
def get_module(module_code: str):
    mod = _get_module_or_404(module_code)
    log_activity("view", "module", user=g.current_user.get("sub"))
    return jsonify(mod)


@module_bp.route("", methods=["POST"])
@token_required
def create_module():
    data = request.get_json(silent=True) or {}
    validate_module_create(data)

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM modules WHERE module_code = ?", (data["module_code"],)
        ).fetchone()
    if existing:
        raise ValidationError(f"Module {data['module_code']} already exists")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO modules
               (module_code, module_name, description, credits, department,
                module_type, semester, year, instructor, prerequisites,
                is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (
                data["module_code"],
                data["module_name"],
                data.get("description", ""),
                data.get("credits", 0),
                data.get("department", ""),
                data.get("module_type", ""),
                data.get("semester", ""),
                data.get("year", ""),
                data.get("instructor", ""),
                data.get("prerequisites", ""),
                now,
                now,
            ),
        )

    log_activity("create", "module", user=g.current_user.get("sub"))
    return jsonify(_get_module_or_404(data["module_code"])), 201


@module_bp.route("/<module_code>", methods=["PUT"])
@token_required
def update_module(module_code: str):
    _get_module_or_404(module_code)
    data = request.get_json(silent=True) or {}
    validate_module_update(data)

    set_clauses = []
    values = []
    allowed = [
        "module_name", "department", "credits", "description",
        "module_type", "semester", "year", "instructor", "prerequisites", "is_active",
    ]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_clauses.append("updated_at = ?")
    values.append(now)

    values.append(module_code)
    with transaction() as conn:
        conn.execute(
            "UPDATE modules SET " + ", ".join(set_clauses) + " WHERE module_code = ?",
            values,
        )

    log_activity("update", "module", user=g.current_user.get("sub"))
    return jsonify(_get_module_or_404(module_code))


@module_bp.route("/<module_code>", methods=["DELETE"])
@token_required
def delete_module(module_code: str):
    _get_module_or_404(module_code)
    with transaction() as conn:
        conn.execute("DELETE FROM modules WHERE module_code = ?", (module_code,))
    log_activity("delete", "module", user=g.current_user.get("sub"))
    return jsonify({"message": f"Module {module_code} deleted"})
