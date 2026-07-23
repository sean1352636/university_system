"""Dining routes: meal accounts, transactions, and menu items."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import validate_meal_topup
from education_system.post_18.university_system.core.exceptions import StudentNotFoundError, ValidationError
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

dining_bp = Blueprint("dining", __name__, url_prefix="/api/dining")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Menu ----

@dining_bp.route("/menu", methods=["GET"])
@token_required
def list_menu():
    category = request.args.get("category")
    available_only = request.args.get("available", "").lower() == "true"

    with get_connection() as conn:
        conditions = []
        params: list = []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if available_only:
            conditions.append("available = 1")

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            "SELECT * FROM menu_items" + where + " ORDER BY category, name", params
        ).fetchall()

    log_activity("view", "menu_items", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- Meal Accounts ----

@dining_bp.route("/accounts/<student_id>", methods=["GET"])
@token_required
def get_account(student_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM meal_accounts WHERE student_id = ?", (student_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Meal account for student {student_id} not found")
    log_activity("view", "meal_account", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@dining_bp.route("/accounts/topup", methods=["POST"])
@token_required
def topup_account():
    data = request.get_json(silent=True) or {}
    validate_meal_topup(data)

    student_id = data["student_id"]
    amount = float(data["amount"])

    with get_connection() as conn:
        account = conn.execute(
            "SELECT * FROM meal_accounts WHERE student_id = ?", (student_id,)
        ).fetchone()
    if not account:
        raise ValidationError(f"Meal account for student {student_id} not found")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_balance = float(account["balance"]) + amount

    with transaction() as conn:
        conn.execute(
            "UPDATE meal_accounts SET balance = ?, last_updated = ? WHERE student_id = ?",
            (new_balance, now, student_id),
        )
        conn.execute(
            """INSERT INTO meal_transactions
               (student_id, transaction_type, amount, description, transaction_date, balance_after)
               VALUES (?, 'topup', ?, ?, ?, ?)""",
            (student_id, amount, data.get("description", "Account top-up"), now, new_balance),
        )

    log_activity("create", "meal_topup", user=g.current_user.get("sub"))
    return jsonify({"student_id": student_id, "amount": amount, "new_balance": new_balance}), 201


# ---- Transactions ----

@dining_bp.route("/transactions", methods=["GET"])
@token_required
def list_transactions():
    student_id = request.args.get("student_id")
    if not student_id:
        raise ValidationError("'student_id' query parameter is required")

    page, per_page, offset = get_pagination_params()

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM meal_transactions WHERE student_id = ? ORDER BY transaction_date DESC LIMIT ? OFFSET ?",
            (student_id, per_page, offset),
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM meal_transactions WHERE student_id = ?", (student_id,)
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "meal_transactions", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))
