"""Tk GUI main window for the Secondary School System.

Same layout as the sixth form and university main windows:

    row 0 - header (Dashboard · Logout · Switch to CLI · Switch System | title | Shutdown)
    row 1 - left navigation (search + accordion of categories) | content area
    row 2 - status bar (status · current user · system / version)

The menu comes from :mod:`app.routing` (shared with the CLI) and is
filtered by :mod:`core.permissions.access`. A menu entry opens the page its area
registered for the key (``PAGES`` in ``modules/<module>/gui/__init__.py``, see
:mod:`ui.gui.navigation.pages`); a few entries that are not ordinary pages (dialogs,
pickers, the My Day landing page, About) are ``open_<key>`` methods here.
Entries with neither show a "not built yet" page.

Launched only by the unified launcher after the shared login - there is no
standalone login.
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
from education_system.systems.secondary import SYSTEM_KEY, SYSTEM_NAME
from education_system.systems.secondary.app import bootstrap
from education_system.systems.secondary.core.permissions import access
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.app import routing as menu
from education_system.systems.secondary.ui.gui.navigation import pages

logger = logging.getLogger(__name__)

VERSION = "0.1.0"
FOOTER_LABEL = "Secondary School"


def _footer_label() -> str:
    """The school's name from School Settings (the old fixed label until set)."""
    try:
        from education_system.systems.secondary.modules.communication.domain import letters
        return letters.school_name() or FOOTER_LABEL
    except Exception:  # noqa: BLE001 - only a label
        return FOOTER_LABEL


#: A page draws itself into a parent frame, so the same function can render
#: in the main window or in a pop-out window.
PageDraw = Callable[[ttk.Frame], None]


