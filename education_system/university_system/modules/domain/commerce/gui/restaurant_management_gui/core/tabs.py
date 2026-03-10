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


def create_menu_tab(self, parent=None):
    """Create menu management tab"""
    if parent is None:
        menu_frame = ttk.Frame(self.notebook)
        self.notebook.add(menu_frame, text=_t("restaurant.tab_menu_items"))
    else:
        menu_frame = parent
    btn_frame = ttk.Frame(menu_frame)
    btn_frame.pack(fill='x', padx=10, pady=10)
    ttk.Button(btn_frame, text=_t("restaurant.view_all_items"),
              command=self.view_menu_items).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.add_new_item"),
              command=self.add_menu_item_dialog).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.update_item"),
              command=self.update_menu_item_dialog).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.menu_analytics"),
              command=self.show_menu_analytics).pack(side='left', padx=5)
    
    columns = ('ID', 'Name', 'Category', 'Price', 'Available', 'Vegetarian', 'Vegan')
    column_labels = (
        _t("restaurant.columns.id"),
        _t("restaurant.columns.name"),
        _t("restaurant.columns.category"),
        _t("restaurant.columns.price"),
        _t("restaurant.columns.available"),
        _t("restaurant.columns.vegetarian"),
        _t("restaurant.columns.vegan")
    )
    self.menu_tree = ttk.Treeview(menu_frame, columns=columns, show='headings', height=20)

    for col, label in zip(columns, column_labels):
        self.menu_tree.heading(col, text=label)
        self.menu_tree.column(col, width=100)
    
    tree_frame = ttk.Frame(menu_frame)
    tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
    scrollbar_menu = ttk.Scrollbar(tree_frame, orient='vertical', command=self.menu_tree.yview)
    self.menu_tree.configure(yscrollcommand=scrollbar_menu.set)
    
    self.menu_tree.pack(side='left', fill='both', expand=True)
    scrollbar_menu.pack(side='right', fill='y')

def create_place_order_tab(self, parent=None):
    """Create place new order tab"""
    from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.orders import place_order
    if parent is None:
        place_order_frame = ttk.Frame(self.notebook)
        self.notebook.add(place_order_frame, text="📝 Place Order")
    else:
        place_order_frame = parent
    place_order.create_place_order_tab(self, place_order_frame)

def create_orders_tab(self, parent=None):
    """Create orders management tab"""
    if parent is None:
        orders_frame = ttk.Frame(self.notebook)
        self.notebook.add(orders_frame, text=_t("restaurant.tab_orders"))
    else:
        orders_frame = parent
    btn_frame = ttk.Frame(orders_frame)
    btn_frame.pack(fill='x', padx=10, pady=10)
    ttk.Button(btn_frame, text=_t("restaurant.view_orders"),
              command=self.view_orders_gui).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.update_status"),
              command=self.update_order_status_dialog).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.process_payment"),
              command=self.process_payment_dialog).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.add_tip"),
              command=self.add_tip).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.apply_discount"),
              command=self.apply_discount).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.refund_order"),
              command=self.refund_order).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.order_analytics"),
              command=self.show_order_analytics).pack(side='left', padx=5)

    columns = ('Order ID', 'Customer', 'Date', 'Total', 'Status', 'Payment')
    column_labels = (
        _t("restaurant.columns.order_id"),
        _t("restaurant.columns.customer"),
        _t("restaurant.columns.date"),
        _t("restaurant.columns.total"),
        _t("restaurant.columns.status"),
        _t("restaurant.columns.payment")
    )
    self.orders_tree = ttk.Treeview(orders_frame, columns=columns, show='headings', height=20)

    for col, label in zip(columns, column_labels):
        self.orders_tree.heading(col, text=label)
        self.orders_tree.column(col, width=120)

    tree_frame = ttk.Frame(orders_frame)
    tree_frame.pack(fill='both', expand=True, padx=10, pady=10)

    scrollbar_orders = ttk.Scrollbar(tree_frame, orient='vertical', command=self.orders_tree.yview)
    self.orders_tree.configure(yscrollcommand=scrollbar_orders.set)

    self.orders_tree.pack(side='left', fill='both', expand=True)
    scrollbar_orders.pack(side='right', fill='y')

