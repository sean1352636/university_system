#!/usr/bin/env python3
"""
Charity Shop Stock Management CLI
A command-line interface for managing charity shop inventory.
Features: Stock tracking, sold status, revenue calculation, and reporting.

Integrated with the University Management System.
"""

import sqlite3
import logging
import csv
import json
import os
import random
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal

# University system imports
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from university_system.infrastructure.database.db import get_connection

# Import auth instance management
try:
    from university_system.infrastructure.auth import get_current_user, set_auth_instance
    from university_system.infrastructure.shared_context import get_auth, set_auth as set_shared_auth
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None
    get_auth = lambda: None
    set_shared_auth = lambda x: None

# Import activity logger for audit trail
try:
    from university_system.modules.shared.utils.simple_activity_logger import (
        log_activity,
        log_create,
        log_read,
        log_update,
        log_delete,
        log_search,
        log_menu_navigation,
    )
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None
    log_create = lambda *args, **kwargs: None
    log_read = lambda *args, **kwargs: None
    log_update = lambda *args, **kwargs: None
    log_delete = lambda *args, **kwargs: None
    log_search = lambda *args, **kwargs: None
    log_menu_navigation = lambda *args, **kwargs: None

# Import i18n for internationalization
from university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)

logger = logging.getLogger(__name__)

# Global auth instance
auth = None

# Table name for charity shop stock
TABLE_NAME = "charity_shop_stock"

# Additional table names
CUSTOMERS_TABLE = "charity_shop_customers"
DONATIONS_TABLE = "charity_shop_donations"
DONORS_TABLE = "charity_shop_donors"
STAFF_TABLE = "charity_shop_staff"
GIFT_CARDS_TABLE = "charity_shop_gift_cards"
PRICE_HISTORY_TABLE = "charity_shop_price_history"
SALES_TABLE = "charity_shop_sales"
BUNDLES_TABLE = "charity_shop_bundles"
PROMOTIONS_TABLE = "charity_shop_promotions"
LAYAWAY_TABLE = "charity_shop_layaway"
LOYALTY_TABLE = "charity_shop_loyalty"
ARCHIVED_TABLE = "charity_shop_archived"
LOCATIONS_TABLE = "charity_shop_locations"
SHIFTS_TABLE = "charity_shop_shifts"
TASKS_TABLE = "charity_shop_tasks"
WISHLISTS_TABLE = "charity_shop_wishlists"
FEEDBACK_TABLE = "charity_shop_feedback"
REFERRALS_TABLE = "charity_shop_referrals"

# Categories for charity shop items
CATEGORIES = [
    "Books", "Clothing", "Electronics", "Furniture", "Homeware",
    "Toys", "Music/DVDs", "Accessories", "Sports", "Other"
]

# Condition options
CONDITIONS = ["New", "Excellent", "Good", "Fair", "Poor"]

# Low stock threshold default
DEFAULT_LOW_STOCK_THRESHOLD = 5

# Loyalty points per pound spent
LOYALTY_POINTS_PER_POUND = 10


def set_auth(auth_instance: Any) -> None:
    """Set the global auth instance for charity shop CLI."""
    global auth
    auth = auth_instance
    if HAS_AUTH:
        set_auth_instance(auth_instance)
        try:
            set_shared_auth(auth_instance)
        except Exception as e:
            logger.warning(f"Failed to set auth in shared_context: {e}")


def init_charity_shop_db() -> bool:
    """Initialize the charity shop database tables."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if main table exists and has the correct columns
        cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
        columns = [col[1] for col in cursor.fetchall()]

        if 'sold' not in columns:
            if 'id' in columns:
                # Migration: add new columns to existing table
                cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN sold INTEGER DEFAULT 0")
                cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN sold_date TEXT")
                cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN sold_quantity INTEGER DEFAULT 0")
            else:
                # Create new table
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
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

        # Add new columns to main stock table if missing
        cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
        columns = [col[1] for col in cursor.fetchall()]

        new_columns = [
            ("low_stock_threshold", "INTEGER DEFAULT 5"),
            ("barcode", "TEXT"),
            ("location_id", "INTEGER"),
            ("discount_percent", "REAL DEFAULT 0"),
            ("donation_cost", "REAL DEFAULT 0"),
        ]
        for col_name, col_def in new_columns:
            if col_name not in columns:
                try:
                    cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {col_name} {col_def}")
                except sqlite3.OperationalError:
                    pass

        # Create customers table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {CUSTOMERS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                address TEXT,
                date_registered TEXT NOT NULL,
                birthday TEXT,
                is_vip INTEGER DEFAULT 0,
                loyalty_points INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0,
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                notes TEXT
            )
        """)

        # Create donors table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {DONORS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                address TEXT,
                date_registered TEXT NOT NULL,
                total_donations INTEGER DEFAULT 0,
                total_value REAL DEFAULT 0,
                notes TEXT
            )
        """)

        # Create donations table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {DONATIONS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                donor_id INTEGER,
                item_description TEXT NOT NULL,
                category TEXT,
                quantity INTEGER DEFAULT 1,
                estimated_value REAL,
                date_received TEXT NOT NULL,
                receipt_number TEXT,
                donation_drive_id TEXT,
                notes TEXT,
                FOREIGN KEY (donor_id) REFERENCES {DONORS_TABLE}(id)
            )
        """)

        # Create staff table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {STAFF_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                role TEXT DEFAULT 'volunteer',
                date_joined TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                total_hours REAL DEFAULT 0,
                total_sales REAL DEFAULT 0,
                sales_count INTEGER DEFAULT 0
            )
        """)

        # Create gift cards table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {GIFT_CARDS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                initial_balance REAL NOT NULL,
                current_balance REAL NOT NULL,
                date_issued TEXT NOT NULL,
                expiry_date TEXT,
                issued_to INTEGER,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (issued_to) REFERENCES {CUSTOMERS_TABLE}(id)
            )
        """)

        # Create price history table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {PRICE_HISTORY_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                old_price REAL,
                new_price REAL NOT NULL,
                change_date TEXT NOT NULL,
                changed_by TEXT,
                reason TEXT,
                FOREIGN KEY (item_id) REFERENCES {TABLE_NAME}(id)
            )
        """)

        # Create sales table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {SALES_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER,
                customer_id INTEGER,
                staff_id INTEGER,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                discount_applied REAL DEFAULT 0,
                total_amount REAL NOT NULL,
                payment_method TEXT DEFAULT 'cash',
                sale_date TEXT NOT NULL,
                refunded INTEGER DEFAULT 0,
                refund_date TEXT,
                refund_reason TEXT,
                gift_card_id INTEGER,
                loyalty_points_earned INTEGER DEFAULT 0,
                FOREIGN KEY (item_id) REFERENCES {TABLE_NAME}(id),
                FOREIGN KEY (customer_id) REFERENCES {CUSTOMERS_TABLE}(id),
                FOREIGN KEY (staff_id) REFERENCES {STAFF_TABLE}(id)
            )
        """)

        # Create bundles table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {BUNDLES_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                bundle_price REAL NOT NULL,
                item_ids TEXT NOT NULL,
                date_created TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                times_sold INTEGER DEFAULT 0
            )
        """)

        # Create promotions table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {PROMOTIONS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                discount_type TEXT NOT NULL,
                discount_value REAL NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                category TEXT,
                min_purchase REAL DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        """)

        # Create layaway table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {LAYAWAY_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                customer_id INTEGER NOT NULL,
                total_price REAL NOT NULL,
                deposit_paid REAL NOT NULL,
                remaining_balance REAL NOT NULL,
                start_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (item_id) REFERENCES {TABLE_NAME}(id),
                FOREIGN KEY (customer_id) REFERENCES {CUSTOMERS_TABLE}(id)
            )
        """)

        # Create loyalty points log table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {LOYALTY_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                points_change INTEGER NOT NULL,
                reason TEXT,
                transaction_date TEXT NOT NULL,
                sale_id INTEGER,
                FOREIGN KEY (customer_id) REFERENCES {CUSTOMERS_TABLE}(id)
            )
        """)

        # Create archived items table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {ARCHIVED_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_id INTEGER,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                condition TEXT,
                date_added TEXT,
                date_archived TEXT NOT NULL,
                archive_reason TEXT
            )
        """)

        # Create locations table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {LOCATIONS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                address TEXT,
                phone TEXT,
                manager TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)

        # Create shifts table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {SHIFTS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id INTEGER NOT NULL,
                shift_date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                hours_worked REAL,
                notes TEXT,
                FOREIGN KEY (staff_id) REFERENCES {STAFF_TABLE}(id)
            )
        """)

        # Create tasks table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {TASKS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                assigned_to INTEGER,
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'pending',
                due_date TEXT,
                created_date TEXT NOT NULL,
                completed_date TEXT,
                FOREIGN KEY (assigned_to) REFERENCES {STAFF_TABLE}(id)
            )
        """)

        # Create wishlists table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {WISHLISTS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                item_description TEXT NOT NULL,
                category TEXT,
                max_price REAL,
                date_added TEXT NOT NULL,
                notified INTEGER DEFAULT 0,
                FOREIGN KEY (customer_id) REFERENCES {CUSTOMERS_TABLE}(id)
            )
        """)

        # Create feedback table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {FEEDBACK_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                item_id INTEGER,
                rating INTEGER NOT NULL,
                comment TEXT,
                feedback_date TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES {CUSTOMERS_TABLE}(id),
                FOREIGN KEY (item_id) REFERENCES {TABLE_NAME}(id)
            )
        """)

        # Create referrals table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {REFERRALS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,
                referral_date TEXT NOT NULL,
                reward_given INTEGER DEFAULT 0,
                reward_amount REAL DEFAULT 0,
                FOREIGN KEY (referrer_id) REFERENCES {CUSTOMERS_TABLE}(id),
                FOREIGN KEY (referred_id) REFERENCES {CUSTOMERS_TABLE}(id)
            )
        """)

        conn.commit()
        conn.close()
        logger.info("Charity shop database initialized successfully")
        return True

    except sqlite3.Error as e:
        logger.error(f"Error initializing charity shop database: {e}")
        print(f"Database error: {e}")
        return False


def setup_charity_shop_permissions(auth_instance=None) -> None:
    """Setup permissions for the charity shop module."""
    if auth_instance is None:
        auth_instance = auth or get_auth()

    if auth_instance is None:
        logger.warning("No auth instance available for setting up charity shop permissions")
        return

    # Define charity shop permissions
    permissions = [
        'view_charity_shop_stock',
        'add_charity_shop_item',
        'edit_charity_shop_item',
        'delete_charity_shop_item',
        'sell_charity_shop_item',
        'view_charity_shop_reports',
        'manage_charity_shop',
    ]

    # Add permissions to roles
    try:
        if hasattr(auth_instance, 'add_permission_to_role'):
            # Admin gets all permissions
            for perm in permissions:
                try:
                    auth_instance.add_permission_to_role('admin', perm)
                except Exception:
                    pass

            # Staff gets most permissions
            staff_perms = [p for p in permissions if 'delete' not in p]
            for perm in staff_perms:
                try:
                    auth_instance.add_permission_to_role('staff', perm)
                except Exception:
                    pass

            # Students and instructors can view
            for role in ['student', 'instructor']:
                try:
                    auth_instance.add_permission_to_role(role, 'view_charity_shop_stock')
                except Exception:
                    pass

            logger.info("Charity shop permissions setup complete")
    except Exception as e:
        logger.warning(f"Could not setup charity shop permissions: {e}")


# ============================================================================
# Database Operations
# ============================================================================

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


# ============================================================================
# INVENTORY MANAGEMENT FUNCTIONS (10)
# ============================================================================

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


def barcode_scanner_integration(barcode: str) -> Optional[Dict]:
    """Look up item by barcode or create new entry."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"SELECT * FROM {TABLE_NAME} WHERE barcode = ?", (barcode,))
    item = cursor.fetchone()
    conn.close()

    if item:
        return {
            'id': item[0],
            'name': item[1],
            'category': item[2],
            'price': item[3],
            'quantity': item[4],
            'condition': item[5],
            'barcode': barcode
        }
    return None


def set_item_barcode(item_id: int, barcode: str) -> bool:
    """Set barcode for an item."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE {TABLE_NAME} SET barcode = ? WHERE id = ?", (barcode, item_id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error setting barcode: {e}")
        return False


# ============================================================================
# SALES & PRICING FUNCTIONS (10)
# ============================================================================

def apply_discount(item_id: int, discount_type: str, discount_value: float) -> bool:
    """Apply percentage or fixed discount to an item."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(f"SELECT price FROM {TABLE_NAME} WHERE id = ?", (item_id,))
        item = cursor.fetchone()

        if not item:
            conn.close()
            return False

        original_price = item[0]

        if discount_type == 'percent':
            new_price = original_price * (1 - discount_value / 100)
            discount_percent = discount_value
        else:  # fixed
            new_price = max(0, original_price - discount_value)
            discount_percent = (discount_value / original_price) * 100 if original_price > 0 else 0

        # Log price change
        cursor.execute(f"""
            INSERT INTO {PRICE_HISTORY_TABLE} (item_id, old_price, new_price, change_date, reason)
            VALUES (?, ?, ?, ?, ?)
        """, (item_id, original_price, new_price, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              f"Discount applied: {discount_type} {discount_value}"))

        cursor.execute(f"UPDATE {TABLE_NAME} SET price = ?, discount_percent = ? WHERE id = ?",
                      (new_price, discount_percent, item_id))

        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error applying discount: {e}")
        return False


def create_sale_bundle(name: str, description: str, item_ids: List[int], bundle_price: float) -> Optional[int]:
    """Bundle multiple items at special price."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(f"""
            INSERT INTO {BUNDLES_TABLE} (name, description, bundle_price, item_ids, date_created, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (name, description, bundle_price, json.dumps(item_ids),
              datetime.now().strftime("%Y-%m-%d")))

        bundle_id = cursor.lastrowid
        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_create('charity_shop_bundle', bundle_id=bundle_id, name=name, items=len(item_ids))

        return bundle_id
    except sqlite3.Error as e:
        logger.error(f"Error creating bundle: {e}")
        return None


def get_bundles(active_only: bool = True) -> List[Dict]:
    """Get all bundles."""
    conn = get_connection()
    cursor = conn.cursor()

    query = f"SELECT * FROM {BUNDLES_TABLE}"
    if active_only:
        query += " WHERE is_active = 1"

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    bundles = []
    for row in rows:
        bundles.append({
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'bundle_price': row[3],
            'item_ids': json.loads(row[4]) if row[4] else [],
            'date_created': row[5],
            'is_active': row[6],
            'times_sold': row[7]
        })
    return bundles


def price_history_tracker(item_id: int) -> List[Dict]:
    """Track price changes over time for an item."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT old_price, new_price, change_date, changed_by, reason
        FROM {PRICE_HISTORY_TABLE}
        WHERE item_id = ?
        ORDER BY change_date DESC
    """, (item_id,))

    history = []
    for row in cursor.fetchall():
        history.append({
            'old_price': row[0],
            'new_price': row[1],
            'change_date': row[2],
            'changed_by': row[3],
            'reason': row[4]
        })

    conn.close()
    return history


