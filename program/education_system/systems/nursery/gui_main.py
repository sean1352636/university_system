"""Tk GUI main menu for the Nursery System.

Layout mirrors `primarysch_system` and the other school systems:

    row 0 — header (dashboard · logout · switch-to-CLI · switch-system · shutdown)
    row 1 — left navigation (accordion of categories + search) + content area
    row 2 — status bar (status · current user · system / version)

The menu structure lives in `nursery/menu.py` and is shared with
`cli_main.py`. Every sidebar action is a placeholder stub — Early Years
domain modules will be wired in later.
"""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Callable

from education_system.systems.nursery import SYSTEM_NAME, SYSTEM_SLUG
from education_system.systems.nursery.menu import NAV_CATEGORIES

logger = logging.getLogger(__name__)

VERSION = "0.1.0"
FOOTER_LABEL = "Nursery"


class NurseryMainGUI:
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

        canvas = tk.Canvas(nav, highlightthickness=0, width=300)
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

        all_actions: list[str] = [
            label for _grp, items in NAV_CATEGORIES for label in items
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
                for label in all_actions:
                    if label in seen:
                        continue
                    if q in label.lower():
                        seen.add(label)
                        ttk.Button(
                            results_holder, text=label,
                            command=lambda lbl=label: self._show_stub(lbl),
                        ).pack(fill="x", pady=1)
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
        items: list[str],
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
                    for item_label in items:
                        ttk.Button(
                            sub, text=item_label,
                            command=lambda lbl=item_label: self._show_stub(lbl),
                        ).pack(fill="x", pady=1, padx=4)
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

        # Live snapshot — defensive so the dashboard still renders if a query
        # fails on a partially-seeded database.
        try:
            from education_system.systems.nursery.domain import dashboard
            stats = dashboard.get_stats()
        except Exception:
            logger.exception("Could not load dashboard stats")
            stats = None

        if stats is None:
            ttk.Label(
                root, text="Dashboard data is unavailable — see logs.",
                foreground="#a00",
            ).grid(row=1, column=0, sticky="w")
            self.status_var.set("Dashboard unavailable")
            return

        att = f"{stats.attendance_pct}%" if stats.attendance_pct is not None else "—"
        reg_hint = (
            f"{stats.present}/{stats.register_total} on {stats.register_date}"
            if stats.register_date else "No register yet"
        )
        kpis = [
            ("Children", str(stats.children_on_roll), "On roll"),
            ("Staff", str(stats.staff_total),
             f"{stats.dsl_count} DSL · {stats.first_aider_count} first-aiders"),
            ("Attendance", att, reg_hint),
            ("Waiting list", str(stats.admissions_waiting),
             f"{stats.admissions_offered} offer(s) out"),
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

        # Two-column panel area: rooms occupancy (left) + compliance/today
        # (right).
        panels = ttk.Frame(root)
        panels.grid(row=2, column=0, sticky="nsew", pady=(0, 14))
        panels.columnconfigure(0, weight=1, uniform="panel")
        panels.columnconfigure(1, weight=1, uniform="panel")

        self._build_rooms_panel(panels, stats).grid(
            row=0, column=0, sticky="nsew", padx=(0, 6))

        right = ttk.Frame(panels)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right.columnconfigure(0, weight=1)
        self._build_kv_panel(
            right, "Today & this week", [
                ("Present (latest register)",
                 f"{stats.present} of {stats.register_total}"),
                ("Absent", str(stats.absent)),
                ("Accidents logged (7 days)", str(stats.accidents_recent)),
                ("Medications given (7 days)", str(stats.medications_recent)),
            ],
        ).grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self._build_kv_panel(
            right, "Safeguarding & compliance", [
                ("Designated Safeguarding Leads", str(stats.dsl_count)),
                ("Paediatric first-aiders", str(stats.first_aider_count)),
                ("Staff DBS-checked",
                 f"{stats.dbs_checked} of {stats.staff_total}"),
                ("Open concerns", str(stats.open_concerns)),
                ("Email drafts waiting", str(stats.email_drafts)),
            ],
        ).grid(row=1, column=0, sticky="ew")

        actions = ttk.LabelFrame(root, text="Quick actions", padding=8)
        actions.grid(row=3, column=0, sticky="ew")
        quick = [
            ("Add Child", lambda: self._show_stub("Add Child")),
            ("Search Children", lambda: self._show_stub("Search Children")),
            ("Daily Register", lambda: self._show_stub("Daily Register")),
            ("Observations", lambda: self._show_stub("Observations")),
            ("Accident Log", lambda: self._show_stub("Accident & Incident Log")),
            ("Email / Messaging", lambda: self._show_stub("Email / Messaging")),
        ]
        for i, (lbl, cmd) in enumerate(quick):
            ttk.Button(actions, text=lbl, command=cmd, style="Large.TButton").grid(
                row=0, column=i, padx=4, pady=2, sticky="ew")
            actions.columnconfigure(i, weight=1, uniform="qa")

        self.status_var.set(
            f"Ready · {stats.children_on_roll} children on roll · "
            f"{stats.staff_total} staff")

    def _build_rooms_panel(self, parent: ttk.Frame, stats) -> ttk.LabelFrame:
        """A room-by-room occupancy panel with a capacity bar per room."""
        panel = ttk.LabelFrame(
            parent, text=f"Rooms ({stats.rooms_open} open)", padding=10)
        panel.columnconfigure(1, weight=1)
        if not stats.rooms:
            ttk.Label(panel, text="No rooms configured yet.",
                      foreground="#888").grid(row=0, column=0, columnspan=3,
                                              sticky="w")
            return panel
        for r, room in enumerate(stats.rooms):
            ttk.Label(panel, text=room.name).grid(
                row=r, column=0, sticky="w", padx=(0, 8), pady=3)
            if room.capacity:
                bar = ttk.Progressbar(panel, maximum=room.capacity, length=120)
                bar["value"] = min(room.children, room.capacity)
                bar.grid(row=r, column=1, sticky="ew", padx=6, pady=3)
            colour = "#a45" if room.full else "#555"
            ttk.Label(panel, text=room.label + ("  FULL" if room.full else ""),
                      foreground=colour).grid(row=r, column=2, sticky="e", pady=3)
        return panel

    def _build_kv_panel(self, parent: ttk.Frame, title: str,
                        rows: list[tuple[str, str]]) -> ttk.LabelFrame:
        """A simple label/value panel used for the compliance & today cards."""
        panel = ttk.LabelFrame(parent, text=title, padding=10)
        panel.columnconfigure(0, weight=1)
        for r, (label, value) in enumerate(rows):
            ttk.Label(panel, text=label, foreground="#555").grid(
                row=r, column=0, sticky="w", pady=2)
            ttk.Label(panel, text=value, font=("", 10, "bold")).grid(
                row=r, column=1, sticky="e", pady=2)
        return panel

    def _show_stub(self, label: str) -> None:
        # Route implemented features to their views; fall back to a placeholder.
        if self._dispatch_feature(label):
            return
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

    def _open_student_journey(self) -> None:
        """Embed the read-only cross-system Student Journey panel."""
        self._clear_content()
        from education_system.platform.cross_system.journey_gui import (
            StudentJourneyFrame,
        )
        frame = StudentJourneyFrame(self.content_frame, auth=self.auth)
        frame.pack(fill="both", expand=True)
        self.status_var.set("Opened: Student Journey")

    def _dispatch_feature(self, label: str) -> bool:
        """Open the view for an implemented feature. Returns True if handled."""
        if label == "Student Journey":
            self._open_student_journey()
            return True
        try:
            from education_system.systems.nursery.domain.learners.children import (
                children_views,
            )
            child_views = {
                "Child Directory": children_views.open_directory,
                "Add Child":       children_views.open_add_child,
                "Search Children": children_views.open_search,
                "Child Profile":   children_views.open_profile,
                "Move to Primary School": children_views.open_move_to_primary,
            }
            view = child_views.get(label)
            if view is not None:
                logger.debug("Nursery GUI dispatch: %s", label)
                view(self)
                return True
            if self._dispatch_local_view(label):
                return True
            if self._dispatch_system_view(label):
                return True
            if self._dispatch_ported_view(label):
                return True
        except Exception:
            logger.exception("Nursery GUI handler failed for %s", label)
            try:
                messagebox.showerror(
                    label,
                    f"Could not open {label} — see logs for details.",
                    parent=self.root,
                )
            except Exception:
                logger.debug("Could not show dispatch-error dialog", exc_info=True)
            return True
        return False

    # Nursery menu label -> (views module, function) for the Children &
    # Admissions domain modules implemented for this system. Each manager view
    # renders into this GUI host's (``self``) content pane.
    _LOCAL_VIEWS: dict[str, tuple[str, str]] = {
        "Admissions & Waiting List": ("admissions.admissions_views", "open_manager"),
        "Registration & Enrolment":  ("enrolment.enrolment_views", "open_manager"),
        "Rooms & Age Groups":        ("rooms.rooms_views", "open_manager"),
        "Key Person Assignment":     ("key_persons.key_persons_views", "open_manager"),
        "Funded Hours (15/30 & 2-Year-Old)": (
            "funded_hours.funded_hours_views", "open_manager"),
        "Sessions & Bookings":       ("sessions.sessions_views", "open_manager"),
        "Settling-In":               ("settling_in.settling_in_views", "open_manager"),
        "Transition to School":      ("transitions.transitions_views", "open_manager"),
        "Leavers":                   ("leavers.leavers_views", "open_manager"),
        "Staff : Child Ratios":      ("ratios.ratios_views", "open_manager"),
        "Live Ratio Alerts":         ("ratio_alerts.ratio_alerts_views", "open_manager"),
        "Staff Rota":                ("rota.rota_views", "open_manager"),
        "Qualifications & Training":  ("qualifications.qualifications_views", "open_manager"),
        "Paediatric First Aid":      ("first_aid.first_aid_views", "open_manager"),
        "Invoices & Fees":           ("invoices.invoices_views", "open_manager"),
        "Funded Hours Claims":       ("funding_claims.funding_claims_views", "open_manager"),
        "Payments":                  ("payments.payments_views", "open_manager"),
        "Tax-Free Childcare / Vouchers": (
            "childcare_vouchers.childcare_vouchers_views", "open_manager"),
        "Sibling Discounts":         ("discounts.discounts_views", "open_manager"),
        "Occupancy & Income":        ("occupancy.occupancy_views", "open_manager"),
        "Parent Contacts":           ("parent_contacts.parent_contacts_views", "open_manager"),
        "Emergency Contacts":        ("emergency_contacts.emergency_contacts_views", "open_manager"),
        "Permissions & Consents":    ("consents.consents_views", "open_manager"),
        "Email / Messaging":         ("email_centre.email_centre_views", "open_manager"),
        "Parent Messaging":          ("messaging.messaging_views", "open_manager"),
        "Daily Updates":             ("daily_updates.daily_updates_views", "open_manager"),
        "Newsletters":               ("newsletters.newsletters_views", "open_manager"),
        "Parent Meetings":           ("parent_meetings.parent_meetings_views", "open_manager"),
        "Safeguarding / Child Protection": ("safeguarding.safeguarding_views", "open_manager"),
        "Designated Safeguarding Lead": ("dsl.dsl_views", "open_manager"),
        "Welfare Requirements":      ("welfare.welfare_views", "open_manager"),
        "SEND & Additional Needs":   ("send.send_views", "open_manager"),
        "EHC Plans":                 ("ehc_plans.ehc_plans_views", "open_manager"),
        "Looked-After Children":     ("looked_after.looked_after_views", "open_manager"),
        "Risk Assessments":          ("risk_assessments.risk_assessments_views", "open_manager"),
        "Prevent Duty":              ("prevent_duty.prevent_duty_views", "open_manager"),
        "Concerns & Referrals":      ("concerns.concerns_views", "open_manager"),
        "Wellbeing":                 ("wellbeing.wellbeing_views", "open_manager"),
        "EYFS Profile":              ("eyfs_profile.eyfs_profile_views", "open_manager"),
        "Development Tracking (Prime & Specific Areas)": (
            "development_tracking.development_tracking_views", "open_manager"),
        "Observations":              ("observations.observations_views", "open_manager"),
        "Learning Journeys":         ("learning_journeys.learning_journeys_views", "open_manager"),
        "Next Steps Planning":       ("next_steps.next_steps_views", "open_manager"),
        "2-Year-Old Progress Check": ("progress_check_2yr.progress_check_2yr_views", "open_manager"),
        "Characteristics of Effective Learning": (
            "effective_learning.effective_learning_views", "open_manager"),
        "Activity & Curriculum Planning": (
            "curriculum_planning.curriculum_planning_views", "open_manager"),
        "Cohort Tracking":           ("cohort_tracking.cohort_tracking_views", "open_manager"),
        "Photos & Evidence":         ("evidence.evidence_views", "open_manager"),
        # Daily Care & Routines
        "Daily Register":            ("daily_register.daily_register_views", "open_manager"),
        "Sign In / Sign Out":        ("sign_in_out.sign_in_out_views", "open_manager"),
        "Collections & Late Pickup": ("collections.collections_views", "open_manager"),
        "Daily Diary":               ("daily_diary.daily_diary_views", "open_manager"),
        "Sleep Log":                 ("sleep_log.sleep_log_views", "open_manager"),
        "Nappy / Toileting Log":     ("toileting_log.toileting_log_views", "open_manager"),
        "Meals & Menus":             ("meals.meals_views", "open_manager"),
        "Bottle Feeds":              ("bottle_feeds.bottle_feeds_views", "open_manager"),
        "Allergies & Dietary Requirements": ("allergies.allergies_views", "open_manager"),
        "Accident & Incident Log":   ("accident_log.accident_log_views", "open_manager"),
        "Existing Injuries Log":     ("existing_injuries.existing_injuries_views", "open_manager"),
        "Medication Log":            ("medication_log.medication_log_views", "open_manager"),
    }

    def _dispatch_local_view(self, label: str) -> bool:
        """Open a local domain module's manager view; return True if handled."""
        entry = self._LOCAL_VIEWS.get(label)
        if entry is None:
            return False
        module_path, func_name = entry
        import importlib
        mod = importlib.import_module(
            f"education_system.systems.nursery.domain.{module_path}")
        logger.debug("Nursery GUI dispatch (local): %s -> %s", label, module_path)
        getattr(mod, func_name)(self)
        return True

    def _dispatch_system_view(self, label: str) -> bool:
        """Open a System-category view for ``label``; return True if handled.

        The four account/settings/about features open their own Toplevel from
        the root window (``parent``, ``auth``); MFA and User Management render
        into this GUI host (``self``), matching their primary-school originals.
        """
        try:
            if label == "Change Password":
                from education_system.systems.nursery.interfaces.gui import (
                    change_password_views,
                )
                change_password_views.open_change_password_dialog(
                    self.root, auth=self.auth)
            elif label == "User Accounts":
                from education_system.systems.nursery.interfaces.gui import (
                    user_accounts_views,
                )
                user_accounts_views.open_user_accounts_window(
                    self.root, auth=self.auth)
            elif label == "Settings":
                from education_system.systems.nursery.interfaces.gui import (
                    settings_views,
                )
                settings_views.open_settings_window(self.root, auth=self.auth)
            elif label == "About":
                from education_system.systems.nursery.interfaces.gui import (
                    about_views,
                )
                about_views.open_about_window(self.root, auth=self.auth)
            elif label == "Multi-Factor Authentication":
                from education_system.systems.nursery.domain.governance.mfa import (
                    mfa_views,
                )
                mfa_views.open_mfa(self)
            elif label == "User Management":
                from education_system.systems.nursery.domain.governance.user_management import (
                    user_management_views,
                )
                user_management_views.open_user_management_window(self)
            else:
                return False
        except Exception:
            logger.exception("Nursery GUI System handler failed for %s", label)
            try:
                messagebox.showerror(
                    label, f"Could not open {label} — see logs for details.",
                    parent=self.root)
            except Exception:
                logger.debug("Could not show system-dispatch error dialog",
                             exc_info=True)
        return True

    # Nursery menu label -> (views module, function) for the cross-cutting
    # modules ported from the Primary School System. Each view renders into /
    # opens a window from this GUI host (``self``).
    _PORTED_VIEWS: dict[str, tuple[str, str]] = {
        "Policies & Procedures":     ("policies.policies_views", "open_policies_window"),
        "GDPR":                      ("gdpr.gdpr_views", "open_gdpr_window"),
        "Recruitment":               ("recruitment.recruitment_views", "open_recruitment_window"),
        "Complaints":                ("complaints.complaints_views", "open_complaints_window"),
        "Feedback & Surveys":        ("feedback.feedback_views", "open_feedback_window"),
        "Expense Claims":            ("expense_claims.expense_claims_views", "open_expense_claims_window"),
        "Audit Reports":             ("audit_reports.audit_reports_views", "open_audit_reports_window"),
        "Staff Absence":             ("staff_absence.staff_absence_views", "open_staff_absence_window"),
        "Staff Directory":           ("staff.staff_views", "open_directory"),
        "Visitors":                  ("visitors.visitors_views", "open_visitors_window"),
        "DBS Checks":                ("dbs_checks.dbs_checks_views", "open_dbs_checks_window"),
        "Supervisions & Appraisals": ("appraisals.appraisals_views", "open_appraisals_window"),
        # Compliance & Reports
        "Ofsted Readiness":          ("ofsted.ofsted_views", "open_ofsted_window"),
        "EYFS Compliance":           ("eyfs_compliance.eyfs_compliance_views", "open_eyfs_compliance_window"),
        "Attendance Report":         ("attendance_report.attendance_report_views", "open_attendance_report_window"),
        "Occupancy Report":          ("occupancy_report.occupancy_report_views", "open_occupancy_report_window"),
        "Funding Report":            ("funding_report.funding_report_views", "open_funding_report_window"),
        "Accident / Incident Report": ("accident_report.accident_report_views", "open_accident_report_window"),
        "Data Export":               ("data_export.data_export_views", "open_data_export_window"),
    }

    def _dispatch_ported_view(self, label: str) -> bool:
        """Open a ported module's view for ``label``; return True if handled."""
        entry = self._PORTED_VIEWS.get(label)
        if entry is None:
            return False
        module_path, func_name = entry
        import importlib
        mod = importlib.import_module(
            f"education_system.systems.nursery.domain.{module_path}")
        logger.debug("Nursery GUI dispatch (ported): %s -> %s", label, module_path)
        getattr(mod, func_name)(self)
        return True

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
        _switch.request_switch(SYSTEM_SLUG, "cli")
        self.root.destroy()

    def _switch_system(self) -> None:
        from education_system import switch as _switch
        from education_system.launcher.system_switch import pick_system_gui
        target = pick_system_gui(self.root, self.auth.current_user, SYSTEM_SLUG)
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


def run(user_info=None, role=None, shared_auth=None) -> int:
    if shared_auth is None or not getattr(shared_auth, "current_user", None):
        logger.error("nursery GUI invoked without a shared_auth session")
        raise RuntimeError(
            "nursery_system GUI must be launched via run.py — "
            "no standalone login is available."
        )
    cu = shared_auth.current_user or {}
    logger.info("Nursery GUI starting for user=%s role=%s",
                cu.get("username"), role)
    from education_system.systems.nursery.infrastructure.database import init_db
    init_db()
    app = NurseryMainGUI(shared_auth)
    app.root.mainloop()
    logger.info("Nursery GUI exited for user=%s", cu.get("username"))
    return 0


if __name__ == "__main__":
    print("Launch via: python run.py --gui  (then choose Nursery)")
    raise SystemExit(2)
