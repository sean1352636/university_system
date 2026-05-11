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
        ("Student Profile", "open_student_profile"),
        ("Enrolment", "open_enrolment"),
    ]),
    ("Academic Management", [
        ("Courses", "open_courses"),
        ("Subjects & A-Levels", "open_subjects"),
        ("Class Groups", "open_class_groups"),
        ("Timetable", "open_timetable"),
        ("Attendance", "open_attendance"),
        ("Homework & Coursework", "open_homework"),
    ]),
    ("Assessment & Grades", [
        ("Gradebook", "open_gradebook"),
        ("Predicted Grades", "open_predicted_grades"),
        ("Mock Exams", "open_mock_exams"),
        ("Exam Entries", "open_exam_entries"),
        ("Results Day", "open_results_day"),
    ]),
    ("UCAS & Careers", [
        ("UCAS Applications", "open_ucas"),
        ("Personal Statements", "open_personal_statements"),
        ("References", "open_references"),
        ("University Offers", "open_offers"),
        ("Apprenticeships", "open_apprenticeships"),
        ("Careers Guidance", "open_careers"),
    ]),
    ("Pastoral & Wellbeing", [
        ("Tutor Groups", "open_tutor_groups"),
        ("Behaviour Log", "open_behaviour"),
        ("Safeguarding", "open_safeguarding"),
        ("Wellbeing", "open_wellbeing"),
        ("Attendance Concerns", "open_attendance_concerns"),
    ]),
    ("Staff & Communication", [
        ("Staff Directory", "open_staff"),
        ("Parent Contacts", "open_parents"),
        ("Parents' Evenings", "open_parents_evenings"),
        ("Notices & Bulletins", "open_notices"),
        ("Email / Messaging", "open_messaging"),
    ]),
    ("Finance & Bursaries", [
        ("Fees", "open_fees"),
        ("Bursary Applications", "open_bursaries"),
        ("Trips & Payments", "open_trips_payments"),
        ("Receipts", "open_receipts"),
    ]),
    ("Reports & Analytics", [
        ("Attendance Report", "open_report_attendance"),
        ("Grades Report", "open_report_grades"),
        ("Progress Tracking", "open_progress"),
        ("Custom Export", "open_export"),
    ]),
    ("System", [
        ("Change Password", "open_change_password"),
        ("User Accounts", "open_user_accounts"),
        ("Settings", "open_settings"),
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
        ttk.Label(right, text="Sixth Form", foreground="#555").pack(side="left")
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

    # ── Header actions ───────────────────────────────────────────────
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
        _switch.request_switch("college", "cli")
        self.root.destroy()

    def _switch_system(self) -> None:
        from education_system import switch as _switch
        from education_system.launcher.system_switch import pick_system_gui
        target = pick_system_gui(self.root, self.auth.current_user, "college")
        if not target:
            return
        _switch.request_switch(target, "gui")
        self.root.destroy()

    def _shutdown(self) -> None:
        if messagebox.askyesno(
                "Shutdown", "Shut down the Sixth Form System?", parent=self.root):
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

    # ── Student CRUD (delegates to student_views) ────────────────────
    def open_student_directory(self) -> None:
        from education_system.sixthform_system.modules.domain.students import student_views
        student_views.open_directory(self)

    def open_add_student(self) -> None:
        from education_system.sixthform_system.modules.domain.students import student_views
        student_views.open_add_student(self)

    def open_search_students(self) -> None:
        from education_system.sixthform_system.modules.domain.students import student_views
        student_views.open_search(self)

    def open_student_profile(self) -> None:
        from education_system.sixthform_system.modules.domain.students import student_views
        student_views.open_profile(self)

    def open_enrolment(self) -> None:
        from education_system.sixthform_system.modules.domain.enrolments import enrolment_views
        enrolment_views.open_directory(self)

    def open_courses(self) -> None:
        from education_system.sixthform_system.modules.domain.courses import course_views
        course_views.open_directory(self)

    def open_subjects(self) -> None:
        from education_system.sixthform_system.modules.domain.subjects import subject_views
        subject_views.open_directory(self)

    def open_class_groups(self) -> None:
        from education_system.sixthform_system.modules.domain.class_groups import class_group_views
        class_group_views.open_directory(self)

    def open_timetable(self) -> None:
        from education_system.sixthform_system.modules.domain.timetable import timetable_views
        timetable_views.open_directory(self)

    def open_attendance(self) -> None:
        from education_system.sixthform_system.modules.domain.attendance import attendance_views
        attendance_views.open_directory(self)

    def open_homework(self) -> None:
        from education_system.sixthform_system.modules.domain.homework import homework_views
        homework_views.open_directory(self)

    def open_gradebook(self) -> None:
        from education_system.sixthform_system.modules.domain.gradebook import gradebook_views
        gradebook_views.open_directory(self)

    def open_predicted_grades(self) -> None:
        from education_system.sixthform_system.modules.domain.predicted_grades import predicted_grades_views
        predicted_grades_views.open_directory(self)

    def open_mock_exams(self) -> None:
        from education_system.sixthform_system.modules.domain.mock_exams import mock_exam_views
        mock_exam_views.open_directory(self)

    def open_exam_entries(self) -> None:
        from education_system.sixthform_system.modules.domain.exam_entries import exam_entry_views
        exam_entry_views.open_directory(self)

    def open_results_day(self) -> None:
        from education_system.sixthform_system.modules.domain.exam_results import exam_result_views
        exam_result_views.open_directory(self)

    def open_ucas(self) -> None:
        from education_system.sixthform_system.modules.domain.ucas import ucas_views
        ucas_views.open_directory(self)

    def open_personal_statements(self) -> None:
        from education_system.sixthform_system.modules.domain.personal_statements import personal_statement_views
        personal_statement_views.open_directory(self)

    def open_references(self) -> None:
        from education_system.sixthform_system.modules.domain.references import reference_views
        reference_views.open_directory(self)

    def open_offers(self) -> None:
        from education_system.sixthform_system.modules.domain.offers import offer_views
        offer_views.open_directory(self)

    def open_apprenticeships(self) -> None:
        from education_system.sixthform_system.modules.domain.apprenticeships import apprenticeship_views
        apprenticeship_views.open_directory(self)

    def open_careers(self) -> None:
        from education_system.sixthform_system.modules.domain.careers import careers_views
        careers_views.open_directory(self)

    def open_tutor_groups(self) -> None:
        from education_system.sixthform_system.modules.domain.tutor_groups import tutor_group_views
        tutor_group_views.open_directory(self)

    def open_behaviour(self) -> None:
        from education_system.sixthform_system.modules.domain.behaviour import behaviour_views
        behaviour_views.open_directory(self)

    def open_safeguarding(self) -> None:
        from education_system.sixthform_system.modules.domain.safeguarding import safeguarding_views
        safeguarding_views.open_directory(self)

    def open_wellbeing(self) -> None:
        from education_system.sixthform_system.modules.domain.wellbeing import wellbeing_views
        wellbeing_views.open_wellbeing_window(self)

    def open_attendance_concerns(self) -> None:
        from education_system.sixthform_system.modules.domain.attendance_concerns import attendance_concerns_views
        attendance_concerns_views.open_attendance_concerns_window(self)

    def open_staff(self) -> None:
        from education_system.sixthform_system.modules.domain.staff import staff_views
        staff_views.open_directory(self)

    def open_parents(self) -> None:
        from education_system.sixthform_system.modules.domain.parent_contacts import parent_contacts_views
        parent_contacts_views.open_directory(self)

    def open_parents_evenings(self) -> None:
        from education_system.sixthform_system.modules.domain.parents_evenings import parents_evenings_views
        parents_evenings_views.open_parents_evenings_window(self)

    def open_notices(self) -> None:
        from education_system.sixthform_system.modules.domain.notices import notices_views
        notices_views.open_notices_window(self)

    def open_messaging(self) -> None:
        from education_system.sixthform_system.modules.domain.messages import messages_views
        messages_views.open_messages_window(self)

    def open_fees(self) -> None:
        from education_system.sixthform_system.modules.domain.fees import fees_views
        fees_views.open_fees_window(self)

    def open_bursaries(self) -> None:
        from education_system.sixthform_system.modules.domain.bursaries import bursaries_views
        bursaries_views.open_bursaries_window(self)

    def open_trips_payments(self) -> None:
        from education_system.sixthform_system.modules.domain.trips import trips_views
        trips_views.open_trips_window(self)

    def open_receipts(self) -> None:
        from education_system.sixthform_system.modules.domain.receipts import receipts_views
        receipts_views.open_receipts_window(self)

    def open_report_attendance(self) -> None:
        from education_system.sixthform_system.modules.domain.attendance_report import attendance_report_views
        attendance_report_views.open_attendance_report_window(self)

    def open_report_grades(self) -> None:
        from education_system.sixthform_system.modules.domain.grades_report import grades_report_views
        grades_report_views.open_grades_report_window(self)

    def open_progress(self) -> None:
        from education_system.sixthform_system.modules.domain.progress import progress_views
        progress_views.open_progress_window(self)

    def open_export(self) -> None:
        from education_system.sixthform_system.modules.domain.custom_export import custom_export_views
        custom_export_views.open_custom_export_window(self)

    def open_change_password(self) -> None:
        from education_system.sixthform_system.modules.shared.gui import change_password_views
        change_password_views.open_change_password_dialog(
            self, auth=self.auth)

    def open_user_accounts(self) -> None:
        from education_system.sixthform_system.modules.shared.gui import user_accounts_views
        user_accounts_views.open_user_accounts_window(
            self, auth=self.auth)

    def open_settings(self) -> None:
        from education_system.sixthform_system.modules.shared.gui import settings_views
        settings_views.open_settings_window(self, auth=self.auth)

    def open_about(self) -> None:
        from education_system.sixthform_system.modules.shared.gui import about_views
        about_views.open_about_window(self, auth=self.auth)


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