def dynamic_pricing_suggestions(item_id: int) -> Dict:
    """Suggest prices based on demand/condition."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"SELECT name, category, price, condition, quantity, date_added FROM {TABLE_NAME} WHERE id = ?",
                  (item_id,))
    item = cursor.fetchone()

    if not item:
        conn.close()
        return {}

    name, category, current_price, condition, qty, date_added = item

    # Get average price for category
    cursor.execute(f"SELECT AVG(price) FROM {TABLE_NAME} WHERE category = ? AND sold = 0",
                  (category,))
    avg_category_price = cursor.fetchone()[0] or current_price

    # Get sales velocity for this item
    cursor.execute(f"SELECT sold_quantity FROM {TABLE_NAME} WHERE id = ?", (item_id,))
    sold_qty = cursor.fetchone()[0] or 0

    # Calculate days in stock
    try:
        date_obj = datetime.strptime(date_added, "%Y-%m-%d")
        days_in_stock = (datetime.now() - date_obj).days
    except:
        days_in_stock = 0

    conn.close()

    # Condition multipliers
    condition_mult = {'New': 1.2, 'Excellent': 1.1, 'Good': 1.0, 'Fair': 0.8, 'Poor': 0.6}

    # Calculate suggested price
    base_suggestion = avg_category_price * condition_mult.get(condition, 1.0)

    # Adjust for slow-moving items
    if days_in_stock > 60 and sold_qty == 0:
        base_suggestion *= 0.85  # 15% reduction for slow movers
    elif days_in_stock > 90:
        base_suggestion *= 0.75  # 25% reduction

    return {
        'current_price': current_price,
        'suggested_price': round(base_suggestion, 2),
        'category_average': round(avg_category_price, 2),
        'days_in_stock': days_in_stock,
        'condition': condition,
        'reason': 'Based on category average, condition, and time in stock'
    }


def create_promotional_event(name: str, discount_type: str, discount_value: float,
                            start_date: str, end_date: str, category: str = None,
                            min_purchase: float = 0) -> Optional[int]:
    """Set up special sales events."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(f"""
            INSERT INTO {PROMOTIONS_TABLE}
            (name, discount_type, discount_value, start_date, end_date, category, min_purchase, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (name, discount_type, discount_value, start_date, end_date, category, min_purchase))

        promo_id = cursor.lastrowid
        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_create('charity_shop_promotion', promo_id=promo_id, name=name)

        return promo_id
    except sqlite3.Error as e:
        logger.error(f"Error creating promotion: {e}")
        return None


def get_active_promotions() -> List[Dict]:
    """Get currently active promotions."""
    conn = get_connection()
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute(f"""
        SELECT * FROM {PROMOTIONS_TABLE}
        WHERE is_active = 1 AND start_date <= ? AND end_date >= ?
    """, (today, today))

    promos = []
    for row in cursor.fetchall():
        promos.append({
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'discount_type': row[3],
            'discount_value': row[4],
            'start_date': row[5],
            'end_date': row[6],
            'category': row[7],
            'min_purchase': row[8]
        })

    conn.close()
    return promos


def process_refund(sale_id: int, reason: str) -> bool:
    """Handle returns and refunds."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get sale info
        cursor.execute(f"SELECT item_id, quantity, total_amount, customer_id FROM {SALES_TABLE} WHERE id = ?",
                      (sale_id,))
        sale = cursor.fetchone()

        if not sale:
            conn.close()
            return False

        item_id, qty, amount, customer_id = sale

        # Mark sale as refunded
        cursor.execute(f"""
            UPDATE {SALES_TABLE}
            SET refunded = 1, refund_date = ?, refund_reason = ?
            WHERE id = ?
        """, (datetime.now().strftime("%Y-%m-%d"), reason, sale_id))

        # Restore item quantity
        if item_id:
            cursor.execute(f"""
                UPDATE {TABLE_NAME}
                SET quantity = quantity + ?, sold_quantity = sold_quantity - ?, sold = 0
                WHERE id = ?
            """, (qty, qty, item_id))

        # Deduct loyalty points if applicable
        if customer_id:
            points_to_deduct = int(amount * LOYALTY_POINTS_PER_POUND)
            cursor.execute(f"""
                UPDATE {CUSTOMERS_TABLE}
                SET loyalty_points = MAX(0, loyalty_points - ?), total_spent = total_spent - ?
                WHERE id = ?
            """, (points_to_deduct, amount, customer_id))

        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('refund', 'charity_shop_sale', sale_id=sale_id, amount=amount, reason=reason)

        return True
    except sqlite3.Error as e:
        logger.error(f"Error processing refund: {e}")
        return False


def layaway_system(item_id: int, customer_id: int, deposit: float, due_days: int = 30) -> Optional[int]:
    """Hold items for customers with deposits."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get item price
        cursor.execute(f"SELECT price, quantity FROM {TABLE_NAME} WHERE id = ?", (item_id,))
        item = cursor.fetchone()

        if not item or item[1] <= 0:
            conn.close()
            return None

        total_price = item[0]
        remaining = total_price - deposit
        due_date = (datetime.now() + timedelta(days=due_days)).strftime("%Y-%m-%d")

        cursor.execute(f"""
            INSERT INTO {LAYAWAY_TABLE}
            (item_id, customer_id, total_price, deposit_paid, remaining_balance, start_date, due_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
        """, (item_id, customer_id, total_price, deposit, remaining,
              datetime.now().strftime("%Y-%m-%d"), due_date))

        layaway_id = cursor.lastrowid

        # Reserve item (reduce available quantity)
        cursor.execute(f"UPDATE {TABLE_NAME} SET quantity = quantity - 1 WHERE id = ?", (item_id,))

        conn.commit()
        conn.close()
        return layaway_id
    except sqlite3.Error as e:
        logger.error(f"Error creating layaway: {e}")
        return None


def get_layaways(customer_id: int = None, status: str = 'active') -> List[Dict]:
    """Get layaway records."""
    conn = get_connection()
    cursor = conn.cursor()

    query = f"""
        SELECT l.*, s.name as item_name, c.name as customer_name
        FROM {LAYAWAY_TABLE} l
        LEFT JOIN {TABLE_NAME} s ON l.item_id = s.id
        LEFT JOIN {CUSTOMERS_TABLE} c ON l.customer_id = c.id
        WHERE l.status = ?
    """
    params = [status]

    if customer_id:
        query += " AND l.customer_id = ?"
        params.append(customer_id)

    cursor.execute(query, params)

    layaways = []
    for row in cursor.fetchall():
        layaways.append({
            'id': row[0],
            'item_id': row[1],
            'customer_id': row[2],
            'total_price': row[3],
            'deposit_paid': row[4],
            'remaining_balance': row[5],
            'start_date': row[6],
            'due_date': row[7],
            'status': row[8],
            'item_name': row[9] if len(row) > 9 else '',
            'customer_name': row[10] if len(row) > 10 else ''
        })

    conn.close()
    return layaways


def gift_card_management(action: str, **kwargs) -> Any:
    """Issue and redeem gift cards."""
    conn = get_connection()
    cursor = conn.cursor()

    if action == 'issue':
        amount = kwargs.get('amount', 0)
        customer_id = kwargs.get('customer_id')
        expiry_days = kwargs.get('expiry_days', 365)

        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        expiry_date = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d")

        cursor.execute(f"""
            INSERT INTO {GIFT_CARDS_TABLE}
            (code, initial_balance, current_balance, date_issued, expiry_date, issued_to, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (code, amount, amount, datetime.now().strftime("%Y-%m-%d"), expiry_date, customer_id))

        conn.commit()
        conn.close()
        return {'code': code, 'balance': amount, 'expiry': expiry_date}

    elif action == 'check_balance':
        code = kwargs.get('code', '')
        cursor.execute(f"SELECT current_balance, expiry_date, is_active FROM {GIFT_CARDS_TABLE} WHERE code = ?",
                      (code,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return {'balance': result[0], 'expiry': result[1], 'active': result[2]}
        return None

    elif action == 'redeem':
        code = kwargs.get('code', '')
        amount = kwargs.get('amount', 0)

        cursor.execute(f"SELECT id, current_balance, is_active FROM {GIFT_CARDS_TABLE} WHERE code = ?",
                      (code,))
        card = cursor.fetchone()

        if not card or not card[2] or card[1] < amount:
            conn.close()
            return False

        new_balance = card[1] - amount
        cursor.execute(f"UPDATE {GIFT_CARDS_TABLE} SET current_balance = ? WHERE id = ?",
                      (new_balance, card[0]))

        conn.commit()
        conn.close()
        return {'new_balance': new_balance, 'redeemed': amount}

    conn.close()
    return None


def loyalty_points_system(customer_id: int, action: str, **kwargs) -> Any:
    """Track customer purchases for rewards."""
    conn = get_connection()
    cursor = conn.cursor()

    if action == 'check':
        cursor.execute(f"SELECT loyalty_points FROM {CUSTOMERS_TABLE} WHERE id = ?", (customer_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0

    elif action == 'add':
        points = kwargs.get('points', 0)
        reason = kwargs.get('reason', 'Purchase')
        sale_id = kwargs.get('sale_id')

        cursor.execute(f"UPDATE {CUSTOMERS_TABLE} SET loyalty_points = loyalty_points + ? WHERE id = ?",
                      (points, customer_id))

        cursor.execute(f"""
            INSERT INTO {LOYALTY_TABLE} (customer_id, points_change, reason, transaction_date, sale_id)
            VALUES (?, ?, ?, ?, ?)
        """, (customer_id, points, reason, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sale_id))

        conn.commit()
        conn.close()
        return True

    elif action == 'redeem':
        points = kwargs.get('points', 0)

        cursor.execute(f"SELECT loyalty_points FROM {CUSTOMERS_TABLE} WHERE id = ?", (customer_id,))
        current = cursor.fetchone()

        if not current or current[0] < points:
            conn.close()
            return False

        cursor.execute(f"UPDATE {CUSTOMERS_TABLE} SET loyalty_points = loyalty_points - ? WHERE id = ?",
                      (points, customer_id))

        cursor.execute(f"""
            INSERT INTO {LOYALTY_TABLE} (customer_id, points_change, reason, transaction_date)
            VALUES (?, ?, ?, ?)
        """, (customer_id, -points, 'Redemption', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        conn.commit()
        conn.close()
        return True

    conn.close()
    return None


def calculate_profit_margin(item_id: int = None, category: str = None) -> Dict:
    """Show profit after donation costs."""
    conn = get_connection()
    cursor = conn.cursor()

    if item_id:
        cursor.execute(f"""
            SELECT name, price, donation_cost, sold_quantity,
                   (price * sold_quantity) as revenue,
                   (price - COALESCE(donation_cost, 0)) * sold_quantity as profit
            FROM {TABLE_NAME}
            WHERE id = ? AND sold_quantity > 0
        """, (item_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'name': row[0],
                'price': row[1],
                'donation_cost': row[2] or 0,
                'quantity_sold': row[3],
                'revenue': row[4],
                'profit': row[5],
                'margin_percent': (row[5] / row[4] * 100) if row[4] > 0 else 0
            }
        return {}

    else:
        query = f"""
            SELECT SUM(price * sold_quantity) as total_revenue,
                   SUM((price - COALESCE(donation_cost, 0)) * sold_quantity) as total_profit
            FROM {TABLE_NAME}
            WHERE sold_quantity > 0
        """
        if category:
            query = query.replace("WHERE", f"WHERE category = '{category}' AND")

        cursor.execute(query)
        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            return {
                'total_revenue': row[0],
                'total_profit': row[1],
                'margin_percent': (row[1] / row[0] * 100) if row[0] > 0 else 0
            }
        return {'total_revenue': 0, 'total_profit': 0, 'margin_percent': 0}


# ============================================================================
# REPORTING & ANALYTICS FUNCTIONS (10)
# ============================================================================

def generate_daily_sales_report(date: str = None) -> Dict:
    """Daily sales summary."""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT COUNT(*), SUM(total_amount), SUM(quantity)
        FROM {SALES_TABLE}
        WHERE DATE(sale_date) = ? AND refunded = 0
    """, (date,))
    row = cursor.fetchone()

    cursor.execute(f"""
        SELECT payment_method, COUNT(*), SUM(total_amount)
        FROM {SALES_TABLE}
        WHERE DATE(sale_date) = ? AND refunded = 0
        GROUP BY payment_method
    """, (date,))
    by_payment = cursor.fetchall()

    conn.close()

    return {
        'date': date,
        'total_transactions': row[0] or 0,
        'total_revenue': row[1] or 0,
        'total_items_sold': row[2] or 0,
        'by_payment_method': [{'method': r[0], 'count': r[1], 'amount': r[2]} for r in by_payment]
    }


def generate_weekly_sales_report(start_date: str = None) -> Dict:
    """Weekly performance report."""
    if not start_date:
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    end_date = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT DATE(sale_date) as day, COUNT(*), SUM(total_amount), SUM(quantity)
        FROM {SALES_TABLE}
        WHERE DATE(sale_date) >= ? AND DATE(sale_date) < ? AND refunded = 0
        GROUP BY DATE(sale_date)
        ORDER BY day
    """, (start_date, end_date))
    daily = cursor.fetchall()

    cursor.execute(f"""
        SELECT COUNT(*), SUM(total_amount), SUM(quantity)
        FROM {SALES_TABLE}
        WHERE DATE(sale_date) >= ? AND DATE(sale_date) < ? AND refunded = 0
    """, (start_date, end_date))
    totals = cursor.fetchone()

    conn.close()

    return {
        'start_date': start_date,
        'end_date': end_date,
        'total_transactions': totals[0] or 0,
        'total_revenue': totals[1] or 0,
        'total_items_sold': totals[2] or 0,
        'daily_breakdown': [{'date': d[0], 'transactions': d[1], 'revenue': d[2], 'items': d[3]} for d in daily]
    }


def generate_monthly_sales_report(year: int = None, month: int = None) -> Dict:
    """Monthly trends report."""
    if not year:
        year = datetime.now().year
    if not month:
        month = datetime.now().month

    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT COUNT(*), SUM(total_amount), SUM(quantity), AVG(total_amount)
        FROM {SALES_TABLE}
        WHERE DATE(sale_date) >= ? AND DATE(sale_date) < ? AND refunded = 0
    """, (start_date, end_date))
    totals = cursor.fetchone()

    cursor.execute(f"""
        SELECT strftime('%W', sale_date) as week, COUNT(*), SUM(total_amount)
        FROM {SALES_TABLE}
        WHERE DATE(sale_date) >= ? AND DATE(sale_date) < ? AND refunded = 0
        GROUP BY week
    """, (start_date, end_date))
    weekly = cursor.fetchall()

    conn.close()

    return {
        'year': year,
        'month': month,
        'total_transactions': totals[0] or 0,
        'total_revenue': totals[1] or 0,
        'total_items_sold': totals[2] or 0,
        'average_transaction': totals[3] or 0,
        'weekly_breakdown': [{'week': w[0], 'transactions': w[1], 'revenue': w[2]} for w in weekly]
    }


