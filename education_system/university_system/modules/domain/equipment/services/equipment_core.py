"""Equipment Rental System Core Services Module"""

from education_system.university_system.infrastructure.database.db import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from education_system.university_system.infrastructure.database.db import get_db_connection, transaction
from education_system.university_system.core.sql_safety import validate_identifier

logger = logging.getLogger(__name__)

# Equipment categories
EQUIPMENT_CATEGORIES = [
    'audio_visual', 'computers', 'cameras', 'sports', 'tools', 'lab_equipment',
    'projectors', 'lighting', 'furniture', 'event_supplies', 'outdoor', 'other'
]

# Rental statuses
RENTAL_STATUSES = ['reserved', 'checked_out', 'returned', 'overdue', 'cancelled']

# Equipment conditions
EQUIPMENT_CONDITIONS = ['excellent', 'good', 'fair', 'needs_repair', 'out_of_service']

def init_equipment_db():
    """Initialize equipment rental database tables"""
    try:
        with transaction() as conn:
            # Equipment inventory table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS equipment_items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_code TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT NOT NULL,
                    brand TEXT,
                    model TEXT,
                    serial_number TEXT,
                    daily_rate DECIMAL(10,2) NOT NULL,
                    hourly_rate DECIMAL(10,2),
                    deposit_required DECIMAL(10,2) DEFAULT 0,
                    quantity_total INTEGER DEFAULT 1,
                    quantity_available INTEGER DEFAULT 1,
                    condition TEXT DEFAULT 'good',
                    location TEXT,
                    image_path TEXT,
                    notes TEXT,
                    requires_training INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Rentals table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS equipment_rentals (
                    rental_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rental_number TEXT UNIQUE NOT NULL,
                    item_id INTEGER NOT NULL,
                    quantity INTEGER DEFAULT 1,
                    borrower_id TEXT NOT NULL,
                    borrower_name TEXT NOT NULL,
                    borrower_email TEXT,
                    borrower_phone TEXT,
                    borrower_department TEXT,
                    purpose TEXT,
                    checkout_date TEXT NOT NULL,
                    checkout_time TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    due_time TEXT NOT NULL,
                    actual_return_date TEXT,
                    actual_return_time TEXT,
                    daily_rate DECIMAL(10,2) NOT NULL,
                    total_days INTEGER NOT NULL,
                    subtotal DECIMAL(10,2) NOT NULL,
                    deposit_amount DECIMAL(10,2) DEFAULT 0,
                    late_fee DECIMAL(10,2) DEFAULT 0,
                    damage_fee DECIMAL(10,2) DEFAULT 0,
                    total_amount DECIMAL(10,2) NOT NULL,
                    payment_status TEXT DEFAULT 'pending',
                    payment_method TEXT,
                    status TEXT DEFAULT 'reserved',
                    condition_checkout TEXT,
                    condition_return TEXT,
                    notes TEXT,
                    created_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (item_id) REFERENCES equipment_items(item_id)
                )
            ''')

            # Transactions table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS equipment_transactions (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rental_id INTEGER,
                    borrower_id TEXT NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    transaction_type TEXT NOT NULL,
                    payment_method TEXT,
                    reference_number TEXT,
                    status TEXT DEFAULT 'completed',
                    notes TEXT,
                    processed_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (rental_id) REFERENCES equipment_rentals(rental_id)
                )
            ''')

            # Maintenance records
            conn.execute('''
                CREATE TABLE IF NOT EXISTS equipment_maintenance (
                    maintenance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER NOT NULL,
                    maintenance_type TEXT NOT NULL,
                    description TEXT,
                    cost DECIMAL(10,2) DEFAULT 0,
                    performed_date TEXT NOT NULL,
                    next_maintenance_date TEXT,
                    performed_by TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (item_id) REFERENCES equipment_items(item_id)
                )
            ''')

            # Reservations queue
            conn.execute('''
                CREATE TABLE IF NOT EXISTS equipment_reservations (
                    reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER NOT NULL,
                    borrower_id TEXT NOT NULL,
                    borrower_name TEXT NOT NULL,
                    requested_date TEXT NOT NULL,
                    requested_duration INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 5,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (item_id) REFERENCES equipment_items(item_id)
                )
            ''')

        logger.info("Equipment rental database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize equipment database: {e}")
        return False

