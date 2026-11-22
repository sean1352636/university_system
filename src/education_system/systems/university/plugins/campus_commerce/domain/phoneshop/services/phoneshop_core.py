"""Phone Shop Core Service Module"""

from education_system.systems.university.infrastructure.database.db import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from education_system import paths
from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
    process_student_finance_account_payment,
    record_payment_to_finance,
    record_refund_to_finance,
    top_up_student_finance_account,
)

logger = logging.getLogger(__name__)

# Finance posting identity shared by the GUI and every CLI (CLAUDE.md: post to
# Finance from the domain service, never from an interface).
FINANCE_SOURCE = 'PhoneShop'
FINANCE_SALE_DESCRIPTION = 'Phone Shop purchase'
FINANCE_REFUND_DESCRIPTION = 'Phone Shop Purchase Refund'
_STUDENT_ACCOUNT_METHODS = {'finance_account', 'student_account', 'student account'}


def is_student_account_method(payment_method: Optional[str]) -> bool:
    """True when a payment/refund method means the student's finance account."""
    return (payment_method or '').strip().lower() in _STUDENT_ACCOUNT_METHODS


def post_sale_to_finance(order_id: int, customer_id: Optional[str], amount: float,
                         payment_method: Optional[str], processed_by: Optional[str] = None,
                         order_number: Optional[str] = None) -> Optional[int]:
    """Post a completed phone shop sale to Finance. Never raises.

    Student-account sales are debited from the finance account (which records
    its own payments row); every other method is recorded as a payment. A
    posting failure is logged and the local sale is left intact.
    """
    try:
        ref = order_number
        if not ref:
            order = OrderManager.get_order(order_id)
            ref = (order or {}).get('order_number') or str(order_id)
        if is_student_account_method(payment_method):
            result = process_student_finance_account_payment(
                student_id=customer_id,
                amount=amount,
                description=FINANCE_SALE_DESCRIPTION,
                transaction_source=FINANCE_SOURCE,
                transaction_ref=ref,
                processed_by=processed_by or 'System',
            )
            if not result.get('success'):
                logger.warning("Phone Shop order %s: student account payment not posted: %s",
                               ref, result.get('message'))
                return None
            return result.get('payment_id')
        payment_id = record_payment_to_finance(
            student_id=customer_id or 'EXTERNAL',
            amount=amount,
            payment_method=payment_method or 'cash',
            transaction_source=FINANCE_SOURCE,
            transaction_ref=ref,
            notes="Phone Shop purchase",
            created_by=processed_by,
        )
        if payment_id is None:
            logger.warning("Phone Shop order %s: payment not posted to finance", ref)
        return payment_id
    except Exception:
        logger.exception("Phone Shop order %s: finance posting failed", order_id)
        return None


def post_refund_to_finance(order_id: int, customer_id: Optional[str], amount: float,
                           refund_method: Optional[str], reason: Optional[str] = None,
                           processed_by: Optional[str] = None, order_number: Optional[str] = None,
                           transaction_id: Optional[int] = None) -> Dict[str, Any]:
    """Post a phone shop refund to Finance. Never raises.

    Returns ``{'refund_id', 'refund_ref', 'credited'}``; ``credited`` is True
    when a student-account refund was credited back to the account.
    """
    outcome: Dict[str, Any] = {'refund_id': None, 'refund_ref': None, 'credited': False}
    try:
        ref = order_number
        if not ref:
            order = OrderManager.get_order(order_id)
            ref = (order or {}).get('order_number') or str(order_id)
        transaction_ref = f"{ref}-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        refund_id = record_refund_to_finance(
            student_id=customer_id or 'EXTERNAL',
            refund_amount=amount,
            original_payment_id=None,
            refund_reason=reason or FINANCE_REFUND_DESCRIPTION,
            refund_type='order',
            transaction_source=FINANCE_SOURCE,
            transaction_ref=transaction_ref,
            refund_method=refund_method or 'original_payment_method',
            requested_by=processed_by,
            notes=f'phone_shop_transaction_{transaction_id}' if transaction_id else None,
        )
        if refund_id is None:
            logger.warning("Phone Shop order %s: refund not posted to finance", ref)
        outcome['refund_id'] = refund_id
        outcome['refund_ref'] = f"{FINANCE_SOURCE.upper()}-{transaction_ref}"
        if is_student_account_method(refund_method) and customer_id:
            credit = top_up_student_finance_account(
                student_id=customer_id,
                amount=amount,
                payment_method='refund',
                processed_by=processed_by or 'System',
                description=FINANCE_REFUND_DESCRIPTION,
            )
            outcome['credited'] = bool(credit.get('success'))
            if not outcome['credited']:
                logger.warning("Phone Shop order %s: student account not credited: %s",
                               ref, credit.get('message'))
    except Exception:
        logger.exception("Phone Shop order %s: finance refund posting failed", order_id)
    return outcome