def create_refunds_tab(self, parent=None):
    """Create payment refunds management tab"""
    from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.orders import refunds
    if parent is None:
        refunds_frame = ttk.Frame(self.notebook)
        self.notebook.add(refunds_frame, text="Refunds")
    else:
        refunds_frame = parent
    refunds.create_refunds_tab(self, refunds_frame)

def create_customers_tab(self, parent=None):
    """Create customer management tab"""
    if parent is None:
        customers_frame = ttk.Frame(self.notebook)
        self.notebook.add(customers_frame, text=_t("restaurant.tab_customers"))
    else:
        customers_frame = parent
    btn_frame = ttk.Frame(customers_frame)
    btn_frame.pack(fill='x', padx=10, pady=10)
    ttk.Button(btn_frame, text=_t("restaurant.view_customers"),
              command=self.view_customers_gui).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.add_customer"),
              command=self.add_customer_dialog).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.update_customer"),
              command=self.update_customer_dialog).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.loyalty_program"),
              command=self.manage_loyalty_dialog).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.customer_feedback"),
              command=self.manage_customer_feedback).pack(side='left', padx=5)
    
    columns = ('ID', 'Name', 'Email', 'Phone', 'Loyalty Tier', 'Points', 'Total Spent')
    column_labels = (
        _t("restaurant.columns.id"),
        _t("restaurant.columns.name"),
        _t("restaurant.columns.email"),
        _t("restaurant.columns.phone"),
        _t("restaurant.columns.loyalty_tier"),
        _t("restaurant.columns.points"),
        _t("restaurant.columns.total_spent")
    )
    self.customers_tree = ttk.Treeview(customers_frame, columns=columns, show='headings', height=20)

    for col, label in zip(columns, column_labels):
        self.customers_tree.heading(col, text=label)
        self.customers_tree.column(col, width=110)
    
    tree_frame = ttk.Frame(customers_frame)
    tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
    scrollbar_customers = ttk.Scrollbar(tree_frame, orient='vertical', command=self.customers_tree.yview)
    self.customers_tree.configure(yscrollcommand=scrollbar_customers.set)
    
    self.customers_tree.pack(side='left', fill='both', expand=True)
    scrollbar_customers.pack(side='right', fill='y')

def create_tables_tab(self, parent=None):
    """Create table management tab"""
    if parent is None:
        tables_frame = ttk.Frame(self.notebook)
        self.notebook.add(tables_frame, text=_t("restaurant.tab_tables"))
    else:
        tables_frame = parent
    btn_frame = ttk.Frame(tables_frame)
    btn_frame.pack(fill='x', padx=10, pady=10)
    ttk.Button(btn_frame, text=_t("restaurant.view_tables"),
              command=self.view_tables_gui).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.add_table"),
              command=self.add_table_dialog).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.reservations"),
              command=self.manage_reservations_dialog).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.generate_qr"),
              command=self.generate_qr_dialog).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.optimize_layout"),
              command=self.optimize_table_structure).pack(side='left', padx=5)
    
    columns = ('Table ID', 'Capacity', 'Status', 'Location', 'Type')
    column_labels = (
        _t("restaurant.columns.table_id"),
        _t("restaurant.columns.capacity"),
        _t("restaurant.columns.status"),
        _t("restaurant.columns.location"),
        _t("restaurant.columns.type")
    )
    self.tables_tree = ttk.Treeview(tables_frame, columns=columns, show='headings', height=20)

    for col, label in zip(columns, column_labels):
        self.tables_tree.heading(col, text=label)
        self.tables_tree.column(col, width=120)
    
    tree_frame = ttk.Frame(tables_frame)
    tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
    scrollbar_tables = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tables_tree.yview)
    self.tables_tree.configure(yscrollcommand=scrollbar_tables.set)
    
    self.tables_tree.pack(side='left', fill='both', expand=True)
    scrollbar_tables.pack(side='right', fill='y')

