#!/usr/bin/env python3
"""
Charity Shop Stock Management System
A GUI application for managing charity shop inventory with SQLite persistence.
Features: Stock tracking, sold status, revenue calculation, and data visualization.

Integrated with the University Management System.
"""

from university_system.infrastructure.database.db import sqlite3
from university_system.core.sql_safety import validate_table_name
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
from datetime import datetime, timedelta
from pathlib import Path
import logging
import json
import os

# University system imports
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from university_system.infrastructure.shared_context import get_auth, get_current_user
from university_system.core.sql_safety import safe_alter_table_add_column

# Import activity logger for audit trail
try:
    from university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import i18n for language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import finance integration for revenue tracking and student payments
try:
    from university_system.modules.shared.utils.finance_integration import (
        record_revenue_to_finance,
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        get_student_email,
    )
    FINANCE_INTEGRATION_AVAILABLE = True
except ImportError:
    FINANCE_INTEGRATION_AVAILABLE = False
    record_revenue_to_finance = lambda *args, **kwargs: None
    process_student_finance_account_payment = lambda *args, **kwargs: {'success': False, 'message': 'Finance integration not available'}
    get_student_finance_account_balance = lambda x: None
    get_student_info = lambda x: None
    get_student_email = lambda x: None

# Import email service for receipts
try:
    from university_system.infrastructure.email.email_service import send_email
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    send_email = lambda *args, **kwargs: False

logger = logging.getLogger(__name__)

# Email templates directory
EMAIL_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates" / "email"

def load_email_template(template_name: str) -> dict:
    """
    Load an email template from JSON file.

    Args:
        template_name: Name of the template file (without .json extension)

    Returns:
        Dictionary with 'subject' and 'body' keys, or empty dict if not found
    """
    try:
        template_path = EMAIL_TEMPLATES_DIR / f"{template_name}.json"
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            logger.warning(f"Email template not found: {template_path}")
            return {}
    except Exception as e:
        logger.error(f"Error loading email template {template_name}: {e}")
        return {}

def render_email_template(template: dict, variables: dict) -> tuple:
    """
    Render an email template by replacing variables.

    Args:
        template: Dictionary with 'subject' and 'body' keys
        variables: Dictionary of variable names and values to substitute

    Returns:
        Tuple of (subject, body) with variables replaced
    """
    if not template:
        return "", ""

    subject = template.get('subject', '')
    body = template.get('body', '')

    # Replace variables (using $variable_name format)
    for key, value in variables.items():
        subject = subject.replace(f'${key}', str(value))
        body = body.replace(f'${key}', str(value))

    return subject, body

# Try to import matplotlib for charts
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib not installed. Charts will be disabled.")

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
            params = [f"%{search_term}%"]

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

class ItemDialog(tk.Toplevel):
    """Dialog for adding/editing stock items."""

    CATEGORIES = [
        "Books", "Clothing", "Electronics", "Furniture", "Homeware",
        "Toys", "Music/DVDs", "Accessories", "Sports", "Other"
    ]

    CONDITIONS = ["New", "Excellent", "Good", "Fair", "Poor"]

    def __init__(self, parent, title: str, item_data: tuple = None):
        super().__init__(parent)
        self.title(title)
        self.result = None
        self.item_data = item_data

        self.transient(parent)

        self.geometry("400x420")
        self.resizable(False, False)

        self.create_widgets()

        if item_data:
            self.populate_fields(item_data)

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        # Wait for window to be visible before grabbing focus
        self.wait_visibility()
        self.grab_set()
        self.wait_window(self)

    def create_widgets(self):
        """Create dialog widgets."""
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Name
        ttk.Label(main_frame, text=_t("charity_shop.labels.item_name")).grid(row=0, column=0, sticky="w", pady=5)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(main_frame, textvariable=self.name_var, width=35)
        self.name_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        # Category
        ttk.Label(main_frame, text=_t("charity_shop.labels.category")).grid(row=1, column=0, sticky="w", pady=5)
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(main_frame, textvariable=self.category_var,
                                           values=self.CATEGORIES, width=32, state="readonly")
        self.category_combo.grid(row=1, column=1, pady=5, padx=(10, 0))
        self.category_combo.set(self.CATEGORIES[0])

        # Price
        ttk.Label(main_frame, text=_t("charity_shop.labels.price")).grid(row=2, column=0, sticky="w", pady=5)
        self.price_var = tk.StringVar()
        self.price_entry = ttk.Entry(main_frame, textvariable=self.price_var, width=35)
        self.price_entry.grid(row=2, column=1, pady=5, padx=(10, 0))

        # Quantity
        ttk.Label(main_frame, text=_t("charity_shop.labels.quantity")).grid(row=3, column=0, sticky="w", pady=5)
        self.quantity_var = tk.StringVar(value="1")
        self.quantity_spinbox = ttk.Spinbox(main_frame, textvariable=self.quantity_var,
                                            from_=0, to=9999, width=33)
        self.quantity_spinbox.grid(row=3, column=1, pady=5, padx=(10, 0))

        # Condition
        ttk.Label(main_frame, text=_t("charity_shop.labels.condition")).grid(row=4, column=0, sticky="w", pady=5)
        self.condition_var = tk.StringVar()
        self.condition_combo = ttk.Combobox(main_frame, textvariable=self.condition_var,
                                            values=self.CONDITIONS, width=32, state="readonly")
        self.condition_combo.grid(row=4, column=1, pady=5, padx=(10, 0))
        self.condition_combo.set("Good")

        # Sold Status
        ttk.Label(main_frame, text="Status:").grid(row=5, column=0, sticky="w", pady=5)
        self.sold_var = tk.BooleanVar(value=False)
        self.sold_check = ttk.Checkbutton(main_frame, text="Mark as Sold", variable=self.sold_var)
        self.sold_check.grid(row=5, column=1, pady=5, padx=(10, 0), sticky="w")

        # Sold Quantity
        ttk.Label(main_frame, text="Qty Sold:").grid(row=6, column=0, sticky="w", pady=5)
        self.sold_qty_var = tk.StringVar(value="0")
        self.sold_qty_spinbox = ttk.Spinbox(main_frame, textvariable=self.sold_qty_var,
                                             from_=0, to=9999, width=33)
        self.sold_qty_spinbox.grid(row=6, column=1, pady=5, padx=(10, 0))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=30)

        ttk.Button(button_frame, text="Save", command=self.save, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel, width=12).pack(side=tk.LEFT, padx=5)

        self.name_entry.focus_set()

    def populate_fields(self, item_data):
        """Populate fields with existing item data."""
        # item_data: (id, name, category, price, quantity, condition, date_added, sold, sold_date, sold_quantity)
        self.name_var.set(item_data[1])
        self.category_var.set(item_data[2])
        self.price_var.set(f"{item_data[3]:.2f}")
        self.quantity_var.set(str(item_data[4]))
        self.condition_var.set(item_data[5])
        self.sold_var.set(bool(item_data[7]) if len(item_data) > 7 else False)
        self.sold_qty_var.set(str(item_data[9]) if len(item_data) > 9 and item_data[9] else "0")

    def validate(self):
        """Validate input fields."""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Validation Error", "Please enter an item name.", parent=self)
            return False

        try:
            price = float(self.price_var.get())
            if price < 0:
                raise ValueError("Price must be positive")
        except ValueError:
            messagebox.showerror("Validation Error", "Please enter a valid price.", parent=self)
            return False

        try:
            quantity = int(self.quantity_var.get())
            if quantity < 0:
                raise ValueError("Quantity must be positive")
        except ValueError:
            messagebox.showerror("Validation Error", "Please enter a valid quantity.", parent=self)
            return False

        try:
            sold_qty = int(self.sold_qty_var.get())
            if sold_qty < 0:
                raise ValueError("Sold quantity must be positive")
        except ValueError:
            messagebox.showerror("Validation Error", "Please enter a valid sold quantity.", parent=self)
            return False

        return True

    def save(self):
        """Save and close dialog."""
        if self.validate():
            self.result = {
                "name": self.name_var.get().strip(),
                "category": self.category_var.get(),
                "price": float(self.price_var.get()),
                "quantity": int(self.quantity_var.get()),
                "condition": self.condition_var.get(),
                "sold": self.sold_var.get(),
                "sold_quantity": int(self.sold_qty_var.get())
            }
            self.destroy()

    def cancel(self):
        """Cancel and close dialog."""
        self.result = None
        self.destroy()

