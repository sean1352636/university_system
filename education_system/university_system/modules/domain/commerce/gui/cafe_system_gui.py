"""
Cafe System GUI for University Management System
Provides a complete point-of-sale system for campus cafes
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.university_system.infrastructure.database.db import sqlite3

# Import centralized authentication and database
from education_system.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH

# Import i18n for multi-language support
from education_system.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
    get_current_language_name,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Shared cafe helpers — also imported by every cafe_*Mixin module.  These
# live in cafe_common to break the circular import that previously
# happened when the mixin modules tried to import from cafe_system_gui.
from education_system.university_system.modules.domain.commerce.gui.cafe_common import (
    FINANCE_ACCOUNT_AVAILABLE,
    EMAIL_SERVICE_AVAILABLE,
    get_db_connection,
)
# Re-export the optional finance helpers for any external code that
# imports them via cafe_system_gui (preserves the previous module surface).
if FINANCE_ACCOUNT_AVAILABLE:
    from education_system.university_system.modules.shared.utils.finance_integration import (  # noqa: F401
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        record_payment_to_finance,
    )
if EMAIL_SERVICE_AVAILABLE:
    from education_system.university_system.infrastructure.email.email_service import send_email  # noqa: F401

# Import custom exceptions
from education_system.university_system.core.exceptions import (
    DatabaseError,
    DatabaseConnectionError,
    ValidationError
)

def init_db():
    """Initialize cafe database tables"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Unified products table (cafe items have source_type='cafe')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL DEFAULT 'cafe',
                source_product_id INTEGER,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                is_alcoholic INTEGER DEFAULT 0,
                is_available INTEGER DEFAULT 1,
                stock_quantity INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Unified orders table (cafe orders have source_type='cafe')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL DEFAULT 'cafe',
                source_order_id INTEGER,
                student_id TEXT,
                customer_name TEXT,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_amount REAL NOT NULL,
                payment_method TEXT,
                age_verified INTEGER DEFAULT 0,
                order_status TEXT DEFAULT 'pending',
                notes TEXT
            )
        ''')

        # Unified order_items table (cafe order items have source_type='cafe')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL DEFAULT 'cafe',
                source_order_id INTEGER,
                product_id INTEGER,
                item_name TEXT,
                quantity INTEGER,
                unit_price REAL,
                subtotal REAL,
                FOREIGN KEY (source_order_id) REFERENCES orders(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        ''')

        # NOTE: cafe inventory transactions now use the unified 'transactions' table
        # with source_type = 'cafe_inventory'

        conn.commit()

        # Insert sample menu items if table is empty
        cursor.execute("SELECT COUNT(*) FROM products WHERE source_type = 'cafe'")
        if cursor.fetchone()[0] == 0:
            sample_items = [
                ('cafe', 'Espresso', 'Hot Drinks', 'Classic Italian espresso', 2.50, 1, 100),
                ('cafe', 'Cappuccino', 'Hot Drinks', 'Espresso with steamed milk and foam', 3.50, 1, 100),
                ('cafe', 'Latte', 'Hot Drinks', 'Espresso with steamed milk', 3.75, 1, 100),
                ('cafe', 'Americano', 'Hot Drinks', 'Espresso with hot water', 2.75, 1, 100),
                ('cafe', 'Hot Chocolate', 'Hot Drinks', 'Rich hot chocolate', 3.25, 1, 100),
                ('cafe', 'Tea', 'Hot Drinks', 'Selection of teas', 2.25, 1, 100),
                ('cafe', 'Iced Coffee', 'Cold Drinks', 'Chilled coffee over ice', 3.50, 1, 100),
                ('cafe', 'Iced Tea', 'Cold Drinks', 'Refreshing iced tea', 2.75, 1, 100),
                ('cafe', 'Smoothie', 'Cold Drinks', 'Fruit smoothie', 4.50, 1, 50),
                ('cafe', 'Fresh Juice', 'Cold Drinks', 'Freshly squeezed juice', 3.95, 1, 50),
                ('cafe', 'Croissant', 'Pastries', 'Buttery French croissant', 2.50, 1, 30),
                ('cafe', 'Muffin', 'Pastries', 'Blueberry or chocolate chip', 2.75, 1, 40),
                ('cafe', 'Danish', 'Pastries', 'Sweet pastry', 3.00, 1, 30),
                ('cafe', 'Cookie', 'Pastries', 'Freshly baked cookie', 1.50, 1, 60),
                ('cafe', 'Brownie', 'Pastries', 'Chocolate brownie', 2.95, 1, 40),
                ('cafe', 'Sandwich', 'Food', 'Various sandwich options', 5.50, 1, 25),
                ('cafe', 'Panini', 'Food', 'Grilled panini', 6.50, 1, 20),
                ('cafe', 'Salad', 'Food', 'Fresh garden salad', 5.95, 1, 15),
                ('cafe', 'Soup', 'Food', 'Soup of the day', 4.50, 1, 20),
                ('cafe', 'Bagel', 'Food', 'Toasted bagel with spreads', 3.25, 1, 35)
            ]
            cursor.executemany(
                "INSERT INTO products (source_type, name, category, description, price, is_available, stock_quantity) VALUES (?, ?, ?, ?, ?, ?, ?)",
                sample_items
            )
            conn.commit()

        conn.close()
        return True
    except sqlite3.Error as e:
        print(f"Database initialization error: {e}")
        return False


