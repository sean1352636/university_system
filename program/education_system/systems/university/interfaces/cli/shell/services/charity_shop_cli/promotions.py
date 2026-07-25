"""
Promotions, refunds, layaway, gift cards, and loyalty points.
"""

from education_system.systems.university.interfaces.cli.shell.services.charity_shop_cli._imports import (
    sqlite3, random, string, logger, datetime, timedelta,
    get_connection, List, Dict, Any, Optional,
    TABLE_NAME, CUSTOMERS_TABLE, SALES_TABLE, PROMOTIONS_TABLE,
    LAYAWAY_TABLE, GIFT_CARDS_TABLE, LOYALTY_TABLE,
    LOYALTY_POINTS_PER_POUND,
    ACTIVITY_LOGGER_AVAILABLE, log_activity, log_create,
)


def create_promotional_event(name: str, discount_type: str, discount_value: float,
                            start_date: str, end_date: str, category: str = None,
                            min_purchase: float = 0) -> Optional[int]:
    """Set up special sales events."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(f"""
            INSERT INTO {PROMOTIONS_TABLE}
            (name, discount_type, discount_value, start_date, end_date, category, min_purchase, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (name, discount_type, discount_value, start_date, end_date, category, min_purchase))

        promo_id = cursor.lastrowid
        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_create('charity_shop_promotion', promo_id=promo_id, name=name)

        return promo_id
    except sqlite3.Error as e:
        logger.error(f"Error creating promotion: {e}")
        return None


def get_active_promotions() -> List[Dict]:
    """Get currently active promotions."""
    conn = get_connection()
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute(f"""
        SELECT * FROM {PROMOTIONS_TABLE}
        WHERE is_active = 1 AND start_date <= ? AND end_date >= ?
    """, (today, today))

    promos = []
    for row in cursor.fetchall():
        promos.append({
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'discount_type': row[3],
            'discount_value': row[4],
            'start_date': row[5],
            'end_date': row[6],
            'category': row[7],
            'min_purchase': row[8]
        })

    conn.close()
    return promos


def process_refund(sale_id: int, reason: str) -> bool:
    """Handle returns and refunds."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get sale info
        cursor.execute(f"SELECT item_id, quantity, total_amount, customer_id FROM {SALES_TABLE} WHERE id = ?",
                      (sale_id,))
        sale = cursor.fetchone()

        if not sale:
            conn.close()
            return False

        item_id, qty, amount, customer_id = sale

        # Mark sale as refunded
        cursor.execute(f"""
            UPDATE {SALES_TABLE}
            SET refunded = 1, refund_date = ?, refund_reason = ?
            WHERE id = ?
        """, (datetime.now().strftime("%Y-%m-%d"), reason, sale_id))

        # Restore item quantity
        if item_id:
            cursor.execute(f"""
                UPDATE {TABLE_NAME}
                SET quantity = quantity + ?, sold_quantity = sold_quantity - ?, sold = 0
                WHERE id = ?
            """, (qty, qty, item_id))

        # Deduct loyalty points if applicable
        if customer_id:
            points_to_deduct = int(amount * LOYALTY_POINTS_PER_POUND)
            cursor.execute(f"""
                UPDATE {CUSTOMERS_TABLE}
                SET loyalty_points = MAX(0, loyalty_points - ?), total_spent = total_spent - ?
                WHERE id = ?
            """, (points_to_deduct, amount, customer_id))

        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('refund', 'charity_shop_sale', sale_id=sale_id, amount=amount, reason=reason)

        return True
    except sqlite3.Error as e:
        logger.error(f"Error processing refund: {e}")
        return False


def layaway_system(item_id: int, customer_id: int, deposit: float, due_days: int = 30) -> Optional[int]:
    """Hold items for customers with deposits."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get item price
        cursor.execute(f"SELECT price, quantity FROM {TABLE_NAME} WHERE id = ?", (item_id,))
        item = cursor.fetchone()

        if not item or item[1] <= 0:
            conn.close()
            return None

        total_price = item[0]
        remaining = total_price - deposit
        due_date = (datetime.now() + timedelta(days=due_days)).strftime("%Y-%m-%d")

        cursor.execute(f"""
            INSERT INTO {LAYAWAY_TABLE}
            (item_id, customer_id, total_price, deposit_paid, remaining_balance, start_date, due_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
        """, (item_id, customer_id, total_price, deposit, remaining,
              datetime.now().strftime("%Y-%m-%d"), due_date))

        layaway_id = cursor.lastrowid

        # Reserve item (reduce available quantity)
        cursor.execute(f"UPDATE {TABLE_NAME} SET quantity = quantity - 1 WHERE id = ?", (item_id,))

        conn.commit()
        conn.close()
        return layaway_id
    except sqlite3.Error as e:
        logger.error(f"Error creating layaway: {e}")
        return None


