"""Bar sales service shared by the bar GUI and CLI.

Both interfaces used to write the order rows themselves and post to Finance
inline (the CLI with a payload the finance hub did not even accept, so the
whole order rolled back). The local write and the Finance posting now live
here, so a sale rung up on either interface reaches the ledger exactly once.
Posting failures are logged and never roll back the local sale.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.systems.university.infrastructure.database.db import transaction
from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
    ensure_student_finance_account_exists,
    process_student_finance_account_payment,
    record_revenue_to_finance,
)

logger = logging.getLogger(__name__)

FINANCE_SOURCE = 'Bar'
_STUDENT_ACCOUNT_METHODS = {'student account', 'student finance account', 'finance_account', 'student_account'}


def is_student_account_method(payment_method: Optional[str]) -> bool:
    """True when the payment method means the student's finance account."""
    method = (payment_method or '').strip().lower()
    return method in _STUDENT_ACCOUNT_METHODS or ('student' in method and 'account' in method)


def post_sale_to_finance(order_id: int, student_id: Optional[str], amount: float,
                         payment_method: str, item_count: int,
                         processed_by: Optional[str] = None) -> Optional[int]:
    """Record a cash/card bar sale as revenue. Never raises."""
    try:
        payment_id = record_revenue_to_finance(
            student_id=student_id or 'EXTERNAL',
            amount=amount,
            revenue_category='Sale',
            transaction_source=FINANCE_SOURCE,
            transaction_ref=f"ORDER-{order_id}",
            payment_method=payment_method,
            notes=f"Bar Order #{order_id} - {item_count} items",
        )
        if payment_id is None:
            logger.warning("Bar order %s: revenue not posted to finance", order_id)
        return payment_id
    except Exception:
        logger.exception("Bar order %s: finance posting failed", order_id)
        return None


def complete_bar_sale(items: List[Dict[str, Any]], *, customer_name: str,
                      student_id: Optional[str], payment_method: str,
                      age_verified: bool = False,
                      processed_by: Optional[str] = None) -> Dict[str, Any]:
    """Charge the customer, write the order and post the sale to Finance.

    ``items`` are dicts with ``item_id``, ``name``, ``price`` and ``quantity``.
    Student-account sales are debited first (an insufficient balance blocks
    the sale and the finance account records its own payments row); every
    other method writes the order and then records the revenue.
    """
    if not items:
        return {'success': False, 'message': 'Order is empty'}

    total = round(sum(float(i['price']) * float(i['quantity']) for i in items), 2)
    student_id = (student_id or '').strip() or None
    payment_id = None
    charged_to_account = False

    if is_student_account_method(payment_method):
        if not student_id:
            return {'success': False, 'message': 'Student ID required for account payment'}
        try:
            ensure_student_finance_account_exists(student_id)
            result = process_student_finance_account_payment(
                student_id=student_id,
                amount=total,
                description=f"Bar purchase - {len(items)} items",
                transaction_source=FINANCE_SOURCE,
                transaction_ref=f"ORDER-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                processed_by=processed_by or 'System',
            )
        except Exception as e:
            logger.exception("Bar sale: student account payment failed")
            return {'success': False, 'message': f'Payment failed: {e}'}
        if not result.get('success'):
            return {'success': False, 'message': result.get('message', 'Student account payment failed')}
        payment_id = result.get('payment_id')
        charged_to_account = True

    try:
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO orders (source_type, student_id, customer_name, total_amount, payment_method, age_verified, order_status)
                VALUES ('bar', ?, ?, ?, ?, ?, 'completed')
            ''', (student_id, customer_name or 'Guest', total, payment_method, 1 if age_verified else 0))
            order_id = cursor.lastrowid

            for item in items:
                subtotal = round(float(item['price']) * float(item['quantity']), 2)
                conn.execute('''
                    INSERT INTO order_items (source_type, source_order_id, product_id, item_name, quantity, unit_price, subtotal)
                    VALUES ('bar', ?, ?, ?, ?, ?, ?)
                ''', (order_id, item['item_id'], item['name'], item['quantity'], item['price'], subtotal))
                conn.execute('''
                    UPDATE products SET stock_quantity = stock_quantity - ?
                    WHERE product_id = ? AND source_type = 'bar'
                ''', (item['quantity'], item['item_id']))
                conn.execute('''
                    INSERT INTO transactions (source_type, reference_id, reference_type, quantity_change, transaction_type, notes)
                    VALUES ('bar_inventory', ?, 'item', ?, 'sale', ?)
                ''', (item['item_id'], -item['quantity'], f'Order #{order_id}'))
    except Exception as e:
        logger.exception("Bar sale: order write failed")
        return {'success': False, 'message': f'Error processing order: {e}', 'payment_id': payment_id}

    if not charged_to_account:
        payment_id = post_sale_to_finance(order_id, student_id, total, payment_method,
                                          len(items), processed_by)

    return {'success': True, 'order_id': order_id, 'total': total,
            'payment_id': payment_id, 'message': f'Order #{order_id} completed'}
