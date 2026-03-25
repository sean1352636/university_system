"""Butchers Shop Core Services Module

Provides business logic for butchers shop operations including
products, orders, inventory, and transaction management.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

from education_system.university_system.infrastructure.database.db import get_db_connection, transaction

logger = logging.getLogger(__name__)

# Product categories
MEAT_CATEGORIES = {
    'beef': 'Beef',
    'pork': 'Pork',
    'lamb': 'Lamb',
    'chicken': 'Chicken',
    'turkey': 'Turkey',
    'duck': 'Duck',
    'game': 'Game',
    'sausages': 'Sausages',
    'mince': 'Mince',
    'deli': 'Deli Meats',
    'prepared': 'Prepared Meals',
    'specialty': 'Specialty Items'
}

# Unit types
UNIT_TYPES = ['kg', 'g', 'lb', 'oz', 'each', 'pack']

# Order statuses
ORDER_STATUSES = ['pending', 'processing', 'ready', 'collected', 'cancelled']

def init_butcher_db():
    """Initialize butcher shop database tables"""
    with transaction() as conn:
        # Products now use unified 'products' table with source_type='butcher'

        # Orders now use unified 'orders' table with source_type='butcher'

        # Order items now use unified 'order_items' table with source_type='butcher'

        # Butcher transactions now use unified 'transactions' table with source_type='butcher'

        # Inventory log table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS butcher_inventory_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                change_type TEXT NOT NULL,
                quantity_change DECIMAL(10,2) NOT NULL,
                previous_quantity DECIMAL(10,2),
                new_quantity DECIMAL(10,2),
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                FOREIGN KEY (product_id) REFERENCES products(source_product_id)
            )
        ''')

        # Supplier orders table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS butcher_supplier_orders (
                supplier_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_name TEXT NOT NULL,
                order_date TEXT NOT NULL,
                expected_delivery TEXT,
                actual_delivery TEXT,
                status TEXT DEFAULT 'pending',
                total_cost DECIMAL(10,2),
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT
            )
        ''')

        logger.info("Butcher shop database tables initialized successfully")

class ProductManager:
    """Manages butcher shop products"""

    @staticmethod
    def add_product(name: str, category: str, price_per_unit: float,
                   unit_type: str = 'kg', description: str = None,
                   stock_quantity: float = 0, origin: str = None,
                   storage_temp: str = None, shelf_life_days: int = None) -> int:
        """Add a new product to the inventory"""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO products
                (source_type, name, category, description, price_per_unit, unit_type,
                 stock_quantity, origin, storage_temp, shelf_life_days)
                VALUES ('butcher', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, category, description, price_per_unit, unit_type,
                  stock_quantity, origin, storage_temp, shelf_life_days))
            return cursor.lastrowid

    @staticmethod
    def get_product(product_id: int) -> Optional[Dict]:
        """Get product by ID"""
        with get_db_connection() as conn:
            row = conn.execute(
                'SELECT * FROM products WHERE source_product_id = ? AND source_type = ?',
                (product_id, 'butcher')
            ).fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def get_all_products(category: str = None, available_only: bool = True) -> List[Dict]:
        """Get all products, optionally filtered by category"""
        with get_db_connection() as conn:
            query = "SELECT * FROM products WHERE source_type = 'butcher'"
            params = []

            if category:
                query += ' AND category = ?'
                params.append(category)

            if available_only:
                query += ' AND is_available = 1'

            query += ' ORDER BY category, name'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_product(product_id: int, **kwargs) -> bool:
        """Update product details"""
        allowed_fields = ['name', 'category', 'description', 'price_per_unit',
                         'unit_type', 'stock_quantity', 'min_stock_level',
                         'is_available', 'origin', 'storage_temp', 'shelf_life_days']

        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False

        updates['updated_at'] = datetime.now().isoformat()

        set_clause = ', '.join(f'{k} = ?' for k in updates.keys())
        values = list(updates.values()) + [product_id]

        with transaction() as conn:
            conn.execute(
                f"UPDATE products SET {set_clause} WHERE source_product_id = ? AND source_type = 'butcher'",
                values
            )
            return True

    @staticmethod
    def update_stock(product_id: int, quantity_change: float, reason: str,
                    user_id: str = None) -> bool:
        """Update product stock and log the change"""
        with transaction() as conn:
            # Get current stock
            row = conn.execute(
                "SELECT stock_quantity FROM products WHERE source_product_id = ? AND source_type = 'butcher'",
                (product_id,)
            ).fetchone()

            if not row:
                return False

            previous_qty = row['stock_quantity']
            new_qty = previous_qty + quantity_change

            # Update stock
            conn.execute(
                "UPDATE products SET stock_quantity = ?, updated_at = ? WHERE source_product_id = ? AND source_type = 'butcher'",
                (new_qty, datetime.now().isoformat(), product_id)
            )

            # Log the change
            change_type = 'addition' if quantity_change > 0 else 'reduction'
            conn.execute('''
                INSERT INTO butcher_inventory_log
                (product_id, change_type, quantity_change, previous_quantity,
                 new_quantity, reason, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (product_id, change_type, quantity_change, previous_qty,
                  new_qty, reason, user_id))

            return True

    @staticmethod
    def get_low_stock_products() -> List[Dict]:
        """Get products with stock below minimum level"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM products
                WHERE source_type = 'butcher' AND stock_quantity <= min_stock_level AND is_available = 1
                ORDER BY stock_quantity ASC
            ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def search_products(search_term: str) -> List[Dict]:
        """Search products by name or description"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM products
                WHERE source_type = 'butcher' AND (name LIKE ? OR description LIKE ? OR category LIKE ?)
                ORDER BY name
            ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%')).fetchall()
            return [dict(row) for row in rows]

class OrderManager:
    """Manages customer orders"""

    @staticmethod
    def generate_order_number() -> str:
        """Generate unique order number"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        with get_db_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE source_type = 'butcher' AND DATE(created_at) = DATE(?)",
                (datetime.now().isoformat(),)
            ).fetchone()[0]
        return f"BTR-{timestamp}-{count + 1:03d}"

    @staticmethod
    def create_order(customer_id: str, customer_name: str, customer_email: str = None,
                    customer_phone: str = None, order_type: str = 'counter',
                    pickup_date: str = None, pickup_time: str = None,
                    special_instructions: str = None, processed_by: str = None) -> Tuple[int, str]:
        """Create a new order"""
        order_number = OrderManager.generate_order_number()

        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO orders
                (source_type, order_number, customer_id, customer_name, customer_email, customer_phone,
                 order_type, pickup_date, pickup_time, special_instructions, processed_by)
                VALUES ('butcher', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (order_number, customer_id, customer_name, customer_email, customer_phone,
                  order_type, pickup_date, pickup_time, special_instructions, processed_by))
            return cursor.lastrowid, order_number

    @staticmethod
    def add_order_item(order_id: int, product_id: int, quantity: float,
                      special_cut: str = None, notes: str = None) -> int:
        """Add item to an order"""
        with transaction() as conn:
            # Get product details
            product = conn.execute(
                "SELECT name, price_per_unit, unit_type FROM products WHERE source_product_id = ? AND source_type = 'butcher'",
                (product_id,)
            ).fetchone()

            if not product:
                raise ValueError(f"Product {product_id} not found")

            total_price = product['price_per_unit'] * quantity

            cursor = conn.execute('''
                INSERT INTO order_items
                (source_type, order_id, product_id, item_name, quantity, unit_type,
                 unit_price, subtotal, special_cut, notes)
                VALUES ('butcher', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (order_id, product_id, product['name'], quantity, product['unit_type'],
                  product['price_per_unit'], total_price, special_cut, notes))

            # Update order total
            conn.execute('''
                UPDATE orders
                SET total_amount = (SELECT SUM(subtotal) FROM order_items WHERE order_id = ? AND source_type = 'butcher'),
                    updated_at = ?
                WHERE order_id = ?
            ''', (order_id, datetime.now().isoformat(), order_id))

            return cursor.lastrowid

    @staticmethod
    def get_order(order_id: int) -> Optional[Dict]:
        """Get order by ID with items"""
        with get_db_connection() as conn:
            order = conn.execute(
                "SELECT * FROM orders WHERE order_id = ? AND source_type = 'butcher'",
                (order_id,)
            ).fetchone()

            if not order:
                return None

            order_dict = dict(order)

            items = conn.execute(
                "SELECT * FROM order_items WHERE order_id = ? AND source_type = 'butcher'",
                (order_id,)
            ).fetchall()
            order_dict['items'] = [dict(item) for item in items]

            return order_dict

    @staticmethod
    def get_order_by_number(order_number: str) -> Optional[Dict]:
        """Get order by order number"""
        with get_db_connection() as conn:
            order = conn.execute(
                "SELECT * FROM orders WHERE order_number = ? AND source_type = 'butcher'",
                (order_number,)
            ).fetchone()

            if order:
                return OrderManager.get_order(order['order_id'])
            return None

    @staticmethod
    def update_order_status(order_id: int, status: str, user_id: str = None) -> bool:
        """Update order status"""
        if status not in ORDER_STATUSES:
            return False

        with transaction() as conn:
            conn.execute('''
                UPDATE orders
                SET order_status = ?, updated_at = ?, processed_by = ?
                WHERE order_id = ? AND source_type = 'butcher'
            ''', (status, datetime.now().isoformat(), user_id, order_id))
            return True

    @staticmethod
    def update_payment_status(order_id: int, payment_status: str, payment_method: str = None) -> bool:
        """Update order payment status"""
        with transaction() as conn:
            conn.execute('''
                UPDATE orders
                SET payment_status = ?, payment_method = ?, updated_at = ?
                WHERE order_id = ? AND source_type = 'butcher'
            ''', (payment_status, payment_method, datetime.now().isoformat(), order_id))
            return True

    @staticmethod
    def get_orders_by_status(status: str) -> List[Dict]:
        """Get orders by status"""
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM orders WHERE order_status = ? AND source_type = 'butcher' ORDER BY created_at DESC",
                (status,)
            ).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_customer_orders(customer_id: str) -> List[Dict]:
        """Get all orders for a customer"""
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM orders WHERE customer_id = ? AND source_type = 'butcher' ORDER BY created_at DESC",
                (customer_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_todays_orders() -> List[Dict]:
        """Get all orders for today"""
        with get_db_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM orders
                WHERE source_type = 'butcher' AND DATE(created_at) = DATE('now', 'localtime')
                ORDER BY created_at DESC
            ''').fetchall()
            return [dict(row) for row in rows]

