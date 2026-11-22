"""Audit Log screen.

Kept from the old Audit Reports window, in their places: Run Report
(Report drop-down, Run, Save snapshot, Export…, the filters and the
result), Saved Reports (New…, Edit…, Run, Delete, Refresh), Past Runs
(View, Delete, Refresh) and Overview (Refresh). New: Events - every trail
in one list (activity log + every ``*_audit`` table) with filters (From,
To, User, Action, Area / table, Target, Outcome, Text), Search, Clear,
paging, Detail… and Export CSV…; Failed / denied; Summary (by user, action,
area and outcome). Read-only; admin only. Searches run in the background
(``tk_threads``). Rules are in :mod:`modules.administration.domain.audit_log`.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui import tk_threads
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.administration.domain import audit_log as AL
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

_ERRORS = W.ERRORS
OUTCOMES = ("", "failed", "ok", "denied", "invalid", "error", "not_found", "not_built")
_EVENT_COLS = [("at", "Time", 145), ("source", "Trail", 120), ("user", "User", 90),
               ("action", "Action", 170), ("target", "Target", 110), ("outcome", "Outcome", 70),
               ("detail", "Detail", 360)]
_FILTERS = (("date_from", "From", 11), ("date_to", "To", 11), ("user", "User", 12),
            ("action", "Action", 16), ("area", "Area / table", 18), ("target", "Target", 12),
            ("outcome", "Outcome", 10), ("text", "Text", 14))


class AuditLogPage:
    TABS = ("Run Report", "Saved Reports", "Past Runs", "Overview", "Events",
            "Failed / denied", "Summary")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        activity_log.record("audit_log.open", outcome="ok" if AL.can_read(principal)
                            else "denied")
        ttk.Label(parent, text="Audit Log", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar(value="Read-only view of the activity log and every "
                                               "audit table. Reading it is itself logged.")
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        if not AL.can_read(principal):
            ttk.Label(parent, text="Only a system administrator can read the audit log.",
                      foreground="#a44").pack(anchor="w")
            return
        try:
            self.users, self.areas = AL.users(), AL.areas()
        except Exception:  # noqa: BLE001 - the drop-downs just start empty
            self.users, self.areas = [], [AL.ACTIVITY]
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        self.result: AL.ReportResult | None = None
        start = state.get("tab") if state.get("tab") in self.TABS else "Events"
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # ── helpers ──────────────────────────────────────────────────────

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, W.problems(e), parent=self._top())

    def _info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text, parent=self._top())

    def _bg(self, work: Callable[[], Any], done: Callable[[Any], None], title: str) -> None:
        """Run *work* off the main thread; *done(result)* back on it."""
        widget = self.parent

        def run() -> None:
            try:
                out = work()
            except Exception as e:  # noqa: BLE001 - shown to the user below
                tk_threads.ui(widget, self._bg_failed, title, e)
                return
            tk_threads.ui(widget, self._bg_done, done, out)
        tk_threads.start_thread(widget, run, name="secondary-audit-log")

    def _bg_done(self, done: Callable[[Any], None], out: Any) -> None:
        try:
            if self.parent.winfo_exists():
                done(out)
        except tk.TclError:
            pass

    def _bg_failed(self, title: str, e: Exception) -> None:
        try:
            if self.parent.winfo_exists():
                self._err(title, e)
        except tk.TclError:
            pass

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        build = {"Run Report": (self._build_run, None),
                 "Saved Reports": (self._build_saved, self.refresh_saved),
                 "Past Runs": (self._build_runs, self.refresh_runs),
                 "Overview": (self._build_overview, self.refresh_overview),
                 "Events": (self._build_events, None),
                 "Failed / denied": (self._build_failed, None),
                 "Summary": (self._build_summary, self.refresh_summary)}[name]
        if name not in self._built:
            self._built.add(name)
            build[0](self.tabs[name])
            if name in ("Events", "Failed / denied"):
                self.search(name)
        if build[1]:
            build[1]()

    def _filter_bar(self, parent: tk.Misc, key: str, *, outcome: bool = True
                    ) -> dict[str, tk.StringVar]:
        saved = self.state.get(f"filters_{key}", {})
        box = ttk.LabelFrame(parent, text="Filters", padding=6)
        box.pack(fill="x", pady=(0, 4))
        out: dict[str, tk.StringVar] = {}
        for i, (name, label, width) in enumerate(_FILTERS):
            if name == "outcome" and not outcome:
                continue
            ttk.Label(box, text=label + ":").grid(row=i // 4, column=(i % 4) * 2, sticky="w",
                                                  padx=(0, 4), pady=2)
            var = tk.StringVar(value=saved.get(name, ""))
            if name == "user":
                w = ttk.Combobox(box, textvariable=var, values=["", *self.users], width=width)
            elif name == "area":
                w = ttk.Combobox(box, textvariable=var, values=["", *self.areas], width=width)
            elif name == "outcome":
                w = ttk.Combobox(box, textvariable=var, values=list(OUTCOMES), width=width)
            else:
                w = ttk.Entry(box, textvariable=var, width=width)
            w.grid(row=i // 4, column=(i % 4) * 2 + 1, sticky="w", padx=(0, 10), pady=2)
            out[name] = var
        ttk.Label(box, text="Dates YYYY-MM-DD. Action: exact (pupil.update) or a prefix "
                            "(pupil.).", foreground="#777").grid(row=2, column=0,
                                                                  columnspan=8, sticky="w")
        return out

    def _values(self, fvars: dict[str, tk.StringVar], key: str) -> dict[str, str]:
        v = {k: x.get().strip() for k, x in fvars.items()}
        self.state[f"filters_{key}"] = v
        return v

    def _show_entry(self, e: AL.Entry) -> None:
        try:
            full = AL.get_entry(e.source, int(e.row_id or 0), actor=self.principal)
        except _ERRORS as ex:
            self._err("Detail", ex)
            return
        lines = [f"{label + ':':<12} {value}" for label, value in (
            ("Time", full.at), ("Trail", full.source), ("User", full.user),
            ("Role", full.role), ("Interface", full.interface), ("Session", full.session),
            ("Action", full.action), ("Target", full.target), ("Outcome", full.outcome))
            if value]
        if full.detail:
            lines.append("\nDetail:")
            lines += [f"  {k}: {v}" for k, v in full.detail.items()]
        W.text_window(self.parent, f"Audit entry — {full.key}", "\n".join(lines),
                      size="640x420")

    # ── Events / Failed ──────────────────────────────────────────────

    def _build_list(self, tab: ttk.Frame, key: str) -> None:
        fvars = self._filter_bar(tab, key, outcome=key == "Events")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        page_var = tk.StringVar()
        ui = {"filters": fvars, "page": 1, "rows": {}, "page_var": page_var}
        for text, cmd in (("Search", lambda: self.search(key, page=1)),
                          ("Clear", lambda: self._clear(key)),
                          ("◀ Prev", lambda: self.search(key, page=ui["page"] - 1)),
                          ("Next ▶", lambda: self.search(key, page=ui["page"] + 1)),
                          ("Detail…", lambda: self._detail(key)),
                          ("Export CSV…", lambda: self.export(key))):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        ttk.Label(bar, textvariable=page_var, foreground="#555").pack(side="left", padx=8)
        tree = W.tree(tab, _EVENT_COLS, height=18, stretch={"detail"}, tags=W.STANDARD_TAGS)
        tree.bind("<Double-1>", lambda _e: self._detail(key))
        ui["tree"] = tree
        setattr(self, f"_ui_{'events' if key == 'Events' else 'failed'}", ui)

    def _build_events(self, tab) -> None:
        self._build_list(tab, "Events")

    def _build_failed(self, tab) -> None:
        ttk.Label(tab, text="Refused and failed actions: screens and changes someone wasn't "
                            "allowed to make, invalid entries and errors.",
                  foreground="#555").pack(anchor="w", pady=(0, 4))
        self._build_list(tab, "Failed / denied")

    def _ui(self, key: str) -> dict[str, Any]:
        return getattr(self, f"_ui_{'events' if key == 'Events' else 'failed'}")

    def _clear(self, key: str) -> None:
        for v in self._ui(key)["filters"].values():
            v.set("")
        self.search(key, page=1)

    def search(self, key: str, page: int = 1) -> None:
        ui = self._ui(key)
        filters = self._values(ui["filters"], key)
        page = max(1, page)
        fn = AL.search if key == "Events" else AL.failures
        ui["page_var"].set("Searching…")

        def done(result: AL.Page) -> None:
            ui["page"] = result.page
            tree = ui["tree"]
            tree.delete(*tree.get_children())
            ui["rows"] = {}
            for n, e in enumerate(result.entries):
                iid = f"{n}"
                ui["rows"][iid] = e
                tree.insert("", "end", iid=iid, tags=("bad",) if e.failed else (),
                            values=(e.at, e.source, e.user, e.action, e.target, e.outcome,
                                    e.detail_text()))
            ui["page_var"].set(f"Page {result.page} of {result.pages} - {result.total} "
                               "entr" + ("y" if result.total == 1 else "ies"))
        self._bg(lambda: fn(filters, actor=self.principal, page=page), done, key)

    def _detail(self, key: str) -> None:
        ui = self._ui(key)
        sel = ui["tree"].selection()
        if not sel:
            self._info("Detail", "Select an entry first.")
            return
        self._show_entry(ui["rows"][sel[0]])

    def export(self, key: str) -> None:
        filters = self._values(self._ui(key)["filters"], key)
        if key != "Events":
            filters = {**filters, "outcome": filters.get("outcome") or "failed"}
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            initialfile="audit_log.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n = AL.export_csv(path, filters, actor=self.principal)
        except (*_ERRORS, OSError) as e:
            self._err("Export", e)
            return
        self._info("Export", f"Exported {n} entr{'y' if n == 1 else 'ies'} to\n{path}")

    # ── Summary ──────────────────────────────────────────────────────

    def _build_summary(self, tab) -> None:
        self.sum_filters = self._filter_bar(tab, "Summary")
        ttk.Button(tab, text="Refresh", command=self.refresh_summary).pack(anchor="w",
                                                                           pady=(0, 4))
        self.sum_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.sum_var, font=("", 10, "bold")).pack(anchor="w")
        row = ttk.Frame(tab)
        row.pack(fill="both", expand=True)
        self.sum_trees = {}
        for key, title in (("by_user", "User"), ("by_action", "Action"), ("by_area", "Area"),
                           ("by_outcome", "Outcome")):
            col = ttk.Frame(row)
            col.pack(side="left", fill="both", expand=True, padx=3)
            self.sum_trees[key] = W.tree(col, [("name", title, 160), ("n", "Events", 60)],
                                         height=16, stretch={"name"})

    def refresh_summary(self) -> None:
        filters = self._values(self.sum_filters, "Summary")

        def done(s: dict[str, Any]) -> None:
            self.sum_var.set(f"{s['total']} entries, {s['failed']} refused/failed, "
                             f"{s['users']} people  ({s['first'] or '-'} to {s['last'] or '-'})")
            for key, tree in self.sum_trees.items():
                tree.delete(*tree.get_children())
                for name, n in s[key]:
                    tree.insert("", "end", values=(name, n))
        self._bg(lambda: AL.summary(filters, actor=self.principal), done, "Summary")

    # ── Run Report (old) ─────────────────────────────────────────────

    def _build_run(self, tab) -> None:
        top = ttk.Frame(tab)
        top.pack(fill="x", pady=(0, 4))
        ttk.Label(top, text="Report:").pack(side="left")
        labels = [AL.REPORT_LABELS[t] for t in AL.REPORT_TYPES]
        self.rep_var = tk.StringVar(value=self.state.get("report", labels[0]))
        cb = ttk.Combobox(top, textvariable=self.rep_var, values=labels, state="readonly",
                          width=28)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _e: self._describe())
        ttk.Button(top, text="Run", command=self.run).pack(side="left", padx=2)
        ttk.Button(top, text="Save snapshot", command=self.snapshot).pack(side="left", padx=2)
        ttk.Button(top, text="Export…", command=lambda: self.export_result(self.result)).pack(
            side="left", padx=2)
        self.desc_var = tk.StringVar()
        ttk.Label(tab, textvariable=self.desc_var, foreground="#555").pack(anchor="w")
        self.run_filters = self._filter_bar(tab, "Run Report")
        out = ttk.LabelFrame(tab, text="Result")
        out.pack(fill="both", expand=True)
        self.result_host = out
        self.result_tree: ttk.Treeview | None = None
        self._describe()

    def _report_type(self) -> str:
        label = self.rep_var.get()
        return next((k for k, v in AL.REPORT_LABELS.items() if v == label), AL.REPORT_TYPES[0])

    def _describe(self) -> None:
        self.state["report"] = self.rep_var.get()
        self.desc_var.set(AL.REPORT_DESCRIPTIONS[self._report_type()])

    def _show_result(self, host: tk.Misc, res: AL.ReportResult, attr: str | None = None
                     ) -> ttk.Treeview:
        for child in host.winfo_children():
            child.destroy()
        ttk.Label(host, text=f"{res.title} — {len(res.rows)} row(s), {res.generated_at}",
                  foreground="#555").pack(anchor="w")
        cols = [(f"c{i}", c, 150 if i else 170) for i, c in enumerate(res.columns)]
        tree = W.tree(host, cols, height=14, stretch={cols[-1][0]})
        for r in res.rows:
            tree.insert("", "end", values=[str(v) for v in r])
        return tree

    def run(self) -> None:
        rtype = self._report_type()
        filters = self._values(self.run_filters, "Run Report")

        def done(res: AL.ReportResult) -> None:
            self.result = res
            self.result_tree = self._show_result(self.result_host, res)
        self._bg(lambda: AL.run_report(rtype, filters, actor=self.principal), done, "Run")

    def snapshot(self, res: AL.ReportResult | None = None) -> None:
        res = res or self.result
        if res is None:
            self._info("Save snapshot", "Run a report first.")
            return
        try:
            run = AL.save_run(res, actor=self.principal)
        except _ERRORS as e:
            self._err("Save snapshot", e)
            return
        self._info("Save snapshot", f"Saved as run #{run.run_id} ({run.row_count} rows).")
        if "Past Runs" in self._built:
            self.refresh_runs()

    def export_result(self, res: AL.ReportResult | None) -> None:
        if res is None:
            self._info("Export", "Run a report first.")
            return
        path = filedialog.asksaveasfilename(
            parent=self._top(), defaultextension=".csv", initialfile=f"{res.report_type}.csv",
            filetypes=[("CSV", "*.csv"), ("Text", "*.txt")])
        if not path:
            return
        try:
            n = AL.export_report(res, path, actor=self.principal)
        except (*_ERRORS, OSError) as e:
            self._err("Export", e)
            return
        self._info("Export", f"Wrote {n} row(s) to\n{path}")

    # ── Saved Reports (old) ──────────────────────────────────────────

    def _build_saved(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        for text, cmd in (("New…", self.new_def), ("Edit…", self.edit_def),
                          ("Run", self.run_def), ("Delete", self.delete_def),
                          ("Refresh", self.refresh_saved)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        self.saved_tree = W.tree(tab, [("id", "ID", 50), ("name", "Name", 200),
                                       ("type", "Type", 170), ("filters", "Filters", 260),
                                       ("by", "Created by", 100), ("desc", "Description", 240)],
                                 height=16, stretch={"desc"})
        self.saved_tree.bind("<Double-1>", lambda _e: self.run_def())

    def refresh_saved(self) -> None:
        t = self.saved_tree
        t.delete(*t.get_children())
        try:
            defs = AL.list_defs(actor=self.principal)
        except _ERRORS as e:
            self._err("Saved Reports", e)
            return
        for d in defs:
            t.insert("", "end", iid=str(d.report_id), values=(
                d.report_id, d.name, AL.REPORT_LABELS.get(d.report_type, d.report_type),
                ", ".join(f"{k}={v}" for k, v in d.filters.items()), d.created_by or "",
                d.description or ""))

    def _def_fields(self, d: AL.ReportDef | None) -> list:
        f = d.filters if d else {}
        return [("name", "Name", d.name if d else "", None),
                ("report_type", "Type", AL.REPORT_LABELS[d.report_type] if d else
                 AL.REPORT_LABELS[AL.REPORT_TYPES[0]], [AL.REPORT_LABELS[t]
                                                        for t in AL.REPORT_TYPES]),
                ("description", "Description", d.description if d else "", "text"),
                ("created_by", "Created by", d.created_by if d else self.principal.username,
                 ["" if not d else d.created_by or ""] if d else [self.principal.username]),
                *[(f"f_{k}", f"Filter: {label}", f.get(k, ""), None)
                  for k, label, _w in _FILTERS]]

    @staticmethod
    def _def_data(v: dict[str, Any]) -> dict[str, Any]:
        return {"name": v["name"], "report_type": v["report_type"],
                "description": v["description"],
                "filters": {k[2:]: x for k, x in v.items() if k.startswith("f_") and x}}

    def _selected_def(self, title: str) -> int | None:
        sel = self.saved_tree.selection()
        if not sel:
            self._info(title, "Select a saved report first.")
            return None
        return int(sel[0])

    def new_def(self) -> None:
        def save(v):
            AL.create_def(self._def_data(v), actor=self.principal)
            self.refresh_saved()
        W.form_dialog(self.parent, "New saved report", self._def_fields(None), save)

    def edit_def(self) -> None:
        rid = self._selected_def("Edit")
        if rid is None:
            return
        d = AL.get_def(rid)

        def save(v):
            AL.update_def(rid, self._def_data(v), actor=self.principal)
            self.refresh_saved()
        W.form_dialog(self.parent, f"Edit saved report — {d.name}", self._def_fields(d), save)

    def run_def(self) -> None:
        rid = self._selected_def("Run")
        if rid is None:
            return

        def done(res: AL.ReportResult) -> None:
            win, frm = W.dialog(self.parent, res.title, size="900x520")
            bar = ttk.Frame(frm)
            bar.pack(fill="x", pady=(0, 4))
            ttk.Button(bar, text="Save snapshot", command=lambda: self.snapshot(res)).pack(
                side="left", padx=2)
            ttk.Button(bar, text="Export…", command=lambda: self.export_result(res)).pack(
                side="left", padx=2)
            ttk.Button(bar, text="Close", command=win.destroy).pack(side="right")
            host = ttk.Frame(frm)
            host.pack(fill="both", expand=True)
            self._show_result(host, res)
        self._bg(lambda: AL.run_def(rid, actor=self.principal), done, "Run")

    def delete_def(self) -> None:
        rid = self._selected_def("Delete")
        if rid is None or not messagebox.askyesno("Delete", "Delete this saved report?",
                                                  parent=self._top()):
            return
        try:
            AL.delete_def(rid, actor=self.principal)
        except _ERRORS as e:
            self._err("Delete", e)
            return
        self.refresh_saved()

    # ── Past Runs (old) ──────────────────────────────────────────────

    def _build_runs(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        for text, cmd in (("View", self.view_run), ("Delete", self.delete_run),
                          ("Refresh", self.refresh_runs)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        self.runs_tree = W.tree(tab, [("id", "ID", 50), ("at", "Run at (UTC)", 150),
                                      ("title", "Report", 300), ("rows", "Rows", 60),
                                      ("by", "Run by", 100), ("filters", "Filters", 300)],
                                height=16, stretch={"filters"})
        self.runs_tree.bind("<Double-1>", lambda _e: self.view_run())

    def refresh_runs(self) -> None:
        t = self.runs_tree
        t.delete(*t.get_children())
        try:
            runs = AL.list_runs(actor=self.principal)
        except _ERRORS as e:
            self._err("Past Runs", e)
            return
        for r in runs:
            t.insert("", "end", iid=str(r.run_id), values=(
                r.run_id, r.run_at, r.title, r.row_count, r.run_by or "",
                ", ".join(f"{k}={v}" for k, v in r.filters.items())))

    def view_run(self) -> None:
        sel = self.runs_tree.selection()
        if not sel:
            self._info("View", "Select a run first.")
            return
        try:
            run = AL.get_run(int(sel[0]), actor=self.principal)
        except _ERRORS as e:
            self._err("View", e)
            return
        W.text_window(self.parent, f"Run #{run.run_id} — {run.title}",
                      AL.render(run.as_result()), size="900x520",
                      save_name=f"audit_run_{run.run_id}.txt")

    def delete_run(self) -> None:
        sel = self.runs_tree.selection()
        if not sel or not messagebox.askyesno("Delete", "Delete this saved run?",
                                              parent=self._top()):
            return
        try:
            AL.delete_run(int(sel[0]), actor=self.principal)
        except _ERRORS as e:
            self._err("Delete", e)
            return
        self.refresh_runs()

    # ── Overview (old) ───────────────────────────────────────────────

    def _build_overview(self, tab) -> None:
        ttk.Button(tab, text="Refresh", command=self.refresh_overview).pack(anchor="w",
                                                                            pady=(0, 6))
        self.ov_text = tk.Text(tab, height=26, wrap="word", font=("TkFixedFont", 10))
        self.ov_text.pack(fill="both", expand=True)

    def refresh_overview(self) -> None:
        def done(ov: dict[str, Any]) -> None:
            lines = [f"Last 7 days (since {ov['since']}): {ov['events']} events, "
                     f"{ov['failed']} refused/failed, {ov['users']} people", "",
                     "Most active:"]
            lines += [f"  {u:<24} {n}" for u, n in ov["top_users"]] or ["  (none)"]
            lines += ["", "Most common actions:"]
            lines += [f"  {a:<34} {n}" for a, n in ov["top_actions"]] or ["  (none)"]
            lines += ["", "Audit tables:"]
            lines += [f"  {t:<34} {n} row(s)" for t, n in ov["trails"]]
            lines += ["", f"Activity log files ({ov['log_bytes'] // 1024} KB):"]
            lines += [f"  {p}" for p in ov["log_files"]] or ["  (none yet)"]
            self.ov_text.configure(state="normal")
            self.ov_text.delete("1.0", "end")
            self.ov_text.insert("1.0", "\n".join(lines))
            self.ov_text.configure(state="disabled")
        self._bg(lambda: AL.overview(actor=self.principal), done, "Overview")


def draw_audit_log(parent: ttk.Frame, *, principal: Principal, state: dict) -> AuditLogPage:
    return AuditLogPage(parent, principal=principal, state=state)
