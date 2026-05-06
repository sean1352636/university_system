"""
Bar GUI for University Management System
Provides a complete point-of-sale system for the university pub/bar
with age verification, finance integration, and email receipts.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime, timedelta
from education_system.university_system.infrastructure.database.db import sqlite3
from decimal import Decimal

# Import centralized authentication and database
from education_system.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH

# Import localization for multi-language support
from education_system.university_system.infrastructure.localization import get_translation
_t = get_translation

# Keep i18n for language switching support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
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

# Import activity logger
try:
    from education_system.university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

def get_db_connection():
    """Get database connection with proper error handling"""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        return conn
    except (sqlite3.Error, OSError) as e:
        print(f"Database connection error: {e}")
        return None

def init_db():
    """Initialize bar database tables"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Unified products table (bar items have source_type='bar')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL DEFAULT 'bar',
                source_product_id INTEGER,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                is_alcoholic INTEGER DEFAULT 0,
                is_available INTEGER DEFAULT 1,
                stock_quantity INTEGER DEFAULT 100,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Unified orders table (bar orders have source_type='bar')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL DEFAULT 'bar',
                source_order_id INTEGER,
                student_id TEXT,
                customer_name TEXT,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_amount REAL NOT NULL,
                payment_method TEXT,
                age_verified INTEGER DEFAULT 0,
                order_status TEXT DEFAULT 'completed',
                notes TEXT
            )
        ''')

        # Unified order_items table (bar order items have source_type='bar')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL DEFAULT 'bar',
                source_order_id INTEGER,
                product_id INTEGER,
                item_name TEXT,
                quantity INTEGER,
                unit_price REAL,
                subtotal REAL,
                FOREIGN KEY (source_order_id) REFERENCES orders(order_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            )
        ''')

        # NOTE: bar inventory transactions now use the unified 'transactions' table
        # with source_type = 'bar_inventory'

        conn.commit()

        # Insert sample menu items if table is empty
        cursor.execute("SELECT COUNT(*) FROM products WHERE source_type = 'bar'")
        if cursor.fetchone()[0] == 0:
            sample_items = [
                # Beer
                ('bar', 'Lager', 'Beer', 'Refreshing lager beer', 3.50, 1, 1, 100),
                ('bar', 'Ale', 'Beer', 'Traditional English ale', 4.00, 1, 1, 80),
                ('bar', 'IPA', 'Beer', 'India Pale Ale with hoppy flavor', 4.50, 1, 1, 60),
                ('bar', 'Stout', 'Beer', 'Rich dark stout', 5.00, 1, 1, 50),
                ('bar', 'Cider', 'Beer', 'Crisp apple cider', 4.00, 1, 1, 70),
                # Wine
                ('bar', 'House Red', 'Wine', 'Glass of house red wine', 4.50, 1, 1, 40),
                ('bar', 'House White', 'Wine', 'Glass of house white wine', 4.50, 1, 1, 40),
                ('bar', 'Prosecco', 'Wine', 'Glass of Italian sparkling wine', 6.00, 1, 1, 30),
                ('bar', 'Rose', 'Wine', 'Glass of rose wine', 5.00, 1, 1, 35),
                # Spirits
                ('bar', 'Vodka', 'Spirits', 'Single shot of vodka', 3.00, 1, 1, 100),
                ('bar', 'Gin', 'Spirits', 'Single shot of gin', 3.50, 1, 1, 100),
                ('bar', 'Rum', 'Spirits', 'Single shot of rum', 3.00, 1, 1, 100),
                ('bar', 'Whisky', 'Spirits', 'Single shot of whisky', 4.00, 1, 1, 80),
                ('bar', 'Tequila', 'Spirits', 'Single shot of tequila', 3.50, 1, 1, 60),
                # Cocktails
                ('bar', 'Mojito', 'Cocktails', 'Rum, mint, lime, soda', 7.00, 1, 1, 50),
                ('bar', 'Margarita', 'Cocktails', 'Tequila, lime, triple sec', 7.50, 1, 1, 50),
                ('bar', 'Long Island', 'Cocktails', 'Vodka, gin, rum, tequila, cola', 8.50, 1, 1, 40),
                ('bar', 'Cosmopolitan', 'Cocktails', 'Vodka, cranberry, lime', 7.00, 1, 1, 45),
                ('bar', 'Pina Colada', 'Cocktails', 'Rum, coconut, pineapple', 7.50, 1, 1, 40),
                # Soft Drinks
                ('bar', 'Cola', 'Soft Drinks', 'Classic cola', 1.80, 0, 1, 200),
                ('bar', 'Lemonade', 'Soft Drinks', 'Sparkling lemonade', 1.80, 0, 1, 200),
                ('bar', 'Orange Juice', 'Soft Drinks', 'Fresh orange juice', 2.50, 0, 1, 100),
                ('bar', 'Tonic Water', 'Soft Drinks', 'Schweppes tonic', 1.50, 0, 1, 150),
                ('bar', 'Sparkling Water', 'Soft Drinks', 'Mineral water', 1.50, 0, 1, 200),
                # Snacks
                ('bar', 'Crisps', 'Snacks', 'Variety of crisps', 1.50, 0, 1, 100),
                ('bar', 'Nuts', 'Snacks', 'Salted peanuts', 2.00, 0, 1, 80),
                ('bar', 'Nachos', 'Snacks', 'Nachos with salsa and cheese', 5.00, 0, 1, 50),
                ('bar', 'Chips', 'Snacks', 'Portion of chips', 3.50, 0, 1, 60),
                ('bar', 'Onion Rings', 'Snacks', 'Crispy onion rings', 4.00, 0, 1, 50),
                # Hot Drinks
                ('bar', 'Coffee', 'Hot Drinks', 'Fresh brewed coffee', 2.50, 0, 1, 100),
                ('bar', 'Tea', 'Hot Drinks', 'Selection of teas', 2.00, 0, 1, 100),
                ('bar', 'Hot Chocolate', 'Hot Drinks', 'Rich hot chocolate', 3.00, 0, 1, 80),
            ]
            cursor.executemany('''
                INSERT INTO products (source_type, name, category, description, price, is_alcoholic, is_available, stock_quantity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', sample_items)
            conn.commit()

        conn.close()
        return True

    except Exception as e:
        print(f"Database initialization error: {e}")
        return False

class BarGUI:
    """Main Bar GUI class for University Pub/Bar management"""

    def __init__(self, root, auth):
        """Initialize the Bar GUI

        Args:
            root: Parent Tkinter window
            auth: Authentication manager instance
        """
        self.root = root
        self.auth = auth
        self.bar_window = None
        self.current_order = []
        self.order_total = 0.0
        self.age_verified = False

        # Get current user info
        if auth and hasattr(auth, 'current_user') and auth.current_user:
            self.current_user = auth.current_user
        else:
            self.current_user = {'username': 'Guest', 'role': 'guest', 'id': None}

        # Initialize database
        init_db()

        # Load categories
        self.categories = self._load_categories()

    def _load_categories(self):
        """Load all menu categories from database"""
        try:
            conn = get_db_connection()
            if not conn:
                return ['Beer', 'Wine', 'Spirits', 'Cocktails', 'Soft Drinks', 'Snacks', 'Hot Drinks']
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT category FROM products WHERE source_type = 'bar' ORDER BY category")
            categories = [row[0] for row in cursor.fetchall()]
            conn.close()
            return categories if categories else ['Beer', 'Wine', 'Spirits', 'Cocktails', 'Soft Drinks', 'Snacks', 'Hot Drinks']
        except Exception:
            return ['Beer', 'Wine', 'Spirits', 'Cocktails', 'Soft Drinks', 'Snacks', 'Hot Drinks']

    def get_current_user_display_info(self):
        """Get formatted display string for current user info"""
        if not self.current_user:
            return "No user logged in"

        student_id = self.current_user.get('student_id') or self.current_user.get('id') or 'N/A'
        name = self.current_user.get('full_name')
        if not name:
            first = self.current_user.get('first_name', '')
            last = self.current_user.get('last_name', '')
            if first or last:
                name = f"{first} {last}".strip()
            else:
                name = self.current_user.get('username', 'Unknown')
        email = self.current_user.get('email', 'No email')
        return f"ID: {student_id}  |  Name: {name}  |  Email: {email}"

    def show_bar(self):
        """Initialize and show the bar interface"""
        # Check if window already exists
        if self.bar_window is not None:
            try:
                if self.bar_window.winfo_exists():
                    self.bar_window.lift()
                    self.bar_window.focus_force()
                    return
            except tk.TclError:
                pass

        # Create new window
        self.bar_window = tk.Toplevel(self.root)
        self.bar_window.title(_t("bar.window_title", default="University Bar Management System"))
        self.bar_window.geometry("1400x850")

        # Center window
        self.bar_window.update_idletasks()
        x = (self.bar_window.winfo_screenwidth() - 1400) // 2
        y = (self.bar_window.winfo_screenheight() - 850) // 2
        self.bar_window.geometry(f"+{x}+{y}")

        # Configure grid
        self.bar_window.columnconfigure(0, weight=1)
        self.bar_window.rowconfigure(1, weight=1)

        # Header
        header_frame = ttk.Frame(self.bar_window)
        header_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=10)

        self.title_label = ttk.Label(
            header_frame,
            text=_t("bar.header_title", default="University Bar - Point of Sale & Management"),
            font=('Helvetica', 20, 'bold')
        )
        self.title_label.pack(side=tk.LEFT, padx=10)

        # User info
        user_info = _t("bar.user_info", default="Logged in as: {username} ({role})",
                       username=self.current_user.get('username', 'Guest'),
                       role=self.current_user.get('role', 'guest'))
        self.user_label = ttk.Label(header_frame, text=user_info, font=('Helvetica', 10))
        self.user_label.pack(side=tk.RIGHT, padx=10)

        # Language button
        self.lang_btn = ttk.Button(
            header_frame,
            text=f"Language: {get_current_language_name()}",
            command=self.change_language
        )
        self.lang_btn.pack(side=tk.RIGHT, padx=5)

        # Return to homepage button
        self.return_btn = ttk.Button(
            header_frame,
            text=_t("bar.return_to_homepage", default="Return to Homepage"),
            command=self.return_to_homepage
        )
        self.return_btn.pack(side=tk.RIGHT, padx=5)

        # Main content with notebook tabs
        self.notebook = ttk.Notebook(self.bar_window)
        self.notebook.grid(row=1, column=0, sticky='nsew', padx=10, pady=(0, 10))

        # Create tabs
        self.create_pos_tab()
        self.create_menu_management_tab()
        self.create_orders_tab()
        self.create_inventory_tab()
        self.create_reports_tab()

        # Log activity
        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('access', 'bar', user_id=self.current_user.get('id'))

    def change_language(self):
        """Open language selector and refresh UI on change"""
        old_lang = get_current_language()
        show_gui_language_selector(self.bar_window)
        new_lang = get_current_language()
        if old_lang != new_lang:
            self.refresh_ui_text()

    def refresh_ui_text(self):
        """Refresh all UI text after language change"""
        self.bar_window.title(_t("bar.window_title", default="University Bar Management System"))
        # Recreate the interface to apply language changes
        for widget in self.bar_window.winfo_children():
            widget.destroy()
        # Reinitialize the interface
        self.bar_window.columnconfigure(0, weight=1)
        self.bar_window.rowconfigure(1, weight=1)

        # Recreate header
        header_frame = ttk.Frame(self.bar_window)
        header_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=10)

        self.title_label = ttk.Label(
            header_frame,
            text=_t("bar.header_title", default="University Bar - Point of Sale & Management"),
            font=('Helvetica', 20, 'bold')
        )
        self.title_label.pack(side=tk.LEFT, padx=10)

        user_info = _t("bar.user_info", default="Logged in as: {username} ({role})",
                       username=self.current_user.get('username', 'Guest'),
                       role=self.current_user.get('role', 'guest'))
        self.user_label = ttk.Label(header_frame, text=user_info, font=('Helvetica', 10))
        self.user_label.pack(side=tk.RIGHT, padx=10)

        self.lang_btn = ttk.Button(
            header_frame,
            text=f"Language: {get_current_language_name()}",
            command=self.change_language
        )
        self.lang_btn.pack(side=tk.RIGHT, padx=5)

        self.return_btn = ttk.Button(
            header_frame,
            text=_t("bar.return_to_homepage", default="Return to Homepage"),
            command=self.return_to_homepage
        )
        self.return_btn.pack(side=tk.RIGHT, padx=5)

        self.notebook = ttk.Notebook(self.bar_window)
        self.notebook.grid(row=1, column=0, sticky='nsew', padx=10, pady=(0, 10))

        self.create_pos_tab()
        self.create_menu_management_tab()
        self.create_orders_tab()
        self.create_inventory_tab()
        self.create_reports_tab()

    def return_to_homepage(self):
        """Close bar window and return to main GUI"""
        if self.bar_window:
            self.bar_window.destroy()
            self.bar_window = None

    def create_pos_tab(self):
        """Create Point of Sale tab"""
        pos_frame = ttk.Frame(self.notebook)
        self.notebook.add(pos_frame, text=_t("bar.tabs.pos", default="Point of Sale"))

        # Configure grid
        pos_frame.columnconfigure(0, weight=1)
        pos_frame.columnconfigure(1, weight=1)
        pos_frame.rowconfigure(0, weight=1)

        # Left side - Menu items
        left_frame = ttk.LabelFrame(pos_frame, text=_t("bar.pos.menu_items", default="Menu Items"), padding="10")
        left_frame.grid(row=0, column=0, sticky='nsew', padx=(10, 5), pady=10)

        # Category filter
        filter_frame = ttk.Frame(left_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_frame, text=_t("bar.pos.category", default="Category:")).pack(side=tk.LEFT, padx=5)
        self.category_filter = ttk.Combobox(filter_frame, state='readonly', values=['All'] + self.categories)
        self.category_filter.set('All')
        self.category_filter.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.category_filter.bind('<<ComboboxSelected>>', lambda e: self.load_menu_items_for_pos())

        ttk.Button(filter_frame, text=_t("bar.pos.all", default="All"), command=self.reset_category_filter).pack(side=tk.LEFT, padx=5)

        # Menu items list with scrollbar
        items_frame = ttk.Frame(left_frame)
        items_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(items_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.menu_items_listbox = tk.Listbox(
            items_frame,
            yscrollcommand=scrollbar.set,
            font=('Courier', 10),
            height=20
        )
        self.menu_items_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.menu_items_listbox.yview)

        # Double-click to add item
        self.menu_items_listbox.bind('<Double-Button-1>', lambda e: self.add_item_to_order())

        # Add button
        ttk.Button(left_frame, text=_t("bar.pos.add_to_order", default="Add to Order"), command=self.add_item_to_order).pack(pady=5)

        # Right side - Current order
        right_frame = ttk.LabelFrame(pos_frame, text=_t("bar.pos.current_order", default="Current Order"), padding="10")
        right_frame.grid(row=0, column=1, sticky='nsew', padx=(5, 10), pady=10)

        right_frame.rowconfigure(2, weight=1)
        right_frame.columnconfigure(0, weight=1)

        # Customer info frame
        customer_frame = ttk.Frame(right_frame)
        customer_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))

        ttk.Label(customer_frame, text=_t("bar.pos.customer", default="Customer:")).pack(side=tk.LEFT, padx=5)
        self.customer_name_entry = ttk.Entry(customer_frame, width=20)
        self.customer_name_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(customer_frame, text=_t("bar.pos.student_id", default="Student ID:")).pack(side=tk.LEFT, padx=5)
        self.student_id_entry = ttk.Entry(customer_frame, width=15)
        self.student_id_entry.pack(side=tk.LEFT, padx=5)

        # Pre-fill with current user info
        if self.current_user.get('username'):
            self.customer_name_entry.insert(0, self.current_user.get('full_name', self.current_user.get('username', '')))
        # Use student_id if available, otherwise use username (for finance account lookup)
        user_finance_id = self.current_user.get('student_id') or self.current_user.get('username', '')
        if user_finance_id:
            self.student_id_entry.insert(0, user_finance_id)

        # Order items treeview
        columns = ('item', 'qty', 'price', 'subtotal')
        self.order_tree = ttk.Treeview(right_frame, columns=columns, show='headings', height=12)
        self.order_tree.heading('item', text=_t("bar.pos.item", default="Item"))
        self.order_tree.heading('qty', text=_t("bar.pos.quantity", default="Qty"))
        self.order_tree.heading('price', text=_t("bar.pos.price", default="Price"))
        self.order_tree.heading('subtotal', text=_t("bar.pos.subtotal", default="Subtotal"))
        self.order_tree.column('item', width=150)
        self.order_tree.column('qty', width=50)
        self.order_tree.column('price', width=80)
        self.order_tree.column('subtotal', width=80)
        self.order_tree.grid(row=2, column=0, sticky='nsew', pady=5)

        # Order scrollbar
        order_scroll = ttk.Scrollbar(right_frame, orient='vertical', command=self.order_tree.yview)
        order_scroll.grid(row=2, column=1, sticky='ns')
        self.order_tree.configure(yscrollcommand=order_scroll.set)

        # Order buttons frame
        order_btn_frame = ttk.Frame(right_frame)
        order_btn_frame.grid(row=3, column=0, sticky='ew', pady=5)

        ttk.Button(order_btn_frame, text=_t("bar.pos.remove", default="Remove Item"), command=self.remove_item_from_order).pack(side=tk.LEFT, padx=5)
        ttk.Button(order_btn_frame, text=_t("bar.pos.clear_order", default="Clear Order"), command=self.clear_order).pack(side=tk.LEFT, padx=5)

        # Total display
        total_frame = ttk.Frame(right_frame)
        total_frame.grid(row=4, column=0, sticky='ew', pady=10)

        ttk.Label(total_frame, text=_t("bar.pos.total", default="Total:"), font=('Helvetica', 14, 'bold')).pack(side=tk.LEFT, padx=5)
        self.total_label = ttk.Label(total_frame, text="£0.00", font=('Helvetica', 14, 'bold'))
        self.total_label.pack(side=tk.LEFT, padx=5)

        # Payment method
        payment_frame = ttk.Frame(right_frame)
        payment_frame.grid(row=5, column=0, sticky='ew', pady=5)

        ttk.Label(payment_frame, text=_t("bar.pos.payment_method", default="Payment Method:")).pack(side=tk.LEFT, padx=5)
        self.payment_method = ttk.Combobox(payment_frame, state='readonly',
                                            values=[_t("bar.pos.cash", default="Cash"), _t("bar.pos.student_account", default="Student Finance Account"), _t("bar.pos.card", default="Card")])
        self.payment_method.set(_t("bar.pos.cash", default="Cash"))
        self.payment_method.pack(side=tk.LEFT, padx=5)

        # Complete order button
        ttk.Button(right_frame, text=_t("bar.pos.complete_order", default="Complete Order"),
                   command=self.complete_order, style='Accent.TButton').grid(row=6, column=0, sticky='ew', pady=10)

        # Load menu items
        self.load_menu_items_for_pos()

    def load_menu_items_for_pos(self):
        """Load menu items filtered by category"""
        self.menu_items_listbox.delete(0, tk.END)
        try:
            conn = get_db_connection()
            if not conn:
                return
            cursor = conn.cursor()

            category = self.category_filter.get()
            if category == 'All':
                cursor.execute("SELECT product_id, name, category, price, is_alcoholic FROM products WHERE source_type = 'bar' AND is_available = 1 ORDER BY category, name")
            else:
                cursor.execute("SELECT product_id, name, category, price, is_alcoholic FROM products WHERE source_type = 'bar' AND is_available = 1 AND category = ? ORDER BY name", (category,))

            self.menu_item_data = {}
            for row in cursor.fetchall():
                item_id, name, cat, price, is_alcoholic = row
                alcoholic_marker = " [18+]" if is_alcoholic else ""
                display = f"{name:<25} £{price:>6.2f}{alcoholic_marker}"
                self.menu_items_listbox.insert(tk.END, display)
                self.menu_item_data[self.menu_items_listbox.size() - 1] = {
                    'item_id': item_id, 'name': name, 'category': cat,
                    'price': price, 'is_alcoholic': is_alcoholic
                }
            conn.close()
        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to load menu: {e}")

    def reset_category_filter(self):
        """Reset category filter to show all items"""
        self.category_filter.set('All')
        self.load_menu_items_for_pos()

    def add_item_to_order(self):
        """Add selected item to current order"""
        selection = self.menu_items_listbox.curselection()
        if not selection:
            messagebox.showwarning(_t("common.warning", default="Warning"), _t("bar.messages.select_item", default="Please select an item to add to order"))
            return

        idx = selection[0]
        if idx not in self.menu_item_data:
            return

        item = self.menu_item_data[idx]

        # Check if item already in order
        for i, order_item in enumerate(self.current_order):
            if order_item['item_id'] == item['item_id']:
                self.current_order[i]['quantity'] += 1
                self.current_order[i]['subtotal'] = self.current_order[i]['quantity'] * self.current_order[i]['price']
                self.update_order_display()
                return

        # Add new item
        self.current_order.append({
            'item_id': item['item_id'],
            'name': item['name'],
            'price': item['price'],
            'quantity': 1,
            'subtotal': item['price'],
            'is_alcoholic': item['is_alcoholic']
        })
        self.update_order_display()

    def remove_item_from_order(self):
        """Remove selected item from cart"""
        selection = self.order_tree.selection()
        if not selection:
            return

        item_idx = self.order_tree.index(selection[0])
        if 0 <= item_idx < len(self.current_order):
            del self.current_order[item_idx]
            self.update_order_display()

    def clear_order(self):
        """Clear all items from current order"""
        self.current_order = []
        self.age_verified = False
        self.update_order_display()

    def update_order_display(self):
        """Update the order treeview and total"""
        # Clear treeview
        for item in self.order_tree.get_children():
            self.order_tree.delete(item)

        # Add items
        self.order_total = 0.0
        for item in self.current_order:
            self.order_tree.insert('', 'end', values=(
                item['name'],
                item['quantity'],
                f"£{item['price']:.2f}",
                f"£{item['subtotal']:.2f}"
            ))
            self.order_total += item['subtotal']

        self.update_order_total()

    def update_order_total(self):
        """Calculate and display order total"""
        self.total_label.config(text=f"£{self.order_total:.2f}")

    def verify_customer_age(self):
        """Check if customer is 18+ for alcohol"""
        # Check if order contains alcohol
        has_alcohol = any(item.get('is_alcoholic', False) for item in self.current_order)
        if not has_alcohol:
            return True

        return self.show_age_verification_dialog()

    def show_age_verification_dialog(self):
        """Display age verification popup"""
        result = messagebox.askyesno(
            _t("bar.age_verification.title", default="Age Verification Required"),
            _t("bar.age_verification.message", default="This order contains alcoholic items.\n\nCustomer must be 18 or older.\n\nHas the customer's age been verified?")
        )
        if result:
            self.age_verified = True
            return True
        else:
            # Remove alcoholic items
            self.current_order = [item for item in self.current_order if not item.get('is_alcoholic', False)]
            self.update_order_display()
            messagebox.showinfo(_t("common.info", default="Information"), _t("bar.age_verification.alcohol_removed", default="Alcoholic items have been removed from the order."))
            return False

    def complete_order(self):
        """Process order, check age verification, handle payment"""
        if not self.current_order:
            messagebox.showwarning(_t("common.warning", default="Warning"), _t("bar.messages.no_items", default="No items in order. Please add items first."))
            return

        # Age verification for alcohol
        has_alcohol = any(item.get('is_alcoholic', False) for item in self.current_order)
        if has_alcohol and not self.age_verified:
            if not self.verify_customer_age():
                if not self.current_order:  # All items were alcoholic and removed
                    return

        customer_name = self.customer_name_entry.get().strip() or 'Walk-in Customer'
        student_id = self.student_id_entry.get().strip()

        # Process payment
        payment_method = self.payment_method.get()
        payment_success = self.process_payment(student_id, self.order_total, payment_method)

        if not payment_success:
            return

        # Record order in database
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror(_t("common.error", default="Error"), _t("common.database_error", default="Database connection error"))
                return

            cursor = conn.cursor()

            # Insert order
            cursor.execute('''
                INSERT INTO orders (source_type, student_id, customer_name, total_amount, payment_method, age_verified, order_status)
                VALUES ('bar', ?, ?, ?, ?, ?, 'completed')
            ''', (student_id, customer_name, self.order_total, payment_method, 1 if self.age_verified else 0))

            order_id = cursor.lastrowid

            # Insert order items
            for item in self.current_order:
                cursor.execute('''
                    INSERT INTO order_items (source_type, source_order_id, product_id, item_name, quantity, unit_price, subtotal)
                    VALUES ('bar', ?, ?, ?, ?, ?, ?)
                ''', (order_id, item['item_id'], item['name'], item['quantity'], item['price'], item['subtotal']))

                # Update stock
                cursor.execute('''
                    UPDATE products SET stock_quantity = stock_quantity - ? WHERE product_id = ? AND source_type = 'bar'
                ''', (item['quantity'], item['item_id']))

            conn.commit()
            conn.close()

            # Record revenue
            self.record_revenue(self.order_total, f"Order #{order_id}")

            # Send receipt email
            customer_email = self.current_user.get('email')
            if customer_email and EMAIL_SERVICE_AVAILABLE:
                self.send_receipt_email(
                    order_id, customer_email, self.current_order, self.order_total,
                    payment_method=payment_method, customer_name=customer_name
                )

            # Log activity
            if ACTIVITY_LOGGER_AVAILABLE:
                log_activity('create', 'bar_order', user_id=self.current_user.get('id'),
                           details={'order_id': order_id, 'amount': self.order_total})

            messagebox.showinfo(_t("common.success", default="Success"), _t("bar.messages.order_complete", default="Order completed successfully!"))

            # Clear order
            self.clear_order()

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to complete order: {e}")

    def process_payment(self, student_id, amount, payment_method):
        """Handle payment via student finance account or cash"""
        if _t("bar.pos.student_account", default="Student Finance Account") in payment_method:
            if not FINANCE_ACCOUNT_AVAILABLE:
                messagebox.showerror(_t("common.error", default="Error"), _t("bar.messages.account_payment_unavailable", default="Student account payment not available"))
                return False

            if not student_id:
                messagebox.showerror(_t("common.error", default="Error"), _t("bar.messages.student_id_required", default="Student ID required for account payment"))
                return False

            # Ensure student has a finance account (creates one if needed)
            try:
                from education_system.university_system.modules.shared.utils.finance_integration import ensure_student_finance_account_exists
                ensure_student_finance_account_exists(student_id)
            except Exception as e:
                messagebox.showerror(_t("common.error", default="Error"), f"Could not initialize student account: {e}")
                return False

            # Check balance
            balance = self.get_student_finance_balance(student_id)
            if balance is None:
                messagebox.showerror(_t("common.error", default="Error"), _t("bar.messages.balance_check_failed", default="Could not retrieve account balance. Please contact the Finance Office."))
                return False

            if balance < amount:
                messagebox.showerror(_t("common.error", default="Error"), f"Insufficient balance. Current balance: £{balance:.2f}, Required: £{amount:.2f}. Please top up your account.")
                return False

            # Process payment
            try:
                result = process_student_finance_account_payment(
                    student_id, amount, "Bar purchase", "Bar", f"ORDER-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                )
                if not result.get('success', False):
                    messagebox.showerror(_t("common.error", default="Error"), result.get('message', _t("bar.messages.payment_failed", default="Payment failed. Please try again.")))
                    return False
                return True
            except Exception as e:
                messagebox.showerror(_t("common.error", default="Error"), f"Payment failed: {e}")
                return False

        # Cash or card payment - just confirm
        return True

    def record_revenue(self, amount, description):
        """Add sale to finance system as revenue.

        8.117.104: routed through unified record_payment() with
        ``source_type='bar'`` so cross-domain reports can isolate bar
        revenue. Pre-fix this did a raw INSERT with all rows tagged
        ``payment_method='Bar Revenue'`` and student_id='BAR_REVENUE'
        so analytics couldn't tell bar tabs apart from other revenue.
        """
        if not FINANCE_ACCOUNT_AVAILABLE:
            return
        try:
            from education_system.university_system.modules.domain.finance.core.unified_payments import (
                record_payment,
            )
            record_payment(
                student_id='BAR_REVENUE',
                amount=amount,
                payment_method='cash',
                source_type='bar',
                payment_type='revenue',
                department='bar',
                description=description,
                created_by=self.current_user.get('username', 'system'),
            )
        except Exception as e:
            print(f"Failed to record revenue: {e}")

    def get_student_finance_balance(self, student_id):
        """Check student's available balance"""
        if not FINANCE_ACCOUNT_AVAILABLE:
            return None
        try:
            return get_student_finance_account_balance(student_id)
        except Exception:
            return None

    def send_receipt_email(self, order_id, customer_email, order_items, total, payment_method=None, customer_name=None):
        """Send email receipt to customer after purchase"""
        if not EMAIL_SERVICE_AVAILABLE:
            return

        try:
            # Build itemized order details
            item_lines = []
            for item in order_items:
                qty = item['quantity']
                unit_price = item['price']
                subtotal = item['subtotal']
                name = item['name']
                if qty > 1:
                    item_lines.append(f"  {name:<20} {qty} x £{unit_price:.2f}  =  £{subtotal:.2f}")
                else:
                    item_lines.append(f"  {name:<20}                £{subtotal:.2f}")
            order_details = "\n".join(item_lines)

            # Build receipt
            receipt_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            payment_info = payment_method or "N/A"
            customer_info = customer_name or "Valued Customer"

            subject = _t("bar.receipts.subject", default="University Bar - Receipt #[{order_id}]", order_id=order_id)
            body = f"""
════════════════════════════════════════════════════
              UNIVERSITY BAR - RECEIPT
════════════════════════════════════════════════════

Order #: {order_id}
Date: {receipt_date}
Customer: {customer_info}

────────────────────────────────────────────────────
ITEMS PURCHASED:
────────────────────────────────────────────────────
{order_details}

────────────────────────────────────────────────────
TOTAL:                              £{total:.2f}
Payment Method: {payment_info}
────────────────────────────────────────────────────

{_t("bar.receipts.thank_you", default="Thank you for your purchase!")}

Questions? Contact the University Bar staff.

════════════════════════════════════════════════════
            """

            send_email(customer_email, subject, body)
            print(f"Receipt sent to {customer_email}")
        except Exception as e:
            print(f"Failed to send receipt email: {e}")

    def send_admin_report(self, report_type='daily'):
        """Send daily/weekly sales report to admin email"""
        if not EMAIL_SERVICE_AVAILABLE:
            messagebox.showwarning(_t("common.warning", default="Warning"), "Email service not available")
            return

        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Determine date range
            if report_type == 'daily':
                start_date = datetime.now().replace(hour=0, minute=0, second=0)
            elif report_type == 'weekly':
                start_date = datetime.now() - timedelta(days=7)
            else:
                start_date = datetime.now().replace(day=1, hour=0, minute=0, second=0)

            # Get sales data
            cursor.execute('''
                SELECT COUNT(*), SUM(total_amount), AVG(total_amount)
                FROM orders
                WHERE source_type = 'bar' AND order_date >= ? AND order_status = 'completed'
            ''', (start_date.strftime('%Y-%m-%d %H:%M:%S'),))

            result = cursor.fetchone()
            order_count = result[0] or 0
            total_revenue = result[1] or 0
            avg_order = result[2] or 0

            # Get top items
            cursor.execute('''
                SELECT item_name, SUM(quantity) as qty, SUM(subtotal) as revenue
                FROM order_items
                WHERE source_type = 'bar' AND source_order_id IN (SELECT order_id FROM orders WHERE source_type = 'bar' AND order_date >= ?)
                GROUP BY item_name
                ORDER BY qty DESC
                LIMIT 5
            ''', (start_date.strftime('%Y-%m-%d %H:%M:%S'),))

            top_items = cursor.fetchall()
            conn.close()

            # Get admin emails
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL")
            admin_emails = [row[0] for row in cursor.fetchall()]
            conn.close()

            if not admin_emails:
                messagebox.showwarning(_t("common.warning", default="Warning"), _t("bar.reports.no_admin_emails", default="No admin email addresses found"))
                return

            # Build report
            report_title = f"Bar {report_type.title()} Sales Report"
            top_items_text = "\n".join([f"  {item[0]}: {item[1]} sold (£{item[2]:.2f})" for item in top_items])

            body = f"""
{report_title}
{'=' * 40}

Period: {start_date.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}

Summary:
  Total Orders: {order_count}
  Total Revenue: £{total_revenue:.2f}
  Average Order: £{avg_order:.2f}

Top 5 Items:
{top_items_text}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """

            # Send to all admins
            for email in admin_emails:
                send_email(email, report_title, body)

            messagebox.showinfo(_t("common.success", default="Success"), _t("bar.reports.report_sent", default="Report sent to admin emails"))

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to send report: {e}")

    def create_menu_management_tab(self):
        """Create Menu Management tab for admin"""
        menu_frame = ttk.Frame(self.notebook)
        self.notebook.add(menu_frame, text=_t("bar.tabs.menu", default="Menu Management"))

        menu_frame.columnconfigure(0, weight=1)
        menu_frame.rowconfigure(1, weight=1)

        # Buttons frame
        btn_frame = ttk.Frame(menu_frame)
        btn_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=10)

        ttk.Button(btn_frame, text=_t("bar.menu.add_item", default="Add Item"), command=self.add_menu_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("bar.menu.edit_item", default="Edit Item"), command=self.edit_menu_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("bar.menu.delete_item", default="Delete Item"), command=self.delete_menu_item).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.refresh", default="Refresh"), command=self.load_menu_management).pack(side=tk.LEFT, padx=5)

        # Menu items treeview
        columns = ('id', 'name', 'category', 'price', 'alcoholic', 'available', 'stock')
        self.menu_tree = ttk.Treeview(menu_frame, columns=columns, show='headings', height=20)
        self.menu_tree.heading('id', text='ID')
        self.menu_tree.heading('name', text=_t("bar.menu.name", default="Name:"))
        self.menu_tree.heading('category', text=_t("bar.menu.category", default="Category:"))
        self.menu_tree.heading('price', text=_t("bar.menu.price", default="Price (£):"))
        self.menu_tree.heading('alcoholic', text=_t("bar.menu.is_alcoholic", default="Alcoholic (18+):"))
        self.menu_tree.heading('available', text=_t("bar.menu.available", default="Available:"))
        self.menu_tree.heading('stock', text=_t("bar.menu.stock", default="Stock Quantity:"))

        self.menu_tree.column('id', width=50)
        self.menu_tree.column('name', width=150)
        self.menu_tree.column('category', width=100)
        self.menu_tree.column('price', width=80)
        self.menu_tree.column('alcoholic', width=80)
        self.menu_tree.column('available', width=80)
        self.menu_tree.column('stock', width=80)

        self.menu_tree.grid(row=1, column=0, sticky='nsew', padx=10, pady=(0, 10))

        # Scrollbar
        menu_scroll = ttk.Scrollbar(menu_frame, orient='vertical', command=self.menu_tree.yview)
        menu_scroll.grid(row=1, column=1, sticky='ns')
        self.menu_tree.configure(yscrollcommand=menu_scroll.set)

        self.load_menu_management()

    def load_menu_management(self):
        """Load all menu items into management view"""
        for item in self.menu_tree.get_children():
            self.menu_tree.delete(item)

        try:
            conn = get_db_connection()
            if not conn:
                return
            cursor = conn.cursor()
            cursor.execute("SELECT product_id, name, category, price, is_alcoholic, is_available, stock_quantity FROM products WHERE source_type = 'bar' ORDER BY category, name")

            for row in cursor.fetchall():
                alcoholic = "Yes" if row[4] else "No"
                available = "Yes" if row[5] else "No"
                self.menu_tree.insert('', 'end', values=(
                    row[0], row[1], row[2], f"£{row[3]:.2f}", alcoholic, available, row[6]
                ))
            conn.close()
        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to load menu: {e}")

    def add_menu_item(self):
        """Add new drink/snack to menu"""
        dialog = tk.Toplevel(self.bar_window)
        dialog.title(_t("bar.menu.add_item"))
        dialog.geometry("400x350")
        dialog.transient(self.bar_window)
        dialog.grab_set()

        # Form fields
        ttk.Label(dialog, text=_t("bar.menu.name", default="Name:")).grid(row=0, column=0, padx=10, pady=5, sticky='e')
        name_entry = ttk.Entry(dialog, width=30)
        name_entry.grid(row=0, column=1, padx=10, pady=5)

        ttk.Label(dialog, text=_t("bar.menu.category", default="Category:")).grid(row=1, column=0, padx=10, pady=5, sticky='e')
        category_combo = ttk.Combobox(dialog, values=self.categories, width=27)
        category_combo.grid(row=1, column=1, padx=10, pady=5)

        ttk.Label(dialog, text=_t("bar.menu.description", default="Description:")).grid(row=2, column=0, padx=10, pady=5, sticky='e')
        desc_entry = ttk.Entry(dialog, width=30)
        desc_entry.grid(row=2, column=1, padx=10, pady=5)

        ttk.Label(dialog, text=_t("bar.menu.price", default="Price (£):")).grid(row=3, column=0, padx=10, pady=5, sticky='e')
        price_entry = ttk.Entry(dialog, width=30)
        price_entry.grid(row=3, column=1, padx=10, pady=5)

        ttk.Label(dialog, text=_t("bar.menu.is_alcoholic", default="Alcoholic (18+):")).grid(row=4, column=0, padx=10, pady=5, sticky='e')
        alcoholic_var = tk.BooleanVar()
        ttk.Checkbutton(dialog, variable=alcoholic_var).grid(row=4, column=1, padx=10, pady=5, sticky='w')

        ttk.Label(dialog, text=_t("bar.menu.stock", default="Stock Quantity:")).grid(row=5, column=0, padx=10, pady=5, sticky='e')
        stock_entry = ttk.Entry(dialog, width=30)
        stock_entry.insert(0, "100")
        stock_entry.grid(row=5, column=1, padx=10, pady=5)

        def save_item():
            name = name_entry.get().strip()
            category = category_combo.get().strip()
            description = desc_entry.get().strip()
            try:
                price = float(price_entry.get())
                stock = int(stock_entry.get())
            except ValueError:
                messagebox.showerror(_t("common.error", default="Error"), _t("bar.messages.invalid_price_stock", default="Invalid price or stock value"))
                return

            if not name or not category:
                messagebox.showerror(_t("common.error", default="Error"), _t("bar.messages.name_category_required", default="Name and category are required"))
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO products (source_type, name, category, description, price, is_alcoholic, is_available, stock_quantity)
                    VALUES ('bar', ?, ?, ?, ?, ?, 1, ?)
                ''', (name, category, description, price, 1 if alcoholic_var.get() else 0, stock))
                conn.commit()
                conn.close()

                if ACTIVITY_LOGGER_AVAILABLE:
                    log_activity('create', 'bar_menu_item', user_id=self.current_user.get('id'),
                               details={'name': name})

                messagebox.showinfo(_t("common.success", default="Success"), _t("bar.messages.menu_updated", default="Menu updated successfully"))
                dialog.destroy()
                self.load_menu_management()
                self.load_menu_items_for_pos()
                self.categories = self._load_categories()
            except Exception as e:
                messagebox.showerror(_t("common.error", default="Error"), f"Failed to add item: {e}")

        ttk.Button(dialog, text=_t("common.save", default="Save"), command=save_item).grid(row=6, column=0, columnspan=2, pady=20)

    def edit_menu_item(self):
        """Modify existing menu item"""
        selection = self.menu_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning", default="Warning"), _t("bar.messages.select_to_edit", default="Please select an item to edit"))
            return

        values = self.menu_tree.item(selection[0])['values']
        item_id = values[0]

        dialog = tk.Toplevel(self.bar_window)
        dialog.title(_t("bar.menu.edit_item"))
        dialog.geometry("400x350")
        dialog.transient(self.bar_window)
        dialog.grab_set()

        # Get current item data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE product_id = ? AND source_type = 'bar'", (item_id,))
        item = cursor.fetchone()
        conn.close()

        if not item:
            messagebox.showerror(_t("common.error", default="Error"), _t("bar.messages.item_not_found", default="Item not found"))
            dialog.destroy()
            return

        # Form fields
        ttk.Label(dialog, text=_t("bar.menu.name", default="Name:")).grid(row=0, column=0, padx=10, pady=5, sticky='e')
        name_entry = ttk.Entry(dialog, width=30)
        name_entry.insert(0, item[1])
        name_entry.grid(row=0, column=1, padx=10, pady=5)

        ttk.Label(dialog, text=_t("bar.menu.category", default="Category:")).grid(row=1, column=0, padx=10, pady=5, sticky='e')
        category_combo = ttk.Combobox(dialog, values=self.categories, width=27)
        category_combo.set(item[2])
        category_combo.grid(row=1, column=1, padx=10, pady=5)

        ttk.Label(dialog, text=_t("bar.menu.description", default="Description:")).grid(row=2, column=0, padx=10, pady=5, sticky='e')
        desc_entry = ttk.Entry(dialog, width=30)
        desc_entry.insert(0, item[3] or '')
        desc_entry.grid(row=2, column=1, padx=10, pady=5)

        ttk.Label(dialog, text=_t("bar.menu.price", default="Price (£):")).grid(row=3, column=0, padx=10, pady=5, sticky='e')
        price_entry = ttk.Entry(dialog, width=30)
        price_entry.insert(0, str(item[4]))
        price_entry.grid(row=3, column=1, padx=10, pady=5)

        ttk.Label(dialog, text=_t("bar.menu.is_alcoholic", default="Alcoholic (18+):")).grid(row=4, column=0, padx=10, pady=5, sticky='e')
        alcoholic_var = tk.BooleanVar(value=bool(item[5]))
        ttk.Checkbutton(dialog, variable=alcoholic_var).grid(row=4, column=1, padx=10, pady=5, sticky='w')

        ttk.Label(dialog, text=_t("bar.menu.available", default="Available:")).grid(row=5, column=0, padx=10, pady=5, sticky='e')
        available_var = tk.BooleanVar(value=bool(item[6]))
        ttk.Checkbutton(dialog, variable=available_var).grid(row=5, column=1, padx=10, pady=5, sticky='w')

        ttk.Label(dialog, text=_t("bar.menu.stock", default="Stock Quantity:")).grid(row=6, column=0, padx=10, pady=5, sticky='e')
        stock_entry = ttk.Entry(dialog, width=30)
        stock_entry.insert(0, str(item[7]))
        stock_entry.grid(row=6, column=1, padx=10, pady=5)

        def save_item():
            name = name_entry.get().strip()
            category = category_combo.get().strip()
            description = desc_entry.get().strip()
            try:
                price = float(price_entry.get())
                stock = int(stock_entry.get())
            except ValueError:
                messagebox.showerror(_t("common.error", default="Error"), _t("bar.messages.invalid_price_stock", default="Invalid price or stock value"))
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE products
                    SET name=?, category=?, description=?, price=?, is_alcoholic=?, is_available=?, stock_quantity=?
                    WHERE product_id=? AND source_type = 'bar'
                ''', (name, category, description, price,
                      1 if alcoholic_var.get() else 0,
                      1 if available_var.get() else 0,
                      stock, item_id))
                conn.commit()
                conn.close()

                if ACTIVITY_LOGGER_AVAILABLE:
                    log_activity('update', 'bar_menu_item', user_id=self.current_user.get('id'),
                               details={'item_id': item_id})

                messagebox.showinfo(_t("common.success", default="Success"), _t("bar.messages.menu_updated", default="Menu updated successfully"))
                dialog.destroy()
                self.load_menu_management()
                self.load_menu_items_for_pos()
            except Exception as e:
                messagebox.showerror(_t("common.error", default="Error"), f"Failed to update item: {e}")

        ttk.Button(dialog, text=_t("common.save", default="Save"), command=save_item).grid(row=7, column=0, columnspan=2, pady=20)

    def delete_menu_item(self):
        """Remove item from menu"""
        selection = self.menu_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning", default="Warning"), _t("bar.messages.select_to_delete", default="Please select an item to delete"))
            return

        values = self.menu_tree.item(selection[0])['values']
        item_id = values[0]
        item_name = values[1]

        if not messagebox.askyesno(_t("common.confirm", default="Confirm"), f"Delete '{item_name}' from menu?"):
            return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM products WHERE product_id = ? AND source_type = 'bar'", (item_id,))
            conn.commit()
            conn.close()

            if ACTIVITY_LOGGER_AVAILABLE:
                log_activity('delete', 'bar_menu_item', user_id=self.current_user.get('id'),
                           details={'item_id': item_id, 'name': item_name})

            messagebox.showinfo(_t("common.success", default="Success"), _t("bar.messages.menu_updated", default="Menu updated successfully"))
            self.load_menu_management()
            self.load_menu_items_for_pos()
        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to delete item: {e}")

    def create_orders_tab(self):
        """Create Orders History tab"""
        orders_frame = ttk.Frame(self.notebook)
        self.notebook.add(orders_frame, text=_t("bar.tabs.orders", default="Order History"))

        orders_frame.columnconfigure(0, weight=1)
        orders_frame.rowconfigure(1, weight=1)

        # Filter frame
        filter_frame = ttk.Frame(orders_frame)
        filter_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=10)

        ttk.Button(filter_frame, text=_t("common.refresh", default="Refresh"), command=self.load_orders).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text=_t("bar.orders.view_details", default="View Details"), command=self.view_order_details).pack(side=tk.LEFT, padx=5)

        # Orders treeview
        columns = ('order_id', 'date', 'customer', 'total', 'payment', 'status')
        self.orders_tree = ttk.Treeview(orders_frame, columns=columns, show='headings', height=20)
        self.orders_tree.heading('order_id', text=_t("bar.orders.order_id", default="Order ID"))
        self.orders_tree.heading('date', text=_t("bar.orders.date", default="Date/Time"))
        self.orders_tree.heading('customer', text=_t("bar.orders.customer", default="Customer"))
        self.orders_tree.heading('total', text=_t("bar.orders.total", default="Total"))
        self.orders_tree.heading('payment', text=_t("bar.pos.payment_method", default="Payment Method:"))
        self.orders_tree.heading('status', text=_t("bar.orders.status", default="Status"))

        self.orders_tree.column('order_id', width=80)
        self.orders_tree.column('date', width=150)
        self.orders_tree.column('customer', width=150)
        self.orders_tree.column('total', width=100)
        self.orders_tree.column('payment', width=120)
        self.orders_tree.column('status', width=100)

        self.orders_tree.grid(row=1, column=0, sticky='nsew', padx=10, pady=(0, 10))

        orders_scroll = ttk.Scrollbar(orders_frame, orient='vertical', command=self.orders_tree.yview)
        orders_scroll.grid(row=1, column=1, sticky='ns')
        self.orders_tree.configure(yscrollcommand=orders_scroll.set)

        self.load_orders()

    def load_orders(self):
        """Load orders from database"""
        for item in self.orders_tree.get_children():
            self.orders_tree.delete(item)

        try:
            conn = get_db_connection()
            if not conn:
                return
            cursor = conn.cursor()
            cursor.execute('''
                SELECT order_id, order_date, customer_name, total_amount, payment_method, order_status
                FROM orders
                WHERE source_type = 'bar'
                ORDER BY order_date DESC
                LIMIT 100
            ''')

            for row in cursor.fetchall():
                self.orders_tree.insert('', 'end', values=(
                    row[0], row[1], row[2], f"£{row[3]:.2f}", row[4], row[5]
                ))
            conn.close()
        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to load orders: {e}")

    def view_order_details(self):
        """View details of selected order"""
        selection = self.orders_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning", default="Warning"), _t("bar.messages.select_to_view", default="Please select an order to view"))
            return

        values = self.orders_tree.item(selection[0])['values']
        order_id = values[0]

        dialog = tk.Toplevel(self.bar_window)
        dialog.title(f"Order #{order_id} Details")
        dialog.geometry("500x400")
        dialog.transient(self.bar_window)

        # Get order items
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT item_name, quantity, unit_price, subtotal
            FROM order_items
            WHERE source_type = 'bar' AND source_order_id = ?
        ''', (order_id,))
        items = cursor.fetchall()
        conn.close()

        # Display items
        text = tk.Text(dialog, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text.insert(tk.END, f"Order #{order_id}\n")
        text.insert(tk.END, f"Date: {values[1]}\n")
        text.insert(tk.END, f"Customer: {values[2]}\n")
        text.insert(tk.END, f"Payment: {values[4]}\n")
        text.insert(tk.END, f"Status: {values[5]}\n\n")
        text.insert(tk.END, "-" * 40 + "\n")
        text.insert(tk.END, f"{'Item':<20} {'Qty':<5} {'Price':<10} {'Subtotal':<10}\n")
        text.insert(tk.END, "-" * 40 + "\n")

        for item in items:
            text.insert(tk.END, f"{item[0]:<20} {item[1]:<5} £{item[2]:<9.2f} £{item[3]:<9.2f}\n")

        text.insert(tk.END, "-" * 40 + "\n")
        text.insert(tk.END, f"{'Total:':<25} {'':<5} {'':<10} {values[3]}\n")
        text.config(state=tk.DISABLED)

        ttk.Button(dialog, text=_t("common.close", default="Close"), command=dialog.destroy).pack(pady=10)

    def create_inventory_tab(self):
        """Create Inventory tab"""
        inv_frame = ttk.Frame(self.notebook)
        self.notebook.add(inv_frame, text=_t("bar.tabs.inventory", default="Inventory"))

        inv_frame.columnconfigure(0, weight=1)
        inv_frame.rowconfigure(1, weight=1)

        # Buttons
        btn_frame = ttk.Frame(inv_frame)
        btn_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=10)

        ttk.Button(btn_frame, text=_t("common.refresh", default="Refresh"), command=self.load_inventory).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("bar.inventory.restock_button", default="Restock Item"), command=self.restock_item).pack(side=tk.LEFT, padx=5)

        # Inventory treeview
        columns = ('id', 'name', 'category', 'stock', 'status')
        self.inv_tree = ttk.Treeview(inv_frame, columns=columns, show='headings', height=20)
        self.inv_tree.heading('id', text='ID')
        self.inv_tree.heading('name', text=_t("bar.menu.name", default="Name:"))
        self.inv_tree.heading('category', text=_t("bar.menu.category", default="Category:"))
        self.inv_tree.heading('stock', text=_t("bar.menu.stock", default="Stock Quantity:"))
        self.inv_tree.heading('status', text=_t("common.status", default="Status"))

        self.inv_tree.column('id', width=50)
        self.inv_tree.column('name', width=200)
        self.inv_tree.column('category', width=120)
        self.inv_tree.column('stock', width=80)
        self.inv_tree.column('status', width=100)

        self.inv_tree.grid(row=1, column=0, sticky='nsew', padx=10, pady=(0, 10))

        inv_scroll = ttk.Scrollbar(inv_frame, orient='vertical', command=self.inv_tree.yview)
        inv_scroll.grid(row=1, column=1, sticky='ns')
        self.inv_tree.configure(yscrollcommand=inv_scroll.set)

        self.load_inventory()

    def load_inventory(self):
        """Load inventory data"""
        for item in self.inv_tree.get_children():
            self.inv_tree.delete(item)

        try:
            conn = get_db_connection()
            if not conn:
                return
            cursor = conn.cursor()
            cursor.execute("SELECT product_id, name, category, stock_quantity FROM products WHERE source_type = 'bar' ORDER BY stock_quantity ASC")

            for row in cursor.fetchall():
                stock = row[3]
                if stock <= 10:
                    status = _t("bar.inventory.status_low", default="Low Stock")
                elif stock <= 30:
                    status = _t("bar.inventory.status_medium", default="Medium")
                else:
                    status = _t("bar.inventory.status_good", default="Good")

                self.inv_tree.insert('', 'end', values=(row[0], row[1], row[2], stock, status))
            conn.close()
        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to load inventory: {e}")

    def restock_item(self):
        """Restock selected inventory item"""
        selection = self.inv_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning", default="Warning"), _t("bar.messages.select_to_restock", default="Please select an item to restock"))
            return

        values = self.inv_tree.item(selection[0])['values']
        item_id = values[0]
        item_name = values[1]
        current_stock = values[3]

        quantity = simpledialog.askinteger(
            _t("bar.inventory.restock_title", default="Restock"),
            _t("bar.inventory.restock_prompt", default="Enter quantity to add to '{item_name}'\\nCurrent stock: {current_stock}", item_name=item_name, current_stock=current_stock),
            parent=self.bar_window,
            minvalue=1,
            maxvalue=1000
        )

        if quantity:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE product_id = ? AND source_type = 'bar'",
                              (quantity, item_id))

                # Log inventory transaction
                cursor.execute('''
                    INSERT INTO transactions (source_type, reference_id, reference_type, quantity_change, transaction_type, notes)
                    VALUES ('bar_inventory', ?, 'item', ?, 'restock', ?)
                ''', (item_id, quantity, f"Restocked by {self.current_user.get('username', 'unknown')}"))

                conn.commit()
                conn.close()

                if ACTIVITY_LOGGER_AVAILABLE:
                    log_activity('restock', 'bar_inventory', user_id=self.current_user.get('id'),
                               details={'item_id': item_id, 'quantity': quantity})

                messagebox.showinfo(_t("common.success", default="Success"), f"Added {quantity} units to {item_name}")
                self.load_inventory()
            except Exception as e:
                messagebox.showerror(_t("common.error", default="Error"), f"Failed to restock: {e}")

    def create_reports_tab(self):
        """Create Reports tab"""
        reports_frame = ttk.Frame(self.notebook)
        self.notebook.add(reports_frame, text=_t("bar.tabs.reports", default="Reports"))

        # Report buttons
        btn_frame = ttk.LabelFrame(reports_frame, text=_t("bar.reports.generate_report", default="Generate Report"), padding="20")
        btn_frame.pack(fill=tk.X, padx=20, pady=20)

        ttk.Button(btn_frame, text=_t("bar.reports.daily_sales", default="Daily Sales Report"),
                   command=lambda: self.generate_report('daily')).pack(side=tk.LEFT, padx=10, pady=10)
        ttk.Button(btn_frame, text=_t("bar.reports.weekly_sales", default="Weekly Sales Report"),
                   command=lambda: self.generate_report('weekly')).pack(side=tk.LEFT, padx=10, pady=10)
        ttk.Button(btn_frame, text=_t("bar.reports.monthly_sales", default="Monthly Sales Report"),
                   command=lambda: self.generate_report('monthly')).pack(side=tk.LEFT, padx=10, pady=10)

        # Email report to admin
        email_frame = ttk.LabelFrame(reports_frame, text=_t("bar.reports.send_to_admin", default="Send Report to Admin"), padding="20")
        email_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(email_frame, text=f"{_t('bar.reports.send_to_admin')} (Daily)",
                   command=lambda: self.send_admin_report('daily')).pack(side=tk.LEFT, padx=10, pady=10)
        ttk.Button(email_frame, text=f"{_t('bar.reports.send_to_admin')} (Weekly)",
                   command=lambda: self.send_admin_report('weekly')).pack(side=tk.LEFT, padx=10, pady=10)

        # Report display
        self.report_text = tk.Text(reports_frame, wrap=tk.WORD, height=20)
        self.report_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def generate_report(self, report_type):
        """Generate and display sales report"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Determine date range
            if report_type == 'daily':
                start_date = datetime.now().replace(hour=0, minute=0, second=0)
                title = "Daily Sales Report"
            elif report_type == 'weekly':
                start_date = datetime.now() - timedelta(days=7)
                title = "Weekly Sales Report"
            else:
                start_date = datetime.now().replace(day=1, hour=0, minute=0, second=0)
                title = "Monthly Sales Report"

            # Get summary
            cursor.execute('''
                SELECT COUNT(*), COALESCE(SUM(total_amount), 0), COALESCE(AVG(total_amount), 0)
                FROM orders
                WHERE source_type = 'bar' AND order_date >= ? AND order_status = 'completed'
            ''', (start_date.strftime('%Y-%m-%d %H:%M:%S'),))

            result = cursor.fetchone()
            order_count = result[0] or 0
            total_revenue = result[1] or 0
            avg_order = result[2] or 0

            # Get top items
            cursor.execute('''
                SELECT item_name, SUM(quantity) as qty, SUM(subtotal) as revenue
                FROM order_items
                WHERE source_type = 'bar' AND source_order_id IN (SELECT order_id FROM orders WHERE source_type = 'bar' AND order_date >= ? AND order_status = 'completed')
                GROUP BY item_name
                ORDER BY qty DESC
                LIMIT 10
            ''', (start_date.strftime('%Y-%m-%d %H:%M:%S'),))

            top_items = cursor.fetchall()

            # Get category breakdown
            cursor.execute('''
                SELECT p.category, SUM(oi.quantity) as qty, SUM(oi.subtotal) as revenue
                FROM order_items oi
                JOIN products p ON oi.product_id = p.product_id AND p.source_type = 'bar'
                WHERE oi.source_type = 'bar' AND oi.source_order_id IN (SELECT order_id FROM orders WHERE source_type = 'bar' AND order_date >= ? AND order_status = 'completed')
                GROUP BY p.category
                ORDER BY revenue DESC
            ''', (start_date.strftime('%Y-%m-%d %H:%M:%S'),))

            categories = cursor.fetchall()
            conn.close()

            # Display report
            self.report_text.config(state=tk.NORMAL)
            self.report_text.delete(1.0, tk.END)

            self.report_text.insert(tk.END, f"{title}\n")
            self.report_text.insert(tk.END, "=" * 50 + "\n\n")
            self.report_text.insert(tk.END, f"Period: {start_date.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}\n\n")

            self.report_text.insert(tk.END, "Summary\n")
            self.report_text.insert(tk.END, "-" * 30 + "\n")
            self.report_text.insert(tk.END, f"Total Orders: {order_count}\n")
            self.report_text.insert(tk.END, f"Total Revenue: £{total_revenue:.2f}\n")
            self.report_text.insert(tk.END, f"Average Order: £{avg_order:.2f}\n\n")

            self.report_text.insert(tk.END, "Top 10 Items\n")
            self.report_text.insert(tk.END, "-" * 30 + "\n")
            for item in top_items:
                self.report_text.insert(tk.END, f"{item[0]}: {item[1]} sold (£{item[2]:.2f})\n")

            self.report_text.insert(tk.END, "\nCategory Breakdown\n")
            self.report_text.insert(tk.END, "-" * 30 + "\n")
            for cat in categories:
                self.report_text.insert(tk.END, f"{cat[0]}: {cat[1]} items (£{cat[2]:.2f})\n")

            self.report_text.insert(tk.END, f"\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.report_text.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to generate report: {e}")

# Module-level function for external access
def open_bar_gui(root, auth):
    """Open the Bar GUI from external modules"""
    bar = BarGUI(root, auth)
    bar.show_bar()
    return bar
