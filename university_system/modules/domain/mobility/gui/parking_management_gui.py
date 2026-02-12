from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import logging
import threading
import os
import sys

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

# Import email template utilities
try:
    from university_system.infrastructure.email.template_utils import render_template
    TEMPLATE_AVAILABLE = True
except ImportError:
    TEMPLATE_AVAILABLE = False

# Import compatibility layer first
try:
    from university_system.modules.domain.mobility.services.parking_compatibility import (
        set_gui_mode, get_function_output, validate_gui_data,
        get_user_permissions, format_console_output_for_gui,
        execute_console_function_with_params, cleanup_compatibility_layer
    )
    COMPATIBILITY_AVAILABLE = True
except ImportError:
    COMPATIBILITY_AVAILABLE = False

# Import the existing parking management functions
try:
    from university_system.modules.domain.mobility.services.parking_management import (
        init_db, set_auth, PARKING_ZONES, PERMIT_TYPES, VEHICLE_TYPES,
        create_parking_permit, view_parking_permit, update_parking_permit, delete_parking_permit,
        register_vehicle, view_vehicle, update_vehicle, delete_vehicle,
        record_violation, generate_compliance_report, generate_revenue_report,
        generate_user_activity_report, export_users,
        view_violations, update_violation, delete_violation,
        view_parking_lots, add_parking_lot, update_parking_lot, delete_parking_lot,
        generate_permit_report, generate_violation_report, generate_analytics_dashboard,
        export_permits, export_vehicles, export_violations, export_parking_lots
    )
    from university_system.infrastructure.auth import UserAuth
    from university_system.infrastructure.shared_context import get_auth
    from university_system.infrastructure.database.db import get_connection
    PARKING_MANAGEMENT_AVAILABLE = True
except ImportError as e:
    PARKING_MANAGEMENT_AVAILABLE = False
    print(f"Warning: Could not import parking management modules: {e}")
    # Define fallback constants
    PARKING_ZONES = {
        'A': {'name': 'Faculty/Staff', 'hourly_rate': 0, 'annual_fee': 250},
        'B': {'name': 'Commuter Students', 'hourly_rate': 0, 'annual_fee': 180},
        'C': {'name': 'Resident Students', 'hourly_rate': 0, 'annual_fee': 220},
        'V': {'name': 'Visitor', 'hourly_rate': 2.50, 'annual_fee': 0},
        'H': {'name': 'Handicap Accessible', 'hourly_rate': 0, 'annual_fee': 150},
        'M': {'name': 'Metered', 'hourly_rate': 1.75, 'annual_fee': 0},
        'R': {'name': 'Reserved', 'hourly_rate': 0, 'annual_fee': 350},
    }
    PERMIT_TYPES = ['Annual', 'Semester', 'Monthly', 'Daily', 'Temporary']
    VEHICLE_TYPES = ['Sedan', 'SUV', 'Truck', 'Motorcycle', 'Compact', 'Van']

class ParkingManagementGUI:
    def __init__(self, root, auth_system=None):
        # Initialize i18n for language support
        init_i18n()

        self.root = root
        self.root.title(_t("parking.title"))
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)

        # Initialize authentication - use provided auth system or centralized auth
        if auth_system:
            self.auth = auth_system
        else:
            # Use centralized auth system
            self.auth = get_auth()
            if self.auth is None:
                self.auth = UserAuth()
        set_auth(self.auth)

        # Initialize database
        init_db()

        # Initialize payment and refund tables
        self._init_payment_refund_tables()

        # Current user info
        self.current_user = None

        # Setup current user from existing authentication system
        self.setup_current_user()

        # Create the main interface
        self.setup_gui()

        # Show appropriate interface based on authentication status
        if self.current_user:
            self.update_user_status()
            self.update_status("Using authenticated user session")
            self.update_tab_access()
        else:
            # User must log in through main University System GUI
            messagebox.showerror(
                _t("common.error"),
                _t("parking.messages.auth_required")
            )
            self.root.destroy()

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
                        "first_name": auth_user.get('first_name', ''),
                        "last_name": auth_user.get('last_name', ''),
                        "id": auth_user.get('id', 0)
                    }
                else:
                    # Handle case where it might be an object
                    self.current_user = {
                        "username": getattr(auth_user, 'username', 'Unknown'),
                        "role": getattr(auth_user, 'role', 'user'),
                        "permissions": getattr(auth_user, 'permissions', []),
                        "first_name": getattr(auth_user, 'first_name', ''),
                        "last_name": getattr(auth_user, 'last_name', ''),
                        "id": getattr(auth_user, 'id', 0)
                    }

                print(f"✓ Parking Management GUI: Using authenticated user {self.current_user['username']} ({self.current_user['role']})")
            else:
                self.current_user = None
                print("ℹ Parking Management GUI: No authenticated user - will show login screen")
        except Exception as e:
            print(f"✗ Error setting up current user: {e}")
            self.current_user = None

    def _init_payment_refund_tables(self):
        """Initialize payment and refund tables in the database"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Create parking_payments table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS parking_payments (
                    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    violation_id TEXT NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    payment_method TEXT NOT NULL,
                    payment_reference TEXT UNIQUE,
                    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    student_id TEXT,
                    processed_by TEXT,
                    notes TEXT,
                    FOREIGN KEY (violation_id) REFERENCES parking_violations(violation_id)
                )
            ''')

            # Create parking_refunds table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS parking_refunds (
                    refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payment_id INTEGER NOT NULL,
                    violation_id TEXT NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    refund_method TEXT NOT NULL,
                    refund_reference TEXT UNIQUE,
                    refund_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    student_id TEXT,
                    processed_by TEXT,
                    reason TEXT,
                    FOREIGN KEY (payment_id) REFERENCES parking_payments(payment_id),
                    FOREIGN KEY (violation_id) REFERENCES parking_violations(violation_id)
                )
            ''')

            # Add payment_status column to parking_violations if it doesn't exist
            try:
                cursor.execute("SELECT payment_status FROM parking_violations LIMIT 1")
            except Exception:
                cursor.execute("ALTER TABLE parking_violations ADD COLUMN payment_status TEXT DEFAULT 'Unpaid'")

            # Create finance_payments table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS finance_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payment_reference TEXT UNIQUE,
                    department TEXT,
                    transaction_id TEXT,
                    amount DECIMAL(10,2),
                    payment_method TEXT,
                    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_by TEXT,
                    notes TEXT
                )
            ''')

            conn.commit()
            conn.close()
            logging.info("Payment and refund tables initialized")
        except Exception as e:
            logging.error(f"Error initializing payment/refund tables: {e}")

    def setup_gui(self):
        """Set up the main GUI interface"""
        # Create main frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create status bar
        self.create_status_bar()

        # Ensure a persistent top-corner main menu button is available
        self.create_main_menu_button()

        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 30))
        
        # Create tabs
        self.create_tabs()
        
    def create_menu_bar(self):
        """Create the menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.file"), menu=file_menu)
        file_menu.add_command(label=_t("parking.menu.export_data"), command=self.show_export_dialog)
        file_menu.add_separator()
        file_menu.add_command(label=_t("common.exit"), command=self.root.quit)

        # Reports menu
        reports_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("parking.menu.reports"), menu=reports_menu)
        reports_menu.add_command(label=_t("parking.menu.permit_report"), command=self.generate_permit_report)
        reports_menu.add_command(label=_t("parking.menu.violation_report"), command=self.generate_violation_report)
        reports_menu.add_command(label=_t("parking.menu.occupancy_report"), command=self.generate_occupancy_report)
        reports_menu.add_command(label=_t("parking.menu.revenue_report"), command=self.generate_revenue_report)
        reports_menu.add_command(label=_t("parking.menu.user_activity_report"), command=self.generate_user_activity_report)
        reports_menu.add_command(label=_t("parking.menu.compliance_report"), command=self.generate_compliance_report)
        reports_menu.add_command(label=_t("parking.menu.analytics_dashboard"), command=self.show_analytics)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.tools"), menu=tools_menu)
        tools_menu.add_command(label=_t("parking.menu.refresh_all"), command=self.refresh_all_data)
        tools_menu.add_command(label=_t("parking.menu.database_backup"), command=self.backup_database)
        tools_menu.add_command(label=_t("parking.menu.update_spaces"), command=self.update_available_spaces_dialog)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.help"), menu=help_menu)
        help_menu.add_command(label=_t("parking.menu.about"), command=self.show_about)

    def create_main_menu_button(self):
        """Place a top-corner button to return to the main menu"""
        try:
            if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                return
        except Exception:
            pass

        self.main_menu_button = ttk.Button(
            self.root,
            text=_t("common.return_to_main_menu"),
            command=self.return_to_main_menu,
        )
        # Place in the top-right corner with a slight margin
        self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

    def create_status_bar(self):
        """Create the status bar"""
        self.status_frame = ttk.Frame(self.main_frame)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(self.status_frame, text=_t("common.ready"))
        self.status_label.pack(side=tk.LEFT)

        self.user_label = ttk.Label(self.status_frame, text=_t("parking.not_logged_in"))
        self.user_label.pack(side=tk.RIGHT)
    
    def create_tabs(self):
        """Create all the tabs"""
        # Permits tab
        self.permits_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.permits_frame, text=_t("parking.tabs.permits"))
        self.setup_permits_tab()

        # Vehicles tab
        self.vehicles_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.vehicles_frame, text=_t("parking.tabs.vehicles"))
        self.setup_vehicles_tab()

        # Violations tab
        self.violations_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.violations_frame, text=_t("parking.tabs.violations"))
        self.setup_violations_tab()

        # Parking Lots tab
        self.lots_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.lots_frame, text=_t("parking.tabs.parking_lots"))
        self.setup_lots_tab()

        # Payments & Refunds tab
        self.payments_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.payments_frame, text="Payments & Refunds")
        self.setup_payments_tab()

        # Dashboard tab
        self.dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.dashboard_frame, text=_t("parking.tabs.dashboard"))
        self.setup_dashboard_tab()
    
    def setup_permits_tab(self):
        """Setup the permits management tab"""
        # Create toolbar
        toolbar = ttk.Frame(self.permits_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(toolbar, text=_t("parking.btn.create_permit"), command=self.create_permit_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("parking.btn.edit_selected"), command=self.edit_selected_permit).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("parking.btn.delete_selected"), command=self.delete_selected_permit).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("common.refresh"), command=self.refresh_permits).pack(side=tk.LEFT, padx=2)

        # Search frame
        search_frame = ttk.Frame(self.permits_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(search_frame, text=_t("common.search") + ":").pack(side=tk.LEFT)
        self.permit_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.permit_search_var)
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        search_entry.bind('<KeyRelease>', self.filter_permits)
        
        # Create treeview for permits
        columns = ("ID", "User", "Zone", "Type", "Start Date", "End Date", "Status", "Vehicle")
        self.permits_tree = ttk.Treeview(self.permits_frame, columns=columns, show="headings")
        
        # Configure columns
        for col in columns:
            self.permits_tree.heading(col, text=col)
            self.permits_tree.column(col, width=100)
        
        # Add scrollbars
        permits_scrolly = ttk.Scrollbar(self.permits_frame, orient=tk.VERTICAL, command=self.permits_tree.yview)
        permits_scrollx = ttk.Scrollbar(self.permits_frame, orient=tk.HORIZONTAL, command=self.permits_tree.xview)
        self.permits_tree.configure(yscrollcommand=permits_scrolly.set, xscrollcommand=permits_scrollx.set)
        
        # Pack treeview and scrollbars
        self.permits_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        permits_scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        permits_scrollx.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Load permits data
        self.refresh_permits()
    
    def setup_vehicles_tab(self):
        """Setup the vehicles management tab"""
        # Create toolbar
        toolbar = ttk.Frame(self.vehicles_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text=_t("parking.btn.register_vehicle"), command=self.register_vehicle_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("parking.btn.edit_selected"), command=self.edit_selected_vehicle).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("parking.btn.delete_selected"), command=self.delete_selected_vehicle).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("common.refresh"), command=self.refresh_vehicles).pack(side=tk.LEFT, padx=2)

        # Search frame
        search_frame = ttk.Frame(self.vehicles_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(search_frame, text=_t("common.search") + ":").pack(side=tk.LEFT)
        self.vehicle_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.vehicle_search_var)
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        search_entry.bind('<KeyRelease>', self.filter_vehicles)
        
        # Create treeview for vehicles
        columns = ("ID", "License Plate", "Make", "Model", "Year", "Color", "Type", "Owner")
        self.vehicles_tree = ttk.Treeview(self.vehicles_frame, columns=columns, show="headings")
        
        # Configure columns
        for col in columns:
            self.vehicles_tree.heading(col, text=col)
            self.vehicles_tree.column(col, width=100)
        
        # Add scrollbars
        vehicles_scrolly = ttk.Scrollbar(self.vehicles_frame, orient=tk.VERTICAL, command=self.vehicles_tree.yview)
        vehicles_scrollx = ttk.Scrollbar(self.vehicles_frame, orient=tk.HORIZONTAL, command=self.vehicles_tree.xview)
        self.vehicles_tree.configure(yscrollcommand=vehicles_scrolly.set, xscrollcommand=vehicles_scrollx.set)
        
        # Pack treeview and scrollbars
        self.vehicles_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        vehicles_scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        vehicles_scrollx.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Load vehicles data
        self.refresh_vehicles()
    
    def setup_violations_tab(self):
        """Setup the violations management tab"""
        # Create toolbar
        toolbar = ttk.Frame(self.violations_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text=_t("parking.btn.record_violation"), command=self.record_violation_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("parking.btn.edit_selected"), command=self.edit_selected_violation).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("parking.btn.delete_selected"), command=self.delete_selected_violation).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Pay Fine", command=self.pay_selected_violation).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("common.refresh"), command=self.refresh_violations).pack(side=tk.LEFT, padx=2)

        # Search frame
        search_frame = ttk.Frame(self.violations_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(search_frame, text=_t("common.search") + ":").pack(side=tk.LEFT)
        self.violation_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.violation_search_var)
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        search_entry.bind('<KeyRelease>', self.filter_violations)
        
        # Create treeview for violations
        columns = ("ID", "License Plate", "Type", "Date", "Fine", "Status", "Location", "Officer")
        self.violations_tree = ttk.Treeview(self.violations_frame, columns=columns, show="headings")
        
        # Configure columns
        for col in columns:
            self.violations_tree.heading(col, text=col)
            self.violations_tree.column(col, width=100)
        
        # Add scrollbars
        violations_scrolly = ttk.Scrollbar(self.violations_frame, orient=tk.VERTICAL, command=self.violations_tree.yview)
        violations_scrollx = ttk.Scrollbar(self.violations_frame, orient=tk.HORIZONTAL, command=self.violations_tree.xview)
        self.violations_tree.configure(yscrollcommand=violations_scrolly.set, xscrollcommand=violations_scrollx.set)
        
        # Pack treeview and scrollbars
        self.violations_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        violations_scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        violations_scrollx.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Load violations data
        self.refresh_violations()
    
    def setup_lots_tab(self):
        """Setup the parking lots management tab"""
        # Create toolbar
        toolbar = ttk.Frame(self.lots_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text=_t("parking.btn.add_lot"), command=self.add_lot_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("parking.btn.edit_selected"), command=self.edit_selected_lot).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("parking.btn.delete_selected"), command=self.delete_selected_lot).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("common.refresh"), command=self.refresh_lots).pack(side=tk.LEFT, padx=2)
        
        # Create treeview for lots
        columns = ("ID", "Name", "Location", "Total Spaces", "Available", "Zone", "Hours")
        self.lots_tree = ttk.Treeview(self.lots_frame, columns=columns, show="headings")
        
        # Configure columns
        for col in columns:
            self.lots_tree.heading(col, text=col)
            self.lots_tree.column(col, width=100)
        
        # Add scrollbars
        lots_scrolly = ttk.Scrollbar(self.lots_frame, orient=tk.VERTICAL, command=self.lots_tree.yview)
        lots_scrollx = ttk.Scrollbar(self.lots_frame, orient=tk.HORIZONTAL, command=self.lots_tree.xview)
        self.lots_tree.configure(yscrollcommand=lots_scrolly.set, xscrollcommand=lots_scrollx.set)
        
        # Pack treeview and scrollbars
        self.lots_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        lots_scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        lots_scrollx.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Load lots data
        self.refresh_lots()

    def setup_payments_tab(self):
        """Setup the payments and refunds management tab"""
        # Create toolbar
        toolbar = ttk.Frame(self.payments_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(toolbar, text="Refund Payment", command=self.refund_selected_payment).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="View Details", command=self.view_payment_details).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_t("common.refresh"), command=self.refresh_payments).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Export to CSV", command=self.export_payments_csv).pack(side=tk.LEFT, padx=2)

        # Search frame
        search_frame = ttk.Frame(self.payments_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(search_frame, text=_t("common.search") + ":").pack(side=tk.LEFT)
        self.payment_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.payment_search_var)
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        search_entry.bind('<KeyRelease>', self.filter_payments)

        # Create treeview for payments
        columns = ("Pay ID", "Violation ID", "Amount", "Method", "Reference", "Date", "Status")
        self.payments_tree = ttk.Treeview(self.payments_frame, columns=columns, show="headings")

        # Configure columns
        for col in columns:
            self.payments_tree.heading(col, text=col)
            self.payments_tree.column(col, width=120)

        # Add scrollbars
        payments_scrolly = ttk.Scrollbar(self.payments_frame, orient=tk.VERTICAL, command=self.payments_tree.yview)
        payments_scrollx = ttk.Scrollbar(self.payments_frame, orient=tk.HORIZONTAL, command=self.payments_tree.xview)
        self.payments_tree.configure(yscrollcommand=payments_scrolly.set, xscrollcommand=payments_scrollx.set)

        # Pack treeview and scrollbars
        self.payments_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        payments_scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        payments_scrollx.pack(side=tk.BOTTOM, fill=tk.X)

        # Load payments data
        self.refresh_payments()

    def refresh_payments(self):
        """Refresh payments list"""
        for item in self.payments_tree.get_children():
            self.payments_tree.delete(item)

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    p.payment_id,
                    p.violation_id,
                    p.amount,
                    p.payment_method,
                    p.payment_reference,
                    p.payment_date,
                    CASE
                        WHEN r.refund_id IS NOT NULL THEN 'Refunded'
                        ELSE 'Paid'
                    END as status
                FROM parking_payments p
                LEFT JOIN parking_refunds r ON p.payment_id = r.payment_id
                ORDER BY p.payment_date DESC
            """)
            payments = cursor.fetchall()
            conn.close()

            for payment in payments:
                values = (
                    payment[0],
                    payment[1],
                    f"${float(payment[2]):.2f}",
                    payment[3].replace('_', ' ').title(),
                    payment[4],
                    payment[5],
                    payment[6]
                )
                self.payments_tree.insert("", tk.END, values=values)

        except Exception as e:
            logging.error(f"Error refreshing payments: {e}")
            messagebox.showerror("Error", f"Failed to load payments: {str(e)}")

    def refund_selected_payment(self):
        """Refund selected payment"""
        selection = self.payments_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a payment to refund.")
            return

        values = self.payments_tree.item(selection[0])['values']

        # Check if already refunded
        if values[6] == 'Refunded':
            messagebox.showwarning("Already Refunded", "This payment has already been refunded.")
            return

        # Get full payment data
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT payment_id, violation_id, amount, payment_method, payment_reference, payment_date, student_id
            FROM parking_payments WHERE payment_id = ?
        """, (values[0],))
        payment_data = cursor.fetchone()
        conn.close()

        if payment_data:
            self.process_refund(payment_data)

    def view_payment_details(self):
        """View payment details"""
        selection = self.payments_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a payment to view.")
            return

        values = self.payments_tree.item(selection[0])['values']

        # Get full details
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, v.license_plate, v.violation_type, v.fine_amount
            FROM parking_payments p
            LEFT JOIN parking_violations v ON p.violation_id = v.violation_id
            WHERE p.payment_id = ?
        """, (values[0],))
        payment = cursor.fetchone()
        conn.close()

        if payment:
            details = f"""Payment ID: {payment[0]}
