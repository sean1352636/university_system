"""
Mail/Post System Core Services

Provides comprehensive mail and package handling services including
receiving, storing, tracking, and delivery notifications with
email and finance integration.
"""

import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity

# Constants
PACKAGE_STATUSES = ['received', 'stored', 'notified', 'collected', 'returned', 'forwarded']
PACKAGE_TYPES = ['letter', 'small_parcel', 'large_parcel', 'registered', 'express', 'international']
STORAGE_FEES = {
    'letter': 0.00,
    'small_parcel': 0.00,
    'large_parcel': 2.50,
    'registered': 1.00,
    'express': 0.00,
    'international': 3.00
}
DAILY_STORAGE_FEE = 0.50  # Per day after 7 days
FREE_STORAGE_DAYS = 7
FORWARDING_FEES = {
    'domestic': 5.00,
    'international': 15.00
}
PO_BOX_MONTHLY_FEE = 10.00


def generate_tracking_number() -> str:
    """Generate a unique tracking number."""
    return f"UNI-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def generate_reference() -> str:
    """Generate a unique reference number."""
    return f"REF-{uuid.uuid4().hex[:12].upper()}"


def init_mail_db():
    """Initialize mail/post system database tables."""
    try:
        with transaction() as conn:
            # Mail packages table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS mail_packages (
                    package_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tracking_number TEXT UNIQUE NOT NULL,
                    recipient_id TEXT NOT NULL,
                    recipient_name TEXT NOT NULL,
                    recipient_email TEXT,
                    recipient_phone TEXT,
                    sender_name TEXT,
                    sender_address TEXT,
                    package_type TEXT NOT NULL,
                    description TEXT,
                    weight_kg DECIMAL(10,2),
                    dimensions TEXT,
                    status TEXT DEFAULT 'received',
                    storage_location TEXT,
                    received_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notification_sent INTEGER DEFAULT 0,
                    notification_date TIMESTAMP,
                    collected_date TIMESTAMP,
                    collected_by TEXT,
                    storage_fee DECIMAL(10,2) DEFAULT 0.00,
                    total_charges DECIMAL(10,2) DEFAULT 0.00,
                    payment_status TEXT DEFAULT 'pending',
                    notes TEXT,
                    created_by TEXT
                )
            ''')

            # PO Boxes table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS mail_po_boxes (
                    box_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    box_number TEXT UNIQUE NOT NULL,
                    holder_id TEXT,
                    holder_name TEXT,
                    holder_email TEXT,
                    size TEXT DEFAULT 'standard',
                    monthly_fee DECIMAL(10,2) DEFAULT 10.00,
                    status TEXT DEFAULT 'available',
                    rental_start DATE,
                    rental_end DATE,
                    auto_renew INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Mail forwarding table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS mail_forwarding (
                    forwarding_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL,
                    forward_address TEXT NOT NULL,
                    forward_type TEXT DEFAULT 'domestic',
                    start_date DATE NOT NULL,
                    end_date DATE,
                    status TEXT DEFAULT 'active',
                    fee DECIMAL(10,2) DEFAULT 0.00,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Mail transactions table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS mail_transactions (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL,
                    transaction_type TEXT NOT NULL,
                    package_id INTEGER,
                    amount DECIMAL(10,2) NOT NULL,
                    payment_method TEXT,
                    status TEXT DEFAULT 'completed',
                    receipt_sent INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_by TEXT,
                    FOREIGN KEY (package_id) REFERENCES mail_packages(package_id)
                )
            ''')

            # Mail notifications log
            conn.execute('''
                CREATE TABLE IF NOT EXISTS mail_notifications (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    package_id INTEGER NOT NULL,
                    recipient_email TEXT NOT NULL,
                    notification_type TEXT NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'sent',
                    FOREIGN KEY (package_id) REFERENCES mail_packages(package_id)
                )
            ''')

            # Initialize some PO boxes if empty
            cursor = conn.execute("SELECT COUNT(*) FROM mail_po_boxes")
            if cursor.fetchone()[0] == 0:
                for i in range(1, 51):
                    box_num = f"PO-{i:03d}"
                    size = 'large' if i <= 10 else ('medium' if i <= 30 else 'standard')
                    fee = 15.00 if size == 'large' else (12.00 if size == 'medium' else 10.00)
                    conn.execute('''
                        INSERT INTO mail_po_boxes (box_number, size, monthly_fee, status)
                        VALUES (?, ?, ?, 'available')
                    ''', (box_num, size, fee))

        return True
    except Exception as e:
        print(f"Error initializing mail database: {e}")
        return False