def best_selling_items_report(limit: int = 10, period_days: int = 30) -> List[Dict]:
    """Top performing items."""
    conn = get_connection()
    cursor = conn.cursor()

    start_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")

    cursor.execute(f"""
        SELECT s.name, s.category, SUM(sl.quantity) as qty_sold,
               SUM(sl.total_amount) as revenue, s.price
        FROM {SALES_TABLE} sl
        JOIN {TABLE_NAME} s ON sl.item_id = s.id
        WHERE DATE(sl.sale_date) >= ? AND sl.refunded = 0
        GROUP BY sl.item_id
        ORDER BY qty_sold DESC
        LIMIT ?
    """, (start_date, limit))

    results = []
    for row in cursor.fetchall():
        results.append({
            'name': row[0],
            'category': row[1],
            'quantity_sold': row[2],
            'revenue': row[3],
            'unit_price': row[4]
        })

    conn.close()
    return results


def slow_moving_items_report(days_threshold: int = 60) -> List[Dict]:
    """Items not selling."""
    conn = get_connection()
    cursor = conn.cursor()

    cutoff_date = (datetime.now() - timedelta(days=days_threshold)).strftime("%Y-%m-%d")

    cursor.execute(f"""
        SELECT id, name, category, price, quantity, date_added,
               julianday('now') - julianday(date_added) as days_in_stock
        FROM {TABLE_NAME}
        WHERE sold = 0 AND quantity > 0 AND date_added <= ?
        ORDER BY date_added ASC
    """, (cutoff_date,))

    results = []
    for row in cursor.fetchall():
        results.append({
            'id': row[0],
            'name': row[1],
            'category': row[2],
            'price': row[3],
            'quantity': row[4],
            'date_added': row[5],
            'days_in_stock': int(row[6])
        })

    conn.close()
    return results


def revenue_trend_analysis(period: str = 'monthly', num_periods: int = 12) -> List[Dict]:
    """Revenue over time analysis."""
    conn = get_connection()
    cursor = conn.cursor()

    if period == 'daily':
        group_format = '%Y-%m-%d'
        days_back = num_periods
    elif period == 'weekly':
        group_format = '%Y-W%W'
        days_back = num_periods * 7
    else:  # monthly
        group_format = '%Y-%m'
        days_back = num_periods * 30

    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    cursor.execute(f"""
        SELECT strftime(?, sale_date) as period,
               COUNT(*) as transactions,
               SUM(total_amount) as revenue,
               SUM(quantity) as items
        FROM {SALES_TABLE}
        WHERE DATE(sale_date) >= ? AND refunded = 0
        GROUP BY period
        ORDER BY period
    """, (group_format, start_date))

    results = []
    for row in cursor.fetchall():
        results.append({
            'period': row[0],
            'transactions': row[1],
            'revenue': row[2],
            'items_sold': row[3]
        })

    conn.close()
    return results


def category_performance_comparison(period_days: int = 30) -> List[Dict]:
    """Compare category sales."""
    conn = get_connection()
    cursor = conn.cursor()

    start_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")

    cursor.execute(f"""
        SELECT s.category,
               COUNT(DISTINCT sl.id) as transactions,
               SUM(sl.quantity) as items_sold,
               SUM(sl.total_amount) as revenue,
               AVG(sl.total_amount) as avg_sale
        FROM {SALES_TABLE} sl
        JOIN {TABLE_NAME} s ON sl.item_id = s.id
        WHERE DATE(sl.sale_date) >= ? AND sl.refunded = 0
        GROUP BY s.category
        ORDER BY revenue DESC
    """, (start_date,))

    results = []
    for row in cursor.fetchall():
        results.append({
            'category': row[0],
            'transactions': row[1],
            'items_sold': row[2],
            'revenue': row[3],
            'average_sale': row[4]
        })

    conn.close()
    return results


def seasonal_trends_report() -> Dict:
    """Identify seasonal patterns."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT strftime('%m', sale_date) as month,
               COUNT(*) as transactions,
               SUM(total_amount) as revenue
        FROM {SALES_TABLE}
        WHERE refunded = 0
        GROUP BY month
        ORDER BY month
    """)

    monthly = {}
    for row in cursor.fetchall():
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        month_idx = int(row[0]) - 1
        monthly[month_names[month_idx]] = {
            'transactions': row[1],
            'revenue': row[2]
        }

    # By day of week
    cursor.execute(f"""
        SELECT strftime('%w', sale_date) as day,
               COUNT(*) as transactions,
               SUM(total_amount) as revenue
        FROM {SALES_TABLE}
        WHERE refunded = 0
        GROUP BY day
    """)

    day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    daily = {}
    for row in cursor.fetchall():
        daily[day_names[int(row[0])]] = {
            'transactions': row[1],
            'revenue': row[2]
        }

    conn.close()

    return {
        'by_month': monthly,
        'by_day_of_week': daily
    }


def donor_contribution_report(period_days: int = 365) -> List[Dict]:
    """Track donations by source."""
    conn = get_connection()
    cursor = conn.cursor()

    start_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")

    cursor.execute(f"""
        SELECT d.name, d.email,
               COUNT(dn.id) as donation_count,
               SUM(dn.quantity) as items_donated,
               SUM(dn.estimated_value) as total_value
        FROM {DONORS_TABLE} d
        LEFT JOIN {DONATIONS_TABLE} dn ON d.id = dn.donor_id
        WHERE dn.date_received >= ?
        GROUP BY d.id
        ORDER BY total_value DESC
    """, (start_date,))

    results = []
    for row in cursor.fetchall():
        results.append({
            'name': row[0],
            'email': row[1],
            'donation_count': row[2],
            'items_donated': row[3],
            'total_value': row[4]
        })

    conn.close()
    return results


def tax_deduction_report(year: int = None) -> List[Dict]:
    """Generate donation receipts for tax purposes."""
    if not year:
        year = datetime.now().year

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT d.id, d.name, d.email, d.address,
               SUM(dn.estimated_value) as total_value,
               COUNT(dn.id) as donation_count
        FROM {DONORS_TABLE} d
        JOIN {DONATIONS_TABLE} dn ON d.id = dn.donor_id
        WHERE strftime('%Y', dn.date_received) = ?
        GROUP BY d.id
        ORDER BY d.name
    """, (str(year),))

    results = []
    for row in cursor.fetchall():
        results.append({
            'donor_id': row[0],
            'name': row[1],
            'email': row[2],
            'address': row[3],
            'total_deductible': row[4],
            'donation_count': row[5],
            'tax_year': year
        })

    conn.close()
    return results


# ============================================================================
# CUSTOMER MANAGEMENT FUNCTIONS (8)
# ============================================================================

def register_customer(name: str, email: str = None, phone: str = None,
                     address: str = None, birthday: str = None) -> Optional[int]:
    """Create customer profiles."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Generate referral code
        referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        cursor.execute(f"""
            INSERT INTO {CUSTOMERS_TABLE}
            (name, email, phone, address, birthday, date_registered, referral_code)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, email, phone, address, birthday,
              datetime.now().strftime("%Y-%m-%d"), referral_code))

        customer_id = cursor.lastrowid
        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_create('charity_shop_customer', customer_id=customer_id, name=name)

        return customer_id
    except sqlite3.Error as e:
        logger.error(f"Error registering customer: {e}")
        return None


def get_customer(customer_id: int) -> Optional[Dict]:
    """Get customer details."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"SELECT * FROM {CUSTOMERS_TABLE} WHERE id = ?", (customer_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            'id': row[0],
            'name': row[1],
            'email': row[2],
            'phone': row[3],
            'address': row[4],
            'date_registered': row[5],
            'birthday': row[6],
            'is_vip': row[7],
            'loyalty_points': row[8],
            'total_spent': row[9],
            'referral_code': row[10],
            'referred_by': row[11],
            'notes': row[12]
        }
    return None


def customer_purchase_history(customer_id: int) -> List[Dict]:
    """View customer transactions."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT sl.id, sl.sale_date, sl.quantity, sl.total_amount,
               sl.payment_method, sl.refunded, s.name as item_name
        FROM {SALES_TABLE} sl
        LEFT JOIN {TABLE_NAME} s ON sl.item_id = s.id
        WHERE sl.customer_id = ?
        ORDER BY sl.sale_date DESC
    """, (customer_id,))

    history = []
    for row in cursor.fetchall():
        history.append({
            'sale_id': row[0],
            'date': row[1],
            'quantity': row[2],
            'amount': row[3],
            'payment_method': row[4],
            'refunded': row[5],
            'item_name': row[6]
        })

    conn.close()
    return history


def customer_wishlist(customer_id: int, action: str, **kwargs) -> Any:
    """Save items customers are interested in."""
    conn = get_connection()
    cursor = conn.cursor()

    if action == 'add':
        description = kwargs.get('description', '')
        category = kwargs.get('category')
        max_price = kwargs.get('max_price')

        cursor.execute(f"""
            INSERT INTO {WISHLISTS_TABLE} (customer_id, item_description, category, max_price, date_added)
            VALUES (?, ?, ?, ?, ?)
        """, (customer_id, description, category, max_price, datetime.now().strftime("%Y-%m-%d")))

        conn.commit()
        conn.close()
        return True

    elif action == 'view':
        cursor.execute(f"SELECT * FROM {WISHLISTS_TABLE} WHERE customer_id = ?", (customer_id,))
        items = []
        for row in cursor.fetchall():
            items.append({
                'id': row[0],
                'description': row[2],
                'category': row[3],
                'max_price': row[4],
                'date_added': row[5],
                'notified': row[6]
            })
        conn.close()
        return items

    elif action == 'remove':
        wishlist_id = kwargs.get('wishlist_id')
        cursor.execute(f"DELETE FROM {WISHLISTS_TABLE} WHERE id = ? AND customer_id = ?",
                      (wishlist_id, customer_id))
        conn.commit()
        conn.close()
        return True

    conn.close()
    return None


def send_customer_notifications(customer_ids: List[int], subject: str, message: str,
                               method: str = 'email') -> int:
    """Email/SMS about new items (returns count of notifications sent)."""
    sent_count = 0
    conn = get_connection()
    cursor = conn.cursor()

    for cid in customer_ids:
        cursor.execute(f"SELECT email, phone, name FROM {CUSTOMERS_TABLE} WHERE id = ?", (cid,))
        customer = cursor.fetchone()

        if customer:
            # In production, this would actually send emails/SMS
            # For now, we just log the notification
            if ACTIVITY_LOGGER_AVAILABLE:
                log_activity('notification', 'charity_shop_customer',
                            customer_id=cid, method=method, subject=subject)
            sent_count += 1

    conn.close()
    return sent_count


def customer_feedback_system(action: str, **kwargs) -> Any:
    """Collect reviews and ratings."""
    conn = get_connection()
    cursor = conn.cursor()

    if action == 'submit':
        customer_id = kwargs.get('customer_id')
        item_id = kwargs.get('item_id')
        rating = kwargs.get('rating', 5)
        comment = kwargs.get('comment', '')

        cursor.execute(f"""
            INSERT INTO {FEEDBACK_TABLE} (customer_id, item_id, rating, comment, feedback_date)
            VALUES (?, ?, ?, ?, ?)
        """, (customer_id, item_id, rating, comment, datetime.now().strftime("%Y-%m-%d")))

        conn.commit()
        conn.close()
        return True

    elif action == 'view_item':
        item_id = kwargs.get('item_id')
        cursor.execute(f"""
            SELECT f.*, c.name as customer_name
            FROM {FEEDBACK_TABLE} f
            LEFT JOIN {CUSTOMERS_TABLE} c ON f.customer_id = c.id
            WHERE f.item_id = ?
            ORDER BY f.feedback_date DESC
        """, (item_id,))

        feedback = []
        for row in cursor.fetchall():
            feedback.append({
                'id': row[0],
                'rating': row[3],
                'comment': row[4],
                'date': row[5],
                'customer_name': row[6] if len(row) > 6 else 'Anonymous'
            })
        conn.close()
        return feedback

    elif action == 'average':
        item_id = kwargs.get('item_id')
        cursor.execute(f"SELECT AVG(rating), COUNT(*) FROM {FEEDBACK_TABLE} WHERE item_id = ?",
                      (item_id,))
        row = cursor.fetchone()
        conn.close()
        return {'average': row[0] or 0, 'count': row[1]}

    conn.close()
    return None


def vip_customer_management(action: str, customer_id: int = None) -> Any:
    """Track frequent shoppers."""
    conn = get_connection()
    cursor = conn.cursor()

    if action == 'make_vip':
        cursor.execute(f"UPDATE {CUSTOMERS_TABLE} SET is_vip = 1 WHERE id = ?", (customer_id,))
        conn.commit()
        conn.close()
        return True

    elif action == 'remove_vip':
        cursor.execute(f"UPDATE {CUSTOMERS_TABLE} SET is_vip = 0 WHERE id = ?", (customer_id,))
        conn.commit()
        conn.close()
        return True

    elif action == 'list_vips':
        cursor.execute(f"""
            SELECT id, name, email, total_spent, loyalty_points
            FROM {CUSTOMERS_TABLE}
            WHERE is_vip = 1
            ORDER BY total_spent DESC
        """)
        vips = []
        for row in cursor.fetchall():
            vips.append({
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'total_spent': row[3],
                'loyalty_points': row[4]
            })
        conn.close()
        return vips

    elif action == 'auto_promote':
        # Auto-promote customers who spent over threshold
        threshold = 500  # £500 total spent
        cursor.execute(f"""
            UPDATE {CUSTOMERS_TABLE}
            SET is_vip = 1
            WHERE total_spent >= ? AND is_vip = 0
        """, (threshold,))
        promoted = cursor.rowcount
        conn.commit()
        conn.close()
        return promoted

    conn.close()
    return None


