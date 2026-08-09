from education_system.systems.university.domain.operations.commerce.cafe import *  # noqa: F401,F403
from .schema import get_db_connection

def create_order(student_id: str, customer_name: str, items: List[Dict], payment_method: str) -> Optional[int]:
    """Create a new order with items."""
    try:
        conn = get_db_connection()
        if not conn:
            return None

        cursor = conn.cursor()

        # Calculate total
        total = sum(item['subtotal'] for item in items)

        # Insert order
        cursor.execute(
            "INSERT INTO orders (source_type, student_id, customer_name, total_amount, payment_method, order_status) VALUES ('cafe', ?, ?, ?, ?, 'completed')",
            (student_id or None, customer_name, total, payment_method)
        )
        order_id = cursor.lastrowid

        # Insert order items and update inventory
        for item in items:
            cursor.execute(
                "INSERT INTO order_items (source_type, source_order_id, product_id, item_name, quantity, unit_price, subtotal) VALUES ('cafe', ?, ?, ?, ?, ?, ?)",
                (order_id, item['item_id'], item['name'], item['quantity'], item['price'], item['subtotal'])
            )

            # Update inventory
            cursor.execute(
                "UPDATE products SET stock_quantity = stock_quantity - ? WHERE product_id = ? AND source_type = 'cafe'",
                (item['quantity'], item['item_id'])
            )

            # Log inventory transaction
            cursor.execute(
                "INSERT INTO transactions (source_type, reference_id, reference_type, quantity_change, transaction_type, notes) VALUES ('cafe_inventory', ?, 'item', ?, 'sale', ?)",
                (item['item_id'], -item['quantity'], f'Order #{order_id}')
            )

        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('sale', 'cafe_order', order_id=order_id, total=total, payment_method=payment_method)

        return order_id
    except sqlite3.Error as e:
        logger.error(f"Error creating order: {e}")
        return None

def get_orders(filter_type: str = "all") -> List[Tuple]:
    """Get order history with optional date filter."""
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()

    source_filter = "WHERE o.source_type = 'cafe'"
    if filter_type == "today":
        source_filter = "WHERE o.source_type = 'cafe' AND DATE(o.order_date) = DATE('now')"
    elif filter_type == "week":
        source_filter = "WHERE o.source_type = 'cafe' AND DATE(o.order_date) >= DATE('now', '-7 days')"
    elif filter_type == "month":
        source_filter = "WHERE o.source_type = 'cafe' AND DATE(o.order_date) >= DATE('now', 'start of month')"

    query = f'''
        SELECT
            o.order_id,
            o.order_date,
            COALESCE(o.customer_name, o.student_id, 'Walk-in'),
            COUNT(oi.item_id),
            o.total_amount,
            o.payment_method,
            o.order_status
        FROM orders o
        LEFT JOIN order_items oi ON o.order_id = oi.source_order_id AND oi.source_type = 'cafe'
        {source_filter}
        GROUP BY o.order_id
        ORDER BY o.order_date DESC
    '''

    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    return results

def get_order_items(order_id: int) -> List[Tuple]:
    """Get items for a specific order."""
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()
    cursor.execute(
        "SELECT item_name, quantity, unit_price, subtotal FROM order_items WHERE source_type = 'cafe' AND source_order_id = ?",
        (order_id,)
    )
    results = cursor.fetchall()
    conn.close()
    return results
