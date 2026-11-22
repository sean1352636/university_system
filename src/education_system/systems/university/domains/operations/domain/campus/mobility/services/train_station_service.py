"""Train station ticketing — purchases and refunds, posted to Finance once.

Both the Tk train station app and ``shell/cli/services/train_station_cli.py``
call these functions, so the local write and the Finance posting live here
and neither interface posts directly.

* Cash / Card purchase  → one ``payments`` row via the finance bus
  (``TrainStation`` / ticket number), posted after the ticket is written.
* Student Account       → drawn down from the student's finance account
  first (Finance writes its own ``payments`` row); the ticket is only
  written when the draw-down succeeds.
* Refund                → one ``unified_refunds`` row (``source_type='train'``,
  ``reference_type='ticket'``) auto-posted to the GL; a student-account refund
  also credits ``student_finance_accounts``.

Posting failures are logged and never roll back the operational write.
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

SOURCE = "TrainStation"


def _code(prefix: str) -> str:
    return prefix + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def get_service(service_id: int) -> Optional[dict[str, Any]]:
    """The train service row as a dict, or ``None``."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM train_station_services WHERE id = ?", (service_id,)
        ).fetchone()
    return dict(row) if row else None


def purchase_ticket(
    service_id: int,
    passenger_name: str,
    payment_method: str,
    price_paid: float,
    student_id: Optional[str] = None,
    processed_by: Optional[str] = None,
) -> tuple[Optional[int], Optional[str], Optional[str]]:
    """Sell a ticket, take the money and post it to Finance.

    Returns ``(ticket_id, ticket_number, receipt_number)`` or
    ``(None, None, None)`` when the payment was declined or the write failed.
    """
    try:
        service = get_service(service_id) or {}
        route = f"{service.get('departure_station', '?')} to {service.get('arrival_station', '?')}"
        student_account = finance_bus.is_student_account_method(payment_method)
        processed_by = processed_by or "System"

        if student_account:
            if not student_id:
                logger.error("Student-account train purchase with no student id")
                return None, None, None
            result = finance_bus.pay_from_student_account(
                student_id=student_id,
                amount=price_paid,
                description=f"Train ticket: {route}",
                transaction_source=SOURCE,
                transaction_ref=f"TRAIN-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                processed_by=processed_by,
            )
            if not result.get("success"):
                logger.error("Student-account train purchase declined: %s", result.get("message"))
                return None, None, None

        ticket_number = _code("TKT")
        receipt_number = _code("RCP")
        purchase_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with transaction() as conn:
            cur = conn.execute(
                """
                INSERT INTO train_station_tickets
                (ticket_number, service_id, passenger_name, payment_method, price_paid, purchase_date)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ticket_number, service_id, passenger_name, payment_method, price_paid, purchase_date),
            )
            ticket_id = cur.lastrowid
            conn.execute(
                """
                INSERT INTO train_station_receipts
                (receipt_number, ticket_id, total_amount, payment_method, transaction_date)
                VALUES (?, ?, ?, ?, ?)
                """,
                (receipt_number, ticket_id, price_paid, payment_method, purchase_date),
            )
            conn.execute(
                "UPDATE train_station_services SET available_seats = available_seats - 1 WHERE id = ?",
                (service_id,),
            )

        if not student_account:
            payment_id = finance_bus.record_payment(
                student_id=student_id or "EXTERNAL",
                amount=price_paid,
                payment_method=payment_method,
                transaction_source=SOURCE,
                transaction_ref=ticket_number,
                notes=f"Train ticket {service.get('service_number', '')}: {route} ({passenger_name})",
                created_by=processed_by,
            )
            if not payment_id:
                logger.error("Finance posting failed for train ticket %s (ticket kept)", ticket_number)

        return ticket_id, ticket_number, receipt_number
    except Exception as exc:
        logger.error("Error purchasing train ticket: %s", exc)
        return None, None, None


def has_refund(ticket_number: str) -> bool:
    """Whether a refund has already been recorded for the ticket."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT refund_id FROM unified_refunds WHERE source_type = 'train' "
            "AND reference_type = 'ticket' AND reference_id = ?",
            (ticket_number,),
        ).fetchone()
    return row is not None


def process_refund(
    ticket_number: str,
    amount: float,
    refund_method: str,
    student_id: Optional[str] = None,
    processed_by: Optional[str] = None,
) -> dict[str, Any]:
    """Refund a ticket and post the refund to Finance.

    Returns ``{'refund_id', 'refund_ref', 'old_balance', 'new_balance'}``.
    Raises ``ValueError`` for a student-account refund with no student id.
    """
    student_account = finance_bus.is_student_account_method(refund_method)
    if student_account and not student_id:
        raise ValueError("A student account refund needs a student id")
    processed_by = processed_by or "System"
    refund_ref = f"TRAIN-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    old_balance = new_balance = None

    if student_account:
        finance_bus.ensure_student_account(student_id)

    with transaction() as conn:
        cur = conn.cursor()
        try:  # older databases predate the status column
            cur.execute("ALTER TABLE train_station_tickets ADD COLUMN status TEXT DEFAULT 'active'")
        except Exception:
            pass
        cur.execute(
            "UPDATE train_station_tickets SET status = 'refunded' WHERE ticket_number = ?",
            (ticket_number,),
        )
        cur.execute(
            """
            INSERT INTO unified_refunds
            (source_type, reference_id, reference_type, student_id, amount, refund_method,
             refund_reference, refund_date, processed_by, status)
            VALUES ('train', ?, 'ticket', ?, ?, ?, ?, ?, ?, 'processed')
            """,
            (ticket_number, student_id, amount, refund_method, refund_ref, now, processed_by),
        )
        refund_id = cur.lastrowid

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
                 f"Train ticket refund - {refund_ref}", refund_ref, processed_by, now),
            )

    finance_bus.notify_ledger("refund", refund_id, posted_by=processed_by)
    logger.info("Train ticket %s refunded: £%.2f via %s (%s)", ticket_number, amount, refund_method, refund_ref)
    return {"refund_id": refund_id, "refund_ref": refund_ref,
            "old_balance": old_balance, "new_balance": new_balance}


__all__ = ["SOURCE", "get_service", "purchase_ticket", "has_refund", "process_refund"]