Violation ID: {payment[1]}
License Plate: {payment[10]}
Violation Type: {payment[11]}
Amount: ${float(payment[2]):.2f}
Payment Method: {payment[3].replace('_', ' ').title()}
Payment Reference: {payment[4]}
Payment Date: {payment[5]}
Student ID: {payment[6] or 'N/A'}
Processed By: {payment[7] or 'N/A'}
Notes: {payment[8] or 'None'}
"""
            messagebox.showinfo("Payment Details", details)

    def filter_payments(self, event=None):
        """Filter payments by search term"""
        search_term = self.payment_search_var.get().lower()

        all_items = self.payments_tree.get_children()

        for item in all_items:
            values = self.payments_tree.item(item)['values']
            if any(search_term in str(value).lower() for value in values):
                self.payments_tree.item(item, tags=())
            else:
                self.payments_tree.item(item, tags=('hidden',))

        self.payments_tree.tag_configure('hidden', foreground='gray')

    def export_payments_csv(self):
        """Export payments to CSV"""
        from tkinter import filedialog
        from datetime import datetime
        import csv

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"parking_payments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if not filename:
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.payment_id, p.violation_id, p.amount, p.payment_method,
                       p.payment_reference, p.payment_date, p.student_id, p.processed_by
                FROM parking_payments p
                ORDER BY p.payment_date DESC
            """)
            payments = cursor.fetchall()
            conn.close()

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Payment ID", "Violation ID", "Amount", "Method", "Reference",
                               "Date", "Student ID", "Processed By"])
                writer.writerows(payments)

            messagebox.showinfo("Export Successful", f"Payments exported to:\n{filename}")

        except Exception as e:
            logging.error(f"Error exporting payments: {e}")
            messagebox.showerror("Export Error", f"Failed to export payments: {str(e)}")

    def setup_dashboard_tab(self):
        """Setup the dashboard tab"""
        # Create main dashboard frame
        dashboard_main = ttk.Frame(self.dashboard_frame)
        dashboard_main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(dashboard_main, text=_t("parking.dashboard.title"),
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))

        # Create stats frame
        stats_frame = ttk.LabelFrame(dashboard_main, text=_t("parking.dashboard.title"))
        stats_frame.pack(fill=tk.X, pady=(0, 20))

        # Stats grid
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X, padx=10, pady=10)

        # Create stat labels
        self.stats_labels = {}
        stats = [
            (_t("parking.dashboard.active_permits"), "active_permits"),
            (_t("parking.dashboard.total_vehicles"), "total_vehicles"),
            (_t("parking.dashboard.unpaid_violations"), "unpaid_violations"),
            (_t("parking.dashboard.available_spaces"), "available_spaces")
        ]
        
        for i, (label, key) in enumerate(stats):
            row, col = i // 2, i % 2
            
            stat_frame = ttk.Frame(stats_grid)
            stat_frame.grid(row=row, column=col, padx=20, pady=10, sticky="w")
            
            ttk.Label(stat_frame, text=label + ":", font=("Arial", 10, "bold")).pack()
            self.stats_labels[key] = ttk.Label(stat_frame, text="Loading...", 
                                             font=("Arial", 12))
            self.stats_labels[key].pack()
        
        # Recent activity frame
        activity_frame = ttk.LabelFrame(dashboard_main, text=_t("parking.dashboard.recent_activity"))
        activity_frame.pack(fill=tk.BOTH, expand=True)
        
        self.activity_text = ScrolledText(activity_frame, height=10, state=tk.DISABLED)
        self.activity_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Refresh dashboard
        self.refresh_dashboard()
    
    def update_user_status(self):
        """Update the user status in the status bar"""
        if self.current_user:
            self.user_label.config(text=f"{_t('common.user')}: {self.current_user['first_name']} {self.current_user['last_name']} ({self.current_user['role']})")
        else:
            self.user_label.config(text=_t("parking.not_logged_in"))

    def update_status(self, message):
        """Update the status bar message"""
        self.status_label.config(text=message)
        # Clear status after 3 seconds
        self.root.after(3000, lambda: self.status_label.config(text=_t("common.ready")))
    
    def update_tab_access(self):
        """
        Enable/disable tabs based on user permissions

        Controls tab access based on user role:
        - Admin/Staff: Full access to all tabs
        - Student: Limited access (Dashboard, view own permits/vehicles/violations)
        - Guest/Unknown: Dashboard only

        Tabs are not removed, but their content may be restricted based on
        the user's role and permissions.
        """
        if not self.current_user:
            # No user logged in - minimal access
            return

        user_role = self.current_user.get('role', '').lower()

        # Define tab access based on role
        # For parking management, most operations require staff/admin privileges
        if user_role in ['admin', 'administrator', 'staff', 'faculty']:
            # Full access - all tabs available
            # Staff and faculty can manage parking operations
            pass

        elif user_role == 'student':
            # Students have view-only or self-service access
            # They can:
            # - View and manage their own permits
            # - Register their own vehicles
            # - View their own violations
            # - View parking lots and dashboard
            # The actual permission checks happen in individual tab methods
            pass

        else:
            # Guest or unknown role - dashboard only
            # Most tabs will show limited information
            pass

        # Note: Fine-grained permission checks are performed at the
        # operation level (create, edit, delete) within each tab's methods.
        # This method serves as a high-level access indicator.

        # Update UI elements based on permissions
        self._update_tab_buttons_state()

    def _update_tab_buttons_state(self):
        """
        Update button states in tabs based on user role

        Helper method to enable/disable action buttons within tabs
        based on the current user's role and permissions.
        """
        if not self.current_user:
            return

        user_role = self.current_user.get('role', '').lower()
        is_staff_or_admin = user_role in ['admin', 'administrator', 'staff', 'faculty']

        # For students, certain buttons (like administrative functions)
        # should be disabled. However, since button states are managed
        # within individual tab methods, this serves as a placeholder
        # for future fine-grained UI control.

        # Actual button state management happens at the tab level
        # when buttons are created with permission checks
        pass

    # Data refresh methods
    def refresh_all_data(self):
        """Refresh all data in all tabs"""
        self.refresh_permits()
        self.refresh_vehicles()
        self.refresh_violations()
        self.refresh_lots()
        self.refresh_dashboard()
        self.update_status("All data refreshed")
    
    def refresh_permits(self):
        """Refresh permits data"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT p.permit_id, p.full_name, p.zone, p.permit_type, 
                   p.start_date, p.end_date, p.active_status,
                   COALESCE(v.license_plate, 'N/A') as vehicle
            FROM parking_permits p
            LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
            ORDER BY p.issue_date DESC
            ''')
            
            permits = cursor.fetchall()
            
            # Clear existing data
            for item in self.permits_tree.get_children():
                self.permits_tree.delete(item)
            
            # Insert new data - convert sqlite3.Row to tuple for display
            for permit in permits:
                permit_values = tuple(permit) if hasattr(permit, '__iter__') else permit
                self.permits_tree.insert("", tk.END, values=permit_values)
            
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh permits: {e}")
    
    def refresh_vehicles(self):
        """Refresh vehicles data"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT v.vehicle_id, v.license_plate, v.make, v.model, v.year,
                   v.color, v.vehicle_type,
                   COALESCE(u.first_name || ' ' || u.last_name, 'N/A') as owner
            FROM vehicles v
            LEFT JOIN users u ON v.owner_id = u.id
            ORDER BY v.vehicle_id
            ''')
            
            vehicles = cursor.fetchall()
            
            # Clear existing data
            for item in self.vehicles_tree.get_children():
                self.vehicles_tree.delete(item)
            
            # Insert new data - convert sqlite3.Row to tuple for display
            for vehicle in vehicles:
                vehicle_values = tuple(vehicle) if hasattr(vehicle, '__iter__') else vehicle
                self.vehicles_tree.insert("", tk.END, values=vehicle_values)
            
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh vehicles: {e}")
    
    def refresh_violations(self):
        """Refresh violations data"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT v.violation_id, v.license_plate, v.violation_type,
                   v.violation_date, v.fine_amount, v.payment_status,
                   v.location,
                   COALESCE(u.first_name || ' ' || u.last_name, 'N/A') as officer
            FROM parking_violations v
            LEFT JOIN users u ON v.officer_id = u.id
            ORDER BY v.violation_date DESC
            ''')
            
            violations = cursor.fetchall()
            
            # Clear existing data
            for item in self.violations_tree.get_children():
                self.violations_tree.delete(item)
            
            # Insert new data - convert sqlite3.Row to tuple for display
            for violation in violations:
                violation_values = tuple(violation) if hasattr(violation, '__iter__') else violation
                self.violations_tree.insert("", tk.END, values=violation_values)
            
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh violations: {e}")
    
    def refresh_lots(self):
        """Refresh parking lots data"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM parking_lots ORDER BY lot_id')
            lots = cursor.fetchall()

            # Clear existing data
            for item in self.lots_tree.get_children():
                self.lots_tree.delete(item)

            # Insert new data - convert sqlite3.Row to tuple for display
            for lot in lots:
                # Convert sqlite3.Row object to tuple to avoid display issues
                lot_values = tuple(lot) if hasattr(lot, '__iter__') else lot
                self.lots_tree.insert("", tk.END, values=lot_values)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh lots: {e}")
    
    def refresh_dashboard(self):
        """Refresh dashboard statistics"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get statistics
            cursor.execute("SELECT COUNT(*) FROM parking_permits WHERE active_status = 'Active'")
            active_permits = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM vehicles")
            total_vehicles = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM parking_violations WHERE payment_status = 'Unpaid'")
            unpaid_violations = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(available_spaces) FROM parking_lots")
            available_spaces = cursor.fetchone()[0] or 0
            
            # Update stats labels
            self.stats_labels["active_permits"].config(text=str(active_permits))
            self.stats_labels["total_vehicles"].config(text=str(total_vehicles))
            self.stats_labels["unpaid_violations"].config(text=str(unpaid_violations))
            self.stats_labels["available_spaces"].config(text=str(available_spaces))
            
            # Get recent activity
            cursor.execute('''
            SELECT 'Permit' as type, permit_id as id, issue_date as date, full_name as details
            FROM parking_permits
            WHERE date(issue_date) >= date('now', '-7 days')
            UNION ALL
            SELECT 'Violation' as type, violation_id as id, violation_date as date, 
                   violation_type || ' - ' || license_plate as details
            FROM parking_violations
            WHERE date(violation_date) >= date('now', '-7 days')
            ORDER BY date DESC
            LIMIT 20
            ''')
            
            activities = cursor.fetchall()
            
            # Update activity text
            self.activity_text.config(state=tk.NORMAL)
            self.activity_text.delete(1.0, tk.END)
            
            if activities:
                for activity in activities:
                    self.activity_text.insert(tk.END, 
                        f"{activity[1]} - {activity[0]} - {activity[3]} ({activity[2]})\n")
            else:
                self.activity_text.insert(tk.END, "No recent activity")
            
            self.activity_text.config(state=tk.DISABLED)
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh dashboard: {e}")
    
    # Filter methods
    def filter_permits(self, event=None):
        """Filter permits based on search term"""
        search_term = self.permit_search_var.get().lower()
        
        # Get all items
        all_items = self.permits_tree.get_children()
        
        for item in all_items:
            values = self.permits_tree.item(item)['values']
            # Check if search term is in any of the values
            if any(search_term in str(value).lower() for value in values):
                self.permits_tree.item(item, tags=())
            else:
                self.permits_tree.item(item, tags=('hidden',))
        
        # Configure tags
        self.permits_tree.tag_configure('hidden', foreground='gray')
    
    def filter_vehicles(self, event=None):
        """Filter vehicles based on search term"""
        search_term = self.vehicle_search_var.get().lower()
        
        all_items = self.vehicles_tree.get_children()
        
        for item in all_items:
            values = self.vehicles_tree.item(item)['values']
            if any(search_term in str(value).lower() for value in values):
                self.vehicles_tree.item(item, tags=())
            else:
                self.vehicles_tree.item(item, tags=('hidden',))
        
        self.vehicles_tree.tag_configure('hidden', foreground='gray')
    
    def filter_violations(self, event=None):
        """Filter violations based on search term"""
        search_term = self.violation_search_var.get().lower()
        
        all_items = self.violations_tree.get_children()
        
        for item in all_items:
            values = self.violations_tree.item(item)['values']
            if any(search_term in str(value).lower() for value in values):
                self.violations_tree.item(item, tags=())
            else:
                self.violations_tree.item(item, tags=('hidden',))
        
        self.violations_tree.tag_configure('hidden', foreground='gray')
    
    # Dialog methods
    def create_permit_dialog(self):
        """Show create permit dialog"""
        dialog = PermitDialog(self.root, "Create New Permit")
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            # Create permit with the provided data
            try:
                self.create_permit_from_data(dialog.result)
                self.refresh_permits()
                self.update_status("Permit created successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create permit: {e}")
    
    def register_vehicle_dialog(self):
        """Show register vehicle dialog"""
        dialog = VehicleDialog(self.root, "Register New Vehicle")
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            try:
                self.register_vehicle_from_data(dialog.result)
                self.refresh_vehicles()
                self.update_status("Vehicle registered successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to register vehicle: {e}")
    
    def record_violation_dialog(self):
        """Show record violation dialog"""
        dialog = ViolationDialog(self.root, "Record New Violation")
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            try:
                self.record_violation_from_data(dialog.result)
                self.refresh_violations()
                self.update_status("Violation recorded successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to record violation: {e}")
    
    def add_lot_dialog(self):
        """Show add lot dialog"""
        dialog = LotDialog(self.root, "Add New Parking Lot")
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            try:
                self.add_lot_from_data(dialog.result)
                self.refresh_lots()
                self.update_status("Parking lot added successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add parking lot: {e}")
    
    # Edit/Delete methods
    def edit_selected_permit(self):
        """Edit the selected permit"""
        selected = self.permits_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a permit to edit")
            return
        
        # Get permit data and show edit dialog
        permit_id = self.permits_tree.item(selected[0])['values'][0]
        
        try:
            # Get full permit data from database
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM parking_permits WHERE permit_id = ?', (permit_id,))
            permit_data = cursor.fetchone()
            conn.close()
            
            if permit_data:
                dialog = PermitDialog(self.root, "Edit Permit", permit_data)
                self.root.wait_window(dialog.dialog)
                
                if dialog.result:
                    self.update_permit_from_data(permit_id, dialog.result)
                    self.refresh_permits()
                    self.update_status("Permit updated successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to edit permit: {e}")
    
    def delete_selected_permit(self):
        """Delete the selected permit"""
        selected = self.permits_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a permit to delete")
            return
        
        permit_id = self.permits_tree.item(selected[0])['values'][0]
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete permit {permit_id}?"):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM parking_permits WHERE permit_id = ?', (permit_id,))
                conn.commit()
                conn.close()
                
                self.refresh_permits()
                self.update_status("Permit deleted successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete permit: {e}")
    
    def edit_selected_vehicle(self):
        """Edit the selected vehicle"""
        selected = self.vehicles_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a vehicle to edit")
            return
        
        vehicle_id = self.vehicles_tree.item(selected[0])['values'][0]
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM vehicles WHERE vehicle_id = ?', (vehicle_id,))
            vehicle_data = cursor.fetchone()
            conn.close()
            
            if vehicle_data:
                dialog = VehicleDialog(self.root, "Edit Vehicle", vehicle_data)
                self.root.wait_window(dialog.dialog)
                
                if dialog.result:
                    self.update_vehicle_from_data(vehicle_id, dialog.result)
                    self.refresh_vehicles()
                    self.update_status("Vehicle updated successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to edit vehicle: {e}")
    
    def delete_selected_vehicle(self):
        """Delete the selected vehicle"""
        selected = self.vehicles_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a vehicle to delete")
            return
        
        vehicle_id = self.vehicles_tree.item(selected[0])['values'][0]
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete vehicle {vehicle_id}?"):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM vehicles WHERE vehicle_id = ?', (vehicle_id,))
                conn.commit()
                conn.close()
                
                self.refresh_vehicles()
                self.update_status("Vehicle deleted successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete vehicle: {e}")
    
    def edit_selected_violation(self):
        """Edit the selected violation"""
        selected = self.violations_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a violation to edit")
            return
        
        violation_id = self.violations_tree.item(selected[0])['values'][0]
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM parking_violations WHERE violation_id = ?', (violation_id,))
            violation_data = cursor.fetchone()
            conn.close()
            
            if violation_data:
                dialog = ViolationDialog(self.root, "Edit Violation", violation_data)
                self.root.wait_window(dialog.dialog)
                
                if dialog.result:
                    self.update_violation_from_data(violation_id, dialog.result)
                    self.refresh_violations()
                    self.update_status("Violation updated successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to edit violation: {e}")
    
    def delete_selected_violation(self):
        """Delete the selected violation"""
        selected = self.violations_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a violation to delete")
            return
        
        violation_id = self.violations_tree.item(selected[0])['values'][0]
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete violation {violation_id}?"):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM parking_violations WHERE violation_id = ?', (violation_id,))
                conn.commit()
                conn.close()
                
                self.refresh_violations()
                self.update_status("Violation deleted successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete violation: {e}")

    def pay_selected_violation(self):
        """Pay fine for selected violation"""
        selected = self.violations_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a violation to pay.")
            return

        violation_data = self.violations_tree.item(selected[0])['values']

        # Check if already paid
        if len(violation_data) > 5 and violation_data[5] == 'Paid':
            messagebox.showinfo("Already Paid", "This violation has already been paid.")
            return

        # Process payment
        self.process_payment(violation_data)

    def process_payment(self, violation_data):
        """Show payment dialog and process payment"""
        dialog = PaymentDialog(self.root, violation_data, self.current_user)
        self.root.wait_window(dialog.dialog)

        if not dialog.result:
            return

        try:
            from university_system.infrastructure.database.db import transaction
            from datetime import datetime

            payment_ref = f"PARKING-PAY-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            processed_by = self.current_user.get('username') if self.current_user else 'system'

            with transaction() as conn:
                cursor = conn.cursor()

                # Record payment
                cursor.execute("""
                    INSERT INTO parking_payments
                    (violation_id, amount, payment_method, payment_reference, student_id, processed_by, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (dialog.result['violation_id'], dialog.result['amount'], dialog.result['payment_method'],
                      payment_ref, dialog.result['student_id'], processed_by, 'Parking fine payment'))

                # Update violation status
                cursor.execute("""
                    UPDATE parking_violations
                    SET payment_status = 'Paid'
                    WHERE violation_id = ?
                """, (dialog.result['violation_id'],))

                # If student account, deduct amount
                if dialog.result['payment_method'] == 'student_account' and dialog.result['student_id']:
                    cursor.execute("""
                        UPDATE student_finance_accounts
                        SET balance = balance - ?
                        WHERE student_id = ?
                    """, (dialog.result['amount'], dialog.result['student_id']))

                    # Log in student finance transactions
                    cursor.execute("SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?",
                                 (dialog.result['student_id'],))
                    account_result = cursor.fetchone()
                    if account_result:
                        account_id, new_balance = account_result
                        cursor.execute("""
                            INSERT INTO student_finance_transactions
                            (account_id, student_id, transaction_type, amount, balance_after, description,
                             reference_id, processed_by, created_at)
                            VALUES (?, ?, 'debit', ?, ?, ?, ?, ?, ?)
                        """, (account_id, dialog.result['student_id'], dialog.result['amount'], new_balance,
                              f"Parking fine payment - {payment_ref}", payment_ref, processed_by,
                              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                # Add to finance system for central tracking
                try:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS finance_payments (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            payment_reference TEXT UNIQUE,
                            department TEXT,
                            transaction_id TEXT,
                            amount DECIMAL(10,2),
                            payment_method TEXT,
                            payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            processed_by TEXT,
                            notes TEXT
                        )
                    """)
                    cursor.execute("""
                        INSERT INTO finance_payments
                        (payment_reference, department, transaction_id, amount, payment_method, processed_by, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (payment_ref, 'Parking Services', dialog.result['violation_id'], dialog.result['amount'],
                          dialog.result['payment_method'], processed_by, 'Parking fine payment'))
                except Exception as e:
                    logging.warning(f"Could not log to finance_payments: {e}")

            # Send confirmation email
            self.send_payment_confirmation_email(dialog.result['violation_id'], dialog.result['amount'],
                                                dialog.result['payment_method'], payment_ref,
                                                dialog.result['student_id'], violation_data)

            # Refresh violations list
            self.refresh_violations()

            messagebox.showinfo("Payment Successful",
                              f"Payment processed successfully!\nReference: {payment_ref}")

        except Exception as e:
            logging.error(f"Error processing payment: {e}")
            messagebox.showerror("Payment Error", f"Failed to process payment: {str(e)}")

    def send_payment_confirmation_email(self, violation_id, amount, payment_method, payment_ref, student_id, violation_data):
        """Send payment confirmation email"""
        try:
            from university_system.infrastructure.email.email_service import send_email
            from datetime import datetime

            # Get student/owner details
            if not student_id:
                return

            conn = get_connection()
            cursor = conn.cursor()

            # Try students table first
            cursor.execute("SELECT first_name, last_name, email_address FROM students WHERE student_id = ?", (student_id,))
            result = cursor.fetchone()

            if result and result[2]:
                student_name = f"{result[0]} {result[1]}"
                student_email = result[2]
            else:
                # Fall back to users table
                cursor.execute("SELECT first_name, last_name, email, username FROM users WHERE username = ? OR id = ?",
                             (student_id, student_id))
                result = cursor.fetchone()
                if result and result[2]:
                    student_name = f"{result[0] or ''} {result[1] or ''}".strip() or result[3]
                    student_email = result[2]
                else:
                    logging.warning(f"No email found for student {student_id}")
                    conn.close()
                    return

            conn.close()

            # Build email
            try:
                if TEMPLATE_AVAILABLE:
                    subject, body = render_template('parking_fine_payment_confirmation', {
                        'student_name': student_name,
                        'fine_id': str(violation_id),
                        'amount': f"{amount:.2f}",
                        'payment_method': payment_method.replace('_', ' ').title(),
                        'payment_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                        'payment_id': payment_ref
                    })
                else:
                    raise Exception("Template not available")
            except Exception as template_error:
                logging.warning(f"Failed to render template: {template_error}. Using fallback email.")
                subject = f"Parking Fine Payment Confirmation - {payment_ref}"
                body = f"""Dear {student_name},

This confirms your parking fine payment has been processed successfully.

Payment Details:
- Violation ID: {violation_id}
- Amount Paid: ${amount:.2f}
- Payment Method: {payment_method.replace('_', ' ').title()}
- Payment Reference: {payment_ref}
- Payment Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Violation Details:
- Type: {violation_data[2]}
- License Plate: {violation_data[1]}
- Date: {violation_data[3]}
- Location: {violation_data[6]}

Your violation status is now: PAID

Thank you for your prompt payment.

Parking Services
University Parking Management
"""

            send_email(recipient_email=student_email, subject=subject, body=body)
            logging.info(f"Payment confirmation email sent to {student_email}")

        except Exception as e:
            logging.error(f"Error sending payment confirmation email: {e}")

    def process_refund(self, payment_data):
        """Show refund dialog and process refund"""
        dialog = RefundDialog(self.root, payment_data, self.current_user)
        self.root.wait_window(dialog.dialog)

        if not dialog.result:
            return

        try:
            from university_system.infrastructure.database.db import transaction
            from datetime import datetime

            refund_ref = f"PARKING-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            processed_by = self.current_user.get('username') if self.current_user else 'system'

            with transaction() as conn:
                cursor = conn.cursor()

                # Record refund
                cursor.execute("""
                    INSERT INTO parking_refunds
                    (payment_id, violation_id, amount, refund_method, refund_reference, student_id, processed_by, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (dialog.result['payment_id'], dialog.result['violation_id'], dialog.result['amount'],
                      dialog.result['refund_method'], refund_ref, dialog.result['student_id'], processed_by,
                      'Parking fine refund'))

                # Update violation status
                cursor.execute("""
                    UPDATE parking_violations
                    SET payment_status = 'Refunded'
                    WHERE violation_id = ?
                """, (dialog.result['violation_id'],))

                # Update payment notes
                try:
                    cursor.execute("""
                        UPDATE parking_payments
                        SET notes = notes || ' [REFUNDED: ' || ? || ']'
                        WHERE payment_id = ?
                    """, (refund_ref, dialog.result['payment_id']))
                except Exception:
                    pass

                # If student account, add refund amount
                if dialog.result['refund_method'] == 'student_account' and dialog.result['student_id']:
                    cursor.execute("""
                        UPDATE student_finance_accounts
                        SET balance = balance + ?
                        WHERE student_id = ?
                    """, (dialog.result['amount'], dialog.result['student_id']))

                    # Log in student finance transactions
                    cursor.execute("SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?",
                                 (dialog.result['student_id'],))
                    account_result = cursor.fetchone()
                    if account_result:
                        account_id, new_balance = account_result
                        cursor.execute("""
                            INSERT INTO student_finance_transactions
                            (account_id, student_id, transaction_type, amount, balance_after, description,
                             reference_id, processed_by, created_at)
                            VALUES (?, ?, 'credit', ?, ?, ?, ?, ?, ?)
                        """, (account_id, dialog.result['student_id'], dialog.result['amount'], new_balance,
                              f"Parking fine refund - {refund_ref}", refund_ref, processed_by,
                              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                # Add to finance_refunds for central tracking
                cursor.execute("""
                    INSERT OR IGNORE INTO finance_refunds
                    (refund_reference, department, transaction_id, amount, refund_method, processed_by, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (refund_ref, 'Parking Services', dialog.result['violation_id'], dialog.result['amount'],
                      dialog.result['refund_method'], processed_by, 'Parking fine refund'))

            # Send confirmation email
            self.send_refund_confirmation_email(dialog.result['violation_id'], dialog.result['amount'],
                                              dialog.result['refund_method'], refund_ref,
                                              dialog.result['student_id'], payment_data)

            # Refresh payments list
            if hasattr(self, 'refresh_payments'):
                self.refresh_payments()

            messagebox.showinfo("Refund Successful",
                              f"Refund processed successfully!\nReference: {refund_ref}")

        except Exception as e:
            logging.error(f"Error processing refund: {e}")
            messagebox.showerror("Refund Error", f"Failed to process refund: {str(e)}")

    def send_refund_confirmation_email(self, violation_id, amount, refund_method, refund_ref, student_id, payment_data):
        """Send refund confirmation email"""
        try:
            from university_system.infrastructure.email.email_service import send_email
            from datetime import datetime

            if not student_id:
                return

            conn = get_connection()
            cursor = conn.cursor()

            # Try students table first
            cursor.execute("SELECT first_name, last_name, email_address FROM students WHERE student_id = ?", (student_id,))
            result = cursor.fetchone()

            if result and result[2]:
                student_name = f"{result[0]} {result[1]}"
                student_email = result[2]
            else:
                # Fall back to users table
                cursor.execute("SELECT first_name, last_name, email, username FROM users WHERE username = ? OR id = ?",
                             (student_id, student_id))
                result = cursor.fetchone()
                if result and result[2]:
                    student_name = f"{result[0] or ''} {result[1] or ''}".strip() or result[3]
                    student_email = result[2]
                else:
                    logging.warning(f"No email found for student {student_id}")
                    conn.close()
                    return

            # Get new balance if student account refund
            balance_text = ""
            if refund_method == 'student_account':
                cursor.execute("SELECT balance FROM student_finance_accounts WHERE student_id = ?", (student_id,))
                balance_result = cursor.fetchone()
                if balance_result:
                    balance_text = f"\nYour new student account balance is: ${balance_result[0]:.2f}\n"

            conn.close()

            # Build email
            try:
                if TEMPLATE_AVAILABLE:
                    subject, body = render_template('parking_fine_refund_confirmation', {
                        'student_name': student_name,
                        'fine_id': str(violation_id),
                        'amount': f"{amount:.2f}",
                        'payment_method': refund_method.replace('_', ' ').title(),
                        'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                        'refund_id': refund_ref
                    })
                else:
                    raise Exception("Template not available")
            except Exception as template_error:
                logging.warning(f"Failed to render template: {template_error}. Using fallback email.")
                subject = f"Parking Fine Refund Confirmation - {refund_ref}"
                body = f"""Dear {student_name},

This confirms your parking fine refund has been processed successfully.

Refund Details:
- Violation ID: {violation_id}
- Refund Amount: ${amount:.2f}
- Refund Method: {refund_method.replace('_', ' ').title()}
- Refund Reference: {refund_ref}
- Refund Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Original Payment:
- Payment Reference: {payment_data[4]}
- Payment Date: {payment_data[5]}
{balance_text}
If you have any questions about this refund, please contact Parking Services.

Parking Services
University Parking Management
"""

            send_email(recipient_email=student_email, subject=subject, body=body)
            logging.info(f"Refund confirmation email sent to {student_email}")

        except Exception as e:
            logging.error(f"Error sending refund confirmation email: {e}")

    def edit_selected_lot(self):
        """Edit the selected parking lot"""
        selected = self.lots_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a lot to edit")
            return
        
        lot_id = self.lots_tree.item(selected[0])['values'][0]
        
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM parking_lots WHERE lot_id = ?', (lot_id,))
            lot_data = cursor.fetchone()
            conn.close()
            
            if lot_data:
                dialog = LotDialog(self.root, "Edit Parking Lot", lot_data)
                self.root.wait_window(dialog.dialog)
                
                if dialog.result:
                    self.update_lot_from_data(lot_id, dialog.result)
                    self.refresh_lots()
                    self.update_status("Parking lot updated successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to edit lot: {e}")
    
    def delete_selected_lot(self):
        """Delete the selected parking lot"""
        selected = self.lots_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a lot to delete")
            return
        
        lot_id = self.lots_tree.item(selected[0])['values'][0]
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete lot {lot_id}?"):
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM parking_lots WHERE lot_id = ?', (lot_id,))
                conn.commit()
                conn.close()
                
                self.refresh_lots()
                self.update_status("Parking lot deleted successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete lot: {e}")
    
    # Database operation methods
    def create_permit_from_data(self, data):
        """Create a permit from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()
        
        # Generate permit ID
        cursor.execute('SELECT COUNT(*) FROM parking_permits')
        count = cursor.fetchone()[0] + 1
        permit_id = f"P{data['zone']}{datetime.now().year % 100}{str(count).zfill(4)}"
        
        # Insert permit
        cursor.execute('''
        INSERT INTO parking_permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            permit_id,
            data.get('user_id'),
            data['full_name'],
            data['email'],
            data['zone'],
            data['permit_type'],
            data['start_date'],
            data['end_date'],
            'Active',
            data.get('vehicle_id'),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

        conn.commit()
        conn.close()

        # Send permit confirmation email automatically
        try:
            from university_system.infrastructure.email.email_service import send_permit_confirmation
            send_permit_confirmation(
                permit_id,
                data['email'],
                data['zone'],
                data['permit_type'],
                data['start_date'],
                data['end_date']
            )
        except Exception as e:
            import logging
            logging.warning(f"Failed to send permit confirmation email: {e}")

    def register_vehicle_from_data(self, data):
        """Register a vehicle from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Generate vehicle ID
            cursor.execute('SELECT COUNT(*) FROM vehicles')
            count = cursor.fetchone()[0] + 1
            vehicle_id = f"V{str(count).zfill(6)}"

            # Validate owner_id if provided
            owner_id = data.get('owner_id')
            if owner_id:
                try:
                    owner_id = int(owner_id)
                    # Verify user exists
                    cursor.execute('SELECT id FROM users WHERE id = ?', (owner_id,))
                    if not cursor.fetchone():
                        logging.warning(f"Owner ID {owner_id} not found in users table, setting to NULL")
                        owner_id = None
                except (ValueError, TypeError):
                    logging.warning(f"Invalid owner_id format: {owner_id}, setting to NULL")
                    owner_id = None

            # Insert vehicle
            cursor.execute('''
            INSERT INTO vehicles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                vehicle_id,
                data['license_plate'],
                data['make'],
                data['model'],
                data['year'],
                data['color'],
                data['vehicle_type'],
                owner_id,
                data['registration_state']
            ))

            conn.commit()
            logging.info(f"Vehicle {vehicle_id} registered successfully with owner_id={owner_id}")
        except Exception as e:
            conn.rollback()
            logging.error(f"Failed to register vehicle: {e}")
            raise
        finally:
            conn.close()
    
    def record_violation_from_data(self, data):
        """Record a violation from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()

        # Generate violation ID
        cursor.execute('SELECT COUNT(*) FROM parking_violations')
        count = cursor.fetchone()[0] + 1
        violation_id = f"VIO{str(count).zfill(6)}"

        # Insert violation
        cursor.execute('''
        INSERT INTO parking_violations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            violation_id,
            data.get('vehicle_id'),
            data['license_plate'],
            data['violation_type'],
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            data['fine_amount'],
            'Unpaid',
            data['location'],
            self.current_user['id']
        ))

        conn.commit()
        conn.close()

        # Send email notification if requested
        if data.get('send_email', False) and data.get('student_email'):
            self._send_violation_email(
                violation_id,
                data['student_id'],
                data['student_email'],
                data['license_plate'],
                data['violation_type'],
                data['location'],
                data['fine_amount']
            )
    
    def add_lot_from_data(self, data):
        """Add a parking lot from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()
        
        # Generate lot ID
        cursor.execute('SELECT COUNT(*) FROM parking_lots')
        count = cursor.fetchone()[0] + 1
        lot_id = f"L{str(count).zfill(3)}"
        
        # Insert lot
        cursor.execute('''
        INSERT INTO parking_lots VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            lot_id,
            data['lot_name'],
            data['location'],
            data['total_spaces'],
            data['total_spaces'],  # Initially all spaces are available
            data['zone'],
            data['hours']
        ))
        
        conn.commit()
        conn.close()
    
    def update_permit_from_data(self, permit_id, data):
        """Update a permit from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE parking_permits 
        SET full_name=?, email=?, zone=?, permit_type=?, 
            start_date=?, end_date=?, active_status=?, vehicle_id=?
        WHERE permit_id=?
        ''', (
            data['full_name'],
            data['email'],
            data['zone'],
            data['permit_type'],
            data['start_date'],
            data['end_date'],
            data.get('active_status', 'Active'),
            data.get('vehicle_id'),
            permit_id
        ))

        conn.commit()
        conn.close()

        # Send permit update confirmation email automatically
        try:
            from university_system.infrastructure.email.email_service import send_permit_update_confirmation
            # Identify which fields were updated
            updated_fields = []
            if 'full_name' in data:
                updated_fields.append(f"Full Name: {data['full_name']}")
            if 'zone' in data:
                updated_fields.append(f"Zone: {data['zone']}")
            if 'permit_type' in data:
                updated_fields.append(f"Permit Type: {data['permit_type']}")
            if 'start_date' in data:
                updated_fields.append(f"Start Date: {data['start_date']}")
            if 'end_date' in data:
                updated_fields.append(f"End Date: {data['end_date']}")
            if 'active_status' in data:
                updated_fields.append(f"Status: {data.get('active_status', 'Active')}")

            send_permit_update_confirmation(
                permit_id,
                data['email'],
                updated_fields
            )
        except Exception as e:
            import logging
            logging.warning(f"Failed to send permit update confirmation email: {e}")

    def update_vehicle_from_data(self, vehicle_id, data):
        """Update a vehicle from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE vehicles 
        SET license_plate=?, make=?, model=?, year=?, color=?, 
            vehicle_type=?, registration_state=?
        WHERE vehicle_id=?
        ''', (
            data['license_plate'],
            data['make'],
            data['model'],
            data['year'],
            data['color'],
            data['vehicle_type'],
            data['registration_state'],
            vehicle_id
        ))
        
        conn.commit()
        conn.close()
    
    def update_violation_from_data(self, violation_id, data):
        """Update a violation from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE parking_violations 
        SET violation_type=?, fine_amount=?, payment_status=?, location=?
        WHERE violation_id=?
        ''', (
            data['violation_type'],
            data['fine_amount'],
            data['payment_status'],
            data['location'],
            violation_id
        ))
        
        conn.commit()
        conn.close()
    
    def update_lot_from_data(self, lot_id, data):
        """Update a parking lot from dialog data"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE parking_lots 
        SET lot_name=?, location=?, total_spaces=?, zone=?, hours_of_operation=?
        WHERE lot_id=?
        ''', (
            data['lot_name'],
            data['location'],
            data['total_spaces'],
            data['zone'],
            data['hours'],
            lot_id
        ))
        
        conn.commit()
        conn.close()
    
    # Report methods
    def generate_permit_report(self):
        """Generate permit report"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Generate comprehensive permit report
            output = []
            output.append("PARKING PERMIT REPORT")
            output.append("=" * 80)
            output.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            output.append("")

            # Active Permits
            output.append("ACTIVE PERMITS")
            output.append("-" * 80)
            cursor.execute('''
                SELECT p.permit_id, p.full_name, p.zone, p.permit_type,
                       p.issue_date, p.end_date, v.license_plate
                FROM parking_permits p
                LEFT JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                WHERE p.active_status = 'Active'
                ORDER BY p.zone, p.issue_date DESC
            ''')
            active_permits = cursor.fetchall()

            if active_permits:
                output.append(f"{'ID':<12} {'Name':<25} {'Zone':<6} {'Type':<12} {'License':<12} {'Issued':<12} {'Expires':<12}")
                output.append("-" * 80)
                for permit in active_permits:
                    output.append(f"{permit[0]:<12} {permit[1]:<25} {permit[2]:<6} {permit[3]:<12} {permit[6] or 'N/A':<12} {permit[4]:<12} {permit[5]:<12}")
                output.append(f"\nTotal Active Permits: {len(active_permits)}")
            else:
                output.append("No active permits found.")

            output.append("\n")

            # Permits by Zone
            output.append("PERMITS BY ZONE")
            output.append("-" * 80)
            cursor.execute('''
                SELECT zone, COUNT(*) as count,
                       SUM(CASE WHEN active_status = 'Active' THEN 1 ELSE 0 END) as active
                FROM parking_permits
                GROUP BY zone
                ORDER BY zone
            ''')
            zone_stats = cursor.fetchall()

            if zone_stats:
                output.append(f"{'Zone':<10} {'Total':<10} {'Active':<10}")
                output.append("-" * 30)
                for stat in zone_stats:
                    output.append(f"{stat[0]:<10} {stat[1]:<10} {stat[2]:<10}")
            else:
                output.append("No zone data available.")

            output.append("\n")

            # Permits by Type
            output.append("PERMITS BY TYPE")
            output.append("-" * 80)
            cursor.execute('''
                SELECT permit_type, COUNT(*) as count,
                       SUM(CASE WHEN active_status = 'Active' THEN 1 ELSE 0 END) as active
                FROM parking_permits
                GROUP BY permit_type
                ORDER BY count DESC
            ''')
            type_stats = cursor.fetchall()

            if type_stats:
                output.append(f"{'Type':<15} {'Total':<10} {'Active':<10}")
                output.append("-" * 35)
                for stat in type_stats:
                    output.append(f"{stat[0]:<15} {stat[1]:<10} {stat[2]:<10}")
            else:
                output.append("No type data available.")

            output.append("\n")

            # Expiring Soon (within 30 days)
            output.append("PERMITS EXPIRING SOON (Next 30 Days)")
            output.append("-" * 80)
            cursor.execute('''
                SELECT permit_id, full_name, zone, permit_type, end_date
                FROM parking_permits
                WHERE active_status = 'Active'
                AND date(end_date) BETWEEN date('now') AND date('now', '+30 days')
                ORDER BY end_date
            ''')
            expiring = cursor.fetchall()

            if expiring:
                output.append(f"{'ID':<12} {'Name':<30} {'Zone':<6} {'Type':<12} {'Expires':<12}")
                output.append("-" * 72)
                for permit in expiring:
                    output.append(f"{permit[0]:<12} {permit[1]:<30} {permit[2]:<6} {permit[3]:<12} {permit[4]:<12}")
                output.append(f"\nTotal Expiring Soon: {len(expiring)}")
            else:
                output.append("No permits expiring in the next 30 days.")

            conn.close()

            # Show in dialog
            self.show_text_dialog("Parking Permit Report", "\n".join(output))
        except Exception as e:
            logging.error(f"Error generating permit report: {e}")
            messagebox.showerror("Error", f"Failed to generate permit report: {e}")

    def generate_violation_report(self):
        """Generate violation report"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Generate comprehensive violation report
            output = []
            output.append("PARKING VIOLATION REPORT")
            output.append("=" * 80)
            output.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            output.append("")

            # All Violations Summary
            output.append("VIOLATION SUMMARY")
            output.append("-" * 80)
            cursor.execute('''
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN payment_status = 'Paid' THEN 1 ELSE 0 END) as paid,
                       SUM(CASE WHEN payment_status = 'Unpaid' THEN 1 ELSE 0 END) as unpaid,
                       SUM(CASE WHEN payment_status = 'Pending' THEN 1 ELSE 0 END) as pending,
                       SUM(fine_amount) as total_fines,
                       SUM(CASE WHEN payment_status = 'Paid' THEN fine_amount ELSE 0 END) as collected,
                       SUM(CASE WHEN payment_status = 'Unpaid' THEN fine_amount ELSE 0 END) as outstanding
                FROM parking_violations
            ''')
            summary = cursor.fetchone()

            output.append(f"Total Violations: {summary[0] or 0}")
            output.append(f"  - Paid: {summary[1] or 0}")
            output.append(f"  - Unpaid: {summary[2] or 0}")
            output.append(f"  - Pending: {summary[3] or 0}")
            output.append(f"Total Fines: ${summary[4] or 0:.2f}")
            output.append(f"  - Collected: ${summary[5] or 0:.2f}")
            output.append(f"  - Outstanding: ${summary[6] or 0:.2f}")

            output.append("\n")

            # Violations by Type
            output.append("VIOLATIONS BY TYPE")
            output.append("-" * 80)
            cursor.execute('''
                SELECT violation_type, COUNT(*) as count,
                       SUM(fine_amount) as total_fines,
                       SUM(CASE WHEN payment_status = 'Unpaid' THEN 1 ELSE 0 END) as unpaid
                FROM parking_violations
                GROUP BY violation_type
                ORDER BY count DESC
            ''')
            type_stats = cursor.fetchall()

            if type_stats:
                output.append(f"{'Type':<30} {'Count':<10} {'Total Fines':<15} {'Unpaid':<10}")
                output.append("-" * 65)
                for stat in type_stats:
                    output.append(f"{stat[0]:<30} {stat[1]:<10} ${stat[2]:<14.2f} {stat[3]:<10}")
            else:
                output.append("No violation data available.")

            output.append("\n")

            # Recent Violations (last 30 days)
            output.append("RECENT VIOLATIONS (Last 30 Days)")
            output.append("-" * 80)
            cursor.execute('''
                SELECT v.violation_id, v.license_plate, v.violation_type,
                       v.violation_date, v.fine_amount, v.payment_status, v.location
                FROM parking_violations v
                WHERE date(v.violation_date) >= date('now', '-30 days')
                ORDER BY v.violation_date DESC
                LIMIT 50
            ''')
            recent = cursor.fetchall()

            if recent:
                output.append(f"{'ID':<12} {'Plate':<10} {'Type':<25} {'Date':<12} {'Fine':<10} {'Status':<10}")
                output.append("-" * 80)
                for violation in recent:
                    output.append(f"{violation[0]:<12} {violation[1]:<10} {violation[2]:<25} {violation[3]:<12} ${violation[4]:<9.2f} {violation[5]:<10}")
                output.append(f"\nTotal Recent Violations: {len(recent)}")
            else:
                output.append("No recent violations found.")

            output.append("\n")

            # Top Violators
            output.append("TOP VIOLATORS")
            output.append("-" * 80)
            cursor.execute('''
                SELECT license_plate, COUNT(*) as violations,
                       SUM(fine_amount) as total_fines,
                       SUM(CASE WHEN payment_status = 'Unpaid' THEN fine_amount ELSE 0 END) as outstanding
                FROM parking_violations
                GROUP BY license_plate
                HAVING violations > 1
                ORDER BY violations DESC
                LIMIT 10
            ''')
            top_violators = cursor.fetchall()

            if top_violators:
                output.append(f"{'License Plate':<15} {'Violations':<12} {'Total Fines':<15} {'Outstanding':<15}")
                output.append("-" * 57)
                for violator in top_violators:
                    output.append(f"{violator[0]:<15} {violator[1]:<12} ${violator[2]:<14.2f} ${violator[3]:<14.2f}")
            else:
                output.append("No repeat violators found.")

            conn.close()

            # Show in dialog
            self.show_text_dialog("Parking Violation Report", "\n".join(output))
        except Exception as e:
            logging.error(f"Error generating violation report: {e}")
            messagebox.showerror("Error", f"Failed to generate violation report: {e}")
    
    def show_analytics(self):
        """Show analytics dashboard"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Generate comprehensive analytics dashboard
            output = []
            output.append("PARKING ANALYTICS DASHBOARD")
            output.append("=" * 80)
            output.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            output.append("")

            # Overall Statistics
            output.append("OVERALL STATISTICS")
            output.append("-" * 80)

            cursor.execute("SELECT COUNT(*) FROM parking_permits WHERE active_status = 'Active'")
            active_permits = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM parking_permits")
            total_permits = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM vehicles")
            total_vehicles = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM parking_violations WHERE payment_status = 'Unpaid'")
            unpaid_violations = cursor.fetchone()[0]

            cursor.execute("SELECT SUM(fine_amount) FROM parking_violations WHERE payment_status = 'Unpaid'")
            unpaid_fines = cursor.fetchone()[0] or 0

            cursor.execute("SELECT SUM(total_spaces) FROM parking_lots")
            total_spaces = cursor.fetchone()[0] or 0

            cursor.execute("SELECT SUM(available_spaces) FROM parking_lots")
            available_spaces = cursor.fetchone()[0] or 0

            output.append(f"Active Permits: {active_permits}")
            output.append(f"Total Permits (All Time): {total_permits}")
            output.append(f"Registered Vehicles: {total_vehicles}")
            output.append(f"Unpaid Violations: {unpaid_violations}")
            output.append(f"Unpaid Fines: ${unpaid_fines:.2f}")
            output.append(f"Total Parking Spaces: {total_spaces}")
            output.append(f"Available Spaces: {available_spaces}")
            output.append(f"Occupied Spaces: {total_spaces - available_spaces}")
            if total_spaces > 0:
                output.append(f"Occupancy Rate: {((total_spaces - available_spaces) / total_spaces * 100):.1f}%")

            output.append("\n")

            # Monthly Trends
            output.append("MONTHLY TRENDS (Last 6 Months)")
            output.append("-" * 80)
            cursor.execute('''
                SELECT strftime('%Y-%m', violation_date) as month,
                       COUNT(*) as violations,
                       SUM(fine_amount) as fines
                FROM parking_violations
                WHERE date(violation_date) >= date('now', '-6 months')
                GROUP BY month
                ORDER BY month DESC
            ''')
            monthly = cursor.fetchall()

            if monthly:
                output.append(f"{'Month':<10} {'Violations':<15} {'Fines':<15}")
                output.append("-" * 40)
                for month in monthly:
                    output.append(f"{month[0]:<10} {month[1]:<15} ${month[2]:<14.2f}")
            else:
                output.append("No monthly data available.")

            output.append("\n")

            # Zone Utilization
            output.append("ZONE UTILIZATION")
            output.append("-" * 80)
            cursor.execute('''
                SELECT zone, COUNT(*) as active_permits
                FROM parking_permits
                WHERE active_status = 'Active'
                GROUP BY zone
                ORDER BY active_permits DESC
            ''')
            zone_util = cursor.fetchall()

            if zone_util:
                output.append(f"{'Zone':<10} {'Active Permits':<20}")
                output.append("-" * 30)
                for zone in zone_util:
                    output.append(f"{zone[0]:<10} {zone[1]:<20}")
            else:
                output.append("No zone utilization data available.")

            output.append("\n")

            # Revenue Analysis
            output.append("REVENUE ANALYSIS")
            output.append("-" * 80)
            cursor.execute('''
                SELECT SUM(fine_amount) as total_fines,
                       SUM(CASE WHEN payment_status = 'Paid' THEN fine_amount ELSE 0 END) as collected,
                       SUM(CASE WHEN payment_status = 'Unpaid' THEN fine_amount ELSE 0 END) as outstanding,
                       COUNT(*) as total_violations
                FROM parking_violations
            ''')
            revenue = cursor.fetchone()

            output.append(f"Total Fines Issued: ${revenue[0] or 0:.2f}")
            output.append(f"Fines Collected: ${revenue[1] or 0:.2f}")
            output.append(f"Outstanding Fines: ${revenue[2] or 0:.2f}")
            output.append(f"Collection Rate: {((revenue[1] or 0) / (revenue[0] or 1) * 100) if (revenue[0] or 0) > 0 else 0:.1f}%")

            conn.close()

            # Show in dialog
            self.show_text_dialog("Parking Analytics Dashboard", "\n".join(output))
        except Exception as e:
            logging.error(f"Error generating analytics dashboard: {e}")
            messagebox.showerror("Error", f"Failed to generate analytics: {e}")
    
    def show_text_dialog(self, title, content):
        """Show a dialog with text content"""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("800x600")

        # Main frame
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Text widget
        text_widget = ScrolledText(main_frame)
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert(tk.END, content)
        text_widget.config(state=tk.DISABLED)

        # Button frame
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        # Export as TXT button
        ttk.Button(button_frame, text="Export as TXT",
                  command=lambda: self.export_report_as_txt(title, content)).pack(side=tk.LEFT, padx=5)

        # Send to Admin button
        ttk.Button(button_frame, text="Send Report to Admin",
                  command=lambda: self.send_report_to_admin(title, content)).pack(side=tk.LEFT, padx=5)

        # Close button
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def export_report_as_txt(self, title, content):
        """Export report content as a text file"""
        try:
            # Ask user for save location
            filename = filedialog.asksaveasfilename(
                title="Save Report",
                defaultextension=".txt",
                initialfile=f"{title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )

            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"{title}\n")
                    f.write("=" * len(title) + "\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write(content)

                messagebox.showinfo("Success", f"Report exported successfully to:\n{filename}")
                logging.info(f"Report '{title}' exported to {filename}")
        except Exception as e:
            logging.error(f"Failed to export report: {e}")
            messagebox.showerror("Error", f"Failed to export report: {e}")

    def send_report_to_admin(self, title, content):
        """Send report to admin via email"""
        try:
            # Get admin email from database
            conn = get_connection()
            cursor = conn.cursor()

            # Query for admin users' emails
            cursor.execute('''
                SELECT email, first_name, last_name
                FROM users
                WHERE role = 'admin'
                AND email IS NOT NULL
                AND email != ''
                ORDER BY id
                LIMIT 1
            ''')

            admin = cursor.fetchone()
            conn.close()

            if not admin or not admin[0]:
                messagebox.showwarning("No Admin Email",
                    "No admin email address found in the system.\n"
                    "Please contact your system administrator.")
                return

            admin_email = admin[0]
            admin_name = f"{admin[1]} {admin[2]}" if admin[1] else "Administrator"

            # Prepare email content using template
            try:
                if TEMPLATE_AVAILABLE:
                    email_subject, email_body = render_template('parking_management_report', {
                        'admin_name': admin_name,
                        'report_title': title,
                        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'report_content': content,
                        'separator': '=' * 80
                    })
                else:
                    raise Exception("Template not available")
            except Exception as template_error:
                logging.warning(f"Failed to render template: {template_error}. Using fallback email.")
                # Fallback if template not available
                email_subject = f"Parking Management Report: {title}"
                email_body = f"""
Dear {admin_name},

Please find the attached parking management report below.

Report: {title}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Submitted by: {self.current_user.get('name', 'System')} ({self.current_user.get('id', 'N/A')})

{'=' * 80}

{content}

{'=' * 80}

This is an automated email from the University Parking Management System.

Best regards,
Parking Management System
"""

            # Send email using internal email service (stores in database for admin inbox)
            try:
                from university_system.infrastructure.email.email_service import send_email

                # Send email - will be stored in database and appear in admin's inbox
                send_email(
                    recipient_email=admin_email,
                    subject=email_subject,
                    body=email_body
                )

                messagebox.showinfo("Report Sent",
                    f"Report successfully sent to {admin_name}'s inbox.\n\n"
                    f"The admin can view this report in their email inbox within the system.")
                logging.info(f"Report '{title}' sent to admin inbox: {admin_email}")

            except Exception as email_error:
                # Email failed - show warning but don't error out
                messagebox.showwarning("Email Failed",
                    f"Could not send report to admin inbox.\n\n"
                    f"Error: {str(email_error)}\n\n"
                    f"Please use 'Export as TXT' to save the report\n"
                    f"and send it manually.")
                logging.error(f"Failed to send report to {admin_email}: {email_error}")

        except Exception as e:
            logging.error(f"Failed to send report to admin: {e}")
            messagebox.showerror("Error", f"Failed to send report to admin: {e}")

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            if isinstance(self.root, tk.Toplevel):
                # Just close the child window
                self.root.destroy()
            else:
                # Running standalone, need to create main GUI
                self.root.destroy()
                from university_system.modules.shared.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def show_export_dialog(self):
        """Show export dialog with multiple options"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Export Data")
        dialog.geometry("350x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        ttk.Label(main_frame, text="Export Options", font=("Arial", 12, "bold")).pack(pady=(0, 20))
        
        # Quick export buttons
        ttk.Label(main_frame, text="Quick Export:").pack(anchor="w", pady=(0, 5))
        
        quick_frame = ttk.Frame(main_frame)
        quick_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Button(quick_frame, text="Export Permits (CSV)", 
                  command=lambda: export_permits('csv')).pack(fill=tk.X, pady=2)
        ttk.Button(quick_frame, text="Export Vehicles (CSV)", 
                  command=lambda: export_vehicles('csv')).pack(fill=tk.X, pady=2)
        ttk.Button(quick_frame, text="Export Violations (CSV)", 
                  command=lambda: export_violations('csv')).pack(fill=tk.X, pady=2)
        ttk.Button(quick_frame, text="Export Parking Lots (CSV)", 
                  command=lambda: export_parking_lots('csv')).pack(fill=tk.X, pady=2)
        
        # Advanced options
        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        
        ttk.Button(main_frame, text="Advanced Export Options", 
                  command=self.show_advanced_export_dialog).pack(fill=tk.X, pady=5)
        
        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)
        
    def backup_database(self):
        """Backup the database"""
        try:
            import shutil
            
            # Get backup location
            backup_path = filedialog.asksaveasfilename(
                title="Save Database Backup",
                defaultextension=".db",
                filetypes=[("Database files", "*.db"), ("All files", "*.*")]
            )
            
            if backup_path:
                # Copy current database
                current_db = str(DEFAULT_DB_PATH)  # Adjust as needed
                shutil.copy2(current_db, backup_path)
                
                self.update_status("Database backed up successfully")
                messagebox.showinfo("Success", f"Database backed up to {backup_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to backup database: {e}")

    def update_available_spaces_dialog(self):
        """Show dialog to update available spaces for parking lots"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Get all lots
            cursor.execute('SELECT lot_id, lot_name, total_spaces, available_spaces FROM parking_lots ORDER BY lot_id')
            lots = cursor.fetchall()
            
            if not lots:
                messagebox.showinfo("Info", "No parking lots found.")
                conn.close()
                return
            
            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Update Available Spaces")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Create frame with scrollbar
            main_frame = ttk.Frame(dialog)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Create canvas and scrollbar for lots list
            canvas = tk.Canvas(main_frame)
            scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Add lot entries
            lot_vars = {}
            
            ttk.Label(scrollable_frame, text="Update Available Spaces", font=("Arial", 12, "bold")).pack(pady=(0, 10))
            
            for lot in lots:
                lot_frame = ttk.Frame(scrollable_frame)
                lot_frame.pack(fill=tk.X, pady=2)
                
                ttk.Label(lot_frame, text=f"{lot[0]} - {lot[1]}:").pack(side=tk.LEFT)
                ttk.Label(lot_frame, text=f"(Total: {lot[2]})").pack(side=tk.LEFT, padx=(5, 10))
                
                var = tk.StringVar(value=str(lot[3]))
                lot_vars[lot[0]] = var
                
                entry = ttk.Entry(lot_frame, textvariable=var, width=10)
                entry.pack(side=tk.RIGHT)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Buttons
            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
            
            def save_changes():
                try:
                    for lot_id, var in lot_vars.items():
                        available = int(var.get())
                        if available < 0:
                            messagebox.showerror("Error", f"Available spaces for {lot_id} cannot be negative.")
                            return
                        
                        # Get total spaces for validation
                        cursor.execute('SELECT total_spaces FROM parking_lots WHERE lot_id = ?', (lot_id,))
                        total = cursor.fetchone()[0]
                        
                        if available > total:
                            messagebox.showerror("Error", f"Available spaces for {lot_id} cannot exceed total spaces ({total}).")
                            return
                        
                        # Update available spaces
                        cursor.execute('UPDATE parking_lots SET available_spaces = ? WHERE lot_id = ?', (available, lot_id))
                    
                    conn.commit()
                    self.refresh_lots()
                    self.update_status("Available spaces updated successfully")
                    dialog.destroy()
                    
                except ValueError:
                    messagebox.showerror("Error", "Please enter valid numbers for available spaces.")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update available spaces: {e}")
            
            ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open update dialog: {e}")

    def show_advanced_export_dialog(self):
        """Show advanced export options dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Advanced Export Options")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        ttk.Label(main_frame, text="Advanced Export Options", font=("Arial", 12, "bold")).pack(pady=(0, 20))
        
        # Export type
        ttk.Label(main_frame, text="Export Type:").pack(anchor="w")
        export_type_var = tk.StringVar()
        export_types = [
            ("All Data (Complete Export)", "all"),
            ("Permits Only", "permits"),
            ("Vehicles Only", "vehicles"),
            ("Violations Only", "violations"),
            ("Parking Lots Only", "lots"),
            ("Users Only", "users")
        ]
        
        for text, value in export_types:
            ttk.Radiobutton(main_frame, text=text, variable=export_type_var, value=value).pack(anchor="w")
        
        export_type_var.set("all")
        
        ttk.Label(main_frame, text="").pack()  # Spacer
        
        # Format type
        ttk.Label(main_frame, text="Format:").pack(anchor="w")
        format_var = tk.StringVar()
        formats = [("CSV", "csv"), ("Excel", "excel"), ("PDF", "pdf"), ("Text", "txt")]
        
        for text, value in formats:
            ttk.Radiobutton(main_frame, text=text, variable=format_var, value=value).pack(anchor="w")
        
        format_var.set("csv")
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=20)
        
        def export_data():
            export_type = export_type_var.get()
            format_type = format_var.get()
            
            try:
                if export_type == "all":
                    # Export all data types
                    export_permits(format_type)
                    export_vehicles(format_type)
                    export_violations(format_type)
                    export_parking_lots(format_type)
                    messagebox.showinfo("Success", "All data exported successfully!")
                elif export_type == "permits":
                    export_permits(format_type)
                elif export_type == "vehicles":
                    export_vehicles(format_type)
                elif export_type == "violations":
                    export_violations(format_type)
                elif export_type == "lots":
                    export_parking_lots(format_type)
                elif export_type == "users":
                    export_users(format_type)
                
                dialog.destroy()
                self.update_status(f"{export_type.title()} exported successfully")
                
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {e}")
        
        ttk.Button(button_frame, text="Export", command=export_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def generate_occupancy_report(self):
        """Generate parking lot occupancy report"""
        try:
            import io
            import sys
            
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()
            
            # Generate occupancy report content
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT lot_id, lot_name, total_spaces, available_spaces, zone
            FROM parking_lots
            ORDER BY lot_id
            ''')
            
            lots = cursor.fetchall()
            
            print("PARKING LOT OCCUPANCY REPORT")
            print("=" * 60)
            print(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print()
            
            total_spaces = 0
            total_available = 0
            
            print(f"{'Lot ID':<8} {'Lot Name':<25} {'Total':<8} {'Available':<10} {'Occupied':<10} {'Rate':<8} {'Zone':<6}")
            print("-" * 75)
            
            for lot in lots:
                occupied = lot[2] - lot[3]
                rate = (occupied / lot[2] * 100) if lot[2] > 0 else 0
                
                print(f"{lot[0]:<8} {lot[1]:<25} {lot[2]:<8} {lot[3]:<10} {occupied:<10} {rate:<7.1f}% {lot[4]:<6}")
                
                total_spaces += lot[2]
                total_available += lot[3]
            
            print("-" * 75)
            total_occupied = total_spaces - total_available
            overall_rate = (total_occupied / total_spaces * 100) if total_spaces > 0 else 0
            print(f"{'TOTAL':<34} {total_spaces:<8} {total_available:<10} {total_occupied:<10} {overall_rate:<7.1f}%")
            
            output = buffer.getvalue()
            sys.stdout = old_stdout
            conn.close()
            
            self.show_text_dialog("Parking Lot Occupancy Report", output)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate occupancy report: {e}")

    def generate_compliance_report(self):
        """Generate compliance and audit report"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Generate comprehensive compliance report
            output = []
            output.append("PARKING COMPLIANCE & AUDIT REPORT")
            output.append("=" * 80)
            output.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            output.append("")

            # Permit Compliance
            output.append("PERMIT COMPLIANCE")
            output.append("-" * 80)

            cursor.execute("SELECT COUNT(*) FROM parking_permits WHERE active_status = 'Active'")
            active_permits = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM parking_permits WHERE active_status = 'Expired'")
            expired_permits = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM parking_permits
                WHERE active_status = 'Active'
                AND date(end_date) < date('now')
            ''')
            expired_not_updated = cursor.fetchone()[0]

            output.append(f"Active Permits: {active_permits}")
            output.append(f"Expired Permits: {expired_permits}")
            output.append(f"Permits Expired but Not Updated: {expired_not_updated}")
            if expired_not_updated > 0:
                output.append(f"⚠ WARNING: {expired_not_updated} permits need status update!")

            output.append("\n")

            # Violation Compliance
            output.append("VIOLATION COMPLIANCE")
            output.append("-" * 80)

            cursor.execute('''
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN payment_status = 'Paid' THEN 1 ELSE 0 END) as paid,
                       SUM(CASE WHEN payment_status = 'Unpaid' THEN 1 ELSE 0 END) as unpaid,
                       SUM(CASE WHEN date(violation_date) < date('now', '-90 days')
                           AND payment_status = 'Unpaid' THEN 1 ELSE 0 END) as overdue
                FROM parking_violations
            ''')
            viol_compliance = cursor.fetchone()

            output.append(f"Total Violations: {viol_compliance[0]}")
            output.append(f"Paid Violations: {viol_compliance[1]}")
            output.append(f"Unpaid Violations: {viol_compliance[2]}")
            output.append(f"Overdue (>90 days): {viol_compliance[3]}")
            if viol_compliance[3] > 0:
                output.append(f"⚠ WARNING: {viol_compliance[3]} violations overdue for collection!")

            output.append("\n")

            # Parking Lot Compliance
            output.append("PARKING LOT COMPLIANCE")
            output.append("-" * 80)

            cursor.execute('''
                SELECT COUNT(*) FROM parking_lots
                WHERE available_spaces < 0
            ''')
            negative_spaces = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM parking_lots
                WHERE available_spaces > total_spaces
            ''')
            invalid_spaces = cursor.fetchone()[0]

            cursor.execute('''
                SELECT lot_id, lot_name, total_spaces, available_spaces
                FROM parking_lots
                WHERE total_spaces - available_spaces > total_spaces
            ''')
            overcapacity = cursor.fetchall()

            output.append(f"Lots with Negative Available Spaces: {negative_spaces}")
            output.append(f"Lots with Invalid Space Count: {invalid_spaces}")
            output.append(f"Lots Over Capacity: {len(overcapacity)}")

            if negative_spaces > 0 or invalid_spaces > 0:
                output.append("⚠ WARNING: Data integrity issues detected!")

            output.append("\n")

            # Audit Trail
            output.append("RECENT AUDIT TRAIL (Last 30 Days)")
            output.append("-" * 80)

            try:
                cursor.execute('''
                    SELECT timestamp, activity_type, activity_description, user_id
                    FROM user_activity_log
                    WHERE date(timestamp) >= date('now', '-30 days')
                    AND (activity_type LIKE '%parking%' OR activity_description LIKE '%parking%'
                         OR activity_description LIKE '%permit%' OR activity_description LIKE '%violation%')
                    ORDER BY timestamp DESC
                    LIMIT 20
                ''')
                audit_trail = cursor.fetchall()

                if audit_trail:
                    output.append(f"{'Date':<20} {'Activity':<20} {'Description':<30} {'User ID':<10}")
                    output.append("-" * 80)
                    for entry in audit_trail:
                        desc = entry[2][:27] + "..." if len(entry[2]) > 30 else entry[2]
                        output.append(f"{entry[0]:<20} {entry[1]:<20} {desc:<30} {entry[3]:<10}")
                else:
                    output.append("No recent parking-related audit trail available.")
            except Exception as e:
                output.append(f"Audit trail not available (table may not exist)")

            conn.close()

            # Show in dialog
            self.show_text_dialog("Compliance & Audit Report", "\n".join(output))
        except Exception as e:
            logging.error(f"Error generating compliance report: {e}")
            messagebox.showerror("Error", f"Failed to generate compliance report: {e}")

    def generate_revenue_report(self):
        """Generate revenue report"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Generate comprehensive revenue report
            output = []
            output.append("PARKING REVENUE REPORT")
            output.append("=" * 80)
            output.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            output.append("")

            # Overall Revenue Summary
            output.append("OVERALL REVENUE SUMMARY")
            output.append("-" * 80)

            cursor.execute('''
                SELECT SUM(fine_amount) as total_fines,
                       SUM(CASE WHEN payment_status = 'Paid' THEN fine_amount ELSE 0 END) as collected,
                       SUM(CASE WHEN payment_status = 'Unpaid' THEN fine_amount ELSE 0 END) as outstanding,
                       SUM(CASE WHEN payment_status = 'Pending' THEN fine_amount ELSE 0 END) as pending,
                       COUNT(*) as total_violations
                FROM parking_violations
            ''')
            overall = cursor.fetchone()

            output.append(f"Total Fines Issued: ${overall[0] or 0:.2f}")
            output.append(f"  - Collected: ${overall[1] or 0:.2f}")
            output.append(f"  - Outstanding: ${overall[2] or 0:.2f}")
            output.append(f"  - Pending: ${overall[3] or 0:.2f}")
            output.append(f"Total Violations: {overall[4]}")
            if overall[0] and overall[0] > 0:
                output.append(f"Collection Rate: {(overall[1] / overall[0] * 100):.1f}%")

            output.append("\n")

            # Monthly Revenue Breakdown
            output.append("MONTHLY REVENUE BREAKDOWN (Last 12 Months)")
            output.append("-" * 80)

            cursor.execute('''
                SELECT strftime('%Y-%m', violation_date) as month,
                       COUNT(*) as violations,
                       SUM(fine_amount) as total_fines,
                       SUM(CASE WHEN payment_status = 'Paid' THEN fine_amount ELSE 0 END) as collected,
                       SUM(CASE WHEN payment_status = 'Unpaid' THEN fine_amount ELSE 0 END) as outstanding
                FROM parking_violations
                WHERE date(violation_date) >= date('now', '-12 months')
                GROUP BY month
                ORDER BY month DESC
            ''')
            monthly = cursor.fetchall()

            if monthly:
                output.append(f"{'Month':<10} {'Violations':<12} {'Fines':<15} {'Collected':<15} {'Outstanding':<15}")
                output.append("-" * 67)
                for month in monthly:
                    output.append(f"{month[0]:<10} {month[1]:<12} ${month[2]:<14.2f} ${month[3]:<14.2f} ${month[4]:<14.2f}")
            else:
                output.append("No monthly revenue data available.")

            output.append("\n")

            # Revenue by Violation Type
            output.append("REVENUE BY VIOLATION TYPE")
            output.append("-" * 80)

            cursor.execute('''
                SELECT violation_type,
                       COUNT(*) as violations,
                       SUM(fine_amount) as total_fines,
                       SUM(CASE WHEN payment_status = 'Paid' THEN fine_amount ELSE 0 END) as collected,
                       AVG(fine_amount) as avg_fine
                FROM parking_violations
                GROUP BY violation_type
                ORDER BY total_fines DESC
            ''')
            by_type = cursor.fetchall()

            if by_type:
                output.append(f"{'Type':<30} {'Count':<8} {'Total':<15} {'Collected':<15} {'Avg Fine':<12}")
                output.append("-" * 80)
                for vtype in by_type:
                    output.append(f"{vtype[0]:<30} {vtype[1]:<8} ${vtype[2]:<14.2f} ${vtype[3]:<14.2f} ${vtype[4]:<11.2f}")
            else:
                output.append("No violation type data available.")

            output.append("\n")

            # Permit Revenue Estimate
            output.append("PERMIT REVENUE ESTIMATE")
            output.append("-" * 80)

            cursor.execute('''
                SELECT zone, permit_type, COUNT(*) as count
                FROM parking_permits
                WHERE active_status = 'Active'
                GROUP BY zone, permit_type
                ORDER BY zone, permit_type
            ''')
            permits = cursor.fetchall()

            if permits:
                total_permit_revenue = 0
                output.append(f"{'Zone':<8} {'Type':<15} {'Count':<10} {'Est. Revenue':<15}")
                output.append("-" * 48)
                for permit in permits:
                    # Estimate revenue based on zone and type
                    zone = permit[0]
                    ptype = permit[1]
                    count = permit[2]

                    # Estimate based on zone rates
                    if zone in PARKING_ZONES:
                        est_revenue = count * PARKING_ZONES[zone].get('annual_fee', 0)
                    else:
                        est_revenue = count * 200  # Default estimate

                    total_permit_revenue += est_revenue
                    output.append(f"{zone:<8} {ptype:<15} {count:<10} ${est_revenue:<14.2f}")

                output.append("-" * 48)
                output.append(f"{'TOTAL PERMIT REVENUE':<33} ${total_permit_revenue:<14.2f}")
            else:
                output.append("No permit revenue data available.")

            conn.close()

            # Show in dialog
            self.show_text_dialog("Parking Revenue Report", "\n".join(output))
        except Exception as e:
            logging.error(f"Error generating revenue report: {e}")
            messagebox.showerror("Error", f"Failed to generate revenue report: {e}")

    def generate_user_activity_report(self):
        """Generate user activity report"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Generate comprehensive user activity report
            output = []
            output.append("USER ACTIVITY REPORT")
            output.append("=" * 80)
            output.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            output.append("")

            # Active Permit Holders
            output.append("ACTIVE PERMIT HOLDERS")
            output.append("-" * 80)

            cursor.execute('''
                SELECT COUNT(DISTINCT full_name) as unique_users,
                       COUNT(*) as total_permits
                FROM parking_permits
                WHERE active_status = 'Active'
            ''')
            permit_users = cursor.fetchone()

            output.append(f"Unique Active Permit Holders: {permit_users[0]}")
            output.append(f"Total Active Permits: {permit_users[1]}")

            output.append("\n")

            # Recent Permit Activity
            output.append("RECENT PERMIT ACTIVITY (Last 30 Days)")
            output.append("-" * 80)

            cursor.execute('''
                SELECT permit_id, full_name, zone, permit_type, issue_date
                FROM parking_permits
                WHERE date(issue_date) >= date('now', '-30 days')
                ORDER BY issue_date DESC
                LIMIT 20
            ''')
            recent_permits = cursor.fetchall()

            if recent_permits:
                output.append(f"{'Permit ID':<12} {'Name':<30} {'Zone':<6} {'Type':<12} {'Issued':<12}")
                output.append("-" * 72)
                for permit in recent_permits:
                    output.append(f"{permit[0]:<12} {permit[1]:<30} {permit[2]:<6} {permit[3]:<12} {permit[4]:<12}")
                output.append(f"\nTotal New Permits (30 days): {len(recent_permits)}")
            else:
                output.append("No recent permit activity.")

            output.append("\n")

            # Violation Activity by User
            output.append("TOP VIOLATORS (All Time)")
            output.append("-" * 80)

            cursor.execute('''
                SELECT license_plate,
                       COUNT(*) as violations,
                       SUM(fine_amount) as total_fines,
                       SUM(CASE WHEN payment_status = 'Unpaid' THEN fine_amount ELSE 0 END) as unpaid,
                       MAX(violation_date) as last_violation
                FROM parking_violations
                GROUP BY license_plate
                HAVING violations > 0
                ORDER BY violations DESC
                LIMIT 15
            ''')
            violators = cursor.fetchall()

            if violators:
                output.append(f"{'License Plate':<15} {'Violations':<12} {'Total Fines':<15} {'Unpaid':<15} {'Last Violation':<15}")
                output.append("-" * 72)
                for violator in violators:
                    output.append(f"{violator[0]:<15} {violator[1]:<12} ${violator[2]:<14.2f} ${violator[3]:<14.2f} {violator[4]:<15}")
            else:
                output.append("No violation activity found.")

            output.append("\n")

            # Recent User Actions
            output.append("RECENT USER ACTIONS (Last 7 Days)")
            output.append("-" * 80)

            try:
                cursor.execute('''
                    SELECT timestamp, activity_type, activity_description, user_id
                    FROM user_activity_log
                    WHERE date(timestamp) >= date('now', '-7 days')
                    AND (activity_type LIKE '%parking%' OR activity_description LIKE '%parking%'
                         OR activity_description LIKE '%permit%' OR activity_description LIKE '%violation%')
                    ORDER BY timestamp DESC
                    LIMIT 30
                ''')
                recent_actions = cursor.fetchall()

                if recent_actions:
                    output.append(f"{'Date':<20} {'Activity Type':<25} {'Description':<30} {'User ID':<10}")
                    output.append("-" * 85)
                    for action in recent_actions:
                        desc = action[2][:27] + "..." if len(action[2]) > 30 else action[2]
                        output.append(f"{action[0]:<20} {action[1]:<25} {desc:<30} {action[3]:<10}")
                else:
                    output.append("No recent parking-related user actions found.")
            except Exception as e:
                output.append(f"User activity log not available (table may not exist)")

            output.append("\n")

            # User Statistics Summary
            output.append("USER STATISTICS SUMMARY")
            output.append("-" * 80)

            cursor.execute("SELECT COUNT(DISTINCT license_plate) FROM vehicles")
            unique_vehicles = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT license_plate) FROM parking_violations")
            vehicles_with_violations = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM parking_permits
                WHERE active_status = 'Active'
                AND date(end_date) BETWEEN date('now') AND date('now', '+30 days')
            ''')
            expiring_soon = cursor.fetchone()[0]

            output.append(f"Total Registered Vehicles: {unique_vehicles}")
            output.append(f"Vehicles with Violations: {vehicles_with_violations}")
            output.append(f"Permits Expiring Soon (30 days): {expiring_soon}")

            conn.close()

            # Show in dialog
            self.show_text_dialog("User Activity Report", "\n".join(output))
        except Exception as e:
            logging.error(f"Error generating user activity report: {e}")
            messagebox.showerror("Error", f"Failed to generate user activity report: {e}")
    
    def _send_violation_email(self, violation_id, student_id, student_email, license_plate, violation_type, location, fine_amount):
        """Send violation notification email to student"""
        try:
            # Get owner name - check both students and users tables
            student_name = "Student"
            try:
                conn = get_connection()
                cursor = conn.cursor()

                # First try students table
                cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
                student_data = cursor.fetchone()

                if student_data:
                    student_name = f"{student_data[0]} {student_data[1]}"
                else:
                    # Fall back to users table (for admin/staff)
                    cursor.execute('SELECT first_name, last_name, username FROM users WHERE username = ? OR id = ?',
                                 (student_id, student_id))
                    user_data = cursor.fetchone()
                    if user_data:
                        student_name = f"{user_data[0] or ''} {user_data[1] or ''}".strip() or user_data[2] or "User"

                conn.close()
            except Exception as e:
                logging.error(f"Could not fetch owner name: {e}")

            # Load email template
            import json
            # Navigate from parking_management_gui.py up to university_system root, then to templates
            template_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
                'templates', 'email', 'parking_violation_notice.json'
            )

            with open(template_path, 'r') as f:
                template = json.load(f)

            # Prepare template variables
            violation_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            signature = "Parking Services\nUniversity Parking Management\nPhone: (555) 123-4567\nEmail: parking@university.edu"

            # Replace variables in subject and body
            subject = template['subject'].replace('$violation_id', violation_id)

            body = template['body']
            body = body.replace('$student_name', student_name)
            body = body.replace('$violation_id', violation_id)
            body = body.replace('$violation_type', violation_type)
            body = body.replace('$license_plate', license_plate)
            body = body.replace('$location', location)
            body = body.replace('$violation_date', violation_date)
            body = body.replace('$fine_amount', f"{fine_amount:.2f}")
            body = body.replace('$payment_status', 'Unpaid')
            body = body.replace('$signature', signature)

            # Send email using email service
            try:
                from university_system.infrastructure.email.email_service import send_email
                send_email(
                    recipient_email=student_email,
                    subject=subject,
                    body=body
                )
                logging.info(f"Violation notification email sent to {student_email} for violation {violation_id}")
            except ImportError:
                # Fallback: Log the email content
                logging.warning(f"Email service not available. Email would have been sent to {student_email}:")
                logging.info(f"Subject: {subject}")
                logging.info(f"Body: {body}")
                messagebox.showinfo("Email Notification",
                    f"Email service unavailable.\n\n"
                    f"Violation notice for {student_name} logged.\n"
                    f"Manual notification required to: {student_email}")

        except Exception as e:
            logging.error(f"Failed to send violation email: {e}")
            messagebox.showwarning("Email Error",
                f"Violation recorded successfully, but email notification failed.\n"
                f"Please notify the student manually.")

    def show_about(self):
        """Show about dialog"""
        about_text = """
Parking Management System GUI

Version: 1.0
Author: System Administrator

This is a comprehensive parking management system
with both GUI and console interfaces.

Features:
- Permit Management
- Vehicle Registration
- Violation Tracking
- Parking Lot Management
- Reports and Analytics
- Data Export
- Email Notifications
        """
        messagebox.showinfo("About", about_text)


