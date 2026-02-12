"""Finance routes: fees, payments, scholarships, and account balances."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from university_system.api.auth import token_required
from university_system.api.pagination import get_pagination_params, paginated_response
from university_system.api.validators import validate_payment_create
from university_system.core.exceptions import StudentNotFoundError, ValidationError
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

finance_bp = Blueprint("finance", __name__, url_prefix="/api/finance")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


def _get_student_or_404(student_id: str) -> None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
    if not row:
        raise StudentNotFoundError(student_id)


@finance_bp.route("/fees", methods=["GET"])
@token_required
def list_fees():
    student_id = request.args.get("student_id")
    if not student_id:
        raise ValidationError("'student_id' query parameter is required")

    _get_student_or_404(student_id)

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT sf.*, ft.fee_name, ft.description AS fee_description
               FROM student_fees sf
               LEFT JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
               WHERE sf.student_id = ?
               ORDER BY sf.due_date""",
            (student_id,),
        ).fetchall()

    log_activity("view", "student_fees", user=g.current_user.get("sub"))
    return jsonify({"student_id": student_id, "fees": [_row_to_dict(r) for r in rows]})


@finance_bp.route("/payments", methods=["GET"])
@token_required
def list_payments():
    student_id = request.args.get("student_id")

    with get_connection() as conn:
        if student_id:
            _get_student_or_404(student_id)
            page, per_page, offset = get_pagination_params()
            rows = conn.execute(
                "SELECT * FROM payments WHERE student_id = ? ORDER BY payment_date DESC LIMIT ? OFFSET ?",
                (student_id, per_page, offset),
            ).fetchall()
            total_row = conn.execute(
                "SELECT COUNT(*) FROM payments WHERE student_id = ?", (student_id,)
            ).fetchone()
        else:
            page, per_page, offset = get_pagination_params()
            rows = conn.execute(
                "SELECT * FROM payments ORDER BY payment_date DESC LIMIT ? OFFSET ?",
                (per_page, offset),
            ).fetchall()
            total_row = conn.execute("SELECT COUNT(*) FROM payments").fetchone()

        total = total_row[0] if total_row else 0

    log_activity("view", "payments", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@finance_bp.route("/payments", methods=["POST"])
@token_required
def create_payment():
    data = request.get_json(silent=True) or {}
    validate_payment_create(data)

    _get_student_or_404(data["student_id"])

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO payments
               (student_id, amount, payment_type, payment_date, description, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data["student_id"],
                float(data["amount"]),
                data["payment_type"],
                data.get("payment_date", now),
                data.get("description", ""),
                data.get("status", "completed"),
                now,
            ),
        )
        payment_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM payments WHERE payment_id = ?", (payment_id,)
        ).fetchone()

    log_activity("create", "payment", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@finance_bp.route("/scholarships", methods=["GET"])
@token_required
def list_scholarships():
    page, per_page, offset = get_pagination_params()

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM scholarships WHERE status = 'active' ORDER BY scholarship_name LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM scholarships WHERE status = 'active'"
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "scholarships", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@finance_bp.route("/account/<student_id>", methods=["GET"])
@token_required
def student_account(student_id: str):
    _get_student_or_404(student_id)

    with get_connection() as conn:
        fees_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM student_fees WHERE student_id = ?",
            (student_id,),
        ).fetchone()
        payments_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE student_id = ? AND status = 'completed'",
            (student_id,),
        ).fetchone()

    total_fees = fees_row[0] if fees_row else 0
    total_payments = payments_row[0] if payments_row else 0
    balance = total_fees - total_payments

    log_activity("view", "student_account", user=g.current_user.get("sub"))
    return jsonify({
        "student_id": student_id,
        "total_fees": total_fees,
        "total_payments": total_payments,
        "balance": balance,
    })