def customer_birthday_discounts() -> List[Dict]:
    """Get customers with birthdays this month for special offers."""
    conn = get_connection()
    cursor = conn.cursor()

    current_month = datetime.now().strftime("%m")

    cursor.execute(f"""
        SELECT id, name, email, birthday, loyalty_points
        FROM {CUSTOMERS_TABLE}
        WHERE strftime('%m', birthday) = ?
    """, (current_month,))

    customers = []
    for row in cursor.fetchall():
        customers.append({
            'id': row[0],
            'name': row[1],
            'email': row[2],
            'birthday': row[3],
            'loyalty_points': row[4]
        })

    conn.close()
    return customers


def customer_referral_program(referrer_code: str, new_customer_id: int, reward_points: int = 100) -> bool:
    """Reward customer referrals."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Find referrer by code
        cursor.execute(f"SELECT id FROM {CUSTOMERS_TABLE} WHERE referral_code = ?", (referrer_code,))
        referrer = cursor.fetchone()

        if not referrer:
            conn.close()
            return False

        referrer_id = referrer[0]

        # Update new customer's referred_by
        cursor.execute(f"UPDATE {CUSTOMERS_TABLE} SET referred_by = ? WHERE id = ?",
                      (referrer_id, new_customer_id))

        # Record referral
        cursor.execute(f"""
            INSERT INTO {REFERRALS_TABLE} (referrer_id, referred_id, referral_date, reward_given, reward_amount)
            VALUES (?, ?, ?, 1, ?)
        """, (referrer_id, new_customer_id, datetime.now().strftime("%Y-%m-%d"), reward_points))

        # Award points to referrer
        cursor.execute(f"UPDATE {CUSTOMERS_TABLE} SET loyalty_points = loyalty_points + ? WHERE id = ?",
                      (reward_points, referrer_id))

        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error processing referral: {e}")
        return False


# ============================================================================
# DONATION MANAGEMENT FUNCTIONS (6)
# ============================================================================

def record_donation(donor_id: int, item_description: str, category: str = None,
                   quantity: int = 1, estimated_value: float = None,
                   donation_drive_id: str = None, notes: str = None) -> Optional[int]:
    """Log donated items with donor info."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        receipt_number = f"DON-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

        cursor.execute(f"""
            INSERT INTO {DONATIONS_TABLE}
            (donor_id, item_description, category, quantity, estimated_value,
             date_received, receipt_number, donation_drive_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (donor_id, item_description, category, quantity, estimated_value,
              datetime.now().strftime("%Y-%m-%d"), receipt_number, donation_drive_id, notes))

        donation_id = cursor.lastrowid

        # Update donor totals
        cursor.execute(f"""
            UPDATE {DONORS_TABLE}
            SET total_donations = total_donations + 1,
                total_value = total_value + COALESCE(?, 0)
            WHERE id = ?
        """, (estimated_value, donor_id))

        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_create('charity_shop_donation', donation_id=donation_id,
                       donor_id=donor_id, description=item_description)

        return donation_id
    except sqlite3.Error as e:
        logger.error(f"Error recording donation: {e}")
        return None


def generate_donation_receipt(donation_id: int) -> Optional[Dict]:
    """Create tax receipts for donors."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT dn.*, d.name, d.email, d.address
        FROM {DONATIONS_TABLE} dn
        JOIN {DONORS_TABLE} d ON dn.donor_id = d.id
        WHERE dn.id = ?
    """, (donation_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        'receipt_number': row[7],
        'date': row[6],
        'donor_name': row[10],
        'donor_email': row[11],
        'donor_address': row[12],
        'item_description': row[2],
        'category': row[3],
        'quantity': row[4],
        'estimated_value': row[5],
        'organization': 'University Charity Shop',
        'tax_id': 'XX-XXXXXXX',  # Would be real tax ID
        'statement': 'This receipt confirms that the above items were donated. '
                    'No goods or services were provided in exchange for this donation.'
    }


def donor_database(action: str, **kwargs) -> Any:
    """Track donor information and history."""
    conn = get_connection()
    cursor = conn.cursor()

    if action == 'add':
        name = kwargs.get('name')
        email = kwargs.get('email')
        phone = kwargs.get('phone')
        address = kwargs.get('address')
        notes = kwargs.get('notes')

        cursor.execute(f"""
            INSERT INTO {DONORS_TABLE} (name, email, phone, address, date_registered, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, email, phone, address, datetime.now().strftime("%Y-%m-%d"), notes))

        donor_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return donor_id

    elif action == 'get':
        donor_id = kwargs.get('donor_id')
        cursor.execute(f"SELECT * FROM {DONORS_TABLE} WHERE id = ?", (donor_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'phone': row[3],
                'address': row[4],
                'date_registered': row[5],
                'total_donations': row[6],
                'total_value': row[7],
                'notes': row[8]
            }
        return None

    elif action == 'search':
        search_term = kwargs.get('term', '')
        cursor.execute(f"""
            SELECT * FROM {DONORS_TABLE}
            WHERE name LIKE ? OR email LIKE ?
        """, (f"%{search_term}%", f"%{search_term}%"))

        donors = []
        for row in cursor.fetchall():
            donors.append({
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'total_donations': row[6],
                'total_value': row[7]
            })
        conn.close()
        return donors

    elif action == 'list':
        cursor.execute(f"SELECT * FROM {DONORS_TABLE} ORDER BY name")
        donors = []
        for row in cursor.fetchall():
            donors.append({
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'total_donations': row[6],
                'total_value': row[7]
            })
        conn.close()
        return donors

    conn.close()
    return None


def donation_value_estimator(category: str, condition: str, description: str = "") -> float:
    """Estimate value for tax purposes based on category and condition."""
    # Base values by category (in GBP)
    base_values = {
        'Books': 3.00,
        'Clothing': 8.00,
        'Electronics': 25.00,
        'Furniture': 50.00,
        'Homeware': 10.00,
        'Toys': 5.00,
        'Music/DVDs': 2.00,
        'Accessories': 7.00,
        'Sports': 15.00,
        'Other': 5.00
    }

    # Condition multipliers
    condition_mult = {
        'New': 1.5,
        'Excellent': 1.2,
        'Good': 1.0,
        'Fair': 0.6,
        'Poor': 0.3
    }

    base = base_values.get(category, 5.00)
    multiplier = condition_mult.get(condition, 1.0)

    return round(base * multiplier, 2)


def donation_drive_tracker(action: str, **kwargs) -> Any:
    """Manage collection events."""
    # Store drives in a simple format within donations table using donation_drive_id
    conn = get_connection()
    cursor = conn.cursor()

    if action == 'summary':
        drive_id = kwargs.get('drive_id')

        cursor.execute(f"""
            SELECT COUNT(*) as donations,
                   SUM(quantity) as items,
                   SUM(estimated_value) as value
            FROM {DONATIONS_TABLE}
            WHERE donation_drive_id = ?
        """, (drive_id,))

        row = cursor.fetchone()
        conn.close()

        return {
            'drive_id': drive_id,
            'total_donations': row[0] or 0,
            'total_items': row[1] or 0,
            'total_value': row[2] or 0
        }

    elif action == 'list_drives':
        cursor.execute(f"""
            SELECT DISTINCT donation_drive_id,
                   COUNT(*) as donations,
                   SUM(estimated_value) as value,
                   MIN(date_received) as start_date,
                   MAX(date_received) as end_date
            FROM {DONATIONS_TABLE}
            WHERE donation_drive_id IS NOT NULL
            GROUP BY donation_drive_id
        """)

        drives = []
        for row in cursor.fetchall():
            drives.append({
                'drive_id': row[0],
                'donations': row[1],
                'total_value': row[2],
                'start_date': row[3],
                'end_date': row[4]
            })
        conn.close()
        return drives

    conn.close()
    return None


def thank_you_letter_generator(donor_id: int, year: int = None) -> Dict:
    """Generate automated donor appreciation letter."""
    if not year:
        year = datetime.now().year

    conn = get_connection()
    cursor = conn.cursor()

    # Get donor info
    cursor.execute(f"SELECT name, email, address FROM {DONORS_TABLE} WHERE id = ?", (donor_id,))
    donor = cursor.fetchone()

    if not donor:
        conn.close()
        return {}

    # Get year's donations
    cursor.execute(f"""
        SELECT COUNT(*), SUM(quantity), SUM(estimated_value)
        FROM {DONATIONS_TABLE}
        WHERE donor_id = ? AND strftime('%Y', date_received) = ?
    """, (donor_id, str(year)))
    stats = cursor.fetchone()

    conn.close()

    letter = {
        'donor_name': donor[0],
        'donor_email': donor[1],
        'donor_address': donor[2],
        'year': year,
        'donation_count': stats[0] or 0,
        'items_donated': stats[1] or 0,
        'total_value': stats[2] or 0,
        'letter_text': f"""
Dear {donor[0]},

Thank you for your generous donations to the University Charity Shop during {year}.

Your {stats[0] or 0} donation(s) totaling {stats[1] or 0} items with an estimated value of
£{stats[2] or 0:.2f} have made a real difference in our community.

Your support helps us:
- Provide affordable items to students and community members
- Reduce waste through recycling and reuse
- Fund university programs and scholarships

We truly appreciate your continued support and look forward to your future contributions.

With gratitude,
University Charity Shop Team
"""
    }

    return letter


# ============================================================================
# STAFF & OPERATIONS FUNCTIONS (6)
# ============================================================================

def staff_performance_tracker(staff_id: int = None, period_days: int = 30) -> Any:
    """Monitor sales per staff member."""
    conn = get_connection()
    cursor = conn.cursor()

    start_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")

    if staff_id:
        cursor.execute(f"""
            SELECT st.name, st.role,
                   COUNT(sl.id) as sales_count,
                   SUM(sl.total_amount) as total_sales,
                   AVG(sl.total_amount) as avg_sale
            FROM {STAFF_TABLE} st
            LEFT JOIN {SALES_TABLE} sl ON st.id = sl.staff_id AND DATE(sl.sale_date) >= ?
            WHERE st.id = ?
            GROUP BY st.id
        """, (start_date, staff_id))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'name': row[0],
                'role': row[1],
                'sales_count': row[2] or 0,
                'total_sales': row[3] or 0,
                'average_sale': row[4] or 0
            }
        return None

    else:
        cursor.execute(f"""
            SELECT st.id, st.name, st.role,
                   COUNT(sl.id) as sales_count,
                   SUM(sl.total_amount) as total_sales
            FROM {STAFF_TABLE} st
            LEFT JOIN {SALES_TABLE} sl ON st.id = sl.staff_id AND DATE(sl.sale_date) >= ?
            WHERE st.is_active = 1
            GROUP BY st.id
            ORDER BY total_sales DESC
        """, (start_date,))

        staff = []
        for row in cursor.fetchall():
            staff.append({
                'id': row[0],
                'name': row[1],
                'role': row[2],
                'sales_count': row[3] or 0,
                'total_sales': row[4] or 0
            })
        conn.close()
        return staff


