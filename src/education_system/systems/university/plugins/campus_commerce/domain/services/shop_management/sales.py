"""University Shop sales: the one place a shop sale or refund reaches Finance.

Both the CLI (``shopping.checkout_process``) and the GUI
(``shop_management_gui.checkout_manager`` / ``refund_manager``) record the
local sale through :func:`record_shop_sale` and refunds through
:func:`refund_shop_transaction`, so a sale rung up on either interface lands
in the ledger and, for student-account payments, on the student's finance
account.

Finance is reached only through the public ``finance_integration``
functions; this module never writes canonical finance tables itself.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, Iterable, Optional

from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
    process_student_finance_account_payment,
    record_payment_to_finance,
    record_refund_to_finance,
    top_up_student_finance_account,
)

logger = logging.getLogger(__name__)

FINANCE_SOURCE = "Shop"
STUDENT_ACCOUNT_METHOD = "Student Account"
# Money has not moved yet: the finance GUI is opened for manual processing.
PENDING_METHODS = frozenset({"Finance System"})


def record_shop_sale(
    user_id: int,
    cart_items: Iterable[Dict[str, Any]],
    total: float,
    payment_method: str,
    *,
    student_id: Optional[str] = None,
    finance_user_id: Optional[str] = None,
    processed_by: Optional[str] = None,
    notes: Optional[str] = None,
    clear_db_cart: bool = False,
) -> Dict[str, Any]:
    """Write the sale locally and post it to Finance.

    ``cart_items`` are mappings with ``product_id``, ``quantity`` and
    ``price``. ``student_id`` is stored on the transaction; ``finance_user_id``
    is the identifier the finance hub keys the account on (student_id, else
    username) and defaults to ``student_id``.

    Order of operations:

    1. ``Student Account`` → debit the finance account first through
       ``process_student_finance_account_payment`` (which records the
       payment row and GL journal itself). Failure aborts the sale.
    2. Insert the transaction, its items, decrement inventory and (CLI only)
       clear the DB cart.
    3. Any other completed method → ``record_payment_to_finance``.
       A posting failure is logged; the local sale is never rolled back.

    Returns ``{'transaction_id', 'finance_payment_id', 'account_result',
    'status', 'error'}``; ``transaction_id`` is None on failure.
    """
    result: Dict[str, Any] = {
        'transaction_id': None, 'finance_payment_id': None,
        'account_result': None, 'status': None, 'error': None,
    }
    items = list(cart_items)
    if not items:
        result['error'] = "Cart is empty."
        return result

    finance_user_id = finance_user_id or student_id
    transaction_id = f"T{int(time.time())}"
    status = "Pending Payment" if payment_method in PENDING_METHODS else "Completed"
    result['status'] = status

    if payment_method == STUDENT_ACCOUNT_METHOD:
        if not finance_user_id:
            result['error'] = "Unable to identify a finance account for this user."
            return result
        account_result = process_student_finance_account_payment(
            student_id=str(finance_user_id),
            amount=float(total),
            description=f"Shop purchase #{transaction_id}",
            transaction_source=FINANCE_SOURCE,
            transaction_ref=transaction_id,
            processed_by=processed_by or "System",
            check_balance=True,
            send_low_balance_alert=True,
        )
        result['account_result'] = account_result
        if not account_result.get('success'):
            result['error'] = account_result.get('message', 'Student account payment failed')
            return result

    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO transactions
                (source_transaction_id, customer_id, student_id, total_amount, created_at,
                 payment_method, status, notes, source_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'shop')
                ''',
                [transaction_id, user_id, student_id, float(total),
                 datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                 payment_method, status, notes],
            )
            cursor.executemany(
                '''
                INSERT INTO shop_transaction_items
                (transaction_id, product_id, quantity, price_per_item, subtotal)
                VALUES (?, ?, ?, ?, ?)
                ''',
                [(transaction_id, it['product_id'], it['quantity'], it['price'],
                  float(it['price']) * int(it['quantity'])) for it in items],
            )
            cursor.executemany(
                'UPDATE shop_inventory SET quantity = quantity - ? WHERE product_id = ?',
                [(it['quantity'], it['product_id']) for it in items],
            )
            if clear_db_cart:
                cursor.execute(
                    "DELETE FROM cart WHERE source_type = 'shop' AND user_id = ?", [user_id])
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.error("Shop sale write failed: %s", e)
        result['error'] = f"Database error during checkout: {e}"
        return result

    result['transaction_id'] = transaction_id

    if status == "Completed" and payment_method != STUDENT_ACCOUNT_METHOD:
        try:
            result['finance_payment_id'] = record_payment_to_finance(
                student_id=str(finance_user_id or "EXTERNAL"),
                amount=float(total),
                payment_method=payment_method,
                transaction_source=FINANCE_SOURCE,
                transaction_ref=transaction_id,
                notes=f'Shop purchase: {len(items)} item(s)',
                created_by=processed_by,
            )
        except Exception:
            logger.exception("Finance posting failed for shop transaction %s", transaction_id)

    # Cross-domain: loyalty ledger / unified student view. Walk-ins skipped.
    if student_id and student_id != "EXTERNAL":
        try:
            from education_system.systems.university.services.bus import commerce_bus
            commerce_bus.post_sale(
                student_id, source="shop", amount=float(total),
                description=f"Shop purchase ({len(items)} items)",
                reference_id=transaction_id, processed_by=processed_by,
            )
        except Exception:
            logger.debug("commerce_bus.post_sale failed", exc_info=True)

    return result


def refund_shop_transaction(
    transaction_id: str,
    amount: float,
    refund_method: str,
    *,
    student_id: Optional[str] = None,
    processed_by: Optional[str] = None,
    reason: str = "Customer Request",
) -> Dict[str, Any]:
    """Mark a shop transaction refunded and post the refund to Finance.

    ``'Student Account'`` re-credits the finance account through
    ``top_up_student_finance_account`` (failure aborts). The refund is
    always recorded through ``record_refund_to_finance`` (unified_refunds
    + ledger). Returns ``{'success', 'refund_id', 'refund_ref', 'message'}``.
    """
    result: Dict[str, Any] = {'success': False, 'refund_id': None,
                              'refund_ref': None, 'message': ''}
    try:
        conn = get_connection()
        try:
            row = conn.execute(
                '''
                SELECT t.status, t.student_id AS trans_student_id,
                       u.student_id AS user_student_id, u.username
                FROM transactions t
                LEFT JOIN users u ON t.customer_id = u.id
                WHERE t.source_type = 'shop' AND t.source_transaction_id = ?
                ''', (transaction_id,)).fetchone()
        finally:
            conn.close()
        if not row:
            result['message'] = "Transaction not found"
            return result
        if (row['status'] or '').lower() == 'refunded':
            result['message'] = "This transaction has already been refunded"
            return result
        student_id = student_id or row['trans_student_id'] or row['user_student_id'] or row['username']

        refund_ref = f"SHOP-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        if refund_method == STUDENT_ACCOUNT_METHOD:
            if not student_id:
                result['message'] = "No finance account linked to this transaction"
                return result
            topup = top_up_student_finance_account(
                create_if_missing=True,
                student_id=str(student_id), amount=float(amount),
                payment_method='Refund', processed_by=processed_by or 'System',
                description=f'Shop Purchase Refund - {refund_ref}')
            if not topup.get('success'):
                result['message'] = topup.get('message', 'Failed to credit student account')
                return result
            result['account_created'] = bool(topup.get('account_created'))

        conn = get_connection()
        try:
            conn.execute(
                "UPDATE transactions SET status = 'refunded' "
                "WHERE source_type = 'shop' AND source_transaction_id = ?",
                (transaction_id,))
            conn.commit()
        finally:
            conn.close()

        result['refund_ref'] = refund_ref
        result['success'] = True
        try:
            result['refund_id'] = record_refund_to_finance(
                student_id=str(student_id or "EXTERNAL"),
                refund_amount=float(amount),
                original_payment_id=None,
                refund_reason=reason,
                refund_type='full',
                transaction_source=FINANCE_SOURCE,
                transaction_ref=str(transaction_id),
                refund_method=refund_method,
                requested_by=processed_by or 'System',
                notes=f"Refund reference {refund_ref}",
            )
        except Exception:
            logger.exception("Finance refund posting failed for shop %s", transaction_id)
        result['message'] = f"Refund of GBP {float(amount):.2f} processed" + (
            " (a finance account was opened for the student)"
            if result.get('account_created') else "")
        return result
    except sqlite3.Error as e:
        result['message'] = f"Database error: {e}"
        return result
