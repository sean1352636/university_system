"""Batch Operations: the Dashboard, Update, Export, Automation and History
tabs, and the dialogs behind the menu bar (Open Database, Restore Backup,
Find Duplicates, Command Line Mode, Settings, About, the API server). The
window itself is ``batch_operations``; rules are in
``university/application`` (``batch_window`` and the other ``batch_*``)."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from education_system.systems.university.shell.gui.batch_operations import (
    SELECTIONS,
    TITLE,
    EXPORT_FORMATS,
    _app,
    _bar,
    _call,
    _guard,
    _header,
    _tree,
    option_cards,
)


def _text(parent, title, text, size="900x600"):
    from education_system.systems.university.shell.gui.batch_operations_extra import _text_window
    return _text_window(parent, title, text, size)


# ── Dashboard ───────────────────────────────────────────────────────────


class DashboardTab:
    def __init__(self, gui):
        self.gui, self.root = gui, gui.root
        self.frame = tab = ttk.Frame(gui.notebook)
        gui.notebook.add(tab, text="Dashboard")
        _header(tab, "Batch Operations Dashboard")
        top = ttk.Frame(tab, padding=(14, 0))
        top.pack(fill=tk.X)
        ttk.Label(top, text="Figures for the last").pack(side=tk.LEFT)
        self.days = ttk.Combobox(top, state="readonly", width=6, values=["7", "30", "90", "365"])
        self.days.set("30")
        self.days.pack(side=tk.LEFT, padx=4)
        ttk.Label(top, text="days").pack(side=tk.LEFT)
        self.days.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        for label, command in (("Refresh", self.refresh), ("New import…", gui.new_import),
                               ("Data quality check", lambda: gui.show_tab("Data Quality",
                                                                          "load")),
                               ("System status", lambda: gui.extra.system_status(gui))):
            ttk.Button(top, text=label, command=command).pack(side=tk.LEFT, padx=4)
        cards = ttk.Frame(tab, padding=(14, 8))
        cards.pack(fill=tk.X)
        self.figures = {}
        for i, (key, label) in enumerate((
                ("jobs", "Jobs run"), ("rows", "Rows processed"), ("succeeded", "Rows done"),
                ("failed", "Rows failed"), ("success_rate", "Success rate"),
                ("running", "Running now"), ("exports", "Exports"),
                ("scheduled", "Scheduled tasks"), ("db", "Database"))):
            box = ttk.LabelFrame(cards, text=label, padding=8)
            box.grid(row=i // 5, column=i % 5, padx=5, pady=5, sticky="nsew")
            self.figures[key] = ttk.Label(box, text="-", font=("Arial", 14, "bold"))
            self.figures[key].pack()
            cards.grid_columnconfigure(i % 5, weight=1)
        panes = ttk.Frame(tab)
        panes.pack(fill=tk.BOTH, expand=True, padx=8)
        left = ttk.LabelFrame(panes, text="Recent jobs", padding=4)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        right = ttk.LabelFrame(panes, text="Scheduled tasks", padding=4)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
        self.recent = _tree(left, [("id", "#"), ("kind", "Kind"), ("when", "Started"),
                                   ("by", "By"), ("status", "Status"), ("ok", "Done"),
                                   ("fail", "Failed")], [40, 80, 140, 80, 70, 50, 50])
        self.scheduled = _tree(right, [("what", "What"), ("when", "Runs"), ("next", "Next"),
                                       ("last", "Last")], [260, 100, 130, 130])

    def refresh(self):
        d = _call(self.root, _app("batch_window").dashboard, self.gui.viewer,
                  int(self.days.get()))
        if not isinstance(d, dict):
            return
        values = {"jobs": d["jobs"], "rows": d["rows"], "succeeded": d["succeeded"],
                  "failed": d["failed"],
                  "success_rate": "-" if d["success_rate"] is None else f"{d['success_rate']}%",
                  "running": d["running"], "exports": f"{d['exports']} ({d['rows_exported']} "
                                                       "rows)",
                  "scheduled": len(d["scheduled"]),
                  "db": f"{d['database']['size_mb']} MB"}
        for key, value in values.items():
            self.figures[key].configure(text=str(value))
        self.recent.delete(*self.recent.get_children())
        for j in d["recent"]:
            self.recent.insert("", "end", values=(j["id"], j["shown_kind"], j["started_at"],
                                                  j["actor"], j["status"], j["succeeded"],
                                                  j["failed"]))
        self.scheduled.delete(*self.scheduled.get_children())
        for t in d["scheduled"]:
            self.scheduled.insert("", "end", values=(t["what"], t["when"], t["next"] or "",
                                                     t["last"] or ""))


# ── Update ──────────────────────────────────────────────────────────────


class UpdateTab:
    """Batch Update (any bulk action, with a preview), Module Updates and
    Grade Updates."""

    def __init__(self, gui):
        self.gui, self.root = gui, gui.root
        self.frame = tab = ttk.Frame(gui.notebook)
        gui.notebook.add(tab, text="Update")
        _header(tab, "Update Operations")
        option_cards(tab, (
            ("Batch Update", "Update multiple records at once: choose the students and the "
                             "change below, preview it, then run it", self.batch_update),
            ("Module Updates", "Enrol on or withdraw from a module in batch (or import a "
                               "module enrolments file)", self.module_updates),
            ("Grade Updates", "Batch update student marks from a file, through the marking "
                              "rules", self.grade_updates)))
        bulk = _app("student_bulk_actions")
        form = ttk.LabelFrame(tab, text="Students and change", padding=8)
        form.pack(fill=tk.X, padx=20, pady=6)
        self.selection = ttk.Combobox(form, state="readonly", width=24, values=list(SELECTIONS))
        self.selection.set("Listed below")
        self.selection_value = ttk.Combobox(form, width=34)
        self.selection.bind("<<ComboboxSelected>>", lambda _e: self._selection_choices())
        self.ids_text = tk.Text(form, width=40, height=4)
        self.action = ttk.Combobox(form, values=list(bulk.ACTIONS.values()), state="readonly",
                                   width=34)
        self.action_value = ttk.Entry(form, width=36)
        self.action_value2 = ttk.Entry(form, width=36)
        self.action_reason = ttk.Entry(form, width=36)
        rows = (("Students", self.selection), ("Course / group / saved search",
                                                self.selection_value),
                ("Student IDs (for a list)", self.ids_text), ("Action", self.action),
                ("Value (course, module, field name or email subject)", self.action_value),
                ("New value / email message", self.action_value2), ("Reason *",
                                                                     self.action_reason))
        for r, (label, widget) in enumerate(rows):
            ttk.Label(form, text=label, wraplength=220).grid(row=r, column=0, sticky="nw",
                                                            pady=2)
            widget.grid(row=r, column=1, sticky="w", pady=2)
        ttk.Button(form, text="Load IDs from file…", command=self._load_ids).grid(
            row=2, column=2, sticky="nw", padx=4)
        ttk.Label(form, foreground="#555555", wraplength=380, text=(
            "Fields that can be set in bulk: " + ", ".join(bulk.SETTABLE) +
            ". Personal details stay one by one in Student Records.")).grid(
            row=4, column=2, rowspan=2, sticky="nw", padx=4)
        _bar(tab, (("Preview changes", self.preview), ("Run", self.run)), side=tk.TOP)
        self.note = ttk.Label(tab, padding=(20, 0), wraplength=1100)
        self.note.pack(anchor="w")
        self.tree = _tree(tab, [("sid", "Student"), ("name", "Name"), ("now", "Now"),
                                ("after", "After"), ("change", "Change")],
                          [100, 200, 220, 220, 100], height=8)

    def refresh(self):
        pass

    def batch_update(self):
        self.action.set(_app("student_bulk_actions").ACTIONS["set_field"])
        self.action_value.focus_set()

    def module_updates(self):
        if messagebox.askyesno(TITLE, "Do you have a file of module enrolments? (Yes = import "
                                      "the file; No = choose students and a module here)",
                               parent=self.root):
            self.gui.kind.set("Module enrolments")
            self.gui._load_mappings()
            self.gui.new_import()
            return
        self.action.set(_app("student_bulk_actions").ACTIONS["enrol_module"])
        self.action_value.focus_set()

    def grade_updates(self):
        self.gui.kind.set("Marks")
        self.gui._load_mappings()
        self.gui.new_import()

    def _selection_choices(self):
        how = SELECTIONS[self.selection.get()]
        values = []
        if how == "group":
            values = list(_app("student_search_saved").PRESETS)
        elif how == "saved":
            values = [f"{s['id']}: {s['name']}" for s in
                      _call(self.root, _app("student_search_saved").saved, self.gui.viewer) or []]
        elif how == "course":
            values = _call(self.root, _app("student_search").choices, "course") or []
        self.selection_value.configure(values=values)
        self.selection_value.set(values[0] if values else "")

    def _chosen_students(self):
        how = SELECTIONS[self.selection.get()]
        if how == "list":
            value = self.ids_text.get("1.0", tk.END)
        elif how == "saved":
            value = self.selection_value.get().split(":", 1)[0]
        else:
            value = self.selection_value.get().strip()
        return _call(self.root, _app("batch_exports").select_students, self.gui.viewer, how,
                     value)

    def _load_ids(self):
        path = filedialog.askopenfilename(parent=self.root)
        loaded = path and _guard(self.root, _app("batch_imports").read_and_map, path, "actions")
        if loaded:
            self.ids_text.delete("1.0", tk.END)
            self.ids_text.insert("1.0", "\n".join(r["student_id"] for r in loaded[0]))
            self.selection.set("Listed below")

    def _action(self):
        bulk = _app("student_bulk_actions")
        key = {v: k for k, v in bulk.ACTIONS.items()}.get(self.action.get())
        first, second = self.action_value.get().strip(), self.action_value2.get().strip()
        value = {"set_field": (first, second), "email": second}.get(key, first or None)
        return key, value, first

    def preview(self):
        key, value, _first = self._action()
        ids = self._chosen_students()
        if ids is None:
            return
        if not key or not ids:
            messagebox.showinfo(TITLE, "Choose the students and the action.", parent=self.root)
            return
        rows = _call(self.root, _app("batch_window").preview_actions, self.gui.viewer, ids, key,
                     value)
        if not isinstance(rows, list):
            return
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(rows):
            self.tree.insert("", "end", iid=str(i), values=(r["student_id"], r["name"], r["now"],
                                                            r["after"], r["change"]))
        changes = sum(1 for r in rows if r["change"] == "will change")
        self.note.configure(text=f"Preview - nothing saved. {len(rows)} student(s): {changes} "
                                 "will change.")

    def run(self):
        key, value, first = self._action()
        ids = self._chosen_students()
        if ids is None:
            return
        if not key or not ids:
            messagebox.showinfo(TITLE, "Choose an action and the students.", parent=self.root)
            return
        if not messagebox.askyesno(TITLE, f"{self.action.get()} for {len(ids)} student(s)? "
                                          "Preview changes first if you have not.",
                                   parent=self.root):
            return
        reason = self.action_reason.get()
        source = f"{self.selection.get().lower()}: {self.selection_value.get() or 'list'}"

        def work():
            return _app("batch_imports").run_actions(
                [{"student_id": i} for i in ids], self.gui.viewer, key, value=value,
                reason=reason, subject=first if key == "email" else "", source=source)

        def done(result):
            failed = "; ".join(f"{sid}: {why}" for sid, why in result["failed"][:20])
            self.note.configure(text=f"Job #{result['job_id']}: {result['done']} done, "
                                     f"{len(result['failed'])} failed. {failed}")
        self.gui.run_job(f"{self.action.get()} for {len(ids)} student(s)", work, done)


# ── Export ──────────────────────────────────────────────────────────────


class ExportTab:
    def __init__(self, gui):
        self.gui, self.root = gui, gui.root
        self.frame = tab = ttk.Frame(gui.notebook)
        gui.notebook.add(tab, text="Export")
        _header(tab, "Export Operations")
        option_cards(tab, (
            ("Export Students", "Export student records to CSV / Excel / JSON with the options "
                                "below", self.export),
            ("Export Statistics", "Export enrolment statistics and counts (no individuals)",
             self.statistics),
            ("Export Reports", "Generate and export batch reports (success, errors, "
                               "performance, comprehensive)",
             lambda: gui.extra.ReportsDialog(gui))))
        form = ttk.LabelFrame(tab, text="Export options", padding=8)
        form.pack(fill=tk.X, padx=20, pady=6)
        saved = _call(self.root, _app("student_search_saved").saved, gui.viewer) or []
        self._saved = {f"Saved: {s['name']}": s["id"] for s in saved}
        self.group = ttk.Combobox(form, state="readonly", width=40, values=list(
            _app("student_search_saved").PRESETS) + ["All students"] + list(self._saved))
        self.group.set("Current students")
        self.format = ttk.Combobox(form, state="readonly", width=16, values=list(EXPORT_FORMATS))
        self.format.set("CSV")
        self.course = ttk.Combobox(form, width=20, values=_call(
            self.root, _app("student_search").choices, "course") or [])
        self.date_from = ttk.Entry(form, width=14)
        self.date_to = ttk.Entry(form, width=14)
        self.modules = tk.BooleanVar(value=False)
        for r, (label, widget) in enumerate((
                ("Students", self.group), ("Format", self.format),
                ("Only course (optional)", self.course),
                ("Registered from (YYYY-MM-DD)", self.date_from),
                ("Registered to (YYYY-MM-DD)", self.date_to))):
            ttk.Label(form, text=label).grid(row=r, column=0, sticky="w", pady=2)
            widget.grid(row=r, column=1, sticky="w", pady=2)
        ttk.Checkbutton(form, text="Include the modules each student is enrolled on",
                        variable=self.modules).grid(row=5, column=1, sticky="w")
        ttk.Label(form, foreground="#555555", wraplength=520, text=(
            "Exports only the columns you are allowed to see, never erased records, and every "
            "export is recorded (History, Exports). For a precise list, use Advanced Search and "
            "save it; it then appears under Students.")).grid(row=0, column=2, rowspan=4,
                                                             sticky="nw", padx=10)
        buttons = [("Export…", self.export), ("Enrolment statistics…", self.statistics)]
        if gui.viewer.role in _app("batch_exports").ADMIN_ROLES:
            buttons += [("Send to another database…", lambda: send_to_database(gui, self)),
                        ("Send to an endpoint…", lambda: send_to_endpoint(gui, self))]
        _bar(tab, buttons, side=tk.TOP)
        self.note = ttk.Label(tab, padding=(20, 4), wraplength=1100)
        self.note.pack(anchor="w")

    def refresh(self):
        pass

    def options(self):
        group = self.group.get()
        return {"group": None if group in self._saved else group,
                "saved_id": self._saved.get(group), "course": self.course.get().strip() or None,
                "include_modules": self.modules.get()}

    def export(self):
        fmt = EXPORT_FORMATS[self.format.get()]
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=f".{fmt}",
                                            filetypes=[(self.format.get(), f"*.{fmt}")])
        if not path:
            return
        n = _call(self.root, _app("batch_exports").export_students, self.gui.viewer, path,
                  fmt=fmt, date_from=self.date_from.get().strip() or None,
                  date_to=self.date_to.get().strip() or None, write=True, **self.options())
        if n is not None:
            self.note.configure(text=f"Exported {n} student(s) to {path}.")
            self.gui.refresh_jobs()

    def statistics(self):
        report = _call(self.root, _app("batch_reports").enrolment_statistics, self.gui.viewer)
        if isinstance(report, dict):
            self.gui.extra.show_report(self.root, report)


def send_to_database(gui, export_tab=None):
    from education_system.systems.university.shell.gui.batch_operations_extra import ask_database
    config = ask_database(gui.root)
    if not config:
        return
    table, replace = config.pop("table"), config.pop("replace")
    if not messagebox.askyesno(TITLE, "Copy the chosen students' data to another database? Only "
                                      "do this where a data sharing agreement allows it.",
                               parent=gui.root):
        return
    options = export_tab.options() if export_tab else {"group": "Current students"}
    n = _call(gui.root, _app("batch_exports").export_to_database, gui.viewer, config,
              table=table, replace=replace, write=True, **options)
    if n is not None:
        messagebox.showinfo(TITLE, f"{n} row(s) written to {table}.", parent=gui.root)
        gui.tabs["Automation"].log(f"External database: {n} row(s) written to {table}")


def send_to_endpoint(gui, export_tab=None, url=None, token=None):
    url = url or simpledialog.askstring(TITLE, "HTTPS address that receives the students "
                                               "(JSON):", parent=gui.root)
    if not url:
        return
    if token is None:
        token = simpledialog.askstring(TITLE, "Bearer token (leave blank if none):",
                                       parent=gui.root, show="*")
    if not messagebox.askyesno(TITLE, f"Send the chosen students' data to {url}? Only do this "
                                      "where a data sharing agreement allows it.",
                               parent=gui.root):
        return
    options = export_tab.options() if export_tab else {"group": "Current students"}
    result = _call(gui.root, _app("batch_exports").push_to_endpoint, gui.viewer, url,
                   token=token or None, write=True, **options)
    if isinstance(result, dict):
        messagebox.showinfo(TITLE, f"{result['sent']} student(s) sent (HTTP {result['status']}).",
                            parent=gui.root)
        gui.tabs["Automation"].log(f"REST push: {result['sent']} student(s) to {url} "
                                   f"(HTTP {result['status']})")


# ── Automation ──────────────────────────────────────────────────────────


class AutomationTab:
    """Scheduled tasks (watched folders with a daily time, e-mailed reports)
    and API integration (the unified API server, another database, a REST
    endpoint)."""

    def __init__(self, gui):
        self.gui, self.root = gui, gui.root
        self.frame = tab = ttk.Frame(gui.notebook)
        gui.notebook.add(tab, text="Automation")
        _header(tab, "Automation & Integration")
        top = ttk.Frame(tab, padding=(14, 0))
        top.pack(fill=tk.X)
        left = ttk.LabelFrame(top, text="Scheduled Tasks", padding=8)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        right = ttk.LabelFrame(top, text="API Integration", padding=8)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        for label, command in (("Schedule Daily (watched folder import)", self.schedule_daily),
                               ("Schedule Weekly (e-mailed report)", self.schedule_weekly),
                               ("View Scheduled Tasks", self.view_scheduled),
                               ("Run anything due now", self.run_now)):
            ttk.Button(left, text=label, command=command).pack(fill=tk.X, pady=3)
        admin = gui.is_admin
        for label, command in (("Start API Server", lambda: ApiServerDialog(gui)),
                               ("External Database", lambda: send_to_database(gui)),
                               ("REST API Setup", lambda: RestSetupDialog(gui))):
            ttk.Button(right, text=label, command=command,
                       state="normal" if admin else "disabled").pack(fill=tk.X, pady=3)
        if not admin:
            ttk.Label(right, text="Administrators only.", foreground="#777777").pack()
        book = ttk.Notebook(tab)
        book.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        watch = ttk.Frame(book)
        book.add(watch, text="Watched folders")
        ttk.Label(watch, padding=6, wraplength=1100, text=(
            "New files in a watched folder are imported when anyone opens Batch Operations or "
            "presses Run now, and every day at its set time by the background scheduler, then "
            "moved to its processed/ or failed/ sub-folder.")).pack(anchor="w")
        _bar(watch, (("Add…", self.add_watch), ("Set daily time…", self.watch_time),
                     ("Pause / resume", self.pause_watch), ("Remove", self.remove_watch),
                     ("Run now", self.run_watch)))
        self.watch_tree = _tree(watch, [("id", "#"), ("kind", "Imports"), ("folder", "Folder"),
                                        ("mode", "Mode"), ("owner", "Owner"), ("on", "Active"),
                                        ("at", "Daily at"), ("last", "Last run")],
                                [40, 70, 320, 70, 80, 60, 70, 280], height=6)
        tasks = ttk.Frame(book)
        book.add(tasks, text="All scheduled tasks")
        _bar(tasks, (("Add scheduled report…", self.schedule_weekly),
                     ("Pause / resume report", self.toggle_report),
                     ("Remove report", self.remove_report), ("Refresh", self.refresh)))
        self.task_tree = _tree(tasks, [("type", "What"), ("id", "#"), ("what", "Details"),
                                       ("when", "Runs"), ("next", "Next"), ("last", "Last"),
                                       ("owner", "Owner")], [100, 40, 400, 100, 130, 140, 90],
                               height=6)
        self.book, self.tasks_frame = book, tasks
        status = ttk.LabelFrame(tab, text="Automation status", padding=4)
        status.pack(fill=tk.X, padx=8, pady=(0, 6))
        self.status = tk.Text(status, height=5, wrap="word", font=("Courier", 9))
        self.status.pack(fill=tk.X)
        self.refresh()
        self._show_scheduler()

    def log(self, line):
        from datetime import datetime
        self.status.configure(state="normal")
        self.status.insert(tk.END, f"{datetime.now():%H:%M:%S}  {line}\n")
        self.status.see(tk.END)
        self.status.configure(state="disabled")

    def _show_scheduler(self):
        try:
            from education_system.systems.university.infrastructure.batch import scheduler
            running = getattr(scheduler, "_THREAD", None) or getattr(scheduler, "_WORKER", None)
            alive = bool(running and running.is_alive())
        except Exception:
            alive = False
        self.log("Background scheduler: " + ("running (checks every minute)" if alive else
                                             "not running in this process; tasks run when the "
                                             "university system is started, or press Run "
                                             "anything due now"))

    def refresh(self):
        self.watch_tree.delete(*self.watch_tree.get_children())
        for w in _call(self.root, _app("batch_jobs").watches, self.gui.viewer) or []:
            self.watch_tree.insert("", "end", iid=str(w["id"]), values=(
                w["id"], w["kind"], w["folder"], w["mode"], w["owner"],
                "yes" if w["active"] else "paused", w.get("run_at") or "manual",
                f"{w['last_run_at'] or ''} {w['last_result'] or ''}".strip()))
        self.task_tree.delete(*self.task_tree.get_children())
        for t in _call(self.root, _app("batch_schedule").scheduled_tasks, self.gui.viewer) or []:
            self.task_tree.insert("", "end", iid=f"{t['type']}:{t['id']}", values=(
                t["type"], t["id"], t["what"], t["when"], t["next"], t["last"] or "",
                t["owner"]))

    def view_scheduled(self):
        self.refresh()
        self.book.select(self.tasks_frame)

    def schedule_daily(self):
        folder = filedialog.askdirectory(parent=self.root, title="Folder to import from daily")
        if not folder:
            return
        kind = "marks" if messagebox.askyesno(TITLE, "Does this folder hold marks? (No = "
                                              "students)", parent=self.root) else "students"
        reason = simpledialog.askstring(TITLE, "Reason recorded on each imported change:",
                                        parent=self.root)
        if not reason:
            return
        at = simpledialog.askstring(TITLE, "Import every day at (HH:MM, 24-hour):",
                                    parent=self.root, initialvalue="02:00")
        if not at:
            return
        watch_id = _call(self.root, _app("batch_jobs").add_watch, self.gui.viewer, kind, folder,
                         reason, write=True)
        if watch_id and _call(self.root, _app("batch_schedule").set_watch_time, self.gui.viewer,
                              watch_id, at, write=True):
            self.log(f"Daily import of {kind} from {folder} at {at}")
            self.refresh()

    def schedule_weekly(self):
        from education_system.systems.university.shell.gui.batch_operations_extra import (
            REPORTS,
        )
        win = tk.Toplevel(self.root)
        win.title("Scheduled report")
        win.transient(self.root.winfo_toplevel())
        body = ttk.Frame(win, padding=10)
        body.pack(fill=tk.BOTH, expand=True)
        report = ttk.Combobox(body, state="readonly", values=list(REPORTS), width=36)
        report.set("Success rates")
        frequency = ttk.Combobox(body, state="readonly", values=["daily", "weekly", "monthly"],
                                 width=12)
        frequency.set("weekly")
        recipients = ttk.Entry(body, width=50)
        for r, (label, widget) in enumerate((("Report", report), ("How often", frequency),
                                             ("E-mail to (comma-separated)", recipients))):
            ttk.Label(body, text=label).grid(row=r, column=0, sticky="w", pady=2)
            widget.grid(row=r, column=1, sticky="w", pady=2)

        def save():
            if _call(win, _app("batch_schedule").add_report_schedule, self.gui.viewer,
                     REPORTS[report.get()], frequency.get(), recipients.get(), write=True):
                self.log(f"{frequency.get().title()} report: {report.get()} to "
                         f"{recipients.get()}")
                win.destroy()
                self.refresh()
        ttk.Button(body, text="Save", command=save).grid(row=4, column=1, sticky="w", pady=8)

    def _picked_report(self):
        sel = self.task_tree.selection()
        if not sel or not sel[0].startswith("report:"):
            messagebox.showinfo(TITLE, "Select a scheduled report.", parent=self.root)
            return None
        return int(sel[0].split(":", 1)[1])

    def toggle_report(self):
        sid = self._picked_report()
        rows = {r["id"]: r for r in _call(self.root, _app("batch_schedule").report_schedules,
                                          self.gui.viewer) or []} if sid else {}
        if sid in rows and _call(self.root, _app("batch_schedule").set_report_active,
                                 self.gui.viewer, sid, not rows[sid]["active"], write=True):
            self.refresh()

    def remove_report(self):
        sid = self._picked_report()
        if sid and messagebox.askyesno(TITLE, "Remove this scheduled report?", parent=self.root) \
                and _call(self.root, _app("batch_schedule").remove_report_schedule,
                          self.gui.viewer, sid, write=True):
            self.refresh()

    def run_now(self):
        from education_system.systems.university.infrastructure.batch import scheduler
        report = _guard(self.root, scheduler.run_once)
        if isinstance(report, dict):
            watches = report.get("watches") or []
            self.log(f"Ran due tasks: {len(watches)} watched folder(s), "
                     f"{report.get('reports') or 0} report e-mail(s)")
            self.refresh()
            self.gui.refresh_jobs()

    def _picked_watch(self):
        sel = self.watch_tree.selection()
        if not sel:
            messagebox.showinfo(TITLE, "Select a watched folder first.", parent=self.root)
        return int(sel[0]) if sel else None

    def add_watch(self):
        folder = filedialog.askdirectory(parent=self.root)
        if not folder:
            return
        kind = "marks" if messagebox.askyesno(TITLE, "Does this folder hold marks? (No = "
                                              "students)", parent=self.root) else "students"
        reason = simpledialog.askstring(TITLE, "Reason recorded on each imported change:",
                                        parent=self.root)
        if reason and _call(self.root, _app("batch_jobs").add_watch, self.gui.viewer, kind,
                            folder, reason, write=True):
            self.log(f"Watching {folder} for {kind}")
            self.refresh()

    def watch_time(self):
        wid = self._picked_watch()
        if not wid:
            return
        at = simpledialog.askstring(TITLE, "Import every day at (HH:MM, 24-hour; blank = only "
                                           "when someone presses Run):", parent=self.root)
        if at is not None and _call(self.root, _app("batch_schedule").set_watch_time,
                                    self.gui.viewer, wid, at, write=True):
            self.refresh()

    def pause_watch(self):
        wid = self._picked_watch()
        rows = {str(w["id"]): w for w in _call(self.root, _app("batch_jobs").watches,
                                               self.gui.viewer) or []}
        if wid and str(wid) in rows and _call(self.root, _app("batch_jobs").set_watch_active,
                                              self.gui.viewer, wid,
                                              not rows[str(wid)]["active"], write=True):
            self.refresh()

    def remove_watch(self):
        wid = self._picked_watch()
        if wid and messagebox.askyesno(TITLE, "Stop watching this folder?", parent=self.root) \
                and _call(self.root, _app("batch_jobs").remove_watch, self.gui.viewer, wid,
                          write=True):
            self.refresh()

    def run_watch(self):
        result = _guard(self.root, _app("batch_imports").run_watch_folders)
        if isinstance(result, dict):
            lines = [f"#{w}: {r}" for w, r in result["watches"]]
            for line in lines:
                self.log(f"Watched folder {line}")
            messagebox.showinfo(TITLE, "\n".join(lines) or "No active watched folders.",
                                parent=self.root)
            self.refresh()
            self.gui.refresh_jobs()


class ApiServerDialog:
    """The unified REST API: Configuration, Security and Monitoring, with
    Start / Stop for a server started from here."""

    def __init__(self, gui):
        from education_system.systems.university.infrastructure.batch import api_server
        self.api, self.gui = api_server, gui
        self.win = win = tk.Toplevel(gui.root)
        win.title("API Server Configuration & Management")
        win.geometry("900x620")
        bar = ttk.Frame(win, padding=(8, 4))
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        for label, command in (("Start Server", self.start), ("Stop Server", self.stop),
                               ("Refresh", self.refresh), ("Close", win.destroy)):
            ttk.Button(bar, text=label, command=command).pack(side=tk.LEFT, padx=2)
        book = ttk.Notebook(win)
        book.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        config, security, monitor = (ttk.Frame(book, padding=8) for _ in range(3))
        book.add(config, text="Configuration")
        book.add(security, text="Security")
        book.add(monitor, text="Monitoring")
        server = ttk.LabelFrame(config, text="Server Configuration", padding=8)
        server.pack(fill=tk.X)
        self.config_label = ttk.Label(server, justify="left", font=("Courier", 10))
        self.config_label.pack(anchor="w")
        ttk.Label(server, foreground="#555555", wraplength=820, text=(
            "Host and port come from API_HOST / API_PORT, CORS from API_CORS_ORIGINS and the "
            "default rate limit from API_DEFAULT_RATE_LIMIT, set in the environment before "
            "starting.")).pack(anchor="w", pady=(4, 0))
        endpoints = ttk.LabelFrame(config, text="API Endpoints", padding=4)
        endpoints.pack(fill=tk.BOTH, expand=True, pady=6)
        ttk.Button(endpoints, text="List the endpoints", command=self.list_endpoints).pack(
            side=tk.BOTTOM, anchor="w")
        self.endpoint_tree = _tree(endpoints, [("rule", "Route"), ("methods", "Methods")],
                                   [600, 160], height=10)
        auth = ttk.LabelFrame(security, text="Authentication, rate limiting and other "
                                             "protections", padding=8)
        auth.pack(fill=tk.BOTH, expand=True)
        for name, what in api_server.security():
            row = ttk.Frame(auth)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=name, width=20, font=("Arial", 10, "bold")).pack(side=tk.LEFT)
            ttk.Label(row, text=what, wraplength=640).pack(side=tk.LEFT)
        status = ttk.LabelFrame(monitor, text="Current Server Status", padding=8)
        status.pack(fill=tk.X)
        self.status_label = ttk.Label(status, justify="left", font=("Courier", 10))
        self.status_label.pack(anchor="w")
        logs = ttk.LabelFrame(monitor, text="Server Logs", padding=4)
        logs.pack(fill=tk.BOTH, expand=True, pady=6)
        self.log_text = tk.Text(logs, wrap="none", font=("Courier", 9), height=14)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.refresh()

    def refresh(self):
        s = self.api.status()
        self.config_label.configure(text=(
            f"Host:        {s['host']}\nPort:        {s['port']}\nEnvironment: {s['environment']}"
            f"\nDebug:       {s['debug']}\nCommand:     {s['command']}"))
        health = self.api.health() if s["listening"] else None
        self.status_label.configure(text=(
            f"State:   {s['state']}\nAddress: {s['url']}\nHealth:  "
            f"{health.get('status', 'ok') if isinstance(health, dict) else 'not reachable'}"))
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert("1.0", self.api.log_tail())
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def start(self):
        if _guard(self.win, self.api.start) is not None:
            self.gui.tabs["Automation"].log("API server starting")
            self.win.after(3000, self.refresh)

    def stop(self):
        if _guard(self.win, self.api.stop) is not None:
            self.gui.tabs["Automation"].log("API server stopped")
            self.refresh()

    def list_endpoints(self):
        from education_system.systems.university.shell.gui.batch_operations import Progress

        def done(rows):
            self.endpoint_tree.delete(*self.endpoint_tree.get_children())
            for rule, methods in rows:
                self.endpoint_tree.insert("", "end", values=(rule, methods))
        Progress(self.gui, "Reading the API's routes", self.api.endpoints, done)


class RestSetupDialog:
    """Send students to another system's HTTPS endpoint: address, token,
    a connection test, then the send."""

    def __init__(self, gui):
        self.gui = gui
        self.win = win = tk.Toplevel(gui.root)
        win.title("REST API Setup")
        win.transient(gui.root.winfo_toplevel())
        body = ttk.Frame(win, padding=10)
        body.pack(fill=tk.BOTH, expand=True)
        self.url = ttk.Entry(body, width=60)
        self.token = ttk.Entry(body, width=60, show="*")
        for r, (label, widget) in enumerate((("Base URL (https)", self.url),
                                             ("API key / bearer token", self.token))):
            ttk.Label(body, text=label).grid(row=r, column=0, sticky="w", pady=2)
            widget.grid(row=r, column=1, sticky="w", pady=2)
        ttk.Label(body, foreground="#555555", wraplength=520, text=(
            "Nothing here is stored. The students sent are the Export tab's current choice "
            "(Current students by default).")).grid(row=2, column=0, columnspan=2, sticky="w")
        bar = ttk.Frame(body)
        bar.grid(row=3, column=1, sticky="w", pady=8)
        ttk.Button(bar, text="Test Connection", command=self.test).pack(side=tk.LEFT)
        ttk.Button(bar, text="Send students", command=self.send).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Close", command=win.destroy).pack(side=tk.LEFT)

    def test(self):
        import urllib.request
        url = self.url.get().strip()
        if not url.lower().startswith("https://"):
            messagebox.showerror(TITLE, "Only https:// addresses are allowed.", parent=self.win)
            return
        request = urllib.request.Request(url, method="HEAD")
        if self.token.get().strip():
            request.add_header("Authorization", f"Bearer {self.token.get().strip()}")
        try:
            with urllib.request.urlopen(request, timeout=8) as response:  # nosec B310 - https only
                messagebox.showinfo(TITLE, f"Reached {url}: HTTP {response.status}.",
                                    parent=self.win)
        except Exception as exc:
            code = getattr(exc, "code", None)
            messagebox.showinfo(TITLE, f"{url} answered HTTP {code}." if code else
                                f"Could not reach {url}: {exc}", parent=self.win)

    def send(self):
        tab = self.gui.tabs.get("Export")
        send_to_endpoint(self.gui, tab, url=self.url.get().strip(),
                         token=self.token.get().strip())


# ── History ─────────────────────────────────────────────────────────────


class HistoryTab:
    def __init__(self, gui):
        self.gui, self.root = gui, gui.root
        self.frame = tab = ttk.Frame(gui.notebook)
        gui.notebook.add(tab, text="History")
        _header(tab, "Operation History")
        control = ttk.Frame(tab, padding=(20, 0))
        control.pack(fill=tk.X)
        window = _app("batch_window")
        ttk.Label(control, text="Filter by:").pack(side=tk.LEFT)
        self.filter = ttk.Combobox(control, state="readonly", width=12,
                                   values=list(window.HISTORY_FILTERS))
        self.filter.set("All")
        self.filter.pack(side=tk.LEFT, padx=4)
        self.filter.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Label(control, text="Last days:").pack(side=tk.LEFT, padx=(8, 0))
        self.days = ttk.Entry(control, width=6)
        default_days = _call(self.root, window.setting, "history_days")
        self.days.insert(0, default_days if isinstance(default_days, str) else "90")
        self.days.pack(side=tk.LEFT, padx=4)
        for label, command in (("Refresh", self.refresh), ("Export History", self.export),
                               ("Clear History", self.clear)):
            ttk.Button(control, text=label, command=command).pack(side=tk.LEFT, padx=4)
        _bar(tab, (("Details…", self.details), ("Save errors…", self.errors),
                   ("Undo…", self.undo), ("Resume interrupted…", gui._resume)))
        self.tree = _tree(tab, [("when", "Date/Time"), ("operation", "Operation"),
                                ("records", "Records"), ("success", "Success"),
                                ("errors", "Errors"), ("by", "By"), ("detail", "Details")],
                          [150, 300, 70, 70, 60, 90, 420], height=16)
        self._rows = []
        self._since = None

    def _days(self):
        text = self.days.get().strip()
        return int(text) if text.isdigit() and int(text) > 0 else None

    def refresh(self):
        rows = _call(self.root, _app("batch_window").history, self.filter.get(),
                     self._days()) or []
        if self._since:
            rows = [r for r in rows if str(r["when"] or "") >= self._since]
        self._rows = rows
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            self.tree.insert("", "end", iid=r["key"], values=(
                r["when"], r["operation"], r["records"], r["success"], r["errors"], r["by"],
                r["detail"]))

    def export(self):
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".csv",
                                            initialfile="batch_history.csv")
        if path:
            n = _guard(self.root, _app("batch_window").export_history_rows, self._rows, path)
            if n is not None:
                messagebox.showinfo(TITLE, f"{n} entr{'y' if n == 1 else 'ies'} saved to "
                                           f"{path}.", parent=self.root)

    def clear(self):
        """The history is the audit trail and what Undo works from, so it is
        never deleted; clearing empties this view from now on."""
        from datetime import datetime
        if messagebox.askyesno(TITLE, "Jobs and exports are kept: they are the audit trail and "
                                      "what Undo works from. Clear this view, showing only what "
                                      "happens from now on? (Refresh with a number of days to "
                                      "see older entries again.)", parent=self.root):
            self._since = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.refresh()
            self._since = None

    def _job_id(self):
        sel = self.tree.selection()
        if not sel or not sel[0].startswith("job:"):
            messagebox.showinfo(TITLE, "Select a job (exports have no rows to show or undo).",
                                parent=self.root)
            return None
        return int(sel[0].split(":", 1)[1])

    def details(self):
        job_id = self._job_id()
        j = job_id and _call(self.root, _app("batch_jobs").job, job_id)
        if not isinstance(j, dict):
            return
        win = tk.Toplevel(self.root)
        win.title(f"Job #{job_id}")
        win.geometry("900x480")
        view = _tree(win, [("row", "Row"), ("ref", "Record"), ("outcome", "Result"),
                           ("message", "Details")], [50, 120, 90, 600], height=18)
        for i, r in enumerate(j["rows"]):
            view.insert("", "end", iid=str(i), values=(r["row_no"], r["ref"] or "",
                                                       r["outcome"], r["message"] or ""))

    def errors(self):
        job_id = self._job_id()
        if not job_id:
            return
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".csv",
                                            initialfile=f"job_{job_id}_errors.csv")
        if path:
            n = _call(self.root, _app("batch_jobs").error_report, job_id, path)
            if n is not None:
                messagebox.showinfo(TITLE, f"{n} row(s) saved to {path}.", parent=self.root)

    def undo(self, job_id=None):
        job_id = job_id or self._job_id()
        if not job_id:
            return
        reason = simpledialog.askstring(TITLE, f"Why is job #{job_id} being undone?",
                                        parent=self.root)
        if not reason:
            return

        def done(result):
            failed = "\n".join(f"row {r}: {why}" for r, why in result["failed"][:20])
            messagebox.showinfo(TITLE, f"{result['undone']} row(s) undone." +
                                (f"\n\nNot undone:\n{failed}" if failed else ""),
                                parent=self.root)
        self.gui.run_job(f"Undoing job #{job_id}",
                         lambda: {**_app("batch_jobs").undo(job_id, self.gui.viewer, reason),
                                  "job_id": job_id}, done)


# ── dialogs behind the menu bar ─────────────────────────────────────────


def database_dialog(gui):
    """File → Open Database: the database Batch Operations works on. It
    cannot be switched while the university system is running; this shows
    which it is and checks it."""
    window = _app("batch_window")
    info = _call(gui.root, window.database_info)
    if not isinstance(info, dict):
        return
    counts = "\n".join(f"  {k:<22} {'-' if v is None else v}" for k, v in info["counts"].items())
    text = (f"Batch Operations always works on the university database:\n\n"
            f"  Path          {info['path']}\n  Size          {info['size_mb']} MB "
            f"({info['free_mb']} MB free pages)\n  Last changed  {info['modified']}\n"
            f"  Journal mode  {info['journal_mode']}\n  Tables        {info['tables']}\n\n"
            f"Rows:\n{counts}\n\nSwitching to another database file while the system is running "
            "would split records between files, so it is not offered. To work on another copy, "
            "start the system with that database configured.")
    win, bar = _text(gui.root, "Database", text, "760x480")

    def check():
        found = _call(win, window.integrity_check)
        if isinstance(found, list):
            messagebox.showinfo(TITLE, "Integrity check: " + ("ok" if found == ["ok"] else
                                                               "\n".join(found[:20])),
                                parent=win)
    ttk.Button(bar, text="Check integrity", command=check).pack(side=tk.LEFT)


def restore_backup(gui):
    """File → Restore Backup: the backup system's own restore dialog."""
    if not gui.is_admin:
        messagebox.showinfo(TITLE, "Restoring a backup is for administrators.", parent=gui.root)
        return
    from education_system.systems.university.shell.gui.database.dialogs.restore import (
        RestoreDialog,
    )
    RestoreDialog(gui.root)