def create_staff_tab(self, parent=None):
    """Create staff management tab"""
    if parent is None:
        staff_frame = ttk.Frame(self.notebook)
        self.notebook.add(staff_frame, text=_t("restaurant.tab_staff"))
    else:
        staff_frame = parent
    btn_frame = ttk.Frame(staff_frame)
    btn_frame.pack(fill='x', padx=10, pady=10)
    ttk.Button(btn_frame, text=_t("restaurant.view_staff"),
              command=self.view_staff_gui).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.add_staff"),
              command=self.add_staff_dialog).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.manage_schedules"),
              command=self.manage_schedules_dialog).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.schedule_conflicts"),
              command=self.view_schedule_conflicts).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.staff_performance"),
              command=self.staff_performance).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.staff_analytics"),
              command=self.show_staff_analytics).pack(side='left', padx=5)
    
    columns = ('Staff ID', 'Name', 'Role', 'Hourly Rate', 'Status', 'Performance')
    column_labels = (
        _t("restaurant.columns.staff_id"),
        _t("restaurant.columns.name"),
        _t("restaurant.columns.role"),
        _t("restaurant.columns.hourly_rate"),
        _t("restaurant.columns.status"),
        _t("restaurant.columns.performance")
    )
    self.staff_tree = ttk.Treeview(staff_frame, columns=columns, show='headings', height=20)

    for col, label in zip(columns, column_labels):
        self.staff_tree.heading(col, text=label)
        self.staff_tree.column(col, width=120)
    
    tree_frame = ttk.Frame(staff_frame)
    tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
    scrollbar_staff = ttk.Scrollbar(tree_frame, orient='vertical', command=self.staff_tree.yview)
    self.staff_tree.configure(yscrollcommand=scrollbar_staff.set)
    
    self.staff_tree.pack(side='left', fill='both', expand=True)
    scrollbar_staff.pack(side='right', fill='y')

def create_inventory_tab(self, parent=None):
    """Create inventory management tab"""
    if parent is None:
        inventory_frame = ttk.Frame(self.notebook)
        self.notebook.add(inventory_frame, text=_t("restaurant.tab_inventory"))
    else:
        inventory_frame = parent
    btn_frame = ttk.Frame(inventory_frame)
    btn_frame.pack(fill='x', padx=10, pady=10)
    ttk.Button(btn_frame, text=_t("restaurant.view_inventory"),
              command=self.view_inventory_gui).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.purchase_orders"),
              command=self.manage_purchase_orders_dialog).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.suppliers"),
              command=self.manage_suppliers_dialog).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.waste_tracking"),
              command=self.waste_tracking_dialog).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.inventory_reports"),
              command=self.inventory_reports).pack(side='left', padx=5)
    ttk.Button(btn_frame, text=_t("restaurant.low_stock_alerts"),
              command=self.low_stock_alerts).pack(side='left', padx=5)
    
    columns = ('Item ID', 'Name', 'Quantity', 'Unit', 'Cost/Unit', 'Reorder Level')
    column_labels = (
        _t("restaurant.columns.item_id"),
        _t("restaurant.columns.name"),
        _t("restaurant.columns.quantity"),
        _t("restaurant.columns.unit"),
        _t("restaurant.columns.cost_per_unit"),
        _t("restaurant.columns.reorder_level")
    )
    self.inventory_tree = ttk.Treeview(inventory_frame, columns=columns, show='headings', height=20)

    for col, label in zip(columns, column_labels):
        self.inventory_tree.heading(col, text=label)
        self.inventory_tree.column(col, width=120)
    
    tree_frame = ttk.Frame(inventory_frame)
    tree_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
    scrollbar_inventory = ttk.Scrollbar(tree_frame, orient='vertical', command=self.inventory_tree.yview)
    self.inventory_tree.configure(yscrollcommand=scrollbar_inventory.set)
    
    self.inventory_tree.pack(side='left', fill='both', expand=True)
    scrollbar_inventory.pack(side='right', fill='y')

