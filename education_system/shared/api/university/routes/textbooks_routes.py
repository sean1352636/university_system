"""Textbooks routes: textbooks, listings, and exchanges."""

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

textbooks_bp = Blueprint("textbooks", __name__, url_prefix="/api/textbooks")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- textbooks ----

@textbooks_bp.route("/textbooks", methods=["GET"])
@token_required
def list_textbooks():
    search = request.args.get("search")
    course_id = request.args.get("course_id")
    edition = request.args.get("edition")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM textbooks WHERE title LIKE ? OR author LIKE ? OR isbn LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if course_id:
            conditions.append("course_id = ?")
            params.append(course_id)
        if edition:
            conditions.append("edition = ?")
            params.append(edition)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM textbooks" + where + " ORDER BY textbook_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM textbooks" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "textbooks", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@textbooks_bp.route("/textbooks/<int:textbook_id>", methods=["GET"])
@token_required
def get_textbook(textbook_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM textbooks WHERE textbook_id = ?", (textbook_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"textbooks {textbook_id} not found")
    log_activity("view", "textbooks", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@textbooks_bp.route("/textbooks", methods=["POST"])
@token_required
def create_textbook():
    data = request.get_json(silent=True) or {}
    for field in ["title", "author", "isbn"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO textbooks
               (title, author, isbn, course_id, edition, publisher, price, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["title"], data["author"], data["isbn"], data.get("course_id", ""), data.get("edition", ""), data.get("publisher", ""), data.get("price", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM textbooks WHERE textbook_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "textbooks", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- listings ----

@textbooks_bp.route("/listings", methods=["GET"])
@token_required
def list_listings():
    search = request.args.get("search")
    seller_id = request.args.get("seller_id")
    status = request.args.get("status")
    condition = request.args.get("condition")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM textbook_listings WHERE title LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if seller_id:
            conditions.append("seller_id = ?")
            params.append(seller_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if condition:
            conditions.append("condition = ?")
            params.append(condition)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM textbook_listings" + where + " ORDER BY listing_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM textbook_listings" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "textbook_listings", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@textbooks_bp.route("/listings/<int:listing_id>", methods=["GET"])
@token_required
def get_listing(listing_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM textbook_listings WHERE listing_id = ?", (listing_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"listings {listing_id} not found")
    log_activity("view", "textbook_listings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@textbooks_bp.route("/listings", methods=["POST"])
@token_required
def create_listing():
    data = request.get_json(silent=True) or {}
    for field in ["seller_id", "textbook_id", "price", "condition"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO textbook_listings
               (seller_id, textbook_id, price, condition, notes, photo_url, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["seller_id"], data["textbook_id"], data["price"], data["condition"], data.get("notes", ""), data.get("photo_url", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM textbook_listings WHERE listing_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "textbook_listings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
