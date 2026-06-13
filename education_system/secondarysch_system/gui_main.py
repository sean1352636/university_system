"""Tk GUI main menu for the Secondary School System.

Layout mirrors `sixthform_system` and `university_system`:

    row 0 — header (logout · switch-to-CLI · switch-system · shutdown)
    row 1 — left navigation (accordion of categories) + right content area
    row 2 — status bar (status · current user · system / version)

Every sidebar action is a placeholder stub — domain modules will be
wired in later.
"""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Callable

from education_system.secondarysch_system import SYSTEM_NAME

logger = logging.getLogger(__name__)

VERSION = "0.1.0"
FOOTER_LABEL = "Secondary School"


NAV_CATEGORIES: list[tuple[str, list[tuple[str, str]]]] = [
    ("Pupil Management", [
        ("Pupil Directory", "open_pupil_directory"),
        ("Add Pupil", "open_add_pupil"),
        ("Search Pupils", "open_search_pupils"),
        ("Advanced Search", "open_advanced_search"),
        ("Pupil Profile", "open_pupil_profile"),
        ("Admissions", "open_admissions"),
        ("Year Group Enrolment", "open_enrolment"),
        ("Onboarding", "open_onboarding"),
        ("Bulk Operations", "open_bulk_operations"),
        ("Alumni", "open_alumni"),
    ]),
    ("Academic Management", [
        ("Academic Year", "open_academic_year"),
        ("Calendar", "open_calendar"),
        ("Year Groups", "open_year_groups"),
        ("Form Groups", "open_form_groups"),
        ("Subjects (KS3 / GCSE)", "open_subjects"),
        ("Options Process", "open_options"),
        ("Timetable", "open_timetable"),
        ("Attendance", "open_attendance"),
        ("Lesson Plans", "open_lesson_plans"),
        ("Cover", "open_cover"),
        ("Cover Agency", "open_cover_agency"),
        ("Homework", "open_homework"),
        ("Assignments", "open_assignments"),
        ("Enrichment & Clubs", "open_enrichment"),
        ("Library", "open_library"),
    ]),
    ("Assessment & Grades", [
        ("Gradebook", "open_gradebook"),
        ("Target Grades", "open_target_grades"),
        ("Baseline Assessment", "open_baseline_assessment"),
        ("Progress 8", "open_progress_8"),
        ("Attainment 8", "open_attainment_8"),
        ("Mock Exams", "open_mock_exams"),
        ("GCSE Exam Entries", "open_exam_entries"),
        ("Results Day", "open_results_day"),
        ("Intervention Tracking", "open_intervention_tracking"),
        ("Early Warning", "open_early_warning"),
        ("Observations", "open_observations"),
        ("Self Assessment", "open_self_assessment"),
        ("Quality Assurance", "open_quality_assurance"),
        ("SEF Builder", "open_sef_builder"),
    ]),
    ("Pastoral & Wellbeing", [
        ("Form Tutors", "open_form_tutors"),
        ("Behaviour Log", "open_behaviour"),
        ("Detentions", "open_detentions"),
        ("Disciplinary", "open_disciplinary"),
        ("Safeguarding", "open_safeguarding"),
        ("SEND", "open_send"),
        ("Pupil Premium", "open_pupil_premium"),
        ("Accessibility", "open_accessibility"),
        ("Wellbeing", "open_wellbeing"),
        ("Pupil Support", "open_pupil_support"),
        ("Peer Mentoring", "open_peer_mentoring"),
        ("Attendance Concerns", "open_attendance_concerns"),
        ("Absence Requests", "open_absence_requests"),
        ("First Aid", "open_first_aid"),
        ("Emergency", "open_emergency"),
        ("Prevent Duty", "open_prevent_duty"),
        ("Equality & Diversity", "open_equality_diversity"),
        ("Complaints", "open_complaints"),
        ("Feedback", "open_feedback"),
        ("Surveys", "open_surveys"),
        ("School Council", "open_school_council"),
        ("Transport", "open_transport"),
    ]),
    ("Staff & Communication", [
        ("Staff Directory", "open_staff"),
        ("Departments", "open_departments"),
        ("Staff HR", "open_staff_hr"),
        ("Staff Absence", "open_staff_absence"),
        ("Staff Wellbeing", "open_staff_wellbeing"),
        ("Recruitment", "open_recruitment"),
        ("Appraisals", "open_appraisals"),
        ("CPD", "open_cpd"),
        ("DBS Checks", "open_dbs_checks"),
        ("Visitors", "open_visitors"),
        ("Parent Contacts", "open_parents"),
        ("Parents' Evenings", "open_parents_evenings"),
        ("Notices & Bulletins", "open_notices"),
        ("Announcements", "open_announcements"),
        ("Notifications", "open_notifications"),
        ("Activity Feed", "open_activity_feed"),
        ("Email / Messaging", "open_messaging"),
        ("Letter Templates", "open_letter_templates"),
        ("Document Hub", "open_document_hub"),
        ("Attachments", "open_attachments"),
    ]),
    ("Finance", [
        ("School Fees", "open_fees"),
        ("Trips & Payments", "open_trips_payments"),
        ("Receipts", "open_receipts"),
        ("Expense Claims", "open_expense_claims"),
        ("Funding", "open_funding"),
        ("School Census", "open_census"),
    ]),
    ("Reports & Analytics", [
        ("Attendance Report", "open_report_attendance"),
        ("Grades Report", "open_report_grades"),
        ("Progress Tracking", "open_progress"),
        ("KPI Dashboard", "open_kpi_dashboard"),
        ("Data Dashboard", "open_data_dashboard"),
        ("Progress Dashboard", "open_progress_dashboard"),
        ("Mobile Dashboard", "open_mobile_dashboard"),
        ("Audit Reports", "open_audit_reports"),
        ("Data Export", "open_data_export"),
        ("Custom Export", "open_export"),
    ]),
    ("Cross-System", [
        ("Student Journey", "open_student_journey"),
        ("Analytics Dashboard", "open_cross_analytics"),
        ("Cross-System Calendar", "open_cross_calendar"),
        ("Central Admin Portal", "open_central_admin"),
        ("GDPR Compliance", "open_cross_gdpr"),
        ("Shared Documents", "open_shared_documents"),
        ("Pupil Self-Service", "open_self_service"),
        ("Certificates", "open_certificates"),
    ]),
    ("System", [
        ("Change Password", "open_change_password"),
        ("Multi-Factor Authentication", "open_mfa"),
        ("User Accounts", "open_user_accounts"),
        ("User Management", "open_user_management"),
        ("Settings", "open_settings"),
        ("Compliance", "open_compliance"),
        ("Governance", "open_governance"),
        ("Policies", "open_policies"),
        ("GDPR", "open_gdpr"),
        ("Risk Management", "open_risk_management"),
        ("Health & Safety", "open_health_safety"),
        ("Assets", "open_assets"),
        ("Multi-Language", "open_multi_language"),
        ("To-Do", "open_todo"),
        ("About", "open_about"),
    ]),
]


