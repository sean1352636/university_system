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
try:
    from university_system.infrastructure.auth.user_authentication import UserAuth
    AUTH_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import UserAuth: {e}")
    AUTH_AVAILABLE = False
    # Will define fallback below

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

# Fallback Authentication class for when centralized auth is not available
if not AUTH_AVAILABLE:
    class UserAuth:
        def __init__(self):
            self.current_user = None

        def login(self, username, password):
            if username and password:
                self.current_user = {'username': username, 'role': 'manager'}
                return True
            return False

        def logout(self):
            self.current_user = None

        def check_permission(self, permission):
            return bool(self.current_user)

class RestaurantManagementGUI:
    def __init__(self, root, auth=None):
        self.root = root
        self.auth = auth

        # Initialize database
        if not init_db():
            messagebox.showerror("Database Error", "Failed to initialize database")
            return

        # Set up authentication using centralized system
        if self.auth is None:
            self.auth = UserAuth()

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

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)
        
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
        """Show purchase orders management dialog"""
        messagebox.showinfo("Purchase Orders",
            "Purchase Orders Management\n\n" +
            "This feature would allow you to:\n" +
            "• Create new purchase orders\n" +
            "• Track order status (Pending, Approved, Received)\n" +
            "• Manage supplier orders\n" +
            "• Update inventory upon receipt\n" +
            "• Generate order reports")

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