class PackageManager:
    """Manages mail package operations."""

    @staticmethod
    def receive_package(recipient_id: str, recipient_name: str, recipient_email: str,
                       package_type: str, sender_name: str = None, sender_address: str = None,
                       description: str = None, weight_kg: float = None,
                       storage_location: str = None, created_by: str = None) -> Optional[Dict]:
        """Receive and register a new package."""
        try:
            tracking_number = generate_tracking_number()
            base_fee = STORAGE_FEES.get(package_type, 0.00)

            with transaction() as conn:
                conn.execute('''
                    INSERT INTO mail_packages
                    (tracking_number, recipient_id, recipient_name, recipient_email,
                     package_type, sender_name, sender_address, description, weight_kg,
                     storage_location, storage_fee, total_charges, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (tracking_number, recipient_id, recipient_name, recipient_email,
                      package_type, sender_name, sender_address, description, weight_kg,
                      storage_location, base_fee, base_fee, created_by))

                package_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            log_activity('create', 'mail_package', package_id=package_id,
                        details={'tracking': tracking_number, 'recipient': recipient_name})

            return {
                'package_id': package_id,
                'tracking_number': tracking_number,
                'storage_fee': base_fee
            }
        except Exception as e:
            print(f"Error receiving package: {e}")
            return None

    @staticmethod
    def get_package(package_id: int = None, tracking_number: str = None) -> Optional[Dict]:
        """Get package details by ID or tracking number."""
        try:
            with get_connection() as conn:
                if package_id:
                    cursor = conn.execute(
                        "SELECT * FROM mail_packages WHERE package_id = ?", (package_id,))
                else:
                    cursor = conn.execute(
                        "SELECT * FROM mail_packages WHERE tracking_number = ?", (tracking_number,))
                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            print(f"Error getting package: {e}")
            return None

    @staticmethod
    def get_packages_for_recipient(recipient_id: str, status: str = None) -> List[Dict]:
        """Get all packages for a recipient."""
        try:
            with get_connection() as conn:
                if status:
                    cursor = conn.execute('''
                        SELECT * FROM mail_packages
                        WHERE recipient_id = ? AND status = ?
                        ORDER BY received_date DESC
                    ''', (recipient_id, status))
                else:
                    cursor = conn.execute('''
                        SELECT * FROM mail_packages
                        WHERE recipient_id = ?
                        ORDER BY received_date DESC
                    ''', (recipient_id,))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting packages: {e}")
            return []

    @staticmethod
    def get_pending_packages() -> List[Dict]:
        """Get all packages awaiting collection."""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM mail_packages
                    WHERE status IN ('received', 'stored', 'notified')
                    ORDER BY received_date ASC
                ''')
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting pending packages: {e}")
            return []

    @staticmethod
    def update_package_status(package_id: int, status: str, notes: str = None) -> bool:
        """Update package status."""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE mail_packages
                    SET status = ?, notes = COALESCE(?, notes)
                    WHERE package_id = ?
                ''', (status, notes, package_id))
            return True
        except Exception as e:
            print(f"Error updating package status: {e}")
            return False

    @staticmethod
    def mark_collected(package_id: int, collected_by: str) -> bool:
        """Mark a package as collected."""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE mail_packages
                    SET status = 'collected', collected_date = ?, collected_by = ?
                    WHERE package_id = ?
                ''', (datetime.now().isoformat(), collected_by, package_id))
            log_activity('update', 'mail_package', package_id=package_id,
                        details={'action': 'collected', 'by': collected_by})
            return True
        except Exception as e:
            print(f"Error marking package collected: {e}")
            return False

    @staticmethod
    def calculate_storage_fees(package_id: int) -> float:
        """Calculate storage fees for a package."""
        try:
            package = PackageManager.get_package(package_id=package_id)
            if not package:
                return 0.0

            received_date = datetime.fromisoformat(package['received_date'].replace('Z', '+00:00'))
            days_stored = (datetime.now() - received_date.replace(tzinfo=None)).days

            base_fee = package['storage_fee'] or 0.0
            if days_stored > FREE_STORAGE_DAYS:
                extra_days = days_stored - FREE_STORAGE_DAYS
                base_fee += extra_days * DAILY_STORAGE_FEE

            return round(base_fee, 2)
        except Exception as e:
            print(f"Error calculating storage fees: {e}")
            return 0.0

    @staticmethod
    def search_packages(search_term: str) -> List[Dict]:
        """Search packages by tracking number, recipient name, or sender."""
        try:
            with get_connection() as conn:
                search = f"%{search_term}%"
                cursor = conn.execute('''
                    SELECT * FROM mail_packages
                    WHERE tracking_number LIKE ?
                       OR recipient_name LIKE ?
                       OR sender_name LIKE ?
                    ORDER BY received_date DESC
                    LIMIT 100
                ''', (search, search, search))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error searching packages: {e}")
            return []


