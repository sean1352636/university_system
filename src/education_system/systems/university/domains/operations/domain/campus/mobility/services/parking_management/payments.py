"""Parking fine payments and refunds — the one place parking money reaches Finance.

Both the parking GUI (Payments tab) and the CLI ``pay_violation_fine`` menu call
these functions, so the local write and the Finance posting happen once, here.
A student-account payment debits ``student_finance_accounts``; every payment
writes one ``payments`` row (``source_type='parking'``) which is then
auto-posted to the GL. Refunds mirror that through ``unified_refunds``.
Posting failures are logged and never roll back the operational write.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.services.bus import finance_bus

logger = logging.getLogger(__name__)

PAYMENT_METHODS = ("cash", "card", "student_account")


def resolve_student_id_for_plate(license_plate: str) -> Optional[str]:
    """The finance identity (student_id or username) of the vehicle's owner."""
    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(u.student_id, u.username)
                FROM vehicles v
                JOIN users u ON v.owner_id = u.id
                WHERE v.license_plate = ?
                """,
                (license_plate,),
            ).fetchone()
        return row[0] if row else None
    except Exception as exc:
        logger.error("Error resolving student for plate %s: %s", license_plate, exc)
        return None


def record_fine_payment(
    violation_id: str,
    amount: float,
    payment_method: str,
    student_id: Optional[str] = None,
    processed_by: Optional[str] = None,
    notes: str = "Parking fine payment",
) -> dict[str, Any]:
    """Take payment for a parking violation and post it to Finance.

    Returns ``{'payment_id', 'payment_ref', 'new_balance'}``. Raises on a
    database failure so callers can report it; a student-account payment with
    no ``student_id`` is rejected with ``ValueError``.
    """
    method = str(payment_method or "cash").strip().lower()
    student_account = finance_bus.is_student_account_method(method)
    if student_account and not student_id:
        raise ValueError("A student account payment needs a student id")

    payment_ref = f"PARKING-PAY-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    processed_by = processed_by or "system"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_balance = None

    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO payments
            (source_type, reference_id, reference_type, amount, payment_method, payment_reference,
             student_id, processed_by, notes, status, payment_date, created_by, created_at)
            VALUES ('parking', ?, 'violation', ?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?)
            """,
            (violation_id, amount, method, payment_ref, student_id, processed_by, notes,
             now, processed_by, now),
        )
        payment_id = cursor.lastrowid

        cursor.execute(
            "UPDATE parking_violations SET payment_status = 'Paid' WHERE violation_id = ?",
            (violation_id,),
        )

        if student_account:
            cursor.execute(
                "UPDATE student_finance_accounts SET balance = balance - ? WHERE student_id = ?",
                (amount, student_id),
            )
            cursor.execute(
                "SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?",
                (student_id,),
            )
            account = cursor.fetchone()
            if account:
                account_id, new_balance = account[0], account[1]
                cursor.execute(
                    """
                    INSERT INTO transactions
                    (source_type, account_id, student_id, transaction_type, amount, balance_after,
                     description, reference_id, processed_by, created_at)
                    VALUES ('student_finance', ?, ?, 'debit', ?, ?, ?, ?, ?, ?)
                    """,
                    (account_id, student_id, amount, new_balance,
                     f"Parking fine payment - {payment_ref}", payment_ref, processed_by, now),
                )

    # Auto-post the parking payment to the GL (never raises).
    finance_bus.notify_ledger("payment", payment_id, posted_by=processed_by)
    logger.info("Parking fine %s paid: £%.2f via %s (%s)", violation_id, amount, method, payment_ref)
    return {"payment_id": payment_id, "payment_ref": payment_ref, "new_balance": new_balance}


def record_fine_refund(
    payment_id: int,
    violation_id: str,
    amount: float,
    refund_method: str,
    student_id: Optional[str] = None,
    processed_by: Optional[str] = None,
) -> dict[str, Any]:
    """Refund a parking fine payment and post the refund to Finance.

    Returns ``{'refund_id', 'refund_ref', 'new_balance'}``.
    """
    method = str(refund_method or "cash").strip().lower()
    student_account = finance_bus.is_student_account_method(method)
    if student_account and not student_id:
        raise ValueError("A student account refund needs a student id")

    refund_ref = f"PARKING-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    processed_by = processed_by or "system"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_balance = None

    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO unified_refunds
            (source_type, reference_id, reference_type, amount, refund_method, refund_reference,
             student_id, processed_by, reason, refund_date, status)
            VALUES ('parking', ?, 'payment', ?, ?, ?, ?, ?, ?, ?, 'processed')
            """,
            (str(payment_id), amount, method, refund_ref, student_id, processed_by,
             f"Parking fine refund (violation: {violation_id})", now),
        )
        refund_id = cursor.lastrowid

        cursor.execute(
            "UPDATE parking_violations SET payment_status = 'Refunded' WHERE violation_id = ?",
            (violation_id,),
        )
        cursor.execute(
            """
            UPDATE payments
            SET notes = COALESCE(notes, '') || ' [REFUNDED: ' || ? || ']'
            WHERE payment_id = ? AND source_type = 'parking'
            """,
            (refund_ref, payment_id),
        )

        if student_account:
            cursor.execute(
                "UPDATE student_finance_accounts SET balance = balance + ? WHERE student_id = ?",
                (amount, student_id),
            )
            cursor.execute(
                "SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?",
                (student_id,),
            )
            account = cursor.fetchone()
            if account:
                account_id, new_balance = account[0], account[1]
                cursor.execute(
                    """
                    INSERT INTO transactions
                    (source_type, account_id, student_id, transaction_type, amount, balance_after,
                     description, reference_id, processed_by, created_at)
                    VALUES ('student_finance', ?, ?, 'credit', ?, ?, ?, ?, ?, ?)
                    """,
                    (account_id, student_id, amount, new_balance,
                     f"Parking fine refund - {refund_ref}", refund_ref, processed_by, now),
                )

    finance_bus.notify_ledger("refund", refund_id, posted_by=processed_by)
    logger.info("Parking fine %s refunded: £%.2f via %s (%s)", violation_id, amount, method, refund_ref)
    return {"refund_id": refund_id, "refund_ref": refund_ref, "new_balance": new_balance}


__all__ = [
    "PAYMENT_METHODS",
    "resolve_student_id_for_plate",
    "record_fine_payment",
    "record_fine_refund",
]
