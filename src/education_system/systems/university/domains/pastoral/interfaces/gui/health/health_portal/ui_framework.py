import tkinter as tk
from tkinter import ttk, messagebox

from education_system.systems.university.infrastructure.i18n import get_text as _t


class UIFrameworkMixin:
    """Mixin for main GUI layout, navigation, and content area management."""

    def setup_styles(self):
        """Configure ttk styles for the application"""
        style = ttk.Style()

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

        # Named for what it does: this returns to the university menu, it is
        # not a logout. The Health Portal offers neither a logout nor a
        # language switcher, matching the health CLI.
        return_btn = ttk.Button(header_frame, text=_t("health_portal.btn.return_main"),
                                command=self.return_to_main_menu)
        return_btn.grid(row=0, column=2, padx=(10, 0))

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

    # Navigation is grouped into collapsible categories rather than one long
    # scrolling column of ~35 buttons. Same shape as the health CLI, which
    # groups the same actions into categories you open one at a time: you see
    # the headings first, expand the one you want, and only that category's
    # buttons are on screen. Categories the user has no permission for are
    # never built, so there are no empty headings.
    NAV_CATEGORIES = [
        ("📋 Health Records & Clinical Data", [
            ("manage_records", "manage_health_records", 'manage_health_records'),
            ("view_records", "view_health_records",
             ('view_any_health_record', 'view_own_health_record')),
            ("view_history", "view_medical_history", None),
            ("Allergies", "clinical_allergies", None),
            ("Prescriptions", "clinical_prescriptions", None),
            ("Lab Results", "clinical_lab_results", None),
            ("Medical Conditions", "clinical_conditions", None),
        ]),
        ("🩺 Providers & Referrals", [
            ("Provider Dashboard", "provider_dashboard", 'manage_health_records'),
            ("Provider Schedules", "provider_schedules", 'manage_health_records'),
            ("Referrals", "clinical_referrals", 'manage_health_records'),
        ]),
        ("📅 Appointments & Scheduling", [
            ("schedule_appt", "schedule_appointment",
             ('schedule_health_appointment', 'manage_health_appointments')),
            ("view_appts", "view_appointments",
             ('view_own_appointments', 'manage_health_appointments')),
        ]),
        ("💉 Vaccinations & Immunizations", [
            ("record_vaccine", "record_vaccination", 'manage_vaccinations'),
            ("view_vaccines", "view_vaccination_records",
             ('view_own_vaccinations', 'manage_vaccinations', 'view_any_health_record')),
        ]),
        ("🏥 Care Plans & Clinical Management", [
            ("Care Plans", "clinical_care_plans", 'manage_health_records'),
            ("Screening", "clinical_screening", 'manage_health_records'),
            ("Screening Schedules", "provider_screening", 'manage_health_records'),
        ]),
        ("🚨 Emergency & Safety", [
            ("manage_contacts", "manage_emergency_contacts", None),
        ]),
        ("🌟 Wellness & Prevention", [
            ("Wellness", "clinical_wellness", None),
        ]),
        ("🧠 Mental Health & Wellness", [
            ("Mental Health & Wellness", "mental_health_wellness", None),
        ]),
        ("📊 Analytics & Reporting", [
            ("generate_reports", "generate_health_reports",
             ('view_any_health_record', 'manage_health_records')),
            ("health_reports", "health_reports", 'view_any_health_record'),
        ]),
        ("✉️ Integration & Communications", [
            ("email_manager", "email_manager", 'staff'),
            ("send_report_email", "send_health_report_email", 'staff'),
            ("send_record_email", "send_health_record_email", 'staff'),
        ]),
        ("♿ Accessibility & Accommodations", [
            ("accessibility_tools", "open_accessibility_tools", None),
            ("medical_accommodations", "medical_accommodations", None),
        ]),
        ("🦷 Health Services", [
            ("Dentist", "show_dentist", None),
        ]),
        ("🔒 Data Management & Security", [
            ("security_audit", "security_audit", 'admin'),
            ("data_management", "data_management", 'admin'),
            ("Integration Management", "integration_management", 'admin'),
        ]),
    ]

    def _nav_label(self, key):
        """Translate a nav label, falling back to the literal for new entries."""
        if " " in key or key[:1].isupper():
            return key
        return _t(f"health_portal.nav.{key}")

    def _nav_item_allowed(self, requirement):
        """Whether the signed-in user may see a nav entry.

        *requirement* is ``None`` (everyone), a role sentinel (``'admin'`` /
        ``'staff'``), a permission name, or a tuple of permissions of which
        any one is enough.
        """
        if requirement is None:
            return True
        if requirement == 'admin':
            return self.is_admin()
        if requirement == 'staff':
            return self.is_admin() or self.is_staff()
        if isinstance(requirement, tuple):
            return any(self.auth.check_permission(name) for name in requirement)
        return self.auth.check_permission(requirement)

    def _visible_nav_categories(self):
        """The categories, with unavailable entries and empty categories dropped."""
        visible = []
        for title, entries in self.NAV_CATEGORIES:
            allowed = [(label, function_name)
                       for label, function_name, requirement in entries
                       if self._nav_item_allowed(requirement)]
            if allowed:
                visible.append((title, allowed))
        return visible

    def toggle_nav_category(self, title):
        """Expand or collapse one category, then redraw the sidebar."""
        expanded = getattr(self, '_nav_expanded', None)
        if expanded is None:
            expanded = self._nav_expanded = set()
        if title in expanded:
            expanded.discard(title)
        else:
            expanded.add(title)
        self.populate_navigation()

    def populate_navigation(self):
        """Populate navigation as collapsible categories."""
        for widget in self.nav_buttons_frame.winfo_children():
            widget.destroy()

        if not hasattr(self, '_nav_expanded'):
            # Open the first category on the very first draw so the sidebar
            # never looks empty, then remember what the user opens.
            self._nav_expanded = set()
            first = self._visible_nav_categories()
            if first:
                self._nav_expanded.add(first[0][0])

        button_row = 0
        for title, entries in self._visible_nav_categories():
            is_open = title in self._nav_expanded
            header = ttk.Button(
                self.nav_buttons_frame,
                text=f"{'▼' if is_open else '▶'} {title}  ({len(entries)})",
                width=30,
                command=lambda t=title: self.toggle_nav_category(t),
            )
            header.grid(row=button_row, column=0, sticky=(tk.W, tk.E),
                        pady=(6, 2), padx=2)
            button_row += 1

            if not is_open:
                continue

            for label, function_name in entries:
                btn = ttk.Button(
                    self.nav_buttons_frame, text=self._nav_label(label), width=28,
                    command=lambda fn=function_name: self.load_function(fn))
                btn.grid(row=button_row, column=0, sticky=(tk.W, tk.E),
                         pady=2, padx=(18, 2))
                button_row += 1

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
        # The content frame may have been destroyed if the parent window was
        # closed (e.g., sibling Toplevel torn down) while the nav-button
        # callbacks are still wired up. Bail quietly in that case rather than
        # throwing TclError on winfo_children.
        try:
            content_alive = bool(self.content_frame.winfo_exists())
        except tk.TclError:
            content_alive = False
        if not content_alive:
            return

        for widget in self.content_frame.winfo_children():
            try:
                widget.destroy()
            except tk.TclError:
                pass

        try:
            self.status_var.set(f"Loading {function_name}...")
        except (tk.TclError, AttributeError):
            pass

        try:
            if hasattr(self, f'create_{function_name}'):
                getattr(self, f'create_{function_name}')()
            else:
                self.create_missing_feature_notice(function_name)
        except tk.TclError:
            # Window torn down mid-render — silently abort.
            return
        except Exception as e:
            messagebox.showerror(_t("common.error"), f"Failed to load {function_name}: {str(e)}")

        try:
            self.status_var.set(_t("health_portal.status.ready"))
        except (tk.TclError, AttributeError):
            pass

    def create_missing_feature_notice(self, function_name):
        """Show a clear notice when no GUI handler is registered."""
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

    def create_show_dentist(self):
        """Embed the Dentist GUI directly in the content frame."""
        try:
            from education_system.systems.university.domains.pastoral.interfaces.gui.health.health_portal.dentist_gui import DentistGUI
            DentistGUI(self.content_frame, self.auth)
        except Exception as e:
            ttk.Label(self.content_frame, text=f"Dentist could not be loaded: {e}",
                      font=("Arial", 12)).grid(row=0, column=0, padx=20, pady=20)

    def create_show_medical_accommodations(self):
        """Embed the Medical Accommodation GUI in the content frame."""
        self.create_medical_accommodations()

    # --- Embedded clinical / provider / mental-health panels -------------
    def _embed_health_panel(self, module_suffix, attr):
        """Import and embed a panel class into the content frame."""
        try:
            import importlib
            base = "education_system.systems.university.domains.pastoral.interfaces.gui.health.health_portal."
            mod = importlib.import_module(base + module_suffix)
            getattr(mod, attr)(self.content_frame, self.auth)
        except Exception as e:
            ttk.Label(self.content_frame, text=f"Could not load panel: {e}",
                      font=("Arial", 12)).grid(row=0, column=0, padx=20, pady=20)

    def create_clinical_allergies(self):
        self._embed_health_panel("clinical_panels", "AllergiesPanel")

    def create_clinical_prescriptions(self):
        self._embed_health_panel("clinical_panels", "PrescriptionsPanel")

    def create_clinical_lab_results(self):
        self._embed_health_panel("clinical_panels", "LabResultsPanel")

    def create_clinical_conditions(self):
        self._embed_health_panel("clinical_panels", "ConditionsPanel")

    def create_clinical_care_plans(self):
        self._embed_health_panel("clinical_panels", "CarePlansPanel")

    def create_clinical_referrals(self):
        self._embed_health_panel("clinical_panels", "ReferralsPanel")

    def create_clinical_screening(self):
        self._embed_health_panel("clinical_panels", "ScreeningPanel")

    def create_clinical_wellness(self):
        self._embed_health_panel("clinical_panels", "WellnessPanel")

    def create_mental_health_wellness(self):
        self._embed_health_panel("mental_health_panel", "MentalHealthWellnessPanel")

    def create_provider_schedules(self):
        self._embed_health_panel("provider_panels", "ProviderSchedulePanel")

    def create_provider_dashboard(self):
        self._embed_health_panel("provider_panels", "ProviderDashboardPanel")

    def create_provider_screening(self):
        self._embed_health_panel("provider_panels", "ScreeningSchedulePanel")

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            if isinstance(self.root, tk.Toplevel):
                self.root.destroy()
            else:
                self.root.destroy()
                from education_system.systems.university.shell.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()