def command_line_mode(gui):
    """Tools → Command Line Mode: open the batch menu in a terminal, or show
    the command when no terminal can be opened."""
    import shutil
    import subprocess  # nosec B404 - fixed argument list
    import sys
    command = [sys.executable, "-m", "education_system", "--university", "--cli"]
    for terminal, flag in (("x-terminal-emulator", "-e"), ("gnome-terminal", "--"),
                           ("konsole", "-e"), ("xterm", "-e")):
        if shutil.which(terminal):
            if messagebox.askyesno(TITLE, "Open the university command line in a new terminal? "
                                          "Batch operations is under its menu.",
                                   parent=gui.root):
                subprocess.Popen([terminal, flag, *command],  # nosec B603 - fixed argv
                                 start_new_session=True)
            return
    win, _bar_ = _text(gui.root, "Command Line Mode",
                       "No terminal program was found. Run this in a terminal:\n\n  " +
                       " ".join(command) + "\n\nthen choose Batch operations.", "720x220")


def about(gui):
    info = _call(gui.root, _app("batch_window").database_info) or {}
    messagebox.showinfo(TITLE, (
        "Batch Operations - University System\n\n"
        "Imports, bulk updates, exports, data quality, scheduling and integration, each run "
        "recorded as a job you can review, export and (for imports) undo.\n\n"
        f"Signed in as {gui.viewer.username or '-'} ({gui.viewer.role or '-'})\n"
        f"Database: {info.get('path', '-')}"), parent=gui.root)


