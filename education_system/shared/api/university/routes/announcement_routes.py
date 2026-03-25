"""Announcement routes: campus-wide announcements."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import admin_required, token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import validate_announcement_create, validate_announcement_update
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

announcement_bp = Blueprint("announcements", __name__, url_prefix="/api/announcements")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


@announcement_bp.route("", methods=["GET"])
@token_required
def list_announcements():
    target_audience = request.args.get("audience")
    active_only = request.args.get("active", "true").lower() != "false"

    with get_connection() as conn:
        conditions = []
        params: list = []
        if active_only:
            conditions.append("is_active = 1")
        if target_audience:
            conditions.append("target_audience = ?")
            params.append(target_audience)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM announcements" + where + " ORDER BY is_urgent DESC, created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM announcements" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "announcements", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@announcement_bp.route("/<int:announcement_id>", methods=["GET"])
@token_required
def get_announcement(announcement_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM announcements WHERE id = ?", (announcement_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Announcement {announcement_id} not found")
    log_activity("view", "announcement", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@announcement_bp.route("", methods=["POST"])
@token_required
@admin_required
def create_announcement():
    data = request.get_json(silent=True) or {}
    validate_announcement_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO announcements
               (creator_id, title, content, target_audience, is_urgent,
                is_active, start_date, end_date, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)""",
            (
                g.current_user.get("user_id"),
                data["title"],
                data["content"],
                data["target_audience"],
                data.get("is_urgent", 0),
                data["start_date"],
                data.get("end_date"),
                now,
                now,
            ),
        )
        ann_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM announcements WHERE id = ?", (ann_id,)
        ).fetchone()

    log_activity("create", "announcement", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@announcement_bp.route("/<int:announcement_id>", methods=["PUT"])
@token_required
@admin_required
def update_announcement(announcement_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM announcements WHERE id = ?", (announcement_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Announcement {announcement_id} not found")

    data = request.get_json(silent=True) or {}
    validate_announcement_update(data)

    set_clauses = []
    values = []
    allowed = [
        "title", "content", "target_audience", "is_urgent",
        "is_active", "start_date", "end_date",
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
    values.append(announcement_id)

    with transaction() as conn:
        conn.execute(
            "UPDATE announcements SET " + ", ".join(set_clauses) + " WHERE id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM announcements WHERE id = ?", (announcement_id,)
        ).fetchone()

    log_activity("update", "announcement", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@announcement_bp.route("/<int:announcement_id>", methods=["DELETE"])
@token_required
@admin_required
def delete_announcement(announcement_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM announcements WHERE id = ?", (announcement_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Announcement {announcement_id} not found")

    with transaction() as conn:
        conn.execute("DELETE FROM announcements WHERE id = ?", (announcement_id,))

    log_activity("delete", "announcement", user=g.current_user.get("sub"))
    return jsonify({"message": f"Announcement {announcement_id} deleted"})
