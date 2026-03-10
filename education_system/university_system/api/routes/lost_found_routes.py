"""Lost & found routes: item management and claims."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.university_system.api.auth import token_required
from education_system.university_system.api.pagination import get_pagination_params, paginated_response
from education_system.university_system.api.validators import validate_lost_found_create
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

lost_found_bp = Blueprint("lost_found", __name__, url_prefix="/api/lost-found")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


@lost_found_bp.route("", methods=["GET"])
@token_required
def list_items():
    status = request.args.get("status")
    category = request.args.get("category")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{search}%"
            rows = conn.execute(
                "SELECT * FROM lost_found WHERE item_description LIKE ? OR location_found LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
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
            "SELECT * FROM lost_found" + where + " ORDER BY found_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM lost_found" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "lost_found_items", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@lost_found_bp.route("/<int:item_id>", methods=["GET"])
@token_required
def get_item(item_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM lost_found WHERE id = ?", (item_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Lost & found item {item_id} not found")
    log_activity("view", "lost_found_item", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@lost_found_bp.route("", methods=["POST"])
@token_required
def create_item():
    data = request.get_json(silent=True) or {}
    validate_lost_found_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO lost_found
               (item_description, category, location_found, found_date,
                found_time, storage_location, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, 'unclaimed', ?)""",
            (
                data["item_description"],
                data.get("category", "other"),
                data.get("location_found", ""),
                data["found_date"],
                data.get("found_time", ""),
                data.get("storage_location", ""),
                data.get("notes", ""),
            ),
        )
        item_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM lost_found WHERE id = ?", (item_id,)
        ).fetchone()

    log_activity("create", "lost_found_item", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@lost_found_bp.route("/<int:item_id>/claim", methods=["POST"])
@token_required
def claim_item(item_id: int):
    with get_connection() as conn:
        item = conn.execute(
            "SELECT * FROM lost_found WHERE id = ?", (item_id,)
        ).fetchone()
    if not item:
        raise ValidationError(f"Lost & found item {item_id} not found")
    if item["status"] == "claimed":
        raise ValidationError(f"Item {item_id} has already been claimed")

    data = request.get_json(silent=True) or {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        conn.execute(
            """UPDATE lost_found
               SET status = 'claimed', claimed = 1, claimed_by_name = ?,
                   claimed_by_email = ?, claimed_by_phone = ?,
                   claim_date = ?, identification_method = ?
               WHERE id = ?""",
            (
                data.get("claimed_by_name", ""),
                data.get("claimed_by_email", ""),
                data.get("claimed_by_phone", ""),
                now,
                data.get("identification_method", ""),
                item_id,
            ),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM lost_found WHERE id = ?", (item_id,)
        ).fetchone()

    log_activity("claim", "lost_found_item", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))
