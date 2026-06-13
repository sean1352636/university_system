"""Library routes: book catalog, loans, and reservations."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import validate_book_loan_create, validate_book_reservation_create
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

library_bp = Blueprint("library", __name__, url_prefix="/api/library")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Books ----

@library_bp.route("/books", methods=["GET"])
@token_required
def list_books():
    search = request.args.get("search")
    category = request.args.get("category")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM books WHERE title LIKE ? OR author LIKE ? OR isbn LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params = []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM books" + where + " ORDER BY title LIMIT ? OFFSET ?", params
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM books" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "books", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@library_bp.route("/books/<book_id>", methods=["GET"])
@token_required
def get_book(book_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM books WHERE book_id = ?", (book_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Book {book_id} not found")
    log_activity("view", "book", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Loans ----

@library_bp.route("/loans", methods=["GET"])
@token_required
def list_loans():
    user_id = request.args.get("user_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params = []
        if user_id:
            conditions.append("bl.user_id = ?")
            params.append(user_id)
        if status:
            conditions.append("bl.status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT bl.*, b.title, b.author"
            " FROM book_loans bl"
            " LEFT JOIN books b ON bl.book_id = b.book_id"
            + where + " ORDER BY bl.checkout_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM book_loans bl" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "book_loans", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@library_bp.route("/loans", methods=["POST"])
@token_required
def create_loan():
    data = request.get_json(silent=True) or {}
    validate_book_loan_create(data)

    with get_connection() as conn:
        book = conn.execute(
            "SELECT status FROM books WHERE book_id = ?", (data["book_id"],)
        ).fetchone()
        if not book:
            raise ValidationError(f"Book {data['book_id']} not found")
        if book["status"] != "available":
            raise ValidationError(f"Book {data['book_id']} is not available (status: {book['status']})")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO book_loans
               (book_id, user_id, checkout_date, due_date, status, checkout_method, notes)
               VALUES (?, ?, ?, ?, 'active', ?, ?)""",
            (
                data["book_id"],
                data["user_id"],
                now,
                data["due_date"],
                data.get("checkout_method", "manual"),
                data.get("notes", ""),
            ),
        )
        loan_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "UPDATE books SET status = 'checked_out' WHERE book_id = ?",
            (data["book_id"],),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM book_loans WHERE loan_id = ?", (loan_id,)
        ).fetchone()

    log_activity("create", "book_loan", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@library_bp.route("/loans/<int:loan_id>/return", methods=["POST"])
@token_required
def return_loan(loan_id: int):
    with get_connection() as conn:
        loan = conn.execute(
            "SELECT * FROM book_loans WHERE loan_id = ?", (loan_id,)
        ).fetchone()
    if not loan:
        raise ValidationError(f"Loan {loan_id} not found")
    if loan["status"] != "active":
        raise ValidationError(f"Loan {loan_id} is not active (status: {loan['status']})")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            "UPDATE book_loans SET status = 'returned', return_date = ? WHERE loan_id = ?",
            (now, loan_id),
        )
        conn.execute(
            "UPDATE books SET status = 'available' WHERE book_id = ?",
            (loan["book_id"],),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM book_loans WHERE loan_id = ?", (loan_id,)
        ).fetchone()

    log_activity("return", "book_loan", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Reservations ----

@library_bp.route("/reservations", methods=["GET"])
@token_required
def list_reservations():
    user_id = request.args.get("user_id")

    with get_connection() as conn:
        if user_id:
            rows = conn.execute(
                """SELECT br.*, b.title, b.author
                   FROM book_reservations br
                   LEFT JOIN books b ON br.book_id = b.book_id
                   WHERE br.user_id = ?
                   ORDER BY br.reservation_date DESC""",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT br.*, b.title, b.author
                   FROM book_reservations br
                   LEFT JOIN books b ON br.book_id = b.book_id
                   ORDER BY br.reservation_date DESC"""
            ).fetchall()

    log_activity("view", "book_reservations", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@library_bp.route("/reservations", methods=["POST"])
@token_required
def create_reservation():
    data = request.get_json(silent=True) or {}
    validate_book_reservation_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO book_reservations
               (book_id, user_id, reservation_date, expiry_date, status)
               VALUES (?, ?, ?, ?, 'active')""",
            (
                data["book_id"],
                data["user_id"],
                now,
                data.get("expiry_date", ""),
            ),
        )
        res_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM book_reservations WHERE reservation_id = ?", (res_id,)
        ).fetchone()

    log_activity("create", "book_reservation", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