# Constants
PHONE_CATEGORIES = ['Smartphone', 'Feature Phone', 'Tablet', 'Smartwatch', 'Accessories', 'Cases', 'Chargers', 'Headphones']
ORDER_STATUSES = ['pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded']
PAYMENT_STATUSES = ['pending', 'completed', 'failed', 'refunded']

def get_phoneshop_db_path():
    """Get the phone shop database path"""
    return str(paths.UNIVERSITY_DEFAULT_DB_PATH)

def init_phoneshop_db():
    """Initialize the phone shop database tables"""
    conn = sqlite3.connect(get_phoneshop_db_path())
    try:
        cursor = conn.cursor()

        # Products table (unified)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL DEFAULT 'phone_shop',
            source_product_id TEXT,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            brand TEXT,
            model TEXT,
            category TEXT NOT NULL,
            description TEXT,
            price DECIMAL(10,2) NOT NULL,
            cost_price DECIMAL(10,2),
            stock_quantity INTEGER DEFAULT 0,
            min_stock_level INTEGER DEFAULT 5,
            specifications TEXT,
            warranty_months INTEGER DEFAULT 12,
            is_active BOOLEAN DEFAULT 1,
            image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Orders table (unified)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL DEFAULT 'phone_shop',
            source_order_id TEXT,
            order_number TEXT UNIQUE NOT NULL,
            customer_id TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            customer_email TEXT,
            customer_phone TEXT,
            shipping_address TEXT,
            subtotal DECIMAL(10,2) NOT NULL,
            tax_amount DECIMAL(10,2) DEFAULT 0,
            shipping_fee DECIMAL(10,2) DEFAULT 0,
            discount_amount DECIMAL(10,2) DEFAULT 0,
            total_amount DECIMAL(10,2) NOT NULL,
            order_status TEXT DEFAULT 'pending',
            payment_status TEXT DEFAULT 'pending',
            payment_method TEXT,
            notes TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Order items table (unified)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL DEFAULT 'phone_shop',
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price DECIMAL(10,2) NOT NULL,
            subtotal DECIMAL(10,2) NOT NULL,
            warranty_id TEXT,
            serial_number TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        )
        ''')

        # Phone shop transactions now use unified 'transactions' table with source_type='phone_shop'

        # Warranties table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS phoneshop_warranties (
            warranty_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_item_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            serial_number TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            warranty_type TEXT DEFAULT 'standard',
            status TEXT DEFAULT 'active',
            customer_id TEXT NOT NULL,
            FOREIGN KEY (order_item_id) REFERENCES order_items(item_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        )
        ''')

        conn.commit()
        logger.info("Phone shop database initialized")
    finally:
        conn.close()

