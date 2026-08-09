"""Tk GUI shell for the FE College System.

Layout matches the other systems in this repository:

    row 0 — header (dashboard · logout · switch-to-CLI · switch-system · shutdown)
    row 1 — left navigation + content area
    row 2 — status bar (status · current user · system / version)

What differs is the navigation: rather than one menu for everyone, the sidebar
is built from the signed-in user's *view* (admin, staff or learner), which the
controller derives from the launcher role. A learner never sees an admin screen
because it is never rendered, not because a click is refused.
"""

from __future__ import annotations

import importlib
import logging
import sys
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from education_system.systems.fe_college import SYSTEM_NAME, SYSTEM_SLUG
from education_system.systems.fe_college.config import (
    COLLEGE_NAME,
    VERSION,
    WINDOW_GEOMETRY,
    WINDOW_MINSIZE,
)
from education_system.systems.fe_college.interfaces.gui.controllers.college_controller import (
    CollegeController,
)

logger = logging.getLogger(__name__)

FOOTER_LABEL = "FE College"

# view -> [(section, [(screen key, label)])]. The screen key resolves to a
# module under interfaces/gui/windows/<view>/ exposing ``open_window(host)``.
NAVIGATION: dict[str, list[tuple[str, list[tuple[str, str]]]]] = {
    "admin": [
        ("Overview", [
            ("dashboard", "Dashboard"),
            ("reports", "Reports"),
        ]),
        ("People", [
            ("students", "Learners"),
            ("staff", "Staff"),
            ("users", "Users & access"),
        ]),
        ("Curriculum", [
            ("courses", "Courses & units"),
            ("timetables", "Timetable & rooms"),
        ]),
        ("Money", [
            ("finance", "Fees, bursaries & funding"),
        ]),
        ("Communication", [
            ("email", "Email centre"),
        ]),
    ],
    "staff": [
        ("Overview", [
            ("dashboard", "My teaching"),
            ("timetable", "My timetable"),
        ]),
        ("Teaching", [
            ("registers", "Take a register"),
            ("lesson_plans", "Lesson plans"),
        ]),
        ("Assessment", [
            ("assignments", "Assignments"),
            ("marking", "Marking"),
        ]),
        ("Learners", [
            ("student_records", "Learner records"),
        ]),
        ("Communication", [
            ("email", "Email centre"),
        ]),
    ],
    "student": [
        ("Overview", [
            ("dashboard", "My dashboard"),
            ("timetable", "My timetable"),
        ]),
        ("My learning", [
            ("courses", "My courses"),
            ("assignments", "My assignments"),
            ("results", "My results"),
        ]),
        ("Me", [
            ("attendance", "My attendance"),
            ("profile", "My details"),
            ("support", "Support"),
        ]),
    ],
}