# Dialog classes
class PermitDialog:
    def __init__(self, parent, title, permit_data=None):
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x550")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.permit_data = permit_data
        self.setup_ui()
    
    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Student Lookup Section
        lookup_frame = ttk.LabelFrame(main_frame, text="Student Lookup", padding="5")
        lookup_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        ttk.Label(lookup_frame, text="Student ID:").grid(row=0, column=0, sticky="w", padx=5)
        self.student_id_var = tk.StringVar()
        self.student_id_entry = ttk.Entry(lookup_frame, textvariable=self.student_id_var, width=20)
        self.student_id_entry.grid(row=0, column=1, padx=5)

        ttk.Button(lookup_frame, text="Lookup Student",
                  command=self.lookup_student).grid(row=0, column=2, padx=5)

        # User info
        ttk.Label(main_frame, text="Full Name:").grid(row=1, column=0, sticky="w", pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var).grid(row=1, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Email:").grid(row=2, column=0, sticky="w", pady=5)
        self.email_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.email_var).grid(row=2, column=1, sticky="ew", pady=5)

        # Permit info
        ttk.Label(main_frame, text="Zone:").grid(row=3, column=0, sticky="w", pady=5)
        self.zone_var = tk.StringVar()
        zone_combo = ttk.Combobox(main_frame, textvariable=self.zone_var,
                                 values=list(PARKING_ZONES.keys()), state="readonly")
        zone_combo.grid(row=3, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Permit Type:").grid(row=4, column=0, sticky="w", pady=5)
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var,
                                 values=PERMIT_TYPES, state="readonly")
        type_combo.grid(row=4, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Start Date:").grid(row=5, column=0, sticky="w", pady=5)
        self.start_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(main_frame, textvariable=self.start_var).grid(row=5, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="End Date:").grid(row=6, column=0, sticky="w", pady=5)
        self.end_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.end_var).grid(row=6, column=1, sticky="ew", pady=5)

        # Vehicle selection
        ttk.Label(main_frame, text="Vehicle (optional):").grid(row=7, column=0, sticky="w", pady=5)
        self.vehicle_var = tk.StringVar()
        self.vehicle_combo = ttk.Combobox(main_frame, textvariable=self.vehicle_var, state="readonly")
        self.vehicle_combo.grid(row=7, column=1, sticky="ew", pady=5)

        # Load vehicles
        self.load_vehicles()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=8, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
        
        # Auto-calculate end date when type changes
        type_combo.bind('<<ComboboxSelected>>', self.calculate_end_date)
        
        # Load existing data if editing
        if self.permit_data:
            self.load_permit_data()
    
    def load_vehicles(self):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT vehicle_id, license_plate, make, model FROM vehicles')
            vehicles = cursor.fetchall()
            conn.close()

            vehicle_options = ["None"] + [f"{v[0]} - {v[1]} ({v[2]} {v[3]})" for v in vehicles]
            self.vehicle_combo['values'] = vehicle_options
            self.vehicle_combo.current(0)
        except Exception as e:
            print(f"Error loading vehicles: {e}")

    def lookup_student(self):
        """Lookup student in database and autofill form"""
        student_id = self.student_id_var.get().strip()

        if not student_id:
            messagebox.showwarning("Warning", "Please enter a Student ID")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Search for student by student_id
            cursor.execute('''
                SELECT student_id, first_name, last_name, email_address
                FROM students
                WHERE student_id = ?
            ''', (student_id,))

            student = cursor.fetchone()

            if student:
                # Autofill the form with student information
                full_name = f"{student[1]} {student[2]}"  # first_name + last_name
                email = student[3] if student[3] else ""

                self.name_var.set(full_name)
                self.email_var.set(email)

                # Also load student's vehicles if any
                cursor.execute('''
                    SELECT vehicle_id, license_plate, make, model
                    FROM vehicles
                    WHERE owner_id = ?
                ''', (student_id,))

                vehicles = cursor.fetchall()

                if vehicles:
                    # Update vehicle combo with student's vehicles at the top
                    cursor.execute('SELECT vehicle_id, license_plate, make, model FROM vehicles')
                    all_vehicles = cursor.fetchall()

                    # Put student vehicles first
                    vehicle_options = ["None"]
                    for v in vehicles:
                        vehicle_options.append(f"{v[0]} - {v[1]} ({v[2]} {v[3]}) [Student's Vehicle]")

                    # Add other vehicles
                    for v in all_vehicles:
                        if v[0] not in [sv[0] for sv in vehicles]:
                            vehicle_options.append(f"{v[0]} - {v[1]} ({v[2]} {v[3]})")

                    self.vehicle_combo['values'] = vehicle_options

                    # Auto-select first student vehicle if available
                    if len(vehicles) > 0:
                        self.vehicle_combo.current(1)  # Select first student vehicle

                messagebox.showinfo("Success", f"Student found: {full_name}\nForm auto-filled with student information.")
            else:
                messagebox.showerror("Not Found", f"No student found with ID: {student_id}")

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to lookup student: {e}")
            logging.error(f"Student lookup error: {e}")

    def calculate_end_date(self, event=None):
        permit_type = self.type_var.get()
        start_date = datetime.strptime(self.start_var.get(), '%Y-%m-%d')
        
        if permit_type == 'Annual':
            end_date = start_date.replace(year=start_date.year + 1)
        elif permit_type == 'Semester':
            end_date = start_date + timedelta(days=120)
        elif permit_type == 'Monthly':
            end_date = start_date + timedelta(days=30)
        elif permit_type == 'Daily':
            end_date = start_date + timedelta(days=1)
        else:  # Temporary
            end_date = start_date + timedelta(days=7)
        
        self.end_var.set(end_date.strftime('%Y-%m-%d'))
    
    def load_permit_data(self):
        # Load existing permit data for editing
        if self.permit_data:
            self.name_var.set(self.permit_data[2])  # full_name
            self.email_var.set(self.permit_data[3])  # email
            self.zone_var.set(self.permit_data[4])  # zone
            self.type_var.set(self.permit_data[5])  # permit_type
            self.start_var.set(self.permit_data[6])  # start_date
            self.end_var.set(self.permit_data[7])  # end_date
    
    def save(self):
        # Validate required fields
        if not all([self.name_var.get(), self.email_var.get(), 
                   self.zone_var.get(), self.type_var.get()]):
            messagebox.showerror("Error", "Please fill in all required fields")
            return
        
        # Get vehicle ID if selected
        vehicle_id = None
        if self.vehicle_var.get() and self.vehicle_var.get() != "None":
            vehicle_id = self.vehicle_var.get().split(" - ")[0]
        
        self.result = {
            'full_name': self.name_var.get(),
            'email': self.email_var.get(),
            'zone': self.zone_var.get(),
            'permit_type': self.type_var.get(),
            'start_date': self.start_var.get(),
            'end_date': self.end_var.get(),
            'vehicle_id': vehicle_id,
            'student_id': self.student_id_var.get().strip() if self.student_id_var.get().strip() else None
        }
        
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()