def get_layaways(customer_id: int = None, status: str = 'active') -> List[Dict]:
    """Get layaway records."""
    conn = get_connection()
    cursor = conn.cursor()

    query = f"""
        SELECT l.*, s.name as item_name, c.name as customer_name
        FROM {LAYAWAY_TABLE} l
        LEFT JOIN {TABLE_NAME} s ON l.item_id = s.id
        LEFT JOIN {CUSTOMERS_TABLE} c ON l.customer_id = c.id
        WHERE l.status = ?
    """
    params = [status]

    if customer_id:
        query += " AND l.customer_id = ?"
        params.append(customer_id)

    cursor.execute(query, params)

    layaways = []
    for row in cursor.fetchall():
        layaways.append({
            'id': row[0],
            'item_id': row[1],
            'customer_id': row[2],
            'total_price': row[3],
            'deposit_paid': row[4],
            'remaining_balance': row[5],
            'start_date': row[6],
            'due_date': row[7],
            'status': row[8],
            'item_name': row[9] if len(row) > 9 else '',
            'customer_name': row[10] if len(row) > 10 else ''
        })

    conn.close()
    return layaways


def gift_card_management(action: str, **kwargs) -> Any:
    """Issue and redeem gift cards."""
    conn = get_connection()
    cursor = conn.cursor()

    if action == 'issue':
        amount = kwargs.get('amount', 0)
        customer_id = kwargs.get('customer_id')
        expiry_days = kwargs.get('expiry_days', 365)

        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        expiry_date = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d")

        cursor.execute(f"""
            INSERT INTO {GIFT_CARDS_TABLE}
            (code, initial_balance, current_balance, date_issued, expiry_date, issued_to, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (code, amount, amount, datetime.now().strftime("%Y-%m-%d"), expiry_date, customer_id))

        conn.commit()
        conn.close()
        return {'code': code, 'balance': amount, 'expiry': expiry_date}

    elif action == 'check_balance':
        code = kwargs.get('code', '')
        cursor.execute(f"SELECT current_balance, expiry_date, is_active FROM {GIFT_CARDS_TABLE} WHERE code = ?",
                      (code,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return {'balance': result[0], 'expiry': result[1], 'active': result[2]}
        return None

    elif action == 'redeem':
        code = kwargs.get('code', '')
        amount = kwargs.get('amount', 0)

        cursor.execute(f"SELECT id, current_balance, is_active FROM {GIFT_CARDS_TABLE} WHERE code = ?",
                      (code,))
        card = cursor.fetchone()

        if not card or not card[2] or card[1] < amount:
            conn.close()
            return False

        new_balance = card[1] - amount
        cursor.execute(f"UPDATE {GIFT_CARDS_TABLE} SET current_balance = ? WHERE id = ?",
                      (new_balance, card[0]))

        conn.commit()
        conn.close()
        return {'new_balance': new_balance, 'redeemed': amount}

    conn.close()
    return None


def loyalty_points_system(customer_id: int, action: str, **kwargs) -> Any:
    """Track customer purchases for rewards."""
    conn = get_connection()
    cursor = conn.cursor()

    if action == 'check':
        cursor.execute(f"SELECT loyalty_points FROM {CUSTOMERS_TABLE} WHERE id = ?", (customer_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0

    elif action == 'add':
        points = kwargs.get('points', 0)
        reason = kwargs.get('reason', 'Purchase')
        sale_id = kwargs.get('sale_id')

        cursor.execute(f"UPDATE {CUSTOMERS_TABLE} SET loyalty_points = loyalty_points + ? WHERE id = ?",
                      (points, customer_id))

        cursor.execute(f"""
            INSERT INTO {LOYALTY_TABLE} (customer_id, points_change, reason, transaction_date, sale_id)
            VALUES (?, ?, ?, ?, ?)
        """, (customer_id, points, reason, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sale_id))

        conn.commit()
        conn.close()
        return True

    elif action == 'redeem':
        points = kwargs.get('points', 0)

        cursor.execute(f"SELECT loyalty_points FROM {CUSTOMERS_TABLE} WHERE id = ?", (customer_id,))
        current = cursor.fetchone()

        if not current or current[0] < points:
            conn.close()
            return False

        cursor.execute(f"UPDATE {CUSTOMERS_TABLE} SET loyalty_points = loyalty_points - ? WHERE id = ?",
                      (points, customer_id))

        cursor.execute(f"""
            INSERT INTO {LOYALTY_TABLE} (customer_id, points_change, reason, transaction_date)
            VALUES (?, ?, ?, ?)
        """, (customer_id, -points, 'Redemption', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        conn.commit()
        conn.close()
        return True

    conn.close()
    return None
