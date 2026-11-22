"""Restaurant order settlement: the one place an order payment or refund
reaches Finance.

The CLI (``order_processing``) and the GUI (``restaurant_management_gui``
orders/payments, orders/place_order, orders/refunds) all settle through
these functions, so a payment taken on either interface lands in the ledger
and, for finance-account payments, on the customer's finance account.

Finance is reached only through the public ``finance_integration``
functions; this module never writes canonical finance tables itself.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
    process_student_finance_account_payment,
    record_payment_to_finance,
    record_refund_to_finance,
    top_up_student_finance_account,
)

logger = logging.getLogger(__name__)

FINANCE_SOURCE = "Restaurant"
FINANCE_ACCOUNT_METHOD = "Finance Account"


def _resolve_bus_student(order_id) -> Optional[str]:
    """Student linked to the order's restaurant customer (loyalty bus only)."""
    try:
        conn = get_connection()
        try:
            crow = conn.execute(
                "SELECT rc.customer_id, rc.email FROM orders o "
                "LEFT JOIN restaurant_customers rc ON rc.customer_id = o.customer_id "
                "WHERE o.order_id = ?", (order_id,)).fetchone()
        finally:
            conn.close()
        from education_system.systems.university.services.bus import commerce_bus
        return commerce_bus.resolve_student(
            customer_id=crow[0] if crow else None,
            email=crow[1] if crow else None,
        )
    except Exception:
        logger.debug("commerce_bus student resolution failed", exc_info=True)
        return None


def post_order_payment(
    order_id,
    amount: float,
    payment_method: str,
    *,
    student_id: Optional[str] = None,
    processed_by: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Post an already-recorded order payment to Finance.

    ``Finance Account`` debits the customer's finance account through
    ``process_student_finance_account_payment`` (which records the payment
    row itself) and reports failure in ``success``. Every other method is
    recorded with ``record_payment_to_finance``; a posting failure is
    logged and reported, never raised.

    Returns ``{'success', 'payment_id', 'message', 'account_result'}``.
    """
    result: Dict[str, Any] = {'success': False, 'payment_id': None,
                              'message': '', 'account_result': None}
    if payment_method == FINANCE_ACCOUNT_METHOD:
        if not student_id:
            result['message'] = "No finance account linked to this order"
            return result
        account_result = process_student_finance_account_payment(
            student_id=str(student_id),
            amount=float(amount),
            description=f"Restaurant Order #{order_id}",
            transaction_source=FINANCE_SOURCE,
            transaction_ref=f"ORDER-{order_id}",
            processed_by=processed_by or 'system',
        )
        result['account_result'] = account_result
        result['success'] = bool(account_result.get('success'))
        result['message'] = account_result.get('message', '')
    else:
        try:
            payment_id = record_payment_to_finance(
                student_id=str(student_id or "EXTERNAL"),
                amount=float(amount),
                payment_method=payment_method,
                transaction_source=FINANCE_SOURCE,
                transaction_ref=str(order_id),
                notes=notes or f'Restaurant order payment via {payment_method}',
                created_by=processed_by,
            )
            result['payment_id'] = payment_id
            result['success'] = payment_id is not None
        except Exception as e:
            logger.exception("Finance posting failed for restaurant order %s", order_id)
            result['message'] = str(e)

    # Cross-domain: loyalty tier + unified transaction history (best-effort).
    bus_student = student_id if student_id and student_id != "EXTERNAL" else _resolve_bus_student(order_id)
    if bus_student:
        try:
            from education_system.systems.university.services.bus import commerce_bus
            commerce_bus.post_sale(
                bus_student, source="restaurant", amount=float(amount),
                description=f"Restaurant order {order_id}", reference_id=str(order_id),
            )
        except Exception:
            logger.debug("commerce_bus.post_sale failed", exc_info=True)
    return result


def settle_order_payment(
    order_id,
    amount: float,
    payment_method: str,
    *,
    status: str = 'Completed',
    student_id: Optional[str] = None,
    processed_by: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Mark the order paid locally, then post the payment to Finance.

    The local update commits first; a Finance failure is logged and
    reported in the result, never rolled back.
    """
    try:
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE orders SET payment_method = ?, order_status = ? WHERE order_id = ?",
                (payment_method, status, order_id))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        return {'success': False, 'payment_id': None, 'message': f"Database error: {e}",
                'account_result': None}
    return post_order_payment(order_id, amount, payment_method, student_id=student_id,
                              processed_by=processed_by, notes=notes)


def refund_order_payment(
    order_id,
    amount: float,
    refund_method: str,
    *,
    refund_type: str = 'Full',
    reason: str = 'Customer Request',
    notes: Optional[str] = None,
    student_id: Optional[str] = None,
    processed_by: Optional[str] = None,
    deduct_from_total: bool = False,
) -> Dict[str, Any]:
    """Refund an order and post the refund to Finance.

    ``Finance Account`` re-credits the customer's finance account through
    ``top_up_student_finance_account`` (failure aborts). The order status
    becomes ``Refunded`` (or ``Partially Refunded``) and, when
    ``deduct_from_total`` is set, ``total_amount`` is reduced. The refund is
    always recorded through ``record_refund_to_finance`` (unified_refunds +
    ledger). Returns ``{'success', 'refund_id', 'refund_ref', 'message'}``.
    """
    result: Dict[str, Any] = {'success': False, 'refund_id': None,
                              'refund_ref': None, 'message': ''}
    full = str(refund_type).lower() == 'full'
    refund_ref = f"REST-REFUND-{order_id}"

    if refund_method == FINANCE_ACCOUNT_METHOD:
        if not student_id:
            result['message'] = "Cannot refund to Finance Account: no account linked to this order"
            return result
        topup = top_up_student_finance_account(
            create_if_missing=True,
            student_id=str(student_id), amount=float(amount),
            payment_method='Refund', processed_by=processed_by or 'System',
            description=f'Restaurant Refund - Order: {order_id}')
        if not topup.get('success'):
            result['message'] = topup.get('message', 'Failed to credit finance account')
            return result
        result['account_created'] = bool(topup.get('account_created'))

    try:
        conn = get_connection()
        try:
            new_status = 'Refunded' if full else 'Partially Refunded'
            if deduct_from_total:
                conn.execute(
                    "UPDATE orders SET order_status = ?, total_amount = total_amount - ? "
                    "WHERE order_id = ?", (new_status, float(amount), order_id))
            else:
                conn.execute("UPDATE orders SET order_status = ? WHERE order_id = ?",
                             (new_status, order_id))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        result['message'] = f"Database error: {e}"
        return result

    result['success'] = True
    result['refund_ref'] = refund_ref
    try:
        result['refund_id'] = record_refund_to_finance(
            student_id=str(student_id or "EXTERNAL"),
            refund_amount=float(amount),
            original_payment_id=None,
            refund_reason=reason,
            refund_type='full' if full else 'partial',
            transaction_source=FINANCE_SOURCE,
            transaction_ref=str(order_id),
            refund_method=refund_method,
            requested_by=processed_by or 'System',
            notes=notes,
        )
    except Exception:
        logger.exception("Finance refund posting failed for restaurant order %s", order_id)
    result['message'] = f"Refund of GBP {float(amount):.2f} processed" + (
            " (a finance account was opened for the student)"
            if result.get('account_created') else "")
    return result