class TransactionManager:
    """Manages financial transactions"""

    @staticmethod
    def process_payment(order_id: int, amount: float, payment_method: str,
                       customer_id: str, reference_number: str = None,
                       processed_by: str = None) -> int:
        """Process payment for an order"""
        with transaction() as conn:
            # Record transaction
            cursor = conn.execute('''
                INSERT INTO transactions
                (source_type, reference_id, reference_type, customer_id, amount, payment_method, reference_number, processed_by)
                VALUES ('butcher', ?, 'order', ?, ?, ?, ?, ?)
            ''', (order_id, customer_id, amount, payment_method, reference_number, processed_by))

            transaction_id = cursor.lastrowid

            # Update order payment status
            conn.execute('''
                UPDATE orders
                SET payment_status = 'paid', payment_method = ?, payment_reference = ?, updated_at = ?
                WHERE order_id = ? AND source_type = 'butcher'
            ''', (payment_method, reference_number, datetime.now().isoformat(), order_id))

            # Record in main finance system
            try:
                conn.execute('''
                    INSERT INTO payments
                    (student_id, amount, payment_method, payment_date, status, notes, created_by)
                    VALUES (?, ?, ?, ?, 'completed', 'Butcher Shop Purchase', ?)
                ''', (customer_id, amount, payment_method, datetime.now().isoformat(), processed_by))
            except Exception as e:
                logger.warning(f"Could not record to main finance system: {e}")

            return transaction_id

    @staticmethod
    def process_refund(order_id: int, amount: float, reason: str,
                      customer_id: str, processed_by: str = None) -> int:
        """Process refund for an order"""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO transactions
                (source_type, reference_id, reference_type, customer_id, amount, payment_method, transaction_type,
                 reference_number, processed_by)
                VALUES ('butcher', ?, 'order', ?, ?, 'refund', 'refund', ?, ?)
            ''', (order_id, customer_id, -amount, reason, processed_by))

            return cursor.lastrowid

    @staticmethod
    def get_transaction(transaction_id: int) -> Optional[Dict]:
        """Get transaction by ID"""
        with get_db_connection() as conn:
            row = conn.execute(
                'SELECT * FROM transactions WHERE transaction_id = ? AND source_type = ?',
                (transaction_id, 'butcher')
            ).fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def mark_receipt_sent(transaction_id: int) -> bool:
        """Mark receipt as sent"""
        with transaction() as conn:
            conn.execute(
                'UPDATE transactions SET receipt_sent = 1 WHERE transaction_id = ? AND source_type = \'butcher\'',
                (transaction_id,)
            )
            return True

    @staticmethod
    def get_daily_sales(date: str = None) -> Dict:
        """Get sales summary for a day"""
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')

        with get_db_connection() as conn:
            # Get from orders table (paid orders)
            row = conn.execute('''
                SELECT
                    COUNT(*) as transaction_count,
                    SUM(total_amount) as total_sales
                FROM orders
                WHERE source_type = 'butcher' AND DATE(created_at) = ? AND payment_status = 'paid'
            ''', (date,)).fetchone()

            # Get refunds separately
            refunds = conn.execute('''
                SELECT SUM(total_amount) as total_refunds
                FROM orders
                WHERE source_type = 'butcher' AND DATE(created_at) = ? AND payment_status = 'refunded'
            ''', (date,)).fetchone()

            total_sales = row['total_sales'] or 0
            total_refunds = refunds['total_refunds'] or 0 if refunds else 0

            return {
                'date': date,
                'transaction_count': row['transaction_count'] or 0,
                'total_sales': total_sales,
                'total_refunds': total_refunds,
                'net_sales': total_sales - total_refunds
            }

class ReportManager:
    """Generates reports for the butcher shop"""

    @staticmethod
    def generate_sales_report(start_date: str, end_date: str) -> Dict:
        """Generate sales report for date range"""
        with get_db_connection() as conn:
            # Sales summary from orders table
            summary = conn.execute('''
                SELECT
                    COUNT(*) as total_orders,
                    SUM(total_amount) as total_revenue,
                    AVG(total_amount) as avg_order_value
                FROM orders
                WHERE source_type = 'butcher' AND DATE(created_at) BETWEEN ? AND ? AND payment_status = 'paid'
            ''', (start_date, end_date)).fetchone()

            # Sales by category
            by_category = conn.execute('''
                SELECT
                    p.category,
                    SUM(oi.quantity) as total_quantity,
                    SUM(oi.subtotal) as total_sales
                FROM order_items oi
                JOIN products p ON oi.product_id = p.source_product_id AND p.source_type = 'butcher'
                JOIN orders o ON oi.order_id = o.order_id AND o.source_type = 'butcher'
                WHERE oi.source_type = 'butcher' AND DATE(o.created_at) BETWEEN ? AND ?
                    AND o.payment_status = 'paid'
                GROUP BY p.category
                ORDER BY total_sales DESC
            ''', (start_date, end_date)).fetchall()

            # Top selling products
            top_products = conn.execute('''
                SELECT
                    oi.item_name as product_name,
                    SUM(oi.quantity) as total_quantity,
                    SUM(oi.subtotal) as total_sales
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id AND o.source_type = 'butcher'
                WHERE oi.source_type = 'butcher' AND DATE(o.created_at) BETWEEN ? AND ?
                    AND o.payment_status = 'paid'
                GROUP BY oi.product_id, oi.item_name
                ORDER BY total_quantity DESC
                LIMIT 10
            ''', (start_date, end_date)).fetchall()

            return {
                'period': {'start': start_date, 'end': end_date},
                'summary': dict(summary) if summary else {},
                'by_category': [dict(row) for row in by_category],
                'top_products': [dict(row) for row in top_products],
                'generated_at': datetime.now().isoformat()
            }

    @staticmethod
    def generate_inventory_report() -> Dict:
        """Generate current inventory report"""
        with get_db_connection() as conn:
            # All products with stock info
            products = conn.execute('''
                SELECT
                    source_product_id as product_id, name, category, stock_quantity,
                    min_stock_level, unit_type, price_per_unit,
                    (stock_quantity * price_per_unit) as stock_value
                FROM products
                WHERE source_type = 'butcher' AND is_available = 1
                ORDER BY category, name
            ''').fetchall()

            # Summary
            summary = conn.execute('''
                SELECT
                    COUNT(*) as total_products,
                    SUM(stock_quantity * price_per_unit) as total_stock_value,
                    COUNT(CASE WHEN stock_quantity <= min_stock_level THEN 1 END) as low_stock_count
                FROM products
                WHERE source_type = 'butcher' AND is_available = 1
            ''').fetchone()

            return {
                'products': [dict(row) for row in products],
                'summary': dict(summary) if summary else {},
                'generated_at': datetime.now().isoformat()
            }

    @staticmethod
    def generate_admin_report() -> str:
        """Generate comprehensive admin report as text"""
        today = datetime.now().strftime('%Y-%m-%d')
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        daily_sales = TransactionManager.get_daily_sales(today) or {}
        weekly_report = ReportManager.generate_sales_report(week_ago, today) or {'summary': {}, 'top_products': []}
        inventory = ReportManager.generate_inventory_report() or {'summary': {}}

        # Safe get values with defaults
        transaction_count = daily_sales.get('transaction_count', 0) or 0
        total_sales = daily_sales.get('total_sales', 0) or 0
        total_refunds = daily_sales.get('total_refunds', 0) or 0
        net_sales = daily_sales.get('net_sales', 0) or 0

        summary = weekly_report.get('summary', {}) or {}
        total_orders = summary.get('total_orders', 0) or 0
        total_revenue = summary.get('total_revenue', 0) or 0
        avg_order_value = summary.get('avg_order_value', 0) or 0

        inv_summary = inventory.get('summary', {}) or {}
        total_products = inv_summary.get('total_products', 0) or 0
        total_stock_value = inv_summary.get('total_stock_value', 0) or 0
        low_stock_count = inv_summary.get('low_stock_count', 0) or 0

        report = f"""
BUTCHER SHOP ADMIN REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'=' * 50}

TODAY'S SALES ({today})
{'-' * 30}
Transactions: {transaction_count}
Total Sales: £{total_sales:.2f}
Refunds: £{total_refunds:.2f}
Net Sales: £{net_sales:.2f}

WEEKLY SUMMARY ({week_ago} to {today})
{'-' * 30}
Total Orders: {total_orders}
Total Revenue: £{total_revenue:.2f}
Average Order: £{avg_order_value:.2f}

TOP SELLING PRODUCTS
{'-' * 30}
"""
        top_products = weekly_report.get('top_products', []) or []
        if top_products:
            for i, product in enumerate(top_products[:5], 1):
                qty = product.get('total_quantity', 0) or 0
                sales = product.get('total_sales', 0) or 0
                name = product.get('product_name', 'Unknown')
                report += f"{i}. {name}: {qty:.1f} units (£{sales:.2f})\n"
        else:
            report += "No sales data available\n"

        report += f"""
INVENTORY STATUS
{'-' * 30}
Total Products: {total_products}
Stock Value: £{total_stock_value:.2f}
Low Stock Items: {low_stock_count}

{'=' * 50}
End of Report
"""
        return report

def launch_butcher_gui(parent=None, auth=None):
    """Launch the Butcher Shop GUI"""
    from education_system.university_system.modules.domain.butcher.gui.butcher_gui import ButcherGUI
    return ButcherGUI(parent, auth)