class EquipmentManager:
    """Manages equipment inventory"""

    @staticmethod
    def add_item(item_code: str, name: str, category: str, daily_rate: float,
                 **kwargs) -> Optional[int]:
        """Add a new equipment item"""
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO equipment_items
                    (item_code, name, category, daily_rate, description, brand, model,
                     serial_number, hourly_rate, deposit_required, quantity_total,
                     quantity_available, condition, location, requires_training, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item_code, name, category, daily_rate,
                    kwargs.get('description'),
                    kwargs.get('brand'),
                    kwargs.get('model'),
                    kwargs.get('serial_number'),
                    kwargs.get('hourly_rate'),
                    kwargs.get('deposit_required', 0),
                    kwargs.get('quantity_total', 1),
                    kwargs.get('quantity_available', kwargs.get('quantity_total', 1)),
                    kwargs.get('condition', 'good'),
                    kwargs.get('location'),
                    kwargs.get('requires_training', 0),
                    kwargs.get('notes')
                ))
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to add equipment: {e}")
            return None

    @staticmethod
    def update_item(item_id: int, **kwargs) -> bool:
        """Update equipment item details"""
        try:
            updates = []
            values = []
            for key, value in kwargs.items():
                if value is not None:
                    updates.append(validate_identifier(key, "column") + " = ?")
                    values.append(value)

            if not updates:
                return False

            updates.append("updated_at = CURRENT_TIMESTAMP")
            values.append(item_id)

            with transaction() as conn:
                conn.execute(
                    "UPDATE equipment_items"
                    " SET " + ", ".join(updates) +
                    " WHERE item_id = ?",
                    values)
            return True
        except Exception as e:
            logger.error(f"Failed to update equipment: {e}")
            return False

    @staticmethod
    def get_item(item_id: int) -> Optional[Dict]:
        """Get equipment item by ID"""
        try:
            with get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM equipment_items WHERE item_id = ?',
                    (item_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get equipment: {e}")
            return None

    @staticmethod
    def get_available_items(category: str = None) -> List[Dict]:
        """Get available equipment items"""
        try:
            with get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                query = "SELECT * FROM equipment_items WHERE quantity_available > 0 AND is_active = 1"
                params = []

                if category:
                    query += " AND category = ?"
                    params.append(category)

                query += " ORDER BY category, name"
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get available equipment: {e}")
            return []

    @staticmethod
    def get_all_items() -> List[Dict]:
        """Get all equipment items"""
        try:
            with get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    'SELECT * FROM equipment_items WHERE is_active = 1 ORDER BY category, name'
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get all equipment: {e}")
            return []

    @staticmethod
    def update_availability(item_id: int, quantity_change: int) -> bool:
        """Update equipment availability"""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE equipment_items
                    SET quantity_available = quantity_available + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE item_id = ?
                ''', (quantity_change, item_id))
            return True
        except Exception as e:
            logger.error(f"Failed to update availability: {e}")
            return False

class RentalManager:
    """Manages equipment rental operations"""

    @staticmethod
    def generate_rental_number() -> str:
        """Generate unique rental number"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"EQR-{timestamp}"

    @staticmethod
    def create_rental(item_id: int, borrower_id: str, borrower_name: str,
                     checkout_date: str, checkout_time: str,
                     due_date: str, due_time: str, daily_rate: float,
                     quantity: int = 1, **kwargs) -> Optional[int]:
        """Create a new equipment rental"""
        try:
            rental_number = RentalManager.generate_rental_number()

            # Calculate total days
            checkout = datetime.strptime(checkout_date, '%Y-%m-%d')
            due = datetime.strptime(due_date, '%Y-%m-%d')
            total_days = max(1, (due - checkout).days)

            subtotal = daily_rate * total_days * quantity
            deposit = kwargs.get('deposit_amount', 0)
            total_amount = subtotal + deposit

            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO equipment_rentals
                    (rental_number, item_id, quantity, borrower_id, borrower_name,
                     borrower_email, borrower_phone, borrower_department, purpose,
                     checkout_date, checkout_time, due_date, due_time,
                     daily_rate, total_days, subtotal, deposit_amount, total_amount,
                     status, condition_checkout, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'reserved', ?, ?)
                ''', (
                    rental_number, item_id, quantity, borrower_id, borrower_name,
                    kwargs.get('borrower_email'), kwargs.get('borrower_phone'),
                    kwargs.get('borrower_department'), kwargs.get('purpose'),
                    checkout_date, checkout_time, due_date, due_time,
                    daily_rate, total_days, subtotal, deposit, total_amount,
                    kwargs.get('condition_checkout'), kwargs.get('created_by')
                ))

                # Update availability
                conn.execute('''
                    UPDATE equipment_items
                    SET quantity_available = quantity_available - ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE item_id = ?
                ''', (quantity, item_id))

                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to create rental: {e}")
            return None

    @staticmethod
    def get_rental(rental_id: int) -> Optional[Dict]:
        """Get rental by ID"""
        try:
            with get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT r.*, e.item_code, e.name as item_name, e.category
                    FROM equipment_rentals r
                    JOIN equipment_items e ON r.item_id = e.item_id
                    WHERE r.rental_id = ?
                ''', (rental_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get rental: {e}")
            return None

    @staticmethod
    def get_rentals_by_status(status: str = None) -> List[Dict]:
        """Get rentals filtered by status"""
        try:
            with get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                if status:
                    cursor = conn.execute('''
                        SELECT r.*, e.item_code, e.name as item_name
                        FROM equipment_rentals r
                        JOIN equipment_items e ON r.item_id = e.item_id
                        WHERE r.status = ?
                        ORDER BY r.due_date ASC
                    ''', (status,))
                else:
                    cursor = conn.execute('''
                        SELECT r.*, e.item_code, e.name as item_name
                        FROM equipment_rentals r
                        JOIN equipment_items e ON r.item_id = e.item_id
                        ORDER BY r.checkout_date DESC
                    ''')
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get rentals: {e}")
            return []

    @staticmethod
    def checkout_item(rental_id: int, condition: str = None) -> bool:
        """Check out equipment (start rental)"""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE equipment_rentals
                    SET status = 'checked_out', condition_checkout = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE rental_id = ?
                ''', (condition, rental_id))
            return True
        except Exception as e:
            logger.error(f"Failed to checkout: {e}")
            return False

    @staticmethod
    def return_item(rental_id: int, condition: str,
                   late_fee: float = 0, damage_fee: float = 0) -> bool:
        """Return equipment"""
        try:
            now = datetime.now()
            with transaction() as conn:
                # Get rental details
                cursor = conn.execute(
                    'SELECT item_id, quantity, total_amount FROM equipment_rentals WHERE rental_id = ?',
                    (rental_id,)
                )
                rental = cursor.fetchone()
                if not rental:
                    return False

                item_id, quantity, current_total = rental
                new_total = current_total + late_fee + damage_fee

                conn.execute('''
                    UPDATE equipment_rentals
                    SET status = 'returned', actual_return_date = ?, actual_return_time = ?,
                        condition_return = ?, late_fee = ?, damage_fee = ?,
                        total_amount = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE rental_id = ?
                ''', (
                    now.strftime('%Y-%m-%d'), now.strftime('%H:%M'),
                    condition, late_fee, damage_fee, new_total, rental_id
                ))

                # Update availability
                conn.execute('''
                    UPDATE equipment_items
                    SET quantity_available = quantity_available + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE item_id = ?
                ''', (quantity, item_id))

            return True
        except Exception as e:
            logger.error(f"Failed to return item: {e}")
            return False

    @staticmethod
    def cancel_rental(rental_id: int, reason: str = None) -> bool:
        """Cancel a rental"""
        try:
            with transaction() as conn:
                # Get item and quantity
                cursor = conn.execute(
                    'SELECT item_id, quantity FROM equipment_rentals WHERE rental_id = ?',
                    (rental_id,)
                )
                result = cursor.fetchone()
                if not result:
                    return False

                item_id, quantity = result

                conn.execute('''
                    UPDATE equipment_rentals
                    SET status = 'cancelled', notes = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE rental_id = ?
                ''', (reason, rental_id))

                # Restore availability
                conn.execute('''
                    UPDATE equipment_items
                    SET quantity_available = quantity_available + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE item_id = ?
                ''', (quantity, item_id))

            return True
        except Exception as e:
            logger.error(f"Failed to cancel rental: {e}")
            return False

    @staticmethod
    def extend_rental(rental_id: int, new_due_date: str, new_due_time: str) -> bool:
        """Extend rental due date"""
        try:
            with transaction() as conn:
                # Get current rental info
                cursor = conn.execute(
                    'SELECT checkout_date, daily_rate, quantity FROM equipment_rentals WHERE rental_id = ?',
                    (rental_id,)
                )
                rental = cursor.fetchone()
                if not rental:
                    return False

                checkout_date, daily_rate, quantity = rental

                # Calculate new totals
                checkout = datetime.strptime(checkout_date, '%Y-%m-%d')
                new_due = datetime.strptime(new_due_date, '%Y-%m-%d')
                total_days = max(1, (new_due - checkout).days)
                new_subtotal = daily_rate * total_days * quantity

                conn.execute('''
                    UPDATE equipment_rentals
                    SET due_date = ?, due_time = ?, total_days = ?,
                        subtotal = ?, total_amount = subtotal + deposit_amount,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE rental_id = ?
                ''', (new_due_date, new_due_time, total_days, new_subtotal, rental_id))

            return True
        except Exception as e:
            logger.error(f"Failed to extend rental: {e}")
            return False

