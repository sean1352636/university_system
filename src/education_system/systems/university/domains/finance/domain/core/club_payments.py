"""Club payment management shared by the Finance GUI and CLI.

Lifted from the Finance GUI club-payments tab
(``interfaces/gui/finance/layout/_club_payments.py``) and the standalone
club payment window (``shell/gui/main/features/finance_gui.py``).  Club
payments are ordinary rows in the shared ``payments`` table tagged with
``source_type = 'club'``; ``reference_id`` holds the club id.
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

#: Enumerations that match what already lives in the ``payments`` table.
PAYMENT_TYPES: tuple[str, ...] = (
    "membership_fee",
    "event_fee",
    "sponsorship",
    "fundraising",
    "equipment",
    "travel",
    "other",
)
PAYMENT_METHODS: tuple[str, ...] = (
    "cash",
    "card",
    "bank_transfer",
    "cheque",
    "online",
    "other",
)


def club_payment_overview(days: int = 30) -> dict[str, Any]:
    """Count, total and distinct clubs paid in the last *days* days."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(amount), 0), COUNT(DISTINCT reference_id)
            FROM payments
            WHERE source_type = 'club'
              AND payment_date >= date('now', ?)
            """,
            (f"-{int(days)} days",),
        ).fetchone()
    finally:
        conn.close()
    return {
        "days": days,
        "total_payments": int(row[0] or 0) if row else 0,
        "total_amount": float(row[1] or 0) if row else 0.0,
        "clubs_with_payments": int(row[2] or 0) if row else 0,
    }


def list_clubs() -> list[tuple[int, str]]:
    """Active (non-archived) clubs as ``(club_id, club_name)``, by name."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT club_id, club_name FROM student_clubs "
            "WHERE COALESCE(status, 'active') != 'archived' ORDER BY club_name"
        ).fetchall()
    finally:
        conn.close()
    return [(int(r[0]), str(r[1])) for r in rows]


def record_club_payment(
    club_id: int,
    amount: float,
    payment_type: str = "membership_fee",
    payment_method: str = "cash",
    payment_date: str | None = None,
    notes: str | None = None,
    processed_by: str | None = None,
) -> int:
    """Insert a completed club payment and post it to the ledger.

    Returns the new ``payment_id``.  Validation mirrors the GUI form: a
    positive amount, an ISO date and known type/method enumerations.
    """
    if amount is None or float(amount) <= 0:
        raise ValueError("Amount must be positive.")
    if payment_type not in PAYMENT_TYPES:
        raise ValueError(f"Payment type must be one of: {', '.join(PAYMENT_TYPES)}.")
    if payment_method not in PAYMENT_METHODS:
        raise ValueError(f"Payment method must be one of: {', '.join(PAYMENT_METHODS)}.")
    date_str = payment_date or datetime.now().strftime("%Y-%m-%d")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("Payment date must be YYYY-MM-DD.") from exc

    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO payments (
                amount, currency, payment_method, payment_date, status, notes,
                source_type, payment_type, reference_type, reference_id, processed_by,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                float(amount), "GBP", payment_method, date_str, "completed",
                (notes or "").strip() or None,
                "club", payment_type, "club", str(int(club_id)), processed_by,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        payment_id = int(cur.lastrowid)
        conn.commit()
    finally:
        conn.close()

    # Auto-post to the general ledger; never let a ledger failure undo a payment.
    try:
        from education_system.systems.university.domains.finance.domain.ledger import notify_ledger

        notify_ledger("payment", payment_id, posted_by=processed_by or "club_payments")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("ledger hook failed: %s", exc)
    return payment_id


def club_payment_history(limit: int = 200) -> list[dict[str, Any]]:
    """Most recent club payments with the club name resolved."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                p.payment_id,
                p.payment_date,
                COALESCE(c.club_name, 'Club #' || p.reference_id) AS club,
                p.amount,
                p.currency,
                p.payment_type,
                p.payment_method,
                p.status
            FROM payments p
            LEFT JOIN student_clubs c ON CAST(p.reference_id AS INTEGER) = c.club_id
            WHERE p.source_type = 'club'
            ORDER BY p.payment_date DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    finally:
        conn.close()
    history = []
    for r in rows:
        raw_date = r[1]
        date_s = raw_date.split("T")[0] if isinstance(raw_date, str) else str(raw_date or "")
        history.append(
            {
                "payment_id": r[0],
                "payment_date": date_s,
                "club": r[2] or "",
                "amount": float(r[3] or 0),
                "currency": r[4] or "GBP",
                "payment_type": r[5] or "",
                "payment_method": r[6] or "",
                "status": r[7] or "",
            }
        )
    return history


__all__ = [
    "PAYMENT_METHODS",
    "PAYMENT_TYPES",
    "club_payment_history",
    "club_payment_overview",
    "list_clubs",
    "record_club_payment",
]
