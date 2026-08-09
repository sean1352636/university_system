"""Charity Shop - Database operations."""

from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.interfaces.gui.shell.services.charity_shop_gui._imports import (
    sqlite3, validate_table_name, safe_alter_table_add_column,
    DEFAULT_DB_PATH, datetime, timedelta, logging,
)

logger = logging.getLogger(__name__)


class Database:
    """Handle all database operations for charity shop inventory."""

    TABLE_NAME = "charity_shop_stock"

    def __init__(self, db_path: str = None):
        """Initialize database with optional custom path.

        Args:
            db_path: Path to database file. Defaults to university system's student_records.db
        """
        validate_table_name(self.TABLE_NAME)
        self.db_path = db_path if db_path else str(DEFAULT_DB_PATH)
        self.init_database()

    def get_connection(self):
        """Get a database connection."""
        return sqlite3.connect(self.db_path)

    def init_database(self):
        """Create the charity_shop_stock table if it doesn't exist."""
        with self.get_connection() as conn:
            # Check if we need to migrate (add sold columns)
            cursor = conn.execute(f"PRAGMA table_info({self.TABLE_NAME})")
            columns = [col[1] for col in cursor.fetchall()]

            if 'sold' not in columns:
                # Table doesn't exist or needs migration
                if 'id' in columns:
                    # Migration: add new columns to existing table
                    safe_alter_table_add_column(self.TABLE_NAME, "sold", "INTEGER DEFAULT 0", conn)
                    safe_alter_table_add_column(self.TABLE_NAME, "sold_date", "TEXT", conn)
                    safe_alter_table_add_column(self.TABLE_NAME, "sold_quantity", "INTEGER DEFAULT 0", conn)
                else:
                    # Create new table
                    conn.execute(f"""
                        CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL,
                            category TEXT NOT NULL,
                            price REAL NOT NULL,
                            quantity INTEGER NOT NULL,
                            condition TEXT DEFAULT 'Good',
                            date_added TEXT NOT NULL,
                            sold INTEGER DEFAULT 0,
                            sold_date TEXT,
                            sold_quantity INTEGER DEFAULT 0
                        )
                    """)
            conn.commit()
            logger.info(f"Charity shop database initialized at {self.db_path}")

    def get_all_stock(self, show_sold: str = "all"):
        """Retrieve all stock items with optional sold filter."""
        with self.get_connection() as conn:
            if show_sold == "available":
                cursor = conn.execute(
                    f"SELECT id, name, category, price, quantity, condition, date_added, sold, sold_date, sold_quantity FROM {self.TABLE_NAME} WHERE sold = 0 ORDER BY name"
                )
            elif show_sold == "sold":
                cursor = conn.execute(
                    f"SELECT id, name, category, price, quantity, condition, date_added, sold, sold_date, sold_quantity FROM {self.TABLE_NAME} WHERE sold = 1 ORDER BY sold_date DESC"
                )
            else:
                cursor = conn.execute(
                    f"SELECT id, name, category, price, quantity, condition, date_added, sold, sold_date, sold_quantity FROM {self.TABLE_NAME} ORDER BY name"
                )
            return cursor.fetchall()

    def search_stock(self, search_term: str, category: str = "All", show_sold: str = "all"):
        """Search stock by name and optionally filter by category and sold status."""
        with self.get_connection() as conn:
            query = f"SELECT id, name, category, price, quantity, condition, date_added, sold, sold_date, sold_quantity FROM {self.TABLE_NAME} WHERE name LIKE ?"
            params = [f"%{escape_like(search_term)}%"]

            if category != "All":
                query += " AND category = ?"
                params.append(category)

            if show_sold == "available":
                query += " AND sold = 0"
            elif show_sold == "sold":
                query += " AND sold = 1"

            query += " ORDER BY name"
            cursor = conn.execute(query, params)
            return cursor.fetchall()

    def add_item(self, name: str, category: str, price: float, quantity: int, condition: str):
        """Add a new stock item."""
        with self.get_connection() as conn:
            conn.execute(
                f"INSERT INTO {self.TABLE_NAME} (name, category, price, quantity, condition, date_added, sold, sold_quantity) VALUES (?, ?, ?, ?, ?, ?, 0, 0)",
                (name, category, price, quantity, condition, datetime.now().strftime("%Y-%m-%d"))
            )
            conn.commit()

    def update_item(self, item_id: int, name: str, category: str, price: float, quantity: int, condition: str, sold: bool, sold_quantity: int = 0):
        """Update an existing stock item."""
        with self.get_connection() as conn:
            sold_date = datetime.now().strftime("%Y-%m-%d") if sold else None
            conn.execute(
                f"UPDATE {self.TABLE_NAME} SET name = ?, category = ?, price = ?, quantity = ?, condition = ?, sold = ?, sold_date = ?, sold_quantity = ? WHERE id = ?",
                (name, category, price, quantity, condition, 1 if sold else 0, sold_date, sold_quantity, item_id)
            )
            conn.commit()

    def mark_as_sold(self, item_id: int, quantity_sold: int = None):
        """Mark an item as sold."""
        with self.get_connection() as conn:
            # Get current item
            cursor = conn.execute(f"SELECT quantity, sold_quantity FROM {self.TABLE_NAME} WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            if row:
                current_qty = row[0]
                current_sold_qty = row[1] or 0

                if quantity_sold is None:
                    quantity_sold = current_qty

                new_qty = max(0, current_qty - quantity_sold)
                new_sold_qty = current_sold_qty + quantity_sold

                # Mark as fully sold if no quantity left
                is_sold = 1 if new_qty == 0 else 0
                sold_date = datetime.now().strftime("%Y-%m-%d") if is_sold else None

                conn.execute(
                    f"UPDATE {self.TABLE_NAME} SET quantity = ?, sold = ?, sold_date = ?, sold_quantity = ? WHERE id = ?",
                    (new_qty, is_sold, sold_date, new_sold_qty, item_id)
                )
                conn.commit()

    def mark_as_available(self, item_id: int):
        """Mark an item as available (not sold)."""
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE {self.TABLE_NAME} SET sold = 0, sold_date = NULL WHERE id = ?",
                (item_id,)
            )
            conn.commit()

    def delete_item(self, item_id: int):
        """Delete a stock item."""
        with self.get_connection() as conn:
            conn.execute(f"DELETE FROM {self.TABLE_NAME} WHERE id = ?", (item_id,))
            conn.commit()

    def get_categories(self):
        """Get all unique categories."""
        with self.get_connection() as conn:
            cursor = conn.execute(f"SELECT DISTINCT category FROM {self.TABLE_NAME} ORDER BY category")
            return [row[0] for row in cursor.fetchall()]

    def get_stock_summary(self):
        """Get summary statistics for available stock."""
        with self.get_connection() as conn:
            cursor = conn.execute(f"""
                SELECT
                    COUNT(*) as total_items,
                    SUM(quantity) as total_quantity,
                    SUM(price * quantity) as total_value
                FROM {self.TABLE_NAME} WHERE sold = 0
            """)
            return cursor.fetchone()

    def get_revenue_summary(self):
        """Get revenue statistics from sold items."""
        with self.get_connection() as conn:
            cursor = conn.execute(f"""
                SELECT
                    COUNT(*) as sold_items,
                    SUM(sold_quantity) as total_sold,
                    SUM(price * sold_quantity) as total_revenue
                FROM {self.TABLE_NAME} WHERE sold_quantity > 0
            """)
            return cursor.fetchone()

    def get_revenue_by_category(self):
        """Get revenue breakdown by category."""
        with self.get_connection() as conn:
            cursor = conn.execute(f"""
                SELECT category, SUM(price * sold_quantity) as revenue
                FROM {self.TABLE_NAME} WHERE sold_quantity > 0
                GROUP BY category
                ORDER BY revenue DESC
            """)
            return cursor.fetchall()

    def get_revenue_by_date(self, days: int = 30):
        """Get revenue by date for the last N days."""
        with self.get_connection() as conn:
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            cursor = conn.execute(f"""
                SELECT sold_date, SUM(price * sold_quantity) as revenue
                FROM {self.TABLE_NAME}
                WHERE sold_date IS NOT NULL AND sold_date >= ?
                GROUP BY sold_date
                ORDER BY sold_date
            """, (start_date,))
            return cursor.fetchall()

    def get_stock_by_category(self):
        """Get stock count by category."""
        with self.get_connection() as conn:
            cursor = conn.execute(f"""
                SELECT category, COUNT(*) as count, SUM(quantity) as total_qty
                FROM {self.TABLE_NAME} WHERE sold = 0
                GROUP BY category
                ORDER BY count DESC
            """)
            return cursor.fetchall()

    def get_sales_by_condition(self):
        """Get sales breakdown by item condition."""
        with self.get_connection() as conn:
            cursor = conn.execute(f"""
                SELECT condition, SUM(sold_quantity) as sold, SUM(price * sold_quantity) as revenue
                FROM {self.TABLE_NAME} WHERE sold_quantity > 0
                GROUP BY condition
                ORDER BY revenue DESC
            """)
            return cursor.fetchall()