def shift_scheduling(action: str, **kwargs) -> Any:
    """Manage volunteer/staff schedules."""
    conn = get_connection()
    cursor = conn.cursor()

    if action == 'add':
        staff_id = kwargs.get('staff_id')
        shift_date = kwargs.get('date')
        start_time = kwargs.get('start_time')
        end_time = kwargs.get('end_time')
        notes = kwargs.get('notes', '')

        # Calculate hours
        try:
            start = datetime.strptime(start_time, "%H:%M")
            end = datetime.strptime(end_time, "%H:%M")
            hours = (end - start).seconds / 3600
        except:
            hours = 0

        cursor.execute(f"""
            INSERT INTO {SHIFTS_TABLE} (staff_id, shift_date, start_time, end_time, hours_worked, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (staff_id, shift_date, start_time, end_time, hours, notes))

        conn.commit()
        conn.close()
        return True

    elif action == 'view_date':
        date = kwargs.get('date')
        cursor.execute(f"""
            SELECT sh.*, st.name as staff_name
            FROM {SHIFTS_TABLE} sh
            JOIN {STAFF_TABLE} st ON sh.staff_id = st.id
            WHERE sh.shift_date = ?
            ORDER BY sh.start_time
        """, (date,))

        shifts = []
        for row in cursor.fetchall():
            shifts.append({
                'id': row[0],
                'staff_id': row[1],
                'staff_name': row[7] if len(row) > 7 else '',
                'date': row[2],
                'start_time': row[3],
                'end_time': row[4],
                'hours': row[5]
            })
        conn.close()
        return shifts

    elif action == 'view_staff':
        staff_id = kwargs.get('staff_id')
        cursor.execute(f"""
            SELECT * FROM {SHIFTS_TABLE}
            WHERE staff_id = ?
            ORDER BY shift_date DESC
            LIMIT 30
        """, (staff_id,))

        shifts = []
        for row in cursor.fetchall():
            shifts.append({
                'id': row[0],
                'date': row[2],
                'start_time': row[3],
                'end_time': row[4],
                'hours': row[5]
            })
        conn.close()
        return shifts

    conn.close()
    return None


def task_assignment_system(action: str, **kwargs) -> Any:
    """Assign daily tasks to staff."""
    conn = get_connection()
    cursor = conn.cursor()

    if action == 'create':
        title = kwargs.get('title')
        description = kwargs.get('description', '')
        assigned_to = kwargs.get('assigned_to')
        priority = kwargs.get('priority', 'medium')
        due_date = kwargs.get('due_date')

        cursor.execute(f"""
            INSERT INTO {TASKS_TABLE}
            (title, description, assigned_to, priority, status, due_date, created_date)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
        """, (title, description, assigned_to, priority, due_date,
              datetime.now().strftime("%Y-%m-%d")))

        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return task_id

    elif action == 'update_status':
        task_id = kwargs.get('task_id')
        status = kwargs.get('status')  # pending, in_progress, completed

        completed_date = datetime.now().strftime("%Y-%m-%d") if status == 'completed' else None

        cursor.execute(f"""
            UPDATE {TASKS_TABLE}
            SET status = ?, completed_date = ?
            WHERE id = ?
        """, (status, completed_date, task_id))

        conn.commit()
        conn.close()
        return True

    elif action == 'view_staff':
        staff_id = kwargs.get('staff_id')
        cursor.execute(f"""
            SELECT * FROM {TASKS_TABLE}
            WHERE assigned_to = ? AND status != 'completed'
            ORDER BY priority, due_date
        """, (staff_id,))

        tasks = []
        for row in cursor.fetchall():
            tasks.append({
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'priority': row[4],
                'status': row[5],
                'due_date': row[6]
            })
        conn.close()
        return tasks

    elif action == 'view_all':
        status_filter = kwargs.get('status', 'pending')
        cursor.execute(f"""
            SELECT t.*, st.name as staff_name
            FROM {TASKS_TABLE} t
            LEFT JOIN {STAFF_TABLE} st ON t.assigned_to = st.id
            WHERE t.status = ?
            ORDER BY t.priority, t.due_date
        """, (status_filter,))

        tasks = []
        for row in cursor.fetchall():
            tasks.append({
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'assigned_to': row[3],
                'staff_name': row[9] if len(row) > 9 else 'Unassigned',
                'priority': row[4],
                'status': row[5],
                'due_date': row[6]
            })
        conn.close()
        return tasks

    conn.close()
    return None


def volunteer_hours_tracker(staff_id: int, period: str = 'month') -> Dict:
    """Log volunteer time."""
    conn = get_connection()
    cursor = conn.cursor()

    if period == 'week':
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    elif period == 'month':
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    elif period == 'year':
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    else:
        start_date = '1900-01-01'

    cursor.execute(f"""
        SELECT st.name, st.role,
               SUM(sh.hours_worked) as total_hours,
               COUNT(sh.id) as shift_count,
               AVG(sh.hours_worked) as avg_hours
        FROM {STAFF_TABLE} st
        LEFT JOIN {SHIFTS_TABLE} sh ON st.id = sh.staff_id AND sh.shift_date >= ?
        WHERE st.id = ?
        GROUP BY st.id
    """, (start_date, staff_id))

    row = cursor.fetchone()

    # Get recent shifts
    cursor.execute(f"""
        SELECT shift_date, start_time, end_time, hours_worked
        FROM {SHIFTS_TABLE}
        WHERE staff_id = ? AND shift_date >= ?
        ORDER BY shift_date DESC
        LIMIT 10
    """, (staff_id, start_date))

    recent_shifts = [{'date': r[0], 'start': r[1], 'end': r[2], 'hours': r[3]}
                    for r in cursor.fetchall()]

    conn.close()

    if row:
        return {
            'name': row[0],
            'role': row[1],
            'total_hours': row[2] or 0,
            'shift_count': row[3] or 0,
            'average_hours': row[4] or 0,
            'period': period,
            'recent_shifts': recent_shifts
        }
    return {}


def opening_closing_checklist(action: str, checklist_type: str = 'opening') -> Any:
    """Daily procedures checklist."""
    # Predefined checklists
    opening_items = [
        'Unlock doors and disable alarm',
        'Turn on lights and displays',
        'Check cash float and count opening balance',
        'Power on POS system and verify connection',
        'Check voicemail and emails',
        'Review scheduled staff for the day',
        'Inspect store floor and tidy displays',
        'Check stock levels of fast-moving items',
        'Review any pending layaways due today',
        'Set out any new donations received'
    ]

    closing_items = [
        'Announce store closing 15 minutes prior',
        'Ensure all customers have left',
        'Count and reconcile cash register',
        'Complete daily sales report',
        'Secure cash in safe',
        'Power off POS system',
        'Check fitting rooms and clear items',
        'Tidy store floor and straighten displays',
        'Take out trash and recycling',
        'Turn off lights and set alarm',
        'Lock all doors and check security'
    ]

    items = opening_items if checklist_type == 'opening' else closing_items

    if action == 'get':
        return {
            'type': checklist_type,
            'items': [{'id': i+1, 'task': item, 'completed': False} for i, item in enumerate(items)]
        }

    elif action == 'log':
        # In production, would save to database
        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity(f'{checklist_type}_checklist', 'charity_shop_operations',
                        completed=True, date=datetime.now().strftime("%Y-%m-%d"))
        return True

    return None


def cash_register_reconciliation(opening_float: float, expected_total: float,
                                actual_total: float, notes: str = "") -> Dict:
    """End-of-day cash counting."""
    difference = actual_total - expected_total
    status = 'balanced' if abs(difference) < 0.01 else ('over' if difference > 0 else 'short')

    result = {
        'date': datetime.now().strftime("%Y-%m-%d"),
        'opening_float': opening_float,
        'expected_total': expected_total,
        'actual_total': actual_total,
        'difference': difference,
        'status': status,
        'notes': notes
    }

    if ACTIVITY_LOGGER_AVAILABLE:
        log_activity('cash_reconciliation', 'charity_shop_operations',
                    status=status, difference=difference)

    return result


def register_staff(name: str, email: str = None, phone: str = None, role: str = 'volunteer') -> Optional[int]:
    """Register a new staff member or volunteer."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(f"""
            INSERT INTO {STAFF_TABLE} (name, email, phone, role, date_joined, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (name, email, phone, role, datetime.now().strftime("%Y-%m-%d")))

        staff_id = cursor.lastrowid
        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_create('charity_shop_staff', staff_id=staff_id, name=name, role=role)

        return staff_id
    except sqlite3.Error as e:
        logger.error(f"Error registering staff: {e}")
        return None


def get_all_staff(active_only: bool = True) -> List[Dict]:
    """Get all staff members."""
    conn = get_connection()
    cursor = conn.cursor()

    query = f"SELECT * FROM {STAFF_TABLE}"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY name"

    cursor.execute(query)

    staff = []
    for row in cursor.fetchall():
        staff.append({
            'id': row[0],
            'name': row[1],
            'email': row[2],
            'phone': row[3],
            'role': row[4],
            'date_joined': row[5],
            'is_active': row[6],
            'total_hours': row[7],
            'total_sales': row[8],
            'sales_count': row[9]
        })

    conn.close()
    return staff


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


# ============================================================================
# CLI Menu Functions
# ============================================================================

def display_charity_shop_menu() -> None:
    """Display the main menu for the charity shop CLI."""
    global auth

    # Get auth from shared context if not set
    if not auth:
        auth = get_auth()

    if not auth or not auth.current_user:
        print(get_text('charity.not_logged_in', default='\nYou must be logged in to access the Charity Shop.'))
        return

    # Initialize database if needed
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{TABLE_NAME}'")
        if not cursor.fetchone():
            conn.close()
            print("Charity shop database not initialized. Initializing now...")
            if not init_charity_shop_db():
                print("Failed to initialize charity shop database.")
                return
        else:
            conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if not init_charity_shop_db():
            print("Failed to initialize charity shop database.")
            return

    if ACTIVITY_LOGGER_AVAILABLE:
        log_menu_navigation('charity_shop_menu')

    while True:
        print("\n" + "=" * 60)
        print(f"           {get_text('charity.title', default='CHARITY SHOP STOCK MANAGEMENT')}")
        print("=" * 60)

        # Show summary
        stock_summary = get_stock_summary()
        revenue_summary = get_revenue_summary()

        print(f"\n{get_text('charity.summary.stock', default='Stock')}: {stock_summary[0]} {get_text('charity.summary.items', default='items')} | {get_text('charity.summary.qty', default='Qty')}: {stock_summary[1]} | {get_text('charity.summary.value', default='Value')}: £{stock_summary[2]:.2f}")
        print(f"{get_text('charity.summary.revenue', default='Revenue')}: £{revenue_summary[2]:.2f} | {get_text('charity.summary.sold', default='Sold')}: {revenue_summary[1]} {get_text('charity.summary.items', default='items')}")
        print("-" * 60)

        # Build menu based on permissions
        options = []
        option_num = 1

        # View options (available to all)
        print(f"\n{option_num}. {get_text('charity.menu.view_all', default='View All Stock')}")
        options.append('view_all')
        option_num += 1

        print(f"{option_num}. {get_text('charity.menu.view_available', default='View Available Stock')}")
        options.append('view_available')
        option_num += 1

        print(f"{option_num}. {get_text('charity.menu.view_sold', default='View Sold Items')}")
        options.append('view_sold')
        option_num += 1

        print(f"{option_num}. {get_text('charity.menu.search', default='Search Stock')}")
        options.append('search')
        option_num += 1

        # Management options (staff/admin)
        if auth.check_permission('add_charity_shop_item') or auth.check_permission('manage_charity_shop'):
            print(f"{option_num}. {get_text('charity.menu.add', default='Add New Item')}")
            options.append('add')
            option_num += 1

        if auth.check_permission('edit_charity_shop_item') or auth.check_permission('manage_charity_shop'):
            print(f"{option_num}. {get_text('charity.menu.edit', default='Edit Item')}")
            options.append('edit')
            option_num += 1

        if auth.check_permission('sell_charity_shop_item') or auth.check_permission('manage_charity_shop'):
            print(f"{option_num}. {get_text('charity.menu.sell', default='Sell Item')}")
            options.append('sell')
            option_num += 1

            print(f"{option_num}. {get_text('charity.menu.mark_available', default='Mark Item Available')}")
            options.append('mark_available')
            option_num += 1

        if auth.check_permission('delete_charity_shop_item') or auth.check_permission('manage_charity_shop'):
            print(f"{option_num}. {get_text('charity.menu.delete', default='Delete Item')}")
            options.append('delete')
            option_num += 1

        # Reports (staff/admin)
        if auth.check_permission('view_charity_shop_reports') or auth.check_permission('manage_charity_shop'):
            print(f"{option_num}. {get_text('charity.menu.reports', default='View Reports')}")
            options.append('reports')
            option_num += 1

        # Advanced management submenus (staff/admin)
        if auth.check_permission('manage_charity_shop') or auth.check_permission('edit_charity_shop_item'):
            print(f"\n--- Advanced Management ---")
            print(f"{option_num}. Inventory Management")
            options.append('inventory')
            option_num += 1

            print(f"{option_num}. Sales & Pricing")
            options.append('sales_pricing')
            option_num += 1

            print(f"{option_num}. Customer Management")
            options.append('customers')
            option_num += 1

            print(f"{option_num}. Donation Management")
            options.append('donations')
            option_num += 1

            print(f"{option_num}. Staff & Operations")
            options.append('staff_ops')
            option_num += 1

        # Language option
        print(f"\n{option_num}. {get_text('charity.menu.language', default='Language')}")
        options.append('language')
        option_num += 1

        print(f"{option_num}. {get_text('charity.menu.return', default='Return to Main Menu')}")

        choice = input(f"\n{get_text('charity.prompt.choice', default='Enter your choice')}: ").strip()

        try:
            choice_num = int(choice)

            if choice_num > 0 and choice_num <= len(options):
                selected = options[choice_num - 1]

                if selected == 'view_all':
                    view_stock_cli('all')
                elif selected == 'view_available':
                    view_stock_cli('available')
                elif selected == 'view_sold':
                    view_stock_cli('sold')
                elif selected == 'search':
                    search_stock_cli()
                elif selected == 'add':
                    add_item_cli()
                elif selected == 'edit':
                    edit_item_cli()
                elif selected == 'sell':
                    sell_item_cli()
                elif selected == 'mark_available':
                    mark_available_cli()
                elif selected == 'delete':
                    delete_item_cli()
                elif selected == 'reports':
                    view_reports_cli()
                elif selected == 'inventory':
                    inventory_management_cli()
                elif selected == 'sales_pricing':
                    sales_pricing_cli()
                elif selected == 'customers':
                    customer_management_cli()
                elif selected == 'donations':
                    donation_management_cli()
                elif selected == 'staff_ops':
                    staff_operations_cli()
                elif selected == 'language':
                    display_language_menu_option()

            elif choice_num == len(options) + 1:
                print(get_text('charity.returning', default='Returning to main menu...'))
                break
            else:
                print(get_text('charity.invalid_choice', default='Invalid choice. Please try again.'))

        except ValueError:
            if choice.lower() in ['q', 'quit', 'exit', 'back']:
                break
            print(get_text('charity.invalid_input', default='Invalid input. Please enter a number.'))


def view_stock_cli(filter_type: str = 'all') -> None:
    """View stock items in CLI."""
    stock = get_all_stock(filter_type)

    if not stock:
        print(f"\nNo {'sold ' if filter_type == 'sold' else 'available ' if filter_type == 'available' else ''}items found.")
        return

    if ACTIVITY_LOGGER_AVAILABLE:
        log_read('charity_shop_stock', filter=filter_type, count=len(stock))

    print(f"\n{'=' * 100}")
    print(f"{'ID':<5} {'Name':<25} {'Category':<12} {'Price':<10} {'Qty':<5} {'Condition':<10} {'Status':<10} {'Sold':<5}")
    print(f"{'=' * 100}")

    for item in stock:
        item_id, name, category, price, qty, condition, date_added, sold, sold_date, sold_qty = item
        status = "Sold" if sold else "Available"
        print(f"{item_id:<5} {name[:24]:<25} {category:<12} £{price:<9.2f} {qty:<5} {condition:<10} {status:<10} {sold_qty or 0:<5}")

    print(f"{'=' * 100}")
    print(f"Total: {len(stock)} items")

    input("\nPress Enter to continue...")


def search_stock_cli() -> None:
    """Search stock items."""
    print("\n--- Search Stock ---")
    search_term = input("Enter search term (item name): ").strip()

    print("\nCategories: All, " + ", ".join(CATEGORIES))
    category = input("Filter by category (or 'All'): ").strip()
    if category not in ["All"] + CATEGORIES:
        category = "All"

    print("\nStatus: all, available, sold")
    status = input("Filter by status: ").strip().lower()
    if status not in ['all', 'available', 'sold']:
        status = 'all'

    results = search_stock(search_term, category, status)

    if ACTIVITY_LOGGER_AVAILABLE:
        log_search('charity_shop_stock', search_term=search_term, results_count=len(results))

    if not results:
        print("\nNo items found matching your criteria.")
    else:
        print(f"\n{'=' * 100}")
        print(f"{'ID':<5} {'Name':<25} {'Category':<12} {'Price':<10} {'Qty':<5} {'Condition':<10} {'Status':<10}")
        print(f"{'=' * 100}")

        for item in results:
            item_id, name, category, price, qty, condition, date_added, sold, sold_date, sold_qty = item
            status = "Sold" if sold else "Available"
            print(f"{item_id:<5} {name[:24]:<25} {category:<12} £{price:<9.2f} {qty:<5} {condition:<10} {status:<10}")

        print(f"\nFound {len(results)} items.")

    input("\nPress Enter to continue...")


def add_item_cli() -> None:
    """Add a new item via CLI."""
    print("\n--- Add New Item ---")

    name = input("Item name: ").strip()
    if not name:
        print("Item name is required.")
        return

    print("\nCategories: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CATEGORIES)))
    try:
        cat_choice = int(input("Select category (number): "))
        if 1 <= cat_choice <= len(CATEGORIES):
            category = CATEGORIES[cat_choice - 1]
        else:
            category = "Other"
    except ValueError:
        category = "Other"

    try:
        price = float(input("Price (£): "))
        if price < 0:
            print("Price must be positive.")
            return
    except ValueError:
        print("Invalid price.")
        return

    try:
        quantity = int(input("Quantity: "))
        if quantity < 0:
            print("Quantity must be positive.")
            return
    except ValueError:
        print("Invalid quantity.")
        return

    print("\nConditions: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CONDITIONS)))
    try:
        cond_choice = int(input("Select condition (number): "))
        if 1 <= cond_choice <= len(CONDITIONS):
            condition = CONDITIONS[cond_choice - 1]
        else:
            condition = "Good"
    except ValueError:
        condition = "Good"

    if add_item(name, category, price, quantity, condition):
        print(f"\n✅ Item '{name}' added successfully!")
    else:
        print("\n❌ Failed to add item.")

    input("\nPress Enter to continue...")


def edit_item_cli() -> None:
    """Edit an existing item via CLI."""
    print("\n--- Edit Item ---")

    try:
        item_id = int(input("Enter item ID to edit: "))
    except ValueError:
        print("Invalid ID.")
        return

    # Get current item
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {TABLE_NAME} WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()

    if not item:
        print("Item not found.")
        return

    item_id, name, category, price, qty, condition, date_added, sold, sold_date, sold_qty = item

    print(f"\nCurrent values:")
    print(f"  Name: {name}")
    print(f"  Category: {category}")
    print(f"  Price: £{price:.2f}")
    print(f"  Quantity: {qty}")
    print(f"  Condition: {condition}")

    print("\n(Press Enter to keep current value)")

    new_name = input(f"New name [{name}]: ").strip() or name

    print("\nCategories: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CATEGORIES)))
    cat_input = input(f"New category [{category}]: ").strip()
    try:
        cat_choice = int(cat_input)
        if 1 <= cat_choice <= len(CATEGORIES):
            new_category = CATEGORIES[cat_choice - 1]
        else:
            new_category = category
    except ValueError:
        new_category = category

    price_input = input(f"New price [{price:.2f}]: ").strip()
    try:
        new_price = float(price_input) if price_input else price
    except ValueError:
        new_price = price

    qty_input = input(f"New quantity [{qty}]: ").strip()
    try:
        new_qty = int(qty_input) if qty_input else qty
    except ValueError:
        new_qty = qty

    print("\nConditions: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CONDITIONS)))
    cond_input = input(f"New condition [{condition}]: ").strip()
    try:
        cond_choice = int(cond_input)
        if 1 <= cond_choice <= len(CONDITIONS):
            new_condition = CONDITIONS[cond_choice - 1]
        else:
            new_condition = condition
    except ValueError:
        new_condition = condition

    if update_item(item_id, new_name, new_category, new_price, new_qty, new_condition, bool(sold), sold_qty or 0):
        print(f"\n✅ Item updated successfully!")
    else:
        print("\n❌ Failed to update item.")

    input("\nPress Enter to continue...")


def sell_item_cli() -> None:
    """Sell an item via CLI."""
    print("\n--- Sell Item ---")

    try:
        item_id = int(input("Enter item ID to sell: "))
    except ValueError:
        print("Invalid ID.")
        return

    # Get current item
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT name, quantity, price FROM {TABLE_NAME} WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()

    if not item:
        print("Item not found.")
        return

    name, available_qty, price = item

    if available_qty <= 0:
        print(f"'{name}' is out of stock.")
        return

    print(f"\nItem: {name}")
    print(f"Available: {available_qty}")
    print(f"Price: £{price:.2f}")

    try:
        qty_to_sell = int(input(f"Quantity to sell (1-{available_qty}): "))
        if qty_to_sell < 1 or qty_to_sell > available_qty:
            print("Invalid quantity.")
            return
    except ValueError:
        print("Invalid quantity.")
        return

    revenue = qty_to_sell * price

    confirm = input(f"\nSell {qty_to_sell} x '{name}' for £{revenue:.2f}? (y/n): ").strip().lower()
    if confirm == 'y':
        if mark_as_sold(item_id, qty_to_sell):
            print(f"\n✅ Sold {qty_to_sell} x '{name}' for £{revenue:.2f}!")
        else:
            print("\n❌ Failed to process sale.")
    else:
        print("Sale cancelled.")

    input("\nPress Enter to continue...")


def mark_available_cli() -> None:
    """Mark an item as available via CLI."""
    print("\n--- Mark Item Available ---")

    try:
        item_id = int(input("Enter item ID: "))
    except ValueError:
        print("Invalid ID.")
        return

    if mark_as_available(item_id):
        print("\n✅ Item marked as available!")
    else:
        print("\n❌ Failed to update item.")

    input("\nPress Enter to continue...")


def delete_item_cli() -> None:
    """Delete an item via CLI."""
    print("\n--- Delete Item ---")

    try:
        item_id = int(input("Enter item ID to delete: "))
    except ValueError:
        print("Invalid ID.")
        return

    # Get item name
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT name FROM {TABLE_NAME} WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()

    if not item:
        print("Item not found.")
        return

    confirm = input(f"Are you sure you want to delete '{item[0]}'? (y/n): ").strip().lower()
    if confirm == 'y':
        if delete_item(item_id):
            print(f"\n✅ Item '{item[0]}' deleted!")
        else:
            print("\n❌ Failed to delete item.")
    else:
        print("Deletion cancelled.")

    input("\nPress Enter to continue...")


def view_reports_cli() -> None:
    """View charity shop reports."""
    while True:
        print("\n--- Charity Shop Reports ---")
        print("1. Stock Summary")
        print("2. Revenue Summary")
        print("3. Revenue by Category")
        print("4. Stock by Category")
        print("5. Daily Sales Report")
        print("6. Weekly Sales Report")
        print("7. Monthly Sales Report")
        print("8. Best Selling Items")
        print("9. Slow Moving Items")
        print("10. Category Performance")
        print("11. Seasonal Trends")
        print("12. Profit Margins")
        print("13. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            summary = get_stock_summary()
            print(f"\n{'=' * 40}")
            print("STOCK SUMMARY")
            print(f"{'=' * 40}")
            print(f"Total unique items: {summary[0]}")
            print(f"Total quantity: {summary[1]}")
            print(f"Total stock value: £{summary[2]:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '2':
            summary = get_revenue_summary()
            print(f"\n{'=' * 40}")
            print("REVENUE SUMMARY")
            print(f"{'=' * 40}")
            print(f"Items with sales: {summary[0]}")
            print(f"Total items sold: {summary[1]}")
            print(f"Total revenue: £{summary[2]:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '3':
            revenue = get_revenue_by_category()
            print(f"\n{'=' * 40}")
            print("REVENUE BY CATEGORY")
            print(f"{'=' * 40}")
            if revenue:
                for cat, rev in revenue:
                    print(f"{cat:<20} £{rev:.2f}")
            else:
                print("No sales data available.")
            input("\nPress Enter to continue...")

        elif choice == '4':
            stock = get_stock_by_category()
            print(f"\n{'=' * 40}")
            print("STOCK BY CATEGORY")
            print(f"{'=' * 40}")
            if stock:
                for cat, count, qty in stock:
                    print(f"{cat:<20} {count} items ({qty} units)")
            else:
                print("No stock data available.")
            input("\nPress Enter to continue...")

        elif choice == '5':
            date = input("Enter date (YYYY-MM-DD) or press Enter for today: ").strip() or None
            report = generate_daily_sales_report(date)
            print(f"\n{'=' * 50}")
            print(f"DAILY SALES REPORT - {report['date']}")
            print(f"{'=' * 50}")
            print(f"Total Transactions: {report['total_transactions']}")
            print(f"Total Revenue: £{report['total_revenue']:.2f}")
            print(f"Items Sold: {report['total_items_sold']}")
            if report['by_payment_method']:
                print("\nBy Payment Method:")
                for pm in report['by_payment_method']:
                    print(f"  {pm['method']}: {pm['count']} transactions, £{pm['amount']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '6':
            report = generate_weekly_sales_report()
            print(f"\n{'=' * 50}")
            print(f"WEEKLY SALES REPORT")
            print(f"{'=' * 50}")
            print(f"Period: {report['start_date']} to {report['end_date']}")
            print(f"Total Transactions: {report['total_transactions']}")
            print(f"Total Revenue: £{report['total_revenue']:.2f}")
            print(f"Items Sold: {report['total_items_sold']}")
            if report['daily_breakdown']:
                print("\nDaily Breakdown:")
                for day in report['daily_breakdown']:
                    print(f"  {day['date']}: {day['transactions']} trans, £{day['revenue']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '7':
            report = generate_monthly_sales_report()
            print(f"\n{'=' * 50}")
            print(f"MONTHLY SALES REPORT - {report['year']}/{report['month']:02d}")
            print(f"{'=' * 50}")
            print(f"Total Transactions: {report['total_transactions']}")
            print(f"Total Revenue: £{report['total_revenue']:.2f}")
            print(f"Items Sold: {report['total_items_sold']}")
            print(f"Average Transaction: £{report['average_transaction']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '8':
            items = best_selling_items_report()
            print(f"\n{'=' * 60}")
            print("BEST SELLING ITEMS (Last 30 Days)")
            print(f"{'=' * 60}")
            if items:
                for i, item in enumerate(items, 1):
                    print(f"{i}. {item['name']} ({item['category']})")
                    print(f"   Sold: {item['quantity_sold']} | Revenue: £{item['revenue']:.2f}")
            else:
                print("No sales data available.")
            input("\nPress Enter to continue...")

        elif choice == '9':
            items = slow_moving_items_report()
            print(f"\n{'=' * 60}")
            print("SLOW MOVING ITEMS (60+ Days)")
            print(f"{'=' * 60}")
            if items:
                for item in items:
                    print(f"ID {item['id']}: {item['name']} - £{item['price']:.2f}")
                    print(f"   {item['days_in_stock']} days in stock | Qty: {item['quantity']}")
            else:
                print("No slow-moving items found.")
            input("\nPress Enter to continue...")

        elif choice == '10':
            results = category_performance_comparison()
            print(f"\n{'=' * 70}")
            print("CATEGORY PERFORMANCE (Last 30 Days)")
            print(f"{'=' * 70}")
            print(f"{'Category':<15} {'Trans':<8} {'Items':<8} {'Revenue':<12} {'Avg Sale':<10}")
            print("-" * 70)
            for r in results:
                print(f"{r['category']:<15} {r['transactions']:<8} {r['items_sold']:<8} £{r['revenue']:<11.2f} £{r['average_sale']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '11':
            trends = seasonal_trends_report()
            print(f"\n{'=' * 50}")
            print("SEASONAL TRENDS")
            print(f"{'=' * 50}")
            print("\nBy Month:")
            for month, data in trends['by_month'].items():
                print(f"  {month}: {data['transactions']} trans, £{data['revenue']:.2f}")
            print("\nBy Day of Week:")
            for day, data in trends['by_day_of_week'].items():
                print(f"  {day}: {data['transactions']} trans, £{data['revenue']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '12':
            margins = calculate_profit_margin()
            print(f"\n{'=' * 50}")
            print("PROFIT MARGINS")
            print(f"{'=' * 50}")
            print(f"Total Revenue: £{margins['total_revenue']:.2f}")
            print(f"Total Profit: £{margins['total_profit']:.2f}")
            print(f"Margin: {margins['margin_percent']:.1f}%")
            input("\nPress Enter to continue...")

        elif choice == '13':
            break


# ============================================================================
# INVENTORY MANAGEMENT CLI
# ============================================================================

def inventory_management_cli() -> None:
    """Inventory management submenu."""
    while True:
        print("\n" + "=" * 50)
        print("       INVENTORY MANAGEMENT")
        print("=" * 50)
        print("1. Bulk Import Items (CSV)")
        print("2. Bulk Export Items (CSV)")
        print("3. Adjust Stock Quantity")
        print("4. Set Low Stock Alert")
        print("5. View Low Stock Items")
        print("6. Merge Duplicate Items")
        print("7. Archive Old Items")
        print("8. View/Restore Archived Items")
        print("9. Transfer Between Locations")
        print("10. Barcode Lookup")
        print("11. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            file_path = input("Enter CSV file path: ").strip()
            if file_path:
                success, errors = bulk_import_items(file_path)
                if errors == -1:
                    print("\n❌ File not found.")
                else:
                    print(f"\n✅ Imported {success} items, {errors} errors.")
            input("\nPress Enter to continue...")

        elif choice == '2':
            file_path = input("Enter export file path (e.g., inventory.csv): ").strip()
            if file_path:
                filter_type = input("Filter (all/available/sold) [all]: ").strip() or "all"
                if bulk_export_items(file_path, filter_type):
                    print(f"\n✅ Exported to {file_path}")
                else:
                    print("\n❌ Export failed.")
            input("\nPress Enter to continue...")

        elif choice == '3':
            try:
                item_id = int(input("Item ID: "))
                adjustment = int(input("Adjustment (+/-): "))
                reason = input("Reason (optional): ").strip()
                if adjust_stock_quantity(item_id, adjustment, reason):
                    print("\n✅ Stock adjusted!")
                else:
                    print("\n❌ Failed to adjust stock.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '4':
            try:
                item_id = int(input("Item ID: "))
                threshold = int(input("Low stock threshold: "))
                if set_low_stock_alert(item_id, threshold):
                    print("\n✅ Alert threshold set!")
                else:
                    print("\n❌ Failed to set alert.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '5':
            items = view_low_stock_items()
            print(f"\n{'=' * 60}")
            print("LOW STOCK ITEMS")
            print(f"{'=' * 60}")
            if items:
                for item in items:
                    print(f"ID {item[0]}: {item[1]} ({item[2]}) - Qty: {item[3]}, Threshold: {item[4]}")
            else:
                print("No low stock items.")
            input("\nPress Enter to continue...")

        elif choice == '6':
            try:
                keep_id = int(input("Item ID to keep: "))
                merge_id = int(input("Item ID to merge (will be deleted): "))
                if merge_duplicate_items(keep_id, merge_id):
                    print("\n✅ Items merged!")
                else:
                    print("\n❌ Failed to merge.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '7':
            try:
                days = int(input("Archive items older than (days) [90]: ") or "90")
                count = archive_old_items(days)
                print(f"\n✅ Archived {count} items.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '8':
            archived = get_archived_items()
            print(f"\n{'=' * 60}")
            print("ARCHIVED ITEMS")
            print(f"{'=' * 60}")
            if archived:
                for item in archived:
                    print(f"ID {item[0]}: {item[2]} - Archived: {item[7]}")
                restore = input("\nEnter IDs to restore (comma-separated) or press Enter: ").strip()
                if restore:
                    ids = [int(x.strip()) for x in restore.split(",")]
                    count = restore_archived_items(ids)
                    print(f"\n✅ Restored {count} items.")
            else:
                print("No archived items.")
            input("\nPress Enter to continue...")

        elif choice == '9':
            locations = get_all_locations()
            if not locations:
                print("\nNo locations configured. Add locations first.")
            else:
                print("\nLocations:")
                for loc in locations:
                    print(f"  {loc['id']}: {loc['name']}")
                try:
                    item_id = int(input("Item ID: "))
                    from_loc = int(input("From location ID: "))
                    to_loc = int(input("To location ID: "))
                    qty = int(input("Quantity: "))
                    if transfer_between_locations(item_id, from_loc, to_loc, qty):
                        print("\n✅ Transfer complete!")
                    else:
                        print("\n❌ Transfer failed.")
                except ValueError:
                    print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '10':
            barcode = input("Enter barcode: ").strip()
            item = barcode_scanner_integration(barcode)
            if item:
                print(f"\nFound: {item['name']} (ID: {item['id']})")
                print(f"Price: £{item['price']:.2f} | Qty: {item['quantity']}")
            else:
                print("\nNo item found with that barcode.")
                assign = input("Assign to item ID? ").strip()
                if assign:
                    try:
                        if set_item_barcode(int(assign), barcode):
                            print("✅ Barcode assigned!")
                    except ValueError:
                        pass
            input("\nPress Enter to continue...")

        elif choice == '11':
            break


# ============================================================================
# SALES & PRICING CLI
# ============================================================================

def sales_pricing_cli() -> None:
    """Sales and pricing submenu."""
    while True:
        print("\n" + "=" * 50)
        print("       SALES & PRICING")
        print("=" * 50)
        print("1. Apply Discount to Item")
        print("2. Create Sale Bundle")
        print("3. View Bundles")
        print("4. Price History")
        print("5. Dynamic Pricing Suggestions")
        print("6. Create Promotional Event")
        print("7. View Active Promotions")
        print("8. Process Refund")
        print("9. Layaway Management")
        print("10. Gift Card Management")
        print("11. Loyalty Points")
        print("12. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            try:
                item_id = int(input("Item ID: "))
                print("Discount type: 1. Percentage  2. Fixed amount")
                dtype = input("Choice: ").strip()
                discount_type = 'percent' if dtype == '1' else 'fixed'
                value = float(input(f"{'Percentage' if dtype == '1' else 'Amount'}: "))
                if apply_discount(item_id, discount_type, value):
                    print("\n✅ Discount applied!")
                else:
                    print("\n❌ Failed to apply discount.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '2':
            name = input("Bundle name: ").strip()
            description = input("Description: ").strip()
            item_ids_str = input("Item IDs (comma-separated): ").strip()
            try:
                item_ids = [int(x.strip()) for x in item_ids_str.split(",")]
                bundle_price = float(input("Bundle price: £"))
                bundle_id = create_sale_bundle(name, description, item_ids, bundle_price)
                if bundle_id:
                    print(f"\n✅ Bundle created (ID: {bundle_id})")
                else:
                    print("\n❌ Failed to create bundle.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '3':
            bundles = get_bundles()
            print(f"\n{'=' * 60}")
            print("ACTIVE BUNDLES")
            print(f"{'=' * 60}")
            for b in bundles:
                print(f"ID {b['id']}: {b['name']} - £{b['bundle_price']:.2f}")
                print(f"   Items: {b['item_ids']} | Sold: {b['times_sold']} times")
            input("\nPress Enter to continue...")

        elif choice == '4':
            try:
                item_id = int(input("Item ID: "))
                history = price_history_tracker(item_id)
                print(f"\n{'=' * 60}")
                print("PRICE HISTORY")
                print(f"{'=' * 60}")
                for h in history:
                    print(f"{h['change_date']}: £{h['old_price']:.2f} → £{h['new_price']:.2f}")
                    if h['reason']:
                        print(f"   Reason: {h['reason']}")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '5':
            try:
                item_id = int(input("Item ID: "))
                suggestion = dynamic_pricing_suggestions(item_id)
                if suggestion:
                    print(f"\nCurrent Price: £{suggestion['current_price']:.2f}")
                    print(f"Suggested Price: £{suggestion['suggested_price']:.2f}")
                    print(f"Category Average: £{suggestion['category_average']:.2f}")
                    print(f"Days in Stock: {suggestion['days_in_stock']}")
                    print(f"Condition: {suggestion['condition']}")
                    print(f"\n{suggestion['reason']}")
                else:
                    print("Item not found.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '6':
            name = input("Promotion name: ").strip()
            print("Discount type: 1. Percentage  2. Fixed amount")
            dtype = input("Choice: ").strip()
            discount_type = 'percent' if dtype == '1' else 'fixed'
            try:
                value = float(input("Discount value: "))
                start = input("Start date (YYYY-MM-DD): ").strip()
                end = input("End date (YYYY-MM-DD): ").strip()
                category = input("Category (optional): ").strip() or None
                promo_id = create_promotional_event(name, discount_type, value, start, end, category)
                if promo_id:
                    print(f"\n✅ Promotion created (ID: {promo_id})")
                else:
                    print("\n❌ Failed to create promotion.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '7':
            promos = get_active_promotions()
            print(f"\n{'=' * 60}")
            print("ACTIVE PROMOTIONS")
            print(f"{'=' * 60}")
            if promos:
                for p in promos:
                    print(f"{p['name']}: {p['discount_value']}{'%' if p['discount_type'] == 'percent' else '£'} off")
                    print(f"   {p['start_date']} to {p['end_date']}")
                    if p['category']:
                        print(f"   Category: {p['category']}")
            else:
                print("No active promotions.")
            input("\nPress Enter to continue...")

        elif choice == '8':
            try:
                sale_id = int(input("Sale ID to refund: "))
                reason = input("Refund reason: ").strip()
                if process_refund(sale_id, reason):
                    print("\n✅ Refund processed!")
                else:
                    print("\n❌ Failed to process refund.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '9':
            layaway_menu_cli()

        elif choice == '10':
            gift_card_menu_cli()

        elif choice == '11':
            loyalty_menu_cli()

        elif choice == '12':
            break


def layaway_menu_cli() -> None:
    """Layaway submenu."""
    while True:
        print("\n--- Layaway Management ---")
        print("1. Create Layaway")
        print("2. View Active Layaways")
        print("3. Back")

        choice = input("Choice: ").strip()

        if choice == '1':
            try:
                item_id = int(input("Item ID: "))
                customer_id = int(input("Customer ID: "))
                deposit = float(input("Deposit amount: £"))
                days = int(input("Due in (days) [30]: ") or "30")
                layaway_id = layaway_system(item_id, customer_id, deposit, days)
                if layaway_id:
                    print(f"\n✅ Layaway created (ID: {layaway_id})")
                else:
                    print("\n❌ Failed to create layaway.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '2':
            layaways = get_layaways()
            print(f"\n{'=' * 70}")
            print("ACTIVE LAYAWAYS")
            print(f"{'=' * 70}")
            for l in layaways:
                print(f"ID {l['id']}: {l['item_name']} for {l['customer_name']}")
                print(f"   Total: £{l['total_price']:.2f} | Paid: £{l['deposit_paid']:.2f} | Due: {l['due_date']}")
            input("\nPress Enter to continue...")

        elif choice == '3':
            break


def gift_card_menu_cli() -> None:
    """Gift card submenu."""
    while True:
        print("\n--- Gift Card Management ---")
        print("1. Issue Gift Card")
        print("2. Check Balance")
        print("3. Redeem Gift Card")
        print("4. Back")

        choice = input("Choice: ").strip()

        if choice == '1':
            try:
                amount = float(input("Gift card amount: £"))
                customer_id = input("Customer ID (optional): ").strip()
                cid = int(customer_id) if customer_id else None
                result = gift_card_management('issue', amount=amount, customer_id=cid)
                if result:
                    print(f"\n✅ Gift Card Issued!")
                    print(f"Code: {result['code']}")
                    print(f"Balance: £{result['balance']:.2f}")
                    print(f"Expires: {result['expiry']}")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '2':
            code = input("Gift card code: ").strip()
            result = gift_card_management('check_balance', code=code)
            if result:
                print(f"\nBalance: £{result['balance']:.2f}")
                print(f"Expires: {result['expiry']}")
                print(f"Active: {'Yes' if result['active'] else 'No'}")
            else:
                print("Gift card not found.")
            input("\nPress Enter to continue...")

        elif choice == '3':
            try:
                code = input("Gift card code: ").strip()
                amount = float(input("Amount to redeem: £"))
                result = gift_card_management('redeem', code=code, amount=amount)
                if result:
                    print(f"\n✅ Redeemed £{result['redeemed']:.2f}")
                    print(f"New balance: £{result['new_balance']:.2f}")
                else:
                    print("\n❌ Redemption failed (invalid card or insufficient balance).")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '4':
            break


def loyalty_menu_cli() -> None:
    """Loyalty points submenu."""
    while True:
        print("\n--- Loyalty Points ---")
        print("1. Check Points")
        print("2. Add Points")
        print("3. Redeem Points")
        print("4. Back")

        choice = input("Choice: ").strip()

        if choice == '1':
            try:
                customer_id = int(input("Customer ID: "))
                points = loyalty_points_system(customer_id, 'check')
                print(f"\nLoyalty Points: {points}")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '2':
            try:
                customer_id = int(input("Customer ID: "))
                points = int(input("Points to add: "))
                reason = input("Reason: ").strip()
                if loyalty_points_system(customer_id, 'add', points=points, reason=reason):
                    print("\n✅ Points added!")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '3':
            try:
                customer_id = int(input("Customer ID: "))
                points = int(input("Points to redeem: "))
                if loyalty_points_system(customer_id, 'redeem', points=points):
                    print("\n✅ Points redeemed!")
                else:
                    print("\n❌ Insufficient points.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '4':
            break


# ============================================================================
# CUSTOMER MANAGEMENT CLI
# ============================================================================

def customer_management_cli() -> None:
    """Customer management submenu."""
    while True:
        print("\n" + "=" * 50)
        print("       CUSTOMER MANAGEMENT")
        print("=" * 50)
        print("1. Register Customer")
        print("2. View Customer")
        print("3. Customer Purchase History")
        print("4. Customer Wishlist")
        print("5. VIP Management")
        print("6. Birthday Discounts")
        print("7. Referral Program")
        print("8. Customer Feedback")
        print("9. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            name = input("Customer name: ").strip()
            email = input("Email (optional): ").strip() or None
            phone = input("Phone (optional): ").strip() or None
            address = input("Address (optional): ").strip() or None
            birthday = input("Birthday YYYY-MM-DD (optional): ").strip() or None
            customer_id = register_customer(name, email, phone, address, birthday)
            if customer_id:
                print(f"\n✅ Customer registered (ID: {customer_id})")
            else:
                print("\n❌ Registration failed.")
            input("\nPress Enter to continue...")

        elif choice == '2':
            try:
                customer_id = int(input("Customer ID: "))
                customer = get_customer(customer_id)
                if customer:
                    print(f"\n{'=' * 40}")
                    print(f"Name: {customer['name']}")
                    print(f"Email: {customer['email']}")
                    print(f"Phone: {customer['phone']}")
                    print(f"VIP: {'Yes' if customer['is_vip'] else 'No'}")
                    print(f"Loyalty Points: {customer['loyalty_points']}")
                    print(f"Total Spent: £{customer['total_spent']:.2f}")
                    print(f"Referral Code: {customer['referral_code']}")
                else:
                    print("Customer not found.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '3':
            try:
                customer_id = int(input("Customer ID: "))
                history = customer_purchase_history(customer_id)
                print(f"\n{'=' * 60}")
                print("PURCHASE HISTORY")
                print(f"{'=' * 60}")
                for h in history:
                    status = " (REFUNDED)" if h['refunded'] else ""
                    print(f"{h['date']}: {h['item_name']} x{h['quantity']} - £{h['amount']:.2f}{status}")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '4':
            try:
                customer_id = int(input("Customer ID: "))
                print("1. View Wishlist  2. Add Item  3. Remove Item")
                action = input("Choice: ").strip()
                if action == '1':
                    items = customer_wishlist(customer_id, 'view')
                    print("\nWishlist:")
                    for item in items:
                        print(f"  {item['id']}: {item['description']} (Max: £{item['max_price']})")
                elif action == '2':
                    desc = input("Item description: ").strip()
                    cat = input("Category (optional): ").strip() or None
                    price = input("Max price (optional): ").strip()
                    max_price = float(price) if price else None
                    customer_wishlist(customer_id, 'add', description=desc, category=cat, max_price=max_price)
                    print("✅ Added to wishlist!")
                elif action == '3':
                    wid = int(input("Wishlist item ID: "))
                    customer_wishlist(customer_id, 'remove', wishlist_id=wid)
                    print("✅ Removed!")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '5':
            print("1. List VIPs  2. Make VIP  3. Remove VIP  4. Auto-Promote")
            action = input("Choice: ").strip()
            if action == '1':
                vips = vip_customer_management('list_vips')
                print("\nVIP Customers:")
                for v in vips:
                    print(f"  {v['name']} - Spent: £{v['total_spent']:.2f}, Points: {v['loyalty_points']}")
            elif action == '2':
                try:
                    cid = int(input("Customer ID: "))
                    vip_customer_management('make_vip', cid)
                    print("✅ Customer is now VIP!")
                except ValueError:
                    print("Invalid input.")
            elif action == '3':
                try:
                    cid = int(input("Customer ID: "))
                    vip_customer_management('remove_vip', cid)
                    print("✅ VIP status removed!")
                except ValueError:
                    print("Invalid input.")
            elif action == '4':
                count = vip_customer_management('auto_promote')
                print(f"✅ Promoted {count} customers to VIP!")
            input("\nPress Enter to continue...")

        elif choice == '6':
            customers = customer_birthday_discounts()
            print("\nCustomers with birthdays this month:")
            for c in customers:
                print(f"  {c['name']} - {c['birthday']} ({c['email']})")
            input("\nPress Enter to continue...")

        elif choice == '7':
            try:
                code = input("Referrer's code: ").strip()
                new_id = int(input("New customer ID: "))
                if customer_referral_program(code, new_id):
                    print("✅ Referral processed! Points awarded.")
                else:
                    print("❌ Invalid referral code.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '8':
            print("1. Submit Feedback  2. View Item Feedback")
            action = input("Choice: ").strip()
            if action == '1':
                try:
                    cid = int(input("Customer ID: "))
                    iid = int(input("Item ID: "))
                    rating = int(input("Rating (1-5): "))
                    comment = input("Comment: ").strip()
                    customer_feedback_system('submit', customer_id=cid, item_id=iid, rating=rating, comment=comment)
                    print("✅ Feedback submitted!")
                except ValueError:
                    print("Invalid input.")
            elif action == '2':
                try:
                    iid = int(input("Item ID: "))
                    feedback = customer_feedback_system('view_item', item_id=iid)
                    avg = customer_feedback_system('average', item_id=iid)
                    print(f"\nAverage Rating: {avg['average']:.1f}/5 ({avg['count']} reviews)")
                    for f in feedback:
                        print(f"  {f['rating']}/5 - {f['comment']} ({f['customer_name']})")
                except ValueError:
                    print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '9':
            break


# ============================================================================
# DONATION MANAGEMENT CLI
# ============================================================================

def donation_management_cli() -> None:
    """Donation management submenu."""
    while True:
        print("\n" + "=" * 50)
        print("       DONATION MANAGEMENT")
        print("=" * 50)
        print("1. Register Donor")
        print("2. Record Donation")
        print("3. Generate Donation Receipt")
        print("4. View Donors")
        print("5. Donation Value Estimator")
        print("6. Donation Drive Summary")
        print("7. Thank You Letter")
        print("8. Tax Deduction Report")
        print("9. Donor Contribution Report")
        print("10. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            name = input("Donor name: ").strip()
            email = input("Email (optional): ").strip() or None
            phone = input("Phone (optional): ").strip() or None
            address = input("Address (optional): ").strip() or None
            donor_id = donor_database('add', name=name, email=email, phone=phone, address=address)
            if donor_id:
                print(f"\n✅ Donor registered (ID: {donor_id})")
            input("\nPress Enter to continue...")

        elif choice == '2':
            try:
                donor_id = int(input("Donor ID: "))
                description = input("Item description: ").strip()
                print("Categories: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CATEGORIES)))
                cat_num = input("Category number: ").strip()
                category = CATEGORIES[int(cat_num)-1] if cat_num else None
                qty = int(input("Quantity [1]: ") or "1")
                print("Conditions: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CONDITIONS)))
                cond_num = input("Condition number: ").strip()
                condition = CONDITIONS[int(cond_num)-1] if cond_num else "Good"
                est_value = donation_value_estimator(category or "Other", condition)
                print(f"Estimated value: £{est_value:.2f}")
                use_est = input("Use this value? (y/n) [y]: ").strip().lower() != 'n'
                value = est_value if use_est else float(input("Enter value: £"))
                drive_id = input("Donation drive ID (optional): ").strip() or None
                notes = input("Notes (optional): ").strip() or None
                donation_id = record_donation(donor_id, description, category, qty, value, drive_id, notes)
                if donation_id:
                    print(f"\n✅ Donation recorded (ID: {donation_id})")
            except (ValueError, IndexError):
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '3':
            try:
                donation_id = int(input("Donation ID: "))
                receipt = generate_donation_receipt(donation_id)
                if receipt:
                    print(f"\n{'=' * 50}")
                    print("DONATION RECEIPT")
                    print(f"{'=' * 50}")
                    print(f"Receipt #: {receipt['receipt_number']}")
                    print(f"Date: {receipt['date']}")
                    print(f"Donor: {receipt['donor_name']}")
                    print(f"Item: {receipt['item_description']}")
                    print(f"Quantity: {receipt['quantity']}")
                    print(f"Estimated Value: £{receipt['estimated_value']:.2f}")
                    print(f"\n{receipt['statement']}")
                else:
                    print("Donation not found.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '4':
            donors = donor_database('list')
            print(f"\n{'=' * 60}")
            print("DONORS")
            print(f"{'=' * 60}")
            for d in donors:
                print(f"ID {d['id']}: {d['name']} - {d['total_donations']} donations, £{d['total_value']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '5':
            print("Categories: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CATEGORIES)))
            cat_num = input("Category number: ").strip()
            print("Conditions: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CONDITIONS)))
            cond_num = input("Condition number: ").strip()
            try:
                category = CATEGORIES[int(cat_num)-1]
                condition = CONDITIONS[int(cond_num)-1]
                value = donation_value_estimator(category, condition)
                print(f"\nEstimated Value: £{value:.2f}")
            except (ValueError, IndexError):
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '6':
            print("1. View Drive Summary  2. List All Drives")
            action = input("Choice: ").strip()
            if action == '1':
                drive_id = input("Drive ID: ").strip()
                summary = donation_drive_tracker('summary', drive_id=drive_id)
                print(f"\nDrive: {summary['drive_id']}")
                print(f"Donations: {summary['total_donations']}")
                print(f"Items: {summary['total_items']}")
                print(f"Value: £{summary['total_value']:.2f}")
            elif action == '2':
                drives = donation_drive_tracker('list_drives')
                print("\nDonation Drives:")
                for d in drives:
                    print(f"  {d['drive_id']}: {d['donations']} donations, £{d['total_value']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '7':
            try:
                donor_id = int(input("Donor ID: "))
                year = input("Year (optional): ").strip()
                year = int(year) if year else None
                letter = thank_you_letter_generator(donor_id, year)
                if letter:
                    print(letter['letter_text'])
                else:
                    print("Donor not found.")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '8':
            year = input("Year (optional): ").strip()
            year = int(year) if year else None
            report = tax_deduction_report(year)
            print(f"\n{'=' * 60}")
            print(f"TAX DEDUCTION REPORT - {year or datetime.now().year}")
            print(f"{'=' * 60}")
            for r in report:
                print(f"{r['name']}: {r['donation_count']} donations, £{r['total_deductible']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '9':
            report = donor_contribution_report()
            print(f"\n{'=' * 60}")
            print("DONOR CONTRIBUTION REPORT")
            print(f"{'=' * 60}")
            for r in report:
                print(f"{r['name']}: {r['donation_count']} donations, {r['items_donated']} items, £{r['total_value']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '10':
            break


# ============================================================================
# STAFF & OPERATIONS CLI
# ============================================================================

def staff_operations_cli() -> None:
    """Staff and operations submenu."""
    while True:
        print("\n" + "=" * 50)
        print("       STAFF & OPERATIONS")
        print("=" * 50)
        print("1. Register Staff/Volunteer")
        print("2. View Staff")
        print("3. Staff Performance")
        print("4. Shift Scheduling")
        print("5. Volunteer Hours")
        print("6. Task Management")
        print("7. Opening Checklist")
        print("8. Closing Checklist")
        print("9. Cash Reconciliation")
        print("10. Manage Locations")
        print("11. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            name = input("Name: ").strip()
            email = input("Email (optional): ").strip() or None
            phone = input("Phone (optional): ").strip() or None
            role = input("Role (volunteer/staff/manager) [volunteer]: ").strip() or 'volunteer'
            staff_id = register_staff(name, email, phone, role)
            if staff_id:
                print(f"\n✅ Staff registered (ID: {staff_id})")
            input("\nPress Enter to continue...")

        elif choice == '2':
            staff = get_all_staff()
            print(f"\n{'=' * 60}")
            print("STAFF LIST")
            print(f"{'=' * 60}")
            for s in staff:
                print(f"ID {s['id']}: {s['name']} ({s['role']}) - Hours: {s['total_hours']:.1f}")
            input("\nPress Enter to continue...")

        elif choice == '3':
            staff = staff_performance_tracker()
            print(f"\n{'=' * 60}")
            print("STAFF PERFORMANCE (Last 30 Days)")
            print(f"{'=' * 60}")
            for s in staff:
                print(f"{s['name']} ({s['role']}): {s['sales_count']} sales, £{s['total_sales']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '4':
            print("1. Add Shift  2. View Date  3. View Staff Shifts")
            action = input("Choice: ").strip()
            if action == '1':
                try:
                    staff_id = int(input("Staff ID: "))
                    date = input("Date (YYYY-MM-DD): ").strip()
                    start = input("Start time (HH:MM): ").strip()
                    end = input("End time (HH:MM): ").strip()
                    shift_scheduling('add', staff_id=staff_id, date=date, start_time=start, end_time=end)
                    print("✅ Shift added!")
                except ValueError:
                    print("Invalid input.")
            elif action == '2':
                date = input("Date (YYYY-MM-DD): ").strip()
                shifts = shift_scheduling('view_date', date=date)
                print(f"\nShifts on {date}:")
                for s in shifts:
                    print(f"  {s['staff_name']}: {s['start_time']} - {s['end_time']} ({s['hours']:.1f}h)")
            elif action == '3':
                try:
                    staff_id = int(input("Staff ID: "))
                    shifts = shift_scheduling('view_staff', staff_id=staff_id)
                    print("\nRecent Shifts:")
                    for s in shifts:
                        print(f"  {s['date']}: {s['start_time']} - {s['end_time']} ({s['hours']:.1f}h)")
                except ValueError:
                    print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '5':
            try:
                staff_id = int(input("Staff ID: "))
                period = input("Period (week/month/year) [month]: ").strip() or 'month'
                hours = volunteer_hours_tracker(staff_id, period)
                if hours:
                    print(f"\n{hours['name']} ({hours['role']})")
                    print(f"Period: {hours['period']}")
                    print(f"Total Hours: {hours['total_hours']:.1f}")
                    print(f"Shifts: {hours['shift_count']}")
                    print(f"Average: {hours['average_hours']:.1f}h per shift")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '6':
            print("1. Create Task  2. View All Tasks  3. Update Status")
            action = input("Choice: ").strip()
            if action == '1':
                title = input("Task title: ").strip()
                desc = input("Description: ").strip()
                assigned = input("Assign to staff ID (optional): ").strip()
                priority = input("Priority (low/medium/high) [medium]: ").strip() or 'medium'
                due = input("Due date (YYYY-MM-DD): ").strip()
                assigned_to = int(assigned) if assigned else None
                task_id = task_assignment_system('create', title=title, description=desc,
                                                  assigned_to=assigned_to, priority=priority, due_date=due)
                print(f"✅ Task created (ID: {task_id})")
            elif action == '2':
                status = input("Status (pending/in_progress/completed) [pending]: ").strip() or 'pending'
                tasks = task_assignment_system('view_all', status=status)
                print(f"\nTasks ({status}):")
                for t in tasks:
                    print(f"  [{t['priority']}] {t['title']} - {t['staff_name']} (Due: {t['due_date']})")
            elif action == '3':
                try:
                    task_id = int(input("Task ID: "))
                    status = input("New status (pending/in_progress/completed): ").strip()
                    task_assignment_system('update_status', task_id=task_id, status=status)
                    print("✅ Status updated!")
                except ValueError:
                    print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '7':
            checklist = opening_closing_checklist('get', 'opening')
            print("\n--- OPENING CHECKLIST ---")
            for item in checklist['items']:
                status = input(f"[ ] {item['task']} (done? y/n): ").strip().lower()
                item['completed'] = status == 'y'
            completed = sum(1 for i in checklist['items'] if i['completed'])
            print(f"\n{completed}/{len(checklist['items'])} tasks completed")
            opening_closing_checklist('log', 'opening')
            input("\nPress Enter to continue...")

        elif choice == '8':
            checklist = opening_closing_checklist('get', 'closing')
            print("\n--- CLOSING CHECKLIST ---")
            for item in checklist['items']:
                status = input(f"[ ] {item['task']} (done? y/n): ").strip().lower()
                item['completed'] = status == 'y'
            completed = sum(1 for i in checklist['items'] if i['completed'])
            print(f"\n{completed}/{len(checklist['items'])} tasks completed")
            opening_closing_checklist('log', 'closing')
            input("\nPress Enter to continue...")

        elif choice == '9':
            try:
                opening = float(input("Opening float: £"))
                expected = float(input("Expected total: £"))
                actual = float(input("Actual total: £"))
                notes = input("Notes: ").strip()
                result = cash_register_reconciliation(opening, expected, actual, notes)
                print(f"\nStatus: {result['status'].upper()}")
                print(f"Difference: £{result['difference']:.2f}")
            except ValueError:
                print("Invalid input.")
            input("\nPress Enter to continue...")

        elif choice == '10':
            print("1. View Locations  2. Add Location")
            action = input("Choice: ").strip()
            if action == '1':
                locations = get_all_locations()
                print("\nLocations:")
                for loc in locations:
                    print(f"  ID {loc['id']}: {loc['name']} - {loc['address']}")
            elif action == '2':
                name = input("Location name: ").strip()
                address = input("Address: ").strip() or None
                phone = input("Phone: ").strip() or None
                manager = input("Manager: ").strip() or None
                loc_id = add_location(name, address, phone, manager)
                if loc_id:
                    print(f"✅ Location added (ID: {loc_id})")
            input("\nPress Enter to continue...")

        elif choice == '11':
            break


# Export functions for use in cli_main.py
__all__ = [
    'display_charity_shop_menu',
    'init_charity_shop_db',
    'setup_charity_shop_permissions',
    'set_auth',
    # New management functions
    'inventory_management_cli',
    'sales_pricing_cli',
    'customer_management_cli',
    'donation_management_cli',
    'staff_operations_cli',
    # Core functions
    'bulk_import_items',
    'bulk_export_items',
    'adjust_stock_quantity',
    'set_low_stock_alert',
    'view_low_stock_items',
    'merge_duplicate_items',
    'archive_old_items',
    'restore_archived_items',
    'transfer_between_locations',
    'barcode_scanner_integration',
    'apply_discount',
    'create_sale_bundle',
    'price_history_tracker',
    'dynamic_pricing_suggestions',
    'create_promotional_event',
    'process_refund',
    'layaway_system',
    'gift_card_management',
    'loyalty_points_system',
    'calculate_profit_margin',
    'generate_daily_sales_report',
    'generate_weekly_sales_report',
    'generate_monthly_sales_report',
    'best_selling_items_report',
    'slow_moving_items_report',
    'revenue_trend_analysis',
    'category_performance_comparison',
    'seasonal_trends_report',
    'donor_contribution_report',
    'tax_deduction_report',
    'register_customer',
    'customer_purchase_history',
    'customer_wishlist',
    'send_customer_notifications',
    'customer_feedback_system',
    'vip_customer_management',
    'customer_birthday_discounts',
    'customer_referral_program',
    'record_donation',
    'generate_donation_receipt',
    'donor_database',
    'donation_value_estimator',
    'donation_drive_tracker',
    'thank_you_letter_generator',
    'staff_performance_tracker',
    'shift_scheduling',
    'task_assignment_system',
    'volunteer_hours_tracker',
    'opening_closing_checklist',
    'cash_register_reconciliation',
]
