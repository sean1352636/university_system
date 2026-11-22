"""Advanced Search window: find students by any combination of conditions,
open, export or act on the matches, save searches (optionally shared) and
schedule reports from them.

Rules live in ``university/application``: ``student_search`` (fields,
permissions, paging, export, audit), ``student_search_saved`` (saved
searches, ready-made searches, summaries, scheduled reports) and
``student_bulk_actions``. This module only presents them; the reports,
follow-ups, favourites, history, groups, email lists and export dialog are
in ``advanced_search_tools``. The classic layout — the left menu of every
feature in nine groups, the Dashboard and Output tabs, the results'
right-click menu and student details — is in ``advanced_search_classic``,
and the windows it opens (demographics, predictive, analytics, import /
export, smart and admin features, permissions…) in
``advanced_search_windows``.
"""

from __future__ import annotations

import logging
import tkinter as tk
from contextlib import closing
from tkinter import filedialog, messagebox, scrolledtext, ttk

logger = logging.getLogger(__name__)
TITLE = "Advanced Search"
MAX_CONDITIONS = 8


def _search():
    from education_system.systems.university.application.students import search as student_search
    return student_search


def _saved():
    from education_system.systems.university.application.students import (
        search_saved as student_search_saved,
    )
    return student_search_saved


def _bulk():
    from education_system.systems.university.application.students import (
        bulk_actions as student_bulk_actions,
    )
    return student_bulk_actions


def _classic():
    from education_system.systems.university.domains.learners.interfaces.gui.students import (
        advanced_search_classic,
    )
    return advanced_search_classic


def _tools():
    from education_system.systems.university.domains.learners.interfaces.gui.students import (
        advanced_search_tools,
    )
    return advanced_search_tools


def _call(parent, fn, *args, write=False, **kwargs):
    """Run a rule on its own connection; a refusal becomes a dialog (None)."""
    from education_system.systems.university.infrastructure.database.db import get_connection
    try:
        with closing(get_connection(row_factory=False)) as conn:
            result = fn(conn, *args, **kwargs)
            if write:
                conn.commit()
    except ValueError as exc:
        messagebox.showerror(TITLE, str(exc), parent=parent)
        return None
    except Exception as exc:
        logger.exception("advanced search action failed")
        messagebox.showerror(TITLE, f"That did not work: {exc}", parent=parent)
        return None
    emails = result.get("emails") if isinstance(result, dict) else None
    if write and emails:
        from education_system.systems.university.application.teaching import (
            occurrences as timetable_occurrences,
        )
        timetable_occurrences.send_emails(emails)
    return True if result is None else result


def _tree(parent, columns, widths, height=12):
    frame = ttk.Frame(parent)
    frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
    view = ttk.Treeview(frame, columns=[c for c, _h in columns], show="headings", height=height)
    for (key, title), width in zip(columns, widths):
        view.heading(key, text=title)
        view.column(key, width=width, anchor="w")
    yscroll = ttk.Scrollbar(frame, orient="vertical", command=view.yview)
    view.configure(yscrollcommand=yscroll.set)
    yscroll.pack(side=tk.RIGHT, fill=tk.Y)
    view.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    return view


def _viewer(auth):
    user = getattr(auth, "current_user", None) or {}
    if not isinstance(user, dict):
        user = {"username": getattr(user, "username", ""), "role": getattr(user, "role", "")}
    check = getattr(auth, "check_permission", None) or getattr(auth, "has_permission", None) \
        or (lambda _p: False)
    return _search().Viewer.from_check(user.get("username") or "", user.get("role") or "",
                                       check, user.get("student_id") or user.get("username"))


