"""
Core inventory management: CRUD, bulk import/export, stock adjustments.
"""

from ._imports import (
    sqlite3, csv, logger, datetime, timedelta,
    get_connection, List, Tuple, Optional,
    TABLE_NAME, DEFAULT_LOW_STOCK_THRESHOLD,
    ACTIVITY_LOGGER_AVAILABLE, log_activity, log_create, log_update, log_delete,
)


def get_all_stock(show_sold: str = "all") -> List[Tuple]:
    """Retrieve all stock items with optional sold filter."""
    conn = get_connection()
    cursor = conn.cursor()

    if show_sold == "available":
        cursor.execute(
            f"SELECT id, name, category, price, quantity, condition, date_added, sold, sold_date, sold_quantity FROM {TABLE_NAME} WHERE sold = 0 ORDER BY name"
        )
    elif show_sold == "sold":
        cursor.execute(
            f"SELECT id, name, category, price, quantity, condition, date_added, sold, sold_date, sold_quantity FROM {TABLE_NAME} WHERE sold = 1 ORDER BY sold_date DESC"
        )
    else:
        cursor.execute(
            f"SELECT id, name, category, price, quantity, condition, date_added, sold, sold_date, sold_quantity FROM {TABLE_NAME} ORDER BY name"
        )

    results = cursor.fetchall()
    conn.close()
    return results


def search_stock(search_term: str, category: str = "All", show_sold: str = "all") -> List[Tuple]:
    """Search stock by name and optionally filter by category and sold status."""
    conn = get_connection()
    cursor = conn.cursor()

    query = f"SELECT id, name, category, price, quantity, condition, date_added, sold, sold_date, sold_quantity FROM {TABLE_NAME} WHERE name LIKE ?"
    params = [f"%{search_term}%"]

    if category != "All":
        query += " AND category = ?"
        params.append(category)

    if show_sold == "available":
        query += " AND sold = 0"
    elif show_sold == "sold":
        query += " AND sold = 1"

    query += " ORDER BY name"
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return results


def add_item(name: str, category: str, price: float, quantity: int, condition: str) -> bool:
    """Add a new stock item."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"INSERT INTO {TABLE_NAME} (name, category, price, quantity, condition, date_added, sold, sold_quantity) VALUES (?, ?, ?, ?, ?, ?, 0, 0)",
            (name, category, price, quantity, condition, datetime.now().strftime("%Y-%m-%d"))
        )
        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_create('charity_shop_item', item_name=name, category=category, price=price, quantity=quantity)

        return True
    except sqlite3.Error as e:
        logger.error(f"Error adding item: {e}")
        return False


def update_item(item_id: int, name: str, category: str, price: float, quantity: int,
                condition: str, sold: bool, sold_quantity: int = 0) -> bool:
    """Update an existing stock item."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        sold_date = datetime.now().strftime("%Y-%m-%d") if sold else None
        cursor.execute(
            f"UPDATE {TABLE_NAME} SET name = ?, category = ?, price = ?, quantity = ?, condition = ?, sold = ?, sold_date = ?, sold_quantity = ? WHERE id = ?",
            (name, category, price, quantity, condition, 1 if sold else 0, sold_date, sold_quantity, item_id)
        )
        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_update('charity_shop_item', item_id=item_id, changes={'name': name, 'price': price})

        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating item: {e}")
        return False


def mark_as_sold(item_id: int, quantity_sold: int = None) -> bool:
    """Mark an item as sold."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get current item
        cursor.execute(f"SELECT name, quantity, sold_quantity, price FROM {TABLE_NAME} WHERE id = ?", (item_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False

        item_name, current_qty, current_sold_qty, price = row
        current_sold_qty = current_sold_qty or 0

        if quantity_sold is None:
            quantity_sold = current_qty

        new_qty = max(0, current_qty - quantity_sold)
        new_sold_qty = current_sold_qty + quantity_sold

        # Mark as fully sold if no quantity left
        is_sold = 1 if new_qty == 0 else 0
        sold_date = datetime.now().strftime("%Y-%m-%d") if is_sold else None

        cursor.execute(
            f"UPDATE {TABLE_NAME} SET quantity = ?, sold = ?, sold_date = ?, sold_quantity = ? WHERE id = ?",
            (new_qty, is_sold, sold_date, new_sold_qty, item_id)
        )
        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('sell', 'charity_shop_item', item_id=item_id, item_name=item_name,
                         quantity_sold=quantity_sold, revenue=quantity_sold * price)

        return True
    except sqlite3.Error as e:
        logger.error(f"Error marking item as sold: {e}")
        return False


def mark_as_available(item_id: int) -> bool:
    """Mark an item as available (not sold)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE {TABLE_NAME} SET sold = 0, sold_date = NULL WHERE id = ?",
            (item_id,)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error marking item as available: {e}")
        return False


