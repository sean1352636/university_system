"""Student ID routes: ID cards, replacements, and access permissions."""

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

student_id_bp = Blueprint("student_id", __name__, url_prefix="/api/student-id")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- cards ----

@student_id_bp.route("/cards", methods=["GET"])
@token_required
def list_cards():
    search = request.args.get("search")
    student_id = request.args.get("student_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM student_id_cards WHERE student_name LIKE ? OR card_number LIKE ?",
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

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM student_id_cards" + where + " ORDER BY card_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM student_id_cards" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "student_id_cards", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@student_id_bp.route("/cards/<int:card_id>", methods=["GET"])
@token_required
def get_card(card_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_id_cards WHERE card_id = ?", (card_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"cards {card_id} not found")
    log_activity("view", "student_id_cards", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@student_id_bp.route("/cards", methods=["POST"])
@token_required
def create_card():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "student_name", "card_number"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO student_id_cards
               (student_id, student_name, card_number, photo_url, issue_date, expiry_date, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["student_name"], data["card_number"], data.get("photo_url", ""), data.get("issue_date", ""), data.get("expiry_date", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_id_cards WHERE card_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "student_id_cards", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- replacements ----

@student_id_bp.route("/replacements", methods=["GET"])
@token_required
def list_replacements():
    student_id = request.args.get("student_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM id_card_replacements" + where + " ORDER BY replacement_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM id_card_replacements" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "id_card_replacements", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@student_id_bp.route("/replacements/<int:replacement_id>", methods=["GET"])
@token_required
def get_replacement(replacement_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM id_card_replacements WHERE replacement_id = ?", (replacement_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"replacements {replacement_id} not found")
    log_activity("view", "id_card_replacements", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@student_id_bp.route("/replacements", methods=["POST"])
@token_required
def create_replacement():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "reason"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO id_card_replacements
               (student_id, reason, fee, payment_status, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (data["student_id"], data["reason"], data.get("fee", ""), data.get("payment_status", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM id_card_replacements WHERE replacement_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "id_card_replacements", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
