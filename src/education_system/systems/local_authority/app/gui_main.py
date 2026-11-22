"""Tk GUI main window for the Local Authority Education System.

Same layout as the secondary, sixth form, SEND, adult education, alternative
provision, training provider and university main windows:

    row 0 - header (Dashboard · Applications · Due & Overdue · Logout · Switch to CLI
            [· Switch System for superadmins] | title | Shutdown)
    row 1 - left navigation (search + accordion of categories) | content area
    row 2 - status bar (status · current user · system / version)

The menu comes from :mod:`app.routing` (shared with the CLI). A menu key that
names a record type opens that type's list page (``ui.gui.kit``); the other
keys are pages in :data:`ui.gui.pages.CUSTOM` or ``open_<key>`` methods here.

Launched only by the unified launcher after the shared login
(``python -m education_system --localauthority --gui``); ``core.access``
turns that session into the principal every screen asks.
"""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from datetime import datetime
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui import window_sizing
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.local_authority import SYSTEM_KEY, SYSTEM_NAME
from education_system.systems.local_authority.app import routing as menu
from education_system.systems.local_authority.core import access
from education_system.systems.local_authority.core import records as r

logger = logging.getLogger(__name__)

VERSION = "0.1.0"
FOOTER_LABEL = "Local Authority Education"

PageDraw = Callable[[ttk.Frame], None]


