"""Music Shop Core Service Module"""

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from education_system.post_18.university_system.core import paths

logger = logging.getLogger(__name__)

# Constants
MUSIC_CATEGORIES = ['Vinyl Records', 'CDs', 'Cassettes', 'Instruments', 'Sheet Music', 'Merchandise', 'Audio Equipment', 'Accessories']
GENRES = ['Rock', 'Pop', 'Jazz', 'Classical', 'Hip-Hop', 'Electronic', 'Country', 'R&B', 'Metal', 'Folk', 'Blues', 'Indie', 'World', 'Soundtracks']
ORDER_STATUSES = ['pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded']
CONDITION_TYPES = ['new', 'mint', 'excellent', 'good', 'fair', 'poor']

def get_musicshop_db_path():
    """Get the music shop database path"""
    return str(paths.DEFAULT_DB_PATH)

def init_musicshop_db():
    """Initialize the music shop database tables"""
    conn = sqlite3.connect(get_musicshop_db_path())
    try:
        cursor = conn.cursor()

        # Products table (unified)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL DEFAULT 'music_shop',
            source_product_id TEXT,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            artist TEXT,
            category TEXT NOT NULL,
            genre TEXT,
            format TEXT,
            label TEXT,
            release_year INTEGER,
            condition TEXT DEFAULT 'new',
            description TEXT,
            price DECIMAL(10,2) NOT NULL,
            cost_price DECIMAL(10,2),
            stock_quantity INTEGER DEFAULT 0,
            min_stock_level INTEGER DEFAULT 3,
            is_rare BOOLEAN DEFAULT 0,
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
            source_type TEXT NOT NULL DEFAULT 'music_shop',
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
            source_type TEXT NOT NULL DEFAULT 'music_shop',
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            artist TEXT,
            quantity INTEGER NOT NULL,
            unit_price DECIMAL(10,2) NOT NULL,
            subtotal DECIMAL(10,2) NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        )
        ''')

        # Music shop transactions now use unified 'transactions' table with source_type='music_shop'

        # Wishlist table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS musicshop_wishlists (
            wishlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(product_id),
            UNIQUE(customer_id, product_id)
        )
        ''')

        conn.commit()
        logger.info("Music shop database initialized")
    finally:
        conn.close()

