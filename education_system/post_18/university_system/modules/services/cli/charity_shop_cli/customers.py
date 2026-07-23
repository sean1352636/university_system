"""
Customer management: registration, wishlists, VIP, feedback, referrals.
"""

from education_system.post_18.university_system.modules.services.cli.charity_shop_cli._imports import (
    sqlite3, random, string, logger, datetime,
    get_connection, List, Dict, Any, Optional,
    TABLE_NAME, CUSTOMERS_TABLE, SALES_TABLE,
    WISHLISTS_TABLE, FEEDBACK_TABLE, REFERRALS_TABLE,
    ACTIVITY_LOGGER_AVAILABLE, log_activity, log_create,
)


def register_customer(name: str, email: str = None, phone: str = None,
                     address: str = None, birthday: str = None) -> Optional[int]:
    """Create customer profiles."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Generate referral code
        referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        cursor.execute(f"""
            INSERT INTO {CUSTOMERS_TABLE}
            (name, email, phone, address, birthday, date_registered, referral_code)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, email, phone, address, birthday,
              datetime.now().strftime("%Y-%m-%d"), referral_code))

        customer_id = cursor.lastrowid
        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_create('charity_shop_customer', customer_id=customer_id, name=name)

        return customer_id
    except sqlite3.Error as e:
        logger.error(f"Error registering customer: {e}")
        return None


