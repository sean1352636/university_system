"""Shared imports and module state for the split implementation."""

import logging

from datetime import datetime, timedelta

from typing import Optional, List, Dict, Tuple

import re

from education_system.systems.university.infrastructure.database.db import get_connection, transaction

from education_system.systems.university.infrastructure.shared_context import get_auth

try:
    from education_system.systems.university.domain.operations.commerce.butcher.services.butcher_core import (
        init_butcher_db, MEAT_PRODUCTS, PRODUCT_CATEGORIES
    )
    BUTCHER_CORE_AVAILABLE = True
except ImportError:
    BUTCHER_CORE_AVAILABLE = False
    MEAT_PRODUCTS = {}
    PRODUCT_CATEGORIES = ['Beef', 'Pork', 'Chicken', 'Lamb', 'Seafood', 'Deli']

    def init_butcher_db():
        """Fallback database initialization"""
        try:
            with transaction() as conn:
                # Products now use unified 'products' table with source_type='butcher'

                # Orders now use unified 'orders' table with source_type='butcher'

                # Order items now use unified 'order_items' table with source_type='butcher'

                # Inventory adjustments table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS butcher_inventory_adjustments (
                        adjustment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER NOT NULL,
                        quantity_change REAL NOT NULL,
                        reason TEXT NOT NULL,
                        adjusted_by TEXT NOT NULL,
                        adjustment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        notes TEXT,
                        FOREIGN KEY (product_id) REFERENCES products(product_id)
                    )
                ''')

                # Stock alerts table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS butcher_stock_alerts (
                        alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER NOT NULL,
                        alert_type TEXT NOT NULL,
                        alert_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        resolved BOOLEAN DEFAULT 0,
                        resolved_date TIMESTAMP,
                        FOREIGN KEY (product_id) REFERENCES products(product_id)
                    )
                ''')

                # Expiry tracking table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS butcher_product_expiry (
                        expiry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER NOT NULL,
                        batch_number TEXT,
                        quantity_kg REAL NOT NULL,
                        expiry_date DATE NOT NULL,
                        received_date DATE DEFAULT CURRENT_DATE,
                        status TEXT DEFAULT 'active',
                        FOREIGN KEY (product_id) REFERENCES products(product_id)
                    )
                ''')

                # Initialize sample products if table is empty
                cursor = conn.execute("SELECT COUNT(*) FROM products WHERE source_type = 'butcher'")
                if cursor.fetchone()[0] == 0:
                    sample_products = [
                        ('Ribeye Steak', 'Beef', 24.99, 15.0, 'Premium ribeye steak', 'Prime Meats Ltd'),
                        ('Sirloin Steak', 'Beef', 19.99, 20.0, 'Quality sirloin steak', 'Prime Meats Ltd'),
                        ('Beef Mince', 'Beef', 8.99, 30.0, 'Lean beef mince', 'Prime Meats Ltd'),
                        ('Pork Chops', 'Pork', 12.99, 18.0, 'Thick cut pork chops', 'Farm Fresh Pork'),
                        ('Pork Sausages', 'Pork', 7.99, 25.0, 'Traditional pork sausages', 'Farm Fresh Pork'),
                        ('Chicken Breast', 'Chicken', 10.99, 22.0, 'Free-range chicken breast', 'Valley Poultry'),
                        ('Whole Chicken', 'Chicken', 6.99, 15.0, 'Free-range whole chicken', 'Valley Poultry'),
                        ('Lamb Chops', 'Lamb', 18.99, 12.0, 'Premium lamb chops', 'Highland Lamb'),
                        ('Leg of Lamb', 'Lamb', 16.99, 10.0, 'Whole leg of lamb', 'Highland Lamb'),
                        ('Salmon Fillet', 'Seafood', 22.99, 8.0, 'Fresh Atlantic salmon', 'Ocean Fresh'),
                        ('Cod Fillet', 'Seafood', 16.99, 10.0, 'Fresh cod fillet', 'Ocean Fresh'),
                        ('Bacon Rashers', 'Deli', 9.99, 20.0, 'Smoked bacon rashers', 'Deli Masters'),
                        ('Ham Slices', 'Deli', 11.99, 15.0, 'Honey roast ham', 'Deli Masters'),
                    ]

                    for product in sample_products:
                        conn.execute('''
                            INSERT INTO products
                            (source_type, product_name, category, price_per_kg, stock_kg, description, supplier)
                            VALUES ('butcher', ?, ?, ?, ?, ?, ?)
                        ''', product)

                    logger.info("Initialized butcher shop with sample products")

            return True
        except Exception as e:
            logging.error(f"Database initialization error: {e}")
            return False

try:
    from education_system.systems.university.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

try:
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
        record_payment_to_finance,
        process_student_finance_account_payment
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

logger = logging.getLogger(__name__)

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