class ProductManager:
    """Manage music shop products"""

    @staticmethod
    def add_product(sku: str, title: str, category: str, price: float, **kwargs) -> Optional[int]:
        """Add a new product"""
        conn = sqlite3.connect(get_musicshop_db_path())
        cursor = conn.cursor()

        try:
            cursor.execute('''
            INSERT INTO products
            (source_type, sku, name, artist, category, genre, format, label, release_year, condition,
             description, price, cost_price, stock_quantity, min_stock_level, is_rare, image_url)
            VALUES ('music_shop', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                sku, title, kwargs.get('artist'), category, kwargs.get('genre'),
                kwargs.get('format'), kwargs.get('label'), kwargs.get('release_year'),
                kwargs.get('condition', 'new'), kwargs.get('description'), price,
                kwargs.get('cost_price'), kwargs.get('stock_quantity', 0),
                kwargs.get('min_stock_level', 3), kwargs.get('is_rare', False),
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
        conn = sqlite3.connect(get_musicshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM products WHERE source_type = ? AND product_id = ?', ('music_shop', product_id,))
            row = cursor.fetchone()

            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def get_all_products() -> List[Dict]:
        """Get all products"""
        conn = sqlite3.connect(get_musicshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM products WHERE source_type = ? AND is_active = 1 ORDER BY name', ('music_shop',))
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def get_products_by_category(category: str) -> List[Dict]:
        """Get products by category"""
        conn = sqlite3.connect(get_musicshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                'SELECT * FROM products WHERE source_type = ? AND category = ? AND is_active = 1 ORDER BY name',
                ('music_shop', category,)
            )
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def get_products_by_genre(genre: str) -> List[Dict]:
        """Get products by genre"""
        conn = sqlite3.connect(get_musicshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                'SELECT * FROM products WHERE source_type = ? AND genre = ? AND is_active = 1 ORDER BY name',
                ('music_shop', genre,)
            )
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def update_product(product_id: int, **kwargs) -> bool:
        """Update product"""
        conn = sqlite3.connect(get_musicshop_db_path())
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
                "UPDATE products SET " + ", ".join(updates) + " WHERE source_type = 'music_shop' AND product_id = ?",
                values)

            conn.commit()
            success = cursor.rowcount > 0
            return success
        finally:
            conn.close()

    @staticmethod
    def update_stock(product_id: int, quantity_change: int) -> bool:
        """Update product stock"""
        conn = sqlite3.connect(get_musicshop_db_path())
        try:
            cursor = conn.cursor()

            cursor.execute('''
            UPDATE products
            SET stock_quantity = stock_quantity + ?, updated_at = ?
            WHERE source_type = 'music_shop' AND product_id = ?
            ''', (quantity_change, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), product_id))

            conn.commit()
            success = cursor.rowcount > 0
            return success
        finally:
            conn.close()

    @staticmethod
    def get_low_stock_products() -> List[Dict]:
        """Get products with low stock"""
        conn = sqlite3.connect(get_musicshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
            SELECT * FROM products
            WHERE source_type = 'music_shop' AND stock_quantity <= min_stock_level AND is_active = 1
            ORDER BY stock_quantity
            ''')
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def get_rare_items() -> List[Dict]:
        """Get rare/collectible items"""
        conn = sqlite3.connect(get_musicshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
            SELECT * FROM products WHERE source_type = 'music_shop' AND is_rare = 1 AND is_active = 1 ORDER BY name
            ''')
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def search_products(query: str) -> List[Dict]:
        """Search products"""
        conn = sqlite3.connect(get_musicshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
            SELECT * FROM products
            WHERE source_type = 'music_shop' AND (name LIKE ? OR artist LIKE ? OR genre LIKE ? OR sku LIKE ?) AND is_active = 1
            ORDER BY name
            ''', (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%'))
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

class OrderManager:
    """Manage music shop orders"""

    @staticmethod
    def _generate_order_number() -> str:
        """Generate unique order number"""
        return f"MUS-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    @staticmethod
    def create_order(customer_id: str, customer_name: str, items: List[Dict], **kwargs) -> Optional[int]:
        """Create a new order"""
        conn = sqlite3.connect(get_musicshop_db_path())
        cursor = conn.cursor()

        try:
            subtotal = sum(item['quantity'] * item['unit_price'] for item in items)
            tax_amount = kwargs.get('tax_amount', subtotal * 0.20)
            shipping_fee = kwargs.get('shipping_fee', 0)
            discount_amount = kwargs.get('discount_amount', 0)
            total_amount = subtotal + tax_amount + shipping_fee - discount_amount

            order_number = OrderManager._generate_order_number()

            cursor.execute('''
            INSERT INTO orders
            (source_type, order_number, customer_id, customer_name, customer_email, customer_phone,
             shipping_address, subtotal, tax_amount, shipping_fee, discount_amount,
             total_amount, payment_method, notes, created_by)
            VALUES ('music_shop', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                order_number, customer_id, customer_name,
                kwargs.get('customer_email'), kwargs.get('customer_phone'),
                kwargs.get('shipping_address'), subtotal, tax_amount, shipping_fee,
                discount_amount, total_amount, kwargs.get('payment_method'),
                kwargs.get('notes'), kwargs.get('created_by')
            ))

            order_id = cursor.lastrowid

            for item in items:
                cursor.execute('''
                INSERT INTO order_items
                (source_type, order_id, product_id, item_name, artist, quantity, unit_price, subtotal)
                VALUES ('music_shop', ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    order_id, item['product_id'], item['product_title'],
                    item.get('artist'), item['quantity'], item['unit_price'],
                    item['quantity'] * item['unit_price']
                ))

                cursor.execute('''
                UPDATE products SET stock_quantity = stock_quantity - ? WHERE source_type = 'music_shop' AND product_id = ?
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
        conn = sqlite3.connect(get_musicshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM orders WHERE source_type = ? AND order_id = ?', ('music_shop', order_id,))
            row = cursor.fetchone()

            if row:
                order = dict(row)
                cursor.execute('SELECT * FROM order_items WHERE source_type = ? AND order_id = ?', ('music_shop', order_id,))
                order['items'] = [dict(item) for item in cursor.fetchall()]
            else:
                order = None

            return order
        finally:
            conn.close()

    @staticmethod
    def get_orders_by_status(status: str) -> List[Dict]:
        """Get orders by status"""
        conn = sqlite3.connect(get_musicshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
            SELECT * FROM orders WHERE source_type = 'music_shop' AND order_status = ? ORDER BY created_at DESC
            ''', (status,))
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def get_customer_orders(customer_id: str) -> List[Dict]:
        """Get orders for a customer"""
        conn = sqlite3.connect(get_musicshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
            SELECT * FROM orders WHERE source_type = 'music_shop' AND customer_id = ? ORDER BY created_at DESC
            ''', (customer_id,))
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def update_order_status(order_id: int, status: str) -> bool:
        """Update order status"""
        conn = sqlite3.connect(get_musicshop_db_path())
        try:
            cursor = conn.cursor()

            cursor.execute('''
            UPDATE orders SET order_status = ?, updated_at = ? WHERE source_type = 'music_shop' AND order_id = ?
            ''', (status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), order_id))

            conn.commit()
            success = cursor.rowcount > 0
            return success
        finally:
            conn.close()

    @staticmethod
    def cancel_order(order_id: int, reason: str = None) -> bool:
        """Cancel an order and restore stock"""
        conn = sqlite3.connect(get_musicshop_db_path())
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT product_id, quantity FROM order_items WHERE source_type = ? AND order_id = ?', ('music_shop', order_id,))
            items = cursor.fetchall()

            for product_id, quantity in items:
                cursor.execute('''
                UPDATE products SET stock_quantity = stock_quantity + ? WHERE source_type = 'music_shop' AND product_id = ?
                ''', (quantity, product_id))

            cursor.execute('''
            UPDATE orders SET order_status = 'cancelled', notes = ?, updated_at = ? WHERE source_type = 'music_shop' AND order_id = ?
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
    """Manage music shop transactions"""

    @staticmethod
    def record_payment(order_id: int, customer_id: str, amount: float, payment_method: str, **kwargs) -> Optional[int]:
        """Record a payment transaction"""
        conn = sqlite3.connect(get_musicshop_db_path())
        cursor = conn.cursor()

        try:
            cursor.execute('''
            INSERT INTO transactions
            (source_type, reference_id, reference_type, customer_id, transaction_type, amount, payment_method, reference_number, processed_by)
            VALUES ('music_shop', ?, 'order', ?, 'payment', ?, ?, ?, ?)
            ''', (
                order_id, customer_id, amount, payment_method,
                kwargs.get('reference_number'), kwargs.get('processed_by')
            ))

            cursor.execute('''
            UPDATE orders SET payment_status = 'completed', order_status = 'confirmed',
            payment_method = ?, updated_at = ? WHERE source_type = 'music_shop' AND order_id = ?
            ''', (payment_method, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), order_id))

            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to record payment: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    @staticmethod
    def process_refund(order_id: int, amount: float, reason: str = None, **kwargs) -> Optional[int]:
        """Process a refund"""
        conn = sqlite3.connect(get_musicshop_db_path())
        cursor = conn.cursor()

        try:
            order = OrderManager.get_order(order_id)
            if not order:
                return None

            cursor.execute('''
            INSERT INTO transactions
            (source_type, reference_id, reference_type, customer_id, transaction_type, amount, payment_method, reference_number, processed_by)
            VALUES ('music_shop', ?, 'order', ?, 'refund', ?, ?, ?, ?)
            ''', (
                order_id, order['customer_id'], -amount, order.get('payment_method'),
                reason, kwargs.get('processed_by')
            ))

            cursor.execute('''
            UPDATE orders SET payment_status = 'refunded', order_status = 'refunded', updated_at = ?
            WHERE source_type = 'music_shop' AND order_id = ?
            ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), order_id))

            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to process refund: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

class WishlistManager:
    """Manage customer wishlists"""

    @staticmethod
    def add_to_wishlist(customer_id: str, product_id: int) -> bool:
        """Add product to wishlist"""
        conn = sqlite3.connect(get_musicshop_db_path())
        cursor = conn.cursor()

        try:
            cursor.execute('''
            INSERT OR IGNORE INTO musicshop_wishlists (customer_id, product_id) VALUES (?, ?)
            ''', (customer_id, product_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to add to wishlist: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def remove_from_wishlist(customer_id: str, product_id: int) -> bool:
        """Remove product from wishlist"""
        conn = sqlite3.connect(get_musicshop_db_path())
        try:
            cursor = conn.cursor()

            cursor.execute('''
            DELETE FROM musicshop_wishlists WHERE customer_id = ? AND product_id = ?
            ''', (customer_id, product_id))

            conn.commit()
            success = cursor.rowcount > 0
            return success
        finally:
            conn.close()

    @staticmethod
    def get_wishlist(customer_id: str) -> List[Dict]:
        """Get customer's wishlist"""
        conn = sqlite3.connect(get_musicshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
            SELECT p.* FROM products p
            JOIN musicshop_wishlists w ON p.product_id = w.product_id
            WHERE p.source_type = 'music_shop' AND w.customer_id = ?
            ORDER BY w.added_at DESC
            ''', (customer_id,))
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

class ReportManager:
    """Generate music shop reports"""

    @staticmethod
    def get_sales_summary() -> Dict:
        """Get sales summary"""
        conn = sqlite3.connect(get_musicshop_db_path())
        try:
            cursor = conn.cursor()

            cursor.execute('''
            SELECT
                COUNT(*) as total_orders,
                SUM(CASE WHEN order_status NOT IN ('cancelled', 'refunded') THEN total_amount ELSE 0 END) as total_revenue,
                AVG(CASE WHEN order_status NOT IN ('cancelled', 'refunded') THEN total_amount ELSE NULL END) as avg_order_value,
                SUM(CASE WHEN order_status = 'pending' THEN 1 ELSE 0 END) as pending_orders,
                SUM(CASE WHEN order_status = 'delivered' THEN 1 ELSE 0 END) as completed_orders
            FROM orders WHERE source_type = 'music_shop'
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
        conn = sqlite3.connect(get_musicshop_db_path())
        try:
            cursor = conn.cursor()

            cursor.execute('''
            SELECT
                COUNT(*) as total_products,
                SUM(stock_quantity) as total_stock,
                SUM(stock_quantity * price) as total_value,
                SUM(CASE WHEN stock_quantity <= min_stock_level THEN 1 ELSE 0 END) as low_stock_count,
                SUM(CASE WHEN is_rare = 1 THEN 1 ELSE 0 END) as rare_items_count
            FROM products WHERE source_type = 'music_shop' AND is_active = 1
            ''')
            row = cursor.fetchone()

            return {
                'total_products': row[0] or 0,
                'total_stock': row[1] or 0,
                'total_value': row[2] or 0,
                'low_stock_count': row[3] or 0,
                'rare_items_count': row[4] or 0
            }
        finally:
            conn.close()

    @staticmethod
    def get_sales_by_genre() -> List[Dict]:
        """Get sales breakdown by genre"""
        conn = sqlite3.connect(get_musicshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
            SELECT p.genre, COUNT(oi.item_id) as items_sold, SUM(oi.subtotal) as revenue
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id AND p.source_type = 'music_shop'
            JOIN orders o ON oi.order_id = o.order_id AND o.source_type = 'music_shop'
            WHERE oi.source_type = 'music_shop' AND o.order_status NOT IN ('cancelled', 'refunded') AND p.genre IS NOT NULL
            GROUP BY p.genre
            ORDER BY revenue DESC
            ''')
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def get_top_selling_products(limit: int = 10) -> List[Dict]:
        """Get top selling products"""
        conn = sqlite3.connect(get_musicshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
            SELECT p.*, SUM(oi.quantity) as total_sold, SUM(oi.subtotal) as total_revenue
            FROM products p
            JOIN order_items oi ON p.product_id = oi.product_id AND oi.source_type = 'music_shop'
            JOIN orders o ON oi.order_id = o.order_id AND o.source_type = 'music_shop'
            WHERE p.source_type = 'music_shop' AND o.order_status NOT IN ('cancelled', 'refunded')
            GROUP BY p.product_id
            ORDER BY total_sold DESC
            LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def get_top_artists(limit: int = 10) -> List[Dict]:
        """Get top selling artists"""
        conn = sqlite3.connect(get_musicshop_db_path())
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
            SELECT p.artist, COUNT(DISTINCT oi.order_id) as orders, SUM(oi.quantity) as items_sold, SUM(oi.subtotal) as revenue
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id AND p.source_type = 'music_shop'
            JOIN orders o ON oi.order_id = o.order_id AND o.source_type = 'music_shop'
            WHERE oi.source_type = 'music_shop' AND o.order_status NOT IN ('cancelled', 'refunded') AND p.artist IS NOT NULL
            GROUP BY p.artist
            ORDER BY revenue DESC
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
        top_artists = ReportManager.get_top_artists(5)
        genre_sales = ReportManager.get_sales_by_genre()

        report = f"""
MUSIC SHOP ADMIN REPORT
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
Rare/Collectible Items: {inventory['rare_items_count']}

TOP SELLING PRODUCTS
--------------------
"""
        for i, p in enumerate(top_products, 1):
            report += f"{i}. {p['name']} by {p.get('artist', 'Unknown')}\n"
            report += f"   Sold: {p.get('total_sold', 0)} | Revenue: £{p.get('total_revenue', 0):.2f}\n"

        report += "\nTOP ARTISTS\n-----------\n"
        for i, a in enumerate(top_artists, 1):
            report += f"{i}. {a['artist']} - £{a.get('revenue', 0):.2f} ({a.get('items_sold', 0)} items)\n"

        report += "\nSALES BY GENRE\n--------------\n"
        for g in genre_sales[:5]:
            report += f"  {g['genre']}: £{g.get('revenue', 0):.2f}\n"

        return report