class POBoxManager:
    """Manages PO Box rentals."""

    @staticmethod
    def get_available_boxes() -> List[Dict]:
        """Get all available PO boxes."""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM mail_po_boxes
                    WHERE status = 'available'
                    ORDER BY box_number
                ''')
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting available boxes: {e}")
            return []

    @staticmethod
    def rent_box(box_id: int, holder_id: str, holder_name: str, holder_email: str,
                 months: int = 1) -> Optional[Dict]:
        """Rent a PO box."""
        try:
            with transaction() as conn:
                # Get box details
                cursor = conn.execute(
                    "SELECT * FROM mail_po_boxes WHERE box_id = ? AND status = 'available'",
                    (box_id,))
                row = cursor.fetchone()
                if not row:
                    return None

                columns = [desc[0] for desc in cursor.description]
                box = dict(zip(columns, row))

                start_date = datetime.now().date()
                end_date = start_date + timedelta(days=30 * months)
                total_fee = box['monthly_fee'] * months

                conn.execute('''
                    UPDATE mail_po_boxes
                    SET holder_id = ?, holder_name = ?, holder_email = ?,
                        status = 'rented', rental_start = ?, rental_end = ?
                    WHERE box_id = ?
                ''', (holder_id, holder_name, holder_email,
                      start_date.isoformat(), end_date.isoformat(), box_id))

            return {
                'box_number': box['box_number'],
                'rental_fee': total_fee,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
        except Exception as e:
            print(f"Error renting PO box: {e}")
            return None

    @staticmethod
    def get_user_box(user_id: str) -> Optional[Dict]:
        """Get user's rented PO box."""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM mail_po_boxes
                    WHERE holder_id = ? AND status = 'rented'
                ''', (user_id,))
                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            print(f"Error getting user box: {e}")
            return None

    @staticmethod
    def release_box(box_id: int) -> bool:
        """Release a PO box rental."""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE mail_po_boxes
                    SET holder_id = NULL, holder_name = NULL, holder_email = NULL,
                        status = 'available', rental_start = NULL, rental_end = NULL
                    WHERE box_id = ?
                ''', (box_id,))
            return True
        except Exception as e:
            print(f"Error releasing PO box: {e}")
            return False


class ForwardingManager:
    """Manages mail forwarding services."""

    @staticmethod
    def setup_forwarding(user_id: str, user_name: str, forward_address: str,
                        forward_type: str = 'domestic', start_date: str = None,
                        end_date: str = None) -> Optional[Dict]:
        """Set up mail forwarding."""
        try:
            if not start_date:
                start_date = datetime.now().date().isoformat()

            fee = FORWARDING_FEES.get(forward_type, FORWARDING_FEES['domestic'])

            with transaction() as conn:
                conn.execute('''
                    INSERT INTO mail_forwarding
                    (user_id, user_name, forward_address, forward_type, start_date, end_date, fee)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, user_name, forward_address, forward_type, start_date, end_date, fee))

                forwarding_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            return {
                'forwarding_id': forwarding_id,
                'fee': fee
            }
        except Exception as e:
            print(f"Error setting up forwarding: {e}")
            return None

    @staticmethod
    def get_user_forwarding(user_id: str) -> Optional[Dict]:
        """Get user's active forwarding settings."""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM mail_forwarding
                    WHERE user_id = ? AND status = 'active'
                ''', (user_id,))
                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            print(f"Error getting forwarding: {e}")
            return None

    @staticmethod
    def cancel_forwarding(forwarding_id: int) -> bool:
        """Cancel mail forwarding."""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE mail_forwarding SET status = 'cancelled' WHERE forwarding_id = ?
                ''', (forwarding_id,))
            return True
        except Exception as e:
            print(f"Error cancelling forwarding: {e}")
            return False


