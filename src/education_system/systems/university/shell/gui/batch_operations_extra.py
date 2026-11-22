"""Batch Operations: the Data Quality, Utilities and User Operations tabs,
the report windows (the comprehensive report keeps its General / Import /
Summary / Detailed Issues tabs), System Status, System Logs and the user
guide. Rules are in ``university/application`` (``batch_admin``,
``batch_reports``, ``batch_window``); this module only presents them.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from education_system.systems.university.application.batch.admin import GUIDE
from education_system.systems.university.shell.gui.batch_operations import (
    TITLE,
    _app,
    _bar,
    _call,
    _guard,
    _header,
    _tree,
    option_cards,
)

REPORTS = {"Success rates": "success", "Error analysis": "errors",
           "Performance trends": "performance", "Comprehensive (with system figures)":
           "comprehensive", "Enrolment statistics": "statistics"}


def _admin(gui) -> bool:
    return gui.is_admin


def _text_window(parent, title, text, size="900x620"):
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry(size)
    bar = ttk.Frame(win, padding=(6, 4))
    bar.pack(side=tk.BOTTOM, fill=tk.X)
    body = tk.Text(win, wrap="none", font=("Courier", 10))
    scroll = ttk.Scrollbar(win, orient="vertical", command=body.yview)
    body.configure(yscrollcommand=scroll.set)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    body.pack(fill=tk.BOTH, expand=True)
    body.insert("1.0", text)
    body.configure(state="disabled")
    ttk.Button(bar, text="Close", command=win.destroy).pack(side=tk.RIGHT)
    return win, bar


def _save_button(win, bar, report):
    reports = _app("batch_reports")

    def save():
        path = filedialog.asksaveasfilename(parent=win, defaultextension=".json",
                                            filetypes=[("JSON", "*.json"), ("CSV", "*.csv"),
                                                       ("Text", "*.txt")])
        if not path:
            return
        if path.lower().endswith(".txt"):
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(reports.as_text(report))
        elif not _guard(win, reports.write_report, report, path):
            return
        messagebox.showinfo(TITLE, f"Saved to {path}", parent=win)
    ttk.Button(bar, text="Export Report…", command=save).pack(side=tk.LEFT)


def show_report(parent, report):
    """A report as text, with Export (JSON, CSV or text). The comprehensive
    report is shown in its four tabs."""
    reports = _app("batch_reports")
    if report.get("system") is not None and report.get("success") is not None:
        win = tk.Toplevel(parent)
        win.title(report.get("title", "Report"))
        win.geometry("1000x680")
        bar = ttk.Frame(win, padding=(6, 4))
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(win, text="Comprehensive System Report Generated Successfully",
                  font=("Arial", 12, "bold"), padding=6).pack(anchor="w")
        book = ttk.Notebook(win)
        book.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        for label, text in (
                ("General", "\n".join([report["title"], f"Generated {report['generated_at']}",
                                       ""] + reports._system_lines(report["system"]))),
                ("Import", reports.as_text(report["success"])),
                ("Summary", reports.as_text(report["performance"])),
                ("Detailed Issues", reports.as_text(report["errors"]))):
            frame = ttk.Frame(book)
            book.add(frame, text=label)
            body = tk.Text(frame, wrap="none", font=("Courier", 10))
            scroll = ttk.Scrollbar(frame, orient="vertical", command=body.yview)
            body.configure(yscrollcommand=scroll.set)
            scroll.pack(side=tk.RIGHT, fill=tk.Y)
            body.pack(fill=tk.BOTH, expand=True)
            body.insert("1.0", text)
            body.configure(state="disabled")
        _save_button(win, bar, report)
        ttk.Button(bar, text="Close", command=win.destroy).pack(side=tk.RIGHT)
        return win
    win, bar = _text_window(parent, report.get("title", "Report"), reports.as_text(report))
    _save_button(win, bar, report)
    return win


def ask_database(parent) -> dict | None:
    """Connection details for an export to another database (never stored)."""
    win = tk.Toplevel(parent)
    win.title("External Database")
    win.transient(parent.winfo_toplevel())
    body = ttk.Frame(win, padding=10)
    body.pack(fill=tk.BOTH, expand=True)
    fields = {}
    kind = ttk.Combobox(body, state="readonly", values=["sqlite", "postgresql", "mysql"],
                        width=14)
    kind.set("sqlite")
    rows = [("Type", kind)]
    for key, label, show in (("path", "SQLite file", None), ("host", "Host", None),
                             ("port", "Port", None), ("database", "Database", None),
                             ("user", "User", None), ("password", "Password", "*"),
                             ("table", "Table", None)):
        fields[key] = ttk.Entry(body, width=36, show=show or "")
        rows.append((label, fields[key]))
    fields["table"].insert(0, "students_export")
    replace = tk.BooleanVar(value=False)
    for r, (label, widget) in enumerate(rows):
        ttk.Label(body, text=label).grid(row=r, column=0, sticky="w", pady=2)
        widget.grid(row=r, column=1, sticky="w", pady=2)
    ttk.Checkbutton(body, text="Empty the table first", variable=replace).grid(
        row=len(rows), column=1, sticky="w")
    result: dict = {}

    def browse():
        path = filedialog.asksaveasfilename(parent=win, defaultextension=".db")
        if path:
            fields["path"].delete(0, tk.END)
            fields["path"].insert(0, path)

    def ok():
        result.update({k: e.get().strip() for k, e in fields.items()})
        result["type"] = kind.get()
        result["replace"] = replace.get()
        win.destroy()

    def test():
        config = {k: e.get().strip() for k, e in fields.items()}
        config["type"] = kind.get()
        from education_system.systems.university.infrastructure.batch import external_export
        found = _guard(win, external_export.test_connection, config)
        if found is not None:
            messagebox.showinfo(TITLE, f"Test Connection: {found}.", parent=win)
    bar = ttk.Frame(body)
    bar.grid(row=len(rows) + 1, column=1, sticky="w", pady=8)
    ttk.Button(bar, text="SQLite file…", command=browse).pack(side=tk.LEFT)
    ttk.Button(bar, text="Test Connection", command=test).pack(side=tk.LEFT, padx=4)
    ttk.Button(bar, text="Send", command=ok).pack(side=tk.LEFT)
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side=tk.LEFT, padx=4)
    parent.wait_window(win)
    return result or None


# ── actions used by the menus and several tabs ──────────────────────────


def generate_template(gui):
    """Tools → Generate Template: one kind, or every kind into a folder."""
    files = _app("batch_files")
    kinds = ("students", "marks", "staff", "enrolments", "actions")
    choice = simpledialog.askstring(TITLE, "Template for which import? (" + ", ".join(kinds) +
                                    ", or all)", parent=gui.root, initialvalue="students")
    if not choice:
        return
    choice = choice.strip().lower()
    if choice == "all":
        folder = filedialog.askdirectory(parent=gui.root)
        if folder:
            from pathlib import Path
            made = [files.write_template(k, Path(folder) / f"{k}_template.csv") for k in kinds]
            messagebox.showinfo(TITLE, f"{len(made)} template(s) saved in {folder}.",
                                parent=gui.root)
        return
    if choice not in kinds:
        messagebox.showerror(TITLE, "Choose one of: " + ", ".join(kinds) + " or all.",
                             parent=gui.root)
        return
    path = filedialog.asksaveasfilename(parent=gui.root, defaultextension=".csv",
                                        initialfile=f"{choice}_template.csv")
    if path:
        files.write_template(choice, path)
        messagebox.showinfo(TITLE, f"Template saved to {path}", parent=gui.root)


def create_backup(gui):
    if not gui.is_admin:
        messagebox.showinfo(TITLE, "Backups are taken by administrators.", parent=gui.root)
        return
    if not messagebox.askyesno(TITLE, "Back up the whole database now?", parent=gui.root):
        return
    from education_system.systems.university.infrastructure.database import data_backup
    from education_system.systems.university.shell.gui.batch_operations import Progress

    def done(path):
        if path:
            messagebox.showinfo(TITLE, f"Backup saved to {path}", parent=gui.root)
        else:
            messagebox.showerror(TITLE, "The backup did not complete; see the application log.",
                                 parent=gui.root)
    Progress(gui, "Backing up the database",
             lambda: data_backup.create_backup(manual=True, operation_name="batch_operations"),
             done)


def system_status(gui):
    from education_system.systems.university.shell.gui.batch_operations import Progress

    def done(report):
        if isinstance(report, dict):
            show_report(gui.root, {**report, "title": "System status"})
    Progress(gui, "Measuring the system",
             lambda: _app("batch_reports").system_status(gui.viewer), done)


def show_logs(gui):
    """View → System Logs: the live application log, filtered, with a
    saved copy. The log itself is never cleared from here (it is rotated
    by the logging configuration)."""
    if not gui.is_admin:
        messagebox.showinfo(TITLE, "The application log is for administrators.",
                            parent=gui.root)
        return
    win = tk.Toplevel(gui.root)
    win.title("System Logs")
    win.geometry("1150x700")
    top = ttk.Frame(win, padding=(6, 4))
    top.pack(side=tk.TOP, fill=tk.X)
    ttk.Label(top, text="Show").pack(side=tk.LEFT)
    level = ttk.Combobox(top, state="readonly", width=10, values=["All", "WARNING", "ERROR"])
    level.set("All")
    level.pack(side=tk.LEFT, padx=4)
    ttk.Label(top, text="containing").pack(side=tk.LEFT)
    needle = ttk.Entry(top, width=30)
    needle.pack(side=tk.LEFT, padx=4)
    bar = ttk.Frame(win, padding=(6, 4))
    bar.pack(side=tk.BOTTOM, fill=tk.X)
    body = tk.Text(win, wrap="none", font=("Courier", 9))
    scroll = ttk.Scrollbar(win, orient="vertical", command=body.yview)
    body.configure(yscrollcommand=scroll.set)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    body.pack(fill=tk.BOTH, expand=True)
    state = {"lines": [], "path": None}

    def load():
        found = _guard(win, _app("batch_admin").log_lines, gui.viewer,
                       None if level.get() == "All" else level.get(),
                       needle.get().strip() or None, 2000)
        if not isinstance(found, dict):
            return
        state.update(found)
        win.title(f"System Logs - {found['path'] or 'no log file found'}")
        body.configure(state="normal")
        body.delete("1.0", tk.END)
        body.insert("1.0", "\n".join(found["lines"]) or "(no matching lines)")
        body.see(tk.END)
        body.configure(state="disabled")

    def download():
        path = filedialog.asksaveasfilename(parent=win, defaultextension=".log",
                                            initialfile="university_log_extract.log")
        if path:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(state["lines"]))
            messagebox.showinfo(TITLE, f"{len(state['lines'])} line(s) saved to {path}.",
                                parent=win)
    ttk.Button(top, text="View Logs", command=load).pack(side=tk.LEFT, padx=4)
    ttk.Button(bar, text="Download Logs…", command=download).pack(side=tk.LEFT)
    ttk.Button(bar, text="Close", command=win.destroy).pack(side=tk.RIGHT)
    load()


def user_guide(gui):
    guide = GUIDE + (
        "\n\nThe window\n----------\n"
        "Dashboard - figures for recent jobs, exports and scheduled tasks.\n"
        "Import - the six import cards (CSV, Excel, several files, duplicate check, preview, "
        "resume) above the file and options.\n"
        "Update - bulk changes with a preview; module and mark updates.\n"
        "Export - students, statistics and reports; administrators can send to another "
        "database or an HTTPS endpoint.\n"
        "Data Quality - validate, find duplicates, clean (safe fixes), the quality dashboard.\n"
        "Utilities - templates, backup, undo the last operation, settings.\n"
        "Automation - daily watched-folder imports, e-mailed reports, the API server, "
        "external database and REST setup.\n"
        "User Operations - staff accounts, role permissions, module enrolment, e-mail "
        "campaigns.\n"
        "History - every job and export; details, errors, undo, resume, export.\n"
        "Tools → Settings - backup before imports, duplicate rule, job e-mails, default "
        "mappings.")
    _text_window(gui.root, "User Guide", guide, "860x680")


def merge_duplicates(gui):
    from education_system.systems.university.domains.learners.interfaces.gui.identity_management.identity_management_app import (  # noqa: E501
        IdentityManagementApp,
    )
    win = tk.Toplevel(gui.root)
    win.title("Identity Management")
    win.geometry("1200x760")
    user = dict(getattr(gui.auth, "current_user", None) or {})
    IdentityManagementApp(win, user=user).pack(fill=tk.BOTH, expand=True)


class ReportsDialog:
    """Export → Export Reports: choose a report and the period."""

    def __init__(self, gui):
        self.gui = gui
        self.win = win = tk.Toplevel(gui.root)
        win.title("Generate Reports")
        win.transient(gui.root.winfo_toplevel())
        body = ttk.Frame(win, padding=10)
        body.pack(fill=tk.BOTH, expand=True)
        ttk.Label(body, wraplength=460, foreground="#555555", text=(
            "Reports are built from the jobs actually recorded and from measured system "
            "figures; anything that cannot be measured says so instead of being estimated.")
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.report = ttk.Combobox(body, state="readonly", width=38, values=list(REPORTS))
        self.report.set("Comprehensive (with system figures)")
        self.days = ttk.Entry(body, width=8)
        self.days.insert(0, "90")
        for r, (label, widget) in enumerate((("Report", self.report),
                                             ("Last how many days", self.days)), 1):
            ttk.Label(body, text=label).grid(row=r, column=0, sticky="w", pady=2)
            widget.grid(row=r, column=1, sticky="w", pady=2)
        bar = ttk.Frame(body)
        bar.grid(row=3, column=1, sticky="w", pady=8)
        ttk.Button(bar, text="Generate", command=self.show).pack(side=tk.LEFT)
        ttk.Button(bar, text="Close", command=win.destroy).pack(side=tk.LEFT, padx=4)

    def show(self):
        from education_system.systems.university.shell.gui.batch_operations import Progress
        from education_system.systems.university.infrastructure.database.db import get_connection
        reports = _app("batch_reports")
        key = REPORTS[self.report.get()]
        text = self.days.get().strip()
        days = int(text) if text.isdigit() and int(text) > 0 else None
        viewer = self.gui.viewer

        def work():
            from contextlib import closing
            with closing(get_connection(row_factory=False)) as conn:
                fn = {"success": lambda: reports.success_rates(conn, viewer, days),
                      "errors": lambda: reports.error_analysis(conn, viewer, days),
                      "performance": lambda: reports.performance(conn, viewer, days),
                      "comprehensive": lambda: reports.comprehensive(conn, viewer, days),
                      "statistics": lambda: reports.enrolment_statistics(conn, viewer)}[key]
                return fn()
        Progress(self.gui, f"Generating {self.report.get().lower()}", work,
                 lambda report: show_report(self.gui.root, report))


# ── Data Quality ────────────────────────────────────────────────────────


class QualityTab:
    """Analysis Tools on the left (Validate Data, Find Duplicates, Clean
    Data, e-mail the report), the Quality Dashboard on the right, the issues
    below."""

    def __init__(self, gui):
        self.gui, self.root = gui, gui.root
        self.frame = tab = ttk.Frame(gui.notebook)
        gui.notebook.add(tab, text="Data Quality")
        _header(tab, "Data Quality Tools")
        top = ttk.Frame(tab, padding=(14, 0))
        top.pack(fill=tk.X)
        tools = ttk.LabelFrame(top, text="Analysis Tools", padding=8)
        tools.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6))
        for label, command in (("Validate Data", self.load),
                               ("Find Duplicates", lambda: gui.more.DuplicatesWindow(gui)),
                               ("Clean Data (safe fixes)", self.fix),
                               ("Export issues…", self.export),
                               ("Email Report to Admin", self.email),
                               ("Merge Duplicates (Identity Management)…",
                                lambda: merge_duplicates(gui))):
            ttk.Button(tools, text=label, command=command, width=36).pack(fill=tk.X, pady=3)
        dash = ttk.LabelFrame(top, text="Quality Dashboard", padding=8)
        dash.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Button(dash, text="Refresh Dashboard", command=self.load).pack(side=tk.BOTTOM,
                                                                        anchor="w")
        self.summary = ttk.Label(dash, wraplength=760, justify="left",
                                 text="Press Refresh to load the dashboard.")
        self.summary.pack(anchor="w")
        self.kinds = _tree(dash, [("kind", "Problem"), ("issues", "Issues"),
                                  ("fixable", "Safe fixes")], [260, 80, 80], height=5)
        ttk.Label(tab, padding=(20, 4), foreground="#555555", text=(
            "Select issues below and press Clean Data to apply their safe fixes; anything "
            "without one is decided by hand in Student Records.")).pack(anchor="w")
        self.tree = _tree(tab, [("kind", "Problem"), ("sid", "Student"), ("name", "Name"),
                                ("detail", "Details"), ("fix", "Safe fix")],
                          [110, 90, 170, 560, 160], height=10)
        self.tree.configure(selectmode="extended")
        self._issues = {}

    def refresh(self):
        pass

    def load(self):
        dash = _call(self.root, _app("batch_admin").quality_dashboard, self.gui.viewer)
        if not isinstance(dash, dict):
            return
        self.tree.delete(*self.tree.get_children())
        self._issues = {i["key"]: i for i in dash["list"]}
        for i in dash["list"]:
            fix = ", ".join(f"{k} → {v}" for k, v in (i["fix"] or {}).items())
            self.tree.insert("", "end", iid=i["key"], values=(
                i["kind"], i["student_id"], i["name"], i["detail"], fix or "decide by hand"))
        self.kinds.delete(*self.kinds.get_children())
        for k in dash["by_kind"]:
            self.kinds.insert("", "end", values=(k["kind"], k["issues"], k["fixable"]))
        self.summary.configure(text=(
            f"{dash['students']} records checked; {dash['issues']} issue(s) on "
            f"{dash['students_affected']} record(s); "
            f"{dash['clean_percent'] if dash['clean_percent'] is not None else '-'}% clean; "
            f"{dash['fixable']} can be fixed safely."))

    def fix(self):
        keys = [k for k in self.tree.selection() if (self._issues.get(k) or {}).get("fix")]
        if not keys:
            if not self._issues:
                self.load()
            messagebox.showinfo(TITLE, "Select issues that have a safe fix (Validate Data "
                                       "lists them).", parent=self.root)
            return
        if not messagebox.askyesno(TITLE, f"Apply {len(keys)} fix(es)? Each change is written "
                                          "to the student's change history.", parent=self.root):
            return
        n = _call(self.root, _app("batch_admin").apply_quality_fixes, self.gui.viewer, keys,
                  write=True)
        if n is not None:
            messagebox.showinfo(TITLE, f"{n} record(s) corrected.", parent=self.root)
            self.load()

    def export(self):
        if not self._issues:
            self.load()
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".csv",
                                            initialfile="data_quality_issues.csv")
        if not path:
            return
        import csv
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["problem", "student_id", "name", "details", "safe_fix"])
            for i in self._issues.values():
                writer.writerow([i["kind"], i["student_id"], i["name"], i["detail"],
                                 "; ".join(f"{k}={v}" for k, v in (i["fix"] or {}).items())])
        messagebox.showinfo(TITLE, f"{len(self._issues)} issue(s) saved to {path}.",
                            parent=self.root)

    def email(self):
        emails = _call(self.root, _app("batch_admin").quality_report_emails, self.gui.viewer,
                       write=True)
        if emails:
            messagebox.showinfo(TITLE, f"Report sent to {len(emails)} administrator(s).",
                                parent=self.root)


# ── Utilities ───────────────────────────────────────────────────────────


class UtilitiesTab:
    def __init__(self, gui):
        self.gui, self.root = gui, gui.root
        self.frame = tab = ttk.Frame(gui.notebook)
        gui.notebook.add(tab, text="Utilities")
        _header(tab, "Utility Tools")
        option_cards(tab, (
            ("Generate Template", "Generate CSV import templates (one kind, or all)",
             lambda: generate_template(gui)),
            ("Backup Database", "Create a backup of the database (administrators)",
             lambda: create_backup(gui)),
            ("Undo Last Operation", "Undo the most recent batch operation you ran that can be "
                                    "undone", self.undo_last),
            ("Settings", "Configure batch operations settings",
             lambda: gui.more.SettingsDialog(gui)),
            ("System Logs", "The live application log, filtered (administrators)",
             lambda: show_logs(gui)),
            ("User Guide", "What each tab and card does", lambda: user_guide(gui))),
            columns=2)

    def refresh(self):
        pass

    def undo_last(self):
        job = _call(self.root, _app("batch_window").last_undoable, self.gui.viewer)
        if not isinstance(job, dict):
            messagebox.showinfo(TITLE, "You have no finished import that can still be undone.",
                                parent=self.root)
            return
        if messagebox.askyesno(TITLE, f"Undo job #{job['id']} ({job['kind']}, {job['total']} "
                                      f"row(s), {job['started_at']})?", parent=self.root):
            self.gui.tabs["History"].undo(job["id"])


# ── User Operations ─────────────────────────────────────────────────────


class UserOperationsTab:
    """Bulk User Creation, Bulk Permission Updates, Batch Course Enrollment,
    Send Email Campaign."""

    def __init__(self, gui):
        self.gui, self.root = gui, gui.root
        self.frame = tab = ttk.Frame(gui.notebook)
        gui.notebook.add(tab, text="User Operations")
        _header(tab, "Batch User Operations")
        option_cards(tab, (
            ("Bulk User Creation", "Create staff accounts from a CSV file; each person gets an "
                                   "activation e-mail (students' sign-ins come with the student "
                                   "import)", self.bulk_users),
            ("Bulk Permission Updates", "Grant or revoke permissions for a role, typed or from "
                                        "a CSV list (administrators)", self.focus_roles),
            ("Batch Course Enrollment", "Enrol students on modules from a CSV file, or choose "
                                        "students and a module on the Update tab",
             self.enrolment),
            ("Send Email Campaign", "Send a message to all students, all staff, a course or a "
                                    "list, through the outbox", self.focus_mail)), columns=4)
        panes = ttk.Frame(tab)
        panes.pack(fill=tk.BOTH, expand=True, padx=8)
        mail = ttk.LabelFrame(panes, text="E-mail campaign", padding=8)
        mail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        admin = _app("batch_admin")
        self.segment = ttk.Combobox(mail, state="readonly", width=34,
                                    values=list(admin.SEGMENTS.values()))
        self.segment.set(admin.SEGMENTS["students"])
        self.course = ttk.Combobox(mail, width=24, values=_call(
            self.root, _app("student_search").choices, "course") or [])
        self.addresses = ttk.Entry(mail, width=50)
        self.subject = ttk.Entry(mail, width=50)
        self.body = tk.Text(mail, width=60, height=6)
        for r, (label, widget) in enumerate((("Send to", self.segment),
                                             ("Course (for a course)", self.course),
                                             ("Addresses (for a list)", self.addresses),
                                             ("Subject", self.subject), ("Message", self.body))):
            ttk.Label(mail, text=label).grid(row=r, column=0, sticky="nw", pady=2)
            widget.grid(row=r, column=1, sticky="w", pady=2)
        bar = ttk.Frame(mail)
        bar.grid(row=5, column=1, sticky="w", pady=4)
        ttk.Button(bar, text="Preview recipients", command=self.preview).pack(side=tk.LEFT)
        ttk.Button(bar, text="Send", command=self.send).pack(side=tk.LEFT, padx=4)
        ttk.Label(mail, foreground="#555555", wraplength=520, text=(
            "Unsubscribes are respected and the send is audited. Bulk e-mail needs the bulk "
            "sender or e-mail administrator role.")).grid(row=6, column=0, columnspan=2,
                                                         sticky="w")
        roles = ttk.LabelFrame(panes, text="Role permissions in bulk (administrators)",
                               padding=8)
        roles.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
        pm = getattr(gui.auth, "permission_manager", None)
        role_names = [r.get("role_name") for r in (pm.list_roles() if pm else [])]
        self.role = ttk.Combobox(roles, state="readonly", width=24, values=role_names)
        self.permissions = tk.Text(roles, width=44, height=8)
        ttk.Label(roles, text="Role").grid(row=0, column=0, sticky="w")
        self.role.grid(row=0, column=1, sticky="w", pady=2)
        ttk.Label(roles, text="Permissions\n(one per line)").grid(row=1, column=0, sticky="nw")
        self.permissions.grid(row=1, column=1, sticky="w", pady=2)
        bar = ttk.Frame(roles)
        bar.grid(row=2, column=1, sticky="w", pady=4)
        for label, command in (("Load from file…", self.load_permissions),
                               ("Grant to role", lambda: self.apply(True)),
                               ("Revoke from role", lambda: self.apply(False))):
            ttk.Button(bar, text=label, command=command,
                       state="normal" if pm and _admin(gui) else "disabled").pack(
                side=tk.LEFT, padx=2)

    def refresh(self):
        pass

    def bulk_users(self):
        self.gui.kind.set("Staff accounts")
        self.gui._load_mappings()
        self.gui.new_import()

    def enrolment(self):
        self.gui.kind.set("Module enrolments")
        self.gui._load_mappings()
        self.gui.new_import()

    def focus_roles(self):
        self.role.focus_set()

    def focus_mail(self):
        self.subject.focus_set()

    def _segment(self):
        admin = _app("batch_admin")
        return {v: k for k, v in admin.SEGMENTS.items()}[self.segment.get()]

    def preview(self):
        found = _call(self.root, _app("batch_admin").campaign_preview, self._segment(),
                      self.course.get().strip() or None, self.addresses.get())
        if isinstance(found, dict):
            sample = "\n".join(found["sample"])
            messagebox.showinfo(TITLE, f"{found['count']} recipient(s).\n\n{sample}"
                                + ("\n…" if found["count"] > len(found["sample"]) else ""),
                                parent=self.root)

    def send(self):
        user = getattr(self.gui.auth, "current_user", None) or {}
        body = self.body.get("1.0", tk.END).strip()
        if not messagebox.askyesno(TITLE, f"Send '{self.subject.get()}' to "
                                          f"{self.segment.get().lower()}?", parent=self.root):
            return
        result = _call(self.root, _app("batch_admin").campaign, user.get("username") or "",
                       user.get("role") or "", segment=self._segment(),
                       subject=self.subject.get(), body=body,
                       course=self.course.get().strip() or None,
                       addresses=self.addresses.get(), write=True)
        if isinstance(result, dict):
            try:
                from education_system.systems.university.infrastructure.email import (
                    outbox_delivery,
                )
                outbox_delivery.kick()
            except Exception:
                pass
            messagebox.showinfo(TITLE, f"{result['recipients']} recipient(s): "
                                       f"{result['queued']} queued, {result['stored']} kept "
                                       f"in-app only, {result['suppressed']} not sent "
                                       "(unsubscribed or blocked).", parent=self.root)

    def load_permissions(self):
        path = filedialog.askopenfilename(parent=self.root)
        names = path and _guard(self.root, _app("batch_admin").read_permission_list, path)
        if names:
            self.permissions.delete("1.0", tk.END)
            self.permissions.insert("1.0", "\n".join(names))

    def apply(self, grant):
        names = self.permissions.get("1.0", tk.END).split()
        role = self.role.get()
        if not role or not names:
            messagebox.showinfo(TITLE, "Choose the role and list the permissions.",
                                parent=self.root)
            return
        if not messagebox.askyesno(TITLE, f"{'Grant' if grant else 'Revoke'} {len(names)} "
                                          f"permission(s) {'to' if grant else 'from'} {role}?",
                                   parent=self.root):
            return
        result = _guard(self.root, _app("batch_admin").apply_role_permissions,
                        getattr(self.gui.auth, "permission_manager", None), role, names, grant)
        if isinstance(result, dict):
            parts = [f"{len(result['changed'])} changed"]
            if result["unknown"]:
                parts.append("unknown: " + ", ".join(result["unknown"]))
            if result["refused"]:
                parts.append("refused: " + ", ".join(result["refused"]))
            messagebox.showinfo(TITLE, "; ".join(parts), parent=self.root)
