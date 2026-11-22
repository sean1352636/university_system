import logging
import tkinter as tk
from tkinter import ttk
from education_system.systems.university.domains.health.interfaces.gui.health._dialogs import messagebox

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

        user_info = _t("health_portal.header_logged_in", default="Logged in as: {username} ({role})").format(
            username=self.auth.current_user['username'], role=self.auth.current_user['role'])
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
            ("manage_records", "manage_health_records", 'clinician'),
            ("view_records", "view_health_records", 'patient'),
            ("view_history", "view_medical_history", 'patient'),
            ("student_dashboard", "student_health_dashboard", 'patient'),
            ("allergies", "clinical_allergies", 'patient'),
            ("prescriptions", "clinical_prescriptions", 'patient'),
            ("vital_signs", "vital_signs", 'patient'),
            ("lab_results", "clinical_lab_results", 'patient'),
            ("medical_conditions", "clinical_conditions", 'patient'),
            ("personal_metrics", "personal_metrics", 'patient'),
            ("record_templates", "record_templates", 'clinician'),
        ]),
        ("🩺 Providers & Referrals", [
            ("provider_dashboard", "provider_dashboard", 'clinician'),
            ("provider_schedules", "provider_schedules", 'clinician'),
            ("referrals", "clinical_referrals", 'clinician'),
        ]),
        ("📅 Appointments & Scheduling", [
            ("schedule_appt", "schedule_appointment", 'patient'),
            ("view_appts", "view_appointments", 'patient'),
        ]),
        ("💉 Vaccinations & Immunizations", [
            ("record_vaccine", "record_vaccination", 'clinician'),
            ("view_vaccines", "view_vaccination_records", 'patient'),
        ]),
        ("🏥 Care Plans & Clinical Management", [
            ("care_plans", "clinical_care_plans", 'clinician'),
            ("screening", "clinical_screening", 'clinician'),
            ("screening_schedules", "provider_screening", 'clinician'),
            ("risk_assessment", "risk_assessment", 'clinician'),
            ("drug_interactions", "drug_interactions", 'clinician'),
        ]),
        ("🚨 Emergency & Safety", [
            ("manage_contacts", "manage_emergency_contacts", 'patient'),
            ("disease_surveillance", "disease_surveillance", 'surveillance'),
            ("break_glass", "break_glass_access", 'outside_team'),
        ]),
        ("📢 Health Advisories", [
            ("health_advisories", "health_advisories", 'advisories'),
        ]),
        ("🌟 Wellness & Prevention", [
            ("wellness", "clinical_wellness", 'patient'),
        ]),
        ("🧠 Mental Health & Wellness", [
            ("mental_health", "mental_health_wellness", 'patient'),
        ]),
        ("💳 Insurance & Financial", [
            ("insurance", "insurance_information", 'patient'),
        ]),
        ("📊 Analytics & Reporting", [
            ("generate_reports", "generate_health_reports", 'patient'),
            ("health_reports", "health_reports", 'clinician'),
            ("quality_assurance", "quality_assurance", 'clinician'),
        ]),
        ("✉️ Integration & Communications", [
            ("email_manager", "email_manager", 'clinician'),
            ("send_report_email", "send_health_report_email", 'clinician'),
            ("send_record_email", "send_health_record_email", 'clinician'),
        ]),
        ("♿ Accessibility & Accommodations", [
            ("accessibility_tools", "open_accessibility_tools", None),
            ("medical_accommodations", "medical_accommodations", 'accommodations'),
        ]),
        ("🦷 Health Services", [
            ("dentist", "show_dentist", 'patient'),
        ]),
        ("🔒 Data Management & Security", [
            ("security_audit", "security_audit", 'admin'),
            ("data_management", "data_management", 'admin'),
            ("integration_management", "integration_management", 'admin'),
            ("data_retention", "data_retention", 'clinician'),
            ("backup_recovery", "backup_recovery", 'admin'),
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
        from education_system.systems.university.domains.health.interfaces.gui.health.health_portal import (
            access_ui,
        )
        if requirement is None:
            return True
        if requirement == 'admin':
            return self.is_admin()
        if requirement == 'staff':
            return self.is_admin() or self.is_staff()
        # Health-team roles (nurse, doctor, clinician, first-aider, dentist,
        # health administrator) and administrators.
        if requirement == 'clinician':
            return access_ui.is_clinician(self.auth)
        # The health team, or a student for their own record.
        if requirement == 'patient':
            return access_ui.is_clinician(self.auth) or bool(access_ui.own_student_id(self.auth))
        # Staff outside the health team: break-glass access only.
        if requirement == 'outside_team':
            return (not access_ui.is_clinician(self.auth)
                    and not access_ui.own_student_id(self.auth)
                    and (self.is_staff() or self.is_admin()))
        # Disease surveillance: the health team, with the advisory permission
        # (the CLI's rule).
        if requirement == 'surveillance':
            return (access_ui.is_clinician(self.auth)
                    and bool(self.auth.check_permission('issue_health_advisories')))
        # Advisories: the health team and students read the published ones;
        # anyone holding the advisory permissions too.
        if requirement == 'advisories':
            return (access_ui.is_clinician(self.auth) or bool(access_ui.own_student_id(self.auth))
                    or any(self.auth.check_permission(name) for name in
                           ('view_health_advisories', 'issue_health_advisories')))
        if requirement == 'accommodations':
            return (access_ui.is_clinician(self.auth) or bool(access_ui.own_student_id(self.auth))
                    or any(self.auth.check_permission(name) for name in
                           ('view_accommodations', 'manage_accommodations',
                            'approve_accommodations')))
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
            self.status_var.set(_t("health_portal.status.loading", default="Loading {name}...")
                                .format(name=function_name.replace('_', ' ')))
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
            logging.getLogger(__name__).exception("Health Portal screen %s failed", function_name)
            messagebox.showerror(_t("common.error"), f"Failed to load {function_name}: {str(e)}")

        try:
            self.status_var.set(_t("health_portal.status.ready"))
        except (tk.TclError, AttributeError):
            pass

    def create_missing_feature_notice(self, function_name):
        """Shown only if a navigation entry names a screen that does not
        exist (every entry in NAV_CATEGORIES maps to a ``create_*`` method)."""
        display_name = function_name.replace('_', ' ').title()
        ttk.Label(self.content_frame, text=display_name, style='Title.TLabel').grid(
            row=0, column=0, pady=10)
        ttk.Label(self.content_frame,
                  text=_t("health_portal.messages.screen_missing",
                          default="There is no '{name}' screen in this version of the "
                                  "Health Portal.").format(name=display_name),
                  font=('Arial', 11)).grid(row=1, column=0, padx=20, sticky='w')
        self.content_frame.columnconfigure(0, weight=1)

    # --- Screens for the features that used to be CLI-only ------------
    # (cli_parity_panels: each backed by the CLI's own domain services)
    def _embed_parity_panel(self, attr):
        self._embed_health_panel("cli_parity_panels", attr)

    def create_vital_signs(self):
        self._embed_parity_panel("VitalSignsPanel")

    def create_insurance_information(self):
        self._embed_parity_panel("InsurancePanel")

    def create_health_advisories(self):
        self._embed_parity_panel("AdvisoriesPanel")

    def create_disease_surveillance(self):
        self._embed_parity_panel("SurveillancePanel")

    def create_risk_assessment(self):
        self._embed_parity_panel("RiskAssessmentPanel")

    def create_quality_assurance(self):
        self._embed_parity_panel("QualityAssurancePanel")

    def create_data_retention(self):
        self._embed_parity_panel("RetentionPanel")

    def create_backup_recovery(self):
        self._embed_parity_panel("BackupRecoveryPanel")

    def create_record_templates(self):
        self._embed_parity_panel("RecordTemplatesPanel")

    def create_student_health_dashboard(self):
        self._embed_parity_panel("StudentDashboardPanel")

    def create_drug_interactions(self):
        self._embed_parity_panel("DrugInteractionsPanel")

    def create_personal_metrics(self):
        self._embed_parity_panel("PersonalMetricsPanel")

    def create_view_health_records(self):
        """Read-only list of health records (the Manage screen's View tab on
        its own: no Add tab and no sixth-form import). Update/Delete still
        appear for the health team, as on the Manage screen."""
        title = ttk.Label(self.content_frame, text=_t("health_portal.tabs.view_records"),
                          style='Title.TLabel')
        title.grid(row=0, column=0, pady=10, sticky=tk.W)

        view_frame = ttk.Frame(self.content_frame)
        view_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        self.create_view_health_records_form(view_frame)

        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)

    def create_view_vaccinations(self):
        """Alias for vaccination records (for navigation compatibility)"""
        self.create_record_vaccination()

    def create_view_appointments(self):
        """Appointment list (the Schedule screen's View tab on its own, no
        booking form). Update Status/Cancel/Feedback appear as they do there."""
        title = ttk.Label(self.content_frame, text=_t(
            'gui.pastoral.health.health_portal.appointments.tabs.view_appointments',
            default="View Appointments"), style='Title.TLabel')
        title.grid(row=0, column=0, pady=10, sticky=tk.W)

        view_frame = ttk.Frame(self.content_frame)
        view_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        self.create_view_appointments_form(view_frame)

        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)

    def create_show_dentist(self):
        """Embed the Dentist GUI directly in the content frame."""
        try:
            from education_system.systems.university.domains.health.interfaces.gui.health.health_portal.dentist_gui import DentistGUI
            DentistGUI(self.content_frame, self.auth)
        except Exception as e:
            ttk.Label(self.content_frame, text=f"Dentist could not be loaded: {e}",
                      font=("Arial", 12)).grid(row=0, column=0, padx=20, pady=20)

    def create_break_glass_access(self):
        """Emergency access to one student's record for someone outside the
        health team: a written reason, logged, and the health administrators
        told; the grant expires on its own."""
        from education_system.systems.university.domains.health.interfaces.gui.health.health_portal import access_ui

        ttk.Label(self.content_frame, text="Emergency access (break-glass)",
                  style='Title.TLabel').grid(row=0, column=0, pady=10, sticky='w')
        ttk.Label(self.content_frame,
                  text="Health records are for the health team and the student themselves.\n"
                       "Use this only in an emergency. Your reason is recorded and the health\n"
                       "administrators are told.", foreground='#555555').grid(
            row=1, column=0, padx=20, sticky='w')
        form = ttk.Frame(self.content_frame)
        form.grid(row=2, column=0, padx=20, pady=15, sticky='w')
        ttk.Label(form, text="Student ID:").grid(row=0, column=0, sticky='w')
        student_var = tk.StringVar()
        ttk.Entry(form, textvariable=student_var, width=20).grid(row=0, column=1, padx=5)

        def request():
            sid = student_var.get().strip()
            if access_ui.request_break_glass(self.content_frame, self.auth, sid):
                messagebox.showinfo(access_ui.TITLE,
                                    f"Access to {sid}'s health record granted for a limited "
                                    "time. Open Health Records and search for the student.",
                                    parent=self.content_frame)

        ttk.Button(form, text="Request access", command=request).grid(row=0, column=2, padx=5)
        self.content_frame.columnconfigure(0, weight=1)

    def create_show_medical_accommodations(self):
        """Embed the Medical Accommodation GUI in the content frame."""
        self.create_medical_accommodations()

    # --- Embedded clinical / provider / mental-health panels -------------
    def _embed_health_panel(self, module_suffix, attr):
        """Import and embed a panel class into the content frame."""
        try:
            import importlib
            base = "education_system.systems.university.domains.health.interfaces.gui.health.health_portal."
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
