# main_gui.py
# Main AccommodationGUI class that combines all mixins and provides
# the core interface (init, menu, tab creation, status bar, refresh).

from education_system.university_system.modules.domain.health.gui.medical_accommodation._common import (
    tk, ttk, messagebox,
    ScrolledText, datetime, sqlite3,
    init_i18n, _t,
    CLI_AVAILABLE, TEMPLATES_TABLE, get_connection,
)

if CLI_AVAILABLE:
    from education_system.university_system.modules.domain.health.gui.medical_accommodation._common import (
        init_accommodation_db, set_auth, get_accommodation_types,
        auth, log_action, cli_notify_student,
    )

# Import mixins
from education_system.university_system.modules.domain.health.gui.medical_accommodation.search import SearchMixin
from education_system.university_system.modules.domain.health.gui.medical_accommodation.import_export import ImportExportMixin
from education_system.university_system.modules.domain.health.gui.medical_accommodation.approval import ApprovalMixin
from education_system.university_system.modules.domain.health.gui.medical_accommodation.templates import TemplateMixin
from education_system.university_system.modules.domain.health.gui.medical_accommodation.dashboard import DashboardMixin
from education_system.university_system.modules.domain.health.gui.medical_accommodation.accommodations import AccommodationCRUDMixin
from education_system.university_system.modules.domain.health.gui.medical_accommodation.cli_integration import CliIntegrationMixin

# Import dialogs used directly by the main class
from education_system.university_system.modules.domain.health.gui.medical_accommodation.dialogs.document_upload import DocumentUploadDialog
from education_system.university_system.modules.domain.health.gui.medical_accommodation.dialogs.database_info import DatabaseInfoDialog
from education_system.university_system.modules.domain.health.gui.medical_accommodation.dialogs.settings import SettingsDialog
from education_system.university_system.modules.domain.health.gui.medical_accommodation.dialogs.help import HelpDialog
from education_system.university_system.modules.domain.health.gui.medical_accommodation.bulk_operations import BulkOperationsDialog


