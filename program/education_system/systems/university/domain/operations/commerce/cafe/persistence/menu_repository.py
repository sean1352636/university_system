from education_system.systems.university.domain.operations.commerce.cafe import *  # noqa: F401,F403
from .schema import get_db_connection

def get_all_menu_items(category: str = None, available_only: bool = False) -> List[Tuple]:
    """Retrieve all menu items with optional filtering."""
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()
    query = "SELECT product_id, name, category, description, price, is_available, stock_quantity FROM products WHERE source_type = 'cafe'"
    params = []

    conditions = []
    if category and category != "All":
        conditions.append("category = ?")
        params.append(category)
    if available_only:
        conditions.append("is_available = 1")

    if conditions:
        query += " AND " + " AND ".join(conditions)

    query += " ORDER BY category, name"
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return results

def get_menu_item(item_id: int) -> Optional[Tuple]:
    """Get a single menu item by ID."""
    conn = get_db_connection()
    if not conn:
        return None

    cursor = conn.cursor()
    cursor.execute(
        "SELECT product_id, name, category, description, price, is_available, stock_quantity FROM products WHERE source_type = 'cafe' AND product_id = ?",
        (item_id,)
    )
    result = cursor.fetchone()
    conn.close()
    return result

def add_menu_item(name: str, category: str, description: str, price: float, stock: int) -> bool:
    """Add a new menu item."""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO products (source_type, name, category, description, price, is_available, stock_quantity) VALUES ('cafe', ?, ?, ?, ?, 1, ?)",
            (name, category, description, price, stock)
        )
        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_create('cafe_menu_item', item_name=name, category=category, price=price)

        return True
    except sqlite3.Error as e:
        logger.error(f"Error adding menu item: {e}")
        return False

def update_menu_item(item_id: int, name: str, category: str, price: float, stock: int, available: bool) -> bool:
    """Update an existing menu item."""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute(
            "UPDATE products SET name = ?, category = ?, price = ?, stock_quantity = ?, is_available = ? WHERE product_id = ? AND source_type = 'cafe'",
            (name, category, price, stock, 1 if available else 0, item_id)
        )
        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_update('cafe_menu_item', item_id=item_id, changes={'name': name, 'price': price})

        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating menu item: {e}")
        return False

def delete_menu_item(item_id: int) -> bool:
    """Delete a menu item."""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute("SELECT name FROM products WHERE source_type = 'cafe' AND product_id = ?", (item_id,))
        row = cursor.fetchone()
        item_name = row[0] if row else "Unknown"

        cursor.execute("DELETE FROM products WHERE product_id = ? AND source_type = 'cafe'", (item_id,))
        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_delete('cafe_menu_item', item_id=item_id, item_name=item_name)

        return True
    except sqlite3.Error as e:
        logger.error(f"Error deleting menu item: {e}")
        return False