class TransactionManager:
    """Manages payment transactions"""

    @staticmethod
    def record_payment(rental_id: int, borrower_id: str, amount: float,
                      payment_method: str, processed_by: str = None) -> Optional[int]:
        """Record a payment transaction"""
        try:
            import random
            ref_number = f"EQP-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO equipment_transactions
                    (rental_id, borrower_id, amount, transaction_type, payment_method,
                     reference_number, status, processed_by)
                    VALUES (?, ?, ?, 'payment', ?, ?, 'completed', ?)
                ''', (rental_id, borrower_id, amount, payment_method, ref_number, processed_by))

                # Update rental payment status
                conn.execute('''
                    UPDATE equipment_rentals
                    SET payment_status = 'paid', payment_method = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE rental_id = ?
                ''', (payment_method, rental_id))

                # Record in main payments table for finance integration
                conn.execute('''
                    INSERT INTO payments
                    (student_id, amount, payment_method, payment_date, status, notes, created_by)
                    VALUES (?, ?, ?, ?, 'completed', 'Equipment Rental Payment', ?)
                ''', (borrower_id, amount, payment_method,
                      datetime.now().strftime('%Y-%m-%d'), processed_by))

                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to record payment: {e}")
            return None

    @staticmethod
    def refund_deposit(rental_id: int, borrower_id: str, amount: float,
                      processed_by: str = None) -> Optional[int]:
        """Refund deposit"""
        try:
            import random
            ref_number = f"EQD-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO equipment_transactions
                    (rental_id, borrower_id, amount, transaction_type, payment_method,
                     reference_number, status, notes, processed_by)
                    VALUES (?, ?, ?, 'deposit_refund', 'refund', ?, 'completed', 'Deposit refund', ?)
                ''', (rental_id, borrower_id, amount, ref_number, processed_by))
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to refund deposit: {e}")
            return None

    @staticmethod
    def get_transactions(rental_id: int = None) -> List[Dict]:
        """Get transactions"""
        try:
            with get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                if rental_id:
                    cursor = conn.execute(
                        'SELECT * FROM equipment_transactions WHERE rental_id = ? ORDER BY created_at DESC',
                        (rental_id,)
                    )
                else:
                    cursor = conn.execute(
                        'SELECT * FROM equipment_transactions ORDER BY created_at DESC LIMIT 100'
                    )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get transactions: {e}")
            return []

