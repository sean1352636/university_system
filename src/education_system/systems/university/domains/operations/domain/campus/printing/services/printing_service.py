"""Printing service — database operations and business logic for the print-quota system."""

import logging
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


def init_db():
    """Create printing tables if they do not exist."""
    with get_connection() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS print_quotas (
            quota_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL UNIQUE,
            total_pages INTEGER DEFAULT 500,
            used_pages INTEGER DEFAULT 0,
            color_pages_used INTEGER DEFAULT 0,
            semester TEXT DEFAULT '',
            last_reset TEXT DEFAULT (date('now'))
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS print_jobs (
            job_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            pages INTEGER DEFAULT 1,
            copies INTEGER DEFAULT 1,
            color INTEGER DEFAULT 0,
            double_sided INTEGER DEFAULT 1,
            paper_size TEXT DEFAULT 'A4',
            printer_location TEXT DEFAULT '',
            status TEXT DEFAULT 'queued',
            cost_credits INTEGER DEFAULT 0,
            submitted_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS print_credit_transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            amount INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        )""")


# ---------------------------------------------------------------------------
# Quota helpers
# ---------------------------------------------------------------------------

def ensure_quota(student_id, conn=None):
    """Ensure a print-quota row exists for *student_id* and return it.

    When *conn* is ``None`` a new connection is obtained.
    """
    def _inner(c):
        row = c.execute("SELECT * FROM print_quotas WHERE student_id = ?", (student_id,)).fetchone()
        if not row:
            c.execute("INSERT INTO print_quotas (student_id, total_pages, used_pages) VALUES (?, 500, 0)", (student_id,))
            c.commit()
            row = c.execute("SELECT * FROM print_quotas WHERE student_id = ?", (student_id,)).fetchone()
        return row

    if conn is not None:
        return _inner(conn)
    with get_connection() as c:
        return _inner(c)


def get_quota(student_id):
    """Return the quota row for *student_id* (creating one if needed).

    Returns a dict-like ``sqlite3.Row`` with keys:
    ``total_pages``, ``used_pages``, ``color_pages_used``, etc.
    """
    return ensure_quota(student_id)


# ---------------------------------------------------------------------------
# Cost calculation
# ---------------------------------------------------------------------------

def calculate_cost(pages, copies, color, double_sided):
    """Return the credit cost for a print job.

    Parameters
    ----------
    pages : int
    copies : int
    color : bool
        True for colour printing (2 credits/page), False for mono.
    double_sided : bool
        True halves the page cost (rounded up).
    """
    rate = 2 if color else 1
    total = int(pages) * int(copies) * rate
    if double_sided:
        total = max(1, total // 2 + total % 2)
    return total


# ---------------------------------------------------------------------------
# Print jobs
# ---------------------------------------------------------------------------

def submit_print_job(
    student_id,
    file_name,
    pages,
    copies,
    color,
    double_sided,
    paper_size="A4",
    printer_location="",
):
    """Submit a print job, deduct credits, and record the transaction.

    Parameters
    ----------
    color : bool
    double_sided : bool

    Returns
    -------
    int
        The credit cost that was deducted.

    Raises
    ------
    ValueError
        If the student does not have enough remaining credits.
    """
    color_int = 1 if color else 0
    duplex_int = 1 if double_sided else 0
    cost = calculate_cost(pages, copies, color, double_sided)

    with get_connection() as conn:
        quota = ensure_quota(student_id, conn)
        remaining = quota["total_pages"] - quota["used_pages"]
        if cost > remaining:
            raise ValueError(
                f"Insufficient print credits. Need {cost}, have {remaining}."
            )

        conn.execute(
            """INSERT INTO print_jobs
                (student_id, file_name, pages, copies, color, double_sided,
                 paper_size, printer_location, cost_credits, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued')""",
            (student_id, file_name, int(pages), int(copies), color_int, duplex_int,
             paper_size, printer_location, cost),
        )

        color_pages_add = int(pages) * int(copies) if color else 0
        conn.execute(
            "UPDATE print_quotas SET used_pages = used_pages + ?, color_pages_used = color_pages_used + ? WHERE student_id = ?",
            (cost, color_pages_add, student_id),
        )

        conn.execute(
            "INSERT INTO print_credit_transactions (student_id, amount, transaction_type, description) VALUES (?, ?, 'debit', ?)",
            (student_id, -cost, f"Print job: {file_name} ({pages}p x{copies})"),
        )
        conn.commit()

    return cost


def get_print_history(student_id):
    """Return all print jobs for *student_id* in reverse chronological order."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM print_jobs WHERE student_id = ? ORDER BY submitted_at DESC",
            (student_id,),
        ).fetchall()


# ---------------------------------------------------------------------------
# Credit transactions
# ---------------------------------------------------------------------------

def get_transactions(student_id):
    """Return credit transactions for *student_id* in reverse chronological order."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM print_credit_transactions WHERE student_id = ? ORDER BY created_at DESC",
            (student_id,),
        ).fetchall()


