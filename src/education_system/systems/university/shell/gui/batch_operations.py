"""Batch Operations window, laid out as it always was: the menu bar (File,
Tools, View, Help), the tabs Dashboard, Import, Update, Export, Data
Quality, Utilities, Automation, User Operations and History, and a status
bar with a progress bar and the database state.

This module holds the window, the menu bar, the status bar, the progress
dialog, the Import tab and the jobs / watched-folder helpers the other tabs
share. The Update, Export, Automation, History and Dashboard tabs and the
dialogs behind the menus are in ``batch_operations_more``; Data Quality,
Utilities, User Operations and the report windows are in
``batch_operations_extra``.

Every rule is in ``university/application``: ``batch_files`` (reading,
mapping, templates), ``batch_imports`` (the importers, resume, several
files, watched-folder runs), ``batch_enrolments``, ``batch_jobs`` (jobs,
undo, watch folders), ``batch_exports``, ``batch_reports``,
``batch_schedule``, ``batch_admin``, ``batch_window`` (settings, dashboard,
history, preview), ``student_bulk_actions`` and ``student_search``
(permissions). This module only presents them.
"""

from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from contextlib import closing
from tkinter import filedialog, messagebox, simpledialog, ttk

logger = logging.getLogger(__name__)
TITLE = "Batch Operations"
KINDS = {"Students": "students", "Marks": "marks", "Staff accounts": "staff",
         "Module enrolments": "enrolments"}
SELECTIONS = {"Listed below": "list", "Everyone on a course": "course",
              "A group": "group", "A saved search": "saved"}
EXPORT_FORMATS = {"CSV": "csv", "Excel (.xlsx)": "xlsx", "JSON": "json"}
MODES = {"Add new students": "create", "Update existing (by student_id)": "update",
         "Add or update": "both"}


def _app(name):
    import importlib
    return importlib.import_module(f"education_system.systems.university.application.{name}")


def _call(parent, fn, *args, write=False, **kwargs):
    from education_system.systems.university.infrastructure.database.db import get_connection
    try:
        with closing(get_connection(row_factory=False)) as conn:
            result = fn(conn, *args, **kwargs)
            if write:
                conn.commit()
            return True if result is None else result
    except ValueError as exc:
        messagebox.showerror(TITLE, str(exc), parent=parent)
    except Exception as exc:
        logger.exception("batch operation failed")
        messagebox.showerror(TITLE, f"That did not work: {exc}", parent=parent)
    return None


def _guard(parent, fn, *args, **kwargs):
    """Run a rule that manages its own connections; refusals become dialogs."""
    try:
        return fn(*args, **kwargs)
    except ValueError as exc:
        messagebox.showerror(TITLE, str(exc), parent=parent)
    except Exception as exc:
        logger.exception("batch operation failed")
        messagebox.showerror(TITLE, f"That did not work: {exc}", parent=parent)
    return None


def _tree(parent, columns, widths, height=10):
    frame = ttk.Frame(parent)
    frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
    view = ttk.Treeview(frame, columns=[c for c, _h in columns], show="headings", height=height)
    for (key, title), width in zip(columns, widths):
        view.heading(key, text=title)
        view.column(key, width=width, anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=view.yview)
    view.configure(yscrollcommand=bar.set)
    bar.pack(side=tk.RIGHT, fill=tk.Y)
    view.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    return view


def _bar(parent, buttons, side=tk.BOTTOM):
    bar = ttk.Frame(parent, padding=(6, 4))
    bar.pack(side=side, fill=tk.X)
    for label, command in buttons:
        ttk.Button(bar, text=label, command=command).pack(side=tk.LEFT, padx=2)
    return bar


def _header(parent, text):
    ttk.Label(parent, text=text, font=("Arial", 14, "bold")).pack(pady=(10, 8))


