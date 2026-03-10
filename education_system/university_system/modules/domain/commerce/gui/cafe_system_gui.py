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
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
    get_current_language_name,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Import finance integration for student payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        record_payment_to_finance
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

# Import email service for receipts
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available")

# Import custom exceptions
from education_system.university_system.infrastructure.exceptions import (
    DatabaseError,
    DatabaseConnectionError,
    ValidationError
)

def get_db_connection():
    """Get database connection with proper error handling"""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        return conn
    except (sqlite3.Error, OSError) as e:
        print(f"Database connection error: {e}")
        return None

def init_db():
    """Initialize cafe database tables"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Cafe menu items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_menu_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                available INTEGER DEFAULT 1,
                stock_quantity INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Cafe orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                customer_name TEXT,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_amount REAL NOT NULL,
                payment_method TEXT,
                status TEXT DEFAULT 'pending',
                notes TEXT
            )
        ''')

        # Cafe order items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                item_id INTEGER,
                item_name TEXT,
                quantity INTEGER,
                unit_price REAL,
                subtotal REAL,
                FOREIGN KEY (order_id) REFERENCES cafe_orders(order_id),
                FOREIGN KEY (item_id) REFERENCES cafe_menu_items(item_id)
            )
        ''')

        # Cafe inventory transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_inventory_transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER,
                quantity_change INTEGER,
                transaction_type TEXT,
                transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (item_id) REFERENCES cafe_menu_items(item_id)
            )
        ''')

        conn.commit()

        # Insert sample menu items if table is empty
        cursor.execute('SELECT COUNT(*) FROM cafe_menu_items')
        if cursor.fetchone()[0] == 0:
            sample_items = [
                ('Espresso', 'Hot Drinks', 'Classic Italian espresso', 2.50, 1, 100),
                ('Cappuccino', 'Hot Drinks', 'Espresso with steamed milk and foam', 3.50, 1, 100),
                ('Latte', 'Hot Drinks', 'Espresso with steamed milk', 3.75, 1, 100),
                ('Americano', 'Hot Drinks', 'Espresso with hot water', 2.75, 1, 100),
                ('Hot Chocolate', 'Hot Drinks', 'Rich hot chocolate', 3.25, 1, 100),
                ('Tea', 'Hot Drinks', 'Selection of teas', 2.25, 1, 100),
                ('Iced Coffee', 'Cold Drinks', 'Chilled coffee over ice', 3.50, 1, 100),
                ('Iced Tea', 'Cold Drinks', 'Refreshing iced tea', 2.75, 1, 100),
                ('Smoothie', 'Cold Drinks', 'Fruit smoothie', 4.50, 1, 50),
                ('Fresh Juice', 'Cold Drinks', 'Freshly squeezed juice', 3.95, 1, 50),
                ('Croissant', 'Pastries', 'Buttery French croissant', 2.50, 1, 30),
                ('Muffin', 'Pastries', 'Blueberry or chocolate chip', 2.75, 1, 40),
                ('Danish', 'Pastries', 'Sweet pastry', 3.00, 1, 30),
                ('Cookie', 'Pastries', 'Freshly baked cookie', 1.50, 1, 60),
                ('Brownie', 'Pastries', 'Chocolate brownie', 2.95, 1, 40),
                ('Sandwich', 'Food', 'Various sandwich options', 5.50, 1, 25),
                ('Panini', 'Food', 'Grilled panini', 6.50, 1, 20),
                ('Salad', 'Food', 'Fresh garden salad', 5.95, 1, 15),
                ('Soup', 'Food', 'Soup of the day', 4.50, 1, 20),
                ('Bagel', 'Food', 'Toasted bagel with spreads', 3.25, 1, 35)
            ]
            cursor.executemany(
                'INSERT INTO cafe_menu_items (name, category, description, price, available, stock_quantity) VALUES (?, ?, ?, ?, ?, ?)',
                sample_items
            )
            conn.commit()

        conn.close()
        return True
    except sqlite3.Error as e:
        print(f"Database initialization error: {e}")
        return False


# Import mixins (after module-level functions are defined, since mixins reference them)
from .cafe_user_service import CafeUserMixin
from .cafe_pos import CafePOSMixin
from .cafe_menu import CafeMenuMixin
from .cafe_orders import CafeOrdersMixin
from .cafe_refunds import CafeRefundsMixin
from .cafe_inventory import CafeInventoryMixin
from .cafe_reports import CafeReportsMixin


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
