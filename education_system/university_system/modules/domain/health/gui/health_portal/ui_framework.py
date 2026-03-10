import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.modules.shared.utils.i18n import get_text as _t


class UIFrameworkMixin:
    """Mixin for main GUI layout, navigation, and content area management."""

    def setup_styles(self):
        """Configure ttk styles for the application"""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('Title.TLabel', font=('Arial', 16, 'bold'), background='#f0f0f0')
        style.configure('Heading.TLabel', font=('Arial', 12, 'bold'), background='#f0f0f0')
        style.configure('Success.TLabel', foreground='green', font=('Arial', 10, 'bold'))
        style.configure('Error.TLabel', foreground='red', font=('Arial', 10, 'bold'))
        style.configure('Warning.TLabel', foreground='orange', font=('Arial', 10, 'bold'))

    def create_main_interface(self):
        """Create the main interface after successful login"""
        for widget in self.root.winfo_children():
            widget.destroy()

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=0)
        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=0)

        self.create_header(main_frame)
        self.create_navigation(main_frame)
        self.create_content_area(main_frame)
        self.create_status_bar(main_frame)

    def create_header(self, parent):
        """Create the header section"""
        header_frame = ttk.Frame(parent, padding="5")
        header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E))

        title_label = ttk.Label(header_frame, text=_t("health_portal.header_title"),
                               style='Title.TLabel')
        title_label.grid(row=0, column=0, sticky=tk.W)

        user_info = f"Logged in as: {self.auth.current_user['username']} ({self.auth.current_user['role']})"
        user_label = ttk.Label(header_frame, text=user_info)
        user_label.grid(row=0, column=1, sticky=tk.E)

        logout_btn = ttk.Button(header_frame, text=_t("health_portal.btn.return_main"), command=self.return_to_main_menu)
        logout_btn.grid(row=0, column=2, padx=(10, 0))

        header_frame.columnconfigure(1, weight=1)

    def create_navigation(self, parent):
        """Create the navigation panel with buttons and scrollbar"""
        nav_frame = ttk.LabelFrame(parent, text=_t("health_portal.nav.title"), padding="5")
        nav_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))

        self.nav_canvas = tk.Canvas(nav_frame, highlightthickness=0, bg='#f0f0f0')
        self.nav_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        nav_scroll = ttk.Scrollbar(nav_frame, orient=tk.VERTICAL, command=self.nav_canvas.yview)
        nav_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.nav_canvas.configure(yscrollcommand=nav_scroll.set)

        self.nav_buttons_frame = ttk.Frame(self.nav_canvas)
        self.nav_canvas_window = self.nav_canvas.create_window((0, 0), window=self.nav_buttons_frame, anchor='nw')

        self.nav_buttons_frame.bind('<Configure>', lambda e: self.nav_canvas.configure(scrollregion=self.nav_canvas.bbox('all')))
        self.nav_canvas.bind('<Configure>', self._on_nav_canvas_configure)
        self.nav_canvas.bind_all('<MouseWheel>', self._on_nav_mousewheel)

        nav_frame.columnconfigure(0, weight=1)
        nav_frame.rowconfigure(0, weight=1)

        self.populate_navigation()

    def _on_nav_canvas_configure(self, event):
        """Handle canvas resize to adjust button frame width"""
        canvas_width = event.width
        self.nav_canvas.itemconfig(self.nav_canvas_window, width=canvas_width)

    def _on_nav_mousewheel(self, event):
        """Handle mousewheel scrolling for navigation"""
        if self.nav_canvas.winfo_containing(event.x_root, event.y_root) == self.nav_canvas:
            self.nav_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def populate_navigation(self):
        """Populate navigation buttons based on user permissions and role"""
        for widget in self.nav_buttons_frame.winfo_children():
            widget.destroy()

        is_admin = self.is_admin()
        is_staff = self.is_staff()
        is_student = self.is_student()

        button_row = 0

        def create_section_header(text):
            nonlocal button_row
            header = ttk.Label(self.nav_buttons_frame, text=text, font=('Arial', 10, 'bold'),
                             background='#e0e0e0', anchor='w', padding=(5, 5))
            header.grid(row=button_row, column=0, sticky=(tk.W, tk.E), pady=(5, 2), padx=2)
            button_row += 1

        def create_nav_button(text, function_name):
            nonlocal button_row
            btn = ttk.Button(self.nav_buttons_frame, text=text,
                           command=lambda: self.load_function(function_name), width=30)
            btn.grid(row=button_row, column=0, sticky=(tk.W, tk.E), pady=2, padx=(10, 2))
            button_row += 1

        if (self.auth.check_permission('manage_health_records') or
            self.auth.check_permission('view_own_health_record') or
            self.auth.check_permission('view_any_health_record')):

            create_section_header(_t("health_portal.nav.health_records"))

            if self.auth.check_permission('manage_health_records'):
                create_nav_button(_t("health_portal.nav.manage_records"), 'manage_health_records')

            create_nav_button(_t("health_portal.nav.view_records"), 'view_health_records')
            create_nav_button(_t("health_portal.nav.view_history"), 'view_medical_history')
            create_nav_button(_t("health_portal.nav.generate_reports"), 'generate_health_reports')

        if (self.auth.check_permission('manage_health_appointments') or
            self.auth.check_permission('schedule_health_appointment') or
            self.auth.check_permission('view_own_appointments')):

            create_section_header(_t("health_portal.nav.appointments"))

            if (self.auth.check_permission('schedule_health_appointment') or
                self.auth.check_permission('manage_health_appointments')):
                create_nav_button(_t("health_portal.nav.schedule_appt"), 'schedule_appointment')

            create_nav_button(_t("health_portal.nav.view_appts"), 'view_appointments')

        if (self.auth.check_permission('manage_vaccinations') or
            self.auth.check_permission('view_own_vaccinations') or
            self.auth.check_permission('verify_vaccinations')):

            create_section_header(_t("health_portal.nav.vaccinations"))

            if self.auth.check_permission('manage_vaccinations'):
                create_nav_button(_t("health_portal.nav.record_vaccine"), 'record_vaccination')

            create_nav_button(_t("health_portal.nav.view_vaccines"), 'view_vaccination_records')

        create_section_header(_t("health_portal.nav.emergency_contacts"))
        create_nav_button(_t("health_portal.nav.manage_contacts"), 'manage_emergency_contacts')

        if (is_admin or is_staff) and self.auth.check_permission('view_any_health_record'):
            create_section_header(_t("health_portal.nav.reports_analytics"))
            create_nav_button(_t("health_portal.nav.health_reports"), 'health_reports')

        if is_admin or is_staff:
            create_section_header(_t("health_portal.nav.integration"))
            create_nav_button(_t("health_portal.nav.email_manager"), 'email_manager')
            create_nav_button(_t("health_portal.nav.send_report_email"), 'send_health_report_email')
            create_nav_button(_t("health_portal.nav.send_record_email"), 'send_health_record_email')

        create_section_header(_t("health_portal.nav.accessibility"))
        create_nav_button(_t("health_portal.nav.accessibility_tools"), 'open_accessibility_tools')
        create_nav_button(_t("health_portal.nav.medical_accommodations"), 'medical_accommodations')

        if is_admin:
            create_section_header(_t("health_portal.nav.administration"))
            create_nav_button(_t("health_portal.nav.security_audit"), 'security_audit')
            create_nav_button(_t("health_portal.nav.data_management"), 'data_management')

        self.nav_buttons_frame.columnconfigure(0, weight=1)
        self.nav_canvas.yview_moveto(0)

    def create_content_area(self, parent):
        """Create the main content area"""
        self.content_frame = ttk.LabelFrame(parent, text=_t("health_portal.content.title"), padding="10")
        self.content_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(0, weight=1)

        self.content_area = self.content_frame

        welcome_text = _t("health_portal.content.welcome")
        welcome_label = ttk.Label(self.content_frame, text=welcome_text, justify=tk.CENTER)
        welcome_label.grid(row=0, column=0, pady=50)

    def create_status_bar(self, parent):
        """Create the status bar"""
        self.status_var = tk.StringVar()
        self.status_var.set(_t("health_portal.status.ready"))

        status_bar = ttk.Label(parent, textvariable=self.status_var, relief=tk.SUNKEN, padding="5")
        status_bar.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E))

    def load_function(self, function_name):
        """Load the selected function in the content area"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        self.status_var.set(f"Loading {function_name}...")

        try:
            if hasattr(self, f'create_{function_name}'):
                getattr(self, f'create_{function_name}')()
            else:
                self.create_placeholder(function_name)
        except Exception as e:
            messagebox.showerror(_t("common.error"), f"Failed to load {function_name}: {str(e)}")

        self.status_var.set(_t("health_portal.status.ready"))

    def create_placeholder(self, function_name):
        """Create a placeholder interface for functions not yet implemented"""
        display_name = function_name.replace('_', ' ').title()

        title = ttk.Label(self.content_frame, text=display_name, style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        info_frame = ttk.LabelFrame(self.content_frame, text=_t("health_portal.labels.feature_info", "Feature Information"), padding=15)
        info_frame.grid(row=1, column=0, pady=20, padx=20, sticky='ew')

        ttk.Label(info_frame,
                 text=_t("health_portal.messages.feature_under_development",
                         "The '{name}' interface is under development.").format(name=display_name),
                 font=('Arial', 11)).pack(anchor='w', pady=5)

        ttk.Label(info_frame,
                 text=_t("health_portal.messages.backend_available",
                         "The backend service for this feature is available. A full GUI interface\n"
                         "will be added in a future update. In the meantime, you can access\n"
                         "this functionality through the CLI interface."),
                 foreground='gray').pack(anchor='w', pady=5)

        features_frame = ttk.LabelFrame(self.content_frame, text=_t("health_portal.labels.available_features", "Available Features"), padding=15)
        features_frame.grid(row=2, column=0, pady=10, padx=20, sticky='ew')

        available = [
            "Manage Health Records", "Schedule Appointments", "Record Vaccinations",
            "Health Reports & Analytics", "Emergency Contacts", "Security Audit",
            "Data Management", "Email Manager"
        ]
        ttk.Label(features_frame,
                 text=_t("health_portal.messages.try_these", "Try one of these fully implemented features:"),
                 font=('Arial', 10, 'bold')).pack(anchor='w')
        ttk.Label(features_frame, text="  " + "  |  ".join(available), foreground='#555555').pack(anchor='w', pady=5)

        self.content_frame.columnconfigure(0, weight=1)

    def create_view_health_records(self):
        """Alias for view health records (for navigation compatibility)"""
        self.create_manage_health_records()

    def create_view_vaccinations(self):
        """Alias for vaccination records (for navigation compatibility)"""
        self.create_record_vaccination()

    def create_view_appointments(self):
        """Alias for appointment management (for navigation compatibility)"""
        self.create_schedule_appointment()

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            if isinstance(self.root, tk.Toplevel):
                self.root.destroy()
            else:
                self.root.destroy()
                from education_system.university_system.modules.shared.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()