def get_customer(customer_id: int) -> Optional[Dict]:
    """Get customer details."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"SELECT * FROM {CUSTOMERS_TABLE} WHERE id = ?", (customer_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            'id': row[0],
            'name': row[1],
            'email': row[2],
            'phone': row[3],
            'address': row[4],
            'date_registered': row[5],
            'birthday': row[6],
            'is_vip': row[7],
            'loyalty_points': row[8],
            'total_spent': row[9],
            'referral_code': row[10],
            'referred_by': row[11],
            'notes': row[12]
        }
    return None


def customer_purchase_history(customer_id: int) -> List[Dict]:
    """View customer transactions."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT sl.id, sl.sale_date, sl.quantity, sl.total_amount,
               sl.payment_method, sl.refunded, s.name as item_name
        FROM {SALES_TABLE} sl
        LEFT JOIN {TABLE_NAME} s ON sl.item_id = s.id
        WHERE sl.customer_id = ?
        ORDER BY sl.sale_date DESC
    """, (customer_id,))

    history = []
    for row in cursor.fetchall():
        history.append({
            'sale_id': row[0],
            'date': row[1],
            'quantity': row[2],
            'amount': row[3],
            'payment_method': row[4],
            'refunded': row[5],
            'item_name': row[6]
        })

    conn.close()
    return history


def customer_wishlist(customer_id: int, action: str, **kwargs) -> Any:
    """Save items customers are interested in."""
    conn = get_connection()
    cursor = conn.cursor()

    if action == 'add':
        description = kwargs.get('description', '')
        category = kwargs.get('category')
        max_price = kwargs.get('max_price')

        cursor.execute(f"""
            INSERT INTO {WISHLISTS_TABLE} (customer_id, item_description, category, max_price, date_added)
            VALUES (?, ?, ?, ?, ?)
        """, (customer_id, description, category, max_price, datetime.now().strftime("%Y-%m-%d")))

        conn.commit()
        conn.close()
        return True

    elif action == 'view':
        cursor.execute(f"SELECT * FROM {WISHLISTS_TABLE} WHERE customer_id = ?", (customer_id,))
        items = []
        for row in cursor.fetchall():
            items.append({
                'id': row[0],
                'description': row[2],
                'category': row[3],
                'max_price': row[4],
                'date_added': row[5],
                'notified': row[6]
            })
        conn.close()
        return items

    elif action == 'remove':
        wishlist_id = kwargs.get('wishlist_id')
        cursor.execute(f"DELETE FROM {WISHLISTS_TABLE} WHERE id = ? AND customer_id = ?",
                      (wishlist_id, customer_id))
        conn.commit()
        conn.close()
        return True

    conn.close()
    return None


def send_customer_notifications(customer_ids: List[int], subject: str, message: str,
                               method: str = 'email') -> int:
    """Email/SMS about new items (returns count of notifications sent)."""
    sent_count = 0
    conn = get_connection()
    cursor = conn.cursor()

    for cid in customer_ids:
        cursor.execute(f"SELECT email, phone, name FROM {CUSTOMERS_TABLE} WHERE id = ?", (cid,))
        customer = cursor.fetchone()

        if customer:
            # In production, this would actually send emails/SMS
            # For now, we just log the notification
            if ACTIVITY_LOGGER_AVAILABLE:
                log_activity('notification', 'charity_shop_customer',
                            customer_id=cid, method=method, subject=subject)
            sent_count += 1

    conn.close()
    return sent_count


def customer_feedback_system(action: str, **kwargs) -> Any:
    """Collect reviews and ratings."""
    conn = get_connection()
    cursor = conn.cursor()

    if action == 'submit':
        customer_id = kwargs.get('customer_id')
        item_id = kwargs.get('item_id')
        rating = kwargs.get('rating', 5)
        comment = kwargs.get('comment', '')

        cursor.execute(f"""
            INSERT INTO {FEEDBACK_TABLE} (customer_id, item_id, rating, comment, feedback_date)
            VALUES (?, ?, ?, ?, ?)
        """, (customer_id, item_id, rating, comment, datetime.now().strftime("%Y-%m-%d")))

        conn.commit()
        conn.close()
        return True

    elif action == 'view_item':
        item_id = kwargs.get('item_id')
        cursor.execute(f"""
            SELECT f.*, c.name as customer_name
            FROM {FEEDBACK_TABLE} f
            LEFT JOIN {CUSTOMERS_TABLE} c ON f.customer_id = c.id
            WHERE f.item_id = ?
            ORDER BY f.feedback_date DESC
        """, (item_id,))

        feedback = []
        for row in cursor.fetchall():
            feedback.append({
                'id': row[0],
                'rating': row[3],
                'comment': row[4],
                'date': row[5],
                'customer_name': row[6] if len(row) > 6 else 'Anonymous'
            })
        conn.close()
        return feedback

    elif action == 'average':
        item_id = kwargs.get('item_id')
        cursor.execute(f"SELECT AVG(rating), COUNT(*) FROM {FEEDBACK_TABLE} WHERE item_id = ?",
                      (item_id,))
        row = cursor.fetchone()
        conn.close()
        return {'average': row[0] or 0, 'count': row[1]}

    conn.close()
    return None


def vip_customer_management(action: str, customer_id: int = None) -> Any:
    """Track frequent shoppers."""
    conn = get_connection()
    cursor = conn.cursor()

    if action == 'make_vip':
        cursor.execute(f"UPDATE {CUSTOMERS_TABLE} SET is_vip = 1 WHERE id = ?", (customer_id,))
        conn.commit()
        conn.close()
        return True

    elif action == 'remove_vip':
        cursor.execute(f"UPDATE {CUSTOMERS_TABLE} SET is_vip = 0 WHERE id = ?", (customer_id,))
        conn.commit()
        conn.close()
        return True

    elif action == 'list_vips':
        cursor.execute(f"""
            SELECT id, name, email, total_spent, loyalty_points
            FROM {CUSTOMERS_TABLE}
            WHERE is_vip = 1
            ORDER BY total_spent DESC
        """)
        vips = []
        for row in cursor.fetchall():
            vips.append({
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'total_spent': row[3],
                'loyalty_points': row[4]
            })
        conn.close()
        return vips

    elif action == 'auto_promote':
        # Auto-promote customers who spent over threshold
        threshold = 500  # £500 total spent
        cursor.execute(f"""
            UPDATE {CUSTOMERS_TABLE}
            SET is_vip = 1
            WHERE total_spent >= ? AND is_vip = 0
        """, (threshold,))
        promoted = cursor.rowcount
        conn.commit()
        conn.close()
        return promoted

    conn.close()
    return None


def customer_birthday_discounts() -> List[Dict]:
    """Get customers with birthdays this month for special offers."""
    conn = get_connection()
    cursor = conn.cursor()

    current_month = datetime.now().strftime("%m")

    cursor.execute(f"""
        SELECT id, name, email, birthday, loyalty_points
        FROM {CUSTOMERS_TABLE}
        WHERE strftime('%m', birthday) = ?
    """, (current_month,))

    customers = []
    for row in cursor.fetchall():
        customers.append({
            'id': row[0],
            'name': row[1],
            'email': row[2],
            'birthday': row[3],
            'loyalty_points': row[4]
        })

    conn.close()
    return customers


def customer_referral_program(referrer_code: str, new_customer_id: int, reward_points: int = 100) -> bool:
    """Reward customer referrals."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Find referrer by code
        cursor.execute(f"SELECT id FROM {CUSTOMERS_TABLE} WHERE referral_code = ?", (referrer_code,))
        referrer = cursor.fetchone()

        if not referrer:
            conn.close()
            return False

        referrer_id = referrer[0]

        # Update new customer's referred_by
        cursor.execute(f"UPDATE {CUSTOMERS_TABLE} SET referred_by = ? WHERE id = ?",
                      (referrer_id, new_customer_id))

        # Record referral
        cursor.execute(f"""
            INSERT INTO {REFERRALS_TABLE} (referrer_id, referred_id, referral_date, reward_given, reward_amount)
            VALUES (?, ?, ?, 1, ?)
        """, (referrer_id, new_customer_id, datetime.now().strftime("%Y-%m-%d"), reward_points))

        # Award points to referrer
        cursor.execute(f"UPDATE {CUSTOMERS_TABLE} SET loyalty_points = loyalty_points + ? WHERE id = ?",
                      (reward_points, referrer_id))

        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error processing referral: {e}")
        return False
