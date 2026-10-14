"""Library finance (fines, fine revenue, book costs) shared by GUI and CLI.

Lifted from the Finance GUI's Library Finance manager
(``interfaces/gui/finance/library_finance_manager.py``).  Fines live on
``book_loans.fine_amount``; fine payments are ordinary ``payments`` rows,
allocated against the student's unpaid "Library Fee" (``fee_type_id`` 3)
when one exists; book purchase costs live on the ``books`` row.

Email notifications are best-effort: the email stack is imported lazily and
every send returns ``False`` instead of raising.
"""

from __future__ import annotations

import csv
from datetime import datetime
import logging
from typing import Any

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

#: ``fee_types.fee_type_id`` of the seeded "Library Fee" row.
LIBRARY_FEE_TYPE_ID = 3

#: Fines below a penny are rounding noise and are never shown.
MIN_FINE = 0.01

#: Payment methods offered when settling a fine.
FINE_PAYMENT_METHODS: tuple[str, ...] = ("Cash", "Card", "Bank Transfer", "Online")

_FINES_SELECT = """
    SELECT
        bl.loan_id,
        bl.user_id,
        s.first_name || ' ' || s.last_name AS name,
        bl.book_id,
        b.title,
        CAST(julianday('now') - julianday(bl.due_date) AS INTEGER) AS days_overdue,
        bl.fine_amount,
        bl.status
    FROM book_loans bl
    JOIN books b ON bl.book_id = b.book_id
    LEFT JOIN students s ON bl.user_id = s.student_id
    WHERE bl.fine_amount >= ?
"""

_FINE_REVENUE_FROM = """
    FROM payment_allocations pa
    JOIN payments p ON pa.payment_id = p.payment_id
    JOIN student_fees sf ON pa.student_fee_id = sf.student_fee_id
    WHERE sf.fee_type_id = ?
"""


def _fine_row(r) -> dict[str, Any]:
    return {
        "loan_id": r[0],
        "user_id": r[1],
        "name": r[2] or "N/A",
        "book_id": r[3],
        "title": r[4] or "",
        "days_overdue": int(r[5] or 0),
        "fine_amount": float(r[6] or 0),
        "status": r[7] or "",
    }


# --------------------------------------------------------------------------- #
# Fines
# --------------------------------------------------------------------------- #
def list_fines(search: str | None = None) -> list[dict[str, Any]]:
    """Outstanding fines, largest first; optionally filtered by user id or name."""
    sql = _FINES_SELECT
    params: list[Any] = [MIN_FINE]
    term = (search or "").strip()
    if term:
        sql += " AND (bl.user_id LIKE ? OR s.first_name || ' ' || s.last_name LIKE ?)"
        params += [f"%{term}%", f"%{term}%"]
    sql += " ORDER BY bl.fine_amount DESC"
    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [_fine_row(r) for r in rows]


def get_fine(loan_id: int) -> dict[str, Any] | None:
    """One loan's fine row (any amount), or ``None`` when the loan is unknown."""
    conn = get_connection()
    try:
        row = conn.execute(_FINES_SELECT + " AND bl.loan_id = ?", (0, loan_id)).fetchone()
    finally:
        conn.close()
    return _fine_row(row) if row else None


def _loan_details(conn, loan_id: int) -> tuple | None:
    return conn.execute(
        """
        SELECT bl.user_id, b.title, bl.due_date,
               CAST((julianday('now') - julianday(bl.due_date)) AS INTEGER)
        FROM book_loans bl
        JOIN books b ON bl.book_id = b.book_id
        WHERE bl.loan_id = ?
        """,
        (loan_id,),
    ).fetchone()


def create_fine(loan_id: int, amount: float, notify: bool = True) -> dict[str, Any]:
    """Set a fine on a loan and (optionally) email the borrower.

    Returns ``{"loan_id", "amount", "email_sent", "email"}``.
    """
    if amount is None or float(amount) <= 0:
        raise ValueError("Fine amount must be greater than 0.")
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE book_loans SET fine_amount = ? WHERE loan_id = ?", (float(amount), loan_id)
        )
        if cur.rowcount == 0:
            raise ValueError(f"Loan ID {loan_id} not found.")
        details = _loan_details(conn, loan_id)
        conn.commit()
    finally:
        conn.close()

    result = {"loan_id": loan_id, "amount": float(amount), "email_sent": False, "email": None}
    if notify and details:
        user_id, title, due_date, days_overdue = details
        user_info = get_user_email(user_id)
        if user_info:
            result["email"] = user_info["email"]
            result["email_sent"] = send_fine_notification_email(
                user_info, float(amount), title, due_date, max(int(days_overdue or 0), 0)
            )
    return result