def create_reports_tab(self, parent=None):
    """Create reports tab"""
    if parent is None:
        reports_frame = ttk.Frame(self.notebook)
        self.notebook.add(reports_frame, text=_t("restaurant.tab_reports"))
    else:
        reports_frame = parent
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
    ttk.Label(scrollable_frame, text=_t("restaurant.basic_financial_reports"), style='Heading.TLabel').pack(pady=10)
    financial_frame = ttk.Frame(scrollable_frame)
    financial_frame.pack(fill='x', padx=20, pady=5)
    ttk.Button(financial_frame, text=_t("restaurant.daily_sales"),
              command=self.daily_sales_report).pack(side='left', padx=5)
    ttk.Button(financial_frame, text=_t("restaurant.monthly_summary"),
              command=self.monthly_summary_report).pack(side='left', padx=5)
    ttk.Button(financial_frame, text=_t("restaurant.profit_analysis"),
              command=self.profit_analysis_report).pack(side='left', padx=5)
    # Advanced Financial Reports
    ttk.Label(scrollable_frame, text=_t("restaurant.advanced_financial_reports"), style='Heading.TLabel').pack(pady=(20, 10))
    advanced_financial_frame = ttk.Frame(scrollable_frame)
    advanced_financial_frame.pack(fill='x', padx=20, pady=5)
    ttk.Button(advanced_financial_frame, text=_t("restaurant.payroll_report"),
              command=self.export_payroll_report).pack(side='left', padx=5)
    ttk.Button(advanced_financial_frame, text=_t("restaurant.expense_report"),
              command=self.export_expense_report).pack(side='left', padx=5)
    ttk.Button(advanced_financial_frame, text=_t("restaurant.tax_reports"),
              command=self.tax_reports_menu).pack(side='left', padx=5)
    ttk.Button(advanced_financial_frame, text=_t("restaurant.financial_forecast"),
              command=self.financial_forecasting).pack(side='left', padx=5)
    # Data Export
    ttk.Label(scrollable_frame, text=_t("restaurant.data_export"), style='Heading.TLabel').pack(pady=(20, 10))
    export_frame = ttk.Frame(scrollable_frame)
    export_frame.pack(fill='x', padx=20, pady=5)
    ttk.Button(export_frame, text=_t("restaurant.export_financial_data"),
              command=self.export_financial_data_menu).pack(side='left', padx=5)
    ttk.Button(export_frame, text=_t("restaurant.export_sales_data"),
              command=self.export_sales_data).pack(side='left', padx=5)
    # Operational Reports
    ttk.Label(scrollable_frame, text=_t("restaurant.operational_reports"), style='Heading.TLabel').pack(pady=(20, 10))
    operational_frame = ttk.Frame(scrollable_frame)
    operational_frame.pack(fill='x', padx=20, pady=5)
    ttk.Button(operational_frame, text=_t("restaurant.menu_performance"),
              command=self.menu_performance_report).pack(side='left', padx=5)
    ttk.Button(operational_frame, text=_t("restaurant.customer_analytics"),
              command=self.customer_analytics_report).pack(side='left', padx=5)
    ttk.Button(operational_frame, text=_t("restaurant.staff_performance_report"),
              command=self.staff_performance_report).pack(side='left', padx=5)
    # System Tools
    ttk.Label(scrollable_frame, text=_t("restaurant.system_tools"), style='Heading.TLabel').pack(pady=(20, 10))
    tools_frame = ttk.Frame(scrollable_frame)
    tools_frame.pack(fill='x', padx=20, pady=5)
    ttk.Button(tools_frame, text=_t("restaurant.system_settings"),
              command=self.display_system_settings).pack(side='left', padx=5)
    ttk.Button(tools_frame, text=_t("restaurant.backup_recovery"),
              command=self.backup_database).pack(side='left', padx=5)
    # Report Output
    ttk.Label(scrollable_frame, text=_t("restaurant.report_output"), style='Heading.TLabel').pack(pady=(20, 5))
    self.report_text = ScrolledText(scrollable_frame, height=15, width=80)
    self.report_text.pack(fill='both', expand=True, padx=20, pady=10)
    # Pack the canvas and scrollbar
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

