from datetime import datetime
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH
from education_system.systems.university.domain.operations.commerce.services.shop_management import config
from education_system.systems.university.domain.operations.commerce.services.shop_management.config import get_system_settings
from education_system.systems.university.domain.operations.commerce.services.shop_management.inventory import get_inventory_valuation


def log_shop_activity(activity_type, description, user_id=None, details=None):
    """Log shop activities for audit trail"""

    try:
        if not user_id and config.auth and config.auth.current_user:
            user_id = config.auth.current_user['id']

        # This would typically log to a separate audit table
        # For now, we'll just use the simple activity logger
        from education_system.systems.university.infrastructure.utils.activity_logger import log_dynamic_activity

        log_dynamic_activity(
            module="shop",
            activity_type=activity_type,
            description=description,
            user_id=user_id,
            additional_data=details
        )

    except Exception as e:
        # Don't let logging errors break the main functionality
        print(f"Warning: Could not log activity: {e}")


def get_transaction_summary(transaction_id):
    """Get a detailed summary of a transaction"""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get transaction
        cursor.execute(
            '''
            SELECT t.*, u.username, u.email
            FROM transactions t
            LEFT JOIN users u ON t.customer_id = u.id
            WHERE t.source_type = 'shop' AND t.source_transaction_id = ?
            ''',
            [transaction_id]
        )

        transaction = cursor.fetchone()

        if not transaction:
            conn.close()
            return None

        # Get items
        cursor.execute(
            '''
            SELECT ti.*, p.name, p.category
            FROM shop_transaction_items ti
            JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'shop'
            WHERE ti.transaction_id = ?
            ORDER BY p.name
            ''',
            [transaction_id]
        )

        items = cursor.fetchall()

        conn.close()

        return {
            'transaction': dict(transaction),
            'items': [dict(item) for item in items],
            'item_count': len(items),
            'total_quantity': sum(item['quantity'] for item in items)
        }

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"Error getting transaction summary: {e}")
        return None


def backup_shop_database():
    """Create a backup of the shop database"""
    try:
        import shutil

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"shop_backup_{timestamp}.db"

        db_path = str(DEFAULT_DB_PATH)
        shutil.copy2(db_path, backup_filename)

        print(f"Database backup created: {backup_filename}")
        return backup_filename

    except Exception as e:
        print(f"Error creating backup: {e}")
        return None


def test_shop_system():
    """Test basic shop system functionality"""
    print("\nTesting Shop System...")

    try:
        # Test database connection
        conn = get_connection()
        cursor = conn.cursor()

        # Test tables exist
        tables = ['products', 'shop_inventory', 'transactions', 'shop_transaction_items', 'shop_discounts', 'cart']

        for table in tables:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            if not cursor.fetchone():
                print(f"Table {table} not found")
                conn.close()
                return False

        # Test sample data
        cursor.execute("SELECT COUNT(*) FROM products WHERE source_type = 'shop'")
        product_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM shop_inventory")
        inventory_count = cursor.fetchone()[0]

        conn.close()

        print("Database structure: OK")
        print(f"Products: {product_count}")
        print(f"Inventory records: {inventory_count}")

        # Test utility functions
        settings = get_system_settings()
        if settings and 'currency_symbol' in settings:
            print("System settings: OK")

        valuation = get_inventory_valuation()
        if valuation:
            print(f"Inventory valuation: \u00a3{valuation['total_value']:.2f}")

        print("Shop system test completed successfully!")
        return True

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"Shop system test failed: {e}")
        return False