class ProductManager:
    """Manage phone shop products"""

    @staticmethod
    def add_product(sku: str, name: str, category: str, price: float, **kwargs) -> Optional[int]:
        """Add a new product"""
        conn = sqlite3.connect(get_phoneshop_db_path())
        cursor = conn.cursor()

        try:
            cursor.execute('''
            INSERT INTO products
            (source_type, sku, name, brand, model, category, description, price, cost_price,
             stock_quantity, min_stock_level, specifications, warranty_months, image_url)
            VALUES ('phone_shop', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                sku, name, kwargs.get('brand'), kwargs.get('model'), category,
                kwargs.get('description'), price, kwargs.get('cost_price'),
                kwargs.get('stock_quantity', 0), kwargs.get('min_stock_level', 5),
                kwargs.get('specifications'), kwargs.get('warranty_months', 12),
                kwargs.get('image_url')
            ))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            logger.error(f"Failed to add product: {e}")
            return None
        finally:
            conn.close()

    @staticmethod
    def get_product(product_id: int) -> Optional[Dict]:
        """Get product by ID"""
        conn = sqlite3.connect(get_phoneshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM products WHERE source_type = ? AND product_id = ?', ('phone_shop', product_id,))
            row = cursor.fetchone()

            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def get_all_products() -> List[Dict]:
        """Get all products"""
        conn = sqlite3.connect(get_phoneshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM products WHERE source_type = ? AND is_active = 1 ORDER BY name', ('phone_shop',))
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def get_products_by_category(category: str) -> List[Dict]:
        """Get products by category"""
        conn = sqlite3.connect(get_phoneshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                'SELECT * FROM products WHERE source_type = ? AND category = ? AND is_active = 1 ORDER BY name',
                ('phone_shop', category,)
            )
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def update_product(product_id: int, **kwargs) -> bool:
        """Update product"""
        conn = sqlite3.connect(get_phoneshop_db_path())
        try:
            cursor = conn.cursor()

            updates = []
            values = []
            for key, value in kwargs.items():
                if value is not None:
                    updates.append(f"{key} = ?")
                    values.append(value)

            if not updates:
                return False

            updates.append("updated_at = ?")
            values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            values.append(product_id)

            cursor.execute(
                "UPDATE products SET " + ", ".join(updates) + " WHERE source_type = 'phone_shop' AND product_id = ?",
                values)

            conn.commit()
            success = cursor.rowcount > 0
            return success
        finally:
            conn.close()

    @staticmethod
    def update_stock(product_id: int, quantity_change: int) -> bool:
        """Update product stock"""
        conn = sqlite3.connect(get_phoneshop_db_path())
        try:
            cursor = conn.cursor()

            cursor.execute('''
            UPDATE products
            SET stock_quantity = stock_quantity + ?, updated_at = ?
            WHERE source_type = 'phone_shop' AND product_id = ?
            ''', (quantity_change, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), product_id))

            conn.commit()
            success = cursor.rowcount > 0
            return success
        finally:
            conn.close()

    @staticmethod
    def get_low_stock_products() -> List[Dict]:
        """Get products with low stock"""
        conn = sqlite3.connect(get_phoneshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
            SELECT * FROM products
            WHERE source_type = 'phone_shop' AND stock_quantity <= min_stock_level AND is_active = 1
            ORDER BY stock_quantity
            ''')
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def search_products(query: str) -> List[Dict]:
        """Search products"""
        conn = sqlite3.connect(get_phoneshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
            SELECT * FROM products
            WHERE source_type = 'phone_shop' AND (name LIKE ? OR brand LIKE ? OR model LIKE ? OR sku LIKE ?) AND is_active = 1
            ORDER BY name
            ''', (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%'))
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

class OrderManager:
    """Manage phone shop orders"""

    @staticmethod
    def _generate_order_number() -> str:
        """Generate unique order number"""
        return f"PHO-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    @staticmethod
    def create_order(customer_id: str, customer_name: str, items: List[Dict], **kwargs) -> Optional[int]:
        """Create a new order"""
        conn = sqlite3.connect(get_phoneshop_db_path())
        cursor = conn.cursor()

        try:
            # Calculate totals
            subtotal = sum(item['quantity'] * item['unit_price'] for item in items)
            tax_amount = kwargs.get('tax_amount', subtotal * 0.20)  # 20% VAT
            shipping_fee = kwargs.get('shipping_fee', 0)
            discount_amount = kwargs.get('discount_amount', 0)
            total_amount = subtotal + tax_amount + shipping_fee - discount_amount

            order_number = OrderManager._generate_order_number()

            cursor.execute('''
            INSERT INTO orders
            (source_type, order_number, customer_id, customer_name, customer_email, customer_phone,
             shipping_address, subtotal, tax_amount, shipping_fee, discount_amount,
             total_amount, payment_method, notes, created_by)
            VALUES ('phone_shop', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                order_number, customer_id, customer_name,
                kwargs.get('customer_email'), kwargs.get('customer_phone'),
                kwargs.get('shipping_address'), subtotal, tax_amount, shipping_fee,
                discount_amount, total_amount, kwargs.get('payment_method'),
                kwargs.get('notes'), kwargs.get('created_by')
            ))

            order_id = cursor.lastrowid

            # Add order items and update stock
            for item in items:
                cursor.execute('''
                INSERT INTO order_items
                (source_type, order_id, product_id, item_name, quantity, unit_price, subtotal, serial_number)
                VALUES ('phone_shop', ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    order_id, item['product_id'], item['product_name'],
                    item['quantity'], item['unit_price'],
                    item['quantity'] * item['unit_price'], item.get('serial_number')
                ))

                # Reduce stock
                cursor.execute('''
                UPDATE products
                SET stock_quantity = stock_quantity - ?
                WHERE source_type = 'phone_shop' AND product_id = ?
                ''', (item['quantity'], item['product_id']))

            conn.commit()
            return order_id
        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    @staticmethod
    def get_order(order_id: int) -> Optional[Dict]:
        """Get order by ID"""
        conn = sqlite3.connect(get_phoneshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM orders WHERE source_type = ? AND order_id = ?', ('phone_shop', order_id,))
            row = cursor.fetchone()

            if row:
                order = dict(row)
                cursor.execute('SELECT * FROM order_items WHERE source_type = ? AND order_id = ?', ('phone_shop', order_id,))
                order['items'] = [dict(item) for item in cursor.fetchall()]
            else:
                order = None

            return order
        finally:
            conn.close()

    @staticmethod
    def get_orders_by_status(status: str) -> List[Dict]:
        """Get orders by status"""
        conn = sqlite3.connect(get_phoneshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
            SELECT * FROM orders WHERE source_type = 'phone_shop' AND order_status = ? ORDER BY created_at DESC
            ''', (status,))
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def get_customer_orders(customer_id: str) -> List[Dict]:
        """Get orders for a customer"""
        conn = sqlite3.connect(get_phoneshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
            SELECT * FROM orders WHERE source_type = 'phone_shop' AND customer_id = ? ORDER BY created_at DESC
            ''', (customer_id,))
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def update_order_status(order_id: int, status: str) -> bool:
        """Update order status"""
        conn = sqlite3.connect(get_phoneshop_db_path())
        try:
            cursor = conn.cursor()

            cursor.execute('''
            UPDATE orders SET order_status = ?, updated_at = ? WHERE source_type = 'phone_shop' AND order_id = ?
            ''', (status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), order_id))

            conn.commit()
            success = cursor.rowcount > 0
            return success
        finally:
            conn.close()

    @staticmethod
    def cancel_order(order_id: int, reason: str = None) -> bool:
        """Cancel an order and restore stock"""
        conn = sqlite3.connect(get_phoneshop_db_path())
        cursor = conn.cursor()

        try:
            # Get order items to restore stock
            cursor.execute('SELECT product_id, quantity FROM order_items WHERE source_type = ? AND order_id = ?', ('phone_shop', order_id,))
            items = cursor.fetchall()

            # Restore stock
            for product_id, quantity in items:
                cursor.execute('''
                UPDATE products SET stock_quantity = stock_quantity + ? WHERE source_type = 'phone_shop' AND product_id = ?
                ''', (quantity, product_id))

            # Update order status
            cursor.execute('''
            UPDATE orders SET order_status = 'cancelled', notes = ?, updated_at = ? WHERE source_type = 'phone_shop' AND order_id = ?
            ''', (reason, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), order_id))

            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

class TransactionManager:
    """Manage phone shop transactions"""

    @staticmethod
    def record_payment(order_id: int, customer_id: str, amount: float, payment_method: str, **kwargs) -> Optional[int]:
        """Record a payment transaction"""
        conn = sqlite3.connect(get_phoneshop_db_path())
        cursor = conn.cursor()

        try:
            cursor.execute('''
            INSERT INTO transactions
            (source_type, reference_id, reference_type, customer_id, transaction_type, amount, payment_method, reference_number, processed_by)
            VALUES ('phone_shop', ?, 'order', ?, 'payment', ?, ?, ?, ?)
            ''', (
                order_id, customer_id, amount, payment_method,
                kwargs.get('reference_number'), kwargs.get('processed_by')
            ))

            # Update order payment status
            cursor.execute('''
            UPDATE orders SET payment_status = 'completed', order_status = 'confirmed',
            payment_method = ?, updated_at = ? WHERE source_type = 'phone_shop' AND order_id = ?
            ''', (payment_method, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), order_id))

            conn.commit()
            txn_id = cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to record payment: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

        if kwargs.get('post_to_finance', True):
            post_sale_to_finance(
                order_id, customer_id, amount, payment_method,
                processed_by=kwargs.get('processed_by'),
                order_number=kwargs.get('order_number'),
            )
        return txn_id

    @staticmethod
    def process_refund(order_id: int, amount: float, reason: str = None, **kwargs) -> Optional[int]:
        """Process a refund"""
        conn = sqlite3.connect(get_phoneshop_db_path())
        cursor = conn.cursor()

        try:
            order = OrderManager.get_order(order_id)
            if not order:
                return None

            cursor.execute('''
            INSERT INTO transactions
            (source_type, reference_id, reference_type, customer_id, transaction_type, amount, payment_method, reference_number, processed_by)
            VALUES ('phone_shop', ?, 'order', ?, 'refund', ?, ?, ?, ?)
            ''', (
                order_id, order['customer_id'], -amount, order.get('payment_method'),
                reason, kwargs.get('processed_by')
            ))

            # Update order status
            cursor.execute('''
            UPDATE orders SET payment_status = 'refunded', order_status = 'refunded', updated_at = ?
            WHERE source_type = 'phone_shop' AND order_id = ?
            ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), order_id))

            cursor.execute('''
            UPDATE transactions SET status = 'refunded'
            WHERE source_type = 'phone_shop' AND reference_type = 'order' AND reference_id = ?
              AND transaction_type = 'payment'
            ''', (order_id,))

            conn.commit()
            txn_id = cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to process refund: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

        if kwargs.get('post_to_finance', True):
            post_refund_to_finance(
                order_id, order['customer_id'], amount,
                kwargs.get('refund_method') or order.get('payment_method'),
                reason=reason, processed_by=kwargs.get('processed_by'),
                order_number=order.get('order_number'),
                transaction_id=kwargs.get('transaction_id'),
            )
        return txn_id

    @staticmethod
    def refund_order(order_id: int, amount: float, refund_method: Optional[str],
                     reason: Optional[str] = None, processed_by: Optional[str] = None,
                     transaction_id: Optional[int] = None) -> Dict[str, Any]:
        """Refund an order locally and post it to Finance in one step.

        Used by the GUI refund flows; returns the local transaction id plus the
        finance outcome (``refund_id``, ``refund_ref``, ``credited``).
        """
        order = OrderManager.get_order(order_id)
        if not order:
            return {'success': False, 'message': 'Order not found'}
        txn_id = TransactionManager.process_refund(
            order_id, amount, reason, processed_by=processed_by, post_to_finance=False,
        )
        if not txn_id:
            return {'success': False, 'message': 'Failed to record refund'}
        outcome = post_refund_to_finance(
            order_id, order.get('customer_id'), amount, refund_method,
            reason=reason, processed_by=processed_by,
            order_number=order.get('order_number'), transaction_id=transaction_id,
        )
        return {'success': True, 'transaction_id': txn_id, 'customer_id': order.get('customer_id'), **outcome}

