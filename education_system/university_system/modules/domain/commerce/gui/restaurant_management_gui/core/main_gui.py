from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import threading
import sys
import os

# Import centralized authentication system
# Import authentication - REQUIRED (no fallback for security)
from education_system.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    # Note: Translation not available at import time, using English fallback
    print("Warning: Student finance account integration not available")

# Import custom exceptions for proper error handling
from education_system.university_system.infrastructure.exceptions import (
    DatabaseError,
    DatabaseConnectionError,
    QueryError,
    ValidationError,
    InvalidInputError
)

# Attempt to import the enhanced restaurant DB initializer from the CLI version.
# If available, calling this will create the full set of tables defined in
# services/restaurant_management.py. Alias the import to avoid naming
# conflicts with this module's own init_db function.
try:
    from education_system.university_system.modules.domain.commerce.services.restaurant_management import init_db as init_enhanced_restaurant_db
except ImportError:
    init_enhanced_restaurant_db = None

# Database configuration
# Always point to the central student_records.db in refactored/db_files.
try:
    from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH as DATABASE_FILE
except ImportError:
    # Fallback to local file if refactored.database.db is unavailable
    DATABASE_FILE = str(DEFAULT_DB_PATH)

def get_db_connection():
    """Get database connection with proper error handling"""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        return conn
    except (sqlite3.Error, OSError) as e:
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
                import education_system.university_system.modules.domain.commerce.services.restaurant_management as _rm_mod
                _old_db_file = getattr(_rm_mod, 'DATABASE_FILE', None)
                _rm_mod.DATABASE_FILE = DATABASE_FILE
                init_enhanced_restaurant_db()
                # Restore original CLI database file constant
                if _old_db_file is not None:
                    _rm_mod.DATABASE_FILE = _old_db_file
            except (ImportError, sqlite3.Error, AttributeError) as e:
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

        # restaurant_orders table removed - now using unified 'orders' table with source_type='restaurant'

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

    except sqlite3.Error as e:
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

        # Initialize i18n for multi-language support
        init_i18n()

        # Get authentication instance - REQUIRED for security
        self.auth = auth if auth is not None else get_auth()
        if self.auth is None:
            # Try global auth as fallback
            self.auth = get_global_auth()

        if self.auth is None:
            messagebox.showerror(
                _t("restaurant.auth_required_title"),
                _t("restaurant.auth_not_available")
            )
            root.destroy()
            return

        # Initialize database
        if not init_db():
            messagebox.showerror(_t("common.error"), _t("restaurant.db_init_failed"))
            return

        # Check if user is already authenticated
        self.current_user = None
        self.setup_current_user()

        # Don't auto-show - let the caller decide when to show
        # This prevents double window creation when called from main_gui
        self.restaurant_window = None

        # Pre-initialize GUI attributes that are created later in
        # create_main_interface / create_all_content_frames.  Without these
        # defaults, any method that references them before the window is
        # fully built would crash with an AttributeError (blank-screen bug).
        self.content_area = None
        self.content_frames = {}
        self.side_panel = None
        self.nav_buttons = {}
        self.menu_tree = None
        self.orders_tree = None
        self.customers_tree = None
        self.tables_tree = None
        self.staff_tree = None
        self.inventory_tree = None
        self.report_text = None

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
                        "permissions": auth_user.get('permissions', []),
                        "student_id": auth_user.get('student_id'),
                        "id": auth_user.get('id'),
                        "email": auth_user.get('email')
                    }
                else:
                    # Handle case where it might be an object
                    self.current_user = {
                        "username": getattr(auth_user, 'username', 'Unknown'),
                        "role": getattr(auth_user, 'role', 'user'),
                        "permissions": getattr(auth_user, 'permissions', []),
                        "student_id": getattr(auth_user, 'student_id', None),
                        "id": getattr(auth_user, 'id', None),
                        "email": getattr(auth_user, 'email', None)
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
        except (AttributeError, KeyError, TypeError) as e:
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
        # Check if window already exists and is valid
        if self.restaurant_window is not None:
            try:
                if self.restaurant_window.winfo_exists():
                    # Window already exists, just bring it to front
                    self.restaurant_window.lift()
                    self.restaurant_window.focus_force()
                    return
            except tk.TclError:
                # Window was destroyed, continue to create new one
                pass

        # Store the original root (parent window from main_gui)
        self._parent_root = self.root

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

        self.restaurant_window.title(_t("restaurant.window_title"))
        self.restaurant_window.geometry("1200x800")
        self.restaurant_window.configure(bg='#f0f0f0')

        # Update root reference to use the new window for all subsequent operations
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
        welcome_text = _t("restaurant.welcome_message", username=username, role=role)
        self.welcome_label = ttk.Label(welcome_frame, text=welcome_text, style='Heading.TLabel')
        self.welcome_label.pack()

        self.return_menu_btn = ttk.Button(
            welcome_frame,
            text=_t("restaurant.return_to_main"),
            command=self.return_to_main_menu,
            style='Custom.TButton'
        )
        self.return_menu_btn.pack(pady=(10, 0))

        # Create container for side panel and content area
        container = ttk.Frame(main_frame)
        container.pack(fill='both', expand=True)

        # Side panel for navigation buttons
        self.side_panel = ttk.Frame(container, width=200, relief='solid', borderwidth=1)
        self.side_panel.pack(side='left', fill='y', padx=(0, 10))
        self.side_panel.pack_propagate(False)  # Prevent shrinking

        # Content area for displaying different sections
        self.content_area = ttk.Frame(container)
        self.content_area.pack(side='left', fill='both', expand=True)

        # Create all content frames (hidden initially)
        self.content_frames = {}
        self.create_all_content_frames()

        # Create side panel buttons
        self.create_side_panel_buttons()

        # Show Menu section by default
        self.show_section('menu')

    def create_menu_bar(self):
        """Create the application menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.file"), menu=file_menu)
        file_menu.add_command(label=_t("menu.backup_database"), command=self.backup_database)
        file_menu.add_separator()
        file_menu.add_command(label=_t("restaurant.return_to_main"), command=self.return_to_main_menu)

        # Language menu
        language_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.language"), menu=language_menu)
        language_menu.add_command(
            label=f"{_t('menu.change_language')} [{get_current_language_name()}]",
            command=self.change_language
        )

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.help"), menu=help_menu)
        help_menu.add_command(label=_t("menu.about"), command=self.show_about)

        self.create_main_menu_button()

    def create_main_menu_button(self):
        """Ensure a top-right navigation button for the main menu exists"""
        try:
            if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                return
        except tk.TclError:
            pass

        self.main_menu_button = ttk.Button(
            self.root,
            text=_t("restaurant.return_to_main"),
            command=self.return_to_main_menu,
        )
        self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

    def change_language(self):
        """Open language selector and refresh UI on change"""
        old_lang = get_current_language()
        show_gui_language_selector(self.root)
        new_lang = get_current_language()
        if old_lang != new_lang:
            # Refresh the entire interface to apply new language
            self.refresh_ui_text()

    def refresh_ui_text(self):
        """Refresh all UI text after language change"""
        # Simplest approach: recreate the main interface
        self.restaurant_window.title(_t("restaurant.window_title"))
        self.create_main_interface()

    def create_side_panel_buttons(self):
        """Create navigation buttons in the side panel"""
        ttk.Label(self.side_panel, text=_t("common.navigation"), font=('Arial', 12, 'bold')).pack(pady=(10, 15))

        buttons_config = [
            ('menu', '🍽️  Menu Items', 'menu'),
            ('place_order', '📝  Place Order', 'place_order'),
            ('orders', '📋  Orders', 'orders'),
            ('refunds', '💰  Refunds', 'refunds'),
            ('customers', '👥  Customers', 'customers'),
            ('tables', '🪑  Tables', 'tables'),
            ('staff', '👔  Staff', 'staff'),
            ('inventory', '📦  Inventory', 'inventory'),
            ('reports', '📊  Reports', 'reports'),
        ]

        self.nav_buttons = {}
        for section_id, text, key in buttons_config:
            btn = ttk.Button(
                self.side_panel,
                text=text,
                command=lambda s=section_id: self.show_section(s),
                width=25
            )
            btn.pack(pady=2, padx=5, fill='x')
            self.nav_buttons[section_id] = btn

    def create_all_content_frames(self):
        """Create all content frames (hidden initially)"""
        # Create frames for each section
        sections = ['menu', 'place_order', 'orders', 'refunds', 'customers',
                   'tables', 'staff', 'inventory', 'reports']

        for section in sections:
            frame = ttk.Frame(self.content_area)
            self.content_frames[section] = frame

        # Create content in each frame using existing tab creation methods
        self.create_menu_tab(self.content_frames['menu'])
        self.create_place_order_tab(self.content_frames['place_order'])
        self.create_orders_tab(self.content_frames['orders'])
        self.create_refunds_tab(self.content_frames['refunds'])
        self.create_customers_tab(self.content_frames['customers'])
        self.create_tables_tab(self.content_frames['tables'])
        self.create_staff_tab(self.content_frames['staff'])
        self.create_inventory_tab(self.content_frames['inventory'])
        self.create_reports_tab(self.content_frames['reports'])

    def show_section(self, section_id):
        """Show the selected section and hide others"""
        if not self.content_frames:
            return

        # Hide all frames
        for frame in self.content_frames.values():
            frame.pack_forget()

        # Show selected frame
        if section_id in self.content_frames:
            self.content_frames[section_id].pack(fill='both', expand=True)

        # Update button styles to highlight active section
        for btn_id, btn in self.nav_buttons.items():
            if btn_id == section_id:
                btn.state(['pressed'])
            else:
                btn.state(['!pressed'])

    def clear_window(self):
        """Clear all widgets from the window"""
        if self.root is None:
            return
        for widget in self.root.winfo_children():
            widget.destroy()

    def return_to_main_menu(self):
        """Return to the main menu by closing this window"""
        try:
            # Close the restaurant window (not the parent root)
            if hasattr(self, 'restaurant_window') and self.restaurant_window:
                try:
                    if self.restaurant_window.winfo_exists():
                        self.restaurant_window.destroy()
                except tk.TclError:
                    pass
                self.restaurant_window = None

            # Restore root to the original parent so re-open works correctly
            if hasattr(self, '_parent_root') and self._parent_root:
                self.root = self._parent_root
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo(_t("restaurant.about_title"), _t("restaurant.about_text"))

    # dynamic method placeholders will be patched below

# Import and attach methods from other modules
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.core.tabs import create_menu_tab, create_place_order_tab, create_orders_tab, create_refunds_tab, create_customers_tab, create_tables_tab, create_staff_tab, create_inventory_tab, create_reports_tab
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.menu.menu_management import view_menu_items, add_menu_item_dialog, update_menu_item_dialog, show_menu_analytics, generate_menu_analytics_text
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.orders.order_management import view_orders_gui, update_order_status_dialog, process_payment_dialog, show_order_analytics, generate_order_analytics
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.orders.payments import add_tip, refund_order, apply_discount, process_cash_payment, process_card_payment, process_meal_plan_payment, open_finance_gui_for_payment, add_finance_button_to_payment_options
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.customers.customer_management import view_customers_gui, add_customer_dialog, update_customer_dialog
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.customers.feedback import manage_customer_feedback, view_recent_feedback, respond_to_feedback, submit_demo_feedback, export_feedback_report, export_feedback_report_pdf
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.customers.loyalty import manage_loyalty_dialog, view_loyalty_tiers, promote_customer_tier, award_bonus_points
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.customers.meal_plan import manage_meal_plan_dialog, manage_staff_subsidy_dialog
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.tables.table_management import view_tables_gui, add_table_dialog, manage_reservations_dialog, optimize_table_structure
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.tables.qr_codes import generate_qr_dialog, create_qr_code_image, create_enhanced_qr_image, print_qr_codes, scan_qr_code_usage, update_qr_database_record
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.staff.staff_management import view_staff_gui, add_staff_dialog, manage_schedules_dialog, show_staff_analytics, generate_staff_analytics, view_schedule_conflicts
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.staff.performance import staff_performance, view_performance_rankings, update_performance_scores, export_performance_report
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.inventory.inventory_management import view_inventory_gui, waste_tracking_dialog, inventory_transactions, low_stock_alerts
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.inventory.purchase_orders import manage_purchase_orders_dialog, view_purchase_orders, create_purchase_order, update_purchase_order, receive_purchase_order, purchase_order_reports, manage_suppliers_dialog
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.inventory.inventory_reports import inventory_reports, inventory_valuation_report, stock_movement_report, low_stock_report, expiry_report, abc_analysis
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.reports.sales_reports import show_report_window, daily_sales_report, monthly_summary_report, profit_analysis_report, menu_performance_report, customer_analytics_report, generate_customer_analytics_text, staff_performance_report
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.reports.waste_reports import view_waste_reports, generate_waste_by_date_range, generate_waste_by_category, generate_waste_by_reason, generate_waste_trends, generate_waste_cost_analysis
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.reports.financial_reports import export_payroll_report, export_expense_report, tax_reports_menu, generate_vat_report, generate_sales_tax_summary, financial_forecasting, export_financial_data_menu, export_complete_financial_data, export_sales_data
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.settings.backup_settings import display_system_settings, backup_database, create_full_backup, create_incremental_backup, verify_backup, restore_from_backup, view_backup_history, manage_backup_location, schedule_backups, log_backup_event

RestaurantManagementGUI.create_menu_tab = create_menu_tab
RestaurantManagementGUI.create_place_order_tab = create_place_order_tab
RestaurantManagementGUI.create_orders_tab = create_orders_tab
RestaurantManagementGUI.create_refunds_tab = create_refunds_tab
RestaurantManagementGUI.create_customers_tab = create_customers_tab
RestaurantManagementGUI.create_tables_tab = create_tables_tab
RestaurantManagementGUI.create_staff_tab = create_staff_tab
RestaurantManagementGUI.create_inventory_tab = create_inventory_tab
RestaurantManagementGUI.create_reports_tab = create_reports_tab
RestaurantManagementGUI.view_menu_items = view_menu_items
RestaurantManagementGUI.add_menu_item_dialog = add_menu_item_dialog
RestaurantManagementGUI.update_menu_item_dialog = update_menu_item_dialog
RestaurantManagementGUI.show_menu_analytics = show_menu_analytics
RestaurantManagementGUI.generate_menu_analytics_text = generate_menu_analytics_text
RestaurantManagementGUI.view_orders_gui = view_orders_gui
RestaurantManagementGUI.update_order_status_dialog = update_order_status_dialog
RestaurantManagementGUI.process_payment_dialog = process_payment_dialog
RestaurantManagementGUI.show_order_analytics = show_order_analytics
RestaurantManagementGUI.generate_order_analytics = generate_order_analytics
RestaurantManagementGUI.add_tip = add_tip
RestaurantManagementGUI.refund_order = refund_order
RestaurantManagementGUI.apply_discount = apply_discount
RestaurantManagementGUI.process_cash_payment = process_cash_payment
RestaurantManagementGUI.process_card_payment = process_card_payment
RestaurantManagementGUI.process_meal_plan_payment = process_meal_plan_payment
RestaurantManagementGUI.open_finance_gui_for_payment = open_finance_gui_for_payment
RestaurantManagementGUI.add_finance_button_to_payment_options = add_finance_button_to_payment_options
RestaurantManagementGUI.view_customers_gui = view_customers_gui
RestaurantManagementGUI.add_customer_dialog = add_customer_dialog
RestaurantManagementGUI.update_customer_dialog = update_customer_dialog
RestaurantManagementGUI.manage_customer_feedback = manage_customer_feedback
RestaurantManagementGUI.view_recent_feedback = view_recent_feedback
RestaurantManagementGUI.respond_to_feedback = respond_to_feedback
RestaurantManagementGUI.submit_demo_feedback = submit_demo_feedback
RestaurantManagementGUI.export_feedback_report = export_feedback_report
RestaurantManagementGUI.export_feedback_report_pdf = export_feedback_report_pdf
RestaurantManagementGUI.manage_loyalty_dialog = manage_loyalty_dialog
RestaurantManagementGUI.manage_meal_plan_dialog = manage_meal_plan_dialog
RestaurantManagementGUI.manage_staff_subsidy_dialog = manage_staff_subsidy_dialog
RestaurantManagementGUI.view_loyalty_tiers = view_loyalty_tiers
RestaurantManagementGUI.promote_customer_tier = promote_customer_tier
RestaurantManagementGUI.award_bonus_points = award_bonus_points
RestaurantManagementGUI.view_tables_gui = view_tables_gui
RestaurantManagementGUI.add_table_dialog = add_table_dialog
RestaurantManagementGUI.manage_reservations_dialog = manage_reservations_dialog
RestaurantManagementGUI.optimize_table_structure = optimize_table_structure
RestaurantManagementGUI.generate_qr_dialog = generate_qr_dialog
RestaurantManagementGUI.create_qr_code_image = create_qr_code_image
RestaurantManagementGUI.create_enhanced_qr_image = create_enhanced_qr_image
RestaurantManagementGUI.print_qr_codes = print_qr_codes
RestaurantManagementGUI.scan_qr_code_usage = scan_qr_code_usage
RestaurantManagementGUI.update_qr_database_record = update_qr_database_record
RestaurantManagementGUI.view_staff_gui = view_staff_gui
RestaurantManagementGUI.add_staff_dialog = add_staff_dialog
RestaurantManagementGUI.manage_schedules_dialog = manage_schedules_dialog
RestaurantManagementGUI.show_staff_analytics = show_staff_analytics
RestaurantManagementGUI.generate_staff_analytics = generate_staff_analytics
RestaurantManagementGUI.view_schedule_conflicts = view_schedule_conflicts
RestaurantManagementGUI.staff_performance = staff_performance
RestaurantManagementGUI.view_performance_rankings = view_performance_rankings
RestaurantManagementGUI.update_performance_scores = update_performance_scores
RestaurantManagementGUI.export_performance_report = export_performance_report
RestaurantManagementGUI.view_inventory_gui = view_inventory_gui
RestaurantManagementGUI.waste_tracking_dialog = waste_tracking_dialog
RestaurantManagementGUI.inventory_transactions = inventory_transactions
RestaurantManagementGUI.low_stock_alerts = low_stock_alerts
RestaurantManagementGUI.manage_purchase_orders_dialog = manage_purchase_orders_dialog
RestaurantManagementGUI.view_purchase_orders = view_purchase_orders
RestaurantManagementGUI.create_purchase_order = create_purchase_order
RestaurantManagementGUI.update_purchase_order = update_purchase_order
RestaurantManagementGUI.receive_purchase_order = receive_purchase_order
RestaurantManagementGUI.purchase_order_reports = purchase_order_reports
RestaurantManagementGUI.manage_suppliers_dialog = manage_suppliers_dialog
RestaurantManagementGUI.inventory_reports = inventory_reports
RestaurantManagementGUI.inventory_valuation_report = inventory_valuation_report
RestaurantManagementGUI.stock_movement_report = stock_movement_report
RestaurantManagementGUI.low_stock_report = low_stock_report
RestaurantManagementGUI.expiry_report = expiry_report
RestaurantManagementGUI.abc_analysis = abc_analysis
RestaurantManagementGUI.show_report_window = show_report_window
RestaurantManagementGUI.daily_sales_report = daily_sales_report
RestaurantManagementGUI.monthly_summary_report = monthly_summary_report
RestaurantManagementGUI.profit_analysis_report = profit_analysis_report
RestaurantManagementGUI.menu_performance_report = menu_performance_report
RestaurantManagementGUI.customer_analytics_report = customer_analytics_report
RestaurantManagementGUI.generate_customer_analytics_text = generate_customer_analytics_text
RestaurantManagementGUI.staff_performance_report = staff_performance_report
RestaurantManagementGUI.view_waste_reports = view_waste_reports
RestaurantManagementGUI.generate_waste_by_date_range = generate_waste_by_date_range
RestaurantManagementGUI.generate_waste_by_category = generate_waste_by_category
RestaurantManagementGUI.generate_waste_by_reason = generate_waste_by_reason
RestaurantManagementGUI.generate_waste_trends = generate_waste_trends
RestaurantManagementGUI.generate_waste_cost_analysis = generate_waste_cost_analysis
RestaurantManagementGUI.export_payroll_report = export_payroll_report
RestaurantManagementGUI.export_expense_report = export_expense_report
RestaurantManagementGUI.tax_reports_menu = tax_reports_menu
RestaurantManagementGUI.generate_vat_report = generate_vat_report
RestaurantManagementGUI.generate_sales_tax_summary = generate_sales_tax_summary
RestaurantManagementGUI.financial_forecasting = financial_forecasting
RestaurantManagementGUI.export_financial_data_menu = export_financial_data_menu
RestaurantManagementGUI.export_complete_financial_data = export_complete_financial_data
RestaurantManagementGUI.export_sales_data = export_sales_data
RestaurantManagementGUI.display_system_settings = display_system_settings
RestaurantManagementGUI.backup_database = backup_database
RestaurantManagementGUI.create_full_backup = create_full_backup
RestaurantManagementGUI.create_incremental_backup = create_incremental_backup
RestaurantManagementGUI.verify_backup = verify_backup
RestaurantManagementGUI.restore_from_backup = restore_from_backup
RestaurantManagementGUI.view_backup_history = view_backup_history
RestaurantManagementGUI.manage_backup_location = manage_backup_location
RestaurantManagementGUI.schedule_backups = schedule_backups
RestaurantManagementGUI.log_backup_event = log_backup_event