class VehicleDialog:
    def __init__(self, parent, title, vehicle_data=None):
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x550")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.vehicle_data = vehicle_data
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Student/Owner Lookup Section
        lookup_frame = ttk.LabelFrame(main_frame, text="Owner Lookup", padding="5")
        lookup_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        ttk.Label(lookup_frame, text="Student ID:").grid(row=0, column=0, sticky="w", padx=5)
        self.owner_id_var = tk.StringVar()
        self.owner_id_entry = ttk.Entry(lookup_frame, textvariable=self.owner_id_var, width=20)
        self.owner_id_entry.grid(row=0, column=1, padx=5)

        ttk.Button(lookup_frame, text="Lookup Owner",
                  command=self.lookup_owner).grid(row=0, column=2, padx=5)

        # Owner name display (read-only)
        ttk.Label(main_frame, text="Owner Name:").grid(row=1, column=0, sticky="w", pady=5)
        self.owner_name_var = tk.StringVar(value="Not linked")
        ttk.Entry(main_frame, textvariable=self.owner_name_var, state="readonly").grid(row=1, column=1, sticky="ew", pady=5)

        # Vehicle info
        ttk.Label(main_frame, text="License Plate:").grid(row=2, column=0, sticky="w", pady=5)
        self.plate_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.plate_var).grid(row=2, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Make:").grid(row=3, column=0, sticky="w", pady=5)
        self.make_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.make_var).grid(row=3, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Model:").grid(row=4, column=0, sticky="w", pady=5)
        self.model_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.model_var).grid(row=4, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Year:").grid(row=5, column=0, sticky="w", pady=5)
        self.year_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.year_var).grid(row=5, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Color:").grid(row=6, column=0, sticky="w", pady=5)
        self.color_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.color_var).grid(row=6, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Vehicle Type:").grid(row=7, column=0, sticky="w", pady=5)
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var,
                                 values=VEHICLE_TYPES, state="readonly")
        type_combo.grid(row=7, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Registration State:").grid(row=8, column=0, sticky="w", pady=5)
        self.state_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.state_var).grid(row=8, column=1, sticky="ew", pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=9, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
        
        # Load existing data if editing
        if self.vehicle_data:
            self.load_vehicle_data()
    
    def load_vehicle_data(self):
        if self.vehicle_data:
            self.plate_var.set(self.vehicle_data[1])  # license_plate
            self.make_var.set(self.vehicle_data[2])   # make
            self.model_var.set(self.vehicle_data[3])  # model
            self.year_var.set(str(self.vehicle_data[4]))  # year
            self.color_var.set(self.vehicle_data[5])  # color
            self.type_var.set(self.vehicle_data[6])   # vehicle_type
            self.state_var.set(self.vehicle_data[8])  # registration_state

            # Load owner info if available
            if self.vehicle_data[7]:  # owner_id
                self.owner_id_var.set(self.vehicle_data[7])
                self.lookup_owner()  # Auto-lookup to display owner name

    def lookup_owner(self):
        """Lookup vehicle owner (student/user) in database"""
        owner_id = self.owner_id_var.get().strip()

        if not owner_id:
            self.owner_name_var.set("Not linked")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Try to find in users table first (for foreign key compatibility)
            cursor.execute('''
                SELECT id, first_name, last_name, username
                FROM users
                WHERE username = ? OR id = ?
            ''', (owner_id, owner_id))

            user = cursor.fetchone()

            if user:
                # user = (id, first_name, last_name, username)
                owner_name = f"{user[1] or ''} {user[2] or ''}".strip() or user[3] or "Unknown"
                self.owner_name_var.set(owner_name)
                # Update the owner_id_var to the actual user.id for foreign key
                self.owner_id_var.set(str(user[0]))
                messagebox.showinfo("Success", f"Owner found: {owner_name}")
            else:
                # Fallback to students table
                cursor.execute('''
                    SELECT first_name, last_name
                    FROM students
                    WHERE student_id = ?
                ''', (owner_id,))

                student = cursor.fetchone()

                if student:
                    owner_name = f"{student[0]} {student[1]}"
                    self.owner_name_var.set(owner_name)
                    messagebox.showwarning("Note",
                        f"Student found: {owner_name}\n\n"
                        f"However, this student doesn't have a user account.\n"
                        f"Vehicle will be registered without owner link.\n"
                        f"Owner ID field will be cleared.")
                    # Clear owner_id since no matching user exists
                    self.owner_id_var.set("")
                else:
                    self.owner_name_var.set("Not found")
                    messagebox.showwarning("Not Found",
                        f"No user or student found with ID: {owner_id}\n\n"
                        f"Owner ID field will be cleared.")
                    self.owner_id_var.set("")

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to lookup owner: {e}")
            logging.error(f"Owner lookup error: {e}")

    def save(self):
        # Validate required fields
        if not all([self.plate_var.get(), self.make_var.get(), 
                   self.model_var.get(), self.year_var.get()]):
            messagebox.showerror("Error", "Please fill in all required fields")
            return
        
        try:
            year = int(self.year_var.get())
            if year < 1900 or year > datetime.now().year + 1:
                raise ValueError("Invalid year")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid year")
            return
        
        self.result = {
            'license_plate': self.plate_var.get().upper(),
            'make': self.make_var.get(),
            'model': self.model_var.get(),
            'year': year,
            'color': self.color_var.get(),
            'vehicle_type': self.type_var.get() or 'Sedan',
            'registration_state': self.state_var.get().upper(),
            'owner_id': self.owner_id_var.get().strip() if self.owner_id_var.get().strip() else None
        }
        
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()


class ViolationDialog:
    def __init__(self, parent, title, violation_data=None):
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("550x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.violation_data = violation_data
        self.vehicle_id = None
        self.student_id = None
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Vehicle Lookup Section
        lookup_frame = ttk.LabelFrame(main_frame, text="Vehicle Lookup", padding="5")
        lookup_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        ttk.Label(lookup_frame, text="License Plate:").grid(row=0, column=0, sticky="w", padx=5)
        self.plate_var = tk.StringVar()
        self.plate_entry = ttk.Entry(lookup_frame, textvariable=self.plate_var, width=20)
        self.plate_entry.grid(row=0, column=1, padx=5)

        ttk.Button(lookup_frame, text="Lookup Vehicle",
                  command=self.lookup_vehicle).grid(row=0, column=2, padx=5)

        # Vehicle & Owner Info Display (read-only)
        info_frame = ttk.LabelFrame(main_frame, text="Vehicle & Owner Information", padding="5")
        info_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Label(info_frame, text="Vehicle:").grid(row=0, column=0, sticky="w", pady=2)
        self.vehicle_info_var = tk.StringVar(value="Not found")
        ttk.Entry(info_frame, textvariable=self.vehicle_info_var, state="readonly", width=40).grid(row=0, column=1, sticky="ew", pady=2, padx=(5, 0))

        ttk.Label(info_frame, text="Owner:").grid(row=1, column=0, sticky="w", pady=2)
        self.owner_info_var = tk.StringVar(value="Not found")
        ttk.Entry(info_frame, textvariable=self.owner_info_var, state="readonly", width=40).grid(row=1, column=1, sticky="ew", pady=2, padx=(5, 0))

        ttk.Label(info_frame, text="Email:").grid(row=2, column=0, sticky="w", pady=2)
        self.email_var = tk.StringVar(value="Not found")
        ttk.Entry(info_frame, textvariable=self.email_var, state="readonly", width=40).grid(row=2, column=1, sticky="ew", pady=2, padx=(5, 0))

        info_frame.columnconfigure(1, weight=1)

        # Violation info
        ttk.Label(main_frame, text="Violation Details", font=('Arial', 10, 'bold')).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 5))

        ttk.Label(main_frame, text="Violation Type:").grid(row=3, column=0, sticky="w", pady=5)
        self.type_var = tk.StringVar()
        violation_types = ["No Permit", "Expired Permit", "Wrong Zone", "Improper Parking",
                          "Blocking Access", "Fire Lane", "Handicap Zone", "Other"]
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var,
                                 values=violation_types, state="readonly")
        type_combo.grid(row=3, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Location:").grid(row=4, column=0, sticky="w", pady=5)
        self.location_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.location_var).grid(row=4, column=1, sticky="ew", pady=5)

        ttk.Label(main_frame, text="Fine Amount:").grid(row=5, column=0, sticky="w", pady=5)
        self.fine_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.fine_var).grid(row=5, column=1, sticky="ew", pady=5)

        # Payment status (for editing)
        if self.violation_data:
            ttk.Label(main_frame, text="Payment Status:").grid(row=6, column=0, sticky="w", pady=5)
            self.status_var = tk.StringVar()
            status_combo = ttk.Combobox(main_frame, textvariable=self.status_var,
                                       values=["Paid", "Unpaid", "Appealed", "Waived"], state="readonly")
            status_combo.grid(row=6, column=1, sticky="ew", pady=5)

        # Send Email Notification checkbox
        ttk.Label(main_frame, text="Notification:").grid(row=7, column=0, sticky="w", pady=5)
        self.send_email_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text="Send violation email to owner",
                       variable=self.send_email_var).grid(row=7, column=1, sticky="w", pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=8, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
        
        # Auto-set fine amount based on violation type
        type_combo.bind('<<ComboboxSelected>>', self.set_default_fine)
        
        # Load existing data if editing
        if self.violation_data:
            self.load_violation_data()

    def lookup_vehicle(self):
        """Lookup vehicle and owner from license plate"""
        license_plate = self.plate_var.get().strip().upper()

        if not license_plate:
            messagebox.showwarning("Warning", "Please enter a license plate")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Search for vehicle by license plate
            cursor.execute('''
                SELECT vehicle_id, license_plate, make, model, year, color, owner_id
                FROM vehicles
                WHERE UPPER(license_plate) = ?
            ''', (license_plate,))

            vehicle = cursor.fetchone()

            if vehicle:
                self.vehicle_id = vehicle[0]
                vehicle_desc = f"{vehicle[2]} {vehicle[3]} {vehicle[4]} ({vehicle[5]})"
                self.vehicle_info_var.set(vehicle_desc)

                # Lookup owner if vehicle has owner_id
                if vehicle[6]:  # owner_id
                    owner_id = vehicle[6]
                    owner_found = False

                    # First try students table
                    cursor.execute('''
                        SELECT student_id, first_name, last_name, email_address
                        FROM students
                        WHERE student_id = ?
                    ''', (owner_id,))

                    student = cursor.fetchone()

                    if student:
                        self.student_id = student[0]
                        owner_name = f"{student[1]} {student[2]}"
                        email = student[3] if student[3] else "No email on file"
                        owner_found = True
                    else:
                        # Fall back to users table (for admin/staff)
                        cursor.execute('''
                            SELECT username, first_name, last_name, email
                            FROM users
                            WHERE username = ? OR id = ?
                        ''', (owner_id, owner_id))

                        user = cursor.fetchone()

                        if user:
                            self.student_id = user[0]  # Use username as ID
                            owner_name = f"{user[1] or ''} {user[2] or ''}".strip() or user[0]
                            email = user[3] if user[3] else "No email on file"
                            owner_found = True

                    if owner_found:
                        self.owner_info_var.set(owner_name)
                        self.email_var.set(email)

                        messagebox.showinfo("Success",
                            f"Vehicle found!\n\n"
                            f"Vehicle: {vehicle_desc}\n"
                            f"Owner: {owner_name}\n"
                            f"Email: {email}")
                    else:
                        self.owner_info_var.set("Owner not found in database")
                        self.email_var.set("No email")
                        messagebox.showwarning("Partial Match",
                            f"Vehicle found: {vehicle_desc}\n"
                            f"But owner ID {owner_id} not found in students or users database")
                else:
                    self.owner_info_var.set("No owner linked")
                    self.email_var.set("No email")
                    messagebox.showinfo("Vehicle Found",
                        f"Vehicle found: {vehicle_desc}\n"
                        f"No owner is linked to this vehicle")
            else:
                self.vehicle_info_var.set("Not found")
                self.owner_info_var.set("Not found")
                self.email_var.set("Not found")
                self.vehicle_id = None
                self.student_id = None
                messagebox.showwarning("Not Found",
                    f"No vehicle found with license plate: {license_plate}")

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to lookup vehicle: {e}")
            logging.error(f"Vehicle lookup error in violation dialog: {e}")

    def set_default_fine(self, event=None):
        violation_type = self.type_var.get()
        fine_amounts = {
            "No Permit": 50.00,
            "Expired Permit": 40.00,
            "Wrong Zone": 40.00,
            "Improper Parking": 30.00,
            "Blocking Access": 75.00,
            "Fire Lane": 100.00,
            "Handicap Zone": 250.00,
            "Other": 50.00
        }
        
        default_fine = fine_amounts.get(violation_type, 50.00)
        self.fine_var.set(str(default_fine))
    
    def load_violation_data(self):
        if self.violation_data:
            self.plate_var.set(self.violation_data[2])  # license_plate
            self.type_var.set(self.violation_data[3])   # violation_type
            self.location_var.set(self.violation_data[7])  # location
            self.fine_var.set(str(self.violation_data[5]))  # fine_amount
            if hasattr(self, 'status_var'):
                self.status_var.set(self.violation_data[6])  # payment_status
    
    def save(self):
        # Validate required fields
        if not all([self.plate_var.get(), self.type_var.get(), 
                   self.location_var.get(), self.fine_var.get()]):
            messagebox.showerror("Error", "Please fill in all required fields")
            return
        
        try:
            fine_amount = float(self.fine_var.get())
            if fine_amount < 0:
                raise ValueError("Fine amount cannot be negative")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid fine amount")
            return
        
        self.result = {
            'license_plate': self.plate_var.get().upper(),
            'violation_type': self.type_var.get(),
            'location': self.location_var.get(),
            'fine_amount': fine_amount,
            'payment_status': getattr(self, 'status_var', tk.StringVar(value='Unpaid')).get(),
            'vehicle_id': self.vehicle_id,
            'student_id': self.student_id,
            'send_email': self.send_email_var.get(),
            'student_email': self.email_var.get() if self.email_var.get() not in ["Not found", "No email", "No email on file"] else None
        }
        
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()


class LotDialog:
    def __init__(self, parent, title, lot_data=None):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x350")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.lot_data = lot_data
        self.setup_ui()
    
    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Lot info
        ttk.Label(main_frame, text="Lot Name:").grid(row=0, column=0, sticky="w", pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var).grid(row=0, column=1, sticky="ew", pady=5)
        
        ttk.Label(main_frame, text="Location:").grid(row=1, column=0, sticky="w", pady=5)
        self.location_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.location_var).grid(row=1, column=1, sticky="ew", pady=5)
        
        ttk.Label(main_frame, text="Total Spaces:").grid(row=2, column=0, sticky="w", pady=5)
        self.spaces_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.spaces_var).grid(row=2, column=1, sticky="ew", pady=5)
        
        ttk.Label(main_frame, text="Zone:").grid(row=3, column=0, sticky="w", pady=5)
        self.zone_var = tk.StringVar()
        zone_combo = ttk.Combobox(main_frame, textvariable=self.zone_var, 
                                 values=list(PARKING_ZONES.keys()), state="readonly")
        zone_combo.grid(row=3, column=1, sticky="ew", pady=5)
        
        ttk.Label(main_frame, text="Hours of Operation:").grid(row=4, column=0, sticky="w", pady=5)
        self.hours_var = tk.StringVar(value="24/7")
        ttk.Entry(main_frame, textvariable=self.hours_var).grid(row=4, column=1, sticky="ew", pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
        
        # Load existing data if editing
        if self.lot_data:
            self.load_lot_data()
    
    def load_lot_data(self):
        if self.lot_data:
            self.name_var.set(self.lot_data[1])     # lot_name
            self.location_var.set(self.lot_data[2]) # location
            self.spaces_var.set(str(self.lot_data[3]))  # total_spaces
            self.zone_var.set(self.lot_data[5])     # zone
            self.hours_var.set(self.lot_data[6])    # hours_of_operation
    
    def save(self):
        # Validate required fields
        if not all([self.name_var.get(), self.location_var.get(), 
                   self.spaces_var.get(), self.zone_var.get()]):
            messagebox.showerror("Error", "Please fill in all required fields")
            return
        
        try:
            total_spaces = int(self.spaces_var.get())
            if total_spaces <= 0:
                raise ValueError("Total spaces must be positive")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number of spaces")
            return
        
        self.result = {
            'lot_name': self.name_var.get(),
            'location': self.location_var.get(),
            'total_spaces': total_spaces,
            'zone': self.zone_var.get(),
            'hours': self.hours_var.get() or "24/7"
        }
        
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()


class ExportDialog:
    def __init__(self, parent):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Export Data")
        self.dialog.geometry("300x250")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.setup_ui()
    
    def setup_ui(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        ttk.Label(main_frame, text="Export Type:").grid(row=0, column=0, sticky="w", pady=5)
        self.export_var = tk.StringVar()
        export_combo = ttk.Combobox(main_frame, textvariable=self.export_var, 
                                   values=["permits", "vehicles", "violations", "lots"], 
                                   state="readonly")
        export_combo.grid(row=0, column=1, sticky="ew", pady=5)
        
        ttk.Label(main_frame, text="Format:").grid(row=1, column=0, sticky="w", pady=5)
        self.format_var = tk.StringVar()
        format_combo = ttk.Combobox(main_frame, textvariable=self.format_var, 
                                   values=["csv", "excel", "pdf", "txt"], 
                                   state="readonly")
        format_combo.grid(row=1, column=1, sticky="ew", pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Export", command=self.export).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
    
    def export(self):
        if not self.export_var.get() or not self.format_var.get():
            messagebox.showerror("Error", "Please select both export type and format")
            return
        
        self.result = (self.export_var.get(), self.format_var.get())
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()


class PaymentDialog:
    """Dialog for processing parking fine payments"""

    def __init__(self, parent, violation_data, current_user=None):
        self.result = None
        self.violation_data = violation_data
        self.current_user = current_user
        self.payment_method = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Pay Parking Fine")
        self.dialog.geometry("550x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text=f"Pay Parking Fine - {self.violation_data[0]}",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Violation details
        details_frame = ttk.LabelFrame(main_frame, text="Violation Details", padding="10")
        details_frame.pack(fill=tk.X, pady=(0, 15))

        details = [
            ("Type:", self.violation_data[2]),
            ("License Plate:", self.violation_data[1]),
            ("Date:", self.violation_data[3]),
            ("Location:", self.violation_data[6]),
            ("Fine Amount:", f"${float(self.violation_data[4]):.2f}"),
            ("Status:", self.violation_data[5])
        ]

        for i, (label, value) in enumerate(details):
            ttk.Label(details_frame, text=label, font=('Arial', 9, 'bold')).grid(
                row=i, column=0, sticky=tk.W, pady=2, padx=(0, 10))
            ttk.Label(details_frame, text=str(value)).grid(
                row=i, column=1, sticky=tk.W, pady=2)

        # Payment method selection
        method_frame = ttk.LabelFrame(main_frame, text="Select Payment Method", padding="10")
        method_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Get student balance if available
        student_id = self.get_student_id_from_violation()
        current_balance = None
        new_balance = None

        if student_id:
            try:
                from university_system.modules.shared.utils.finance_integration import get_student_finance_account_balance
                current_balance = get_student_finance_account_balance(student_id)
                new_balance = current_balance - float(self.violation_data[4])
            except Exception as e:
                logging.warning(f"Could not get student balance: {e}")

        # Display balance if available
        if current_balance is not None:
            balance_frame = ttk.Frame(method_frame)
            balance_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(balance_frame, text=f"Current Student Account Balance: ${current_balance:.2f}",
                     foreground='blue', font=('Arial', 10)).pack()
            ttk.Label(balance_frame, text=f"New Balance After Payment: ${new_balance:.2f}",
                     foreground='green' if new_balance >= 0 else 'red',
                     font=('Arial', 10)).pack()

            if new_balance < 0:
                ttk.Label(balance_frame, text="⚠ Insufficient balance for student account payment",
                         foreground='red').pack()

        # Payment buttons
        btn_container = ttk.Frame(method_frame)
        btn_container.pack(fill=tk.BOTH, expand=True)

        tk.Button(btn_container, text="💵 Pay with Cash",
                 command=lambda: self.select_payment_method('cash'),
                 font=('Arial', 11, 'bold'), bg='#27ae60', fg='white',
                 activebackground='#229954', activeforeground='white',
                 relief='raised', padx=20, pady=12, cursor='hand2',
                 borderwidth=3).pack(pady=8, fill=tk.X)

        tk.Button(btn_container, text="💳 Pay with Card",
                 command=lambda: self.select_payment_method('card'),
                 font=('Arial', 11, 'bold'), bg='#3498db', fg='white',
                 activebackground='#2980b9', activeforeground='white',
                 relief='raised', padx=20, pady=12, cursor='hand2',
                 borderwidth=3).pack(pady=8, fill=tk.X)

        student_account_enabled = current_balance is not None and new_balance >= 0
        student_account_btn = tk.Button(btn_container, text="🏦 Pay with Student Account",
                                       command=lambda: self.select_payment_method('student_account'),
                                       font=('Arial', 11, 'bold'),
                                       bg='#9b59b6' if student_account_enabled else '#95a5a6',
                                       fg='white',
                                       activebackground='#8e44ad' if student_account_enabled else '#7f8c8d',
                                       activeforeground='white',
                                       relief='raised', padx=20, pady=12,
                                       cursor='hand2' if student_account_enabled else 'arrow',
                                       borderwidth=3,
                                       state='normal' if student_account_enabled else 'disabled')
        student_account_btn.pack(pady=8, fill=tk.X)

        # Cancel button
        ttk.Button(main_frame, text="Cancel", command=self.dialog.destroy).pack(pady=(10, 0))

    def get_student_id_from_violation(self):
        """Get student ID from violation license plate"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get vehicle owner from license plate
            cursor.execute("""
                SELECT owner_id FROM vehicles
                WHERE license_plate = ?
            """, (self.violation_data[1],))

            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except Exception as e:
            logging.error(f"Error getting student ID: {e}")
            return None

    def select_payment_method(self, method):
        """Process payment with selected method"""
        self.payment_method = method

        if not messagebox.askyesno("Confirm Payment",
                                   f"Process payment of ${float(self.violation_data[4]):.2f} via {method.replace('_', ' ').title()}?"):
            return

        self.result = {
            'violation_id': self.violation_data[0],
            'amount': float(self.violation_data[4]),
            'payment_method': method,
            'student_id': self.get_student_id_from_violation()
        }

        self.dialog.destroy()


class RefundDialog:
    """Dialog for processing parking payment refunds"""

    def __init__(self, parent, payment_data, current_user=None):
        self.result = None
        self.payment_data = payment_data
        self.current_user = current_user
        self.refund_method = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Refund Parking Payment")
        self.dialog.geometry("550x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text=f"Refund Payment - {self.payment_data[4]}",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Payment details
        details_frame = ttk.LabelFrame(main_frame, text="Payment Details", padding="10")
        details_frame.pack(fill=tk.X, pady=(0, 15))

        details = [
            ("Payment ID:", self.payment_data[0]),
            ("Violation ID:", self.payment_data[1]),
            ("Amount:", f"${float(self.payment_data[2]):.2f}"),
            ("Payment Method:", self.payment_data[3].replace('_', ' ').title()),
            ("Payment Reference:", self.payment_data[4]),
            ("Payment Date:", self.payment_data[5])
        ]

        for i, (label, value) in enumerate(details):
            ttk.Label(details_frame, text=label, font=('Arial', 9, 'bold')).grid(
                row=i, column=0, sticky=tk.W, pady=2, padx=(0, 10))
            ttk.Label(details_frame, text=str(value)).grid(
                row=i, column=1, sticky=tk.W, pady=2)

        # Refund method selection
        method_frame = ttk.LabelFrame(main_frame, text="Select Refund Method", padding="10")
        method_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Get student balance if refunding to student account
        student_id = self.payment_data[6] if len(self.payment_data) > 6 else None
        current_balance = None
        new_balance = None

        if student_id:
            try:
                from university_system.modules.shared.utils.finance_integration import get_student_finance_account_balance
                current_balance = get_student_finance_account_balance(student_id)
                new_balance = current_balance + float(self.payment_data[2])

                balance_frame = ttk.Frame(method_frame)
                balance_frame.pack(fill=tk.X, pady=(0, 10))

                ttk.Label(balance_frame, text=f"Current Student Account Balance: ${current_balance:.2f}",
                         foreground='blue', font=('Arial', 10)).pack()
                ttk.Label(balance_frame, text=f"New Balance After Refund: ${new_balance:.2f}",
                         foreground='green', font=('Arial', 10)).pack()
            except Exception as e:
                logging.warning(f"Could not get student balance: {e}")

        # Refund buttons
        btn_container = ttk.Frame(method_frame)
        btn_container.pack(fill=tk.BOTH, expand=True)

        tk.Button(btn_container, text="💵 Refund as Cash",
                 command=lambda: self.select_refund_method('cash'),
                 font=('Arial', 11, 'bold'), bg='#27ae60', fg='white',
                 activebackground='#229954', activeforeground='white',
                 relief='raised', padx=20, pady=12, cursor='hand2',
                 borderwidth=3).pack(pady=8, fill=tk.X)

        tk.Button(btn_container, text="💳 Refund to Card",
                 command=lambda: self.select_refund_method('card'),
                 font=('Arial', 11, 'bold'), bg='#3498db', fg='white',
                 activebackground='#2980b9', activeforeground='white',
                 relief='raised', padx=20, pady=12, cursor='hand2',
                 borderwidth=3).pack(pady=8, fill=tk.X)

        tk.Button(btn_container, text="🏦 Refund to Student Account",
                 command=lambda: self.select_refund_method('student_account'),
                 font=('Arial', 11, 'bold'), bg='#9b59b6', fg='white',
                 activebackground='#8e44ad', activeforeground='white',
                 relief='raised', padx=20, pady=12, cursor='hand2',
                 borderwidth=3).pack(pady=8, fill=tk.X)

        # Cancel button
        ttk.Button(main_frame, text="Cancel", command=self.dialog.destroy).pack(pady=(10, 0))

    def select_refund_method(self, method):
        """Process refund with selected method"""
        self.refund_method = method

        if not messagebox.askyesno("Confirm Refund",
                                   f"Process refund of ${float(self.payment_data[2]):.2f} via {method.replace('_', ' ').title()}?"):
            return

        self.result = {
            'payment_id': self.payment_data[0],
            'violation_id': self.payment_data[1],
            'amount': float(self.payment_data[2]),
            'refund_method': method,
            'student_id': self.payment_data[6] if len(self.payment_data) > 6 else None
        }

        self.dialog.destroy()


# Console compatibility function
def run_console_interface():
    """Run the original console interface"""
    try:
        # Import and run the original console interface
        from parking_management import display_parking_menu
        display_parking_menu()
    except ImportError:
        print("Console interface not available")


def main():
    """Main function to choose between GUI and console interface"""
    import sys
    
    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == '--console':
        # Run console interface
        run_console_interface()
    else:
        # Run GUI interface
        root = tk.Tk()
        app = ParkingManagementGUI(root)
        
        # Fix: Properly add console menu option
        try:
            # The menubar is already created in app.create_menu_bar()
            # We can access it through the root window
            existing_menubar = root.nametowidget(root['menu']) if root['menu'] else None
            if existing_menubar:
                console_menu = tk.Menu(existing_menubar, tearoff=0)
                console_menu.add_command(label="Switch to Console", command=run_console_interface)
                existing_menubar.add_cascade(label="Interface", menu=console_menu)
        except Exception as e:
            print(f"Warning: Could not add console menu: {e}")
        
        root.mainloop()

if __name__ == "__main__":
    main()
