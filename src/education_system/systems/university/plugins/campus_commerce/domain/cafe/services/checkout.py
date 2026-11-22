"""Cafe checkout: the one place a cafe sale or refund reaches Finance.

The CLI (``interfaces/cli/services/cafe/commands/point_of_sale``) and the
GUI (``interfaces/gui/cafe_pos`` / ``cafe_refunds``) both complete sales
through :func:`create_order` and refunds through :func:`refund_order`.

The persistence layer's ``order_repository.create_order`` only writes the
local rows; this module wraps it with the finance-account debit and the
Finance posting. Finance is reached only through the public
``finance_integration`` functions.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from ..persistence.order_repository import *  # noqa: F401,F403
from ..persistence import order_repository as _orders
from ..persistence.schema import get_db_connection
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
    process_student_finance_account_payment,
    record_payment_to_finance,
    record_refund_to_finance,
    top_up_student_finance_account,
)

logger = logging.getLogger(__name__)

FINANCE_SOURCE = "Cafe"
ACCOUNT_METHODS = frozenset({"finance_account", "student_account"})
PAYMENT_METHOD_DISPLAY = {
    'finance_account': 'Finance Account',
    'student_account': 'Finance Account',
    'cash': 'Cash',
    'card': 'Card',
    'debit_card': 'Debit Card',
    'credit_card': 'Credit Card',
}


def create_order(student_id: Optional[str], customer_name: str, items: List[Dict],
                 payment_method: str, *, processed_by: Optional[str] = None,
                 finance_user_id: Optional[str] = None) -> Optional[int]:
    """Complete a cafe sale: debit / write / post.

    ``items`` are ``{'item_id', 'name', 'quantity', 'price', 'subtotal'}``.

    1. ``finance_account`` / ``student_account`` → debit the account first
       with ``process_student_finance_account_payment`` (which records the
       payment row itself). Failure aborts the sale (returns None).
    2. Write the order through the persistence layer (stored payment method
       is the display name, e.g. ``'Cash'``).
    3. Any other method → ``record_payment_to_finance``; a posting failure
       is logged, never rolled back.

    Returns the order id, or None if nothing was sold.
    """
    total = sum(float(item['subtotal']) for item in items)
    account_id = finance_user_id or student_id
    if payment_method in ACCOUNT_METHODS:
        if not account_id:
            logger.warning("Cafe finance-account sale without an account identifier")
            return None
        charge = process_student_finance_account_payment(
            student_id=str(account_id),
            amount=total,
            description="Cafe Purchase",
            transaction_source=FINANCE_SOURCE,
            transaction_ref=f"CAFE-{uuid.uuid4().hex[:12].upper()}",
            processed_by=processed_by or 'System',
        )
        if not charge.get('success'):
            logger.warning("Cafe finance-account payment failed: %s", charge.get('message'))
            return None

    display = PAYMENT_METHOD_DISPLAY.get(payment_method, payment_method)
    order_id = _orders.create_order(student_id, customer_name, items, display)
    if not order_id:
        return None

    if payment_method not in ACCOUNT_METHODS:
        try:
            record_payment_to_finance(
                student_id=str(account_id or 'WALK-IN'),
                amount=total,
                payment_method=display,
                transaction_source=FINANCE_SOURCE,
                transaction_ref=f'ORDER-{order_id}',
                currency='GBP',
                status='completed',
                notes=f'Cafe order #{order_id} - {len(items)} item(s)',
                created_by=processed_by or 'System',
            )
        except Exception:
            logger.exception("Finance posting failed for cafe order %s", order_id)
    return order_id


def refund_order(order_id: int, amount: float, refund_method: str, *,
                 student_id: Optional[str] = None,
                 processed_by: Optional[str] = None,
                 reason: str = "Customer Request") -> Dict[str, Any]:
    """Mark a cafe order refunded and post the refund to Finance.

    ``'Student Account'`` re-credits the finance account through
    ``top_up_student_finance_account`` (failure aborts). The refund is
    always recorded through ``record_refund_to_finance`` (unified_refunds
    + ledger). Returns ``{'success', 'refund_id', 'refund_ref', 'message'}``.
    """
    result: Dict[str, Any] = {'success': False, 'refund_id': None,
                              'refund_ref': None, 'message': ''}
    conn = get_db_connection()
    if not conn:
        result['message'] = "Database connection failed"
        return result
    try:
        row = conn.execute(
            "SELECT order_status, student_id FROM orders WHERE order_id = ? AND source_type = 'cafe'",
            (order_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        result['message'] = "Order not found"
        return result
    if (row[0] or '').lower() == 'refunded':
        result['message'] = "This order has already been refunded"
        return result
    student_id = student_id or row[1]

    if refund_method == 'Student Account':
        if not student_id:
            result['message'] = "Student ID required for a student account refund"
            return result
        topup = top_up_student_finance_account(
            create_if_missing=True,
            student_id=str(student_id), amount=float(amount),
            payment_method='Refund', processed_by=processed_by or 'System',
            description=f'Cafe Refund - Order: {order_id}')
        if not topup.get('success'):
            result['message'] = topup.get('message', 'Failed to credit student account')
            return result
        result['account_created'] = bool(topup.get('account_created'))

    try:
        conn = get_db_connection()
        try:
            conn.execute(
                "UPDATE orders SET order_status = 'refunded' WHERE order_id = ? AND source_type = 'cafe'",
                (order_id,))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        result['message'] = f"Database error: {e}"
        return result

    refund_ref = f"CAFE-REFUND-{uuid.uuid4().hex[:12].upper()}"
    result['refund_ref'] = refund_ref
    result['success'] = True
    try:
        result['refund_id'] = record_refund_to_finance(
            student_id=str(student_id or "WALK-IN"),
            refund_amount=float(amount),
            original_payment_id=None,
            refund_reason=reason,
            refund_type='full',
            transaction_source=FINANCE_SOURCE,
            transaction_ref=str(order_id),
            refund_method=refund_method,
            requested_by=processed_by or 'System',
            notes=f"Refund reference {refund_ref}",
        )
    except Exception:
        logger.exception("Finance refund posting failed for cafe order %s", order_id)
    result['message'] = f"Refund of GBP {float(amount):.2f} processed" + (
            " (a finance account was opened for the student)"
            if result.get('account_created') else "")
    return result
