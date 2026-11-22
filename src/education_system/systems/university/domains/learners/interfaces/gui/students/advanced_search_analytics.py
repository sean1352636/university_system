"""Analytics windows of Advanced Search: the search analytics dashboard,
student demographics (six tabs), academic performance, predictive
analytics (six tabs, on real data) and comprehensive reports.

Counts under ``student_search_reports.SUPPRESS`` are shown as ``<10`` and
never drawn, so small groups cannot be identified. Trends and pass rates
describe past students; nothing here predicts an individual.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from education_system.systems.university.domains.learners.interfaces.gui.students.advanced_search import (  # noqa: E501
    TITLE, _call, _tree,
)

SUPPRESSED_NOTE = ("Counts under 10 are shown as <10 so small groups cannot be identified. "
                   "Trends and rates describe past students, not individuals.")


def _reports():
    from education_system.systems.university.application.students import (
        search_reports as student_search_reports,
    )
    return student_search_reports


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


def _staff_only(gui):
    if gui.viewer.can_view_all:
        return True
    messagebox.showinfo(TITLE, "Reports are for staff who can search all students.",
                        parent=gui.master)
    return False


def _clear(frame):
    for child in frame.winfo_children():
        child.destroy()


def table(frame, report, height=14):
    """Show a generated report (``columns``/``labels``/``rows``) in ``frame``."""
    _clear(frame)
    ttk.Label(frame, text=report["title"], padding=(6, 4), wraplength=1000).pack(anchor="w")
    cols = report["columns"]
    tree = _tree(frame, [(f"c{i}", report["labels"][c]) for i, c in enumerate(cols)],
                 [max(80, min(260, 9 * len(report["labels"][c]))) for c in cols], height=height)
    for i, row in enumerate(report["rows"]):
        tree.insert("", "end", iid=str(i), values=["" if row.get(c) is None else row.get(c)
                                                   for c in cols])
    return tree


def bars(frame, rows, width=520):
    """A bar per row (``value``, ``count``, ``shown``); suppressed counts
    get no bar."""
    shown = [r for r in rows if not str(r["shown"]).startswith("<")]
    top = max([r["count"] for r in shown] or [1])
    canvas = tk.Canvas(frame, width=width + 260, height=22 * len(rows) + 10, background="white")
    canvas.pack(anchor="w", padx=6, pady=6)
    for i, r in enumerate(rows):
        y = 8 + i * 22
        canvas.create_text(4, y + 8, text=str(r["value"])[:30], anchor="w", font=("Segoe UI", 8))
        if not str(r["shown"]).startswith("<"):
            canvas.create_rectangle(200, y, 200 + int(width * r["count"] / top), y + 16,
                                    fill="#4a90d9", outline="")
        canvas.create_text(205 + width, y + 8, anchor="w", font=("Segoe UI", 8),
                           text=f"{r['shown']}" + (f" ({r['percent']}%)" if r.get("percent")
                                                   is not None else ""))


class _ScopedWindow:
    """A window with "current search / everyone" scope and a notebook."""

    def __init__(self, gui, title, width=1100, height=720):
        self.gui = gui
        self.win = _tools()._toplevel(gui.master, title, width, height)
        top = ttk.Frame(self.win, padding=6)
        top.pack(fill=tk.X)
        self.scope = tk.StringVar(value="search" if gui.state["criteria"] else "all")
        ttk.Radiobutton(top, text="Students in the current search", variable=self.scope,
                        value="search", command=self.refresh).pack(side=tk.LEFT)
        ttk.Radiobutton(top, text="Everyone", variable=self.scope, value="all",
                        command=self.refresh).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side=tk.LEFT, padx=6)
        bar = ttk.Frame(self.win, padding=6)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(bar, text="Close", command=self.win.destroy).pack(side=tk.RIGHT)
        self.bar = bar
        ttk.Label(self.win, text=SUPPRESSED_NOTE, foreground="#555", padding=(6, 0)).pack(
            anchor="w")
        self.nb = ttk.Notebook(self.win)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    def criteria(self):
        return self.gui.state["criteria"] if self.scope.get() == "search" else {}

    def tab(self, text):
        frame = ttk.Frame(self.nb)
        self.nb.add(frame, text=text)
        return frame

    def select(self, text):
        for tab_id in self.nb.tabs():
            if text.lower() in self.nb.tab(tab_id, "text").lower():
                self.nb.select(tab_id)

    def refresh(self):
        pass

    def generated(self, frame, name, **options):
        report = _call(self.gui.master, _reports().generate, name, self.criteria(),
                       self.gui.viewer, write=True, **options)
        if isinstance(report, dict):
            table(frame, report)
            if self.gui.viewer.can_export:
                ttk.Button(frame, text="Export…", command=lambda: _tools().export_report(
                    self.gui, report, self.win)).pack(anchor="w", padx=6, pady=4)
        return report


# ── demographics ────────────────────────────────────────────────────────


class DemographicsWindow(_ScopedWindow):
    TABS = ("Overview Summary", "Age Distribution", "Gender Analysis", "Course Enrollment",
            "Cross-Tabulation", "Full Report")

    def __init__(self, gui, start=None):
        if not _staff_only(gui):
            return
        super().__init__(gui, "Student demographics")
        self.frames = {name: self.tab(name) for name in self.TABS}
        self._crosstab_controls()
        self.refresh()
        if start:
            self.select(start)

    def _crosstab_controls(self):
        frame = self.frames["Cross-Tabulation"]
        dims = _call(self.gui.master, _reports().available_dimensions) or {}
        self._dims = {v: k for k, v in dims.items()}
        controls = ttk.Frame(frame, padding=6)
        controls.pack(fill=tk.X)
        ttk.Label(controls, text="Rows").pack(side=tk.LEFT)
        self.row_dim = ttk.Combobox(controls, values=list(dims.values()), state="readonly",
                                    width=18)
        self.row_dim.set(dims.get("course", ""))
        self.row_dim.pack(side=tk.LEFT, padx=4)
        ttk.Label(controls, text="by").pack(side=tk.LEFT)
        self.col_dim = ttk.Combobox(controls, values=list(dims.values()), state="readonly",
                                    width=18)
        self.col_dim.set(dims.get("gender", ""))
        self.col_dim.pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text="Cross-tabulate", command=self._crosstab).pack(side=tk.LEFT)
        self.cross_out = ttk.Frame(frame)
        self.cross_out.pack(fill=tk.BOTH, expand=True)

    def _distribution(self, frame, key, extra=None):
        _clear(frame)
        data = _call(self.gui.master, _reports().distribution, self.criteria(), self.gui.viewer,
                     key)
        if not isinstance(data, dict):
            return
        ttk.Label(frame, text=f"{data['label']} — {data['total']} student(s)",
                  font=("Segoe UI", 10, "bold"), padding=6).pack(anchor="w")
        bars(frame, data["rows"])
        if extra:
            extra(frame)

    def refresh(self):
        self._overview()
        self._distribution(self.frames["Age Distribution"], "age_band")
        self._distribution(self.frames["Gender Analysis"], "gender",
                           lambda f: self._small_cross(f, "gender", "course"))
        self._distribution(self.frames["Course Enrollment"], "course", self._modules)
        if self.row_dim.get():
            self._crosstab()
        self.generated(self.frames["Full Report"], "demographics")

    def _overview(self):
        frame = self.frames["Overview Summary"]
        _clear(frame)
        data = _call(self.gui.master, _reports().demographics, self.criteria(), self.gui.viewer)
        if not isinstance(data, dict):
            return
        ttk.Label(frame, text=f"{data['total']} student(s)", font=("Segoe UI", 12, "bold"),
                  padding=6).pack(anchor="w")
        text = tk.Text(frame, wrap="word", font=("Courier", 9), height=26)
        text.pack(fill=tk.BOTH, expand=True, padx=6)
        for part in data["parts"]:
            top = ", ".join(f"{r['value']} {r['shown']}" for r in part["rows"][:5])
            text.insert(tk.END, f"{part['label']:<16} {top}\n")
        text.configure(state="disabled")

    def _modules(self, frame):
        holder = ttk.Frame(frame)
        holder.pack(fill=tk.BOTH, expand=True)
        self.generated(holder, "module_enrolment")

    def _small_cross(self, frame, row, col):
        data = _call(self.gui.master, _reports().crosstab, self.criteria(), self.gui.viewer,
                     row, col)
        if isinstance(data, dict):
            self._grid(frame, data)

    def _crosstab(self):
        row, col = self._dims.get(self.row_dim.get()), self._dims.get(self.col_dim.get())
        if not row or not col:
            return
        data = _call(self.gui.master, _reports().crosstab, self.criteria(), self.gui.viewer,
                     row, col)
        _clear(self.cross_out)
        if isinstance(data, dict):
            self._grid(self.cross_out, data)

    @staticmethod
    def _grid(frame, data):
        cols = data["cols"]
        tree = _tree(frame, [("row", f"{data['row_label']} \\ {data['col_label']}")]
                     + [(f"c{i}", c) for i, c in enumerate(cols)] + [("total", "Total")],
                     [180] + [90] * len(cols) + [80], height=10)
        for r in data["rows"]:
            tree.insert("", "end", values=[r] + [data["cells"][f"{r}\t{c}"] for c in cols]
                        + [data["row_totals"][r]])
        tree.insert("", "end", values=["Total"] + [data["col_totals"][c] for c in cols]
                    + [data["total"]])


# ── performance ─────────────────────────────────────────────────────────


class PerformanceWindow(_ScopedWindow):
    def __init__(self, gui):
        if not _staff_only(gui):
            return
        super().__init__(gui, "Academic performance analysis")
        self.by_module = self.tab("By Module")
        self.attendance = self.tab("Attendance")
        self.pass_rates = self.tab("Pass Rates")
        one = self.tab("One Student")
        controls = ttk.Frame(one, padding=6)
        controls.pack(fill=tk.X)
        ttk.Label(controls, text="Student ID").pack(side=tk.LEFT)
        self.sid = ttk.Entry(controls, width=14)
        self.sid.insert(0, (gui.selected_ids() or [""])[0])
        self.sid.pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text="Show", command=self._one).pack(side=tk.LEFT)
        self.one_out = ttk.Frame(one)
        self.one_out.pack(fill=tk.BOTH, expand=True)
        self.refresh()

    def refresh(self):
        self.generated(self.by_module, "performance")
        self.generated(self.attendance, "attendance")
        self.generated(self.pass_rates, "module_pass_rates")

    def _one(self):
        if self.sid.get().strip():
            self.generated(self.one_out, "student_performance", student_id=self.sid.get().strip())


# ── predictive analytics ────────────────────────────────────────────────


class PredictiveWindow(_ScopedWindow):
    TABS = ("At-Risk Students", "Enrollment Prediction", "Success Probability", "Recommended",
            "Popular Searches", "Recent Searches")

    def __init__(self, gui, start=None):
        if not _staff_only(gui):
            return
        super().__init__(gui, "Predictive analytics")
        self.frames = {name: self.tab(name) for name in self.TABS}
        self.refresh()
        if start:
            self.select(start)

    def refresh(self):
        self.generated(self.frames["At-Risk Students"], "at_risk")
        self.generated(self.frames["Enrollment Prediction"], "registrations")
        self.generated(self.frames["Success Probability"], "module_pass_rates")
        self._searches(self.frames["Recommended"], _insights().recommended_searches,
                       [("source", "From"), ("name", "Name"), ("search", "Search")])
        self._searches(self.frames["Popular Searches"], _insights().popular_searches,
                       [("times", "Times run"), ("search", "Search")],
                       note="Only searches that identify nobody are listed.")
        self._searches(self.frames["Recent Searches"], _insights().recent_searches,
                       [("at", "When"), ("search", "Search"), ("count", "Found")])

    def _searches(self, frame, fn, columns, note=None):
        _clear(frame)
        rows = _call(self.gui.master, fn, self.gui.viewer) or []
        if note:
            ttk.Label(frame, text=note, foreground="#555", padding=6).pack(anchor="w")
        bar = ttk.Frame(frame, padding=4)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        tree = _tree(frame, columns, [140 if k != "search" else 560 for k, _ in columns])
        store = {}
        for i, r in enumerate(rows):
            store[str(i)] = r
            tree.insert("", "end", iid=str(i), values=["" if r.get(k) is None else r.get(k)
                                                       for k, _ in columns])

        def run():
            r = store.get((tree.selection() or [""])[0])
            if r:
                self.gui.load_criteria(r["criteria"])
                from education_system.systems.university.domains.learners.interfaces.gui.students import (  # noqa: E501
                    advanced_search_classic,
                )
                advanced_search_classic.show_tab(self.gui, "Search")
        ttk.Button(bar, text="Run this search", command=run).pack(side=tk.LEFT)
        tree.bind("<Double-1>", lambda _e: run())


# ── search analytics dashboard ──────────────────────────────────────────


class AnalyticsDashboard:
    def __init__(self, gui):
        self.gui = gui
        win = _tools()._toplevel(gui.master, "Search analytics dashboard", 1000, 660)
        bar = ttk.Frame(win, padding=6)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(bar, text="Close", command=win.destroy).pack(side=tk.RIGHT)
        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        if gui.viewer.role in _reports().search.ADMIN_ROLES:
            self._admin(nb)
        self._mine(nb)

    def _admin(self, nb):
        act = _call(self.gui.master, _reports().search_activity, self.gui.viewer, write=True)
        if not isinstance(act, dict):
            return
        for title, rows, columns in (
                ("By action", [{"action": k, "times": v} for k, v in act["by_action"].items()],
                 [("action", "Action"), ("times", "Times")]),
                ("By person", act["by_user"], [("user", "Who"), ("actions", "Actions")]),
                ("By day", act["by_day"], [("day", "Day"), ("actions", "Actions")]),
                ("Top searches", act["top_searches"], [("times", "Times"),
                                                       ("search", "Search")])):
            frame = ttk.Frame(nb)
            nb.add(frame, text=title)
            tree = _tree(frame, columns, [120 if k != "search" else 600 for k, _ in columns])
            for i, r in enumerate(rows):
                tree.insert("", "end", iid=str(i), values=[r.get(k) for k, _ in columns])

    def _mine(self, nb):
        frame = ttk.Frame(nb)
        nb.add(frame, text="Your activity")
        history = _call(self.gui.master, _extras().history, self.gui.viewer, 500) or []
        counts = {}
        for h in history:
            counts[h["action"]] = counts.get(h["action"], 0) + 1
        ttk.Label(frame, padding=6, text="Your last 500 entries in the search audit: " + (
            ", ".join(f"{k} {v}" for k, v in counts.items()) or "none")).pack(anchor="w")
        if self.gui.viewer.can_view_all:
            popular = _call(self.gui.master, _insights().popular_searches, self.gui.viewer) or []
            ttk.Label(frame, padding=6, text="Searches staff run most (identifying nobody):"
                      ).pack(anchor="w")
            tree = _tree(frame, [("times", "Times"), ("search", "Search")], [80, 700])
            for i, r in enumerate(popular):
                tree.insert("", "end", iid=str(i), values=(r["times"], r["search"]))


def _extras():
    from education_system.systems.university.application.students import (
        search_extras as student_search_extras,
    )
    return student_search_extras


# ── comprehensive reports ───────────────────────────────────────────────


class ComprehensiveReports(_ScopedWindow):
    def __init__(self, gui):
        if not _staff_only(gui):
            return
        super().__init__(gui, "Comprehensive reports", 1000, 680)
        frame = self.tab("Reports")
        rp = _reports()
        admin = gui.viewer.role in rp.search.ADMIN_ROLES
        names = [(k, v) for k, v in rp.REPORTS.items()
                 if (admin or k not in rp.ADMIN_REPORTS) and k != "student_performance"]
        listing = ttk.Frame(frame, padding=6)
        listing.pack(side=tk.LEFT, fill=tk.Y)
        self.out = ttk.Frame(frame)
        self.out.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for key, label in names:
            ttk.Button(listing, text=label, width=34,
                       command=lambda k=key: self.generated(self.out, k)).pack(anchor="w",
                                                                               pady=1)
        ttk.Separator(listing).pack(fill=tk.X, pady=6)
        ttk.Button(listing, text="Custom report…", width=34, command=self._custom).pack(
            anchor="w")

    def _custom(self):
        messagebox.showinfo(TITLE, (
            "Custom SQL reports are not offered: free SQL could read anything in the database. "
            "Build the report instead from conditions on the Search tab, then use Export to "
            "choose exactly the fields and format you need, or Save search and Schedule a "
            "report to have it sent regularly."), parent=self.win)
        if self.gui.viewer.can_export:
            self.gui.export()
