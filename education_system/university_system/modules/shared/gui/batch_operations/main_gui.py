"""
Batch Operations GUI - Main GUI Module

Contains the core BatchOperationsGUI class that creates the main interface
and delegates operations to specialized manager classes.
"""

import json
import queue
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from tkinter.ttk import Progressbar, Notebook

from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

from education_system.university_system.modules.shared.gui.batch_operations.constants import GUI_SETTINGS_PATH

# Import managers
from education_system.university_system.modules.shared.gui.batch_operations.import_manager import ImportManager
from education_system.university_system.modules.shared.gui.batch_operations.update_manager import UpdateManager
from education_system.university_system.modules.shared.gui.batch_operations.export_manager import ExportManager
from education_system.university_system.modules.shared.gui.batch_operations.report_manager import ReportManager
from education_system.university_system.modules.shared.gui.batch_operations.quality_manager import QualityManager
from education_system.university_system.modules.shared.gui.batch_operations.utility_manager import UtilityManager
from education_system.university_system.modules.shared.gui.batch_operations.automation_manager import AutomationManager
from education_system.university_system.modules.shared.gui.batch_operations.user_operations_manager import UserOperationsManager

# Import the enhanced batch operations class with GUI-specific methods
from education_system.university_system.modules.shared.gui.batch_operations.backend import EnhancedBatchOperationManager


