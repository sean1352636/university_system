"""Tk GUI main menu for the Sixth Form System.

Layout mirrors `university_system` `UnifiedManagementGUI`:

    row 0 — header (login/logout · switch-to-CLI · shutdown)
    row 1 — left navigation (accordion of categories) + right content area
    row 2 — status bar (status · current user · system / version)
"""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Callable
from education_system.sixthform_system import SYSTEM_NAME

logger = logging.getLogger(__name__)

VERSION = "0.1.0"

# Short label shown in the bottom-right of the status bar. Overridden
# by sibling systems (e.g. secondarysch_system) that re-use this GUI.
FOOTER_LABEL = "Sixth Form"


# ── Feature catalogue ────────────────────────────────────────────────
# Each top-level entry is one accordion category in the sidebar; each
# tuple inside is one button ``(label, handler_attr_name)``. The
# handlers are simple methods on `SixthFormMainGUI` that swap content
# into the right-hand pane — real domain wiring goes in later.

NAV_CATEGORIES: list[tuple[str, list[tuple[str, str]]]] = [
    ("Student Management", [
        ("Student Directory", "open_student_directory"),
        ("Add Student", "open_add_student"),
        ("Search Students", "open_search_students"),
        ("Advanced Search", "open_advanced_search"),
        ("Student Profile", "open_student_profile"),
        ("Admissions", "open_admissions"),
        ("Enrolment", "open_enrolment"),
        ("Onboarding", "open_onboarding"),
        ("Bulk Operations", "open_bulk_operations"),
        ("Alumni", "open_alumni"),
    ]),
    ("Academic Management", [
        ("Academic Year", "open_academic_year"),
        ("Calendar", "open_calendar"),
        ("Courses", "open_courses"),
        ("Subjects & A-Levels", "open_subjects"),
        ("Class Groups", "open_class_groups"),
        ("Timetable", "open_timetable"),
        ("Attendance", "open_attendance"),
        ("Lesson Plans", "open_lesson_plans"),
        ("Cover", "open_cover"),
        ("Cover Agency", "open_cover_agency"),
        ("Homework & Coursework", "open_homework"),
        ("Assignments", "open_assignments"),
        ("Enrichment", "open_enrichment"),
        ("Library", "open_library"),
        ("Study Planner", "open_study_planner"),
        ("EPQ", "open_epq"),
        ("Work Experience", "open_work_experience"),
        ("Room Booking", "open_room_booking"),
    ]),
    ("Assessment & Grades", [
        ("Gradebook", "open_gradebook"),
        ("Predicted Grades", "open_predicted_grades"),
        ("Baseline Assessment", "open_baseline_assessment"),
        ("Target Setting", "open_target_setting"),
        ("ILP", "open_ilp"),
        ("Intervention Tracking", "open_intervention_tracking"),
        ("Early Warning", "open_early_warning"),
        ("Value Added", "open_value_added"),
        ("Mock Exams", "open_mock_exams"),
        ("Exam Entries", "open_exam_entries"),
        ("Results Day", "open_results_day"),
        ("Observations", "open_observations"),
        ("Self Assessment", "open_self_assessment"),
        ("Quality Assurance", "open_quality_assurance"),
        ("SEF Builder", "open_sef_builder"),
    ]),
    ("UCAS & Careers", [
        ("UCAS Applications", "open_ucas"),
        ("Personal Statements", "open_personal_statements"),
        ("References", "open_references"),
        ("University Offers", "open_offers"),
        ("University Visits", "open_university_visits"),
        ("Apprenticeships", "open_apprenticeships"),
        ("Careers Guidance", "open_careers"),
        ("Destinations", "open_destinations"),
    ]),
    ("Pastoral & Wellbeing", [
        ("Tutor Groups", "open_tutor_groups"),
        ("Behaviour Log", "open_behaviour"),
        ("Disciplinary", "open_disciplinary"),
        ("Safeguarding", "open_safeguarding"),
        ("SEND", "open_send"),
        ("Accessibility", "open_accessibility"),
        ("Wellbeing", "open_wellbeing"),
        ("Student Wellbeing", "open_student_wellbeing"),
        ("Student Support", "open_student_support"),
        ("Peer Mentoring", "open_peer_mentoring"),
        ("Attendance Concerns", "open_attendance_concerns"),
        ("Absence Requests", "open_absence_requests"),
        ("First Aid", "open_first_aid"),
        ("Medical Records", "open_medical_records"),
        ("Emergency", "open_emergency"),
        ("Prevent Duty", "open_prevent_duty"),
        ("Equality & Diversity", "open_equality_diversity"),
        ("Complaints", "open_complaints"),
        ("Feedback", "open_feedback"),
        ("Surveys", "open_surveys"),
        ("Student Council", "open_student_council"),
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
    ("Finance & Bursaries", [
        ("Finance Dashboard", "open_finance_hub"),
        ("Fees", "open_fees"),
        ("Bursary Applications", "open_bursaries"),
        ("Trips & Payments", "open_trips_payments"),
        ("Receipts", "open_receipts"),
        ("Expense Claims", "open_expense_claims"),
        ("Funding", "open_funding"),
        ("Census ILR", "open_census_ilr"),
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
        ("Student Self-Service", "open_self_service"),
        ("Certificates", "open_certificates"),
        ("University Visits → CRM", "open_university_visits_crm"),
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


class SixthFormMainGUI:
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

        # Sign the user out after a stretch of inactivity, matching
        # the university system's 30-minute default. Configurable via
        # the EDU_SIXTHFORM_IDLE_TIMEOUT_MINUTES env var.
        try:
            from education_system.sixthform_system.modules.shared.gui.idle_timeout import (
                IdleTimeoutWatcher,
            )
            self._idle_watcher = IdleTimeoutWatcher(
                self.root, on_timeout=self._idle_logout)
            self._idle_watcher.start()
        except Exception:
            logger.exception("Could not start idle-timeout watcher")
            self._idle_watcher = None

    # ── Layout scaffolding ───────────────────────────────────────────
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

        # Superadmins (admin role on the university system) can hop
        # straight to another system without going through the login.
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

        # ── Search bar (filters across all sidebar actions) ──────────
        search_frame = ttk.Frame(nav)
        search_frame.grid(row=0, column=0, columnspan=2, sticky="ew",
                          pady=(0, 6))
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

        # Categories area (always present, hidden while searching)
        categories_holder = ttk.Frame(inner)
        categories_holder.pack(fill="x")
        for group_label, items in NAV_CATEGORIES:
            self._make_category(categories_holder, group_label, items, canvas)

        # Flat results area shown only when there's a query
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

    # ── Content helpers ──────────────────────────────────────────────
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

        kpis = self._gather_kpis()
        kpi_row = ttk.Frame(root)
        kpi_row.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        for i in range(len(kpis)):
            kpi_row.columnconfigure(i, weight=1, uniform="kpi")
        for i, (label, value, hint) in enumerate(kpis):
            self._make_kpi_tile(kpi_row, i, label, value, hint)

        actions = ttk.LabelFrame(root, text="Quick actions", padding=8)
        actions.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        quick = [
            ("Add Student", self.open_add_student),
            ("Search Students", self.open_search_students),
            ("Take Register", self.open_attendance),
            ("Timetable", self.open_timetable),
            ("Gradebook", self.open_gradebook),
            ("Behaviour Log", self.open_behaviour),
        ]
        for i, (lbl, cmd) in enumerate(quick):
            ttk.Button(actions, text=lbl, command=cmd, style="Large.TButton").grid(
                row=0, column=i, padx=4, pady=2, sticky="ew")
            actions.columnconfigure(i, weight=1, uniform="qa")

        lower = ttk.Frame(root)
        lower.grid(row=3, column=0, sticky="nsew")
        lower.columnconfigure(0, weight=1, uniform="lower")
        lower.columnconfigure(1, weight=1, uniform="lower")
        root.rowconfigure(3, weight=1)

        self._build_recent_students_panel(lower)
        self._build_recent_behaviour_panel(lower)

        self.status_var.set("Ready")

    # ── Dashboard helpers ────────────────────────────────────────────
    def _make_kpi_tile(
        self,
        parent: ttk.Frame,
        column: int,
        label: str,
        value: str,
        hint: str,
    ) -> None:
        tile = ttk.LabelFrame(parent, padding=12)
        tile.grid(row=0, column=column, padx=4, sticky="nsew")
        ttk.Label(tile, text=label, foreground="#666").pack(anchor="w")
        ttk.Label(tile, text=value, font=("", 22, "bold")).pack(
            anchor="w", pady=(2, 0))
        ttk.Label(tile, text=hint, foreground="#888", font=("", 9)).pack(
            anchor="w", pady=(2, 0))

    def _gather_kpis(self) -> list[tuple[str, str, str]]:
        today = datetime.now().strftime("%Y-%m-%d")

        student_count = self._safe_count(
            "education_system.sixthform_system.modules.domain.students.students.students",
            "list_students",
        )
        staff_count = self._safe_count(
            "education_system.sixthform_system.modules.domain.staff_comms.staff.staff",
            "list_staff",
        )
        course_count = self._safe_count(
            "education_system.sixthform_system.modules.domain.academics.courses.courses",
            "list_courses",
        )

        att_pct, att_hint = self._today_attendance_pct(today)

        return [
            ("Students", str(student_count) if student_count is not None else "—",
             "Enrolled in roll"),
            ("Staff", str(staff_count) if staff_count is not None else "—",
             "Active records"),
            ("Courses", str(course_count) if course_count is not None else "—",
             "Catalogue size"),
            ("Today's Attendance", att_pct, att_hint),
        ]

    def _safe_count(self, module_path: str, func_name: str) -> int | None:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            fn = getattr(mod, func_name, None)
            if fn is None:
                return None
            rows = fn()
            return len(rows) if rows is not None else 0
        except Exception:
            logger.debug("KPI count failed for %s.%s", module_path, func_name,
                         exc_info=True)
            return None

    def _today_attendance_pct(self, today: str) -> tuple[str, str]:
        try:
            from education_system.sixthform_system.modules.domain.academics.attendance import (
                attendance as att,
            )
            rows = att.list_records(date=today)
            if not rows:
                return ("—", "No marks recorded today")
            present_like = {"Present", "Late"}
            present = sum(1 for r in rows if getattr(r, "status", None) in present_like)
            pct = (present / len(rows)) * 100
            return (f"{pct:.0f}%", f"{present}/{len(rows)} marked present/late")
        except Exception:
            logger.debug("Today's attendance KPI failed", exc_info=True)
            return ("—", "Attendance not available")

    def _build_recent_students_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.LabelFrame(parent, text="Recently added students", padding=8)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        try:
            from education_system.sixthform_system.modules.domain.students.students import (
                students as sdata,
            )
            rows = sdata.list_students() or []
        except Exception:
            rows = []

        if not rows:
            ttk.Label(panel, text="No students on roll yet.",
                      foreground="#777").pack(anchor="w")
            ttk.Button(panel, text="Add the first student",
                       command=self.open_add_student).pack(anchor="w", pady=(6, 0))
            return

        try:
            recent = sorted(
                rows,
                key=lambda s: getattr(s, "student_id", "") or "",
                reverse=True,
            )[:6]
        except Exception:
            recent = rows[:6]

        cols = ("id", "name", "subjects")
        tree = ttk.Treeview(panel, columns=cols, show="headings", height=6)
        tree.heading("id", text="ID")
        tree.heading("name", text="Name")
        tree.heading("subjects", text="Subjects")
        tree.column("id", width=80, anchor="w")
        tree.column("name", width=180, anchor="w")
        tree.column("subjects", width=240, anchor="w")
        for s in recent:
            subs = ", ".join(getattr(s, "subjects", []) or [])
            tree.insert("", "end", values=(
                getattr(s, "student_id", ""),
                getattr(s, "full_name", ""),
                subs,
            ))
        tree.pack(fill="both", expand=True)
        ttk.Button(panel, text="Open Student Directory →",
                   command=self.open_student_directory).pack(
            anchor="e", pady=(6, 0))

    def _build_recent_behaviour_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.LabelFrame(parent, text="Recent behaviour entries", padding=8)
        panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        try:
            from education_system.sixthform_system.modules.domain.pastoral.behaviour import (
                behaviour as bdata,
            )
            rows = bdata.list_entries() or []
        except Exception:
            rows = []

        if not rows:
            ttk.Label(panel, text="No behaviour entries logged.",
                      foreground="#777").pack(anchor="w")
            ttk.Button(panel, text="Log behaviour",
                       command=self.open_behaviour).pack(anchor="w", pady=(6, 0))
            return

        recent = rows[:6]
        cols = ("date", "type", "student", "category")
        tree = ttk.Treeview(panel, columns=cols, show="headings", height=6)
        tree.heading("date", text="Date")
        tree.heading("type", text="Type")
        tree.heading("student", text="Student")
        tree.heading("category", text="Category")
        tree.column("date", width=85, anchor="w")
        tree.column("type", width=70, anchor="w")
        tree.column("student", width=90, anchor="w")
        tree.column("category", width=160, anchor="w")
        for e in recent:
            tree.insert("", "end", values=(
                getattr(e, "entry_date", ""),
                getattr(e, "entry_type", ""),
                getattr(e, "student_id", ""),
                getattr(e, "category", ""),
            ))
        tree.pack(fill="both", expand=True)
        ttk.Button(panel, text="Open Behaviour Log →",
                   command=self.open_behaviour).pack(
            anchor="e", pady=(6, 0))

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

    # ── Header actions ───────────────────────────────────────────────
    def _logout(self) -> None:
        from education_system import switch as _switch
        self._stop_idle_watcher()
        try:
            self.auth.logout()
        except Exception:
            pass
        _switch.request_logout("gui")
        self.root.destroy()

    def _idle_logout(self) -> None:
        """Auto-logout path fired by ``IdleTimeoutWatcher``.

        Same teardown as the manual Logout button, plus a polite
        notice so the user understands why they're back at the
        login screen.
        """
        user = (self.auth.current_user or {}).get("username", "?")
        logger.info("Idle logout for user=%s", user)
        from education_system import switch as _switch
        self._stop_idle_watcher()
        try:
            messagebox.showinfo(
                "Signed out",
                "You've been signed out due to inactivity. "
                "Please sign in again to continue.",
                parent=self.root,
            )
        except tk.TclError:
            pass
        try:
            self.auth.logout()
        except Exception:
            pass
        _switch.request_logout("gui")
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _stop_idle_watcher(self) -> None:
        watcher = getattr(self, "_idle_watcher", None)
        if watcher is not None:
            try:
                watcher.stop()
            except Exception:
                logger.debug("Idle watcher stop raised", exc_info=True)

    def _switch_to_cli(self) -> None:
        if not messagebox.askyesno(
                "Switch to CLI",
                "Close the GUI and continue in the CLI?",
                parent=self.root):
            return
        from education_system import switch as _switch
        self._stop_idle_watcher()
        _switch.request_switch("college", "cli")
        self.root.destroy()

    def _switch_system(self) -> None:
        from education_system import switch as _switch
        from education_system.launcher.system_switch import pick_system_gui
        target = pick_system_gui(self.root, self.auth.current_user, "college")
        if not target:
            return
        self._stop_idle_watcher()
        _switch.request_switch(target, "gui")
        self.root.destroy()

    def _shutdown(self) -> None:
        if messagebox.askyesno(
                "Shutdown", "Shut down the Sixth Form System?", parent=self.root):
            self._stop_idle_watcher()
            try:
                self.auth.logout()
            except Exception:
                pass
            self.root.destroy()
            sys.exit(0)

    def _on_close(self) -> None:
        self._stop_idle_watcher()
        try:
            self.auth.logout()
        except Exception:
            pass
        self.root.destroy()

    # ── Student CRUD (delegates to student_views) ────────────────────
    def open_student_directory(self) -> None:
        from education_system.sixthform_system.modules.domain.students.students import student_views
        student_views.open_directory(self)

    def open_add_student(self) -> None:
        from education_system.sixthform_system.modules.domain.students.students import student_views
        student_views.open_add_student(self)

    def open_search_students(self) -> None:
        from education_system.sixthform_system.modules.domain.students.students import student_views
        student_views.open_search(self)

    def open_student_profile(self) -> None:
        from education_system.sixthform_system.modules.domain.students.students import student_views
        student_views.open_profile(self)

    def open_enrolment(self) -> None:
        from education_system.sixthform_system.modules.domain.students.enrolments import enrolment_views
        enrolment_views.open_directory(self)

    def open_courses(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.courses import course_views
        course_views.open_directory(self)

    def open_subjects(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.subjects import subject_views
        subject_views.open_directory(self)

    def open_class_groups(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.class_groups import class_group_views
        class_group_views.open_directory(self)

    def open_timetable(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.timetable import timetable_views
        timetable_views.open_directory(self)

    def open_attendance(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.attendance import attendance_views
        attendance_views.open_directory(self)

    def open_homework(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.homework import homework_views
        homework_views.open_directory(self)

    def open_gradebook(self) -> None:
        from education_system.sixthform_system.modules.domain.assessment.gradebook import gradebook_views
        gradebook_views.open_directory(self)

    def open_predicted_grades(self) -> None:
        from education_system.sixthform_system.modules.domain.assessment.predicted_grades import predicted_grades_views
        predicted_grades_views.open_directory(self)

    def open_mock_exams(self) -> None:
        from education_system.sixthform_system.modules.domain.assessment.mock_exams import mock_exam_views
        mock_exam_views.open_directory(self)

    def open_exam_entries(self) -> None:
        from education_system.sixthform_system.modules.domain.assessment.exam_entries import exam_entry_views
        exam_entry_views.open_directory(self)

    def open_results_day(self) -> None:
        from education_system.sixthform_system.modules.domain.assessment.exam_results import exam_result_views
        exam_result_views.open_directory(self)

    def open_ucas(self) -> None:
        from education_system.sixthform_system.modules.domain.progression.ucas import ucas_views
        ucas_views.open_directory(self)

    def open_personal_statements(self) -> None:
        from education_system.sixthform_system.modules.domain.progression.personal_statements import personal_statement_views
        personal_statement_views.open_directory(self)

    def open_references(self) -> None:
        from education_system.sixthform_system.modules.domain.progression.references import reference_views
        reference_views.open_directory(self)

    def open_offers(self) -> None:
        from education_system.sixthform_system.modules.domain.progression.offers import offer_views
        offer_views.open_directory(self)

    def open_apprenticeships(self) -> None:
        from education_system.sixthform_system.modules.domain.progression.apprenticeships import apprenticeship_views
        apprenticeship_views.open_directory(self)

    def open_university_visits(self) -> None:
        from education_system.sixthform_system.modules.domain.progression.university_visits import university_visits_views
        university_visits_views.open_directory(self)

    def open_careers(self) -> None:
        from education_system.sixthform_system.modules.domain.progression.careers import careers_views
        careers_views.open_directory(self)

    def open_destinations(self) -> None:
        from education_system.sixthform_system.modules.domain.progression.destinations import destinations_views
        destinations_views.open_directory(self)

    def open_epq(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.epq import epq_views
        epq_views.open_directory(self)

    def open_work_experience(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.work_experience import work_experience_views
        work_experience_views.open_directory(self)

    def open_room_booking(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.room_booking import room_booking_views
        room_booking_views.open_directory(self)

    def open_medical_records(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.medical_records import medical_records_views
        medical_records_views.open_directory(self)

    def open_tutor_groups(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.tutor_groups import tutor_group_views
        tutor_group_views.open_directory(self)

    def open_behaviour(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.behaviour import behaviour_views
        behaviour_views.open_directory(self)

    def open_safeguarding(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.safeguarding import safeguarding_views
        safeguarding_views.open_directory(self)

    def open_wellbeing(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.wellbeing import wellbeing_views
        wellbeing_views.open_wellbeing_window(self)

    def open_student_wellbeing(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.student_wellbeing import student_wellbeing_views
        student_wellbeing_views.open_student_wellbeing_window(self)

    def open_prevent_duty(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.prevent_duty import prevent_duty_views
        prevent_duty_views.open_prevent_duty_window(self)

    def open_attendance_concerns(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.attendance_concerns import attendance_concerns_views
        attendance_concerns_views.open_attendance_concerns_window(self)

    def open_staff(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.staff import staff_views
        staff_views.open_directory(self)

    def open_parents(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.parent_contacts import parent_contacts_views
        parent_contacts_views.open_directory(self)

    def open_parents_evenings(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.parents_evenings import parents_evenings_views
        parents_evenings_views.open_parents_evenings_window(self)

    def open_notices(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.notices import notices_views
        notices_views.open_notices_window(self)

    def open_messaging(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.messages import messages_views
        messages_views.open_messages_window(self)

    def open_finance_hub(self) -> None:
        from education_system.sixthform_system.modules.domain.finance.finance_hub import finance_hub_views
        finance_hub_views.open_finance_hub(self)

    def open_fees(self) -> None:
        from education_system.sixthform_system.modules.domain.finance.fees import fees_views
        fees_views.open_fees_window(self)

    def open_bursaries(self) -> None:
        from education_system.sixthform_system.modules.domain.finance.bursaries import bursaries_views
        bursaries_views.open_bursaries_window(self)

    def open_trips_payments(self) -> None:
        from education_system.sixthform_system.modules.domain.finance.trips import trips_views
        trips_views.open_trips_window(self)

    def open_receipts(self) -> None:
        from education_system.sixthform_system.modules.domain.finance.receipts import receipts_views
        receipts_views.open_receipts_window(self)

    def open_report_attendance(self) -> None:
        from education_system.sixthform_system.modules.domain.reports.attendance_report import attendance_report_views
        attendance_report_views.open_attendance_report_window(self)

    def open_report_grades(self) -> None:
        from education_system.sixthform_system.modules.domain.reports.grades_report import grades_report_views
        grades_report_views.open_grades_report_window(self)

    def open_progress(self) -> None:
        from education_system.sixthform_system.modules.domain.reports.progress import progress_views
        progress_views.open_progress_window(self)

    def open_kpi_dashboard(self) -> None:
        from education_system.sixthform_system.modules.domain.reports.kpi_dashboard import kpi_dashboard_views
        kpi_dashboard_views.open_kpi_dashboard_window(self)

    def open_data_dashboard(self) -> None:
        from education_system.sixthform_system.modules.domain.reports.data_dashboard import data_dashboard_views
        data_dashboard_views.open_data_dashboard_window(self)

    def open_progress_dashboard(self) -> None:
        from education_system.sixthform_system.modules.domain.reports.progress_dashboard import progress_dashboard_views
        progress_dashboard_views.open_progress_dashboard_window(self)

    def open_mobile_dashboard(self) -> None:
        from education_system.sixthform_system.modules.domain.reports.mobile_dashboard import mobile_dashboard_views
        mobile_dashboard_views.open_mobile_dashboard_window(self)

    def open_export(self) -> None:
        from education_system.sixthform_system.modules.domain.reports.custom_export import custom_export_views
        custom_export_views.open_custom_export_window(self)

    def open_audit_reports(self) -> None:
        from education_system.sixthform_system.modules.domain.reports.audit_reports import audit_reports_views
        audit_reports_views.open_audit_reports_window(self)

    def open_data_export(self) -> None:
        from education_system.sixthform_system.modules.domain.reports.data_export import data_export_views
        data_export_views.open_data_export_window(self)

    def open_gdpr(self) -> None:
        from education_system.sixthform_system.modules.domain.governance.gdpr import gdpr_views
        gdpr_views.open_gdpr_window(self)

    def open_risk_management(self) -> None:
        from education_system.sixthform_system.modules.domain.governance.risk_management import risk_management_views
        risk_management_views.open_risk_management_window(self)

    def open_change_password(self) -> None:
        from education_system.sixthform_system.modules.shared.gui import change_password_views
        change_password_views.open_change_password_dialog(
            self, auth=self.auth)

    def open_mfa(self) -> None:
        from education_system.sixthform_system.modules.shared.gui import mfa_views
        mfa_views.open_mfa_dialog(self, auth=self.auth)

    def open_user_accounts(self) -> None:
        from education_system.sixthform_system.modules.shared.gui import user_accounts_views
        user_accounts_views.open_user_accounts_window(
            self, auth=self.auth)

    def open_settings(self) -> None:
        from education_system.sixthform_system.modules.shared.gui import settings_views
        settings_views.open_settings_window(self, auth=self.auth)

    def open_user_management(self) -> None:
        from education_system.sixthform_system.modules.domain.governance.user_management import user_management_views
        user_management_views.open_user_management_window(self)

    def open_compliance(self) -> None:
        from education_system.sixthform_system.modules.domain.governance.compliance import compliance_views
        compliance_views.open_compliance_window(self)

    def open_governance(self) -> None:
        from education_system.sixthform_system.modules.domain.governance.governance import governance_views
        governance_views.open_governance_window(self)

    def open_policies(self) -> None:
        from education_system.sixthform_system.modules.domain.governance.policies import policies_views
        policies_views.open_policies_window(self)

    def open_absence_requests(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.absence_requests import absence_requests_views
        absence_requests_views.open_absence_requests_window(self)

    def open_academic_year(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.academic_year import academic_year_views
        academic_year_views.open_academic_year_window(self)

    def open_accessibility(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.accessibility import accessibility_views
        accessibility_views.open_accessibility_window(self)

    def open_activity_feed(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.activity_feed import activity_feed_views
        activity_feed_views.open_activity_feed_window(self)

    def open_advanced_search(self) -> None:
        from education_system.sixthform_system.modules.domain.students.advanced_search import advanced_search_views
        advanced_search_views.open_advanced_search_window(self)

    def open_admissions(self) -> None:
        from education_system.sixthform_system.modules.domain.students.admissions import admissions_views
        admissions_views.open_admissions_window(self)

    def open_onboarding(self) -> None:
        from education_system.sixthform_system.modules.domain.students.onboarding import onboarding_views
        onboarding_views.open_onboarding_window(self)

    def open_bulk_operations(self) -> None:
        from education_system.sixthform_system.modules.domain.students.bulk_operations import bulk_operations_views
        bulk_operations_views.open_bulk_operations_window(self)

    def open_alumni(self) -> None:
        from education_system.sixthform_system.modules.domain.students.alumni import alumni_views
        alumni_views.open_alumni_window(self)

    def open_calendar(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.calendar import calendar_views
        calendar_views.open_calendar_window(self)

    def open_lesson_plans(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.lesson_plans import lesson_plans_views
        lesson_plans_views.open_lesson_plans_window(self)

    def open_cover(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.cover import cover_views
        cover_views.open_cover_window(self)

    def open_cover_agency(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.cover_agency import cover_agency_views
        cover_agency_views.open_cover_agency_window(self)

    def open_assignments(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.assignments import assignments_views
        assignments_views.open_assignments_window(self)

    def open_enrichment(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.enrichment import enrichment_views
        enrichment_views.open_enrichment_window(self)

    def open_library(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.library import library_views
        library_views.open_library_window(self)

    def open_study_planner(self) -> None:
        from education_system.sixthform_system.modules.domain.academics.study_planner import study_planner_views
        study_planner_views.open_study_planner_window(self)

    def open_baseline_assessment(self) -> None:
        from education_system.sixthform_system.modules.domain.assessment.baseline_assessment import baseline_assessment_views
        baseline_assessment_views.open_baseline_assessment_window(self)

    def open_target_setting(self) -> None:
        from education_system.sixthform_system.modules.domain.assessment.target_setting import target_setting_views
        target_setting_views.open_target_setting_window(self)

    def open_ilp(self) -> None:
        from education_system.sixthform_system.modules.domain.assessment.ilp import ilp_views
        ilp_views.open_ilp_window(self)

    def open_intervention_tracking(self) -> None:
        from education_system.sixthform_system.modules.domain.assessment.intervention_tracking import intervention_tracking_views
        intervention_tracking_views.open_intervention_tracking_window(self)

    def open_value_added(self) -> None:
        from education_system.sixthform_system.modules.domain.assessment.value_added import value_added_views
        value_added_views.open_value_added_window(self)

    def open_early_warning(self) -> None:
        from education_system.sixthform_system.modules.domain.assessment.early_warning import early_warning_views
        early_warning_views.open_early_warning_window(self)

    def open_observations(self) -> None:
        from education_system.sixthform_system.modules.domain.assessment.observations import observations_views
        observations_views.open_observations_window(self)

    def open_self_assessment(self) -> None:
        from education_system.sixthform_system.modules.domain.assessment.self_assessment import self_assessment_views
        self_assessment_views.open_self_assessment_window(self)

    def open_quality_assurance(self) -> None:
        from education_system.sixthform_system.modules.domain.assessment.quality_assurance import quality_assurance_views
        quality_assurance_views.open_quality_assurance_window(self)

    def open_sef_builder(self) -> None:
        from education_system.sixthform_system.modules.domain.assessment.sef_builder import sef_builder_views
        sef_builder_views.open_sef_builder_window(self)

    def open_send(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.send import send_views
        send_views.open_send_window(self)

    def open_disciplinary(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.disciplinary import disciplinary_views
        disciplinary_views.open_disciplinary_window(self)

    def open_student_support(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.student_support import student_support_views
        student_support_views.open_student_support_window(self)

    def open_peer_mentoring(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.peer_mentoring import peer_mentoring_views
        peer_mentoring_views.open_peer_mentoring_window(self)

    def open_first_aid(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.first_aid import first_aid_views
        first_aid_views.open_first_aid_window(self)

    def open_emergency(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.emergency import emergency_views
        emergency_views.open_emergency_window(self)

    def open_health_safety(self) -> None:
        from education_system.sixthform_system.modules.domain.governance.health_safety import health_safety_views
        health_safety_views.open_health_safety_window(self)

    def open_assets(self) -> None:
        from education_system.sixthform_system.modules.domain.governance.assets import assets_views
        assets_views.open_assets_window(self)

    def open_equality_diversity(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.equality_diversity import equality_diversity_views
        equality_diversity_views.open_equality_diversity_window(self)

    def open_complaints(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.complaints import complaints_views
        complaints_views.open_complaints_window(self)

    def open_feedback(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.feedback import feedback_views
        feedback_views.open_feedback_window(self)

    def open_surveys(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.surveys import surveys_views
        surveys_views.open_surveys_window(self)

    def open_student_council(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.student_council import student_council_views
        student_council_views.open_student_council_window(self)

    def open_transport(self) -> None:
        from education_system.sixthform_system.modules.domain.pastoral.transport import transport_views
        transport_views.open_transport_window(self)

    def open_staff_hr(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.staff_hr import staff_hr_views
        staff_hr_views.open_staff_hr_window(self)

    def open_departments(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.departments import departments_views
        departments_views.open_departments_window(self)

    def open_staff_absence(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.staff_absence import staff_absence_views
        staff_absence_views.open_staff_absence_window(self)

    def open_staff_wellbeing(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.staff_wellbeing import staff_wellbeing_views
        staff_wellbeing_views.open_staff_wellbeing_window(self)

    def open_recruitment(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.recruitment import recruitment_views
        recruitment_views.open_recruitment_window(self)

    def open_appraisals(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.appraisals import appraisals_views
        appraisals_views.open_appraisals_window(self)

    def open_cpd(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.cpd import cpd_views
        cpd_views.open_cpd_window(self)

    def open_dbs_checks(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.dbs_checks import dbs_checks_views
        dbs_checks_views.open_dbs_checks_window(self)

    def open_visitors(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.visitors import visitors_views
        visitors_views.open_visitors_window(self)

    def open_announcements(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.announcements import announcements_views
        announcements_views.open_announcements_window(self)

    def open_notifications(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.notifications import notifications_views
        notifications_views.open_notifications_window(self)

    def open_letter_templates(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.letter_templates import letter_templates_views
        letter_templates_views.open_letter_templates_window(self)

    def open_document_hub(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.document_hub import document_hub_views
        document_hub_views.open_document_hub_window(self)

    def open_attachments(self) -> None:
        from education_system.sixthform_system.modules.domain.staff_comms.attachments import attachments_views
        attachments_views.open_attachments_window(self)

    def open_census_ilr(self) -> None:
        from education_system.sixthform_system.modules.domain.finance.census_ilr import census_ilr_views
        census_ilr_views.open_census_ilr_window(self)

    def open_expense_claims(self) -> None:
        from education_system.sixthform_system.modules.domain.finance.expense_claims import expense_claims_views
        expense_claims_views.open_expense_claims_window(self)

    def open_funding(self) -> None:
        from education_system.sixthform_system.modules.domain.finance.funding import funding_views
        funding_views.open_funding_window(self)

    def open_about(self) -> None:
        from education_system.sixthform_system.modules.shared.gui import about_views
        about_views.open_about_window(self, auth=self.auth)

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
        from education_system.shared.cross_system.journey_gui import StudentJourneyFrame
        self._open_cross_frame(StudentJourneyFrame, "Student Journey")

    def open_cross_analytics(self) -> None:
        from education_system.shared.analytics.analytics_gui import AnalyticsDashboardFrame
        self._open_cross_frame(AnalyticsDashboardFrame, "Analytics Dashboard")

    def open_cross_calendar(self) -> None:
        from education_system.shared.calendar.calendar_gui import CrossSystemCalendarFrame
        self._open_cross_frame(CrossSystemCalendarFrame, "Cross-System Calendar")

    def open_central_admin(self) -> None:
        from education_system.shared.admin_portal.admin_gui import CentralAdminFrame
        self._open_cross_frame(CentralAdminFrame, "Central Admin Portal")

    def open_cross_gdpr(self) -> None:
        from education_system.shared.gdpr.gdpr_gui import GDPRComplianceFrame
        self._open_cross_frame(GDPRComplianceFrame, "GDPR Compliance")

    def open_shared_documents(self) -> None:
        from education_system.shared.documents.document_gui import SharedDocumentsFrame
        self._open_cross_frame(SharedDocumentsFrame, "Shared Documents")

    def open_self_service(self) -> None:
        from education_system.shared.student_portal.portal_gui import StudentSelfServiceFrame
        self._open_cross_frame(StudentSelfServiceFrame, "Student Self-Service")

    def open_certificates(self) -> None:
        from education_system.shared.certificates.certificates_gui import CertificatesGUI
        self._open_cross_frame(CertificatesGUI, "Certificates")

    def open_university_visits_crm(self) -> None:
        from education_system.sixthform_system.modules.domain.progression.university_visits import (
            university_visits_views,
        )
        try:
            university_visits_views.open_directory(self)
        except Exception as e:
            logger.exception("University Visits view failed")
            self._show_stub(f"University Visits → CRM (error: {e})")

    def open_multi_language(self) -> None:
        from education_system.shared.i18n.selector_gui import show_language_selector
        show_language_selector(self)

    def open_todo(self) -> None:
        from education_system.sixthform_system.modules.domain.governance.todo import todo_views
        todo_views.open_todo_window(self)


def run(user_info=None, role=None, shared_auth=None) -> int:
    """Launch the GUI for an already-authenticated session.

    The unified launcher (`run.py`) calls this after the universal login
    succeeds, passing the shared `UserAuth` instance whose `current_user`
    is already populated. No per-system login is shown.
    """
    if shared_auth is None or not getattr(shared_auth, "current_user", None):
        logger.error("sixthform GUI invoked without a shared_auth session")
        raise RuntimeError(
            "sixthform_system GUI must be launched via run.py — "
            "no standalone login is available."
        )
    cu = shared_auth.current_user or {}
    logger.info("Sixth-form GUI starting for user=%s role=%s",
                cu.get("username"), role)
    app = SixthFormMainGUI(shared_auth)
    app.root.mainloop()
    logger.info("Sixth-form GUI exited for user=%s", cu.get("username"))
    return 0


if __name__ == "__main__":
    print("Launch via: python run.py --gui  (then choose Sixth Form)")
    raise SystemExit(2)