class PaymentDeclined(Exception):
    """Raised when the payment for a credit top-up could not be taken."""


def purchase_credits(student_id, pages, price, payment_method="Cash", processed_by=None):
    """Take payment for *pages* print credits, add them to the quota and post
    the payment to Finance.

    Shared by the GUI purchase dialog and the CLI, so the Finance posting lives
    here and neither interface posts directly.

    Parameters
    ----------
    pages : int
        Number of page credits to add.
    price : str | float
        Price charged (e.g. ``"4.50"``).
    payment_method : str
        ``"Cash"``, ``"Card"`` or a student-finance-account label
        (``"student_finance"`` / ``"Student Finance Account"``). A
        student-account purchase is drawn down from the balance first; a
        cash/card purchase is posted to Finance after the credits are added.
    processed_by : str, optional
        Operator recorded on the Finance row (defaults to the student).

    Returns a dict with ``transaction_id``, ``method_label``, ``new_total``
    and ``new_balance`` (student account only). Raises :class:`PaymentDeclined`
    when the money could not be taken, in which case no credits are added.
    """
    from education_system.systems.university.services.bus import finance_bus

    pages = int(pages)
    price_f = float(price)
    if pages <= 0 or price_f < 0:
        raise ValueError("pages must be positive and price non-negative")
    processed_by = processed_by or str(student_id)

    new_balance = None
    if finance_bus.is_student_account_method(payment_method):
        method_label = "Student Finance Account"
        result = finance_bus.pay_from_student_account(
            student_id=student_id,
            amount=price_f,
            description=f"Print credits top-up ({pages} pages)",
            transaction_source="Printing",
            transaction_ref=f"CREDITS-{pages}",
            processed_by=processed_by,
        )
        if not result.get("success"):
            raise PaymentDeclined(result.get("message") or "Payment could not be processed.")
        transaction_id = result.get("transaction_id")
        new_balance = result.get("new_balance")
        ref = None
    else:
        method_label = "Cash" if str(payment_method).strip().lower() == "cash" else "Card"
        ref = f"CREDITS-{pages}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        transaction_id = f"Printing-{ref}"

    with get_connection() as conn:
        ensure_quota(student_id, conn)
        conn.execute(
            "UPDATE print_quotas SET total_pages = total_pages + ? WHERE student_id = ?",
            (pages, student_id),
        )
        conn.execute(
            "INSERT INTO print_credit_transactions (student_id, amount, transaction_type, description) VALUES (?, ?, 'credit', ?)",
            (student_id, pages,
             f"Purchased {pages} pages (\u00a3{price}) via {method_label} [{transaction_id}]"),
        )
        row = conn.execute(
            "SELECT total_pages FROM print_quotas WHERE student_id = ?", (student_id,)
        ).fetchone()
        new_total = row[0] if row else pages
        conn.commit()

    # Cash/card: post to Finance after the local write. A failure is logged
    # and does not undo the credits already granted.
    if ref is not None:
        payment_id = finance_bus.record_payment(
            student_id=student_id,
            amount=price_f,
            payment_method=method_label,
            transaction_source="Printing",
            transaction_ref=ref,
            notes=f"Print credits top-up ({pages} pages)",
            created_by=processed_by,
        )
        if not payment_id:
            logger.error("Finance posting failed for print credits %s (credits kept)", ref)

    return {
        "transaction_id": transaction_id,
        "method_label": method_label,
        "new_total": new_total,
        "new_balance": new_balance,
    }