class LAMainGUI:
    def __init__(self, auth, principal: access.Principal | None = None) -> None:
        menu.load_areas()
        self.auth = auth
        self.principal = principal or access.from_auth(auth)
        self._states: dict[str, dict] = {}

        self.root = tk.Tk()
        self.root.title(SYSTEM_NAME)
        self.root.report_callback_exception = self._on_callback_error
        window_sizing.fit(self.root, "1400x900", (1200, 800))

        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.style.configure("Large.TButton", padding=6)
        self.style.configure("Category.TButton", padding=8, font=("", 10, "bold"))

        self.status_var = tk.StringVar(value="Ready")
        self.current_user_var = tk.StringVar(value=self.principal.username or "—")
        self.content_frame: ttk.Frame | None = None
        self._content_canvas: tk.Canvas | None = None
        self._current_page: tuple[str, PageDraw] | None = None
        self._popout_btn: ttk.Button | None = None

        self._setup_layout()
        self._show_welcome()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Sign out after EDU_IDLE_TIMEOUT_MINUTES of inactivity, the same
        # way the Logout button does.
        from education_system.platform.delivery.gui.idle_timeout import install_idle_logout
        self._cancel_idle = install_idle_logout(self.root, self._idle_logout)

    # ── helpers pages use ────────────────────────────────────────────
    def status(self, text: str) -> None:
        self.status_var.set(text)

    def state_for(self, key: str) -> dict:
        """A dict that survives redraws, so a page keeps its tab / filters."""
        return self._states.setdefault(key, {})

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
        ttk.Button(left, text="📄 Applications",
                   command=self._handler("applications", "Applications & Offers")).pack(
            side="left", padx=(0, 6))
        ttk.Button(left, text="📋 Due & Overdue",
                   command=self._handler("due_report", "Due & Overdue")).pack(
            side="left", padx=(0, 6))
        ttk.Button(left, text="Logout", command=self._logout).pack(side="left", padx=(0, 6))
        ttk.Button(left, text="Switch to CLI", command=self._switch_to_cli).pack(
            side="left", padx=(0, 6))
        try:
            from education_system.launcher.roles import is_superadmin
            if is_superadmin(getattr(self.auth, "current_user", None)):
                ttk.Button(left, text="Switch System",
                           command=self._switch_system).pack(side="left", padx=(0, 6))
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
        inner.bind("<Configure>",
                   lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=1, column=0, sticky="nsew")
        scroll.grid(row=1, column=1, sticky="ns")

        def _on_mw(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_linux_scroll(event):
            canvas.yview_scroll(-1 if event.num == 4 else 1, "units")

        def _bind_wheel(_e):
            canvas.bind_all("<MouseWheel>", _on_mw)
            canvas.bind_all("<Button-4>", _on_linux_scroll)
            canvas.bind_all("<Button-5>", _on_linux_scroll)

        def _unbind_wheel(_e):
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                canvas.unbind_all(seq)

        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)

        # ── Search box (filters across every sidebar entry) ──────────
        search_frame = ttk.Frame(nav)
        search_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        search_frame.columnconfigure(0, weight=1)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var)
        search_entry.grid(row=0, column=0, sticky="ew")
        placeholder = "🔍 Search features..."

        def _set_placeholder() -> None:
            search_entry.delete(0, tk.END)
            search_entry.insert(0, placeholder)
            search_entry.config(foreground="gray")

        def _on_focus_in(_e) -> None:
            if search_var.get() == placeholder:
                search_entry.delete(0, tk.END)
                search_entry.config(foreground="black")

        def _on_focus_out(_e) -> None:
            if not search_var.get().strip():
                _set_placeholder()

        search_entry.bind("<FocusIn>", _on_focus_in)
        search_entry.bind("<FocusOut>", _on_focus_out)
        _set_placeholder()
        self.root.bind(
            "<Control-k>",
            lambda _e: (search_entry.focus_set(), search_entry.select_range(0, tk.END)),
            add="+")

        categories_holder = ttk.Frame(inner)
        categories_holder.pack(fill="x")
        visible = [(grp, [(lbl, key) for lbl, key in items if self.principal.can_open(lbl)])
                   for grp, items in menu.CATEGORIES]
        visible = [(grp, items) for grp, items in visible if items]
        for group_label, items in visible:
            self._make_category(categories_holder, group_label, items, canvas)

        results_holder = ttk.Frame(inner)
        all_actions = [entry for _grp, items in visible for entry in items]

        def _on_search_change(*_a) -> None:
            for w in results_holder.winfo_children():
                w.destroy()
            q = search_var.get().strip().lower()
            if not q or q == placeholder.lower():
                results_holder.pack_forget()
                categories_holder.pack(fill="x")
            else:
                categories_holder.pack_forget()
                results_holder.pack(fill="x", padx=5)
                matches = [(lbl, key) for lbl, key in all_actions if q in lbl.lower()]
                for lbl, key in matches:
                    ttk.Button(results_holder, text=lbl,
                               command=self._handler(key, lbl)).pack(fill="x", pady=1)
                if not matches:
                    ttk.Label(results_holder, text="No matches",
                              foreground="#888").pack(anchor="w", pady=4)
            inner.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))

        search_var.trace_add("write", _on_search_change)
        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _make_category(self, parent: ttk.Frame, label: str,
                       items: list[tuple[str, str]], canvas: tk.Canvas) -> None:
        container = ttk.Frame(parent)
        container.pack(fill="x", pady=2, padx=5)
        state: dict = {"expanded": False, "sub": None}
        btn = ttk.Button(container, text=f"{label}  ▶", style="Category.TButton")
        btn.pack(fill="x")

        def toggle() -> None:
            if state["expanded"]:
                state["sub"].pack_forget()
                btn.configure(text=f"{label}  ▶")
                state["expanded"] = False
            else:
                if state["sub"] is None:
                    sub = ttk.Frame(container)
                    for item_label, key in items:
                        ttk.Button(sub, text=item_label,
                                   command=self._handler(key, item_label)).pack(
                            fill="x", pady=1, padx=4)
                    state["sub"] = sub
                state["sub"].pack(fill="x", pady=(2, 4))
                btn.configure(text=f"{label}  ▼")
                state["expanded"] = True
            parent.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))

        btn.configure(command=toggle)

    def _build_content(self, parent: ttk.Frame) -> None:
        outer = ttk.Frame(parent, padding=0)
        outer.grid(row=1, column=1, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=0)
        outer.rowconfigure(1, weight=1)

        page_bar = ttk.Frame(outer, padding=(10, 4, 10, 0))
        page_bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        self._popout_btn = ttk.Button(
            page_bar, text="⧉ Open in new window", state="disabled",
            command=self._open_current_page_in_window)
        self._popout_btn.pack(side="right")

        canvas = tk.Canvas(outer, highlightthickness=0)
        canvas.grid(row=1, column=0, sticky="nsew")
        vs = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        vs.grid(row=1, column=1, sticky="ns")
        canvas.configure(yscrollcommand=vs.set)

        self.content_frame = ttk.Frame(canvas, padding=10)
        win = canvas.create_window((0, 0), window=self.content_frame, anchor="nw")
        self.content_frame.bind(
            "<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        self._content_canvas = canvas

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
        ttk.Label(centre, textvariable=self.current_user_var).pack(side="left")

        right = ttk.Frame(bar, padding=(2, 4))
        right.grid(row=0, column=2, sticky="e")
        ttk.Label(right, text=FOOTER_LABEL, foreground="#555").pack(side="left")
        ttk.Label(right, text=" · ", foreground="#aaa").pack(side="left")
        ttk.Label(right, text=f"v{VERSION}", foreground="#555").pack(side="left")

    # ── Pages ────────────────────────────────────────────────────────
    def _clear_content(self) -> None:
        if self.content_frame is None:
            return
        for w in self.content_frame.winfo_children():
            w.destroy()
        if self._content_canvas is not None:
            self._content_canvas.yview_moveto(0)

    def _show_page(self, label: str, draw: PageDraw) -> None:
        self._clear_content()
        assert self.content_frame is not None
        draw(self.content_frame)
        self._set_current_page((label, draw))
        self.status_var.set(f"Opened: {label}")

    def _set_current_page(self, page: tuple[str, PageDraw] | None) -> None:
        self._current_page = page
        if self._popout_btn is not None:
            self._popout_btn.configure(state="normal" if page else "disabled")

    def _open_current_page_in_window(self) -> None:
        if not self._current_page:
            return
        label, draw = self._current_page
        win = tk.Toplevel(self.root)
        win.title(f"{label} — {SYSTEM_NAME}")
        window_sizing.fit(win, "1000x700", (700, 500))
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)
        draw(frame)

    def _handler(self, key: str, label: str) -> Callable[[], None]:
        """The command for a menu entry: an ``open_<key>`` method here, else a
        custom page, else the record type's list page, else "not built yet"."""
        def run() -> None:
            if not self.principal.can_open(label):
                messagebox.showwarning("Not available", self.principal.denied_message(label),
                                       parent=self.root)
                return
            self.open_page(key, label)
        return run

    def open_page(self, key: str, label: str | None = None) -> None:
        from education_system.systems.local_authority.ui.gui import kit, pages
        method = getattr(self, f"open_{key}", None)
        if callable(method):
            method()
        elif key in pages.CUSTOM:
            title, draw = pages.CUSTOM[key]
            self._show_page(title, lambda parent: draw(parent, self))
        elif key in r.REGISTRY:
            rt = r.REGISTRY[key]
            self._show_page(rt.title, lambda parent: kit.draw_records(
                parent, rt, principal=self.principal, state=self.state_for(key),
                on_status=self.status, open_learner=self.show_learner))
        else:
            text = label or key
            self._show_page(text, lambda parent: _draw_not_built(parent, text))

    def show_learner(self, learner_id: int) -> None:
        """One child's profile (also used by lists, reports and the dashboard)."""
        from education_system.systems.local_authority.ui.gui import pages
        self._show_page("Child Profile", lambda parent: pages.draw_learner(
            parent, self, learner_id))

    def open_add_learner(self) -> None:
        from education_system.systems.local_authority.modules import learners
        from education_system.systems.local_authority.ui.gui import kit
        kit.open_form(self.root, learners.LEARNERS, None, principal=self.principal,
                      on_saved=self.show_learner)

    def open_about(self) -> None:
        principal = self.principal

        def draw(parent: ttk.Frame) -> None:
            ttk.Label(parent, text=SYSTEM_NAME, font=("", 16, "bold")).pack(
                anchor="w", pady=(0, 8))
            from education_system.systems.local_authority.infrastructure import database
            rows = [
                ("Version", VERSION),
                ("Covers", "A council's education services: children and families, the "
                           "schools register, admissions and appeals, fair access, attendance "
                           "and penalty notices, children missing education, home education, "
                           "exclusions, SEND / EHC plans and home-to-school transport"),
                ("Areas", f"{len(r.REGISTRY)} record types in {len(menu.CATEGORIES)} menu groups"),
                ("Database", str(database.db_path())),
                ("Signed in as", f"{principal.username} ({principal.role or 'no role'})"),
            ]
            grid = ttk.Frame(parent)
            grid.pack(anchor="w")
            for i, (k, v) in enumerate(rows):
                ttk.Label(grid, text=f"{k}:", foreground="#555").grid(
                    row=i, column=0, sticky="w", padx=(0, 12), pady=2)
                ttk.Label(grid, text=v, wraplength=700, justify="left").grid(
                    row=i, column=1, sticky="w", pady=2)

        self._show_page("About", draw)

    # ── Dashboard ────────────────────────────────────────────────────
    def _show_welcome(self) -> None:
        from education_system.systems.local_authority.core import dates
        from education_system.systems.local_authority.modules import children, reports
        self._clear_content()
        self._set_current_page(None)
        assert self.content_frame is not None
        root = self.content_frame
        root.columnconfigure(0, weight=1)

        now = datetime.now()
        greet = ("Good morning" if now.hour < 12
                 else "Good afternoon" if now.hour < 18 else "Good evening")
        header = ttk.Frame(root)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=f"{greet}, {self.current_user_var.get()}",
                  font=("", 20, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text=now.strftime("%A, %d %B %Y · %H:%M"),
                  foreground="#666").grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Button(header, text="↻ Refresh", command=self._show_welcome).grid(
            row=0, column=1, rowspan=2, sticky="e", padx=(8, 0))

        try:
            d = reports.dashboard()
        except Exception:
            logger.exception("Dashboard figures failed")
            d = None
        if d is None:
            kpis = [(label, "—", "Couldn't read the records") for label in
                    ("Children", "Admissions", "Attendance & welfare", "SEND")]
        else:
            ehc = "—" if d["ehc_20_weeks"] is None else f"{d['ehc_20_weeks']}%"
            kpis = [
                ("Children", str(d["children"]),
                 f"{d['not_in_education']} of school age not in education · "
                 f"{d['cme_open']} missing education · {d['ehe']} home educated"),
                ("Admissions", f"{d['applications_open']} awaiting a decision",
                 f"{d['appeals_pending']} appeal(s) pending"),
                ("Attendance & welfare", f"{d['attendance_cases']} open case(s)",
                 f"{d['suspensions']} suspension(s) · {d['exclusions']} permanent "
                 "exclusion(s) this year"),
                ("SEND", f"{d['ehc_plans']} EHC plan(s)",
                 f"{d['ehc_open']} assessment(s) open · {ehc} issued within 20 weeks"),
            ]
        kpi_row = ttk.Frame(root)
        kpi_row.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        for i, (label, value, hint) in enumerate(kpis):
            kpi_row.columnconfigure(i, weight=1, uniform="kpi")
            tile = ttk.LabelFrame(kpi_row, padding=12)
            tile.grid(row=0, column=i, padx=4, sticky="nsew")
            ttk.Label(tile, text=label, foreground="#666").pack(anchor="w")
            ttk.Label(tile, text=value, font=("", 18, "bold"), wraplength=260,
                      justify="left").pack(anchor="w", pady=(2, 0))
            ttk.Label(tile, text=hint, foreground="#888", font=("", 9), wraplength=260,
                      justify="left").pack(anchor="w", pady=(2, 0))

        quick = [("Add Child", "add_learner"), ("Applications & Offers", "applications"),
                 ("Attendance Cases", "attendance_cases"),
                 ("Children Missing Education", "cme"),
                 ("EHC Needs Assessments", "ehc_requests"),
                 ("Transport Applications", "transport")]
        quick = [(lbl, key) for lbl, key in quick if self.principal.can_open(lbl)]
        actions = ttk.LabelFrame(root, text="Quick actions", padding=8)
        actions.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        for i, (lbl, key) in enumerate(quick):
            ttk.Button(actions, text=lbl, command=self._handler(key, lbl),
                       style="Large.TButton").grid(row=0, column=i, padx=4, pady=2, sticky="ew")
            actions.columnconfigure(i, weight=1, uniform="qa")

        lower = ttk.Frame(root)
        lower.grid(row=3, column=0, sticky="nsew")
        root.rowconfigure(3, weight=1)
        for i in range(2):
            lower.columnconfigure(i, weight=1, uniform="lower")

        box = ttk.LabelFrame(lower, text="Due soon", padding=10)
        box.grid(row=0, column=0, padx=4, sticky="nsew")
        due = d["due"][:10] if d else []
        for item in due:
            ttk.Button(box, text=f"{'⚠ ' if item.overdue else ''}{dates.uk(item.due)} · "
                                 f"{item.what}{' · ' + item.learner if item.learner else ''}",
                       command=(lambda lid=item.learner_id: self.show_learner(lid))
                       if item.learner_id else
                       (lambda area=item.area: self.open_page(area))).pack(fill="x", pady=1)
        if not due:
            ttk.Label(box, text="Nothing due in the next 30 days.", foreground="#888").pack(
                anchor="w")
        ttk.Button(box, text="All due & overdue…",
                   command=self._handler("due_report", "Due & Overdue")).pack(
            anchor="e", pady=(4, 0))

        box = ttk.LabelFrame(lower, text="Recent children", padding=10)
        box.grid(row=0, column=1, padx=4, sticky="nsew")
        try:
            recent = sorted(children.active_learners(), key=lambda x: x["updated_at"],
                            reverse=True)[:10]
        except Exception:
            logger.exception("Recent children panel failed")
            recent = []
        for row in recent:
            ttk.Button(box, text=f"{children.child_label(row)} · {row['education']}",
                       command=lambda lid=row["id"]: self.show_learner(lid)).pack(
                fill="x", pady=1)
        if not recent:
            ttk.Label(box, text="No children yet. Use Add Child to create the first record.",
                      foreground="#888", wraplength=300, justify="left").pack(anchor="w")
        self.status_var.set("Ready")

    # ── Header actions ───────────────────────────────────────────────
    def _stop_idle_watcher(self) -> None:
        cancel = getattr(self, "_cancel_idle", None)
        if cancel is not None:
            try:
                cancel()
            except Exception:
                logger.debug("Idle watcher cancel raised", exc_info=True)

    def _sign_out(self) -> None:
        self._stop_idle_watcher()
        try:
            self.auth.logout()
        except Exception:
            logger.exception("Logout failed")

    def _on_callback_error(self, exc_type, exc, tb) -> None:
        logger.error("Unhandled error in the Local Authority Education GUI", exc_info=(exc_type, exc, tb))
        try:
            messagebox.showerror(SYSTEM_NAME, f"Something went wrong:\n{exc}", parent=self.root)
        except tk.TclError:
            pass

    def _logout(self) -> None:
        from education_system import switch as _switch
        self._sign_out()
        _switch.request_logout("gui")
        self.root.destroy()

    def _idle_logout(self) -> None:
        """Same teardown as Logout, then say why (the notice is modal, so it
        comes last or it would keep the session open on screen)."""
        from education_system import switch as _switch
        from education_system.platform.delivery.gui import idle_timeout as _idle
        logger.info("Idle logout for user=%s", self.principal.username)
        self._sign_out()
        _switch.request_logout("gui")
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        _idle.notify_signed_out(
            self.root, "Signed out",
            "You've been signed out due to inactivity. Please sign in again to continue.")

    def _switch_to_cli(self) -> None:
        if not messagebox.askyesno("Switch to CLI", "Close the GUI and continue in the CLI?",
                                   parent=self.root):
            return
        from education_system import switch as _switch
        self._stop_idle_watcher()
        _switch.request_switch(SYSTEM_KEY, "cli")
        self.root.destroy()

    def _switch_system(self) -> None:
        from education_system import switch as _switch
        from education_system.launcher.system_switch import pick_system_gui
        target = pick_system_gui(self.root, self.auth.current_user, SYSTEM_KEY)
        if not target:
            return
        self._stop_idle_watcher()
        _switch.request_switch(target, "gui")
        self.root.destroy()

    def _shutdown(self) -> None:
        if not messagebox.askyesno("Shutdown", f"Shut down the {SYSTEM_NAME}?",
                                   parent=self.root):
            return
        self._sign_out()
        self.root.destroy()
        sys.exit(0)

    def _on_close(self) -> None:
        self._sign_out()
        self.root.destroy()


def _draw_not_built(parent: ttk.Frame, label: str) -> None:
    ttk.Label(parent, text=label, font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))
    ttk.Label(parent, text=f"{label} hasn't been built yet in the {SYSTEM_NAME}.",
              foreground="#555").pack(anchor="w")


def run(user_info=None, role=None, shared_auth=None) -> int:
    """Open the main window for a session the unified login already signed in."""
    access.require_shared_session(shared_auth, "gui")
    principal = access.from_auth(shared_auth, role)
    logger.info("Local Authority Education GUI starting for user=%s role=%s",
                principal.username, principal.role)
    if not principal.is_staff:
        logger.warning("Refusing Local Authority Education GUI for user=%s role=%s",
                       principal.username, principal.role)
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(SYSTEM_NAME, access.refusal(principal), parent=root)
        root.destroy()
        return 0
    app = LAMainGUI(shared_auth, principal)
    app.root.mainloop()
    logger.info("Local Authority Education GUI exited for user=%s", principal.username)
    return 0


if __name__ == "__main__":
    print("Launch via: python -m education_system --localauthority --gui")
    raise SystemExit(2)