class BatchOperationsGUI:
    """Main GUI application for batch operations"""

    def __init__(self, root=None, auth=None):
        self.root = root if root else tk.Tk()
        self.auth = auth  # Store authentication instance
        self.root.title(_t("batch_ops.title"))
        self.root.geometry("1200x800")

        # Initialize enhanced backend with GUI-specific methods
        self.backend = EnhancedBatchOperationManager()

        # Queue for thread communication
        self.message_queue = queue.Queue()

        # Style configuration
        self.setup_styles()

        # Initialize managers (composition pattern) - must happen before
        # create_main_interface() since it calls refresh_history() etc.
        self.import_mgr = ImportManager(self)
        self.update_mgr = UpdateManager(self)
        self.export_mgr = ExportManager(self)
        self.report_mgr = ReportManager(self)
        self.quality_mgr = QualityManager(self)
        self.utility_mgr = UtilityManager(self)
        self.automation_mgr = AutomationManager(self)
        self.user_ops_mgr = UserOperationsManager(self)

        # Create main interface
        self.create_main_interface()

        # Start queue processing
        self.process_queue()

    def show_import_results(self, result, operation_type="Import"):
        """Delegate to import manager's results dialog."""
        self.import_mgr.show_import_results(result, operation_type)

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Use the gui_launcher utility to avoid circular imports
            from education_system.university_system.modules.shared.gui.gui_launcher import return_to_main_menu
            return_to_main_menu(self, self.auth)
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def setup_styles(self):
        """Configure GUI styles"""
        style = ttk.Style()

        # Configure tab style
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))
        style.configure('Subheader.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Status.TLabel', font=('Arial', 10))

        # Configure button styles
        style.configure('Action.TButton', font=('Arial', 10, 'bold'))
        style.configure('Success.TButton', background='#28a745')
        style.configure('Warning.TButton', background='#ffc107')
        style.configure('Danger.TButton', background='#dc3545')

    def create_main_interface(self):
        """Create the main GUI interface"""
        # Main menu bar
        self.create_menu_bar()

        # Add return to main menu button at top right
        return_btn = ttk.Button(
            self.root,
            text=_t("batch_ops.buttons.return_main_menu"),
            command=self.return_to_main_menu
        )
        return_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

        # Main content area with tabs
        self.notebook = Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Create tabs for different operation categories
        self.create_import_tab()
        self.create_update_tab()
        self.create_export_tab()
        self.create_quality_tab()
        self.create_utilities_tab()
        self.create_automation_tab()
        self.create_user_operations_tab()
        self.create_history_tab()

        # Status bar
        self.create_status_bar()

    def create_menu_bar(self):
        """Create application menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("batch_ops.menu.file"), menu=file_menu)
        file_menu.add_command(label=_t("batch_ops.menu.new_import"), command=self.import_from_csv)
        file_menu.add_command(label=_t("batch_ops.menu.open_database"), command=self.open_database)
        file_menu.add_separator()
        file_menu.add_command(label=_t("batch_ops.menu.create_backup"), command=self.create_backup)
        file_menu.add_command(label=_t("batch_ops.menu.restore_backup"), command=self.restore_backup)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("batch_ops.menu.tools"), menu=tools_menu)
        tools_menu.add_command(label=_t("batch_ops.menu.generate_template"), command=self.generate_template)
        tools_menu.add_command(label=_t("batch_ops.menu.data_quality_check"), command=self.run_data_quality_check)
        tools_menu.add_command(label=_t("batch_ops.menu.find_duplicates"), command=self.find_duplicates)
        tools_menu.add_separator()
        tools_menu.add_command(label=_t("batch_ops.menu.command_line_mode"), command=self.open_command_line_mode)
        tools_menu.add_command(label=_t("batch_ops.menu.settings"), command=self.show_settings)
        tools_menu.add_command(label=_t("batch_ops.menu.system_status"), command=self.show_system_status)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("batch_ops.menu.view"), menu=view_menu)
        view_menu.add_command(label=_t("batch_ops.menu.dashboard"), command=self.show_dashboard)
        view_menu.add_command(label=_t("batch_ops.menu.import_history"), command=self.show_import_history)
        view_menu.add_command(label=_t("batch_ops.menu.system_logs"), command=self.show_system_logs)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("batch_ops.menu.help"), menu=help_menu)
        help_menu.add_command(label=_t("batch_ops.menu.user_guide"), command=self.show_user_guide)
        help_menu.add_command(label=_t("batch_ops.menu.about"), command=self.show_about)

    def create_import_tab(self):
        """Create import operations tab"""
        import_frame = ttk.Frame(self.notebook)
        self.notebook.add(import_frame, text=_t("batch_ops.tabs.import"))

        # Header
        header = ttk.Label(import_frame, text=_t("batch_ops.headers.import"), style='Header.TLabel')
        header.pack(pady=(10, 20))

        # Main content in scrollable frame
        canvas = tk.Canvas(import_frame)
        scrollbar = ttk.Scrollbar(import_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Import options in grid layout
        options = [
            (_t("batch_ops.import.csv_title"), _t("batch_ops.import.csv_desc"), self.import_from_csv),
            (_t("batch_ops.import.excel_title"), _t("batch_ops.import.excel_desc"), self.import_from_excel),
            (_t("batch_ops.import.multi_file_title"), _t("batch_ops.import.multi_file_desc"), self.multi_file_import),
            (_t("batch_ops.import.duplicate_title"), _t("batch_ops.import.duplicate_desc"), self.import_with_duplicates),
            (_t("batch_ops.import.preview_title"), _t("batch_ops.import.preview_desc"), self.preview_import),
            (_t("batch_ops.import.resume_title"), _t("batch_ops.import.resume_desc"), self.resume_import)
        ]

        for i, (title, description, command) in enumerate(options):
            self.create_option_card(scrollable_frame, title, description, command, row=i//2, column=i%2)

    def create_update_tab(self):
        """Create update operations tab"""
        update_frame = ttk.Frame(self.notebook)
        self.notebook.add(update_frame, text=_t("batch_ops.tabs.update"))

        # Header
        header = ttk.Label(update_frame, text=_t("batch_ops.headers.update"), style='Header.TLabel')
        header.pack(pady=(10, 20))

        # Content frame
        content_frame = ttk.Frame(update_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20)

        # Update options
        options = [
            (_t("batch_ops.update.batch_title"), _t("batch_ops.update.batch_desc"), self.batch_update_records),
            (_t("batch_ops.update.module_title"), _t("batch_ops.update.module_desc"), self.bulk_module_operations),
            (_t("batch_ops.update.grade_title"), _t("batch_ops.update.grade_desc"), self.import_grade_data)
        ]

        for i, (title, description, command) in enumerate(options):
            self.create_option_card(content_frame, title, description, command, row=i//2, column=i%2)

    def create_export_tab(self):
        """Create export operations tab"""
        export_frame = ttk.Frame(self.notebook)
        self.notebook.add(export_frame, text=_t("batch_ops.tabs.export"))

        # Header
        header = ttk.Label(export_frame, text=_t("batch_ops.headers.export"), style='Header.TLabel')
        header.pack(pady=(10, 20))

        # Content frame
        content_frame = ttk.Frame(export_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20)

        # Export options
        options = [
            (_t("batch_ops.export.students_title"), _t("batch_ops.export.students_desc"), self.export_students),
            (_t("batch_ops.export.statistics_title"), _t("batch_ops.export.statistics_desc"), self.export_statistics),
            (_t("batch_ops.export.reports_title"), _t("batch_ops.export.reports_desc"), self.generate_reports)
        ]

        for i, (title, description, command) in enumerate(options):
            self.create_option_card(content_frame, title, description, command, row=i//2, column=i%2)

    def create_quality_tab(self):
        """Create data quality tab"""
        quality_frame = ttk.Frame(self.notebook)
        self.notebook.add(quality_frame, text=_t("batch_ops.tabs.quality"))

        # Header
        header = ttk.Label(quality_frame, text=_t("batch_ops.headers.quality"), style='Header.TLabel')
        header.pack(pady=(10, 20))

        # Split into two sections
        left_frame = ttk.LabelFrame(quality_frame, text=_t("batch_ops.quality.analysis_tools"), padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(20, 10), pady=10)

        right_frame = ttk.LabelFrame(quality_frame, text=_t("batch_ops.quality.dashboard"), padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 20), pady=10)

        # Analysis tools
        analysis_options = [
            (_t("batch_ops.quality.validate_data"), self.validate_data),
            (_t("batch_ops.quality.find_duplicates"), self.find_duplicates),
            (_t("batch_ops.quality.clean_data"), self.clean_data),
            (_t("batch_ops.buttons.return_main_menu"), self.return_to_main_menu)
        ]

        for i, (title, command) in enumerate(analysis_options):
            btn = ttk.Button(left_frame, text=title, command=command, style='Action.TButton')
            btn.pack(fill=tk.X, pady=5)

        # Quality dashboard
        self.quality_text = scrolledtext.ScrolledText(right_frame, height=20, width=50)
        self.quality_text.pack(fill=tk.BOTH, expand=True)

        # Refresh button
        refresh_btn = ttk.Button(right_frame, text=_t("batch_ops.buttons.refresh_dashboard"), command=self.refresh_quality_dashboard)
        refresh_btn.pack(pady=(10, 0))

    def create_utilities_tab(self):
        """Create utilities tab"""
        utilities_frame = ttk.Frame(self.notebook)
        self.notebook.add(utilities_frame, text=_t("batch_ops.tabs.utilities"))

        # Header
        header = ttk.Label(utilities_frame, text=_t("batch_ops.headers.utilities"), style='Header.TLabel')
        header.pack(pady=(10, 20))

        # Content frame
        content_frame = ttk.Frame(utilities_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20)

        # Utilities options
        options = [
            (_t("batch_ops.utilities.template_title"), _t("batch_ops.utilities.template_desc"), self.generate_template),
            (_t("batch_ops.utilities.backup_title"), _t("batch_ops.utilities.backup_desc"), self.create_backup),
            (_t("batch_ops.utilities.undo_title"), _t("batch_ops.utilities.undo_desc"), self.undo_import),
            (_t("batch_ops.utilities.settings_title"), _t("batch_ops.utilities.settings_desc"), self.show_settings)
        ]

        for i, (title, description, command) in enumerate(options):
            self.create_option_card(content_frame, title, description, command, row=i//2, column=i%2)

    def create_automation_tab(self):
        """Create automation tab"""
        automation_frame = ttk.Frame(self.notebook)
        self.notebook.add(automation_frame, text=_t("batch_ops.tabs.automation"))

        # Header
        header = ttk.Label(automation_frame, text=_t("batch_ops.headers.automation"), style='Header.TLabel')
        header.pack(pady=(10, 20))

        # Content in two columns
        left_frame = ttk.LabelFrame(automation_frame, text=_t("batch_ops.automation.scheduled_tasks"), padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(20, 10), pady=10)

        right_frame = ttk.LabelFrame(automation_frame, text=_t("batch_ops.automation.api_integration"), padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 20), pady=10)

        # Scheduled tasks
        schedule_options = [
            (_t("batch_ops.automation.schedule_daily"), self.schedule_daily_import),
            (_t("batch_ops.automation.schedule_weekly"), self.schedule_weekly_report),
            (_t("batch_ops.automation.view_scheduled"), self.view_scheduled_tasks),
            (_t("batch_ops.buttons.return_main_menu"), self.return_to_main_menu)
        ]

        for title, command in schedule_options:
            btn = ttk.Button(left_frame, text=title, command=command)
            btn.pack(fill=tk.X, pady=5)

        # API and integration
        api_options = [
            (_t("batch_ops.automation.start_api"), self.start_api_server),
            (_t("batch_ops.automation.external_db"), self.setup_external_db),
            (_t("batch_ops.automation.rest_api"), self.setup_rest_api),
            (_t("batch_ops.buttons.return_main_menu"), self.return_to_main_menu)
        ]

        for title, command in api_options:
            btn = ttk.Button(right_frame, text=title, command=command)
            btn.pack(fill=tk.X, pady=5)

        # Status display
        self.automation_status = scrolledtext.ScrolledText(automation_frame, height=10)
        self.automation_status.pack(fill=tk.X, padx=20, pady=10)

    def create_user_operations_tab(self):
        """Create user operations tab for bulk user management"""
        user_ops_frame = ttk.Frame(self.notebook)
        self.notebook.add(user_ops_frame, text="User Operations")

        header = ttk.Label(user_ops_frame, text="Batch User Operations",
                           style='Header.TLabel')
        header.pack(pady=(10, 20))

        content_frame = ttk.Frame(user_ops_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20)

        options = [
            ("Bulk User Creation",
             "Create multiple user accounts from a CSV file with automatic role assignment.",
             self.bulk_create_users),
            ("Bulk Permission Updates",
             "Grant or revoke permissions for users by role or from a CSV list.",
             self.bulk_permission_update),
            ("Batch Course Enrollment",
             "Enroll multiple students in courses from a CSV file.",
             self.batch_course_enrollment),
            ("Send Email Campaign",
             "Send targeted email campaigns to all users or segments via the email system.",
             self.batch_email_campaign),
        ]

        for i, (title, description, command) in enumerate(options):
            self.create_option_card(content_frame, title, description, command,
                                    row=i // 2, column=i % 2)

    def create_history_tab(self):
        """Create import history tab"""
        history_frame = ttk.Frame(self.notebook)
        self.notebook.add(history_frame, text=_t("batch_ops.tabs.history"))

        # Header
        header = ttk.Label(history_frame, text=_t("batch_ops.headers.history"), style='Header.TLabel')
        header.pack(pady=(10, 20))

        # Control frame
        control_frame = ttk.Frame(history_frame)
        control_frame.pack(fill=tk.X, padx=20, pady=10)

        # Filter controls
        ttk.Label(control_frame, text=_t("batch_ops.history.filter_by")).pack(side=tk.LEFT, padx=(0, 10))

        self.history_filter = ttk.Combobox(control_frame, values=[_t("batch_ops.history.all"), _t("batch_ops.history.imports"), _t("batch_ops.history.updates"), _t("batch_ops.history.exports")], state="readonly")
        self.history_filter.set(_t("batch_ops.history.all"))
        self.history_filter.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(control_frame, text=_t("batch_ops.buttons.refresh"), command=self.refresh_history).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(control_frame, text=_t("batch_ops.history.export_history"), command=self.export_history).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(control_frame, text=_t("batch_ops.history.clear_history"), command=self.clear_history).pack(side=tk.LEFT)

        # History display
        self.history_tree = ttk.Treeview(history_frame, columns=("timestamp", "operation", "records", "success", "errors"), show="headings")

        # Configure columns
        self.history_tree.heading("timestamp", text=_t("batch_ops.history.date_time"))
        self.history_tree.heading("operation", text=_t("batch_ops.history.operation"))
        self.history_tree.heading("records", text=_t("batch_ops.history.records"))
        self.history_tree.heading("success", text=_t("batch_ops.history.success"))
        self.history_tree.heading("errors", text=_t("batch_ops.history.errors"))

        self.history_tree.column("timestamp", width=150)
        self.history_tree.column("operation", width=200)
        self.history_tree.column("records", width=100)
        self.history_tree.column("success", width=100)
        self.history_tree.column("errors", width=100)

        # Scrollbar for history
        history_scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=history_scrollbar.set)

        self.history_tree.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=10)
        history_scrollbar.pack(side="right", fill="y", padx=(0, 20), pady=10)

        # Load initial history
        self.refresh_history()

    def create_status_bar(self):
        """Create status bar at bottom of window"""
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # Status label
        self.status_label = ttk.Label(self.status_frame, text=_t("batch_ops.status.ready"), style='Status.TLabel')
        self.status_label.pack(side=tk.LEFT, padx=10, pady=5)

        # Progress bar (hidden by default)
        self.main_progress = Progressbar(self.status_frame, length=200)

        # Database status
        self.db_status_label = ttk.Label(self.status_frame, text=_t("batch_ops.status.db_connected"), style='Status.TLabel')
        self.db_status_label.pack(side=tk.RIGHT, padx=10, pady=5)

        # Navigation back to the main system
        exit_button = ttk.Button(
            self.status_frame,
            text=_t("batch_ops.buttons.return_main_menu"),
            command=self.return_to_main_menu
        )
        exit_button.pack(side=tk.RIGHT, padx=10, pady=5)

    def create_option_card(self, parent, title, description, command, row, column):
        """Create an option card widget"""
        card_frame = ttk.LabelFrame(parent, text=title, padding="10")
        card_frame.grid(row=row, column=column, padx=10, pady=10, sticky="ew")

        # Configure column weights
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)

        # Description
        desc_label = ttk.Label(card_frame, text=description, wraplength=250)
        desc_label.pack(pady=(0, 10))

        # Action button
        action_btn = ttk.Button(card_frame, text=_t("batch_ops.buttons.execute"), command=command, style='Action.TButton')
        action_btn.pack()

    def update_status(self, message):
        """Update status bar message"""
        self.status_label.config(text=message)
        self.root.update_idletasks()

    def show_progress(self):
        """Show progress bar in status bar"""
        self.main_progress.pack(side=tk.RIGHT, padx=(0, 10), pady=5)

    def hide_progress(self):
        """Hide progress bar in status bar"""
        self.main_progress.pack_forget()

    def process_queue(self):
        """Process messages from worker threads"""
        try:
            while True:
                message = self.message_queue.get_nowait()
                # Process different types of messages
                if message['type'] == 'status':
                    self.update_status(message['text'])
                elif message['type'] == 'progress':
                    # Handle progress updates - update progress bar and status
                    current = message.get('current', 0)
                    total = message.get('total', 100)
                    text = message.get('text', '')

                    # Ensure progress bar is visible
                    if not self.main_progress.winfo_ismapped():
                        self.show_progress()

                    # Update progress bar value (calculate percentage)
                    if total > 0:
                        percentage = (current / total) * 100
                        self.main_progress['value'] = percentage

                        # Update status with progress info
                        if text:
                            self.update_status(f"{text} ({current}/{total} - {percentage:.1f}%)")
                        else:
                            self.update_status(f"Processing: {current}/{total} ({percentage:.1f}%)")
                    else:
                        # Indeterminate progress
                        self.main_progress['mode'] = 'indeterminate'
                        self.main_progress.start(10)
                        if text:
                            self.update_status(text)
                elif message['type'] == 'complete':
                    self.hide_progress()
                    # Reset progress bar
                    self.main_progress['value'] = 0
                    self.main_progress['mode'] = 'determinate'
                    self.main_progress.stop()
                    messagebox.showinfo(_t("batch_ops.dialogs.complete"), message['text'])
                elif message['type'] == 'error':
                    self.hide_progress()
                    # Reset progress bar
                    self.main_progress['value'] = 0
                    self.main_progress['mode'] = 'determinate'
                    self.main_progress.stop()
                    messagebox.showerror(_t("batch_ops.dialogs.error"), message['text'])
        except queue.Empty:
            # No messages in queue - this is expected, not an error
            # Simply continue to schedule the next check
            pass

        # Schedule next check
        self.root.after(100, self.process_queue)

    def run(self):
        """Start the GUI application"""
        # Load settings if available
        try:
            with open(GUI_SETTINGS_PATH, 'r') as f:
                settings = json.load(f)
                self.backend.db_path = settings.get('db_path', str(DEFAULT_DB_PATH))
                self.backend.backup_dir = settings.get('backup_dir', 'backups')
        except FileNotFoundError:
            pass

        # Initialize displays
        self.refresh_quality_dashboard()
        self.refresh_history()
        self.update_automation_status()

        # Start the main event loop
        self.root.mainloop()

    # =========================================================================
    # Delegation methods - Import operations (delegate to import_mgr)
    # =========================================================================

    def import_from_csv(self):
        """Import student data from CSV file"""
        return self.import_mgr.import_from_csv()

    def import_from_excel(self):
        """Import student data from Excel file"""
        return self.import_mgr.import_from_excel()

    def multi_file_import(self):
        """Import data from multiple files"""
        return self.import_mgr.multi_file_import()

    def import_with_duplicates(self):
        """Import data with duplicate handling"""
        return self.import_mgr.import_with_duplicates()

    def preview_import(self):
        """Preview import data before committing"""
        return self.import_mgr.preview_import()

    def resume_import(self):
        """Resume a previously interrupted import"""
        return self.import_mgr.resume_import()

    # =========================================================================
    # Delegation methods - Update operations (delegate to update_mgr)
    # =========================================================================

    def batch_update_records(self):
        """Batch update existing records"""
        return self.update_mgr.batch_update_records()

    def bulk_module_operations(self):
        """Perform bulk module operations"""
        return self.update_mgr.bulk_module_operations()

    def import_grade_data(self):
        """Import grade data in bulk"""
        return self.update_mgr.import_grade_data()

    # =========================================================================
    # Delegation methods - Export operations (delegate to export_mgr)
    # =========================================================================

    def export_students(self):
        """Export student data"""
        return self.export_mgr.export_students()

    def export_statistics(self):
        """Export enrollment statistics"""
        return self.export_mgr.export_statistics()

    def generate_reports(self):
        """Generate batch reports"""
        return self.export_mgr.generate_reports()

    # =========================================================================
    # Delegation methods - Quality operations (delegate to quality_mgr)
    # =========================================================================

    def validate_data(self):
        """Validate data integrity"""
        return self.quality_mgr.validate_data()

    def find_duplicates(self):
        """Find duplicate records"""
        return self.quality_mgr.find_duplicates()

    def clean_data(self):
        """Clean and normalize data"""
        return self.quality_mgr.clean_data()

    def refresh_quality_dashboard(self):
        """Refresh the quality dashboard display"""
        return self.quality_mgr.refresh_quality_dashboard()

    # =========================================================================
    # Delegation methods - Utility operations (delegate to utility_mgr)
    # =========================================================================

    def generate_template(self):
        """Generate import template file"""
        return self.utility_mgr.generate_template()

    def create_backup(self):
        """Create database backup"""
        return self.utility_mgr.create_backup()

    def restore_backup(self):
        """Restore database from backup"""
        return self.utility_mgr.restore_backup()

    def undo_import(self):
        """Undo the last import operation"""
        return self.utility_mgr.undo_import()

    def show_settings(self):
        """Show application settings"""
        return self.utility_mgr.show_settings()

    def open_database(self):
        """Open a database file"""
        return self.utility_mgr.open_database()

    def open_command_line_mode(self):
        """Open command line mode"""
        return self.utility_mgr.open_command_line_mode()

    def show_system_logs(self):
        """Show system logs"""
        return self.utility_mgr.show_system_logs()

    def show_user_guide(self):
        """Show user guide"""
        return self.utility_mgr.show_user_guide()

    def show_about(self):
        """Show about dialog"""
        return self.utility_mgr.show_about()

    def show_system_status(self):
        """Show system status dialog"""
        return self.utility_mgr.show_system_status()

    # =========================================================================
    # Delegation methods - Automation operations (delegate to automation_mgr)
    # =========================================================================

    def schedule_daily_import(self):
        """Schedule a daily import task"""
        return self.automation_mgr.schedule_daily_import()

    def schedule_weekly_report(self):
        """Schedule a weekly report task"""
        return self.automation_mgr.schedule_weekly_report()

    def view_scheduled_tasks(self):
        """View all scheduled tasks"""
        return self.automation_mgr.view_scheduled_tasks()

    def start_api_server(self):
        """Start the API server"""
        return self.automation_mgr.start_api_server()

    def setup_external_db(self):
        """Setup external database connection"""
        return self.automation_mgr.setup_external_db()

    def setup_rest_api(self):
        """Setup REST API integration"""
        return self.automation_mgr.setup_rest_api()

    def test_connections(self):
        """Test external connections"""
        return self.automation_mgr.test_connections()

    # =========================================================================
    # Delegation methods - Report/view operations (delegate to report_mgr)
    # =========================================================================

    def run_data_quality_check(self):
        """Run a data quality check"""
        return self.report_mgr.run_data_quality_check()

    def show_dashboard(self):
        """Show the dashboard"""
        return self.report_mgr.show_dashboard()

    def show_import_history(self):
        """Show import history"""
        return self.report_mgr.show_import_history()

    def export_history(self):
        """Export operation history"""
        return self.report_mgr.export_history()

    def clear_history(self):
        """Clear operation history"""
        return self.report_mgr.clear_history()

    def refresh_history(self):
        """Refresh the history display"""
        return self.report_mgr.refresh_history()

    def update_automation_status(self):
        """Update the automation status display"""
        return self.report_mgr.update_automation_status()

    def get_quality_dashboard_data(self):
        """Get quality dashboard data"""
        return self.report_mgr.get_quality_dashboard_data()

    def generate_template_file(self):
        """Generate a template file"""
        return self.report_mgr.generate_template_file()

    def generate_enrollment_statistics(self):
        """Generate enrollment statistics"""
        return self.report_mgr.generate_enrollment_statistics()

    def export_students_to_file(self):
        """Export students to a file"""
        return self.report_mgr.export_students_to_file()

    def generate_success_rate_report(self):
        """Generate success rate report"""
        return self.report_mgr.generate_success_rate_report()

    def generate_error_analysis_report(self):
        """Generate error analysis report"""
        return self.report_mgr.generate_error_analysis_report()

    def generate_performance_report(self):
        """Generate performance report"""
        return self.report_mgr.generate_performance_report()

    def generate_comprehensive_report(self):
        """Generate comprehensive report"""
        return self.report_mgr.generate_comprehensive_report()

    def show_connection_test_results(self):
        """Show connection test results"""
        return self.report_mgr.show_connection_test_results()

    # =========================================================================
    # Delegation methods - User operations (delegate to user_ops_mgr)
    # =========================================================================

    def bulk_create_users(self):
        """Bulk create users from CSV"""
        return self.user_ops_mgr.bulk_create_users()

    def bulk_permission_update(self):
        """Bulk update permissions"""
        return self.user_ops_mgr.bulk_permission_update()

    def batch_course_enrollment(self):
        """Batch enroll students in courses"""
        return self.user_ops_mgr.batch_course_enrollment()

    def batch_email_campaign(self):
        """Send batch email campaign"""
        return self.user_ops_mgr.batch_email_campaign()