def delete_item(item_id: int) -> bool:
    """Delete a stock item."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get item name for logging
        cursor.execute(f"SELECT name FROM {TABLE_NAME} WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        item_name = row[0] if row else "Unknown"

        cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_delete('charity_shop_item', item_id=item_id, item_name=item_name)

        return True
    except sqlite3.Error as e:
        logger.error(f"Error deleting item: {e}")
        return False


def get_stock_summary() -> Tuple:
    """Get summary statistics for available stock."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT
            COUNT(*) as total_items,
            COALESCE(SUM(quantity), 0) as total_quantity,
            COALESCE(SUM(price * quantity), 0) as total_value
        FROM {TABLE_NAME} WHERE sold = 0
    """)
    result = cursor.fetchone()
    conn.close()
    return result


def get_revenue_summary() -> Tuple:
    """Get revenue statistics from sold items."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT
            COUNT(*) as sold_items,
            COALESCE(SUM(sold_quantity), 0) as total_sold,
            COALESCE(SUM(price * sold_quantity), 0) as total_revenue
        FROM {TABLE_NAME} WHERE sold_quantity > 0
    """)
    result = cursor.fetchone()
    conn.close()
    return result


def get_revenue_by_category() -> List[Tuple]:
    """Get revenue breakdown by category."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT category, SUM(price * sold_quantity) as revenue
        FROM {TABLE_NAME} WHERE sold_quantity > 0
        GROUP BY category
        ORDER BY revenue DESC
    """)
    results = cursor.fetchall()
    conn.close()
    return results


def get_stock_by_category() -> List[Tuple]:
    """Get stock count by category."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT category, COUNT(*) as count, SUM(quantity) as total_qty
        FROM {TABLE_NAME} WHERE sold = 0
        GROUP BY category
        ORDER BY count DESC
    """)
    results = cursor.fetchall()
    conn.close()
    return results


def bulk_import_items(file_path: str) -> Tuple[int, int]:
    """
    Import items from CSV file.
    Returns (success_count, error_count).
    """
    success_count = 0
    error_count = 0

    try:
        with open(file_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    name = row.get('name', '').strip()
                    category = row.get('category', 'Other').strip()
                    price = float(row.get('price', 0))
                    quantity = int(row.get('quantity', 1))
                    condition = row.get('condition', 'Good').strip()

                    if name and add_item(name, category, price, quantity, condition):
                        success_count += 1
                    else:
                        error_count += 1
                except (ValueError, KeyError):
                    error_count += 1

        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('bulk_import', 'charity_shop_items',
                        file=file_path, success=success_count, errors=error_count)

    except FileNotFoundError:
        logger.error(f"Import file not found: {file_path}")
        return 0, -1
    except Exception as e:
        logger.error(f"Error importing items: {e}")
        return success_count, error_count

    return success_count, error_count


def bulk_export_items(file_path: str, filter_type: str = "all") -> bool:
    """Export inventory to CSV file."""
    try:
        stock = get_all_stock(filter_type)

        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'name', 'category', 'price', 'quantity',
                           'condition', 'date_added', 'sold', 'sold_date', 'sold_quantity'])
            for item in stock:
                writer.writerow(item)

        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('bulk_export', 'charity_shop_items',
                        file=file_path, count=len(stock))

        return True
    except Exception as e:
        logger.error(f"Error exporting items: {e}")
        return False


def adjust_stock_quantity(item_id: int, adjustment: int, reason: str = "") -> bool:
    """Quick adjust stock levels (add positive, subtract negative)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(f"SELECT quantity, name FROM {TABLE_NAME} WHERE id = ?", (item_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False

        current_qty, name = row
        new_qty = max(0, current_qty + adjustment)

        cursor.execute(f"UPDATE {TABLE_NAME} SET quantity = ? WHERE id = ?", (new_qty, item_id))
        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('adjust_stock', 'charity_shop_item', item_id=item_id,
                        item_name=name, adjustment=adjustment, reason=reason)

        return True
    except sqlite3.Error as e:
        logger.error(f"Error adjusting stock: {e}")
        return False


def set_low_stock_alert(item_id: int, threshold: int) -> bool:
    """Configure low stock alert threshold for an item."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE {TABLE_NAME} SET low_stock_threshold = ? WHERE id = ?",
                      (threshold, item_id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error setting low stock alert: {e}")
        return False


def view_low_stock_items(threshold: int = None) -> List[Tuple]:
    """Show items needing restock (below threshold)."""
    conn = get_connection()
    cursor = conn.cursor()

    if threshold:
        cursor.execute(f"""
            SELECT id, name, category, quantity, low_stock_threshold
            FROM {TABLE_NAME}
            WHERE sold = 0 AND quantity <= ?
            ORDER BY quantity ASC
        """, (threshold,))
    else:
        cursor.execute(f"""
            SELECT id, name, category, quantity, COALESCE(low_stock_threshold, {DEFAULT_LOW_STOCK_THRESHOLD}) as threshold
            FROM {TABLE_NAME}
            WHERE sold = 0 AND quantity <= COALESCE(low_stock_threshold, {DEFAULT_LOW_STOCK_THRESHOLD})
            ORDER BY quantity ASC
        """)

    results = cursor.fetchall()
    conn.close()
    return results


def merge_duplicate_items(item_id_keep: int, item_id_merge: int) -> bool:
    """Combine similar items by merging quantities."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get both items
        cursor.execute(f"SELECT quantity, sold_quantity FROM {TABLE_NAME} WHERE id = ?", (item_id_keep,))
        keep_item = cursor.fetchone()

        cursor.execute(f"SELECT quantity, sold_quantity, name FROM {TABLE_NAME} WHERE id = ?", (item_id_merge,))
        merge_item = cursor.fetchone()

        if not keep_item or not merge_item:
            conn.close()
            return False

        new_qty = keep_item[0] + merge_item[0]
        new_sold_qty = (keep_item[1] or 0) + (merge_item[1] or 0)

        cursor.execute(f"UPDATE {TABLE_NAME} SET quantity = ?, sold_quantity = ? WHERE id = ?",
                      (new_qty, new_sold_qty, item_id_keep))
        cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE id = ?", (item_id_merge,))

        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('merge_items', 'charity_shop_items',
                        kept_id=item_id_keep, merged_id=item_id_merge, merged_name=merge_item[2])

        return True
    except sqlite3.Error as e:
        logger.error(f"Error merging items: {e}")
        return False