# Import mixins (after module-level functions are defined, since mixins reference them)
from education_system.university_system.modules.domain.commerce.gui.cafe_user_service import CafeUserMixin
from education_system.university_system.modules.domain.commerce.gui.cafe_pos import CafePOSMixin
from education_system.university_system.modules.domain.commerce.gui.cafe_menu import CafeMenuMixin
from education_system.university_system.modules.domain.commerce.gui.cafe_orders import CafeOrdersMixin
from education_system.university_system.modules.domain.commerce.gui.cafe_refunds import CafeRefundsMixin
from education_system.university_system.modules.domain.commerce.gui.cafe_inventory import CafeInventoryMixin
from education_system.university_system.modules.domain.commerce.gui.cafe_reports import CafeReportsMixin


class CafeSystemGUI(CafeUserMixin, CafePOSMixin, CafeMenuMixin, CafeOrdersMixin,
                     CafeRefundsMixin, CafeInventoryMixin, CafeReportsMixin):
    """Main Cafe System GUI class"""

    def __init__(self, root, auth=None, return_to_main=None):
        """
        Initialize Cafe System GUI

        Args:
            root: Tkinter root window
            auth: Authentication instance
            return_to_main: Callback function to return to main menu
        """
        self.root = root
        self.return_to_main = return_to_main

        # Initialize i18n for multi-language support
        init_i18n()

        # Get authentication instance
        self.auth = auth if auth is not None else get_auth()
        if self.auth is None:
            self.auth = get_global_auth()

        if self.auth is None:
            messagebox.showerror(
                _t("cafe.auth_required_title"),
                _t("cafe.auth_not_available")
            )
            if hasattr(root, 'destroy'):
                root.destroy()
            return

        # Initialize database
        if not init_db():
            messagebox.showerror(_t("common.error"), _t("cafe.db_init_failed"))
            return

        # Setup current user
        self.current_user = None
        self.setup_current_user()

        # Current order tracking
        self.current_order_items = []

        # Menu item ID mapping for listbox (since Listbox doesn't support tags)
        self.menu_item_map = {}

        # Don't auto-show - let the caller decide
        self.cafe_window = None

    def show_cafe_system(self):
        """Initialize and show the cafe system interface"""
        # Check if window already exists
        if self.cafe_window is not None:
            try:
                if self.cafe_window.winfo_exists():
                    self.cafe_window.lift()
                    self.cafe_window.focus_force()
                    return
            except tk.TclError:
                pass

        # Create new window
        self.cafe_window = tk.Toplevel(self.root)
        self.cafe_window.title(_t("cafe.window_title"))
        self.cafe_window.geometry("1400x800")

        # Configure grid
        self.cafe_window.columnconfigure(0, weight=1)
        self.cafe_window.rowconfigure(1, weight=1)

        # Header
        header_frame = ttk.Frame(self.cafe_window, style='Header.TFrame')
        header_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=10)

        self.title_label = ttk.Label(
            header_frame,
            text=_t("cafe.header_title"),
            font=('Helvetica', 20, 'bold')
        )
        self.title_label.pack(side=tk.LEFT, padx=10)

        # User info
        user_info = _t("cafe.user_info", username=self.current_user['username'], role=self.current_user['role'])
        self.user_label = ttk.Label(header_frame, text=user_info, font=('Helvetica', 10))
        self.user_label.pack(side=tk.RIGHT, padx=10)

        # Language button
        self.lang_btn = ttk.Button(
            header_frame,
            text=f"{_t('menu.language')}: {get_current_language_name()}",
            command=self.change_language
        )
        self.lang_btn.pack(side=tk.RIGHT, padx=5)

        # Return to homepage button
        self.return_btn = ttk.Button(
            header_frame,
            text=_t("cafe.return_to_homepage"),
            command=self.return_to_homepage
        )
        self.return_btn.pack(side=tk.RIGHT, padx=5)

        # Main content with notebook tabs
        self.notebook = ttk.Notebook(self.cafe_window)
        self.notebook.grid(row=1, column=0, sticky='nsew', padx=10, pady=(0, 10))

        # Create tabs
        self.create_pos_tab()
        self.create_menu_management_tab()
        self.create_orders_tab()
        self.create_inventory_tab()
        self.create_reports_tab()

    def change_language(self):
        """Open language selector and refresh UI on change"""
        old_lang = get_current_language()
        show_gui_language_selector(self.cafe_window)
        new_lang = get_current_language()
        if old_lang != new_lang:
            self.refresh_ui_text()

    def refresh_ui_text(self):
        """Refresh all UI text after language change"""
        self.cafe_window.title(_t("cafe.window_title"))
        # Recreate the interface to apply language changes
        for widget in self.cafe_window.winfo_children():
            widget.destroy()
        # Reinitialize the interface
        self.cafe_window.columnconfigure(0, weight=1)
        self.cafe_window.rowconfigure(1, weight=1)

        # Recreate header
        header_frame = ttk.Frame(self.cafe_window, style='Header.TFrame')
        header_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=10)

        self.title_label = ttk.Label(
            header_frame,
            text=_t("cafe.header_title"),
            font=('Helvetica', 20, 'bold')
        )
        self.title_label.pack(side=tk.LEFT, padx=10)

        user_info = _t("cafe.user_info", username=self.current_user['username'], role=self.current_user['role'])
        self.user_label = ttk.Label(header_frame, text=user_info, font=('Helvetica', 10))
        self.user_label.pack(side=tk.RIGHT, padx=10)

        self.lang_btn = ttk.Button(
            header_frame,
            text=f"{_t('menu.language')}: {get_current_language_name()}",
            command=self.change_language
        )
        self.lang_btn.pack(side=tk.RIGHT, padx=5)

        self.return_btn = ttk.Button(
            header_frame,
            text=_t("cafe.return_to_homepage"),
            command=self.return_to_homepage
        )
        self.return_btn.pack(side=tk.RIGHT, padx=5)

        self.notebook = ttk.Notebook(self.cafe_window)
        self.notebook.grid(row=1, column=0, sticky='nsew', padx=10, pady=(0, 10))

        self.create_pos_tab()
        self.create_menu_management_tab()
        self.create_orders_tab()
        self.create_refunds_tab()
        self.create_inventory_tab()
        self.create_reports_tab()

    def return_to_homepage(self):
        """Return to main homepage"""
        if self.cafe_window:
            self.cafe_window.destroy()
            self.cafe_window = None

        # Call the return_to_main callback if provided
        if self.return_to_main:
            self.return_to_main()

def main():
    """Standalone main function for testing"""
    root = tk.Tk()
    root.withdraw()  # Hide main window

    cafe_gui = CafeSystemGUI(root)
    cafe_gui.show_cafe_system()

    root.mainloop()

if __name__ == "__main__":
    main()