def update_fine(loan_id: int, amount: float) -> None:
    """Replace the fine on a loan (``0`` clears it)."""
    if amount is None or float(amount) < 0:
        raise ValueError("Fine amount cannot be negative.")
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE book_loans SET fine_amount = ? WHERE loan_id = ?", (float(amount), loan_id)
        )
        if cur.rowcount == 0:
            raise ValueError(f"Loan ID {loan_id} not found.")
        conn.commit()
    finally:
        conn.close()


def waive_fine(
    loan_id: int,
    reason: str = "Fine waived by library administration",
    notify: bool = True,
) -> dict[str, Any]:
    """Zero a loan's fine and (optionally) email the borrower."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT bl.user_id, b.title, bl.fine_amount
            FROM book_loans bl JOIN books b ON bl.book_id = b.book_id
            WHERE bl.loan_id = ?
            """,
            (loan_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Loan ID {loan_id} not found.")
        conn.execute("UPDATE book_loans SET fine_amount = 0 WHERE loan_id = ?", (loan_id,))
        conn.commit()
    finally:
        conn.close()

    user_id, title, previous = row[0], row[1], float(row[2] or 0)
    result = {"loan_id": loan_id, "waived_amount": previous, "email_sent": False, "email": None}
    if notify:
        user_info = get_user_email(user_id)
        if user_info:
            result["email"] = user_info["email"]
            result["email_sent"] = send_fine_waived_email(user_info, previous, title, reason)
    return result


def process_fine_payment(
    loan_id: int,
    payment_amount: float,
    payment_method: str = "Cash",
    notify: bool = True,
) -> dict[str, Any]:
    """Take a payment against a loan's fine and record it in Finance.

    Reduces ``book_loans.fine_amount``, inserts a completed ``payments`` row,
    allocates it to the student's unpaid Library Fee when one exists, posts to
    the ledger and emails a receipt.  Overpayment is rejected.
    """
    fine = get_fine(loan_id)
    if fine is None:
        raise ValueError(f"Loan ID {loan_id} not found.")
    if payment_amount is None or float(payment_amount) <= 0:
        raise ValueError("Payment must be greater than 0.")
    if float(payment_amount) > fine["fine_amount"] + 1e-9:
        raise ValueError("Payment exceeds fine amount.")
    if payment_method not in FINE_PAYMENT_METHODS:
        raise ValueError(f"Payment method must be one of: {', '.join(FINE_PAYMENT_METHODS)}.")

    user_id = fine["user_id"]
    amount = float(payment_amount)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_fine = round(fine["fine_amount"] - amount, 2)
    if new_fine < MIN_FINE:
        new_fine = 0.0

    conn = get_connection()
    try:
        conn.execute("UPDATE book_loans SET fine_amount = ? WHERE loan_id = ?", (new_fine, loan_id))
        cur = conn.execute(
            """
            INSERT INTO payments
            (student_id, amount, currency, payment_method, payment_date, status, notes, created_at)
            VALUES (?, ?, 'GBP', ?, DATE('now'), 'completed',
                    'Library fine payment - Loan ID: ' || ?, ?)
            """,
            (user_id, amount, payment_method, loan_id, now),
        )
        payment_id = int(cur.lastrowid)
        fee = conn.execute(
            """
            SELECT student_fee_id FROM student_fees
            WHERE student_id = ? AND fee_type_id = ? AND status = 'unpaid'
            ORDER BY created_at DESC LIMIT 1
            """,
            (user_id, LIBRARY_FEE_TYPE_ID),
        ).fetchone()
        if fee:
            conn.execute(
                "INSERT INTO payment_allocations (payment_id, student_fee_id, amount, created_at) "
                "VALUES (?, ?, ?, ?)",
                (payment_id, fee[0], amount, now),
            )
        conn.commit()
    finally:
        conn.close()

    try:
        from education_system.systems.university.domains.finance.domain.ledger import notify_ledger

        notify_ledger("payment", payment_id, posted_by="library_fine")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("ledger hook failed: %s", exc)

    result = {
        "loan_id": loan_id,
        "payment_id": payment_id,
        "paid": amount,
        "remaining_fine": new_fine,
        "allocated": bool(fee),
        "email_sent": False,
        "email": None,
    }
    if notify:
        user_info = get_user_email(user_id)
        if user_info:
            result["email"] = user_info["email"]
            result["email_sent"] = send_payment_receipt_email(
                user_info, fine["fine_amount"], amount, payment_method,
                fine["title"] or "Unknown Book", f"LIB-{payment_id}", now,
            )
    return result


# --------------------------------------------------------------------------- #
# Fine revenue
# --------------------------------------------------------------------------- #
def revenue_report(start_date: str, end_date: str) -> dict[str, Any]:
    """Fine revenue summary plus a monthly breakdown for a date range."""
    if not start_date or not end_date:
        raise ValueError("Both start and end dates are required.")
    conn = get_connection()
    try:
        stats = conn.execute(
            "SELECT COUNT(DISTINCT p.payment_id), SUM(pa.amount), AVG(pa.amount)"
            + _FINE_REVENUE_FROM
            + " AND p.payment_date BETWEEN ? AND ?",
            (LIBRARY_FEE_TYPE_ID, start_date, end_date),
        ).fetchone()
        monthly = conn.execute(
            "SELECT strftime('%Y-%m', p.payment_date) AS month, COUNT(p.payment_id), SUM(pa.amount)"
            + _FINE_REVENUE_FROM
            + " AND p.payment_date BETWEEN ? AND ? GROUP BY month ORDER BY month DESC",
            (LIBRARY_FEE_TYPE_ID, start_date, end_date),
        ).fetchall()
    finally:
        conn.close()
    return {
        "start_date": start_date,
        "end_date": end_date,
        "payment_count": int(stats[0] or 0) if stats else 0,
        "total_revenue": float(stats[1] or 0) if stats else 0.0,
        "avg_payment": float(stats[2] or 0) if stats else 0.0,
        "monthly": [(str(m[0]), int(m[1] or 0), float(m[2] or 0)) for m in monthly],
    }


def revenue_report_text(report: dict[str, Any]) -> str:
    """Plain-text rendering of :func:`revenue_report`."""
    bar = "=" * 60
    lines = [
        "",
        "LIBRARY FINE REVENUE REPORT",
        f"Period: {report['start_date']} to {report['end_date']}",
        bar,
        "",
        "SUMMARY STATISTICS:",
        f"  Total Payments Received:    {report['payment_count']:,}",
        f"  Total Revenue:              £{report['total_revenue']:,.2f}",
        f"  Average Payment:            £{report['avg_payment']:,.2f}",
        "",
        "MONTHLY BREAKDOWN:",
        bar,
        "Month          Payments      Revenue",
        "-" * 60,
    ]
    lines += [f"{m:<14} {n:>8}      £{rev:>10,.2f}" for m, n, rev in report["monthly"]]
    lines.append(bar)
    return "\n".join(lines) + "\n"


def revenue_rows(start_date: str, end_date: str) -> list[tuple]:
    """Individual fine payments in a range (date, student, amount, method, notes)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT p.payment_date, p.student_id, pa.amount, p.payment_method, p.notes"
            + _FINE_REVENUE_FROM
            + " AND p.payment_date BETWEEN ? AND ? ORDER BY p.payment_date DESC",
            (LIBRARY_FEE_TYPE_ID, start_date, end_date),
        ).fetchall()
    finally:
        conn.close()
    return [tuple(r) for r in rows]


def export_revenue_csv(filename: str, start_date: str, end_date: str) -> int:
    """Write the fine payments in a range to *filename*; returns rows written."""
    if not start_date or not end_date:
        raise ValueError("Both start and end dates are required.")
    rows = revenue_rows(start_date, end_date)
    with open(filename, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Date", "Student ID", "Amount", "Payment Method", "Notes"])
        writer.writerows(rows)
    return len(rows)


# --------------------------------------------------------------------------- #
# Book costs
# --------------------------------------------------------------------------- #
_COST_COLUMNS = (
    ("purchase_price", "REAL DEFAULT 0.0"),
    ("purchase_date", "TEXT"),
    ("supplier", "TEXT"),
    ("quantity", "INTEGER DEFAULT 1"),
)


def ensure_book_cost_columns() -> None:
    """Add the purchase-cost columns to ``books`` when they are missing."""
    conn = get_connection()
    try:
        present = {row[1] for row in conn.execute("PRAGMA table_info(books)")}
        for name, decl in _COST_COLUMNS:
            if name not in present:
                conn.execute(f"ALTER TABLE books ADD COLUMN {name} {decl}")
        conn.commit()
    finally:
        conn.close()


def list_book_costs() -> list[dict[str, Any]]:
    """Every book with its purchase price, date, supplier and quantity."""
    ensure_book_cost_columns()
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT book_id, title, author, isbn, COALESCE(purchase_price, 0.0),
                   purchase_date, supplier, COALESCE(quantity, 1)
            FROM books
            ORDER BY title
            """
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "book_id": r[0],
            "title": r[1] or "",
            "author": r[2] or "N/A",
            "isbn": r[3] or "N/A",
            "purchase_price": float(r[4] or 0),
            "purchase_date": r[5] or "N/A",
            "supplier": r[6] or "N/A",
            "quantity": int(r[7] or 1),
        }
        for r in rows
    ]