def _count_pupils() -> int:
    from education_system.secondarysch_system.modules.domain.pupils.pupils import pupils
    return len(pupils.list_pupils())


def _count_staff() -> int:
    from education_system.secondarysch_system.modules.domain.staff_comms.staff import staff
    return len(staff.list_staff())


def _count_form_groups() -> int:
    from education_system.secondarysch_system.modules.domain.academics.form_groups import form_groups
    return len(form_groups.list_all())


def _safe_count(fn) -> str:
    try:
        return str(fn())
    except Exception:
        logger.exception("Dashboard KPI lookup failed")
        return "—"


class SecondarySchoolMainGUI:
    def __init__(self, auth):
        self.auth = auth
        self.root = tk.Tk()
        self.root.title(SYSTEM_NAME)
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.style.configure("Large.TButton", padding=6)
        self.style.configure("Category.TButton", padding=8, font=("", 10, "bold"))

        self.status_var = tk.StringVar(value="Ready")
        user = (auth.current_user or {}).get("username", "—")
        self.current_user_var = tk.StringVar(value=user)

        self.content_frame: ttk.Frame | None = None
        self._setup_layout()
        self._show_welcome()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_layout(self) -> None:
        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(1, weight=1)

        self._build_header(main)
        self._build_nav(main)
        self._build_content(main)
        self._build_status_bar(main)

    def _build_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, padding=(0, 0, 0, 6))
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(1, weight=1)

        left = ttk.Frame(header)
        left.grid(row=0, column=0, sticky="w")
        ttk.Button(left, text="🏠 Dashboard", command=self._show_welcome).pack(
            side="left", padx=(0, 6))
        ttk.Button(left, text="Logout", command=self._logout).pack(side="left", padx=(0, 6))
        ttk.Button(left, text="Switch to CLI", command=self._switch_to_cli).pack(
            side="left", padx=(0, 6))

        try:
            from education_system.launcher.roles import is_superadmin
            if is_superadmin(self.auth.current_user):
                ttk.Button(
                    left, text="Switch System",
                    command=self._switch_system,
                ).pack(side="left", padx=(0, 6))
        except Exception:
            logger.exception("Could not evaluate superadmin status for header")

        title = ttk.Frame(header)
        title.grid(row=0, column=1)
        ttk.Label(title, text=SYSTEM_NAME, font=("", 14, "bold")).pack()

        right = ttk.Frame(header)
        right.grid(row=0, column=2, sticky="e")
        ttk.Button(right, text="⏻ Shutdown", command=self._shutdown).pack(side="right")

    def _build_nav(self, parent: ttk.Frame) -> None:
        nav = ttk.LabelFrame(parent, text="Navigation", padding=5)
        nav.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        nav.rowconfigure(1, weight=1)
        nav.columnconfigure(0, weight=1)

        canvas = tk.Canvas(nav, highlightthickness=0, width=260)
        scroll = ttk.Scrollbar(nav, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)

        inner.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(win, width=e.width),
        )
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=1, column=0, sticky="nsew")
        scroll.grid(row=1, column=1, sticky="ns")

        def _on_mw(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_mw))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        search_frame = ttk.Frame(nav)
        search_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        search_frame.columnconfigure(0, weight=1)

        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var)
        search_entry.grid(row=0, column=0, sticky="ew")
        self.nav_search_entry = search_entry

        _PLACEHOLDER = "🔍 Search features..."

        def _set_placeholder() -> None:
            search_entry.delete(0, tk.END)
            search_entry.insert(0, _PLACEHOLDER)
            try:
                search_entry.config(foreground="gray")
            except tk.TclError:
                pass

        def _on_focus_in(_e) -> None:
            if search_var.get() == _PLACEHOLDER:
                search_entry.delete(0, tk.END)
                try:
                    search_entry.config(foreground="black")
                except tk.TclError:
                    pass

        def _on_focus_out(_e) -> None:
            if not search_var.get().strip():
                _set_placeholder()

        search_entry.bind("<FocusIn>", _on_focus_in)
        search_entry.bind("<FocusOut>", _on_focus_out)
        _set_placeholder()

        try:
            self.root.bind(
                "<Control-k>",
                lambda _e: (search_entry.focus_set(), search_entry.select_range(0, tk.END)),
                add="+",
            )
        except tk.TclError:
            pass

        categories_holder = ttk.Frame(inner)
        categories_holder.pack(fill="x")
        for group_label, items in NAV_CATEGORIES:
            self._make_category(categories_holder, group_label, items, canvas)

        results_holder = ttk.Frame(inner)

        all_actions: list[tuple[str, str]] = [
            (label, handler)
            for _grp, items in NAV_CATEGORIES
            for label, handler in items
        ]

        def _on_search_change(*_a) -> None:
            for w in results_holder.winfo_children():
                w.destroy()
            q = search_var.get().strip().lower()
            if not q or q == _PLACEHOLDER.lower():
                results_holder.pack_forget()
                categories_holder.pack(fill="x")
            else:
                categories_holder.pack_forget()
                results_holder.pack(fill="x", padx=5)
                seen: set[str] = set()
                for label, handler in all_actions:
                    if handler in seen:
                        continue
                    if q in label.lower():
                        seen.add(handler)
                        cmd = self._handler(handler, label)
                        ttk.Button(results_holder, text=label,
                                   command=cmd).pack(fill="x", pady=1)
                if not seen:
                    ttk.Label(results_holder, text="No matches",
                              foreground="#888").pack(anchor="w", pady=4)
            try:
                inner.update_idletasks()
                canvas.configure(scrollregion=canvas.bbox("all"))
            except tk.TclError:
                pass

        search_var.trace_add("write", _on_search_change)

        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _make_category(
        self,
        parent: ttk.Frame,
        label: str,
        items: list[tuple[str, str]],
        canvas: tk.Canvas,
    ) -> None:
        container = ttk.Frame(parent)
        container.pack(fill="x", pady=2, padx=5)

        state = {"expanded": False, "sub": None}
        btn = ttk.Button(container, text=f"{label}  ▶", style="Category.TButton")
        btn.pack(fill="x")

        def toggle() -> None:
            if state["expanded"]:
                if state["sub"] is not None:
                    state["sub"].pack_forget()
                btn.configure(text=f"{label}  ▶")
                state["expanded"] = False
            else:
                if state["sub"] is None:
                    sub = ttk.Frame(container)
                    for item_label, handler_name in items:
                        cmd = self._handler(handler_name, item_label)
                        ttk.Button(sub, text=item_label, command=cmd).pack(
                            fill="x", pady=1, padx=4)
                    state["sub"] = sub
                state["sub"].pack(fill="x", pady=(2, 4))
                btn.configure(text=f"{label}  ▼")
                state["expanded"] = True
            try:
                parent.update_idletasks()
                canvas.configure(scrollregion=canvas.bbox("all"))
            except tk.TclError:
                pass

        btn.configure(command=toggle)

    def _build_content(self, parent: ttk.Frame) -> None:
        outer = ttk.Frame(parent, padding=0)
        outer.grid(row=1, column=1, sticky="nsew")
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        canvas = tk.Canvas(outer, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        vs = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        vs.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=vs.set)

        self.content_frame = ttk.Frame(canvas, padding=10)
        win = canvas.create_window((0, 0), window=self.content_frame, anchor="nw")
        self.content_frame.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(win, width=e.width),
        )
        self._content_canvas = canvas

    def _build_status_bar(self, parent: ttk.Frame) -> None:
        ttk.Separator(parent, orient="horizontal").grid(
            row=2, column=0, columnspan=2, sticky="new")
        bar = ttk.Frame(parent)
        bar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        bar.columnconfigure(0, weight=1)
        bar.columnconfigure(1, weight=1)
        bar.columnconfigure(2, weight=1)

        left = ttk.Frame(bar, padding=(2, 4))
        left.grid(row=0, column=0, sticky="w")
        ttk.Label(left, text="Status: ", foreground="#555").pack(side="left")
        ttk.Label(left, textvariable=self.status_var).pack(side="left")

        centre = ttk.Frame(bar, padding=(2, 4))
        centre.grid(row=0, column=1)
        ttk.Label(centre, text="User: ", foreground="#555").pack(side="left")
        ttk.Label(centre, textvariable=self.current_user_var).pack(side="left")

        right = ttk.Frame(bar, padding=(2, 4))
        right.grid(row=0, column=2, sticky="e")
        ttk.Label(right, text=FOOTER_LABEL, foreground="#555").pack(side="left")
        ttk.Label(right, text=" · ", foreground="#aaa").pack(side="left")
        ttk.Label(right, text=f"v{VERSION}", foreground="#555").pack(side="left")

    def _clear_content(self) -> None:
        if self.content_frame is None:
            return
        for w in self.content_frame.winfo_children():
            w.destroy()

    def _show_welcome(self) -> None:
        self._clear_content()
        assert self.content_frame is not None
        root = self.content_frame
        root.columnconfigure(0, weight=1)

        now = datetime.now()
        hour = now.hour
        if hour < 12:
            greet = "Good morning"
        elif hour < 18:
            greet = "Good afternoon"
        else:
            greet = "Good evening"
        user = self.current_user_var.get()

        header = ttk.Frame(root)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(
            header, text=f"{greet}, {user}",
            font=("", 20, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text=now.strftime("%A, %d %B %Y · %H:%M"),
            foreground="#666",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Button(header, text="↻ Refresh",
                   command=self._show_welcome).grid(
            row=0, column=1, rowspan=2, sticky="e", padx=(8, 0))

        kpis = [
            ("Pupils", _safe_count(_count_pupils), "On roll"),
            ("Staff", _safe_count(_count_staff), "Active records"),
            ("Form Groups", _safe_count(_count_form_groups), "Years 7–11"),
            ("Today's Attendance", "—", "Awaiting marks"),
        ]
        kpi_row = ttk.Frame(root)
        kpi_row.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        for i in range(len(kpis)):
            kpi_row.columnconfigure(i, weight=1, uniform="kpi")
        for i, (label, value, hint) in enumerate(kpis):
            tile = ttk.LabelFrame(kpi_row, padding=12)
            tile.grid(row=0, column=i, padx=4, sticky="nsew")
            ttk.Label(tile, text=label, foreground="#666").pack(anchor="w")
            ttk.Label(tile, text=value, font=("", 22, "bold")).pack(
                anchor="w", pady=(2, 0))
            ttk.Label(tile, text=hint, foreground="#888", font=("", 9)).pack(
                anchor="w", pady=(2, 0))

        actions = ttk.LabelFrame(root, text="Quick actions", padding=8)
        actions.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        quick = [
            ("Add Pupil", self.open_add_pupil),
            ("Search Pupils", self.open_search_pupils),
            ("Take Register", lambda: self._show_stub("Attendance")),
            ("Timetable", lambda: self._show_stub("Timetable")),
            ("Gradebook", lambda: self._show_stub("Gradebook")),
            ("Behaviour Log", lambda: self._show_stub("Behaviour Log")),
        ]
        for i, (lbl, cmd) in enumerate(quick):
            ttk.Button(actions, text=lbl, command=cmd, style="Large.TButton").grid(
                row=0, column=i, padx=4, pady=2, sticky="ew")
            actions.columnconfigure(i, weight=1, uniform="qa")

        info = ttk.LabelFrame(root, text="Getting started", padding=10)
        info.grid(row=3, column=0, sticky="nsew")
        ttk.Label(
            info,
            text=(
                "Domain modules for the Secondary School System have not been "
                "wired up yet. Every sidebar action opens a placeholder — "
                "use them as a map of the features that will land here."
            ),
            wraplength=720, foreground="#555", justify="left",
        ).pack(anchor="w")

        self.status_var.set("Ready")

    def _handler(self, name: str, label: str) -> Callable[[], None]:
        method = getattr(self, name, None)
        if callable(method):
            return method
        return lambda: self._show_stub(label)

    def _show_stub(self, label: str) -> None:
        self._clear_content()
        assert self.content_frame is not None
        ttk.Label(self.content_frame, text=label, font=("", 16, "bold")).pack(
            anchor="w", pady=(0, 8))
        ttk.Label(
            self.content_frame,
            text=f"{label} module is not yet implemented.",
            foreground="#555",
        ).pack(anchor="w")
        self.status_var.set(f"Opened: {label}")

    def _logout(self) -> None:
        from education_system import switch as _switch
        try:
            self.auth.logout()
        except Exception:
            pass
        _switch.request_logout("gui")
        self.root.destroy()

    def _switch_to_cli(self) -> None:
        if not messagebox.askyesno(
                "Switch to CLI",
                "Close the GUI and continue in the CLI?",
                parent=self.root):
            return
        from education_system import switch as _switch
        _switch.request_switch("school", "cli")
        self.root.destroy()

    def _switch_system(self) -> None:
        from education_system import switch as _switch
        from education_system.launcher.system_switch import pick_system_gui
        target = pick_system_gui(self.root, self.auth.current_user, "school")
        if not target:
            return
        _switch.request_switch(target, "gui")
        self.root.destroy()

    def _shutdown(self) -> None:
        if messagebox.askyesno(
                "Shutdown", f"Shut down the {SYSTEM_NAME}?", parent=self.root):
            try:
                self.auth.logout()
            except Exception:
                pass
            self.root.destroy()
            sys.exit(0)

    def _on_close(self) -> None:
        try:
            self.auth.logout()
        except Exception:
            pass
        self.root.destroy()

    def open_pupil_directory(self) -> None:
        from education_system.secondarysch_system.modules.domain.pupils.pupils import (
            pupil_views,
        )
        pupil_views.open_directory(self)

    def open_add_pupil(self) -> None:
        from education_system.secondarysch_system.modules.domain.pupils.pupils import (
            pupil_views,
        )
        pupil_views.open_add_pupil(self)

    def open_search_pupils(self) -> None:
        from education_system.secondarysch_system.modules.domain.pupils.pupils import (
            pupil_views,
        )
        pupil_views.open_search(self)

    def open_advanced_search(self) -> None:
        from education_system.secondarysch_system.modules.domain.pupils.pupils import (
            pupil_views,
        )
        pupil_views.open_advanced_search(self)

    def open_admissions(self) -> None:
        from education_system.secondarysch_system.modules.domain.pupils.admissions import (
            admissions_views,
        )
        admissions_views.open_admissions(self)

    def open_enrolment(self) -> None:
        from education_system.secondarysch_system.modules.domain.pupils.enrolment import (
            enrolment_views,
        )
        enrolment_views.open_enrolment(self)

    def open_mfa(self) -> None:
        from education_system.secondarysch_system.modules.domain.governance.mfa import (
            mfa_views,
        )
        mfa_views.open_mfa(self)

    def open_pupil_profile(self) -> None:
        from education_system.secondarysch_system.modules.domain.pupils.pupils import (
            pupil_views,
        )
        pupil_views.open_profile(self)

    def open_multi_language(self) -> None:
        from education_system.shared.i18n.selector_gui import show_language_selector
        show_language_selector(self.root)

    def open_onboarding(self) -> None:
        from education_system.secondarysch_system.modules.domain.pupils.onboarding import (
            onboarding_views,
        )
        onboarding_views.open_onboarding(self)

    def open_bulk_operations(self) -> None:
        from education_system.secondarysch_system.modules.domain.pupils.bulk_operations import (
            bulk_operations_views,
        )
        bulk_operations_views.open_bulk_operations(self)

    def open_alumni(self) -> None:
        from education_system.secondarysch_system.modules.domain.pupils.alumni import (
            alumni_views,
        )
        alumni_views.open_alumni(self)

    def open_academic_year(self) -> None:
        from education_system.secondarysch_system.modules.domain.academics.academic_year import (
            academic_year_views,
        )
        academic_year_views.open_academic_year_window(self)

    def open_calendar(self) -> None:
        from education_system.secondarysch_system.modules.domain.academics.calendar import (
            calendar_views,
        )
        calendar_views.open_calendar_window(self)

    def open_year_groups(self) -> None:
        from education_system.secondarysch_system.modules.domain.academics.year_groups import (
            year_groups_views,
        )
        year_groups_views.open_year_groups(self)

    def open_form_groups(self) -> None:
        from education_system.secondarysch_system.modules.domain.academics.form_groups import (
            form_groups_views,
        )
        form_groups_views.open_form_groups(self)

    def open_subjects(self) -> None:
        from education_system.secondarysch_system.modules.domain.academics.subjects import (
            subjects_views,
        )
        subjects_views.open_subjects(self)

    def open_options(self) -> None:
        from education_system.secondarysch_system.modules.domain.academics.options import (
            options_views,
        )
        options_views.open_options(self)

    def open_timetable(self) -> None:
        from education_system.secondarysch_system.modules.domain.academics.timetable import (
            timetable_views,
        )
        timetable_views.open_timetable(self)

    def open_attendance(self) -> None:
        from education_system.secondarysch_system.modules.domain.academics.attendance import (
            attendance_views,
        )
        attendance_views.open_attendance(self)

    def open_lesson_plans(self) -> None:
        from education_system.secondarysch_system.modules.domain.academics.lesson_plans import (
            lesson_plans_views,
        )
        lesson_plans_views.open_lesson_plans(self)

    def open_cover(self) -> None:
        from education_system.secondarysch_system.modules.domain.academics.cover import (
            cover_views,
        )
        cover_views.open_cover(self)

    def open_cover_agency(self) -> None:
        from education_system.secondarysch_system.modules.domain.academics.cover_agency import (
            cover_agency_views,
        )
        cover_agency_views.open_cover_agency(self)

    def open_homework(self) -> None:
        from education_system.secondarysch_system.modules.domain.academics.homework import (
            homework_views,
        )
        homework_views.open_homework(self)

    def open_assignments(self) -> None:
        from education_system.secondarysch_system.modules.domain.academics.assignments import (
            assignments_views,
        )
        assignments_views.open_assignments(self)

    def open_enrichment(self) -> None:
        from education_system.secondarysch_system.modules.domain.academics.enrichment import (
            enrichment_views,
        )
        enrichment_views.open_enrichment(self)

    def open_library(self) -> None:
        from education_system.secondarysch_system.modules.domain.academics.library import (
            library_views,
        )
        library_views.open_library(self)

    def open_target_grades(self) -> None:
        from education_system.secondarysch_system.modules.domain.assessment.target_grades import (
            target_grades_views,
        )
        target_grades_views.open_target_grades(self)

    def open_gradebook(self) -> None:
        from education_system.secondarysch_system.modules.domain.assessment.gradebook import (
            gradebook_views,
        )
        gradebook_views.open_gradebook(self)

    def open_baseline_assessment(self) -> None:
        from education_system.secondarysch_system.modules.domain.assessment.baseline_assessment import (
            baseline_assessment_views,
        )
        baseline_assessment_views.open_baseline_assessment(self)

    def open_mock_exams(self) -> None:
        from education_system.secondarysch_system.modules.domain.assessment.mock_exams import (
            mock_exams_views,
        )
        mock_exams_views.open_mock_exams(self)

    def open_attainment_8(self) -> None:
        from education_system.secondarysch_system.modules.domain.assessment.attainment_8 import (
            attainment_8_views,
        )
        attainment_8_views.open_attainment_8(self)

    def open_progress_8(self) -> None:
        from education_system.secondarysch_system.modules.domain.assessment.progress_8 import (
            progress_8_views,
        )
        progress_8_views.open_progress_8(self)

    def open_exam_entries(self) -> None:
        from education_system.secondarysch_system.modules.domain.assessment.exam_entries import (
            exam_entries_views,
        )
        exam_entries_views.open_exam_entries(self)

    def open_results_day(self) -> None:
        from education_system.secondarysch_system.modules.domain.assessment.exam_results import (
            exam_results_views,
        )
        exam_results_views.open_results_day(self)

    def open_intervention_tracking(self) -> None:
        from education_system.secondarysch_system.modules.domain.assessment.intervention_tracking import (
            intervention_tracking_views,
        )
        intervention_tracking_views.open_intervention_tracking(self)

    def open_early_warning(self) -> None:
        from education_system.secondarysch_system.modules.domain.assessment.early_warning import (
            early_warning_views,
        )
        early_warning_views.open_early_warning(self)

    def open_observations(self) -> None:
        from education_system.secondarysch_system.modules.domain.assessment.observations import (
            observations_views,
        )
        observations_views.open_observations(self)

    def open_self_assessment(self) -> None:
        from education_system.secondarysch_system.modules.domain.assessment.self_assessment import (
            self_assessment_views,
        )
        self_assessment_views.open_self_assessment(self)

    def open_quality_assurance(self) -> None:
        from education_system.secondarysch_system.modules.domain.assessment.quality_assurance import (
            quality_assurance_views,
        )
        quality_assurance_views.open_quality_assurance(self)

    def open_sef_builder(self) -> None:
        from education_system.secondarysch_system.modules.domain.assessment.sef_builder import (
            sef_builder_views,
        )
        sef_builder_views.open_sef_builder(self)

    def open_form_tutors(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.form_tutors import (
            form_tutors_views,
        )
        form_tutors_views.open_form_tutors(self)

    def open_behaviour(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.behaviour import (
            behaviour_views,
        )
        behaviour_views.open_behaviour(self)

    def open_detentions(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.detentions import (
            detentions_views,
        )
        detentions_views.open_detentions(self)

    def open_disciplinary(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.disciplinary import (
            disciplinary_views,
        )
        disciplinary_views.open_disciplinary(self)

    def open_pupil_premium(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.pupil_premium import (
            pupil_premium_views,
        )
        pupil_premium_views.open_pupil_premium(self)

    def open_send(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.send import (
            send_views,
        )
        send_views.open_send(self)

    def open_safeguarding(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.safeguarding import (
            safeguarding_views,
        )
        safeguarding_views.open_safeguarding(self)

    def open_accessibility(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.accessibility import (
            accessibility_views,
        )
        accessibility_views.open_accessibility(self)

    def open_wellbeing(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.wellbeing import (
            wellbeing_views,
        )
        wellbeing_views.open_wellbeing(self)

    def open_pupil_support(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.pupil_support import (
            pupil_support_views,
        )
        pupil_support_views.open_pupil_support(self)

    def open_peer_mentoring(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.peer_mentoring import (
            peer_mentoring_views,
        )
        peer_mentoring_views.open_peer_mentoring(self)

    def open_attendance_concerns(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.attendance_concerns import (
            attendance_concerns_views,
        )
        attendance_concerns_views.open_attendance_concerns(self)

    def open_absence_requests(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.absence_requests import (
            absence_requests_views,
        )
        absence_requests_views.open_absence_requests(self)

    def open_first_aid(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.first_aid import (
            first_aid_views,
        )
        first_aid_views.open_first_aid(self)

    def open_emergency(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.emergency import (
            emergency_views,
        )
        emergency_views.open_emergency(self)

    def open_prevent_duty(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.prevent_duty import (
            prevent_duty_views,
        )
        prevent_duty_views.open_prevent_duty(self)

    def open_equality_diversity(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.equality_diversity import (
            equality_diversity_views,
        )
        equality_diversity_views.open_equality_diversity_window(self)

    def open_complaints(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.complaints import (
            complaints_views,
        )
        complaints_views.open_complaints_window(self)

    def open_feedback(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.feedback import (
            feedback_views,
        )
        feedback_views.open_feedback_window(self)

    def open_surveys(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.surveys import (
            surveys_views,
        )
        surveys_views.open_surveys_window(self)

    def open_school_council(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.school_council import (
            school_council_views,
        )
        school_council_views.open_school_council_window(self)

    def open_transport(self) -> None:
        from education_system.secondarysch_system.modules.domain.pastoral.transport import (
            transport_views,
        )
        transport_views.open_transport_window(self)

    def open_staff(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.staff import (
            staff_views,
        )
        staff_views.open_directory(self)

    def open_staff_hr(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.staff_hr import (
            staff_hr_views,
        )
        staff_hr_views.open_staff_hr_window(self)

    def open_departments(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.departments import (
            departments_views,
        )
        departments_views.open_departments_window(self)

    def open_staff_absence(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.staff_absence import (
            staff_absence_views,
        )
        staff_absence_views.open_staff_absence_window(self)

    def open_staff_wellbeing(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.staff_wellbeing import (
            staff_wellbeing_views,
        )
        staff_wellbeing_views.open_staff_wellbeing_window(self)

    def open_recruitment(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.recruitment import (
            recruitment_views,
        )
        recruitment_views.open_recruitment_window(self)

    def open_appraisals(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.appraisals import (
            appraisals_views,
        )
        appraisals_views.open_appraisals_window(self)

    def open_cpd(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.cpd import (
            cpd_views,
        )
        cpd_views.open_cpd_window(self)

    def open_dbs_checks(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.dbs_checks import (
            dbs_checks_views,
        )
        dbs_checks_views.open_dbs_checks_window(self)

    def open_visitors(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.visitors import (
            visitors_views,
        )
        visitors_views.open_visitors_window(self)

    def open_parents(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.parent_contacts import (
            parent_contacts_views,
        )
        parent_contacts_views.open_directory(self)

    def open_parents_evenings(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.parents_evenings import (
            parents_evenings_views,
        )
        parents_evenings_views.open_parents_evenings_window(self)

    def open_notices(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.notices import (
            notices_views,
        )
        notices_views.open_notices_window(self)

    def open_announcements(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.announcements import (
            announcements_views,
        )
        announcements_views.open_announcements_window(self)

    def open_notifications(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.notifications import (
            notifications_views,
        )
        notifications_views.open_notifications_window(self)

    def open_activity_feed(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.activity_feed import (
            activity_feed_views,
        )
        activity_feed_views.open_activity_feed_window(self)

    def open_messaging(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.messages import (
            messages_views,
        )
        messages_views.open_messages_window(self)

    def open_letter_templates(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.letter_templates import (
            letter_templates_views,
        )
        letter_templates_views.open_letter_templates_window(self)

    def open_document_hub(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.document_hub import (
            document_hub_views,
        )
        document_hub_views.open_document_hub_window(self)

    def open_attachments(self) -> None:
        from education_system.secondarysch_system.modules.domain.staff_comms.attachments import (
            attachments_views,
        )
        attachments_views.open_attachments_window(self)

    def open_fees(self) -> None:
        from education_system.secondarysch_system.modules.domain.finance.fees import (
            fees_views,
        )
        fees_views.open_fees_window(self)

    def open_trips_payments(self) -> None:
        from education_system.secondarysch_system.modules.domain.finance.trips import (
            trips_views,
        )
        trips_views.open_trips_window(self)

    def open_receipts(self) -> None:
        from education_system.secondarysch_system.modules.domain.finance.receipts import (
            receipts_views,
        )
        receipts_views.open_receipts_window(self)

    def open_expense_claims(self) -> None:
        from education_system.secondarysch_system.modules.domain.finance.expense_claims import (
            expense_claims_views,
        )
        expense_claims_views.open_expense_claims_window(self)

    def open_funding(self) -> None:
        from education_system.secondarysch_system.modules.domain.finance.funding import (
            funding_views,
        )
        funding_views.open_funding_window(self)

    def open_census(self) -> None:
        from education_system.secondarysch_system.modules.domain.finance.census import (
            census_views,
        )
        census_views.open_census_window(self)

    def open_progress(self) -> None:
        from education_system.secondarysch_system.modules.domain.reports.progress import (
            progress_views,
        )
        progress_views.open_progress_window(self)

    def open_kpi_dashboard(self) -> None:
        from education_system.secondarysch_system.modules.domain.reports.kpi_dashboard import (
            kpi_dashboard_views,
        )
        kpi_dashboard_views.open_kpi_dashboard_window(self)

    def open_data_dashboard(self) -> None:
        from education_system.secondarysch_system.modules.domain.reports.data_dashboard import (
            data_dashboard_views,
        )
        data_dashboard_views.open_data_dashboard_window(self)

    def open_progress_dashboard(self) -> None:
        from education_system.secondarysch_system.modules.domain.reports.progress_dashboard import (
            progress_dashboard_views,
        )
        progress_dashboard_views.open_progress_dashboard_window(self)

    def open_mobile_dashboard(self) -> None:
        from education_system.secondarysch_system.modules.domain.reports.mobile_dashboard import (
            mobile_dashboard_views,
        )
        mobile_dashboard_views.open_mobile_dashboard_window(self)

    def open_audit_reports(self) -> None:
        from education_system.secondarysch_system.modules.domain.reports.audit_reports import (
            audit_reports_views,
        )
        audit_reports_views.open_audit_reports_window(self)

    def open_data_export(self) -> None:
        from education_system.secondarysch_system.modules.domain.reports.data_export import (
            data_export_views,
        )
        data_export_views.open_data_export_window(self)

    def open_export(self) -> None:
        from education_system.secondarysch_system.modules.domain.reports.custom_export import (
            custom_export_views,
        )
        custom_export_views.open_custom_export_window(self)

    def open_change_password(self) -> None:
        from education_system.secondarysch_system.modules.shared.gui import (
            change_password_views,
        )
        change_password_views.open_change_password_dialog(self.root, auth=self.auth)

    def open_user_accounts(self) -> None:
        from education_system.secondarysch_system.modules.shared.gui import (
            user_accounts_views,
        )
        user_accounts_views.open_user_accounts_window(self.root, auth=self.auth)

    def open_settings(self) -> None:
        from education_system.secondarysch_system.modules.shared.gui import (
            settings_views,
        )
        settings_views.open_settings_window(self.root, auth=self.auth)

    def open_about(self) -> None:
        from education_system.secondarysch_system.modules.shared.gui import (
            about_views,
        )
        about_views.open_about_window(self.root, auth=self.auth)

    # ── Cross-System (shared frames from education_system/shared) ──
    def _open_cross_frame(self, FrameClass, label: str) -> None:
        self._clear_content()
        assert self.content_frame is not None
        try:
            frame = FrameClass(self.content_frame, auth=self.auth)
        except Exception as e:
            logger.exception("Failed to open cross-system frame %s", label)
            ttk.Label(self.content_frame,
                      text=f"{label}\n\nCould not open: {e}",
                      foreground="#a00").pack(anchor="w")
            return
        frame.pack(fill="both", expand=True)
        self.status_var.set(f"Opened: {label}")

    def open_student_journey(self) -> None:
        from education_system.shared.cross_system.journey_gui import (
            StudentJourneyFrame,
        )
        self._open_cross_frame(StudentJourneyFrame, "Student Journey")

    def open_cross_analytics(self) -> None:
        from education_system.shared.analytics.analytics_gui import (
            AnalyticsDashboardFrame,
        )
        self._open_cross_frame(AnalyticsDashboardFrame, "Analytics Dashboard")

    def open_cross_calendar(self) -> None:
        from education_system.shared.calendar.calendar_gui import (
            CrossSystemCalendarFrame,
        )
        self._open_cross_frame(CrossSystemCalendarFrame, "Cross-System Calendar")

    def open_central_admin(self) -> None:
        from education_system.shared.admin_portal.admin_gui import (
            CentralAdminFrame,
        )
        self._open_cross_frame(CentralAdminFrame, "Central Admin Portal")

    def open_cross_gdpr(self) -> None:
        from education_system.shared.gdpr.gdpr_gui import (
            GDPRComplianceFrame,
        )
        self._open_cross_frame(GDPRComplianceFrame, "GDPR Compliance")

    def open_shared_documents(self) -> None:
        from education_system.shared.documents.document_gui import (
            SharedDocumentsFrame,
        )
        self._open_cross_frame(SharedDocumentsFrame, "Shared Documents")

    def open_self_service(self) -> None:
        from education_system.shared.student_portal.portal_gui import (
            StudentSelfServiceFrame,
        )
        self._open_cross_frame(StudentSelfServiceFrame, "Pupil Self-Service")

    def open_certificates(self) -> None:
        from education_system.shared.certificates.certificates_gui import (
            CertificatesGUI,
        )
        self._open_cross_frame(CertificatesGUI, "Certificates")

    def open_compliance(self) -> None:
        from education_system.secondarysch_system.modules.domain.governance.compliance import (
            compliance_views,
        )
        compliance_views.open_compliance_window(self)

    def open_governance(self) -> None:
        from education_system.secondarysch_system.modules.domain.governance.governance import (
            governance_views,
        )
        governance_views.open_governance_window(self)

    def open_policies(self) -> None:
        from education_system.secondarysch_system.modules.domain.governance.policies import (
            policies_views,
        )
        policies_views.open_policies_window(self)

    def open_gdpr(self) -> None:
        from education_system.secondarysch_system.modules.domain.governance.gdpr import (
            gdpr_views,
        )
        gdpr_views.open_gdpr_window(self)

    def open_risk_management(self) -> None:
        from education_system.secondarysch_system.modules.domain.governance.risk_management import (
            risk_management_views,
        )
        risk_management_views.open_risk_management_window(self)

    def open_health_safety(self) -> None:
        from education_system.secondarysch_system.modules.domain.governance.health_safety import (
            health_safety_views,
        )
        health_safety_views.open_health_safety_window(self)

    def open_assets(self) -> None:
        from education_system.secondarysch_system.modules.domain.governance.assets import (
            assets_views,
        )
        assets_views.open_assets_window(self)

    def open_todo(self) -> None:
        from education_system.secondarysch_system.modules.domain.governance.todo import (
            todo_views,
        )
        todo_views.open_todo_window(self)

    def open_user_management(self) -> None:
        from education_system.secondarysch_system.modules.domain.governance.user_management import (
            user_management_views,
        )
        user_management_views.open_user_management_window(self)


def run(user_info=None, role=None, shared_auth=None) -> int:
    if shared_auth is None or not getattr(shared_auth, "current_user", None):
        logger.error("secondarysch GUI invoked without a shared_auth session")
        raise RuntimeError(
            "secondarysch_system GUI must be launched via run.py — "
            "no standalone login is available."
        )
    cu = shared_auth.current_user or {}
    logger.info("Secondary-school GUI starting for user=%s role=%s",
                cu.get("username"), role)
    app = SecondarySchoolMainGUI(shared_auth)
    app.root.mainloop()
    logger.info("Secondary-school GUI exited for user=%s", cu.get("username"))
    return 0


if __name__ == "__main__":
    print("Launch via: python run.py --gui  (then choose Secondary School)")
    raise SystemExit(2)