class ReportManager:
    """Generate phone shop reports"""

    @staticmethod
    def get_sales_summary() -> Dict:
        """Get sales summary"""
        conn = sqlite3.connect(get_phoneshop_db_path())
        try:
            cursor = conn.cursor()

            cursor.execute('''
            SELECT
                COUNT(*) as total_orders,
                SUM(CASE WHEN order_status NOT IN ('cancelled', 'refunded') THEN total_amount ELSE 0 END) as total_revenue,
                AVG(CASE WHEN order_status NOT IN ('cancelled', 'refunded') THEN total_amount ELSE NULL END) as avg_order_value,
                SUM(CASE WHEN order_status = 'pending' THEN 1 ELSE 0 END) as pending_orders,
                SUM(CASE WHEN order_status = 'delivered' THEN 1 ELSE 0 END) as completed_orders
            FROM orders WHERE source_type = 'phone_shop'
            ''')
            row = cursor.fetchone()

            return {
                'total_orders': row[0] or 0,
                'total_revenue': row[1] or 0,
                'avg_order_value': row[2] or 0,
                'pending_orders': row[3] or 0,
                'completed_orders': row[4] or 0
            }
        finally:
            conn.close()

    @staticmethod
    def get_inventory_summary() -> Dict:
        """Get inventory summary"""
        conn = sqlite3.connect(get_phoneshop_db_path())
        try:
            cursor = conn.cursor()

            cursor.execute('''
            SELECT
                COUNT(*) as total_products,
                SUM(stock_quantity) as total_stock,
                SUM(stock_quantity * price) as total_value,
                SUM(CASE WHEN stock_quantity <= min_stock_level THEN 1 ELSE 0 END) as low_stock_count
            FROM products WHERE source_type = 'phone_shop' AND is_active = 1
            ''')
            row = cursor.fetchone()

            return {
                'total_products': row[0] or 0,
                'total_stock': row[1] or 0,
                'total_value': row[2] or 0,
                'low_stock_count': row[3] or 0
            }
        finally:
            conn.close()

    @staticmethod
    def get_top_selling_products(limit: int = 10) -> List[Dict]:
        """Get top selling products"""
        conn = sqlite3.connect(get_phoneshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
            SELECT p.*, SUM(oi.quantity) as total_sold, SUM(oi.subtotal) as total_revenue
            FROM products p
            JOIN order_items oi ON p.product_id = oi.product_id AND oi.source_type = 'phone_shop'
            JOIN orders o ON oi.order_id = o.order_id AND o.source_type = 'phone_shop'
            WHERE p.source_type = 'phone_shop' AND o.order_status NOT IN ('cancelled', 'refunded')
            GROUP BY p.product_id
            ORDER BY total_sold DESC
            LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def generate_admin_report() -> str:
        """Generate comprehensive admin report"""
        sales = ReportManager.get_sales_summary()
        inventory = ReportManager.get_inventory_summary()
        top_products = ReportManager.get_top_selling_products(5)

        report = f"""
PHONE SHOP ADMIN REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'=' * 50}

SALES SUMMARY
-------------
Total Orders: {sales['total_orders']}
Total Revenue: £{sales['total_revenue']:.2f}
Average Order Value: £{sales['avg_order_value']:.2f}
Pending Orders: {sales['pending_orders']}
Completed Orders: {sales['completed_orders']}

INVENTORY SUMMARY
-----------------
Total Products: {inventory['total_products']}
Total Stock Units: {inventory['total_stock']}
Total Inventory Value: £{inventory['total_value']:.2f}
Low Stock Items: {inventory['low_stock_count']}

TOP SELLING PRODUCTS
--------------------
"""
        for i, p in enumerate(top_products, 1):
            report += f"{i}. {p['name']} - {p.get('total_sold', 0)} units (£{p.get('total_revenue', 0):.2f})\n"

        return report
