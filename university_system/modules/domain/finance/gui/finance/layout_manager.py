"""UI layout and navigation"""

from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from university_system.infrastructure.database.db import sqlite3
import sys
import io
import os
import csv
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import json
import threading
import warnings
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
from cryptography.fernet import Fernet
import logging
import qrcode
from io import BytesIO
import base64
from university_system.modules.domain.finance.gui.finance_reporting import launch_financial_gui
from university_system.modules.shared.utils.i18n import get_text as _

# Import Research & Grants GUI
try:
    from university_system.modules.domain.research.gui.research_grants_gui import launch_research_grants_gui
    RESEARCH_GRANTS_AVAILABLE = True
except ImportError:
    RESEARCH_GRANTS_AVAILABLE = False
    launch_research_grants_gui = None

# Import Financial Aid & Scholarships GUI
try:
    from university_system.modules.domain.finance.gui.financial_aid.financial_aid_gui import launch_financial_aid_gui
    FINANCIAL_AID_GUI_AVAILABLE = True
except ImportError:
    FINANCIAL_AID_GUI_AVAILABLE = False
    launch_financial_aid_gui = None

# Import authentication - REQUIRED (no fallback for security)
from university_system.infrastructure.auth import UserAuth, get_global_auth
from university_system.infrastructure.shared_context import get_auth

# Import other modules with backward compatibility fallbacks
try:
    from university_system.infrastructure.email.email_service import send_email
    from university_system.infrastructure.database.db import get_connection, transaction
    from university_system.infrastructure.logging.log_config import configure_logging, get_log_file
except ImportError:
    # Fallback for backward compatibility (non-security critical)
    def send_email(*args, **kwargs):
        return True

    from pathlib import Path
    def get_connection():
        """
        Fallback database connection for standalone mode.
        Use the central student_records.db located in the refactored/db_files
        directory rather than creating an enhanced_student_finance.db in the
        current working directory. This ensures the application operates on
        a single database file when the main refactored modules are not
        available.
        """
        # Determine the project root (refactored directory) one level above finance
        base_dir = Path(__file__).resolve().parents[1]
        db_path = base_dir / "db_files" / str(DEFAULT_DB_PATH)
        return sqlite3.connect(str(DEFAULT_DB_PATH))

    def configure_logging(name=None):
        return logging.getLogger(name or __name__)

    def get_log_file(name):
        from university_system.modules.shared.constants import paths
        return str(paths.LOG_DIR / name)

try:
    from university_system.modules.finance.core.financial_core import (
        assign_to_collection_agency, track_collection_progress,
        update_collection_case_status, create_payment_arrangement,
        send_arrangement_confirmation, setup_collection_workflows,
        check_required_packages, ensure_database_exists, verify_fix
    )
except ImportError:
    # Stub implementations for missing functions
    def assign_to_collection_agency(*args, **kwargs):
        print("assign_to_collection_agency function not implemented")
    
    def track_collection_progress(*args, **kwargs):
        print("track_collection_progress function not implemented")
    
    def update_collection_case_status(*args, **kwargs):
        print("update_collection_case_status function not implemented")
    
    def create_payment_arrangement(*args, **kwargs):
        print("create_payment_arrangement function not implemented")
    
    def send_arrangement_confirmation(*args, **kwargs):
        print("send_arrangement_confirmation function not implemented")
    
    def setup_collection_workflows(*args, **kwargs):
        print("setup_collection_workflows function not implemented")
    
    def check_required_packages(*args, **kwargs):
        print("check_required_packages function not implemented")
    
    def ensure_database_exists(*args, **kwargs):
        print("ensure_database_exists function not implemented")
    
    def verify_fix(*args, **kwargs):
        print("verify_fix function not implemented")

# Add these import stubs for the missing functions if they don't exist
try:
    from university_system.modules.finance.core.financial_core import (
        modify_payment_plan, view_student_credits, add_student_credit,
        manage_financial_aid, create_budget_plan, view_overdue_accounts,
        create_collection_case, aging_analysis_report, collection_case_status_report,
        view_student_collection_detail, manage_collection_agencies,
        budget_vs_actual_analysis, generate_aid_reports, aid_distribution_summary,
        aid_by_academic_year, loan_repayment_status_report, aid_effectiveness_analysis,
        track_loan_repayments, view_aid_types, create_aid_type, edit_aid_type,
        deactivate_aid_type, review_pending_aid_applications, process_loan_payment,
        view_aid_application_detail, manage_budget_categories, view_budget_categories,
        create_budget_category, edit_budget_category, deactivate_budget_category,
        variance_analysis_report, budget_performance_trends, category_performance_report,
        collection_performance_summary, monthly_revenue_trend_report,
        enhanced_notification_system, manage_aid_types, recovery_rate_analysis,
        agency_performance_report, export_forecast_report, complete_database_fix,
        quick_fix_database, initialize_finance, detect_payment_fraud,
        setup_email_config, setup_sms_config, generate_qr_payment_code,
        process_stripe_payment, create_approval_workflow, apply_credit_to_fees,
        update_actual_amounts, view_credit_history, send_collection_notice,
        add_collection_agency, edit_collection_agency, deactivate_collection_agency,
        view_collection_agencies, test_email_service, test_sms_service,
        generate_audit_report
    )
except ImportError:
    # Create stub functions for missing finance core features so the GUI can still load
    def _make_stub(name):
        def _stub(*args, **kwargs):
            print(f"{name} function not implemented")
        return _stub

    _missing_functions = [
        'modify_payment_plan', 'view_student_credits', 'add_student_credit',
        'manage_financial_aid', 'create_budget_plan', 'view_overdue_accounts',
        'create_collection_case', 'aging_analysis_report', 'collection_case_status_report',
        'view_student_collection_detail', 'manage_collection_agencies',
        'budget_vs_actual_analysis', 'generate_aid_reports', 'aid_distribution_summary',
        'aid_by_academic_year', 'loan_repayment_status_report', 'aid_effectiveness_analysis',
        'track_loan_repayments', 'view_aid_types', 'create_aid_type', 'edit_aid_type',
        'deactivate_aid_type', 'review_pending_aid_applications', 'process_loan_payment',
        'view_aid_application_detail', 'manage_budget_categories', 'view_budget_categories',
        'create_budget_category', 'edit_budget_category', 'deactivate_budget_category',
        'variance_analysis_report', 'budget_performance_trends', 'category_performance_report',
        'collection_performance_summary', 'monthly_revenue_trend_report',
        'enhanced_notification_system', 'manage_aid_types', 'recovery_rate_analysis',
        'agency_performance_report', 'export_forecast_report', 'complete_database_fix',
        'quick_fix_database', 'initialize_finance', 'detect_payment_fraud',
        'setup_email_config', 'setup_sms_config', 'generate_qr_payment_code',
        'process_stripe_payment', 'create_approval_workflow', 'apply_credit_to_fees',
        'update_actual_amounts', 'view_credit_history', 'send_collection_notice',
        'add_collection_agency', 'edit_collection_agency', 'deactivate_collection_agency',
        'view_collection_agencies', 'test_email_service', 'test_sms_service',
        'generate_audit_report'
    ]

    globals().update({name: _make_stub(name) for name in _missing_functions})

