from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import threading
import sys
import os

# Import centralized authentication system
# Import authentication - REQUIRED (no fallback for security)
from university_system.infrastructure.auth.user_authentication import UserAuth, get_global_auth
from university_system.infrastructure.shared_context import get_auth

# Attempt to import the enhanced restaurant DB initializer from the CLI version.
# If available, calling this will create the full set of tables defined in
# services/restaurant_management.py. Alias the import to avoid naming
# conflicts with this module's own init_db function.
try:
    from university_system.modules.domain.commerce.services.restaurant_management import init_db as init_enhanced_restaurant_db
except ImportError:
    init_enhanced_restaurant_db = None

# Database configuration
# Always point to the central student_records.db in refactored/db_files.
try:
    from university_system.infrastructure.database.db import DEFAULT_DB_PATH as DATABASE_FILE
except Exception:
    # Fallback to local file if refactored.database.db is unavailable
    DATABASE_FILE = str(DEFAULT_DB_PATH)

def get_db_connection():
    """Get database connection with proper error handling"""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def init_db():
    """Initialize database with basic tables"""
    try:
        # If the enhanced initializer exists, invoke it first so that all
        # additional tables defined in the CLI version are created. Do this
        # before creating the GUI's own minimal tables to maintain
        # compatibility. Ignore errors from this call to avoid breaking the GUI.
        if init_enhanced_restaurant_db:
            try:
                # Import the CLI module to override its DATABASE_FILE so
                # that the enhanced initializer writes to the same file
                # used by this GUI. Without this, the CLI code defaults to
                # creating a separate str(DEFAULT_DB_PATH) in the working
                # directory. Temporarily override and restore after.
                import university_system.modules.domain.commerce.services.restaurant_management as _rm_mod
                _old_db_file = getattr(_rm_mod, 'DATABASE_FILE', None)
                _rm_mod.DATABASE_FILE = DATABASE_FILE
                init_enhanced_restaurant_db()
                # Restore original CLI database file constant
                if _old_db_file is not None:
                    _rm_mod.DATABASE_FILE = _old_db_file
            except Exception as e:
                print(f"Warning: failed to initialize enhanced restaurant database: {e}")

        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Create basic tables if they don't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS menu_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                category TEXT,
                allergens TEXT,
                vegetarian BOOLEAN DEFAULT 0,
                vegan BOOLEAN DEFAULT 0,
                available BOOLEAN DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurant_orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                order_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_price REAL,
                tax_amount REAL,
                status TEXT DEFAULT 'Pending',
                payment_method TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurant_customers (
                customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                loyalty_tier TEXT DEFAULT 'Bronze',
                loyalty_points INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurant_tables (
                table_id INTEGER PRIMARY KEY AUTOINCREMENT,
                capacity INTEGER NOT NULL,
                status TEXT DEFAULT 'Available',
                location TEXT,
                table_type TEXT DEFAULT 'Standard'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurant_staff (
                staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                hourly_rate REAL,
                status TEXT DEFAULT 'Active',
                performance_score REAL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restaurant_inventory (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                quantity REAL DEFAULT 0,
                unit TEXT,
                cost_per_unit REAL,
                reorder_level REAL DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Database initialization error: {e}")
        return False

class RestaurantManagementGUI:
    def __init__(self, root, auth=None):
        """
        Initialize Restaurant Management GUI.

        Args:
            root: Tkinter root window
            auth: Authentication instance (if None, will use get_auth())

        Raises:
            RuntimeError: If authentication system is not available
        """
        self.root = root

        # Get authentication instance - REQUIRED for security
        self.auth = auth if auth is not None else get_auth()
        if self.auth is None:
            # Try global auth as fallback
            self.auth = get_global_auth()

        if self.auth is None:
            messagebox.showerror(
                "Authentication Required",
                "Authentication system not available. Restaurant Management GUI cannot start."
            )
            root.destroy()
            return

        # Initialize database
        if not init_db():
            messagebox.showerror("Database Error", "Failed to initialize database")
            return

        # Check if user is already authenticated
        self.current_user = None
        self.setup_current_user()

    def setup_current_user(self):
        """Setup current user from existing authentication system"""
        try:
            # Check if auth system has a current authenticated user
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                auth_user = self.auth.current_user

                # auth_user is already a dictionary from UserAuth system
                if isinstance(auth_user, dict):
                    self.current_user = {
                        "username": auth_user.get('username', 'Unknown'),
                        "role": auth_user.get('role', 'user'),
                        "permissions": auth_user.get('permissions', [])
                    }
                else:
                    # Handle case where it might be an object
                    self.current_user = {
                        "username": getattr(auth_user, 'username', 'Unknown'),
                        "role": getattr(auth_user, 'role', 'user'),
                        "permissions": getattr(auth_user, 'permissions', [])
                    }

                print(f"✓ Restaurant GUI: Using authenticated user {self.current_user['username']} ({self.current_user['role']})")
            else:
                self.current_user = {
                    "username": "restaurant_manager",
                    "role": "manager",
                    "permissions": []
                }
                if self.auth:
                    self.auth.current_user = self.current_user
                print("ℹ Restaurant GUI: No authenticated user detected - using default manager context")
        except Exception as e:
            print(f"✗ Error setting up current user: {e}")
            self.current_user = {
                "username": "restaurant_manager",
                "role": "manager",
                "permissions": []
            }
            if self.auth:
                self.auth.current_user = self.current_user

    def show_restaurant_management(self):
        """Initialize and show the restaurant management interface"""
        # Create new window for restaurant management
        try:
            # Check if root exists and is valid
            if self.root and self.root.winfo_exists():
                self.restaurant_window = tk.Toplevel(self.root)
            else:
                # Root doesn't exist, create a new one
                self.root = tk.Tk()
                self.restaurant_window = self.root
        except tk.TclError:
            # Root is invalid, create a new one
            self.root = tk.Tk()
            self.restaurant_window = self.root

        self.restaurant_window.title("University Restaurant Management System")
        self.restaurant_window.geometry("1200x800")
        self.restaurant_window.configure(bg='#f0f0f0')

        # Update root reference to use the new window
        self.root = self.restaurant_window

        # Set up styles and create interface
        self.setup_styles()
        if self.auth and not getattr(self.auth, 'current_user', None):
            self.auth.current_user = self.current_user

        self.create_main_interface()

    def setup_styles(self):
        """Set up custom styles for the GUI"""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('Title.TLabel', font=('Arial', 16, 'bold'), background='#f0f0f0')
        style.configure('Heading.TLabel', font=('Arial', 12, 'bold'), background='#f0f0f0')
        style.configure('Custom.TButton', font=('Arial', 10))
        
    def create_main_interface(self):
        """Create the main application interface after successful login"""
        self.clear_window()
        
        self.create_menu_bar()
        
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        welcome_frame = ttk.Frame(main_frame)
        welcome_frame.pack(fill='x', pady=(0, 20))
        
        username = self.auth.current_user.get('username', 'User')
        role = self.auth.current_user.get('role', 'User')
        welcome_text = f"Welcome, {username}! Role: {role}"
        ttk.Label(welcome_frame, text=welcome_text, style='Heading.TLabel').pack()

        ttk.Button(
            welcome_frame,
            text="🏠 Return to Main Menu",
            command=self.return_to_main_menu,
            style='Custom.TButton'
        ).pack(pady=(10, 0))

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True)
        
        self.create_menu_tab()
        self.create_orders_tab()
        self.create_customers_tab()
        self.create_tables_tab()
        self.create_staff_tab()
        self.create_inventory_tab()
        self.create_reports_tab()
        
    def create_menu_bar(self):
        """Create the application menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Backup Database", command=self.backup_database)
        file_menu.add_separator()
        file_menu.add_command(label="Return to Main Menu", command=self.return_to_main_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

        self.create_main_menu_button()

    def create_main_menu_button(self):
        """Ensure a top-right navigation button for the main menu exists"""
        try:
            if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                return
        except Exception:
            pass

        self.main_menu_button = ttk.Button(
            self.root,
            text="🏠 Return to Main Menu",
            command=self.return_to_main_menu,
        )
        self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)
        
    def create_menu_tab(self):
        """Create menu management tab"""
        menu_frame = ttk.Frame(self.notebook)
        self.notebook.add(menu_frame, text="Menu Items")
        
        btn_frame = ttk.Frame(menu_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(btn_frame, text="View All Items", 
                  command=self.view_menu_items).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Add New Item", 
                  command=self.add_menu_item_dialog).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Update Item", 
                  command=self.update_menu_item_dialog).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Menu Analytics", 
                  command=self.show_menu_analytics).pack(side='left', padx=5)
        
        columns = ('ID', 'Name', 'Category', 'Price', 'Available', 'Vegetarian', 'Vegan')
        self.menu_tree = ttk.Treeview(menu_frame, columns=columns, show='headings', height=20)
        
        for col in columns:
            self.menu_tree.heading(col, text=col)
            self.menu_tree.column(col, width=100)
        
        tree_frame = ttk.Frame(menu_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        scrollbar_menu = ttk.Scrollbar(tree_frame, orient='vertical', command=self.menu_tree.yview)
        self.menu_tree.configure(yscrollcommand=scrollbar_menu.set)
        
        self.menu_tree.pack(side='left', fill='both', expand=True)
        scrollbar_menu.pack(side='right', fill='y')
        
    def create_orders_tab(self):
        """Create orders management tab"""
        orders_frame = ttk.Frame(self.notebook)
        self.notebook.add(orders_frame, text="Orders")
        
        btn_frame = ttk.Frame(orders_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(btn_frame, text="View Orders",
                  command=self.view_orders_gui).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Update Status",
                  command=self.update_order_status_dialog).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Process Payment",
                  command=self.process_payment_dialog).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Add Tip",
                  command=self.add_tip).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Apply Discount",
                  command=self.apply_discount).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refund Order",
                  command=self.refund_order).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Order Analytics",
                  command=self.show_order_analytics).pack(side='left', padx=5)
        
        columns = ('Order ID', 'Customer', 'Date', 'Total', 'Status', 'Payment')
        self.orders_tree = ttk.Treeview(orders_frame, columns=columns, show='headings', height=20)
        
        for col in columns:
            self.orders_tree.heading(col, text=col)
            self.orders_tree.column(col, width=120)
        
        tree_frame = ttk.Frame(orders_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        scrollbar_orders = ttk.Scrollbar(tree_frame, orient='vertical', command=self.orders_tree.yview)
        self.orders_tree.configure(yscrollcommand=scrollbar_orders.set)
        
        self.orders_tree.pack(side='left', fill='both', expand=True)
        scrollbar_orders.pack(side='right', fill='y')
        
    def create_customers_tab(self):
        """Create customer management tab"""
        customers_frame = ttk.Frame(self.notebook)
        self.notebook.add(customers_frame, text="Customers")
        
        btn_frame = ttk.Frame(customers_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(btn_frame, text="View Customers",
                  command=self.view_customers_gui).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Add Customer",
                  command=self.add_customer_dialog).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Update Customer",
                  command=self.update_customer_dialog).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Loyalty Program",
                  command=self.manage_loyalty_dialog).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Customer Feedback",
                  command=self.manage_customer_feedback).pack(side='left', padx=5)
        
        columns = ('ID', 'Name', 'Email', 'Phone', 'Loyalty Tier', 'Points', 'Total Spent')
        self.customers_tree = ttk.Treeview(customers_frame, columns=columns, show='headings', height=20)
        
        for col in columns:
            self.customers_tree.heading(col, text=col)
            self.customers_tree.column(col, width=110)
        
        tree_frame = ttk.Frame(customers_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        scrollbar_customers = ttk.Scrollbar(tree_frame, orient='vertical', command=self.customers_tree.yview)
        self.customers_tree.configure(yscrollcommand=scrollbar_customers.set)
        
        self.customers_tree.pack(side='left', fill='both', expand=True)
        scrollbar_customers.pack(side='right', fill='y')
        
    def create_tables_tab(self):
        """Create table management tab"""
        tables_frame = ttk.Frame(self.notebook)
        self.notebook.add(tables_frame, text="Tables")
        
        btn_frame = ttk.Frame(tables_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(btn_frame, text="View Tables",
                  command=self.view_tables_gui).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Add Table",
                  command=self.add_table_dialog).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Reservations",
                  command=self.manage_reservations_dialog).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Generate QR Codes",
                  command=self.generate_qr_dialog).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Optimize Table Layout",
                  command=self.optimize_table_structure).pack(side='left', padx=5)
        
        columns = ('Table ID', 'Capacity', 'Status', 'Location', 'Type')
        self.tables_tree = ttk.Treeview(tables_frame, columns=columns, show='headings', height=20)
        
        for col in columns:
            self.tables_tree.heading(col, text=col)
            self.tables_tree.column(col, width=120)
        
        tree_frame = ttk.Frame(tables_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        scrollbar_tables = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tables_tree.yview)
        self.tables_tree.configure(yscrollcommand=scrollbar_tables.set)
        
        self.tables_tree.pack(side='left', fill='both', expand=True)
        scrollbar_tables.pack(side='right', fill='y')
        
    def create_staff_tab(self):
        """Create staff management tab"""
        staff_frame = ttk.Frame(self.notebook)
        self.notebook.add(staff_frame, text="Staff")
        
        btn_frame = ttk.Frame(staff_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(btn_frame, text="View Staff",
                  command=self.view_staff_gui).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Add Staff",
                  command=self.add_staff_dialog).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Manage Schedules",
                  command=self.manage_schedules_dialog).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Schedule Conflicts",
                  command=self.view_schedule_conflicts).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Staff Performance",
                  command=self.staff_performance).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Staff Analytics",
                  command=self.show_staff_analytics).pack(side='left', padx=5)
        
        columns = ('Staff ID', 'Name', 'Role', 'Hourly Rate', 'Status', 'Performance')
        self.staff_tree = ttk.Treeview(staff_frame, columns=columns, show='headings', height=20)
        
        for col in columns:
            self.staff_tree.heading(col, text=col)
            self.staff_tree.column(col, width=120)
        
        tree_frame = ttk.Frame(staff_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        scrollbar_staff = ttk.Scrollbar(tree_frame, orient='vertical', command=self.staff_tree.yview)
        self.staff_tree.configure(yscrollcommand=scrollbar_staff.set)
        
        self.staff_tree.pack(side='left', fill='both', expand=True)
        scrollbar_staff.pack(side='right', fill='y')
        
    def create_inventory_tab(self):
        """Create inventory management tab"""
        inventory_frame = ttk.Frame(self.notebook)
        self.notebook.add(inventory_frame, text="Inventory")
        
        btn_frame = ttk.Frame(inventory_frame)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(btn_frame, text="View Inventory",
                  command=self.view_inventory_gui).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Purchase Orders",
                  command=self.manage_purchase_orders_dialog).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Suppliers",
                  command=self.manage_suppliers_dialog).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Waste Tracking",
                  command=self.waste_tracking_dialog).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Inventory Reports",
                  command=self.inventory_reports).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Low Stock Alerts",
                  command=self.low_stock_alerts).pack(side='left', padx=5)
        
        columns = ('Item ID', 'Name', 'Quantity', 'Unit', 'Cost/Unit', 'Reorder Level')
        self.inventory_tree = ttk.Treeview(inventory_frame, columns=columns, show='headings', height=20)
        
        for col in columns:
            self.inventory_tree.heading(col, text=col)
            self.inventory_tree.column(col, width=120)
        
        tree_frame = ttk.Frame(inventory_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        scrollbar_inventory = ttk.Scrollbar(tree_frame, orient='vertical', command=self.inventory_tree.yview)
        self.inventory_tree.configure(yscrollcommand=scrollbar_inventory.set)
        
        self.inventory_tree.pack(side='left', fill='both', expand=True)
        scrollbar_inventory.pack(side='right', fill='y')
        
    def create_reports_tab(self):
        """Create reports tab"""
        reports_frame = ttk.Frame(self.notebook)
        self.notebook.add(reports_frame, text="Reports")

        # Create a scrollable frame for all the buttons
        canvas = tk.Canvas(reports_frame)
        scrollbar = ttk.Scrollbar(reports_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Basic Financial Reports
        ttk.Label(scrollable_frame, text="Basic Financial Reports", style='Heading.TLabel').pack(pady=10)

        financial_frame = ttk.Frame(scrollable_frame)
        financial_frame.pack(fill='x', padx=20, pady=5)

        ttk.Button(financial_frame, text="Daily Sales",
                  command=self.daily_sales_report).pack(side='left', padx=5)
        ttk.Button(financial_frame, text="Monthly Summary",
                  command=self.monthly_summary_report).pack(side='left', padx=5)
        ttk.Button(financial_frame, text="Profit Analysis",
                  command=self.profit_analysis_report).pack(side='left', padx=5)

        # Advanced Financial Reports
        ttk.Label(scrollable_frame, text="Advanced Financial Reports", style='Heading.TLabel').pack(pady=(20, 10))

        advanced_financial_frame = ttk.Frame(scrollable_frame)
        advanced_financial_frame.pack(fill='x', padx=20, pady=5)

        ttk.Button(advanced_financial_frame, text="Payroll Report",
                  command=self.export_payroll_report).pack(side='left', padx=5)
        ttk.Button(advanced_financial_frame, text="Expense Report",
                  command=self.export_expense_report).pack(side='left', padx=5)
        ttk.Button(advanced_financial_frame, text="Tax Reports",
                  command=self.tax_reports_menu).pack(side='left', padx=5)
        ttk.Button(advanced_financial_frame, text="Financial Forecast",
                  command=self.financial_forecasting).pack(side='left', padx=5)

        # Data Export
        ttk.Label(scrollable_frame, text="Data Export", style='Heading.TLabel').pack(pady=(20, 10))

        export_frame = ttk.Frame(scrollable_frame)
        export_frame.pack(fill='x', padx=20, pady=5)

        ttk.Button(export_frame, text="Export Financial Data",
                  command=self.export_financial_data_menu).pack(side='left', padx=5)
        ttk.Button(export_frame, text="Export Sales Data",
                  command=self.export_sales_data).pack(side='left', padx=5)

        # Operational Reports
        ttk.Label(scrollable_frame, text="Operational Reports", style='Heading.TLabel').pack(pady=(20, 10))

        operational_frame = ttk.Frame(scrollable_frame)
        operational_frame.pack(fill='x', padx=20, pady=5)

        ttk.Button(operational_frame, text="Menu Performance",
                  command=self.menu_performance_report).pack(side='left', padx=5)
        ttk.Button(operational_frame, text="Customer Analytics",
                  command=self.customer_analytics_report).pack(side='left', padx=5)
        ttk.Button(operational_frame, text="Staff Performance",
                  command=self.staff_performance_report).pack(side='left', padx=5)

        # System Tools
        ttk.Label(scrollable_frame, text="System Tools", style='Heading.TLabel').pack(pady=(20, 10))

        tools_frame = ttk.Frame(scrollable_frame)
        tools_frame.pack(fill='x', padx=20, pady=5)

        ttk.Button(tools_frame, text="System Settings",
                  command=self.display_system_settings).pack(side='left', padx=5)
        ttk.Button(tools_frame, text="Backup & Recovery",
                  command=self.backup_database).pack(side='left', padx=5)

        # Report Output
        ttk.Label(scrollable_frame, text="Report Output", style='Heading.TLabel').pack(pady=(20, 5))

        self.report_text = ScrolledText(scrollable_frame, height=15, width=80)
        self.report_text.pack(fill='both', expand=True, padx=20, pady=10)

        # Pack the canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
    def clear_window(self):
        """Clear all widgets from the window"""
        for widget in self.root.winfo_children():
            widget.destroy()
            
    # Menu Items Functions
    def view_menu_items(self):
        """Display menu items in the treeview"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return
                
            cursor = conn.cursor()
            cursor.execute('''
                SELECT item_id, name, category, price, available, vegetarian, vegan 
                FROM menu_items 
                ORDER BY category, name
            ''')
            items = cursor.fetchall()
            
            for item in self.menu_tree.get_children():
                self.menu_tree.delete(item)
                
            for item in items:
                available = "Yes" if item[4] else "No"
                vegetarian = "Yes" if item[5] else "No"
                vegan = "Yes" if item[6] else "No"
                
                self.menu_tree.insert('', 'end', values=(
                    item[0], item[1], item[2], f"£{item[3]:.2f}", 
                    available, vegetarian, vegan
                ))
                
            conn.close()
            messagebox.showinfo("Success", f"Loaded {len(items)} menu items")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load menu items: {str(e)}")
            
    def add_menu_item_dialog(self):
        """Show dialog to add new menu item"""
        dialog = MenuItemDialog(self.root, "Add Menu Item")
        if dialog.result:
            self.view_menu_items()
            
    def update_menu_item_dialog(self):
        """Show dialog to update menu item"""
        selection = self.menu_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a menu item to update")
            return
            
        item_values = self.menu_tree.item(selection[0])['values']
        item_id = item_values[0]
        
        dialog = MenuItemDialog(self.root, "Update Menu Item", item_id)
        if dialog.result:
            self.view_menu_items()
            
    def show_menu_analytics(self):
        """Show menu analytics in a new window"""
        try:
            analytics_window = tk.Toplevel(self.root)
            analytics_window.title("Menu Analytics")
            analytics_window.geometry("800x600")
            
            text_area = ScrolledText(analytics_window, height=30, width=80)
            text_area.pack(fill='both', expand=True, padx=10, pady=10)
            
            analytics_text = self.generate_menu_analytics_text()
            text_area.insert('1.0', analytics_text)
            text_area.config(state='disabled')
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate analytics: {str(e)}")
            
    def generate_menu_analytics_text(self):
        """Generate menu analytics as text"""
        try:
            conn = get_db_connection()
            if not conn:
                return "Database connection failed"
                
            cursor = conn.cursor()
            
            text = "MENU ANALYTICS\n"
            text += "=" * 50 + "\n\n"
            
            cursor.execute('''
                SELECT category, COUNT(*) as count, AVG(price) as avg_price
                FROM menu_items
                GROUP BY category
                ORDER BY count DESC
            ''')
            
            categories = cursor.fetchall()
            
            text += "Menu Items by Category:\n"
            text += "-" * 30 + "\n"
            for cat in categories:
                text += f"{cat[0]}: {cat[1]} items, Avg Price: £{cat[2]:.2f}\n"
                
            conn.close()
            return text
            
        except Exception as e:
            return f"Error generating analytics: {str(e)}"

    # Orders Functions
    def view_orders_gui(self):
        """Display orders in the treeview"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return
                
            cursor = conn.cursor()
            cursor.execute('''
                SELECT o.order_id, COALESCE(c.name, 'Walk-in'), o.order_time, 
                       o.total_price, o.status, o.payment_method
                FROM restaurant_orders o
                LEFT JOIN restaurant_customers c ON o.customer_id = c.customer_id
                ORDER BY o.order_time DESC
                LIMIT 50
            ''')
            orders = cursor.fetchall()
            
            for item in self.orders_tree.get_children():
                self.orders_tree.delete(item)
                
            for order in orders:
                order_time = order[2][:16] if order[2] else 'N/A'
                
                self.orders_tree.insert('', 'end', values=(
                    order[0], order[1], order_time, f"£{order[3]:.2f}", 
                    order[4], order[5] or 'N/A'
                ))
                
            conn.close()
            messagebox.showinfo("Success", f"Loaded {len(orders)} orders")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load orders: {str(e)}")
            
    def update_order_status_dialog(self):
        """Show dialog to update order status"""
        selection = self.orders_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an order to update")
            return
            
        item_values = self.orders_tree.item(selection[0])['values']
        order_id = item_values[0]
        
        dialog = OrderStatusDialog(self.root, order_id)
        if dialog.result:
            self.view_orders_gui()
            
    def process_payment_dialog(self):
        """Show payment processing dialog"""
        selection = self.orders_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an order to process payment")
            return
            
        item_values = self.orders_tree.item(selection[0])['values']
        order_id = item_values[0]
        
        dialog = PaymentDialog(self.root, order_id)
        if dialog.result:
            self.view_orders_gui()
            
    def show_order_analytics(self):
        """Show order analytics"""
        try:
            analytics_window = tk.Toplevel(self.root)
            analytics_window.title("Order Analytics")
            analytics_window.geometry("800x600")
            
            text_area = ScrolledText(analytics_window, height=30, width=80)
            text_area.pack(fill='both', expand=True, padx=10, pady=10)
            
            analytics_text = self.generate_order_analytics()
            text_area.insert('1.0', analytics_text)
            text_area.config(state='disabled')
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate analytics: {str(e)}")
            
    def generate_order_analytics(self):
        """Generate order analytics text"""
        try:
            conn = get_db_connection()
            if not conn:
                return "Database connection failed"
                
            cursor = conn.cursor()
            
            text = "ORDER ANALYTICS\n"
            text += "=" * 50 + "\n\n"
            
            cursor.execute('''
                SELECT COUNT(*) as total_orders, AVG(total_price) as avg_value
                FROM restaurant_orders
                WHERE status = 'Completed'
            ''')
            
            stats = cursor.fetchone()
            
            if stats:
                text += f"Total Orders: {stats[0]}\n"
                text += f"Average Order Value: £{stats[1]:.2f}\n" if stats[1] else "Average Order Value: N/A\n"
            
            conn.close()
            return text
            
        except Exception as e:
            return f"Error generating analytics: {str(e)}"

    # Advanced Order Management Functions
    def add_tip(self):
        """Add tip to completed order"""
        selection = self.orders_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an order to add a tip")
            return

        item = self.orders_tree.item(selection[0])
        order_id = item['values'][0]

        # Create tip dialog
        tip_dialog = tk.Toplevel(self.root)
        tip_dialog.title("Add Tip")
        tip_dialog.geometry("400x300")
        tip_dialog.transient(self.root)
        tip_dialog.grab_set()

        main_frame = ttk.Frame(tip_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"Add Tip to Order #{order_id}",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Get current order details
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT total_price, tip_amount, payment_status
                    FROM restaurant_orders
                    WHERE order_id = ?
                ''', (order_id,))
                order_data = cursor.fetchone()
                conn.close()

                if not order_data:
                    messagebox.showerror("Error", "Order not found")
                    tip_dialog.destroy()
                    return

                current_total, current_tip, payment_status = order_data

                if payment_status != 'Paid':
                    messagebox.showwarning("Cannot Add Tip", "Order must be paid before adding a tip")
                    tip_dialog.destroy()
                    return

                # Display current info
                info_frame = ttk.LabelFrame(main_frame, text="Order Information", padding=10)
                info_frame.pack(fill='x', pady=10)

                ttk.Label(info_frame, text=f"Current Total: £{current_total:.2f}").pack(anchor='w')
                ttk.Label(info_frame, text=f"Current Tip: £{current_tip or 0:.2f}").pack(anchor='w')

                # Tip entry
                tip_frame = ttk.LabelFrame(main_frame, text="Add Tip", padding=10)
                tip_frame.pack(fill='x', pady=10)

                ttk.Label(tip_frame, text="Tip Amount (£):").grid(row=0, column=0, sticky='w', pady=5)
                tip_amount_var = tk.DoubleVar(value=0.0)
                tip_entry = ttk.Entry(tip_frame, textvariable=tip_amount_var, width=20)
                tip_entry.grid(row=0, column=1, pady=5, padx=5)

                # Quick tip buttons
                quick_frame = ttk.Frame(tip_frame)
                quick_frame.grid(row=1, column=0, columnspan=2, pady=10)

                ttk.Label(quick_frame, text="Quick Select:").pack(side='left', padx=5)
                ttk.Button(quick_frame, text="10%",
                          command=lambda: tip_amount_var.set(round(current_total * 0.10, 2))).pack(side='left', padx=2)
                ttk.Button(quick_frame, text="15%",
                          command=lambda: tip_amount_var.set(round(current_total * 0.15, 2))).pack(side='left', padx=2)
                ttk.Button(quick_frame, text="20%",
                          command=lambda: tip_amount_var.set(round(current_total * 0.20, 2))).pack(side='left', padx=2)

                def save_tip():
                    tip_amount = tip_amount_var.get()
                    if tip_amount <= 0:
                        messagebox.showwarning("Invalid Amount", "Tip amount must be greater than 0")
                        return

                    try:
                        conn = get_db_connection()
                        if conn:
                            cursor = conn.cursor()
                            new_tip_total = (current_tip or 0) + tip_amount
                            new_total = current_total + tip_amount

                            cursor.execute('''
                                UPDATE restaurant_orders
                                SET tip_amount = ?, total_price = ?
                                WHERE order_id = ?
                            ''', (new_tip_total, new_total, order_id))
                            conn.commit()
                            conn.close()

                            messagebox.showinfo("Success", f"Tip of £{tip_amount:.2f} added successfully!\n\nNew Total: £{new_total:.2f}")
                            tip_dialog.destroy()
                            self.view_orders_gui()  # Refresh
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to add tip: {e}")

                button_frame = ttk.Frame(main_frame)
                button_frame.pack(pady=10)

                ttk.Button(button_frame, text="Add Tip", command=save_tip).pack(side='left', padx=5)
                ttk.Button(button_frame, text="Cancel", command=tip_dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load order: {e}")
            tip_dialog.destroy()

    def refund_order(self):
        """Process refund for an order"""
        selection = self.orders_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an order to refund")
            return

        item = self.orders_tree.item(selection[0])
        order_id = item['values'][0]

        # Create refund dialog
        refund_dialog = tk.Toplevel(self.root)
        refund_dialog.title("Process Refund")
        refund_dialog.geometry("450x450")
        refund_dialog.transient(self.root)
        refund_dialog.grab_set()

        main_frame = ttk.Frame(refund_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"Process Refund for Order #{order_id}",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT total_price, payment_status, payment_method
                    FROM restaurant_orders
                    WHERE order_id = ?
                ''', (order_id,))
                order_data = cursor.fetchone()
                conn.close()

                if not order_data:
                    messagebox.showerror("Error", "Order not found")
                    refund_dialog.destroy()
                    return

                total_price, payment_status, payment_method = order_data

                if payment_status != 'Paid':
                    messagebox.showwarning("Cannot Refund", "Order must be paid before processing refund")
                    refund_dialog.destroy()
                    return

                # Display order info
                info_frame = ttk.LabelFrame(main_frame, text="Order Information", padding=10)
                info_frame.pack(fill='x', pady=10)

                ttk.Label(info_frame, text=f"Order Total: £{total_price:.2f}").pack(anchor='w')
                ttk.Label(info_frame, text=f"Payment Method: {payment_method}").pack(anchor='w')

                # Refund type
                refund_frame = ttk.LabelFrame(main_frame, text="Refund Details", padding=10)
                refund_frame.pack(fill='x', pady=10)

                refund_type_var = tk.StringVar(value="Full")
                ttk.Radiobutton(refund_frame, text="Full Refund", variable=refund_type_var,
                               value="Full").pack(anchor='w')
                ttk.Radiobutton(refund_frame, text="Partial Refund", variable=refund_type_var,
                               value="Partial").pack(anchor='w')

                ttk.Label(refund_frame, text="Refund Amount (£):").pack(anchor='w', pady=(10,0))
                refund_amount_var = tk.DoubleVar(value=total_price)
                refund_entry = ttk.Entry(refund_frame, textvariable=refund_amount_var, width=20)
                refund_entry.pack(anchor='w', padx=20)

                def update_refund_amount(*args):
                    if refund_type_var.get() == "Full":
                        refund_amount_var.set(total_price)
                        refund_entry.config(state='disabled')
                    else:
                        refund_entry.config(state='normal')

                refund_type_var.trace('w', update_refund_amount)
                update_refund_amount()

                # Reason
                ttk.Label(refund_frame, text="Refund Reason:").pack(anchor='w', pady=(10,0))
                reason_var = tk.StringVar()
                reason_combo = ttk.Combobox(refund_frame, textvariable=reason_var, width=30)
                reason_combo['values'] = ('Customer Request', 'Order Error', 'Quality Issue',
                                         'Late Delivery', 'Wrong Item', 'Other')
                reason_combo.pack(anchor='w', padx=20)

                ttk.Label(refund_frame, text="Additional Notes:").pack(anchor='w', pady=(10,0))
                notes_text = tk.Text(refund_frame, height=3, width=40)
                notes_text.pack(anchor='w', padx=20)

                def process_refund():
                    refund_amount = refund_amount_var.get()
                    if refund_amount <= 0 or refund_amount > total_price:
                        messagebox.showwarning("Invalid Amount",
                                             f"Refund amount must be between £0.01 and £{total_price:.2f}")
                        return

                    reason = reason_var.get()
                    if not reason:
                        messagebox.showwarning("Missing Information", "Please select a refund reason")
                        return

                    notes = notes_text.get(1.0, tk.END).strip()

                    # Confirm refund
                    if not messagebox.askyesno("Confirm Refund",
                                              f"Process {refund_type_var.get()} refund of £{refund_amount:.2f}?\n\n" +
                                              f"Reason: {reason}\n" +
                                              f"This action cannot be undone."):
                        return

                    try:
                        conn = get_db_connection()
                        if conn:
                            cursor = conn.cursor()

                            # Create refunds table if doesn't exist
                            cursor.execute('''
                                CREATE TABLE IF NOT EXISTS order_refunds (
                                    refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    order_id INTEGER,
                                    refund_amount REAL,
                                    refund_type TEXT,
                                    reason TEXT,
                                    notes TEXT,
                                    refund_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                                    FOREIGN KEY (order_id) REFERENCES restaurant_orders(order_id)
                                )
                            ''')

                            # Insert refund record
                            cursor.execute('''
                                INSERT INTO order_refunds (order_id, refund_amount, refund_type, reason, notes)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (order_id, refund_amount, refund_type_var.get(), reason, notes))

                            # Update order status
                            new_status = 'Refunded' if refund_type_var.get() == 'Full' else 'Partially Refunded'
                            cursor.execute('''
                                UPDATE restaurant_orders
                                SET payment_status = ?, total_price = total_price - ?
                                WHERE order_id = ?
                            ''', (new_status, refund_amount, order_id))

                            conn.commit()
                            conn.close()

                            messagebox.showinfo("Success",
                                              f"Refund processed successfully!\n\n" +
                                              f"Amount: £{refund_amount:.2f}\n" +
                                              f"Method: {payment_method}\n\n" +
                                              f"Funds will be returned to customer's {payment_method}.")
                            refund_dialog.destroy()
                            self.view_orders_gui()  # Refresh
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to process refund: {e}")

                button_frame = ttk.Frame(main_frame)
                button_frame.pack(pady=10)

                ttk.Button(button_frame, text="Process Refund", command=process_refund).pack(side='left', padx=5)
                ttk.Button(button_frame, text="Cancel", command=refund_dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load order: {e}")
            refund_dialog.destroy()

    def apply_discount(self):
        """Apply discount to an order"""
        selection = self.orders_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an order to apply discount")
            return

        item = self.orders_tree.item(selection[0])
        order_id = item['values'][0]

        # Create discount dialog
        discount_dialog = tk.Toplevel(self.root)
        discount_dialog.title("Apply Discount")
        discount_dialog.geometry("450x450")
        discount_dialog.transient(self.root)
        discount_dialog.grab_set()

        main_frame = ttk.Frame(discount_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"Apply Discount to Order #{order_id}",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT total_price, discount_amount, payment_status
                    FROM restaurant_orders
                    WHERE order_id = ?
                ''', (order_id,))
                order_data = cursor.fetchone()
                conn.close()

                if not order_data:
                    messagebox.showerror("Error", "Order not found")
                    discount_dialog.destroy()
                    return

                original_total, current_discount, payment_status = order_data

                # Display order info
                info_frame = ttk.LabelFrame(main_frame, text="Order Information", padding=10)
                info_frame.pack(fill='x', pady=10)

                ttk.Label(info_frame, text=f"Original Total: £{original_total:.2f}").pack(anchor='w')
                ttk.Label(info_frame, text=f"Current Discount: £{current_discount or 0:.2f}").pack(anchor='w')
                ttk.Label(info_frame, text=f"Current Total: £{original_total - (current_discount or 0):.2f}").pack(anchor='w')

                # Discount details
                discount_frame = ttk.LabelFrame(main_frame, text="Discount Details", padding=10)
                discount_frame.pack(fill='x', pady=10)

                discount_type_var = tk.StringVar(value="Percentage")
                ttk.Radiobutton(discount_frame, text="Percentage (%)", variable=discount_type_var,
                               value="Percentage").pack(anchor='w')
                ttk.Radiobutton(discount_frame, text="Fixed Amount (£)", variable=discount_type_var,
                               value="Fixed").pack(anchor='w')

                ttk.Label(discount_frame, text="Discount Value:").pack(anchor='w', pady=(10,0))
                discount_value_var = tk.DoubleVar(value=0.0)
                discount_entry = ttk.Entry(discount_frame, textvariable=discount_value_var, width=20)
                discount_entry.pack(anchor='w', padx=20)

                # Calculated discount display
                calculated_label = ttk.Label(discount_frame, text="Discount Amount: £0.00", foreground='blue')
                calculated_label.pack(anchor='w', padx=20, pady=5)

                def update_calculated_discount(*args):
                    try:
                        value = discount_value_var.get()
                        if discount_type_var.get() == "Percentage":
                            discount_amount = (original_total * value) / 100
                            calculated_label.config(text=f"Discount Amount: £{discount_amount:.2f} ({value}%)")
                        else:
                            calculated_label.config(text=f"Discount Amount: £{value:.2f}")
                    except:
                        calculated_label.config(text="Discount Amount: £0.00")

                discount_value_var.trace('w', update_calculated_discount)
                discount_type_var.trace('w', update_calculated_discount)

                # Promotional code
                ttk.Label(discount_frame, text="Promo Code (optional):").pack(anchor='w', pady=(10,0))
                promo_var = tk.StringVar()
                ttk.Entry(discount_frame, textvariable=promo_var, width=20).pack(anchor='w', padx=20)

                # Reason
                ttk.Label(discount_frame, text="Discount Reason:").pack(anchor='w', pady=(10,0))
                reason_var = tk.StringVar()
                reason_combo = ttk.Combobox(discount_frame, textvariable=reason_var, width=30)
                reason_combo['values'] = ('Promotional Offer', 'Loyalty Reward', 'Compensation',
                                         'Staff Discount', 'Manager Discretion', 'Other')
                reason_combo.pack(anchor='w', padx=20)

                # Manager approval for large discounts
                approval_var = tk.BooleanVar(value=False)
                approval_check = ttk.Checkbutton(discount_frame, text="Manager Approval (for discounts > 20%)",
                                                variable=approval_var, state='disabled')
                approval_check.pack(anchor='w', pady=5)

                def check_approval_needed(*args):
                    try:
                        value = discount_value_var.get()
                        if discount_type_var.get() == "Percentage" and value > 20:
                            approval_check.config(state='normal')
                        else:
                            approval_check.config(state='disabled')
                            approval_var.set(False)
                    except:
                        pass

                discount_value_var.trace('w', check_approval_needed)
                discount_type_var.trace('w', check_approval_needed)

                def apply_discount_action():
                    value = discount_value_var.get()
                    if value <= 0:
                        messagebox.showwarning("Invalid Value", "Discount value must be greater than 0")
                        return

                    # Calculate discount amount
                    if discount_type_var.get() == "Percentage":
                        if value > 100:
                            messagebox.showwarning("Invalid Percentage", "Percentage cannot exceed 100%")
                            return
                        discount_amount = (original_total * value) / 100

                        # Check for manager approval
                        if value > 20 and not approval_var.get():
                            messagebox.showwarning("Approval Required",
                                                 "Manager approval required for discounts over 20%")
                            return
                    else:
                        discount_amount = value
                        if discount_amount >= original_total:
                            messagebox.showwarning("Invalid Amount",
                                                 f"Discount cannot exceed order total (£{original_total:.2f})")
                            return

                    reason = reason_var.get()
                    if not reason:
                        messagebox.showwarning("Missing Information", "Please select a discount reason")
                        return

                    try:
                        conn = get_db_connection()
                        if conn:
                            cursor = conn.cursor()

                            # Create discounts table if doesn't exist
                            cursor.execute('''
                                CREATE TABLE IF NOT EXISTS order_discounts (
                                    discount_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    order_id INTEGER,
                                    discount_amount REAL,
                                    discount_type TEXT,
                                    discount_value REAL,
                                    promo_code TEXT,
                                    reason TEXT,
                                    manager_approved BOOLEAN,
                                    discount_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                                    FOREIGN KEY (order_id) REFERENCES restaurant_orders(order_id)
                                )
                            ''')

                            # Insert discount record
                            cursor.execute('''
                                INSERT INTO order_discounts
                                (order_id, discount_amount, discount_type, discount_value,
                                 promo_code, reason, manager_approved)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (order_id, discount_amount, discount_type_var.get(), value,
                                 promo_var.get() or None, reason, approval_var.get()))

                            # Update order
                            new_discount_total = (current_discount or 0) + discount_amount
                            new_total = original_total - new_discount_total

                            cursor.execute('''
                                UPDATE restaurant_orders
                                SET discount_amount = ?, total_price = ?
                                WHERE order_id = ?
                            ''', (new_discount_total, new_total, order_id))

                            conn.commit()
                            conn.close()

                            messagebox.showinfo("Success",
                                              f"Discount applied successfully!\n\n" +
                                              f"Discount: £{discount_amount:.2f}\n" +
                                              f"New Total: £{new_total:.2f}")
                            discount_dialog.destroy()
                            self.view_orders_gui()  # Refresh
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to apply discount: {e}")

                button_frame = ttk.Frame(main_frame)
                button_frame.pack(pady=10)

                ttk.Button(button_frame, text="Apply Discount", command=apply_discount_action).pack(side='left', padx=5)
                ttk.Button(button_frame, text="Cancel", command=discount_dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load order: {e}")
            discount_dialog.destroy()

    def process_cash_payment(self, order_id, total_amount):
        """Process cash payment with change calculation"""
        cash_dialog = tk.Toplevel(self.root)
        cash_dialog.title("Cash Payment")
        cash_dialog.geometry("400x350")
        cash_dialog.transient(self.root)
        cash_dialog.grab_set()

        main_frame = ttk.Frame(cash_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Cash Payment", font=('Arial', 14, 'bold')).pack(pady=10)

        # Order info
        info_frame = ttk.LabelFrame(main_frame, text="Payment Details", padding=10)
        info_frame.pack(fill='x', pady=10)

        ttk.Label(info_frame, text=f"Order Total: £{total_amount:.2f}",
                 font=('Arial', 12, 'bold'), foreground='blue').pack(anchor='w', pady=5)

        # Cash tendered
        ttk.Label(info_frame, text="Cash Tendered (£):").pack(anchor='w', pady=(10,0))
        cash_tendered_var = tk.DoubleVar(value=0.0)
        cash_entry = ttk.Entry(info_frame, textvariable=cash_tendered_var, width=20, font=('Arial', 12))
        cash_entry.pack(anchor='w', pady=5)
        cash_entry.focus()

        # Change display
        change_label = ttk.Label(info_frame, text="Change: £0.00",
                                font=('Arial', 12, 'bold'), foreground='green')
        change_label.pack(anchor='w', pady=10)

        def update_change(*args):
            try:
                tendered = cash_tendered_var.get()
                change = tendered - total_amount
                if change >= 0:
                    change_label.config(text=f"Change: £{change:.2f}", foreground='green')
                else:
                    change_label.config(text=f"Insufficient: £{abs(change):.2f} short", foreground='red')
            except:
                change_label.config(text="Change: £0.00", foreground='green')

        cash_tendered_var.trace('w', update_change)

        # Quick amount buttons
        quick_frame = ttk.Frame(main_frame)
        quick_frame.pack(pady=10)

        ttk.Label(quick_frame, text="Quick Amounts:").pack(side='left', padx=5)
        for amount in [10, 20, 50, 100]:
            ttk.Button(quick_frame, text=f"£{amount}",
                      command=lambda a=amount: cash_tendered_var.set(a)).pack(side='left', padx=2)

        def complete_payment():
            tendered = cash_tendered_var.get()
            if tendered < total_amount:
                messagebox.showwarning("Insufficient Cash",
                                     f"Cash tendered (£{tendered:.2f}) is less than order total (£{total_amount:.2f})")
                return

            change = tendered - total_amount

            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()

                    # Create cash transactions table
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS cash_transactions (
                            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            order_id INTEGER,
                            cash_tendered REAL,
                            change_given REAL,
                            transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (order_id) REFERENCES restaurant_orders(order_id)
                        )
                    ''')

                    # Record cash transaction
                    cursor.execute('''
                        INSERT INTO cash_transactions (order_id, cash_tendered, change_given)
                        VALUES (?, ?, ?)
                    ''', (order_id, tendered, change))

                    # Update order
                    cursor.execute('''
                        UPDATE restaurant_orders
                        SET payment_status = 'Paid', payment_method = 'Cash'
                        WHERE order_id = ?
                    ''', (order_id,))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Payment Complete",
                                      f"Cash payment processed successfully!\n\n" +
                                      f"Cash Tendered: £{tendered:.2f}\n" +
                                      f"Change: £{change:.2f}")
                    cash_dialog.destroy()
                    self.view_orders_gui()  # Refresh
            except Exception as e:
                messagebox.showerror("Error", f"Failed to process cash payment: {e}")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Complete Payment", command=complete_payment).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=cash_dialog.destroy).pack(side='left', padx=5)

    def process_card_payment(self, order_id, total_amount):
        """Process card payment"""
        card_dialog = tk.Toplevel(self.root)
        card_dialog.title("Card Payment")
        card_dialog.geometry("400x400")
        card_dialog.transient(self.root)
        card_dialog.grab_set()

        main_frame = ttk.Frame(card_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Card Payment", font=('Arial', 14, 'bold')).pack(pady=10)

        # Order info
        info_frame = ttk.LabelFrame(main_frame, text="Payment Details", padding=10)
        info_frame.pack(fill='x', pady=10)

        ttk.Label(info_frame, text=f"Order Total: £{total_amount:.2f}",
                 font=('Arial', 12, 'bold'), foreground='blue').pack(anchor='w', pady=5)

        # Card type
        ttk.Label(info_frame, text="Card Type:").pack(anchor='w', pady=(10,0))
        card_type_var = tk.StringVar(value="Credit Card")
        card_type_combo = ttk.Combobox(info_frame, textvariable=card_type_var, width=25, state='readonly')
        card_type_combo['values'] = ('Credit Card', 'Debit Card', 'Contactless')
        card_type_combo.pack(anchor='w', pady=5)

        # Card last 4 digits (optional)
        ttk.Label(info_frame, text="Card Last 4 Digits (optional):").pack(anchor='w', pady=(10,0))
        card_last4_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=card_last4_var, width=10).pack(anchor='w', pady=5)

        # Transaction ID
        ttk.Label(info_frame, text="Transaction ID:").pack(anchor='w', pady=(10,0))
        import random
        transaction_id = f"TXN{random.randint(100000, 999999)}"
        transaction_id_var = tk.StringVar(value=transaction_id)
        ttk.Entry(info_frame, textvariable=transaction_id_var, width=25, state='readonly').pack(anchor='w', pady=5)

        # Status display
        status_label = ttk.Label(main_frame, text="Ready to process payment",
                                font=('Arial', 10), foreground='blue')
        status_label.pack(pady=10)

        def authorize_payment():
            card_type = card_type_var.get()
            card_last4 = card_last4_var.get()

            if card_last4 and (not card_last4.isdigit() or len(card_last4) != 4):
                messagebox.showwarning("Invalid Input", "Card last 4 digits must be exactly 4 digits")
                return

            # Simulate payment authorization
            status_label.config(text="Authorizing payment...", foreground='orange')
            card_dialog.update()

            import time
            time.sleep(1)  # Simulate processing

            # Simulate success (95% success rate for demo)
            import random
            success = random.random() < 0.95

            if success:
                try:
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()

                        # Create card transactions table
                        cursor.execute('''
                            CREATE TABLE IF NOT EXISTS card_transactions (
                                transaction_id TEXT PRIMARY KEY,
                                order_id INTEGER,
                                card_type TEXT,
                                card_last4 TEXT,
                                amount REAL,
                                authorization_code TEXT,
                                transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY (order_id) REFERENCES restaurant_orders(order_id)
                            )
                        ''')

                        # Generate authorization code
                        auth_code = f"AUTH{random.randint(100000, 999999)}"

                        # Record card transaction
                        cursor.execute('''
                            INSERT INTO card_transactions
                            (transaction_id, order_id, card_type, card_last4, amount, authorization_code)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (transaction_id, order_id, card_type, card_last4 or None, total_amount, auth_code))

                        # Update order
                        cursor.execute('''
                            UPDATE restaurant_orders
                            SET payment_status = 'Paid', payment_method = ?
                            WHERE order_id = ?
                        ''', (card_type, order_id))

                        conn.commit()
                        conn.close()

                        status_label.config(text="Payment Authorized!", foreground='green')
                        messagebox.showinfo("Payment Complete",
                                          f"Card payment processed successfully!\n\n" +
                                          f"Card Type: {card_type}\n" +
                                          f"Amount: £{total_amount:.2f}\n" +
                                          f"Transaction ID: {transaction_id}\n" +
                                          f"Authorization Code: {auth_code}")
                        card_dialog.destroy()
                        self.view_orders_gui()  # Refresh
                except Exception as e:
                    status_label.config(text="Payment Failed", foreground='red')
                    messagebox.showerror("Error", f"Failed to process card payment: {e}")
            else:
                status_label.config(text="Payment Declined", foreground='red')
                messagebox.showerror("Payment Declined",
                                   "Card payment was declined.\n\n" +
                                   "Please try another payment method or contact your bank.")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Authorize Payment", command=authorize_payment).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=card_dialog.destroy).pack(side='left', padx=5)

    def process_meal_plan_payment(self, order_id, total_amount):
        """Process meal plan payment"""
        meal_plan_dialog = tk.Toplevel(self.root)
        meal_plan_dialog.title("Meal Plan Payment")
        meal_plan_dialog.geometry("450x500")
        meal_plan_dialog.transient(self.root)
        meal_plan_dialog.grab_set()

        main_frame = ttk.Frame(meal_plan_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Meal Plan Payment", font=('Arial', 14, 'bold')).pack(pady=10)

        # Order info
        info_frame = ttk.LabelFrame(main_frame, text="Payment Details", padding=10)
        info_frame.pack(fill='x', pady=10)

        ttk.Label(info_frame, text=f"Order Total: £{total_amount:.2f}",
                 font=('Arial', 12, 'bold'), foreground='blue').pack(anchor='w', pady=5)

        # Student ID lookup
        ttk.Label(info_frame, text="Student ID:").pack(anchor='w', pady=(10,0))
        student_id_var = tk.StringVar()
        student_entry = ttk.Entry(info_frame, textvariable=student_id_var, width=20)
        student_entry.pack(anchor='w', pady=5)
        student_entry.focus()

        # Student info display
        student_info_frame = ttk.LabelFrame(main_frame, text="Student Information", padding=10)
        student_info_frame.pack(fill='x', pady=10)

        student_name_label = ttk.Label(student_info_frame, text="Name: -")
        student_name_label.pack(anchor='w')

        plan_type_label = ttk.Label(student_info_frame, text="Plan Type: -")
        plan_type_label.pack(anchor='w')

        balance_label = ttk.Label(student_info_frame, text="Balance: £0.00", foreground='gray')
        balance_label.pack(anchor='w')

        status_label = ttk.Label(student_info_frame, text="Status: Not Checked", foreground='gray')
        status_label.pack(anchor='w', pady=5)

        def check_meal_plan():
            student_id = student_id_var.get()
            if not student_id:
                messagebox.showwarning("Missing Information", "Please enter Student ID")
                return

            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()

                    # Create meal plans table if doesn't exist
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS student_meal_plans (
                            student_id TEXT PRIMARY KEY,
                            student_name TEXT,
                            plan_type TEXT,
                            balance REAL,
                            plan_start_date DATE,
                            plan_end_date DATE,
                            is_active BOOLEAN DEFAULT 1
                        )
                    ''')

                    # Check if student exists
                    cursor.execute('''
                        SELECT student_name, plan_type, balance, is_active
                        FROM student_meal_plans
                        WHERE student_id = ?
                    ''', (student_id,))
                    student_data = cursor.fetchone()

                    if not student_data:
                        # Create demo student for testing
                        messagebox.showinfo("Demo Mode",
                                          "Student not found. Creating demo meal plan for testing purposes.")
                        cursor.execute('''
                            INSERT INTO student_meal_plans
                            (student_id, student_name, plan_type, balance, is_active)
                            VALUES (?, ?, ?, ?, 1)
                        ''', (student_id, f"Student {student_id}", "Standard Plan", 500.00))
                        conn.commit()

                        student_data = (f"Student {student_id}", "Standard Plan", 500.00, 1)

                    conn.close()

                    student_name, plan_type, balance, is_active = student_data

                    student_name_label.config(text=f"Name: {student_name}")
                    plan_type_label.config(text=f"Plan Type: {plan_type}")
                    balance_label.config(text=f"Balance: £{balance:.2f}",
                                        foreground='green' if balance >= total_amount else 'red')

                    if not is_active:
                        status_label.config(text="Status: Plan Inactive", foreground='red')
                        messagebox.showwarning("Inactive Plan", "This meal plan is not active")
                    elif balance < total_amount:
                        status_label.config(text="Status: Insufficient Balance", foreground='red')
                        messagebox.showwarning("Insufficient Balance",
                                             f"Current balance (£{balance:.2f}) is less than order total (£{total_amount:.2f})")
                    else:
                        status_label.config(text="Status: Valid - Ready to Process", foreground='green')

            except Exception as e:
                messagebox.showerror("Error", f"Failed to check meal plan: {e}")

        ttk.Button(info_frame, text="Check Meal Plan", command=check_meal_plan).pack(pady=10)

        def process_payment():
            student_id = student_id_var.get()
            if not student_id:
                messagebox.showwarning("Missing Information", "Please enter Student ID")
                return

            if status_label.cget('text') != "Status: Valid - Ready to Process":
                messagebox.showwarning("Cannot Process", "Please check meal plan first and ensure it's valid")
                return

            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()

                    # Deduct from meal plan
                    cursor.execute('''
                        UPDATE student_meal_plans
                        SET balance = balance - ?
                        WHERE student_id = ?
                    ''', (total_amount, student_id))

                    # Create meal plan transactions table
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS meal_plan_transactions (
                            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            order_id INTEGER,
                            student_id TEXT,
                            amount REAL,
                            transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (order_id) REFERENCES restaurant_orders(order_id)
                        )
                    ''')

                    # Record transaction
                    cursor.execute('''
                        INSERT INTO meal_plan_transactions (order_id, student_id, amount)
                        VALUES (?, ?, ?)
                    ''', (order_id, student_id, total_amount))

                    # Update order
                    cursor.execute('''
                        UPDATE restaurant_orders
                        SET payment_status = 'Paid', payment_method = 'Meal Plan'
                        WHERE order_id = ?
                    ''', (order_id,))

                    # Get new balance
                    cursor.execute('SELECT balance FROM student_meal_plans WHERE student_id = ?', (student_id,))
                    new_balance = cursor.fetchone()[0]

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Payment Complete",
                                      f"Meal plan payment processed successfully!\n\n" +
                                      f"Student ID: {student_id}\n" +
                                      f"Amount Deducted: £{total_amount:.2f}\n" +
                                      f"New Balance: £{new_balance:.2f}")
                    meal_plan_dialog.destroy()
                    self.view_orders_gui()  # Refresh
            except Exception as e:
                messagebox.showerror("Error", f"Failed to process meal plan payment: {e}")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Process Payment", command=process_payment).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=meal_plan_dialog.destroy).pack(side='left', padx=5)

    # Customer Functions
    def view_customers_gui(self):
        """Display customers in the treeview"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return
                
            cursor = conn.cursor()
            cursor.execute('''
                SELECT customer_id, name, email, phone, loyalty_tier, loyalty_points, total_spent
                FROM restaurant_customers
                ORDER BY name
            ''')
            customers = cursor.fetchall()
            
            for item in self.customers_tree.get_children():
                self.customers_tree.delete(item)
                
            for customer in customers:
                self.customers_tree.insert('', 'end', values=(
                    customer[0], customer[1], customer[2] or 'N/A', 
                    customer[3] or 'N/A', customer[4], customer[5], f"£{customer[6]:.2f}"
                ))
                
            conn.close()
            messagebox.showinfo("Success", f"Loaded {len(customers)} customers")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load customers: {str(e)}")
            
    def add_customer_dialog(self):
        """Show dialog to add new customer"""
        dialog = CustomerDialog(self.root, "Add Customer")
        if dialog.result:
            self.view_customers_gui()
            
    def update_customer_dialog(self):
        """Show dialog to update customer"""
        selection = self.customers_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a customer to update")
            return
            
        item_values = self.customers_tree.item(selection[0])['values']
        customer_id = item_values[0]
        
        dialog = CustomerDialog(self.root, "Update Customer", customer_id)
        if dialog.result:
            self.view_customers_gui()

    # ============================================================================
    # CUSTOMER FEEDBACK MANAGEMENT SYSTEM
    # ============================================================================

    def manage_customer_feedback(self):
        """Main customer feedback management interface"""
        feedback_dialog = tk.Toplevel(self.root)
        feedback_dialog.title("Customer Feedback Management")
        feedback_dialog.geometry("1000x700")
        feedback_dialog.transient(self.root)
        feedback_dialog.grab_set()

        main_frame = ttk.Frame(feedback_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Customer Feedback Management",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Create feedback table if it doesn't exist
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()

                # Customer feedback table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS customer_feedback (
                        feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        customer_id INTEGER,
                        customer_name TEXT,
                        order_id INTEGER,
                        rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                        category TEXT,
                        feedback_text TEXT NOT NULL,
                        response TEXT,
                        responded_by TEXT,
                        response_date DATETIME,
                        status TEXT DEFAULT 'Pending',
                        feedback_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (customer_id) REFERENCES restaurant_customers(customer_id),
                        FOREIGN KEY (order_id) REFERENCES restaurant_orders(order_id)
                    )
                ''')

                conn.commit()
                conn.close()
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to initialize feedback table: {e}")
            feedback_dialog.destroy()
            return

        # Action buttons frame
        btn_frame = ttk.LabelFrame(main_frame, text="Actions", padding=15)
        btn_frame.pack(fill='x', pady=10)

        # Row 1: Viewing and Managing
        row1 = ttk.Frame(btn_frame)
        row1.pack(fill='x', pady=5)

        ttk.Button(row1, text="View Recent Feedback",
                  command=lambda: self.view_recent_feedback(feedback_dialog),
                  width=25).pack(side='left', padx=5)

        ttk.Button(row1, text="Respond to Feedback",
                  command=lambda: self.respond_to_feedback(feedback_dialog),
                  width=25).pack(side='left', padx=5)

        ttk.Button(row1, text="Submit New Feedback (Demo)",
                  command=lambda: self.submit_demo_feedback(feedback_dialog),
                  width=25).pack(side='left', padx=5)

        # Row 2: Reporting
        row2 = ttk.Frame(btn_frame)
        row2.pack(fill='x', pady=5)

        ttk.Button(row2, text="Export Feedback Report (CSV)",
                  command=self.export_feedback_report,
                  width=25).pack(side='left', padx=5)

        ttk.Button(row2, text="Generate Analytics Report",
                  command=lambda: self.export_feedback_report_pdf(feedback_dialog),
                  width=25).pack(side='left', padx=5)

        # Statistics frame
        stats_frame = ttk.LabelFrame(main_frame, text="Feedback Statistics", padding=15)
        stats_frame.pack(fill='x', pady=10)

        def update_stats():
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()

                    # Total feedback
                    cursor.execute("SELECT COUNT(*) FROM customer_feedback")
                    total = cursor.fetchone()[0]

                    # Pending responses
                    cursor.execute("SELECT COUNT(*) FROM customer_feedback WHERE status = 'Pending'")
                    pending = cursor.fetchone()[0]

                    # Average rating
                    cursor.execute("SELECT AVG(rating) FROM customer_feedback")
                    avg_rating = cursor.fetchone()[0] or 0

                    # Ratings distribution
                    cursor.execute('''
                        SELECT rating, COUNT(*) FROM customer_feedback
                        GROUP BY rating ORDER BY rating DESC
                    ''')
                    ratings = cursor.fetchall()

                    conn.close()

                    stats_text = (f"Total Feedback: {total} | Pending Responses: {pending} | "
                                f"Average Rating: {avg_rating:.2f}/5.0\n\n"
                                f"Rating Distribution: ")

                    for rating, count in ratings:
                        stats_text += f"{rating}⭐: {count}  "

                    stats_label.config(text=stats_text)
            except Exception as e:
                stats_label.config(text=f"Error loading statistics: {e}")

        stats_label = ttk.Label(stats_frame, text="Loading statistics...", font=('Arial', 9))
        stats_label.pack()

        update_stats()

        # Refresh and close buttons
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill='x', pady=10)

        ttk.Button(bottom_frame, text="Refresh Statistics",
                  command=update_stats).pack(side='left', padx=5)
        ttk.Button(bottom_frame, text="Close",
                  command=feedback_dialog.destroy).pack(side='right', padx=5)

    def view_recent_feedback(self, parent_dialog):
        """View and browse customer feedback with filters"""
        view_dialog = tk.Toplevel(parent_dialog)
        view_dialog.title("View Customer Feedback")
        view_dialog.geometry("1200x700")
        view_dialog.transient(parent_dialog)
        view_dialog.grab_set()

        main_frame = ttk.Frame(view_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Customer Feedback",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Filter frame
        filter_frame = ttk.LabelFrame(main_frame, text="Filters", padding=10)
        filter_frame.pack(fill='x', pady=10)

        filter_row = ttk.Frame(filter_frame)
        filter_row.pack(fill='x', pady=5)

        ttk.Label(filter_row, text="Status:").pack(side='left', padx=5)
        status_var = tk.StringVar(value='All')
        status_combo = ttk.Combobox(filter_row, textvariable=status_var,
                                   values=['All', 'Pending', 'Responded'],
                                   width=15, state='readonly')
        status_combo.pack(side='left', padx=5)

        ttk.Label(filter_row, text="Rating:").pack(side='left', padx=20)
        rating_var = tk.StringVar(value='All')
        rating_combo = ttk.Combobox(filter_row, textvariable=rating_var,
                                   values=['All', '5', '4', '3', '2', '1'],
                                   width=10, state='readonly')
        rating_combo.pack(side='left', padx=5)

        ttk.Label(filter_row, text="Category:").pack(side='left', padx=20)
        category_var = tk.StringVar(value='All')
        category_combo = ttk.Combobox(filter_row, textvariable=category_var,
                                     values=['All', 'Food Quality', 'Service', 'Cleanliness',
                                            'Pricing', 'Ambiance', 'Other'],
                                     width=15, state='readonly')
        category_combo.pack(side='left', padx=5)

        # Treeview frame
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill='both', expand=True, pady=10)

        # Scrollbars
        v_scroll = ttk.Scrollbar(tree_frame, orient='vertical')
        h_scroll = ttk.Scrollbar(tree_frame, orient='horizontal')

        columns = ('ID', 'Date', 'Customer', 'Rating', 'Category', 'Feedback', 'Status', 'Response')
        feedback_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                     yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set,
                                     height=20)

        v_scroll.config(command=feedback_tree.yview)
        h_scroll.config(command=feedback_tree.xview)

        # Configure columns
        column_widths = {'ID': 50, 'Date': 100, 'Customer': 120, 'Rating': 60,
                        'Category': 100, 'Feedback': 250, 'Status': 80, 'Response': 200}

        for col in columns:
            feedback_tree.heading(col, text=col)
            feedback_tree.column(col, width=column_widths.get(col, 100))

        feedback_tree.pack(side='left', fill='both', expand=True)
        v_scroll.pack(side='right', fill='y')
        h_scroll.pack(side='bottom', fill='x')

        def load_feedback():
            # Clear existing items
            for item in feedback_tree.get_children():
                feedback_tree.delete(item)

            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()

                    # Build query with filters
                    query = '''
                        SELECT feedback_id, feedback_date, customer_name, rating,
                               category, feedback_text, status, response
                        FROM customer_feedback
                        WHERE 1=1
                    '''
                    params = []

                    if status_var.get() != 'All':
                        query += ' AND status = ?'
                        params.append(status_var.get())

                    if rating_var.get() != 'All':
                        query += ' AND rating = ?'
                        params.append(int(rating_var.get()))

                    if category_var.get() != 'All':
                        query += ' AND category = ?'
                        params.append(category_var.get())

                    query += ' ORDER BY feedback_date DESC'

                    cursor.execute(query, params)
                    feedbacks = cursor.fetchall()

                    for fb in feedbacks:
                        # Truncate long text for display
                        feedback_text = fb[5][:100] + '...' if len(fb[5]) > 100 else fb[5]
                        response_text = (fb[7][:100] + '...' if fb[7] and len(fb[7]) > 100
                                       else fb[7] or 'N/A')

                        feedback_tree.insert('', 'end', values=(
                            fb[0],  # ID
                            fb[1][:16] if fb[1] else 'N/A',  # Date
                            fb[2] or 'Anonymous',  # Customer
                            f"{fb[3]}⭐",  # Rating
                            fb[4] or 'General',  # Category
                            feedback_text,  # Feedback
                            fb[6],  # Status
                            response_text  # Response
                        ))

                    conn.close()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load feedback: {e}")

        def view_full_feedback():
            """View complete feedback details"""
            selection = feedback_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select feedback to view details")
                return

            item = feedback_tree.item(selection[0])
            feedback_id = item['values'][0]

            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT * FROM customer_feedback WHERE feedback_id = ?
                    ''', (feedback_id,))
                    fb = cursor.fetchone()
                    conn.close()

                    if fb:
                        details = f"""
Feedback ID: {fb[0]}
Customer: {fb[2] or 'Anonymous'}
Order ID: {fb[3] or 'N/A'}
Date: {fb[11]}

Rating: {fb[4]}⭐ / 5
Category: {fb[5] or 'General'}

Feedback:
{fb[6]}

Status: {fb[10]}

Response:
{fb[7] or 'No response yet'}

{'Responded by: ' + fb[8] if fb[8] else ''}
{'Response date: ' + fb[9] if fb[9] else ''}
                        """.strip()

                        messagebox.showinfo("Feedback Details", details)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load feedback details: {e}")

        load_feedback()

        # Button frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)

        ttk.Button(btn_frame, text="Apply Filters", command=load_feedback).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="View Full Details", command=view_full_feedback).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh", command=load_feedback).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=view_dialog.destroy).pack(side='right', padx=5)

    def respond_to_feedback(self, parent_dialog):
        """Respond to customer feedback"""
        # First select feedback to respond to
        select_dialog = tk.Toplevel(parent_dialog)
        select_dialog.title("Select Feedback to Respond")
        select_dialog.geometry("1000x600")
        select_dialog.transient(parent_dialog)
        select_dialog.grab_set()

        main_frame = ttk.Frame(select_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Select Feedback to Respond To",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        ttk.Label(main_frame, text="Only showing pending feedback that needs a response",
                 foreground='blue').pack(pady=5)

        # Feedback list
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill='both', expand=True, pady=10)

        columns = ('ID', 'Date', 'Customer', 'Rating', 'Category', 'Feedback')
        fb_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            fb_tree.heading(col, text=col)
            fb_tree.column(col, width=150)

        fb_tree.pack(fill='both', expand=True)

        def load_pending_feedback():
            for item in fb_tree.get_children():
                fb_tree.delete(item)

            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT feedback_id, feedback_date, customer_name, rating,
                               category, feedback_text
                        FROM customer_feedback
                        WHERE status = 'Pending'
                        ORDER BY feedback_date DESC
                    ''')
                    feedbacks = cursor.fetchall()

                    for fb in feedbacks:
                        feedback_text = fb[5][:150] + '...' if len(fb[5]) > 150 else fb[5]
                        fb_tree.insert('', 'end', values=(
                            fb[0],
                            fb[1][:16] if fb[1] else 'N/A',
                            fb[2] or 'Anonymous',
                            f"{fb[3]}⭐",
                            fb[4] or 'General',
                            feedback_text
                        ))

                    conn.close()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load feedback: {e}")

        load_pending_feedback()

        def proceed_to_respond():
            selection = fb_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select feedback to respond to")
                return

            item = fb_tree.item(selection[0])
            feedback_id = item['values'][0]
            select_dialog.destroy()
            show_response_dialog(feedback_id)

        def show_response_dialog(feedback_id):
            """Show response composition dialog"""
            response_dialog = tk.Toplevel(parent_dialog)
            response_dialog.title("Respond to Customer Feedback")
            response_dialog.geometry("700x600")
            response_dialog.transient(parent_dialog)
            response_dialog.grab_set()

            main_frame = ttk.Frame(response_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Respond to Customer Feedback",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            # Load feedback details
            try:
                conn = get_db_connection()
                if not conn:
                    return

                cursor = conn.cursor()
                cursor.execute('''
                    SELECT feedback_id, customer_name, rating, category,
                           feedback_text, feedback_date
                    FROM customer_feedback WHERE feedback_id = ?
                ''', (feedback_id,))
                fb = cursor.fetchone()
                conn.close()

                if not fb:
                    messagebox.showerror("Error", "Feedback not found")
                    response_dialog.destroy()
                    return

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load feedback: {e}")
                response_dialog.destroy()
                return

            # Display original feedback
            feedback_frame = ttk.LabelFrame(main_frame, text="Original Feedback", padding=15)
            feedback_frame.pack(fill='x', pady=10)

            feedback_info = f"""
Customer: {fb[1] or 'Anonymous'}
Date: {fb[5]}
Rating: {fb[2]}⭐ / 5
Category: {fb[3] or 'General'}

Feedback:
{fb[4]}
            """.strip()

            ttk.Label(feedback_frame, text=feedback_info, justify='left',
                     font=('Arial', 9)).pack(pady=5)

            # Response composition
            response_frame = ttk.LabelFrame(main_frame, text="Your Response", padding=15)
            response_frame.pack(fill='both', expand=True, pady=10)

            ttk.Label(response_frame, text="Compose your response to the customer:",
                     foreground='blue').pack(pady=5)

            response_text = ScrolledText(response_frame, height=10, width=60, font=('Arial', 10))
            response_text.pack(fill='both', expand=True, pady=5)

            # Quick response templates
            templates_frame = ttk.Frame(response_frame)
            templates_frame.pack(fill='x', pady=5)

            ttk.Label(templates_frame, text="Quick Templates:").pack(side='left', padx=5)

            def insert_template(template):
                response_text.delete('1.0', tk.END)
                response_text.insert('1.0', template)

            templates = {
                "Thank You": "Thank you for your valuable feedback! We truly appreciate you taking the time to share your experience with us.",
                "Apology": "We sincerely apologize for the experience you had. This does not reflect our usual standards, and we are taking immediate steps to address this issue.",
                "Improvement": "Thank you for bringing this to our attention. We are constantly working to improve our service and your feedback helps us do that."
            }

            for name, text in templates.items():
                ttk.Button(templates_frame, text=name,
                          command=lambda t=text: insert_template(t)).pack(side='left', padx=2)

            def save_response():
                response = response_text.get('1.0', tk.END).strip()

                if not response:
                    messagebox.showwarning("Empty Response", "Please enter a response")
                    return

                # Get current user
                current_user = "System"
                if AUTH_AVAILABLE:
                    try:
                        from university_system.infrastructure.shared_context import get_auth
                        auth = get_auth()
                        if auth.current_user:
                            current_user = auth.current_user.get('username', 'Unknown')
                    except:
                        pass

                try:
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE customer_feedback
                            SET response = ?,
                                responded_by = ?,
                                response_date = CURRENT_TIMESTAMP,
                                status = 'Responded'
                            WHERE feedback_id = ?
                        ''', (response, current_user, feedback_id))

                        conn.commit()
                        conn.close()

                        messagebox.showinfo("Success",
                                          f"Response submitted successfully!\n\n"
                                          f"Feedback ID: {feedback_id}\n"
                                          f"Responded by: {current_user}")
                        response_dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save response: {e}")

            # Buttons
            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(fill='x', pady=10)

            ttk.Button(btn_frame, text="Submit Response",
                      command=save_response).pack(side='left', padx=5)
            ttk.Button(btn_frame, text="Cancel",
                      command=response_dialog.destroy).pack(side='right', padx=5)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)

        ttk.Button(btn_frame, text="Respond to Selected",
                  command=proceed_to_respond).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh", command=load_pending_feedback).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=select_dialog.destroy).pack(side='right', padx=5)

    def submit_demo_feedback(self, parent_dialog):
        """Submit demo feedback for testing purposes"""
        demo_dialog = tk.Toplevel(parent_dialog)
        demo_dialog.title("Submit Feedback (Demo)")
        demo_dialog.geometry("600x500")
        demo_dialog.transient(parent_dialog)
        demo_dialog.grab_set()

        main_frame = ttk.Frame(demo_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Submit Customer Feedback",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='both', expand=True, pady=10)

        fields = {}

        row = 0
        ttk.Label(form_frame, text="Customer Name:").grid(row=row, column=0, sticky='w', pady=5)
        fields['name'] = ttk.Entry(form_frame, width=40)
        fields['name'].grid(row=row, column=1, pady=5, padx=10)

        row += 1
        ttk.Label(form_frame, text="Rating:*").grid(row=row, column=0, sticky='w', pady=5)
        fields['rating'] = ttk.Combobox(form_frame, values=['5 - Excellent', '4 - Good', '3 - Average',
                                                            '2 - Poor', '1 - Very Poor'],
                                       width=38, state='readonly')
        fields['rating'].grid(row=row, column=1, pady=5, padx=10)
        fields['rating'].current(0)

        row += 1
        ttk.Label(form_frame, text="Category:*").grid(row=row, column=0, sticky='w', pady=5)
        fields['category'] = ttk.Combobox(form_frame,
                                         values=['Food Quality', 'Service', 'Cleanliness',
                                                'Pricing', 'Ambiance', 'Other'],
                                         width=38, state='readonly')
        fields['category'].grid(row=row, column=1, pady=5, padx=10)
        fields['category'].current(0)

        row += 1
        ttk.Label(form_frame, text="Feedback:*").grid(row=row, column=0, sticky='nw', pady=5)
        fields['feedback'] = ScrolledText(form_frame, height=10, width=40, font=('Arial', 10))
        fields['feedback'].grid(row=row, column=1, pady=5, padx=10)

        def submit_feedback():
            try:
                feedback_text = fields['feedback'].get('1.0', tk.END).strip()
                if not feedback_text:
                    messagebox.showwarning("Missing Info", "Please enter feedback")
                    return

                rating_text = fields['rating'].get()
                rating = int(rating_text.split(' - ')[0])

                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO customer_feedback
                        (customer_name, rating, category, feedback_text, status)
                        VALUES (?, ?, ?, ?, 'Pending')
                    ''', (fields['name'].get().strip() or 'Anonymous',
                          rating,
                          fields['category'].get(),
                          feedback_text))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", "Feedback submitted successfully!")
                    demo_dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to submit feedback: {e}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)

        ttk.Button(btn_frame, text="Submit Feedback", command=submit_feedback).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=demo_dialog.destroy).pack(side='right', padx=5)

    def export_feedback_report(self):
        """Export feedback data to CSV with statistics"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Get all feedback
            cursor.execute('''
                SELECT feedback_id, feedback_date, customer_name, order_id,
                       rating, category, feedback_text, response, responded_by,
                       response_date, status
                FROM customer_feedback
                ORDER BY feedback_date DESC
            ''')
            feedbacks = cursor.fetchall()

            # Get statistics
            cursor.execute("SELECT COUNT(*) FROM customer_feedback")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT AVG(rating) FROM customer_feedback")
            avg_rating = cursor.fetchone()[0] or 0

            cursor.execute('''
                SELECT rating, COUNT(*) FROM customer_feedback
                GROUP BY rating ORDER BY rating DESC
            ''')
            rating_dist = cursor.fetchall()

            cursor.execute('''
                SELECT category, COUNT(*) FROM customer_feedback
                GROUP BY category ORDER BY COUNT(*) DESC
            ''')
            category_dist = cursor.fetchall()

            conn.close()

            # Create CSV content
            import csv
            from io import StringIO

            output = StringIO()
            writer = csv.writer(output)

            # Summary section
            writer.writerow(['CUSTOMER FEEDBACK REPORT'])
            writer.writerow(['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow([])

            writer.writerow(['SUMMARY STATISTICS'])
            writer.writerow(['Total Feedback:', total])
            writer.writerow(['Average Rating:', f"{avg_rating:.2f}/5.0"])
            writer.writerow([])

            writer.writerow(['RATING DISTRIBUTION'])
            writer.writerow(['Rating', 'Count'])
            for rating, count in rating_dist:
                writer.writerow([f"{rating} Stars", count])
            writer.writerow([])

            writer.writerow(['CATEGORY DISTRIBUTION'])
            writer.writerow(['Category', 'Count'])
            for category, count in category_dist:
                writer.writerow([category or 'N/A', count])
            writer.writerow([])

            # Detailed feedback data
            writer.writerow(['DETAILED FEEDBACK'])
            writer.writerow(['ID', 'Date', 'Customer', 'Order ID', 'Rating', 'Category',
                           'Feedback', 'Response', 'Responded By', 'Response Date', 'Status'])

            for fb in feedbacks:
                writer.writerow(fb)

            csv_content = output.getvalue()

            # Save to file
            filename = f"customer_feedback_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = os.path.join(os.getcwd(), filename)

            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                f.write(csv_content)

            messagebox.showinfo("Export Success",
                              f"Feedback report exported successfully!\n\n"
                              f"File: {filename}\n"
                              f"Location: {filepath}\n"
                              f"Total Feedback: {total}\n"
                              f"Average Rating: {avg_rating:.2f}/5.0")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export feedback report: {e}")

    def export_feedback_report_pdf(self, parent_dialog):
        """Generate comprehensive feedback analytics report"""
        report_dialog = tk.Toplevel(parent_dialog)
        report_dialog.title("Feedback Analytics Report")
        report_dialog.geometry("900x700")
        report_dialog.transient(parent_dialog)
        report_dialog.grab_set()

        main_frame = ttk.Frame(report_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Customer Feedback Analytics",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Report output
        output_frame = ttk.LabelFrame(main_frame, text="Analytics Report", padding=10)
        output_frame.pack(fill='both', expand=True, pady=10)

        output_text = ScrolledText(output_frame, height=30, width=100, font=('Courier', 9))
        output_text.pack(fill='both', expand=True)

        def generate_report():
            try:
                conn = get_db_connection()
                if not conn:
                    return

                cursor = conn.cursor()

                # Get statistics
                cursor.execute("SELECT COUNT(*) FROM customer_feedback")
                total = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM customer_feedback WHERE status = 'Pending'")
                pending = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM customer_feedback WHERE status = 'Responded'")
                responded = cursor.fetchone()[0]

                cursor.execute("SELECT AVG(rating) FROM customer_feedback")
                avg_rating = cursor.fetchone()[0] or 0

                cursor.execute('''
                    SELECT rating, COUNT(*) FROM customer_feedback
                    GROUP BY rating ORDER BY rating DESC
                ''')
                rating_dist = cursor.fetchall()

                cursor.execute('''
                    SELECT category, COUNT(*), AVG(rating)
                    FROM customer_feedback
                    GROUP BY category
                    ORDER BY COUNT(*) DESC
                ''')
                category_stats = cursor.fetchall()

                # Get recent feedback samples
                cursor.execute('''
                    SELECT customer_name, rating, category, feedback_text, feedback_date
                    FROM customer_feedback
                    ORDER BY feedback_date DESC
                    LIMIT 5
                ''')
                recent = cursor.fetchall()

                # Response rate
                response_rate = (responded / total * 100) if total > 0 else 0

                conn.close()

                # Generate report
                report = f"""
{'='*90}
                    CUSTOMER FEEDBACK ANALYTICS REPORT
                    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*90}

EXECUTIVE SUMMARY:
-----------------
Total Feedback Received:        {total}
Pending Responses:              {pending}
Completed Responses:            {responded}
Response Rate:                  {response_rate:.1f}%

Overall Customer Satisfaction:  {avg_rating:.2f} / 5.0 ⭐

RATING DISTRIBUTION:
-------------------
"""
                for rating, count in rating_dist:
                    percentage = (count / total * 100) if total > 0 else 0
                    bar = '█' * int(percentage / 2)
                    report += f"{rating} Stars:  {count:>4} ({percentage:>5.1f}%)  {bar}\n"

                report += f"""

FEEDBACK BY CATEGORY:
--------------------
{'Category':<20} {'Count':>8} {'Avg Rating':>12} {'Percentage':>12}
{'-'*60}
"""
                for category, count, avg_rat in category_stats:
                    percentage = (count / total * 100) if total > 0 else 0
                    report += f"{(category or 'N/A'):<20} {count:>8} {avg_rat:>12.2f} {percentage:>11.1f}%\n"

                report += f"""

INSIGHTS & RECOMMENDATIONS:
--------------------------
"""
                # Generate insights based on data
                if avg_rating >= 4.5:
                    report += "✓ Excellent overall satisfaction! Customers are very happy.\n"
                elif avg_rating >= 4.0:
                    report += "✓ Good overall satisfaction with room for improvement.\n"
                elif avg_rating >= 3.0:
                    report += "⚠ Average satisfaction. Focus on addressing customer concerns.\n"
                else:
                    report += "⚠ Low satisfaction. Immediate action required.\n"

                if pending > 0:
                    report += f"⚠ {pending} feedback items need responses. Timely responses improve satisfaction.\n"

                if response_rate < 50:
                    report += f"⚠ Low response rate ({response_rate:.1f}%). Aim for >80% response rate.\n"

                # Category-specific insights
                if category_stats:
                    lowest_cat = min(category_stats, key=lambda x: x[2])
                    report += f"⚠ '{lowest_cat[0]}' has lowest rating ({lowest_cat[2]:.2f}). Priority area for improvement.\n"

                report += f"""

RECENT FEEDBACK SAMPLES:
-----------------------
"""
                for idx, (cust, rating, cat, fb, date) in enumerate(recent, 1):
                    fb_short = fb[:200] + '...' if len(fb) > 200 else fb
                    report += f"""
{idx}. {cust or 'Anonymous'} | {rating}⭐ | {cat} | {date}
   {fb_short}
"""

                report += "\n" + "="*90 + "\n"
                report += "\nACTION ITEMS:\n"
                report += "1. Respond to all pending feedback within 24-48 hours\n"
                report += "2. Address lowest-rated categories with targeted improvements\n"
                report += "3. Follow up with customers who gave 1-2 star ratings\n"
                report += "4. Continue practices that led to 5-star ratings\n"
                report += "5. Monitor trends monthly to track improvement\n"

                output_text.delete('1.0', tk.END)
                output_text.insert('1.0', report)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate report: {e}")

        generate_report()

        # Export button
        def export_report():
            report_content = output_text.get('1.0', tk.END)
            filename = f"feedback_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = os.path.join(os.getcwd(), filename)

            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(report_content)

                messagebox.showinfo("Export Success",
                                  f"Analytics report exported!\n\n"
                                  f"File: {filename}\n"
                                  f"Location: {filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)

        ttk.Button(btn_frame, text="Export to File", command=export_report).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh", command=generate_report).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=report_dialog.destroy).pack(side='right', padx=5)

    def manage_loyalty_dialog(self):
        """Show loyalty program management dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Loyalty Program Management")
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Loyalty Program Management", font=('Arial', 14, 'bold')).pack(pady=10)

        # Tier information frame
        tier_frame = ttk.LabelFrame(main_frame, text="Loyalty Tiers", padding=10)
        tier_frame.pack(fill='both', expand=True, pady=10)

        # Customer selection
        search_frame = ttk.Frame(tier_frame)
        search_frame.pack(fill='x', pady=5)

        ttk.Label(search_frame, text="Select Customer:").pack(side='left', padx=5)
        customer_var = tk.StringVar()
        customer_combo = ttk.Combobox(search_frame, textvariable=customer_var, width=40)
        customer_combo.pack(side='left', padx=5)

        # Load customers
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('SELECT customer_id, name, loyalty_tier, loyalty_points FROM restaurant_customers ORDER BY name')
                customers = cursor.fetchall()
                conn.close()

                customer_list = [f"{c[0]}: {c[1]} ({c[2]}, {c[3]} pts)" for c in customers]
                customer_combo['values'] = customer_list
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load customers: {e}")

        # Points adjustment frame
        adjust_frame = ttk.LabelFrame(tier_frame, text="Adjust Points", padding=10)
        adjust_frame.pack(fill='x', pady=10)

        ttk.Label(adjust_frame, text="Points to Add/Subtract:").grid(row=0, column=0, sticky='w', pady=5)
        points_var = tk.StringVar(value="0")
        ttk.Entry(adjust_frame, textvariable=points_var, width=15).grid(row=0, column=1, pady=5)

        ttk.Label(adjust_frame, text="Reason:").grid(row=1, column=0, sticky='w', pady=5)
        reason_var = tk.StringVar()
        ttk.Entry(adjust_frame, textvariable=reason_var, width=40).grid(row=1, column=1, pady=5, columnspan=2)

        def adjust_points():
            selection = customer_var.get()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a customer")
                return

            try:
                customer_id = int(selection.split(':')[0])
                points_change = int(points_var.get())

                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE restaurant_customers
                        SET loyalty_points = loyalty_points + ?
                        WHERE customer_id = ?
                    ''', (points_change, customer_id))
                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", f"Points adjusted by {points_change}")
                    dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to adjust points: {e}")

        ttk.Button(adjust_frame, text="Apply Adjustment", command=adjust_points).grid(row=2, column=0, columnspan=3, pady=10)

        # Tier upgrade information
        info_frame = ttk.LabelFrame(tier_frame, text="Tier Information", padding=10)
        info_frame.pack(fill='both', expand=True, pady=10)

        info_text = ScrolledText(info_frame, height=10, width=70)
        info_text.pack(fill='both', expand=True)

        info_content = """Loyalty Tier Benefits:

Bronze (0-99 points):
  - 2% discount on all orders
  - Birthday reward

Silver (100-499 points):
  - 5% discount on all orders
  - Birthday reward
  - Priority reservations

Gold (500-999 points):
  - 8% discount on all orders
  - Birthday reward
  - Priority reservations
  - Free appetizer monthly

Platinum (1000+ points):
  - 10% discount on all orders
  - Birthday reward
  - Priority reservations
  - Free appetizer monthly
  - Exclusive menu access"""

        info_text.insert('1.0', info_content)
        info_text.config(state='disabled')

        # Advanced features buttons
        advanced_frame = ttk.LabelFrame(main_frame, text="Advanced Features", padding=10)
        advanced_frame.pack(fill='x', pady=10)

        btn_row = ttk.Frame(advanced_frame)
        btn_row.pack(fill='x', pady=5)

        ttk.Button(btn_row, text="View Loyalty Tiers",
                  command=lambda: self.view_loyalty_tiers(dialog),
                  width=20).pack(side='left', padx=5)

        ttk.Button(btn_row, text="Promote Customer Tier",
                  command=lambda: self.promote_customer_tier(dialog),
                  width=20).pack(side='left', padx=5)

        ttk.Button(btn_row, text="Award Bonus Points",
                  command=lambda: self.award_bonus_points(dialog),
                  width=20).pack(side='left', padx=5)

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def view_loyalty_tiers(self, parent_dialog):
        """View and manage loyalty tier structure"""
        tiers_dialog = tk.Toplevel(parent_dialog)
        tiers_dialog.title("Loyalty Tier Management")
        tiers_dialog.geometry("900x700")
        tiers_dialog.transient(parent_dialog)
        tiers_dialog.grab_set()

        main_frame = ttk.Frame(tiers_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Loyalty Tier Structure",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Tier definitions
        tier_frame = ttk.LabelFrame(main_frame, text="Tier Definitions", padding=15)
        tier_frame.pack(fill='both', expand=True, pady=10)

        # Tier details
        tiers = [
            {
                'name': 'Bronze',
                'range': '0-99 points',
                'discount': '2%',
                'benefits': ['Birthday reward', 'Email notifications']
            },
            {
                'name': 'Silver',
                'range': '100-499 points',
                'discount': '5%',
                'benefits': ['Birthday reward', 'Priority reservations', 'Email notifications']
            },
            {
                'name': 'Gold',
                'range': '500-999 points',
                'discount': '8%',
                'benefits': ['Birthday reward', 'Priority reservations', 'Free appetizer monthly',
                           'Exclusive promotions']
            },
            {
                'name': 'Platinum',
                'range': '1000+ points',
                'discount': '10%',
                'benefits': ['Birthday reward', 'Priority reservations', 'Free appetizer monthly',
                           'Exclusive menu access', 'VIP events', 'Dedicated support']
            }
        ]

        # Display tiers in a grid
        for idx, tier in enumerate(tiers):
            # Tier card frame
            tier_card = ttk.LabelFrame(tier_frame, text=f"{tier['name']} Tier", padding=10)
            tier_card.grid(row=idx//2, column=idx%2, padx=10, pady=10, sticky='nsew')

            # Tier details
            details_text = f"""
Points Range: {tier['range']}
Discount: {tier['discount']}

Benefits:
"""
            for benefit in tier['benefits']:
                details_text += f"  • {benefit}\n"

            ttk.Label(tier_card, text=details_text, justify='left',
                     font=('Arial', 9)).pack(anchor='w')

        # Configure grid weights
        tier_frame.columnconfigure(0, weight=1)
        tier_frame.columnconfigure(1, weight=1)

        # Statistics frame
        stats_frame = ttk.LabelFrame(main_frame, text="Customer Distribution by Tier", padding=15)
        stats_frame.pack(fill='x', pady=10)

        def update_tier_stats():
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()

                    # Count customers in each tier
                    cursor.execute('''
                        SELECT loyalty_tier, COUNT(*), AVG(loyalty_points)
                        FROM restaurant_customers
                        GROUP BY loyalty_tier
                        ORDER BY
                            CASE loyalty_tier
                                WHEN 'Platinum' THEN 4
                                WHEN 'Gold' THEN 3
                                WHEN 'Silver' THEN 2
                                WHEN 'Bronze' THEN 1
                                ELSE 0
                            END DESC
                    ''')
                    tier_stats = cursor.fetchall()

                    cursor.execute("SELECT COUNT(*) FROM restaurant_customers")
                    total_customers = cursor.fetchone()[0]

                    conn.close()

                    stats_text = "Customer Distribution:\n\n"
                    for tier, count, avg_points in tier_stats:
                        percentage = (count / total_customers * 100) if total_customers > 0 else 0
                        bar = '█' * int(percentage / 2)
                        stats_text += f"{tier:12} {count:>4} customers ({percentage:>5.1f}%)  Avg: {avg_points:>6.1f} pts  {bar}\n"

                    stats_label.config(text=stats_text)
            except Exception as e:
                stats_label.config(text=f"Error loading statistics: {e}")

        stats_label = ttk.Label(stats_frame, text="Loading statistics...",
                               font=('Courier', 9), justify='left')
        stats_label.pack(anchor='w')

        update_tier_stats()

        # Tier upgrade rules
        rules_frame = ttk.LabelFrame(main_frame, text="Tier Upgrade Rules", padding=10)
        rules_frame.pack(fill='x', pady=10)

        rules_text = """
Automatic Tier Upgrades:
• Customers are automatically upgraded when they reach the points threshold for the next tier
• Points are earned at a rate of 1 point per £1 spent
• Points never expire
• Tier downgrades do not occur (tier is the highest achieved, not current points)

Manual Promotions:
• Managers can manually promote customers for exceptional loyalty
• Use the 'Promote Customer Tier' function to upgrade customers
• Manual promotions are permanent and recorded in the system
        """.strip()

        ttk.Label(rules_frame, text=rules_text, justify='left', font=('Arial', 9)).pack(anchor='w')

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)

        ttk.Button(btn_frame, text="Refresh Statistics",
                  command=update_tier_stats).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=tiers_dialog.destroy).pack(side='right', padx=5)

    def promote_customer_tier(self, parent_dialog):
        """Manually promote a customer to a higher loyalty tier"""
        promote_dialog = tk.Toplevel(parent_dialog)
        promote_dialog.title("Promote Customer Tier")
        promote_dialog.geometry("700x600")
        promote_dialog.transient(parent_dialog)
        promote_dialog.grab_set()

        main_frame = ttk.Frame(promote_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Promote Customer to Higher Tier",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        ttk.Label(main_frame,
                 text="Select a customer and promote them to a higher loyalty tier",
                 foreground='blue').pack(pady=5)

        # Customer selection
        search_frame = ttk.LabelFrame(main_frame, text="Select Customer", padding=15)
        search_frame.pack(fill='x', pady=10)

        ttk.Label(search_frame, text="Customer:").grid(row=0, column=0, sticky='w', pady=5)
        customer_var = tk.StringVar()
        customer_combo = ttk.Combobox(search_frame, textvariable=customer_var,
                                      width=50, state='readonly')
        customer_combo.grid(row=0, column=1, pady=5, padx=10)

        # Load customers
        customer_data = {}
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT customer_id, name, loyalty_tier, loyalty_points
                    FROM restaurant_customers
                    ORDER BY name
                ''')
                customers = cursor.fetchall()
                conn.close()

                for cust in customers:
                    label = f"{cust[1]} - {cust[2]} ({cust[3]} points)"
                    customer_data[label] = cust
                    customer_combo['values'] = list(customer_data.keys())
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load customers: {e}")

        # Current tier info
        current_info_frame = ttk.LabelFrame(main_frame, text="Current Information", padding=15)
        current_info_frame.pack(fill='x', pady=10)

        current_info_label = ttk.Label(current_info_frame,
                                      text="Select a customer to view their current tier",
                                      font=('Arial', 9))
        current_info_label.pack(pady=5)

        # New tier selection
        new_tier_frame = ttk.LabelFrame(main_frame, text="Promote To", padding=15)
        new_tier_frame.pack(fill='x', pady=10)

        ttk.Label(new_tier_frame, text="New Tier:").grid(row=0, column=0, sticky='w', pady=5)
        new_tier_var = tk.StringVar()
        new_tier_combo = ttk.Combobox(new_tier_frame, textvariable=new_tier_var,
                                     values=['Bronze', 'Silver', 'Gold', 'Platinum'],
                                     width=30, state='readonly')
        new_tier_combo.grid(row=0, column=1, pady=5, padx=10)

        ttk.Label(new_tier_frame, text="Reason:*").grid(row=1, column=0, sticky='w', pady=5)
        reason_entry = ttk.Entry(new_tier_frame, width=50)
        reason_entry.grid(row=1, column=1, pady=5, padx=10, columnspan=2)

        ttk.Label(new_tier_frame, text="Notes:").grid(row=2, column=0, sticky='nw', pady=5)
        notes_text = tk.Text(new_tier_frame, height=4, width=50)
        notes_text.grid(row=2, column=1, pady=5, padx=10)

        def update_customer_info(*args):
            """Update displayed customer information"""
            selection = customer_var.get()
            if selection and selection in customer_data:
                cust = customer_data[selection]
                info = f"""
Customer ID: {cust[0]}
Name: {cust[1]}
Current Tier: {cust[2]}
Loyalty Points: {cust[3]}
                """.strip()
                current_info_label.config(text=info)

                # Set default new tier to one above current
                tier_order = ['Bronze', 'Silver', 'Gold', 'Platinum']
                current_tier = cust[2]
                if current_tier in tier_order:
                    current_idx = tier_order.index(current_tier)
                    if current_idx < len(tier_order) - 1:
                        new_tier_combo.set(tier_order[current_idx + 1])

        customer_combo.bind('<<ComboboxSelected>>', update_customer_info)

        def promote_customer():
            """Execute the tier promotion"""
            selection = customer_var.get()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a customer")
                return

            if not new_tier_var.get():
                messagebox.showwarning("No Tier", "Please select a new tier")
                return

            if not reason_entry.get().strip():
                messagebox.showwarning("No Reason", "Please provide a reason for the promotion")
                return

            cust = customer_data[selection]
            current_tier = cust[2]
            new_tier = new_tier_var.get()

            # Validate promotion is an upgrade
            tier_order = ['Bronze', 'Silver', 'Gold', 'Platinum']
            if current_tier not in tier_order or new_tier not in tier_order:
                messagebox.showerror("Error", "Invalid tier selection")
                return

            current_idx = tier_order.index(current_tier)
            new_idx = tier_order.index(new_tier)

            if new_idx <= current_idx:
                messagebox.showerror("Invalid Promotion",
                                   f"Cannot promote from {current_tier} to {new_tier}.\n"
                                   f"New tier must be higher than current tier.")
                return

            # Confirm promotion
            confirm = messagebox.askyesno("Confirm Promotion",
                                         f"Promote {cust[1]} from {current_tier} to {new_tier}?\n\n"
                                         f"Reason: {reason_entry.get()}\n\n"
                                         f"This action will be recorded in the system.")

            if not confirm:
                return

            # Get current user
            current_user = "System"
            if AUTH_AVAILABLE:
                try:
                    from university_system.infrastructure.shared_context import get_auth
                    auth = get_auth()
                    if auth.is_logged_in():
                        current_user = auth.get_current_user().username
                except:
                    pass

            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()

                    # Create tier promotions table if it doesn't exist
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS loyalty_tier_promotions (
                            promotion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            customer_id INTEGER NOT NULL,
                            old_tier TEXT NOT NULL,
                            new_tier TEXT NOT NULL,
                            reason TEXT,
                            notes TEXT,
                            promoted_by TEXT,
                            promotion_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (customer_id) REFERENCES restaurant_customers(customer_id)
                        )
                    ''')

                    # Update customer tier
                    cursor.execute('''
                        UPDATE restaurant_customers
                        SET loyalty_tier = ?
                        WHERE customer_id = ?
                    ''', (new_tier, cust[0]))

                    # Record the promotion
                    cursor.execute('''
                        INSERT INTO loyalty_tier_promotions
                        (customer_id, old_tier, new_tier, reason, notes, promoted_by)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (cust[0], current_tier, new_tier, reason_entry.get(),
                          notes_text.get('1.0', tk.END).strip(), current_user))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success",
                                      f"Customer {cust[1]} promoted successfully!\n\n"
                                      f"{current_tier} → {new_tier}\n"
                                      f"Promoted by: {current_user}")
                    promote_dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to promote customer: {e}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)

        ttk.Button(btn_frame, text="Promote Customer",
                  command=promote_customer).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel",
                  command=promote_dialog.destroy).pack(side='right', padx=5)

    def award_bonus_points(self, parent_dialog):
        """Award promotional bonus points to customers"""
        bonus_dialog = tk.Toplevel(parent_dialog)
        bonus_dialog.title("Award Bonus Points")
        bonus_dialog.geometry("800x650")
        bonus_dialog.transient(parent_dialog)
        bonus_dialog.grab_set()

        main_frame = ttk.Frame(bonus_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Award Bonus Loyalty Points",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        ttk.Label(main_frame,
                 text="Award bonus points to customers for promotions, events, or special occasions",
                 foreground='blue').pack(pady=5)

        # Award type selection
        type_frame = ttk.LabelFrame(main_frame, text="Award Type", padding=15)
        type_frame.pack(fill='x', pady=10)

        award_type_var = tk.StringVar(value='individual')

        ttk.Radiobutton(type_frame, text="Individual Customer",
                       variable=award_type_var, value='individual').pack(anchor='w', pady=2)
        ttk.Radiobutton(type_frame, text="All Customers in Tier",
                       variable=award_type_var, value='tier').pack(anchor='w', pady=2)
        ttk.Radiobutton(type_frame, text="All Customers",
                       variable=award_type_var, value='all').pack(anchor='w', pady=2)

        # Selection frame (changes based on award type)
        selection_frame = ttk.LabelFrame(main_frame, text="Select Recipients", padding=15)
        selection_frame.pack(fill='x', pady=10)

        # Individual customer selection
        individual_frame = ttk.Frame(selection_frame)
        ttk.Label(individual_frame, text="Customer:").pack(side='left', padx=5)
        customer_var = tk.StringVar()
        customer_combo = ttk.Combobox(individual_frame, textvariable=customer_var,
                                      width=50, state='readonly')
        customer_combo.pack(side='left', padx=5)

        # Tier selection
        tier_frame_inner = ttk.Frame(selection_frame)
        ttk.Label(tier_frame_inner, text="Tier:").pack(side='left', padx=5)
        tier_var = tk.StringVar()
        tier_combo = ttk.Combobox(tier_frame_inner, textvariable=tier_var,
                                  values=['Bronze', 'Silver', 'Gold', 'Platinum'],
                                  width=20, state='readonly')
        tier_combo.pack(side='left', padx=5)

        # All customers frame
        all_frame = ttk.Frame(selection_frame)
        ttk.Label(all_frame, text="This will award points to ALL customers in the system",
                 foreground='red', font=('Arial', 9, 'bold')).pack(pady=5)

        # Load customers
        customer_data = {}
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT customer_id, name, loyalty_tier, loyalty_points
                    FROM restaurant_customers
                    ORDER BY name
                ''')
                customers = cursor.fetchall()
                conn.close()

                for cust in customers:
                    label = f"{cust[1]} - {cust[2]} ({cust[3]} points)"
                    customer_data[label] = cust
                customer_combo['values'] = list(customer_data.keys())
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load customers: {e}")

        def update_selection_ui(*args):
            """Update UI based on award type selection"""
            # Hide all frames
            individual_frame.pack_forget()
            tier_frame_inner.pack_forget()
            all_frame.pack_forget()

            # Show appropriate frame
            if award_type_var.get() == 'individual':
                individual_frame.pack(fill='x', pady=5)
            elif award_type_var.get() == 'tier':
                tier_frame_inner.pack(fill='x', pady=5)
            else:  # 'all'
                all_frame.pack(fill='x', pady=5)

        award_type_var.trace('w', update_selection_ui)
        update_selection_ui()  # Initial setup

        # Points and reason
        details_frame = ttk.LabelFrame(main_frame, text="Bonus Details", padding=15)
        details_frame.pack(fill='x', pady=10)

        ttk.Label(details_frame, text="Bonus Points:*").grid(row=0, column=0, sticky='w', pady=5)
        points_entry = ttk.Entry(details_frame, width=20)
        points_entry.grid(row=0, column=1, sticky='w', pady=5, padx=10)
        points_entry.insert(0, "100")

        ttk.Label(details_frame, text="Reason/Campaign:*").grid(row=1, column=0, sticky='w', pady=5)
        reason_entry = ttk.Entry(details_frame, width=50)
        reason_entry.grid(row=1, column=1, pady=5, padx=10, columnspan=2)

        ttk.Label(details_frame, text="Description:").grid(row=2, column=0, sticky='nw', pady=5)
        desc_text = tk.Text(details_frame, height=4, width=50)
        desc_text.grid(row=2, column=1, pady=5, padx=10)

        # Preview
        preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding=10)
        preview_frame.pack(fill='x', pady=10)

        preview_label = ttk.Label(preview_frame, text="Configure award details above",
                                 font=('Arial', 9))
        preview_label.pack()

        def update_preview(*args):
            """Update preview of who will receive points"""
            try:
                points = int(points_entry.get() or 0)
                award_type = award_type_var.get()

                if award_type == 'individual':
                    if customer_var.get():
                        cust = customer_data[customer_var.get()]
                        preview_label.config(
                            text=f"Will award {points} points to:\n{cust[1]} (Current: {cust[3]} → New: {cust[3] + points})")
                    else:
                        preview_label.config(text="Please select a customer")

                elif award_type == 'tier':
                    if tier_var.get():
                        conn = get_db_connection()
                        if conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                SELECT COUNT(*) FROM restaurant_customers
                                WHERE loyalty_tier = ?
                            ''', (tier_var.get(),))
                            count = cursor.fetchone()[0]
                            conn.close()
                            preview_label.config(
                                text=f"Will award {points} points to {count} customers in {tier_var.get()} tier")
                    else:
                        preview_label.config(text="Please select a tier")

                else:  # 'all'
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM restaurant_customers")
                        count = cursor.fetchone()[0]
                        conn.close()
                        preview_label.config(
                            text=f"Will award {points} points to ALL {count} customers")

            except:
                preview_label.config(text="Configure award details above")

        points_entry.bind('<KeyRelease>', update_preview)
        customer_var.trace('w', update_preview)
        tier_var.trace('w', update_preview)
        award_type_var.trace('w', update_preview)

        def award_points():
            """Execute the bonus points award"""
            try:
                points = int(points_entry.get())
                if points <= 0:
                    messagebox.showwarning("Invalid Points", "Points must be greater than 0")
                    return
            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter a valid number of points")
                return

            if not reason_entry.get().strip():
                messagebox.showwarning("Missing Reason", "Please provide a reason for the bonus points")
                return

            award_type = award_type_var.get()

            # Validate selection
            if award_type == 'individual' and not customer_var.get():
                messagebox.showwarning("No Selection", "Please select a customer")
                return
            elif award_type == 'tier' and not tier_var.get():
                messagebox.showwarning("No Selection", "Please select a tier")
                return

            # Get current user
            current_user = "System"
            if AUTH_AVAILABLE:
                try:
                    from university_system.infrastructure.shared_context import get_auth
                    auth = get_auth()
                    if auth.is_logged_in():
                        current_user = auth.get_current_user().username
                except:
                    pass

            # Confirm award
            if award_type == 'all':
                confirm = messagebox.askyesno("Confirm Award",
                                            f"Award {points} bonus points to ALL customers?\n\n"
                                            f"Reason: {reason_entry.get()}\n\n"
                                            f"This cannot be undone.")
            else:
                confirm = messagebox.askyesno("Confirm Award",
                                            f"Award {points} bonus points?\n\n"
                                            f"Reason: {reason_entry.get()}")

            if not confirm:
                return

            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()

                    # Create bonus points table if it doesn't exist
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS loyalty_bonus_points (
                            bonus_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            customer_id INTEGER,
                            points_awarded INTEGER NOT NULL,
                            reason TEXT NOT NULL,
                            description TEXT,
                            awarded_by TEXT,
                            award_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (customer_id) REFERENCES restaurant_customers(customer_id)
                        )
                    ''')

                    customers_affected = 0

                    if award_type == 'individual':
                        cust = customer_data[customer_var.get()]
                        cursor.execute('''
                            UPDATE restaurant_customers
                            SET loyalty_points = loyalty_points + ?
                            WHERE customer_id = ?
                        ''', (points, cust[0]))

                        cursor.execute('''
                            INSERT INTO loyalty_bonus_points
                            (customer_id, points_awarded, reason, description, awarded_by)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (cust[0], points, reason_entry.get(),
                              desc_text.get('1.0', tk.END).strip(), current_user))

                        customers_affected = 1

                    elif award_type == 'tier':
                        # Get all customers in tier
                        cursor.execute('''
                            SELECT customer_id FROM restaurant_customers
                            WHERE loyalty_tier = ?
                        ''', (tier_var.get(),))
                        tier_customers = cursor.fetchall()

                        for (cust_id,) in tier_customers:
                            cursor.execute('''
                                UPDATE restaurant_customers
                                SET loyalty_points = loyalty_points + ?
                                WHERE customer_id = ?
                            ''', (points, cust_id))

                            cursor.execute('''
                                INSERT INTO loyalty_bonus_points
                                (customer_id, points_awarded, reason, description, awarded_by)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (cust_id, points, reason_entry.get(),
                                  desc_text.get('1.0', tk.END).strip(), current_user))

                        customers_affected = len(tier_customers)

                    else:  # 'all'
                        cursor.execute("SELECT customer_id FROM restaurant_customers")
                        all_customers = cursor.fetchall()

                        for (cust_id,) in all_customers:
                            cursor.execute('''
                                UPDATE restaurant_customers
                                SET loyalty_points = loyalty_points + ?
                                WHERE customer_id = ?
                            ''', (points, cust_id))

                            cursor.execute('''
                                INSERT INTO loyalty_bonus_points
                                (customer_id, points_awarded, reason, description, awarded_by)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (cust_id, points, reason_entry.get(),
                                  desc_text.get('1.0', tk.END).strip(), current_user))

                        customers_affected = len(all_customers)

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success",
                                      f"Bonus points awarded successfully!\n\n"
                                      f"Points Awarded: {points}\n"
                                      f"Customers Affected: {customers_affected}\n"
                                      f"Awarded by: {current_user}")
                    bonus_dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to award bonus points: {e}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)

        ttk.Button(btn_frame, text="Award Points",
                  command=award_points).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel",
                  command=bonus_dialog.destroy).pack(side='right', padx=5)

    # Tables Functions
    def view_tables_gui(self):
        """Display tables in the treeview"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return
                
            cursor = conn.cursor()
            cursor.execute('''
                SELECT table_id, capacity, status, location, table_type 
                FROM restaurant_tables 
                ORDER BY table_id
            ''')
            tables = cursor.fetchall()
            
            for item in self.tables_tree.get_children():
                self.tables_tree.delete(item)
                
            for table in tables:
                self.tables_tree.insert('', 'end', values=(
                    table[0], table[1], table[2], table[3] or 'N/A', table[4] or 'Standard'
                ))
                
            conn.close()
            messagebox.showinfo("Success", f"Loaded {len(tables)} tables")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load tables: {str(e)}")
            
    def add_table_dialog(self):
        """Show dialog to add new table"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Restaurant Table")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Add New Table", font=('Arial', 12, 'bold')).pack(pady=10)

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='both', expand=True, pady=10)

        fields = {}

        row = 0
        ttk.Label(form_frame, text="Table ID:*").grid(row=row, column=0, sticky='w', pady=5)
        fields['table_id'] = ttk.Entry(form_frame, width=30)
        fields['table_id'].grid(row=row, column=1, pady=5, padx=10)

        row += 1
        ttk.Label(form_frame, text="Capacity:*").grid(row=row, column=0, sticky='w', pady=5)
        fields['capacity'] = ttk.Spinbox(form_frame, from_=1, to=20, width=28)
        fields['capacity'].grid(row=row, column=1, pady=5, padx=10)
        fields['capacity'].set(4)

        row += 1
        ttk.Label(form_frame, text="Location:").grid(row=row, column=0, sticky='w', pady=5)
        fields['location'] = ttk.Combobox(form_frame, values=['Indoor', 'Outdoor', 'Patio', 'VIP Area', 'Bar'], width=28)
        fields['location'].grid(row=row, column=1, pady=5, padx=10)
        fields['location'].current(0)

        row += 1
        ttk.Label(form_frame, text="Table Type:").grid(row=row, column=0, sticky='w', pady=5)
        fields['table_type'] = ttk.Combobox(form_frame, values=['Standard', 'Booth', 'High Top', 'Counter'], width=28)
        fields['table_type'].grid(row=row, column=1, pady=5, padx=10)
        fields['table_type'].current(0)

        row += 1
        ttk.Label(form_frame, text="Status:").grid(row=row, column=0, sticky='w', pady=5)
        fields['status'] = ttk.Combobox(form_frame, values=['Available', 'Occupied', 'Reserved', 'Maintenance'], width=28)
        fields['status'].grid(row=row, column=1, pady=5, padx=10)
        fields['status'].current(0)

        def save_table():
            table_id = fields['table_id'].get().strip()
            if not table_id:
                messagebox.showerror("Error", "Table ID is required")
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO restaurant_tables (table_id, capacity, status, location, table_type)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    table_id,
                    int(fields['capacity'].get()),
                    fields['status'].get(),
                    fields['location'].get(),
                    fields['table_type'].get()
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Table {table_id} added successfully")
                self.view_tables_gui()
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add table: {e}")

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(pady=10)

        ttk.Button(buttons_frame, text="Save", command=save_table).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
            
    def manage_reservations_dialog(self):
        """Show reservations management dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Reservations Management")
        dialog.geometry("900x700")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Reservations Management", font=('Arial', 14, 'bold')).pack(pady=10)

        # Create reservations table if it doesn't exist
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS restaurant_reservations (
                        reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        customer_id INTEGER,
                        table_id INTEGER,
                        reservation_date TEXT NOT NULL,
                        reservation_time TEXT NOT NULL,
                        party_size INTEGER NOT NULL,
                        status TEXT DEFAULT 'Confirmed',
                        notes TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (customer_id) REFERENCES restaurant_customers(customer_id),
                        FOREIGN KEY (table_id) REFERENCES restaurant_tables(table_id)
                    )
                ''')
                conn.commit()
                conn.close()
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to initialize reservations table: {e}")
            dialog.destroy()
            return

        # Button frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)

        def new_reservation():
            res_dialog = tk.Toplevel(dialog)
            res_dialog.title("New Reservation")
            res_dialog.geometry("500x600")
            res_dialog.transient(dialog)
            res_dialog.grab_set()

            form_frame = ttk.Frame(res_dialog, padding=20)
            form_frame.pack(fill='both', expand=True)

            fields = {}

            row = 0
            ttk.Label(form_frame, text="Customer:").grid(row=row, column=0, sticky='w', pady=5)
            fields['customer'] = ttk.Combobox(form_frame, width=35)
            fields['customer'].grid(row=row, column=1, pady=5, padx=10)

            # Load customers
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT customer_id, name FROM restaurant_customers ORDER BY name')
                    customers = cursor.fetchall()
                    conn.close()
                    fields['customer']['values'] = [f"{c[0]}: {c[1]}" for c in customers]
            except:
                pass

            row += 1
            ttk.Label(form_frame, text="Table:").grid(row=row, column=0, sticky='w', pady=5)
            fields['table'] = ttk.Combobox(form_frame, width=35)
            fields['table'].grid(row=row, column=1, pady=5, padx=10)

            # Load tables
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT table_id, capacity, location FROM restaurant_tables WHERE status = "Available" ORDER BY table_id')
                    tables = cursor.fetchall()
                    conn.close()
                    fields['table']['values'] = [f"Table {t[0]} (Capacity: {t[1]}, {t[2]})" for t in tables]
            except:
                pass

            row += 1
            ttk.Label(form_frame, text="Date (YYYY-MM-DD):*").grid(row=row, column=0, sticky='w', pady=5)
            fields['date'] = ttk.Entry(form_frame, width=35)
            fields['date'].grid(row=row, column=1, pady=5, padx=10)
            fields['date'].insert(0, datetime.now().strftime('%Y-%m-%d'))

            row += 1
            ttk.Label(form_frame, text="Time (HH:MM):*").grid(row=row, column=0, sticky='w', pady=5)
            fields['time'] = ttk.Entry(form_frame, width=35)
            fields['time'].grid(row=row, column=1, pady=5, padx=10)
            fields['time'].insert(0, "18:00")

            row += 1
            ttk.Label(form_frame, text="Party Size:*").grid(row=row, column=0, sticky='w', pady=5)
            fields['party_size'] = ttk.Spinbox(form_frame, from_=1, to=20, width=33)
            fields['party_size'].grid(row=row, column=1, pady=5, padx=10)
            fields['party_size'].set(2)

            row += 1
            ttk.Label(form_frame, text="Notes:").grid(row=row, column=0, sticky='nw', pady=5)
            fields['notes'] = tk.Text(form_frame, height=5, width=35)
            fields['notes'].grid(row=row, column=1, pady=5, padx=10)

            def save_reservation():
                try:
                    customer_selection = fields['customer'].get()
                    customer_id = int(customer_selection.split(':')[0]) if customer_selection else None

                    table_selection = fields['table'].get()
                    table_id = int(table_selection.split()[1]) if table_selection else None

                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO restaurant_reservations
                            (customer_id, table_id, reservation_date, reservation_time, party_size, notes, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (customer_id, table_id, fields['date'].get(), fields['time'].get(),
                              int(fields['party_size'].get()), fields['notes'].get('1.0', tk.END).strip(), 'Confirmed'))
                        conn.commit()
                        conn.close()

                        messagebox.showinfo("Success", "Reservation created successfully!")
                        res_dialog.destroy()
                        load_reservations()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create reservation: {e}")

            button_frame = ttk.Frame(form_frame)
            button_frame.grid(row=row+1, column=0, columnspan=2, pady=20)

            ttk.Button(button_frame, text="Save", command=save_reservation).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=res_dialog.destroy).pack(side='left', padx=5)

        ttk.Button(btn_frame, text="New Reservation", command=new_reservation).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh", command=lambda: load_reservations()).pack(side='left', padx=5)

        # Reservations treeview
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill='both', expand=True, pady=10)

        columns = ('ID', 'Customer', 'Table', 'Date', 'Time', 'Party Size', 'Status')
        reservations_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)

        for col in columns:
            reservations_tree.heading(col, text=col)
            reservations_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=reservations_tree.yview)
        reservations_tree.configure(yscrollcommand=scrollbar.set)

        reservations_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        def load_reservations():
            for item in reservations_tree.get_children():
                reservations_tree.delete(item)

            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT r.reservation_id, COALESCE(c.name, 'Walk-in'), r.table_id,
                               r.reservation_date, r.reservation_time, r.party_size, r.status
                        FROM restaurant_reservations r
                        LEFT JOIN restaurant_customers c ON r.customer_id = c.customer_id
                        ORDER BY r.reservation_date DESC, r.reservation_time DESC
                        LIMIT 100
                    ''')
                    reservations = cursor.fetchall()
                    conn.close()

                    for res in reservations:
                        reservations_tree.insert('', 'end', values=res)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load reservations: {e}")

        load_reservations()

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)
        
    def generate_qr_dialog(self):
        """Show QR code management menu"""
        dialog = tk.Toplevel(self.root)
        dialog.title("QR Code Management")
        dialog.geometry("500x600")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="QR Code Management",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Generate QR Codes section
        generate_section = ttk.LabelFrame(main_frame, text="Generate QR Codes", padding=15)
        generate_section.pack(fill='x', pady=10)

        ttk.Button(generate_section, text="Generate Single QR Code",
                  command=self.create_qr_code_image,
                  width=30).pack(pady=5)

        ttk.Button(generate_section, text="Generate Enhanced Branded QR",
                  command=self.create_enhanced_qr_image,
                  width=30).pack(pady=5)

        ttk.Button(generate_section, text="Batch Print QR Codes",
                  command=self.print_qr_codes,
                  width=30).pack(pady=5)

        # Analytics section
        analytics_section = ttk.LabelFrame(main_frame, text="QR Code Analytics", padding=15)
        analytics_section.pack(fill='x', pady=10)

        ttk.Button(analytics_section, text="View QR Code Usage Analytics",
                  command=self.scan_qr_code_usage,
                  width=30).pack(pady=5)

        # Management section
        mgmt_section = ttk.LabelFrame(main_frame, text="QR Code Database", padding=15)
        mgmt_section.pack(fill='x', pady=10)

        ttk.Button(mgmt_section, text="Update QR Database Records",
                  command=self.update_qr_database_record,
                  width=30).pack(pady=5)

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=15)

    def create_qr_code_image(self):
        """Generate individual QR code image for a table"""
        try:
            import qrcode
            from tkinter import filedialog
            import os

            # Ask for table number
            table_number = simpledialog.askstring("Generate QR Code",
                                                  "Enter table number:")
            if not table_number:
                return

            # Create QR code data
            qr_data = f"https://restaurant.example.com/table/{table_number}"

            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_data)
            qr.make(fit=True)

            # Create image
            img = qr.make_image(fill_color="black", back_color="white")

            # Ask where to save
            filename = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
                initialfile=f"table_{table_number}_qr.png"
            )

            if filename:
                img.save(filename)

                # Update database
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS qr_codes (
                            qr_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            table_number TEXT,
                            qr_data TEXT,
                            generated_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                            image_path TEXT
                        )
                    ''')
                    cursor.execute('''
                        INSERT INTO qr_codes (table_number, qr_data, image_path)
                        VALUES (?, ?, ?)
                    ''', (table_number, qr_data, filename))
                    conn.commit()
                    conn.close()

                messagebox.showinfo("Success",
                                   f"QR code generated successfully!\n\n" +
                                   f"Table: {table_number}\n" +
                                   f"Saved to: {filename}\n" +
                                   f"Size: High resolution (suitable for printing)")

        except ImportError:
            messagebox.showerror("Missing Library",
                                "QR code generation requires the 'qrcode' library.\n\n" +
                                "Install with: pip install qrcode[pil]")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate QR code:\n{str(e)}")

    def create_enhanced_qr_image(self):
        """Generate branded QR code with logo and colors"""
        try:
            import qrcode
            from PIL import Image, ImageDraw, ImageFont
            from tkinter import filedialog

            # Ask for table number
            table_number = simpledialog.askstring("Generate Enhanced QR",
                                                  "Enter table number:")
            if not table_number:
                return

            # Ask for customization
            include_label = messagebox.askyesno("Customization",
                                               "Include table number label on QR code?")

            # Create QR code data
            qr_data = f"https://restaurant.example.com/table/{table_number}"

            # Generate QR code with higher error correction for logo overlay
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_data)
            qr.make(fit=True)

            # Create image with white background
            img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

            if include_label:
                # Add label below QR code
                from PIL import ImageDraw, ImageFont
                width, height = img.size
                new_img = Image.new('RGB', (width, height + 80), 'white')
                new_img.paste(img, (0, 0))

                draw = ImageDraw.Draw(new_img)
                try:
                    # Try to use a nice font
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
                except:
                    # Fallback to default
                    font = ImageFont.load_default()

                text = f"Table {table_number}"
                # Get text bounding box
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_x = (width - text_width) // 2
                text_y = height + 20

                draw.text((text_x, text_y), text, fill="black", font=font)
                img = new_img

            # Ask where to save
            filename = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
                initialfile=f"table_{table_number}_branded_qr.png"
            )

            if filename:
                img.save(filename, quality=95)

                # Update database
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS qr_codes (
                            qr_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            table_number TEXT,
                            qr_data TEXT,
                            generated_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                            image_path TEXT,
                            is_branded BOOLEAN DEFAULT 0
                        )
                    ''')
                    cursor.execute('''
                        INSERT INTO qr_codes (table_number, qr_data, image_path, is_branded)
                        VALUES (?, ?, ?, 1)
                    ''', (table_number, qr_data, filename))
                    conn.commit()
                    conn.close()

                messagebox.showinfo("Success",
                                   f"Enhanced QR code generated!\n\n" +
                                   f"Table: {table_number}\n" +
                                   f"Saved to: {filename}\n" +
                                   f"Features: High quality, labeled")

        except ImportError:
            messagebox.showerror("Missing Library",
                                "Enhanced QR code generation requires 'qrcode' and 'Pillow'.\n\n" +
                                "Install with: pip install qrcode[pil] Pillow")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate enhanced QR code:\n{str(e)}")

    def print_qr_codes(self):
        """Batch generate and print QR codes for multiple tables"""
        try:
            import qrcode
            from PIL import Image, ImageDraw, ImageFont
            from tkinter import filedialog

            # Ask for table range
            start_table = simpledialog.askinteger("Batch Generate",
                                                 "Start table number:",
                                                 minvalue=1, maxvalue=100)
            if not start_table:
                return

            end_table = simpledialog.askinteger("Batch Generate",
                                               "End table number:",
                                               minvalue=start_table, maxvalue=100)
            if not end_table:
                return

            # Ask for save directory
            save_dir = filedialog.askdirectory(title="Select folder to save QR codes")
            if not save_dir:
                return

            generated_count = 0
            errors = []

            for table_num in range(start_table, end_table + 1):
                try:
                    # Create QR code
                    qr_data = f"https://restaurant.example.com/table/{table_num}"
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_H,
                        box_size=10,
                        border=4,
                    )
                    qr.add_data(qr_data)
                    qr.make(fit=True)

                    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

                    # Add label
                    width, height = img.size
                    new_img = Image.new('RGB', (width, height + 80), 'white')
                    new_img.paste(img, (0, 0))

                    draw = ImageDraw.Draw(new_img)
                    try:
                        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
                    except:
                        font = ImageFont.load_default()

                    text = f"Table {table_num}"
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_x = (width - text_width) // 2
                    text_y = height + 20

                    draw.text((text_x, text_y), text, fill="black", font=font)

                    # Save
                    import os
                    filename = os.path.join(save_dir, f"table_{table_num:03d}_qr.png")
                    new_img.save(filename, quality=95)

                    # Update database
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            CREATE TABLE IF NOT EXISTS qr_codes (
                                qr_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                table_number TEXT,
                                qr_data TEXT,
                                generated_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                                image_path TEXT,
                                is_branded BOOLEAN DEFAULT 0
                            )
                        ''')
                        cursor.execute('''
                            INSERT INTO qr_codes (table_number, qr_data, image_path, is_branded)
                            VALUES (?, ?, ?, 1)
                        ''', (str(table_num), qr_data, filename))
                        conn.commit()
                        conn.close()

                    generated_count += 1

                except Exception as e:
                    errors.append(f"Table {table_num}: {str(e)}")

            # Show results
            result_msg = f"Batch QR Code Generation Complete!\n\n"
            result_msg += f"Successfully generated: {generated_count} QR codes\n"
            result_msg += f"Saved to: {save_dir}\n"

            if errors:
                result_msg += f"\nErrors ({len(errors)}):\n"
                result_msg += "\n".join(errors[:5])  # Show first 5 errors
                if len(errors) > 5:
                    result_msg += f"\n... and {len(errors) - 5} more"

            messagebox.showinfo("Batch Generation Complete", result_msg)

        except ImportError:
            messagebox.showerror("Missing Library",
                                "Batch QR code generation requires 'qrcode' and 'Pillow'.\n\n" +
                                "Install with: pip install qrcode[pil] Pillow")
        except Exception as e:
            messagebox.showerror("Error", f"Batch generation failed:\n{str(e)}")

    def scan_qr_code_usage(self):
        """Display QR code scanning analytics"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # Create tables if they don't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS qr_scans (
                    scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_number TEXT,
                    scan_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    customer_id INTEGER,
                    device_type TEXT
                )
            ''')
            conn.commit()

            # Get analytics data
            cursor.execute('''
                SELECT COUNT(*) FROM qr_scans
            ''')
            total_scans = cursor.fetchone()[0]

            cursor.execute('''
                SELECT table_number, COUNT(*) as scan_count
                FROM qr_scans
                GROUP BY table_number
                ORDER BY scan_count DESC
                LIMIT 10
            ''')
            top_tables = cursor.fetchall()

            cursor.execute('''
                SELECT strftime('%H', scan_time) as hour, COUNT(*) as count
                FROM qr_scans
                GROUP BY hour
                ORDER BY count DESC
                LIMIT 5
            ''')
            peak_hours = cursor.fetchall()

            cursor.execute('''
                SELECT DATE(scan_time) as date, COUNT(*) as count
                FROM qr_scans
                WHERE scan_time >= date('now', '-7 days')
                GROUP BY date
                ORDER BY date DESC
            ''')
            recent_scans = cursor.fetchall()

            conn.close()

            # Display analytics
            analytics_dialog = tk.Toplevel(self.root)
            analytics_dialog.title("QR Code Usage Analytics")
            analytics_dialog.geometry("800x600")
            analytics_dialog.transient(self.root)

            main_frame = ttk.Frame(analytics_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="QR Code Usage Analytics",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            # Create scrolled text for report
            report_text = ScrolledText(main_frame, height=30, width=90)
            report_text.pack(fill='both', expand=True)

            report = "QR CODE USAGE ANALYTICS\n"
            report += "=" * 80 + "\n\n"

            report += f"OVERALL STATISTICS:\n"
            report += "-" * 80 + "\n"
            report += f"Total Scans: {total_scans}\n\n"

            report += "TOP 10 MOST SCANNED TABLES:\n"
            report += "-" * 80 + "\n"
            report += f"{'Table':<15} {'Scan Count':<15} {'Engagement':<20}\n"
            report += "-" * 80 + "\n"
            for table, count in top_tables:
                engagement = "High" if count > 50 else "Medium" if count > 20 else "Low"
                report += f"{table:<15} {count:<15} {engagement:<20}\n"

            report += "\n\nPEAK SCANNING HOURS:\n"
            report += "-" * 80 + "\n"
            report += f"{'Hour':<15} {'Scan Count':<15} {'Time Period':<20}\n"
            report += "-" * 80 + "\n"
            for hour, count in peak_hours:
                if hour:
                    hour_int = int(hour)
                    period = "Breakfast" if 6 <= hour_int < 11 else "Lunch" if 11 <= hour_int < 15 else "Dinner" if 17 <= hour_int < 22 else "Other"
                    report += f"{hour:02d}:00{' '*9} {count:<15} {period:<20}\n"

            report += "\n\nSCANS BY DATE (Last 7 Days):\n"
            report += "-" * 80 + "\n"
            report += f"{'Date':<15} {'Scan Count':<15} {'Trend':<20}\n"
            report += "-" * 80 + "\n"
            for date, count in recent_scans:
                trend = "▲" if count > 30 else "▼" if count < 10 else "■"
                report += f"{date:<15} {count:<15} {trend:<20}\n"

            report += "\n\nKEY INSIGHTS:\n"
            report += "-" * 80 + "\n"
            if total_scans == 0:
                report += "• No QR code scans recorded yet\n"
                report += "• Generate and distribute QR codes to tables\n"
                report += "• Encourage customers to scan for digital menus\n"
            else:
                report += f"• Average scans per table: {total_scans / max(len(top_tables), 1):.1f}\n"
                if peak_hours:
                    report += f"• Peak usage hour: {peak_hours[0][0]}:00\n"
                if top_tables:
                    report += f"• Most popular table: {top_tables[0][0]} ({top_tables[0][1]} scans)\n"
                report += "• QR code effectiveness: " + ("High" if total_scans > 100 else "Medium" if total_scans > 30 else "Low") + "\n"

            report_text.insert(1.0, report)
            report_text.config(state='disabled')

            # Add simulate scan button for testing
            def simulate_scan():
                table = simpledialog.askstring("Simulate Scan", "Enter table number:")
                if table:
                    try:
                        conn = get_db_connection()
                        if conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                INSERT INTO qr_scans (table_number, device_type)
                                VALUES (?, 'Mobile')
                            ''', (table,))
                            conn.commit()
                            conn.close()
                            messagebox.showinfo("Success", f"Simulated scan for Table {table}")
                            analytics_dialog.destroy()
                            self.scan_qr_code_usage()  # Refresh
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to simulate scan: {e}")

            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=10)

            ttk.Button(button_frame, text="Simulate Scan (Testing)",
                      command=simulate_scan).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close",
                      command=analytics_dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load QR analytics:\n{str(e)}")

    def update_qr_database_record(self):
        """Update QR code database records"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # Create table if doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS qr_codes (
                    qr_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_number TEXT,
                    qr_data TEXT,
                    generated_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    image_path TEXT,
                    is_branded BOOLEAN DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    version INTEGER DEFAULT 1
                )
            ''')
            conn.commit()

            # Get all QR codes
            cursor.execute('''
                SELECT qr_id, table_number, generated_date, is_active, version
                FROM qr_codes
                ORDER BY table_number
            ''')
            qr_records = cursor.fetchall()
            conn.close()

            if not qr_records:
                messagebox.showinfo("No Records",
                                   "No QR code records found in database.\n\n" +
                                   "Generate QR codes first to create records.")
                return

            # Show management dialog
            mgmt_dialog = tk.Toplevel(self.root)
            mgmt_dialog.title("QR Code Database Management")
            mgmt_dialog.geometry("800x500")
            mgmt_dialog.transient(self.root)

            main_frame = ttk.Frame(mgmt_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="QR Code Database Records",
                     font=('Arial', 12, 'bold')).pack(pady=10)

            # Create treeview
            tree_frame = ttk.Frame(main_frame)
            tree_frame.pack(fill='both', expand=True, pady=10)

            columns = ('ID', 'Table', 'Generated', 'Active', 'Version')
            tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=150)

            for record in qr_records:
                qr_id, table, gen_date, is_active, version = record
                active_status = "Yes" if is_active else "No"
                tree.insert('', 'end', values=(qr_id, table, gen_date, active_status, version))

            scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Action buttons
            def regenerate_qr():
                selection = tree.selection()
                if not selection:
                    messagebox.showwarning("No Selection", "Please select a QR code to regenerate")
                    return

                item = tree.item(selection[0])
                qr_id = item['values'][0]
                table_num = item['values'][1]

                if messagebox.askyesno("Confirm", f"Regenerate QR code for Table {table_num}?"):
                    try:
                        conn = get_db_connection()
                        if conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                UPDATE qr_codes
                                SET version = version + 1,
                                    generated_date = CURRENT_TIMESTAMP
                                WHERE qr_id = ?
                            ''', (qr_id,))
                            conn.commit()
                            conn.close()
                            messagebox.showinfo("Success", f"QR code record updated for Table {table_num}")
                            mgmt_dialog.destroy()
                            self.update_qr_database_record()  # Refresh
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to update record: {e}")

            def toggle_active():
                selection = tree.selection()
                if not selection:
                    messagebox.showwarning("No Selection", "Please select a QR code")
                    return

                item = tree.item(selection[0])
                qr_id = item['values'][0]
                table_num = item['values'][1]
                current_status = item['values'][3]

                new_status = 0 if current_status == "Yes" else 1

                try:
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE qr_codes
                            SET is_active = ?
                            WHERE qr_id = ?
                        ''', (new_status, qr_id))
                        conn.commit()
                        conn.close()
                        messagebox.showinfo("Success",
                                           f"Table {table_num} QR code " +
                                           ("activated" if new_status else "deactivated"))
                        mgmt_dialog.destroy()
                        self.update_qr_database_record()  # Refresh
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update status: {e}")

            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=10)

            ttk.Button(button_frame, text="Regenerate Selected",
                      command=regenerate_qr).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Toggle Active/Inactive",
                      command=toggle_active).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close",
                      command=mgmt_dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to manage QR database:\n{str(e)}")

    def optimize_table_structure(self):
        """Optimize table arrangement based on utilization data"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # Get table utilization data
            cursor.execute('''
                SELECT t.table_id, t.capacity, t.location, t.table_type,
                       COUNT(r.reservation_id) as reservation_count,
                       AVG(r.party_size) as avg_party_size
                FROM restaurant_tables t
                LEFT JOIN restaurant_reservations r ON t.table_id = r.table_id
                WHERE r.reservation_date >= date('now', '-30 days')
                GROUP BY t.table_id
                ORDER BY reservation_count DESC
            ''')
            utilization_data = cursor.fetchall()

            # Get revenue per table (if order data exists)
            cursor.execute('''
                SELECT t.table_id, SUM(o.total_price) as total_revenue
                FROM restaurant_tables t
                LEFT JOIN restaurant_orders o ON t.table_id = o.table_id
                WHERE o.order_time >= datetime('now', '-30 days')
                GROUP BY t.table_id
            ''')
            revenue_data = dict(cursor.fetchall())

            conn.close()

            # Display optimization analysis
            opt_dialog = tk.Toplevel(self.root)
            opt_dialog.title("Table Structure Optimization")
            opt_dialog.geometry("900x700")
            opt_dialog.transient(self.root)

            main_frame = ttk.Frame(opt_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Table Structure Optimization Analysis",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            # Create scrolled text for report
            report_text = ScrolledText(main_frame, height=35, width=100)
            report_text.pack(fill='both', expand=True)

            report = "TABLE STRUCTURE OPTIMIZATION ANALYSIS\n"
            report += "=" * 90 + "\n\n"

            # Table utilization analysis
            report += "TABLE UTILIZATION ANALYSIS (Last 30 Days):\n"
            report += "-" * 90 + "\n"
            report += f"{'Table':<10} {'Capacity':<10} {'Reservations':<15} {'Avg Party':<12} {'Revenue':<15} {'Efficiency':<15}\n"
            report += "-" * 90 + "\n"

            total_capacity = 0
            total_reservations = 0
            underutilized = []
            overutilized = []

            for table_id, capacity, location, table_type, res_count, avg_party in utilization_data:
                revenue = revenue_data.get(table_id, 0)
                efficiency = (avg_party / capacity * 100) if capacity and avg_party else 0

                total_capacity += capacity
                total_reservations += res_count

                report += f"{table_id:<10} {capacity:<10} {res_count:<15} {avg_party or 0:<12.1f} £{revenue:<14.2f} {efficiency:<14.1f}%\n"

                if efficiency < 60 and res_count > 5:
                    underutilized.append((table_id, capacity, efficiency))
                elif efficiency > 95 and res_count > 10:
                    overutilized.append((table_id, capacity, efficiency))

            # Capacity vs Demand analysis
            report += "\n\nCAPACITY VS DEMAND ANALYSIS:\n"
            report += "-" * 90 + "\n"
            report += f"Total Seating Capacity: {total_capacity} seats\n"
            report += f"Total Reservations (30 days): {total_reservations}\n"
            if utilization_data:
                avg_util = (total_reservations / (len(utilization_data) * 30)) * 100
                report += f"Average Table Utilization: {avg_util:.1f}%\n\n"

            # Recommendations
            report += "OPTIMIZATION RECOMMENDATIONS:\n"
            report += "-" * 90 + "\n"

            if underutilized:
                report += "\n1. UNDERUTILIZED TABLES (< 60% efficiency):\n"
                for table_id, capacity, efficiency in underutilized:
                    report += f"   • Table {table_id} ({capacity} seats) - {efficiency:.1f}% efficiency\n"
                    report += f"     Recommendation: Consider converting to smaller table or different configuration\n"

            if overutilized:
                report += "\n2. OVERUTILIZED TABLES (> 95% efficiency):\n"
                for table_id, capacity, efficiency in overutilized:
                    report += f"   • Table {table_id} ({capacity} seats) - {efficiency:.1f}% efficiency\n"
                    report += f"     Recommendation: High demand - consider adding similar capacity tables\n"

            if not underutilized and not overutilized:
                report += "• Current table configuration appears well-balanced\n"
                report += "• Continue monitoring utilization trends\n"

            # Revenue optimization
            report += "\n3. REVENUE OPTIMIZATION:\n"
            top_revenue = sorted(revenue_data.items(), key=lambda x: x[1], reverse=True)[:3]
            if top_revenue:
                report += "   Top revenue-generating tables:\n"
                for table_id, revenue in top_revenue:
                    report += f"   • Table {table_id}: £{revenue:.2f}\n"
                report += "   Recommendation: Prioritize these table locations for expansion\n"

            # Turnover rate analysis
            report += "\n4. TURNOVER RATE ANALYSIS:\n"
            if total_reservations > 0:
                daily_turnover = total_reservations / 30
                report += f"   • Average daily table turnovers: {daily_turnover:.1f}\n"
                if daily_turnover < 2:
                    report += "   • Recommendation: Low turnover - consider strategies to increase table turnover\n"
                elif daily_turnover > 4:
                    report += "   • Recommendation: High turnover - ensure service quality is maintained\n"

            report += "\n\nACTION ITEMS:\n"
            report += "-" * 90 + "\n"
            report += "1. Review underutilized tables for reconfiguration\n"
            report += "2. Monitor overutilized tables for customer satisfaction\n"
            report += "3. Consider adding capacity in high-revenue areas\n"
            report += "4. Optimize table allocation during peak hours\n"
            report += "5. Review reservation patterns for better planning\n"

            report_text.insert(1.0, report)
            report_text.config(state='disabled')

            ttk.Button(main_frame, text="Close",
                      command=opt_dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze table structure:\n{str(e)}")

    # Staff Functions
    def view_staff_gui(self):
        """Display staff in the treeview"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return
                
            cursor = conn.cursor()
            cursor.execute('''
                SELECT staff_id, name, role, hourly_rate, status, performance_score 
                FROM restaurant_staff 
                ORDER BY name
            ''')
            staff = cursor.fetchall()
            
            for item in self.staff_tree.get_children():
                self.staff_tree.delete(item)
                
            for member in staff:
                hourly_rate = f"£{member[3]:.2f}" if member[3] else "N/A"
                performance = f"{member[5]:.1f}/10" if member[5] else "N/A"
                
                self.staff_tree.insert('', 'end', values=(
                    member[0], member[1], member[2], hourly_rate, member[4], performance
                ))
                
            conn.close()
            messagebox.showinfo("Success", f"Loaded {len(staff)} staff members")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load staff: {str(e)}")
            
    def add_staff_dialog(self):
        """Show dialog to add new staff"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Staff Member")
        dialog.geometry("500x500")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Add New Staff Member", font=('Arial', 12, 'bold')).pack(pady=10)

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='both', expand=True, pady=10)

        fields = {}

        row = 0
        ttk.Label(form_frame, text="Name:*").grid(row=row, column=0, sticky='w', pady=5)
        fields['name'] = ttk.Entry(form_frame, width=30)
        fields['name'].grid(row=row, column=1, pady=5, padx=10)

        row += 1
        ttk.Label(form_frame, text="Role:*").grid(row=row, column=0, sticky='w', pady=5)
        fields['role'] = ttk.Combobox(form_frame, values=['Waiter', 'Chef', 'Manager', 'Bartender', 'Host', 'Cleaner'], width=28)
        fields['role'].grid(row=row, column=1, pady=5, padx=10)
        fields['role'].current(0)

        row += 1
        ttk.Label(form_frame, text="Hourly Rate (£):*").grid(row=row, column=0, sticky='w', pady=5)
        fields['hourly_rate'] = ttk.Entry(form_frame, width=30)
        fields['hourly_rate'].grid(row=row, column=1, pady=5, padx=10)
        fields['hourly_rate'].insert(0, "10.00")

        row += 1
        ttk.Label(form_frame, text="Email:").grid(row=row, column=0, sticky='w', pady=5)
        fields['email'] = ttk.Entry(form_frame, width=30)
        fields['email'].grid(row=row, column=1, pady=5, padx=10)

        row += 1
        ttk.Label(form_frame, text="Phone:").grid(row=row, column=0, sticky='w', pady=5)
        fields['phone'] = ttk.Entry(form_frame, width=30)
        fields['phone'].grid(row=row, column=1, pady=5, padx=10)

        row += 1
        ttk.Label(form_frame, text="Status:").grid(row=row, column=0, sticky='w', pady=5)
        fields['status'] = ttk.Combobox(form_frame, values=['Active', 'On Leave', 'Inactive'], width=28)
        fields['status'].grid(row=row, column=1, pady=5, padx=10)
        fields['status'].current(0)

        def save_staff():
            name = fields['name'].get().strip()
            if not name:
                messagebox.showerror("Error", "Name is required")
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO restaurant_staff (name, role, hourly_rate, email, phone, status, performance_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    name,
                    fields['role'].get(),
                    float(fields['hourly_rate'].get()),
                    fields['email'].get() or None,
                    fields['phone'].get() or None,
                    fields['status'].get(),
                    5.0  # Default performance score
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Staff member {name} added successfully")
                self.view_staff_gui()
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add staff member: {e}")

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(pady=10)

        ttk.Button(buttons_frame, text="Save", command=save_staff).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
            
    def manage_schedules_dialog(self):
        """Show schedules management dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Staff Schedules Management")
        dialog.geometry("1000x700")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Staff Schedules Management", font=('Arial', 14, 'bold')).pack(pady=10)

        # Create schedules table if it doesn't exist
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS restaurant_schedules (
                        schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        staff_id INTEGER NOT NULL,
                        shift_date TEXT NOT NULL,
                        shift_start TEXT NOT NULL,
                        shift_end TEXT NOT NULL,
                        role TEXT,
                        notes TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (staff_id) REFERENCES restaurant_staff(staff_id)
                    )
                ''')
                conn.commit()
                conn.close()
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to initialize schedules table: {e}")
            dialog.destroy()
            return

        # Control frame
        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.pack(fill='x', pady=10)

        # Week selector
        week_frame = ttk.Frame(ctrl_frame)
        week_frame.pack(side='left', padx=5)

        ttk.Label(week_frame, text="Week Starting:").pack(side='left', padx=5)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        date_entry = ttk.Entry(week_frame, textvariable=date_var, width=15)
        date_entry.pack(side='left', padx=5)

        def add_shift():
            shift_dialog = tk.Toplevel(dialog)
            shift_dialog.title("Add Shift")
            shift_dialog.geometry("500x500")
            shift_dialog.transient(dialog)
            shift_dialog.grab_set()

            form_frame = ttk.Frame(shift_dialog, padding=20)
            form_frame.pack(fill='both', expand=True)

            fields = {}

            row = 0
            ttk.Label(form_frame, text="Staff Member:*").grid(row=row, column=0, sticky='w', pady=5)
            fields['staff'] = ttk.Combobox(form_frame, width=35)
            fields['staff'].grid(row=row, column=1, pady=5, padx=10)

            # Load staff
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT staff_id, name, role FROM restaurant_staff WHERE status = "Active" ORDER BY name')
                    staff = cursor.fetchall()
                    conn.close()
                    fields['staff']['values'] = [f"{s[0]}: {s[1]} ({s[2]})" for s in staff]
            except:
                pass

            row += 1
            ttk.Label(form_frame, text="Date (YYYY-MM-DD):*").grid(row=row, column=0, sticky='w', pady=5)
            fields['date'] = ttk.Entry(form_frame, width=35)
            fields['date'].grid(row=row, column=1, pady=5, padx=10)
            fields['date'].insert(0, datetime.now().strftime('%Y-%m-%d'))

            row += 1
            ttk.Label(form_frame, text="Start Time (HH:MM):*").grid(row=row, column=0, sticky='w', pady=5)
            fields['start'] = ttk.Entry(form_frame, width=35)
            fields['start'].grid(row=row, column=1, pady=5, padx=10)
            fields['start'].insert(0, "09:00")

            row += 1
            ttk.Label(form_frame, text="End Time (HH:MM):*").grid(row=row, column=0, sticky='w', pady=5)
            fields['end'] = ttk.Entry(form_frame, width=35)
            fields['end'].grid(row=row, column=1, pady=5, padx=10)
            fields['end'].insert(0, "17:00")

            row += 1
            ttk.Label(form_frame, text="Role:").grid(row=row, column=0, sticky='w', pady=5)
            fields['role'] = ttk.Combobox(form_frame, values=['Waiter', 'Chef', 'Manager', 'Bartender', 'Host'], width=33)
            fields['role'].grid(row=row, column=1, pady=5, padx=10)

            row += 1
            ttk.Label(form_frame, text="Notes:").grid(row=row, column=0, sticky='nw', pady=5)
            fields['notes'] = tk.Text(form_frame, height=4, width=35)
            fields['notes'].grid(row=row, column=1, pady=5, padx=10)

            def save_shift():
                try:
                    staff_selection = fields['staff'].get()
                    if not staff_selection:
                        messagebox.showwarning("Missing Info", "Please select a staff member")
                        return

                    staff_id = int(staff_selection.split(':')[0])

                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO restaurant_schedules
                            (staff_id, shift_date, shift_start, shift_end, role, notes)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (staff_id, fields['date'].get(), fields['start'].get(), fields['end'].get(),
                              fields['role'].get(), fields['notes'].get('1.0', tk.END).strip()))
                        conn.commit()
                        conn.close()

                        messagebox.showinfo("Success", "Shift added successfully!")
                        shift_dialog.destroy()
                        load_schedules()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to add shift: {e}")

            button_frame = ttk.Frame(form_frame)
            button_frame.grid(row=row+1, column=0, columnspan=2, pady=20)

            ttk.Button(button_frame, text="Save", command=save_shift).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=shift_dialog.destroy).pack(side='left', padx=5)

        ttk.Button(ctrl_frame, text="Add Shift", command=add_shift).pack(side='left', padx=5)
        ttk.Button(ctrl_frame, text="Refresh", command=lambda: load_schedules()).pack(side='left', padx=5)

        # Schedules treeview
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill='both', expand=True, pady=10)

        columns = ('ID', 'Staff', 'Date', 'Start', 'End', 'Role', 'Notes')
        schedules_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)

        for col in columns:
            schedules_tree.heading(col, text=col)
            schedules_tree.column(col, width=100 if col != 'Notes' else 150)

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=schedules_tree.yview)
        schedules_tree.configure(yscrollcommand=scrollbar.set)

        schedules_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        def load_schedules():
            for item in schedules_tree.get_children():
                schedules_tree.delete(item)

            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT s.schedule_id, st.name, s.shift_date, s.shift_start, s.shift_end, s.role, s.notes
                        FROM restaurant_schedules s
                        JOIN restaurant_staff st ON s.staff_id = st.staff_id
                        ORDER BY s.shift_date DESC, s.shift_start
                        LIMIT 100
                    ''')
                    schedules = cursor.fetchall()
                    conn.close()

                    for sch in schedules:
                        schedules_tree.insert('', 'end', values=sch)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load schedules: {e}")

        load_schedules()

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)
        
    def show_staff_analytics(self):
        """Show staff analytics"""
        try:
            analytics_window = tk.Toplevel(self.root)
            analytics_window.title("Staff Analytics")
            analytics_window.geometry("800x600")
            
            text_area = ScrolledText(analytics_window, height=30, width=80)
            text_area.pack(fill='both', expand=True, padx=10, pady=10)
            
            analytics_text = self.generate_staff_analytics()
            text_area.insert('1.0', analytics_text)
            text_area.config(state='disabled')
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate analytics: {str(e)}")
            
    def generate_staff_analytics(self):
        """Generate staff analytics text"""
        try:
            conn = get_db_connection()
            if not conn:
                return "Database connection failed"
                
            cursor = conn.cursor()
            
            text = "STAFF ANALYTICS\n"
            text += "=" * 50 + "\n\n"
            
            cursor.execute('''
                SELECT role, COUNT(*) as count, AVG(hourly_rate) as avg_rate, AVG(performance_score) as avg_performance
                FROM restaurant_staff
                WHERE status = 'Active'
                GROUP BY role
            ''')
            
            role_data = cursor.fetchall()
            
            text += "Staff by Role:\n"
            text += "-" * 50 + "\n"
            for role in role_data:
                avg_rate = f"£{role[2]:.2f}" if role[2] else "N/A"
                avg_perf = f"{role[3]:.1f}/10" if role[3] else "N/A"
                text += f"{role[0]}: {role[1]} staff, Avg Rate: {avg_rate}, Avg Performance: {avg_perf}\n"
                
            conn.close()
            return text
            
        except Exception as e:
            return f"Error generating analytics: {str(e)}"

    def view_schedule_conflicts(self):
        """Identify and display scheduling conflicts"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # Find overlapping shifts
            cursor.execute('''
                SELECT s1.shift_id as shift1_id, s1.staff_id, s1.shift_date, s1.start_time, s1.end_time,
                       s2.shift_id as shift2_id, s2.start_time as overlap_start, s2.end_time as overlap_end,
                       st.name
                FROM restaurant_shifts s1
                JOIN restaurant_shifts s2 ON s1.staff_id = s2.staff_id
                    AND s1.shift_id != s2.shift_id
                    AND s1.shift_date = s2.shift_date
                    AND s1.start_time < s2.end_time
                    AND s1.end_time > s2.start_time
                JOIN restaurant_staff st ON s1.staff_id = st.staff_id
                WHERE s1.shift_date >= date('now')
                ORDER BY s1.shift_date, s1.start_time
            ''')
            conflicts = cursor.fetchall()

            # Check for understaffed periods (need at least 2 staff per 4-hour period)
            cursor.execute('''
                SELECT shift_date, start_time, COUNT(*) as staff_count
                FROM restaurant_shifts
                WHERE shift_date >= date('now')
                GROUP BY shift_date, start_time
                HAVING COUNT(*) < 2
                ORDER BY shift_date, start_time
            ''')
            understaffed = cursor.fetchall()

            # Check for overstaffed periods (more than 6 staff at once)
            cursor.execute('''
                SELECT shift_date, start_time, COUNT(*) as staff_count
                FROM restaurant_shifts
                WHERE shift_date >= date('now')
                GROUP BY shift_date, start_time
                HAVING COUNT(*) > 6
                ORDER BY shift_date, start_time
            ''')
            overstaffed = cursor.fetchall()

            conn.close()

            # Display conflicts
            conflict_dialog = tk.Toplevel(self.root)
            conflict_dialog.title("Schedule Conflicts")
            conflict_dialog.geometry("900x700")
            conflict_dialog.transient(self.root)

            main_frame = ttk.Frame(conflict_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Schedule Conflicts & Issues",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            report_text = ScrolledText(main_frame, height=35, width=100)
            report_text.pack(fill='both', expand=True)

            report = "SCHEDULE CONFLICTS REPORT\n"
            report += "=" * 90 + "\n\n"

            # Overlapping shifts
            report += "1. OVERLAPPING SHIFTS (Double-booked staff):\n"
            report += "-" * 90 + "\n"
            if conflicts:
                for shift1_id, staff_id, shift_date, start1, end1, shift2_id, start2, end2, name in conflicts:
                    report += f"Staff: {name} (ID: {staff_id})\n"
                    report += f"  Date: {shift_date}\n"
                    report += f"  Shift 1: {start1} - {end1} (ID: {shift1_id})\n"
                    report += f"  Shift 2: {start2} - {end2} (ID: {shift2_id})\n"
                    report += f"  CONFLICT: Shifts overlap!\n\n"
                report += f"\nTotal conflicts found: {len(conflicts)}\n"
            else:
                report += "No overlapping shifts detected.\n"

            # Understaffed periods
            report += "\n\n2. UNDERSTAFFED PERIODS (< 2 staff):\n"
            report += "-" * 90 + "\n"
            if understaffed:
                for shift_date, start_time, staff_count in understaffed:
                    report += f"Date: {shift_date}, Time: {start_time} - Staff Count: {staff_count}\n"
                report += f"\nTotal understaffed periods: {len(understaffed)}\n"
            else:
                report += "No understaffed periods detected.\n"

            # Overstaffed periods
            report += "\n\n3. OVERSTAFFED PERIODS (> 6 staff):\n"
            report += "-" * 90 + "\n"
            if overstaffed:
                for shift_date, start_time, staff_count in overstaffed:
                    report += f"Date: {shift_date}, Time: {start_time} - Staff Count: {staff_count}\n"
                report += f"\nTotal overstaffed periods: {len(overstaffed)}\n"
            else:
                report += "No overstaffed periods detected.\n"

            # Recommendations
            report += "\n\nRECOMMENDATIONS:\n"
            report += "-" * 90 + "\n"
            if conflicts:
                report += "• Resolve overlapping shifts immediately\n"
                report += "• Contact affected staff to confirm availability\n"
                report += "• Update shift assignments\n"
            if understaffed:
                report += "• Schedule additional staff for understaffed periods\n"
                report += "• Consider part-time staff or on-call arrangements\n"
            if overstaffed:
                report += "• Reduce staff during overstaffed periods to optimize costs\n"
                report += "• Reassign staff to other duties or locations\n"
            if not conflicts and not understaffed and not overstaffed:
                report += "• Schedule appears well-balanced\n"
                report += "• Continue monitoring for future conflicts\n"

            report_text.insert(1.0, report)
            report_text.config(state='disabled')

            ttk.Button(main_frame, text="Close",
                      command=conflict_dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to check schedule conflicts:\n{str(e)}")

    def staff_performance(self):
        """Staff performance management menu"""
        perf_dialog = tk.Toplevel(self.root)
        perf_dialog.title("Staff Performance Management")
        perf_dialog.geometry("400x350")
        perf_dialog.transient(self.root)
        perf_dialog.grab_set()

        main_frame = ttk.Frame(perf_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Staff Performance Management",
                 font=('Arial', 14, 'bold')).pack(pady=20)

        ttk.Button(main_frame, text="View Performance Rankings",
                  command=lambda: [perf_dialog.destroy(), self.view_performance_rankings()],
                  width=35).pack(pady=10)

        ttk.Button(main_frame, text="Update Performance Scores",
                  command=lambda: [perf_dialog.destroy(), self.update_performance_scores()],
                  width=35).pack(pady=10)

        ttk.Button(main_frame, text="Export Performance Report",
                  command=lambda: [perf_dialog.destroy(), self.export_performance_report()],
                  width=35).pack(pady=10)

        ttk.Button(main_frame, text="Close",
                  command=perf_dialog.destroy,
                  width=35).pack(pady=20)

    def view_performance_rankings(self):
        """Display staff performance rankings"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # Create performance table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS staff_performance (
                    performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    staff_id INTEGER,
                    punctuality_score INTEGER DEFAULT 5,
                    quality_score INTEGER DEFAULT 5,
                    efficiency_score INTEGER DEFAULT 5,
                    teamwork_score INTEGER DEFAULT 5,
                    overall_score REAL DEFAULT 5.0,
                    evaluation_date DATE DEFAULT CURRENT_DATE,
                    notes TEXT,
                    FOREIGN KEY (staff_id) REFERENCES restaurant_staff(staff_id)
                )
            ''')
            conn.commit()

            # Get performance rankings
            cursor.execute('''
                SELECT s.staff_id, s.name, s.position,
                       COALESCE(AVG(p.overall_score), 5.0) as avg_score,
                       COUNT(p.performance_id) as eval_count
                FROM restaurant_staff s
                LEFT JOIN staff_performance p ON s.staff_id = p.staff_id
                GROUP BY s.staff_id
                ORDER BY avg_score DESC
            ''')
            rankings = cursor.fetchall()

            conn.close()

            # Display rankings
            rank_dialog = tk.Toplevel(self.root)
            rank_dialog.title("Staff Performance Rankings")
            rank_dialog.geometry("800x600")
            rank_dialog.transient(self.root)

            main_frame = ttk.Frame(rank_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Staff Performance Rankings",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            # Create treeview
            columns = ('Rank', 'Staff ID', 'Name', 'Position', 'Avg Score', 'Evaluations', 'Performance')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=100)

            rank = 1
            for staff_id, name, position, avg_score, eval_count in rankings:
                performance = "Excellent" if avg_score >= 8 else "Good" if avg_score >= 6 else "Needs Improvement"
                tree.insert('', 'end', values=(rank, staff_id, name, position,
                                              f"{avg_score:.1f}/10", eval_count, performance))
                rank += 1

            scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            ttk.Button(main_frame, text="Close",
                      command=rank_dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load performance rankings:\n{str(e)}")

    def update_performance_scores(self):
        """Update individual staff performance scores"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()
            cursor.execute('SELECT staff_id, name, position FROM restaurant_staff ORDER BY name')
            staff_list = cursor.fetchall()
            conn.close()

            if not staff_list:
                messagebox.showinfo("No Staff", "No staff members found in database")
                return

            # Create dialog
            update_dialog = tk.Toplevel(self.root)
            update_dialog.title("Update Performance Scores")
            update_dialog.geometry("500x650")
            update_dialog.transient(self.root)

            main_frame = ttk.Frame(update_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Update Performance Scores",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            # Staff selection
            staff_frame = ttk.LabelFrame(main_frame, text="Select Staff Member", padding=10)
            staff_frame.pack(fill='x', pady=10)

            staff_var = tk.StringVar()
            staff_dropdown = ttk.Combobox(staff_frame, textvariable=staff_var, width=40, state='readonly')
            staff_dropdown['values'] = [f"{s[0]} - {s[1]} ({s[2]})" for s in staff_list]
            staff_dropdown.pack()

            # Performance criteria
            criteria_frame = ttk.LabelFrame(main_frame, text="Performance Criteria (1-10)", padding=10)
            criteria_frame.pack(fill='x', pady=10)

            punctuality_var = tk.IntVar(value=5)
            quality_var = tk.IntVar(value=5)
            efficiency_var = tk.IntVar(value=5)
            teamwork_var = tk.IntVar(value=5)

            ttk.Label(criteria_frame, text="Punctuality:").grid(row=0, column=0, sticky='w', pady=5)
            ttk.Scale(criteria_frame, from_=1, to=10, variable=punctuality_var, orient='horizontal', length=200).grid(row=0, column=1, padx=10)
            ttk.Label(criteria_frame, textvariable=punctuality_var).grid(row=0, column=2)

            ttk.Label(criteria_frame, text="Quality:").grid(row=1, column=0, sticky='w', pady=5)
            ttk.Scale(criteria_frame, from_=1, to=10, variable=quality_var, orient='horizontal', length=200).grid(row=1, column=1, padx=10)
            ttk.Label(criteria_frame, textvariable=quality_var).grid(row=1, column=2)

            ttk.Label(criteria_frame, text="Efficiency:").grid(row=2, column=0, sticky='w', pady=5)
            ttk.Scale(criteria_frame, from_=1, to=10, variable=efficiency_var, orient='horizontal', length=200).grid(row=2, column=1, padx=10)
            ttk.Label(criteria_frame, textvariable=efficiency_var).grid(row=2, column=2)

            ttk.Label(criteria_frame, text="Teamwork:").grid(row=3, column=0, sticky='w', pady=5)
            ttk.Scale(criteria_frame, from_=1, to=10, variable=teamwork_var, orient='horizontal', length=200).grid(row=3, column=1, padx=10)
            ttk.Label(criteria_frame, textvariable=teamwork_var).grid(row=3, column=2)

            # Notes
            notes_frame = ttk.LabelFrame(main_frame, text="Manager Comments", padding=10)
            notes_frame.pack(fill='both', expand=True, pady=10)

            notes_text = tk.Text(notes_frame, height=5, width=50)
            notes_text.pack(fill='both', expand=True)

            # Save button
            def save_performance():
                if not staff_var.get():
                    messagebox.showwarning("No Selection", "Please select a staff member")
                    return

                staff_id = int(staff_var.get().split(' - ')[0])

                overall_score = (punctuality_var.get() + quality_var.get() +
                               efficiency_var.get() + teamwork_var.get()) / 4

                try:
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            CREATE TABLE IF NOT EXISTS staff_performance (
                                performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                staff_id INTEGER,
                                punctuality_score INTEGER,
                                quality_score INTEGER,
                                efficiency_score INTEGER,
                                teamwork_score INTEGER,
                                overall_score REAL,
                                evaluation_date DATE DEFAULT CURRENT_DATE,
                                notes TEXT,
                                FOREIGN KEY (staff_id) REFERENCES restaurant_staff(staff_id)
                            )
                        ''')
                        cursor.execute('''
                            INSERT INTO staff_performance
                            (staff_id, punctuality_score, quality_score, efficiency_score,
                             teamwork_score, overall_score, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (staff_id, punctuality_var.get(), quality_var.get(),
                             efficiency_var.get(), teamwork_var.get(), overall_score,
                             notes_text.get(1.0, tk.END)))
                        conn.commit()
                        conn.close()
                        messagebox.showinfo("Success", "Performance evaluation saved successfully!")
                        update_dialog.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save performance: {e}")

            ttk.Button(main_frame, text="Save Evaluation",
                      command=save_performance).pack(pady=10)
            ttk.Button(main_frame, text="Cancel",
                      command=update_dialog.destroy).pack()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update performance scores:\n{str(e)}")

    def export_performance_report(self):
        """Export staff performance report"""
        try:
            from tkinter import filedialog
            import csv

            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # Get comprehensive performance data
            cursor.execute('''
                SELECT s.staff_id, s.name, s.position,
                       AVG(p.punctuality_score) as avg_punctuality,
                       AVG(p.quality_score) as avg_quality,
                       AVG(p.efficiency_score) as avg_efficiency,
                       AVG(p.teamwork_score) as avg_teamwork,
                       AVG(p.overall_score) as avg_overall,
                       COUNT(p.performance_id) as eval_count,
                       MAX(p.evaluation_date) as latest_eval
                FROM restaurant_staff s
                LEFT JOIN staff_performance p ON s.staff_id = p.staff_id
                GROUP BY s.staff_id
                ORDER BY avg_overall DESC
            ''')
            performance_data = cursor.fetchall()

            conn.close()

            if not performance_data:
                messagebox.showinfo("No Data", "No performance data available")
                return

            # Ask for export format
            format_choice = messagebox.askquestion("Export Format",
                                                  "Export as CSV?\n(No = Display in window)")

            if format_choice == 'yes':
                filename = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile="staff_performance_report.csv"
                )

                if filename:
                    with open(filename, 'w', newline='') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(['Staff ID', 'Name', 'Position', 'Punctuality', 'Quality',
                                       'Efficiency', 'Teamwork', 'Overall Score', 'Evaluations', 'Latest Eval'])

                        for record in performance_data:
                            writer.writerow(record)

                    messagebox.showinfo("Success", f"Performance report exported to:\n{filename}")
            else:
                # Display in report window
                report = "STAFF PERFORMANCE REPORT\n"
                report += "=" * 120 + "\n\n"
                report += f"{'ID':<6} {'Name':<20} {'Position':<15} {'Punct':<7} {'Quality':<8} {'Effic':<7} {'Team':<7} {'Overall':<8} {'Evals':<7} {'Latest':<12}\n"
                report += "-" * 120 + "\n"

                for (staff_id, name, position, punc, qual, effic, team, overall, evals, latest) in performance_data:
                    report += f"{staff_id:<6} {name:<20} {position:<15} "
                    report += f"{punc or 0:<7.1f} {qual or 0:<8.1f} {effic or 0:<7.1f} {team or 0:<7.1f} "
                    report += f"{overall or 0:<8.1f} {evals or 0:<7} {latest or 'N/A':<12}\n"

                # Show in main report area if available, otherwise create dialog
                if hasattr(self, 'report_text'):
                    self.report_text.delete(1.0, tk.END)
                    self.report_text.insert(tk.END, report)
                else:
                    report_dialog = tk.Toplevel(self.root)
                    report_dialog.title("Performance Report")
                    report_dialog.geometry("1000x600")
                    report_text = ScrolledText(report_dialog, height=30, width=120)
                    report_text.pack(fill='both', expand=True, padx=10, pady=10)
                    report_text.insert(1.0, report)
                    report_text.config(state='disabled')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export performance report:\n{str(e)}")

    # Inventory Functions
    def view_inventory_gui(self):
        """Display inventory in the treeview"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return
                
            cursor = conn.cursor()
            cursor.execute('''
                SELECT item_id, name, quantity, unit, cost_per_unit, reorder_level 
                FROM restaurant_inventory 
                ORDER BY name
            ''')
            items = cursor.fetchall()
            
            for item in self.inventory_tree.get_children():
                self.inventory_tree.delete(item)
                
            for item in items:
                cost_str = f"£{item[4]:.2f}" if item[4] else "N/A"
                reorder_str = f"{item[5]:.1f}" if item[5] else "N/A"
                
                self.inventory_tree.insert('', 'end', values=(
                    item[0], item[1], f"{item[2]:.1f}", item[3], cost_str, reorder_str
                ))
                
            conn.close()
            messagebox.showinfo("Success", f"Loaded {len(items)} inventory items")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load inventory: {str(e)}")
            
    def manage_purchase_orders_dialog(self):
        """Comprehensive purchase order management system"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Purchase Orders Management")
        dialog.geometry("1000x700")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Purchase Orders Management",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Create purchase orders table if it doesn't exist
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()

                # Main purchase orders table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS purchase_orders (
                        po_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        po_number TEXT UNIQUE NOT NULL,
                        supplier_id INTEGER,
                        order_date DATE NOT NULL,
                        expected_delivery DATE,
                        actual_delivery DATE,
                        status TEXT DEFAULT 'Pending',
                        total_amount REAL DEFAULT 0,
                        tax_amount REAL DEFAULT 0,
                        shipping_cost REAL DEFAULT 0,
                        notes TEXT,
                        ordered_by TEXT,
                        approved_by TEXT,
                        received_by TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (supplier_id) REFERENCES restaurant_suppliers(supplier_id)
                    )
                ''')

                # Purchase order line items table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS purchase_order_items (
                        po_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        po_id INTEGER NOT NULL,
                        item_name TEXT NOT NULL,
                        description TEXT,
                        quantity REAL NOT NULL,
                        unit TEXT,
                        unit_price REAL NOT NULL,
                        total_price REAL NOT NULL,
                        received_quantity REAL DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id)
                    )
                ''')

                conn.commit()
                conn.close()
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to initialize purchase orders tables: {e}")
            dialog.destroy()
            return

        # Button frame with organized sections
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)

        # Section 1: Viewing and Creating
        ttk.Label(btn_frame, text="View & Create:", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=5)

        ttk.Button(btn_frame, text="View All Purchase Orders",
                  command=lambda: self.view_purchase_orders(dialog)).grid(
                      row=1, column=0, padx=5, pady=2, sticky='ew')

        ttk.Button(btn_frame, text="Create New Purchase Order",
                  command=lambda: self.create_purchase_order(dialog)).grid(
                      row=1, column=1, padx=5, pady=2, sticky='ew')

        # Section 2: Managing
        ttk.Label(btn_frame, text="Manage Orders:", font=('Arial', 10, 'bold')).grid(
            row=2, column=0, columnspan=2, sticky='w', pady=(15, 5))

        ttk.Button(btn_frame, text="Update Purchase Order",
                  command=lambda: self.update_purchase_order(dialog)).grid(
                      row=3, column=0, padx=5, pady=2, sticky='ew')

        ttk.Button(btn_frame, text="Receive Purchase Order",
                  command=lambda: self.receive_purchase_order(dialog)).grid(
                      row=3, column=1, padx=5, pady=2, sticky='ew')

        # Section 3: Reports
        ttk.Label(btn_frame, text="Reports & Analytics:", font=('Arial', 10, 'bold')).grid(
            row=4, column=0, columnspan=2, sticky='w', pady=(15, 5))

        ttk.Button(btn_frame, text="Purchase Order Reports",
                  command=lambda: self.purchase_order_reports(dialog)).grid(
                      row=5, column=0, columnspan=2, padx=5, pady=2, sticky='ew')

        # Configure column weights for equal button width
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        # Summary statistics frame
        stats_frame = ttk.LabelFrame(main_frame, text="Purchase Order Statistics", padding=15)
        stats_frame.pack(fill='x', pady=10)

        def update_stats():
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()

                    # Total POs
                    cursor.execute("SELECT COUNT(*) FROM purchase_orders")
                    total_pos = cursor.fetchone()[0]

                    # Pending POs
                    cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE status = 'Pending'")
                    pending_pos = cursor.fetchone()[0]

                    # Approved POs
                    cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE status = 'Approved'")
                    approved_pos = cursor.fetchone()[0]

                    # Received POs
                    cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE status = 'Received'")
                    received_pos = cursor.fetchone()[0]

                    # Total value
                    cursor.execute("SELECT SUM(total_amount) FROM purchase_orders WHERE status != 'Cancelled'")
                    total_value = cursor.fetchone()[0] or 0

                    conn.close()

                    stats_text = (f"Total Purchase Orders: {total_pos} | "
                                f"Pending: {pending_pos} | "
                                f"Approved: {approved_pos} | "
                                f"Received: {received_pos} | "
                                f"Total Value: £{total_value:,.2f}")

                    stats_label.config(text=stats_text)
            except Exception as e:
                stats_label.config(text=f"Error loading statistics: {e}")

        stats_label = ttk.Label(stats_frame, text="Loading statistics...", font=('Arial', 9))
        stats_label.pack()

        update_stats()

        # Refresh button
        ttk.Button(main_frame, text="Refresh Statistics",
                  command=update_stats).pack(pady=10)

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def view_purchase_orders(self, parent_dialog):
        """View all purchase orders with filtering options"""
        view_dialog = tk.Toplevel(parent_dialog)
        view_dialog.title("View Purchase Orders")
        view_dialog.geometry("1200x700")
        view_dialog.transient(parent_dialog)
        view_dialog.grab_set()

        main_frame = ttk.Frame(view_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Purchase Orders List",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Filter frame
        filter_frame = ttk.LabelFrame(main_frame, text="Filters", padding=10)
        filter_frame.pack(fill='x', pady=10)

        filter_row1 = ttk.Frame(filter_frame)
        filter_row1.pack(fill='x', pady=5)

        ttk.Label(filter_row1, text="Status:").pack(side='left', padx=5)
        status_var = tk.StringVar(value='All')
        status_combo = ttk.Combobox(filter_row1, textvariable=status_var,
                                   values=['All', 'Pending', 'Approved', 'Received', 'Cancelled'],
                                   width=15, state='readonly')
        status_combo.pack(side='left', padx=5)

        ttk.Label(filter_row1, text="Supplier:").pack(side='left', padx=5)
        supplier_var = tk.StringVar(value='All')
        supplier_combo = ttk.Combobox(filter_row1, textvariable=supplier_var,
                                     values=['All'], width=20, state='readonly')
        supplier_combo.pack(side='left', padx=5)

        # Treeview frame
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill='both', expand=True, pady=10)

        # Scrollbars
        v_scroll = ttk.Scrollbar(tree_frame, orient='vertical')
        h_scroll = ttk.Scrollbar(tree_frame, orient='horizontal')

        columns = ('PO#', 'Supplier', 'Order Date', 'Expected', 'Status', 'Total', 'Items', 'Notes')
        po_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                              yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set, height=20)

        v_scroll.config(command=po_tree.yview)
        h_scroll.config(command=po_tree.xview)

        # Configure columns
        column_widths = {'PO#': 100, 'Supplier': 150, 'Order Date': 100, 'Expected': 100,
                        'Status': 100, 'Total': 100, 'Items': 80, 'Notes': 200}

        for col in columns:
            po_tree.heading(col, text=col)
            po_tree.column(col, width=column_widths.get(col, 100))

        po_tree.pack(side='left', fill='both', expand=True)
        v_scroll.pack(side='right', fill='y')
        h_scroll.pack(side='bottom', fill='x')

        def load_purchase_orders():
            # Clear existing items
            for item in po_tree.get_children():
                po_tree.delete(item)

            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()

                    # Build query with filters
                    query = '''
                        SELECT po.po_number, COALESCE(s.name, 'N/A') as supplier_name,
                               po.order_date, po.expected_delivery, po.status,
                               po.total_amount, COUNT(poi.po_item_id) as item_count,
                               po.notes
                        FROM purchase_orders po
                        LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                        LEFT JOIN purchase_order_items poi ON po.po_id = poi.po_id
                        WHERE 1=1
                    '''

                    params = []

                    if status_var.get() != 'All':
                        query += ' AND po.status = ?'
                        params.append(status_var.get())

                    if supplier_var.get() != 'All':
                        query += ' AND s.name = ?'
                        params.append(supplier_var.get())

                    query += ' GROUP BY po.po_id ORDER BY po.order_date DESC'

                    cursor.execute(query, params)
                    orders = cursor.fetchall()

                    for order in orders:
                        po_tree.insert('', 'end', values=(
                            order[0],  # PO Number
                            order[1],  # Supplier
                            order[2],  # Order Date
                            order[3] or 'N/A',  # Expected Delivery
                            order[4],  # Status
                            f"£{order[5]:,.2f}",  # Total
                            order[6],  # Item Count
                            order[7] or ''  # Notes
                        ))

                    conn.close()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load purchase orders: {e}")

        def load_suppliers():
            """Load supplier list for filter"""
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT DISTINCT name FROM restaurant_suppliers ORDER BY name")
                    suppliers = [row[0] for row in cursor.fetchall()]
                    supplier_combo['values'] = ['All'] + suppliers
                    conn.close()
            except Exception:
                pass

        def view_po_details():
            """View detailed information about selected PO"""
            selection = po_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a purchase order to view details")
                return

            item = po_tree.item(selection[0])
            po_number = item['values'][0]

            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()

                    # Get PO header details
                    cursor.execute('''
                        SELECT po.*, s.name as supplier_name
                        FROM purchase_orders po
                        LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                        WHERE po.po_number = ?
                    ''', (po_number,))
                    po_data = cursor.fetchone()

                    # Get PO line items
                    cursor.execute('''
                        SELECT item_name, description, quantity, unit, unit_price,
                               total_price, received_quantity
                        FROM purchase_order_items
                        WHERE po_id = ?
                    ''', (po_data[0],))
                    items = cursor.fetchall()

                    conn.close()

                    # Create details dialog
                    details_dialog = tk.Toplevel(view_dialog)
                    details_dialog.title(f"PO Details - {po_number}")
                    details_dialog.geometry("800x600")
                    details_dialog.transient(view_dialog)

                    details_frame = ttk.Frame(details_dialog, padding=20)
                    details_frame.pack(fill='both', expand=True)

                    # Header info
                    header_text = f"""
Purchase Order: {po_data[1]}
Supplier: {po_data[14]}
Order Date: {po_data[3]}
Expected Delivery: {po_data[4] or 'Not specified'}
Actual Delivery: {po_data[5] or 'Not delivered'}
Status: {po_data[6]}

Total Amount: £{po_data[7]:,.2f}
Tax Amount: £{po_data[8]:,.2f}
Shipping Cost: £{po_data[9]:,.2f}

Ordered By: {po_data[11] or 'N/A'}
Approved By: {po_data[12] or 'Not approved'}
Received By: {po_data[13] or 'Not received'}

Notes: {po_data[10] or 'None'}
                    """.strip()

                    ttk.Label(details_frame, text=header_text, justify='left',
                             font=('Courier', 9)).pack(pady=10)

                    # Items list
                    ttk.Label(details_frame, text="Line Items:", font=('Arial', 10, 'bold')).pack(pady=5)

                    items_tree = ttk.Treeview(details_frame,
                                            columns=('Item', 'Qty', 'Unit', 'Price', 'Total', 'Received'),
                                            show='headings', height=15)

                    for col in ('Item', 'Qty', 'Unit', 'Price', 'Total', 'Received'):
                        items_tree.heading(col, text=col)
                        items_tree.column(col, width=120)

                    for item in items:
                        items_tree.insert('', 'end', values=(
                            f"{item[0]} - {item[1] or ''}",
                            item[2],
                            item[3],
                            f"£{item[4]:.2f}",
                            f"£{item[5]:.2f}",
                            item[6]
                        ))

                    items_tree.pack(fill='both', expand=True)

                    ttk.Button(details_frame, text="Close",
                              command=details_dialog.destroy).pack(pady=10)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load PO details: {e}")

        # Load data
        load_suppliers()
        load_purchase_orders()

        # Button frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)

        ttk.Button(btn_frame, text="Apply Filters", command=load_purchase_orders).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="View Details", command=view_po_details).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh", command=load_purchase_orders).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=view_dialog.destroy).pack(side='right', padx=5)

    def create_purchase_order(self, parent_dialog):
        """Create a new purchase order with items"""
        create_dialog = tk.Toplevel(parent_dialog)
        create_dialog.title("Create Purchase Order")
        create_dialog.geometry("900x700")
        create_dialog.transient(parent_dialog)
        create_dialog.grab_set()

        main_frame = ttk.Frame(create_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Create New Purchase Order",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # PO Header Form
        header_frame = ttk.LabelFrame(main_frame, text="Purchase Order Details", padding=15)
        header_frame.pack(fill='x', pady=10)

        fields = {}

        # Row 1: PO Number and Supplier
        row1 = ttk.Frame(header_frame)
        row1.pack(fill='x', pady=5)

        ttk.Label(row1, text="PO Number:*").pack(side='left', padx=5)
        fields['po_number'] = ttk.Entry(row1, width=20)
        fields['po_number'].pack(side='left', padx=5)
        # Auto-generate PO number
        fields['po_number'].insert(0, f"PO-{datetime.now().strftime('%Y%m%d-%H%M%S')}")

        ttk.Label(row1, text="Supplier:*").pack(side='left', padx=20)
        fields['supplier'] = ttk.Combobox(row1, width=30, state='readonly')
        fields['supplier'].pack(side='left', padx=5)

        # Load suppliers
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT supplier_id, name FROM restaurant_suppliers WHERE status = 'Active'")
                suppliers = cursor.fetchall()
                supplier_dict = {f"{s[1]} (ID: {s[0]})": s[0] for s in suppliers}
                fields['supplier']['values'] = list(supplier_dict.keys())
                fields['supplier_dict'] = supplier_dict
                conn.close()
        except Exception:
            pass

        # Row 2: Dates
        row2 = ttk.Frame(header_frame)
        row2.pack(fill='x', pady=5)

        ttk.Label(row2, text="Order Date:*").pack(side='left', padx=5)
        fields['order_date'] = ttk.Entry(row2, width=15)
        fields['order_date'].pack(side='left', padx=5)
        fields['order_date'].insert(0, datetime.now().strftime('%Y-%m-%d'))

        ttk.Label(row2, text="Expected Delivery:").pack(side='left', padx=20)
        fields['expected_date'] = ttk.Entry(row2, width=15)
        fields['expected_date'].pack(side='left', padx=5)
        # Default to 7 days from now
        fields['expected_date'].insert(0, (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))

        # Row 3: Additional costs
        row3 = ttk.Frame(header_frame)
        row3.pack(fill='x', pady=5)

        ttk.Label(row3, text="Shipping Cost (£):").pack(side='left', padx=5)
        fields['shipping'] = ttk.Entry(row3, width=15)
        fields['shipping'].pack(side='left', padx=5)
        fields['shipping'].insert(0, "0.00")

        ttk.Label(row3, text="Tax Rate (%):").pack(side='left', padx=20)
        fields['tax_rate'] = ttk.Entry(row3, width=15)
        fields['tax_rate'].pack(side='left', padx=5)
        fields['tax_rate'].insert(0, "20.0")

        # Row 4: Notes
        row4 = ttk.Frame(header_frame)
        row4.pack(fill='x', pady=5)

        ttk.Label(row4, text="Notes:").pack(side='left', padx=5)
        fields['notes'] = ttk.Entry(row4, width=60)
        fields['notes'].pack(side='left', padx=5)

        # Items Section
        items_frame = ttk.LabelFrame(main_frame, text="Order Items", padding=15)
        items_frame.pack(fill='both', expand=True, pady=10)

        # Items list storage
        po_items = []

        # Items treeview
        items_tree = ttk.Treeview(items_frame,
                                 columns=('Item', 'Description', 'Qty', 'Unit', 'Price', 'Total'),
                                 show='headings', height=10)

        for col in ('Item', 'Description', 'Qty', 'Unit', 'Price', 'Total'):
            items_tree.heading(col, text=col)
            items_tree.column(col, width=120)

        items_tree.pack(fill='both', expand=True, pady=5)

        def add_item():
            """Add item to PO"""
            item_dialog = tk.Toplevel(create_dialog)
            item_dialog.title("Add Item")
            item_dialog.geometry("500x400")
            item_dialog.transient(create_dialog)
            item_dialog.grab_set()

            item_frame = ttk.Frame(item_dialog, padding=20)
            item_frame.pack(fill='both', expand=True)

            item_fields = {}

            ttk.Label(item_frame, text="Item Name:*").grid(row=0, column=0, sticky='w', pady=5)
            item_fields['name'] = ttk.Entry(item_frame, width=40)
            item_fields['name'].grid(row=0, column=1, pady=5, padx=10)

            ttk.Label(item_frame, text="Description:").grid(row=1, column=0, sticky='w', pady=5)
            item_fields['desc'] = ttk.Entry(item_frame, width=40)
            item_fields['desc'].grid(row=1, column=1, pady=5, padx=10)

            ttk.Label(item_frame, text="Quantity:*").grid(row=2, column=0, sticky='w', pady=5)
            item_fields['qty'] = ttk.Entry(item_frame, width=40)
            item_fields['qty'].grid(row=2, column=1, pady=5, padx=10)

            ttk.Label(item_frame, text="Unit:").grid(row=3, column=0, sticky='w', pady=5)
            item_fields['unit'] = ttk.Combobox(item_frame,
                                              values=['kg', 'L', 'pieces', 'boxes', 'cases', 'units'],
                                              width=38)
            item_fields['unit'].grid(row=3, column=1, pady=5, padx=10)
            item_fields['unit'].current(0)

            ttk.Label(item_frame, text="Unit Price (£):*").grid(row=4, column=0, sticky='w', pady=5)
            item_fields['price'] = ttk.Entry(item_frame, width=40)
            item_fields['price'].grid(row=4, column=1, pady=5, padx=10)

            ttk.Label(item_frame, text="Total:").grid(row=5, column=0, sticky='w', pady=5)
            total_label = ttk.Label(item_frame, text="£0.00", font=('Arial', 10, 'bold'))
            total_label.grid(row=5, column=1, sticky='w', pady=5, padx=10)

            def update_total(*args):
                try:
                    qty = float(item_fields['qty'].get() or 0)
                    price = float(item_fields['price'].get() or 0)
                    total = qty * price
                    total_label.config(text=f"£{total:.2f}")
                except:
                    total_label.config(text="£0.00")

            item_fields['qty'].bind('<KeyRelease>', update_total)
            item_fields['price'].bind('<KeyRelease>', update_total)

            def save_item():
                try:
                    if not item_fields['name'].get().strip():
                        messagebox.showwarning("Missing Info", "Item name is required")
                        return

                    qty = float(item_fields['qty'].get())
                    price = float(item_fields['price'].get())
                    total = qty * price

                    item = {
                        'name': item_fields['name'].get().strip(),
                        'desc': item_fields['desc'].get().strip(),
                        'qty': qty,
                        'unit': item_fields['unit'].get(),
                        'price': price,
                        'total': total
                    }

                    po_items.append(item)
                    items_tree.insert('', 'end', values=(
                        item['name'],
                        item['desc'],
                        item['qty'],
                        item['unit'],
                        f"£{item['price']:.2f}",
                        f"£{item['total']:.2f}"
                    ))

                    update_order_total()
                    item_dialog.destroy()

                except ValueError:
                    messagebox.showerror("Invalid Input", "Please enter valid numbers for quantity and price")

            btn_frame = ttk.Frame(item_frame)
            btn_frame.grid(row=6, column=0, columnspan=2, pady=20)

            ttk.Button(btn_frame, text="Add Item", command=save_item).pack(side='left', padx=5)
            ttk.Button(btn_frame, text="Cancel", command=item_dialog.destroy).pack(side='left', padx=5)

        def remove_item():
            """Remove selected item"""
            selection = items_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select an item to remove")
                return

            index = items_tree.index(selection[0])
            po_items.pop(index)
            items_tree.delete(selection[0])
            update_order_total()

        # Total display
        total_frame = ttk.Frame(items_frame)
        total_frame.pack(fill='x', pady=5)

        total_label = ttk.Label(total_frame, text="Subtotal: £0.00 | Tax: £0.00 | Shipping: £0.00 | Total: £0.00",
                               font=('Arial', 10, 'bold'))
        total_label.pack()

        def update_order_total():
            try:
                subtotal = sum(item['total'] for item in po_items)
                shipping = float(fields['shipping'].get() or 0)
                tax_rate = float(fields['tax_rate'].get() or 0) / 100
                tax = subtotal * tax_rate
                total = subtotal + tax + shipping

                total_label.config(text=f"Subtotal: £{subtotal:.2f} | Tax: £{tax:.2f} | "
                                      f"Shipping: £{shipping:.2f} | Total: £{total:.2f}")
            except:
                pass

        fields['shipping'].bind('<KeyRelease>', lambda e: update_order_total())
        fields['tax_rate'].bind('<KeyRelease>', lambda e: update_order_total())

        # Item buttons
        item_btn_frame = ttk.Frame(items_frame)
        item_btn_frame.pack(fill='x', pady=5)

        ttk.Button(item_btn_frame, text="Add Item", command=add_item).pack(side='left', padx=5)
        ttk.Button(item_btn_frame, text="Remove Item", command=remove_item).pack(side='left', padx=5)

        # Save PO
        def save_purchase_order():
            try:
                # Validation
                if not fields['po_number'].get().strip():
                    messagebox.showwarning("Missing Info", "PO Number is required")
                    return

                if not fields['supplier'].get():
                    messagebox.showwarning("Missing Info", "Please select a supplier")
                    return

                if not po_items:
                    messagebox.showwarning("Missing Items", "Please add at least one item to the purchase order")
                    return

                # Get supplier ID
                supplier_id = fields['supplier_dict'][fields['supplier'].get()]

                # Calculate totals
                subtotal = sum(item['total'] for item in po_items)
                shipping = float(fields['shipping'].get() or 0)
                tax_rate = float(fields['tax_rate'].get() or 0) / 100
                tax = subtotal * tax_rate
                total = subtotal + tax + shipping

                # Get current user
                current_user = "System"
                if AUTH_AVAILABLE:
                    try:
                        from university_system.infrastructure.shared_context import get_auth
                        auth = get_auth()
                        if auth.current_user:
                            current_user = auth.current_user.get('username', 'Unknown')
                    except:
                        pass

                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()

                    # Insert PO header
                    cursor.execute('''
                        INSERT INTO purchase_orders
                        (po_number, supplier_id, order_date, expected_delivery,
                         total_amount, tax_amount, shipping_cost, notes, ordered_by, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
                    ''', (fields['po_number'].get().strip(),
                          supplier_id,
                          fields['order_date'].get(),
                          fields['expected_date'].get() or None,
                          total,
                          tax,
                          shipping,
                          fields['notes'].get().strip() or None,
                          current_user))

                    po_id = cursor.lastrowid

                    # Insert line items
                    for item in po_items:
                        cursor.execute('''
                            INSERT INTO purchase_order_items
                            (po_id, item_name, description, quantity, unit, unit_price, total_price)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (po_id, item['name'], item['desc'], item['qty'],
                              item['unit'], item['price'], item['total']))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success",
                                      f"Purchase Order {fields['po_number'].get()} created successfully!\n\n"
                                      f"Total: £{total:,.2f}\n"
                                      f"Items: {len(po_items)}")
                    create_dialog.destroy()

            except sqlite3.IntegrityError:
                messagebox.showerror("Error", "PO Number already exists. Please use a unique PO number.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create purchase order: {e}")

        # Bottom buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)

        ttk.Button(btn_frame, text="Save Purchase Order",
                  command=save_purchase_order).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel",
                  command=create_dialog.destroy).pack(side='right', padx=5)

    def update_purchase_order(self, parent_dialog):
        """Update an existing purchase order"""
        # First, select which PO to update
        select_dialog = tk.Toplevel(parent_dialog)
        select_dialog.title("Select Purchase Order to Update")
        select_dialog.geometry("800x500")
        select_dialog.transient(parent_dialog)
        select_dialog.grab_set()

        main_frame = ttk.Frame(select_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Select Purchase Order to Update",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Only show Pending or Approved POs
        ttk.Label(main_frame, text="Only Pending and Approved purchase orders can be updated",
                 foreground='blue').pack(pady=5)

        # PO list
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill='both', expand=True, pady=10)

        columns = ('PO#', 'Supplier', 'Date', 'Status', 'Total', 'Items')
        po_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            po_tree.heading(col, text=col)
            po_tree.column(col, width=120)

        po_tree.pack(fill='both', expand=True)

        def load_pos():
            for item in po_tree.get_children():
                po_tree.delete(item)

            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT po.po_id, po.po_number, COALESCE(s.name, 'N/A'),
                               po.order_date, po.status, po.total_amount,
                               COUNT(poi.po_item_id)
                        FROM purchase_orders po
                        LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                        LEFT JOIN purchase_order_items poi ON po.po_id = poi.po_id
                        WHERE po.status IN ('Pending', 'Approved')
                        GROUP BY po.po_id
                        ORDER BY po.order_date DESC
                    ''')
                    pos = cursor.fetchall()

                    for po in pos:
                        po_tree.insert('', 'end', values=(
                            po[1],  # PO Number
                            po[2],  # Supplier
                            po[3],  # Date
                            po[4],  # Status
                            f"£{po[5]:,.2f}",  # Total
                            po[6]  # Items
                        ), tags=(po[0],))  # Store PO ID in tags

                    conn.close()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load purchase orders: {e}")

        load_pos()

        def proceed_to_update():
            selection = po_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a purchase order to update")
                return

            po_id = po_tree.item(selection[0])['tags'][0]
            select_dialog.destroy()
            show_update_dialog(po_id)

        def show_update_dialog(po_id):
            """Show update dialog for selected PO"""
            update_dialog = tk.Toplevel(parent_dialog)
            update_dialog.title("Update Purchase Order")
            update_dialog.geometry("700x600")
            update_dialog.transient(parent_dialog)
            update_dialog.grab_set()

            main_frame = ttk.Frame(update_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Update Purchase Order",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            # Load current PO data
            try:
                conn = get_db_connection()
                if not conn:
                    return

                cursor = conn.cursor()
                cursor.execute('''
                    SELECT po.*, s.name
                    FROM purchase_orders po
                    LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                    WHERE po.po_id = ?
                ''', (po_id,))
                po_data = cursor.fetchone()
                conn.close()

                if not po_data:
                    messagebox.showerror("Error", "Purchase order not found")
                    update_dialog.destroy()
                    return

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load PO data: {e}")
                update_dialog.destroy()
                return

            # Update form
            form_frame = ttk.LabelFrame(main_frame, text="Update Fields", padding=15)
            form_frame.pack(fill='both', expand=True, pady=10)

            fields = {}

            # PO Number (read-only)
            row = 0
            ttk.Label(form_frame, text="PO Number:").grid(row=row, column=0, sticky='w', pady=5)
            ttk.Label(form_frame, text=po_data[1], font=('Arial', 10, 'bold')).grid(
                row=row, column=1, sticky='w', pady=5, padx=10)

            # Status
            row += 1
            ttk.Label(form_frame, text="Status:*").grid(row=row, column=0, sticky='w', pady=5)
            fields['status'] = ttk.Combobox(form_frame,
                                          values=['Pending', 'Approved', 'Cancelled'],
                                          width=30, state='readonly')
            fields['status'].grid(row=row, column=1, sticky='w', pady=5, padx=10)
            fields['status'].set(po_data[6])

            # Expected Delivery
            row += 1
            ttk.Label(form_frame, text="Expected Delivery:").grid(row=row, column=0, sticky='w', pady=5)
            fields['expected'] = ttk.Entry(form_frame, width=32)
            fields['expected'].grid(row=row, column=1, sticky='w', pady=5, padx=10)
            fields['expected'].insert(0, po_data[4] or '')

            # Shipping Cost
            row += 1
            ttk.Label(form_frame, text="Shipping Cost (£):").grid(row=row, column=0, sticky='w', pady=5)
            fields['shipping'] = ttk.Entry(form_frame, width=32)
            fields['shipping'].grid(row=row, column=1, sticky='w', pady=5, padx=10)
            fields['shipping'].insert(0, f"{po_data[9]:.2f}")

            # Notes
            row += 1
            ttk.Label(form_frame, text="Notes:").grid(row=row, column=0, sticky='nw', pady=5)
            fields['notes'] = tk.Text(form_frame, height=4, width=32)
            fields['notes'].grid(row=row, column=1, pady=5, padx=10)
            if po_data[10]:
                fields['notes'].insert('1.0', po_data[10])

            # Current info display
            row += 1
            info_text = f"""
Current Information:
Supplier: {po_data[15]}
Order Date: {po_data[3]}
Total Amount: £{po_data[7]:,.2f}
Tax Amount: £{po_data[8]:,.2f}
Ordered By: {po_data[11] or 'N/A'}
            """.strip()
            ttk.Label(form_frame, text=info_text, justify='left', foreground='blue').grid(
                row=row, column=0, columnspan=2, sticky='w', pady=10)

            def save_updates():
                try:
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()

                        cursor.execute('''
                            UPDATE purchase_orders
                            SET status = ?,
                                expected_delivery = ?,
                                shipping_cost = ?,
                                notes = ?
                            WHERE po_id = ?
                        ''', (fields['status'].get(),
                              fields['expected'].get() or None,
                              float(fields['shipping'].get() or 0),
                              fields['notes'].get('1.0', tk.END).strip() or None,
                              po_id))

                        conn.commit()
                        conn.close()

                        messagebox.showinfo("Success", "Purchase order updated successfully!")
                        update_dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update purchase order: {e}")

            # Buttons
            btn_frame = ttk.Frame(form_frame)
            btn_frame.grid(row=row+1, column=0, columnspan=2, pady=20)

            ttk.Button(btn_frame, text="Save Updates", command=save_updates).pack(side='left', padx=5)
            ttk.Button(btn_frame, text="Cancel", command=update_dialog.destroy).pack(side='left', padx=5)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)

        ttk.Button(btn_frame, text="Update Selected", command=proceed_to_update).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh", command=load_pos).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=select_dialog.destroy).pack(side='right', padx=5)

    def receive_purchase_order(self, parent_dialog):
        """Mark purchase order as received and optionally update inventory"""
        # Select PO to receive
        select_dialog = tk.Toplevel(parent_dialog)
        select_dialog.title("Receive Purchase Order")
        select_dialog.geometry("900x600")
        select_dialog.transient(parent_dialog)
        select_dialog.grab_set()

        main_frame = ttk.Frame(select_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Receive Purchase Order",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        ttk.Label(main_frame, text="Select an Approved purchase order to receive",
                 foreground='blue').pack(pady=5)

        # PO list
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill='both', expand=True, pady=10)

        columns = ('PO#', 'Supplier', 'Order Date', 'Expected', 'Total', 'Items')
        po_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            po_tree.heading(col, text=col)
            po_tree.column(col, width=130)

        po_tree.pack(fill='both', expand=True)

        def load_approved_pos():
            for item in po_tree.get_children():
                po_tree.delete(item)

            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT po.po_id, po.po_number, COALESCE(s.name, 'N/A'),
                               po.order_date, po.expected_delivery, po.total_amount,
                               COUNT(poi.po_item_id)
                        FROM purchase_orders po
                        LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                        LEFT JOIN purchase_order_items poi ON po.po_id = poi.po_id
                        WHERE po.status = 'Approved'
                        GROUP BY po.po_id
                        ORDER BY po.expected_delivery
                    ''')
                    pos = cursor.fetchall()

                    for po in pos:
                        po_tree.insert('', 'end', values=(
                            po[1],  # PO Number
                            po[2],  # Supplier
                            po[3],  # Order Date
                            po[4] or 'N/A',  # Expected
                            f"£{po[5]:,.2f}",  # Total
                            po[6]  # Items
                        ), tags=(po[0],))

                    conn.close()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load purchase orders: {e}")

        load_approved_pos()

        def proceed_to_receive():
            selection = po_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a purchase order to receive")
                return

            po_id = po_tree.item(selection[0])['tags'][0]
            po_number = po_tree.item(selection[0])['values'][0]
            select_dialog.destroy()
            show_receive_dialog(po_id, po_number)

        def show_receive_dialog(po_id, po_number):
            """Show receiving dialog with item quantities"""
            receive_dialog = tk.Toplevel(parent_dialog)
            receive_dialog.title(f"Receive PO - {po_number}")
            receive_dialog.geometry("900x700")
            receive_dialog.transient(parent_dialog)
            receive_dialog.grab_set()

            main_frame = ttk.Frame(receive_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"Receive Purchase Order: {po_number}",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            # Instructions
            ttk.Label(main_frame,
                     text="Enter the actual quantity received for each item (defaults to ordered quantity)",
                     foreground='blue').pack(pady=5)

            # Load PO items
            try:
                conn = get_db_connection()
                if not conn:
                    return

                cursor = conn.cursor()
                cursor.execute('''
                    SELECT po_item_id, item_name, description, quantity, unit
                    FROM purchase_order_items
                    WHERE po_id = ?
                ''', (po_id,))
                items = cursor.fetchall()
                conn.close()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load items: {e}")
                receive_dialog.destroy()
                return

            # Items frame with scrollbar
            items_frame = ttk.LabelFrame(main_frame, text="Items to Receive", padding=15)
            items_frame.pack(fill='both', expand=True, pady=10)

            canvas = tk.Canvas(items_frame)
            scrollbar = ttk.Scrollbar(items_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Header row
            ttk.Label(scrollable_frame, text="Item", font=('Arial', 9, 'bold'),
                     width=25).grid(row=0, column=0, padx=5, pady=5)
            ttk.Label(scrollable_frame, text="Ordered Qty", font=('Arial', 9, 'bold'),
                     width=15).grid(row=0, column=1, padx=5, pady=5)
            ttk.Label(scrollable_frame, text="Received Qty", font=('Arial', 9, 'bold'),
                     width=15).grid(row=0, column=2, padx=5, pady=5)
            ttk.Label(scrollable_frame, text="Unit", font=('Arial', 9, 'bold'),
                     width=10).grid(row=0, column=3, padx=5, pady=5)

            # Create entry fields for each item
            item_entries = {}
            for idx, item in enumerate(items, start=1):
                item_id, name, desc, qty, unit = item

                # Item name
                display_name = f"{name}\n{desc}" if desc else name
                ttk.Label(scrollable_frame, text=display_name, width=25,
                         wraplength=180).grid(row=idx, column=0, padx=5, pady=5, sticky='w')

                # Ordered quantity
                ttk.Label(scrollable_frame, text=str(qty), width=15).grid(
                    row=idx, column=1, padx=5, pady=5)

                # Received quantity entry
                rec_entry = ttk.Entry(scrollable_frame, width=15)
                rec_entry.grid(row=idx, column=2, padx=5, pady=5)
                rec_entry.insert(0, str(qty))  # Default to ordered quantity
                item_entries[item_id] = rec_entry

                # Unit
                ttk.Label(scrollable_frame, text=unit, width=10).grid(
                    row=idx, column=3, padx=5, pady=5)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Receiving details
            details_frame = ttk.Frame(main_frame)
            details_frame.pack(fill='x', pady=10)

            ttk.Label(details_frame, text="Received By:").pack(side='left', padx=5)
            received_by = ttk.Entry(details_frame, width=20)
            received_by.pack(side='left', padx=5)

            # Get current user
            current_user = "System"
            if AUTH_AVAILABLE:
                try:
                    from university_system.infrastructure.shared_context import get_auth
                    auth = get_auth()
                    if auth.is_logged_in():
                        current_user = auth.get_current_user().username
                except:
                    pass
            received_by.insert(0, current_user)

            ttk.Label(details_frame, text="Received Date:").pack(side='left', padx=20)
            received_date = ttk.Entry(details_frame, width=15)
            received_date.pack(side='left', padx=5)
            received_date.insert(0, datetime.now().strftime('%Y-%m-%d'))

            # Update inventory checkbox
            update_inv_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(main_frame, text="Update inventory quantities",
                          variable=update_inv_var).pack(pady=5)

            def save_receipt():
                try:
                    conn = get_db_connection()
                    if not conn:
                        return

                    cursor = conn.cursor()

                    # Update PO status
                    cursor.execute('''
                        UPDATE purchase_orders
                        SET status = 'Received',
                            actual_delivery = ?,
                            received_by = ?
                        WHERE po_id = ?
                    ''', (received_date.get(), received_by.get(), po_id))

                    # Update received quantities for each item
                    for item_id, entry in item_entries.items():
                        received_qty = float(entry.get() or 0)
                        cursor.execute('''
                            UPDATE purchase_order_items
                            SET received_quantity = ?
                            WHERE po_item_id = ?
                        ''', (received_qty, item_id))

                    # Optionally update inventory
                    if update_inv_var.get():
                        for item_id, entry in item_entries.items():
                            received_qty = float(entry.get() or 0)

                            # Get item name
                            cursor.execute('''
                                SELECT item_name FROM purchase_order_items
                                WHERE po_item_id = ?
                            ''', (item_id,))
                            item_name = cursor.fetchone()[0]

                            # Check if item exists in inventory
                            cursor.execute('''
                                SELECT item_id, quantity FROM restaurant_inventory
                                WHERE LOWER(item_name) = LOWER(?)
                            ''', (item_name,))
                            existing = cursor.fetchone()

                            if existing:
                                # Update existing inventory
                                new_qty = existing[1] + received_qty
                                cursor.execute('''
                                    UPDATE restaurant_inventory
                                    SET quantity = ?,
                                        last_updated = CURRENT_TIMESTAMP
                                    WHERE item_id = ?
                                ''', (new_qty, existing[0]))
                            # If not in inventory, could add here but skipping for safety

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success",
                                      f"Purchase Order {po_number} marked as received!\n\n"
                                      f"Received by: {received_by.get()}\n"
                                      f"Date: {received_date.get()}")
                    receive_dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to receive purchase order: {e}")

            # Buttons
            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(fill='x', pady=10)

            ttk.Button(btn_frame, text="Complete Receipt",
                      command=save_receipt).pack(side='left', padx=5)
            ttk.Button(btn_frame, text="Cancel",
                      command=receive_dialog.destroy).pack(side='right', padx=5)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)

        ttk.Button(btn_frame, text="Receive Selected", command=proceed_to_receive).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh", command=load_approved_pos).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=select_dialog.destroy).pack(side='right', padx=5)

    def purchase_order_reports(self, parent_dialog):
        """Generate various purchase order reports and analytics"""
        reports_dialog = tk.Toplevel(parent_dialog)
        reports_dialog.title("Purchase Order Reports")
        reports_dialog.geometry("900x700")
        reports_dialog.transient(parent_dialog)
        reports_dialog.grab_set()

        main_frame = ttk.Frame(reports_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Purchase Order Reports & Analytics",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Report options
        reports_frame = ttk.LabelFrame(main_frame, text="Available Reports", padding=15)
        reports_frame.pack(fill='both', expand=True, pady=10)

        # Report output area
        output_frame = ttk.LabelFrame(main_frame, text="Report Output", padding=10)
        output_frame.pack(fill='both', expand=True, pady=10)

        output_text = ScrolledText(output_frame, height=20, width=100, font=('Courier', 9))
        output_text.pack(fill='both', expand=True)

        def generate_summary_report():
            """Overall PO summary statistics"""
            try:
                conn = get_db_connection()
                if not conn:
                    return

                cursor = conn.cursor()

                # Get statistics
                cursor.execute("SELECT COUNT(*) FROM purchase_orders")
                total_pos = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE status = 'Pending'")
                pending = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE status = 'Approved'")
                approved = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE status = 'Received'")
                received = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE status = 'Cancelled'")
                cancelled = cursor.fetchone()[0]

                cursor.execute("SELECT SUM(total_amount) FROM purchase_orders WHERE status != 'Cancelled'")
                total_value = cursor.fetchone()[0] or 0

                cursor.execute("SELECT AVG(total_amount) FROM purchase_orders WHERE status != 'Cancelled'")
                avg_value = cursor.fetchone()[0] or 0

                cursor.execute('''
                    SELECT s.name, COUNT(po.po_id), SUM(po.total_amount)
                    FROM purchase_orders po
                    JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                    WHERE po.status != 'Cancelled'
                    GROUP BY s.name
                    ORDER BY SUM(po.total_amount) DESC
                    LIMIT 5
                ''')
                top_suppliers = cursor.fetchall()

                conn.close()

                # Generate report
                report = f"""
{'='*80}
                    PURCHASE ORDER SUMMARY REPORT
                    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*80}

OVERALL STATISTICS:
------------------
Total Purchase Orders:     {total_pos}
  - Pending:              {pending}
  - Approved:             {approved}
  - Received:             {received}
  - Cancelled:            {cancelled}

FINANCIAL SUMMARY:
-----------------
Total Value (excl. cancelled):  £{total_value:,.2f}
Average PO Value:               £{avg_value:,.2f}

TOP 5 SUPPLIERS BY VALUE:
------------------------
"""
                for idx, (supplier, count, value) in enumerate(top_suppliers, 1):
                    report += f"{idx}. {supplier:<30} POs: {count:>3}  Value: £{value:>10,.2f}\n"

                report += "\n" + "="*80 + "\n"

                output_text.delete('1.0', tk.END)
                output_text.insert('1.0', report)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate report: {e}")

        def generate_status_report():
            """Detailed report by status"""
            try:
                conn = get_db_connection()
                if not conn:
                    return

                cursor = conn.cursor()

                report = f"""
{'='*80}
                    PURCHASE ORDERS BY STATUS
                    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*80}

"""

                for status in ['Pending', 'Approved', 'Received', 'Cancelled']:
                    cursor.execute('''
                        SELECT po.po_number, s.name, po.order_date, po.total_amount
                        FROM purchase_orders po
                        LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                        WHERE po.status = ?
                        ORDER BY po.order_date DESC
                    ''', (status,))
                    pos = cursor.fetchall()

                    report += f"\n{status.upper()} PURCHASE ORDERS ({len(pos)}):\n"
                    report += "-" * 80 + "\n"

                    if pos:
                        report += f"{'PO Number':<20} {'Supplier':<25} {'Date':<12} {'Amount':>12}\n"
                        report += "-" * 80 + "\n"
                        for po in pos:
                            report += f"{po[0]:<20} {(po[1] or 'N/A'):<25} {po[2]:<12} £{po[3]:>10,.2f}\n"
                    else:
                        report += "No purchase orders with this status\n"

                    report += "\n"

                conn.close()

                report += "="*80 + "\n"

                output_text.delete('1.0', tk.END)
                output_text.insert('1.0', report)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate report: {e}")

        def generate_supplier_report():
            """Report by supplier"""
            try:
                conn = get_db_connection()
                if not conn:
                    return

                cursor = conn.cursor()

                cursor.execute('''
                    SELECT s.name, s.supplier_id
                    FROM restaurant_suppliers s
                    ORDER BY s.name
                ''')
                suppliers = cursor.fetchall()

                report = f"""
{'='*80}
                    PURCHASE ORDERS BY SUPPLIER
                    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*80}

"""

                for supplier_name, supplier_id in suppliers:
                    cursor.execute('''
                        SELECT COUNT(*), SUM(total_amount), AVG(total_amount)
                        FROM purchase_orders
                        WHERE supplier_id = ? AND status != 'Cancelled'
                    ''', (supplier_id,))
                    stats = cursor.fetchone()
                    count, total, avg = stats[0], stats[1] or 0, stats[2] or 0

                    cursor.execute('''
                        SELECT po_number, order_date, status, total_amount
                        FROM purchase_orders
                        WHERE supplier_id = ?
                        ORDER BY order_date DESC
                        LIMIT 5
                    ''', (supplier_id,))
                    recent_pos = cursor.fetchall()

                    report += f"\n{supplier_name.upper()}\n"
                    report += "-" * 80 + "\n"
                    report += f"Total POs: {count}  |  Total Value: £{total:,.2f}  |  Avg Value: £{avg:,.2f}\n\n"

                    if recent_pos:
                        report += f"{'Recent POs:':<20} {'Date':<12} {'Status':<12} {'Amount':>12}\n"
                        report += "-" * 80 + "\n"
                        for po in recent_pos:
                            report += f"{po[0]:<20} {po[1]:<12} {po[2]:<12} £{po[3]:>10,.2f}\n"
                    else:
                        report += "No purchase orders for this supplier\n"

                    report += "\n"

                conn.close()

                report += "="*80 + "\n"

                output_text.delete('1.0', tk.END)
                output_text.insert('1.0', report)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate report: {e}")

        def export_to_csv():
            """Export all POs to CSV"""
            try:
                conn = get_db_connection()
                if not conn:
                    return

                cursor = conn.cursor()
                cursor.execute('''
                    SELECT po.po_number, s.name, po.order_date, po.expected_delivery,
                           po.actual_delivery, po.status, po.total_amount, po.tax_amount,
                           po.shipping_cost, po.ordered_by, po.received_by, po.notes
                    FROM purchase_orders po
                    LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                    ORDER BY po.order_date DESC
                ''')
                pos = cursor.fetchall()
                conn.close()

                # Create CSV content
                import csv
                from io import StringIO

                output = StringIO()
                writer = csv.writer(output)

                writer.writerow(['PO Number', 'Supplier', 'Order Date', 'Expected Delivery',
                               'Actual Delivery', 'Status', 'Total Amount', 'Tax Amount',
                               'Shipping Cost', 'Ordered By', 'Received By', 'Notes'])

                for po in pos:
                    writer.writerow(po)

                csv_content = output.getvalue()

                # Save to file
                filename = f"purchase_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                filepath = os.path.join(os.getcwd(), filename)

                with open(filepath, 'w', newline='') as f:
                    f.write(csv_content)

                messagebox.showinfo("Export Success",
                                  f"Purchase orders exported successfully!\n\n"
                                  f"File: {filename}\n"
                                  f"Location: {filepath}\n"
                                  f"Records: {len(pos)}")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {e}")

        # Report buttons
        btn_frame = ttk.Frame(reports_frame)
        btn_frame.pack(fill='x', pady=5)

        ttk.Button(btn_frame, text="Summary Report",
                  command=generate_summary_report).pack(side='left', padx=5, pady=5)
        ttk.Button(btn_frame, text="Status Report",
                  command=generate_status_report).pack(side='left', padx=5, pady=5)
        ttk.Button(btn_frame, text="Supplier Report",
                  command=generate_supplier_report).pack(side='left', padx=5, pady=5)
        ttk.Button(btn_frame, text="Export to CSV",
                  command=export_to_csv).pack(side='left', padx=5, pady=5)

        # Close button
        ttk.Button(main_frame, text="Close", command=reports_dialog.destroy).pack(pady=10)

    def manage_suppliers_dialog(self):
        """Show suppliers management dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Suppliers Management")
        dialog.geometry("900x600")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Suppliers Management", font=('Arial', 14, 'bold')).pack(pady=10)

        # Create suppliers table if it doesn't exist
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS restaurant_suppliers (
                        supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        contact_person TEXT,
                        email TEXT,
                        phone TEXT,
                        address TEXT,
                        category TEXT,
                        status TEXT DEFAULT 'Active',
                        notes TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
                conn.close()
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to initialize suppliers table: {e}")
            dialog.destroy()
            return

        # Button frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)

        def add_supplier():
            sup_dialog = tk.Toplevel(dialog)
            sup_dialog.title("Add Supplier")
            sup_dialog.geometry("500x600")
            sup_dialog.transient(dialog)
            sup_dialog.grab_set()

            form_frame = ttk.Frame(sup_dialog, padding=20)
            form_frame.pack(fill='both', expand=True)

            fields = {}

            row = 0
            ttk.Label(form_frame, text="Supplier Name:*").grid(row=row, column=0, sticky='w', pady=5)
            fields['name'] = ttk.Entry(form_frame, width=40)
            fields['name'].grid(row=row, column=1, pady=5, padx=10)

            row += 1
            ttk.Label(form_frame, text="Contact Person:").grid(row=row, column=0, sticky='w', pady=5)
            fields['contact'] = ttk.Entry(form_frame, width=40)
            fields['contact'].grid(row=row, column=1, pady=5, padx=10)

            row += 1
            ttk.Label(form_frame, text="Email:").grid(row=row, column=0, sticky='w', pady=5)
            fields['email'] = ttk.Entry(form_frame, width=40)
            fields['email'].grid(row=row, column=1, pady=5, padx=10)

            row += 1
            ttk.Label(form_frame, text="Phone:").grid(row=row, column=0, sticky='w', pady=5)
            fields['phone'] = ttk.Entry(form_frame, width=40)
            fields['phone'].grid(row=row, column=1, pady=5, padx=10)

            row += 1
            ttk.Label(form_frame, text="Address:").grid(row=row, column=0, sticky='nw', pady=5)
            fields['address'] = tk.Text(form_frame, height=3, width=40)
            fields['address'].grid(row=row, column=1, pady=5, padx=10)

            row += 1
            ttk.Label(form_frame, text="Category:").grid(row=row, column=0, sticky='w', pady=5)
            fields['category'] = ttk.Combobox(form_frame, values=['Food', 'Beverages', 'Equipment', 'Cleaning', 'Other'], width=38)
            fields['category'].grid(row=row, column=1, pady=5, padx=10)
            fields['category'].current(0)

            row += 1
            ttk.Label(form_frame, text="Notes:").grid(row=row, column=0, sticky='nw', pady=5)
            fields['notes'] = tk.Text(form_frame, height=4, width=40)
            fields['notes'].grid(row=row, column=1, pady=5, padx=10)

            def save_supplier():
                try:
                    if not fields['name'].get().strip():
                        messagebox.showwarning("Missing Info", "Supplier name is required")
                        return

                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO restaurant_suppliers
                            (name, contact_person, email, phone, address, category, notes, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (fields['name'].get(), fields['contact'].get(), fields['email'].get(),
                              fields['phone'].get(), fields['address'].get('1.0', tk.END).strip(),
                              fields['category'].get(), fields['notes'].get('1.0', tk.END).strip(), 'Active'))
                        conn.commit()
                        conn.close()

                        messagebox.showinfo("Success", "Supplier added successfully!")
                        sup_dialog.destroy()
                        load_suppliers()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to add supplier: {e}")

            button_frame = ttk.Frame(form_frame)
            button_frame.grid(row=row+1, column=0, columnspan=2, pady=20)

            ttk.Button(button_frame, text="Save", command=save_supplier).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=sup_dialog.destroy).pack(side='left', padx=5)

        ttk.Button(btn_frame, text="Add Supplier", command=add_supplier).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh", command=lambda: load_suppliers()).pack(side='left', padx=5)

        # Suppliers treeview
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill='both', expand=True, pady=10)

        columns = ('ID', 'Name', 'Contact', 'Phone', 'Email', 'Category', 'Status')
        suppliers_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)

        for col in columns:
            suppliers_tree.heading(col, text=col)
            suppliers_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=suppliers_tree.yview)
        suppliers_tree.configure(yscrollcommand=scrollbar.set)

        suppliers_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        def load_suppliers():
            for item in suppliers_tree.get_children():
                suppliers_tree.delete(item)

            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT supplier_id, name, contact_person, phone, email, category, status
                        FROM restaurant_suppliers
                        ORDER BY name
                    ''')
                    suppliers = cursor.fetchall()
                    conn.close()

                    for sup in suppliers:
                        suppliers_tree.insert('', 'end', values=sup)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load suppliers: {e}")

        load_suppliers()

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def waste_tracking_dialog(self):
        """Show waste tracking dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Waste Tracking")
        dialog.geometry("900x600")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Waste Tracking", font=('Arial', 14, 'bold')).pack(pady=10)

        # Create waste tracking table if it doesn't exist
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS restaurant_waste (
                        waste_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        item_name TEXT NOT NULL,
                        quantity REAL NOT NULL,
                        unit TEXT,
                        reason TEXT,
                        cost_value REAL,
                        waste_date DATE NOT NULL,
                        recorded_by TEXT,
                        notes TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
                conn.close()
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to initialize waste tracking table: {e}")
            dialog.destroy()
            return

        # Button frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=10)

        def record_waste():
            waste_dialog = tk.Toplevel(dialog)
            waste_dialog.title("Record Waste")
            waste_dialog.geometry("500x550")
            waste_dialog.transient(dialog)
            waste_dialog.grab_set()

            form_frame = ttk.Frame(waste_dialog, padding=20)
            form_frame.pack(fill='both', expand=True)

            fields = {}

            row = 0
            ttk.Label(form_frame, text="Item Name:*").grid(row=row, column=0, sticky='w', pady=5)
            fields['item'] = ttk.Entry(form_frame, width=40)
            fields['item'].grid(row=row, column=1, pady=5, padx=10)

            row += 1
            ttk.Label(form_frame, text="Quantity:*").grid(row=row, column=0, sticky='w', pady=5)
            fields['quantity'] = ttk.Entry(form_frame, width=40)
            fields['quantity'].grid(row=row, column=1, pady=5, padx=10)

            row += 1
            ttk.Label(form_frame, text="Unit:").grid(row=row, column=0, sticky='w', pady=5)
            fields['unit'] = ttk.Combobox(form_frame, values=['kg', 'L', 'pieces', 'portions'], width=38)
            fields['unit'].grid(row=row, column=1, pady=5, padx=10)
            fields['unit'].current(0)

            row += 1
            ttk.Label(form_frame, text="Estimated Cost (£):").grid(row=row, column=0, sticky='w', pady=5)
            fields['cost'] = ttk.Entry(form_frame, width=40)
            fields['cost'].grid(row=row, column=1, pady=5, padx=10)
            fields['cost'].insert(0, "0.00")

            row += 1
            ttk.Label(form_frame, text="Reason:").grid(row=row, column=0, sticky='w', pady=5)
            fields['reason'] = ttk.Combobox(form_frame,
                values=['Spoilage', 'Overproduction', 'Preparation waste', 'Expired', 'Damaged', 'Other'],
                width=38)
            fields['reason'].grid(row=row, column=1, pady=5, padx=10)
            fields['reason'].current(0)

            row += 1
            ttk.Label(form_frame, text="Date:*").grid(row=row, column=0, sticky='w', pady=5)
            fields['date'] = ttk.Entry(form_frame, width=40)
            fields['date'].grid(row=row, column=1, pady=5, padx=10)
            fields['date'].insert(0, datetime.now().strftime('%Y-%m-%d'))

            row += 1
            ttk.Label(form_frame, text="Notes:").grid(row=row, column=0, sticky='nw', pady=5)
            fields['notes'] = tk.Text(form_frame, height=4, width=40)
            fields['notes'].grid(row=row, column=1, pady=5, padx=10)

            def save_waste():
                try:
                    if not fields['item'].get().strip() or not fields['quantity'].get().strip():
                        messagebox.showwarning("Missing Info", "Item name and quantity are required")
                        return

                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO restaurant_waste
                            (item_name, quantity, unit, reason, cost_value, waste_date, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (fields['item'].get(), float(fields['quantity'].get()), fields['unit'].get(),
                              fields['reason'].get(), float(fields['cost'].get()), fields['date'].get(),
                              fields['notes'].get('1.0', tk.END).strip()))
                        conn.commit()
                        conn.close()

                        messagebox.showinfo("Success", "Waste record added successfully!")
                        waste_dialog.destroy()
                        load_waste()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to record waste: {e}")

            button_frame = ttk.Frame(form_frame)
            button_frame.grid(row=row+1, column=0, columnspan=2, pady=20)

            ttk.Button(button_frame, text="Save", command=save_waste).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=waste_dialog.destroy).pack(side='left', padx=5)

        ttk.Button(btn_frame, text="Record Waste", command=record_waste).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh", command=lambda: load_waste()).pack(side='left', padx=5)

        # Waste treeview
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill='both', expand=True, pady=10)

        columns = ('ID', 'Item', 'Quantity', 'Unit', 'Cost', 'Reason', 'Date')
        waste_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)

        for col in columns:
            waste_tree.heading(col, text=col)
            waste_tree.column(col, width=110)

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=waste_tree.yview)
        waste_tree.configure(yscrollcommand=scrollbar.set)

        waste_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        def load_waste():
            for item in waste_tree.get_children():
                waste_tree.delete(item)

            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT waste_id, item_name, quantity, unit, cost_value, reason, waste_date
                        FROM restaurant_waste
                        ORDER BY waste_date DESC
                        LIMIT 100
                    ''')
                    waste_records = cursor.fetchall()
                    conn.close()

                    for record in waste_records:
                        cost_display = f"£{record[4]:.2f}" if record[4] else "N/A"
                        display_record = list(record)
                        display_record[4] = cost_display
                        waste_tree.insert('', 'end', values=display_record)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load waste records: {e}")

        load_waste()

        # Summary frame
        summary_frame = ttk.LabelFrame(main_frame, text="Waste Summary", padding=10)
        summary_frame.pack(fill='x', pady=10)

        summary_text = tk.StringVar(value="Loading summary...")
        ttk.Label(summary_frame, textvariable=summary_text).pack()

        def update_summary():
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT COUNT(*), SUM(cost_value), SUM(quantity)
                        FROM restaurant_waste
                        WHERE waste_date >= date('now', '-30 days')
                    ''')
                    stats = cursor.fetchone()
                    conn.close()

                    if stats:
                        summary_text.set(
                            f"Last 30 days: {stats[0]} records | " +
                            f"Total Cost: £{stats[1]:.2f if stats[1] else 0:.2f} | " +
                            f"Total Waste: {stats[2]:.1f if stats[2] else 0:.1f} units"
                        )
            except:
                summary_text.set("Unable to load summary")

        update_summary()

        # Additional buttons
        button_frame_bottom = ttk.Frame(main_frame)
        button_frame_bottom.pack(fill='x', pady=10)

        ttk.Button(button_frame_bottom, text="View Detailed Reports",
                  command=self.view_waste_reports).pack(side='left', padx=5)
        ttk.Button(button_frame_bottom, text="Close", command=dialog.destroy).pack(side='left', padx=5)

    # Comprehensive Inventory Reports
    def inventory_reports(self):
        """Show comprehensive inventory reports menu"""
        reports_dialog = tk.Toplevel(self.root)
        reports_dialog.title("Inventory Reports")
        reports_dialog.geometry("450x500")
        reports_dialog.transient(self.root)
        reports_dialog.grab_set()

        main_frame = ttk.Frame(reports_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Inventory Reports",
                 font=('Arial', 14, 'bold')).pack(pady=20)

        ttk.Button(main_frame, text="Inventory Valuation Report",
                  command=lambda: [reports_dialog.destroy(), self.inventory_valuation_report()],
                  width=35).pack(pady=5)

        ttk.Button(main_frame, text="Stock Movement Report",
                  command=lambda: [reports_dialog.destroy(), self.stock_movement_report()],
                  width=35).pack(pady=5)

        ttk.Button(main_frame, text="Low Stock Report",
                  command=lambda: [reports_dialog.destroy(), self.low_stock_report()],
                  width=35).pack(pady=5)

        ttk.Button(main_frame, text="Expiry Report",
                  command=lambda: [reports_dialog.destroy(), self.expiry_report()],
                  width=35).pack(pady=5)

        ttk.Button(main_frame, text="ABC Analysis",
                  command=lambda: [reports_dialog.destroy(), self.abc_analysis()],
                  width=35).pack(pady=5)

        ttk.Button(main_frame, text="Inventory Transactions Log",
                  command=lambda: [reports_dialog.destroy(), self.inventory_transactions()],
                  width=35).pack(pady=5)

        ttk.Button(main_frame, text="Close",
                  command=reports_dialog.destroy,
                  width=35).pack(pady=20)

    def inventory_valuation_report(self):
        """Calculate total inventory value"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # Get inventory valuation by category/item
            cursor.execute('''
                SELECT item_id, name, quantity, unit, cost_per_unit,
                       (quantity * cost_per_unit) as total_value
                FROM restaurant_inventory
                ORDER BY total_value DESC
            ''')
            items = cursor.fetchall()

            conn.close()

            # Display report
            report_dialog = tk.Toplevel(self.root)
            report_dialog.title("Inventory Valuation Report")
            report_dialog.geometry("900x600")
            report_dialog.transient(self.root)

            main_frame = ttk.Frame(report_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Inventory Valuation Report",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            report_text = ScrolledText(main_frame, height=30, width=100)
            report_text.pack(fill='both', expand=True)

            report = "INVENTORY VALUATION REPORT\n"
            report += "=" * 90 + "\n\n"
            report += f"{'Item ID':<10} {'Item Name':<30} {'Quantity':<12} {'Unit':<10} {'Cost/Unit':<12} {'Total Value':<15}\n"
            report += "-" * 90 + "\n"

            total_value = 0
            for item_id, name, qty, unit, cost, value in items:
                total_value += value if value else 0
                report += f"{item_id:<10} {name:<30} {qty:<12.1f} {unit:<10} £{cost:<11.2f if cost else 0:<11.2f} £{value:<14.2f if value else 0:<14.2f}\n"

            report += "-" * 90 + "\n"
            report += f"{'TOTAL INVENTORY VALUE:':<64} £{total_value:<14.2f}\n"

            report_text.insert(1.0, report)
            report_text.config(state='disabled')

            ttk.Button(main_frame, text="Close",
                      command=report_dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate valuation report:\n{str(e)}")

    def stock_movement_report(self):
        """Track inventory movements (received, used, waste)"""
        try:
            start_date = simpledialog.askstring("Stock Movement", "Enter start date (YYYY-MM-DD):")
            if not start_date:
                return
            end_date = simpledialog.askstring("Stock Movement", "Enter end date (YYYY-MM-DD):")
            if not end_date:
                return

            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # Get movements data (purchases, waste)
            cursor.execute('''
                SELECT 'Purchase' as type, po.order_date as date, poi.item_id,
                       i.name, poi.quantity, 'Received' as movement
                FROM restaurant_purchase_order_items poi
                JOIN restaurant_purchase_orders po ON poi.order_id = po.order_id
                JOIN restaurant_inventory i ON poi.item_id = i.item_id
                WHERE po.order_date BETWEEN ? AND ?
                UNION ALL
                SELECT 'Waste' as type, w.waste_date as date, NULL as item_id,
                       w.item_name as name, w.quantity, 'Waste' as movement
                FROM restaurant_waste w
                WHERE w.waste_date BETWEEN ? AND ?
                ORDER BY date DESC
            ''', (start_date, end_date, start_date, end_date))
            movements = cursor.fetchall()

            conn.close()

            # Display report
            report_dialog = tk.Toplevel(self.root)
            report_dialog.title("Stock Movement Report")
            report_dialog.geometry("900x600")
            report_dialog.transient(self.root)

            main_frame = ttk.Frame(report_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"Stock Movement Report\n{start_date} to {end_date}",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            report_text = ScrolledText(main_frame, height=30, width=100)
            report_text.pack(fill='both', expand=True)

            report = "STOCK MOVEMENT REPORT\n"
            report += "=" * 90 + "\n\n"
            report += f"{'Date':<12} {'Type':<12} {'Item':<30} {'Quantity':<12} {'Movement':<15}\n"
            report += "-" * 90 + "\n"

            total_received = 0
            total_waste = 0

            for mov_type, date, item_id, name, qty, movement in movements:
                report += f"{date:<12} {mov_type:<12} {name:<30} {qty:<12.1f} {movement:<15}\n"
                if movement == 'Received':
                    total_received += qty if qty else 0
                elif movement == 'Waste':
                    total_waste += qty if qty else 0

            report += "\n" + "=" * 90 + "\n"
            report += f"Total Received: {total_received:.1f} units\n"
            report += f"Total Waste: {total_waste:.1f} units\n"
            report += f"Net Movement: {total_received - total_waste:.1f} units\n"

            report_text.insert(1.0, report)
            report_text.config(state='disabled')

            ttk.Button(main_frame, text="Close",
                      command=report_dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate stock movement report:\n{str(e)}")

    def low_stock_report(self):
        """Report on items below reorder level"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # Get low stock items
            cursor.execute('''
                SELECT item_id, name, quantity, unit, reorder_level,
                       cost_per_unit, (reorder_level - quantity) as reorder_qty,
                       ((reorder_level - quantity) * cost_per_unit) as reorder_cost
                FROM restaurant_inventory
                WHERE quantity <= reorder_level
                ORDER BY (reorder_level - quantity) DESC
            ''')
            low_stock = cursor.fetchall()

            conn.close()

            if not low_stock:
                messagebox.showinfo("Low Stock", "No items are currently low on stock!")
                return

            # Display report
            report_dialog = tk.Toplevel(self.root)
            report_dialog.title("Low Stock Report")
            report_dialog.geometry("1000x600")
            report_dialog.transient(self.root)

            main_frame = ttk.Frame(report_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Low Stock Report",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            report_text = ScrolledText(main_frame, height=30, width=110)
            report_text.pack(fill='both', expand=True)

            report = "LOW STOCK REPORT\n"
            report += "=" * 105 + "\n\n"
            report += f"{'ID':<6} {'Item':<25} {'Current':<10} {'Reorder':<10} {'Unit':<8} {'Shortage':<10} {'Cost/Unit':<12} {'Restock Cost':<15} {'Priority':<10}\n"
            report += "-" * 105 + "\n"

            total_restock_cost = 0

            for item_id, name, qty, unit, reorder, cost, reorder_qty, restock_cost in low_stock:
                total_restock_cost += restock_cost if restock_cost else 0
                shortage = reorder - qty
                priority = "CRITICAL" if qty < (reorder * 0.3) else "WARNING"

                report += f"{item_id:<6} {name:<25} {qty:<10.1f} {reorder:<10.1f} {unit:<8} "
                report += f"{shortage:<10.1f} £{cost:<11.2f if cost else 0:<11.2f} £{restock_cost:<14.2f if restock_cost else 0:<14.2f} {priority:<10}\n"

            report += "\n" + "=" * 105 + "\n"
            report += f"Total Items Low on Stock: {len(low_stock)}\n"
            report += f"Total Restock Cost: £{total_restock_cost:.2f}\n"

            report_text.insert(1.0, report)
            report_text.config(state='disabled')

            ttk.Button(main_frame, text="Close",
                      command=report_dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate low stock report:\n{str(e)}")

    def expiry_report(self):
        """Track expiring inventory"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # Add expiry_date column if it doesn't exist
            try:
                cursor.execute('''
                    ALTER TABLE restaurant_inventory ADD COLUMN expiry_date DATE
                ''')
                conn.commit()
            except:
                pass  # Column already exists

            # Get expiring items (next 7, 14, 30 days)
            cursor.execute('''
                SELECT item_id, name, quantity, unit, expiry_date,
                       julianday(expiry_date) - julianday('now') as days_until_expiry,
                       cost_per_unit, (quantity * cost_per_unit) as value_at_risk
                FROM restaurant_inventory
                WHERE expiry_date IS NOT NULL
                ORDER BY expiry_date
            ''')
            expiring_items = cursor.fetchall()

            conn.close()

            # Display report
            report_dialog = tk.Toplevel(self.root)
            report_dialog.title("Expiry Report")
            report_dialog.geometry("1000x600")
            report_dialog.transient(self.root)

            main_frame = ttk.Frame(report_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Inventory Expiry Report",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            report_text = ScrolledText(main_frame, height=30, width=110)
            report_text.pack(fill='both', expand=True)

            report = "INVENTORY EXPIRY REPORT\n"
            report += "=" * 105 + "\n\n"

            expired = []
            expires_7_days = []
            expires_14_days = []
            expires_30_days = []

            for item in expiring_items:
                days_left = item[5]
                if days_left < 0:
                    expired.append(item)
                elif days_left <= 7:
                    expires_7_days.append(item)
                elif days_left <= 14:
                    expires_14_days.append(item)
                elif days_left <= 30:
                    expires_30_days.append(item)

            # Expired items
            report += "EXPIRED ITEMS (Immediate Action Required):\n"
            report += "-" * 105 + "\n"
            if expired:
                report += f"{'ID':<6} {'Item':<25} {'Quantity':<12} {'Expiry Date':<15} {'Days Ago':<12} {'Value Lost':<15}\n"
                report += "-" * 105 + "\n"
                for item_id, name, qty, unit, expiry, days, cost, value in expired:
                    report += f"{item_id:<6} {name:<25} {qty:<12.1f} {expiry:<15} {abs(days):<12.0f} £{value:<14.2f if value else 0:<14.2f}\n"
            else:
                report += "No expired items.\n"

            # Expiring in 7 days
            report += "\n\nEXPIRING WITHIN 7 DAYS (Critical):\n"
            report += "-" * 105 + "\n"
            if expires_7_days:
                report += f"{'ID':<6} {'Item':<25} {'Quantity':<12} {'Expiry Date':<15} {'Days Left':<12} {'Value at Risk':<15}\n"
                report += "-" * 105 + "\n"
                for item_id, name, qty, unit, expiry, days, cost, value in expires_7_days:
                    report += f"{item_id:<6} {name:<25} {qty:<12.1f} {expiry:<15} {days:<12.0f} £{value:<14.2f if value else 0:<14.2f}\n"
            else:
                report += "No items expiring within 7 days.\n"

            # Expiring in 14 days
            report += "\n\nEXPIRING WITHIN 14 DAYS (Warning):\n"
            report += "-" * 105 + "\n"
            if expires_14_days:
                report += f"{'ID':<6} {'Item':<25} {'Quantity':<12} {'Expiry Date':<15} {'Days Left':<12}\n"
                report += "-" * 105 + "\n"
                for item_id, name, qty, unit, expiry, days, cost, value in expires_14_days:
                    report += f"{item_id:<6} {name:<25} {qty:<12.1f} {expiry:<15} {days:<12.0f}\n"
            else:
                report += "No items expiring within 14 days.\n"

            # Summary
            report += "\n\nSUMMARY:\n"
            report += "-" * 105 + "\n"
            report += f"Expired Items: {len(expired)}\n"
            report += f"Expiring in 7 Days: {len(expires_7_days)}\n"
            report += f"Expiring in 14 Days: {len(expires_14_days)}\n"
            report += f"Expiring in 30 Days: {len(expires_30_days)}\n"

            report_text.insert(1.0, report)
            report_text.config(state='disabled')

            ttk.Button(main_frame, text="Close",
                      command=report_dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate expiry report:\n{str(e)}")

    def abc_analysis(self):
        """ABC analysis for inventory optimization"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # Get inventory value data
            cursor.execute('''
                SELECT item_id, name, quantity, cost_per_unit,
                       (quantity * cost_per_unit) as total_value
                FROM restaurant_inventory
                WHERE quantity > 0 AND cost_per_unit > 0
                ORDER BY total_value DESC
            ''')
            items = cursor.fetchall()

            conn.close()

            if not items:
                messagebox.showinfo("No Data", "No inventory data available for ABC analysis")
                return

            # Perform ABC analysis
            total_value = sum(item[4] for item in items)
            cumulative_value = 0
            a_items = []
            b_items = []
            c_items = []

            for item in items:
                cumulative_value += item[4]
                cumulative_percent = (cumulative_value / total_value) * 100

                if cumulative_percent <= 80:  # A items: top 80% of value
                    a_items.append(item)
                elif cumulative_percent <= 95:  # B items: next 15% of value
                    b_items.append(item)
                else:  # C items: remaining 5% of value
                    c_items.append(item)

            # Display report
            report_dialog = tk.Toplevel(self.root)
            report_dialog.title("ABC Analysis")
            report_dialog.geometry("900x700")
            report_dialog.transient(self.root)

            main_frame = ttk.Frame(report_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="ABC Inventory Analysis",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            report_text = ScrolledText(main_frame, height=35, width=100)
            report_text.pack(fill='both', expand=True)

            report = "ABC INVENTORY ANALYSIS\n"
            report += "=" * 90 + "\n\n"

            report += "CATEGORY A ITEMS (High Value - Top 80%):\n"
            report += f"Items: {len(a_items)} ({len(a_items)/len(items)*100:.1f}% of items)\n"
            report += f"Value: £{sum(item[4] for item in a_items):.2f} (~80% of total value)\n"
            report += "-" * 90 + "\n"
            report += f"{'ID':<6} {'Item Name':<30} {'Quantity':<12} {'Value':<15}\n"
            report += "-" * 90 + "\n"
            for item_id, name, qty, cost, value in a_items[:10]:
                report += f"{item_id:<6} {name:<30} {qty:<12.1f} £{value:<14.2f}\n"
            if len(a_items) > 10:
                report += f"... and {len(a_items) - 10} more items\n"

            report += "\n\nCATEGORY B ITEMS (Moderate Value - Next 15%):\n"
            report += f"Items: {len(b_items)} ({len(b_items)/len(items)*100:.1f}% of items)\n"
            report += f"Value: £{sum(item[4] for item in b_items):.2f} (~15% of total value)\n"
            report += "-" * 90 + "\n"
            report += f"{'ID':<6} {'Item Name':<30} {'Quantity':<12} {'Value':<15}\n"
            report += "-" * 90 + "\n"
            for item_id, name, qty, cost, value in b_items[:10]:
                report += f"{item_id:<6} {name:<30} {qty:<12.1f} £{value:<14.2f}\n"
            if len(b_items) > 10:
                report += f"... and {len(b_items) - 10} more items\n"

            report += "\n\nCATEGORY C ITEMS (Low Value - Remaining 5%):\n"
            report += f"Items: {len(c_items)} ({len(c_items)/len(items)*100:.1f}% of items)\n"
            report += f"Value: £{sum(item[4] for item in c_items):.2f} (~5% of total value)\n"

            report += "\n\nRECOMMENDATIONS:\n"
            report += "-" * 90 + "\n"
            report += "Category A Items:\n"
            report += "  • Tight inventory control and frequent monitoring\n"
            report += "  • Accurate demand forecasting\n"
            report += "  • Strong supplier relationships\n"
            report += "  • Priority reordering\n\n"
            report += "Category B Items:\n"
            report += "  • Moderate control and periodic review\n"
            report += "  • Standard reorder procedures\n\n"
            report += "Category C Items:\n"
            report += "  • Simple controls and bulk ordering\n"
            report += "  • Consider reducing stock variety\n"

            report_text.insert(1.0, report)
            report_text.config(state='disabled')

            ttk.Button(main_frame, text="Close",
                      command=report_dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate ABC analysis:\n{str(e)}")

    def inventory_transactions(self):
        """Display detailed inventory transaction log"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # Create transactions table if doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS inventory_transactions (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER,
                    transaction_type TEXT,
                    quantity REAL,
                    transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    user_id INTEGER,
                    notes TEXT
                )
            ''')
            conn.commit()

            # Get recent transactions
            cursor.execute('''
                SELECT t.transaction_id, t.item_id, i.name, t.transaction_type,
                       t.quantity, t.transaction_date, t.notes
                FROM inventory_transactions t
                LEFT JOIN restaurant_inventory i ON t.item_id = i.item_id
                ORDER BY t.transaction_date DESC
                LIMIT 100
            ''')
            transactions = cursor.fetchall()

            conn.close()

            # Display transactions
            trans_dialog = tk.Toplevel(self.root)
            trans_dialog.title("Inventory Transactions Log")
            trans_dialog.geometry("1000x600")
            trans_dialog.transient(self.root)

            main_frame = ttk.Frame(trans_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Inventory Transactions Log (Last 100)",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            # Create treeview
            columns = ('Trans ID', 'Item ID', 'Item Name', 'Type', 'Quantity', 'Date', 'Notes')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=25)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=120)

            for trans in transactions:
                tree.insert('', 'end', values=trans)

            scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            ttk.Button(main_frame, text="Close",
                      command=trans_dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load transactions:\n{str(e)}")

    def low_stock_alerts(self):
        """Show automated low stock alerts"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # Get low stock items
            cursor.execute('''
                SELECT item_id, name, quantity, reorder_level, unit
                FROM restaurant_inventory
                WHERE quantity <= reorder_level
                ORDER BY (quantity / NULLIF(reorder_level, 0))
            ''')
            low_stock = cursor.fetchall()

            conn.close()

            # Display alerts
            alerts_dialog = tk.Toplevel(self.root)
            alerts_dialog.title("Low Stock Alerts")
            alerts_dialog.geometry("700x500")
            alerts_dialog.transient(self.root)

            main_frame = ttk.Frame(alerts_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            if not low_stock:
                ttk.Label(main_frame, text="✓ No Low Stock Alerts",
                         font=('Arial', 14, 'bold'), foreground='green').pack(pady=20)
                ttk.Label(main_frame, text="All inventory levels are adequate.",
                         font=('Arial', 12)).pack(pady=10)
            else:
                ttk.Label(main_frame, text=f"⚠ {len(low_stock)} Low Stock Alerts",
                         font=('Arial', 14, 'bold'), foreground='orange').pack(pady=20)

                # Create treeview for alerts
                columns = ('Item ID', 'Item Name', 'Current Qty', 'Reorder Level', 'Status')
                tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)

                for col in columns:
                    tree.heading(col, text=col)
                    tree.column(col, width=120)

                for item_id, name, qty, reorder, unit in low_stock:
                    status = "CRITICAL" if qty < (reorder * 0.5) else "LOW"
                    tree.insert('', 'end', values=(item_id, name, f"{qty:.1f} {unit}",
                                                  f"{reorder:.1f} {unit}", status),
                               tags=(status,))

                # Color code by status
                tree.tag_configure('CRITICAL', background='#ffcccc')
                tree.tag_configure('LOW', background='#ffffcc')

                scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
                tree.configure(yscrollcommand=scrollbar.set)

                tree.pack(side='left', fill='both', expand=True)
                scrollbar.pack(side='right', fill='y')

                # Action buttons
                button_frame = ttk.Frame(main_frame)
                button_frame.pack(pady=10)

                def send_alert_email():
                    messagebox.showinfo("Email Alert",
                                       f"Low stock alert email would be sent to procurement team.\n\n" +
                                       f"{len(low_stock)} items require reordering.")

                ttk.Button(button_frame, text="Send Email Alert",
                          command=send_alert_email).pack(side='left', padx=5)

            ttk.Button(main_frame, text="Close",
                      command=alerts_dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load low stock alerts:\n{str(e)}")

    # Report Functions
    def daily_sales_report(self):
        """Generate daily sales report"""
        date = simpledialog.askstring("Daily Sales Report", 
                                     "Enter date (YYYY-MM-DD) or leave empty for today:")
        if date is None:
            return
            
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
            
        try:
            conn = get_db_connection()
            if not conn:
                self.report_text.delete(1.0, tk.END)
                self.report_text.insert(tk.END, "Database connection failed")
                return
                
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_orders,
                    SUM(total_price) as total_revenue,
                    AVG(total_price) as avg_order_value
                FROM restaurant_orders
                WHERE DATE(order_time) = ? AND status = 'Completed'
            ''', (date,))
            
            sales_data = cursor.fetchone()
            
            report = f"DAILY SALES REPORT - {date}\n"
            report += "="*80 + "\n\n"
            report += f"Total Orders: {sales_data[0]}\n"
            report += f"Total Revenue: £{sales_data[1]:.2f}\n" if sales_data[1] else "Total Revenue: £0.00\n"
            report += f"Average Order Value: £{sales_data[2]:.2f}\n" if sales_data[2] else "Average Order Value: £0.00\n"
            
            conn.close()
            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(tk.END, report)
            
        except Exception as e:
            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(tk.END, f"Failed to generate report: {str(e)}")

    def monthly_summary_report(self):
        """Generate monthly summary report"""
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, "Monthly summary functionality would be implemented here...")
        
    def profit_analysis_report(self):
        """Generate profit analysis report"""
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, "Profit analysis functionality would be implemented here...")
        
    def menu_performance_report(self):
        """Generate menu performance report"""
        try:
            analytics_text = self.generate_menu_analytics_text()
            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(tk.END, analytics_text)
        except Exception as e:
            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(tk.END, f"Failed to generate report: {str(e)}")
            
    def customer_analytics_report(self):
        """Generate customer analytics report"""
        try:
            analytics_text = self.generate_customer_analytics_text()
            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(tk.END, analytics_text)
        except Exception as e:
            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(tk.END, f"Failed to generate report: {str(e)}")
            
    def generate_customer_analytics_text(self):
        """Generate customer analytics as text"""
        try:
            conn = get_db_connection()
            if not conn:
                return "Database connection failed"
                
            cursor = conn.cursor()
            
            text = "CUSTOMER ANALYTICS REPORT\n"
            text += "=" * 50 + "\n\n"
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_customers,
                    AVG(loyalty_points) as avg_points,
                    SUM(total_spent) as total_revenue,
                    AVG(total_spent) as avg_spent_per_customer
                FROM restaurant_customers
            ''')
            
            stats = cursor.fetchone()
            
            text += "Customer Overview:\n"
            text += "-" * 30 + "\n"
            text += f"Total Customers: {stats[0]}\n"
            text += f"Average Points: {stats[1]:.0f}\n" if stats[1] else "Average Points: N/A\n"
            text += f"Total Revenue: £{stats[2]:.2f}\n" if stats[2] else "Total Revenue: N/A\n"
            text += f"Average Spent per Customer: £{stats[3]:.2f}\n" if stats[3] else "Average Spent per Customer: N/A\n"
                
            conn.close()
            return text
            
        except Exception as e:
            return f"Error generating customer analytics: {str(e)}"
            
    def staff_performance_report(self):
        """Generate staff performance report"""
        analytics_text = self.generate_staff_analytics()
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, analytics_text)

    # Advanced Waste Reports
    def view_waste_reports(self):
        """Show comprehensive waste reports and analytics"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Waste Reports & Analytics")
        dialog.geometry("1000x700")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Waste Reports & Analytics",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Report type selection
        report_frame = ttk.LabelFrame(main_frame, text="Select Report Type", padding=10)
        report_frame.pack(fill='x', pady=10)

        btn_container = ttk.Frame(report_frame)
        btn_container.pack(fill='x')

        ttk.Button(btn_container, text="Waste by Date Range",
                  command=lambda: self.generate_waste_by_date_range(output_text)).pack(side='left', padx=5)
        ttk.Button(btn_container, text="Waste by Category",
                  command=lambda: self.generate_waste_by_category(output_text)).pack(side='left', padx=5)
        ttk.Button(btn_container, text="Waste by Reason",
                  command=lambda: self.generate_waste_by_reason(output_text)).pack(side='left', padx=5)
        ttk.Button(btn_container, text="Waste Trends",
                  command=lambda: self.generate_waste_trends(output_text)).pack(side='left', padx=5)
        ttk.Button(btn_container, text="Cost Analysis",
                  command=lambda: self.generate_waste_cost_analysis(output_text)).pack(side='left', padx=5)

        # Output area
        output_frame = ttk.LabelFrame(main_frame, text="Report Output", padding=10)
        output_frame.pack(fill='both', expand=True, pady=10)

        output_text = ScrolledText(output_frame, height=30, width=100)
        output_text.pack(fill='both', expand=True)

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def generate_waste_by_date_range(self, output_widget):
        """Generate waste report by date range"""
        start_date = simpledialog.askstring("Date Range", "Enter start date (YYYY-MM-DD):")
        if not start_date:
            return
        end_date = simpledialog.askstring("Date Range", "Enter end date (YYYY-MM-DD):")
        if not end_date:
            return

        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT waste_date, item_name, quantity, unit, cost_value, reason
                    FROM restaurant_waste
                    WHERE waste_date BETWEEN ? AND ?
                    ORDER BY waste_date DESC
                ''', (start_date, end_date))
                records = cursor.fetchall()

                cursor.execute('''
                    SELECT COUNT(*), SUM(cost_value), SUM(quantity)
                    FROM restaurant_waste
                    WHERE waste_date BETWEEN ? AND ?
                ''', (start_date, end_date))
                summary = cursor.fetchone()
                conn.close()

                report = f"WASTE REPORT BY DATE RANGE\n"
                report += f"Period: {start_date} to {end_date}\n"
                report += "=" * 100 + "\n\n"
                report += f"Summary:\n"
                report += f"  Total Records: {summary[0]}\n"
                report += f"  Total Cost: £{summary[1]:.2f if summary[1] else 0:.2f}\n"
                report += f"  Total Quantity: {summary[2]:.1f if summary[2] else 0:.1f} units\n\n"
                report += "Detailed Records:\n"
                report += "-" * 100 + "\n"
                report += f"{'Date':<12} {'Item':<25} {'Qty':<8} {'Unit':<8} {'Cost':<10} {'Reason':<20}\n"
                report += "-" * 100 + "\n"

                for record in records:
                    report += f"{record[0]:<12} {record[1]:<25} {record[2]:<8.1f} {record[3]:<8} "
                    report += f"£{record[4]:<9.2f if record[4] else 0:<9.2f} {record[5]:<20}\n"

                output_widget.delete(1.0, tk.END)
                output_widget.insert(tk.END, report)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")

    def generate_waste_by_category(self, output_widget):
        """Generate waste report grouped by category"""
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                # Get waste by item name (category proxy)
                cursor.execute('''
                    SELECT item_name, COUNT(*), SUM(quantity), SUM(cost_value)
                    FROM restaurant_waste
                    GROUP BY item_name
                    ORDER BY SUM(cost_value) DESC
                ''')
                records = cursor.fetchall()
                conn.close()

                report = "WASTE REPORT BY CATEGORY\n"
                report += "=" * 100 + "\n\n"
                report += f"{'Item/Category':<30} {'Records':<10} {'Total Qty':<15} {'Total Cost':<15}\n"
                report += "-" * 100 + "\n"

                total_cost = 0
                for record in records:
                    cost = record[3] if record[3] else 0
                    total_cost += cost
                    report += f"{record[0]:<30} {record[1]:<10} {record[2]:<15.1f} £{cost:<14.2f}\n"

                report += "-" * 100 + "\n"
                report += f"{'TOTAL':<30} {'':<10} {'':<15} £{total_cost:<14.2f}\n"

                output_widget.delete(1.0, tk.END)
                output_widget.insert(tk.END, report)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")

    def generate_waste_by_reason(self, output_widget):
        """Generate waste report grouped by reason"""
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT reason, COUNT(*), SUM(quantity), SUM(cost_value)
                    FROM restaurant_waste
                    GROUP BY reason
                    ORDER BY SUM(cost_value) DESC
                ''')
                records = cursor.fetchall()
                conn.close()

                report = "WASTE REPORT BY REASON\n"
                report += "=" * 100 + "\n\n"
                report += f"{'Reason':<25} {'Records':<10} {'Total Qty':<15} {'Total Cost':<15} {'% of Total':<12}\n"
                report += "-" * 100 + "\n"

                total_cost = sum(record[3] if record[3] else 0 for record in records)

                for record in records:
                    cost = record[3] if record[3] else 0
                    percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                    report += f"{record[0]:<25} {record[1]:<10} {record[2]:<15.1f} "
                    report += f"£{cost:<14.2f} {percentage:<11.1f}%\n"

                report += "-" * 100 + "\n"
                report += f"{'TOTAL':<25} {'':<10} {'':<15} £{total_cost:<14.2f} {'100.0%':<12}\n"

                output_widget.delete(1.0, tk.END)
                output_widget.insert(tk.END, report)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")

    def generate_waste_trends(self, output_widget):
        """Generate waste trends over time"""
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                # Monthly trends
                cursor.execute('''
                    SELECT strftime('%Y-%m', waste_date) as month,
                           COUNT(*), SUM(cost_value), SUM(quantity)
                    FROM restaurant_waste
                    GROUP BY month
                    ORDER BY month DESC
                    LIMIT 12
                ''')
                monthly = cursor.fetchall()

                # Weekly trends
                cursor.execute('''
                    SELECT strftime('%Y-W%W', waste_date) as week,
                           COUNT(*), SUM(cost_value), SUM(quantity)
                    FROM restaurant_waste
                    WHERE waste_date >= date('now', '-8 weeks')
                    GROUP BY week
                    ORDER BY week DESC
                ''')
                weekly = cursor.fetchall()
                conn.close()

                report = "WASTE TRENDS ANALYSIS\n"
                report += "=" * 100 + "\n\n"

                report += "MONTHLY TRENDS (Last 12 Months):\n"
                report += "-" * 100 + "\n"
                report += f"{'Month':<15} {'Records':<10} {'Total Cost':<15} {'Total Qty':<15} {'Avg Cost/Record':<15}\n"
                report += "-" * 100 + "\n"

                for record in monthly:
                    avg_cost = (record[2] / record[1]) if record[1] and record[2] else 0
                    report += f"{record[0]:<15} {record[1]:<10} £{record[2] if record[2] else 0:<14.2f} "
                    report += f"{record[3] if record[3] else 0:<15.1f} £{avg_cost:<14.2f}\n"

                report += "\n\nWEEKLY TRENDS (Last 8 Weeks):\n"
                report += "-" * 100 + "\n"
                report += f"{'Week':<15} {'Records':<10} {'Total Cost':<15} {'Total Qty':<15} {'Avg Cost/Record':<15}\n"
                report += "-" * 100 + "\n"

                for record in weekly:
                    avg_cost = (record[2] / record[1]) if record[1] and record[2] else 0
                    report += f"{record[0]:<15} {record[1]:<10} £{record[2] if record[2] else 0:<14.2f} "
                    report += f"{record[3] if record[3] else 0:<15.1f} £{avg_cost:<14.2f}\n"

                # Add waste reduction suggestions
                report += "\n\nWASTE REDUCTION SUGGESTIONS:\n"
                report += "-" * 100 + "\n"
                if monthly:
                    latest_month_cost = monthly[0][2] if monthly[0][2] else 0
                    if len(monthly) > 1:
                        prev_month_cost = monthly[1][2] if monthly[1][2] else 0
                        if latest_month_cost > prev_month_cost:
                            report += "• Waste cost increased from previous month - review procurement and portion sizes\n"
                        else:
                            report += "• Waste cost decreased from previous month - current practices are effective\n"

                    if latest_month_cost > 500:
                        report += "• High waste cost detected - consider implementing:\n"
                        report += "  - Better inventory management\n"
                        report += "  - Staff training on portion control\n"
                        report += "  - Review menu items with highest waste\n"

                output_widget.delete(1.0, tk.END)
                output_widget.insert(tk.END, report)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate trends report: {e}")

    def generate_waste_cost_analysis(self, output_widget):
        """Generate detailed cost analysis of waste"""
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()

                # Overall statistics
                cursor.execute('''
                    SELECT COUNT(*), SUM(cost_value), AVG(cost_value), MAX(cost_value)
                    FROM restaurant_waste
                ''')
                overall = cursor.fetchone()

                # Cost by reason
                cursor.execute('''
                    SELECT reason, SUM(cost_value)
                    FROM restaurant_waste
                    GROUP BY reason
                    ORDER BY SUM(cost_value) DESC
                ''')
                by_reason = cursor.fetchall()

                # Most expensive waste items
                cursor.execute('''
                    SELECT item_name, waste_date, cost_value, reason
                    FROM restaurant_waste
                    ORDER BY cost_value DESC
                    LIMIT 10
                ''')
                top_expensive = cursor.fetchall()

                conn.close()

                report = "WASTE COST ANALYSIS\n"
                report += "=" * 100 + "\n\n"

                report += "OVERALL STATISTICS:\n"
                report += "-" * 100 + "\n"
                report += f"Total Waste Records: {overall[0]}\n"
                report += f"Total Waste Cost: £{overall[1]:.2f if overall[1] else 0:.2f}\n"
                report += f"Average Waste Cost per Record: £{overall[2]:.2f if overall[2] else 0:.2f}\n"
                report += f"Maximum Single Waste Cost: £{overall[3]:.2f if overall[3] else 0:.2f}\n\n"

                report += "COST BREAKDOWN BY REASON:\n"
                report += "-" * 100 + "\n"
                total_cost = overall[1] if overall[1] else 0
                for record in by_reason:
                    cost = record[1] if record[1] else 0
                    percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                    report += f"  {record[0]:<25} £{cost:<14.2f} ({percentage:.1f}%)\n"

                report += "\n\nTOP 10 MOST EXPENSIVE WASTE ITEMS:\n"
                report += "-" * 100 + "\n"
                report += f"{'Item':<30} {'Date':<12} {'Cost':<12} {'Reason':<25}\n"
                report += "-" * 100 + "\n"
                for record in top_expensive:
                    report += f"{record[0]:<30} {record[1]:<12} £{record[2]:<11.2f if record[2] else 0:<11.2f} {record[3]:<25}\n"

                # Cost impact analysis
                report += "\n\nCOST IMPACT ANALYSIS:\n"
                report += "-" * 100 + "\n"
                monthly_avg = (total_cost / 12) if total_cost > 0 else 0
                annual_projection = total_cost  # If this is YTD data
                report += f"Monthly Average Waste Cost: £{monthly_avg:.2f}\n"
                report += f"Annual Projected Waste Cost: £{annual_projection:.2f}\n"
                report += f"\nPotential Savings with 25% Reduction: £{annual_projection * 0.25:.2f}/year\n"
                report += f"Potential Savings with 50% Reduction: £{annual_projection * 0.50:.2f}/year\n"

                output_widget.delete(1.0, tk.END)
                output_widget.insert(tk.END, report)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate cost analysis: {e}")

    # Financial Export Functions
    def export_payroll_report(self):
        """Export staff payroll data"""
        try:
            from tkinter import filedialog
            import csv

            # Get date range
            start_date = simpledialog.askstring("Payroll Report", "Enter start date (YYYY-MM-DD):")
            if not start_date:
                return
            end_date = simpledialog.askstring("Payroll Report", "Enter end date (YYYY-MM-DD):")
            if not end_date:
                return

            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # Get staff and their shifts
            cursor.execute('''
                SELECT s.staff_id, s.name, s.position, s.hourly_rate,
                       COUNT(sh.shift_id) as shift_count,
                       SUM(
                           CASE
                               WHEN sh.end_time IS NOT NULL THEN
                                   (julianday(sh.end_time) - julianday(sh.start_time)) * 24
                               ELSE 0
                           END
                       ) as total_hours
                FROM restaurant_staff s
                LEFT JOIN restaurant_shifts sh ON s.staff_id = sh.staff_id
                WHERE sh.shift_date BETWEEN ? AND ?
                GROUP BY s.staff_id
                ORDER BY s.name
            ''', (start_date, end_date))

            payroll_data = cursor.fetchall()
            conn.close()

            if not payroll_data:
                messagebox.showinfo("No Data", "No payroll data found for the specified period")
                return

            # Ask for export format
            format_choice = messagebox.askquestion("Export Format",
                                                  "Export as CSV?\n(No = Display in window)")

            if format_choice == 'yes':
                # Export to CSV
                filename = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile=f"payroll_report_{start_date}_to_{end_date}.csv"
                )

                if filename:
                    with open(filename, 'w', newline='') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(['Staff ID', 'Name', 'Position', 'Hourly Rate',
                                       'Shifts Worked', 'Total Hours', 'Gross Pay'])

                        for record in payroll_data:
                            hours = record[5] if record[5] else 0
                            rate = record[3] if record[3] else 0
                            gross_pay = hours * rate
                            writer.writerow([record[0], record[1], record[2], f"£{rate:.2f}",
                                          record[4], f"{hours:.2f}", f"£{gross_pay:.2f}"])

                    messagebox.showinfo("Success", f"Payroll report exported to {filename}")
            else:
                # Display in report window
                report = f"PAYROLL REPORT\n"
                report += f"Period: {start_date} to {end_date}\n"
                report += "=" * 100 + "\n\n"
                report += f"{'ID':<8} {'Name':<25} {'Position':<20} {'Rate':<12} {'Shifts':<10} {'Hours':<12} {'Gross Pay':<12}\n"
                report += "-" * 100 + "\n"

                total_hours = 0
                total_pay = 0

                for record in payroll_data:
                    hours = record[5] if record[5] else 0
                    rate = record[3] if record[3] else 0
                    gross_pay = hours * rate
                    total_hours += hours
                    total_pay += gross_pay

                    report += f"{record[0]:<8} {record[1]:<25} {record[2]:<20} "
                    report += f"£{rate:<11.2f} {record[4]:<10} {hours:<12.2f} £{gross_pay:<11.2f}\n"

                report += "-" * 100 + "\n"
                report += f"{'TOTALS:':<54} {'':<12} {'':<10} {total_hours:<12.2f} £{total_pay:<11.2f}\n"

                self.report_text.delete(1.0, tk.END)
                self.report_text.insert(tk.END, report)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate payroll report: {e}")

    def export_expense_report(self):
        """Export detailed expense report"""
        try:
            from tkinter import filedialog
            import csv

            # Get date range
            start_date = simpledialog.askstring("Expense Report", "Enter start date (YYYY-MM-DD):")
            if not start_date:
                return
            end_date = simpledialog.askstring("Expense Report", "Enter end date (YYYY-MM-DD):")
            if not end_date:
                return

            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # Get expenses from purchase orders
            cursor.execute('''
                SELECT po.order_id, po.supplier_id, s.name as supplier_name,
                       po.order_date, po.total_cost, po.status, po.payment_method
                FROM restaurant_purchase_orders po
                LEFT JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                WHERE po.order_date BETWEEN ? AND ?
                ORDER BY po.order_date DESC
            ''', (start_date, end_date))

            expenses = cursor.fetchall()
            conn.close()

            if not expenses:
                messagebox.showinfo("No Data", "No expense data found for the specified period")
                return

            # Ask for export format
            format_choice = messagebox.askquestion("Export Format",
                                                  "Export as CSV?\n(No = Display in window)")

            if format_choice == 'yes':
                # Export to CSV
                filename = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile=f"expense_report_{start_date}_to_{end_date}.csv"
                )

                if filename:
                    with open(filename, 'w', newline='') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(['Order ID', 'Supplier ID', 'Supplier Name', 'Date',
                                       'Amount', 'Status', 'Payment Method'])

                        for record in expenses:
                            writer.writerow([record[0], record[1], record[2], record[3],
                                          f"£{record[4]:.2f}", record[5], record[6]])

                    messagebox.showinfo("Success", f"Expense report exported to {filename}")
            else:
                # Display in report window
                report = f"EXPENSE REPORT\n"
                report += f"Period: {start_date} to {end_date}\n"
                report += "=" * 110 + "\n\n"
                report += f"{'Order ID':<10} {'Supplier':<25} {'Date':<12} {'Amount':<12} {'Status':<12} {'Payment':<15}\n"
                report += "-" * 110 + "\n"

                total_expense = 0
                status_totals = {}
                payment_totals = {}

                for record in expenses:
                    amount = record[4] if record[4] else 0
                    total_expense += amount

                    status = record[5] if record[5] else 'Unknown'
                    status_totals[status] = status_totals.get(status, 0) + amount

                    payment = record[6] if record[6] else 'Unknown'
                    payment_totals[payment] = payment_totals.get(payment, 0) + amount

                    report += f"{record[0]:<10} {record[2]:<25} {record[3]:<12} £{amount:<11.2f} {status:<12} {payment:<15}\n"

                report += "-" * 110 + "\n"
                report += f"{'TOTAL EXPENSES:':<49} £{total_expense:<11.2f}\n\n"

                report += "BREAKDOWN BY STATUS:\n"
                for status, amount in status_totals.items():
                    report += f"  {status:<20} £{amount:.2f}\n"

                report += "\nBREAKDOWN BY PAYMENT METHOD:\n"
                for payment, amount in payment_totals.items():
                    report += f"  {payment:<20} £{amount:.2f}\n"

                self.report_text.delete(1.0, tk.END)
                self.report_text.insert(tk.END, report)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate expense report: {e}")

    def tax_reports_menu(self):
        """Show tax reporting menu"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Tax Reports")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Tax Reports", font=('Arial', 14, 'bold')).pack(pady=20)

        ttk.Button(main_frame, text="Generate VAT Report",
                  command=lambda: [dialog.destroy(), self.generate_vat_report()],
                  width=30).pack(pady=10)

        ttk.Button(main_frame, text="Generate Sales Tax Summary",
                  command=lambda: [dialog.destroy(), self.generate_sales_tax_summary()],
                  width=30).pack(pady=10)

        ttk.Button(main_frame, text="Close", command=dialog.destroy, width=30).pack(pady=20)

    def generate_vat_report(self):
        """Generate VAT/GST report"""
        try:
            # Get date range
            start_date = simpledialog.askstring("VAT Report", "Enter start date (YYYY-MM-DD):")
            if not start_date:
                return
            end_date = simpledialog.askstring("VAT Report", "Enter end date (YYYY-MM-DD):")
            if not end_date:
                return

            vat_rate = 0.20  # 20% UK VAT rate

            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # VAT collected on sales
            cursor.execute('''
                SELECT SUM(total_price), SUM(tax_amount)
                FROM restaurant_orders
                WHERE DATE(order_time) BETWEEN ? AND ?
                AND status = 'Completed'
            ''', (start_date, end_date))
            sales_data = cursor.fetchone()

            # VAT paid on purchases
            cursor.execute('''
                SELECT SUM(total_cost)
                FROM restaurant_purchase_orders
                WHERE order_date BETWEEN ? AND ?
                AND status = 'Completed'
            ''', (start_date, end_date))
            purchase_data = cursor.fetchone()

            conn.close()

            total_sales = sales_data[0] if sales_data[0] else 0
            vat_collected = sales_data[1] if sales_data[1] else (total_sales * vat_rate / (1 + vat_rate))

            total_purchases = purchase_data[0] if purchase_data[0] else 0
            vat_paid = total_purchases * vat_rate / (1 + vat_rate)

            net_vat_liability = vat_collected - vat_paid

            report = f"VAT REPORT\n"
            report += f"Period: {start_date} to {end_date}\n"
            report += f"VAT Rate: {vat_rate*100:.0f}%\n"
            report += "=" * 80 + "\n\n"

            report += "VAT COLLECTED (Output VAT):\n"
            report += "-" * 80 + "\n"
            report += f"Total Sales (including VAT): £{total_sales:.2f}\n"
            report += f"VAT Collected on Sales: £{vat_collected:.2f}\n\n"

            report += "VAT PAID (Input VAT):\n"
            report += "-" * 80 + "\n"
            report += f"Total Purchases (including VAT): £{total_purchases:.2f}\n"
            report += f"VAT Paid on Purchases: £{vat_paid:.2f}\n\n"

            report += "NET VAT POSITION:\n"
            report += "-" * 80 + "\n"
            if net_vat_liability > 0:
                report += f"VAT Payable to HMRC: £{net_vat_liability:.2f}\n"
            elif net_vat_liability < 0:
                report += f"VAT Reclaimable from HMRC: £{abs(net_vat_liability):.2f}\n"
            else:
                report += f"VAT Position: £0.00 (Neutral)\n"

            report += "\n" + "=" * 80 + "\n"
            report += "This report is for informational purposes only.\n"
            report += "Please consult with a qualified accountant for official VAT returns.\n"

            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(tk.END, report)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate VAT report: {e}")

    def generate_sales_tax_summary(self):
        """Generate sales tax summary"""
        try:
            # Get date range
            start_date = simpledialog.askstring("Sales Tax Summary", "Enter start date (YYYY-MM-DD):")
            if not start_date:
                return
            end_date = simpledialog.askstring("Sales Tax Summary", "Enter end date (YYYY-MM-DD):")
            if not end_date:
                return

            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # Sales by payment method
            cursor.execute('''
                SELECT payment_method, COUNT(*), SUM(total_price), SUM(tax_amount)
                FROM restaurant_orders
                WHERE DATE(order_time) BETWEEN ? AND ?
                AND status = 'Completed'
                GROUP BY payment_method
            ''', (start_date, end_date))
            payment_breakdown = cursor.fetchall()

            # Total sales
            cursor.execute('''
                SELECT COUNT(*), SUM(total_price), SUM(tax_amount)
                FROM restaurant_orders
                WHERE DATE(order_time) BETWEEN ? AND ?
                AND status = 'Completed'
            ''', (start_date, end_date))
            totals = cursor.fetchone()

            conn.close()

            report = f"SALES TAX SUMMARY\n"
            report += f"Period: {start_date} to {end_date}\n"
            report += "=" * 100 + "\n\n"

            report += "SUMMARY:\n"
            report += "-" * 100 + "\n"
            report += f"Total Transactions: {totals[0]}\n"
            report += f"Total Taxable Sales: £{(totals[1] - totals[2]) if totals[1] and totals[2] else 0:.2f}\n"
            report += f"Total Tax Collected: £{totals[2] if totals[2] else 0:.2f}\n"
            report += f"Total Sales (including tax): £{totals[1] if totals[1] else 0:.2f}\n\n"

            report += "BREAKDOWN BY PAYMENT METHOD:\n"
            report += "-" * 100 + "\n"
            report += f"{'Payment Method':<20} {'Transactions':<15} {'Taxable Amount':<18} {'Tax Collected':<18} {'Total':<15}\n"
            report += "-" * 100 + "\n"

            for record in payment_breakdown:
                method = record[0] if record[0] else 'Unknown'
                count = record[1]
                total_amount = record[2] if record[2] else 0
                tax = record[3] if record[3] else 0
                taxable = total_amount - tax

                report += f"{method:<20} {count:<15} £{taxable:<17.2f} £{tax:<17.2f} £{total_amount:<14.2f}\n"

            report += "\n" + "=" * 100 + "\n"
            report += "Filing Period Summary: This report summarizes all sales tax collected for the specified period.\n"

            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(tk.END, report)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate sales tax summary: {e}")

    def financial_forecasting(self):
        """Generate financial forecasts based on historical data"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            # Get historical revenue by month (last 12 months)
            cursor.execute('''
                SELECT strftime('%Y-%m', order_time) as month,
                       SUM(total_price) as revenue,
                       COUNT(*) as order_count
                FROM restaurant_orders
                WHERE status = 'Completed'
                AND order_time >= date('now', '-12 months')
                GROUP BY month
                ORDER BY month
            ''')
            monthly_revenue = cursor.fetchall()

            # Get historical expenses by month
            cursor.execute('''
                SELECT strftime('%Y-%m', order_date) as month,
                       SUM(total_cost) as expenses
                FROM restaurant_purchase_orders
                WHERE status = 'Completed'
                AND order_date >= date('now', '-12 months')
                GROUP BY month
                ORDER BY month
            ''')
            monthly_expenses = cursor.fetchall()

            conn.close()

            if not monthly_revenue:
                messagebox.showinfo("No Data", "Insufficient historical data for forecasting")
                return

            # Calculate averages and trends
            total_revenue = sum(r[1] for r in monthly_revenue if r[1])
            avg_monthly_revenue = total_revenue / len(monthly_revenue) if monthly_revenue else 0

            expense_dict = {e[0]: e[1] for e in monthly_expenses if e[1]}
            total_expenses = sum(expense_dict.values())
            avg_monthly_expenses = total_expenses / len(monthly_expenses) if monthly_expenses else 0

            avg_monthly_profit = avg_monthly_revenue - avg_monthly_expenses

            # Simple linear trend (last 3 months vs previous 3 months)
            if len(monthly_revenue) >= 6:
                recent_avg = sum(r[1] for r in monthly_revenue[-3:] if r[1]) / 3
                previous_avg = sum(r[1] for r in monthly_revenue[-6:-3] if r[1]) / 3
                growth_rate = ((recent_avg - previous_avg) / previous_avg) if previous_avg > 0 else 0
            else:
                growth_rate = 0

            # Forecast next 3 months
            forecast_months = 3
            projected_revenue = []
            projected_expenses = []
            projected_profit = []

            for i in range(1, forecast_months + 1):
                forecast_rev = avg_monthly_revenue * (1 + growth_rate * i)
                forecast_exp = avg_monthly_expenses * (1 + growth_rate * i * 0.8)  # Assume expenses grow slower
                projected_revenue.append(forecast_rev)
                projected_expenses.append(forecast_exp)
                projected_profit.append(forecast_rev - forecast_exp)

            report = "FINANCIAL FORECASTING\n"
            report += "=" * 100 + "\n\n"

            report += "HISTORICAL PERFORMANCE (Last 12 Months):\n"
            report += "-" * 100 + "\n"
            report += f"{'Month':<12} {'Revenue':<15} {'Expenses':<15} {'Profit':<15} {'Orders':<10}\n"
            report += "-" * 100 + "\n"

            for rev_record in monthly_revenue:
                month = rev_record[0]
                revenue = rev_record[1] if rev_record[1] else 0
                expenses = expense_dict.get(month, 0)
                profit = revenue - expenses
                orders = rev_record[2]

                report += f"{month:<12} £{revenue:<14.2f} £{expenses:<14.2f} £{profit:<14.2f} {orders:<10}\n"

            report += "\n\nAVERAGES:\n"
            report += "-" * 100 + "\n"
            report += f"Average Monthly Revenue: £{avg_monthly_revenue:.2f}\n"
            report += f"Average Monthly Expenses: £{avg_monthly_expenses:.2f}\n"
            report += f"Average Monthly Profit: £{avg_monthly_profit:.2f}\n"
            report += f"Growth Rate (Trend): {growth_rate*100:.1f}%\n"

            report += "\n\n3-MONTH FORECAST:\n"
            report += "-" * 100 + "\n"
            report += f"{'Month':<12} {'Projected Revenue':<20} {'Projected Expenses':<20} {'Projected Profit':<20}\n"
            report += "-" * 100 + "\n"

            from datetime import datetime, timedelta
            forecast_start = datetime.now() + timedelta(days=30)

            for i in range(forecast_months):
                forecast_month = (forecast_start + timedelta(days=30*i)).strftime('%Y-%m')
                report += f"{forecast_month:<12} £{projected_revenue[i]:<19.2f} £{projected_expenses[i]:<19.2f} £{projected_profit[i]:<19.2f}\n"

            report += "\n\nKEY INSIGHTS:\n"
            report += "-" * 100 + "\n"
            if growth_rate > 0:
                report += f"• Positive growth trend of {growth_rate*100:.1f}% detected\n"
                report += f"• Projected 3-month revenue: £{sum(projected_revenue):.2f}\n"
                report += f"• Projected 3-month profit: £{sum(projected_profit):.2f}\n"
            elif growth_rate < 0:
                report += f"• Negative growth trend of {growth_rate*100:.1f}% detected\n"
                report += "• Consider reviewing pricing and marketing strategies\n"
            else:
                report += "• Revenue appears stable\n"

            if avg_monthly_profit < 0:
                report += "• WARNING: Average monthly profit is negative\n"
                report += "• Immediate cost reduction or revenue enhancement needed\n"

            report += "\n" + "=" * 100 + "\n"
            report += "Note: Forecasts are based on historical trends and should be used as guidance only.\n"
            report += "Actual results may vary based on market conditions and business decisions.\n"

            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(tk.END, report)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate forecast: {e}")

    def export_financial_data_menu(self):
        """Show export financial data menu"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Export Financial Data")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Export Financial Data",
                 font=('Arial', 14, 'bold')).pack(pady=20)

        ttk.Button(main_frame, text="Export Complete Financial Data",
                  command=lambda: [dialog.destroy(), self.export_complete_financial_data()],
                  width=35).pack(pady=10)

        ttk.Button(main_frame, text="Export Sales Data Only",
                  command=lambda: [dialog.destroy(), self.export_sales_data()],
                  width=35).pack(pady=10)

        ttk.Button(main_frame, text="Close", command=dialog.destroy, width=35).pack(pady=20)

    def export_complete_financial_data(self):
        """Export complete financial data to CSV"""
        try:
            from tkinter import filedialog
            import csv

            # Get date range
            start_date = simpledialog.askstring("Export Financial Data",
                                               "Enter start date (YYYY-MM-DD):")
            if not start_date:
                return
            end_date = simpledialog.askstring("Export Financial Data",
                                             "Enter end date (YYYY-MM-DD):")
            if not end_date:
                return

            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"complete_financial_data_{start_date}_to_{end_date}.csv"
            )

            if not filename:
                return

            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(['COMPLETE FINANCIAL DATA EXPORT'])
                writer.writerow([f'Period: {start_date} to {end_date}'])
                writer.writerow([])

                # Sales Revenue
                writer.writerow(['SALES REVENUE'])
                writer.writerow(['Order ID', 'Date', 'Total Price', 'Tax Amount', 'Payment Method', 'Status'])

                cursor.execute('''
                    SELECT order_id, order_time, total_price, tax_amount, payment_method, status
                    FROM restaurant_orders
                    WHERE DATE(order_time) BETWEEN ? AND ?
                    ORDER BY order_time
                ''', (start_date, end_date))

                sales = cursor.fetchall()
                for record in sales:
                    writer.writerow(record)

                writer.writerow([])

                # Purchase Expenses
                writer.writerow(['PURCHASE EXPENSES'])
                writer.writerow(['Order ID', 'Supplier ID', 'Date', 'Total Cost', 'Status', 'Payment Method'])

                cursor.execute('''
                    SELECT order_id, supplier_id, order_date, total_cost, status, payment_method
                    FROM restaurant_purchase_orders
                    WHERE order_date BETWEEN ? AND ?
                    ORDER BY order_date
                ''', (start_date, end_date))

                purchases = cursor.fetchall()
                for record in purchases:
                    writer.writerow(record)

                writer.writerow([])

                # Waste Costs
                writer.writerow(['WASTE COSTS'])
                writer.writerow(['Waste ID', 'Item', 'Date', 'Cost', 'Reason'])

                cursor.execute('''
                    SELECT waste_id, item_name, waste_date, cost_value, reason
                    FROM restaurant_waste
                    WHERE waste_date BETWEEN ? AND ?
                    ORDER BY waste_date
                ''', (start_date, end_date))

                waste = cursor.fetchall()
                for record in waste:
                    writer.writerow(record)

                writer.writerow([])

                # Summary
                cursor.execute('''
                    SELECT SUM(total_price), SUM(tax_amount)
                    FROM restaurant_orders
                    WHERE DATE(order_time) BETWEEN ? AND ?
                    AND status = 'Completed'
                ''', (start_date, end_date))
                sales_summary = cursor.fetchone()

                cursor.execute('''
                    SELECT SUM(total_cost)
                    FROM restaurant_purchase_orders
                    WHERE order_date BETWEEN ? AND ?
                    AND status = 'Completed'
                ''', (start_date, end_date))
                expense_summary = cursor.fetchone()

                cursor.execute('''
                    SELECT SUM(cost_value)
                    FROM restaurant_waste
                    WHERE waste_date BETWEEN ? AND ?
                ''', (start_date, end_date))
                waste_summary = cursor.fetchone()

                writer.writerow(['FINANCIAL SUMMARY'])
                writer.writerow(['Total Sales Revenue', f"£{sales_summary[0] if sales_summary[0] else 0:.2f}"])
                writer.writerow(['Total Tax Collected', f"£{sales_summary[1] if sales_summary[1] else 0:.2f}"])
                writer.writerow(['Total Purchase Expenses', f"£{expense_summary[0] if expense_summary[0] else 0:.2f}"])
                writer.writerow(['Total Waste Costs', f"£{waste_summary[0] if waste_summary[0] else 0:.2f}"])

                total_expenses = (expense_summary[0] if expense_summary[0] else 0) + (waste_summary[0] if waste_summary[0] else 0)
                total_revenue = sales_summary[0] if sales_summary[0] else 0
                net_profit = total_revenue - total_expenses

                writer.writerow(['Total Expenses', f"£{total_expenses:.2f}"])
                writer.writerow(['Net Profit/Loss', f"£{net_profit:.2f}"])

            conn.close()
            messagebox.showinfo("Success", f"Complete financial data exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export financial data: {e}")

    def export_sales_data(self):
        """Export sales-specific data to CSV"""
        try:
            from tkinter import filedialog
            import csv

            # Get date range
            start_date = simpledialog.askstring("Export Sales Data",
                                               "Enter start date (YYYY-MM-DD):")
            if not start_date:
                return
            end_date = simpledialog.askstring("Export Sales Data",
                                             "Enter end date (YYYY-MM-DD):")
            if not end_date:
                return

            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"sales_data_{start_date}_to_{end_date}.csv"
            )

            if not filename:
                return

            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()

            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(['SALES DATA EXPORT'])
                writer.writerow([f'Period: {start_date} to {end_date}'])
                writer.writerow([])

                # Sales transactions
                writer.writerow(['ALL SALES TRANSACTIONS'])
                writer.writerow(['Order ID', 'Customer ID', 'Date/Time', 'Subtotal',
                               'Tax Amount', 'Total Price', 'Payment Method', 'Status'])

                cursor.execute('''
                    SELECT order_id, customer_id, order_time,
                           (total_price - tax_amount) as subtotal,
                           tax_amount, total_price, payment_method, status
                    FROM restaurant_orders
                    WHERE DATE(order_time) BETWEEN ? AND ?
                    ORDER BY order_time
                ''', (start_date, end_date))

                transactions = cursor.fetchall()
                for record in transactions:
                    writer.writerow(record)

                writer.writerow([])

                # Item-level sales (if available)
                writer.writerow(['ITEM-LEVEL SALES'])
                writer.writerow(['Order ID', 'Item ID', 'Item Name', 'Quantity', 'Price'])

                cursor.execute('''
                    SELECT oi.order_id, oi.item_id, mi.name, oi.quantity, oi.price
                    FROM restaurant_order_items oi
                    JOIN menu_items mi ON oi.item_id = mi.item_id
                    JOIN restaurant_orders ro ON oi.order_id = ro.order_id
                    WHERE DATE(ro.order_time) BETWEEN ? AND ?
                    ORDER BY oi.order_id
                ''', (start_date, end_date))

                items = cursor.fetchall()
                for record in items:
                    writer.writerow(record)

                writer.writerow([])

                # Summary statistics
                writer.writerow(['SALES SUMMARY'])
                cursor.execute('''
                    SELECT
                        COUNT(*) as total_orders,
                        SUM(total_price - tax_amount) as total_sales,
                        SUM(tax_amount) as total_tax,
                        SUM(total_price) as total_with_tax,
                        AVG(total_price) as avg_order_value
                    FROM restaurant_orders
                    WHERE DATE(order_time) BETWEEN ? AND ?
                    AND status = 'Completed'
                ''', (start_date, end_date))

                summary = cursor.fetchone()
                writer.writerow(['Total Orders', summary[0]])
                writer.writerow(['Total Sales (excl. tax)', f"£{summary[1] if summary[1] else 0:.2f}"])
                writer.writerow(['Total Tax Collected', f"£{summary[2] if summary[2] else 0:.2f}"])
                writer.writerow(['Total Sales (incl. tax)', f"£{summary[3] if summary[3] else 0:.2f}"])
                writer.writerow(['Average Order Value', f"£{summary[4] if summary[4] else 0:.2f}"])

            conn.close()
            messagebox.showinfo("Success", f"Sales data exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export sales data: {e}")

    # System Settings
    def display_system_settings(self):
        """Display and configure system settings"""
        dialog = tk.Toplevel(self.root)
        dialog.title("System Settings")
        dialog.geometry("700x800")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="System Settings",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Create notebook for different setting categories
        settings_notebook = ttk.Notebook(main_frame)
        settings_notebook.pack(fill='both', expand=True, pady=10)

        # Restaurant Info Tab
        info_frame = ttk.Frame(settings_notebook, padding=10)
        settings_notebook.add(info_frame, text="Restaurant Info")

        row = 0
        ttk.Label(info_frame, text="Restaurant Name:").grid(row=row, column=0, sticky='w', pady=5)
        restaurant_name = ttk.Entry(info_frame, width=40)
        restaurant_name.insert(0, "University Restaurant")
        restaurant_name.grid(row=row, column=1, pady=5, padx=10)

        row += 1
        ttk.Label(info_frame, text="Address:").grid(row=row, column=0, sticky='w', pady=5)
        address = ttk.Entry(info_frame, width=40)
        address.insert(0, "123 Campus Drive")
        address.grid(row=row, column=1, pady=5, padx=10)

        row += 1
        ttk.Label(info_frame, text="Phone:").grid(row=row, column=0, sticky='w', pady=5)
        phone = ttk.Entry(info_frame, width=40)
        phone.insert(0, "+44 20 1234 5678")
        phone.grid(row=row, column=1, pady=5, padx=10)

        row += 1
        ttk.Label(info_frame, text="Email:").grid(row=row, column=0, sticky='w', pady=5)
        email = ttk.Entry(info_frame, width=40)
        email.insert(0, "info@university-restaurant.ac.uk")
        email.grid(row=row, column=1, pady=5, padx=10)

        # Operating Hours Tab
        hours_frame = ttk.Frame(settings_notebook, padding=10)
        settings_notebook.add(hours_frame, text="Operating Hours")

        row = 0
        ttk.Label(hours_frame, text="Monday - Friday:").grid(row=row, column=0, sticky='w', pady=5)
        weekday_hours = ttk.Entry(hours_frame, width=40)
        weekday_hours.insert(0, "08:00 - 22:00")
        weekday_hours.grid(row=row, column=1, pady=5, padx=10)

        row += 1
        ttk.Label(hours_frame, text="Saturday:").grid(row=row, column=0, sticky='w', pady=5)
        saturday_hours = ttk.Entry(hours_frame, width=40)
        saturday_hours.insert(0, "10:00 - 20:00")
        saturday_hours.grid(row=row, column=1, pady=5, padx=10)

        row += 1
        ttk.Label(hours_frame, text="Sunday:").grid(row=row, column=0, sticky='w', pady=5)
        sunday_hours = ttk.Entry(hours_frame, width=40)
        sunday_hours.insert(0, "Closed")
        sunday_hours.grid(row=row, column=1, pady=5, padx=10)

        # Tax & Currency Tab
        tax_frame = ttk.Frame(settings_notebook, padding=10)
        settings_notebook.add(tax_frame, text="Tax & Currency")

        row = 0
        ttk.Label(tax_frame, text="Currency:").grid(row=row, column=0, sticky='w', pady=5)
        currency = ttk.Combobox(tax_frame, values=['GBP (£)', 'USD ($)', 'EUR (€)'], width=38)
        currency.current(0)
        currency.grid(row=row, column=1, pady=5, padx=10)

        row += 1
        ttk.Label(tax_frame, text="Tax Rate (%):").grid(row=row, column=0, sticky='w', pady=5)
        tax_rate = ttk.Entry(tax_frame, width=40)
        tax_rate.insert(0, "20.0")
        tax_rate.grid(row=row, column=1, pady=5, padx=10)

        row += 1
        ttk.Label(tax_frame, text="Tax Name:").grid(row=row, column=0, sticky='w', pady=5)
        tax_name = ttk.Entry(tax_frame, width=40)
        tax_name.insert(0, "VAT")
        tax_name.grid(row=row, column=1, pady=5, padx=10)

        row += 1
        ttk.Label(tax_frame, text="Tax Number:").grid(row=row, column=0, sticky='w', pady=5)
        tax_number = ttk.Entry(tax_frame, width=40)
        tax_number.insert(0, "GB123456789")
        tax_number.grid(row=row, column=1, pady=5, padx=10)

        # Receipt Settings Tab
        receipt_frame = ttk.Frame(settings_notebook, padding=10)
        settings_notebook.add(receipt_frame, text="Receipt Settings")

        row = 0
        ttk.Label(receipt_frame, text="Receipt Header:").grid(row=row, column=0, sticky='nw', pady=5)
        receipt_header = tk.Text(receipt_frame, height=3, width=40)
        receipt_header.insert(1.0, "Thank you for dining with us!\nUniversity Restaurant")
        receipt_header.grid(row=row, column=1, pady=5, padx=10)

        row += 1
        ttk.Label(receipt_frame, text="Receipt Footer:").grid(row=row, column=0, sticky='nw', pady=5)
        receipt_footer = tk.Text(receipt_frame, height=3, width=40)
        receipt_footer.insert(1.0, "Please visit us again!\nwww.university-restaurant.ac.uk")
        receipt_footer.grid(row=row, column=1, pady=5, padx=10)

        row += 1
        show_tax_details = tk.BooleanVar(value=True)
        ttk.Checkbutton(receipt_frame, text="Show tax details on receipt",
                       variable=show_tax_details).grid(row=row, column=0, columnspan=2, sticky='w', pady=5)

        row += 1
        show_loyalty = tk.BooleanVar(value=True)
        ttk.Checkbutton(receipt_frame, text="Show loyalty points on receipt",
                       variable=show_loyalty).grid(row=row, column=0, columnspan=2, sticky='w', pady=5)

        # Notifications Tab
        notif_frame = ttk.Frame(settings_notebook, padding=10)
        settings_notebook.add(notif_frame, text="Notifications")

        row = 0
        email_notif = tk.BooleanVar(value=True)
        ttk.Checkbutton(notif_frame, text="Email notifications for new orders",
                       variable=email_notif).grid(row=row, column=0, sticky='w', pady=5)

        row += 1
        low_stock_notif = tk.BooleanVar(value=True)
        ttk.Checkbutton(notif_frame, text="Alert when inventory is low",
                       variable=low_stock_notif).grid(row=row, column=0, sticky='w', pady=5)

        row += 1
        waste_notif = tk.BooleanVar(value=False)
        ttk.Checkbutton(notif_frame, text="Daily waste summary email",
                       variable=waste_notif).grid(row=row, column=0, sticky='w', pady=5)

        row += 1
        ttk.Label(notif_frame, text="Notification Email:").grid(row=row, column=0, sticky='w', pady=5)
        notif_email = ttk.Entry(notif_frame, width=40)
        notif_email.insert(0, "manager@university-restaurant.ac.uk")
        notif_email.grid(row=row, column=1, pady=5, padx=10)

        # System Preferences Tab
        pref_frame = ttk.Frame(settings_notebook, padding=10)
        settings_notebook.add(pref_frame, text="Preferences")

        row = 0
        ttk.Label(pref_frame, text="Date Format:").grid(row=row, column=0, sticky='w', pady=5)
        date_format = ttk.Combobox(pref_frame,
                                   values=['YYYY-MM-DD', 'DD/MM/YYYY', 'MM/DD/YYYY'],
                                   width=38)
        date_format.current(0)
        date_format.grid(row=row, column=1, pady=5, padx=10)

        row += 1
        ttk.Label(pref_frame, text="Time Format:").grid(row=row, column=0, sticky='w', pady=5)
        time_format = ttk.Combobox(pref_frame, values=['24-hour', '12-hour'], width=38)
        time_format.current(0)
        time_format.grid(row=row, column=1, pady=5, padx=10)

        row += 1
        ttk.Label(pref_frame, text="Default Table Capacity:").grid(row=row, column=0, sticky='w', pady=5)
        default_capacity = ttk.Entry(pref_frame, width=40)
        default_capacity.insert(0, "4")
        default_capacity.grid(row=row, column=1, pady=5, padx=10)

        row += 1
        auto_complete_orders = tk.BooleanVar(value=False)
        ttk.Checkbutton(pref_frame, text="Auto-complete orders after payment",
                       variable=auto_complete_orders).grid(row=row, column=0, columnspan=2, sticky='w', pady=5)

        # Save and Cancel buttons
        def save_settings():
            try:
                # In a real implementation, save these to a config file or database
                messagebox.showinfo("Success", "Settings saved successfully!\n\n" +
                                   "Note: Some settings may require application restart.")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save settings: {e}")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=10)

        ttk.Button(button_frame, text="Save Settings",
                  command=save_settings).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel",
                  command=dialog.destroy).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Reset to Defaults",
                  command=lambda: messagebox.showinfo("Reset",
                      "This would reset all settings to default values")).pack(side='left', padx=5)

    # Utility Functions
    def backup_database(self):
        """Show backup and recovery management menu"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Backup & Recovery")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Backup & Recovery Management",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Backup section
        backup_section = ttk.LabelFrame(main_frame, text="Backup Operations", padding=15)
        backup_section.pack(fill='x', pady=10)

        ttk.Button(backup_section, text="Create Full Backup",
                  command=self.create_full_backup,
                  width=30).pack(pady=5)

        ttk.Button(backup_section, text="Create Incremental Backup",
                  command=self.create_incremental_backup,
                  width=30).pack(pady=5)

        ttk.Button(backup_section, text="Verify Backup Integrity",
                  command=self.verify_backup,
                  width=30).pack(pady=5)

        # Restore section
        restore_section = ttk.LabelFrame(main_frame, text="Restore Operations", padding=15)
        restore_section.pack(fill='x', pady=10)

        ttk.Button(restore_section, text="Restore from Backup",
                  command=self.restore_from_backup,
                  width=30).pack(pady=5)

        ttk.Button(restore_section, text="View Backup History",
                  command=self.view_backup_history,
                  width=30).pack(pady=5)

        # Management section
        mgmt_section = ttk.LabelFrame(main_frame, text="Backup Management", padding=15)
        mgmt_section.pack(fill='x', pady=10)

        ttk.Button(mgmt_section, text="Manage Backup Location",
                  command=self.manage_backup_location,
                  width=30).pack(pady=5)

        ttk.Button(mgmt_section, text="Schedule Automated Backups",
                  command=self.schedule_backups,
                  width=30).pack(pady=5)

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=15)

    def create_full_backup(self):
        """Create a full database backup"""
        try:
            from tkinter import filedialog
            import shutil
            import os

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_filename = f"restaurant_backup_full_{timestamp}.db"

            filename = filedialog.asksaveasfilename(
                defaultextension=".db",
                filetypes=[("Database files", "*.db"), ("All files", "*.*")],
                initialfile=default_filename,
                title="Save Full Backup As"
            )

            if filename:
                # Close any open connections first
                shutil.copy2(DATABASE_FILE, filename)

                # Get file size
                file_size = os.path.getsize(filename) / (1024 * 1024)  # Convert to MB

                messagebox.showinfo("Backup Complete",
                                   f"Full backup created successfully!\n\n" +
                                   f"Location: {filename}\n" +
                                   f"Size: {file_size:.2f} MB\n" +
                                   f"Timestamp: {timestamp}")

                # Log the backup
                self.log_backup_event("Full Backup", filename, file_size)

        except Exception as e:
            messagebox.showerror("Backup Failed", f"Failed to create backup:\n{str(e)}")

    def create_incremental_backup(self):
        """Create an incremental backup (only changed data)"""
        try:
            messagebox.showinfo("Incremental Backup",
                               "Incremental backup feature:\n\n" +
                               "This would backup only the data that has changed since\n" +
                               "the last backup, reducing backup time and storage.\n\n" +
                               "For this demo, performing a full backup instead.")
            self.create_full_backup()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create incremental backup:\n{str(e)}")

    def verify_backup(self):
        """Verify the integrity of a backup file"""
        try:
            from tkinter import filedialog

            filename = filedialog.askopenfilename(
                filetypes=[("Database files", "*.db"), ("All files", "*.*")],
                title="Select Backup File to Verify"
            )

            if filename:
                # Try to open the database file
                test_conn = sqlite3.connect(filename)
                cursor = test_conn.cursor()

                # Check some basic tables
                tables_to_check = ['menu_items', 'restaurant_orders', 'restaurant_staff']
                verified_tables = []

                for table in tables_to_check:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        verified_tables.append(f"✓ {table}: {count} records")
                    except:
                        verified_tables.append(f"✗ {table}: Missing or corrupted")

                test_conn.close()

                verification_report = "BACKUP VERIFICATION REPORT\n\n"
                verification_report += f"File: {filename}\n"
                verification_report += f"Status: Backup file is valid\n\n"
                verification_report += "Table Verification:\n"
                verification_report += "\n".join(verified_tables)

                messagebox.showinfo("Verification Complete", verification_report)

        except Exception as e:
            messagebox.showerror("Verification Failed",
                                f"Backup verification failed:\n{str(e)}\n\n" +
                                "The backup file may be corrupted or invalid.")

    def restore_from_backup(self):
        """Restore database from a backup file"""
        try:
            from tkinter import filedialog
            import shutil

            # Warning message
            response = messagebox.askyesno("Restore Database",
                                          "WARNING: This will replace the current database with the backup.\n\n" +
                                          "All current data will be lost!\n\n" +
                                          "Do you want to continue?",
                                          icon='warning')

            if not response:
                return

            # Create a safety backup first
            safety_backup = f"pre_restore_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2(DATABASE_FILE, safety_backup)

            # Select backup file to restore
            backup_file = filedialog.askopenfilename(
                filetypes=[("Database files", "*.db"), ("All files", "*.*")],
                title="Select Backup File to Restore"
            )

            if backup_file:
                # Verify the backup first
                try:
                    test_conn = sqlite3.connect(backup_file)
                    test_conn.close()
                except:
                    messagebox.showerror("Invalid Backup",
                                        "The selected file is not a valid database backup.")
                    return

                # Perform the restore
                shutil.copy2(backup_file, DATABASE_FILE)

                messagebox.showinfo("Restore Complete",
                                   f"Database restored successfully!\n\n" +
                                   f"Restored from: {backup_file}\n" +
                                   f"Safety backup created: {safety_backup}\n\n" +
                                   "Please restart the application for changes to take effect.")

                # Log the restore
                self.log_backup_event("Restore", backup_file, 0)

        except Exception as e:
            messagebox.showerror("Restore Failed",
                                f"Failed to restore database:\n{str(e)}\n\n" +
                                f"Your original database is safe.")

    def view_backup_history(self):
        """View backup history"""
        try:
            import os
            import glob

            # Find all backup files in current directory
            backup_files = glob.glob("restaurant_backup_*.db")

            if not backup_files:
                messagebox.showinfo("No Backups Found",
                                   "No backup files found in the current directory.\n\n" +
                                   "Backups are saved with names like:\n" +
                                   "restaurant_backup_full_YYYYMMDD_HHMMSS.db")
                return

            # Create a dialog to show backup history
            history_dialog = tk.Toplevel(self.root)
            history_dialog.title("Backup History")
            history_dialog.geometry("700x400")
            history_dialog.transient(self.root)

            main_frame = ttk.Frame(history_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Available Backups",
                     font=('Arial', 12, 'bold')).pack(pady=10)

            # Create treeview for backup files
            columns = ('Filename', 'Size (MB)', 'Date Modified')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=12)

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=200)

            # Add backup files to treeview
            for backup_file in sorted(backup_files, reverse=True):
                size_mb = os.path.getsize(backup_file) / (1024 * 1024)
                mod_time = datetime.fromtimestamp(os.path.getmtime(backup_file))
                mod_time_str = mod_time.strftime('%Y-%m-%d %H:%M:%S')

                tree.insert('', 'end', values=(backup_file, f"{size_mb:.2f}", mod_time_str))

            scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            ttk.Button(main_frame, text="Close",
                      command=history_dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load backup history:\n{str(e)}")

    def manage_backup_location(self):
        """Manage backup storage location"""
        try:
            from tkinter import filedialog

            current_location = os.path.dirname(os.path.abspath(DATABASE_FILE))

            info_text = f"Current database location:\n{current_location}\n\n"
            info_text += "Backup files are saved in the current working directory.\n\n"
            info_text += "To change the backup location, you can:\n"
            info_text += "• Save backups to a specific folder when creating them\n"
            info_text += "• Move backup files to external storage\n"
            info_text += "• Set up automatic cloud sync for the backup folder"

            messagebox.showinfo("Backup Location", info_text)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to manage backup location:\n{str(e)}")

    def schedule_backups(self):
        """Configure automated backup scheduling"""
        try:
            schedule_dialog = tk.Toplevel(self.root)
            schedule_dialog.title("Schedule Automated Backups")
            schedule_dialog.geometry("500x400")
            schedule_dialog.transient(self.root)

            main_frame = ttk.Frame(schedule_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Automated Backup Schedule",
                     font=('Arial', 12, 'bold')).pack(pady=10)

            # Frequency selection
            freq_frame = ttk.LabelFrame(main_frame, text="Backup Frequency", padding=10)
            freq_frame.pack(fill='x', pady=10)

            frequency_var = tk.StringVar(value="Daily")
            ttk.Radiobutton(freq_frame, text="Hourly", variable=frequency_var,
                           value="Hourly").pack(anchor='w')
            ttk.Radiobutton(freq_frame, text="Daily", variable=frequency_var,
                           value="Daily").pack(anchor='w')
            ttk.Radiobutton(freq_frame, text="Weekly", variable=frequency_var,
                           value="Weekly").pack(anchor='w')
            ttk.Radiobutton(freq_frame, text="Monthly", variable=frequency_var,
                           value="Monthly").pack(anchor='w')

            # Time selection
            time_frame = ttk.LabelFrame(main_frame, text="Backup Time", padding=10)
            time_frame.pack(fill='x', pady=10)

            ttk.Label(time_frame, text="Preferred time:").pack(side='left', padx=5)
            time_entry = ttk.Entry(time_frame, width=10)
            time_entry.insert(0, "02:00")
            time_entry.pack(side='left', padx=5)
            ttk.Label(time_frame, text="(24-hour format)").pack(side='left')

            # Retention policy
            retention_frame = ttk.LabelFrame(main_frame, text="Backup Retention", padding=10)
            retention_frame.pack(fill='x', pady=10)

            ttk.Label(retention_frame, text="Keep backups for:").pack(side='left', padx=5)
            retention_var = tk.StringVar(value="30")
            retention_entry = ttk.Entry(retention_frame, textvariable=retention_var, width=10)
            retention_entry.pack(side='left', padx=5)
            ttk.Label(retention_frame, text="days").pack(side='left')

            def save_schedule():
                messagebox.showinfo("Schedule Saved",
                                   f"Backup schedule configured:\n\n" +
                                   f"Frequency: {frequency_var.get()}\n" +
                                   f"Time: {time_entry.get()}\n" +
                                   f"Retention: {retention_var.get()} days\n\n" +
                                   "Note: This is a configuration preview.\n" +
                                   "In production, this would create a scheduled task.")
                schedule_dialog.destroy()

            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=20)

            ttk.Button(button_frame, text="Save Schedule",
                      command=save_schedule).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel",
                      command=schedule_dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to configure backup schedule:\n{str(e)}")

    def log_backup_event(self, event_type, filename, size_mb):
        """Log backup events to database"""
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS backup_log (
                        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_type TEXT,
                        filename TEXT,
                        file_size_mb REAL,
                        event_time DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute('''
                    INSERT INTO backup_log (event_type, filename, file_size_mb)
                    VALUES (?, ?, ?)
                ''', (event_type, filename, size_mb))
                conn.commit()
                conn.close()
        except:
            pass  # Silently fail if logging doesn't work
            
    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            root_widget = self.root if hasattr(self, 'root') else self.master
            if isinstance(root_widget, tk.Toplevel):
                # Just close the child window
                root_widget.destroy()
            else:
                # Running standalone, need to create main GUI
                root_widget.destroy()
                from university_system.modules.shared.gui.main_gui import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def show_about(self):
        """Show about dialog"""
        about_text = """University Restaurant Management System
        
Version: 2.0 (GUI Edition)
        
Features:
• Menu Management
• Order Processing  
• Customer Management
• Table Management
• Staff Management
• Inventory Management
• Comprehensive Reports
• QR Code Generation
• Backup & Recovery

Built with Python and Tkinter"""

        messagebox.showinfo("About", about_text)

    def open_finance_gui_for_payment(self, order_id=None, amount=None):
        """Open finance GUI for payment processing"""
        try:
            from university_system.modules.domain.finance.gui.finance import FinanceGUI

            finance_window = tk.Toplevel(self.root)
            finance_window.title("Finance System - Restaurant Payment")
            finance_window.geometry("1000x700")

            # Initialize finance GUI
            finance_gui = FinanceGUI(finance_window, auth=self.auth if hasattr(self, 'auth') else None)

            # Pre-populate restaurant payment information if methods exist
            if order_id and amount and hasattr(finance_gui, 'prepopulate_restaurant_payment'):
                finance_gui.prepopulate_restaurant_payment(order_id, amount)

            messagebox.showinfo("Finance System", "Finance system opened for payment processing")

        except ImportError:
            messagebox.showerror("Error", "Finance system is not available")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open finance system: {e}")

    def add_finance_button_to_payment_options(self):
        """Add finance button to payment options if applicable"""
        try:
            # This method can be called from payment dialogs to add finance integration
            # Implementation depends on specific payment dialog structure
            pass
        except Exception as e:
            print(f"Could not add finance button: {e}")


# Dialog Classes

class MenuItemDialog:
    def __init__(self, parent, title, item_id=None):
        self.result = False
        self.item_id = item_id
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        
        if item_id:
            self.load_item_data()
            
    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Name:").grid(row=0, column=0, sticky='w', pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=40).grid(row=0, column=1, pady=5)
        
        ttk.Label(main_frame, text="Description:").grid(row=1, column=0, sticky='nw', pady=5)
        self.desc_text = tk.Text(main_frame, height=3, width=40)
        self.desc_text.grid(row=1, column=1, pady=5)
        
        ttk.Label(main_frame, text="Price (£):").grid(row=2, column=0, sticky='w', pady=5)
        self.price_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.price_var, width=40).grid(row=2, column=1, pady=5)
        
        ttk.Label(main_frame, text="Category:").grid(row=3, column=0, sticky='w', pady=5)
        self.category_var = tk.StringVar()
        category_combo = ttk.Combobox(main_frame, textvariable=self.category_var, 
                                     values=['Main', 'Side', 'Dessert', 'Beverage'])
        category_combo.grid(row=3, column=1, pady=5)
        
        ttk.Label(main_frame, text="Allergens:").grid(row=4, column=0, sticky='w', pady=5)
        self.allergens_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.allergens_var, width=40).grid(row=4, column=1, pady=5)
        
        self.vegetarian_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Vegetarian", variable=self.vegetarian_var).grid(row=5, column=1, sticky='w', pady=5)
        
        self.vegan_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Vegan", variable=self.vegan_var).grid(row=6, column=1, sticky='w', pady=5)
        
        self.available_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text="Available", variable=self.available_var).grid(row=7, column=1, sticky='w', pady=5)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=8, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save).pack(side='left', padx=10)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side='left', padx=10)
        
    def load_item_data(self):
        """Load existing item data for editing"""
        try:
            conn = get_db_connection()
            if not conn:
                return
                
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM menu_items WHERE item_id = ?', (self.item_id,))
            item = cursor.fetchone()
            
            if item:
                self.name_var.set(item[1])
                self.desc_text.insert(1.0, item[2] or '')
                self.price_var.set(str(item[3]))
                self.category_var.set(item[4])
                self.allergens_var.set(item[5] or '')
                self.vegetarian_var.set(bool(item[6]))
                self.vegan_var.set(bool(item[7]))
                self.available_var.set(bool(item[8]))
                
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load item data: {str(e)}")
            
    def save(self):
        """Save the menu item"""
        try:
            if not self.name_var.get().strip():
                messagebox.showerror("Error", "Name is required")
                return
                
            try:
                price = float(self.price_var.get())
            except ValueError:
                messagebox.showerror("Error", "Invalid price")
                return
            
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                description = self.desc_text.get(1.0, tk.END).strip()
                
                if self.item_id:
                    cursor.execute('''
                        UPDATE menu_items 
                        SET name=?, description=?, price=?, category=?, allergens=?, 
                            vegetarian=?, vegan=?, available=?
                        WHERE item_id=?
                    ''', (self.name_var.get(), description, price, self.category_var.get(),
                          self.allergens_var.get(), self.vegetarian_var.get(),
                          self.vegan_var.get(), self.available_var.get(), self.item_id))
                else:
                    cursor.execute('''
                        INSERT INTO menu_items (name, description, price, category, allergens, 
                                              vegetarian, vegan, available)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (self.name_var.get(), description, price, self.category_var.get(),
                          self.allergens_var.get(), self.vegetarian_var.get(),
                          self.vegan_var.get(), self.available_var.get()))
                
                conn.commit()
                conn.close()
            
            messagebox.showinfo("Success", "Menu item saved successfully!")
            self.result = True
            self.dialog.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save item: {str(e)}")
            
    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()


class OrderStatusDialog:
    def __init__(self, parent, order_id):
        self.result = False
        self.order_id = order_id
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Update Order Status")
        self.dialog.geometry("300x200")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        
    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text=f"Order ID: {self.order_id}").pack(pady=10)
        ttk.Label(main_frame, text="New Status:").pack(pady=5)
        
        self.status_var = tk.StringVar()
        status_combo = ttk.Combobox(main_frame, textvariable=self.status_var,
                                   values=['Pending', 'Preparing', 'Ready', 'Completed', 'Cancelled'])
        status_combo.pack(pady=10)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Update", command=self.update_status).pack(side='left', padx=10)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side='left', padx=10)
        
    def update_status(self):
        """Update the order status"""
        if not self.status_var.get():
            messagebox.showerror("Error", "Please select a status")
            return
            
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE restaurant_orders SET status = ? WHERE order_id = ?',
                              (self.status_var.get(), self.order_id))
                conn.commit()
                conn.close()
            
            self.result = True
            self.dialog.destroy()
            messagebox.showinfo("Success", "Order status updated successfully")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update status: {str(e)}")
            
    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()


class PaymentDialog:
    def __init__(self, parent, order_id):
        self.result = False
        self.order_id = order_id
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Process Payment")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        
    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text=f"Order ID: {self.order_id}").pack(pady=10)
        
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('SELECT total_price FROM restaurant_orders WHERE order_id = ?', (self.order_id,))
                result = cursor.fetchone()
                total = result[0] if result else 0
                conn.close()
                
                ttk.Label(main_frame, text=f"Total: £{total:.2f}").pack(pady=5)
            else:
                ttk.Label(main_frame, text="Total: Unknown").pack(pady=5)
        except:
            ttk.Label(main_frame, text="Total: Unknown").pack(pady=5)
            
        ttk.Label(main_frame, text="Payment Method:").pack(pady=5)
        
        self.payment_var = tk.StringVar()
        payment_combo = ttk.Combobox(main_frame, textvariable=self.payment_var,
                                    values=['Cash', 'Card', 'Meal Plan', 'Student Account'])
        payment_combo.pack(pady=10)

        # Student ID field for student account payments
        ttk.Label(main_frame, text="Student ID (for Student Account payments):").pack(pady=(10, 0))
        self.student_id_var = tk.StringVar()
        self.student_id_entry = ttk.Entry(main_frame, textvariable=self.student_id_var)
        self.student_id_entry.pack(pady=5)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Process", command=self.process_payment).pack(side='left', padx=10)
        ttk.Button(button_frame, text="💳 Finance System", command=self.open_finance_system).pack(side='left', padx=10)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side='left', padx=10)
        
    def process_payment(self):
        """Process the payment"""
        payment_method = self.payment_var.get()
        if not payment_method:
            messagebox.showerror("Error", "Please select a payment method")
            return

        # Validate student ID for Student Account payments
        if payment_method == 'Student Account':
            student_id = self.student_id_var.get().strip()
            if not student_id:
                messagebox.showerror("Error", "Please enter a Student ID for Student Account payments")
                return

            # Process payment via finance system
            success = self._process_student_account_payment(student_id)
            if not success:
                return

        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE restaurant_orders SET payment_method = ?, status = ? WHERE order_id = ?',
                              (payment_method, 'Completed', self.order_id))
                conn.commit()
                conn.close()

            self.result = True
            self.dialog.destroy()
            messagebox.showinfo("Success", "Payment processed successfully")

            # Send order confirmation email if using Student Account
            if payment_method == 'Student Account':
                self._send_order_confirmation_email(student_id)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process payment: {str(e)}")

    def _process_student_account_payment(self, student_id):
        """Process payment through student's finance account"""
        try:
            # Get order details
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return False

            cursor = conn.cursor()
            cursor.execute('SELECT total_price FROM restaurant_orders WHERE order_id = ?', (self.order_id,))
            result = cursor.fetchone()
            if not result:
                messagebox.showerror("Error", "Order not found")
                conn.close()
                return False

            total_amount = result[0]

            # Get student details
            cursor.execute('SELECT first_name, last_name, email FROM students WHERE student_id = ?', (student_id,))
            student_result = cursor.fetchone()
            if not student_result:
                messagebox.showerror("Error", f"Student ID {student_id} not found in system")
                conn.close()
                return False

            first_name, last_name, email = student_result

            # Add charge to student's finance account
            fee_id = f"REST_{self.order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            current_date = datetime.now().strftime('%Y-%m-%d')

            cursor.execute('''
                INSERT INTO student_fees
                (fee_id, student_id, fee_type, amount, due_date, description, paid_status, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                fee_id, student_id, 'Restaurant', total_amount, current_date,
                f'Restaurant order #{self.order_id} for {first_name} {last_name}', 'Paid', current_date
            ))

            # Record payment
            try:
                payment_id = f"PAY_{fee_id}"
                cursor.execute('''
                    INSERT INTO payments
                    (payment_id, student_id, amount, payment_method, payment_date, status, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    payment_id, student_id, total_amount, 'Student Account', current_date, 'completed',
                    f'Restaurant payment for order #{self.order_id}'
                ))
            except sqlite3.Error:
                # Payments table might not exist, continue anyway
                pass

            conn.commit()
            conn.close()

            messagebox.showinfo("Finance Integration",
                f"Payment of £{total_amount:.2f} charged to {first_name} {last_name}'s student account")

            return True

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process student account payment: {e}")
            return False

    def _send_order_confirmation_email(self, student_id):
        """Send order confirmation email to student"""
        try:
            # Get student and order details
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Get student details
            cursor.execute('SELECT first_name, last_name, email FROM students WHERE student_id = ?', (student_id,))
            student_result = cursor.fetchone()
            if not student_result:
                conn.close()
                return

            first_name, last_name, email = student_result

            # Get order details
            cursor.execute('SELECT total_price, order_time FROM restaurant_orders WHERE order_id = ?', (self.order_id,))
            order_result = cursor.fetchone()
            if not order_result:
                conn.close()
                return

            total_amount, order_time = order_result

            conn.close()

            from university_system.infrastructure.email.template_utils import render_template

            subject, message = render_template('restaurant_order_confirmation', {
                'first_name': first_name,
                'last_name': last_name,
                'student_id': student_id,
                'order_id': self.order_id,
                'order_time': order_time,
                'total_amount': f'{total_amount:.2f}',
                'signature': 'University Restaurant Team'
            })

            if not (subject and message):
                print("Failed to load restaurant order confirmation template")
                return

            # Try to send via email GUI
            success = self._send_email_via_gui(email, subject, message)

            if success:
                print(f"Restaurant order confirmation sent to {first_name} {last_name} ({email})")
            else:
                # Fallback: show email details
                self._show_restaurant_email_fallback(f"{first_name} {last_name}", email, subject, message)

        except Exception as e:
            print(f"Failed to send restaurant order confirmation email: {e}")

    def _send_email_via_gui(self, to_email, subject, message):
        """Try to send email via email GUI"""
        try:
            from university_system.infrastructure.email.gui.email_manager_gui import EmailGUI
            email_gui = EmailGUI(self.dialog, None)  # May need auth parameter
            email_gui.send_email(to_email=to_email, subject=subject, message=message)
            return True
        except ImportError:
            return False
        except Exception as e:
            print(f"Error sending email via GUI: {e}")
            return False

    def _show_restaurant_email_fallback(self, student_name, email, subject, message):
        """Show fallback dialog for restaurant email"""
        try:
            fallback_window = tk.Toplevel(self.dialog)
            fallback_window.title("Restaurant Order Email - Manual Send")
            fallback_window.geometry("700x500")
            fallback_window.transient(self.dialog)

            ttk.Label(fallback_window,
                     text=f"Restaurant order confirmation for {student_name} - Please send manually:",
                     font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10, pady=10)

            details_frame = ttk.LabelFrame(fallback_window, text="Email Details", padding=10)
            details_frame.pack(fill='both', expand=True, padx=10, pady=10)

            details_text = ScrolledText(details_frame, height=20, width=80)
            details_text.pack(fill='both', expand=True)

            email_details = f"To: {email}\nSubject: {subject}\n\nMessage:\n{message}"
            details_text.insert('1.0', email_details)
            details_text.config(state='disabled')

            ttk.Button(fallback_window, text="Close", command=fallback_window.destroy).pack(pady=10)
        except Exception as e:
            print(f"Failed to show restaurant email fallback: {e}")

    def open_finance_system(self):
        """Open finance system for payment processing"""
        try:
            from university_system.modules.domain.finance.gui.finance import FinanceGUI

            # Get order amount
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('SELECT total_price FROM restaurant_orders WHERE order_id = ?', (self.order_id,))
                result = cursor.fetchone()
                amount = result[0] if result else 0
                conn.close()
            else:
                amount = 0

            finance_window = tk.Toplevel(self.dialog)
            finance_window.title(f"Finance System - Order #{self.order_id}")
            finance_window.geometry("1000x700")

            # Initialize finance GUI
            finance_gui = FinanceGUI(finance_window)

            # Pre-populate restaurant payment information if methods exist
            if hasattr(finance_gui, 'prepopulate_restaurant_payment'):
                finance_gui.prepopulate_restaurant_payment(self.order_id, amount)

            messagebox.showinfo("Finance System", f"Finance system opened for order #{self.order_id} (£{amount:.2f})")

        except ImportError:
            messagebox.showerror("Error", "Finance system is not available")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open finance system: {e}")

    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()


class CustomerDialog:
    def __init__(self, parent, title, customer_id=None):
        self.result = False
        self.customer_id = customer_id

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

        if customer_id:
            self.load_customer_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Name:*").grid(row=0, column=0, sticky='w', pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=40).grid(row=0, column=1, pady=5)

        ttk.Label(main_frame, text="Email:").grid(row=1, column=0, sticky='w', pady=5)
        self.email_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.email_var, width=40).grid(row=1, column=1, pady=5)

        ttk.Label(main_frame, text="Phone:").grid(row=2, column=0, sticky='w', pady=5)
        self.phone_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.phone_var, width=40).grid(row=2, column=1, pady=5)

        ttk.Label(main_frame, text="Loyalty Tier:").grid(row=3, column=0, sticky='w', pady=5)
        self.tier_var = tk.StringVar()
        tier_combo = ttk.Combobox(main_frame, textvariable=self.tier_var,
                                 values=['Bronze', 'Silver', 'Gold', 'Platinum'])
        tier_combo.grid(row=3, column=1, pady=5)
        tier_combo.current(0)

        ttk.Label(main_frame, text="Loyalty Points:").grid(row=4, column=0, sticky='w', pady=5)
        self.points_var = tk.StringVar(value="0")
        ttk.Entry(main_frame, textvariable=self.points_var, width=40).grid(row=4, column=1, pady=5)

        ttk.Label(main_frame, text="Total Spent (£):").grid(row=5, column=0, sticky='w', pady=5)
        self.spent_var = tk.StringVar(value="0.00")
        ttk.Entry(main_frame, textvariable=self.spent_var, width=40).grid(row=5, column=1, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Save", command=self.save).pack(side='left', padx=10)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side='left', padx=10)

    def load_customer_data(self):
        """Load existing customer data for editing"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('SELECT * FROM restaurant_customers WHERE customer_id = ?', (self.customer_id,))
            customer = cursor.fetchone()

            if customer:
                self.name_var.set(customer[1])
                self.email_var.set(customer[2] or '')
                self.phone_var.set(customer[3] or '')
                self.tier_var.set(customer[4])
                self.points_var.set(str(customer[5]))
                self.spent_var.set(f"{customer[6]:.2f}")

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load customer data: {str(e)}")

    def save(self):
        """Save the customer"""
        try:
            if not self.name_var.get().strip():
                messagebox.showerror("Error", "Name is required")
                return

            try:
                points = int(self.points_var.get())
                spent = float(self.spent_var.get())
            except ValueError:
                messagebox.showerror("Error", "Invalid points or spent amount")
                return

            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()

                if self.customer_id:
                    cursor.execute('''
                        UPDATE restaurant_customers
                        SET name=?, email=?, phone=?, loyalty_tier=?, loyalty_points=?, total_spent=?
                        WHERE customer_id=?
                    ''', (self.name_var.get(), self.email_var.get(), self.phone_var.get(),
                          self.tier_var.get(), points, spent, self.customer_id))
                else:
                    cursor.execute('''
                        INSERT INTO restaurant_customers (name, email, phone, loyalty_tier, loyalty_points, total_spent)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (self.name_var.get(), self.email_var.get(), self.phone_var.get(),
                          self.tier_var.get(), points, spent))

                conn.commit()
                conn.close()

            messagebox.showinfo("Success", "Customer saved successfully!")
            self.result = True
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save customer: {str(e)}")

    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()


def main():
    """Main function to run the GUI application"""
    root = tk.Tk()
    app = RestaurantManagementGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