class ReportManager:
    """Manages reports and analytics"""

    @staticmethod
    def get_inventory_summary() -> Dict:
        """Get inventory summary statistics"""
        try:
            with get_db_connection() as conn:
                cursor = conn.execute('''
                    SELECT
                        COUNT(*) as total_items,
                        SUM(quantity_total) as total_quantity,
                        SUM(quantity_available) as available_quantity,
                        SUM(quantity_total - quantity_available) as rented_quantity
                    FROM equipment_items WHERE is_active = 1
                ''')
                return dict(cursor.fetchone())
        except Exception as e:
            logger.error(f"Failed to get inventory summary: {e}")
            return {}

    @staticmethod
    def get_revenue_report(start_date: str = None, end_date: str = None) -> Dict:
        """Get revenue report"""
        try:
            with get_db_connection() as conn:
                query = '''
                    SELECT
                        COUNT(*) as total_rentals,
                        SUM(total_amount) as total_revenue,
                        AVG(total_amount) as avg_rental_value,
                        SUM(late_fee) as total_late_fees,
                        SUM(damage_fee) as total_damage_fees
                    FROM equipment_rentals
                    WHERE payment_status = 'paid'
                '''
                params = []

                if start_date and end_date:
                    query += " AND created_at BETWEEN ? AND ?"
                    params.extend([start_date, end_date])

                cursor = conn.execute(query, params)
                return dict(cursor.fetchone())
        except Exception as e:
            logger.error(f"Failed to get revenue report: {e}")
            return {}

    @staticmethod
    def get_popular_items(limit: int = 10) -> List[Dict]:
        """Get most popular equipment items"""
        try:
            with get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT e.item_id, e.name, e.category,
                           COUNT(r.rental_id) as rental_count,
                           SUM(r.total_amount) as total_revenue
                    FROM equipment_items e
                    LEFT JOIN equipment_rentals r ON e.item_id = r.item_id
                    GROUP BY e.item_id
                    ORDER BY rental_count DESC
                    LIMIT ?
                ''', (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get popular items: {e}")
            return []

    @staticmethod
    def get_overdue_rentals() -> List[Dict]:
        """Get overdue rentals"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            with get_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT r.*, e.name as item_name
                    FROM equipment_rentals r
                    JOIN equipment_items e ON r.item_id = e.item_id
                    WHERE r.status = 'checked_out' AND r.due_date < ?
                    ORDER BY r.due_date ASC
                ''', (today,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get overdue rentals: {e}")
            return []

    @staticmethod
    def generate_admin_report() -> str:
        """Generate comprehensive admin report"""
        try:
            inventory = ReportManager.get_inventory_summary()
            revenue = ReportManager.get_revenue_report()
            popular = ReportManager.get_popular_items(5)
            overdue = ReportManager.get_overdue_rentals()

            report = f"""
EQUIPMENT RENTAL SYSTEM - ADMIN REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'=' * 50}

INVENTORY SUMMARY
-----------------
Total Items: {inventory.get('total_items', 0)}
Total Quantity: {inventory.get('total_quantity', 0)}
Available: {inventory.get('available_quantity', 0)}
Currently Rented: {inventory.get('rented_quantity', 0)}

REVENUE SUMMARY
---------------
Total Rentals: {revenue.get('total_rentals', 0)}
Total Revenue: ${revenue.get('total_revenue', 0):.2f}
Average Rental Value: ${revenue.get('avg_rental_value', 0):.2f}
Late Fees Collected: ${revenue.get('total_late_fees', 0):.2f}
Damage Fees Collected: ${revenue.get('total_damage_fees', 0):.2f}

TOP 5 MOST RENTED ITEMS
-----------------------
"""
            for i, item in enumerate(popular, 1):
                report += f"{i}. {item['name']} ({item['category']}) - {item['rental_count']} rentals\n"

            report += f"\nOVERDUE RENTALS ({len(overdue)})\n"
            report += "-" * 20 + "\n"
            for r in overdue[:5]:
                report += f"- {r['rental_number']}: {r['item_name']} (Due: {r['due_date']})\n"

            return report
        except Exception as e:
            logger.error(f"Failed to generate admin report: {e}")
            return "Error generating report"
