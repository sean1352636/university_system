"""Tk GUI main menu for the Secondary School System.

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

from education_system.secondarysch_system import SYSTEM_NAME

logger = logging.getLogger(__name__)

VERSION = "0.1.0"


NAV_CATEGORIES: list[tuple[str, list[tuple[str, str]]]] = [
    ("Pupil Management", [
        ("Pupil Directory", "open_pupil_directory"),
        ("Add Pupil", "open_add_pupil"),
        ("Search Pupils", "open_search_pupils"),
        ("Pupil Profile", "open_pupil_profile"),
        ("Admissions", "open_admissions"),
        ("Year Group Management", "open_year_groups"),
    ]),
    ("Academic Management", [
        ("Subjects", "open_subjects"),
        ("Classes / Sets", "open_classes"),
        ("Timetable", "open_timetable"),
        ("KS3 Curriculum", "open_ks3"),
        ("KS4 / GCSE Options", "open_ks4_options"),
        ("Homework", "open_homework"),
        ("Cover & Substitution", "open_cover"),
    ]),
    ("Attendance & Registers", [
        ("Daily Register", "open_daily_register"),
        ("Lesson Attendance", "open_lesson_attendance"),
        ("Lateness Log", "open_lateness"),
        ("Absence Reasons", "open_absence_reasons"),
        ("Attendance Report", "open_attendance_report"),
    ]),
    ("Assessment & GCSEs", [
        ("Gradebook", "open_gradebook"),
        ("Assessment Cycles", "open_assessment_cycles"),
        ("Predicted Grades", "open_predicted_grades"),
        ("Mock Exams", "open_mocks"),
        ("GCSE Entries", "open_gcse_entries"),
        ("Results & Certificates", "open_results"),
    ]),
    ("Pastoral & Behaviour", [
        ("Tutor / Form Groups", "open_tutor_groups"),
        ("Behaviour Points", "open_behaviour_points"),
        ("Detentions", "open_detentions"),
        ("Exclusions", "open_exclusions"),
        ("Rewards & Merits", "open_rewards"),
        ("House System", "open_house_system"),
    ]),
    ("Safeguarding & Welfare", [
        ("Safeguarding Log", "open_safeguarding"),
        ("CPOMS-style Incidents", "open_incidents"),
        ("Looked-After Children", "open_lac"),
        ("Pupil Premium", "open_pupil_premium"),
        ("Free School Meals", "open_fsm"),
        ("Medical & First Aid", "open_medical"),
    ]),
    ("SEND & Inclusion", [
        ("SEND Register", "open_send_register"),
        ("EHCPs", "open_ehcps"),
        ("Provision Map", "open_provision_map"),
        ("Intervention Tracking", "open_interventions"),
        ("EAL Support", "open_eal"),
    ]),
    ("Staff & Communication", [
        ("Staff Directory", "open_staff"),
        ("Cover Allocations", "open_cover_alloc"),
        ("Parent Contacts", "open_parents"),
        ("Parents' Evenings", "open_parents_evenings"),
        ("Letters & Bulletins", "open_letters"),
        ("Email / Messaging", "open_messaging"),
    ]),
    ("Finance & Trips", [
        ("Trips & Visits", "open_trips"),
        ("Trip Payments", "open_trip_payments"),
        ("Dinner Money", "open_dinner_money"),
        ("Uniform & Shop", "open_uniform"),
    ]),
    ("Reports & Analytics", [
        ("Attendance Report", "open_report_attendance"),
        ("Behaviour Report", "open_report_behaviour"),
        ("Progress Tracking", "open_progress"),
        ("Census / DfE Returns", "open_census"),
        ("Custom Export", "open_export"),
    ]),
    ("System", [
        ("Change Password", "open_change_password"),
        ("User Accounts", "open_user_accounts"),
        ("Settings", "open_settings"),
        ("About", "open_about"),
    ]),
]


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
        ttk.Button(left, text="Logout", command=self._logout).pack(side="left", padx=(0, 6))
        ttk.Button(left, text="Switch to CLI", command=self._switch_to_cli).pack(
            side="left", padx=(0, 6))

        title = ttk.Frame(header)
        title.grid(row=0, column=1)
        ttk.Label(title, text=SYSTEM_NAME, font=("", 14, "bold")).pack()

        right = ttk.Frame(header)
        right.grid(row=0, column=2, sticky="e")
        ttk.Button(right, text="⏻ Shutdown", command=self._shutdown).pack(side="right")

    def _build_nav(self, parent: ttk.Frame) -> None:
        nav = ttk.LabelFrame(parent, text="Navigation", padding=5)
        nav.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        nav.rowconfigure(0, weight=1)
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
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        def _on_mw(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_mw))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        for group_label, items in NAV_CATEGORIES:
            self._make_category(inner, group_label, items, canvas)

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
        ttk.Label(right, text="Secondary School", foreground="#555").pack(side="left")
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
        ttk.Label(
            self.content_frame,
            text=f"Welcome to {SYSTEM_NAME}",
            font=("", 18, "bold"),
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            self.content_frame,
            text="Select a category on the left to get started.",
            foreground="#555",
        ).pack(anchor="w")
        ttk.Label(
            self.content_frame,
            text=f"Signed in as: {self.current_user_var.get()}",
            foreground="#555",
        ).pack(anchor="w", pady=(20, 0))
        ttk.Label(
            self.content_frame,
            text=f"Session started: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            foreground="#555",
        ).pack(anchor="w")

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

    def _shutdown(self) -> None:
        if messagebox.askyesno(
                "Shutdown", "Shut down the Secondary School System?", parent=self.root):
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

    def open_about(self) -> None:
        self._clear_content()
        assert self.content_frame is not None
        ttk.Label(self.content_frame, text="About", font=("", 16, "bold")).pack(
            anchor="w", pady=(0, 8))
        ttk.Label(
            self.content_frame,
            text=f"{SYSTEM_NAME} v{VERSION}\nPart of the Education System suite.",
        ).pack(anchor="w")


def run(user_info=None, role=None, shared_auth=None) -> int:
    """Launch the GUI for an already-authenticated session."""
    if shared_auth is None or not getattr(shared_auth, "current_user", None):
        raise RuntimeError(
            "secondarysch_system GUI must be launched via run.py — "
            "no standalone login is available."
        )
    app = SecondarySchoolMainGUI(shared_auth)
    app.root.mainloop()
    return 0


if __name__ == "__main__":
    print("Launch via: python run.py --gui  (then choose Secondary School)")
    raise SystemExit(2)