class SettingsDialog:
    """Tools → Settings (administrators change them; everyone can see them)."""

    def __init__(self, gui):
        window = _app("batch_window")
        self.gui, self.window = gui, window
        values = _call(gui.root, window.settings)
        if not isinstance(values, dict):
            return
        self.win = win = tk.Toplevel(gui.root)
        win.title("Application Settings")
        win.transient(gui.root.winfo_toplevel())
        bar = ttk.Frame(win, padding=(8, 4))
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        state = "normal" if gui.is_admin else "disabled"
        ttk.Button(bar, text="Save", command=self.save, state=state).pack(side=tk.LEFT)
        ttk.Button(bar, text="Cancel", command=win.destroy).pack(side=tk.LEFT, padx=4)
        if not gui.is_admin:
            ttk.Label(bar, text="Only an administrator can change these.",
                      foreground="#777777").pack(side=tk.LEFT, padx=8)
        book = ttk.Notebook(win)
        book.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        general, imports, notify = (ttk.Frame(book, padding=10) for _ in range(3))
        book.add(general, text="General")
        book.add(imports, text="Import")
        book.add(notify, text="Notifications")
        info = _call(gui.root, window.database_info) or {}
        from education_system.paths import system_backup_dir
        db = ttk.LabelFrame(general, text="Database", padding=8)
        db.pack(fill=tk.X)
        ttk.Label(db, text=f"Database Path: {info.get('path', '-')}  ({info.get('size_mb', '-')}"
                           " MB) - fixed while the system runs").pack(anchor="w")
        backup = ttk.LabelFrame(general, text="Backup", padding=8)
        backup.pack(fill=tk.X, pady=6)
        ttk.Label(backup, text=f"Backup Directory: {system_backup_dir('university')}").pack(
            anchor="w")
        self.backup = tk.BooleanVar(value=values["backup_before_import"] == "1")
        ttk.Checkbutton(backup, text="Automatic backup before imports, bulk updates and undo",
                        variable=self.backup).pack(anchor="w", pady=(4, 0))
        behaviour = ttk.LabelFrame(imports, text="Import Behavior", padding=8)
        behaviour.pack(fill=tk.X)
        ttk.Label(behaviour, text="Duplicate rule:").grid(row=0, column=0, sticky="w")
        self.rule = ttk.Combobox(behaviour, state="readonly", width=56,
                                 values=list(window.DUPLICATE_RULES.values()))
        self.rule.set(window.DUPLICATE_RULES[values["duplicate_rule"]])
        self.rule.grid(row=0, column=1, sticky="w", pady=2)
        ttk.Label(behaviour, foreground="#555555", wraplength=600, text=(
            "Every row is validated during import (dates, e-mail, course, required fields); "
            "that cannot be turned off.")).grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Label(behaviour, text="History shows the last (days):").grid(row=2, column=0,
                                                                        sticky="w", pady=4)
        self.days = ttk.Entry(behaviour, width=8)
        self.days.insert(0, values["history_days"])
        self.days.grid(row=2, column=1, sticky="w")
        maps = ttk.LabelFrame(imports, text="Default column mapping", padding=8)
        maps.pack(fill=tk.X, pady=6)
        self.mapping = {}
        self._mapping_ids = {}
        for r, kind in enumerate(window.KINDS):
            rows = _call(gui.root, _app("batch_files").mappings, gui.viewer.username, kind) or []
            labels = {f"{m['name']} ({m['owner']})": str(m["id"]) for m in rows}
            self._mapping_ids[kind] = labels
            box = ttk.Combobox(maps, state="readonly", width=40,
                               values=["Automatic"] + list(labels))
            current = values.get(f"default_mapping_{kind}", "")
            box.set(next((k for k, v in labels.items() if v == current), "Automatic"))
            ttk.Label(maps, text=kind.title()).grid(row=r, column=0, sticky="w", pady=2)
            box.grid(row=r, column=1, sticky="w", pady=2)
            self.mapping[kind] = box
        ttk.Label(notify, text="E-mail when a job finishes (comma-separated):").pack(anchor="w")
        self.notify = ttk.Entry(notify, width=70)
        self.notify.insert(0, values["notify_addresses"])
        self.notify.pack(anchor="w", pady=4)
        ttk.Label(notify, foreground="#555555", wraplength=600, text=(
            "The e-mail gives the job's counts and reason, never the rows' personal data, and "
            "goes through the e-mail outbox.")).pack(anchor="w")

    def save(self):
        rules = {v: k for k, v in self.window.DUPLICATE_RULES.items()}
        values = {"backup_before_import": "1" if self.backup.get() else "0",
                  "duplicate_rule": rules[self.rule.get()],
                  "history_days": self.days.get().strip(),
                  "notify_addresses": self.notify.get().strip()}
        for kind, box in self.mapping.items():
            values[f"default_mapping_{kind}"] = self._mapping_ids[kind].get(box.get(), "")
        if _call(self.win, self.window.save_settings, self.gui.viewer, values, write=True):
            messagebox.showinfo(TITLE, "Settings saved.", parent=self.win)
            self.gui._load_mappings()
            self.win.destroy()


