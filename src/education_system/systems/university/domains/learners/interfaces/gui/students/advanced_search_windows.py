"""The windows the Advanced Search menu opens: the search shortcuts
(fuzzy name, module, date range, combined, conditional, the advanced text
search menu), saved search profiles, scheduled reports, import / export,
the smart and admin feature menus, role permissions and the system tools.
The analytics windows are in ``advanced_search_analytics``.

Rules: ``student_search*``, ``batch_imports`` / ``batch_enrolments`` (imports
through the student service, previewed first) and the platform
``PermissionManager`` (role permissions; per-user permission rows were never
read by sign-in, so they are not offered).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from education_system.systems.university.domains.learners.interfaces.gui.students.advanced_search import (  # noqa: E501
    TITLE, _call, _text_window, _tree,
)
from education_system.systems.university.domains.learners.interfaces.gui.students.advanced_search_analytics import (  # noqa: E501,F401
    AnalyticsDashboard, ComprehensiveReports, DemographicsWindow, PerformanceWindow,
    PredictiveWindow,
)


def _search():
    from education_system.systems.university.application.students import search as student_search
    return student_search


def _saved():
    from education_system.systems.university.application.students import (
        search_saved as student_search_saved,
    )
    return student_search_saved


def _insights():
    from education_system.systems.university.application.students import (
        search_insights as student_search_insights,
    )
    return student_search_insights


def _reports():
    from education_system.systems.university.application.students import (
        search_reports as student_search_reports,
    )
    return student_search_reports


def _tools():
    from education_system.systems.university.domains.learners.interfaces.gui.students import (
        advanced_search_tools,
    )
    return advanced_search_tools


def _classic():
    from education_system.systems.university.domains.learners.interfaces.gui.students import (
        advanced_search_classic,
    )
    return advanced_search_classic


def _form(parent, title, fields, note=None):
    """A small modal form; ``fields`` is ``[(key, label, values or None)]``.
    Returns ``{key: value}`` or ``None``."""
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent.winfo_toplevel())
    body = ttk.Frame(win, padding=10)
    body.pack(fill=tk.BOTH, expand=True)
    if note:
        ttk.Label(body, text=note, foreground="#555", wraplength=420).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
    widgets = {}
    for row, (key, label, values) in enumerate(fields, start=1):
        ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", pady=3)
        widget = ttk.Combobox(body, values=values, width=36) if values is not None \
            else ttk.Entry(body, width=38)
        widget.grid(row=row, column=1, sticky="w", pady=3)
        widgets[key] = widget
    result = {}

    def ok():
        result.update({k: w.get().strip() for k, w in widgets.items()})
        win.destroy()
    bar = ttk.Frame(body)
    bar.grid(row=len(fields) + 1, column=1, sticky="w", pady=8)
    ttk.Button(bar, text="OK", command=ok).pack(side=tk.LEFT)
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side=tk.LEFT, padx=4)
    win.grab_set()
    parent.wait_window(win)
    return result or None


def _run(gui, criteria, label):
    gui.load_criteria(criteria)
    _classic().show_tab(gui, "Search")
    gui.log(f"{label}: {_search().describe(criteria)}")


# ── search shortcuts ────────────────────────────────────────────────────


def quick_search(gui, kind):
    {"fuzzy": _fuzzy, "module": _module, "dates": _dates, "combined": _combined,
     "conditional": _conditional}[kind](gui)


def _fuzzy(gui):
    v = _form(gui.master, "Fuzzy name search", [("name", "Name (spelling may differ)", None)],
              "Finds names that sound alike or are spelt slightly differently.")
    if v and v["name"]:
        _run(gui, {"match": "all", "conditions": [
            {"field": "name", "op": "sounds like", "value": v["name"]}]}, "Fuzzy name search")


def _module(gui):
    codes = _call(gui.master, _insights().module_codes) or []
    v = _form(gui.master, "Module enrolment search",
              [("module", "Module code", codes), ("op", "Students who", ["has", "has not"])],
              "Students currently enrolled (or not) on a module.")
    if v and v["module"]:
        _run(gui, {"match": "all", "conditions": [
            {"field": "module", "op": v["op"] or "has", "value": v["module"]}]},
             "Module enrolment search")


def _dates(gui):
    fields = {"Registered": "registration"}
    if gui.viewer.can_view_sensitive:
        fields["Date of birth"] = "dob"
    v = _form(gui.master, "Date range search",
              [("field", "Date", list(fields)), ("from", "From (YYYY-MM-DD)", None),
               ("to", "To (YYYY-MM-DD)", None)], "Leave either end empty for an open range.")
    if not v or v["field"] not in fields or not (v["from"] or v["to"]):
        return
    key = fields[v["field"]]
    if v["from"] and v["to"]:
        cond = {"field": key, "op": "between", "value": f"{v['from']}, {v['to']}"}
    elif v["from"]:
        cond = {"field": key, "op": "after", "value": v["from"]}
    else:
        cond = {"field": key, "op": "before", "value": v["to"]}
    _run(gui, {"match": "all", "conditions": [cond]}, "Date range search")


def _combined(gui):
    courses = _call(gui.master, _search().choices, "course") or []
    statuses = _call(gui.master, _search().choices, "status") or []
    v = _form(gui.master, "Combined filters search",
              [("course", "Course", courses), ("status", "Status", statuses),
               ("year", "Year of study", ["1", "2", "3", "4", "5"]),
               ("mark", "Average mark below", None)], "Fill in any of the filters; all must match.")
    if not v:
        return
    conds = [c for c in (
        v["course"] and {"field": "course", "op": "is", "value": v["course"]},
        v["status"] and {"field": "status", "op": "is", "value": v["status"]},
        v["year"] and {"field": "year_of_study", "op": "=", "value": v["year"]},
        v["mark"] and {"field": "average_mark", "op": "<", "value": v["mark"]}) if c]
    if conds:
        _run(gui, {"match": "all", "conditions": conds}, "Combined filters search")


def _conditional(gui):
    _classic().show_tab(gui, "Search")
    gui.match.set("any")
    messagebox.showinfo(TITLE, (
        "Conditional logic: add a condition per line, then choose 'match all' (AND — every "
        "condition must hold) or 'any' (OR — at least one). 'Any' is selected now. Use "
        "'does not contain', 'is not' and 'has not' for NOT."), parent=gui.master)


class TextSearchMenu:
    OPTIONS = (("Regex Search", "matches regex", "A regular expression, e.g. ^S12"),
               ("Wildcard Search", "matches pattern", "* for any run of characters, ? for one"),
               ("Phonetic Search", "sounds like", "Names that sound alike (Soundex)"),
               ("Combined Text Search", "contains", "Words that must all appear"))

    def __init__(self, gui):
        self.gui = gui
        win = tk.Toplevel(gui.master)
        win.title("Advanced text search")
        body = ttk.Frame(win, padding=12)
        body.pack(fill=tk.BOTH, expand=True)
        ttk.Label(body, text="Text search options", font=("Segoe UI", 11, "bold")).pack(
            anchor="w", pady=(0, 6))
        for label, op, hint in self.OPTIONS:
            ttk.Button(body, text=label, width=30,
                       command=lambda o=op, h=hint, lb=label: self.run(o, h, lb)).pack(
                anchor="w", pady=2)
        ttk.Button(body, text="Search All Fields", width=30, command=self.all_fields).pack(
            anchor="w", pady=2)
        ttk.Button(body, text="❌ Close", command=win.destroy).pack(anchor="e", pady=(8, 0))
        self.win = win

    def run(self, op, hint, label):
        text_fields = [f.label for f in self.gui.fields if f.kind == "text"]
        v = _form(self.win, label, [("field", "Field", text_fields), ("value", "Value", None)],
                  hint)
        if not v or not v["field"] or not (v["value"] or op == "sounds like"):
            return
        key = next(f.key for f in self.gui.fields if f.label == v["field"])
        words = v["value"].split() if op == "contains" else [v["value"]]
        conds = [{"field": key, "op": op, "value": w} for w in words]
        _run(self.gui, {"match": "all", "conditions": conds}, label)

    def all_fields(self):
        text = simpledialog.askstring(TITLE, "Find in every field you may search:",
                                      parent=self.win)
        if text:
            _run(self.gui, {"match": "all", "conditions": [], "text": text,
                            "all_fields": True}, "Search all fields")


# ── saved search profiles, scheduled reports ────────────────────────────


class SearchProfilesWindow:
    def __init__(self, gui):
        self.gui = gui
        self.win = win = _tools()._toplevel(gui.master, "Saved search profiles", 900, 560)
        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        create = ttk.Frame(nb, padding=10)
        nb.add(create, text="Create Profile")
        ttk.Label(create, text="Current search:").grid(row=0, column=0, sticky="nw")
        ttk.Label(create, text=_search().describe(gui.criteria()), wraplength=600).grid(
            row=0, column=1, sticky="w")
        ttk.Label(create, text="Name").grid(row=1, column=0, sticky="w", pady=6)
        self.name = ttk.Entry(create, width=40)
        self.name.grid(row=1, column=1, sticky="w")
        self.shared = tk.BooleanVar(value=False)
        ttk.Checkbutton(create, text="Share with other staff", variable=self.shared).grid(
            row=2, column=1, sticky="w")
        ttk.Button(create, text="Save current search as a profile", command=self.save).grid(
            row=3, column=1, sticky="w", pady=8)
        listing = ttk.Frame(nb)
        nb.add(listing, text="Saved Profiles")
        bar = ttk.Frame(listing, padding=6)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        for label, command in (("Load", self.load_one), ("Share / unshare", self.share),
                               ("Delete", self.delete), ("Export…", self.export),
                               ("Import…", self.import_)):
            ttk.Button(bar, text=label, command=command).pack(side=tk.LEFT, padx=2)
        self.tree = _tree(listing, [("name", "Name"), ("owner", "Owner"), ("shared", "Shared"),
                                    ("summary", "Search")], [180, 100, 60, 480])
        self.tree.bind("<Double-1>", lambda _e: self.load_one())
        self.nb = nb
        self.refresh()

    def refresh(self):
        self.rows = {str(r["id"]): r for r in _call(self.win, _saved().saved,
                                                     self.gui.viewer) or []}
        self.tree.delete(*self.tree.get_children())
        for iid, r in self.rows.items():
            self.tree.insert("", "end", iid=iid, values=(r["name"], r["owner"],
                                                         "yes" if r["shared"] else "",
                                                         r["summary"]))
        self.gui._load_saved()

    def _picked(self):
        r = self.rows.get((self.tree.selection() or [""])[0])
        if not r:
            messagebox.showinfo(TITLE, "Select a profile first.", parent=self.win)
        return r

    def save(self):
        if _call(self.win, _saved().save, self.gui.viewer, self.name.get(), self.gui.criteria(),
                 self.shared.get(), write=True):
            self.gui.log(f"Saved profile '{self.name.get()}'")
            self.refresh()
            self.nb.select(1)

    def load_one(self):
        r = self._picked()
        if r:
            _run(self.gui, r["criteria"], f"Loaded profile '{r['name']}'")

    def share(self):
        r = self._picked()
        if r and _call(self.win, _saved().set_shared, self.gui.viewer, r["id"], not r["shared"],
                       write=True):
            self.refresh()

    def delete(self):
        r = self._picked()
        if r and messagebox.askyesno(TITLE, f"Delete '{r['name']}'?", parent=self.win) and \
                _call(self.win, _saved().delete, self.gui.viewer, r["id"], write=True):
            self.refresh()

    def export(self):
        r = self._picked()
        if r:
            _tools().export_saved(self.gui, r["id"], r["name"])

    def import_(self):
        _tools().import_saved(self.gui)
        self.refresh()


class ScheduledReportsWindow:
    def __init__(self, gui):
        self.gui = gui
        if not gui.viewer.can_export:
            messagebox.showinfo(TITLE, "Scheduled reports need permission to export.",
                                parent=gui.master)
            return
        self.win = win = _tools()._toplevel(gui.master, "Scheduled reports", 960, 560)
        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        create = ttk.Frame(nb, padding=10)
        nb.add(create, text="Create Report")
        self.saved = {r["name"]: r for r in _call(win, _saved().saved, gui.viewer) or []}
        widgets = (("search", "Saved search", list(self.saved)), ("name", "Report name", None),
                   ("frequency", "How often", ["daily", "weekly", "monthly"]),
                   ("recipients", "Email to (comma-separated)", None))
        self.inputs = {}
        for row, (key, label, values) in enumerate(widgets):
            ttk.Label(create, text=label).grid(row=row, column=0, sticky="w", pady=3)
            w = ttk.Combobox(create, values=values, width=40, state="readonly") if values \
                is not None else ttk.Entry(create, width=42)
            w.grid(row=row, column=1, sticky="w", pady=3)
            self.inputs[key] = w
        self.inputs["frequency"].set("weekly")
        ttk.Label(create, foreground="#555", wraplength=600, text=(
            "Each run saves the list as a CSV and emails the recipients a summary only (no "
            "student details). Save the search first on the Saved Profiles window.")).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Button(create, text="Create scheduled report", command=self.create).grid(
            row=5, column=1, sticky="w")
        listing = ttk.Frame(nb)
        nb.add(listing, text="Scheduled Reports")
        bar = ttk.Frame(listing, padding=6)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        for label, command in (("Run now", self.run_now), ("Pause / resume", self.pause),
                               ("Delete", self.delete), ("Refresh", self.refresh)):
            ttk.Button(bar, text=label, command=command).pack(side=tk.LEFT, padx=2)
        self.tree = _tree(listing, [("name", "Report"), ("search", "Saved search"),
                                    ("freq", "How often"), ("to", "Recipients"),
                                    ("next", "Next run"), ("last", "Last result"),
                                    ("on", "Active")], [150, 140, 80, 200, 90, 200, 60])
        self.nb = nb
        self.refresh()

    def refresh(self):
        self.rows = {str(r["id"]): r for r in _call(self.win, _saved().schedules,
                                                     self.gui.viewer) or []}
        self.tree.delete(*self.tree.get_children())
        for iid, r in self.rows.items():
            self.tree.insert("", "end", iid=iid, values=(
                r["name"], r["search_name"], r["frequency"], r["recipients"], r["next_run_on"],
                r["last_result"] or "", "yes" if r["active"] else "paused"))
        self.gui._load_schedules()

    def create(self):
        picked = self.saved.get(self.inputs["search"].get())
        if not picked:
            messagebox.showinfo(TITLE, "Choose a saved search.", parent=self.win)
            return
        if _call(self.win, _saved().schedule, self.gui.viewer, picked["id"],
                 self.inputs["frequency"].get(), self.inputs["recipients"].get(),
                 name=self.inputs["name"].get() or None, write=True):
            self.gui.log(f"Scheduled report on '{picked['name']}' created")
            self.refresh()
            self.nb.select(1)

    def _picked(self):
        r = self.rows.get((self.tree.selection() or [""])[0])
        if not r:
            messagebox.showinfo(TITLE, "Select a scheduled report first.", parent=self.win)
        return r

    def run_now(self):
        r = self._picked()
        result = r and _call(self.win, _saved().run_report, r, self.gui._reports_dir(),
                             write=True)
        if isinstance(result, dict):
            messagebox.showinfo(TITLE, f"{result['count']} student(s) saved to "
                                       f"{result['file']}.", parent=self.win)
            self.refresh()

    def pause(self):
        r = self._picked()
        if r and _call(self.win, _saved().set_active, self.gui.viewer, r["id"],
                       not r["active"], write=True):
            self.refresh()

    def delete(self):
        r = self._picked()
        if r and _call(self.win, _saved().remove_schedule, self.gui.viewer, r["id"],
                       write=True):
            self.refresh()


# ── import / export ─────────────────────────────────────────────────────


class ImportExportWindow:
    def __init__(self, gui):
        self.gui = gui
        self.win = win = tk.Toplevel(gui.master)
        win.title("Import / export")
        body = ttk.Frame(win, padding=12)
        body.pack(fill=tk.BOTH, expand=True)
        imp = ttk.LabelFrame(body, text="Import options", padding=8)
        imp.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        for label, command in (("Import students (CSV / JSON / Excel)…",
                                lambda: self.import_file("students")),
                               ("Import module enrolments…",
                                lambda: self.import_file("enrolments")),
                               ("Import a saved search…", lambda: _tools().import_saved(gui))):
            ttk.Button(imp, text=label, width=36, command=command).pack(anchor="w", pady=2)
        ttk.Label(imp, foreground="#555", wraplength=280, text=(
            "Every import is previewed first and runs through the student service as an "
            "undoable job (Batch Operations → Jobs).")).pack(anchor="w", pady=6)
        exp = ttk.LabelFrame(body, text="Export options", padding=8)
        exp.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        for label, command in (("Export students…", gui.export),
                               ("Export modules…", self.export_modules),
                               ("Export analytics…", lambda: self.export_report(
                                   "search_activity" if self._admin() else "demographics")),
                               ("Export statistics…", lambda: self.export_report(
                                   "system" if self._admin() else "student_summary"))):
            ttk.Button(exp, text=label, width=30, command=command).pack(anchor="w", pady=2)
        ttk.Button(body, text="Close", command=win.destroy).pack(side=tk.BOTTOM, anchor="e")

    def _admin(self):
        return self.gui.viewer.role in _search().ADMIN_ROLES

    def import_file(self, kind):
        from education_system.systems.university.application.batch import imports as batch_imports
        path = filedialog.askopenfilename(parent=self.win, filetypes=[
            ("Data files", "*.csv *.json *.xlsx"), ("All files", "*.*")])
        if not path:
            return
        try:
            rows, _mapping = batch_imports.read_and_map(path, kind)
        except (ValueError, OSError) as exc:
            messagebox.showerror(TITLE, str(exc), parent=self.win)
            return
        reason = simpledialog.askstring(TITLE, "Reason (recorded on every change):",
                                        parent=self.win)
        if not reason:
            return
        run = self._runner(kind, rows, reason, path)
        preview = self._safe(run, True)
        if not isinstance(preview, dict):
            return
        counts = ", ".join(f"{k} {v}" for k, v in preview["counts"].items()) or "nothing"
        if not messagebox.askyesno(TITLE, f"Preview of {len(rows)} row(s): {counts}.\n\n"
                                          "Import now?", parent=self.win):
            return
        done = self._safe(run, False)
        if isinstance(done, dict):
            lines = [f"Job {done['job_id']}: " + ", ".join(f"{k} {v}" for k, v in
                                                           done["counts"].items())]
            lines += [f"row {r['row_no']}: {r['action']} {r['message'] or ''}"
                      for r in done["rows"]]
            _text_window(self.win, "Import result", "\n".join(lines))
            self.gui.log(f"Imported {kind} from {path}: {done['counts']}")
            self.gui.refresh_data()

    def _runner(self, kind, rows, reason, path):
        viewer = self.gui.viewer
        if kind == "enrolments":
            from education_system.systems.university.application.batch import (
                enrolments as batch_enrolments,
            )
            return lambda dry: batch_enrolments.import_enrolments(
                rows, viewer, reason=reason, source=path, dry_run=dry)
        from education_system.systems.university.application.batch import imports as batch_imports
        return lambda dry: batch_imports.import_students(
            rows, viewer, mode="both", reason=reason, source=path, dry_run=dry,
            auth=self.gui.auth)

    def _safe(self, run, dry):
        try:
            return run(dry)
        except ValueError as exc:
            messagebox.showerror(TITLE, str(exc), parent=self.win)
            return None

    def export_modules(self):
        if not self.gui.viewer.can_export:
            messagebox.showerror(TITLE, "You do not have permission to export.", parent=self.win)
            return
        found = _call(self.win, _insights().modules_table, self.gui.viewer, write=True)
        if not isinstance(found, tuple):
            return
        columns, rows = found
        report = {"title": "Module catalogue", "columns": columns, "rows": rows,
                  "labels": {c: c.replace("_", " ").capitalize() for c in columns}}
        _tools().export_report(self.gui, report, self.win)

    def export_report(self, name):
        if not self.gui.viewer.can_export or not self.gui.viewer.can_view_all:
            messagebox.showerror(TITLE, "You do not have permission to export reports.",
                                 parent=self.win)
            return
        report = _call(self.win, _reports().generate, name, {}, self.gui.viewer, write=True)
        if isinstance(report, dict):
            _tools().export_report(self.gui, report, self.win)


# ── smart and admin feature menus ───────────────────────────────────────


def _menu(gui, title, items):
    win = tk.Toplevel(gui.master)
    win.title(title)
    body = ttk.Frame(win, padding=12)
    body.pack(fill=tk.BOTH, expand=True)
    ttk.Label(body, text=title, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))
    for label, command in items:
        ttk.Button(body, text=label, width=32, command=command).pack(anchor="w", pady=2)
    ttk.Button(body, text="❌ Close", command=win.destroy).pack(anchor="e", pady=(8, 0))
    return win


def SmartFeaturesMenu(gui):  # noqa: N802 - opened like the other windows
    def autocomplete():
        _classic().show_tab(gui, "Search")
        gui.text.focus_set()
        messagebox.showinfo(TITLE, "Start typing in the Find box: names, student IDs and "
                                   "emails you may see are suggested as you type.",
                            parent=gui.master)
    return _menu(gui, "Smart features", [
        ("Auto-complete", autocomplete),
        ("Smart Suggestions", lambda: PredictiveWindow(gui, "Recommended")),
        ("Predictive Analytics", lambda: PredictiveWindow(gui)),
        ("Graduation Forecast", lambda: _report_window(gui, "completion")),
    ])


def AdminFeaturesMenu(gui):  # noqa: N802
    return _menu(gui, "Admin features", [
        ("Audit Trail", lambda: _classic().show_tab(gui, "Audit")),
        ("Scheduled Reports", lambda: ScheduledReportsWindow(gui)),
        ("Cache Management", lambda: system_action(gui, "cache")),
        ("System Maintenance", lambda: system_action(gui, "maintenance")),
        ("User Permissions", lambda: PermissionsWindow(gui)),
    ])


def _report_window(gui, name):
    if not gui.viewer.can_view_all:
        messagebox.showinfo(TITLE, "Reports are for staff who can search all students.",
                            parent=gui.master)
        return
    report = _call(gui.master, _reports().generate, name, gui.state["criteria"], gui.viewer,
                   write=True)
    if isinstance(report, dict):
        _tools().ReportWindow(gui, report)


# ── role permissions ────────────────────────────────────────────────────


class PermissionsWindow:
    """Role permissions through the platform PermissionManager."""

    def __init__(self, gui):
        self.gui = gui
        self.pm = getattr(gui.auth, "permission_manager", None)
        if not gui.viewer.can_manage_users or self.pm is None:
            messagebox.showinfo(TITLE, "Changing permissions is for administrators who manage "
                                       "users.", parent=gui.master)
            return
        self.win = win = _tools()._toplevel(gui.master, "User permissions (by role)", 900, 560)
        top = ttk.Frame(win, padding=6)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Role").pack(side=tk.LEFT)
        roles = [r.get("role_name") or r.get("name") for r in self.pm.list_roles() or []]
        self.role = ttk.Combobox(top, values=roles, state="readonly", width=24)
        self.role.pack(side=tk.LEFT, padx=4)
        self.role.bind("<<ComboboxSelected>>", lambda _e: self.load())
        ttk.Label(win, foreground="#555", padding=(6, 0), wraplength=860, text=(
            "People get their permissions from their role. Grant or revoke a permission for "
            "a role here; every change is logged by the permission manager.")).pack(anchor="w")
        bar = ttk.Frame(win, padding=6)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(bar, text="Grant selected →", command=lambda: self.change(True)).pack(
            side=tk.LEFT, padx=2)
        ttk.Button(bar, text="← Revoke selected", command=lambda: self.change(False)).pack(
            side=tk.LEFT, padx=2)
        ttk.Button(bar, text="Close", command=win.destroy).pack(side=tk.RIGHT)
        panes = ttk.Frame(win)
        panes.pack(fill=tk.BOTH, expand=True)
        left = ttk.LabelFrame(panes, text="All permissions", padding=4)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6)
        right = ttk.LabelFrame(panes, text="Current permissions of the role", padding=4)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6)
        self.all = tk.Listbox(left, selectmode="extended")
        self.all.pack(fill=tk.BOTH, expand=True)
        self.current = tk.Listbox(right, selectmode="extended")
        self.current.pack(fill=tk.BOTH, expand=True)
        for p in sorted((p.get("permission_name") or p.get("name") or "")
                        for p in self.pm.list_permissions() or []):
            self.all.insert(tk.END, p)
        if roles:
            self.role.set(roles[0])
            self.load()

    def load(self):
        self.current.delete(0, tk.END)
        for p in sorted(self.pm.get_role_permissions(self.role.get()) or []):
            self.current.insert(tk.END, p)

    def change(self, grant):
        from education_system.systems.university.application.batch import admin as batch_admin
        box = self.all if grant else self.current
        names = [box.get(i) for i in box.curselection()]
        if not names:
            messagebox.showinfo(TITLE, "Select permissions first.", parent=self.win)
            return
        if not messagebox.askyesno(TITLE, f"{'Grant' if grant else 'Revoke'} {len(names)} "
                                          f"permission(s) {'to' if grant else 'from'} "
                                          f"{self.role.get()}?", parent=self.win):
            return
        try:
            result = batch_admin.apply_role_permissions(self.pm, self.role.get(), names, grant)
        except ValueError as exc:
            messagebox.showerror(TITLE, str(exc), parent=self.win)
            return
        self.gui.log(f"Permissions {'granted' if grant else 'revoked'} for {self.role.get()}: "
                     f"{len(result['changed'])} changed")
        self.load()


# ── system tools ────────────────────────────────────────────────────────


def system_action(gui, kind):
    if kind in ("initialise", "status", "maintenance", "optimise", "cache") and \
            gui.viewer.role not in _search().ADMIN_ROLES:
        messagebox.showinfo(TITLE, "System tools are for administrators.", parent=gui.master)
        return
    if kind == "optimise":
        message = _call(gui.master, _reports().optimise, gui.viewer, write=True)
        if message:
            gui.log(message)
            messagebox.showinfo(TITLE, message, parent=gui.master)
        return
    if kind in ("initialise", "status"):
        apply = kind == "initialise"
        found = _call(gui.master, _insights().schema_status, gui.viewer, apply, write=apply)
        if not isinstance(found, dict):
            return
        lines = [f"{t['table']:<28} {'present' if t['present'] else 'MISSING':<8} "
                 f"{'' if t['rows'] is None else t['rows']}" for t in found["tables"]]
        stats = _call(gui.master, _reports().system_stats, gui.viewer) if not apply else None
        if isinstance(stats, dict):
            lines += ["", f"Database size: {stats['database_mb']} MB",
                      f"Integrity check: {stats['integrity']}"]
        _text_window(gui.master, "Database set up" if apply else "Database status",
                     "\n".join(lines))
        gui.log("Search tables set up" if apply else "Database status checked")
        return
    if kind == "cache":
        messagebox.showinfo(TITLE, (
            "Searches are no longer cached: every search reads the live records, so results "
            "are never stale and there is nothing to clear. 'System optimization' refreshes "
            "the database's query statistics instead."), parent=gui.master)
        return
    system_action(gui, "status")
    if messagebox.askyesno(TITLE, "Refresh the database's query statistics now?",
                           parent=gui.master):
        system_action(gui, "optimise")
