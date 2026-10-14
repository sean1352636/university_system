"""Student finance account service.

Reads and writes the ``student_finance_accounts`` / ``transactions`` /
``student_fees`` / ``payments`` / ``unified_refunds`` tables for one student.
Lifted from the bank app GUI, the "My Finances" account window and the finance
GUI's account tab so the CLI equivalents share the same rules.

No database is touched at import time; every function opens its own
connection through the shared university database helpers.
"""

from __future__ import annotations

from contextlib import closing
import csv
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: Transaction types that add money to the account (shown as ``+``).
CREDIT_TYPES: tuple[str, ...] = ("top_up", "topup", "deposit", "credit", "refund", "transfer_in")
#: Transaction types that take money out (shown as ``-``).
DEBIT_TYPES: tuple[str, ...] = ("use", "withdrawal", "payment", "transfer_out")

#: Statistics buckets used by the account overview cards.
_DEPOSIT_STAT_TYPES = ("top_up", "deposit", "refund")
_SPEND_STAT_TYPES = ("use", "withdrawal", "payment")

TOPUP_METHODS: tuple[str, ...] = ("card", "bank_transfer", "cash", "online")
USE_PURPOSES: tuple[str, ...] = (
    "fee_payment", "library_fine", "meal_purchase", "printing", "club_fee", "other",
)
WITHDRAWAL_METHODS: tuple[str, ...] = ("bank_transfer", "cash", "cheque")
QUICK_TOPUP_AMOUNTS: tuple[int, ...] = (10, 20, 50, 100)
MAX_TOPUP = 10_000.0
LOW_BALANCE_WARNING = 20.0

_TXN_SELECT = """
    SELECT created_at, transaction_type, amount, balance_after, description
    FROM transactions
    WHERE source_type = 'student_finance' AND student_id = ?
"""


def _connect():
    """A read connection that is closed when the ``with`` block ends."""
    from education_system.systems.university.infrastructure.database.db import get_connection

    return closing(get_connection())


def _transaction():
    from education_system.systems.university.infrastructure.database.db import transaction

    return transaction()


# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #
def resolve_account_owner(current_user: Optional[Dict[str, Any]]) -> Optional[str]:
    """The finance account a logged-in user may act on: their own.

    Student logins carry ``student_id``; for every other login the username is
    the account key, exactly as the bank app and account GUIs resolve it.
    """
    if not current_user:
        return None
    owner = current_user.get("student_id") or current_user.get("username")
    return str(owner) if owner else None


def ensure_account(student_id: str) -> bool:
    """Create the student's finance account if it does not exist yet."""
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
        ensure_student_finance_account_exists,
    )

    return ensure_student_finance_account_exists(student_id)


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def signed_amount(txn_type: Optional[str], amount: float) -> float:
    """Amount with its direction: credits positive, everything else negative."""
    value = float(amount or 0)
    return value if (txn_type or "") in CREDIT_TYPES else -value


def get_account_balance(student_id: str) -> float:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(balance, 0) FROM student_finance_accounts WHERE student_id = ?",
            (student_id,),
        ).fetchone()
    return float(row[0]) if row else 0.0


def get_account_stats(student_id: str) -> Dict[str, Any]:
    """Transaction count plus money in / money out for the overview cards."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*),
                   COALESCE(SUM(CASE WHEN transaction_type IN (?, ?, ?) THEN amount ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN transaction_type IN (?, ?, ?) THEN amount ELSE 0 END), 0)
            FROM transactions
            WHERE source_type = 'student_finance' AND student_id = ?
            """,
            (*_DEPOSIT_STAT_TYPES, *_SPEND_STAT_TYPES, student_id),
        ).fetchone()
    return {
        "transaction_count": int(row[0] or 0) if row else 0,
        "total_deposited": float(row[1] or 0) if row else 0.0,
        "total_spent": float(row[2] or 0) if row else 0.0,
    }


def get_account_overview(student_id: str) -> Dict[str, Any]:
    """Balance and statistics in one call (what the account window refreshes)."""
    overview = {"student_id": student_id, "balance": get_account_balance(student_id)}
    overview.update(get_account_stats(student_id))
    return overview


def list_account_transactions(
    student_id: str, filter_type: str = "all", limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Newest-first account transactions.

    ``filter_type`` is ``all``, ``deposit`` (money in) or ``spend`` (money out),
    matching the radio filter on the account window.
    """
    sql = _TXN_SELECT
    params: list[Any] = [student_id]
    if filter_type == "deposit":
        sql += " AND transaction_type IN (?, ?, ?)"
        params.extend(_DEPOSIT_STAT_TYPES)
    elif filter_type == "spend":
        sql += " AND transaction_type IN (?, ?, ?)"
        params.extend(_SPEND_STAT_TYPES)
    sql += " ORDER BY created_at DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        {
            "timestamp": row[0] or "",
            "type": row[1] or "unknown",
            "amount": float(row[2] or 0),
            "balance_after": float(row[3] or 0),
            "description": row[4] or "",
        }
        for row in rows
    ]


def get_fee_summary(student_id: str) -> Dict[str, float]:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0),
                   COALESCE(SUM(CASE WHEN status = 'paid' THEN amount ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN status != 'paid' THEN amount ELSE 0 END), 0)
            FROM student_fees WHERE student_id = ?
            """,
            (student_id,),
        ).fetchone()
    return {
        "total_fees": float(row[0] or 0) if row else 0.0,
        "paid": float(row[1] or 0) if row else 0.0,
        "outstanding": float(row[2] or 0) if row else 0.0,
    }


