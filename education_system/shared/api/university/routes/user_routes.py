"""User management routes (admin-gated)."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import admin_required, token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import validate_user_create, validate_user_update
from education_system.post_18.university_system.core.exceptions import ValidationError
from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.infrastructure.shared_context import get_auth
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

user_bp = Blueprint("users", __name__, url_prefix="/api/users")

_SENSITIVE_FIELDS = {"password_hash", "salt"}


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys() if k not in _SENSITIVE_FIELDS}


def _get_user_or_404(user_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise ValidationError(f"User {user_id} not found")
    return _row_to_dict(row)


@user_bp.route("", methods=["GET"])
@token_required
@admin_required
def list_users():
    role = request.args.get("role")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM users WHERE username LIKE ? OR email LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        if role:
            page, per_page, offset = get_pagination_params()
            rows = conn.execute(
                "SELECT * FROM users WHERE role = ? LIMIT ? OFFSET ?",
                (role, per_page, offset),
            ).fetchall()
            total_row = conn.execute(
                "SELECT COUNT(*) FROM users WHERE role = ?", (role,)
            ).fetchone()
        else:
            page, per_page, offset = get_pagination_params()
            rows = conn.execute(
                "SELECT * FROM users LIMIT ? OFFSET ?", (per_page, offset)
            ).fetchall()
            total_row = conn.execute("SELECT COUNT(*) FROM users").fetchone()

        total = total_row[0] if total_row else 0

    log_activity("view", "users", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@user_bp.route("/<int:user_id>", methods=["GET"])
@token_required
def get_user(user_id: int):
    current = g.current_user
    if current.get("role") != "admin" and current.get("user_id") != user_id:
        return jsonify({"error": "Access denied", "status": 403}), 403

    user = _get_user_or_404(user_id)
    log_activity("view", "user", user=current.get("sub"))
    return jsonify(user)


@user_bp.route("", methods=["POST"])
@token_required
@admin_required
def create_user():
    data = request.get_json(silent=True) or {}
    validate_user_create(data)

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM users WHERE username = ?", (data["username"],)
        ).fetchone()
    if existing:
        raise ValidationError(f"Username '{data['username']}' already exists")

    auth = get_auth()
    try:
        auth.create_user(
            username=data["username"],
            password=data["password"],
            role=data["role"],
            email=data.get("email", ""),
        )
    except Exception as exc:
        raise ValidationError(f"Failed to create user: {exc}")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (data["username"],)
        ).fetchone()

    log_activity("create", "user", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@user_bp.route("/<int:user_id>", methods=["PUT"])
@token_required
@admin_required
def update_user(user_id: int):
    _get_user_or_404(user_id)
    data = request.get_json(silent=True) or {}
    validate_user_update(data)

    set_clauses = []
    values = []
    allowed = ["email", "role", "first_name", "last_name", "is_active"]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_clauses.append("updated_at = ?")
    values.append(now)

    values.append(user_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE users SET " + ", ".join(set_clauses) + " WHERE id = ?",
            values,
        )

    log_activity("update", "user", user=g.current_user.get("sub"))
    return jsonify(_get_user_or_404(user_id))


@user_bp.route("/<int:user_id>", methods=["DELETE"])
@token_required
@admin_required
def deactivate_user(user_id: int):
    _get_user_or_404(user_id)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            "UPDATE users SET is_active = 0, updated_at = ? WHERE id = ?",
            (now, user_id),
        )

    log_activity("deactivate", "user", user=g.current_user.get("sub"))
    return jsonify({"message": f"User {user_id} deactivated"})