def set_book_cost(
    book_id: str,
    purchase_price: float,
    purchase_date: str | None = None,
    supplier: str = "",
    quantity: int = 1,
) -> None:
    """Record (or replace) a book's purchase cost details."""
    if purchase_price is None or float(purchase_price) < 0 or int(quantity) < 1:
        raise ValueError("Price and quantity must be positive.")
    ensure_book_cost_columns()
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE books SET purchase_price = ?, purchase_date = ?, supplier = ?, quantity = ? "
            "WHERE book_id = ?",
            (
                float(purchase_price),
                purchase_date or datetime.now().strftime("%Y-%m-%d"),
                (supplier or "").strip(),
                int(quantity),
                str(book_id).strip(),
            ),
        )
        if cur.rowcount == 0:
            raise ValueError(f"Book ID {book_id} not found.")
        conn.commit()
    finally:
        conn.close()


def cost_analysis() -> dict[str, float]:
    """Collection size and investment statistics."""
    ensure_book_cost_columns()
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*),
                   SUM(COALESCE(purchase_price, 0) * COALESCE(quantity, 1)),
                   AVG(COALESCE(purchase_price, 0)),
                   MAX(COALESCE(purchase_price, 0)),
                   MIN(COALESCE(purchase_price, 0))
            FROM books
            """
        ).fetchone()
    finally:
        conn.close()
    return {
        "total_books": int(row[0] or 0),
        "total_cost": float(row[1] or 0),
        "avg_price": float(row[2] or 0),
        "max_price": float(row[3] or 0),
        "min_price": float(row[4] or 0),
    }


def cost_analysis_text(stats: dict[str, float] | None = None) -> str:
    s = stats or cost_analysis()
    bar = "=" * 60
    return "\n".join(
        [
            "",
            "BOOK COST ANALYSIS",
            bar,
            "",
            "SUMMARY:",
            f"  Total Books in Collection:  {s['total_books']:,}",
            f"  Total Investment:           £{s['total_cost']:,.2f}",
            f"  Average Book Price:         £{s['avg_price']:,.2f}",
            f"  Most Expensive Book:        £{s['max_price']:,.2f}",
            f"  Least Expensive Book:       £{s['min_price']:,.2f}",
            "",
            bar,
            "",
        ]
    )


# --------------------------------------------------------------------------- #
# Overview
# --------------------------------------------------------------------------- #
def library_overview() -> dict[str, float]:
    """Outstanding fines, this-month and YTD fine revenue, and book investment."""
    ensure_book_cost_columns()
    conn = get_connection()
    try:
        outstanding = conn.execute(
            "SELECT SUM(fine_amount) FROM book_loans WHERE fine_amount >= ?", (MIN_FINE,)
        ).fetchone()[0]
        this_month = conn.execute(
            "SELECT SUM(pa.amount)" + _FINE_REVENUE_FROM
            + " AND strftime('%Y-%m', p.payment_date) = strftime('%Y-%m', 'now')",
            (LIBRARY_FEE_TYPE_ID,),
        ).fetchone()[0]
        ytd = conn.execute(
            "SELECT SUM(pa.amount)" + _FINE_REVENUE_FROM
            + " AND strftime('%Y', p.payment_date) = strftime('%Y', 'now')",
            (LIBRARY_FEE_TYPE_ID,),
        ).fetchone()[0]
        investment = conn.execute(
            "SELECT SUM(COALESCE(purchase_price, 0) * COALESCE(quantity, 1)) FROM books"
        ).fetchone()[0]
    finally:
        conn.close()
    return {
        "outstanding_fines": float(outstanding or 0),
        "collected_this_month": float(this_month or 0),
        "revenue_ytd": float(ytd or 0),
        "book_investment": float(investment or 0),
    }


# --------------------------------------------------------------------------- #
# Email helpers (best-effort)
# --------------------------------------------------------------------------- #
def get_user_email(user_id) -> dict[str, str] | None:
    """Email + name for a ``users`` row, or ``None``."""
    try:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT email, first_name, last_name FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Error getting user email: %s", exc)
        return None
    if not row:
        return None
    return {
        "email": row[0],
        "first_name": row[1],
        "last_name": row[2],
        "full_name": f"{row[1]} {row[2]}",
    }


def _send_templated(template: str, context: dict[str, str], fallback_subject: str,
                    fallback_body: str, recipient: str) -> bool:
    try:
        from education_system.systems.university.infrastructure.email.email_service import (
            send_email_as_system,
        )
        from education_system.systems.university.infrastructure.email.template_utils import (
            render_template,
        )

        subject, body = render_template(template, context)
        if not subject or not body:
            subject, body = fallback_subject, fallback_body
        send_email_as_system(
            recipient_email=recipient, subject=subject, body=body, system_name="Library System"
        )
        return True
    except Exception as exc:
        logger.warning("Error sending %s email: %s", template, exc)
        return False


def send_fine_notification_email(user_info, fine_amount, book_title, due_date, days_overdue) -> bool:
    if not user_info or not user_info.get("email"):
        return False
    body = (
        f"Dear {user_info['full_name']},\n\n"
        "This is to notify you that a library fine has been assessed on your account.\n\n"
        "FINE DETAILS:\n"
        f"Book Title:      {book_title}\n"
        f"Due Date:        {due_date}\n"
        f"Days Overdue:    {days_overdue}\n"
        f"Fine Amount:     £{fine_amount:.2f}\n\n"
        "Please return the book and pay the fine at your earliest convenience.\n\n"
        "Thank you,\nUniversity Library System\n"
    )
    return _send_templated(
        "library/fine_notice",
        {
            "student_name": user_info["full_name"],
            "book_title": book_title,
            "due_date": due_date,
            "days_overdue": str(days_overdue),
            "fine_amount": f"{fine_amount:.2f}",
        },
        "Library Fine Notice - Overdue Book",
        body,
        user_info["email"],
    )


def send_payment_receipt_email(user_info, fine_amount, payment_amount, payment_method,
                               book_title, transaction_id, payment_date) -> bool:
    if not user_info or not user_info.get("email"):
        return False
    body = (
        f"Dear {user_info['full_name']},\n\n"
        "Thank you for your payment. This email confirms your library fine payment.\n\n"
        "PAYMENT RECEIPT\n"
        f"Receipt Number:  {transaction_id}\n"
        f"Payment Date:    {payment_date}\n"
        f"Payment Method:  {payment_method}\n\n"
        "FINE DETAILS:\n"
        f"Book Title:      {book_title}\n"
        f"Original Fine:   £{fine_amount:.2f}\n"
        f"Amount Paid:     £{payment_amount:.2f}\n\n"
        "Your payment has been processed successfully.\n\n"
        "Best regards,\nUniversity Library System\n"
    )
    return _send_templated(
        "library/payment_receipt",
        {
            "student_name": user_info["full_name"],
            "transaction_id": transaction_id,
            "payment_date": payment_date,
            "payment_method": payment_method,
            "book_title": book_title,
            "fine_amount": f"{fine_amount:.2f}",
            "payment_amount": f"{payment_amount:.2f}",
        },
        "Library Fine Payment Receipt",
        body,
        user_info["email"],
    )


def send_fine_waived_email(user_info, fine_amount, book_title,
                           waiver_reason="Administrative action") -> bool:
    if not user_info or not user_info.get("email"):
        return False
    body = (
        f"Dear {user_info['full_name']},\n\n"
        "Good news! A library fine on your account has been waived.\n\n"
        "WAIVED FINE DETAILS:\n"
        f"Book Title:      {book_title}\n"
        f"Fine Amount:     £{fine_amount:.2f}\n"
        f"Reason:          {waiver_reason}\n"
        "Status:          WAIVED - No payment required\n\n"
        "This fine has been removed from your account.\n\n"
        "Best regards,\nUniversity Library System\n"
    )
    return _send_templated(
        "library/fine_waived",
        {
            "student_name": user_info["full_name"],
            "book_title": book_title,
            "fine_amount": f"{fine_amount:.2f}",
            "waiver_reason": waiver_reason,
        },
        "Library Fine Waived - Good News!",
        body,
        user_info["email"],
    )


__all__ = [
    "FINE_PAYMENT_METHODS",
    "LIBRARY_FEE_TYPE_ID",
    "MIN_FINE",
    "cost_analysis",
    "cost_analysis_text",
    "create_fine",
    "ensure_book_cost_columns",
    "export_revenue_csv",
    "get_fine",
    "get_user_email",
    "library_overview",
    "list_book_costs",
    "list_fines",
    "process_fine_payment",
    "revenue_report",
    "revenue_report_text",
    "revenue_rows",
    "send_fine_notification_email",
    "send_fine_waived_email",
    "send_payment_receipt_email",
    "set_book_cost",
    "update_fine",
    "waive_fine",
]