def list_fees(student_id: str) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT sf.student_fee_id, ft.fee_name, sf.amount, sf.due_date, sf.status
            FROM student_fees sf
            JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
            WHERE sf.student_id = ?
            ORDER BY sf.due_date DESC
            """,
            (student_id,),
        ).fetchall()
    return [
        {
            "fee_id": row[0],
            "fee_name": row[1] or "",
            "amount": float(row[2] or 0),
            "due_date": row[3] or "",
            "status": row[4] or "",
        }
        for row in rows
    ]


def list_payments(student_id: str) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT payment_id, amount, payment_date, payment_method, transaction_id
            FROM payments WHERE student_id = ?
            ORDER BY payment_date DESC
            """,
            (student_id,),
        ).fetchall()
    return [
        {
            "payment_id": row[0],
            "amount": float(row[1] or 0),
            "payment_date": row[2] or "",
            "method": row[3] or "N/A",
            "reference": row[4] or "N/A",
        }
        for row in rows
    ]


def list_refunds(
    student_id: Optional[str] = None, search: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Refunds from the unified refunds ledger, optionally scoped to one student."""
    sql = """
        SELECT refund_id, refund_reference, COALESCE(department, source_type),
               amount, refund_method, refund_date, reference_id,
               COALESCE(processed_by, approved_by, requested_by), notes
        FROM unified_refunds
    """
    clauses: list[str] = []
    params: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        params.append(student_id)
    if search:
        like = f"%{search.lower()}%"
        clauses.append(
            "(LOWER(COALESCE(refund_reference, '')) LIKE ?"
            " OR LOWER(COALESCE(department, source_type, '')) LIKE ?"
            " OR LOWER(COALESCE(reference_id, '')) LIKE ?"
            " OR LOWER(COALESCE(processed_by, '')) LIKE ?"
            " OR LOWER(COALESCE(notes, '')) LIKE ?)"
        )
        params.extend([like] * 5)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY refund_date DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        {
            "refund_id": row[0],
            "reference": row[1] or "",
            "department": row[2] or "",
            "amount": float(row[3] or 0),
            "method": row[4] or "",
            "refund_date": row[5] or "",
            "reference_id": row[6] or "",
            "processed_by": row[7] or "",
            "notes": row[8] or "",
        }
        for row in rows
    ]


def export_account_transactions_csv(student_id: str, path: str) -> int:
    """Write every account transaction to ``path``; returns the row count."""
    transactions = list_account_transactions(student_id)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Date/Time", "Type", "Amount", "Balance After", "Description"])
        for txn in transactions:
            writer.writerow([
                txn["timestamp"], txn["type"], txn["amount"],
                txn["balance_after"], txn["description"],
            ])
    return len(transactions)


# --------------------------------------------------------------------------- #
# Writes
# --------------------------------------------------------------------------- #
def _debit_account(
    student_id: str, amount: float, txn_type: str, description: str, processed_by: str
) -> Dict[str, Any]:
    """Take ``amount`` off the balance and record one ledger row."""
    result: Dict[str, Any] = {"success": False, "message": "", "new_balance": None}
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        result["message"] = "Please enter a valid amount"
        return result
    if amount <= 0:
        result["message"] = "Amount must be positive"
        return result
    try:
        with _transaction() as conn:
            row = conn.execute(
                "SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?",
                (student_id,),
            ).fetchone()
            if row is None:
                result["message"] = f"Finance account not found for student {student_id}"
                return result
            account_id, balance = row[0], float(row[1] or 0)
            if amount > balance:
                result["message"] = (
                    f"Insufficient balance. Current: £{balance:.2f}, "
                    f"Required: £{amount:.2f}"
                )
                return result
            new_balance = balance - amount
            conn.execute(
                """
                UPDATE student_finance_accounts
                SET balance = ?, updated_at = datetime('now')
                WHERE student_id = ?
                """,
                (new_balance, student_id),
            )
            conn.execute(
                """
                INSERT INTO transactions
                (source_type, account_id, student_id, transaction_type, amount,
                 balance_before, balance_after, description, processed_by)
                VALUES ('student_finance', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (account_id, student_id, txn_type, amount, balance, new_balance,
                 description, processed_by),
            )
    except Exception as exc:  # the caller shows the message; never raise into a dialog
        logger.error("Student account %s failed for %s: %s", txn_type, student_id, exc)
        result["message"] = f"Transaction failed: {exc}"
        return result
    result.update(success=True, new_balance=new_balance,
                  message=f"£{amount:.2f} {txn_type} recorded")
    return result


def use_account_balance(
    student_id: str,
    amount: float,
    purpose: str = "fee_payment",
    description: str = "",
    processed_by: str = "Unknown",
) -> Dict[str, Any]:
    """Spend from the balance on a service or fee (ledger type ``use``)."""
    purpose = purpose or "other"
    description = description or purpose.replace("_", " ").title()
    return _debit_account(student_id, amount, "use", description, processed_by)


def withdraw_from_account(
    student_id: str,
    amount: float,
    method: str = "bank_transfer",
    reason: str = "",
    processed_by: str = "Unknown",
) -> Dict[str, Any]:
    """Withdraw cash from the balance (ledger type ``withdrawal``)."""
    method = method or "bank_transfer"
    description = reason or f"Withdrawal via {method}"
    return _debit_account(student_id, amount, "withdrawal", description, processed_by)