class _ConditionRow:
    """One condition: field, operator and value (a list for choice fields)."""

    def __init__(self, owner, parent, on_remove):
        self.owner = owner
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill=tk.X, pady=1)
        labels = [f.label for f in owner.fields]
        self.field = ttk.Combobox(self.frame, values=labels, state="readonly", width=22)
        self.field.pack(side=tk.LEFT)
        self.op = ttk.Combobox(self.frame, state="readonly", width=16)
        self.op.pack(side=tk.LEFT, padx=4)
        self.value = ttk.Combobox(self.frame, width=34)
        self.value.pack(side=tk.LEFT)
        ttk.Button(self.frame, text="✕", width=3,
                   command=lambda: on_remove(self)).pack(side=tk.LEFT, padx=4)
        self.field.bind("<<ComboboxSelected>>", lambda _e: self._on_field())

    def _field(self):
        return next((f for f in self.owner.fields if f.label == self.field.get()), None)

    def _on_field(self):
        f = self._field()
        if not f:
            return
        ops = _search().OPS[f.kind]
        self.op.configure(values=ops)
        self.op.set(ops[0])
        values = _call(self.owner.master, _search().choices, f.key) if f.kind == "choice" else []
        self.value.configure(values=values or [])
        self.value.set("")

    def set(self, cond):
        f = _search().FIELDS.get(cond.get("field"))
        if f and f in self.owner.fields:
            self.field.set(f.label)
            self._on_field()
            self.op.set(cond.get("op") or "")
            self.value.set(cond.get("value") or "")

    def get(self):
        f = self._field()
        if not f:
            return None
        return {"field": f.key, "op": self.op.get(), "value": self.value.get().strip()}