def option_cards(parent, cards, columns=3):
    """The old option cards: a titled box with a description and Execute."""
    grid = ttk.Frame(parent, padding=(14, 0))
    grid.pack(fill=tk.X)
    for i, (title, description, command) in enumerate(cards):
        card = ttk.LabelFrame(grid, text=title, padding=8)
        card.grid(row=i // columns, column=i % columns, padx=6, pady=6, sticky="nsew")
        ttk.Label(card, text=description, wraplength=260).pack(anchor="w", pady=(0, 6))
        ttk.Button(card, text="Execute", command=command).pack(anchor="w")
    for c in range(columns):
        grid.grid_columnconfigure(c, weight=1)
    return grid


def _viewer(auth):
    user = getattr(auth, "current_user", None) or {}
    check = getattr(auth, "check_permission", None) or (lambda _p: False)
    return _app("students.search").Viewer.from_check(user.get("username") or "",
                                                    user.get("role") or "", check)


def send_emails(emails):
    if emails:
        from education_system.systems.university.infrastructure.ui.record_screens import (
            send_emails as _send,
        )
        _send(emails)


class Progress:
    """A modal progress dialog that runs ``work()`` on a worker thread and
    hands its result to ``done(result)`` on the Tk thread. The work cannot
    be interrupted part-way (each row commits on its own); Hide lets it
    finish in the background and the status bar says when it has."""

    def __init__(self, gui, title, work, done=None):
        self.gui, self.done = gui, done
        self.results: queue.Queue = queue.Queue()
        self.win = tk.Toplevel(gui.root)
        self.win.title(title)
        self.win.transient(gui.root.winfo_toplevel())
        self.win.resizable(False, False)
        ttk.Label(self.win, text=title, padding=(14, 10, 14, 4),
                  font=("Arial", 11, "bold")).pack(anchor="w")
        self.note = ttk.Label(self.win, padding=(14, 0), wraplength=420,
                              text="Working… each row is saved as it goes; this window closes "
                                   "when the job is finished.")
        self.note.pack(anchor="w")
        self.bar = ttk.Progressbar(self.win, mode="indeterminate", length=420)
        self.bar.pack(padx=14, pady=10)
        self.bar.start(12)
        ttk.Button(self.win, text="Hide (keep running)", command=self.win.withdraw).pack(
            pady=(0, 10))
        gui.set_status(f"{title}…", busy=True)
        threading.Thread(target=self._run, args=(work,), daemon=True,
                         name="batch-operation").start()
        self.win.after(150, self._poll)

    def _run(self, work):
        try:
            self.results.put(("ok", work()))
        except Exception as exc:          # handed to the Tk thread, shown there
            if not isinstance(exc, ValueError):
                logger.exception("batch operation failed")
            self.results.put(("error", exc))

    def _poll(self):
        try:
            state, value = self.results.get_nowait()
        except queue.Empty:
            self.win.after(150, self._poll)
            return
        self.bar.stop()
        self.win.destroy()
        self.gui.set_status("Ready", busy=False)
        if state == "error":
            messagebox.showerror(TITLE, str(value) if isinstance(value, ValueError)
                                 else f"That did not work: {value}", parent=self.gui.root)
        elif self.done:
            self.done(value)


class BatchOperationsGUI:
    def __init__(self, root, auth=None):
        self.root = root
        self.auth = auth
        self.viewer = _viewer(auth)
        self.is_admin = self.viewer.role in _app("batch.window").ADMIN_ROLES
        toplevel = hasattr(root, "wm_title")
        if toplevel:
            try:
                root.title(TITLE)
                from education_system.platform.delivery.gui import window_sizing
                window_sizing.center(root, 1400, 900, minsize=(1200, 800))
            except tk.TclError:
                pass
        self._build_menu(toplevel)
        self._build_status_bar()           # packed before the notebook, so it stays visible
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=(4, 0))
        from education_system.systems.university.shell.gui import (
            batch_operations_extra as extra,
            batch_operations_more as more,
        )
        self.more, self.extra = more, extra
        self.tabs = {}
        self.tabs["Dashboard"] = more.DashboardTab(self)
        self._build_import()
        self.tabs["Update"] = more.UpdateTab(self)
        self.tabs["Export"] = more.ExportTab(self)
        self.tabs["Data Quality"] = extra.QualityTab(self)
        self.tabs["Utilities"] = extra.UtilitiesTab(self)
        self.tabs["Automation"] = more.AutomationTab(self)
        self.tabs["User Operations"] = extra.UserOperationsTab(self)
        self.tabs["History"] = more.HistoryTab(self)
        _guard(root, _app("batch.imports").run_watch_folders)
        self.refresh_jobs()

    # ------------------------------------------------------------------
    # Menu bar and status bar
    # ------------------------------------------------------------------
    def _menus(self):
        more, extra = (lambda: self.more), (lambda: self.extra)
        return [
            ("File", [("New Import...", self.new_import),
                      ("Open Database...", lambda: more().database_dialog(self)),
                      None,
                      ("Create Backup", lambda: extra().create_backup(self)),
                      ("Restore Backup...", lambda: more().restore_backup(self))]),
            ("Tools", [("Generate Template", lambda: extra().generate_template(self)),
                       ("Data Quality Check", lambda: self.show_tab("Data Quality", "load")),
                       ("Find Duplicates", lambda: more().DuplicatesWindow(self)),
                       None,
                       ("Command Line Mode", lambda: more().command_line_mode(self)),
                       ("Settings", lambda: more().SettingsDialog(self)),
                       ("System Status", lambda: extra().system_status(self))]),
            ("View", [("Dashboard", lambda: self.show_tab("Dashboard", "refresh")),
                      ("Import History", lambda: self.show_tab("History", "refresh")),
                      ("System Logs", lambda: extra().show_logs(self))]),
            ("Help", [("User Guide", lambda: extra().user_guide(self)),
                      ("About", lambda: more().about(self))]),
        ]

    def _build_menu(self, toplevel):
        if toplevel:
            menubar = tk.Menu(self.root)
            for label, items in self._menus():
                menu = tk.Menu(menubar, tearoff=0)
                for item in items:
                    if item is None:
                        menu.add_separator()
                    else:
                        menu.add_command(label=item[0], command=item[1])
                menubar.add_cascade(label=label, menu=menu)
            self.root.config(menu=menubar)
            return
        # Embedded in a workspace tab: a frame cannot hold a menu bar, so the
        # same menus become buttons along the top.
        strip = ttk.Frame(self.root, padding=(6, 2))
        strip.pack(side=tk.TOP, fill=tk.X)
        for label, items in self._menus():
            button = ttk.Menubutton(strip, text=label)
            menu = tk.Menu(button, tearoff=0)
            for item in items:
                if item is None:
                    menu.add_separator()
                else:
                    menu.add_command(label=item[0], command=item[1])
            button["menu"] = menu
            button.pack(side=tk.LEFT, padx=2)

    def _build_status_bar(self):
        bar = ttk.Frame(self.root, padding=(8, 3))
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_label = ttk.Label(bar, text="Ready")
        self.status_label.pack(side=tk.LEFT)
        if hasattr(self.root, "wm_title"):
            ttk.Button(bar, text="Return to Main Menu", command=self.close).pack(
                side=tk.RIGHT, padx=(8, 0))
        self.db_label = ttk.Label(bar, text="")
        self.db_label.pack(side=tk.RIGHT, padx=8)
        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=180)
        info = _call(self.root, _app("batch.window").database_info)
        if isinstance(info, dict):
            self.db_label.configure(text=f"Database connected ({info['size_mb']} MB)")
        else:
            self.db_label.configure(text="Database not available")

    def set_status(self, text, busy=None):
        try:
            self.status_label.configure(text=text)
            if busy is True:
                self.progress.pack(side=tk.RIGHT, padx=8)
                self.progress.start(12)
            elif busy is False:
                self.progress.stop()
                self.progress.pack_forget()
        except tk.TclError:
            pass

    def close(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def show_tab(self, name, method=None):
        tab = self.tabs.get(name)
        if tab is None:
            return
        self.notebook.select(tab.frame)
        if method:
            getattr(tab, method)()

    def refresh_jobs(self):
        for name in ("History", "Dashboard"):
            tab = self.tabs.get(name)
            if tab is not None:
                tab.refresh()

    # ------------------------------------------------------------------
    # Running a job: backup first when set, notify after
    # ------------------------------------------------------------------
    def run_job(self, title, work, done):
        """Run ``work()`` (which returns a dict with ``job_id``) in the
        progress dialog: a backup first when the settings ask for one, the
        job-finished e-mail after."""
        backup = bool(_call(self.root, _app("batch.window").backup_needed))

        def task():
            if backup:
                from education_system.systems.university.infrastructure.database import (
                    data_backup,
                )
                if not data_backup.create_backup(manual=True,
                                                 operation_name="batch_before_import"):
                    raise ValueError("The backup before the job did not complete, so the job "
                                     "was not run (Settings: back up before imports)")
            return work()

        def finished(result):
            job_id = result.get("job_id") if isinstance(result, dict) else None
            if job_id:
                send_emails(_call(self.root, _app("batch.window").job_notice_emails, job_id))
            self.refresh_jobs()
            done(result)
        Progress(self, title, task, finished)

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------
    def _build_import(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Import")
        self.import_frame = tab
        _header(tab, "Import Operations")
        option_cards(tab, (
            ("Import from CSV", "Import student records from CSV files",
             lambda: self.new_import("*.csv")),
            ("Import from Excel", "Import student records from Excel spreadsheets (choose the "
                                  "sheet)", lambda: self.new_import("*.xlsx")),
            ("Multi-File Import", "Import from multiple files at once, each as its own job",
             self._import_many),
            ("Duplicate Detection", "Check a file for duplicate records before import",
             self._duplicates_in_file),
            ("Preview Import", "Preview data before importing; nothing is saved",
             lambda: self._run_import(True)),
            ("Resume Import", "Resume a previously interrupted import", self._resume)))
        form = ttk.LabelFrame(tab, text="File and options", padding=8)
        form.pack(fill=tk.X, padx=20, pady=6)
        self.kind = ttk.Combobox(form, values=list(KINDS), state="readonly", width=18)
        self.kind.set("Students")
        self.mode = ttk.Combobox(form, values=list(MODES), state="readonly", width=30)
        self.mode.set("Add new students")
        self.file_var = tk.StringVar()
        self.reason = ttk.Entry(form, width=50)
        self.provision = tk.BooleanVar(value=True)
        self.mapping_choice = ttk.Combobox(form, state="readonly", width=30)
        self.sheet = ttk.Combobox(form, state="readonly", width=30)
        rows = (("What", self.kind), ("Mode (students)", self.mode),
                ("Column mapping", self.mapping_choice), ("Reason (recorded)", self.reason),
                ("Excel sheet", self.sheet))
        for r, (label, widget) in enumerate(rows):
            ttk.Label(form, text=label).grid(row=r, column=0, sticky="w", pady=2)
            widget.grid(row=r, column=1, sticky="w", pady=2)
        file_row = ttk.Frame(form)
        file_row.grid(row=5, column=1, sticky="w", pady=2)
        ttk.Label(form, text="File").grid(row=5, column=0, sticky="w")
        ttk.Entry(file_row, textvariable=self.file_var, width=50).pack(side=tk.LEFT)
        ttk.Button(file_row, text="Browse…", command=self._browse).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(form, text="Create sign-ins and send activation emails for new students",
                        variable=self.provision).grid(row=6, column=1, sticky="w")
        self.override = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Module enrolments: override module rules (administrators; "
                                   "the reason is recorded)",
                        variable=self.override).grid(row=7, column=1, sticky="w")
        self.kind.bind("<<ComboboxSelected>>", lambda _e: self._load_mappings())
        _bar(tab, (("Download template…", self._template), ("Edit mapping…", self._edit_mapping),
                   ("Preview", lambda: self._run_import(True)),
                   ("Import", lambda: self._run_import(False)),
                   ("Import several files…", self._import_many)), side=tk.TOP)
        self.import_note = ttk.Label(tab, padding=(20, 0), foreground="#555555", wraplength=1100,
                                     text="Preview checks every row and changes nothing. Import "
                                          "records a job you can undo from the History tab.")
        self.import_note.pack(anchor="w")
        self.result_tree = _tree(tab, [("row", "Row"), ("action", "Result"), ("ref", "Record"),
                                       ("message", "Details")], [50, 90, 110, 760], height=8)
        self._mapping = None
        self._load_mappings()

    def new_import(self, pattern=None):
        self.notebook.select(self.import_frame)
        self._browse(pattern)

    def _kind(self):
        return KINDS[self.kind.get()]

    def _browse(self, pattern=None):
        types = [("Data files", pattern or "*.csv *.xlsx *.json"), ("All files", "*.*")]
        path = filedialog.askopenfilename(parent=self.root, filetypes=types)
        if path:
            self.file_var.set(path)
            self._mapping = None
            sheets = _guard(self.root, _app("batch.files").sheet_names, path) or []
            self.sheet.configure(values=sheets)
            self.sheet.set(sheets[0] if sheets else "")

    def _load_mappings(self):
        rows = _call(self.root, _app("batch.files").mappings, self.viewer.username,
                     self._kind()) or []
        self._mappings = {f"{m['name']} ({m['owner']})": m for m in rows}
        self.mapping_choice.configure(values=["Automatic"] + list(self._mappings))
        default = _call(self.root, _app("batch.window").default_mapping, self._kind())
        chosen = next((label for label, m in self._mappings.items()
                       if isinstance(default, int) and m["id"] == default), "Automatic")
        self.mapping_choice.set(chosen)
        self._mapping = None

    def _template(self):
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".csv",
                                            initialfile=f"{self._kind()}_template.csv")
        if path:
            _app("batch.files").write_template(self._kind(), path)
            messagebox.showinfo(TITLE, f"Template saved to {path}", parent=self.root)

    def _current_mapping(self):
        if self._mapping:
            return self._mapping
        chosen = self._mappings.get(self.mapping_choice.get())
        return chosen["mapping"] if chosen else None

    def _edit_mapping(self):
        files = _app("batch.files")
        if not self.file_var.get():
            messagebox.showinfo(TITLE, "Choose a file first.", parent=self.root)
            return
        loaded = _guard(self.root, files.read_table, self.file_var.get(), self.sheet.get() or None)
        if not loaded:
            return
        headers, _rows = loaded
        current = self._current_mapping() or files.auto_mapping(self._kind(), headers)
        _MappingDialog(self, headers, current)

    def _rows(self):
        mode = MODES[self.mode.get()] if self._kind() == "students" else None
        return _guard(self.root, _app("batch.imports").read_and_map, self.file_var.get(),
                      self._kind(), self._current_mapping(), mode, self.sheet.get() or None)

    def _show_rows(self, result, note):
        self.result_tree.delete(*self.result_tree.get_children())
        for i, r in enumerate(result["rows"]):
            self.result_tree.insert("", "end", iid=str(i), values=(
                r["row_no"], r["action"], r.get("ref") or "", r.get("message") or ""))
        counts = ", ".join(f"{k}: {v}" for k, v in result["counts"].items())
        self.import_note.configure(text=f"{note} {counts}")

    def _run_import(self, dry_run):
        if not self.file_var.get():
            messagebox.showinfo(TITLE, "Choose a file first (Browse…).", parent=self.root)
            return
        loaded = self._rows()
        if not loaded:
            return
        rows, _mapping = loaded
        if dry_run:
            result = _guard(self.root, self._import, rows, True)
            if isinstance(result, dict):
                self._show_rows(result, "Preview - nothing saved.")
            return
        if not messagebox.askyesno(TITLE, f"Import {len(rows)} row(s)? Run Preview first if you "
                                          "have not.", parent=self.root):
            return
        self.run_job(f"Importing {len(rows)} row(s)", lambda: self._import(rows, False),
                     lambda result: self._show_rows(result, f"Job #{result['job_id']} recorded."))

    def _import(self, rows, dry_run):
        imports = _app("batch.imports")
        source, reason = self.file_var.get(), self.reason.get().strip()
        kind = self._kind()
        if kind == "marks":
            return imports.import_marks(rows, self.viewer, reason=reason, source=source,
                                        dry_run=dry_run)
        if kind == "staff":
            return imports.import_staff(rows, self.viewer, reason=reason, source=source,
                                        dry_run=dry_run, auth=self.auth)
        if kind == "enrolments":
            return _app("batch.enrolments").import_enrolments(
                rows, self.viewer, reason=reason, source=source, dry_run=dry_run,
                override=self.override.get())
        return imports.import_students(rows, self.viewer, mode=MODES[self.mode.get()],
                                       reason=reason, source=source, dry_run=dry_run,
                                       provision=self.provision.get(), auth=self.auth)

    def _duplicates_in_file(self):
        """Preview the chosen file and show only the rows that are, or may
        be, duplicates (within the file or of existing students)."""
        if self._kind() != "students":
            self.kind.set("Students")
            self._load_mappings()
        if not self.file_var.get():
            self._browse()
            if not self.file_var.get():
                return
        loaded = self._rows()
        if not loaded:
            return
        result = _guard(self.root, self._import, loaded[0], True)
        if not isinstance(result, dict):
            return
        dupes = [r for r in result["rows"] if "duplicate" in (r.get("message") or "")
                 or "same person" in (r.get("message") or "")
                 or "already belongs" in (r.get("message") or "")]
        self._show_rows({"rows": dupes, "counts": {"possible duplicates": len(dupes),
                                                   "rows checked": len(result["rows"])}},
                        "Duplicate check - nothing saved.")
        self.notebook.select(self.import_frame)

    def _import_many(self):
        paths = filedialog.askopenfilenames(parent=self.root, filetypes=[
            ("Data files", "*.csv *.xlsx *.json"), ("All files", "*.*")])
        if not paths:
            return
        reason = self.reason.get().strip()
        if not reason:
            messagebox.showinfo(TITLE, "Give the reason recorded on each change first.",
                                parent=self.root)
            return
        if not messagebox.askyesno(TITLE, f"Import {len(paths)} file(s) of "
                                          f"{self.kind.get().lower()}, each as its own job? "
                                          "Columns are matched automatically.",
                                   parent=self.root):
            return
        mode = MODES[self.mode.get()] if self._kind() == "students" else None

        def work():
            results = _app("batch.imports").import_files(
                list(paths), self._kind(), self.viewer, mode=mode or "create", reason=reason,
                provision=self.provision.get(), auth=self.auth)
            return {"results": results, "job_id": None}

        def done(out):
            results = out["results"]
            self.result_tree.delete(*self.result_tree.get_children())
            for i, r in enumerate(results):
                counts = ", ".join(f"{k}: {v}" for k, v in r["counts"].items())
                self.result_tree.insert("", "end", iid=str(i), values=(
                    i + 1, "failed" if r["error"] else f"job #{r['job_id']}", r["file"],
                    r["error"] or counts))
                if r.get("job_id"):
                    send_emails(_call(self.root, _app("batch.window").job_notice_emails,
                                      r["job_id"]))
            self.import_note.configure(text=f"{sum(1 for r in results if not r['error'])} of "
                                            f"{len(results)} file(s) imported.")
        self.run_job(f"Importing {len(paths)} file(s)", work, done)

    def _resume(self):
        found = _call(self.root, _app("batch.imports").interrupted) or []
        if not found:
            messagebox.showinfo(TITLE, "No import was interrupted part-way.", parent=self.root)
            return
        lines = "\n".join(f"#{j['id']} {j['kind']} {j['source'] or ''}: {j['rows_done']} row(s) "
                          f"done" + ("" if j["resumable"] else " (file gone)") for j in found)
        job_id = simpledialog.askinteger(TITLE, f"Interrupted imports:\n{lines}\n\nResume which "
                                                "job? Rows already done are not repeated.",
                                         parent=self.root)
        if not job_id:
            return

        def done(result):
            counts = ", ".join(f"{k}: {v}" for k, v in result["counts"].items())
            messagebox.showinfo(TITLE, f"Job #{job_id} resumed as job #{result['job_id']} "
                                       f"({result['rows_remaining']} row(s) left): {counts}",
                                parent=self.root)
        self.run_job(f"Resuming job #{job_id}",
                     lambda: _app("batch.imports").resume(job_id, self.viewer, auth=self.auth),
                     done)


class _MappingDialog:
    """Match each canonical column to one of the file's headers; optionally
    save the mapping for next time."""

    def __init__(self, owner: BatchOperationsGUI, headers, current):
        files = _app("batch.files")
        self.owner = owner
        self.win = win = tk.Toplevel(owner.root)
        win.title("Column mapping")
        body = ttk.Frame(win, padding=10)
        body.pack(fill=tk.BOTH, expand=True)
        self.choices = {}
        for r, (column, required, _ex) in enumerate(files.COLUMNS[owner._kind()]):
            ttk.Label(body, text=column + (" *" if required else "")).grid(row=r, column=0,
                                                                         sticky="w")
            box = ttk.Combobox(body, values=["(not in file)"] + list(headers), state="readonly",
                               width=30)
            box.set(current.get(column, "(not in file)"))
            box.grid(row=r, column=1, sticky="w", pady=1)
            self.choices[column] = box
        bar = ttk.Frame(body)
        bar.grid(row=len(self.choices) + 1, column=1, sticky="w", pady=8)
        ttk.Button(bar, text="Use", command=self.use).pack(side=tk.LEFT)
        ttk.Button(bar, text="Use and save…", command=lambda: self.use(save=True)).pack(
            side=tk.LEFT, padx=4)

    def use(self, save=False):
        mapping = {c: b.get() for c, b in self.choices.items() if b.get() != "(not in file)"}
        if save:
            name = simpledialog.askstring(TITLE, "Name for this mapping:", parent=self.win)
            if name and _call(self.win, _app("batch.files").save_mapping,
                              self.owner.viewer.username, self.owner._kind(), name, mapping,
                              write=True):
                self.owner._load_mappings()
        self.owner._mapping = mapping
        self.win.destroy()
