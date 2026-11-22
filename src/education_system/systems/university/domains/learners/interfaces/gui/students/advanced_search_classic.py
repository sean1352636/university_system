"""The Advanced Search window's classic layout: the left menu of every
feature in nine groups, the Dashboard tab, the Output tab, the results'
right-click menu and the four-tab student details window.

The menu opens the tabs of :class:`AdvancedSearchGUI` and the windows in
``advanced_search_windows``; everything runs on the rules in
``university/application`` (``student_search*``, ``student_bulk_actions``).
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, simpledialog, ttk

from education_system.systems.university.domains.learners.interfaces.gui.students.advanced_search import (  # noqa: E501
    TITLE, _call, _tree,
)


def _search():
    from education_system.systems.university.application.students import search as student_search
    return student_search


def _insights():
    from education_system.systems.university.application.students import (
        search_insights as student_search_insights,
    )
    return student_search_insights


def _tools():
    from education_system.systems.university.domains.learners.interfaces.gui.students import (
        advanced_search_tools,
    )
    return advanced_search_tools


def _windows():
    from education_system.systems.university.domains.learners.interfaces.gui.students import (
        advanced_search_windows,
    )
    return advanced_search_windows


# ── the frame: title, menu, tabs, status line ───────────────────────────


def build_frame(gui, master):
    """Title bar, left menu and the right-hand notebook. Returns the notebook."""
    user = gui.viewer.username or "not signed in"
    title = ttk.Frame(master, padding=(8, 6))
    title.pack(side=tk.TOP, fill=tk.X)
    ttk.Label(title, text="🔍 Advanced Student Search", font=("Segoe UI", 14, "bold")).pack(
        side=tk.LEFT)
    ttk.Label(title, text=f"Signed in as {user} ({gui.viewer.role or 'no role'})",
              foreground="#555").pack(side=tk.RIGHT)
    gui.status_var = tk.StringVar(value="Ready")
    ttk.Label(master, textvariable=gui.status_var, relief=tk.SUNKEN, anchor="w",
              padding=(6, 2)).pack(side=tk.BOTTOM, fill=tk.X)
    panes = ttk.PanedWindow(master, orient=tk.HORIZONTAL)
    panes.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
    menu = ttk.LabelFrame(panes, text="📋 Menu", padding=0)
    content = ttk.LabelFrame(panes, text="📊 Content", padding=4)
    panes.add(menu, weight=0)
    panes.add(content, weight=1)
    build_menu(gui, menu)
    notebook = ttk.Notebook(content)
    notebook.pack(fill=tk.BOTH, expand=True)
    gui.notebook = notebook
    return notebook


def show_tab(gui, text):
    """Bring the tab whose title contains ``text`` to the front."""
    for tab_id in gui.notebook.tabs():
        if text.lower() in gui.notebook.tab(tab_id, "text").lower():
            gui.notebook.select(tab_id)
            return True
    messagebox.showinfo(TITLE, f"{text} is not available to your role.", parent=gui.master)
    return False


def _need(gui, flag, what):
    if getattr(gui.viewer, flag, False):
        return True
    messagebox.showinfo(TITLE, f"You do not have permission to {what}.", parent=gui.master)
    return False


def _admin(gui):
    if gui.viewer.role in _search().ADMIN_ROLES:
        return True
    messagebox.showinfo(TITLE, "This is for administrators.", parent=gui.master)
    return False


# ── the left menu ───────────────────────────────────────────────────────


def menu_groups(gui):
    """The nine groups of the old menu: ``[(group, [(label, command)])]``."""
    w = _windows()
    t = _tools()
    return [
        ("📊 Analytics", [
            ("Search Analytics Dashboard", lambda: w.AnalyticsDashboard(gui)),
            ("Student Demographics Reports", lambda: w.DemographicsWindow(gui)),
            ("Advanced Demographics Window", lambda: w.DemographicsWindow(gui, "Cross")),
            ("Advanced Demographic Analysis", lambda: w.DemographicsWindow(gui, "Full")),
            ("Academic Performance Analysis", lambda: w.PerformanceWindow(gui)),
        ]),
        ("🔍 Search", [
            ("Multi-Criteria Search", lambda: multi_criteria(gui)),
            ("Fuzzy Name Search", lambda: w.quick_search(gui, "fuzzy")),
            ("Module Enrollment Search", lambda: w.quick_search(gui, "module")),
            ("Date Range Search", lambda: w.quick_search(gui, "dates")),
            ("Combined Filters Search", lambda: w.quick_search(gui, "combined")),
            ("Advanced Text Search", lambda: w.TextSearchMenu(gui)),
            ("Conditional Logic Search", lambda: w.quick_search(gui, "conditional")),
        ]),
        ("💾 Search Management", [
            ("Saved Search Profiles", lambda: w.SearchProfilesWindow(gui)),
            ("Search History", lambda: show_tab(gui, "My history")),
            ("Load Saved Search", lambda: show_tab(gui, "Saved searches")),
            ("Favorites Manager", lambda: show_tab(gui, "Favourites")),
            ("Repeat Last Search", lambda: t.repeat_last(gui)),
        ]),
        ("🔧 Bulk Operations", [
            ("Bulk Operations Menu", lambda: bulk(gui)),
            ("Mass Email Students", lambda: bulk(gui, "email")),
            ("Batch Data Updates", lambda: bulk(gui, "set_field")),
        ]),
        ("📋 Data Management", [
            ("Duplicate Detection", lambda: run_report(gui, "duplicates")),
            ("Data Quality Reports", lambda: run_report(gui, "data_quality")),
            ("Enhanced Import/Export", lambda: w.ImportExportWindow(gui)),
        ]),
        ("📈 Visualization", [
            ("Interactive Charts", gui.show_chart),
            ("Comprehensive Reports", lambda: w.ComprehensiveReports(gui)),
        ]),
        ("⚡ Smart Features", [
            ("Smart Features Menu", lambda: w.SmartFeaturesMenu(gui)),
        ]),
        ("👑 Admin", [
            ("Admin Features Menu", lambda: w.AdminFeaturesMenu(gui)),
        ]),
        ("🛠️ System", [
            ("Initialize Database", lambda: w.system_action(gui, "initialise")),
            ("System Optimization", lambda: w.system_action(gui, "optimise")),
            ("Database Status Check", lambda: w.system_action(gui, "status")),
            ("System Statistics", lambda: run_report(gui, "system")),
        ]),
    ]


def build_menu(gui, frame):
    canvas = tk.Canvas(frame, borderwidth=0, highlightthickness=0, width=230)
    bar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=bar.set)
    bar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units")
                    if canvas.winfo_exists() else None, add="+")
    row = 0
    for group, items in menu_groups(gui):
        ttk.Label(inner, text=group, font=("Segoe UI", 10, "bold")).grid(
            row=row, column=0, sticky="w", pady=(10, 4), padx=4)
        row += 1
        for label, command in items:
            ttk.Button(inner, text=label, width=28, command=_logged(gui, label, command)).grid(
                row=row, column=0, sticky="ew", pady=1, padx=(12, 4))
            row += 1


def _logged(gui, label, command):
    def run():
        gui.log(f"Opened: {label}")
        command()
    return run


def multi_criteria(gui):
    show_tab(gui, "Search")
    gui.add_row()
    gui.status_var.set("Add conditions, choose match all / any, then Search.")


def bulk(gui, action=None):
    if not (gui.viewer.can_update or gui.viewer.can_withdraw):
        messagebox.showinfo(TITLE, "You do not have permission for bulk actions.",
                            parent=gui.master)
        return
    show_tab(gui, "Search")
    dialog = gui.bulk_dialog()
    if action and dialog is not None:
        dialog.preselect(action)


def run_report(gui, name):
    if not getattr(gui, "reports_tab", None):
        messagebox.showinfo(TITLE, "Reports are for staff who can search all students.",
                            parent=gui.master)
        return
    show_tab(gui, "Reports")
    gui.reports_tab.select(name)
    gui.reports_tab.run()


# ── dashboard ───────────────────────────────────────────────────────────


class DashboardTab:
    FEATURES = (
        "Multi-criteria search with AND / OR, wildcard, regex and 'sounds like' matching",
        "Saved, shared and scheduled searches, favourites and follow-ups",
        "Demographic, performance, data-quality and duplicate reports (small groups hidden)",
        "Charts and exports in nine formats; bulk actions through the student service",
        "Every search, export and bulk action is recorded in the search audit",
    )

    def __init__(self, gui, notebook):
        self.gui = gui
        tab = ttk.Frame(notebook, padding=10)
        notebook.add(tab, text="🏠 Dashboard")
        ttk.Label(tab, text="Welcome to Advanced Student Search",
                  font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(tab, text="Find students by any combination of conditions, then act on, "
                            "report on or export the matches.", foreground="#555").pack(
            anchor="w", pady=(0, 8))
        cols = ttk.Frame(tab)
        cols.pack(fill=tk.BOTH, expand=True)
        left = ttk.LabelFrame(cols, text="✨ Features available", padding=8)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        for line in self.FEATURES:
            ttk.Label(left, text=f"• {line}", wraplength=420).pack(anchor="w", pady=1)
        self.stats = ttk.LabelFrame(cols, text="📈 Quick statistics", padding=8)
        self.stats.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6)
        recent = ttk.LabelFrame(cols, text="🕒 Your recent searches", padding=4)
        recent.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        self.recent = _tree(recent, [("at", "When"), ("search", "Search"), ("n", "Found")],
                            [120, 260, 60], height=8)
        self.recent.bind("<Double-1>", lambda _e: self._rerun())
        self._recent = {}
        quick = ttk.LabelFrame(tab, text="🚀 Quick actions", padding=8)
        quick.pack(fill=tk.X, pady=(8, 0))
        w = _windows()
        for label, command in (("Multi-criteria search", lambda: multi_criteria(gui)),
                               ("Search analytics dashboard", lambda: w.AnalyticsDashboard(gui)),
                               ("Student demographics reports",
                                lambda: w.DemographicsWindow(gui)),
                               ("Check the database", lambda: w.system_action(gui, "status")),
                               ("Refresh", self.load)):
            ttk.Button(quick, text=label, command=command).pack(side=tk.LEFT, padx=3)
        self.load()

    def load(self):
        figures = _call(self.gui.master, _insights().dashboard, self.gui.viewer)
        for child in self.stats.winfo_children():
            child.destroy()
        if isinstance(figures, dict):
            lines = [("Students you can see", figures["students"])]
            lines += [(f"  {status}", n) for status, n in figures["by_status"]]
            lines += [("Your saved searches", figures["my_saved_searches"]),
                      ("Shared searches", figures["shared_searches"]),
                      ("Your scheduled reports", figures["my_scheduled_reports"]),
                      ("Your searches today", figures["searches_today"])]
            if "open_followups" in figures:
                lines += [("Open follow-ups (all / yours)",
                           f"{figures['open_followups']} / {figures['my_followups']}"),
                          ("Your favourites", figures["favourites"])]
            for i, (label, value) in enumerate(lines):
                ttk.Label(self.stats, text=label).grid(row=i, column=0, sticky="w")
                ttk.Label(self.stats, text=str(value), font=("Segoe UI", 10, "bold")).grid(
                    row=i, column=1, sticky="e", padx=(12, 0))
        rows = _call(self.gui.master, _insights().recent_searches, self.gui.viewer, 15) or []
        self._recent = {str(r["id"]): r for r in rows}
        self.recent.delete(*self.recent.get_children())
        for iid, r in self._recent.items():
            self.recent.insert("", "end", iid=iid, values=(r["at"][:16], r["search"],
                                                           "" if r["count"] is None
                                                           else r["count"]))

    def _rerun(self):
        r = self._recent.get((self.recent.selection() or [""])[0])
        if r:
            self.gui.load_criteria(r["criteria"])
            show_tab(self.gui, "Search")


# ── output log ──────────────────────────────────────────────────────────


class OutputTab:
    def __init__(self, gui, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="💻 Output")
        bar = ttk.Frame(tab, padding=4)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(bar, text="🗑️ Clear output", command=self.clear).pack(side=tk.RIGHT)
        ttk.Button(bar, text="Save…", command=self.save).pack(side=tk.RIGHT, padx=4)
        self.text = tk.Text(tab, wrap="word", height=12, font=("Courier", 9), state="disabled")
        self.text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.master = gui.master

    def write(self, message):
        self.text.configure(state="normal")
        self.text.insert(tk.END, f"[{datetime.now():%H:%M:%S}] {message}\n")
        self.text.see(tk.END)
        self.text.configure(state="disabled")

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.configure(state="disabled")

    def save(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(parent=self.master, defaultextension=".txt",
                                            initialfile="advanced_search_output.txt")
        if path:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self.text.get("1.0", "end-1c"))


# ── results right-click menu ────────────────────────────────────────────


def attach_context_menu(gui):
    def popup(event):
        row = gui.tree.identify_row(event.y)
        if row and row not in gui.tree.selection():
            gui.tree.selection_set(row)
        menu = tk.Menu(gui.tree, tearoff=0)
        menu.add_command(label="Student details…", command=lambda: open_details(gui))
        menu.add_command(label="Open in Student Records", command=gui.open_selected)
        menu.add_separator()
        menu.add_command(label="Copy student IDs", command=lambda: copy(gui, "student_id"))
        menu.add_command(label="Copy names", command=lambda: copy(gui, "name"))
        menu.add_command(label="Copy emails", command=lambda: copy(gui, "email_address"))
        menu.add_separator()
        if gui.viewer.can_export:
            menu.add_command(label="Export selected…", command=gui.export)
        menu.add_command(label="Select all on this page",
                         command=lambda: gui.tree.selection_set(gui.tree.get_children()))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    gui.tree.bind("<Button-3>", popup)
    gui.tree.bind("<Button-2>", popup)


def copy(gui, key):
    keys = [f.key for f in gui.columns]
    if key not in keys:
        messagebox.showinfo(TITLE, "That column is not in your results.", parent=gui.master)
        return
    index = keys.index(key)
    values = [str(gui.tree.item(i, "values")[index]) for i in gui.selected_ids()]
    values = [v for v in values if v]
    if not values:
        messagebox.showinfo(TITLE, "Select some rows first.", parent=gui.master)
        return
    gui.master.clipboard_clear()
    gui.master.clipboard_append("; ".join(values) if key == "email_address"
                                else "\n".join(values))
    gui.status_var.set(f"Copied {len(values)} value(s).")
    gui.log(f"Copied {len(values)} {key.replace('_', ' ')} value(s)")


# ── student details (four tabs) ─────────────────────────────────────────


def open_details(gui, student_id=None):
    student_id = student_id or (gui.selected_ids() or [None])[0]
    if not student_id:
        messagebox.showinfo(TITLE, "Select a student first.", parent=gui.master)
        return
    StudentDetails(gui, student_id)


class StudentDetails:
    def __init__(self, gui, student_id):
        self.gui, self.sid = gui, student_id
        profile = _call(gui.master, _insights().student_profile, gui.viewer, student_id)
        if not isinstance(profile, dict):
            return
        perf = None
        if gui.viewer.can_view_all:
            perf = _call(gui.master, _reports_mod().student_performance, gui.viewer, student_id)
        win = _tools()._toplevel(gui.master, f"Student {student_id}", 980, 640)
        bar = ttk.Frame(win, padding=6)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(bar, text="Close", command=win.destroy).pack(side=tk.RIGHT)
        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self._basic(nb, profile)
        self._history(nb, perf)
        self._analytics(nb, perf)
        self._actions(nb, win)
        gui.log(f"Viewed details of {student_id}")

    def _basic(self, nb, profile):
        tab = ttk.Frame(nb, padding=10)
        nb.add(tab, text="Basic Information")
        for i, (label, value) in enumerate(profile["fields"]):
            ttk.Label(tab, text=label, font=("Segoe UI", 10, "bold")).grid(row=i, column=0,
                                                                          sticky="w", pady=2)
            ttk.Label(tab, text=str(value)).grid(row=i, column=1, sticky="w", padx=12)

    def _history(self, nb, perf):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Academic History")
        if not isinstance(perf, dict):
            ttk.Label(tab, text="Academic history is for staff who can search all students.",
                      padding=10).pack(anchor="w")
            return
        ttk.Label(tab, padding=6, wraplength=900, text=(
            f"Course: {perf['course']}   Status: {perf['status']}   Year: "
            f"{perf['year_of_study'] or '?'}\nEnrolled on: "
            f"{', '.join(perf['enrolled']) or 'nothing'}")).pack(anchor="w")
        tree = _tree(tab, [("code", "Module"), ("name", "Name"), ("mark", "Mark"),
                           ("grade", "Grade"), ("outcome", "Outcome"), ("attempt", "Attempt")],
                     [90, 260, 70, 70, 120, 80])
        for i, r in enumerate(perf["results"]):
            tree.insert("", "end", iid=str(i), values=(
                r.get("module_code"), r.get("module_name") or "", r.get("mark") or "",
                r.get("grade") or "", r.get("outcome") or "", r.get("attempt") or ""))

    def _analytics(self, nb, perf):
        tab = ttk.Frame(nb, padding=10)
        nb.add(tab, text="Performance Analytics")
        if not isinstance(perf, dict):
            ttk.Label(tab, text="Performance analytics is for staff who can search all "
                                "students.").pack(anchor="w")
            return
        marks = [float(r["mark"]) for r in perf["results"]
                 if isinstance(r.get("mark"), (int, float))]
        average = "no results" if perf["average_mark"] is None else perf["average_mark"]
        attended = "none recorded" if perf["attendance"] is None else f"{perf['attendance']}%"
        lines = [("Average mark", average), ("Attendance", attended),
                 ("Modules with a result", len(marks)),
                 ("Highest / lowest mark", f"{max(marks):g} / {min(marks):g}" if marks else "—"),
                 ("Modules passed (40+)", sum(1 for m in marks if m >= 40)),
                 ("Modules below 40", sum(1 for m in marks if m < 40))]
        for i, (label, value) in enumerate(lines):
            ttk.Label(tab, text=label, font=("Segoe UI", 10, "bold")).grid(row=i, column=0,
                                                                          sticky="w", pady=2)
            ttk.Label(tab, text=str(value)).grid(row=i, column=1, sticky="w", padx=12)
        if marks:
            canvas = tk.Canvas(tab, width=640, height=200, background="white")
            canvas.grid(row=len(lines), column=0, columnspan=2, pady=10, sticky="w")
            width = max(12, min(60, 600 // len(marks)))
            for i, (r, m) in enumerate(zip(perf["results"], marks)):
                x = 20 + i * (width + 6)
                y = 180 - int(m * 1.6)
                canvas.create_rectangle(x, y, x + width, 180,
                                        fill="#4a90d9" if m >= 40 else "#d9534f")
                canvas.create_text(x + width / 2, 192, text=str(r.get("module_code"))[:8],
                                   font=("Segoe UI", 7))
            canvas.create_line(15, 180 - 64, 630, 180 - 64, dash=(3, 2))
            canvas.create_text(600, 180 - 72, text="40", font=("Segoe UI", 8))

    def _actions(self, nb, win):
        tab = ttk.Frame(nb, padding=10)
        nb.add(tab, text="Actions")
        gui, sid = self.gui, self.sid
        t = _tools()
        actions = [("Open in Student Records",
                    lambda: gui.open_student(sid) if gui.open_student else None)]
        if gui.viewer.can_view_all:
            actions += [("Add to my favourites", lambda: self._favourite()),
                        ("Mark for follow-up…", lambda: t.followup_dialog(gui, [sid])),
                        ("Performance report…", lambda: t.student_performance(gui, sid))]
        if gui.viewer.can_update or gui.viewer.can_withdraw:
            actions.append(("Email or act on this student…", lambda: self._bulk()))
        for label, command in actions:
            ttk.Button(tab, text=label, width=32, command=command).pack(anchor="w", pady=2)

    def _favourite(self):
        note = simpledialog.askstring(TITLE, "Note (optional):", parent=self.gui.master) or ""
        if _call(self.gui.master, _extras_mod().add_favourite, self.gui.viewer, self.sid, note,
                 write=True):
            messagebox.showinfo(TITLE, "Added to your favourites.", parent=self.gui.master)

    def _bulk(self):
        self.gui.tree.selection_set([self.sid]) if self.gui.tree.exists(self.sid) else None
        dialog = self.gui.bulk_dialog(ids=[self.sid])
        if dialog is not None:
            dialog.preselect("email")


def _reports_mod():
    from education_system.systems.university.application.students import (
        search_reports as student_search_reports,
    )
    return student_search_reports


def _extras_mod():
    from education_system.systems.university.application.students import (
        search_extras as student_search_extras,
    )
    return student_search_extras