class AdvancedSearchGUI:
    def __init__(self, master, auth=None, open_student=None):
        self.master = master
        self.auth = auth
        self.open_student = open_student
        self.viewer = _viewer(auth)
        self.fields = _search().fields_for(self.viewer)
        self.columns = _search().columns_for(self.viewer)
        self.rows: list[_ConditionRow] = []
        self.state = {"page": 0, "size": 50, "sort": "name", "total": 0, "criteria": {}}
        self.output = None
        self.status_var = None
        classic = _classic()
        notebook = classic.build_frame(self, master)
        self.dashboard = classic.DashboardTab(self, notebook)
        self._build_search(notebook)
        self._build_saved(notebook)
        self._build_schedules(notebook)
        if self.viewer.role in _search().ADMIN_ROLES:
            self._build_audit(notebook)
        _tools().attach(self, notebook)
        self.output = classic.OutputTab(self, notebook)
        classic.attach_context_menu(self)
        due = _call(master, _saved().run_due, self._reports_dir(), write=True)
        self.log(f"Advanced Search opened by {self.viewer.username or 'nobody'}"
                 + (f"; scheduled reports run: {due}" if isinstance(due, dict) else ""))

    def log(self, message):
        """A line in the Output tab and the status bar."""
        if self.output is not None:
            self.output.write(message)
        if self.status_var is not None:
            self.status_var.set(message)

    @staticmethod
    def _reports_dir():
        from education_system.paths import UNIVERSITY_EXPORTS_DIR
        return str(UNIVERSITY_EXPORTS_DIR / "student_reports")

    # ------------------------------------------------------------------
    # Search tab
    # ------------------------------------------------------------------
    def _build_search(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="🔍 Search & Results")
        top = ttk.Frame(tab, padding=(6, 6, 6, 0))
        top.pack(fill=tk.X)
        ttk.Label(top, text="Find").pack(side=tk.LEFT)
        self.text = ttk.Entry(top, width=26)
        self.text.pack(side=tk.LEFT, padx=4)
        self.text.bind("<Return>", lambda _e: self.run_search())
        self.all_fields = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="in all fields", variable=self.all_fields).pack(side=tk.LEFT)
        ttk.Label(top, text="Ready-made").pack(side=tk.LEFT, padx=(10, 4))
        self.preset = ttk.Combobox(top, values=list(_saved().PRESETS), state="readonly", width=30)
        self.preset.pack(side=tk.LEFT)
        self.preset.bind("<<ComboboxSelected>>",
                         lambda _e: self.load_criteria(_saved().PRESETS[self.preset.get()]))
        self.match = tk.StringVar(value="all")
        ttk.Radiobutton(top, text="match all", variable=self.match, value="all").pack(
            side=tk.LEFT, padx=(10, 0))
        ttk.Radiobutton(top, text="any", variable=self.match, value="any").pack(side=tk.LEFT)
        bar = ttk.Frame(tab, padding=(6, 4))
        bar.pack(fill=tk.X)
        for label, command in (("Add condition", self.add_row), ("Clear", self.clear),
                               ("Search", self.run_search)):
            ttk.Button(bar, text=label, command=command).pack(side=tk.LEFT, padx=2)
        self.conditions = ttk.Frame(tab, padding=(6, 0))
        self.conditions.pack(fill=tk.X)
        self._build_results(tab)
        self.add_row()

    def _build_results(self, tab):
        # Action bar and pager are packed (at the bottom) BEFORE the list so
        # a short window squeezes the list, never the buttons.
        pager = ttk.Frame(tab, padding=(6, 2))
        pager.pack(side=tk.BOTTOM, fill=tk.X)
        self.prev = ttk.Button(pager, text="◀ Prev", width=8, command=lambda: self._page(-1))
        self.prev.pack(side=tk.LEFT)
        self.next = ttk.Button(pager, text="Next ▶", width=8, command=lambda: self._page(1))
        self.next.pack(side=tk.LEFT, padx=4)
        self.page_label = ttk.Label(pager, text="")
        self.page_label.pack(side=tk.LEFT, padx=8)
        self.size = ttk.Combobox(pager, values=[str(s) for s in _search().PAGE_SIZES],
                                 state="readonly", width=5)
        self.size.set("50")
        self.size.pack(side=tk.RIGHT)
        self.size.bind("<<ComboboxSelected>>", lambda _e: self._resize())
        ttk.Label(pager, text="Rows per page").pack(side=tk.RIGHT, padx=4)
        actions = ttk.Frame(tab, padding=(6, 2))
        actions.pack(side=tk.BOTTOM, fill=tk.X)
        buttons = [("Student details…", lambda: _classic().open_details(self)),
                   ("Open student", self.open_selected), ("Summary", self.show_summary),
                   ("Chart…", self.show_chart), ("Save search…", self.save_search)]
        if self.viewer.can_export:
            buttons.append(("Export…", self.export))
        if self.viewer.can_update or self.viewer.can_withdraw:
            buttons.append(("Bulk action…", self.bulk_dialog))
        for label, command in buttons:
            ttk.Button(actions, text=label, command=command).pack(side=tk.LEFT, padx=2)
        more = ttk.Button(actions, text="More ▾")
        more.configure(command=lambda: _tools().more_menu(self, more))
        more.pack(side=tk.LEFT, padx=2)
        self.tree = _tree(tab, [(f.key, f.label) for f in self.columns],
                          [90 if f.key not in ("name", "email_address") else 170
                           for f in self.columns], height=14)
        self.tree.configure(selectmode="extended")
        for f in self.columns:
            self.tree.heading(f.key, command=lambda k=f.key: self._sort(k))
        self.tree.bind("<Double-1>", lambda _e: _classic().open_details(self))

    def add_row(self):
        if len(self.rows) >= MAX_CONDITIONS:
            return
        self.rows.append(_ConditionRow(self, self.conditions, self._remove_row))

    def _remove_row(self, row):
        row.frame.destroy()
        self.rows.remove(row)

    def clear(self):
        for row in list(self.rows):
            self._remove_row(row)
        self.text.delete(0, tk.END)
        self.preset.set("")
        self.add_row()

    def load_criteria(self, criteria):
        for row in list(self.rows):
            self._remove_row(row)
        for cond in criteria.get("conditions") or []:
            self.add_row()
            self.rows[-1].set(cond)
        if not self.rows:
            self.add_row()
        self.match.set(criteria.get("match") or "all")
        self.text.delete(0, tk.END)
        self.text.insert(0, criteria.get("text") or "")
        self.all_fields.set(bool(criteria.get("all_fields")))
        self.run_search()

    def criteria(self):
        return {"match": self.match.get(), "text": self.text.get().strip(),
                "all_fields": bool(self.all_fields.get()),
                "conditions": [c for c in (r.get() for r in self.rows) if c]}

    def run_search(self):
        self.state.update(page=0, criteria=self.criteria())
        self._load()

    def refresh_data(self):
        """Re-run the current search (called after student changes)."""
        try:
            if self.master.winfo_exists():
                self._load(audit=False)
        except tk.TclError:
            pass

    def _load(self, audit=True):
        result = _call(self.master, _search().search, self.state["criteria"], self.viewer,
                       sort=self.state["sort"], page=self.state["page"],
                       page_size=self.state["size"], audit=audit, write=audit)
        if not isinstance(result, dict):
            return
        self.state["total"] = result["total"]
        self.tree.delete(*self.tree.get_children())
        for row in result["rows"]:
            self.tree.insert("", "end", iid=str(row["student_id"]),
                             values=[("" if row.get(f.key) is None else row.get(f.key))
                                     for f in self.columns])
        pages = max(1, -(-result["total"] // self.state["size"]))
        if audit:
            self.log(f"Search: {_search().describe(self.state['criteria'])} → "
                     f"{result['total']} student(s)")
        self.page_label.configure(text=f"{result['total']} student(s) · page "
                                       f"{self.state['page'] + 1} of {pages}")
        self.prev.state(["!disabled"] if self.state["page"] > 0 else ["disabled"])
        self.next.state(["!disabled"] if self.state["page"] + 1 < pages else ["disabled"])

    def _page(self, delta):
        self.state["page"] = max(0, self.state["page"] + delta)
        self._load(audit=False)

    def _resize(self):
        self.state.update(size=int(self.size.get()), page=0)
        self._load(audit=False)

    def _sort(self, key):
        current, _, direction = self.state["sort"].partition(" ")
        self.state["sort"] = f"{key} desc" if current == key and direction != "desc" else key
        self._load(audit=False)

    def selected_ids(self):
        return list(self.tree.selection())

    def open_selected(self):
        ids = self.selected_ids()
        if not ids:
            messagebox.showinfo(TITLE, "Select a student first.", parent=self.master)
            return
        if self.open_student:
            self.open_student(ids[0])
        else:
            messagebox.showinfo(TITLE, f"Open {ids[0]} from Student Records.", parent=self.master)

    def show_summary(self):
        crit = self.state["criteria"]
        result = _call(self.master, _saved().summary, crit, self.viewer)
        if isinstance(result, dict):
            _text_window(self.master, "Summary", _saved().summary_text("Search summary", crit,
                                                                       result))

    def show_chart(self):
        _ChartWindow(self)

    def export(self):
        """Every format, chosen fields, every match or the selected rows."""
        _tools().export_dialog(self)

    def save_search(self):
        from tkinter import simpledialog
        name = simpledialog.askstring(TITLE, "Name for this search:", parent=self.master)
        if not name:
            return
        shared = messagebox.askyesno(TITLE, "Share it with other staff?", parent=self.master)
        if _call(self.master, _saved().save, self.viewer, name, self.criteria(), shared,
                 write=True):
            self._load_saved()

    def bulk_dialog(self, ids=None):
        if not (self.viewer.can_update or self.viewer.can_withdraw):
            messagebox.showinfo(TITLE, "You do not have permission for bulk actions.",
                                parent=self.master)
            return None
        return _BulkDialog(self, ids)

    # ------------------------------------------------------------------
    # Saved searches tab
    # ------------------------------------------------------------------
    def _build_saved(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Saved searches")
        bar = ttk.Frame(tab, padding=6)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        for label, command in (("Run", self._run_saved), ("Share / unshare", self._share),
                               ("Delete", self._delete_saved),
                               ("Schedule a report…", self._schedule),
                               ("Export to file…", self._export_saved),
                               ("Import from file…", lambda: _tools().import_saved(self))):
            ttk.Button(bar, text=label, command=command).pack(side=tk.LEFT, padx=2)
        self.saved_tree = _tree(tab, [("name", "Name"), ("owner", "Owner"), ("shared", "Shared"),
                                      ("summary", "Search")], [180, 100, 70, 520])
        self.saved_tree.bind("<Double-1>", lambda _e: self._run_saved())
        self._load_saved()

    def _load_saved(self):
        self._saved_rows = {str(r["id"]): r for r in
                            _call(self.master, _saved().saved, self.viewer) or []}
        self.saved_tree.delete(*self.saved_tree.get_children())
        for iid, r in self._saved_rows.items():
            self.saved_tree.insert("", "end", iid=iid, values=(
                r["name"], r["owner"], "yes" if r["shared"] else "", r["summary"]))

    def _picked_saved(self):
        r = self._saved_rows.get((self.saved_tree.selection() or [""])[0])
        if not r:
            messagebox.showinfo(TITLE, "Select a saved search first.", parent=self.master)
        return r

    def _export_saved(self):
        r = self._picked_saved()
        if r:
            _tools().export_saved(self, r["id"], r["name"])

    def _run_saved(self):
        r = self._picked_saved()
        if r:
            self.load_criteria(r["criteria"])

    def _share(self):
        r = self._picked_saved()
        if r and _call(self.master, _saved().set_shared, self.viewer, r["id"], not r["shared"],
                       write=True):
            self._load_saved()

    def _delete_saved(self):
        r = self._picked_saved()
        if r and messagebox.askyesno(TITLE, f"Delete '{r['name']}' (and its scheduled "
                                     "reports)?", parent=self.master) and \
                _call(self.master, _saved().delete, self.viewer, r["id"], write=True):
            self._load_saved()
            self._load_schedules()

    def _schedule(self):
        from tkinter import simpledialog
        r = self._picked_saved()
        if not r:
            return
        frequency = simpledialog.askstring(TITLE, "How often? (daily, weekly or monthly)",
                                           initialvalue="weekly", parent=self.master)
        if not frequency:
            return
        recipients = simpledialog.askstring(TITLE, "Email the summary to (comma-separated):",
                                            parent=self.master)
        if recipients and _call(self.master, _saved().schedule, self.viewer, r["id"],
                                frequency.strip().lower(), recipients, write=True):
            self._load_schedules()

    # ------------------------------------------------------------------
    # Scheduled reports tab
    # ------------------------------------------------------------------
    def _build_schedules(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Scheduled reports")
        ttk.Label(tab, padding=6, wraplength=900, text=(
            "Reports run when staff open Advanced Search (there is no background scheduler). "
            "Each run saves the list as a CSV and emails the recipients a summary only.")
        ).pack(anchor="w")
        bar = ttk.Frame(tab, padding=6)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        for label, command in (("Run now", self._run_now), ("Pause / resume", self._pause),
                               ("Delete", self._delete_schedule)):
            ttk.Button(bar, text=label, command=command).pack(side=tk.LEFT, padx=2)
        self.schedule_tree = _tree(tab, [("name", "Report"), ("search", "Saved search"),
                                         ("freq", "How often"), ("to", "Recipients"),
                                         ("next", "Next run"), ("last", "Last result"),
                                         ("on", "Active")],
                                   [150, 140, 80, 200, 90, 220, 60])
        self._load_schedules()

    def _load_schedules(self):
        self._schedule_rows = {str(r["id"]): r for r in
                               _call(self.master, _saved().schedules, self.viewer) or []}
        self.schedule_tree.delete(*self.schedule_tree.get_children())
        for iid, r in self._schedule_rows.items():
            self.schedule_tree.insert("", "end", iid=iid, values=(
                r["name"], r["search_name"], r["frequency"], r["recipients"], r["next_run_on"],
                r["last_result"] or "", "yes" if r["active"] else "paused"))

    def _picked_schedule(self):
        r = self._schedule_rows.get((self.schedule_tree.selection() or [""])[0])
        if not r:
            messagebox.showinfo(TITLE, "Select a scheduled report first.", parent=self.master)
        return r

    def _run_now(self):
        r = self._picked_schedule()
        if not r:
            return
        result = _call(self.master, _saved().run_report, r, self._reports_dir(), write=True)
        if isinstance(result, dict):
            messagebox.showinfo(TITLE, f"{result['count']} student(s) saved to {result['file']}; "
                                f"summary sent to {len(result['emails'])} recipient(s).",
                                parent=self.master)
            self._load_schedules()

    def _pause(self):
        r = self._picked_schedule()
        if r and _call(self.master, _saved().set_active, self.viewer, r["id"], not r["active"],
                       write=True):
            self._load_schedules()

    def _delete_schedule(self):
        r = self._picked_schedule()
        if r and _call(self.master, _saved().remove_schedule, self.viewer, r["id"], write=True):
            self._load_schedules()

    # ------------------------------------------------------------------
    # Audit tab (admins)
    # ------------------------------------------------------------------
    def _build_audit(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Audit")
        bar = ttk.Frame(tab, padding=6)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(bar, text="Refresh", command=self._load_audit).pack(side=tk.LEFT)
        self.audit_tree = _tree(tab, [("at", "When"), ("who", "Who"), ("what", "Action"),
                                      ("n", "Students"), ("criteria", "Search"),
                                      ("detail", "Detail")],
                                [140, 90, 70, 70, 320, 300])
        self._load_audit()

    def _load_audit(self):
        self.audit_tree.delete(*self.audit_tree.get_children())
        for r in _call(self.master, _search().audit_tail, 300) or []:
            self.audit_tree.insert("", "end", iid=str(r["id"]), values=(
                r["at"], r["actor"], r["action"], r["count"] if r["count"] is not None else "",
                r["criteria"], r["detail"] or ""))


def _text_window(parent, title, text):
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("640x460")
    box = scrolledtext.ScrolledText(win, wrap="word")
    box.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
    box.insert("1.0", text)
    box.configure(state="disabled")


class _ChartWindow:
    """The current search's matches charted by one field. Drawn with
    matplotlib when it is installed (imported only here), otherwise as bars
    on a Tk canvas; either way the counts can be saved."""

    COLOURS = ("#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3", "#937860",
               "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD")

    def __init__(self, owner: AdvancedSearchGUI):
        self.owner = owner
        self.data = None
        self.figure = None
        self.fields = _saved().chart_fields(owner.viewer)
        win = self.win = tk.Toplevel(owner.master)
        win.title("Chart of search results")
        width = min(1000, win.winfo_screenwidth() - 60)
        height = min(680, win.winfo_screenheight() - 100)
        win.geometry(f"{width}x{height}")
        win.minsize(min(700, width), min(480, height))
        win.transient(owner.master)
        bar = ttk.Frame(win, padding=6)
        bar.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(bar, text="Chart by").pack(side=tk.LEFT)
        self.field = tk.StringVar(value=self.fields[0][1] if self.fields else "")
        box = ttk.Combobox(bar, textvariable=self.field, state="readonly", width=24,
                           values=[label for _k, label in self.fields])
        box.pack(side=tk.LEFT, padx=4)
        box.bind("<<ComboboxSelected>>", lambda _e: self.draw())
        ttk.Button(bar, text="Save image…", command=self.save_image).pack(side=tk.RIGHT, padx=2)
        ttk.Button(bar, text="Save counts…", command=self.save_counts).pack(side=tk.RIGHT,
                                                                           padx=2)
        self.note = ttk.Label(win, text="", padding=(8, 0))
        self.note.pack(side=tk.BOTTOM, anchor="w")
        self.area = ttk.Frame(win)
        self.area.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        if not self.fields:
            ttk.Label(self.area, text="There is nothing you can chart these results by.").pack()
            return
        self.draw()

    def _key(self):
        return next((k for k, label in self.fields if label == self.field.get()), None)

    def draw(self):
        key = self._key()
        if not key:
            return
        data = _call(self.win, _saved().chart_data, self.owner.state["criteria"],
                     self.owner.viewer, key, write=True)
        if not isinstance(data, dict):
            return
        self.data = data
        for child in self.area.winfo_children():
            child.destroy()
        self.figure = None
        self.note.configure(text=f"{data['total']} student(s) matched"
                                 + (f"; {data['missing']} have no {data['label'].lower()}"
                                    if data["missing"] else ""))
        if not data["values"]:
            ttk.Label(self.area, text="No values to chart.").pack(pady=20)
            return
        try:
            self._draw_matplotlib(data)
        except ImportError:
            self._draw_canvas(data)

    def _draw_matplotlib(self, data):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure
        fig = Figure(figsize=(8, 5), dpi=100)
        ax = fig.add_subplot(111)
        labels, values = data["labels"], data["values"]
        kind = data["chart"]
        if kind == "pie" and len(values) <= 8:
            ax.pie(values, labels=labels, autopct="%1.0f%%", startangle=90,
                   colors=self.COLOURS[:len(values)])
            ax.axis("equal")
        elif kind == "line":
            ax.plot(labels, values, marker="o", color=self.COLOURS[0])
            ax.set_ylabel("Students registered")
            ax.tick_params(axis="x", rotation=45)
        elif kind == "histogram":
            ax.bar(labels, values, width=0.95, color=self.COLOURS[0])
            ax.set_xlabel(data["label"])
            ax.set_ylabel("Students")
            ax.tick_params(axis="x", rotation=45)
        else:
            ax.barh(labels[::-1], values[::-1], color=self.COLOURS[0])
            ax.set_xlabel("Students")
        ax.set_title(f"{data['label']} ({data['total']} students)")
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.area)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.figure = fig

    def _draw_canvas(self, data):
        canvas = tk.Canvas(self.area, background="white", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        self.win.update_idletasks()
        width = max(500, canvas.winfo_width())
        row = 24
        label_w = 190
        peak = max(data["values"]) or 1
        canvas.create_text(10, 12, anchor="w", font=("Segoe UI", 11, "bold"),
                           text=f"{data['label']} ({data['total']} students)")
        for i, (label, value) in enumerate(zip(data["labels"], data["values"])):
            y = 36 + i * row
            canvas.create_text(label_w - 6, y + row / 2, anchor="e", text=str(label)[:28])
            bar = (width - label_w - 60) * value / peak
            canvas.create_rectangle(label_w, y + 3, label_w + bar, y + row - 3,
                                    fill=self.COLOURS[i % len(self.COLOURS)], outline="")
            canvas.create_text(label_w + bar + 6, y + row / 2, anchor="w", text=str(value))
        canvas.configure(scrollregion=(0, 0, width, 50 + row * len(data["values"])))
        self.canvas = canvas

    def save_image(self):
        if not self.data:
            return
        if self.figure is None:
            path = filedialog.asksaveasfilename(parent=self.win, defaultextension=".eps",
                                                filetypes=[("PostScript", "*.eps")],
                                                initialfile=f"chart_{self.data['field']}.eps")
            if path:
                self.canvas.postscript(file=path)
                messagebox.showinfo(TITLE, f"Saved {path} (matplotlib is not installed, so "
                                    "PNG is not available).", parent=self.win)
            return
        path = filedialog.asksaveasfilename(parent=self.win, defaultextension=".png",
                                            filetypes=[("PNG image", "*.png")],
                                            initialfile=f"chart_{self.data['field']}.png")
        if path:
            self.figure.savefig(path, dpi=150)
            messagebox.showinfo(TITLE, f"Saved {path}.", parent=self.win)

    def save_counts(self):
        if not self.data:
            return
        path = filedialog.asksaveasfilename(parent=self.win, defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile=f"chart_{self.data['field']}.csv")
        if not path:
            return
        import csv
        with open(path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow([self.data["label"], "Students"])
            writer.writerows(zip(self.data["labels"], self.data["values"]))
        messagebox.showinfo(TITLE, f"Saved {path}.", parent=self.win)


class _BulkDialog:
    """Choose an action, its value and a reason; apply to the selected
    students or every match. Results are listed per student."""

    def __init__(self, owner: AdvancedSearchGUI, ids=None):
        self.owner = owner
        self.fixed_ids = list(ids) if ids else None
        bulk = _bulk()
        allowed = [k for k in bulk.ACTIONS if (owner.viewer.can_withdraw if k in (
            "withdraw", "reinstate") else owner.viewer.can_update)]
        self.win = win = tk.Toplevel(owner.master)
        win.title("Bulk action")
        body = ttk.Frame(win, padding=10)
        body.pack(fill=tk.BOTH, expand=True)
        self.action = ttk.Combobox(body, values=[bulk.ACTIONS[k] for k in allowed],
                                   state="readonly", width=34)
        self._keys = {bulk.ACTIONS[k]: k for k in allowed}
        self.value = ttk.Combobox(body, width=34)
        self.value2 = ttk.Combobox(body, width=34)
        self.reason = ttk.Entry(body, width=36)
        self.message = tk.Text(body, width=46, height=5, wrap="word")
        self.scope = tk.StringVar(value="selected")
        rows = (("Action", self.action), ("Value / subject", self.value), ("Then", self.value2),
                ("Reason *", self.reason), ("Message (email)", self.message))
        for row, (label, widget) in enumerate(rows):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="nw", pady=3)
            widget.grid(row=row, column=1, sticky="w", pady=3)
        count = len(self.fixed_ids or owner.selected_ids())
        ttk.Radiobutton(body, text=f"Selected students ({count})", variable=self.scope,
                        value="selected").grid(row=5, column=1, sticky="w")
        if not self.fixed_ids:
            ttk.Radiobutton(body, text=f"Every match ({owner.state['total']})",
                            variable=self.scope, value="all").grid(row=6, column=1, sticky="w")
        ttk.Button(body, text="Apply", command=self.apply).grid(row=7, column=1, sticky="w",
                                                                pady=8)
        self.action.bind("<<ComboboxSelected>>", lambda _e: self._on_action())

    def _key(self):
        return self._keys.get(self.action.get())

    def preselect(self, key):
        """Open with ``key`` (an ACTIONS key) chosen, when allowed."""
        label = _bulk().ACTIONS.get(key)
        if label in self._keys:
            self.action.set(label)
            self._on_action()

    def _on_action(self):
        from education_system.systems.university.application.students import (
            record_rules as student_record_rules,
        )
        key = self._key()
        self.value.set("")
        self.value2.set("")
        if key == "set_field":
            self.value.configure(values=list(_bulk().SETTABLE))
            self.value.bind("<<ComboboxSelected>>", lambda _e: self.value2.configure(
                values=list(student_record_rules.MODES if self.value.get() == "mode_of_study"
                            else student_record_rules.FEE_STATUSES)))
        elif key == "transfer":
            self.value.configure(values=_call(self.win, _search().choices, "course") or [])
        else:
            self.value.configure(values=[])

    def _value(self, key):
        if key == "set_field":
            return (self.value.get(), self.value2.get()) if self.value2.get() else None
        if key == "email":
            return self.message.get("1.0", "end-1c").strip()
        return self.value.get().strip() or None

    def apply(self):
        key = self._key()
        if not key:
            return
        ids = (self.fixed_ids or self.owner.selected_ids()) if self.scope.get() == "selected" \
            else _call(self.win, _search().all_ids, self.owner.state["criteria"],
                       self.owner.viewer)
        if not ids:
            messagebox.showinfo(TITLE, "No students to act on.", parent=self.win)
            return
        if not messagebox.askyesno(TITLE, f"{self.action.get()} for {len(ids)} student(s)?",
                                   parent=self.win):
            return
        try:
            result = _bulk().run(key, ids, self.owner.viewer, value=self._value(key),
                                 reason=self.reason.get(), subject=self.value.get())
        except ValueError as exc:
            messagebox.showerror(TITLE, str(exc), parent=self.win)
            return
        lines = [f"Done: {result['done']}"] + [f"{sid}: {why}" for sid, why in result["failed"]]
        self.owner.log(f"Bulk {self.action.get()}: {result['done']} done, "
                       f"{len(result['failed'])} failed")
        _text_window(self.win, "Bulk action result", "\n".join(lines))
        self.owner.refresh_data()
