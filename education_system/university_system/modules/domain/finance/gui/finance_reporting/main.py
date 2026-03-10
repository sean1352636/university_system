import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
import threading
from datetime import datetime, timedelta
import json
import webbrowser
from pathlib import Path
import matplotlib
from education_system.university_system.modules.shared.constants import paths
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

# Import auth instance management from user_authentication
try:
    from education_system.university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)
# Import the shared authentication system
try:
    from education_system.university_system.infrastructure.auth import UserAuth
    from education_system.university_system.infrastructure.shared_context import get_auth
except ImportError as e:
    print(f"⚠️ Could not import UserAuth: {e}")
    UserAuth = None
    get_auth = lambda: None

from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()

# Import from misc - only non-circular imports at module level
from education_system.university_system.modules.domain.finance.gui.finance_reporting.misc import ensure_financial_alerts_table, register_misc_methods

# Import tab creation functions
from education_system.university_system.modules.domain.finance.gui.finance_reporting import dashboard_tab
from education_system.university_system.modules.domain.finance.gui.finance_reporting import analysis_tab
from education_system.university_system.modules.domain.finance.gui.finance_reporting import reports_tab
from education_system.university_system.modules.domain.finance.gui.finance_reporting import settings_tab

# Import feature functions
from education_system.university_system.modules.domain.finance.gui.finance_reporting import advanced_features
from education_system.university_system.modules.domain.finance.gui.finance_reporting import alerts_monitoring
from education_system.university_system.modules.domain.finance.gui.finance_reporting import ml_analytics
from education_system.university_system.modules.domain.finance.gui.finance_reporting import archive_backup
from education_system.university_system.modules.domain.finance.gui.finance_reporting import feature_dialogs