class TransactionManager:
    """Manages mail service transactions."""

    @staticmethod
    def record_payment(user_id: str, transaction_type: str, amount: float,
                      payment_method: str, package_id: int = None,
                      processed_by: str = None) -> Optional[Dict]:
        """Record a payment transaction."""
        try:
            reference = generate_reference()

            with transaction() as conn:
                conn.execute('''
                    INSERT INTO mail_transactions
                    (reference, user_id, transaction_type, package_id, amount,
                     payment_method, processed_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (reference, user_id, transaction_type, package_id, amount,
                      payment_method, processed_by))

                transaction_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                # Update package payment status if applicable
                if package_id:
                    conn.execute('''
                        UPDATE mail_packages SET payment_status = 'paid' WHERE package_id = ?
                    ''', (package_id,))

            return {
                'transaction_id': transaction_id,
                'reference': reference,
                'amount': amount
            }
        except Exception as e:
            print(f"Error recording payment: {e}")
            return None

    @staticmethod
    def get_user_transactions(user_id: str, limit: int = 50) -> List[Dict]:
        """Get user's transaction history."""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM mail_transactions
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (user_id, limit))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting transactions: {e}")
            return []


class ReportManager:
    """Manages reporting for mail services."""

    @staticmethod
    def get_daily_report(date: str = None) -> Dict:
        """Generate daily operations report."""
        try:
            if not date:
                date = datetime.now().date().isoformat()

            with get_connection() as conn:
                # Packages received
                cursor = conn.execute('''
                    SELECT COUNT(*), COALESCE(SUM(storage_fee), 0)
                    FROM mail_packages
                    WHERE DATE(received_date) = ?
                ''', (date,))
                received, fees = cursor.fetchone()

                # Packages collected
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM mail_packages
                    WHERE DATE(collected_date) = ?
                ''', (date,))
                collected = cursor.fetchone()[0]

                # Revenue
                cursor = conn.execute('''
                    SELECT COALESCE(SUM(amount), 0) FROM mail_transactions
                    WHERE DATE(created_at) = ?
                ''', (date,))
                revenue = cursor.fetchone()[0]

                return {
                    'date': date,
                    'packages_received': received,
                    'packages_collected': collected,
                    'storage_fees': fees,
                    'total_revenue': revenue
                }
        except Exception as e:
            print(f"Error generating daily report: {e}")
            return {}

    @staticmethod
    def get_monthly_summary(year: int = None, month: int = None) -> Dict:
        """Generate monthly summary report."""
        try:
            if not year:
                year = datetime.now().year
            if not month:
                month = datetime.now().month

            with get_connection() as conn:
                # Monthly packages
                cursor = conn.execute('''
                    SELECT package_type, COUNT(*), COALESCE(SUM(total_charges), 0)
                    FROM mail_packages
                    WHERE strftime('%Y', received_date) = ? AND strftime('%m', received_date) = ?
                    GROUP BY package_type
                ''', (str(year), f"{month:02d}"))
                by_type = {row[0]: {'count': row[1], 'revenue': row[2]} for row in cursor.fetchall()}

                # Total revenue
                cursor = conn.execute('''
                    SELECT COALESCE(SUM(amount), 0) FROM mail_transactions
                    WHERE strftime('%Y', created_at) = ? AND strftime('%m', created_at) = ?
                ''', (str(year), f"{month:02d}"))
                total_revenue = cursor.fetchone()[0]

                # PO Box rentals
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM mail_po_boxes WHERE status = 'rented'
                ''')
                active_boxes = cursor.fetchone()[0]

                return {
                    'year': year,
                    'month': month,
                    'packages_by_type': by_type,
                    'total_revenue': total_revenue,
                    'active_po_boxes': active_boxes
                }
        except Exception as e:
            print(f"Error generating monthly summary: {e}")
            return {}

    @staticmethod
    def get_pending_notifications() -> List[Dict]:
        """Get packages that need notification."""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM mail_packages
                    WHERE status = 'received' AND notification_sent = 0
                    ORDER BY received_date ASC
                ''')
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting pending notifications: {e}")
            return []
