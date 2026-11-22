"""Charity Shop sale and refund service.

Single Finance posting point for the charity shop. Both interfaces call
these functions; neither posts to Finance itself.

Posting rules
-------------
* ``payment_method == 'Finance Account'`` debits the student's finance
  account through ``process_student_finance_account_payment``. That debit
  *is* the Finance posting (it writes the payments row and fires the GL
  hook), so no revenue row is posted on top of it. If the debit is refused
  nothing is written locally.
* Any other payment method writes the local sale first, then posts the
  cash-in via ``record_revenue_to_finance``.
* Refunds post via ``record_refund_to_finance``; a refund to the student
  account additionally credits it via ``top_up_student_finance_account``.
* A Finance posting failure is logged and never rolls back the local sale.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.systems.university.infrastructure.database.db import transaction

logger = logging.getLogger(__name__)

FINANCE_SOURCE = "Charity Shop"
STOCK_TABLE = "charity_shop_stock"
SALES_TABLE = "charity_shop_sales"
WALK_IN = "WALK-IN"
FINANCE_ACCOUNT_METHOD = "Finance Account"
STUDENT_ACCOUNT_REFUND = "Student Account"


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _debit_student_account(student_id: Optional[str], amount: float, description: str,
                           transaction_ref: str, processed_by: str) -> Dict[str, Any]:
    if not student_id:
        return {'success': False, 'message': 'A student ID is required for Finance Account payment'}
    try:
        from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
            process_student_finance_account_payment,
        )
    except ImportError:
        return {'success': False, 'message': 'Finance integration not available'}
    result = process_student_finance_account_payment(
        student_id=student_id,
        amount=amount,
        description=description,
        transaction_source=FINANCE_SOURCE,
        transaction_ref=transaction_ref,
        processed_by=processed_by,
    )
    if not result.get('success'):
        logger.warning("Charity shop finance-account payment refused (%s): %s",
                       transaction_ref, result.get('message'))
    return result


def record_sale_revenue(amount: float, revenue_category: str, transaction_ref: str,
                        payment_method: str = 'Cash', student_id: Optional[str] = None,
                        notes: Optional[str] = None) -> Optional[int]:
    """Post a cash/card charity shop sale to Finance. Never raises."""
    try:
        from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
            record_revenue_to_finance,
        )
        payment_id = record_revenue_to_finance(
            student_id=student_id or WALK_IN,
            amount=amount,
            revenue_category=revenue_category,
            transaction_source=FINANCE_SOURCE,
            transaction_ref=transaction_ref,
            payment_method=payment_method,
            notes=notes,
        )
        if not payment_id:
            logger.warning("Finance posting returned no id for charity shop %s", transaction_ref)
        return payment_id
    except Exception:
        logger.exception("Finance posting failed for charity shop %s", transaction_ref)
        return None


def _complete_sale(lines: List[Dict[str, Any]], total: float, payment_method: str,
                   student_id: Optional[str], processed_by: str, transaction_ref: str,
                   description: str, notes: str) -> Dict[str, Any]:
    """Shared tail of ``sell_item`` / ``checkout_basket``."""
    if payment_method == FINANCE_ACCOUNT_METHOD:
        debit = _debit_student_account(student_id, total, description, transaction_ref, processed_by)
        if not debit.get('success'):
            return {'success': False, 'message': debit.get('message', 'Payment failed'),
                    'transaction_ref': transaction_ref, 'total': total}

    try:
        with transaction() as conn:
            for line in lines:
                row = conn.execute(
                    f"SELECT quantity, sold_quantity FROM {STOCK_TABLE} WHERE id = ?",  # nosec B608 - constant
                    (line['id'],),
                ).fetchone()
                if not row:
                    raise ValueError(f"Item {line['id']} not found")
                current_qty = row[0] or 0
                new_qty = max(0, current_qty - line['quantity'])
                is_sold = 1 if new_qty == 0 else 0
                sold_date = datetime.now().strftime('%Y-%m-%d') if is_sold else None
                conn.execute(
                    f"UPDATE {STOCK_TABLE} SET quantity = ?, sold = ?, sold_date = ?, sold_quantity = ? WHERE id = ?",  # nosec B608 - constant
                    (new_qty, is_sold, sold_date, (row[1] or 0) + line['quantity'], line['id']),
                )
                if _table_exists(conn, SALES_TABLE):
                    conn.execute(
                        f"INSERT INTO {SALES_TABLE} (item_id, quantity, unit_price, total_amount, payment_method, sale_date) "  # nosec B608 - constant
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (line['id'], line['quantity'], line['price'],
                         line['price'] * line['quantity'], payment_method, _now()),
                    )

            items_json = json.dumps([{
                'id': line['id'], 'name': line['name'],
                'quantity': line['quantity'], 'price': line['price'],
            } for line in lines])
            conn.execute(
                "INSERT INTO transactions "
                "(source_type, reference_number, customer_id, amount, payment_method, status, notes, processed_by, created_at) "
                "VALUES ('charity_shop', ?, ?, ?, ?, 'completed', ?, ?, ?)",
                (transaction_ref, student_id, total, payment_method, items_json, processed_by, _now()),
            )
    except Exception as e:
        logger.error("Charity shop sale %s failed to save: %s", transaction_ref, e)
        return {'success': False, 'message': f"Failed to save sale: {e}",
                'transaction_ref': transaction_ref, 'total': total}

    payment_id = None
    if payment_method != FINANCE_ACCOUNT_METHOD:
        payment_id = record_sale_revenue(
            amount=total, revenue_category="Charity Shop Sale", transaction_ref=transaction_ref,
            payment_method=payment_method, student_id=student_id, notes=notes,
        )
    return {'success': True, 'message': 'Sale complete', 'transaction_ref': transaction_ref,
            'total': total, 'finance_payment_id': payment_id}


def sell_item(item_id: int, quantity: int, payment_method: str = 'Cash',
              student_id: Optional[str] = None, processed_by: str = 'System',
              transaction_ref: Optional[str] = None) -> Dict[str, Any]:
    """Sell ``quantity`` of one stock item and post the sale to Finance.

    Returns ``{'success', 'message', 'transaction_ref', 'total', 'item_name',
    'unit_price'}``.
    """
    try:
        with transaction() as conn:
            row = conn.execute(
                f"SELECT name, quantity, price FROM {STOCK_TABLE} WHERE id = ?",  # nosec B608 - constant
                (item_id,),
            ).fetchone()
    except Exception as e:
        return {'success': False, 'message': f"Database error: {e}"}
    if not row:
        return {'success': False, 'message': 'Item not found'}
    name, available, price = row[0], row[1] or 0, float(row[2] or 0)
    if quantity < 1 or quantity > available:
        return {'success': False, 'message': f"Invalid quantity (available: {available})"}

    total = round(price * quantity, 2)
    transaction_ref = transaction_ref or f"CS-{item_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    result = _complete_sale(
        lines=[{'id': item_id, 'name': name, 'quantity': quantity, 'price': price}],
        total=total, payment_method=payment_method, student_id=student_id,
        processed_by=processed_by, transaction_ref=transaction_ref,
        description=f"Charity Shop: {quantity}x {name}", notes=f"{quantity}x {name}",
    )
    result.update({'item_name': name, 'unit_price': price})
    return result


def checkout_basket(items: List[Dict[str, Any]], payment_method: str = 'Cash',
                    student_id: Optional[str] = None, processed_by: str = 'System',
                    transaction_ref: Optional[str] = None) -> Dict[str, Any]:
    """Sell a basket (``[{'id', 'name', 'quantity', 'price'}, ...]``) as one transaction."""
    if not items:
        return {'success': False, 'message': 'Basket is empty'}
    lines = [{'id': i['id'], 'name': i['name'], 'quantity': int(i['quantity']), 'price': float(i['price'])}
             for i in items]
    total = round(sum(line['price'] * line['quantity'] for line in lines), 2)
    transaction_ref = transaction_ref or f"CS-BASKET-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    return _complete_sale(
        lines=lines, total=total, payment_method=payment_method, student_id=student_id,
        processed_by=processed_by, transaction_ref=transaction_ref,
        description=f"Charity Shop: {len(lines)} items",
        notes=f"Basket checkout: {len(lines)} items",
    )


def record_refund(amount: float, refund_method: str, refund_ref: str,
                  student_id: Optional[str] = None, processed_by: str = 'System',
                  reason: Optional[str] = None, notes: Optional[str] = None) -> Dict[str, Any]:
    """Post a charity shop refund to Finance; credit the student account if asked.

    Returns ``{'refund_id', 'credited', 'new_balance', 'message'}``. Never raises.
    """
    out: Dict[str, Any] = {'refund_id': None, 'credited': False, 'new_balance': None, 'message': ''}
    try:
        from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
            record_refund_to_finance,
            top_up_student_finance_account,
        )
    except ImportError:
        out['message'] = 'Finance integration not available'
        logger.warning("Charity shop refund %s not posted: finance integration unavailable", refund_ref)
        return out

    try:
        out['refund_id'] = record_refund_to_finance(
            student_id=student_id or WALK_IN,
            refund_amount=amount,
            original_payment_id=None,
            refund_reason=reason or 'Charity shop refund',
            refund_type='full',
            transaction_source=FINANCE_SOURCE,
            transaction_ref=refund_ref,
            refund_method=refund_method,
            requested_by=processed_by,
            notes=notes,
        )
    except Exception:
        logger.exception("Finance posting failed for charity shop refund %s", refund_ref)

    if refund_method == STUDENT_ACCOUNT_REFUND and student_id:
        try:
            credit = top_up_student_finance_account(
                student_id=student_id,
                amount=amount,
                payment_method='Refund',
                processed_by=processed_by,
                description=f'Charity Shop Purchase Refund - {refund_ref}',
            )
            out['credited'] = bool(credit.get('success'))
            out['new_balance'] = credit.get('new_balance')
            out['message'] = credit.get('message', '')
            if not out['credited']:
                logger.warning("Charity shop refund %s: student account credit failed: %s",
                               refund_ref, credit.get('message'))
        except Exception:
            logger.exception("Charity shop refund %s: student account credit failed", refund_ref)
    return out


def refund_transaction(transaction_ref: str, amount: float, refund_method: str,
                       processed_by: str = 'System', reason: Optional[str] = None) -> Dict[str, Any]:
    """Refund a charity shop ``transactions`` row (GUI refund flow).

    Marks the local transaction refunded, posts the refund to Finance and,
    for ``refund_method == 'Student Account'``, credits the student's
    finance account. Returns ``{'success', 'refund_ref', 'student_id',
    'payment_method', 'refund_id', 'credited', 'new_balance', 'message'}``.
    """
    try:
        with transaction() as conn:
            row = conn.execute(
                "SELECT customer_id, payment_method, status FROM transactions "
                "WHERE source_type = 'charity_shop' AND reference_number = ?",
                (transaction_ref,),
            ).fetchone()
            if not row:
                return {'success': False, 'message': 'Transaction not found in database'}
            if row[2] == 'refunded':
                return {'success': False, 'message': 'This transaction has already been refunded'}
            conn.execute(
                "UPDATE transactions SET status = 'refunded' "
                "WHERE source_type = 'charity_shop' AND reference_number = ?",
                (transaction_ref,),
            )
    except Exception as e:
        logger.error("Charity shop refund of %s failed to save: %s", transaction_ref, e)
        return {'success': False, 'message': f"Error processing refund: {e}"}

    student_id, payment_method = row[0], row[1]
    refund_ref = f"CHARITY-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    posted = record_refund(
        amount=amount, refund_method=refund_method, refund_ref=refund_ref,
        student_id=student_id, processed_by=processed_by, reason=reason,
        notes=f"Transaction {transaction_ref}",
    )
    return {'success': True, 'refund_ref': refund_ref, 'student_id': student_id,
            'payment_method': payment_method, **posted}