class SecondaryMainGUI:
    def __init__(self, auth, principal: access.Principal | None = None):
        self.auth = auth
        self.principal = principal or access.from_auth(auth)
        # run() normally starts the activity-log session; start one here if
        # the window was opened another way, so no action is logged anonymously.
        current = activity_log.current_session()
        if (current["id"] is None or current["user"] != self.principal.username
                or current["interface"] != "gui"):
            activity_log.start_session(self.principal, "gui")

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
        # Staff land on their own day (the staff portal); the school dashboard
        # is one click away on the header.
        self.open_staff_portal()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Sign out after EDU_IDLE_TIMEOUT_MINUTES of inactivity, the same
        # way the Logout button does.
        from education_system.platform.delivery.gui.idle_timeout import install_idle_logout
        self._cancel_idle = install_idle_logout(self.root, self._idle_logout)

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
        ttk.Button(left, text="👤 My Day", command=self.open_staff_portal).pack(
            side="left", padx=(0, 6))
        ttk.Button(left, text="Logout", command=self._logout).pack(side="left", padx=(0, 6))
        ttk.Button(left, text="Switch to CLI", command=self._switch_to_cli).pack(
            side="left", padx=(0, 6))
        try:
            from education_system.launcher.roles import is_superadmin
            if is_superadmin(self.auth.current_user):
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
        self.nav_search_entry = search_entry

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
        visible = access.visible_categories(self.principal, menu.CATEGORIES)
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
        ttk.Label(right, text=_footer_label(), foreground="#555").pack(side="left")
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
        """Draw a page in the content area and remember it for pop-out."""
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
        activity_log.record("page.popout", target=label)
        win = tk.Toplevel(self.root)
        win.title(f"{label} — {SYSTEM_NAME}")
        window_sizing.fit(win, "1000x700", (700, 500))
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)
        draw(frame)

    def _handler(self, key: str, label: str) -> Callable[[], None]:
        """The command for a menu entry: the main window's own ``open_<key>``
        method (dialogs, the landing page, pickers) if it has one, else the
        page a module registered for *key*, else the "not built yet" page.
        Access is re-checked on every click, so a quick action or search
        result can't reach a refused area."""
        def run() -> None:
            if not self.principal.can_open(label):
                activity_log.record("menu.open", target=label, outcome="denied")
                self._show_denied(label)
                return
            method = getattr(self, f"open_{key}", None)
            if callable(method):
                activity_log.record("menu.open", target=label)
                method()
            elif pages.find(key) is not None:
                activity_log.record("menu.open", target=label)
                self.open_page(key)
            else:
                activity_log.record("menu.open", target=label, outcome="not_built")
                self._show_page(label, lambda parent: _draw_not_built(parent, label))
        return run

    def open_page(self, key: str) -> None:
        """Show the page a module registered for *key* (see ``ui.gui.navigation.pages``).
        Its view module is imported now, not at startup."""
        page = pages.find(key)
        if page is None:
            raise KeyError(f"no page is registered for {key!r}")
        draw = pages.load(page)
        links = {"open_pupil": self.show_pupil_profile, "on_status": self.status_var.set,
                 "open_application": self.show_application, "open_year": self.show_year_group,
                 "open_form": self.show_form_group, "open_group": self.show_teaching_group,
                 "open_message": self.show_message}
        kwargs = {"principal": self.principal, **{name: links[name] for name in page.links}}
        if page.state:
            kwargs["state"] = self.__dict__.setdefault(page.state, {})  # tabs/filters survive redraws
        self._show_page(page.title, lambda parent: draw(parent, **kwargs))

    def _show_denied(self, label: str) -> None:
        logger.warning("Refused %s for user=%s role=%s", label,
                       self.principal.username, self.principal.role)
        messagebox.showwarning("Not available", self.principal.denied_message(label),
                               parent=self.root)

    # ── Dashboard ────────────────────────────────────────────────────
    def _show_welcome(self) -> None:
        activity_log.record("dashboard.open")
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

        # Figures fill in as their areas are built; until then they say so
        # rather than showing a made-up number.
        kpis = [
            ("Pupils on roll", *self._pupils_on_roll()),
            ("Staff", "—", "Available once Staff is built"),
            ("Form groups", *self._form_group_count()),
            ("Attendance today", "—", "Available once Registers is built"),
        ]
        kpi_row = ttk.Frame(root)
        kpi_row.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        for i, (label, value, hint) in enumerate(kpis):
            kpi_row.columnconfigure(i, weight=1, uniform="kpi")
            tile = ttk.LabelFrame(kpi_row, padding=12)
            tile.grid(row=0, column=i, padx=4, sticky="nsew")
            ttk.Label(tile, text=label, foreground="#666").pack(anchor="w")
            ttk.Label(tile, text=value, font=("", 22, "bold")).pack(anchor="w", pady=(2, 0))
            ttk.Label(tile, text=hint, foreground="#888", font=("", 9)).pack(
                anchor="w", pady=(2, 0))

        quick = [
            ("Add Pupil", "add_pupil"),
            ("Search Pupils", "search_pupils"),
            ("Take Register", "attendance"),
            ("Timetable", "timetable"),
            ("Gradebook", "gradebook"),
            ("Behaviour & Rewards", "behaviour"),
            ("Email", "messages"),
        ]
        quick = [(lbl, key) for lbl, key in quick if self.principal.can_open(lbl)]
        if quick:
            actions = ttk.LabelFrame(root, text="Quick actions", padding=8)
            actions.grid(row=2, column=0, sticky="ew", pady=(0, 14))
            for i, (lbl, key) in enumerate(quick):
                ttk.Button(actions, text=lbl, command=self._handler(key, lbl),
                           style="Large.TButton").grid(
                    row=0, column=i, padx=4, pady=2, sticky="ew")
                actions.columnconfigure(i, weight=1, uniform="qa")

        lower = ttk.Frame(root)
        lower.grid(row=3, column=0, sticky="nsew")
        root.rowconfigure(3, weight=1)
        for i in range(3):
            lower.columnconfigure(i, weight=1, uniform="lower")
        self._build_recent_pupils_panel(lower)
        self._build_recent_behaviour_panel(lower)
        panels = [
            ("Coming up", "Term dates and school events will appear here."),
        ]
        for i, (title, text) in enumerate(panels, start=2):
            box = ttk.LabelFrame(lower, text=title, padding=10)
            box.grid(row=0, column=i, padx=4, sticky="nsew")
            ttk.Label(box, text=text, foreground="#888", wraplength=260,
                      justify="left").pack(anchor="w")

        self.status_var.set("Ready")

    def _form_group_count(self) -> tuple[str, str]:
        try:
            from education_system.systems.secondary.modules.curriculum.domain import form_groups
            forms = form_groups.list_forms()
            loose = len(form_groups.without_form())
        except Exception:
            logger.exception("Dashboard form count failed")
            return "—", "Couldn't read form groups"
        return str(len(forms)), (f"{loose} pupil(s) with no form" if loose else "Years 7–11")

    def _pupils_on_roll(self) -> tuple[str, str]:
        """(value, hint) for the dashboard tile; '—' with the reason on failure."""
        try:
            from education_system.systems.secondary.modules.pupils.domain import pupils
            rows = pupils.list_pupils()
        except Exception:
            logger.exception("Dashboard pupil count failed")
            return "—", "Couldn't read pupil records"
        by_year = {y: 0 for y in pupils.YEAR_GROUPS}
        for p in rows:
            by_year[p.year_group] = by_year.get(p.year_group, 0) + 1
        hint = " · ".join(f"Y{y} {n}" for y, n in by_year.items())
        return str(len(rows)), hint

    def _build_recent_pupils_panel(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Recent pupils", padding=10)
        box.grid(row=0, column=0, padx=4, sticky="nsew")
        if not self.principal.can_open("Pupil Directory"):
            return
        try:
            from education_system.systems.secondary.modules.pupils.domain import pupils
            recent = sorted(pupils.list_pupils(roll_status=None),
                            key=lambda p: p.updated_at, reverse=True)[:6]
        except Exception:
            logger.exception("Recent pupils panel failed")
            ttk.Label(box, text="Couldn't read pupil records.", foreground="#a00").pack(
                anchor="w")
            return
        if not recent:
            ttk.Label(box, text="No pupils yet. Use Add Pupil to create the first record.",
                      foreground="#888", wraplength=260, justify="left").pack(anchor="w")
            return
        for p in recent:
            ttk.Button(box, text=f"{p.display_name} · Y{p.year_group}"
                                 f"{' · ' + p.form_group if p.form_group else ''}",
                       command=lambda pid=p.pupil_id: self.show_pupil_profile(pid)).pack(
                fill="x", pady=1)

    def _build_recent_behaviour_panel(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="Recent behaviour", padding=10)
        box.grid(row=0, column=1, padx=4, sticky="nsew")
        if not self.principal.can_open("Behaviour & Rewards"):
            return
        try:
            from education_system.systems.secondary.modules.behaviour.domain import behaviour
            recent = behaviour.recent(6)
        except Exception:
            logger.exception("Recent behaviour panel failed")
            ttk.Label(box, text="Couldn't read behaviour entries.", foreground="#a00").pack(
                anchor="w")
            return
        if not recent:
            ttk.Label(box, text="No behaviour logged yet. Use Behaviour & Rewards to log the "
                                "first entry.", foreground="#888", wraplength=260,
                      justify="left").pack(anchor="w")
            return
        for e in recent:
            ttk.Button(box, text=f"{'★' if e.polarity == 'positive' else '•'} "
                                 f"{e.pupil_name} · {e.incident_type} {e.points:+d}",
                       command=lambda pid=e.pupil_id: self.show_pupil_profile(pid)).pack(
                fill="x", pady=1)
        ttk.Button(box, text="Open Behaviour & Rewards…",
                   command=self._handler("behaviour", "Behaviour & Rewards")).pack(
            anchor="e", pady=(4, 0))

    # ── Built pages ──────────────────────────────────────────────────
    def _pupil_views(self):
        from education_system.systems.secondary.modules.pupils.gui import pupils_views
        return pupils_views

    def open_pupil_directory(self, *, focus_search: bool = False,
                             title: str = "Pupil Directory") -> None:
        views = self._pupil_views()
        self._show_page(title, lambda parent: views.draw_directory(
            parent, principal=self.principal, open_profile=self.show_pupil_profile,
            focus_search=focus_search, title=title))

    def open_search_pupils(self) -> None:
        self.open_pupil_directory(focus_search=True, title="Search Pupils")

    def open_add_pupil(self) -> None:
        views = self._pupil_views()
        views.open_pupil_form(self.root, principal=self.principal, pupil=None,
                              on_saved=lambda p: self.show_pupil_profile(p.pupil_id))

    def open_pupil_profile(self) -> None:
        views = self._pupil_views()
        self._show_page("Pupil Profile", lambda parent: views.draw_pupil_picker(
            parent, on_pick=self.show_pupil_profile))

    def show_pupil_profile(self, pupil_id: int) -> None:
        """One pupil's profile in the main window (also used by search results)."""
        views = self._pupil_views()
        self._show_page("Pupil Profile", lambda parent: views.draw_profile(
            parent, pupil_id, principal=self.principal,
            on_changed=lambda: self.show_pupil_profile(pupil_id),
            on_deleted=self.open_pupil_directory))

    def _admissions_views(self):
        from education_system.systems.secondary.modules.admissions.gui import admissions_views
        return admissions_views

    def show_application(self, application_id: int) -> None:
        views = self._admissions_views()
        self._show_page("Admissions", lambda parent: views.draw_application(
            parent, application_id, principal=self.principal,
            on_changed=lambda: self.show_application(application_id),
            on_back=lambda: self.open_page("admissions"), open_pupil=self.show_pupil_profile))

    def show_year_group(self, year: int) -> None:
        from education_system.systems.secondary.modules.curriculum.gui import year_groups_views
        self._show_page("Year Groups", lambda parent: year_groups_views.draw_year(
            parent, year, principal=self.principal, open_pupil=self.show_pupil_profile,
            on_back=lambda: self.open_page("year_groups"), on_changed=lambda: self.show_year_group(year)))

    def show_form_group(self, form_id: int) -> None:
        from education_system.systems.secondary.modules.curriculum.gui import form_groups_views
        self._show_page("Form Groups", lambda parent: form_groups_views.draw_form(
            parent, form_id, principal=self.principal, open_pupil=self.show_pupil_profile,
            on_back=lambda: self.open_page("form_groups"), on_changed=lambda: self.show_form_group(form_id)))

    def open_staff_portal(self) -> None:
        from education_system.systems.secondary.modules.portals.gui import my_day_views
        try:
            self._show_page("Staff Portal", lambda parent: my_day_views.draw_my_day(
                parent, principal=self.principal, app=self))
        except Exception:
            # The landing page must never stop the window opening.
            logger.exception("Staff portal failed - showing the dashboard")
            self._show_welcome()

    def show_teaching_group(self, group_id: int) -> None:
        from education_system.systems.secondary.modules.curriculum.gui import teaching_groups_views
        self._show_page("Teaching Groups", lambda parent: teaching_groups_views.draw_group(
            parent, group_id, principal=self.principal, open_pupil=self.show_pupil_profile,
            on_back=lambda: self.open_page("teaching_groups"),
            on_changed=lambda: self.show_teaching_group(group_id)))

    def _email_views(self):
        from education_system.systems.secondary.modules.communication.gui import email_views
        return email_views

    def show_message(self, message_id: int) -> None:
        views = self._email_views()
        self._show_page("Email", lambda parent: views.draw_message(
            parent, message_id, principal=self.principal, on_back=lambda: self.open_page("messages"),
            on_changed=lambda: self.show_message(message_id)))

    def open_parent_contacts(self) -> None:
        pupil_views = self._pupil_views()
        self._show_page("Parent Contacts", lambda parent: pupil_views.draw_pupil_picker(
            parent, on_pick=self.show_pupil_contacts))

    def show_pupil_contacts(self, pupil_id: int) -> None:
        from education_system.systems.secondary.modules.communication.gui import contacts_views
        self._show_page("Parent Contacts", lambda parent: contacts_views.draw_contacts_page(
            parent, pupil_id, principal=self.principal,
            on_changed=lambda: self.show_pupil_contacts(pupil_id),
            on_back=self.open_parent_contacts))

    def open_change_password(self) -> None:
        from education_system.platform.delivery.gui.change_password_gui import (
            open_change_password_dialog,
        )
        open_change_password_dialog(self.root, auth=self.auth)

    def open_mfa(self) -> None:
        from education_system.platform.delivery.gui.mfa_setup_gui import open_mfa
        open_mfa(self.root, auth=self.auth)

    def open_about(self) -> None:
        principal = self.principal

        def draw(parent: ttk.Frame) -> None:
            ttk.Label(parent, text=SYSTEM_NAME, font=("", 16, "bold")).pack(
                anchor="w", pady=(0, 8))
            rows = [
                ("Version", VERSION),
                ("Covers", "Years 7–11 (Key Stages 3 and 4)"),
                ("Signed in as", principal.username or "—"),
                ("Role", principal.role or "—"),
            ]
            grid = ttk.Frame(parent)
            grid.pack(anchor="w")
            for r, (k, v) in enumerate(rows):
                ttk.Label(grid, text=f"{k}:", foreground="#555").grid(
                    row=r, column=0, sticky="w", padx=(0, 12), pady=2)
                ttk.Label(grid, text=v).grid(row=r, column=1, sticky="w", pady=2)

        self._show_page("About", draw)

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
        """An unexpected error in a button or screen: log it, tell the user."""
        logger.error("Unhandled error in the secondary GUI",
                     exc_info=(exc_type, exc, tb))
        activity_log.record("error", outcome="error", error=exc_type.__name__)
        try:
            messagebox.showerror(SYSTEM_NAME, f"Something went wrong:\n{exc}",
                                 parent=self.root)
        except tk.TclError:
            pass

    def _logout(self) -> None:
        from education_system import switch as _switch
        activity_log.end_session("logout")
        self._sign_out()
        _switch.request_logout("gui")
        self.root.destroy()

    def _idle_logout(self) -> None:
        """Same teardown as Logout, then say why. The notice comes last: it
        is modal, and shown first it would keep the session open on screen."""
        from education_system import switch as _switch
        from education_system.platform.delivery.gui import idle_timeout as _idle
        logger.info("Idle logout for user=%s", self.principal.username)
        activity_log.end_session("idle_timeout")
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
        if not messagebox.askyesno("Switch to CLI",
                                   "Close the GUI and continue in the CLI?",
                                   parent=self.root):
            return
        from education_system import switch as _switch
        activity_log.end_session("switch_to_cli")
        self._stop_idle_watcher()
        _switch.request_switch(SYSTEM_KEY, "cli")
        self.root.destroy()

    def _switch_system(self) -> None:
        from education_system import switch as _switch
        from education_system.launcher.system_switch import pick_system_gui
        target = pick_system_gui(self.root, self.auth.current_user, SYSTEM_KEY)
        if not target:
            return
        activity_log.end_session(f"switch_system:{target}")
        self._stop_idle_watcher()
        _switch.request_switch(target, "gui")
        self.root.destroy()

    def _shutdown(self) -> None:
        if not messagebox.askyesno("Shutdown", f"Shut down the {SYSTEM_NAME}?",
                                   parent=self.root):
            return
        activity_log.end_session("shutdown")
        self._sign_out()
        self.root.destroy()
        sys.exit(0)

    def _on_close(self) -> None:
        activity_log.end_session("window_closed")
        self._sign_out()
        self.root.destroy()


def _draw_not_built(parent: ttk.Frame, label: str) -> None:
    ttk.Label(parent, text=label, font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))
    ttk.Label(parent,
              text=f"{label} hasn't been built yet in the new {SYSTEM_NAME}.",
              foreground="#555").pack(anchor="w")


