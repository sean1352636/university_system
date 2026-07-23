"""Printing service — database operations and business logic for the print-quota system."""

import logging

from education_system.post_18.university_system.infrastructure.database.db import get_connection

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


def purchase_credits(student_id, pages, price):
    """Add *pages* to the student's quota and record a credit transaction.

    Parameters
    ----------
    pages : int
        Number of page credits to add.
    price : str
        Display price (e.g. ``"4.50"``), stored in the transaction description.
    """
    with get_connection() as conn:
        ensure_quota(student_id, conn)
        conn.execute(
            "UPDATE print_quotas SET total_pages = total_pages + ? WHERE student_id = ?",
            (pages, student_id),
        )
        conn.execute(
            "INSERT INTO print_credit_transactions (student_id, amount, transaction_type, description) VALUES (?, ?, 'credit', ?)",
            (student_id, pages, f"Purchased {pages} pages (\u00a3{price})"),
        )
        conn.commit()