class CollegeGUI:
    """The window every FE College screen renders inside."""

    def __init__(self, auth, session_user: dict | None = None, role: str = "student"):
        self.auth = auth
        self.ctl = CollegeController(session_user or getattr(auth, "current_user", {}), role)

        self.root = tk.Tk()
        self.root.title(f"{SYSTEM_NAME} — {COLLEGE_NAME}")
        self.root.geometry(WINDOW_GEOMETRY)
        self.root.minsize(*WINDOW_MINSIZE)

        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            logger.debug("clam theme unavailable; using the platform default")
        self.style.configure("Category.TButton", padding=8, font=("", 10, "bold"))
        self.style.configure("Nav.TButton", padding=6, anchor="w")

        self.status_var = tk.StringVar(value="Ready")
        self.user_var = tk.StringVar(value=self.ctl.identity.label)
        self.content_frame: ttk.Frame | None = None
        self._current_screen: str | None = None

        self._build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.open_screen("dashboard")

    # ── Layout ─────────────────────────────────────────────────────────────

    def _build_layout(self) -> None:
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
        ttk.Button(left, text="🏠 Dashboard",
                   command=lambda: self.open_screen("dashboard")).pack(
            side="left", padx=(0, 6))
        ttk.Button(left, text="Logout", command=self._logout).pack(side="left", padx=(0, 6))
        ttk.Button(left, text="Switch to CLI", command=self._switch_to_cli).pack(
            side="left", padx=(0, 6))

        try:
            from education_system.launcher.roles import is_superadmin
            if is_superadmin(self.ctl.session_user):
                ttk.Button(left, text="Switch System",
                           command=self._switch_system).pack(side="left", padx=(0, 6))
        except Exception:
            logger.exception("Could not evaluate superadmin status for the header")

        title = ttk.Frame(header)
        title.grid(row=0, column=1)
        ttk.Label(title, text=SYSTEM_NAME, font=("", 14, "bold")).pack()
        ttk.Label(title, text=self.ctl.subtitle(),
                  foreground="#666", font=("", 9)).pack()

        right = ttk.Frame(header)
        right.grid(row=0, column=2, sticky="e")
        ttk.Button(right, text="⏻ Shutdown", command=self._shutdown).pack(side="right")

    def _build_nav(self, parent: ttk.Frame) -> None:
        nav = ttk.LabelFrame(parent, text="Navigation", padding=5)
        nav.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        nav.rowconfigure(1, weight=1)
        nav.columnconfigure(0, weight=1)

        canvas = tk.Canvas(nav, highlightthickness=0, width=250)
        scroll = ttk.Scrollbar(nav, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=1, column=0, sticky="nsew")
        scroll.grid(row=1, column=1, sticky="ns")

        def _on_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_wheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        search_frame = ttk.Frame(nav)
        search_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        search_frame.columnconfigure(0, weight=1)
        self.search_var = tk.StringVar()
        entry = ttk.Entry(search_frame, textvariable=self.search_var)
        entry.grid(row=0, column=0, sticky="ew")
        _placeholder(entry, self.search_var, "🔍 Search screens…")
        try:
            self.root.bind(
                "<Control-k>",
                lambda _e: (entry.focus_set(), entry.select_range(0, tk.END)),
                add="+",
            )
        except tk.TclError:
            logger.debug("Could not bind Ctrl-K")

        sections = NAVIGATION.get(self.ctl.view, NAVIGATION["student"])
        self._nav_categories = ttk.Frame(inner)
        self._nav_categories.pack(fill="x")
        for label, items in sections:
            self._make_category(self._nav_categories, label, items, canvas)

        self._nav_results = ttk.Frame(inner)
        all_items = [(key, label) for _s, items in sections for key, label in items]

        def _on_search(*_a) -> None:
            for child in self._nav_results.winfo_children():
                child.destroy()
            query = self.search_var.get().strip().lower()
            if not query or query.startswith("🔍"):
                self._nav_results.pack_forget()
                self._nav_categories.pack(fill="x")
            else:
                self._nav_categories.pack_forget()
                self._nav_results.pack(fill="x", padx=5)
                matches = [
                    (key, label) for key, label in all_items if query in label.lower()
                ]
                for key, label in matches:
                    ttk.Button(self._nav_results, text=label, style="Nav.TButton",
                               command=lambda k=key: self.open_screen(k)).pack(
                        fill="x", pady=1)
                if not matches:
                    ttk.Label(self._nav_results, text="No matches",
                              foreground="#888").pack(anchor="w", pady=4)
            try:
                inner.update_idletasks()
                canvas.configure(scrollregion=canvas.bbox("all"))
            except tk.TclError:
                logger.debug("Could not resize the nav scroll region")

        self.search_var.trace_add("write", _on_search)
        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _make_category(self, parent, label: str,
                       items: list[tuple[str, str]], canvas) -> None:
        """One expandable navigation group. The first opens by default."""
        container = ttk.Frame(parent)
        container.pack(fill="x", pady=2, padx=5)
        state = {"expanded": False, "sub": None}
        button = ttk.Button(container, text=f"{label}  ▶", style="Category.TButton")
        button.pack(fill="x")

        def toggle() -> None:
            if state["expanded"]:
                if state["sub"] is not None:
                    state["sub"].pack_forget()
                button.configure(text=f"{label}  ▶")
                state["expanded"] = False
            else:
                if state["sub"] is None:
                    sub = ttk.Frame(container)
                    for key, item_label in items:
                        ttk.Button(sub, text=item_label, style="Nav.TButton",
                                   command=lambda k=key: self.open_screen(k)).pack(
                            fill="x", pady=1, padx=4)
                    state["sub"] = sub
                state["sub"].pack(fill="x", pady=(2, 4))
                button.configure(text=f"{label}  ▼")
                state["expanded"] = True
            try:
                parent.update_idletasks()
                canvas.configure(scrollregion=canvas.bbox("all"))
            except tk.TclError:
                logger.debug("Could not resize the nav scroll region")

        button.configure(command=toggle)
        if not getattr(self, "_first_category_open", False):
            toggle()
            self._first_category_open = True

    def _build_content(self, parent: ttk.Frame) -> None:
        outer = ttk.Frame(parent)
        outer.grid(row=1, column=1, sticky="nsew")
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        self.content_frame = ttk.Frame(outer, padding=10)
        self.content_frame.grid(row=0, column=0, sticky="nsew")

    def _build_status_bar(self, parent: ttk.Frame) -> None:
        ttk.Separator(parent, orient="horizontal").grid(
            row=2, column=0, columnspan=2, sticky="new")
        bar = ttk.Frame(parent)
        bar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        for i in range(3):
            bar.columnconfigure(i, weight=1)

        left = ttk.Frame(bar, padding=(2, 4))
        left.grid(row=0, column=0, sticky="w")
        ttk.Label(left, text="Status: ", foreground="#555").pack(side="left")
        ttk.Label(left, textvariable=self.status_var).pack(side="left")

        centre = ttk.Frame(bar, padding=(2, 4))
        centre.grid(row=0, column=1)
        ttk.Label(centre, text="User: ", foreground="#555").pack(side="left")
        ttk.Label(centre, textvariable=self.user_var).pack(side="left")

        right = ttk.Frame(bar, padding=(2, 4))
        right.grid(row=0, column=2, sticky="e")
        ttk.Label(right, text=FOOTER_LABEL, foreground="#555").pack(side="left")
        ttk.Label(right, text=" · ", foreground="#aaa").pack(side="left")
        ttk.Label(right, text=f"v{VERSION}", foreground="#555").pack(side="left")

    # ── Host API used by every window ──────────────────────────────────────

    def clear_content(self) -> None:
        if self.content_frame is None:
            return
        for child in self.content_frame.winfo_children():
            child.destroy()

    def set_status(self, message: str) -> None:
        self.status_var.set(message)

    def refresh_identity(self) -> None:
        """Re-read the identity label after a record is linked."""
        self.user_var.set(self.ctl.identity.label)

    def open_screen(self, key: str, **kwargs) -> None:
        """Render the named screen for the signed-in view.

        A screen that fails to load must not take the shell with it — the error
        is shown in the content pane so the user can navigate somewhere else.
        """
        module_path = (
            "education_system.systems.fe_college.interfaces.gui.windows."
            f"{self.ctl.view}.{key}"
        )
        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError:
            logger.warning("No FE College screen %s for the %s view", key, self.ctl.view)
            self._show_error(
                f"'{key}' is not available",
                f"There is no {key} screen for the {self.ctl.view} view.",
            )
            return

        try:
            self._current_screen = key
            module.open_window(self, **kwargs)
        except Exception as exc:
            logger.exception("FE College screen %s failed to open", key)
            self._show_error(
                f"Could not open {getattr(module, 'TITLE', key)}",
                f"{exc}\n\nThe details are in the application log.",
            )

    def _show_error(self, title: str, detail: str) -> None:
        self.clear_content()
        ttk.Label(self.content_frame, text=title,
                  font=("", 14, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(self.content_frame, text=detail, foreground="#b3261e",
                  wraplength=800, justify="left").pack(anchor="w")
        ttk.Button(self.content_frame, text="Back to the dashboard",
                   command=lambda: self.open_screen("dashboard")).pack(
            anchor="w", pady=(12, 0))
        self.set_status(title)

    # ── Session controls ───────────────────────────────────────────────────

    def _logout(self) -> None:
        from education_system import switch as _switch
        try:
            self.auth.logout()
        except Exception:
            logger.debug("Logout raised; continuing to the login screen", exc_info=True)
        _switch.request_logout("gui")
        self.root.destroy()

    def _switch_to_cli(self) -> None:
        if not messagebox.askyesno("Switch to CLI",
                                   "Close the GUI and continue in the CLI?",
                                   parent=self.root):
            return
        from education_system import switch as _switch
        _switch.request_switch(SYSTEM_SLUG, "cli")
        self.root.destroy()

    def _switch_system(self) -> None:
        from education_system import switch as _switch
        from education_system.launcher.system_switch import pick_system_gui
        target = pick_system_gui(self.root, self.ctl.session_user, SYSTEM_SLUG)
        if not target:
            return
        _switch.request_switch(target, "gui")
        self.root.destroy()

    def _shutdown(self) -> None:
        if not messagebox.askyesno("Shutdown", f"Shut down the {SYSTEM_NAME}?",
                                   parent=self.root):
            return
        try:
            self.auth.logout()
        except Exception:
            logger.debug("Logout raised during shutdown", exc_info=True)
        self.root.destroy()
        sys.exit(0)

    def _on_close(self) -> None:
        try:
            self.auth.logout()
        except Exception:
            logger.debug("Logout raised while closing", exc_info=True)
        self.root.destroy()


def _placeholder(entry: ttk.Entry, var: tk.StringVar, text: str) -> None:
    """Grey placeholder text that clears on focus."""
    def show() -> None:
        entry.delete(0, tk.END)
        entry.insert(0, text)
        try:
            entry.configure(foreground="gray")
        except tk.TclError:
            pass

    def on_focus_in(_e) -> None:
        if var.get() == text:
            entry.delete(0, tk.END)
            try:
                entry.configure(foreground="black")
            except tk.TclError:
                pass

    def on_focus_out(_e) -> None:
        if not var.get().strip():
            show()

    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)
    show()


def run(user_info=None, role=None, shared_auth=None) -> int:
    """Launcher entry point for the FE College GUI."""
    if shared_auth is None or not getattr(shared_auth, "current_user", None):
        logger.error("FE College GUI invoked without a shared_auth session")
        raise RuntimeError(
            "The FE College GUI must be launched via run.py — "
            "no standalone login is available."
        )
    current = shared_auth.current_user or {}
    logger.info("FE College GUI starting for user=%s role=%s",
                current.get("username"), role)

    from education_system.systems.fe_college.infrastructure.persistence import schema
    schema.bootstrap()

    resolved_role = role
    if not resolved_role:
        for entry in (user_info or current).get("systems", []):
            if entry.get("system_key") == SYSTEM_SLUG:
                resolved_role = entry.get("role")
                break
    app = CollegeGUI(shared_auth, user_info or current, resolved_role or "student")
    app.root.mainloop()
    logger.info("FE College GUI exited for user=%s", current.get("username"))
    return 0


if __name__ == "__main__":
    print("Launch via: python run.py --fecollege --gui")
    raise SystemExit(2)