# Configure logging
log_path = get_log_file("analytics.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)

logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')

# Global variables for backward compatibility
auth = get_global_auth()  # Use centralized auth instance
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# Payment gateway configurations (from original file)
PAYMENT_GATEWAYS = {
    'stripe': {
        'public_key': 'pk_test_...',
        'secret_key': 'sk_test_...',
        'webhook_secret': 'whsec_...'
    },
    'paypal': {
        'client_id': 'your_paypal_client_id',
        'client_secret': 'your_paypal_client_secret',
        'environment': 'sandbox'
    }
}

# WARNING: Never commit real API keys to version control!
# Set these environment variables in your deployment environment
SUPPORTED_CURRENCIES = ['GBP', 'USD', 'EUR', 'CAD', 'AUD']
# Load exchange API key from environment variable
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')




class LayoutManager:
    """UI layout and navigation"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn
        try:
            self.finance_system = gui.finance_system
        except Exception:
            self.finance_system = None

    def setup_styles(self):
        """Set up GUI styles and fonts"""
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Define custom styles
        self.style.configure('Title.TLabel', font=('Arial', 16, 'bold'))
        self.style.configure('Heading.TLabel', font=('Arial', 12, 'bold'))
        self.style.configure('Large.TButton', font=('Arial', 10, 'bold'), padding=10)
        
        # Color schemes - ADD 'info' color here
        self.colors = {
            'primary': '#2c3e50',
            'secondary': '#3498db',
            'success': '#27ae60',
            'warning': '#f39c12',
            'danger': '#e74c3c',
            'light': '#ecf0f1',
            'dark': '#34495e',
            'info': '#17a2b8'  # ADD this line
        }
        

    def create_main_interface(self):
        """Create the main GUI interface"""
        # Initialize colors if not already defined
        if not hasattr(self, 'colors'):
            self.colors = {
                'primary': '#2c3e50',
                'secondary': '#3498db',
                'success': '#27ae60',
                'warning': '#f39c12',
                'danger': '#e74c3c',
                'light': '#ecf0f1',
                'dark': '#2c3e50',
                'info': '#17a2b8'
            }
        
        # Main header
        header_frame = tk.Frame(self.root, bg=self.colors['primary'], height=80)
        header_frame.pack(fill='x', padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(
            header_frame,
            text=_("finance_gui.header.title"),
            font=('Arial', 20, 'bold'),
            fg='white',
            bg=self.colors['primary']
        )
        title_label.pack(side=tk.LEFT, expand=True, padx=20)

        # Return to Main Menu button
        return_btn = tk.Button(
            header_frame,
            text=_("finance_gui.header.return_to_main"),
            command=self.gui.return_to_main_menu,
            font=('Arial', 10, 'bold'),
            bg='white',
            fg=self.colors['primary'],
            padx=15,
            pady=5
        )
        return_btn.pack(side=tk.RIGHT, padx=20)
        
        # Main content area with button navigation
        self.main_container = tk.Frame(self.root)
        self.main_container.pack(fill='both', expand=True, padx=10, pady=10)
    
        # Create scrollable sidebar navigation
        sidebar_container = tk.Frame(self.main_container, width=250)
        sidebar_container.pack(side='left', fill='y', padx=(0, 10))
        sidebar_container.pack_propagate(False)
    
        # Canvas + scrollbar for sidebar
        self.nav_canvas = tk.Canvas(sidebar_container, bg=self.colors['primary'], highlightthickness=0, width=230)
        nav_scrollbar = ttk.Scrollbar(sidebar_container, orient="vertical", command=self.nav_canvas.yview)
        self.nav_frame = tk.Frame(self.nav_canvas, bg=self.colors['primary'])
    
        self.nav_frame.bind(
            "<Configure>",
            lambda e: self.nav_canvas.configure(scrollregion=self.nav_canvas.bbox("all"))
        )
    
        # Put navigation frame inside canvas
        self.nav_window = self.nav_canvas.create_window((0, 0), window=self.nav_frame, anchor="nw")
    
        # Wire up scrolling
        self.nav_canvas.configure(yscrollcommand=nav_scrollbar.set)
        self.nav_canvas.pack(side='left', fill='both', expand=True)
        nav_scrollbar.pack(side='right', fill='y')
    
        # Keep navigation width in sync with canvas width
        def _on_nav_canvas_configure(event):
            self.nav_canvas.itemconfig(self.nav_window, width=event.width)
        self.nav_canvas.bind("<Configure>", _on_nav_canvas_configure)
    
        # Bind mouse wheel scrolling for navigation
        self._bind_nav_scroll_events()
    
        # Content frame where different tabs will be shown
        self.content_frame = tk.Frame(self.main_container, bg='white')
        self.content_frame.pack(side='right', fill='both', expand=True)
    
        # Track current tab and tab frames
        self.current_tab = None
        self.tab_frames = {}
        
        # Create navigation buttons and tab frames
        self.setup_navigation()
    
        # Create all tab content
        self.create_dashboard_tab()
        self.create_core_finance_tab()
        self.create_payments_tab()
        self.create_payment_plans_tab()
        self.create_fees_tab()
        self.create_late_fees_tab()
        self.create_students_tab()
        self.create_currency_tab()
        self.create_analytics_tab()
        # self.create_scholarships_tab()  # Removed - integrated into Financial Aid tab
        self.create_reports_tab()
        self.create_revenue_source_tab()
        self.create_collections_tab()
        self.create_aid_tab()
        self.create_budget_tab()
        self.create_forecasting_tab()
        self.create_research_grants_tab()
        self.create_admin_tab()
        self.create_settings_tab()
    
        # Show default tab
        self.show_tab('dashboard')
        
        # Status bar
        self.create_status_bar()
        

    def setup_navigation(self):
        """Setup navigation buttons for different sections with role-based access"""
        is_admin = self.gui.is_admin()
        is_staff = self.gui.is_staff()
        is_student = self.gui.is_student()

        # Define all navigation buttons
        all_nav_buttons = [
            (_("finance_gui.nav.dashboard"), "dashboard", "all"),  # Available to all
            (_("finance_gui.nav.my_finances"), "my_finances", "student"),  # Students only - view own finances
            (_("finance_gui.nav.core_finance"), "core_finance", "admin_staff"),  # Admin and Staff only
            (_("finance_gui.nav.payments"), "payments", "all"),  # All can view payments
            (_("finance_gui.nav.fees"), "fees", "all"),  # All can view fees
            (_("finance_gui.nav.students"), "students", "admin_staff"),  # Admin and Staff only
            (_("finance_gui.nav.reports"), "reports", "admin_staff"),  # Admin and Staff only
            (_("finance_gui.nav.revenue_source"), "revenue_source", "admin_staff"),  # Admin and Staff only
            (_("finance_gui.nav.collections"), "collections", "admin_staff"),  # Admin and Staff only
            (_("finance_gui.nav.aid"), "aid", "all"),  # All can view aid (students view their own)
            (_("finance_gui.nav.budget"), "budget", "admin"),  # Admin only
            (_("finance_gui.nav.forecasting"), "forecasting", "admin"),  # Admin only
            (_("finance_gui.nav.research_grants"), "research_grants", "admin_staff"),  # Admin and Staff only
            (_("finance_gui.nav.admin"), "admin", "admin"),  # Admin only
            (_("finance_gui.nav.settings"), "settings", "admin_staff")  # Admin and Staff only
        ]

        # Filter buttons based on role
        nav_buttons = []
        for text, tab_id, access_level in all_nav_buttons:
            if access_level == "all":
                nav_buttons.append((text, tab_id))
            elif access_level == "admin" and is_admin:
                nav_buttons.append((text, tab_id))
            elif access_level == "admin_staff" and (is_admin or is_staff):
                nav_buttons.append((text, tab_id))
            elif access_level == "student" and is_student:
                nav_buttons.append((text, tab_id))

        # Create buttons
        for text, tab_id in nav_buttons:
            btn = tk.Button(
                self.nav_frame,
                text=text,
                command=lambda t=tab_id: self.show_tab(t),
                bg=self.colors['secondary'],
                fg='white',
                font=('Arial', 10, 'bold'),
                relief='flat',
                padx=10,
                pady=8
            )
            btn.pack(side='top', padx=5, pady=2, fill='x')

        # Add separator
        separator = tk.Frame(self.nav_frame, height=2, bg=self.colors['dark'])
        separator.pack(side='top', fill='x', padx=5, pady=10)

        # Force scroll region update after all content is added
        self.nav_frame.update_idletasks()
        self.nav_canvas.configure(scrollregion=self.nav_canvas.bbox("all"))
    
        # Ensure canvas shows scrollbar when needed
        self.nav_canvas.update_idletasks()
    

    def _bind_nav_scroll_events(self):
        """Bind mouse wheel and keys to navigation scrolling"""
        def _on_mousewheel(event):
            # Only scroll if bar is visible (i.e., content taller than viewport)
            if hasattr(self, 'nav_canvas') and self.nav_canvas.winfo_exists():
                try:
                    scrollbar = None
                    for child in self.nav_canvas.master.winfo_children():
                        if isinstance(child, ttk.Scrollbar):
                            scrollbar = child
                            break
                    if scrollbar and scrollbar.winfo_viewable():
                        if event.delta:  # Windows
                            self.nav_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                        else:            # Linux
                            if event.num == 4:
                                self.nav_canvas.yview_scroll(-1, "units")
                            elif event.num == 5:
                                self.nav_canvas.yview_scroll(1, "units")
                except Exception as e:
                    # Scroll event failed, silently ignore
                    print(f"Debug: Mousewheel scroll failed: {e}")
    
        def _on_keypress(event):
            if hasattr(self, 'nav_canvas') and self.nav_canvas.winfo_exists():
                try:
                    scrollbar = None
                    for child in self.nav_canvas.master.winfo_children():
                        if isinstance(child, ttk.Scrollbar):
                            scrollbar = child
                            break
                    if scrollbar and scrollbar.winfo_viewable():
                        if event.keysym == 'Up':
                            self.nav_canvas.yview_scroll(-1, "units")
                        elif event.keysym == 'Down':
                            self.nav_canvas.yview_scroll(1, "units")
                        elif event.keysym == 'Page_Up':
                            self.nav_canvas.yview_scroll(-10, "units")
                        elif event.keysym == 'Page_Down':
                            self.nav_canvas.yview_scroll(10, "units")
                except Exception as e:
                    # Key scroll event failed, silently ignore
                    print(f"Debug: Keypress scroll failed: {e}")
    
        # Bind to navigation canvas
        try:
            self.nav_canvas.bind("<MouseWheel>", _on_mousewheel)  # Windows
            self.nav_canvas.bind("<Button-4>", _on_mousewheel)    # Linux
            self.nav_canvas.bind("<Button-5>", _on_mousewheel)    # Linux
            self.nav_canvas.bind("<KeyPress>", _on_keypress)
            self.nav_canvas.focus_set()
        except Exception as e:
            # Event binding failed, navigation canvas may not be ready
            print(f"Debug: Canvas event binding failed: {e}")
    

    # Tab creation methods - stub implementations
    def _create_placeholder_tab(self, tab_id, title):
        """Create a placeholder tab with basic structure when main tab creation fails"""
        frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames[tab_id] = frame

        # Add title
        title_label = tk.Label(frame, text=title, font=('Arial', 18, 'bold'), bg='white')
        title_label.pack(pady=20)

        # Add informative message
        msg_frame = tk.Frame(frame, bg='white')
        msg_frame.pack(pady=20, padx=40)

        tk.Label(msg_frame, text=_("finance_gui.placeholder.loading_issue"),
                font=('Arial', 14, 'bold'), bg='white', fg='#e74c3c').pack(pady=5)

        tk.Label(msg_frame, text=_("finance_gui.placeholder.not_initialized"),
                font=('Arial', 11), bg='white', fg='gray').pack(pady=2)

        tk.Label(msg_frame, text=_("finance_gui.placeholder.may_be_due_to"),
                font=('Arial', 10), bg='white', fg='gray').pack(anchor='w', pady=(10, 2))

        reasons = [
            _("finance_gui.placeholder.reason_missing_tables"),
            _("finance_gui.placeholder.reason_module_not_loaded"),
            _("finance_gui.placeholder.reason_init_error")
        ]
        for reason in reasons:
            tk.Label(msg_frame, text=reason, font=('Arial', 10), bg='white', fg='gray').pack(anchor='w')

        # Retry button
        def retry_tab():
            try:
                method_name = f"create_{tab_id}_tab"
                if hasattr(self, method_name):
                    getattr(self, method_name)()
                    self.show_tab(tab_id)
            except Exception as e:
                messagebox.showerror(_("common.error"), _("finance_gui.placeholder.retry_failed", error=str(e)))

        tk.Button(msg_frame, text=_("finance_gui.placeholder.retry_loading"), command=retry_tab,
                 bg=self.colors.get('primary', '#3498db'), fg='white',
                 font=('Arial', 10), padx=15, pady=5).pack(pady=20)

    def create_dashboard_tab(self):
        """Create dashboard tab"""
        try:
            # Try to delegate to dashboard manager if it has the method
            if hasattr(self.gui, 'dashboard') and hasattr(self.gui.dashboard, 'create_dashboard_tab'):
                self.gui.dashboard.create_dashboard_tab()
            else:
                self._create_placeholder_tab('dashboard', '📊 Dashboard')
        except Exception as e:
            print(f"Error creating dashboard tab: {e}")
            self._create_placeholder_tab('dashboard', '📊 Dashboard')

    def create_core_finance_tab(self):
        """Create core finance tab"""
        core_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['core_finance'] = core_frame

        # Title
        title_label = tk.Label(core_frame, text=_("finance_gui.tabs.core_finance.title"),
                               font=('Arial', 18, 'bold'), bg='white')
        title_label.pack(pady=10)

        # Toolbar
        toolbar = tk.Frame(core_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Button(toolbar, text=_("finance_gui.buttons.process_payment"), command=self._process_payment,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text="View All Refunds", command=self._view_all_refunds,
                 bg=self.colors['info'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.create_invoice"), command=self._create_invoice,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.manage_refunds"), command=self._manage_refunds,
                 bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.financial_summary"), command=self._show_financial_summary,
                 bg=self.colors['primary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)

        # Stats frame
        stats_frame = tk.LabelFrame(core_frame, text=_("finance_gui.labels.quick_statistics"), font=('Arial', 12, 'bold'), bg='white')
        stats_frame.pack(fill='x', padx=10, pady=10)

        # Create stat cards
        stats_container = tk.Frame(stats_frame, bg='white')
        stats_container.pack(fill='x', padx=10, pady=10)

        self._create_stat_card(stats_container, _("finance_gui.stats.total_revenue"), _("common.loading"), self.colors['success'], 0, 0)
        self._create_stat_card(stats_container, _("finance_gui.stats.pending_payments"), _("common.loading"), self.colors['warning'], 0, 1)
        self._create_stat_card(stats_container, _("finance_gui.stats.total_refunds"), _("common.loading"), self.colors['danger'], 0, 2)
        self._create_stat_card(stats_container, _("finance_gui.stats.active_students"), _("common.loading"), self.colors['secondary'], 0, 3)

        # Load initial data
        self.root.after(100, self._load_core_finance_stats)

    def _create_stat_card(self, parent, title, value, color, row, col):
        """Create a statistics card"""
        card = tk.Frame(parent, bg=color, relief='raised', bd=2)
        card.grid(row=row, column=col, padx=5, pady=5, sticky='ew')
        parent.grid_columnconfigure(col, weight=1)

        tk.Label(card, text=title, bg=color, fg='white', font=('Arial', 10, 'bold')).pack(pady=5)
        value_label = tk.Label(card, text=value, bg=color, fg='white', font=('Arial', 14, 'bold'))
        value_label.pack(pady=5)
        setattr(self, f"core_stat_{col}", value_label)

    def _load_core_finance_stats(self):
        """Load core finance statistics"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Total revenue from payments
            cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'completed'")
            total_revenue = cursor.fetchone()[0] or 0

            # Add club payments to total revenue
            try:
                cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM club_payments WHERE status = 'completed'")
                club_revenue = cursor.fetchone()[0] or 0
                total_revenue += club_revenue
            except Exception:
                pass  # Table may not exist

            # Add housing payments to total revenue
            try:
                cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM housing_payments WHERE status = 'completed'")
                housing_revenue = cursor.fetchone()[0] or 0
                total_revenue += housing_revenue
            except Exception:
                pass  # Table may not exist

            # Add butcher shop orders to total revenue
            try:
                cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM butcher_orders WHERE payment_status = 'paid'")
                butcher_revenue = cursor.fetchone()[0] or 0
                total_revenue += butcher_revenue
            except Exception:
                pass  # Table may not exist

            # Add gym payments to total revenue
            try:
                cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM gym_transactions WHERE transaction_type IN ('membership', 'membership_renewal', 'pt_session')")
                gym_revenue = cursor.fetchone()[0] or 0
                total_revenue += gym_revenue
            except Exception:
                pass  # Table may not exist

            # Add dentist payments to total revenue
            try:
                cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM dentist_transactions WHERE status = 'completed'")
                dentist_revenue = cursor.fetchone()[0] or 0
                total_revenue += dentist_revenue
            except Exception:
                pass  # Table may not exist

            # Pending payments
            cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
            pending = cursor.fetchone()[0]

            # Total refunds from finance_refunds table (includes all department refunds)
            try:
                cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM finance_refunds")
                refunds = cursor.fetchone()[0] or 0
            except:
                # Fallback to old method if finance_refunds doesn't exist
                cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE payment_method = 'refund'")
                general_refunds = cursor.fetchone()[0] or 0

                try:
                    cursor.execute("SELECT COALESCE(SUM(refund_amount), 0) FROM library_fine_payments WHERE refund_amount > 0")
                    library_refunds = cursor.fetchone()[0] or 0
                except:
                    library_refunds = 0

                refunds = general_refunds + library_refunds

            # Active students
            cursor.execute("SELECT COUNT(*) FROM students WHERE status = 'Active'")
            students = cursor.fetchone()[0]

            conn.close()

            # Update UI
            if hasattr(self, 'core_stat_0'):
                self.core_stat_0.config(text=f"£{total_revenue:,.2f}")
            if hasattr(self, 'core_stat_1'):
                self.core_stat_1.config(text=str(pending))
            if hasattr(self, 'core_stat_2'):
                self.core_stat_2.config(text=f"£{refunds:,.2f}")
            if hasattr(self, 'core_stat_3'):
                self.core_stat_3.config(text=str(students))
        except Exception as e:
            print(f"Error loading core finance stats: {e}")

    def _process_payment(self):
        """Process a payment"""
        try:
            # Call transaction manager's payment function if available
            if hasattr(self.gui, 'transactions') and hasattr(self.gui.transactions, 'gui_record_payment'):
                self.gui.transactions.gui_record_payment()
            else:
                messagebox.showinfo(_("finance_gui.buttons.process_payment"), _("finance_gui.messages.transaction_manager_unavailable"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("finance_gui.messages.failed_open_payment_dialog", error=str(e)))

    def _create_invoice(self):
        """Create an invoice"""
        try:
            # Call invoice manager if available (check both 'invoices' and 'invoice_manager')
            if hasattr(self.gui, 'invoices') and hasattr(self.gui.invoices, 'gui_generate_invoice'):
                self.gui.invoices.gui_generate_invoice()
            elif hasattr(self.gui, 'invoice_manager') and hasattr(self.gui.invoice_manager, 'gui_generate_invoice'):
                self.gui.invoice_manager.gui_generate_invoice()
            else:
                messagebox.showinfo(_("finance_gui.buttons.create_invoice"), _("finance_gui.messages.invoice_manager_unavailable"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("finance_gui.messages.failed_open_invoice_dialog", error=str(e)))

    def _manage_refunds(self):
        """Manage refunds"""
        try:
            # Call transaction manager's refund function if available
            if hasattr(self.gui, 'transactions') and hasattr(self.gui.transactions, 'gui_process_refund'):
                self.gui.transactions.gui_process_refund()
            else:
                messagebox.showinfo(_("finance_gui.buttons.manage_refunds"), _("finance_gui.messages.transaction_manager_unavailable"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("finance_gui.messages.failed_open_refunds_dialog", error=str(e)))

    def _view_all_refunds(self):
        """View all refunds in a table"""
        try:
            from university_system.infrastructure.database.db import get_connection

            # Create refunds window
            refunds_window = tk.Toplevel(self.root)
            refunds_window.title("All Refunds - Database Records")
            refunds_window.geometry("1200x700")
            refunds_window.transient(self.root)

            # Header
            header_frame = ttk.Frame(refunds_window)
            header_frame.pack(fill='x', padx=10, pady=10)

            ttk.Label(header_frame, text="All Refunds", font=('Arial', 16, 'bold')).pack(side='left')

            # Refresh button
            ttk.Button(header_frame, text="Refresh",
                      command=lambda: self._refresh_refunds_table(refunds_tree)).pack(side='right', padx=5)

            # Export button
            ttk.Button(header_frame, text="Export to CSV",
                      command=lambda: self._export_refunds_to_csv(refunds_tree)).pack(side='right', padx=5)

            # Search frame
            search_frame = ttk.Frame(refunds_window)
            search_frame.pack(fill='x', padx=10, pady=5)

            ttk.Label(search_frame, text="Search:").pack(side='left', padx=5)
            search_var = tk.StringVar()
            search_entry = ttk.Entry(search_frame, textvariable=search_var, width=40)
            search_entry.pack(side='left', padx=5)

            def search_refunds(*args):
                search_term = search_var.get().lower()
                self._load_refunds_to_table(refunds_tree, search_term)

            search_var.trace('w', search_refunds)
            ttk.Button(search_frame, text="Clear",
                      command=lambda: search_var.set("")).pack(side='left', padx=5)

            # Table frame with scrollbars
            table_frame = ttk.Frame(refunds_window)
            table_frame.pack(fill='both', expand=True, padx=10, pady=10)

            # Create Treeview
            columns = ('ID', 'Reference', 'Department', 'Amount', 'Method', 'Date', 'Time',
                      'Transaction ID', 'Processed By', 'Notes')
            refunds_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=25)

            # Configure columns
            refunds_tree.heading('ID', text='ID')
            refunds_tree.heading('Reference', text='Refund Reference')
            refunds_tree.heading('Department', text='Department')
            refunds_tree.heading('Amount', text='Amount')
            refunds_tree.heading('Method', text='Method')
            refunds_tree.heading('Date', text='Date')
            refunds_tree.heading('Time', text='Time')
            refunds_tree.heading('Transaction ID', text='Transaction ID')
            refunds_tree.heading('Processed By', text='Processed By')
            refunds_tree.heading('Notes', text='Notes')

            # Set column widths
            refunds_tree.column('ID', width=50, anchor='center')
            refunds_tree.column('Reference', width=180, anchor='w')
            refunds_tree.column('Department', width=120, anchor='w')
            refunds_tree.column('Amount', width=100, anchor='e')
            refunds_tree.column('Method', width=120, anchor='w')
            refunds_tree.column('Date', width=100, anchor='center')
            refunds_tree.column('Time', width=80, anchor='center')
            refunds_tree.column('Transaction ID', width=150, anchor='w')
            refunds_tree.column('Processed By', width=120, anchor='w')
            refunds_tree.column('Notes', width=200, anchor='w')

            # Add scrollbars
            vsb = ttk.Scrollbar(table_frame, orient="vertical", command=refunds_tree.yview)
            hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=refunds_tree.xview)
            refunds_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

            # Pack elements
            refunds_tree.grid(row=0, column=0, sticky='nsew')
            vsb.grid(row=0, column=1, sticky='ns')
            hsb.grid(row=1, column=0, sticky='ew')

            table_frame.grid_rowconfigure(0, weight=1)
            table_frame.grid_columnconfigure(0, weight=1)

            # Summary frame
            summary_frame = ttk.Frame(refunds_window)
            summary_frame.pack(fill='x', padx=10, pady=5)

            self.summary_label = ttk.Label(summary_frame, text="Loading...", font=('Arial', 10, 'bold'))
            self.summary_label.pack()

            # Load data
            self._load_refunds_to_table(refunds_tree)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open refunds view: {e}")
            import traceback
            traceback.print_exc()

    def _load_refunds_to_table(self, tree, search_term=None):
        """Load refunds data into the table"""
        try:
            from university_system.infrastructure.database.db import get_connection

            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()

            # Check if table exists and has correct columns
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='finance_refunds'")
            if not cursor.fetchone():
                tree.insert('', 'end', values=('No Data', 'finance_refunds table does not exist', '', '', '', '', '', '', '', ''))
                conn.close()
                return

            # Check columns
            cursor.execute("PRAGMA table_info(finance_refunds)")
            columns = [col[1] for col in cursor.fetchall()]
            has_refund_time = 'refund_time' in columns

            # Build query
            if search_term:
                if has_refund_time:
                    cursor.execute('''
                        SELECT id, refund_reference, department, amount, refund_method,
                               refund_date, refund_time, transaction_id, processed_by, notes
                        FROM finance_refunds
                        WHERE LOWER(refund_reference) LIKE ?
                           OR LOWER(department) LIKE ?
                           OR LOWER(transaction_id) LIKE ?
                           OR LOWER(processed_by) LIKE ?
                           OR LOWER(notes) LIKE ?
                        ORDER BY id DESC
                    ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%',
                          f'%{search_term}%', f'%{search_term}%'))
                else:
                    cursor.execute('''
                        SELECT id, refund_reference, department, amount, refund_method,
                               refund_date, '' as refund_time, transaction_id, processed_by, notes
                        FROM finance_refunds
                        WHERE LOWER(refund_reference) LIKE ?
                           OR LOWER(department) LIKE ?
                           OR LOWER(transaction_id) LIKE ?
                           OR LOWER(processed_by) LIKE ?
                           OR LOWER(notes) LIKE ?
                        ORDER BY id DESC
                    ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%',
                          f'%{search_term}%', f'%{search_term}%'))
            else:
                if has_refund_time:
                    cursor.execute('''
                        SELECT id, refund_reference, department, amount, refund_method,
                               refund_date, refund_time, transaction_id, processed_by, notes
                        FROM finance_refunds
                        ORDER BY id DESC
                    ''')
                else:
                    cursor.execute('''
                        SELECT id, refund_reference, department, amount, refund_method,
                               refund_date, '' as refund_time, transaction_id, processed_by, notes
                        FROM finance_refunds
                        ORDER BY id DESC
                    ''')

            refunds = cursor.fetchall()

            # Calculate totals
            total_count = len(refunds)
            total_amount = 0.0

            # Insert data
            for refund in refunds:
                refund_id, ref, dept, amount, method, date, time, trans_id, processed_by, notes = refund

                # Format amount
                amount_val = float(amount) if amount else 0.0
                total_amount += amount_val
                amount_str = f"£{amount_val:.2f}"

                # Color code based on method
                tag = 'student_account' if method == 'Student Account' else 'normal'

                tree.insert('', 'end', values=(
                    refund_id or '',
                    ref or '',
                    dept or '',
                    amount_str,
                    method or '',
                    date or '',
                    time or '',
                    trans_id or '',
                    processed_by or '',
                    notes or ''
                ), tags=(tag,))

            # Configure tags
            tree.tag_configure('student_account', background='#e3f2fd')
            tree.tag_configure('normal', background='white')

            # Update summary
            if hasattr(self, 'summary_label'):
                summary_text = f"Total Refunds: {total_count} | Total Amount: £{total_amount:,.2f}"
                self.summary_label.config(text=summary_text)

            conn.close()

        except Exception as e:
            tree.insert('', 'end', values=('Error', str(e), '', '', '', '', '', '', '', ''))
            print(f"Error loading refunds: {e}")
            import traceback
            traceback.print_exc()

    def _refresh_refunds_table(self, tree):
        """Refresh the refunds table"""
        self._load_refunds_to_table(tree)
        messagebox.showinfo("Success", "Refunds list refreshed successfully")

    def _export_refunds_to_csv(self, tree):
        """Export refunds to CSV file"""
        try:
            import csv
            from tkinter import filedialog

            # Ask for save location
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile="refunds_export.csv"
            )

            if not filename:
                return

            # Write to CSV
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Write headers
                writer.writerow(['ID', 'Reference', 'Department', 'Amount', 'Method', 'Date', 'Time',
                               'Transaction ID', 'Processed By', 'Notes'])

                # Write data
                for item in tree.get_children():
                    values = tree.item(item)['values']
                    writer.writerow(values)

            messagebox.showinfo("Success", f"Refunds exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")

    def _show_financial_summary(self):
        """Show financial summary"""
        try:
            # Call dashboard or report manager if available
            if hasattr(self.gui, 'dashboard') and hasattr(self.gui.dashboard, 'gui_generate_financial_dashboard'):
                self.gui.dashboard.gui_generate_financial_dashboard()
            elif hasattr(self.gui, 'report_manager') and hasattr(self.gui.report_manager, 'gui_revenue_summary_report'):
                self.gui.report_manager.gui_revenue_summary_report()
            else:
                # Generate a simple financial summary
                self._generate_simple_financial_summary()
        except Exception as e:
            messagebox.showerror(_("common.error"), _("finance_gui.messages.failed_open_financial_summary", error=str(e)))

    def _generate_simple_financial_summary(self):
        """Generate a simple financial summary when dashboard not available"""
        try:
            from tkinter.scrolledtext import ScrolledText

            # Create summary window
            summary_window = tk.Toplevel(self.root)
            summary_window.title(_("finance_gui.reports.financial_summary"))
            summary_window.geometry("800x600")
            summary_window.transient(self.root)
            summary_window.grab_set()

            # Title
            title_label = tk.Label(summary_window, text=_("finance_gui.reports.financial_summary_report"),
                                  font=('Arial', 16, 'bold'), bg=self.colors['primary'], fg='white', pady=10)
            title_label.pack(fill='x')

            # Summary text area
            summary_text = ScrolledText(summary_window, font=('Courier', 10), wrap='word')
            summary_text.pack(fill='both', expand=True, padx=10, pady=10)

            # Generate summary data
            from university_system.infrastructure.database.db import get_connection

            conn = get_connection()
            cursor = conn.cursor()

            summary = "FINANCIAL SUMMARY REPORT\n"
            summary += "=" * 70 + "\n"
            summary += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

            # Total revenue
            try:
                cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'completed'")
                total_revenue = cursor.fetchone()[0] or 0

                # Add club payments to total revenue
                try:
                    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM club_payments WHERE status = 'completed'")
                    club_revenue = cursor.fetchone()[0] or 0
                    total_revenue += club_revenue
                except Exception:
                    pass

                # Add housing payments to total revenue
                try:
                    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM housing_payments WHERE status = 'completed'")
                    housing_revenue = cursor.fetchone()[0] or 0
                    total_revenue += housing_revenue
                except Exception:
                    pass

                summary += f"Total Revenue (All Sources): £{total_revenue:,.2f}\n"
            except Exception:
                summary += "Total Revenue: Data not available\n"

            # Outstanding fees
            try:
                cursor.execute('''
                    SELECT SUM(sf.amount - COALESCE(pa.total_paid, 0))
                    FROM student_fees sf
                    LEFT JOIN (
                        SELECT student_fee_id, SUM(amount) as total_paid
                        FROM payment_allocations
                        GROUP BY student_fee_id
                    ) pa ON sf.student_fee_id = pa.student_fee_id
                    WHERE sf.status != 'paid'
                ''')
                outstanding = cursor.fetchone()[0] or 0

                # Add library fines to outstanding amount
                try:
                    cursor.execute('''
                        SELECT COALESCE(SUM(fine_amount), 0)
                        FROM book_loans
                        WHERE fine_amount > 0 AND (status = 'active' OR status = 'overdue')
                    ''')
                    library_fines = cursor.fetchone()[0] or 0
                    outstanding += library_fines
                except Exception:
                    pass  # Table may not exist

                # Add late fees to outstanding amount
                try:
                    cursor.execute('''
                        SELECT COALESCE(SUM(late_fee_amount), 0)
                        FROM late_fees
                        WHERE waived = 0
                    ''')
                    late_fees = cursor.fetchone()[0] or 0
                    outstanding += late_fees
                except Exception:
                    pass  # Table may not exist

                summary += f"Total Outstanding Fees: £{outstanding:,.2f}\n"
            except Exception:
                summary += "Total Outstanding Fees: Data not available\n"

            # Student count
            try:
                cursor.execute("SELECT COUNT(*) FROM students WHERE status = 'Active'")
                active_students = cursor.fetchone()[0]
                summary += f"Active Students: {active_students}\n"
            except Exception:
                summary += "Active Students: Data not available\n"

            # Payment count
            try:
                cursor.execute("SELECT COUNT(*) FROM payments WHERE payment_date >= date('now', '-30 days')")
                recent_payments = cursor.fetchone()[0]
                summary += f"Payments (Last 30 Days): {recent_payments}\n"
            except Exception:
                summary += "Payments (Last 30 Days): Data not available\n"

            # Refund requests
            try:
                cursor.execute("SELECT COUNT(*) FROM refunds WHERE status = 'pending'")
                pending_refunds = cursor.fetchone()[0]
                summary += f"Pending Refund Requests: {pending_refunds}\n"
            except Exception:
                summary += "Pending Refund Requests: Data not available\n"

            summary += "\n" + "=" * 70 + "\n"
            summary += "BUDGET SUMMARY\n"
            summary += "=" * 70 + "\n\n"

            # Budget information
            try:
                cursor.execute('''
                    SELECT COUNT(*) as plans,
                           SUM(total_revenue_budget) as revenue_budget,
                           SUM(total_expense_budget) as expense_budget
                    FROM budget_plans
                    WHERE status IN ('active', 'approved')
                ''')
                budget = cursor.fetchone()
                if budget and budget[0]:
                    revenue_budget = budget[1] or 0
                    expense_budget = budget[2] or 0
                    net_budget = revenue_budget - expense_budget
                    summary += f"Active Budget Plans: {budget[0]}\n"
                    summary += f"Total Revenue Budget: £{revenue_budget:,.2f}\n"
                    summary += f"Total Expense Budget: £{expense_budget:,.2f}\n"
                    summary += f"Net Budget: £{net_budget:,.2f}\n"
                else:
                    summary += "No active budget plans\n"
            except Exception:
                summary += "Budget data: Not available\n"

            summary += "\n" + "=" * 70 + "\n"
            summary += "FINANCIAL AID SUMMARY\n"
            summary += "=" * 70 + "\n\n"

            # Financial aid
            try:
                cursor.execute("SELECT COUNT(*) FROM financial_aid WHERE status = 'active'")
                active_aid = cursor.fetchone()[0]
                cursor.execute("SELECT SUM(amount) FROM financial_aid WHERE status = 'active'")
                total_aid = cursor.fetchone()[0] or 0
                summary += f"Active Financial Aid Awards: {active_aid}\n"
                summary += f"Total Financial Aid Amount: £{total_aid:,.2f}\n"
            except Exception:
                summary += "Financial aid data: Not available\n"

            summary += "\n" + "=" * 70 + "\n"
            summary += "COLLECTION SUMMARY\n"
            summary += "=" * 70 + "\n\n"

            # Collection cases
            try:
                cursor.execute("SELECT COUNT(*) FROM collection_cases WHERE status = 'active'")
                active_cases = cursor.fetchone()[0]
                cursor.execute("SELECT SUM(outstanding_amount) FROM collection_cases WHERE status = 'active'")
                outstanding_collection = cursor.fetchone()[0] or 0
                summary += f"Active Collection Cases: {active_cases}\n"
                summary += f"Total Outstanding in Collections: £{outstanding_collection:,.2f}\n"
            except Exception:
                summary += "Collection data: Not available\n"

            summary += "\n" + "=" * 70 + "\n\n"
            summary += "For detailed financial analysis, charts, and reports,\n"
            summary += "please use the Analytics tab or Advanced Reporting GUI.\n"

            conn.close()

            # Display summary
            summary_text.insert('1.0', summary)
            summary_text.config(state='disabled')

            # Close button
            close_btn = ttk.Button(summary_window, text="Close", command=summary_window.destroy)
            close_btn.pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate financial summary: {e}")

    def create_payments_tab(self):
        """Create payments tab"""
        try:
            if hasattr(self.gui, 'transactions') and hasattr(self.gui.transactions, 'create_payments_tab'):
                self.gui.transactions.create_payments_tab()
            else:
                self._create_placeholder_tab('payments', '💳 Payments')
        except Exception as e:
            print(f"Error creating payments tab: {e}")
            self._create_placeholder_tab('payments', '💳 Payments')

    def create_payment_plans_tab(self):
        """Create payment plans tab"""
        plans_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['payment_plans'] = plans_frame

        # Title
        title_label = tk.Label(plans_frame, text=_("finance_gui.tabs.payment_plans.title"),
                               font=('Arial', 18, 'bold'), bg='white')
        title_label.pack(pady=10)

        # Toolbar
        toolbar = tk.Frame(plans_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Button(toolbar, text=_("finance_gui.payment_plans.create_plan"), command=self._create_payment_plan,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.payment_plans.edit_plan"), command=self._edit_payment_plan,
                 bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.payment_plans.delete_plan"), command=self._delete_payment_plan,
                 bg=self.colors['danger'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.refresh"), command=self._refresh_payment_plans,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='right', padx=5)

        # Plans table
        table_frame = tk.Frame(plans_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ('plan_id', 'student_id', 'total_amount', 'installments', 'frequency', 'status', 'start_date')
        self.payment_plans_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.payment_plans_tree.heading(col, text=col.replace('_', ' ').title())
            self.payment_plans_tree.column(col, width=120)

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.payment_plans_tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.payment_plans_tree.xview)
        self.payment_plans_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.payment_plans_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Load data
        self.root.after(100, self._refresh_payment_plans)

    def _create_payment_plan(self):
        """Create new payment plan"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.dialogs.create_payment_plan"))
        dialog.geometry("500x400")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.dialogs.create_payment_plan"), font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        tk.Label(form_frame, text=_("finance_gui.labels.student_id") + ":").grid(row=0, column=0, sticky='w', pady=5)
        student_id_entry = tk.Entry(form_frame, width=30)
        student_id_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.total_amount") + ":").grid(row=1, column=0, sticky='w', pady=5)
        amount_entry = tk.Entry(form_frame, width=30)
        amount_entry.grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.num_installments") + ":").grid(row=2, column=0, sticky='w', pady=5)
        installments_entry = tk.Entry(form_frame, width=30)
        installments_entry.grid(row=2, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.frequency") + ":").grid(row=3, column=0, sticky='w', pady=5)
        frequency_var = tk.StringVar(value="monthly")
        frequency_combo = ttk.Combobox(form_frame, textvariable=frequency_var,
                                      values=['weekly', 'biweekly', 'monthly', 'quarterly'],
                                      state='readonly', width=27)
        frequency_combo.grid(row=3, column=1, pady=5)

        def save_plan():
            try:
                student_id = student_id_entry.get()
                total_amount = float(amount_entry.get())
                installments = int(installments_entry.get())
                frequency = frequency_var.get()

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO student_payment_plans
                    (student_id, total_amount, installments, frequency, status, start_date, created_at)
                    VALUES (?, ?, ?, ?, 'active', date('now'), datetime('now'))
                ''', (student_id, total_amount, installments, frequency))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"), _("finance_gui.messages.payment_plan_created"))
                dialog.destroy()
                self._refresh_payment_plans()
            except Exception as e:
                messagebox.showerror(_("common.error"), _("finance_gui.messages.failed_create_payment_plan", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.buttons.save"), command=save_plan, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _edit_payment_plan(self):
        """Edit selected payment plan"""
        selection = self.payment_plans_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.messages.select_payment_plan_edit"))
            return
        messagebox.showinfo(_("finance_gui.dialogs.edit_plan"), _("finance_gui.messages.edit_functionality_placeholder"))

    def _delete_payment_plan(self):
        """Delete selected payment plan"""
        selection = self.payment_plans_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.messages.select_payment_plan_delete"))
            return

        if messagebox.askyesno(_("finance_gui.dialogs.confirm_delete"), _("finance_gui.messages.confirm_delete_payment_plan")):
            try:
                plan_id = self.payment_plans_tree.item(selection[0])['values'][0]
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM student_payment_plans WHERE id = ?", (plan_id,))
                conn.commit()
                conn.close()
                messagebox.showinfo(_("common.success"), _("finance_gui.messages.payment_plan_deleted"))
                self._refresh_payment_plans()
            except Exception as e:
                messagebox.showerror(_("common.error"), _("finance_gui.messages.failed_delete_payment_plan", error=str(e)))

    def _refresh_payment_plans(self):
        """Refresh payment plans list"""
        try:
            # Clear existing items
            for item in self.payment_plans_tree.get_children():
                self.payment_plans_tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT spp.payment_plan_id as plan_id, spp.student_id, spp.total_amount,
                       ppt.number_of_installments as installments,
                       ppt.installment_frequency as frequency,
                       spp.status, spp.start_date
                FROM student_payment_plans spp
                LEFT JOIN payment_plan_templates ppt ON spp.template_id = ppt.template_id
                ORDER BY spp.created_at DESC
            ''')

            for row in cursor.fetchall():
                self.payment_plans_tree.insert('', 'end', values=row)

            conn.close()
        except Exception as e:
            print(f"Error refreshing payment plans: {e}")

    def create_fees_tab(self):
        """Create fees management tab"""
        fees_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['fees'] = fees_frame

        # Title
        title_label = tk.Label(fees_frame, text=_("finance_gui.tabs.fees.title"),
                               font=('Arial', 18, 'bold'), bg='white')
        title_label.pack(pady=10)

        # Toolbar
        toolbar = tk.Frame(fees_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Button(toolbar, text=_("finance_gui.buttons.assign_fee"), command=self._assign_fee,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.record_payment"), command=self._record_fee_payment,
                 bg=self.colors['info'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.waive_fee"), command=self._waive_fee,
                 bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.refresh"), command=self._refresh_fees,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='right', padx=5)

        # Fees table
        table_frame = tk.Frame(fees_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ('student_fee_id', 'student_id', 'fee_type', 'amount', 'currency', 'status', 'due_date')
        self.fees_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.fees_tree.heading(col, text=col.replace('_', ' ').title())
            self.fees_tree.column(col, width=120)

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.fees_tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.fees_tree.xview)
        self.fees_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.fees_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Load data
        self.root.after(100, self._refresh_fees)

    def _assign_fee(self):
        """Assign a fee to a student"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.dialogs.assign_fee"))
        dialog.geometry("500x450")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.dialogs.assign_student_fee"), font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        tk.Label(form_frame, text=_("finance_gui.labels.student_id") + ":").grid(row=0, column=0, sticky='w', pady=5)
        student_id_entry = tk.Entry(form_frame, width=30)
        student_id_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.fee_type") + ":").grid(row=1, column=0, sticky='w', pady=5)
        fee_type_var = tk.StringVar()
        fee_type_combo = ttk.Combobox(form_frame, textvariable=fee_type_var, state='readonly', width=27)
        fee_type_combo.grid(row=1, column=1, pady=5)

        # Load fee types
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT fee_type_id, fee_name FROM fee_types WHERE is_late_fee = 0")
            fee_types = cursor.fetchall()
            conn.close()
            fee_type_combo['values'] = [f"{ft[0]} - {ft[1]}" for ft in fee_types]
        except Exception as e:
            print(f"Error loading fee types: {e}")

        tk.Label(form_frame, text=_("finance_gui.labels.amount") + ":").grid(row=2, column=0, sticky='w', pady=5)
        amount_entry = tk.Entry(form_frame, width=30)
        amount_entry.grid(row=2, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.currency") + ":").grid(row=3, column=0, sticky='w', pady=5)
        currency_var = tk.StringVar(value="GBP")
        currency_combo = ttk.Combobox(form_frame, textvariable=currency_var,
                                     values=['GBP', 'USD', 'EUR', 'CAD', 'AUD'],
                                     state='readonly', width=27)
        currency_combo.grid(row=3, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.due_date") + ":").grid(row=4, column=0, sticky='w', pady=5)
        due_date_entry = tk.Entry(form_frame, width=30)
        due_date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        due_date_entry.grid(row=4, column=1, pady=5)

        def save_fee():
            try:
                student_id = student_id_entry.get().strip()
                if not student_id:
                    messagebox.showerror(_("common.error"), _("finance_gui.messages.student_id_required"))
                    return

                fee_type_str = fee_type_var.get()
                if not fee_type_str:
                    messagebox.showerror(_("common.error"), _("finance_gui.messages.select_fee_type"))
                    return

                fee_type_id = int(fee_type_str.split(' - ')[0])
                amount = float(amount_entry.get())
                currency = currency_var.get()
                due_date = due_date_entry.get()

                conn = get_connection()
                cursor = conn.cursor()

                # Check if student exists
                cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (student_id,))
                if cursor.fetchone()[0] == 0:
                    conn.close()
                    messagebox.showerror(_("common.error"), _("finance_gui.messages.student_not_found", student_id=student_id))
                    return

                cursor.execute('''
                    INSERT INTO student_fees
                    (student_id, fee_type_id, amount, currency, status, due_date, created_at)
                    VALUES (?, ?, ?, ?, 'unpaid', ?, datetime('now'))
                ''', (student_id, fee_type_id, amount, currency, due_date))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"), _("finance_gui.messages.fee_assigned"))
                dialog.destroy()
                self._refresh_fees()
            except ValueError:
                messagebox.showerror(_("common.error"), _("finance_gui.messages.invalid_amount"))
            except Exception as e:
                messagebox.showerror(_("common.error"), _("finance_gui.messages.failed_assign_fee", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.buttons.save"), command=save_fee, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _record_fee_payment(self):
        """Record a payment for a selected fee"""
        selection = self.fees_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.messages.select_fee_payment"))
            return

        fee_values = self.fees_tree.item(selection[0])['values']
        fee_id = fee_values[0]
        student_id = fee_values[1]
        fee_name = fee_values[2]
        fee_amount = float(fee_values[3])

        # Create payment dialog
        payment_dialog = tk.Toplevel(self.root)
        payment_dialog.title(_("finance_gui.dialogs.record_payment_for_fee", fee_id=fee_id))
        payment_dialog.geometry("500x400")
        payment_dialog.transient(self.root)
        payment_dialog.grab_set()

        # Fee info frame
        info_frame = ttk.LabelFrame(payment_dialog, text=_("finance_gui.labels.fee_information"), padding=15)
        info_frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(info_frame, text=f"{_('finance_gui.labels.fee_id')}: {fee_id}", font=('Arial', 10)).pack(anchor='w')
        ttk.Label(info_frame, text=f"{_('finance_gui.labels.student_id')}: {student_id}", font=('Arial', 10)).pack(anchor='w')
        ttk.Label(info_frame, text=f"{_('finance_gui.labels.fee_name')}: {fee_name}", font=('Arial', 10)).pack(anchor='w')
        ttk.Label(info_frame, text=f"{_('finance_gui.labels.amount_due')}: £{fee_amount:.2f}", font=('Arial', 10, 'bold')).pack(anchor='w')

        # Payment details frame
        payment_frame = ttk.LabelFrame(payment_dialog, text=_("finance_gui.labels.payment_details"), padding=15)
        payment_frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(payment_frame, text=_("finance_gui.labels.payment_amount")).pack(anchor='w')
        amount_var = tk.StringVar(value=str(fee_amount))
        amount_entry = ttk.Entry(payment_frame, textvariable=amount_var, font=('Arial', 12))
        amount_entry.pack(fill='x', pady=(0, 10))

        ttk.Label(payment_frame, text=_("finance_gui.labels.payment_method")).pack(anchor='w')
        method_var = tk.StringVar(value="card")
        method_combo = ttk.Combobox(payment_frame, textvariable=method_var,
                                     values=["card", "cash", "bank_transfer", "cheque", "online"],
                                     state='readonly', font=('Arial', 12))
        method_combo.pack(fill='x', pady=(0, 10))

        ttk.Label(payment_frame, text=_("finance_gui.labels.notes_optional")).pack(anchor='w')
        notes_text = tk.Text(payment_frame, height=4, font=('Arial', 10))
        notes_text.pack(fill='x')

        def save_payment():
            try:
                payment_amount = float(amount_var.get())
                payment_method = method_var.get()
                notes = notes_text.get('1.0', tk.END).strip()

                if payment_amount <= 0:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.payment_amount_positive"))
                    return

                # Get authentication for audit trail
                from university_system.infrastructure.shared_context import get_auth
                auth = get_auth()
                username = 'system'
                if auth and hasattr(auth, 'is_logged_in') and auth.is_logged_in():
                    user = auth.get_current_user()
                    username = user.get('username', 'system') if user else 'system'

                # Save payment to database
                conn = get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                payment_date = datetime.now().strftime('%Y-%m-%d')

                # Insert payment record
                cursor.execute('''
                    INSERT INTO payments
                    (student_id, amount, payment_method, payment_date, status, notes, created_by, created_at)
                    VALUES (?, ?, ?, ?, 'completed', ?, ?, ?)
                ''', (student_id, payment_amount, payment_method, payment_date, notes, username, now))

                payment_id = cursor.lastrowid

                # Create payment allocation
                cursor.execute('''
                    INSERT INTO payment_allocations (payment_id, student_fee_id, amount, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (payment_id, fee_id, payment_amount, now))

                # Get current paid amount for this fee
                cursor.execute('''
                    SELECT COALESCE(SUM(amount), 0) FROM payment_allocations
                    WHERE student_fee_id = ?
                ''', (fee_id,))
                total_paid = cursor.fetchone()[0]

                # Update fee status
                if total_paid >= fee_amount:
                    new_status = 'paid'
                else:
                    new_status = 'partial'

                cursor.execute('''
                    UPDATE student_fees SET status = ?, updated_at = ?
                    WHERE student_fee_id = ?
                ''', (new_status, now, fee_id))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"),
                                  f"{_('finance_gui.messages.payment_recorded', amount=payment_amount)}\n"
                                  f"{_('finance_gui.labels.fee_status')}: {new_status.title()}")
                payment_dialog.destroy()
                self._refresh_fees()

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.invalid_payment_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_record_payment", error=str(e)))
                import traceback
                traceback.print_exc()

        # Buttons
        btn_frame = ttk.Frame(payment_dialog)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text=_("finance_gui.buttons.record_payment"), command=save_payment).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=payment_dialog.destroy).pack(side='left', padx=5)

    def _waive_fee(self):
        """Waive a selected fee"""
        selection = self.fees_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.messages.select_fee_waive"))
            return

        if messagebox.askyesno(_("finance_gui.dialogs.confirm_waive"), _("finance_gui.messages.confirm_waive_fee")):
            try:
                fee_id = self.fees_tree.item(selection[0])['values'][0]
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE student_fees SET status = 'waived' WHERE student_fee_id = ?", (fee_id,))
                conn.commit()
                conn.close()
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.messages.fee_waived"))
                self._refresh_fees()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_waive_fee", error=str(e)))

    def _refresh_fees(self):
        """Refresh fees list"""
        try:
            # Clear existing items
            for item in self.fees_tree.get_children():
                self.fees_tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sf.student_fee_id, sf.student_id, ft.fee_name, sf.amount,
                       sf.currency, sf.status, sf.due_date
                FROM student_fees sf
                LEFT JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                ORDER BY sf.created_at DESC
                LIMIT 500
            ''')

            for row in cursor.fetchall():
                self.fees_tree.insert('', 'end', values=row)

            conn.close()
        except Exception as e:
            print(f"Error refreshing fees: {e}")

    def create_late_fees_tab(self):
        """Create late fees management tab"""
        late_fees_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['late_fees'] = late_fees_frame

        # Title
        title_label = tk.Label(late_fees_frame, text=_("finance_gui.tabs.late_fees.title"),
                               font=('Arial', 18, 'bold'), bg='white')
        title_label.pack(pady=10)

        # Toolbar
        toolbar = tk.Frame(late_fees_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Button(toolbar, text=_("finance_gui.buttons.apply_late_fee"), command=self._apply_late_fee,
                 bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.waive_late_fee"), command=self._waive_late_fee,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.calculate_overdue"), command=self._calculate_overdue_fees,
                 bg=self.colors['danger'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.refresh"), command=self._refresh_late_fees,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='right', padx=5)

        # Late fees table
        table_frame = tk.Frame(late_fees_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ('late_fee_id', 'student_fee_id', 'amount', 'days_overdue', 'calculation_method',
                   'applied_date', 'waived', 'waiver_reason')
        self.late_fees_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.late_fees_tree.heading(col, text=col.replace('_', ' ').title())
            self.late_fees_tree.column(col, width=100)

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.late_fees_tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.late_fees_tree.xview)
        self.late_fees_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.late_fees_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Load data
        self.root.after(100, self._refresh_late_fees)

    def _apply_late_fee(self):
        """Apply a late fee to overdue student fee"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.dialogs.apply_late_fee"))
        dialog.geometry("500x400")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.dialogs.apply_late_fee"), font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        tk.Label(form_frame, text=_("finance_gui.labels.student_fee_id")).grid(row=0, column=0, sticky='w', pady=5)
        student_fee_id_entry = tk.Entry(form_frame, width=30)
        student_fee_id_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.late_fee_amount")).grid(row=1, column=0, sticky='w', pady=5)
        amount_entry = tk.Entry(form_frame, width=30)
        amount_entry.grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.calculation_method")).grid(row=2, column=0, sticky='w', pady=5)
        method_var = tk.StringVar(value="fixed")
        method_combo = ttk.Combobox(form_frame, textvariable=method_var,
                                    values=['fixed', 'percentage', 'daily'],
                                    state='readonly', width=27)
        method_combo.grid(row=2, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.days_overdue")).grid(row=3, column=0, sticky='w', pady=5)
        days_entry = tk.Entry(form_frame, width=30)
        days_entry.grid(row=3, column=1, pady=5)

        def save_late_fee():
            try:
                student_fee_id = int(student_fee_id_entry.get())
                amount = float(amount_entry.get())
                method = method_var.get()
                days_overdue = int(days_entry.get())

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO late_fees
                    (student_fee_id, late_fee_amount, calculation_method, days_overdue,
                     applied_date, waived, created_at)
                    VALUES (?, ?, ?, ?, date('now'), 0, datetime('now'))
                ''', (student_fee_id, amount, method, days_overdue))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.messages.late_fee_applied"))
                dialog.destroy()
                self._refresh_late_fees()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_apply_late_fee", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.buttons.save"), command=save_late_fee, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _waive_late_fee(self):
        """Waive a selected late fee"""
        selection = self.late_fees_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.messages.select_late_fee_waive"))
            return

        reason = simpledialog.askstring(_("finance_gui.dialogs.waive_late_fee"), _("finance_gui.messages.enter_waiver_reason"))
        if not reason:
            return

        try:
            late_fee_id = self.late_fees_tree.item(selection[0])['values'][0]
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE late_fees
                SET waived = 1, waiver_reason = ?, waived_date = date('now'), waived_by = ?
                WHERE late_fee_id = ?
            ''', (reason, auth.current_user.get('username', 'admin'), late_fee_id))
            conn.commit()
            conn.close()
            messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.messages.late_fee_waived"))
            self._refresh_late_fees()
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_waive_late_fee", error=str(e)))

    def _calculate_overdue_fees(self):
        """Calculate and apply late fees for all overdue student fees"""
        if not messagebox.askyesno(_("finance_gui.dialogs.confirm"), _("finance_gui.messages.confirm_calculate_overdue")):
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Find overdue fees without late fees
            cursor.execute('''
                SELECT sf.student_fee_id, sf.amount,
                       julianday('now') - julianday(sf.due_date) as days_overdue
                FROM student_fees sf
                WHERE sf.status = 'unpaid'
                AND sf.due_date < date('now')
                AND NOT EXISTS (
                    SELECT 1 FROM late_fees lf
                    WHERE lf.student_fee_id = sf.student_fee_id
                )
            ''')

            overdue_fees = cursor.fetchall()
            count = 0

            for fee_id, amount, days_overdue in overdue_fees:
                if days_overdue > 0:
                    # Apply 5% late fee
                    late_fee_amount = amount * 0.05
                    cursor.execute('''
                        INSERT INTO late_fees
                        (student_fee_id, late_fee_amount, calculation_method, days_overdue,
                         applied_date, waived, created_at)
                        VALUES (?, ?, 'percentage', ?, date('now'), 0, datetime('now'))
                    ''', (fee_id, late_fee_amount, int(days_overdue)))
                    count += 1

            conn.commit()
            conn.close()

            messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.messages.late_fees_applied_count", count=count))
            self._refresh_late_fees()
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_calculate_overdue", error=str(e)))

    def _refresh_late_fees(self):
        """Refresh late fees list"""
        try:
            # Clear existing items
            for item in self.late_fees_tree.get_children():
                self.late_fees_tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT late_fee_id, student_fee_id, late_fee_amount, days_overdue,
                       calculation_method, applied_date, waived, waiver_reason
                FROM late_fees
                ORDER BY applied_date DESC
                LIMIT 500
            ''')

            for row in cursor.fetchall():
                self.late_fees_tree.insert('', 'end', values=row)

            conn.close()
        except Exception as e:
            print(f"Error refreshing late fees: {e}")

    def create_students_tab(self):
        """Create students tab"""
        try:
            if hasattr(self.gui, 'create_students_tab'):
                self.gui.create_students_tab()
            else:
                self._create_placeholder_tab('students', '👤 Students')
        except Exception as e:
            print(f"Error creating students tab: {e}")
            self._create_placeholder_tab('students', '👤 Students')

    def create_currency_tab(self):
        """Create currency exchange rates management tab"""
        currency_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['currency'] = currency_frame

        # Title
        title_label = tk.Label(currency_frame, text=_("finance_gui.tabs.currency.title"),
                               font=('Arial', 18, 'bold'), bg='white')
        title_label.pack(pady=10)

        # Toolbar
        toolbar = tk.Frame(currency_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Button(toolbar, text=_("finance_gui.buttons.add_rate"), command=self._add_exchange_rate,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.edit_rate"), command=self._edit_exchange_rate,
                 bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.delete_rate"), command=self._delete_exchange_rate,
                 bg=self.colors['danger'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.refresh"), command=self._refresh_exchange_rates,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='right', padx=5)

        # Exchange rates table
        table_frame = tk.Frame(currency_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ('rate_id', 'from_currency', 'to_currency', 'exchange_rate', 'rate_date', 'source')
        self.exchange_rates_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.exchange_rates_tree.heading(col, text=col.replace('_', ' ').title())
            self.exchange_rates_tree.column(col, width=120)

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.exchange_rates_tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.exchange_rates_tree.xview)
        self.exchange_rates_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.exchange_rates_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Load data
        self.root.after(100, self._refresh_exchange_rates)

    def _add_exchange_rate(self):
        """Add a new exchange rate"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.dialogs.add_exchange_rate"))
        dialog.geometry("500x400")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.dialogs.add_exchange_rate"), font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        tk.Label(form_frame, text=_("finance_gui.labels.from_currency")).grid(row=0, column=0, sticky='w', pady=5)
        from_currency_var = tk.StringVar(value="GBP")
        from_currency_combo = ttk.Combobox(form_frame, textvariable=from_currency_var,
                                          values=['GBP', 'USD', 'EUR', 'CAD', 'AUD', 'JPY', 'CHF'],
                                          state='readonly', width=27)
        from_currency_combo.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.to_currency")).grid(row=1, column=0, sticky='w', pady=5)
        to_currency_var = tk.StringVar(value="USD")
        to_currency_combo = ttk.Combobox(form_frame, textvariable=to_currency_var,
                                        values=['GBP', 'USD', 'EUR', 'CAD', 'AUD', 'JPY', 'CHF'],
                                        state='readonly', width=27)
        to_currency_combo.grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.exchange_rate")).grid(row=2, column=0, sticky='w', pady=5)
        rate_entry = tk.Entry(form_frame, width=30)
        rate_entry.grid(row=2, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.source")).grid(row=3, column=0, sticky='w', pady=5)
        source_var = tk.StringVar(value="manual")
        source_combo = ttk.Combobox(form_frame, textvariable=source_var,
                                   values=['manual', 'api', 'bank'],
                                   state='readonly', width=27)
        source_combo.grid(row=3, column=1, pady=5)

        def save_rate():
            try:
                from_currency = from_currency_var.get()
                to_currency = to_currency_var.get()
                exchange_rate = float(rate_entry.get())
                source = source_var.get()

                if from_currency == to_currency:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.currencies_must_differ"))
                    return

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO exchange_rates
                    (from_currency, to_currency, exchange_rate, rate_date, source, created_at)
                    VALUES (?, ?, ?, date('now'), ?, datetime('now'))
                ''', (from_currency, to_currency, exchange_rate, source))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.messages.exchange_rate_added"))
                dialog.destroy()
                self._refresh_exchange_rates()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_add_exchange_rate", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.buttons.save"), command=save_rate, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _edit_exchange_rate(self):
        """Edit selected exchange rate"""
        selection = self.exchange_rates_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.messages.select_rate_edit"))
            return
        messagebox.showinfo(_("finance_gui.dialogs.edit_rate"), _("finance_gui.messages.edit_functionality_coming"))

    def _delete_exchange_rate(self):
        """Delete selected exchange rate"""
        selection = self.exchange_rates_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.messages.select_rate_delete"))
            return

        if messagebox.askyesno(_("finance_gui.dialogs.confirm_delete"), _("finance_gui.messages.confirm_delete_rate")):
            try:
                rate_id = self.exchange_rates_tree.item(selection[0])['values'][0]
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM exchange_rates WHERE rate_id = ?", (rate_id,))
                conn.commit()
                conn.close()
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.messages.exchange_rate_deleted"))
                self._refresh_exchange_rates()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_delete_exchange_rate", error=str(e)))

    def _refresh_exchange_rates(self):
        """Refresh exchange rates list"""
        try:
            # Clear existing items
            for item in self.exchange_rates_tree.get_children():
                self.exchange_rates_tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT rate_id, from_currency, to_currency, exchange_rate, rate_date, source
                FROM exchange_rates
                ORDER BY rate_date DESC, from_currency, to_currency
                LIMIT 500
            ''')

            for row in cursor.fetchall():
                self.exchange_rates_tree.insert('', 'end', values=row)

            conn.close()
        except Exception as e:
            print(f"Error refreshing exchange rates: {e}")

    def create_analytics_tab(self):
        """Create analytics tab"""
        try:
            if hasattr(self.gui, 'analytics') and hasattr(self.gui.analytics, 'create_analytics_tab'):
                self.gui.analytics.create_analytics_tab()
            else:
                self._create_placeholder_tab('analytics', '📊 Analytics')
        except Exception as e:
            print(f"Error creating analytics tab: {e}")
            self._create_placeholder_tab('analytics', '📊 Analytics')

    def create_scholarships_tab(self):
        """Create scholarships management tab - Redirects to Financial Aid GUI"""
        scholarships_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['scholarships'] = scholarships_frame

        # Title
        title_label = tk.Label(
            scholarships_frame,
            text=_("finance_gui.tabs.scholarships.title"),
            font=('Arial', 18, 'bold'),
            bg='white',
            fg=self.colors['primary']
        )
        title_label.pack(pady=20)

        # Description
        desc_label = tk.Label(
            scholarships_frame,
            text=_("finance_gui.tabs.scholarships.description"),
            font=('Arial', 11),
            bg='white',
            fg='#555',
            justify='center'
        )
        desc_label.pack(pady=(0, 30))

        # Launch button
        if FINANCIAL_AID_GUI_AVAILABLE and launch_financial_aid_gui:
            launch_btn = tk.Button(
                scholarships_frame,
                text=_("finance_gui.buttons.open_financial_aid"),
                command=lambda: launch_financial_aid_gui(self.root, self.gui.auth),
                font=('Arial', 12, 'bold'),
                bg=self.colors['success'],
                fg='white',
                padx=30,
                pady=15
            )
            launch_btn.pack(pady=10)
        else:
            error_label = tk.Label(
                scholarships_frame,
                text=_("finance_gui.messages.financial_aid_unavailable"),
                font=('Arial', 11),
                bg='white',
                fg=self.colors['danger']
            )
            error_label.pack(pady=10)

        # Info text
        info_text = ScrolledText(scholarships_frame, height=15, width=80, font=('Arial', 10), wrap='word')
        info_text.pack(padx=20, pady=20, fill='both', expand=True)

        info_content = _("finance_gui.scholarships_info.info_content")
        info_text.insert('1.0', info_content)
        info_text.config(state='disabled')

    def _create_scholarship(self):
        """Create a new scholarship"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.dialogs.create_scholarship"))
        dialog.geometry("500x500")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.dialogs.create_scholarship"), font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        tk.Label(form_frame, text=_("finance_gui.labels.scholarship_name")).grid(row=0, column=0, sticky='w', pady=5)
        name_entry = tk.Entry(form_frame, width=30)
        name_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.description")).grid(row=1, column=0, sticky='w', pady=5)
        description_entry = tk.Entry(form_frame, width=30)
        description_entry.grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.amount")).grid(row=2, column=0, sticky='w', pady=5)
        amount_entry = tk.Entry(form_frame, width=30)
        amount_entry.grid(row=2, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.academic_year")).grid(row=3, column=0, sticky='w', pady=5)
        year_entry = tk.Entry(form_frame, width=30)
        year_entry.insert(0, "2024-2025")
        year_entry.grid(row=3, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.criteria")).grid(row=4, column=0, sticky='w', pady=5)
        criteria_entry = tk.Entry(form_frame, width=30)
        criteria_entry.grid(row=4, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.deadline")).grid(row=5, column=0, sticky='w', pady=5)
        deadline_entry = tk.Entry(form_frame, width=30)
        deadline_entry.grid(row=5, column=1, pady=5)

        def save_scholarship():
            try:
                name = name_entry.get()
                description = description_entry.get()
                amount = float(amount_entry.get())
                academic_year = year_entry.get()
                criteria = criteria_entry.get()
                deadline = deadline_entry.get()

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO scholarships
                    (scholarship_name, description, amount, academic_year, criteria, deadline,
                     is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'))
                ''', (name, description, amount, academic_year, criteria, deadline))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.messages.scholarship_created"))
                dialog.destroy()
                self._refresh_scholarships()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_create_scholarship", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.buttons.save"), command=save_scholarship, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _award_scholarship(self):
        """Award scholarship to a student"""
        selection = self.scholarships_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.messages.select_scholarship_first"))
            return

        scholarship_id = self.scholarships_tree.item(selection[0])['values'][0]

        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.dialogs.award_scholarship"))
        dialog.geometry("400x250")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.dialogs.award_scholarship_to_student"), font=('Arial', 12, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10)

        tk.Label(form_frame, text=_("finance_gui.labels.student_id")).grid(row=0, column=0, sticky='w', pady=5)
        student_id_entry = tk.Entry(form_frame, width=30)
        student_id_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.award_amount")).grid(row=1, column=0, sticky='w', pady=5)
        amount_entry = tk.Entry(form_frame, width=30)
        amount_entry.grid(row=1, column=1, pady=5)

        def save_award():
            try:
                student_id = student_id_entry.get()
                amount = float(amount_entry.get())

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO student_scholarships
                    (student_id, scholarship_id, amount, status, awarded_date, created_at)
                    VALUES (?, ?, ?, 'active', date('now'), datetime('now'))
                ''', (student_id, scholarship_id, amount))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.messages.scholarship_awarded"))
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_award_scholarship", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.buttons.award"), command=save_award, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _deactivate_scholarship(self):
        """Deactivate selected scholarship"""
        selection = self.scholarships_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.messages.select_scholarship_deactivate"))
            return

        if messagebox.askyesno(_("finance_gui.dialogs.confirm"), _("finance_gui.messages.confirm_deactivate_scholarship")):
            try:
                scholarship_id = self.scholarships_tree.item(selection[0])['values'][0]
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE scholarships SET is_active = 0 WHERE scholarship_id = ?", (scholarship_id,))
                conn.commit()
                conn.close()
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.messages.scholarship_deactivated"))
                self._refresh_scholarships()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_deactivate_scholarship", error=str(e)))

    def _refresh_scholarships(self):
        """Refresh scholarships list"""
        try:
            # Clear existing items
            for item in self.scholarships_tree.get_children():
                self.scholarships_tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT scholarship_id, scholarship_name, amount, academic_year, deadline, is_active
                FROM scholarships
                ORDER BY created_at DESC
            ''')

            for row in cursor.fetchall():
                self.scholarships_tree.insert('', 'end', values=row)

            conn.close()
        except Exception as e:
            print(f"Error refreshing scholarships: {e}")

    def create_reports_tab(self):
        """Create reports tab - Redirects to Finance Reporting GUI"""
        reports_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['reports'] = reports_frame

        # Title
        title_label = tk.Label(
            reports_frame,
            text=_("finance_gui.reports_tab.title"),
            font=('Arial', 18, 'bold'),
            bg='white',
            fg=self.colors['primary']
        )
        title_label.pack(pady=20)

        # Description
        desc_label = tk.Label(
            reports_frame,
            text=_("finance_gui.tabs.reports.description"),
            font=('Arial', 11),
            bg='white',
            fg='#555'
        )
        desc_label.pack(pady=(0, 30))

        # Launch button
        launch_btn = tk.Button(
            reports_frame,
            text=_("finance_gui.reports_tab.open_reporting"),
            command=lambda: launch_financial_gui(self.root),
            font=('Arial', 12, 'bold'),
            bg=self.colors['success'],
            fg='white',
            padx=30,
            pady=15
        )
        launch_btn.pack(pady=10)

        # Info text
        info_text = ScrolledText(reports_frame, height=15, width=80, font=('Arial', 10), wrap='word')
        info_text.pack(padx=20, pady=20, fill='both', expand=True)

        info_content = _("finance_gui.reports_tab.info_content")
        info_text.insert('1.0', info_content)
        info_text.config(state='disabled')

    def create_revenue_source_tab(self):
        """Create revenue by source tab"""
        try:
            # Delegate to revenue source manager if available
            if hasattr(self.gui, 'revenue_source') and hasattr(self.gui.revenue_source, 'create_revenue_source_tab'):
                self.gui.revenue_source.create_revenue_source_tab()
            else:
                self._create_placeholder_tab('revenue_source', '💵 Revenue by Source')
        except Exception as e:
            print(f"Error creating revenue source tab: {e}")
            self._create_placeholder_tab('revenue_source', '💵 Revenue by Source')

    def create_collections_tab(self):
        """Create collections management tab"""
        collections_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['collections'] = collections_frame

        # Title
        title_label = tk.Label(collections_frame, text=_("finance_gui.collections_tab.title"),
                               font=('Arial', 18, 'bold'), bg='white')
        title_label.pack(pady=10)

        # Toolbar
        toolbar = tk.Frame(collections_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Button(toolbar, text=_("finance_gui.collections_tab.create_case"), command=self._create_collection_case,
                 bg=self.colors['danger'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.collections_tab.send_notice"), command=self._send_collection_notice,
                 bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.collections_tab.resolve_case"), command=self._resolve_collection_case,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.refresh"), command=self._refresh_collections,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='right', padx=5)

        # Collections table
        table_frame = tk.Frame(collections_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ('case_id', 'student_id', 'total_debt', 'case_status', 'assigned_date',
                   'amount_collected', 'resolution_date')
        self.collections_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.collections_tree.heading(col, text=col.replace('_', ' ').title())
            self.collections_tree.column(col, width=120)

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.collections_tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.collections_tree.xview)
        self.collections_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.collections_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Load data
        self.root.after(100, self._refresh_collections)

    def _create_collection_case(self):
        """Create a new collection case"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.collections.title"))
        dialog.geometry("500x350")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.collections.title"), font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        tk.Label(form_frame, text=_("finance_gui.common_labels.student_id")).grid(row=0, column=0, sticky='w', pady=5)
        student_id_entry = tk.Entry(form_frame, width=30)
        student_id_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.collections.total_debt")).grid(row=1, column=0, sticky='w', pady=5)
        debt_entry = tk.Entry(form_frame, width=30)
        debt_entry.grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.common_labels.notes")).grid(row=2, column=0, sticky='w', pady=5)
        notes_entry = tk.Entry(form_frame, width=30)
        notes_entry.grid(row=2, column=1, pady=5)

        def save_case():
            try:
                student_id = student_id_entry.get()
                total_debt = float(debt_entry.get())
                notes = notes_entry.get()

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO collection_cases
                    (student_id, total_debt, case_status, assigned_date, amount_collected,
                     notes, created_at, updated_at)
                    VALUES (?, ?, 'new', date('now'), 0, ?, datetime('now'), datetime('now'))
                ''', (student_id, total_debt, notes))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.collections_tab.case_created"))
                dialog.destroy()
                self._refresh_collections()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.collections_tab.failed_create_case", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.common_buttons.save"), command=save_case, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.common_buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _send_collection_notice(self):
        """Send collection notice for selected case"""
        selection = self.collections_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.collections_tab.no_selection"), _("finance_gui.collections_tab.select_collection_case"))
            return

        case_values = self.collections_tree.item(selection[0])['values']
        case_id = case_values[0]
        student_id = case_values[1]
        total_debt = case_values[2]

        # Create notice dialog
        notice_dialog = tk.Toplevel(self.root)
        notice_dialog.title(_("finance_gui.collections_tab.send_notice_title", case_id=case_id))
        notice_dialog.geometry("750x700")
        notice_dialog.transient(self.root)
        notice_dialog.grab_set()

        # Create main container with canvas for scrolling
        main_container = tk.Frame(notice_dialog)
        main_container.pack(fill='both', expand=True)

        # Create canvas
        canvas = tk.Canvas(main_container, bg='white')
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='white')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling support
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Case info frame
        info_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.collections.case_information"), padding=15)
        info_frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(info_frame, text=f"{_('finance_gui.collections.case_id')}: {case_id}", font=('Arial', 10)).pack(anchor='w')
        ttk.Label(info_frame, text=f"{_('finance_gui.collections.student_id')}: {student_id}", font=('Arial', 10)).pack(anchor='w')
        ttk.Label(info_frame, text=f"{_('finance_gui.collections.total_debt')}: £{total_debt:.2f}", font=('Arial', 10, 'bold')).pack(anchor='w')

        # Get student info
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT first_name, last_name, email_address FROM students
                WHERE student_id = ?
            ''', (student_id,))
            student = cursor.fetchone()

            if student:
                student_name = f"{student[0]} {student[1]}"
                student_email = student[2]
                ttk.Label(info_frame, text=f"Student: {student_name}", font=('Arial', 10)).pack(anchor='w')
                ttk.Label(info_frame, text=f"Email: {student_email}", font=('Arial', 10)).pack(anchor='w')
            else:
                student_email = None
                ttk.Label(info_frame, text=_("finance_gui.collections.student_details_not_found"), font=('Arial', 10), foreground='red').pack(anchor='w')

            conn.close()
        except Exception as e:
            student_email = None
            ttk.Label(info_frame, text=f"Error loading student: {e}", font=('Arial', 9), foreground='red').pack(anchor='w')

        # Notice type frame
        type_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.collections.notice_type"), padding=15)
        type_frame.pack(fill='x', padx=10, pady=10)

        notice_type_var = tk.StringVar(value="first_notice")
        notice_types = [
            ("first_notice", _("finance_gui.collections_tab.notice_types.first_notice")),
            ("second_notice", _("finance_gui.collections_tab.notice_types.second_notice")),
            ("final_notice", _("finance_gui.collections_tab.notice_types.final_notice")),
            ("legal_notice", _("finance_gui.collections_tab.notice_types.legal_notice")),
            ("payment_demand", _("finance_gui.collections_tab.notice_types.payment_demand"))
        ]

        for value, text in notice_types:
            ttk.Radiobutton(type_frame, text=text, variable=notice_type_var, value=value).pack(anchor='w', pady=2)

        # Message frame
        message_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.collections.message"), padding=15)
        message_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(message_frame, text=_("finance_gui.collections.subject")).pack(anchor='w')
        subject_var = tk.StringVar(value=_("finance_gui.collections_tab.notice_subject_default"))
        subject_entry = ttk.Entry(message_frame, textvariable=subject_var, font=('Arial', 11))
        subject_entry.pack(fill='x', pady=(0, 10))

        ttk.Label(message_frame, text=_("finance_gui.collections_tab.message_body_label")).pack(anchor='w')
        message_text = tk.Text(message_frame, height=10, font=('Arial', 10), wrap='word')
        message_text.pack(fill='both', expand=True)

        # Default message template
        default_message = _("finance_gui.collections_tab.default_message", **{"total_debt:.2f": f"{total_debt:.2f}"})
        message_text.insert('1.0', default_message)

        def send_notice():
            """Send the collection notice"""
            try:
                if not student_email:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.collections_tab.email_not_found"))
                    return

                notice_type = notice_type_var.get()
                subject = subject_var.get().strip()
                message = message_text.get('1.0', tk.END).strip()

                if not subject or not message:
                    messagebox.showwarning(_("finance_gui.messages.warning"), _("finance_gui.collections_tab.missing_subject_message"))
                    return

                # Get authentication for audit trail
                from university_system.infrastructure.shared_context import get_auth
                auth = get_auth()
                username = 'system'
                if auth and hasattr(auth, 'is_logged_in') and auth.is_logged_in():
                    user = auth.get_current_user()
                    username = user.get('username', 'system') if user else 'system'

                # Send email using email service
                from university_system.infrastructure.email.email_service import send_email

                html_message = f"""
                <html>
                <body>
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #d9534f;">{_("finance_gui.email_template.collection_notice_title")}</h2>
                <p><strong>{_("finance_gui.email_template.case_id_label")}</strong> {case_id}</p>
                <p><strong>{_("finance_gui.email_template.outstanding_amount_label")}</strong> £{total_debt:.2f}</p>
                <hr>
                <div style="white-space: pre-wrap;">{message}</div>
                <hr>
                <p style="font-size: 12px; color: #666;">
                {_("finance_gui.email_template.footer")}
                </p>
                </div>
                </body>
                </html>
                """

                # Send email
                success = send_email(
                    recipient_email=student_email,
                    subject=subject,
                    body=html_message
                )

                if success:
                    # Log the notice in database
                    conn = get_connection()
                    cursor = conn.cursor()

                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    # Check if collection_notices table exists
                    cursor.execute('''
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name='collection_notices'
                    ''')

                    if cursor.fetchone():
                        cursor.execute('''
                            INSERT INTO collection_notices
                            (case_id, student_id, notice_type, subject, message, sent_by, sent_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (case_id, student_id, notice_type, subject, message, username, now))
                        conn.commit()

                    # Update case with last notice date
                    cursor.execute('''
                        UPDATE collection_cases
                        SET last_contact_date = ?, updated_at = ?
                        WHERE case_id = ?
                    ''', (now, now, case_id))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo(_("finance_gui.messages.success"),
                                      _("finance_gui.collections_tab.notice_sent", email=student_email, notice_type=notice_type.replace('_', ' ').title()))
                    notice_dialog.destroy()
                    self._refresh_collections()
                else:
                    messagebox.showwarning(_("finance_gui.collections_tab.email_failed"),
                                         _("finance_gui.collections_tab.email_failed_message", email=student_email))

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.collections_tab.failed_send_notice", error=str(e)))
                import traceback
                traceback.print_exc()

        # Buttons
        btn_frame = ttk.Frame(scrollable_frame)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text=_("finance_gui.collections_tab.send_notice_btn"), command=send_notice).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=notice_dialog.destroy).pack(side='left', padx=5)

    def _resolve_collection_case(self):
        """Resolve selected collection case"""
        selection = self.collections_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.collections_tab.no_selection"), _("finance_gui.collections_tab.select_case_to_resolve"))
            return

        amount_collected = simpledialog.askfloat(_("finance_gui.collections_tab.resolve_case_title"), _("finance_gui.collections_tab.enter_amount_collected"))
        if amount_collected is None:
            return

        try:
            case_id = self.collections_tree.item(selection[0])['values'][0]
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE collection_cases
                SET case_status = 'resolved', amount_collected = ?,
                    resolution_date = date('now'), updated_at = datetime('now')
                WHERE case_id = ?
            ''', (amount_collected, case_id))
            conn.commit()
            conn.close()
            messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.collections_tab.case_resolved"))
            self._refresh_collections()
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.collections_tab.failed_resolve_case", error=str(e)))

    def _refresh_collections(self):
        """Refresh collections list"""
        try:
            # Clear existing items
            for item in self.collections_tree.get_children():
                self.collections_tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT case_id, student_id, total_debt, case_status, assigned_date,
                       amount_collected, resolution_date
                FROM collection_cases
                ORDER BY created_at DESC
                LIMIT 500
            ''')

            for row in cursor.fetchall():
                self.collections_tree.insert('', 'end', values=row)

            conn.close()
        except Exception as e:
            print(f"Error refreshing collections: {e}")

    def create_aid_tab(self):
        """Create financial aid management tab"""
        aid_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['aid'] = aid_frame

        # Title
        title_label = tk.Label(aid_frame, text=_("finance_gui.aid_tab.title"),
                               font=('Arial', 18, 'bold'), bg='white', fg=self.colors['primary'])
        title_label.pack(pady=20)

        # Description
        desc_label = tk.Label(
            aid_frame,
            text=_("finance_gui.tabs.scholarships.description"),
            font=('Arial', 11),
            bg='white',
            fg='#555'
        )
        desc_label.pack(pady=(0, 30))

        # Launch full Financial Aid GUI button
        if FINANCIAL_AID_GUI_AVAILABLE and launch_financial_aid_gui:
            launch_btn = tk.Button(
                aid_frame,
                text=_("finance_gui.buttons.open_financial_aid"),
                command=lambda: launch_financial_aid_gui(self.root, self.gui.auth),
                font=('Arial', 12, 'bold'),
                bg=self.colors['success'],
                fg='white',
                padx=30,
                pady=15
            )
            launch_btn.pack(pady=10)
        else:
            error_label = tk.Label(
                aid_frame,
                text=_("finance_gui.aid_tab.module_not_available"),
                font=('Arial', 11),
                bg='white',
                fg=self.colors['danger']
            )
            error_label.pack(pady=10)

        # Separator
        ttk.Separator(aid_frame, orient='horizontal').pack(fill='x', padx=20, pady=20)

        # Quick Actions section
        quick_actions_label = tk.Label(aid_frame, text=_("finance_gui.aid_tab.quick_actions"),
                               font=('Arial', 14, 'bold'), bg='white')
        quick_actions_label.pack(pady=10)

        # Toolbar
        toolbar = tk.Frame(aid_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Button(toolbar, text=_("finance_gui.aid_tab.award_aid"), command=self._award_financial_aid,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.aid_tab.disburse_funds"), command=self._disburse_aid,
                 bg=self.colors['info'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.aid_tab.cancel_aid"), command=self._cancel_aid,
                 bg=self.colors['danger'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.refresh"), command=self._refresh_financial_aid,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='right', padx=5)

        # Financial aid table
        table_frame = tk.Frame(aid_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ('aid_id', 'student_id', 'aid_type', 'awarded_amount', 'disbursed_amount',
                   'remaining_amount', 'status', 'application_date')
        self.aid_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.aid_tree.heading(col, text=col.replace('_', ' ').title())
            self.aid_tree.column(col, width=110)

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.aid_tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.aid_tree.xview)
        self.aid_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.aid_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Load data
        self.root.after(100, self._refresh_financial_aid)

    def _award_financial_aid(self):
        """Award financial aid to a student"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.aid_tab.award_dialog_title"))
        dialog.geometry("500x450")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.aid_tab.award_dialog_title"), font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        tk.Label(form_frame, text=_("finance_gui.aid_tab.student_id_label")).grid(row=0, column=0, sticky='w', pady=5)
        student_id_entry = tk.Entry(form_frame, width=30)
        student_id_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.aid_tab.aid_type_label")).grid(row=1, column=0, sticky='w', pady=5)
        aid_type_var = tk.StringVar()
        aid_type_combo = ttk.Combobox(form_frame, textvariable=aid_type_var, state='readonly', width=27)
        aid_type_combo.grid(row=1, column=1, pady=5)

        # Load aid types
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT aid_type_id, aid_name FROM financial_aid_types WHERE is_active = 1")
            aid_types = cursor.fetchall()
            conn.close()
            aid_type_combo['values'] = [f"{at[0]} - {at[1]}" for at in aid_types]
        except Exception as e:
            print(f"Error loading aid types: {e}")

        tk.Label(form_frame, text=_("finance_gui.aid_tab.awarded_amount_label")).grid(row=2, column=0, sticky='w', pady=5)
        amount_entry = tk.Entry(form_frame, width=30)
        amount_entry.grid(row=2, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.aid_tab.status_label")).grid(row=3, column=0, sticky='w', pady=5)
        status_var = tk.StringVar(value="pending")
        status_combo = ttk.Combobox(form_frame, textvariable=status_var,
                                   values=['pending', 'approved', 'disbursed', 'completed', 'cancelled'],
                                   state='readonly', width=27)
        status_combo.grid(row=3, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.aid_tab.notes_label")).grid(row=4, column=0, sticky='w', pady=5)
        notes_entry = tk.Entry(form_frame, width=30)
        notes_entry.grid(row=4, column=1, pady=5)

        def save_aid():
            try:
                student_id = student_id_entry.get()
                aid_type_str = aid_type_var.get()
                aid_type_id = int(aid_type_str.split(' - ')[0])
                awarded_amount = float(amount_entry.get())
                status = status_var.get()
                notes = notes_entry.get()

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO student_financial_aid
                    (student_id, aid_type_id, awarded_amount, disbursed_amount, remaining_amount,
                     status, application_date, notes, created_at, updated_at)
                    VALUES (?, ?, ?, 0, ?, ?, date('now'), ?, datetime('now'), datetime('now'))
                ''', (student_id, aid_type_id, awarded_amount, awarded_amount, status, notes))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.aid_tab.aid_awarded"))
                dialog.destroy()
                self._refresh_financial_aid()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.aid_tab.failed_award_aid", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.buttons.save"), command=save_aid, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _disburse_aid(self):
        """Disburse funds for selected aid"""
        selection = self.aid_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.aid_tab.no_selection"), _("finance_gui.aid_tab.select_aid_record"))
            return

        amount = simpledialog.askfloat(_("finance_gui.aid_tab.disburse_aid_title"), _("finance_gui.aid_tab.enter_disbursement_amount"))
        if amount is None:
            return

        try:
            aid_id = self.aid_tree.item(selection[0])['values'][0]
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE student_financial_aid
                SET disbursed_amount = disbursed_amount + ?,
                    remaining_amount = remaining_amount - ?,
                    status = 'disbursed',
                    updated_at = datetime('now')
                WHERE aid_id = ?
            ''', (amount, amount, aid_id))
            conn.commit()
            conn.close()
            messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.aid_tab.aid_disbursed"))
            self._refresh_financial_aid()
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.aid_tab.failed_disburse_aid", error=str(e)))

    def _cancel_aid(self):
        """Cancel selected financial aid"""
        selection = self.aid_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.aid_tab.no_selection"), _("finance_gui.aid_tab.select_aid_to_cancel"))
            return

        if messagebox.askyesno(_("finance_gui.dialogs.confirm"), _("finance_gui.aid_tab.confirm_cancel")):
            try:
                aid_id = self.aid_tree.item(selection[0])['values'][0]
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE student_financial_aid
                    SET status = 'cancelled', updated_at = datetime('now')
                    WHERE aid_id = ?
                ''', (aid_id,))
                conn.commit()
                conn.close()
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.aid_tab.aid_cancelled"))
                self._refresh_financial_aid()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.aid_tab.failed_cancel_aid", error=str(e)))

    def _refresh_financial_aid(self):
        """Refresh financial aid list"""
        try:
            # Clear existing items
            for item in self.aid_tree.get_children():
                self.aid_tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sfa.aid_id, sfa.student_id, fat.aid_name, sfa.awarded_amount,
                       sfa.disbursed_amount, sfa.remaining_amount, sfa.status, sfa.application_date
                FROM student_financial_aid sfa
                LEFT JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                ORDER BY sfa.created_at DESC
                LIMIT 500
            ''')

            for row in cursor.fetchall():
                self.aid_tree.insert('', 'end', values=row)

            conn.close()
        except Exception as e:
            print(f"Error refreshing financial aid: {e}")

    def create_budget_tab(self):
        """Create budget tab"""
        try:
            if hasattr(self.gui, 'budgets') and hasattr(self.gui.budgets, 'create_budget_tab'):
                self.gui.budgets.create_budget_tab()
            else:
                self._create_placeholder_tab('budget', '💼 Budget')
        except Exception as e:
            print(f"Error creating budget tab: {e}")
            self._create_placeholder_tab('budget', '💼 Budget')

    def create_forecasting_tab(self):
        """Create financial forecasting tab"""
        forecasting_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['forecasting'] = forecasting_frame

        # Title
        title_label = tk.Label(forecasting_frame, text=_("finance_gui.forecasting_tab.title"),
                               font=('Arial', 18, 'bold'), bg='white')
        title_label.pack(pady=10)

        # Toolbar
        toolbar = tk.Frame(forecasting_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Button(toolbar, text=_("finance_gui.forecasting_tab.generate_forecast"), command=self._generate_forecast,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.forecasting_tab.revenue_projection"), command=self._revenue_projection,
                 bg=self.colors['info'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.forecasting_tab.expense_projection"), command=self._expense_projection,
                 bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.refresh"), command=self._refresh_forecasting,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='right', padx=5)

        # Stats frame
        stats_frame = tk.LabelFrame(forecasting_frame, text=_("finance_gui.forecasting_tab.forecast_summary"), font=('Arial', 12, 'bold'), bg='white')
        stats_frame.pack(fill='x', padx=10, pady=10)

        stats_container = tk.Frame(stats_frame, bg='white')
        stats_container.pack(fill='x', padx=10, pady=10)

        self._create_forecast_stat_card(stats_container, _("finance_gui.forecasting_tab.projected_revenue_6mo"), _("finance_gui.messages.loading"), self.colors['success'], 0, 0)
        self._create_forecast_stat_card(stats_container, _("finance_gui.forecasting_tab.projected_expenses_6mo"), _("finance_gui.messages.loading"), self.colors['danger'], 0, 1)
        self._create_forecast_stat_card(stats_container, _("finance_gui.forecasting_tab.expected_collections"), _("finance_gui.messages.loading"), self.colors['warning'], 0, 2)
        self._create_forecast_stat_card(stats_container, _("finance_gui.forecasting_tab.net_projection"), _("finance_gui.messages.loading"), self.colors['info'], 0, 3)

        # Analysis text area
        analysis_frame = tk.LabelFrame(forecasting_frame, text=_("finance_gui.forecasting_tab.forecast_analysis"), font=('Arial', 12, 'bold'), bg='white')
        analysis_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.forecast_text = ScrolledText(analysis_frame, height=15, width=80, wrap=tk.WORD)
        self.forecast_text.pack(fill='both', expand=True, padx=10, pady=10)

        # Load initial data
        self.root.after(100, self._refresh_forecasting)

    def _create_forecast_stat_card(self, parent, title, value, color, row, col):
        """Create a forecast statistics card"""
        card = tk.Frame(parent, bg=color, relief='raised', bd=2)
        card.grid(row=row, column=col, padx=5, pady=5, sticky='ew')
        parent.grid_columnconfigure(col, weight=1)

        tk.Label(card, text=title, bg=color, fg='white', font=('Arial', 9, 'bold')).pack(pady=5)
        value_label = tk.Label(card, text=value, bg=color, fg='white', font=('Arial', 14, 'bold'))
        value_label.pack(pady=5)
        setattr(self, f"forecast_stat_{col}", value_label)

    def _generate_forecast(self):
        """Generate comprehensive financial forecast"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Calculate historical averages
            cursor.execute('''
                SELECT
                    AVG(monthly_revenue) as avg_revenue,
                    AVG(monthly_fees) as avg_fees
                FROM (
                    SELECT
                        strftime('%Y-%m', created_at) as month,
                        SUM(amount) as monthly_revenue,
                        COUNT(*) as monthly_fees
                    FROM payments
                    WHERE created_at >= date('now', '-12 months')
                    GROUP BY month
                )
            ''')
            result = cursor.fetchone()
            avg_revenue = result[0] if result[0] else 0

            # Project forward
            forecast_months = 6
            projected_revenue = avg_revenue * forecast_months

            conn.close()

            forecast_text = f"Financial Forecast Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            forecast_text += "=" * 70 + "\n\n"
            forecast_text += f"Forecast Period: {forecast_months} months\n"
            forecast_text += f"Based on: 12 months historical data\n\n"
            forecast_text += f"Projected Revenue: £{projected_revenue:,.2f}\n"
            forecast_text += f"Average Monthly Revenue: £{avg_revenue:,.2f}\n\n"
            forecast_text += "Assumptions:\n"
            forecast_text += "- Student enrollment remains stable\n"
            forecast_text += "- Fee structure unchanged\n"
            forecast_text += "- Collection rate at historical average\n\n"
            forecast_text += "Recommendations:\n"
            forecast_text += "- Monitor actual vs. forecast monthly\n"
            forecast_text += "- Adjust for seasonal variations\n"
            forecast_text += "- Review collection strategies\n"

            self.forecast_text.delete('1.0', tk.END)
            self.forecast_text.insert('1.0', forecast_text)

            messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.forecasting_tab.forecast_success"))
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.forecasting_tab.forecast_failed", error=str(e)))

    def _revenue_projection(self):
        """Generate revenue projection with database analysis"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get historical revenue data (last 12 months)
            cursor.execute('''
                SELECT strftime('%Y-%m', payment_date) as month,
                       SUM(amount) as total_revenue
                FROM payments
                WHERE status = 'completed'
                  AND payment_date >= date('now', '-12 months')
                GROUP BY month
                ORDER BY month
            ''')
            revenue_data = cursor.fetchall()

            # Calculate projection
            report = "=" * 80 + "\n"
            report += "REVENUE PROJECTION ANALYSIS\n"
            report += "=" * 80 + "\n\n"
            report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

            if not revenue_data:
                report += "No historical revenue data available for projection.\n"
            else:
                report += "HISTORICAL REVENUE (Last 12 Months):\n"
                report += "-" * 80 + "\n"
                report += f"{'Month':<15} {'Revenue':>20}\n"
                report += "-" * 80 + "\n"

                total_revenue = 0
                for month, revenue in revenue_data:
                    revenue = float(revenue or 0)
                    total_revenue += revenue
                    report += f"{month:<15} £{revenue:>18,.2f}\n"

                avg_monthly = total_revenue / len(revenue_data) if revenue_data else 0

                report += "-" * 80 + "\n"
                report += f"{'Total Revenue':<15} £{total_revenue:>18,.2f}\n"
                report += f"{'Average/Month':<15} £{avg_monthly:>18,.2f}\n\n"

                # Projection (using simple moving average)
                report += "REVENUE PROJECTIONS:\n"
                report += "-" * 80 + "\n"

                # Get last 3 months for trend
                recent_months = revenue_data[-3:] if len(revenue_data) >= 3 else revenue_data
                recent_total = sum(float(r[1] or 0) for r in recent_months)
                recent_avg = recent_total / len(recent_months) if recent_months else 0

                # Calculate growth rate
                if len(revenue_data) >= 6:
                    first_half = sum(float(r[1] or 0) for r in revenue_data[:3])
                    second_half = sum(float(r[1] or 0) for r in revenue_data[-3:])
                    growth_rate = ((second_half - first_half) / first_half * 100) if first_half > 0 else 0
                    report += f"Growth Trend: {growth_rate:+.2f}%\n\n"
                else:
                    growth_rate = 0

                # Project next 3, 6, 12 months
                proj_3_months = recent_avg * 3
                proj_6_months = recent_avg * 6
                proj_12_months = recent_avg * 12

                # Apply growth factor
                growth_factor = 1 + (growth_rate / 100)
                if growth_rate != 0:
                    proj_3_months *= growth_factor
                    proj_6_months *= growth_factor ** 0.5
                    proj_12_months *= growth_factor ** 0.25

                report += f"Next 3 Months:  £{proj_3_months:,.2f}\n"
                report += f"Next 6 Months:  £{proj_6_months:,.2f}\n"
                report += f"Next 12 Months: £{proj_12_months:,.2f}\n\n"

                report += "Note: Projections based on historical trends and simple moving averages.\n"

            conn.close()

            # Display in window
            window = tk.Toplevel(self.root)
            window.title(_("finance_gui.forecasting_tab.revenue_projection_title"))
            window.geometry("900x700")
            window.transient(self.root)

            from tkinter.scrolledtext import ScrolledText
            text_widget = ScrolledText(window, font=('Courier', 10), wrap=tk.WORD)
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', report)
            text_widget.config(state='disabled')

            ttk.Button(window, text=_("finance_gui.buttons.close"), command=window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.forecasting_tab.revenue_projection_failed", error=str(e)))

    def _expense_projection(self):
        """Generate expense projection with database analysis"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get historical expense data (last 12 months)
            cursor.execute('''
                SELECT strftime('%Y-%m', order_date) as month,
                       SUM(total_amount) as total_expense
                FROM purchase_orders
                WHERE status IN ('approved', 'completed', 'paid')
                  AND order_date >= date('now', '-12 months')
                GROUP BY month
                ORDER BY month
            ''')
            expense_data = cursor.fetchall()

            # Calculate projection
            report = "=" * 80 + "\n"
            report += "EXPENSE PROJECTION ANALYSIS\n"
            report += "=" * 80 + "\n\n"
            report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

            if not expense_data:
                report += "No historical expense data available for projection.\n"
            else:
                report += "HISTORICAL EXPENSES (Last 12 Months):\n"
                report += "-" * 80 + "\n"
                report += f"{'Month':<15} {'Expenses':>20}\n"
                report += "-" * 80 + "\n"

                total_expense = 0
                for month, expense in expense_data:
                    expense = float(expense or 0)
                    total_expense += expense
                    report += f"{month:<15} £{expense:>18,.2f}\n"

                avg_monthly = total_expense / len(expense_data) if expense_data else 0

                report += "-" * 80 + "\n"
                report += f"{'Total Expenses':<15} £{total_expense:>18,.2f}\n"
                report += f"{'Average/Month':<15} £{avg_monthly:>18,.2f}\n\n"

                # Projection (using simple moving average)
                report += "EXPENSE PROJECTIONS:\n"
                report += "-" * 80 + "\n"

                # Get last 3 months for trend
                recent_months = expense_data[-3:] if len(expense_data) >= 3 else expense_data
                recent_total = sum(float(e[1] or 0) for e in recent_months)
                recent_avg = recent_total / len(recent_months) if recent_months else 0

                # Calculate growth rate
                if len(expense_data) >= 6:
                    first_half = sum(float(e[1] or 0) for e in expense_data[:3])
                    second_half = sum(float(e[1] or 0) for e in expense_data[-3:])
                    growth_rate = ((second_half - first_half) / first_half * 100) if first_half > 0 else 0
                    report += f"Growth Trend: {growth_rate:+.2f}%\n\n"
                else:
                    growth_rate = 0

                # Project next 3, 6, 12 months
                proj_3_months = recent_avg * 3
                proj_6_months = recent_avg * 6
                proj_12_months = recent_avg * 12

                # Apply growth factor
                growth_factor = 1 + (growth_rate / 100)
                if growth_rate != 0:
                    proj_3_months *= growth_factor
                    proj_6_months *= growth_factor ** 0.5
                    proj_12_months *= growth_factor ** 0.25

                report += f"Next 3 Months:  £{proj_3_months:,.2f}\n"
                report += f"Next 6 Months:  £{proj_6_months:,.2f}\n"
                report += f"Next 12 Months: £{proj_12_months:,.2f}\n\n"

                report += "Note: Projections based on historical trends and simple moving averages.\n"

            conn.close()

            # Display in window
            window = tk.Toplevel(self.root)
            window.title(_("finance_gui.forecasting_tab.expense_projection_title"))
            window.geometry("900x700")
            window.transient(self.root)

            from tkinter.scrolledtext import ScrolledText
            text_widget = ScrolledText(window, font=('Courier', 10), wrap=tk.WORD)
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', report)
            text_widget.config(state='disabled')

            ttk.Button(window, text=_("finance_gui.buttons.close"), command=window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.forecasting_tab.expense_projection_failed", error=str(e)))

    def _refresh_forecasting(self):
        """Refresh forecasting data"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Projected revenue (next 6 months based on historical average)
            cursor.execute('''
                SELECT AVG(monthly_total) * 6 as projected_revenue
                FROM (
                    SELECT strftime('%Y-%m', created_at) as month, SUM(amount) as monthly_total
                    FROM payments
                    WHERE created_at >= date('now', '-12 months')
                    GROUP BY month
                )
            ''')
            result = cursor.fetchone()
            projected_revenue = result[0] if result and result[0] else 0

            # Expected collections
            cursor.execute('''
                SELECT SUM(total_debt - amount_collected) as expected_collections
                FROM collection_cases
                WHERE case_status IN ('new', 'assigned', 'in_progress')
            ''')
            result = cursor.fetchone()
            expected_collections = result[0] if result and result[0] else 0

            conn.close()

            # Update UI
            projected_expenses = projected_revenue * 0.7  # Estimate
            net_projection = projected_revenue - projected_expenses

            if hasattr(self, 'forecast_stat_0'):
                self.forecast_stat_0.config(text=f"£{projected_revenue:,.2f}")
            if hasattr(self, 'forecast_stat_1'):
                self.forecast_stat_1.config(text=f"£{projected_expenses:,.2f}")
            if hasattr(self, 'forecast_stat_2'):
                self.forecast_stat_2.config(text=f"£{expected_collections:,.2f}")
            if hasattr(self, 'forecast_stat_3'):
                self.forecast_stat_3.config(text=f"£{net_projection:,.2f}")

            # Update analysis
            analysis = f"Forecasting Data Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            analysis += "=" * 70 + "\n\n"
            analysis += f"6-Month Revenue Projection: £{projected_revenue:,.2f}\n"
            analysis += f"6-Month Expense Projection: £{projected_expenses:,.2f}\n"
            analysis += f"Expected Collections: £{expected_collections:,.2f}\n"
            analysis += f"Net Projection: £{net_projection:,.2f}\n\n"
            analysis += "Click 'Generate Forecast' for detailed analysis."

            self.forecast_text.delete('1.0', tk.END)
            self.forecast_text.insert('1.0', analysis)

        except Exception as e:
            print(f"Error refreshing forecasting: {e}")

    def create_admin_tab(self):
        """Create admin/system management tab"""
        admin_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['admin'] = admin_frame

        # Title
        title_label = tk.Label(admin_frame, text=_("finance_gui.admin_tab.title"),
                               font=('Arial', 18, 'bold'), bg='white')
        title_label.pack(pady=10)

        # Main container with sections
        main_container = tk.Frame(admin_frame, bg='white')
        main_container.pack(fill='both', expand=True, padx=10, pady=10)

        # Database Management Section
        db_section = tk.LabelFrame(main_container, text=_("finance_gui.admin.database_management"),
                                   font=('Arial', 12, 'bold'), bg='white')
        db_section.pack(fill='x', padx=10, pady=10)

        db_buttons = tk.Frame(db_section, bg='white')
        db_buttons.pack(fill='x', padx=10, pady=10)

        tk.Button(db_buttons, text=_("finance_gui.admin_tab.backup_database"), command=self._backup_database,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(db_buttons, text=_("finance_gui.admin_tab.database_statistics"), command=self._show_db_stats,
                 bg=self.colors['info'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(db_buttons, text=_("finance_gui.admin_tab.cleanup_old_data"), command=self._cleanup_old_data,
                 bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)

        # Fee Type Management Section
        fee_section = tk.LabelFrame(main_container, text=_("finance_gui.admin.fee_type_management"),
                                    font=('Arial', 12, 'bold'), bg='white')
        fee_section.pack(fill='x', padx=10, pady=10)

        fee_buttons = tk.Frame(fee_section, bg='white')
        fee_buttons.pack(fill='x', padx=10, pady=10)

        tk.Button(fee_buttons, text=_("finance_gui.admin_tab.create_fee_type_btn"), command=self._create_fee_type,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(fee_buttons, text=_("finance_gui.admin_tab.view_fee_types_btn"), command=self._view_fee_types,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)

        # Aid Type Management Section
        aid_section = tk.LabelFrame(main_container, text=_("finance_gui.admin.aid_type_management"),
                                    font=('Arial', 12, 'bold'), bg='white')
        aid_section.pack(fill='x', padx=10, pady=10)

        aid_buttons = tk.Frame(aid_section, bg='white')
        aid_buttons.pack(fill='x', padx=10, pady=10)

        tk.Button(aid_buttons, text=_("finance_gui.admin_tab.create_aid_type_btn"), command=self._create_aid_type,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(aid_buttons, text=_("finance_gui.admin_tab.view_aid_types_btn"), command=self._view_aid_types,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)

        # System Status Section
        status_section = tk.LabelFrame(main_container, text=_("finance_gui.admin.system_status"),
                                      font=('Arial', 12, 'bold'), bg='white')
        status_section.pack(fill='both', expand=True, padx=10, pady=10)

        self.admin_status_text = ScrolledText(status_section, height=15, width=80, wrap=tk.WORD)
        self.admin_status_text.pack(fill='both', expand=True, padx=10, pady=10)

        # Refresh button for status
        tk.Button(status_section, text=_("finance_gui.admin_tab.refresh_status"), command=self._refresh_admin_status,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'),
                 padx=15, pady=8).pack(pady=10)

        # Load initial status
        self.root.after(100, self._refresh_admin_status)

    def _backup_database(self):
        """Backup the database"""
        try:
            import shutil
            from pathlib import Path
            from university_system.modules.shared.constants import paths

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = paths.BACKUP_DIR
            backup_dir.mkdir(parents=True, exist_ok=True)

            backup_path = backup_dir / f"student_records_backup_{timestamp}.db"

            shutil.copy2(paths.DEFAULT_DB_PATH, backup_path)
            messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.admin_tab.backup_success", path=str(backup_path)))
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.admin_tab.backup_failed", error=str(e)))

    def _show_db_stats(self):
        """Show database statistics"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            stats_text = "Database Statistics\n"
            stats_text += "=" * 70 + "\n\n"

            tables = ['students', 'student_fees', 'payments', 'scholarships',
                     'student_scholarships', 'collection_cases', 'student_financial_aid',
                     'late_fees', 'exchange_rates']

            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    stats_text += f"{table:30s}: {count:>10,} records\n"
                except Exception:
                    stats_text += f"{table:30s}: Table not found\n"

            conn.close()

            self.admin_status_text.delete('1.0', tk.END)
            self.admin_status_text.insert('1.0', stats_text)
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.admin_tab.db_stats_failed", error=str(e)))

    def _cleanup_old_data(self):
        """Cleanup old data (with confirmation)"""
        if not messagebox.askyesno(_("finance_gui.dialogs.confirm"), _("finance_gui.admin_tab.cleanup_confirm")):
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Delete old payment records
            cursor.execute('''
                DELETE FROM payments
                WHERE created_at < date('now', '-7 years')
            ''')
            deleted_payments = cursor.rowcount

            # Delete old late fees
            cursor.execute('''
                DELETE FROM late_fees
                WHERE created_at < date('now', '-7 years')
            ''')
            deleted_late_fees = cursor.rowcount

            conn.commit()
            conn.close()

            messagebox.showinfo(_("finance_gui.messages.success"),
                              _("finance_gui.admin_tab.cleanup_success", payments=deleted_payments, late_fees=deleted_late_fees))
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.admin_tab.cleanup_failed", error=str(e)))

    def _create_fee_type(self):
        """Create a new fee type"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.admin_tab.create_fee_type_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.admin_tab.create_fee_type_title"), font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        tk.Label(form_frame, text=_("finance_gui.admin_tab.fee_name_label")).grid(row=0, column=0, sticky='w', pady=5)
        name_entry = tk.Entry(form_frame, width=30)
        name_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.admin_tab.description_label")).grid(row=1, column=0, sticky='w', pady=5)
        description_entry = tk.Entry(form_frame, width=30)
        description_entry.grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.admin_tab.academic_year_label")).grid(row=2, column=0, sticky='w', pady=5)
        year_entry = tk.Entry(form_frame, width=30)
        year_entry.insert(0, "2024-2025")
        year_entry.grid(row=2, column=1, pady=5)

        is_recurring_var = tk.BooleanVar()
        tk.Checkbutton(form_frame, text=_("finance_gui.admin_tab.is_recurring_label"), variable=is_recurring_var).grid(row=3, column=1, sticky='w', pady=5)

        def save_fee_type():
            try:
                name = name_entry.get()
                description = description_entry.get()
                academic_year = year_entry.get()
                is_recurring = is_recurring_var.get()

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO fee_types
                    (fee_name, description, academic_year, is_recurring, created_at, updated_at)
                    VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                ''', (name, description, academic_year, 1 if is_recurring else 0))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.admin_tab.fee_type_created"))
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.admin_tab.fee_type_failed", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.buttons.save"), command=save_fee_type, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _view_fee_types(self):
        """View all fee types"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT fee_type_id, fee_name, description, academic_year, is_recurring
                FROM fee_types
                ORDER BY fee_type_id
            ''')

            fee_types = cursor.fetchall()
            conn.close()

            text = _("finance_gui.admin_tab.fee_types_title") + "\n"
            text += "=" * 70 + "\n\n"

            for ft in fee_types:
                text += f"{_('finance_gui.admin_tab.id_label', id=ft[0])}\n"
                text += f"{_('finance_gui.admin_tab.name_label', name=ft[1])}\n"
                text += f"{_('finance_gui.admin_tab.description_value', description=ft[2])}\n"
                text += f"{_('finance_gui.admin_tab.academic_year_value', year=ft[3])}\n"
                recurring_value = _("finance_gui.admin_tab.recurring_yes") if ft[4] else _("finance_gui.admin_tab.recurring_no")
                text += f"{_('finance_gui.admin_tab.recurring_label', value=recurring_value)}\n"
                text += "-" * 70 + "\n"

            self.admin_status_text.delete('1.0', tk.END)
            self.admin_status_text.insert('1.0', text)
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.admin_tab.view_fee_types_failed", error=str(e)))

    def _create_aid_type(self):
        """Create a new financial aid type"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.admin_tab.create_aid_type_title"))
        dialog.geometry("500x450")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.admin_tab.create_aid_type_heading"), font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        tk.Label(form_frame, text=_("finance_gui.admin_tab.aid_type_name_label")).grid(row=0, column=0, sticky='w', pady=5)
        name_entry = tk.Entry(form_frame, width=30)
        name_entry.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.admin_tab.description_label")).grid(row=1, column=0, sticky='w', pady=5)
        description_entry = tk.Entry(form_frame, width=30)
        description_entry.grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.admin_tab.max_amount_label")).grid(row=2, column=0, sticky='w', pady=5)
        max_amount_entry = tk.Entry(form_frame, width=30)
        max_amount_entry.grid(row=2, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.admin_tab.category_label")).grid(row=3, column=0, sticky='w', pady=5)
        category_var = tk.StringVar(value="grant")
        category_combo = ttk.Combobox(form_frame, textvariable=category_var,
                                     values=['grant', 'loan', 'scholarship', 'work_study'],
                                     state='readonly', width=27)
        category_combo.grid(row=3, column=1, pady=5)

        def save_aid_type():
            try:
                name = name_entry.get()
                description = description_entry.get()
                max_amount = float(max_amount_entry.get())
                category = category_var.get()

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO financial_aid_types
                    (aid_name, description, max_amount, aid_category, is_active,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, datetime('now'), datetime('now'))
                ''', (name, description, max_amount, category))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.admin_tab.aid_type_created"))
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.admin_tab.aid_type_failed", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.buttons.save"), command=save_aid_type, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _view_aid_types(self):
        """View all financial aid types"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT aid_type_id, aid_name, description, max_amount, aid_category, is_active
                FROM financial_aid_types
                ORDER BY aid_type_id
            ''')

            aid_types = cursor.fetchall()
            conn.close()

            text = _("finance_gui.admin_tab.aid_types_title") + "\n"
            text += "=" * 70 + "\n\n"

            for at in aid_types:
                text += f"{_('finance_gui.admin_tab.id_label', id=at[0])}\n"
                text += f"{_('finance_gui.admin_tab.name_label', name=at[1])}\n"
                text += f"{_('finance_gui.admin_tab.description_value', description=at[2])}\n"
                text += f"{_('finance_gui.admin_tab.max_amount_value', amount=at[3])}\n"
                text += f"{_('finance_gui.admin_tab.category_value', category=at[4])}\n"
                active_value = _("finance_gui.admin_tab.active_yes") if at[5] else _("finance_gui.admin_tab.active_no")
                text += f"{_('finance_gui.admin_tab.active_label', value=active_value)}\n"
                text += "-" * 70 + "\n"

            self.admin_status_text.delete('1.0', tk.END)
            self.admin_status_text.insert('1.0', text)
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.admin_tab.view_aid_types_failed", error=str(e)))

    def _refresh_admin_status(self):
        """Refresh admin status display"""
        try:
            status_text = f"System Status - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            status_text += "=" * 70 + "\n\n"

            conn = get_connection()
            cursor = conn.cursor()

            # Database info
            status_text += "DATABASE STATUS\n"
            status_text += "-" * 70 + "\n"

            # Count records
            cursor.execute("SELECT COUNT(*) FROM students")
            student_count = cursor.fetchone()[0]
            status_text += f"Total Students: {student_count:,}\n"

            cursor.execute("SELECT COUNT(*) FROM student_fees WHERE status = 'unpaid'")
            unpaid_fees = cursor.fetchone()[0]
            status_text += f"Unpaid Fees: {unpaid_fees:,}\n"

            cursor.execute("SELECT COUNT(*) FROM payments")
            payment_count = cursor.fetchone()[0]
            status_text += f"Total Payments: {payment_count:,}\n"

            cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'completed'")
            total_revenue = cursor.fetchone()[0]
            status_text += f"Total Revenue: £{total_revenue:,.2f}\n\n"

            # Recent activity
            status_text += "RECENT ACTIVITY (Last 7 Days)\n"
            status_text += "-" * 70 + "\n"

            cursor.execute('''
                SELECT COUNT(*) FROM payments
                WHERE created_at >= date('now', '-7 days')
            ''')
            recent_payments = cursor.fetchone()[0]
            status_text += f"New Payments: {recent_payments}\n"

            cursor.execute('''
                SELECT COUNT(*) FROM student_fees
                WHERE created_at >= date('now', '-7 days')
            ''')
            recent_fees = cursor.fetchone()[0]
            status_text += f"New Fees Assigned: {recent_fees}\n"

            cursor.execute('''
                SELECT COUNT(*) FROM collection_cases
                WHERE created_at >= date('now', '-7 days')
            ''')
            recent_collections = cursor.fetchone()[0]
            status_text += f"New Collection Cases: {recent_collections}\n\n"

            status_text += "System is operational and running normally.\n"
            status_text += "Last updated: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            conn.close()

            self.admin_status_text.delete('1.0', tk.END)
            self.admin_status_text.insert('1.0', status_text)

        except Exception as e:
            error_text = f"Error loading system status: {e}"
            self.admin_status_text.delete('1.0', tk.END)
            self.admin_status_text.insert('1.0', error_text)

    def create_research_grants_tab(self):
        """Create research & grants management tab"""
        frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['research_grants'] = frame

        # Add title
        title_label = tk.Label(
            frame,
            text=_("finance_gui.research_grants_tab.title"),
            font=('Arial', 18, 'bold'),
            bg='white',
            fg=self.colors['primary']
        )
        title_label.pack(pady=20)

        # Description
        desc_label = tk.Label(
            frame,
            text=_("finance_gui.tabs.research_grants.description"),
            font=('Arial', 11),
            bg='white',
            fg='#555'
        )
        desc_label.pack(pady=(0, 30))

        # Launch button
        if RESEARCH_GRANTS_AVAILABLE and launch_research_grants_gui:
            launch_btn = tk.Button(
                frame,
                text=_("finance_gui.research_grants_tab.open_management"),
                command=lambda: launch_research_grants_gui(self.root, self.gui.auth),
                font=('Arial', 12, 'bold'),
                bg=self.colors['success'],
                fg='white',
                padx=30,
                pady=15
            )
            launch_btn.pack(pady=10)
        else:
            error_label = tk.Label(
                frame,
                text=_("finance_gui.research_grants_tab.module_not_available"),
                font=('Arial', 11),
                bg='white',
                fg=self.colors['danger']
            )
            error_label.pack(pady=10)

        # Info text
        info_text = ScrolledText(frame, height=15, width=80, font=('Arial', 10), wrap='word')
        info_text.pack(pady=20, padx=20, fill='both', expand=True)

        info_content = _("finance_gui.research_grants_tab.info_content")

        info_text.insert('1.0', info_content)
        info_text.config(state='disabled')

    def create_settings_tab(self):
        """Create settings tab"""
        try:
            if hasattr(self.gui, 'settings') and hasattr(self.gui.settings, 'create_settings_tab'):
                self.gui.settings.create_settings_tab()
            else:
                self._create_placeholder_tab('settings', '⚙️ Settings')
        except Exception as e:
            print(f"Error creating settings tab: {e}")
            self._create_placeholder_tab('settings', '⚙️ Settings')

    def show_tab(self, tab_id):
        """Show the specified tab and hide others"""
        # Special handling for my_finances - opens student's own finance dialog
        if tab_id == 'my_finances':
            if hasattr(self.gui, 'view_my_finances'):
                self.gui.view_my_finances()
            elif hasattr(self.gui, 'view_student_finances'):
                self.gui.view_student_finances()
            return

        # Hide current tab if exists
        if self.current_tab and self.current_tab in self.tab_frames:
            self.tab_frames[self.current_tab].pack_forget()

        # Show new tab
        if tab_id in self.tab_frames:
            self.tab_frames[tab_id].pack(fill='both', expand=True)
            self.current_tab = tab_id

        # Update button styles
        for widget in self.nav_frame.winfo_children():
            if isinstance(widget, tk.Button):
                widget.config(bg=self.colors['secondary'])

        # Highlight active button (simple approach)
        for widget in self.nav_frame.winfo_children():
            if isinstance(widget, tk.Button) and tab_id in widget['text'].lower():
                widget.config(bg=self.colors['primary'])
    

    def create_status_bar(self):
        """Create status bar at bottom"""
        self.status_bar = tk.Frame(self.root, bg='#34495e', height=30)
        self.status_bar.pack(side='bottom', fill='x')

        self.status_var = tk.StringVar(value=_("finance_gui.status_bar.ready"))
        self.status_label = tk.Label(self.status_bar, textvariable=self.status_var,
                               bg='#34495e', fg='white', font=('Arial', 10))
        self.status_label.pack(side='left', padx=10, pady=5)

        # Add Status_label property for backward compatibility
        self.Status_label = self.status_label

        # Connection status
        self.connection_label = tk.Label(self.status_bar, text=_("finance_gui.status_bar.connected"),
                                       bg='#34495e', fg='white', font=('Arial', 10))
        self.connection_label.pack(side='right', padx=10, pady=5)
    
        # Add timestamp
        self.time_var = tk.StringVar()
        time_label = tk.Label(self.status_bar, textvariable=self.time_var,
                             bg='#34495e', fg='white', font=('Arial', 10))
        time_label.pack(side='right', padx=10, pady=5)
    
        self.update_time()
    

    def update_status(self, message):
        """Update status bar message"""
        if hasattr(self, 'status_label') and self.status_label:
            try:
                self.status_label.config(text=message)
                self.root.update_idletasks()
            except Exception as e:
                # Status bar unavailable, silently ignore
                print(f"Debug: Status bar update failed: {e}")

    # ==================== ACTION METHODS ====================


    def update_time(self):
        """Update timestamp in status bar"""
        if hasattr(self, 'time_var') and self.time_var:
            try:
                # Check if root window still exists
                if not hasattr(self, 'root') or not self.root.winfo_exists():
                    return

                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.time_var.set(current_time)
                self.root.after(1000, self.update_time)
            except Exception:
                # Time display unavailable or window destroyed, silently ignore
                pass
    

    def update_system_status(self):
        """Update system status display"""
        try:
            status_info = f"System Status - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            status_info += "=" * 60 + "\n\n"
            
            # Database connection status
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM students')
                student_count = cursor.fetchone()[0]
                status_info += f"✓ Database Connection: OK\n"
                status_info += f"  - Students in system: {student_count}\n"
                conn.close()
            except Exception as e:
                status_info += f"✗ Database Connection: FAILED ({e})\n"
            
            # Check tables
            essential_tables = [
                'students', 'student_fees', 'payments', 'payment_allocations',
                'scholarships', 'student_scholarships', 'payment_plan_templates',
                'student_payment_plans', 'late_fees', 'exchange_rates'
            ]
            
            try:
                conn = get_connection()
                cursor = conn.cursor()
                status_info += f"\nTable Status:\n"
                
                for table in essential_tables:
                    try:
                        cursor.execute(f'SELECT COUNT(*) FROM {table}')
                        count = cursor.fetchone()[0]
                        status_info += f"  ✓ {table}: {count} records\n"
                    except Exception:
                        status_info += f"  ✗ {table}: Missing or corrupted\n"
                
                conn.close()
                
            except Exception as e:
                status_info += f"✗ Table Check Failed: {e}\n"
            
            # System performance
            status_info += f"\nSystem Performance:\n"
            status_info += f"  - GUI Framework: Tkinter\n"
            status_info += f"  - Database: SQLite\n"
            status_info += f"  - Current User: {auth.current_user.get('username', 'Unknown')}\n"
            
            # Recent activity
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                SELECT COUNT(*) FROM payments 
                WHERE date(created_at) = date('now')
                ''')
                
                today_payments = cursor.fetchone()[0]
                
                cursor.execute('''
                SELECT COUNT(*) FROM student_fees 
                WHERE date(created_at) = date('now')
                ''')
                today_fees = cursor.fetchone()[0]
                
                status_info += f"\nToday's Activity:\n"
                status_info += f"  - Payments recorded: {today_payments}\n"
                status_info += f"  - Fees assigned: {today_fees}\n"
                
                conn.close()
                
            except Exception as e:
                status_info += f"\nActivity Check Failed: {e}\n"
            
            # Update display
            self.status_text.delete('1.0', tk.END)
            self.status_text.insert('1.0', status_info)
            
        except Exception as e:
            error_msg = f"Failed to update system status: {e}"
            self.status_text.delete('1.0', tk.END)
            self.status_text.insert('1.0', error_msg)
    
