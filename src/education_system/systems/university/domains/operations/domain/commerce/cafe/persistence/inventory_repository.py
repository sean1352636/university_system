from education_system.systems.university.domains.operations.domain.commerce.cafe import *  # noqa: F401,F403
from .schema import get_db_connection

def update_stock(item_id: int, quantity_change: int, transaction_type: str, notes: str = "") -> bool:
    """Update stock quantity for an item."""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute(
            "UPDATE products SET stock_quantity = stock_quantity + ? WHERE product_id = ? AND source_type = 'cafe'",
            (quantity_change, item_id)
        )
        cursor.execute(
            "INSERT INTO transactions (source_type, reference_id, reference_type, quantity_change, transaction_type, notes) VALUES ('cafe_inventory', ?, 'item', ?, ?, ?)",
            (item_id, quantity_change, transaction_type, notes)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating stock: {e}")
        return False

def get_inventory_transactions(limit: int = 100) -> List[Tuple]:
    """Get recent inventory transactions."""
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()
    cursor.execute('''
        SELECT t.transaction_id, m.name, t.quantity_change, t.transaction_type, t.created_at, t.notes
        FROM transactions t
        JOIN products m ON t.reference_id = m.product_id AND m.source_type = 'cafe' AND t.reference_type = 'item'
        WHERE t.source_type = 'cafe_inventory'
        ORDER BY t.created_at DESC
        LIMIT ?
    ''', (limit,))
    results = cursor.fetchall()
    conn.close()
    return results