class DuplicatesWindow:
    """Tools → Find Duplicates: possible duplicate students across the
    whole record, each pair marked "not a duplicate" or "is a duplicate"
    (merging a real one is two-person work in Identity Management)."""

    def __init__(self, gui):
        self.gui = gui
        self.reports = _app("student_search_reports")
        self.win = win = tk.Toplevel(gui.root)
        win.title("Find Duplicates")
        win.geometry("1100x560")
        top = ttk.Frame(win, padding=(6, 4))
        top.pack(side=tk.TOP, fill=tk.X)
        self.reviewed = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Include pairs already decided", variable=self.reviewed,
                        command=self.load).pack(side=tk.LEFT)
        _bar(win, (("Not a duplicate…", lambda: self.decide("not_duplicate")),
                   ("Is a duplicate…", lambda: self.decide("duplicate")),
                   ("Merge (Identity Management)…", lambda: gui.extra.merge_duplicates(gui)),
                   ("Export…", self.export), ("Close", win.destroy)))
        self.tree = _tree(win, [("a", "Student 1"), ("na", "Name"), ("b", "Student 2"),
                                ("nb", "Name"), ("why", "Why"), ("score", "Score"),
                                ("decision", "Decided")], [90, 170, 90, 170, 340, 60, 110],
                          height=18)
        self._rows = []
        self.load()

    def load(self):
        rows = _call(self.win, self.reports.duplicates, self.gui.viewer, self.reviewed.get())
        self._rows = rows if isinstance(rows, list) else []
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self._rows):
            self.tree.insert("", "end", iid=str(i), values=(
                r["student_a"], r["name_a"], r["student_b"], r["name_b"], r["reasons"],
                r["score"], r["decision"]))

    def decide(self, decision):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(TITLE, "Select a pair first.", parent=self.win)
            return
        r = self._rows[int(sel[0])]
        note = simpledialog.askstring(TITLE, "Note (optional):", parent=self.win)
        if note is not None and _call(self.win, self.reports.review_duplicate, self.gui.viewer,
                                      r["student_a"], r["student_b"], decision, note,
                                      write=True):
            self.load()

    def export(self):
        path = filedialog.asksaveasfilename(parent=self.win, defaultextension=".csv",
                                            initialfile="possible_duplicates.csv")
        if not path:
            return
        import csv
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["student_a", "name_a", "student_b",
                                                        "name_b", "reasons", "score",
                                                        "decision"], extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self._rows)
        messagebox.showinfo(TITLE, f"{len(self._rows)} pair(s) saved to {path}.",
                            parent=self.win)
