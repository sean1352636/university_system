"""Taxi bookings — fares and refunds, posted to Finance once.

Both the Tk taxi booking app and ``shell/cli/services/taxi_booking_cli.py``
call these functions, so the local write and the Finance posting live here
and neither interface posts directly. Same contract as
:mod:`train_station_service`: cash/card is posted after the ticket is
written, a student-account fare is drawn down first, and refunds go through
``unified_refunds`` (``source_type='taxi'``). Posting failures are logged and
never roll back the operational write.
"""

from __future__ import annotations

import logging
import random
import string
from datetime import datetime
from typing import Any, Optional

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.services.bus import finance_bus

logger = logging.getLogger(__name__)

SOURCE = "TaxiBooking"


def generate_ticket_number() -> str:
    return "TX" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def create_ticket(
    service_id: int,
    customer_name: str,
    pickup: str,
    dropoff: str,
    distance: float,
    total_fare: float,
    payment_method: str,
    student_id: Optional[str] = None,
    processed_by: Optional[str] = None,
) -> tuple[Optional[int], Optional[str]]:
    """Book a taxi, take the fare and post it to Finance.

    Returns ``(ticket_id, ticket_number)`` or ``(None, None)`` when the
    payment was declined or the write failed.
    """
    try:
        student_account = finance_bus.is_student_account_method(payment_method)
        processed_by = processed_by or "System"

        if student_account:
            if not student_id:
                logger.error("Student-account taxi booking with no student id")
                return None, None
            result = finance_bus.pay_from_student_account(
                student_id=student_id,
                amount=total_fare,
                description=f"Taxi booking: {pickup} to {dropoff}",
                transaction_source=SOURCE,
                transaction_ref=f"TAXI-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                processed_by=processed_by,
            )
            if not result.get("success"):
                logger.error("Student-account taxi booking declined: %s", result.get("message"))
                return None, None

        ticket_number = generate_ticket_number()
        now = datetime.now()
        with transaction() as conn:
            cur = conn.execute(
                """
                INSERT INTO taxi_booking_tickets
                (ticket_number, service_id, customer_name, pickup_location, dropoff_location,
                 distance_km, total_fare, payment_method, booking_date, booking_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ticket_number, service_id, customer_name, pickup, dropoff, distance,
                 total_fare, payment_method, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")),
            )
            ticket_id = cur.lastrowid

        if not student_account:
            payment_id = finance_bus.record_payment(
                student_id=student_id or "EXTERNAL",
                amount=total_fare,
                payment_method=payment_method,
                transaction_source=SOURCE,
                transaction_ref=ticket_number,
                notes=f"Taxi booking: {pickup} to {dropoff} ({customer_name})",
                created_by=processed_by,
            )
            if not payment_id:
                logger.error("Finance posting failed for taxi ticket %s (ticket kept)", ticket_number)

        return ticket_id, ticket_number
    except Exception as exc:
        logger.error("Error creating taxi ticket: %s", exc)
        return None, None


def process_refund(
    ticket_id: int,
    ticket_number: str,
    amount: float,
    refund_method: str,
    student_id: Optional[str] = None,
    processed_by: Optional[str] = None,
) -> dict[str, Any]:
    """Refund a taxi fare and post the refund to Finance.

    Returns ``{'refund_id', 'refund_ref', 'old_balance', 'new_balance'}``.
    Raises ``ValueError`` for a student-account refund with no student id.
    """
    student_account = finance_bus.is_student_account_method(refund_method)
    if student_account and not student_id:
        raise ValueError("A student account refund needs a student id")
    processed_by = processed_by or "System"
    refund_ref = f"TAXI-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    old_balance = new_balance = None

    if student_account:
        finance_bus.ensure_student_account(student_id)

    with transaction() as conn:
        cur = conn.cursor()
        if student_account:
            cur.execute(
                "SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?",
                (student_id,),
            )
            before = cur.fetchone()
            old_balance = float(before[1]) if before else 0.0
            cur.execute(
                "UPDATE student_finance_accounts SET balance = balance + ? WHERE student_id = ?",
                (amount, student_id),
            )
            cur.execute(
                "SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?",
                (student_id,),
            )
            after = cur.fetchone()
            account_id, new_balance = (after[0], float(after[1])) if after else (None, old_balance + amount)
            cur.execute(
                """
                INSERT INTO transactions
                (source_type, account_id, student_id, transaction_type, amount, balance_after,
                 description, reference_id, processed_by, created_at)
                VALUES ('student_finance', ?, ?, 'credit', ?, ?, ?, ?, ?, ?)
                """,
                (account_id, student_id, amount, new_balance,
                 f"Taxi booking refund - {refund_ref}", refund_ref, processed_by, now),
            )

        cur.execute(
            "UPDATE taxi_booking_tickets SET payment_status = 'Refunded' WHERE id = ?",
            (ticket_id,),
        )
        cur.execute(
            """
            INSERT INTO unified_refunds
            (source_type, reference_id, reference_type, refund_reference, amount,
             refund_method, refund_date, processed_by, student_id, status)
            VALUES ('taxi', ?, 'ticket', ?, ?, ?, ?, ?, ?, 'processed')
            """,
            (ticket_number, refund_ref, amount, refund_method, now, processed_by, student_id),
        )
        refund_id = cur.lastrowid

    finance_bus.notify_ledger("refund", refund_id, posted_by=processed_by)
    logger.info("Taxi ticket %s refunded: £%.2f via %s (%s)", ticket_number, amount, refund_method, refund_ref)
    return {"refund_id": refund_id, "refund_ref": refund_ref,
            "old_balance": old_balance, "new_balance": new_balance}


__all__ = ["SOURCE", "generate_ticket_number", "create_ticket", "process_refund"]
