"""The extra tabs and dialogs of the Advanced Search window: reports
(demographics, cross-tabulation, performance, data quality, duplicates,
insights, administrators' statistics), follow-ups, favourites, your search
history, and from the Search tab: export in any format, groups, email
lists, follow-up marking, favourites, one student's performance, repeat the
last search and Find suggestions.

Rules are in ``university/application``: ``student_search_reports``,
``student_search_extras``, ``student_search``. This module only presents
them; :func:`attach` adds them to an :class:`AdvancedSearchGUI`.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from education_system.systems.university.domains.learners.interfaces.gui.students.advanced_search import (  # noqa: E501
    TITLE, _call, _text_window, _tree,
)


def _search():
    from education_system.systems.university.application.students import search as student_search
    return student_search


def _reports():
    from education_system.systems.university.application.students import (
        search_reports as student_search_reports,
    )
    return student_search_reports


def _extras():
    from education_system.systems.university.application.students import (
        search_extras as student_search_extras,
    )
    return student_search_extras


def _export_formats():
    from education_system.systems.university.infrastructure.data_management import table_export
    return table_export


def _ask_path(parent, initial, admin=False):
    """A save-as dialog offering every export format; ``(path, fmt,
    delimiter)`` or ``None``."""
    te = _export_formats()
    types = [(label, f"*{te.EXTENSIONS[k]}") for k, label in te.FORMATS.items()
             if k != "delimited" and (admin or k != "sql")]
    path = filedialog.asksaveasfilename(parent=parent, initialfile=initial,
                                        defaultextension=".csv", filetypes=types)
    if not path:
        return None
    fmt = te.format_for(path)
    delimiter = ","
    if path.lower().endswith(".txt") and messagebox.askyesno(
            TITLE, "Write the .txt file with a delimiter of your choice (instead of a "
                   "laid-out text table)?", parent=parent):
        delimiter = simpledialog.askstring(TITLE, "Delimiter (one character):",
                                           initialvalue="|", parent=parent)
        if not delimiter:
            return None
        fmt = "delimited"
    return path, fmt, delimiter


def _toplevel(parent, title, width=1000, height=640):
    win = tk.Toplevel(parent)
    win.title(title)
    try:
        from education_system.platform.delivery.gui import window_sizing
        window_sizing.center(win, width, height, minsize=(min(width, 800), min(height, 500)))
    except Exception:
        win.geometry(f"{width}x{height}")
    return win


# ── attaching to the window ─────────────────────────────────────────────


def attach(gui, notebook):
    """Add the tools to ``gui`` (an AdvancedSearchGUI)."""
    _attach_autocomplete(gui)
    if gui.viewer.can_view_all:
        ReportsTab(gui, notebook)
        FollowupsTab(gui, notebook)
        FavouritesTab(gui, notebook)
    HistoryTab(gui, notebook)


def more_menu(gui, widget):
    """The "More ▾" menu under the results."""
    menu = tk.Menu(widget, tearoff=0)
    menu.add_command(label="Select all on this page",
                     command=lambda: gui.tree.selection_set(gui.tree.get_children()))
    menu.add_command(label="Repeat my last search", command=lambda: repeat_last(gui))
    if gui.viewer.can_view_all:
        menu.add_separator()
        menu.add_command(label="Make groups…", command=lambda: GroupsDialog(gui))
        menu.add_command(label="Email list…", command=lambda: email_list_dialog(gui))
        menu.add_command(label="Mark for follow-up…", command=lambda: followup_dialog(gui))
        menu.add_command(label="Add to my favourites", command=lambda: add_favourites(gui))
        menu.add_command(label="Selected student's performance…",
                         command=lambda: student_performance(gui))
    try:
        menu.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())
    finally:
        menu.grab_release()


def export_dialog(gui):
    """Export the matches (or the selected rows) in any format, choosing
    the fields."""
    if not gui.viewer.can_export:
        messagebox.showerror(TITLE, "You do not have permission to export.", parent=gui.master)
        return
    win = tk.Toplevel(gui.master)
    win.title("Export students")
    body = ttk.Frame(win, padding=10)
    body.pack(fill=tk.BOTH, expand=True)
    selected = gui.selected_ids()
    scope = tk.StringVar(value="selected" if selected else "all")
    ttk.Radiobutton(body, text=f"Every match ({gui.state['total']})", variable=scope,
                    value="all").pack(anchor="w")
    ttk.Radiobutton(body, text=f"Selected rows ({len(selected)})", variable=scope,
                    value="selected", state="normal" if selected else "disabled").pack(anchor="w")
    ttk.Label(body, text="Fields").pack(anchor="w", pady=(8, 2))
    chosen = {}
    grid = ttk.Frame(body)
    grid.pack(anchor="w")
    for i, f in enumerate(gui.columns):
        var = tk.BooleanVar(value=True)
        chosen[f.key] = var
        ttk.Checkbutton(grid, text=f.label, variable=var).grid(row=i // 3, column=i % 3,
                                                               sticky="w", padx=4)

    def go():
        fields = [k for k, v in chosen.items() if v.get()]
        if not fields:
            messagebox.showinfo(TITLE, "Choose at least one field.", parent=win)
            return
        target = _ask_path(win, "students.csv", gui.viewer.role in _search().ADMIN_ROLES)
        if not target:
            return
        path, fmt, delimiter = target
        ids = selected if scope.get() == "selected" else None
        n = _call(win, _search().export, gui.state["criteria"], gui.viewer, path, fields,
                  fmt, ids=ids, delimiter=delimiter, write=True)
        if n is not None:
            messagebox.showinfo(TITLE, f"Exported {n} student(s) to {path}.\nThe export is "
                                "recorded in the search audit.", parent=win)
            win.destroy()

    bar = ttk.Frame(body)
    bar.pack(fill=tk.X, pady=(10, 0))
    ttk.Button(bar, text="Export…", command=go).pack(side=tk.LEFT)
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side=tk.LEFT, padx=4)


def repeat_last(gui):
    criteria = _call(gui.master, _extras().last_search, gui.viewer)
    if isinstance(criteria, dict):
        gui.load_criteria(criteria)
    else:
        messagebox.showinfo(TITLE, "You have no earlier search.", parent=gui.master)


def _ids_or_all(gui):
    ids = gui.selected_ids()
    if ids:
        return ids
    if not messagebox.askyesno(TITLE, f"No rows selected. Use every match "
                                      f"({gui.state['total']})?", parent=gui.master):
        return None
    return _call(gui.master, _search().all_ids, gui.state["criteria"], gui.viewer) or None


# ── Find suggestions ────────────────────────────────────────────────────


def _attach_autocomplete(gui):
    box = {"list": None}

    def hide(_e=None):
        if box["list"] is not None:
            box["list"].destroy()
            box["list"] = None

    def pick(_e=None):
        lb = box["list"]
        if lb is not None and lb.curselection():
            gui.text.delete(0, tk.END)
            gui.text.insert(0, lb.get(lb.curselection()[0]))
        hide()
        gui.run_search()

    def update(event):
        if event.keysym in ("Return", "Escape", "Up", "Down", "Tab"):
            if event.keysym == "Escape":
                hide()
            elif event.keysym == "Down" and box["list"] is not None:
                box["list"].focus_set()
                box["list"].selection_set(0)
            return
        found = _call(gui.master, _search().suggestions, gui.viewer, gui.text.get()) or []
        if not found:
            hide()
            return
        if box["list"] is None:
            lb = tk.Listbox(gui.text.winfo_toplevel(), height=min(8, len(found)))
            lb.bind("<Double-1>", pick)
            lb.bind("<Return>", pick)
            lb.bind("<Escape>", hide)
            box["list"] = lb
        lb = box["list"]
        lb.delete(0, tk.END)
        for value in found:
            lb.insert(tk.END, value)
        lb.configure(height=min(8, len(found)))
        top = gui.text.winfo_toplevel()
        lb.place(x=gui.text.winfo_rootx() - top.winfo_rootx(),
                 y=gui.text.winfo_rooty() - top.winfo_rooty() + gui.text.winfo_height(),
                 width=max(gui.text.winfo_width(), 260))
        lb.lift()

    gui.text.bind("<KeyRelease>", update, add="+")
    gui.text.bind("<FocusOut>", lambda _e: gui.text.after(200, hide), add="+")


# ── groups, email lists, follow-ups, favourites ─────────────────────────


class GroupsDialog:
    def __init__(self, gui):
        self.gui = gui
        ex = _extras()
        self.win = win = tk.Toplevel(gui.master)
        win.title("Make groups")
        body = ttk.Frame(win, padding=10)
        body.pack(fill=tk.BOTH, expand=True)
        self.method = tk.StringVar(value="course")
        for key, label in ex.GROUP_METHODS.items():
            ttk.Radiobutton(body, text=label, variable=self.method, value=key).pack(anchor="w")
        row = ttk.Frame(body)
        row.pack(anchor="w", pady=6)
        ttk.Label(row, text="Group size (N)").pack(side=tk.LEFT)
        self.size = ttk.Spinbox(row, from_=1, to=500, width=6)
        self.size.set("5")
        self.size.pack(side=tk.LEFT, padx=4)
        self.only_selected = tk.BooleanVar(value=bool(gui.selected_ids()))
        ttk.Checkbutton(body, text=f"Only the selected rows ({len(gui.selected_ids())})",
                        variable=self.only_selected).pack(anchor="w")
        ttk.Button(body, text="Make groups", command=self.make).pack(anchor="w", pady=8)

    def make(self):
        ids = self.gui.selected_ids() if self.only_selected.get() else None
        groups = _call(self.win, _extras().make_groups, self.gui.state["criteria"],
                       self.gui.viewer, self.method.get(), self.size.get(), ids=ids, write=True)
        if not isinstance(groups, dict):
            return
        win = _toplevel(self.win, f"Groups ({len(groups)})", 820, 560)
        bar = ttk.Frame(win, padding=6)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        tree = ttk.Treeview(win, columns=("id", "name", "course", "status"), show="tree headings")
        for key, title, width in (("#0", "Group / student", 160), ("id", "Student ID", 100),
                                  ("name", "Name", 200), ("course", "Course", 160),
                                  ("status", "Status", 120)):
            tree.heading(key, text=title)
            tree.column(key, width=width)
        tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        for name, members in groups.items():
            parent = tree.insert("", "end", text=f"{name} ({len(members)})", open=True)
            for r in members:
                tree.insert(parent, "end", text="", values=(
                    r["student_id"], r.get("name") or "", r.get("course") or "",
                    r.get("status") or ""))

        def export():
            target = _ask_path(win, "groups.csv")
            if not target:
                return
            path, fmt, delimiter = target
            columns, rows = _extras().groups_table(groups)
            te = _export_formats()
            try:
                te.write(path, columns, rows, fmt, title="Student groups", delimiter=delimiter,
                         labels={c: c.replace("_", " ").capitalize() for c in columns})
            except Exception as exc:
                messagebox.showerror(TITLE, f"Could not export: {exc}", parent=win)
                return
            messagebox.showinfo(TITLE, f"Saved {len(rows)} row(s) to {path}.", parent=win)

        ttk.Button(bar, text="Export…", command=export).pack(side=tk.LEFT)
        ttk.Button(bar, text="Close", command=win.destroy).pack(side=tk.RIGHT)


def email_list_dialog(gui):
    ex = _extras()
    win = tk.Toplevel(gui.master)
    win.title("Email list")
    body = ttk.Frame(win, padding=10)
    body.pack(fill=tk.BOTH, expand=True)
    layout = tk.StringVar(value="semicolon")
    for key, label in ex.LIST_LAYOUTS.items():
        ttk.Radiobutton(body, text=label, variable=layout, value=key).pack(anchor="w")
    personal = tk.BooleanVar(value=False)
    if gui.viewer.can_view_sensitive:
        ttk.Checkbutton(body, text="Personal addresses (instead of university ones)",
                        variable=personal).pack(anchor="w")
    selected = gui.selected_ids()
    only = tk.BooleanVar(value=bool(selected))
    ttk.Checkbutton(body, text=f"Only the selected rows ({len(selected)})",
                    variable=only).pack(anchor="w")
    out = tk.Text(body, height=10, width=70, wrap="word")
    status = ttk.Label(body, text="")

    def make():
        result = _call(win, ex.email_list, gui.state["criteria"], gui.viewer, layout.get(),
                       personal.get(), ids=selected if only.get() else None, write=True)
        if not isinstance(result, dict):
            return
        out.delete("1.0", tk.END)
        out.insert("1.0", result["text"])
        status.configure(text=f"{result['count']} address(es)"
                         + (f"; {len(result['missing'])} without a valid address"
                            if result["missing"] else ""))

    def copy():
        win.clipboard_clear()
        win.clipboard_append(out.get("1.0", "end-1c"))
        status.configure(text="Copied to the clipboard.")

    def save():
        path = filedialog.asksaveasfilename(parent=win, defaultextension=".txt",
                                            initialfile="email_list.txt")
        if path:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(out.get("1.0", "end-1c") + "\n")
            status.configure(text=f"Saved to {path}.")

    bar = ttk.Frame(body)
    bar.pack(fill=tk.X, pady=6)
    for label, command in (("Make list", make), ("Copy", copy), ("Save…", save)):
        ttk.Button(bar, text=label, command=command).pack(side=tk.LEFT, padx=2)
    out.pack(fill=tk.BOTH, expand=True)
    status.pack(anchor="w")
    make()


def followup_dialog(gui, ids=None):
    ids = ids or _ids_or_all(gui)
    if not ids:
        return
    ex = _extras()
    win = tk.Toplevel(gui.master)
    win.title("Mark for follow-up")
    body = ttk.Frame(win, padding=10)
    body.pack(fill=tk.BOTH, expand=True)
    ttk.Label(body, text=f"{len(ids)} student(s)").grid(row=0, column=1, sticky="w")
    reason = ttk.Entry(body, width=50)
    priority = ttk.Combobox(body, values=list(ex.PRIORITIES), state="readonly", width=12)
    priority.set("medium")
    due = ttk.Entry(body, width=14)
    assignee = ttk.Entry(body, width=24)
    for row, (label, widget) in enumerate((("Reason *", reason), ("Priority", priority),
                                           ("Due (YYYY-MM-DD)", due),
                                           ("Assign to (username)", assignee)), start=1):
        ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", pady=3)
        widget.grid(row=row, column=1, sticky="w", pady=3)

    def save():
        result = _call(win, ex.mark_followup, gui.viewer, ids, reason.get(), priority.get(),
                       due.get().strip() or None, assignee.get().strip() or None, write=True)
        if isinstance(result, dict):
            messagebox.showinfo(TITLE, f"{result['marked']} student(s) marked for follow-up.",
                                parent=win)
            win.destroy()
            if getattr(gui, "followups_tab", None):
                gui.followups_tab.load()

    ttk.Button(body, text="Mark", command=save).grid(row=6, column=1, sticky="w", pady=8)


def add_favourites(gui):
    ids = gui.selected_ids()
    if not ids:
        messagebox.showinfo(TITLE, "Select the students first.", parent=gui.master)
        return
    note = simpledialog.askstring(TITLE, "Note (optional):", parent=gui.master) or ""

    def add_all(conn):
        for sid in ids:
            _extras().add_favourite(conn, gui.viewer, sid, note)

    if _call(gui.master, add_all, write=True):
        messagebox.showinfo(TITLE, f"{len(ids)} added to your favourites.", parent=gui.master)
        if getattr(gui, "favourites_tab", None):
            gui.favourites_tab.load()


def student_performance(gui, student_id=None):
    student_id = student_id or (gui.selected_ids() or [None])[0]
    if not student_id:
        messagebox.showinfo(TITLE, "Select a student first.", parent=gui.master)
        return
    report = _call(gui.master, _reports().generate, "student_performance", {}, gui.viewer,
                   student_id=student_id, write=True)
    if isinstance(report, dict):
        ReportWindow(gui, report)


class ReportWindow:
    """A generated report: its text, and Export."""

    def __init__(self, gui, report):
        self.gui, self.report = gui, report
        win = _toplevel(gui.master, report["title"][:90], 960, 620)
        bar = ttk.Frame(win, padding=6)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        if gui.viewer.can_export:
            ttk.Button(bar, text="Export…", command=lambda: export_report(gui, report, win)).pack(
                side=tk.LEFT)
        ttk.Button(bar, text="Close", command=win.destroy).pack(side=tk.RIGHT)
        text = tk.Text(win, wrap="none", font=("Courier", 9))
        text.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        text.insert("1.0", report["text"])
        text.configure(state="disabled")


def export_report(gui, report, parent):
    target = _ask_path(parent, "report.csv", gui.viewer.role in _search().ADMIN_ROLES)
    if not target:
        return
    path, fmt, delimiter = target
    n = _call(parent, _reports().export, report, gui.viewer, path, fmt, delimiter, write=True)
    if n is not None:
        messagebox.showinfo(TITLE, f"Saved {n} row(s) to {path}.", parent=parent)


# ── tabs ────────────────────────────────────────────────────────────────


class ReportsTab:
    def __init__(self, gui, notebook):
        self.gui = gui
        rp = _reports()
        gui.reports_tab = self
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Reports")
        self.admin = gui.viewer.role in _search().ADMIN_ROLES
        names = {k: v for k, v in rp.REPORTS.items() if self.admin or k not in rp.ADMIN_REPORTS}
        self._names = {v: k for k, v in names.items()}
        top = ttk.Frame(tab, padding=6)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Report").pack(side=tk.LEFT)
        self.which = ttk.Combobox(top, values=list(names.values()), state="readonly", width=36)
        self.which.set(names["demographics"])
        self.which.pack(side=tk.LEFT, padx=4)
        self.scope = tk.StringVar(value="search")
        ttk.Radiobutton(top, text="current search's students", variable=self.scope,
                        value="search").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Radiobutton(top, text="everyone", variable=self.scope, value="all").pack(
            side=tk.LEFT)
        dims = _call(gui.master, rp.available_dimensions) or {}
        self._dims = {v: k for k, v in dims.items()}
        opts = ttk.Frame(tab, padding=(6, 0))
        opts.pack(fill=tk.X)
        ttk.Label(opts, text="Cross-tab rows").pack(side=tk.LEFT)
        self.row_dim = ttk.Combobox(opts, values=list(dims.values()), state="readonly", width=18)
        self.row_dim.set(dims.get("course", ""))
        self.row_dim.pack(side=tk.LEFT, padx=4)
        ttk.Label(opts, text="by").pack(side=tk.LEFT)
        self.col_dim = ttk.Combobox(opts, values=list(dims.values()), state="readonly", width=18)
        self.col_dim.set(dims.get("status", ""))
        self.col_dim.pack(side=tk.LEFT, padx=4)
        ttk.Label(opts, text="Student ID (one student's performance)").pack(side=tk.LEFT,
                                                                           padx=(12, 4))
        self.student = ttk.Entry(opts, width=14)
        self.student.pack(side=tk.LEFT)
        bar = ttk.Frame(tab, padding=6)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(bar, text="Run report", command=self.run).pack(side=tk.LEFT, padx=2)
        self.export_btn = ttk.Button(bar, text="Export…", command=self.export,
                                     state="disabled")
        if gui.viewer.can_export:
            self.export_btn.pack(side=tk.LEFT, padx=2)
        self.not_dup = ttk.Button(bar, text="Not a duplicate…",
                                  command=lambda: self.review("not_duplicate"))
        self.is_dup = ttk.Button(bar, text="Is a duplicate…",
                                 command=lambda: self.review("duplicate"))
        if self.admin:
            ttk.Button(bar, text="Optimise database", command=self.optimise).pack(
                side=tk.RIGHT, padx=2)
        ttk.Label(tab, padding=(6, 0), foreground="#555", wraplength=1100, text=(
            f"Counts under {rp.SUPPRESS} are shown as <{rp.SUPPRESS} so small groups cannot be "
            "identified. Trends and pass rates describe past students; nothing here predicts an "
            "individual.")).pack(anchor="w")
        self.tree_frame = ttk.Frame(tab)
        self.tree_frame.pack(fill=tk.BOTH, expand=True)
        self.tree = None
        self.report = None

    def _criteria(self):
        return self.gui.state["criteria"] if self.scope.get() == "search" else {}

    def select(self, name):
        """Choose report ``name`` (a REPORTS key) in the list."""
        for label, key in self._names.items():
            if key == name:
                self.which.set(label)
                return True
        return False

    def run(self):
        name = self._names.get(self.which.get())
        if not name:
            return
        options = {"row": self._dims.get(self.row_dim.get()),
                   "col": self._dims.get(self.col_dim.get()),
                   "student_id": self.student.get().strip() or
                   (self.gui.selected_ids() or [None])[0]}
        if name == "student_performance" and not options["student_id"]:
            messagebox.showinfo(TITLE, "Enter a student ID (or select a student on the Search "
                                       "tab).", parent=self.gui.master)
            return
        report = _call(self.gui.master, _reports().generate, name, self._criteria(),
                       self.gui.viewer, write=True, **options)
        if not isinstance(report, dict):
            return
        self.report = report
        self._show(report)
        self.export_btn.configure(state="normal")
        for button in (self.not_dup, self.is_dup):
            if name == "duplicates" and self.gui.viewer.can_update:
                button.pack(side=tk.LEFT, padx=2)
            else:
                button.pack_forget()

    def _show(self, report):
        for child in self.tree_frame.winfo_children():
            child.destroy()
        ttk.Label(self.tree_frame, text=report["title"], padding=(6, 4),
                  wraplength=1100).pack(anchor="w")
        cols = report["columns"]
        self.tree = _tree(self.tree_frame, [(f"c{i}", report["labels"][c])
                                            for i, c in enumerate(cols)],
                          [max(80, min(260, 9 * len(report["labels"][c]))) for c in cols],
                          height=16)
        for i, row in enumerate(report["rows"]):
            self.tree.insert("", "end", iid=str(i), values=[
                "" if row.get(c) is None else row.get(c) for c in cols])

    def export(self):
        if self.report:
            export_report(self.gui, self.report, self.gui.master)

    def review(self, decision):
        if not self.tree or not self.tree.selection():
            messagebox.showinfo(TITLE, "Select a pair first.", parent=self.gui.master)
            return
        row = self.report["rows"][int(self.tree.selection()[0])]
        note = simpledialog.askstring(TITLE, "Note (why):", parent=self.gui.master)
        if note is None:
            return
        if _call(self.gui.master, _reports().review_duplicate, self.gui.viewer,
                 row["student_a"], row["student_b"], decision, note, write=True):
            if decision == "duplicate":
                messagebox.showinfo(TITLE, "Recorded. Merge the records in Student Records "
                                    "(move anything needed, then withdraw or erase the "
                                    "duplicate).", parent=self.gui.master)
            self.run()

    def optimise(self):
        message = _call(self.gui.master, _reports().optimise, self.gui.viewer, write=True)
        if message:
            messagebox.showinfo(TITLE, message, parent=self.gui.master)


class FollowupsTab:
    def __init__(self, gui, notebook):
        self.gui = gui
        gui.followups_tab = self
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Follow-ups")
        top = ttk.Frame(tab, padding=6)
        top.pack(fill=tk.X)
        self.status = ttk.Combobox(top, values=("open", "done", "all"), state="readonly",
                                   width=8)
        self.status.set("open")
        self.status.pack(side=tk.LEFT)
        self.mine = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Mine only", variable=self.mine,
                        command=self.load).pack(side=tk.LEFT, padx=6)
        self.status.bind("<<ComboboxSelected>>", lambda _e: self.load())
        bar = ttk.Frame(tab, padding=6)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        for label, command in (("Refresh", self.load), ("Open student", self.open),
                               ("Close with outcome…", self.close)):
            ttk.Button(bar, text=label, command=command).pack(side=tk.LEFT, padx=2)
        self.tree = _tree(tab, [("id", "#"), ("student", "Student"), ("name", "Name"),
                                ("priority", "Priority"), ("due", "Due"), ("reason", "Reason"),
                                ("assigned", "Assigned to"), ("by", "Marked by"),
                                ("status", "Status"), ("outcome", "Outcome")],
                          [40, 90, 160, 70, 90, 260, 100, 90, 60, 220])
        self.rows = {}
        self.load()

    def load(self):
        status = None if self.status.get() == "all" else self.status.get()
        rows = _call(self.gui.master, _extras().followups, self.gui.viewer, status,
                     self.mine.get()) or []
        self.rows = {str(r["id"]): r for r in rows}
        self.tree.delete(*self.tree.get_children())
        for iid, r in self.rows.items():
            self.tree.insert("", "end", iid=iid, values=(
                r["id"], r["student_id"], r.get("name") or "", r["priority"], r["due_on"] or "",
                r["reason"], r["assigned_to"] or "", r["created_by"], r["status"],
                r["outcome"] or ""))

    def _picked(self):
        r = self.rows.get((self.tree.selection() or [""])[0])
        if not r:
            messagebox.showinfo(TITLE, "Select a follow-up first.", parent=self.gui.master)
        return r

    def open(self):
        r = self._picked()
        if r and self.gui.open_student:
            self.gui.open_student(r["student_id"])

    def close(self):
        r = self._picked()
        if not r:
            return
        outcome = simpledialog.askstring(TITLE, "What was done?", parent=self.gui.master)
        if outcome and _call(self.gui.master, _extras().close_followup, self.gui.viewer,
                             r["id"], outcome, write=True):
            self.load()


class FavouritesTab:
    def __init__(self, gui, notebook):
        self.gui = gui
        gui.favourites_tab = self
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Favourites")
        bar = ttk.Frame(tab, padding=6)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        for label, command in (("Refresh", self.load), ("Open student", self.open),
                               ("Performance…", self.performance),
                               ("Mark for follow-up…", self.followup),
                               ("Edit note…", self.note), ("Remove", self.remove)):
            ttk.Button(bar, text=label, command=command).pack(side=tk.LEFT, padx=2)
        self.tree = _tree(tab, [("id", "Student ID"), ("name", "Name"), ("course", "Course"),
                                ("status", "Status"), ("note", "Note"), ("added", "Added")],
                          [100, 180, 160, 100, 300, 140])
        self.tree.bind("<Double-1>", lambda _e: self.open())
        self.load()

    def load(self):
        rows = _call(self.gui.master, _extras().favourites, self.gui.viewer) or []
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            self.tree.insert("", "end", iid=r["student_id"], values=(
                r["student_id"], r["name"], r["course"] or "", r["status"] or "",
                r["note"] or "", r["added_at"]))

    def _picked(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(TITLE, "Select a student first.", parent=self.gui.master)
        return sel[0] if sel else None

    def open(self):
        sid = self._picked()
        if sid and self.gui.open_student:
            self.gui.open_student(sid)

    def performance(self):
        sid = self._picked()
        if sid:
            student_performance(self.gui, sid)

    def followup(self):
        sid = self._picked()
        if sid:
            followup_dialog(self.gui, [sid])

    def note(self):
        sid = self._picked()
        if not sid:
            return
        text = simpledialog.askstring(TITLE, "Note:", parent=self.gui.master)
        if text is not None and _call(self.gui.master, _extras().add_favourite,
                                      self.gui.viewer, sid, text, write=True):
            self.load()

    def remove(self):
        sid = self._picked()
        if sid and _call(self.gui.master, _extras().remove_favourite, self.gui.viewer, sid,
                         write=True):
            self.load()


class HistoryTab:
    def __init__(self, gui, notebook):
        self.gui = gui
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="My history")
        bar = ttk.Frame(tab, padding=6)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        for label, command in (("Refresh", self.load), ("Run again", self.again),
                               ("Save as a search…", self.save), ("Export…", self.export)):
            ttk.Button(bar, text=label, command=command).pack(side=tk.LEFT, padx=2)
        ttk.Label(tab, padding=6, foreground="#555", text=(
            "Your searches, exports, bulk actions and reports. They are part of the search "
            "audit, so they cannot be deleted.")).pack(anchor="w")
        self.tree = _tree(tab, [("at", "When"), ("what", "Action"), ("n", "Students"),
                                ("search", "Search"), ("detail", "Detail")],
                          [140, 70, 70, 420, 360])
        self.tree.bind("<Double-1>", lambda _e: self.again())
        self.rows = {}
        self.load()

    def load(self):
        rows = _call(self.gui.master, _extras().history, self.gui.viewer, 300) or []
        self.rows = {str(r["id"]): r for r in rows}
        self.tree.delete(*self.tree.get_children())
        for iid, r in self.rows.items():
            self.tree.insert("", "end", iid=iid, values=(
                r["at"], r["action"], "" if r["count"] is None else r["count"], r["search"],
                r["detail"]))

    def _criteria(self):
        r = self.rows.get((self.tree.selection() or [""])[0])
        if not r or not r["criteria"]:
            messagebox.showinfo(TITLE, "Select an entry that has a search.",
                                parent=self.gui.master)
            return None
        return r["criteria"]

    def again(self):
        criteria = self._criteria()
        if criteria is not None:
            self.gui.load_criteria(criteria)

    def save(self):
        criteria = self._criteria()
        if criteria is None:
            return
        name = simpledialog.askstring(TITLE, "Name for this search:", parent=self.gui.master)
        if name and _call(self.gui.master, _saved_save, self.gui.viewer, name, criteria,
                          write=True):
            self.gui._load_saved()

    def export(self):
        path = filedialog.asksaveasfilename(parent=self.gui.master, defaultextension=".csv",
                                            initialfile="my_search_history.csv")
        if not path:
            return
        te = _export_formats()
        rows = list(self.rows.values())
        columns = ["at", "action", "count", "search", "detail"]
        try:
            te.write(path, columns, rows, te.format_for(path), title="My search history",
                     labels={c: c.capitalize() for c in columns})
        except Exception as exc:
            messagebox.showerror(TITLE, f"Could not export: {exc}", parent=self.gui.master)
            return
        messagebox.showinfo(TITLE, f"Saved {len(rows)} entries to {path}.",
                            parent=self.gui.master)


def _saved_save(conn, viewer, name, criteria):
    from education_system.systems.university.application.students import (
        search_saved as student_search_saved,
    )
    return student_search_saved.save(conn, viewer, name, criteria)


# ── saved searches as files ─────────────────────────────────────────────


def export_saved(gui, saved_id, name):
    path = filedialog.asksaveasfilename(parent=gui.master, defaultextension=".json",
                                        initialfile=f"{name}.json",
                                        filetypes=[("Saved search", "*.json")])
    if path and _call(gui.master, _extras().export_saved, gui.viewer, saved_id, path):
        messagebox.showinfo(TITLE, f"Saved to {path}.", parent=gui.master)


def import_saved(gui):
    path = filedialog.askopenfilename(parent=gui.master, filetypes=[("Saved search", "*.json")])
    if not path:
        return
    shared = messagebox.askyesno(TITLE, "Share it with other staff?", parent=gui.master)
    if _call(gui.master, _extras().import_saved, gui.viewer, path, shared, write=True):
        gui._load_saved()