class FinancialManagementGUI:
    """Enhanced GUI for Financial Management System (core class)"""

    def __init__(self, root, auth_instance=None):
        self.root = root
        self.auth = auth_instance  # Store authentication instance
        self.current_chart_window = None  # Track current chart window to prevent duplicates
        self._time_update_id = None  # Track the after() callback for cleanup

        # Set global auth for backward compatibility with standalone functions
        global auth
        auth = self.auth
        if HAS_AUTH and self.auth:
            set_auth_instance(self.auth)

        self.root.title(_("finance_reporting.title"))
        # Make window bigger - use 90% of screen size
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = int(screen_width * 0.9)
        window_height = int(screen_height * 0.9)
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Ensure database tables exist
        ensure_financial_alerts_table()

        # Configure styles
        self.setup_styles()

        # Create main interface
        self.create_main_interface()

        # Handle window close button (X)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Initialize status
        self.update_status(_("finance_reporting.status.ready"))

        # Run initial health check
        self.run_background_health_check()

    def on_closing(self):
        """Handle window closing - cleanup and destroy"""
        self.cancel_time_update()
        self.root.destroy()

    def setup_styles(self):
        """Configure ttk styles to match main_gui.py standards"""
        self.style = ttk.Style()

        # Use clam theme like main_gui.py
        self.style.theme_use('clam')

        # Header styling (matching main_gui.py)
        self.style.configure('Header.TLabel',
                            font=('Arial', 18, 'bold'))

        self.style.configure('Title.TLabel',
                            font=('Arial', 18, 'bold'))

        self.style.configure('Heading.TLabel',
                            font=('Arial', 14, 'bold'))

        self.style.configure('Section.TLabel',
                            font=('Arial', 12, 'bold'))

        self.style.configure('Info.TLabel',
                            font=('Arial', 11))

        self.style.configure('Status.TLabel',
                            font=('Arial', 10),
                            foreground='#27ae60')

        self.style.configure('Error.TLabel',
                            font=('Arial', 10),
                            foreground='#e74c3c')

        self.style.configure('Warning.TLabel',
                            font=('Arial', 10),
                            foreground='#f39c12')

        # Button styles matching main_gui.py
        self.style.configure('TButton',
                            font=('Arial', 10))

        self.style.configure('Accent.TButton',
                            font=('Arial', 10, 'bold'))

        # Treeview styling
        self.style.configure('Treeview',
                            font=('Arial', 10),
                            rowheight=25)

        self.style.configure('Treeview.Heading',
                            font=('Arial', 10, 'bold'))

        # LabelFrame styling
        self.style.configure('TLabelframe.Label',
                            font=('Arial', 11, 'bold'))

    def create_main_interface(self):
        """Create the main GUI interface"""
        # Main container with padding (matching main_gui.py)
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(2, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)

        # Header with LabelFrame (matching main_gui.py)
        self.create_header(main_frame)

        # Main content area
        self.create_content_area(main_frame)

        # Status bar
        self.create_status_bar(main_frame)

    def create_header(self, parent):
        """Create header with title and quick actions (matching main_gui.py)"""
        header_frame = ttk.LabelFrame(parent, text=_("finance_reporting.header.title"), padding="10")
        header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        header_frame.grid_columnconfigure(1, weight=1)

        # Control buttons row
        button_frame = ttk.Frame(header_frame)
        button_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # Return to main menu button
        ttk.Button(button_frame, text=_("finance_reporting.buttons.return_to_main"),
                  command=self.return_to_main_menu,
                  style='Accent.TButton').pack(side='left', padx=(0, 10))

        # Quick action buttons
        ttk.Button(button_frame, text=_("finance_reporting.buttons.refresh"),
                  command=self.refresh_dashboard).pack(side='left', padx=(0, 5))
        ttk.Button(button_frame, text=_("finance_reporting.buttons.dashboard"),
                  command=self.show_realtime_dashboard).pack(side='left', padx=(0, 5))
        ttk.Button(button_frame, text=_("finance_reporting.buttons.alerts"),
                  command=self.show_alerts).pack(side='left', padx=(0, 5))
        ttk.Button(button_frame, text=_("finance_reporting.buttons.quick_report"),
                  command=self.generate_quick_report).pack(side='left', padx=(0, 5))

        # Status row
        status_frame = ttk.Frame(header_frame)
        status_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W)

        ttk.Label(status_frame, text=_("finance_reporting.labels.status"), font=('Arial', 10, 'bold')).pack(side='left')
        ttk.Label(status_frame, text=_("finance_reporting.status.connected"), font=('Arial', 10)).pack(side='left', padx=(10, 20))

        # User info
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            ttk.Label(status_frame, text=_("finance_reporting.labels.current_user"), font=('Arial', 10, 'bold')).pack(side='left')
            user_info = f"{self.auth.current_user.get('username', 'User')} ({self.auth.current_user.get('role', 'user')})"
            ttk.Label(status_frame, text=user_info, font=('Arial', 10)).pack(side='left', padx=(10, 0))

    def create_content_area(self, parent):
        """Create main content area with sidebar and main panel"""
        # Sidebar
        self.create_sidebar(parent)

        # Main panel with notebook
        self.create_main_panel(parent)

    def create_sidebar(self, parent):
        """Create sidebar with scrollable button navigation"""
        sidebar_frame = ttk.LabelFrame(parent, text=_("finance_reporting.sidebar.navigation"), padding="5")
        sidebar_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        sidebar_frame.grid_rowconfigure(0, weight=1)
        sidebar_frame.grid_columnconfigure(0, weight=1)

        # Create canvas for scrollable buttons
        self.nav_canvas = tk.Canvas(sidebar_frame, bg='white', highlightthickness=0)
        self.nav_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Scrollbar for navigation
        nav_scroll = ttk.Scrollbar(sidebar_frame, orient=tk.VERTICAL, command=self.nav_canvas.yview)
        nav_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.nav_canvas.configure(yscrollcommand=nav_scroll.set)

        # Create frame inside canvas to hold buttons
        self.nav_button_frame = ttk.Frame(self.nav_canvas)
        self.canvas_window = self.nav_canvas.create_window((0, 0), window=self.nav_button_frame, anchor='nw')

        # Bind configuration to update scroll region
        self.nav_button_frame.bind('<Configure>',
            lambda e: self.nav_canvas.configure(scrollregion=self.nav_canvas.bbox('all')))

        # Bind canvas width to frame width
        self.nav_canvas.bind('<Configure>',
            lambda e: self.nav_canvas.itemconfig(self.canvas_window, width=e.width))

        # Enable mouse wheel scrolling
        self.nav_canvas.bind_all('<MouseWheel>', self._on_mousewheel)

        # Populate navigation menu with buttons
        self.populate_navigation()

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        self.nav_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def populate_navigation(self):
        """Populate the navigation with buttons organized by category"""
        # Clear existing buttons
        for widget in self.nav_button_frame.winfo_children():
            widget.destroy()

        # Navigation structure - ADD the missing functions
        nav_structure = {
            _("finance_reporting.nav.advanced_analytics"): {
                'advanced_forecasting': _("finance_reporting.nav.advanced_forecasting"),
                'budget_variance': _("finance_reporting.nav.budget_variance"),
                'realtime_dashboard': _("finance_reporting.nav.realtime_dashboard"),
                'lifecycle_analysis': _("finance_reporting.nav.lifecycle_analysis")
            },
            _("finance_reporting.nav.predictive_analytics"): {
                'payment_risk': _("finance_reporting.nav.payment_risk"),
                'anomaly_detection': _("finance_reporting.nav.anomaly_detection"),
                'cash_flow_forecast': _("finance_reporting.nav.cash_flow_forecast"),
                'scenario_planning': _("finance_reporting.nav.scenario_planning")
            },
            _("finance_reporting.nav.monitoring_alerts"): {
                'alert_system': _("finance_reporting.nav.alert_system"),
                'automated_reporting': _("finance_reporting.nav.automated_reporting"),
                'performance_monitoring': _("finance_reporting.nav.performance_monitoring")
            },
            _("finance_reporting.nav.comparative_analysis"): {
                'yoy_analysis': _("finance_reporting.nav.yoy_analysis"),
                'department_comparison': _("finance_reporting.nav.department_comparison"),
                'comparative_analysis': _("finance_reporting.nav.comprehensive_comparative"),
                'benchmarking': _("finance_reporting.nav.benchmarking")
            },
            _("finance_reporting.nav.strategic_planning"): {
                'payment_optimization': _("finance_reporting.nav.payment_optimization"),
                'collection_strategy': _("finance_reporting.nav.collection_strategy"),
                'scholarship_analysis': _("finance_reporting.nav.scholarship_analysis"),
                'revenue_optimization': _("finance_reporting.nav.revenue_optimization")
            },
            _("finance_reporting.nav.export_integration"): {
                'advanced_export': _("finance_reporting.nav.advanced_export"),
                'api_config': _("finance_reporting.nav.api_config"),
                'custom_reports': _("finance_reporting.nav.custom_reports")
            },
            _("finance_reporting.nav.compliance_audit"): {
                'compliance_audit': _("finance_reporting.nav.compliance_audit_item"),
                'data_quality': _("finance_reporting.nav.data_quality"),
                'regulatory_reporting': _("finance_reporting.nav.regulatory_reporting")
            },
            _("finance_reporting.nav.system_management"): {
                'ml_training': _("finance_reporting.nav.ml_training"),
                'performance_optimization': _("finance_reporting.nav.performance_optimization"),
                'archive_management': _("finance_reporting.nav.archive_management")
            }
        }

        # Color scheme for categories
        category_colors = {
            'Advanced Analytics': '#3498db',
            'Predictive Analytics': '#9b59b6',
            'Monitoring & Alerts': '#e74c3c',
            'Comparative Analysis': '#f39c12',
            'Strategic Planning': '#1abc9c',
            'Export & Integration': '#34495e',
            'Compliance & Audit': '#e67e22',
            'System Management': '#2ecc71'
        }

        # Create buttons organized by category
        row = 0
        for category, items in nav_structure.items():
            # Category label
            cat_label = ttk.Label(
                self.nav_button_frame,
                text=category,
                font=('Arial', 11, 'bold'),
                background=category_colors.get(category, '#3498db'),
                foreground='white',
                padding=(5, 5)
            )
            cat_label.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=(10, 2), padx=2)
            row += 1

            # Function buttons for this category
            for func_id, func_name in items.items():
                btn = ttk.Button(
                    self.nav_button_frame,
                    text=func_name,
                    command=lambda fid=func_id: self.on_function_select(fid)
                )
                btn.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=2, padx=5)
                row += 1

        # Configure column weight
        self.nav_button_frame.grid_columnconfigure(0, weight=1)

    def create_main_panel(self, parent):
        """Create main panel with tabbed interface"""
        main_panel = ttk.Frame(parent)
        main_panel.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_panel.grid_rowconfigure(0, weight=1)
        main_panel.grid_columnconfigure(0, weight=1)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_panel)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Create initial tabs
        self.create_dashboard_tab()
        self.create_analysis_tab()
        self.create_reports_tab()
        self.create_settings_tab()

    def create_status_bar(self, parent):
        """Create status bar at bottom"""
        status_frame = ttk.Frame(parent)
        status_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        status_frame.grid_columnconfigure(1, weight=1)

        # Status label
        self.status_var = tk.StringVar(value=_("finance_reporting.status.ready"))
        ttk.Label(status_frame, textvariable=self.status_var, 
                 style='Status.TLabel').grid(row=0, column=0, sticky=tk.W)

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(status_frame, variable=self.progress_var, 
                                          mode='determinate', length=200)
        self.progress_bar.grid(row=0, column=1, sticky=tk.E, padx=(10, 0))

        # Current time
        self.time_var = tk.StringVar()
        ttk.Label(status_frame, textvariable=self.time_var).grid(row=0, column=2, sticky=tk.E, padx=(10, 0))

        # Update time every second
        self.update_time()

    def update_time(self):
        """Update current time display"""
        try:
            # Check if root window still exists
            if not self.root.winfo_exists():
                self._time_update_id = None
                return

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.time_var.set(current_time)
            self._time_update_id = self.root.after(1000, self.update_time)
        except tk.TclError:
            # Window destroyed, don't schedule next update
            self._time_update_id = None
        except Exception:
            # Other error, don't schedule next update
            self._time_update_id = None

    def cancel_time_update(self):
        """Cancel the time update callback"""
        if self._time_update_id is not None:
            try:
                self.root.after_cancel(self._time_update_id)
            except tk.TclError:
                pass
            self._time_update_id = None

    def update_status(self, message, progress=None):
        """Update status bar message and progress"""
        self.status_var.set(message)
        if progress is not None:
            self.progress_var.set(progress)
        self.root.update_idletasks()

    def log_activity(self, message):
        """Log activity to the dashboard"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        activity_message = f"[{timestamp}] {message}\n"
        self.activity_text.insert(tk.END, activity_message)
        self.activity_text.see(tk.END)

    def return_to_main_menu(self):
        """Return to the main finance GUI by closing this window"""
        try:
            # Cancel any pending after() callbacks
            self.cancel_time_update()
            # Simply close this window - the parent Finance GUI should already be open
            self.root.destroy()
        except Exception as e:
            print(f"Error closing window: {e}")
            import traceback
            traceback.print_exc()

    def on_function_select(self, func_id):
        """Handle function button selection"""
        self.execute_function(func_id)

    def execute_function(self, func_id):
        """Execute selected function in background thread"""
        self.update_status(f"Executing {func_id}...")

        # Run in background thread to prevent GUI freezing
        thread = threading.Thread(target=self.run_function_background, args=(func_id,))
        thread.daemon = True
        thread.start()

    def return_to_home(self):
        """Return to the home page"""
        if self.auth:
            self.return_to_main_menu()
        else:
            messagebox.showinfo(_("common.info"), _("finance_reporting.messages.no_home_page"))

    def get_complete_function_mapping(self):
        """Complete mapping of all function IDs to their implementations"""
        return {
            # Advanced Analytics
            'advanced_forecasting': lambda: self.run_advanced_forecasting_updated(),
            'budget_variance': lambda: self.run_function_background_updated('budget_variance'),
            'realtime_dashboard': lambda: self.run_function_background_updated('realtime_dashboard'),
            'lifecycle_analysis': lambda: self.run_student_lifecycle_analysis(),

            # Predictive Analytics
            'payment_risk': lambda: self.run_risk_analysis_updated(),
            'anomaly_detection': lambda: self.run_anomaly_detection(),
            'cash_flow_forecast': lambda: self.run_cash_flow_forecasting(),
            'scenario_planning': lambda: self.run_scenario_planning(),

            # Monitoring & Alerts
            'alert_system': lambda: self.run_function_background_updated('alert_system'),
            'automated_reporting': lambda: self.run_automated_reporting_setup(),
            'performance_monitoring': lambda: self.run_system_performance_monitoring(),

            # Comparative Analysis
            'yoy_analysis': lambda: self.run_function_background_updated('yoy_analysis'),
            'department_comparison': lambda: self.run_function_background_updated('department_comparison'),
            'comparative_analysis': lambda: self.run_comparative_analysis(),
            'benchmarking': lambda: self.run_peer_benchmarking(),

            # Strategic Planning
            'payment_optimization': lambda: self.show_payment_optimization_dialog(),
            'collection_strategy': lambda: self.show_collection_strategy_dialog(),
            'scholarship_analysis': lambda: self.show_scholarship_analysis_dialog(),
            'revenue_optimization': lambda: self.show_revenue_optimization_dialog(),

            # Export & Integration
            'advanced_export': lambda: self.run_advanced_export(),
            'api_config': lambda: self.show_api_configuration_dialog(),
            'custom_reports': lambda: self.show_custom_report_builder(),

            # Compliance & Audit
            'compliance_audit': lambda: self.run_compliance_audit(),
            'data_quality': lambda: self.run_data_quality_assessment(),
            'regulatory_reporting': lambda: self.show_regulatory_reporting_dialog(),

            # System Management
            'ml_training': lambda: self.run_ml_model_training(),
            'performance_optimization': lambda: self.run_performance_optimization(),
            'archive_management': lambda: self.show_archive_management_dialog(),

            # Additional Missing Functions
            'payment_frequency_analysis': lambda: self.run_payment_frequency_analysis(),
            'enhanced_backup': lambda: self.run_enhanced_backup_system(),
            'system_info': lambda: self.show_enhanced_system_info(),
            'health_check': lambda: self.run_comprehensive_health_check(),
            'comprehensive_export': lambda: self.export_comprehensive_report()
        }


# Bind methods from dashboard_tab module
FinancialManagementGUI.create_dashboard_tab = dashboard_tab.create_dashboard_tab
FinancialManagementGUI.real_time_financial_dashboard = dashboard_tab.real_time_financial_dashboard
FinancialManagementGUI.update_dashboard_metrics = dashboard_tab.update_dashboard_metrics
FinancialManagementGUI.set_metric_values = dashboard_tab.set_metric_values
FinancialManagementGUI.refresh_dashboard = dashboard_tab.refresh_dashboard
FinancialManagementGUI.show_realtime_dashboard = dashboard_tab.show_realtime_dashboard

# Bind methods from analysis_tab module
FinancialManagementGUI.create_analysis_tab = analysis_tab.create_analysis_tab
FinancialManagementGUI.run_student_lifecycle_analysis = analysis_tab.run_student_lifecycle_analysis
FinancialManagementGUI.show_lifecycle_results = analysis_tab.show_lifecycle_results
FinancialManagementGUI.run_comparative_analysis = analysis_tab.run_comparative_analysis
FinancialManagementGUI.show_comparative_results = analysis_tab.show_comparative_results
FinancialManagementGUI.run_performance_optimization = analysis_tab.run_performance_optimization
FinancialManagementGUI.show_optimization_results = analysis_tab.show_optimization_results
FinancialManagementGUI.run_data_quality_assessment = analysis_tab.run_data_quality_assessment
FinancialManagementGUI.show_data_quality_results = analysis_tab.show_data_quality_results
FinancialManagementGUI.run_selected_analysis = analysis_tab.run_selected_analysis
FinancialManagementGUI.show_analysis_results_window = analysis_tab.show_analysis_results_window
FinancialManagementGUI.run_yoy_analysis = analysis_tab.run_yoy_analysis
FinancialManagementGUI.show_yoy_results = analysis_tab.show_yoy_results
FinancialManagementGUI.run_department_comparison = analysis_tab.run_department_comparison
FinancialManagementGUI.show_department_results = analysis_tab.show_department_results
FinancialManagementGUI.run_benchmarking_analysis = analysis_tab.run_benchmarking_analysis
FinancialManagementGUI.show_benchmarking_results = analysis_tab.show_benchmarking_results
FinancialManagementGUI.run_payment_frequency_analysis = analysis_tab.run_payment_frequency_analysis
FinancialManagementGUI.show_frequency_analysis_results = analysis_tab.show_frequency_analysis_results
FinancialManagementGUI.run_fee_structure_analysis = analysis_tab.run_fee_structure_analysis
FinancialManagementGUI.show_fee_structure_results = analysis_tab.show_fee_structure_results
FinancialManagementGUI.run_student_retention_analysis = analysis_tab.run_student_retention_analysis
FinancialManagementGUI.show_retention_analysis_results = analysis_tab.show_retention_analysis_results

# Bind methods from reports_tab module
FinancialManagementGUI.create_reports_tab = reports_tab.create_reports_tab
FinancialManagementGUI.generate_quick_report = reports_tab.generate_quick_report
FinancialManagementGUI.generate_selected_report = reports_tab.generate_selected_report
FinancialManagementGUI.show_custom_report_builder = reports_tab.show_custom_report_builder
FinancialManagementGUI.populate_scheduled_reports = reports_tab.populate_scheduled_reports
FinancialManagementGUI.export_quick_report = reports_tab.export_quick_report
FinancialManagementGUI._export_txt = reports_tab._export_txt
FinancialManagementGUI._export_csv = reports_tab._export_csv
FinancialManagementGUI._export_html = reports_tab._export_html
FinancialManagementGUI._export_excel = reports_tab._export_excel
FinancialManagementGUI._export_pdf = reports_tab._export_pdf
FinancialManagementGUI.export_comprehensive_report = reports_tab.export_comprehensive_report

# Bind methods from settings_tab module
FinancialManagementGUI.create_settings_tab = settings_tab.create_settings_tab
FinancialManagementGUI.browse_export_path = settings_tab.browse_export_path
FinancialManagementGUI.save_settings = settings_tab.save_settings
FinancialManagementGUI.load_settings = settings_tab.load_settings
FinancialManagementGUI.update_system_info = settings_tab.update_system_info

# Bind methods from advanced_features module
FinancialManagementGUI.generate_advanced_financial_forecasting = advanced_features.generate_advanced_financial_forecasting
FinancialManagementGUI.generate_comprehensive_budget_variance_report = advanced_features.generate_comprehensive_budget_variance_report
FinancialManagementGUI.scenario_planning_tools = advanced_features.scenario_planning_tools
FinancialManagementGUI.compliance_audit_system = advanced_features.compliance_audit_system
FinancialManagementGUI.run_function_background = advanced_features.run_function_background
FinancialManagementGUI.run_compliance_check = advanced_features.run_compliance_check
FinancialManagementGUI.run_advanced_forecasting = advanced_features.run_advanced_forecasting
FinancialManagementGUI.run_scenario_planning = advanced_features.run_scenario_planning
FinancialManagementGUI.run_compliance_audit = advanced_features.run_compliance_audit
FinancialManagementGUI.run_automated_reporting_setup = advanced_features.run_automated_reporting_setup
FinancialManagementGUI.run_advanced_export = advanced_features.run_advanced_export
FinancialManagementGUI.run_function_background_updated = advanced_features.run_function_background_updated
FinancialManagementGUI.run_advanced_forecasting_updated = advanced_features.run_advanced_forecasting_updated

# Bind methods from alerts_monitoring module
FinancialManagementGUI.show_alerts = alerts_monitoring.show_alerts
FinancialManagementGUI.run_alert_check = alerts_monitoring.run_alert_check
FinancialManagementGUI.show_system_health = alerts_monitoring.show_system_health
FinancialManagementGUI.run_background_health_check = alerts_monitoring.run_background_health_check
FinancialManagementGUI.show_alert_system_dialog = alerts_monitoring.show_alert_system_dialog
FinancialManagementGUI.show_performance_monitoring_dialog = alerts_monitoring.show_performance_monitoring_dialog
FinancialManagementGUI.run_comprehensive_health_check = alerts_monitoring.run_comprehensive_health_check
FinancialManagementGUI.run_system_performance_monitoring = alerts_monitoring.run_system_performance_monitoring
FinancialManagementGUI.start_performance_monitoring = alerts_monitoring.start_performance_monitoring
FinancialManagementGUI.stop_performance_monitoring = alerts_monitoring.stop_performance_monitoring
FinancialManagementGUI.export_monitoring_log = alerts_monitoring.export_monitoring_log

# Bind methods from ml_analytics module
FinancialManagementGUI.run_risk_analysis = ml_analytics.run_risk_analysis
FinancialManagementGUI.run_risk_analysis_updated = ml_analytics.run_risk_analysis  # Alias
FinancialManagementGUI.show_comprehensive_risk_results = ml_analytics.show_comprehensive_risk_results
FinancialManagementGUI.run_ml_model_training = ml_analytics.run_ml_model_training
FinancialManagementGUI.show_ml_training_results = ml_analytics.show_ml_training_results
FinancialManagementGUI.run_anomaly_detection = ml_analytics.run_anomaly_detection
FinancialManagementGUI.show_anomaly_results = ml_analytics.show_anomaly_results
FinancialManagementGUI.run_cash_flow_forecasting = ml_analytics.run_cash_flow_forecasting
FinancialManagementGUI.show_cash_flow_results = ml_analytics.show_cash_flow_results
FinancialManagementGUI.run_peer_benchmarking = ml_analytics.run_peer_benchmarking

# Bind methods from archive_backup module
FinancialManagementGUI.show_cli_report_in_window = archive_backup.show_cli_report_in_window
FinancialManagementGUI.show_chart_window = archive_backup.show_chart_window
FinancialManagementGUI.show_archive_management_dialog = archive_backup.show_archive_management_dialog
FinancialManagementGUI.create_archive_tables = archive_backup.create_archive_tables
FinancialManagementGUI.run_archive_process = archive_backup.run_archive_process
FinancialManagementGUI.create_database_backup = archive_backup.create_database_backup
FinancialManagementGUI.show_enhanced_system_info = archive_backup.show_enhanced_system_info
FinancialManagementGUI.populate_system_info = archive_backup.populate_system_info
FinancialManagementGUI.run_enhanced_backup_system = archive_backup.run_enhanced_backup_system

# Bind methods from feature_dialogs module
FinancialManagementGUI.show_payment_optimization_dialog = feature_dialogs.show_payment_optimization_dialog
FinancialManagementGUI.show_collection_strategy_dialog = feature_dialogs.show_collection_strategy_dialog
FinancialManagementGUI.show_scholarship_analysis_dialog = feature_dialogs.show_scholarship_analysis_dialog
FinancialManagementGUI.show_revenue_optimization_dialog = feature_dialogs.show_revenue_optimization_dialog
FinancialManagementGUI.show_api_configuration_dialog = feature_dialogs.show_api_configuration_dialog
FinancialManagementGUI.test_api_connection = feature_dialogs.test_api_connection
FinancialManagementGUI.show_regulatory_reporting_dialog = feature_dialogs.show_regulatory_reporting_dialog
FinancialManagementGUI.generate_regulatory_report = feature_dialogs.generate_regulatory_report
FinancialManagementGUI.save_report_to_file = feature_dialogs.save_report_to_file
FinancialManagementGUI.show_automated_reporting_dialog = feature_dialogs.show_automated_reporting_dialog
FinancialManagementGUI.show_advanced_export_dialog = feature_dialogs.show_advanced_export_dialog
FinancialManagementGUI.show_api_config_dialog = feature_dialogs.show_api_config_dialog
FinancialManagementGUI.show_custom_reports_dialog = feature_dialogs.show_custom_reports_dialog
FinancialManagementGUI.generate_regulatory_reports = feature_dialogs.generate_regulatory_reports
FinancialManagementGUI.show_regulatory_report = feature_dialogs.show_regulatory_report

# Register methods from misc module (done last to avoid circular imports)
register_misc_methods(FinancialManagementGUI)

