"""
Stock archival, restoration, and location transfer operations.
"""

from education_system.systems.university.interfaces.cli.shell.services.charity_shop_cli._imports import (
    sqlite3, logger, datetime, timedelta,
    get_connection, List, Tuple, Optional, Dict,
    TABLE_NAME, ARCHIVED_TABLE, LOCATIONS_TABLE,
    ACTIVITY_LOGGER_AVAILABLE, log_activity,
)


def archive_old_items(days_old: int = 90) -> int:
    """Move items older than X days to archive. Returns count of archived items."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cutoff_date = (datetime.now() - timedelta(days=days_old)).strftime("%Y-%m-%d")

        # Get items to archive
        cursor.execute(f"""
            SELECT id, name, category, price, quantity, condition, date_added
            FROM {TABLE_NAME}
            WHERE sold = 0 AND date_added < ?
        """, (cutoff_date,))
        items = cursor.fetchall()

        archived_count = 0
        for item in items:
            cursor.execute(f"""
                INSERT INTO {ARCHIVED_TABLE}
                (original_id, name, category, price, quantity, condition, date_added, date_archived, archive_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (item[0], item[1], item[2], item[3], item[4], item[5], item[6],
                  datetime.now().strftime("%Y-%m-%d"), f"Auto-archived: older than {days_old} days"))

            cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE id = ?", (item[0],))
            archived_count += 1

        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('archive_items', 'charity_shop_items', count=archived_count, days=days_old)

        return archived_count
    except sqlite3.Error as e:
        logger.error(f"Error archiving items: {e}")
        return 0


def restore_archived_items(archived_ids: List[int] = None) -> int:
    """Bring back archived items. If no IDs provided, shows list to choose from."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        if not archived_ids:
            return 0

        restored_count = 0
        for arch_id in archived_ids:
            cursor.execute(f"SELECT * FROM {ARCHIVED_TABLE} WHERE id = ?", (arch_id,))
            item = cursor.fetchone()

            if item:
                cursor.execute(f"""
                    INSERT INTO {TABLE_NAME} (name, category, price, quantity, condition, date_added, sold, sold_quantity)
                    VALUES (?, ?, ?, ?, ?, ?, 0, 0)
                """, (item[2], item[3], item[4], item[5], item[6], datetime.now().strftime("%Y-%m-%d")))

                cursor.execute(f"DELETE FROM {ARCHIVED_TABLE} WHERE id = ?", (arch_id,))
                restored_count += 1

        conn.commit()
        conn.close()
        return restored_count
    except sqlite3.Error as e:
        logger.error(f"Error restoring items: {e}")
        return 0


def get_archived_items() -> List[Tuple]:
    """Get list of archived items."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {ARCHIVED_TABLE} ORDER BY date_archived DESC")
    results = cursor.fetchall()
    conn.close()
    return results


def transfer_between_locations(item_id: int, from_location: int, to_location: int, quantity: int) -> bool:
    """Transfer stock to different shop locations."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check item exists and has enough quantity
        cursor.execute(f"SELECT quantity, name FROM {TABLE_NAME} WHERE id = ? AND location_id = ?",
                      (item_id, from_location))
        item = cursor.fetchone()

        if not item or item[0] < quantity:
            conn.close()
            return False

        # Reduce from source
        cursor.execute(f"UPDATE {TABLE_NAME} SET quantity = quantity - ? WHERE id = ?",
                      (quantity, item_id))

        # Check if item exists at destination
        cursor.execute(f"""
            SELECT id FROM {TABLE_NAME}
            WHERE name = (SELECT name FROM {TABLE_NAME} WHERE id = ?) AND location_id = ?
        """, (item_id, to_location))
        dest_item = cursor.fetchone()

        if dest_item:
            cursor.execute(f"UPDATE {TABLE_NAME} SET quantity = quantity + ? WHERE id = ?",
                          (quantity, dest_item[0]))
        else:
            # Create new item at destination
            cursor.execute(f"""
                INSERT INTO {TABLE_NAME} (name, category, price, quantity, condition, date_added, sold, location_id)
                SELECT name, category, price, ?, condition, ?, 0, ?
                FROM {TABLE_NAME} WHERE id = ?
            """, (quantity, datetime.now().strftime("%Y-%m-%d"), to_location, item_id))

        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('transfer', 'charity_shop_item', item_id=item_id,
                        from_location=from_location, to_location=to_location, quantity=quantity)

        return True
    except sqlite3.Error as e:
        logger.error(f"Error transferring items: {e}")
        return False


def get_all_locations() -> List[Dict]:
    """Get all shop locations."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"SELECT * FROM {LOCATIONS_TABLE} WHERE is_active = 1 ORDER BY name")

    locations = []
    for row in cursor.fetchall():
        locations.append({
            'id': row[0],
            'name': row[1],
            'address': row[2],
            'phone': row[3],
            'manager': row[4]
        })

    conn.close()
    return locations


def add_location(name: str, address: str = None, phone: str = None, manager: str = None) -> Optional[int]:
    """Add a new shop location."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(f"""
            INSERT INTO {LOCATIONS_TABLE} (name, address, phone, manager, is_active)
            VALUES (?, ?, ?, ?, 1)
        """, (name, address, phone, manager))

        location_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return location_id
    except sqlite3.Error as e:
        logger.error(f"Error adding location: {e}")
        return None