class AccommodationGUI(
    SearchMixin,
    ImportExportMixin,
    ApprovalMixin,
    TemplateMixin,
    DashboardMixin,
    AccommodationCRUDMixin,
    CliIntegrationMixin,
):
    def __init__(self, root, auth=None):
        # Initialize i18n for language support
        init_i18n()

        self.root = root
        self.root.title(_t("medical_accommodation.title"))
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')

        # Store authentication instance
        self.auth = auth
        self.current_user = None

        # Get current user from auth if available
        if self.auth and hasattr(self.auth, 'current_user'):
            self.current_user = self.auth.current_user
            if self.current_user:
                print(f"\u2713 Accommodation GUI: Using authenticated user {self.current_user.get('username', 'Unknown')} ({self.current_user.get('role', 'user')})")

        # Initialize the database
        if CLI_AVAILABLE:
            init_accommodation_db()
            if self.auth:
                set_auth(self.auth)

        # Create the main interface
        self.create_menu()
        self.create_main_interface()
        self.create_status_bar()

        # Load initial data
        self.refresh_data()

    # --- Menu ---

    def create_menu(self):
        """Create the main menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("medical_accommodation.menu.file"), menu=file_menu)
        file_menu.add_command(label=_t("medical_accommodation.menu.import_csv"), command=self.import_csv)
        file_menu.add_command(label=_t("medical_accommodation.menu.import_json"), command=self.import_json)
        file_menu.add_separator()
        file_menu.add_command(label=_t("medical_accommodation.menu.export_csv"), command=self.export_csv)
        file_menu.add_command(label=_t("medical_accommodation.menu.export_excel"), command=self.export_excel)
        file_menu.add_command(label=_t("medical_accommodation.menu.export_pdf"), command=self.export_pdf)
        file_menu.add_command(label=_t("medical_accommodation.menu.export_json"), command=self.export_json)
        file_menu.add_separator()
        file_menu.add_command(label=_t("medical_accommodation.menu.exit"), command=self.root.quit)

        # Accommodation menu
        accom_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("medical_accommodation.menu.accommodations"), menu=accom_menu)
        accom_menu.add_command(label=_t("medical_accommodation.menu.add_new"), command=self.add_accommodation_dialog)
        accom_menu.add_command(label=_t("medical_accommodation.menu.update_selected"), command=self.update_accommodation_dialog)
        accom_menu.add_command(label=_t("medical_accommodation.menu.remove_selected"), command=self.remove_accommodation_dialog)
        accom_menu.add_separator()
        accom_menu.add_command(label=_t("medical_accommodation.menu.approve_reject"), command=self.approve_accommodation_dialog)

        # Templates menu
        template_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("medical_accommodation.menu.templates"), menu=template_menu)
        template_menu.add_command(label=_t("medical_accommodation.menu.save_template"), command=self.save_template_dialog)
        template_menu.add_command(label=_t("medical_accommodation.menu.apply_template"), command=self.apply_template_dialog)
        template_menu.add_command(label=_t("medical_accommodation.menu.manage_templates"), command=self.manage_templates_dialog)

        # Reports menu
        reports_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("medical_accommodation.menu.reports"), menu=reports_menu)
        reports_menu.add_command(label=_t("medical_accommodation.menu.dashboard"), command=self.show_dashboard)
        reports_menu.add_command(label=_t("medical_accommodation.menu.statistics"), command=self.generate_statistics)
        reports_menu.add_command(label=_t("medical_accommodation.menu.view_by_type"), command=self.view_students_by_accommodation_type)
        reports_menu.add_command(label=_t("medical_accommodation.menu.expiry_check"), command=self.check_expiry)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("medical_accommodation.menu.tools"), menu=tools_menu)
        tools_menu.add_command(label=_t("medical_accommodation.menu.cli_mode"), command=self.launch_cli)
        tools_menu.add_command(label=_t("medical_accommodation.menu.db_info"), command=self.show_db_info)
        tools_menu.add_command(label=_t("medical_accommodation.menu.settings"), command=self.show_settings)
        tools_menu.add_command(label=_t("medical_accommodation.menu.upload_doc"), command=self.upload_document_dialog)
        tools_menu.add_command(label=_t("medical_accommodation.menu.bulk_ops"), command=self.bulk_operations_dialog)
        tools_menu.add_command(label=_t("medical_accommodation.menu.template_stats"), command=self.show_templates_usage_dialog)
        tools_menu.add_command(label=_t("medical_accommodation.menu.migrate_db"), command=self.migrate_database_schema)
        tools_menu.add_command(label=_t("medical_accommodation.menu.verify_schema"), command=self.verify_db_schema)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("medical_accommodation.menu.help"), menu=help_menu)
        help_menu.add_command(label=_t("medical_accommodation.menu.user_guide"), command=self.show_help)
        help_menu.add_command(label=_t("medical_accommodation.menu.about"), command=self.show_about)

    # --- Main Interface ---

    def create_main_interface(self):
        """Create the main interface with tabs"""
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=10, pady=(5, 0))
        ttk.Button(toolbar, text=_t("medical_accommodation.btn.return_main"), command=self.close_to_main_menu).pack(side=tk.LEFT)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.create_accommodations_tab()
        self.create_search_tab()
        self.create_dashboard_tab()
        self.create_templates_tab()

    def close_to_main_menu(self):
        """Close this window so users return to the main launcher."""
        try:
            self.root.destroy()
        except Exception:
            self.root.quit()

    def create_accommodations_tab(self):
        """Create the main accommodations management tab"""
        self.accom_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.accom_frame, text=_t("medical_accommodation.tabs.accommodations"))

        button_frame = ttk.Frame(self.accom_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(button_frame, text="Add New",
                  command=self.add_accommodation_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Update",
                  command=self.update_accommodation_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Remove",
                  command=self.remove_accommodation_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="View Details",
                  command=self.view_accommodation_details).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Refresh",
                  command=self.refresh_data).pack(side=tk.LEFT, padx=2)

        ttk.Separator(button_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=5, fill=tk.Y)
        ttk.Button(button_frame, text="Approve",
                  command=self.approve_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Reject",
                  command=self.reject_selected).pack(side=tk.LEFT, padx=2)

        tree_frame = ttk.Frame(self.accom_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.accom_tree = ttk.Treeview(tree_frame, columns=(
            'ID', 'Student ID', 'Name', 'Type', 'Start Date', 'End Date', 'Status'
        ), show='headings')

        columns = {
            'ID': 50, 'Student ID': 100, 'Name': 150, 'Type': 150,
            'Start Date': 100, 'End Date': 100, 'Status': 80
        }

        for col, width in columns.items():
            self.accom_tree.heading(col, text=col)
            self.accom_tree.column(col, width=width, minwidth=50)

        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.accom_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.accom_tree.xview)
        self.accom_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        self.accom_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.accom_tree.bind('<Double-1>', self.on_accommodation_double_click)

    def create_search_tab(self):
        """Create the search and filter tab"""
        self.search_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.search_frame, text=_t("medical_accommodation.tabs.search"))

        criteria_frame = ttk.LabelFrame(self.search_frame, text="Search Criteria")
        criteria_frame.pack(fill=tk.X, padx=10, pady=5)

        row1 = ttk.Frame(criteria_frame)
        row1.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(row1, text="Student ID:").pack(side=tk.LEFT)
        self.search_student_id = ttk.Entry(row1, width=15)
        self.search_student_id.pack(side=tk.LEFT, padx=5)

        ttk.Label(row1, text="Type:").pack(side=tk.LEFT, padx=(20,0))
        self.search_type = ttk.Combobox(row1, width=20)
        self.search_type.pack(side=tk.LEFT, padx=5)

        ttk.Label(row1, text="Status:").pack(side=tk.LEFT, padx=(20,0))
        self.search_status = ttk.Combobox(row1, values=['', 'active', 'pending', 'suspended', 'expired'])
        self.search_status.pack(side=tk.LEFT, padx=5)

        row2 = ttk.Frame(criteria_frame)
        row2.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(row2, text="Start Date >=:").pack(side=tk.LEFT)
        self.search_start_date = ttk.Entry(row2, width=12)
        self.search_start_date.pack(side=tk.LEFT, padx=5)

        ttk.Label(row2, text="End Date <=:").pack(side=tk.LEFT, padx=(20,0))
        self.search_end_date = ttk.Entry(row2, width=12)
        self.search_end_date.pack(side=tk.LEFT, padx=5)

        ttk.Label(row2, text="Keyword:").pack(side=tk.LEFT, padx=(20,0))
        self.search_keyword = ttk.Entry(row2, width=20)
        self.search_keyword.pack(side=tk.LEFT, padx=5)

        button_row = ttk.Frame(criteria_frame)
        button_row.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(button_row, text="Search", command=self.perform_search).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_row, text="Clear", command=self.clear_search).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_row, text="Show All", command=self.refresh_data).pack(side=tk.LEFT, padx=2)

        results_frame = ttk.LabelFrame(self.search_frame, text="Search Results")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.search_tree = ttk.Treeview(results_frame, columns=(
            'ID', 'Student ID', 'Name', 'Type', 'Start Date', 'End Date', 'Status', 'Description'
        ), show='headings')

        search_columns = {
            'ID': 50, 'Student ID': 100, 'Name': 120, 'Type': 120,
            'Start Date': 90, 'End Date': 90, 'Status': 70, 'Description': 150
        }

        for col, width in search_columns.items():
            self.search_tree.heading(col, text=col)
            self.search_tree.column(col, width=width, minwidth=50)

        search_v_scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.search_tree.yview)
        search_h_scrollbar = ttk.Scrollbar(results_frame, orient=tk.HORIZONTAL, command=self.search_tree.xview)
        self.search_tree.configure(yscrollcommand=search_v_scrollbar.set, xscrollcommand=search_h_scrollbar.set)

        self.search_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        search_v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        search_h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

    def create_dashboard_tab(self):
        """Create the dashboard tab"""
        self.dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.dashboard_frame, text=_t("medical_accommodation.tabs.dashboard"))

        metrics_frame = ttk.LabelFrame(self.dashboard_frame, text="Key Metrics")
        metrics_frame.pack(fill=tk.X, padx=10, pady=5)

        self.metrics_vars = {}
        metrics_grid = ttk.Frame(metrics_frame)
        metrics_grid.pack(fill=tk.X, padx=10, pady=10)

        metrics = [
            ('Total Accommodations', 'total'),
            ('Active', 'active'),
            ('Pending', 'pending'),
            ('Expired', 'expired'),
            ('This Month', 'this_month'),
            ('Expiring Soon', 'expiring_soon')
        ]

        for i, (label, key) in enumerate(metrics):
            row = i // 3
            col = i % 3

            frame = ttk.Frame(metrics_grid)
            frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')

            ttk.Label(frame, text=label, font=('Arial', 10, 'bold')).pack()
            self.metrics_vars[key] = tk.StringVar(value="0")
            ttk.Label(frame, textvariable=self.metrics_vars[key],
                     font=('Arial', 14)).pack()

        for i in range(3):
            metrics_grid.columnconfigure(i, weight=1)

        charts_frame = ttk.LabelFrame(self.dashboard_frame, text="Statistics")
        charts_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.stats_text = ScrolledText(charts_frame, height=15, width=80)
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Button(self.dashboard_frame, text="Refresh Dashboard",
                  command=self.refresh_dashboard).pack(pady=5)

    def create_templates_tab(self):
        """Create the templates management tab"""
        self.templates_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.templates_frame, text=_t("medical_accommodation.tabs.templates"))

        template_buttons = ttk.Frame(self.templates_frame)
        template_buttons.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(template_buttons, text="Create Template",
                  command=self.save_template_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(template_buttons, text="Apply Template",
                  command=self.apply_template_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(template_buttons, text="Edit Template",
                  command=self.edit_template_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(template_buttons, text="Delete Template",
                  command=self.delete_template_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(template_buttons, text="Import Medical Templates",
                  command=self.import_medical_templates).pack(side=tk.LEFT, padx=2)
        ttk.Button(template_buttons, text="Refresh",
                  command=self.refresh_templates).pack(side=tk.LEFT, padx=2)

        templates_list_frame = ttk.Frame(self.templates_frame)
        templates_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.templates_tree = ttk.Treeview(templates_list_frame, columns=(
            'Name', 'Type', 'Description', 'Duration', 'Created By', 'Created At'
        ), show='headings')

        template_columns = {
            'Name': 150, 'Type': 150, 'Description': 200,
            'Duration': 100, 'Created By': 100, 'Created At': 150
        }

        for col, width in template_columns.items():
            self.templates_tree.heading(col, text=col)
            self.templates_tree.column(col, width=width, minwidth=50)

        templates_v_scrollbar = ttk.Scrollbar(templates_list_frame, orient=tk.VERTICAL, command=self.templates_tree.yview)
        self.templates_tree.configure(yscrollcommand=templates_v_scrollbar.set)

        self.templates_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        templates_v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.templates_tree.bind('<Double-1>', self.on_template_double_click)

    # --- Status Bar ---

    def create_status_bar(self):
        """Create the status bar"""
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.status_bar, textvariable=self.status_var).pack(side=tk.LEFT, padx=5)

        if CLI_AVAILABLE and 'auth' in globals() and auth and auth.current_user:
            user_info = f"User: {auth.current_user}"
            ttk.Label(self.status_bar, text=user_info).pack(side=tk.RIGHT, padx=5)

    # --- Data Refresh ---

    def refresh_data(self):
        """Refresh the accommodations data"""
        if not CLI_AVAILABLE:
            self.status_var.set("CLI module not available")
            return

        try:
            self.status_var.set("Loading accommodations...")
            self.root.update()

            for item in self.accom_tree.get_children():
                self.accom_tree.delete(item)

            types = get_accommodation_types() if CLI_AVAILABLE else []
            self.search_type['values'] = [''] + types

            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT a.id, a.student_id, a.accommodation_type, a.description,
                           a.start_date, a.end_date, a.status, a.created_at,
                           s.first_name, s.last_name, s.email_address
                    FROM accommodations a
                    LEFT JOIN students s ON a.student_id = s.student_id
                    ORDER BY a.id DESC
                ''')

                accommodations = cursor.fetchall()

                for acc in accommodations:
                    name = f"{acc['first_name'] or ''} {acc['last_name'] or ''}".strip() or 'N/A'

                    self.accom_tree.insert('', 'end', values=(
                        acc['id'],
                        acc['student_id'],
                        name,
                        acc['accommodation_type'],
                        acc['start_date'] or 'N/A',
                        acc['end_date'] or 'N/A',
                        acc['status']
                    ))

            self.status_var.set(f"Loaded {len(accommodations)} accommodations")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load accommodations: {str(e)}")
            self.status_var.set("Error loading data")

    def refresh_templates(self):
        """Refresh the templates data"""
        if not CLI_AVAILABLE:
            return

        try:
            for item in self.templates_tree.get_children():
                self.templates_tree.delete(item)

            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name, accommodation_type, description, duration_days,"
                    " created_by, created_at"
                    " FROM [" + TEMPLATES_TABLE + "]"
                    " ORDER BY name"
                )

                templates = cursor.fetchall()

                for template in templates:
                    self.templates_tree.insert('', 'end', values=(
                        template['name'],
                        template['accommodation_type'],
                        template['description'] or 'N/A',
                        f"{template['duration_days']} days" if template['duration_days'] else 'N/A',
                        template['created_by'] or 'N/A',
                        template['created_at'] or 'N/A'
                    ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load templates: {str(e)}")

    # --- Event Handlers ---

    def on_accommodation_double_click(self, event):
        """Handle double-click on accommodation"""
        self.view_accommodation_details()

    def on_template_double_click(self, event):
        """Handle double-click on template"""
        self.edit_template_dialog()

    def get_selected_accommodation(self):
        """Get the currently selected accommodation"""
        selection = self.accom_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an accommodation first")
            return None
        return self.accom_tree.item(selection[0])

    # --- Static / Utility Methods ---

    @staticmethod
    def notify_student(student_id, subject, message):
        """Send notification to student (GUI version)"""
        if not CLI_AVAILABLE:
            messagebox.showinfo("Student Notification",
                f"Would notify {student_id}:\n{subject}\n\n{message}")
            return

        try:
            cli_notify_student(student_id, subject, message)
        except Exception as e:
            messagebox.showerror("Notification Error", f"Failed to notify student: {str(e)}")

    def validate_accommodation_data(self, data):
        """Validate accommodation data before submission"""
        errors = []

        if hasattr(data, '__getitem__') and not hasattr(data, 'get'):
            data = dict(data)

        if not data.get('student_id', '').strip():
            errors.append("Student ID is required")

        if not data.get('accommodation_type', '').strip():
            errors.append("Accommodation type is required")

        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if start_date and end_date:
            try:
                start = datetime.fromisoformat(start_date)
                end = datetime.fromisoformat(end_date)
                if end <= start:
                    errors.append("End date must be after start date")
            except ValueError:
                errors.append("Invalid date format")

        return errors

    def setup_keyboard_shortcuts(self):
        """Set up keyboard shortcuts"""
        self.root.bind('<F5>', lambda e: self.refresh_data())
        self.root.bind('<Control-n>', lambda e: self.add_accommodation_dialog())
        self.root.bind('<Control-e>', lambda e: self.update_accommodation_dialog())
        self.root.bind('<Delete>', lambda e: self.remove_accommodation_dialog())

    # --- Simple Dialog Delegates ---

    def bulk_operations_dialog(self):
        """Show bulk operations dialog"""
        BulkOperationsDialog(self.root, self)

    def upload_document_dialog(self):
        """Show dialog to upload documents for selected accommodation"""
        selected = self.get_selected_accommodation()
        if not selected:
            return

        accommodation_id = selected['values'][0]

        dialog = DocumentUploadDialog(self.root, accommodation_id)
        if dialog.result:
            messagebox.showinfo("Success", "Document uploaded successfully")

    def show_db_info(self):
        """Show database information"""
        DatabaseInfoDialog(self.root)

    def show_settings(self):
        """Show settings dialog"""
        SettingsDialog(self.root)

    def show_help(self):
        """Show help dialog"""
        HelpDialog(self.root)

    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo("About",
            "Student Accommodation Management System\n\n"
            "GUI Version 1.0\n"
            "Backwards compatible with CLI version\n\n"
            "This system helps manage student accommodations\n"
            "with features for registration, tracking, reporting,\n"
            "and template management.")

    @staticmethod
    def launch_gui():
        """Function to launch GUI from CLI"""
        from education_system.university_system.modules.domain.health.gui.medical_accommodation.cli_integration import main
        print("Launching GUI mode...")
        main()