class SellDialog(tk.Toplevel):
    """Dialog for selling items with payment method selection."""

    PAYMENT_METHODS = ["Cash", "Debit/Credit Card", "Finance Account"]

    def __init__(self, parent, item_name: str, max_quantity: int, unit_price: float, current_user: dict = None):
        super().__init__(parent)
        self.title("Sell Item")
        self.result = None
        self.max_quantity = max_quantity
        self.unit_price = unit_price
        self.item_name = item_name
        self.current_user = current_user

        self.transient(parent)

        self.geometry("450x420")
        self.resizable(False, False)

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        # Wait for window to be visible before grabbing focus
        self.wait_visibility()
        self.grab_set()
        self.wait_window(self)

    def create_widgets(self):
        """Create dialog widgets."""
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Item info header
        ttk.Label(main_frame, text=f"Selling: {self.item_name}", font=("Helvetica", 12, "bold")).pack(pady=(0, 5))
        ttk.Label(main_frame, text=f"Price: £{self.unit_price:.2f} each | Available: {self.max_quantity}").pack(pady=(0, 15))

        # Quantity selection
        qty_frame = ttk.LabelFrame(main_frame, text="Quantity", padding="10")
        qty_frame.pack(fill=tk.X, pady=5)

        qty_inner = ttk.Frame(qty_frame)
        qty_inner.pack()

        ttk.Label(qty_inner, text="Quantity to sell:").pack(side=tk.LEFT)
        self.qty_var = tk.StringVar(value="1")
        self.qty_spinbox = ttk.Spinbox(qty_inner, textvariable=self.qty_var,
                                        from_=1, to=self.max_quantity, width=10,
                                        command=self.update_total)
        self.qty_spinbox.pack(side=tk.LEFT, padx=10)
        self.qty_spinbox.bind('<KeyRelease>', lambda e: self.update_total())

        # Total display
        self.total_label = ttk.Label(qty_frame, text=f"Total: £{self.unit_price:.2f}", font=("Helvetica", 11, "bold"))
        self.total_label.pack(pady=5)

        # Customer info - display current logged-in user (read-only)
        customer_frame = ttk.LabelFrame(main_frame, text="Customer (Logged-in User)", padding="10")
        customer_frame.pack(fill=tk.X, pady=10)

        # Get current user details
        self.user_id = ""
        self.user_email = ""
        self.user_name = "Guest"
        if self.current_user:
            self.user_id = self.current_user.get('student_id') or self.current_user.get('username', '')
            self.user_email = self.current_user.get('email', '')
            first_name = self.current_user.get('first_name', '')
            last_name = self.current_user.get('last_name', '')
            self.user_name = f"{first_name} {last_name}".strip() or self.current_user.get('username', 'Guest')

            # If no email in current_user, try to fetch from database
            if not self.user_email and self.user_id and FINANCE_INTEGRATION_AVAILABLE:
                self.user_email = get_student_email(self.user_id) or ""

        # Display user info (read-only)
        ttk.Label(customer_frame, text=f"Name: {self.user_name}", font=("Helvetica", 10)).pack(anchor=tk.W, pady=2)
        ttk.Label(customer_frame, text=f"ID: {self.user_id}", font=("Helvetica", 10)).pack(anchor=tk.W, pady=2)
        ttk.Label(customer_frame, text=f"Email: {self.user_email or '(not set)'}", font=("Helvetica", 10)).pack(anchor=tk.W, pady=2)

        # Balance display
        self.balance_label = ttk.Label(customer_frame, text="", foreground="blue", font=("Helvetica", 10, "bold"))
        self.balance_label.pack(anchor=tk.W, pady=5)

        # Auto-lookup balance
        if self.user_id:
            self.after(100, self._load_balance)

        # Payment method
        payment_frame = ttk.LabelFrame(main_frame, text="Payment Method", padding="10")
        payment_frame.pack(fill=tk.X, pady=10)

        self.payment_var = tk.StringVar(value="Cash")
        for method in self.PAYMENT_METHODS:
            ttk.Radiobutton(payment_frame, text=method, variable=self.payment_var, value=method).pack(anchor=tk.W)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=15)

        ttk.Button(button_frame, text="Complete Sale", command=self.sell, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Sell All", command=self.sell_all, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel, width=10).pack(side=tk.LEFT, padx=5)

    def update_total(self):
        """Update the total price display."""
        try:
            qty = int(self.qty_var.get())
            total = qty * self.unit_price
            self.total_label.config(text=f"Total: £{total:.2f}")
        except ValueError:
            self.total_label.config(text=f"Total: £{self.unit_price:.2f}")

    def _load_balance(self):
        """Load the current user's finance account balance."""
        if not self.user_id or not FINANCE_INTEGRATION_AVAILABLE:
            return

        balance = get_student_finance_account_balance(self.user_id)
        if balance is not None:
            color = "green" if balance >= self.unit_price else "red"
            self.balance_label.config(text=f"Finance Balance: £{balance:.2f}", foreground=color)
        else:
            self.balance_label.config(text="No finance account", foreground="orange")

    def validate_sale(self) -> bool:
        """Validate the sale before processing."""
        try:
            qty = int(self.qty_var.get())
            if qty < 1 or qty > self.max_quantity:
                messagebox.showerror("Error", f"Quantity must be between 1 and {self.max_quantity}", parent=self)
                return False
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid quantity", parent=self)
            return False

        # If paying with Finance Account, verify user has balance
        if self.payment_var.get() == "Finance Account":
            if not self.user_id:
                messagebox.showerror("Error", "You must be logged in to use Finance Account payment", parent=self)
                return False

            if FINANCE_INTEGRATION_AVAILABLE:
                balance = get_student_finance_account_balance(self.user_id)
                total = qty * self.unit_price
                if balance is None:
                    messagebox.showerror("Error", "You do not have a finance account", parent=self)
                    return False
                if balance < total:
                    messagebox.showerror("Error", f"Insufficient balance. Current: £{balance:.2f}, Required: £{total:.2f}", parent=self)
                    return False

        return True

    def sell(self):
        """Complete the sale with specified quantity."""
        if not self.validate_sale():
            return

        qty = int(self.qty_var.get())
        total = qty * self.unit_price

        self.result = {
            'quantity': qty,
            'total': total,
            'payment_method': self.payment_var.get(),
            'student_id': self.user_id or None,
            'customer_email': self.user_email or None
        }
        self.destroy()

    def sell_all(self):
        """Sell all available quantity."""
        self.qty_var.set(str(self.max_quantity))
        self.update_total()
        self.sell()

    def cancel(self):
        """Cancel and close dialog."""
        self.result = None
        self.destroy()

class ChartsWindow(tk.Toplevel):
    """Window for displaying charts and analytics."""

    def __init__(self, parent, db: Database):
        super().__init__(parent)
        self.title("Sales Analytics & Charts")
        self.geometry("900x700")
        self.db = db

        if not MATPLOTLIB_AVAILABLE:
            ttk.Label(self, text="matplotlib is not installed.\nPlease install it with: pip install matplotlib",
                     font=("Helvetica", 12)).pack(expand=True)
            return

        self.create_widgets()

    def create_widgets(self):
        """Create chart widgets."""
        # Create notebook for different chart tabs
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Revenue Overview Tab
        revenue_frame = ttk.Frame(notebook)
        notebook.add(revenue_frame, text="Revenue Overview")
        self.create_revenue_overview(revenue_frame)

        # Category Breakdown Tab
        category_frame = ttk.Frame(notebook)
        notebook.add(category_frame, text="Category Analysis")
        self.create_category_charts(category_frame)

        # Sales Timeline Tab
        timeline_frame = ttk.Frame(notebook)
        notebook.add(timeline_frame, text="Sales Timeline")
        self.create_timeline_chart(timeline_frame)

        # Stock Status Tab
        stock_frame = ttk.Frame(notebook)
        notebook.add(stock_frame, text="Stock Status")
        self.create_stock_charts(stock_frame)

    def create_revenue_overview(self, parent):
        """Create revenue overview with summary stats."""
        # Summary stats at top
        stats_frame = ttk.LabelFrame(parent, text="Revenue Summary", padding="10")
        stats_frame.pack(fill=tk.X, padx=10, pady=10)

        revenue_data = self.db.get_revenue_summary()
        stock_data = self.db.get_stock_summary()

        sold_items = revenue_data[0] or 0
        total_sold = revenue_data[1] or 0
        total_revenue = revenue_data[2] or 0.0

        stock_items = stock_data[0] or 0
        stock_qty = stock_data[1] or 0
        stock_value = stock_data[2] or 0.0

        # Create stats grid
        stats = [
            ("Total Revenue:", f"£{total_revenue:.2f}"),
            ("Items Sold:", str(total_sold)),
            ("Unique Products Sold:", str(sold_items)),
            ("Current Stock Items:", str(stock_items)),
            ("Current Stock Qty:", str(stock_qty)),
            ("Stock Value:", f"£{stock_value:.2f}"),
        ]

        for i, (label, value) in enumerate(stats):
            row, col = divmod(i, 3)
            ttk.Label(stats_frame, text=label, font=("Helvetica", 10)).grid(row=row, column=col*2, sticky="e", padx=5, pady=5)
            ttk.Label(stats_frame, text=value, font=("Helvetica", 10, "bold")).grid(row=row, column=col*2+1, sticky="w", padx=5, pady=5)

        # Pie chart: Revenue vs Remaining Stock Value
        fig = Figure(figsize=(8, 4), dpi=100)
        ax = fig.add_subplot(121)

        if total_revenue > 0 or stock_value > 0:
            values = [total_revenue, stock_value]
            labels = [f'Revenue\n£{total_revenue:.2f}', f'Stock Value\n£{stock_value:.2f}']
            colors = ['#2ecc71', '#3498db']
            ax.pie(values, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
            ax.set_title('Revenue vs Stock Value')
        else:
            ax.text(0.5, 0.5, 'No data available', ha='center', va='center')
            ax.set_title('Revenue vs Stock Value')

        # Bar chart: Sold vs Available
        ax2 = fig.add_subplot(122)
        categories = ['Items Sold', 'In Stock']
        values = [total_sold, stock_qty]
        colors = ['#2ecc71', '#3498db']
        ax2.bar(categories, values, color=colors)
        ax2.set_ylabel('Quantity')
        ax2.set_title('Sold vs Available Stock')

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def create_category_charts(self, parent):
        """Create category breakdown charts."""
        fig = Figure(figsize=(10, 5), dpi=100)

        # Revenue by category (pie chart)
        ax1 = fig.add_subplot(121)
        revenue_by_cat = self.db.get_revenue_by_category()

        if revenue_by_cat:
            categories = [r[0] for r in revenue_by_cat]
            revenues = [r[1] for r in revenue_by_cat]
            colors = plt.cm.Set3(range(len(categories)))
            ax1.pie(revenues, labels=categories, autopct='%1.1f%%', colors=colors, startangle=90)
            ax1.set_title('Revenue by Category')
        else:
            ax1.text(0.5, 0.5, 'No sales data', ha='center', va='center')
            ax1.set_title('Revenue by Category')

        # Stock by category (bar chart)
        ax2 = fig.add_subplot(122)
        stock_by_cat = self.db.get_stock_by_category()

        if stock_by_cat:
            categories = [s[0] for s in stock_by_cat]
            quantities = [s[2] for s in stock_by_cat]
            colors = plt.cm.Set3(range(len(categories)))
            bars = ax2.barh(categories, quantities, color=colors)
            ax2.set_xlabel('Quantity')
            ax2.set_title('Current Stock by Category')
            ax2.invert_yaxis()
        else:
            ax2.text(0.5, 0.5, 'No stock data', ha='center', va='center')
            ax2.set_title('Current Stock by Category')

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def create_timeline_chart(self, parent):
        """Create sales timeline chart."""
        # Controls frame
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(control_frame, text="Show last:").pack(side=tk.LEFT)
        self.days_var = tk.StringVar(value="30")
        days_combo = ttk.Combobox(control_frame, textvariable=self.days_var,
                                  values=["7", "14", "30", "60", "90"], width=5, state="readonly")
        days_combo.pack(side=tk.LEFT, padx=5)
        ttk.Label(control_frame, text="days").pack(side=tk.LEFT)

        self.timeline_container = ttk.Frame(parent)
        self.timeline_container.pack(fill=tk.BOTH, expand=True)

        days_combo.bind("<<ComboboxSelected>>", lambda e: self.update_timeline())
        self.update_timeline()

    def update_timeline(self):
        """Update the timeline chart."""
        for widget in self.timeline_container.winfo_children():
            widget.destroy()

        days = int(self.days_var.get())
        revenue_by_date = self.db.get_revenue_by_date(days)

        fig = Figure(figsize=(10, 5), dpi=100)
        ax = fig.add_subplot(111)

        if revenue_by_date:
            dates = [r[0] for r in revenue_by_date]
            revenues = [r[1] for r in revenue_by_date]

            ax.plot(dates, revenues, marker='o', linewidth=2, markersize=6, color='#2ecc71')
            ax.fill_between(dates, revenues, alpha=0.3, color='#2ecc71')
            ax.set_xlabel('Date')
            ax.set_ylabel('Revenue (£)')
            ax.set_title(f'Daily Revenue - Last {days} Days')
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

            # Add total
            total = sum(revenues)
            ax.text(0.02, 0.98, f'Total: £{total:.2f}', transform=ax.transAxes,
                   fontsize=12, verticalalignment='top', fontweight='bold')
        else:
            ax.text(0.5, 0.5, f'No sales in the last {days} days', ha='center', va='center')
            ax.set_title(f'Daily Revenue - Last {days} Days')

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, self.timeline_container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def create_stock_charts(self, parent):
        """Create stock status charts."""
        fig = Figure(figsize=(10, 5), dpi=100)

        # Sales by condition
        ax1 = fig.add_subplot(121)
        sales_by_condition = self.db.get_sales_by_condition()

        if sales_by_condition:
            conditions = [s[0] for s in sales_by_condition]
            revenues = [s[2] for s in sales_by_condition]
            colors = ['#27ae60', '#2ecc71', '#f1c40f', '#e67e22', '#e74c3c']
            ax1.bar(conditions, revenues, color=colors[:len(conditions)])
            ax1.set_xlabel('Condition')
            ax1.set_ylabel('Revenue (£)')
            ax1.set_title('Revenue by Item Condition')
        else:
            ax1.text(0.5, 0.5, 'No sales data', ha='center', va='center')
            ax1.set_title('Revenue by Item Condition')

        # Stock health (quantity distribution)
        ax2 = fig.add_subplot(122)
        stock_items = self.db.get_all_stock(show_sold="available")

        if stock_items:
            quantities = [item[4] for item in stock_items]
            bins = [0, 1, 5, 10, 20, 50, max(quantities)+1] if max(quantities) > 50 else [0, 1, 5, 10, 20, 50]
            ax2.hist(quantities, bins=bins, color='#3498db', edgecolor='white')
            ax2.set_xlabel('Quantity per Item')
            ax2.set_ylabel('Number of Items')
            ax2.set_title('Stock Quantity Distribution')
        else:
            ax2.text(0.5, 0.5, 'No stock data', ha='center', va='center')
            ax2.set_title('Stock Quantity Distribution')

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

class CharityShopApp:
    """Main application class for Charity Shop Stock Management.

    Integrated with the University Management System for authentication
    and database connectivity.
    """

    def __init__(self, root: tk.Tk, auth=None):
        """Initialize the Charity Shop application.

        Args:
            root: The Tkinter root or toplevel window
            auth: Optional authentication instance from the university system
        """
        # Initialize i18n for language support
        init_i18n()

        self.root = root
        self.root.title(_t("charity_shop.title"))
        self.root.geometry("1100x650")
        self.root.minsize(900, 550)

        # Store auth instance (use shared context if not provided)
        self.auth = auth if auth else get_auth()
        self.current_user = get_current_user()

        # Initialize database (uses student_records.db by default)
        self.db = Database()

        # Initialize shopping basket
        # Each item: {'id': int, 'name': str, 'price': float, 'quantity': int, 'max_qty': int}
        self.basket = []
        self.basket_window = None  # Reference to basket window if open

        self.create_menu()
        self.create_widgets()
        self.refresh_stock_list()
        self.update_summary()

        # Log access
        if ACTIVITY_LOGGER_AVAILABLE and self.current_user:
            log_activity('access', 'charity_shop', details={'user': self.current_user.get('username', 'unknown')})

    def close_window(self):
        """Close the charity shop window and return to homepage."""
        self.root.destroy()

    def create_menu(self):
        """Create application menu."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("charity_shop.menu.file"), menu=file_menu)
        file_menu.add_command(label=_t("charity_shop.menu.add_new_item"), command=self.add_item, accelerator="Ctrl+N")
        file_menu.add_separator()
        file_menu.add_command(label=_t("charity_shop.menu.exit"), command=self.root.quit, accelerator="Ctrl+Q")

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("charity_shop.menu.edit"), menu=edit_menu)
        edit_menu.add_command(label=_t("charity_shop.menu.edit_selected"), command=self.edit_item, accelerator="Ctrl+E")
        edit_menu.add_command(label=_t("charity_shop.menu.delete_selected"), command=self.delete_item, accelerator="Delete")
        edit_menu.add_separator()
        edit_menu.add_command(label=_t("charity_shop.menu.mark_as_sold"), command=self.sell_item, accelerator="Ctrl+S")
        edit_menu.add_command(label=_t("charity_shop.menu.mark_as_available"), command=self.mark_available)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("charity_shop.menu.view"), menu=view_menu)
        view_menu.add_command(label=_t("charity_shop.menu.refresh"), command=self.refresh_stock_list, accelerator="F5")
        view_menu.add_command(label=_t("charity_shop.menu.clear_search"), command=self.clear_search)
        view_menu.add_separator()
        view_menu.add_command(label=_t("charity_shop.menu.view_charts"), command=self.show_charts, accelerator="Ctrl+G")

        # Reports menu
        reports_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("charity_shop.menu.reports"), menu=reports_menu)
        reports_menu.add_command(label=_t("charity_shop.menu.daily_sales"), command=lambda: self.show_report_with_type('daily'))
        reports_menu.add_command(label=_t("charity_shop.menu.weekly_sales"), command=lambda: self.show_report_with_type('weekly'))
        reports_menu.add_command(label=_t("charity_shop.menu.monthly_sales"), command=lambda: self.show_report_with_type('monthly'))
        reports_menu.add_command(label=_t("charity_shop.menu.total_revenue"), command=lambda: self.show_report_with_type('total'))
        reports_menu.add_separator()
        reports_menu.add_command(label=_t("charity_shop.menu.stock_status"), command=lambda: self.show_report_with_type('stock'))
        reports_menu.add_command(label=_t("charity_shop.menu.category_analysis"), command=lambda: self.show_report_with_type('category'))
        reports_menu.add_separator()
        reports_menu.add_command(label=_t("charity_shop.menu.open_reports"), command=self.show_reports_window, accelerator="Ctrl+R")

        # Refunds menu
        refunds_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Refunds", menu=refunds_menu)
        refunds_menu.add_command(label="Manage Refunds", command=self.show_refunds_window)

        # Bind keyboard shortcuts
        self.root.bind("<Control-n>", lambda e: self.add_item())
        self.root.bind("<Control-q>", lambda e: self.root.quit())
        self.root.bind("<Control-e>", lambda e: self.edit_item())
        self.root.bind("<Control-s>", lambda e: self.sell_item())
        self.root.bind("<Control-g>", lambda e: self.show_charts())
        self.root.bind("<Control-r>", lambda e: self.show_reports_window())
        self.root.bind("<Delete>", lambda e: self.delete_item())
        self.root.bind("<F5>", lambda e: self.refresh_stock_list())

    def create_widgets(self):
        """Create main application widgets."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header with title and summary
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        title_label = ttk.Label(header_frame, text=_t("charity_shop.header.stock_management"),
                                font=("Helvetica", 16, "bold"))
        title_label.pack(side=tk.LEFT)

        # Summary frames
        summary_container = ttk.Frame(header_frame)
        summary_container.pack(side=tk.RIGHT)

        # Stock summary
        self.stock_summary_frame = ttk.LabelFrame(summary_container, text=_t("charity_shop.summary.stock"), padding="5")
        self.stock_summary_frame.pack(side=tk.LEFT, padx=(0, 10))

        self.items_label = ttk.Label(self.stock_summary_frame, text="Items: 0")
        self.items_label.pack(side=tk.LEFT, padx=5)

        self.quantity_label = ttk.Label(self.stock_summary_frame, text="Qty: 0")
        self.quantity_label.pack(side=tk.LEFT, padx=5)

        self.value_label = ttk.Label(self.stock_summary_frame, text="Value: £0.00")
        self.value_label.pack(side=tk.LEFT, padx=5)

        # Revenue summary
        self.revenue_summary_frame = ttk.LabelFrame(summary_container, text=_t("charity_shop.summary.revenue"), padding="5")
        self.revenue_summary_frame.pack(side=tk.LEFT)

        self.sold_label = ttk.Label(self.revenue_summary_frame, text="Sold: 0")
        self.sold_label.pack(side=tk.LEFT, padx=5)

        self.revenue_label = ttk.Label(self.revenue_summary_frame, text="Revenue: £0.00", foreground="green")
        self.revenue_label.pack(side=tk.LEFT, padx=5)

        # Return to Homepage button
        ttk.Button(summary_container, text=_t("charity_shop.btn.return_home"),
                   command=self.close_window).pack(side=tk.LEFT, padx=(15, 0))

        # Search and filter frame
        search_frame = ttk.LabelFrame(main_frame, text=_t("charity_shop.filter.search_filter"), padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text=_t("charity_shop.filter.search")).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.on_search())
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=25)
        search_entry.pack(side=tk.LEFT, padx=(5, 15))

        ttk.Label(search_frame, text=_t("charity_shop.filter.category")).pack(side=tk.LEFT)
        self.filter_category_var = tk.StringVar(value="All")
        self.category_filter = ttk.Combobox(search_frame, textvariable=self.filter_category_var,
                                            values=["All"] + ItemDialog.CATEGORIES, width=12, state="readonly")
        self.category_filter.pack(side=tk.LEFT, padx=5)
        self.category_filter.bind("<<ComboboxSelected>>", lambda e: self.on_search())

        ttk.Label(search_frame, text=_t("charity_shop.filter.status")).pack(side=tk.LEFT, padx=(15, 0))
        self.filter_status_var = tk.StringVar(value="all")
        self.status_filter = ttk.Combobox(search_frame, textvariable=self.filter_status_var,
                                          values=["all", "available", "sold"], width=10, state="readonly")
        self.status_filter.pack(side=tk.LEFT, padx=5)
        self.status_filter.bind("<<ComboboxSelected>>", lambda e: self.on_search())

        ttk.Button(search_frame, text=_t("charity_shop.btn.clear"), command=self.clear_search).pack(side=tk.LEFT, padx=10)
        ttk.Button(search_frame, text=_t("charity_shop.btn.charts"), command=self.show_charts).pack(side=tk.RIGHT, padx=5)

        # Stock table frame
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Create Treeview with scrollbars
        columns = ("id", "name", "category", "price", "quantity", "condition", "status", "sold_qty", "date_added")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        # Define column headings and widths
        self.tree.heading("id", text=_t("charity_shop.table.id"))
        self.tree.heading("name", text=_t("charity_shop.table.item_name"))
        self.tree.heading("category", text=_t("charity_shop.table.category"))
        self.tree.heading("price", text=_t("charity_shop.table.price"))
        self.tree.heading("quantity", text=_t("charity_shop.table.qty"))
        self.tree.heading("condition", text=_t("charity_shop.table.condition"))
        self.tree.heading("status", text=_t("charity_shop.table.status"))
        self.tree.heading("sold_qty", text=_t("charity_shop.table.sold"))
        self.tree.heading("date_added", text=_t("charity_shop.table.date_added"))

        self.tree.column("id", width=50, anchor="center")
        self.tree.column("name", width=200, anchor="w")
        self.tree.column("category", width=100, anchor="center")
        self.tree.column("price", width=80, anchor="e")
        self.tree.column("quantity", width=50, anchor="center")
        self.tree.column("condition", width=80, anchor="center")
        self.tree.column("status", width=80, anchor="center")
        self.tree.column("sold_qty", width=50, anchor="center")
        self.tree.column("date_added", width=90, anchor="center")

        # Configure tags for row colors
        self.tree.tag_configure('sold', background='#d5f5e3')
        self.tree.tag_configure('low_stock', background='#fadbd8')

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        # Grid layout for table
        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Double-click to edit
        self.tree.bind("<Double-1>", lambda e: self.edit_item())

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text=_t("charity_shop.btn.add_item"), command=self.add_item, width=12).pack(side=tk.LEFT, padx=3)
        ttk.Button(button_frame, text=_t("charity_shop.btn.edit_item"), command=self.edit_item, width=12).pack(side=tk.LEFT, padx=3)
        ttk.Button(button_frame, text=_t("charity_shop.btn.delete_item"), command=self.delete_item, width=12).pack(side=tk.LEFT, padx=3)

        ttk.Separator(button_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Button(button_frame, text=_t("charity_shop.btn.add_to_basket"), command=self.add_to_basket, width=12).pack(side=tk.LEFT, padx=3)
        ttk.Button(button_frame, text=_t("charity_shop.btn.view_basket"), command=self.show_basket_window, width=12).pack(side=tk.LEFT, padx=3)
        ttk.Button(button_frame, text=_t("charity_shop.btn.quick_sell"), command=self.sell_item, width=10).pack(side=tk.LEFT, padx=3)
        ttk.Button(button_frame, text=_t("charity_shop.btn.mark_available"), command=self.mark_available, width=12).pack(side=tk.LEFT, padx=3)

        ttk.Separator(button_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Quick quantity adjustment
        ttk.Label(button_frame, text=_t("charity_shop.btn.quick_qty")).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="-1", command=lambda: self.adjust_quantity(-1), width=3).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="+1", command=lambda: self.adjust_quantity(1), width=3).pack(side=tk.LEFT, padx=2)

        ttk.Button(button_frame, text=_t("charity_shop.btn.refresh"), command=self.refresh_stock_list, width=10).pack(side=tk.RIGHT, padx=3)

    def refresh_stock_list(self):
        """Refresh the stock list from database."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Get stock data
        search_term = self.search_var.get().strip()
        category = self.filter_category_var.get()
        show_sold = self.filter_status_var.get()

        if search_term or category != "All":
            stock_items = self.db.search_stock(search_term, category, show_sold)
        else:
            stock_items = self.db.get_all_stock(show_sold)

        # Populate tree
        for item in stock_items:
            # item: (id, name, category, price, quantity, condition, date_added, sold, sold_date, sold_quantity)
            status = "Sold" if item[7] else "Available"
            sold_qty = item[9] if len(item) > 9 else 0

            formatted_item = (
                item[0],  # id
                item[1],  # name
                item[2],  # category
                f"£{item[3]:.2f}",  # price
                item[4],  # quantity
                item[5],  # condition
                status,
                sold_qty or 0,
                item[6],  # date_added
            )

            # Determine row tag
            tag = ''
            if item[7]:  # sold
                tag = 'sold'
            elif item[4] <= 2 and item[4] > 0:  # low stock
                tag = 'low_stock'

            self.tree.insert("", tk.END, values=formatted_item, tags=(tag,))

        self.update_summary()

    def update_summary(self):
        """Update the summary statistics."""
        # Stock summary
        summary = self.db.get_stock_summary()
        total_items = summary[0] or 0
        total_quantity = summary[1] or 0
        total_value = summary[2] or 0.0

        self.items_label.config(text=f"Items: {total_items}")
        self.quantity_label.config(text=f"Qty: {total_quantity}")
        self.value_label.config(text=f"Value: £{total_value:.2f}")

        # Revenue summary
        revenue = self.db.get_revenue_summary()
        total_sold = revenue[1] or 0
        total_revenue = revenue[2] or 0.0

        self.sold_label.config(text=f"Sold: {total_sold}")
        self.revenue_label.config(text=f"Revenue: £{total_revenue:.2f}")

    def on_search(self):
        """Handle search/filter changes."""
        self.refresh_stock_list()

    def clear_search(self):
        """Clear search and filter."""
        self.search_var.set("")
        self.filter_category_var.set("All")
        self.filter_status_var.set("all")
        self.refresh_stock_list()

    def get_selected_item(self):
        """Get the currently selected item."""
        selection = self.tree.selection()
        if not selection:
            return None

        values = self.tree.item(selection[0])["values"]
        # Convert price back from string (remove £ symbol)
        price_str = str(values[3]).replace("£", "").replace(",", "")
        # (id, name, category, price, quantity, condition, status, sold_qty, date_added)
        return {
            "id": values[0],
            "name": values[1],
            "category": values[2],
            "price": float(price_str),
            "quantity": values[4],
            "condition": values[5],
            "status": values[6],
            "sold_qty": values[7],
            "date_added": values[8]
        }

    def add_item(self):
        """Add a new stock item."""
        dialog = ItemDialog(self.root, "Add New Item")

        if dialog.result:
            self.db.add_item(
                dialog.result["name"],
                dialog.result["category"],
                dialog.result["price"],
                dialog.result["quantity"],
                dialog.result["condition"]
            )
            self.refresh_stock_list()
            messagebox.showinfo("Success", "Item added successfully!")

            # Log activity
            if ACTIVITY_LOGGER_AVAILABLE:
                log_activity('create', 'charity_shop_item', details={
                    'name': dialog.result["name"],
                    'category': dialog.result["category"],
                    'price': dialog.result["price"],
                    'quantity': dialog.result["quantity"]
                })

    def edit_item(self):
        """Edit the selected stock item."""
        item = self.get_selected_item()
        if not item:
            messagebox.showwarning("No Selection", "Please select an item to edit.")
            return

        # Get full item data from database
        all_items = self.db.get_all_stock()
        item_data = None
        for db_item in all_items:
            if db_item[0] == item["id"]:
                item_data = db_item
                break

        if not item_data:
            messagebox.showerror("Error", "Could not find item in database.")
            return

        dialog = ItemDialog(self.root, "Edit Item", item_data)

        if dialog.result:
            self.db.update_item(
                item["id"],
                dialog.result["name"],
                dialog.result["category"],
                dialog.result["price"],
                dialog.result["quantity"],
                dialog.result["condition"],
                dialog.result["sold"],
                dialog.result["sold_quantity"]
            )
            self.refresh_stock_list()
            messagebox.showinfo("Success", "Item updated successfully!")

    def delete_item(self):
        """Delete the selected stock item."""
        item = self.get_selected_item()
        if not item:
            messagebox.showwarning("No Selection", "Please select an item to delete.")
            return

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{item['name']}'?"):
            self.db.delete_item(item["id"])
            self.refresh_stock_list()
            messagebox.showinfo("Success", "Item deleted successfully!")

            # Log activity
            if ACTIVITY_LOGGER_AVAILABLE:
                log_activity('delete', 'charity_shop_item', details={
                    'item_id': item["id"],
                    'name': item["name"],
                    'category': item["category"]
                })

    def sell_item(self):
        """Mark selected item as sold with payment processing and email receipt."""
        item = self.get_selected_item()
        if not item:
            messagebox.showwarning("No Selection", "Please select an item to sell.")
            return

        if item["quantity"] <= 0:
            messagebox.showwarning("No Stock", "This item is out of stock.")
            return

        # Open enhanced sell dialog with payment options (pass current user for auto-fill)
        dialog = SellDialog(self.root, item["name"], item["quantity"], item["price"], self.current_user)

        if dialog.result:
            sale_data = dialog.result
            quantity = sale_data['quantity']
            total_amount = sale_data['total']
            payment_method = sale_data['payment_method']
            student_id = sale_data['student_id']
            customer_email = sale_data['customer_email']

            # Generate transaction reference
            transaction_ref = f"CS-{item['id']}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Process payment based on method
            payment_success = True
            payment_message = ""

            if payment_method == "Finance Account":
                # Process payment from student finance account
                if FINANCE_INTEGRATION_AVAILABLE and student_id:
                    current_user = get_current_user()
                    processed_by = current_user.get('username', 'System') if current_user else "System"
                    result = process_student_finance_account_payment(
                        student_id=student_id,
                        amount=total_amount,
                        description=f"Charity Shop: {quantity}x {item['name']}",
                        transaction_source="Charity Shop",
                        transaction_ref=transaction_ref,
                        processed_by=processed_by
                    )
                    payment_success = result.get('success', False)
                    payment_message = result.get('message', '')

                    if not payment_success:
                        messagebox.showerror("Payment Failed", f"Finance Account payment failed: {payment_message}")
                        return
                else:
                    messagebox.showerror("Error", "Finance integration not available for student account payment")
                    return

            # Mark item as sold in database
            self.db.mark_as_sold(item["id"], quantity)

            # Record revenue to central finance system
            if FINANCE_INTEGRATION_AVAILABLE:
                record_revenue_to_finance(
                    student_id=student_id or "WALK-IN",
                    amount=total_amount,
                    revenue_category="Charity Shop Sale",
                    transaction_source="Charity Shop",
                    transaction_ref=transaction_ref,
                    payment_method=payment_method,
                    notes=f"{quantity}x {item['name']}"
                )

            # Send email receipt if email provided
            receipt_sent = False
            if customer_email and EMAIL_SERVICE_AVAILABLE:
                receipt_sent = self._send_purchase_receipt(
                    customer_email=customer_email,
                    item_name=item['name'],
                    quantity=quantity,
                    unit_price=item['price'],
                    total_amount=total_amount,
                    payment_method=payment_method,
                    transaction_ref=transaction_ref,
                    student_id=student_id
                )

            self.refresh_stock_list()

            # Show success message
            success_msg = f"Sold {quantity} x {item['name']}!\n"
            success_msg += f"Total: £{total_amount:.2f}\n"
            success_msg += f"Payment: {payment_method}"
            if receipt_sent:
                success_msg += f"\n\nReceipt sent to {customer_email}"
            elif customer_email and not receipt_sent:
                success_msg += f"\n\n(Receipt email could not be sent)"

            messagebox.showinfo("Sale Complete", success_msg)

            # Log activity
            if ACTIVITY_LOGGER_AVAILABLE:
                log_activity('sell', 'charity_shop_item', details={
                    'item_id': item["id"],
                    'name': item["name"],
                    'quantity_sold': quantity,
                    'price_per_item': item["price"],
                    'total_revenue': total_amount,
                    'payment_method': payment_method,
                    'student_id': student_id,
                    'transaction_ref': transaction_ref,
                    'receipt_sent': receipt_sent
                })

    def _send_purchase_receipt(self, customer_email: str, item_name: str, quantity: int,
                               unit_price: float, total_amount: float, payment_method: str,
                               transaction_ref: str, student_id: str = None) -> bool:
        """Send purchase receipt email to customer using JSON template."""
        try:
            # Get student name if available
            customer_name = "Valued Customer"
            if student_id and FINANCE_INTEGRATION_AVAILABLE:
                student_info = get_student_info(student_id)
                if student_info:
                    customer_name = student_info.get('full_name', customer_name)

            # Load template from JSON file
            template = load_email_template("charity_shop_single_item_receipt")

            if not template:
                logger.error("Failed to load charity_shop_single_item_receipt template")
                return False

            # Prepare template variables
            variables = {
                'customer_name': customer_name,
                'transaction_ref': transaction_ref,
                'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'payment_method': payment_method,
                'item_name': item_name,
                'quantity': quantity,
                'unit_price': f"{unit_price:.2f}",
                'total_amount': f"{total_amount:.2f}"
            }

            # Render the template
            subject, body = render_email_template(template, variables)

            result = send_email(customer_email, subject, body)
            if result:
                logger.info(f"Purchase receipt sent to {customer_email} for transaction {transaction_ref}")
                return True
            else:
                logger.warning(f"Failed to send receipt to {customer_email}")
                return False

        except Exception as e:
            logger.error(f"Error sending purchase receipt: {e}")
            return False

    def mark_available(self):
        """Mark selected item as available (not sold)."""
        item = self.get_selected_item()
        if not item:
            messagebox.showwarning("No Selection", "Please select an item.")
            return

        if item["status"] == "Available":
            messagebox.showinfo("Info", "Item is already marked as available.")
            return

        if messagebox.askyesno("Confirm", f"Mark '{item['name']}' as available?"):
            self.db.mark_as_available(item["id"])
            self.refresh_stock_list()
            messagebox.showinfo("Success", "Item marked as available!")

    def adjust_quantity(self, delta: int):
        """Quickly adjust quantity of selected item."""
        item = self.get_selected_item()
        if not item:
            messagebox.showwarning("No Selection", "Please select an item to adjust quantity.")
            return

        # Get full item data
        all_items = self.db.get_all_stock()
        item_data = None
        for db_item in all_items:
            if db_item[0] == item["id"]:
                item_data = db_item
                break

        if item_data:
            new_quantity = max(0, item["quantity"] + delta)
            sold = item_data[7] if len(item_data) > 7 else 0
            sold_qty = item_data[9] if len(item_data) > 9 else 0
            self.db.update_item(
                item["id"], item["name"], item["category"],
                item["price"], new_quantity, item["condition"],
                bool(sold), sold_qty
            )
            self.refresh_stock_list()

    # =========================================================================
    # Shopping Basket Methods
    # =========================================================================

    def show_basket_window(self):
        """Show the basket window."""
        if self.basket_window is None or not self.basket_window.winfo_exists():
            self.basket_window = BasketWindow(self.root, self)
        else:
            self.basket_window.lift()
            self.basket_window.focus_set()

    def add_to_basket(self):
        """Add selected item to the shopping basket."""
        item = self.get_selected_item()
        if not item:
            messagebox.showwarning("No Selection", "Please select an item to add to basket.")
            return

        if item["quantity"] <= 0:
            messagebox.showwarning("Out of Stock", "This item is out of stock.")
            return

        if item["status"] == "Sold":
            messagebox.showwarning("Not Available", "This item has been sold.")
            return

        # Check if item is already in basket
        for basket_item in self.basket:
            if basket_item['id'] == item['id']:
                # Check if we can add more
                if basket_item['quantity'] >= item['quantity']:
                    messagebox.showwarning("Limit Reached", f"Maximum available quantity ({item['quantity']}) already in basket.")
                    return
                basket_item['quantity'] += 1
                self.update_basket_window()
                messagebox.showinfo("Added", f"Added another '{item['name']}' to basket.\nBasket now has {len(self.basket)} item type(s).")
                return

        # Add new item to basket
        self.basket.append({
            'id': item['id'],
            'name': item['name'],
            'price': item['price'],
            'quantity': 1,
            'max_qty': item['quantity']
        })
        self.update_basket_window()
        messagebox.showinfo("Added to Basket", f"Added '{item['name']}' to basket.\nBasket now has {len(self.basket)} item type(s).")

    def remove_from_basket(self, index: int):
        """Remove item at specified index from basket."""
        if 0 <= index < len(self.basket):
            self.basket.pop(index)
            self.update_basket_window()

    def clear_basket(self):
        """Clear all items from basket."""
        self.basket = []
        self.update_basket_window()

    def update_basket_window(self):
        """Update the basket window if it's open."""
        if self.basket_window is not None and self.basket_window.winfo_exists():
            self.basket_window.refresh_display()

    def checkout(self):
        """Open checkout dialog to complete purchase."""
        if not self.basket:
            messagebox.showwarning("Empty Basket", "Please add items to basket before checkout.")
            return

        # Calculate total
        total = sum(item['price'] * item['quantity'] for item in self.basket)

        # Open checkout dialog (pass current user for auto-fill)
        dialog = CheckoutDialog(self.root, self.basket, total, self.current_user)

        if dialog.result:
            self._process_checkout(dialog.result)

    def _process_checkout(self, checkout_data: dict):
        """Process the checkout and complete the sale."""
        payment_method = checkout_data['payment_method']
        student_id = checkout_data.get('student_id')
        customer_email = checkout_data.get('customer_email')
        total_amount = checkout_data['total']

        # Generate transaction reference
        transaction_ref = f"CS-BASKET-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Process payment based on method
        if payment_method == "Finance Account":
            if FINANCE_INTEGRATION_AVAILABLE and student_id:
                current_user = get_current_user()
                processed_by = current_user.get('username', 'System') if current_user else "System"
                result = process_student_finance_account_payment(
                    student_id=student_id,
                    amount=total_amount,
                    description=f"Charity Shop: {len(self.basket)} items",
                    transaction_source="Charity Shop",
                    transaction_ref=transaction_ref,
                    processed_by=processed_by
                )
                if not result.get('success', False):
                    messagebox.showerror("Payment Failed", f"Finance Account payment failed: {result.get('message', '')}")
                    return
            else:
                messagebox.showerror("Error", "Finance integration not available for student account payment")
                return

        # Save transaction to database
        self._save_transaction(transaction_ref, student_id, total_amount, payment_method, self.basket)

        # Process each item in basket
        items_sold = []
        for basket_item in self.basket:
            self.db.mark_as_sold(basket_item['id'], basket_item['quantity'])
            items_sold.append({
                'name': basket_item['name'],
                'quantity': basket_item['quantity'],
                'price': basket_item['price'],
                'subtotal': basket_item['price'] * basket_item['quantity']
            })

        # Record revenue to central finance system
        if FINANCE_INTEGRATION_AVAILABLE:
            record_revenue_to_finance(
                student_id=student_id or "WALK-IN",
                amount=total_amount,
                revenue_category="Charity Shop Sale",
                transaction_source="Charity Shop",
                transaction_ref=transaction_ref,
                payment_method=payment_method,
                notes=f"Basket checkout: {len(items_sold)} items"
            )

        # Send email receipt if email provided
        receipt_sent = False
        if customer_email and EMAIL_SERVICE_AVAILABLE:
            receipt_sent = self._send_basket_receipt(
                customer_email=customer_email,
                items=items_sold,
                total_amount=total_amount,
                payment_method=payment_method,
                transaction_ref=transaction_ref,
                student_id=student_id
            )

        # Clear basket and refresh
        self.basket = []
        self.update_basket_window()
        self.refresh_stock_list()

        # Show success message
        success_msg = f"Purchase Complete!\n\n"
        success_msg += f"Items: {len(items_sold)}\n"
        success_msg += f"Total: £{total_amount:.2f}\n"
        success_msg += f"Payment: {payment_method}"
        if receipt_sent:
            success_msg += f"\n\nReceipt sent to {customer_email}"
        elif customer_email and not receipt_sent:
            success_msg += f"\n\n(Receipt email could not be sent)"

        messagebox.showinfo("Checkout Complete", success_msg)

        # Log activity
        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('checkout', 'charity_shop_basket', details={
                'items_count': len(items_sold),
                'total_revenue': total_amount,
                'payment_method': payment_method,
                'student_id': student_id,
                'transaction_ref': transaction_ref,
                'receipt_sent': receipt_sent
            })

    def _send_basket_receipt(self, customer_email: str, items: list, total_amount: float,
                             payment_method: str, transaction_ref: str, student_id: str = None) -> bool:
        """Send basket purchase receipt email to customer using JSON template."""
        try:
            # Get customer name if available
            customer_name = "Valued Customer"
            if student_id and FINANCE_INTEGRATION_AVAILABLE:
                student_info = get_student_info(student_id)
                if student_info:
                    customer_name = student_info.get('full_name', customer_name)

            # Build items list for receipt
            items_text = ""
            for item in items:
                items_text += f"  {item['name']:<25} x{item['quantity']:<3} £{item['price']:.2f}  =  £{item['subtotal']:.2f}\n"

            # Load template from JSON file
            template = load_email_template("charity_shop_basket_receipt")

            if not template:
                logger.error("Failed to load charity_shop_basket_receipt template")
                return False

            # Prepare template variables
            variables = {
                'customer_name': customer_name,
                'transaction_ref': transaction_ref,
                'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'payment_method': payment_method,
                'items_list': items_text,
                'total_amount': f"{total_amount:.2f}"
            }

            # Render the template
            subject, body = render_email_template(template, variables)

            result = send_email(customer_email, subject, body)
            if result:
                logger.info(f"Basket receipt sent to {customer_email} for transaction {transaction_ref}")
                return True
            else:
                logger.warning(f"Failed to send basket receipt to {customer_email}")
                return False

        except Exception as e:
            logger.error(f"Error sending basket receipt: {e}")
            return False

    def show_charts(self):
        """Show the charts and analytics window."""
        ChartsWindow(self.root, self.db)

    # ==================== REPORTS METHODS ====================

    def show_report_with_type(self, report_type):
        """Show the reports window with a specific report type pre-selected"""
        self.show_reports_window()
        # Set the report type and generate
        if hasattr(self, 'report_type_var'):
            self.report_type_var.set(report_type)
            self.generate_report(report_type)

    def show_reports_window(self):
        """Show the reports window with all report options"""
        report_window = tk.Toplevel(self.root)
        report_window.title("Charity Shop Reports")
        report_window.geometry("800x650")
        report_window.minsize(700, 550)

        # Store reference for other methods
        self.report_window = report_window
        self.report_content = ""

        # Header
        header_frame = ttk.Frame(report_window)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text="Charity Shop Reports",
            font=('Helvetica', 16, 'bold')
        ).pack(side=tk.LEFT)

        # Report selection
        controls_frame = ttk.Frame(report_window)
        controls_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(controls_frame, text="Select Report:").pack(side=tk.LEFT, padx=5)

        self.report_type_var = tk.StringVar(value='daily')
        report_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.report_type_var,
            values=['daily', 'weekly', 'monthly', 'total', 'stock', 'category'],
            state='readonly',
            width=20
        )
        report_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(
            controls_frame,
            text="Generate Report",
            command=lambda: self.generate_report(self.report_type_var.get())
        ).pack(side=tk.LEFT, padx=5)

        # Action buttons
        actions_frame = ttk.Frame(report_window)
        actions_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(
            actions_frame,
            text="Save as TXT",
            command=self.save_report_as_txt
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            actions_frame,
            text="Open in New Window",
            command=self.open_report_in_window
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            actions_frame,
            text="Email to Admin",
            command=self.email_report_to_admin
        ).pack(side=tk.LEFT, padx=5)

        # Report display
        display_frame = ttk.Frame(report_window)
        display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        scrollbar = ttk.Scrollbar(display_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.report_text_widget = tk.Text(
            display_frame,
            wrap=tk.WORD,
            font=('Courier', 10),
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.report_text_widget.yview)
        self.report_text_widget.pack(fill=tk.BOTH, expand=True)

        # Generate initial report
        self.generate_report('daily')

    def generate_report(self, report_type):
        """Generate a report of the specified type"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            report_content = ""
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if report_type == 'daily':
                report_content = "═" * 60 + "\n"
                report_content += "           CHARITY SHOP - DAILY SALES REPORT\n"
                report_content += "═" * 60 + "\n\n"
                report_content += f"Date: {datetime.now().strftime('%Y-%m-%d')}\n"
                report_content += f"Generated: {timestamp}\n\n"

                # Today's sales
                cursor.execute('''
                    SELECT COUNT(*), COALESCE(SUM(price * quantity), 0)
                    FROM charity_shop_stock
                    WHERE sold = 1 AND DATE(date_added) = DATE('now')
                ''')
                result = cursor.fetchone()
                items_sold = result[0] or 0
                daily_revenue = result[1] or 0.0

                report_content += f"Items Sold Today: {items_sold}\n"
                report_content += f"Daily Revenue: £{daily_revenue:.2f}\n\n"

                # Today's sales by category
                report_content += "─" * 40 + "\n"
                report_content += "Sales by Category:\n"
                report_content += "─" * 40 + "\n"
                cursor.execute('''
                    SELECT category, COUNT(*), SUM(price * quantity)
                    FROM charity_shop_stock
                    WHERE sold = 1 AND DATE(date_added) = DATE('now')
                    GROUP BY category
                    ORDER BY SUM(price * quantity) DESC
                ''')
                for row in cursor.fetchall():
                    cat, count, amount = row
                    report_content += f"  {cat or 'Uncategorized':<20} {count:>3} items  £{amount or 0:.2f}\n"

            elif report_type == 'weekly':
                report_content = "═" * 60 + "\n"
                report_content += "          CHARITY SHOP - WEEKLY SALES REPORT\n"
                report_content += "═" * 60 + "\n\n"
                report_content += f"Week Ending: {datetime.now().strftime('%Y-%m-%d')}\n"
                report_content += f"Generated: {timestamp}\n\n"

                cursor.execute('''
                    SELECT COUNT(*), COALESCE(SUM(price * quantity), 0)
                    FROM charity_shop_stock
                    WHERE sold = 1 AND DATE(date_added) >= DATE('now', '-7 days')
                ''')
                result = cursor.fetchone()
                items_sold = result[0] or 0
                weekly_revenue = result[1] or 0.0

                report_content += f"Items Sold This Week: {items_sold}\n"
                report_content += f"Weekly Revenue: £{weekly_revenue:.2f}\n"
                report_content += f"Average Per Day: £{weekly_revenue/7:.2f}\n\n"

                # Daily breakdown
                report_content += "─" * 40 + "\n"
                report_content += "Daily Breakdown:\n"
                report_content += "─" * 40 + "\n"
                cursor.execute('''
                    SELECT DATE(date_added), COUNT(*), SUM(price * quantity)
                    FROM charity_shop_stock
                    WHERE sold = 1 AND DATE(date_added) >= DATE('now', '-7 days')
                    GROUP BY DATE(date_added)
                    ORDER BY DATE(date_added) DESC
                ''')
                for row in cursor.fetchall():
                    date, count, amount = row
                    report_content += f"  {date}  {count:>3} items  £{amount or 0:.2f}\n"

            elif report_type == 'monthly':
                report_content = "═" * 60 + "\n"
                report_content += "         CHARITY SHOP - MONTHLY SALES REPORT\n"
                report_content += "═" * 60 + "\n\n"
                report_content += f"Month: {datetime.now().strftime('%B %Y')}\n"
                report_content += f"Generated: {timestamp}\n\n"

                cursor.execute('''
                    SELECT COUNT(*), COALESCE(SUM(price * quantity), 0)
                    FROM charity_shop_stock
                    WHERE sold = 1 AND DATE(date_added) >= DATE('now', 'start of month')
                ''')
                result = cursor.fetchone()
                items_sold = result[0] or 0
                monthly_revenue = result[1] or 0.0

                report_content += f"Items Sold This Month: {items_sold}\n"
                report_content += f"Monthly Revenue: £{monthly_revenue:.2f}\n\n"

                # Weekly breakdown
                report_content += "─" * 40 + "\n"
                report_content += "Category Breakdown:\n"
                report_content += "─" * 40 + "\n"
                cursor.execute('''
                    SELECT category, COUNT(*), SUM(price * quantity)
                    FROM charity_shop_stock
                    WHERE sold = 1 AND DATE(date_added) >= DATE('now', 'start of month')
                    GROUP BY category
                    ORDER BY SUM(price * quantity) DESC
                ''')
                for row in cursor.fetchall():
                    cat, count, amount = row
                    report_content += f"  {cat or 'Uncategorized':<20} {count:>3} items  £{amount or 0:.2f}\n"

            elif report_type == 'total':
                report_content = "═" * 60 + "\n"
                report_content += "        CHARITY SHOP - TOTAL REVENUE REPORT\n"
                report_content += "═" * 60 + "\n\n"
                report_content += f"Generated: {timestamp}\n\n"

                # Total stats
                cursor.execute('''
                    SELECT COUNT(*), COALESCE(SUM(price * quantity), 0)
                    FROM charity_shop_stock WHERE sold = 1
                ''')
                result = cursor.fetchone()
                total_sold = result[0] or 0
                total_revenue = result[1] or 0.0

                cursor.execute('SELECT COUNT(*) FROM charity_shop_stock WHERE sold = 0')
                available = cursor.fetchone()[0] or 0

                cursor.execute('SELECT COALESCE(SUM(price * quantity), 0) FROM charity_shop_stock WHERE sold = 0')
                available_value = cursor.fetchone()[0] or 0.0

                report_content += "─" * 40 + "\n"
                report_content += "SUMMARY\n"
                report_content += "─" * 40 + "\n"
                report_content += f"Total Items Sold:      {total_sold}\n"
                report_content += f"Total Revenue:         £{total_revenue:.2f}\n"
                report_content += f"Items Still Available: {available}\n"
                report_content += f"Available Stock Value: £{available_value:.2f}\n\n"

                # Revenue by category
                report_content += "─" * 40 + "\n"
                report_content += "Revenue by Category:\n"
                report_content += "─" * 40 + "\n"
                cursor.execute('''
                    SELECT category, COUNT(*), SUM(price * quantity)
                    FROM charity_shop_stock WHERE sold = 1
                    GROUP BY category ORDER BY SUM(price * quantity) DESC
                ''')
                for row in cursor.fetchall():
                    cat, count, amount = row
                    report_content += f"  {cat or 'Uncategorized':<20} {count:>4} items  £{amount or 0:.2f}\n"

            elif report_type == 'stock':
                report_content = "═" * 60 + "\n"
                report_content += "        CHARITY SHOP - STOCK STATUS REPORT\n"
                report_content += "═" * 60 + "\n\n"
                report_content += f"Generated: {timestamp}\n\n"

                # Available stock by category
                cursor.execute('''
                    SELECT category, COUNT(*), SUM(quantity), SUM(price * quantity)
                    FROM charity_shop_stock WHERE sold = 0
                    GROUP BY category ORDER BY category
                ''')

                report_content += "─" * 50 + "\n"
                report_content += "Available Stock by Category:\n"
                report_content += "─" * 50 + "\n"
                report_content += f"{'Category':<20} {'Items':>6} {'Qty':>6} {'Value':>12}\n"
                report_content += "─" * 50 + "\n"

                total_items = 0
                total_qty = 0
                total_value = 0.0
                for row in cursor.fetchall():
                    cat, items, qty, value = row
                    total_items += items or 0
                    total_qty += qty or 0
                    total_value += value or 0.0
                    report_content += f"{cat or 'Uncategorized':<20} {items or 0:>6} {qty or 0:>6} £{value or 0:>10.2f}\n"

                report_content += "─" * 50 + "\n"
                report_content += f"{'TOTAL':<20} {total_items:>6} {total_qty:>6} £{total_value:>10.2f}\n"

            elif report_type == 'category':
                report_content = "═" * 60 + "\n"
                report_content += "       CHARITY SHOP - CATEGORY ANALYSIS REPORT\n"
                report_content += "═" * 60 + "\n\n"
                report_content += f"Generated: {timestamp}\n\n"

                # Get all categories with stats
                cursor.execute('''
                    SELECT
                        category,
                        COUNT(*) as total_items,
                        SUM(CASE WHEN sold = 1 THEN 1 ELSE 0 END) as sold_items,
                        SUM(CASE WHEN sold = 0 THEN 1 ELSE 0 END) as available_items,
                        SUM(CASE WHEN sold = 1 THEN price * quantity ELSE 0 END) as revenue,
                        SUM(CASE WHEN sold = 0 THEN price * quantity ELSE 0 END) as stock_value
                    FROM charity_shop_stock
                    GROUP BY category
                    ORDER BY revenue DESC
                ''')

                report_content += "─" * 60 + "\n"
                report_content += f"{'Category':<15} {'Total':>6} {'Sold':>6} {'Avail':>6} {'Revenue':>12} {'Stock Val':>12}\n"
                report_content += "─" * 60 + "\n"

                for row in cursor.fetchall():
                    cat, total, sold, avail, rev, stock_val = row
                    report_content += f"{(cat or 'Uncategorized'):<15} {total or 0:>6} {sold or 0:>6} {avail or 0:>6} £{rev or 0:>10.2f} £{stock_val or 0:>10.2f}\n"

            conn.close()

            # Store report content
            self.report_content = report_content

            # Display in report window if it exists
            if hasattr(self, 'report_text_widget') and self.report_text_widget.winfo_exists():
                self.report_text_widget.delete('1.0', tk.END)
                self.report_text_widget.insert('1.0', report_content)

            return report_content

        except Exception as e:
            error_msg = f"Error generating report: {e}"
            logger.error(error_msg)
            messagebox.showerror("Error", error_msg)
            return ""

    def save_report_as_txt(self):
        """Save the current report as a TXT file"""
        if not hasattr(self, 'report_content') or not self.report_content:
            messagebox.showwarning("Warning", "No report to save. Please generate a report first.")
            return

        # Generate default filename
        report_type = self.report_type_var.get() if hasattr(self, 'report_type_var') else 'report'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_filename = f"charity_shop_{report_type}_{timestamp}.txt"

        # Ask user for save location
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=default_filename,
            title="Save Report As"
        )

        if not file_path:
            return  # User cancelled

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.report_content)
            messagebox.showinfo("Success", f"Report saved to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save report: {e}")

    def open_report_in_window(self):
        """Open the current report in a separate window"""
        if not hasattr(self, 'report_content') or not self.report_content:
            messagebox.showwarning("Warning", "No report to display. Please generate a report first.")
            return

        # Create new window
        new_window = tk.Toplevel(self.root)
        report_type = self.report_type_var.get() if hasattr(self, 'report_type_var') else 'Report'
        new_window.title(f"Charity Shop Report - {report_type.title()}")
        new_window.geometry("700x600")

        # Header
        header_frame = ttk.Frame(new_window)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text=f"Charity Shop: {report_type.title()} Report",
            font=('Helvetica', 14, 'bold')
        ).pack(side=tk.LEFT)

        ttk.Label(
            header_frame,
            text=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            font=('Helvetica', 10)
        ).pack(side=tk.RIGHT)

        # Report text
        text_frame = ttk.Frame(new_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_widget = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=('Courier', 10),
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=text_widget.yview)
        text_widget.pack(fill=tk.BOTH, expand=True)

        text_widget.insert('1.0', self.report_content)
        text_widget.config(state=tk.DISABLED)

        # Buttons
        button_frame = ttk.Frame(new_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(
            button_frame,
            text="Save as TXT",
            command=self.save_report_as_txt
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Email to Admin",
            command=self.email_report_to_admin
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Close",
            command=new_window.destroy
        ).pack(side=tk.RIGHT, padx=5)

    def email_report_to_admin(self):
        """Email the current report to admin"""
        if not EMAIL_SERVICE_AVAILABLE:
            messagebox.showerror("Error", "Email service is not available.")
            return

        if not hasattr(self, 'report_content') or not self.report_content:
            messagebox.showwarning("Warning", "No report to email. Please generate a report first.")
            return

        # Get admin email from database
        admin_email = self._get_admin_email()
        if not admin_email:
            messagebox.showerror("Error", "Could not find admin email address in database.")
            return

        report_type = self.report_type_var.get() if hasattr(self, 'report_type_var') else 'Report'

        # Confirm before sending
        if not messagebox.askyesno(
            "Confirm Email",
            f"Send '{report_type.title()}' report to:\n{admin_email}?"
        ):
            return

        # Prepare email
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        subject = f"Charity Shop Report: {report_type.title()} - {timestamp}"

        generated_by = 'System'
        if self.current_user:
            generated_by = self.current_user.get('username', 'System')

        body = f"""Charity Shop Report

Report Type: {report_type.title()}
Generated: {timestamp}
Generated By: {generated_by}

{'=' * 60}

{self.report_content}

{'=' * 60}

This report was automatically generated by the University Charity Shop System.
"""

        try:
            result = send_email(admin_email, subject, body)
            if result:
                messagebox.showinfo("Success", f"Report sent to {admin_email}")
            else:
                messagebox.showerror("Error", "Failed to send email. Please try again.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send email: {e}")

    def _get_admin_email(self):
        """Get admin email address from database"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                SELECT email FROM users
                WHERE role = 'admin' AND username = 'admin'
                LIMIT 1
            ''')
            result = cursor.fetchone()
            conn.close()

            if result:
                return result[0]
            return None
        except Exception as e:
            logger.error(f"Error getting admin email: {e}")
            return None

    def _save_transaction(self, transaction_ref, student_id, total_amount, payment_method, basket_items):
        """Save transaction to database for refund tracking"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Create transactions table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS charity_shop_transactions (
                    transaction_id TEXT PRIMARY KEY,
                    transaction_date TEXT NOT NULL,
                    student_id TEXT,
                    total_amount REAL NOT NULL,
                    payment_method TEXT NOT NULL,
                    status TEXT DEFAULT 'completed',
                    items_json TEXT
                )
            ''')

            # Convert basket items to JSON string
            import json
            items_json = json.dumps([{
                'id': item['id'],
                'name': item['name'],
                'quantity': item['quantity'],
                'price': item['price']
            } for item in basket_items])

            # Insert transaction
            cursor.execute('''
                INSERT INTO charity_shop_transactions
                (transaction_id, transaction_date, student_id, total_amount, payment_method, status, items_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (transaction_ref, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  student_id, total_amount, payment_method, 'completed', items_json))

            conn.commit()
            conn.close()
            logger.info(f"Transaction {transaction_ref} saved to database")

        except Exception as e:
            logger.error(f"Error saving transaction: {e}")

    def show_refunds_window(self):
        """Display refunds management window"""
        refunds_window = tk.Toplevel(self.root)
        refunds_window.title("Charity Shop Refunds")
        refunds_window.geometry("900x600")
        refunds_window.transient(self.root)

        main_frame = ttk.Frame(refunds_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_label = ttk.Label(main_frame, text="Charity Shop Transaction Refunds",
                                font=('Arial', 16, 'bold'))
        header_label.pack(pady=10)

        # Search frame
        search_frame = ttk.LabelFrame(main_frame, text="Search Transactions", padding="10")
        search_frame.pack(fill=tk.X, pady=5)

        ttk.Label(search_frame, text="Search by Transaction ID or Student ID:").pack(side=tk.LEFT, padx=5)
        refunds_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=refunds_search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)

        # Transactions table
        trans_frame = ttk.Frame(main_frame)
        trans_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ('transaction_id', 'date', 'student_id', 'amount', 'payment_method', 'status')
        refunds_tree = ttk.Treeview(trans_frame, columns=columns, show='headings', height=15)

        refunds_tree.heading('transaction_id', text='Transaction ID')
        refunds_tree.heading('date', text='Date')
        refunds_tree.heading('student_id', text='Student ID')
        refunds_tree.heading('amount', text='Amount')
        refunds_tree.heading('payment_method', text='Payment Method')
        refunds_tree.heading('status', text='Status')

        refunds_tree.column('transaction_id', width=200)
        refunds_tree.column('date', width=150)
        refunds_tree.column('student_id', width=120)
        refunds_tree.column('amount', width=100)
        refunds_tree.column('payment_method', width=130)
        refunds_tree.column('status', width=100)

        scrollbar = ttk.Scrollbar(trans_frame, orient=tk.VERTICAL, command=refunds_tree.yview)
        refunds_tree.configure(yscrollcommand=scrollbar.set)

        refunds_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def refresh_transactions_list():
            """Refresh the transactions list"""
            for item in refunds_tree.get_children():
                refunds_tree.delete(item)

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Ensure table exists
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS charity_shop_transactions (
                        transaction_id TEXT PRIMARY KEY,
                        transaction_date TEXT NOT NULL,
                        student_id TEXT,
                        total_amount REAL NOT NULL,
                        payment_method TEXT NOT NULL,
                        status TEXT DEFAULT 'completed',
                        items_json TEXT
                    )
                ''')

                search_term = refunds_search_var.get().strip()
                if search_term:
                    query = '''
                        SELECT transaction_id, transaction_date, student_id, total_amount,
                               payment_method, status
                        FROM charity_shop_transactions
                        WHERE transaction_id LIKE ? OR student_id LIKE ?
                        ORDER BY transaction_date DESC
                        LIMIT 500
                    '''
                    search_pattern = f'%{search_term}%'
                    cursor.execute(query, (search_pattern, search_pattern))
                else:
                    query = '''
                        SELECT transaction_id, transaction_date, student_id, total_amount,
                               payment_method, status
                        FROM charity_shop_transactions
                        ORDER BY transaction_date DESC
                        LIMIT 500
                    '''
                    cursor.execute(query)

                transactions = cursor.fetchall()

                for trans in transactions:
                    transaction_id, trans_date, student_id, amount, payment_method, status = trans

                    refunds_tree.insert('', tk.END, values=(
                        transaction_id,
                        trans_date,
                        student_id or 'Walk-in',
                        f"£{amount:.2f}",
                        payment_method,
                        status.upper()
                    ))

                conn.close()

            except Exception as e:
                messagebox.showerror("Database Error", f"Error loading transactions: {e}")

        def process_refund():
            """Process a refund for selected transaction"""
            selection = refunds_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a transaction to refund.")
                return

            item = refunds_tree.item(selection[0])
            values = item['values']

            if len(values) < 6:
                messagebox.showerror("Error", "Invalid transaction data.")
                return

            transaction_id = values[0]
            amount_str = values[3].replace('£', '').strip()
            try:
                amount = float(amount_str)
            except ValueError:
                messagebox.showerror("Error", "Invalid amount format.")
                return

            status = values[5]

            # Check if already refunded
            if status == 'REFUNDED':
                messagebox.showinfo("Already Refunded", "This transaction has already been refunded.")
                return

            # Confirm refund
            if not messagebox.askyesno("Confirm Refund", f"Process refund of £{amount:.2f} for transaction {transaction_id}?"):
                return

            # Get transaction details
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT student_id, payment_method
                    FROM charity_shop_transactions
                    WHERE transaction_id = ?
                ''', (transaction_id,))

                trans_data = cursor.fetchone()
                conn.close()

                if not trans_data:
                    messagebox.showerror("Error", "Transaction not found in database.")
                    return

                student_id = trans_data[0]
                payment_method = trans_data[1]

            except Exception as e:
                messagebox.showerror("Database Error", f"Error fetching transaction details: {e}")
                return

            # Show refund method dialog
            refund_method = self._show_charity_refund_method_dialog(refunds_window, amount, transaction_id, student_id)

            if not refund_method:
                return

            # Process refund
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Update transaction status
                cursor.execute('''
                    UPDATE charity_shop_transactions
                    SET status = 'refunded'
                    WHERE transaction_id = ?
                ''', (transaction_id,))

                # Generate refund reference
                refund_ref = f"CHARITY-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                # Create refunds table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS charity_shop_refunds (
                        refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        transaction_id TEXT NOT NULL,
                        refund_date TEXT NOT NULL,
                        refund_amount REAL NOT NULL,
                        refund_method TEXT NOT NULL,
                        refund_reference TEXT UNIQUE,
                        student_id TEXT,
                        processed_by TEXT,
                        notes TEXT,
                        FOREIGN KEY (transaction_id) REFERENCES charity_shop_transactions (transaction_id)
                    )
                ''')

                # Insert refund record
                processed_by = self.current_user.get('username', 'System') if self.current_user else 'System'
                cursor.execute('''
                    INSERT INTO charity_shop_refunds
                    (transaction_id, refund_date, refund_amount, refund_method, refund_reference, student_id, processed_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (transaction_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), amount, refund_method,
                      refund_ref, student_id, processed_by))

                conn.commit()
                conn.close()

                # If student account refund, add to their account
                if refund_method == 'Student Account':
                    success = self._add_charity_refund_to_student_account(student_id, amount, refund_ref)
                    if not success:
                        messagebox.showwarning("Partial Success",
                                             "Refund recorded but failed to credit student account. Please credit manually.")

                # Send refund receipt email
                self._send_charity_refund_receipt(transaction_id, student_id, amount, refund_method, refund_ref)

                # Notify finance GUI
                self._notify_charity_finance_gui(transaction_id, amount, refund_method, refund_ref, student_id)

                messagebox.showinfo("Refund Processed",
                                  f"Refund of £{amount:.2f} processed successfully.\nRefund Reference: {refund_ref}")

                # Refresh the list
                refresh_transactions_list()

            except Exception as e:
                messagebox.showerror("Database Error", f"Error processing refund: {e}")

        def view_transaction_details():
            """View detailed transaction information"""
            selection = refunds_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a transaction to view details.")
                return

            item = refunds_tree.item(selection[0])
            values = item['values']

            if len(values) < 6:
                messagebox.showerror("Error", "Invalid transaction data.")
                return

            transaction_id = values[0]

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT transaction_id, transaction_date, student_id, total_amount,
                           payment_method, status, items_json
                    FROM charity_shop_transactions
                    WHERE transaction_id = ?
                ''', (transaction_id,))

                trans = cursor.fetchone()
                conn.close()

                if not trans:
                    messagebox.showerror("Error", "Transaction not found.")
                    return

                # Create details window
                details_window = tk.Toplevel(refunds_window)
                details_window.title(f"Transaction Details - {transaction_id}")
                details_window.geometry("500x500")
                details_window.transient(refunds_window)

                details_frame = ttk.Frame(details_window, padding=20)
                details_frame.pack(fill=tk.BOTH, expand=True)

                # Transaction information
                info_text = ScrolledText(details_frame, width=60, height=25, wrap=tk.WORD)
                info_text.pack(fill=tk.BOTH, expand=True)

                # Parse items
                import json
                items = []
                if trans[6]:
                    try:
                        items = json.loads(trans[6])
                    except (ValueError, json.JSONDecodeError):
                        pass

                items_text = ""
                for item in items:
                    subtotal = item['price'] * item['quantity']
                    items_text += f"\n{item['name']}\n"
                    items_text += f"  Quantity: {item['quantity']} x £{item['price']:.2f} = £{subtotal:.2f}\n"

                details = f"""TRANSACTION DETAILS
═══════════════════════════════════════════════════════

Transaction ID:     {trans[0]}
Date:               {trans[1]}
Student ID:         {trans[2] or 'Walk-in Customer'}
Payment Method:     {trans[4]}
Status:             {trans[5].upper()}

═══════════════════════════════════════════════════════
ITEMS PURCHASED
═══════════════════════════════════════════════════════
{items_text}

═══════════════════════════════════════════════════════
TOTAL:              £{trans[3]:.2f}
═══════════════════════════════════════════════════════
"""

                info_text.insert('1.0', details)
                info_text.config(state='disabled')

                ttk.Button(details_frame, text="Close", command=details_window.destroy).pack(pady=10)

            except Exception as e:
                messagebox.showerror("Database Error", f"Error loading transaction details: {e}")

        def export_to_csv():
            """Export transactions list to CSV file"""
            try:
                filename = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile=f"charity_shop_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                )

                if not filename:
                    return

                import csv
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)

                    # Write header
                    writer.writerow(['Transaction ID', 'Date', 'Student ID', 'Amount',
                                   'Payment Method', 'Status'])

                    # Write data
                    for item in refunds_tree.get_children():
                        values = refunds_tree.item(item)['values']
                        writer.writerow(values)

                messagebox.showinfo("Export Successful", f"Data exported to:\n{filename}")

            except Exception as e:
                messagebox.showerror("Export Error", f"Error exporting data: {e}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Search", command=refresh_transactions_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Show All", command=lambda: [refunds_search_var.set(''), refresh_transactions_list()]).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Process Refund", command=process_refund).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="View Details", command=view_transaction_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export to CSV", command=export_to_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=refunds_window.destroy).pack(side=tk.LEFT, padx=5)

        # Initial load
        refresh_transactions_list()

    def _show_charity_refund_method_dialog(self, parent, amount, transaction_id, student_id):
        """Show dialog to select refund method"""
        dialog = tk.Toplevel(parent)
        dialog.title("Select Refund Method")
        dialog.geometry("400x350")
        dialog.transient(parent)
        dialog.grab_set()

        result = {'method': None}

        ttk.Label(dialog, text=f"Refund Amount: £{amount:.2f}", font=('Arial', 12, 'bold')).pack(pady=10)
        ttk.Label(dialog, text=f"Transaction ID: {transaction_id}").pack(pady=5)

        # Show student account balance if student_id available
        if student_id and FINANCE_INTEGRATION_AVAILABLE:
            try:
                current_balance = get_student_finance_account_balance(student_id)
                if current_balance is not None:
                    new_balance = current_balance + amount
                    balance_frame = ttk.LabelFrame(dialog, text="Student Finance Account", padding=10)
                    balance_frame.pack(pady=10, padx=20, fill=tk.X)

                    ttk.Label(balance_frame, text=f"Current Balance: £{current_balance:.2f}").pack(anchor='w')
                    ttk.Label(balance_frame, text=f"After Refund: £{new_balance:.2f}",
                            font=('Arial', 10, 'bold')).pack(anchor='w')
            except Exception as e:
                logger.error(f"Error getting balance: {e}")

        ttk.Label(dialog, text="Select refund method:", font=('Arial', 10)).pack(pady=10)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def select_cash():
            result['method'] = 'Cash'
            dialog.destroy()

        def select_card():
            result['method'] = 'Card'
            dialog.destroy()

        def select_student_account():
            if not student_id:
                messagebox.showerror("Error", "No student ID associated with this transaction.")
                return
            result['method'] = 'Student Account'
            dialog.destroy()

        ttk.Button(button_frame, text="Cash Refund", command=select_cash, width=20).pack(pady=5)
        ttk.Button(button_frame, text="Card Refund", command=select_card, width=20).pack(pady=5)

        if student_id and FINANCE_INTEGRATION_AVAILABLE:
            ttk.Button(button_frame, text="Student Finance Account", command=select_student_account, width=20).pack(pady=5)

        ttk.Button(button_frame, text="Cancel", command=dialog.destroy, width=20).pack(pady=10)

        dialog.wait_window()
        return result['method']

    def _add_charity_refund_to_student_account(self, student_id, amount, refund_ref):
        """Add refund amount to student finance account"""
        try:
            # Use finance integration if available for better handling
            if FINANCE_INTEGRATION_AVAILABLE:
                try:
                    from university_system.modules.shared.utils.finance_integration import top_up_student_finance_account
                    result = top_up_student_finance_account(
                        student_id=student_id,
                        amount=amount,
                        payment_method='Refund',
                        processed_by=self.current_user.get('username', 'System') if self.current_user else 'System',
                        description=f'Charity Shop Purchase Refund - {refund_ref}'
                    )
                    if result.get('success'):
                        logger.info(f"Refund credited to finance account for {student_id}: £{amount:.2f}")
                        return True
                    else:
                        logger.error(f"Finance integration failed: {result.get('message')}")
                        # Fall through to manual method
                except Exception as e:
                    logger.warning(f"Finance integration error, using fallback: {e}")
                    # Fall through to manual method

            # Fallback: Direct database update with correct schema
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Check if student finance account exists and get account_id and current balance
            cursor.execute('SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?', (student_id,))
            account = cursor.fetchone()

            if not account:
                # Create account with refund amount
                cursor.execute('''
                    INSERT INTO student_finance_accounts (student_id, balance, created_at)
                    VALUES (?, ?, ?)
                ''', (student_id, amount, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                # Get the newly created account_id
                cursor.execute('SELECT account_id FROM student_finance_accounts WHERE student_id = ?', (student_id,))
                account = cursor.fetchone()
                account_id = account[0]
                balance_before = 0.0
                balance_after = amount

                logger.info(f"Created new finance account for {student_id} with refund of £{amount:.2f}")
            else:
                account_id = account[0]
                balance_before = account[1]
                balance_after = balance_before + amount

                # Update existing account
                cursor.execute('''
                    UPDATE student_finance_accounts
                    SET balance = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE student_id = ?
                ''', (balance_after, student_id))
                logger.info(f"Updated finance account for {student_id}: +£{amount:.2f}")

            # Record transaction with correct schema
            processed_by = self.current_user.get('username', 'System') if self.current_user else 'System'
            cursor.execute('''
                INSERT INTO student_finance_transactions
                (account_id, student_id, transaction_type, amount, balance_before, balance_after,
                 description, reference_id, processed_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (account_id, student_id, 'credit', amount, balance_before, balance_after,
                  'Charity Shop Purchase Refund', refund_ref, processed_by))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"Error adding refund to student account: {e}")
            return False

    def _send_charity_refund_receipt(self, transaction_id, student_id, amount, method, refund_ref):
        """Send refund receipt email to customer"""
        try:
            if not student_id:
                logger.warning("No student ID available for email receipt")
                return

            # Get customer email
            customer_email = None
            customer_name = "Valued Customer"

            if FINANCE_INTEGRATION_AVAILABLE:
                student_info = get_student_info(student_id)
                if student_info:
                    customer_email = student_info.get('email')
                    customer_name = student_info.get('full_name', customer_name)

            if not customer_email:
                logger.warning(f"No email found for student {student_id}")
                return

            # Get updated balance if student account refund
            balance_text = ""
            if method == 'Student Account' and FINANCE_INTEGRATION_AVAILABLE:
                try:
                    new_balance = get_student_finance_account_balance(student_id)
                    if new_balance is not None:
                        balance_text = f"\n\nYour updated account balance is: £{new_balance:.2f}"
                except Exception:
                    logger.debug("Could not retrieve updated student finance balance")

            # Prepare template variables
            from university_system.infrastructure.email.template_utils import render_template

            template_vars = {
                'customer_name': customer_name,
                'transaction_id': transaction_id,
                'amount': f"{amount:.2f}",
                'method': method,
                'refund_ref': refund_ref,
                'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'balance_text': balance_text
            }

            subject, body = render_template('commerce/charity_shop_payment_refund_receipt', template_vars)
            if not subject or not body:
                logger.error("Failed to render email template")
                return

            if EMAIL_SERVICE_AVAILABLE:
                result = send_email(customer_email, subject, body)
                if result:
                    logger.info(f"Refund receipt sent to {customer_email}")
                else:
                    logger.warning(f"Failed to send refund receipt to {customer_email}")

        except Exception as e:
            logger.error(f"Error sending refund receipt: {e}")

    def _notify_charity_finance_gui(self, transaction_id, amount, method, refund_ref, student_id):
        """Notify finance GUI about the refund"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Insert into finance_refunds table (use 'amount' column name to match existing schema)
            processed_by = self.current_user.get('username', 'System') if self.current_user else 'System'
            cursor.execute('''
                INSERT INTO finance_refunds
                (transaction_id, refund_date, amount, refund_method, refund_reference,
                 student_id, department, processed_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (transaction_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), amount, method,
                  refund_ref, student_id, 'Charity Shop', processed_by))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error notifying finance GUI: {e}")

class BasketWindow(tk.Toplevel):
    """Separate window for viewing and managing the shopping basket."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app  # Reference to main CharityShopApp
        self.title("Shopping Basket")
        self.geometry("500x500")
        self.minsize(400, 400)

        self.create_widgets()
        self.refresh_display()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        """Create basket window widgets."""
        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(header_frame, text="Shopping Basket", font=("Helvetica", 14, "bold")).pack(side=tk.LEFT)

        self.item_count_label = ttk.Label(header_frame, text="0 items", foreground="gray")
        self.item_count_label.pack(side=tk.RIGHT)

        # Basket items treeview
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ("name", "qty", "price", "subtotal")
        self.basket_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)

        self.basket_tree.heading("name", text="Item")
        self.basket_tree.heading("qty", text="Qty")
        self.basket_tree.heading("price", text="Price")
        self.basket_tree.heading("subtotal", text="Subtotal")

        self.basket_tree.column("name", width=200, anchor="w")
        self.basket_tree.column("qty", width=60, anchor="center")
        self.basket_tree.column("price", width=80, anchor="e")
        self.basket_tree.column("subtotal", width=100, anchor="e")

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.basket_tree.yview)
        self.basket_tree.configure(yscrollcommand=scrollbar.set)

        self.basket_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Quantity adjustment frame
        qty_frame = ttk.LabelFrame(main_frame, text="Adjust Quantity", padding="10")
        qty_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(qty_frame, text="-1", command=self.decrease_qty, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Button(qty_frame, text="+1", command=self.increase_qty, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Button(qty_frame, text="Remove Item", command=self.remove_selected, width=12).pack(side=tk.LEFT, padx=15)
        ttk.Button(qty_frame, text="Clear All", command=self.clear_all, width=10).pack(side=tk.RIGHT, padx=5)

        # Total frame
        total_frame = ttk.Frame(main_frame)
        total_frame.pack(fill=tk.X, pady=10)

        ttk.Separator(total_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        total_inner = ttk.Frame(total_frame)
        total_inner.pack(fill=tk.X)

        ttk.Label(total_inner, text="Total:", font=("Helvetica", 14, "bold")).pack(side=tk.LEFT)
        self.total_label = ttk.Label(total_inner, text="£0.00", font=("Helvetica", 16, "bold"), foreground="green")
        self.total_label.pack(side=tk.RIGHT)

        # Checkout button
        checkout_btn = ttk.Button(main_frame, text="Proceed to Checkout", command=self.proceed_to_checkout)
        checkout_btn.pack(fill=tk.X, pady=(10, 0))

        # Style the checkout button
        try:
            style = ttk.Style()
            style.configure("Checkout.TButton", font=("Helvetica", 12, "bold"))
            checkout_btn.configure(style="Checkout.TButton")
        except Exception:
            pass

    def refresh_display(self):
        """Refresh the basket display from app data."""
        # Clear existing items
        for item in self.basket_tree.get_children():
            self.basket_tree.delete(item)

        # Add basket items
        total = 0.0
        total_items = 0
        for basket_item in self.app.basket:
            subtotal = basket_item['price'] * basket_item['quantity']
            total += subtotal
            total_items += basket_item['quantity']

            self.basket_tree.insert("", tk.END, values=(
                basket_item['name'],
                basket_item['quantity'],
                f"£{basket_item['price']:.2f}",
                f"£{subtotal:.2f}"
            ))

        # Update totals
        self.total_label.config(text=f"£{total:.2f}")
        self.item_count_label.config(text=f"{total_items} item{'s' if total_items != 1 else ''}")

    def get_selected_index(self):
        """Get the index of the selected item."""
        selection = self.basket_tree.selection()
        if not selection:
            return None
        return self.basket_tree.index(selection[0])

    def decrease_qty(self):
        """Decrease quantity of selected item."""
        idx = self.get_selected_index()
        if idx is None:
            messagebox.showwarning("No Selection", "Please select an item.", parent=self)
            return

        if self.app.basket[idx]['quantity'] > 1:
            self.app.basket[idx]['quantity'] -= 1
            self.refresh_display()
        else:
            # Remove if quantity would become 0
            if messagebox.askyesno("Remove Item", "Remove this item from basket?", parent=self):
                self.app.remove_from_basket(idx)
                self.refresh_display()

    def increase_qty(self):
        """Increase quantity of selected item."""
        idx = self.get_selected_index()
        if idx is None:
            messagebox.showwarning("No Selection", "Please select an item.", parent=self)
            return

        basket_item = self.app.basket[idx]
        if basket_item['quantity'] < basket_item['max_qty']:
            basket_item['quantity'] += 1
            self.refresh_display()
        else:
            messagebox.showwarning("Limit Reached", f"Maximum available quantity ({basket_item['max_qty']}) reached.", parent=self)

    def remove_selected(self):
        """Remove selected item from basket."""
        idx = self.get_selected_index()
        if idx is None:
            messagebox.showwarning("No Selection", "Please select an item to remove.", parent=self)
            return

        item_name = self.app.basket[idx]['name']
        if messagebox.askyesno("Confirm", f"Remove '{item_name}' from basket?", parent=self):
            self.app.remove_from_basket(idx)
            self.refresh_display()

    def clear_all(self):
        """Clear all items from basket."""
        if not self.app.basket:
            messagebox.showinfo("Empty", "Basket is already empty.", parent=self)
            return

        if messagebox.askyesno("Confirm", "Clear all items from basket?", parent=self):
            self.app.clear_basket()
            self.refresh_display()

    def proceed_to_checkout(self):
        """Open checkout dialog."""
        if not self.app.basket:
            messagebox.showwarning("Empty Basket", "Please add items to basket before checkout.", parent=self)
            return

        # Calculate total
        total = sum(item['price'] * item['quantity'] for item in self.app.basket)

        # Open checkout dialog (pass current user for auto-fill)
        dialog = CheckoutDialog(self, self.app.basket, total, self.app.current_user)

        if dialog.result:
            self.app._process_checkout(dialog.result)
            self.refresh_display()

    def on_close(self):
        """Handle window close."""
        self.app.basket_window = None
        self.destroy()

class CheckoutDialog(tk.Toplevel):
    """Dialog for checkout with payment method selection."""

    PAYMENT_METHODS = ["Cash", "Debit/Credit Card", "Finance Account"]

    def __init__(self, parent, basket: list, total: float, current_user: dict = None):
        super().__init__(parent)
        self.title("Checkout")
        self.result = None
        self.basket = basket
        self.total = total
        self.current_user = current_user

        self.transient(parent)
        self.geometry("600x700")
        self.minsize(550, 600)
        self.resizable(True, True)

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.wait_visibility()
        self.grab_set()
        self.wait_window(self)

    def create_widgets(self):
        """Create checkout dialog widgets."""
        # Create canvas with scrollbar for the entire content
        canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        main_frame = ttk.Frame(scrollable_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        ttk.Label(main_frame, text="Checkout", font=("Helvetica", 16, "bold")).pack(pady=(0, 20))

        # Order summary
        summary_frame = ttk.LabelFrame(main_frame, text="Order Summary", padding="15")
        summary_frame.pack(fill=tk.X, pady=(0, 15))

        # Items header
        header_frame = ttk.Frame(summary_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(header_frame, text="Item", font=("Helvetica", 10, "bold"), width=25).pack(side=tk.LEFT)
        ttk.Label(header_frame, text="Qty", font=("Helvetica", 10, "bold"), width=6).pack(side=tk.LEFT)
        ttk.Label(header_frame, text="Subtotal", font=("Helvetica", 10, "bold"), width=10).pack(side=tk.RIGHT)

        ttk.Separator(summary_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        # Items list
        items_frame = ttk.Frame(summary_frame)
        items_frame.pack(fill=tk.X, pady=5)

        for item in self.basket:
            subtotal = item['price'] * item['quantity']
            item_row = ttk.Frame(items_frame)
            item_row.pack(fill=tk.X, pady=2)
            ttk.Label(item_row, text=item['name'][:28], width=28, anchor="w").pack(side=tk.LEFT)
            ttk.Label(item_row, text=f"x{item['quantity']}", width=6).pack(side=tk.LEFT)
            ttk.Label(item_row, text=f"£{subtotal:.2f}", width=10, anchor="e").pack(side=tk.RIGHT)

        ttk.Separator(summary_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Total
        total_frame = ttk.Frame(summary_frame)
        total_frame.pack(fill=tk.X, pady=5)
        ttk.Label(total_frame, text="TOTAL:", font=("Helvetica", 14, "bold")).pack(side=tk.LEFT)
        ttk.Label(total_frame, text=f"£{self.total:.2f}", font=("Helvetica", 16, "bold"), foreground="green").pack(side=tk.RIGHT)

        # Customer info - display current logged-in user (read-only)
        customer_frame = ttk.LabelFrame(main_frame, text="Customer (Logged-in User)", padding="15")
        customer_frame.pack(fill=tk.X, pady=15)

        # Get current user details
        self.user_id = ""
        self.user_email = ""
        self.user_name = "Guest"
        if self.current_user:
            self.user_id = self.current_user.get('student_id') or self.current_user.get('username', '')
            self.user_email = self.current_user.get('email', '')
            first_name = self.current_user.get('first_name', '')
            last_name = self.current_user.get('last_name', '')
            self.user_name = f"{first_name} {last_name}".strip() or self.current_user.get('username', 'Guest')

            # If no email in current_user, try to fetch from database
            if not self.user_email and self.user_id and FINANCE_INTEGRATION_AVAILABLE:
                self.user_email = get_student_email(self.user_id) or ""

        # Display user info (read-only)
        ttk.Label(customer_frame, text=f"Name: {self.user_name}", font=("Helvetica", 11)).pack(anchor=tk.W, pady=3)
        ttk.Label(customer_frame, text=f"ID: {self.user_id}", font=("Helvetica", 11)).pack(anchor=tk.W, pady=3)
        ttk.Label(customer_frame, text=f"Email: {self.user_email or '(not set)'}", font=("Helvetica", 11)).pack(anchor=tk.W, pady=3)

        # Balance display
        self.balance_label = ttk.Label(customer_frame, text="", foreground="blue", font=("Helvetica", 11, "bold"))
        self.balance_label.pack(anchor=tk.W, pady=8)

        # Auto-lookup balance
        if self.user_id:
            self.after(100, self._load_balance)

        # Payment method
        payment_frame = ttk.LabelFrame(main_frame, text="Payment Method", padding="15")
        payment_frame.pack(fill=tk.X, pady=15)

        self.payment_var = tk.StringVar(value="Cash")
        for method in self.PAYMENT_METHODS:
            rb = ttk.Radiobutton(payment_frame, text=method, variable=self.payment_var, value=method)
            rb.pack(anchor=tk.W, pady=2)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Complete Purchase", command=self.complete_purchase, width=18).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel, width=12).pack(side=tk.LEFT, padx=5)

    def _load_balance(self):
        """Load the current user's finance account balance."""
        if not self.user_id or not FINANCE_INTEGRATION_AVAILABLE:
            return

        balance = get_student_finance_account_balance(self.user_id)
        if balance is not None:
            color = "green" if balance >= self.total else "red"
            self.balance_label.config(text=f"Finance Balance: £{balance:.2f}", foreground=color)
        else:
            self.balance_label.config(text="No finance account", foreground="orange")

    def validate_checkout(self) -> bool:
        """Validate checkout before processing."""
        if self.payment_var.get() == "Finance Account":
            if not self.user_id:
                messagebox.showerror("Error", "You must be logged in to use Finance Account payment", parent=self)
                return False

            if FINANCE_INTEGRATION_AVAILABLE:
                balance = get_student_finance_account_balance(self.user_id)
                if balance is None:
                    messagebox.showerror("Error", "You do not have a finance account", parent=self)
                    return False
                if balance < self.total:
                    messagebox.showerror("Error", f"Insufficient balance. Current: £{balance:.2f}, Required: £{self.total:.2f}", parent=self)
                    return False

        return True

    def complete_purchase(self):
        """Complete the purchase."""
        if not self.validate_checkout():
            return

        self.result = {
            'total': self.total,
            'payment_method': self.payment_var.get(),
            'student_id': self.user_id or None,
            'customer_email': self.user_email or None
        }
        self.destroy()

    def cancel(self):
        """Cancel checkout."""
        self.result = None
        self.destroy()

def main():
    """Main entry point."""
    root = tk.Tk()

    # Set application icon (if available)
    try:
        root.iconbitmap("charity_shop.ico")
    except tk.TclError:
        pass

    # Configure style
    style = ttk.Style()
    style.theme_use("clam")

    app = CharityShopApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
