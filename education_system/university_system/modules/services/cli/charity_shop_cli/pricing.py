"""
Barcodes, discounts, bundles, dynamic pricing, and price history.
"""

from ._imports import (
    sqlite3, json, logger, datetime,
    get_connection, List, Dict, Optional,
    TABLE_NAME, PRICE_HISTORY_TABLE, BUNDLES_TABLE,
    ACTIVITY_LOGGER_AVAILABLE, log_create,
)


def barcode_scanner_integration(barcode: str) -> Optional[Dict]:
    """Look up item by barcode or create new entry."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"SELECT * FROM {TABLE_NAME} WHERE barcode = ?", (barcode,))
    item = cursor.fetchone()
    conn.close()

    if item:
        return {
            'id': item[0],
            'name': item[1],
            'category': item[2],
            'price': item[3],
            'quantity': item[4],
            'condition': item[5],
            'barcode': barcode
        }
    return None


def set_item_barcode(item_id: int, barcode: str) -> bool:
    """Set barcode for an item."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE {TABLE_NAME} SET barcode = ? WHERE id = ?", (barcode, item_id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error setting barcode: {e}")
        return False


def apply_discount(item_id: int, discount_type: str, discount_value: float) -> bool:
    """Apply percentage or fixed discount to an item."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(f"SELECT price FROM {TABLE_NAME} WHERE id = ?", (item_id,))
        item = cursor.fetchone()

        if not item:
            conn.close()
            return False

        original_price = item[0]

        if discount_type == 'percent':
            new_price = original_price * (1 - discount_value / 100)
            discount_percent = discount_value
        else:  # fixed
            new_price = max(0, original_price - discount_value)
            discount_percent = (discount_value / original_price) * 100 if original_price > 0 else 0

        # Log price change
        cursor.execute(f"""
            INSERT INTO {PRICE_HISTORY_TABLE} (item_id, old_price, new_price, change_date, reason)
            VALUES (?, ?, ?, ?, ?)
        """, (item_id, original_price, new_price, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              f"Discount applied: {discount_type} {discount_value}"))

        cursor.execute(f"UPDATE {TABLE_NAME} SET price = ?, discount_percent = ? WHERE id = ?",
                      (new_price, discount_percent, item_id))

        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error applying discount: {e}")
        return False


def create_sale_bundle(name: str, description: str, item_ids: List[int], bundle_price: float) -> Optional[int]:
    """Bundle multiple items at special price."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(f"""
            INSERT INTO {BUNDLES_TABLE} (name, description, bundle_price, item_ids, date_created, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (name, description, bundle_price, json.dumps(item_ids),
              datetime.now().strftime("%Y-%m-%d")))

        bundle_id = cursor.lastrowid
        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_create('charity_shop_bundle', bundle_id=bundle_id, name=name, items=len(item_ids))

        return bundle_id
    except sqlite3.Error as e:
        logger.error(f"Error creating bundle: {e}")
        return None


def get_bundles(active_only: bool = True) -> List[Dict]:
    """Get all bundles."""
    conn = get_connection()
    cursor = conn.cursor()

    query = f"SELECT * FROM {BUNDLES_TABLE}"
    if active_only:
        query += " WHERE is_active = 1"

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    bundles = []
    for row in rows:
        bundles.append({
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'bundle_price': row[3],
            'item_ids': json.loads(row[4]) if row[4] else [],
            'date_created': row[5],
            'is_active': row[6],
            'times_sold': row[7]
        })
    return bundles


def price_history_tracker(item_id: int) -> List[Dict]:
    """Track price changes over time for an item."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT old_price, new_price, change_date, changed_by, reason
        FROM {PRICE_HISTORY_TABLE}
        WHERE item_id = ?
        ORDER BY change_date DESC
    """, (item_id,))

    history = []
    for row in cursor.fetchall():
        history.append({
            'old_price': row[0],
            'new_price': row[1],
            'change_date': row[2],
            'changed_by': row[3],
            'reason': row[4]
        })

    conn.close()
    return history


def dynamic_pricing_suggestions(item_id: int) -> Dict:
    """Suggest prices based on demand/condition."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"SELECT name, category, price, condition, quantity, date_added FROM {TABLE_NAME} WHERE id = ?",
                  (item_id,))
    item = cursor.fetchone()

    if not item:
        conn.close()
        return {}

    name, category, current_price, condition, qty, date_added = item

    # Get average price for category
    cursor.execute(f"SELECT AVG(price) FROM {TABLE_NAME} WHERE category = ? AND sold = 0",
                  (category,))
    avg_category_price = cursor.fetchone()[0] or current_price

    # Get sales velocity for this item
    cursor.execute(f"SELECT sold_quantity FROM {TABLE_NAME} WHERE id = ?", (item_id,))
    sold_qty = cursor.fetchone()[0] or 0

    # Calculate days in stock
    try:
        date_obj = datetime.strptime(date_added, "%Y-%m-%d")
        days_in_stock = (datetime.now() - date_obj).days
    except (ValueError, TypeError):
        days_in_stock = 0

    conn.close()

    # Condition multipliers
    condition_mult = {'New': 1.2, 'Excellent': 1.1, 'Good': 1.0, 'Fair': 0.8, 'Poor': 0.6}

    # Calculate suggested price
    base_suggestion = avg_category_price * condition_mult.get(condition, 1.0)

    # Adjust for slow-moving items
    if days_in_stock > 60 and sold_qty == 0:
        base_suggestion *= 0.85  # 15% reduction for slow movers
    elif days_in_stock > 90:
        base_suggestion *= 0.75  # 25% reduction

    return {
        'current_price': current_price,
        'suggested_price': round(base_suggestion, 2),
        'category_average': round(avg_category_price, 2),
        'days_in_stock': days_in_stock,
        'condition': condition,
        'reason': 'Based on category average, condition, and time in stock'
    }
