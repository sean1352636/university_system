"""Student Union money-in and money-out, posted to Finance.

Every Student Union interface — the Tk payment screen and the event CLI —
records money through these functions, so the central ``payments`` /
``unified_refunds`` rows Finance reports on and the GL posting happen in one
place. Posting is fire-and-forget: a ledger failure is logged and never undoes
the local write.
"""

from __future__ import annotations

import logging
from typing import Optional

from education_system.systems.university.infrastructure.database.db import transaction

logger = logging.getLogger(__name__)

SOURCE_TYPE = 'club'


def _post(source_type: str, row_id: Optional[int], posted_by: Optional[str]) -> None:
    """Auto-post an operational row to the GL. Never raises."""
    if row_id is None:
        return
    try:
        from education_system.systems.university.domains.finance.domain.ledger import notify_ledger
        notify_ledger(source_type, row_id, posted_by=posted_by or 'student_union')
    except Exception:
        logger.exception("ledger hook failed for student_union %s %s", source_type, row_id)


def record_club_payment(
    club_id: int,
    amount: float,
    payment_type: str,
    payment_method: str,
    student_id: Optional[str] = None,
    description: Optional[str] = None,
    notes: Optional[str] = None,
    processed_by: Optional[str] = None,
    reference_type: str = 'club',
    reference_id: Optional[str] = None,
) -> Optional[int]:
    """Record money received by a club (membership, event fee, merchandise…).

    Writes the ``payments`` row with ``source_type='club'`` (status
    'completed' — cash has moved) and posts it to the GL. ``reference_type`` /
    ``reference_id`` default to the club; event ticket sales pass the event.
    Returns the payment id, or None if the write failed.
    """
    if amount is None or float(amount) <= 0:
        raise ValueError("amount must be greater than 0")
    processed_by = processed_by or 'Unknown'
    try:
        with transaction() as conn:
            cur = conn.execute('''
                INSERT INTO payments
                (source_type, reference_id, reference_type, amount, payment_type,
                 payment_method, payment_date, student_id, description, notes,
                 processed_by, status)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?, ?, ?, ?, 'completed')
            ''', (
                SOURCE_TYPE,
                str(reference_id if reference_id is not None else club_id),
                reference_type,
                float(amount),
                payment_type,
                payment_method,
                student_id or None,
                description or None,
                notes or None,
                processed_by,
            ))
            payment_id = cur.lastrowid
    except Exception:
        logger.exception("failed to record club payment for club %s", club_id)
        return None

    _post('payment', payment_id, processed_by)
    return payment_id


def record_event_ticket_sale(
    event_id: int,
    ticket_type: str,
    price: float,
    quantity: int,
    student_id: Optional[str] = None,
    payment_method: str = 'cash',
    processed_by: Optional[str] = None,
    event_name: Optional[str] = None,
) -> Optional[int]:
    """Post the cash from an event ticket sale as an ``event_fee`` payment.

    The ticket and ``event_finances`` rows stay with the caller (they are the
    event's own stock and P&L); this is the Finance record of the money.
    """
    revenue = float(price) * int(quantity)
    label = f"{quantity}x {ticket_type} tickets"
    if event_name:
        label += f" - {event_name}"
    return record_club_payment(
        club_id=event_id,
        amount=revenue,
        payment_type='event_fee',
        payment_method=payment_method,
        student_id=student_id,
        description=label,
        processed_by=processed_by,
        reference_type='event',
        reference_id=str(event_id),
    )


def record_club_refund(
    student_id: Optional[str],
    amount: float,
    refund_method: str,
    refund_ref: str,
    original_payment_id=None,
    processed_by: Optional[str] = None,
) -> Optional[int]:
    """Record a refund of a club payment and post it to the GL.

    Marks the original ``payments`` row refunded (when given), writes one
    ``unified_refunds`` row (status 'processed' — cash has moved) that points
    back at it, and posts the refund. Idempotent at the GL layer on
    (source_type, source_id). Crediting a student finance account is the
    caller's concern; this records the refund itself.
    """
    processed_by = processed_by or 'student_union'
    try:
        with transaction() as conn:
            if original_payment_id is not None:
                conn.execute('''
                    UPDATE payments SET status = 'refunded'
                    WHERE payment_id = ? AND source_type = ?
                ''', (original_payment_id, SOURCE_TYPE))
            cur = conn.execute('''
                INSERT INTO unified_refunds
                (refund_reference, source_type, reference_type, reference_id,
                 student_id, amount, refund_method, refund_date,
                 processed_by, notes, status)
                VALUES (?, 'student_union', 'payment', ?, ?, ?, ?, date('now'),
                        ?, 'Student Union Payment Refund', 'processed')
            ''', (refund_ref,
                  str(original_payment_id) if original_payment_id is not None else None,
                  student_id, float(amount), refund_method, processed_by))
            refund_id = cur.lastrowid
    except Exception:
        logger.exception("failed to record student_union refund %s", refund_ref)
        return None

    logger.info("[Student Union] Refund recorded in unified_refunds: %s", refund_ref)
    _post('refund', refund_id, processed_by)
    return refund_id


__all__ = ['record_club_payment', 'record_event_ticket_sale', 'record_club_refund']