def run(user_info=None, role=None, shared_auth=None) -> int:
    """Open the main window for a session the unified login already signed in.

    Only staff get the staff window. Pupils and parents are told their
    portal rather than the staff window.
    """
    bootstrap.require_shared_session(shared_auth, "gui")
    principal = bootstrap.start_session(shared_auth, role, "gui")
    logger.info("Secondary GUI starting for user=%s role=%s",
                principal.username, principal.role)

    if not principal.is_staff:
        if principal.is_student or principal.is_parent:
            from education_system.systems.secondary.modules.portals.gui import portal_views
            logger.info("Opening the %s portal for user=%s",
                        "pupil" if principal.is_student else "parent", principal.username)
            return portal_views.run_portal(shared_auth, principal)
        else:
            msg = (f"The {SYSTEM_NAME} staff window is only for school staff.\n\n"
                   f"Your account is signed in as '{principal.role or 'no role'}'.")
        logger.warning("Refusing secondary staff GUI for user=%s role=%s",
                       principal.username, principal.role)
        activity_log.end_session("refused_not_staff")
        _show_refusal(msg)
        return 0

    rolled = bootstrap.roll_year_if_due(principal)
    app = SecondaryMainGUI(shared_auth, principal)
    if rolled:
        text = "\n\n".join(r.summary() for r in rolled)
        app.status_var.set(rolled[-1].summary())
        app.root.after(400, lambda: messagebox.showinfo(
            "Year-end rollover", text + "\n\nEach pupil's change history shows the move.",
            parent=app.root))
        app.root.after(450, app._show_welcome)
    app.root.mainloop()
    logger.info("Secondary GUI exited for user=%s", principal.username)
    return 0


def _show_refusal(message: str) -> None:
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo(SYSTEM_NAME, message, parent=root)
    root.destroy()


if __name__ == "__main__":
    print("Launch via: python -m education_system --secondary --gui")
    raise SystemExit(2)
