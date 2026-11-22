"""Mock Exams screen.

The old window is kept: the series list (Year / Status filters; New series,
Edit, Set status, Papers, Delete, Refresh; columns ID, Yr, Start, End,
Status, Name), the Papers window (Add paper, Edit paper, Results, Summary,
Delete paper, Refresh; columns ID, Date, Subj, Paper, Tier, Max), the
Results window (Add result, Edit selected, Delete selected, Refresh;
columns ID, Pupil, Marks, %, Grade, Abs) and the old dialogs.

Added as tabs: Mark entry (a whole-paper sheet with access arrangements),
Tiers, Subject grades (against target), Analysis (subject summary, below
target, compare with an earlier series, missing marks) and Timetable
(clashes and access arrangements), plus release, CSV import / export and
history. Rules live in :mod:`modules.examinations.domain.mock_exams`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui.parented_dialogs import (
    filedialog,
    messagebox,
)
from education_system.systems.secondary.modules.examinations.domain import mock_exams as MX
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
ALL = ""
_ERRORS = (MX.ValidationError, MX.PermissionDenied, MX.NotFound)
STATUS_BG = {"Above": "#e7f6ea", "On track": "#ffffff", "Below": "#fff6d6",
             "Well below": "#fde2e2", "No data": "#f4f4f4", "clash": "#fde2e2",
             "absent": "#eeeeee"}


_problems = W.problems


def _tree(parent, columns, height: int = 12) -> ttk.Treeview:
    return W.tree(parent, columns, height=height, stretch={"name", "detail"}, tags=STATUS_BG,
                  minwidth=0)


def _dialog(owner: tk.Misc, title: str, size: str) -> tuple[tk.Toplevel, ttk.Frame]:
    return W.dialog(owner, title, size=size)


def _text_window(owner, title: str, text: str) -> None:
    W.text_window(owner, title, text, size="760x480")


def _form(frm: ttk.Frame, rows: list[tuple[str, tk.Widget]]) -> None:
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=2, padx=(0, 8))
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)


# ── Old dialogs ──────────────────────────────────────────────────────

def series_dialog(owner, *, principal: Principal, series: MX.MockSeries | None = None,
                  after: Callable[[], None] | None = None) -> None:
    win, frm = _dialog(owner, "Edit series" if series else "New series", "520x380")
    v = {k: tk.StringVar(value=str(getattr(series, k) if series else d)) for k, d in (
        ("name", ""), ("year_group", "11"), ("start_date", ""), ("end_date", ""),
        ("status", MX.DEFAULT_SERIES_STATUS))}
    status = ttk.Combobox(frm, textvariable=v["status"], values=["Planned", "InProgress"],
                          state="disabled" if series else "readonly", width=12)
    _form(frm, [
        ("Name:", ttk.Entry(frm, textvariable=v["name"], width=40)),
        ("Year:", ttk.Combobox(frm, textvariable=v["year_group"],
                               values=[str(y) for y in P.YEAR_GROUPS], state="readonly",
                               width=8)),
        ("Start date:", ttk.Entry(frm, textvariable=v["start_date"], width=14)),
        ("End date:", ttk.Entry(frm, textvariable=v["end_date"], width=14)),
        ("Status:", status),
    ])
    ttk.Label(frm, text="Notes:").grid(row=5, column=0, sticky="nw", pady=2)
    notes = tk.Text(frm, height=5, wrap="word")
    notes.insert("1.0", (series.notes or "") if series else "")
    notes.grid(row=5, column=1, sticky="nsew", pady=2)

    def save() -> None:
        data = {k: x.get() for k, x in v.items()}
        data["notes"] = notes.get("1.0", "end").strip()
        try:
            if series:
                data.pop("status")
                MX.update_series(series.series_id, data, actor=principal)
            else:
                MX.create_series(data, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Mock series", _problems(e), parent=win)
            return
        win.destroy()
        if after:
            after()

    btns = ttk.Frame(frm)
    btns.grid(row=6, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right", padx=(6, 0))
    ttk.Button(btns, text="Save", command=save).pack(side="right")


def status_dialog(owner, *, principal: Principal, series: MX.MockSeries,
                  after: Callable[[], None] | None = None) -> None:
    win, frm = _dialog(owner, "Set status", "380x200")
    ttk.Label(frm, text=series.name[:40]).pack(anchor="w")
    ttk.Label(frm, text=f"Current: {series.status}", foreground="#555").pack(anchor="w")
    var = tk.StringVar(value=series.status)
    ttk.Combobox(frm, textvariable=var, values=list(MX.SERIES_STATUSES), state="readonly",
                 width=14).pack(anchor="w", pady=8)

    def save() -> None:
        try:
            MX.set_series_status(series.series_id, var.get(), actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Set status", _problems(e), parent=win)
            return
        win.destroy()
        if after:
            after()

    btns = ttk.Frame(frm)
    btns.pack(fill="x")
    ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right", padx=(6, 0))
    ttk.Button(btns, text="Save", command=save).pack(side="right")


def paper_dialog(owner, *, principal: Principal, series: MX.MockSeries,
                 paper: MX.MockPaper | None = None,
                 after: Callable[[], None] | None = None) -> None:
    win, frm = _dialog(owner, "Edit paper" if paper else "Add paper", "600x520")
    subjects = {f"{s.code} - {s.name}": s for s in S.list_subjects()}
    v = {
        "subject": tk.StringVar(value=next((k for k, s in subjects.items()
                                            if paper and s.subject_id == paper.subject_id),
                                           "")),
        "paper_name": tk.StringVar(value=paper.paper_name if paper else "Paper 1"),
        "paper_date": tk.StringVar(value=paper.paper_date if paper else series.start_date),
        "start_time": tk.StringVar(value=(paper.start_time or "") if paper else "09:00"),
        "duration_mins": tk.StringVar(value=str(paper.duration_mins or "") if paper else "90"),
        "room": tk.StringVar(value=(paper.room or "") if paper else ""),
        "max_marks": tk.StringVar(value=MX._num(paper.max_marks) if paper else ""),
        "tier": tk.StringVar(value=paper.tier if paper else MX.DEFAULT_TIER),
        "grade_boundaries": tk.StringVar(value=paper.boundaries_text if paper else ""),
    }
    _form(frm, [
        ("Subject:", ttk.Combobox(frm, textvariable=v["subject"], values=list(subjects),
                                  state="readonly", width=42)),
        ("Paper name:", ttk.Entry(frm, textvariable=v["paper_name"], width=24)),
        ("Paper date:", ttk.Entry(frm, textvariable=v["paper_date"], width=14)),
        ("Start time:", ttk.Entry(frm, textvariable=v["start_time"], width=8)),
        ("Length (mins):", ttk.Entry(frm, textvariable=v["duration_mins"], width=8)),
        ("Room:", ttk.Entry(frm, textvariable=v["room"], width=14)),
        ("Max marks:", ttk.Entry(frm, textvariable=v["max_marks"], width=8)),
        ("Tier:", ttk.Combobox(frm, textvariable=v["tier"], values=list(MX.PAPER_TIERS),
                               state="readonly", width=12)),
        ("Grade boundaries:", ttk.Entry(frm, textvariable=v["grade_boundaries"], width=30)),
    ])
    hint = tk.StringVar()

    def show_hint(*_a) -> None:
        grades = MX.TIER_GRADES.get(v["tier"].get(), ())
        hint.set("Lowest mark for each grade, e.g. "
                 + ", ".join(f"{g}=" for g in grades[:3]) + f"…  (grades {grades[-1]}-"
                 f"{grades[0]})" if grades else "")
    v["tier"].trace_add("write", show_hint)
    show_hint()
    ttk.Label(frm, textvariable=hint, foreground="#666").grid(row=9, column=1, sticky="w")
    ttk.Label(frm, text="Notes:").grid(row=10, column=0, sticky="nw", pady=2)
    notes = tk.Text(frm, height=4, wrap="word")
    notes.insert("1.0", (paper.notes or "") if paper else "")
    notes.grid(row=10, column=1, sticky="nsew", pady=2)

    def save() -> None:
        data = {k: x.get() for k, x in v.items() if k != "subject"}
        s = subjects.get(v["subject"].get())
        data["subject_id"] = s.subject_id if s else ""
        data["notes"] = notes.get("1.0", "end").strip()
        try:
            if paper:
                MX.update_paper(paper.paper_id, data, actor=principal)
            else:
                MX.create_paper({**data, "series_id": series.series_id}, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Mock paper", _problems(e), parent=win)
            return
        win.destroy()
        if after:
            after()

    btns = ttk.Frame(frm)
    btns.grid(row=11, column=0, columnspan=2, sticky="e", pady=(8, 0))
    ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right", padx=(6, 0))
    ttk.Button(btns, text="Save", command=save).pack(side="right")


def result_dialog(owner, *, principal: Principal, paper: MX.MockPaper,
                  existing: MX.MockResult | None = None,
                  after: Callable[[], None] | None = None) -> None:
    win, frm = _dialog(owner, "Edit result" if existing else "Add result", "440x380")
    ttk.Label(frm, text=f"{paper.label} · out of {MX._num(paper.max_marks)}"
                        + (f" · boundaries {paper.boundaries_text}" if paper.boundaries
                           else ""), wraplength=400, foreground="#555").pack(anchor="w")
    pupil_var = tk.StringVar(value=existing.admission_no if existing else "")
    marks_var = tk.StringVar(value=MX._num(existing.marks_awarded) if existing else "")
    grade_var = tk.StringVar(value=(existing.grade or "") if existing and
                             existing.grade_source == "manual" else "")
    absent_var = tk.BooleanVar(value=bool(existing and existing.absent))
    reason_var = tk.StringVar(value=(existing.absence_reason or "") if existing else "")
    rows = [
        ("Pupil ID:", ttk.Entry(frm, textvariable=pupil_var, width=14,
                                state="readonly" if existing else "normal")),
        ("Marks:", ttk.Entry(frm, textvariable=marks_var, width=8)),
        ("Grade:", ttk.Combobox(frm, textvariable=grade_var,
                                values=[""] + list(MX.grades_for(paper.tier)), width=6)),
        ("Absent:", ttk.Checkbutton(frm, variable=absent_var)),
        ("Reason:", ttk.Combobox(frm, textvariable=reason_var,
                                 values=[""] + list(MX.ABSENCE_REASONS), state="readonly",
                                 width=12)),
    ]
    for label, widget in rows:
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=12).pack(side="left")
        widget.pack(in_=row, side="left", padx=4)
    ttk.Label(frm, text="Grade blank = from the boundaries.", foreground="#666").pack(
        anchor="w")
    ttk.Label(frm, text="Notes:").pack(anchor="w", pady=(8, 0))
    notes = tk.Text(frm, height=3, wrap="word")
    notes.insert("1.0", (existing.notes or "") if existing else "")
    notes.pack(fill="x")

    def save() -> None:
        data = {"pupil": existing.pupil_id if existing else pupil_var.get(),
                "marks_awarded": "" if absent_var.get() else marks_var.get(),
                "grade": "" if absent_var.get() else grade_var.get(),
                "absent": absent_var.get(), "absence_reason": reason_var.get(),
                "notes": notes.get("1.0", "end").strip()}
        try:
            MX.upsert_result(paper.paper_id, data, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Mock result", _problems(e), parent=win)
            return
        win.destroy()
        if after:
            after()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(8, 0))
    ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right", padx=(6, 0))
    ttk.Button(btns, text="Save", command=save).pack(side="right")


def summary_text(paper_id: int) -> str:
    s = MX.paper_summary(paper_id)
    p = s["paper"]
    lines = [f"{p.label} - {p.paper_date}  (max {MX._num(p.max_marks)})",
             f"Candidates: {s['candidates']}   Results: {s['count']}   Absent: {s['absent']}"
             f"   Missing: {len(s['missing'])}",
             f"Average: {s['avg_pct'] if s['avg_pct'] is not None else '-'}%   Median: "
             f"{s['median_pct'] if s['median_pct'] is not None else '-'}%   Range: "
             f"{s['min_pct'] if s['min_pct'] is not None else '-'}% - "
             f"{s['max_pct'] if s['max_pct'] is not None else '-'}%",
             f"Grade 4+: {s['grade4']}   Grade 5+: {s['grade5']}", "", "Grades:"]
    order = list(MX.grades_for(p.tier))
    for g in sorted(s["grades"], key=lambda x: order.index(x) if x in order else 99):
        lines.append(f"  {g:<4} {'█' * s['grades'][g]} {s['grades'][g]}")
    if s["missing"]:
        lines += ["", "No result yet: " + ", ".join(x.display_name for x in s["missing"])]
    return "\n".join(lines)


def results_window(owner, *, principal: Principal, paper: MX.MockPaper) -> None:
    """The old Results window for one paper."""
    win, frm = _dialog(owner, f"Results - {paper.label}", "720x480")
    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(0, 6))
    tree = _tree(frm, [("id", "ID", 50), ("pupil", "Pupil", 100), ("name", "Name", 200),
                       ("marks", "Marks", 100), ("pct", "%", 60), ("grade", "Grade", 60),
                       ("abs", "Abs", 50)], height=14)

    def refresh() -> None:
        tree.delete(*tree.get_children())
        for r in MX.list_results(paper.paper_id):
            tree.insert("", "end", iid=str(r.result_id), tags=("absent",) if r.absent else (),
                        values=(r.result_id, r.admission_no, r.pupil_name,
                                f"{MX._num(r.marks_awarded)}/{MX._num(paper.max_marks)}"
                                if r.marks_awarded is not None else "",
                                r.mark_pct if r.mark_pct is not None else "",
                                (r.grade or "") + ("*" if r.grade_source == "manual" else ""),
                                "Y" if r.absent else ""))

    def selected() -> MX.MockResult | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Results", "Select a result first.", parent=win)
            return None
        return MX.get_result(int(sel[0]))

    def edit() -> None:
        r = selected()
        if r:
            result_dialog(win, principal=principal, paper=paper, existing=r, after=refresh)

    def delete() -> None:
        r = selected()
        if r is None or not messagebox.askyesno("Results", f"Delete {r.pupil_name}'s result?",
                                                parent=win):
            return
        try:
            MX.delete_result(r.result_id, actor=principal)
        except _ERRORS as e:
            messagebox.showerror("Results", _problems(e), parent=win)
        refresh()

    ttk.Button(bar, text="Add result", command=lambda: result_dialog(
        win, principal=principal, paper=paper, after=refresh)).pack(side="left")
    ttk.Button(bar, text="Edit selected", command=edit).pack(side="left", padx=(6, 0))
    ttk.Button(bar, text="Delete selected", command=delete).pack(side="left", padx=(6, 0))
    ttk.Button(bar, text="Refresh", command=refresh).pack(side="right")
    ttk.Label(frm, text="* grade typed in rather than from the boundaries",
              foreground="#666").pack(anchor="w")
    tree.bind("<Double-1>", lambda _e: edit())
    refresh()


# ── The page ─────────────────────────────────────────────────────────

class MockExamsPage:
    TABS = ("Series", "Papers", "Mark entry", "Tiers", "Subject grades", "Analysis",
            "Timetable")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = MX.is_editor(principal)
        activity_log.record("mock.view")
        ttk.Label(parent, text="Mock Exams", font=("", 16, "bold")).pack(anchor="w")
        self.series_var = tk.StringVar()
        top = ttk.Frame(parent)
        top.pack(fill="x", pady=(2, 6))
        ttk.Label(top, text="Series:").pack(side="left")
        self.series_cb = ttk.Combobox(top, textvariable=self.series_var, state="readonly",
                                      width=48)
        self.series_cb.pack(side="left", padx=4)
        self.series_cb.bind("<<ComboboxSelected>>", lambda _e: self._series_changed())
        self.info_var = tk.StringVar()
        ttk.Label(top, textvariable=self.info_var, foreground="#666").pack(side="left", padx=8)
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._build_series(self.tabs["Series"])
        self._build_papers(self.tabs["Papers"])
        self._build_marks(self.tabs["Mark entry"])
        self._build_tiers(self.tabs["Tiers"])
        self._build_grades(self.tabs["Subject grades"])
        self._build_analysis(self.tabs["Analysis"])
        self._build_timetable(self.tabs["Timetable"])
        self._load_series_choices()
        self.book.select(self.TABS.index(state.get("tab", "Series")))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # helpers
    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, _problems(e), parent=self._top())

    def _load_series_choices(self) -> None:
        self.series_map = {f"{s.name} (Y{s.year_group}, {s.status_label})": s
                           for s in MX.list_series()}
        self.series_cb.configure(values=list(self.series_map))
        want = self.state.get("series_id")
        label = next((k for k, s in self.series_map.items() if s.series_id == want), None)
        if label is None and self.series_map:
            label = next(iter(self.series_map))
        self.series_var.set(label or "")
        self._show_info()

    def series(self) -> MX.MockSeries | None:
        s = self.series_map.get(self.series_var.get())
        return MX.get_series(s.series_id) if s else None

    def _need_series(self) -> MX.MockSeries | None:
        s = self.series()
        if s is None:
            messagebox.showinfo("Mock Exams", "Create or choose a series first.",
                                parent=self._top())
        return s

    def _show_info(self) -> None:
        s = self.series()
        self.info_var.set("" if s is None else
                          f"{s.start_date} to {s.end_date} · {s.status_label}"
                          + (f" · results released {s.released_on}" if s.released else ""))

    def _series_changed(self) -> None:
        s = self.series()
        self.state["series_id"] = s.series_id if s else None
        self._show_info()
        self._on_tab()

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        {"Series": self.refresh_series, "Papers": self.refresh_papers,
         "Mark entry": self.refresh_mark_choices, "Tiers": self.refresh_tier_choices,
         "Subject grades": self.refresh_grades, "Analysis": self.refresh_analysis,
         "Timetable": self.refresh_timetable}[name]()

    def _papers_map(self) -> dict[str, MX.MockPaper]:
        s = self.series()
        return {f"{p.paper_date} {p.label}": p for p in MX.papers(s.series_id)} if s else {}

    # Series (the old main window)
    def _build_series(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
        self.f_year = tk.StringVar(value=self.state.get("f_year", ALL))
        cb = ttk.Combobox(bar, textvariable=self.f_year, values=[ALL] + [
            str(y) for y in P.YEAR_GROUPS], state="readonly", width=5)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_series())
        ttk.Label(bar, text="Status:").pack(side="left", padx=(8, 4))
        self.f_status = tk.StringVar(value=self.state.get("f_status", ALL))
        cb = ttk.Combobox(bar, textvariable=self.f_status, values=[ALL] + list(
            MX.SERIES_STATUSES), state="readonly", width=11)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_series())
        if self.editor:
            ttk.Button(bar, text="New series", command=lambda: series_dialog(
                tab, principal=self.principal, after=self._after_series)).pack(
                side="left", padx=(12, 0))
            ttk.Button(bar, text="Edit", command=self.edit_series).pack(side="left",
                                                                        padx=(4, 0))
            ttk.Button(bar, text="Set status", command=self.series_status).pack(
                side="left", padx=(4, 0))
        ttk.Button(bar, text="Papers", command=self.goto_papers).pack(side="left", padx=(4, 0))
        if self.editor:
            ttk.Button(bar, text="Delete", command=self.delete_series).pack(side="left",
                                                                            padx=(4, 0))
        ttk.Button(bar, text="Refresh", command=self.refresh_series).pack(side="right")
        self.s_tree = _tree(tab, [("id", "ID", 50), ("year", "Yr", 50), ("start", "Start", 100),
                                  ("end", "End", 100), ("status", "Status", 100),
                                  ("name", "Name", 340), ("papers", "Papers", 70),
                                  ("released", "Released", 100)], height=14)
        self.s_tree.bind("<Double-1>", lambda _e: self.goto_papers())
        self.s_tree.bind("<<TreeviewSelect>>", lambda _e: self._pick_series_row())
        acts = ttk.Frame(tab)
        acts.pack(fill="x", pady=(6, 0))
        if self.editor:
            ttk.Button(acts, text="Release results", command=lambda: self.release(True)).pack(
                side="left")
            ttk.Button(acts, text="Withdraw release",
                       command=lambda: self.release(False)).pack(side="left", padx=(4, 0))
        ttk.Button(acts, text="History", command=self.show_history).pack(side="left",
                                                                         padx=(4, 0))

    def _after_series(self) -> None:
        self._load_series_choices()
        self.refresh_series()

    def refresh_series(self) -> None:
        self.state["f_year"], self.state["f_status"] = self.f_year.get(), self.f_status.get()
        self.s_tree.delete(*self.s_tree.get_children())
        for s in MX.list_series(year_group=self.f_year.get() or None,
                                status=self.f_status.get() or None):
            self.s_tree.insert("", "end", iid=str(s.series_id), values=(
                s.series_id, s.year_group, s.start_date, s.end_date, s.status, s.name,
                len(MX.papers(s.series_id)), s.released_on or ""))
        cur = self.series()
        if cur and self.s_tree.exists(str(cur.series_id)):
            self.s_tree.selection_set(str(cur.series_id))

    def _pick_series_row(self) -> None:
        sel = self.s_tree.selection()
        if not sel:
            return
        label = next((k for k, s in self.series_map.items() if s.series_id == int(sel[0])),
                     None)
        if label and label != self.series_var.get():
            self.series_var.set(label)
            self.state["series_id"] = int(sel[0])
            self._show_info()

    def _selected_series(self) -> MX.MockSeries | None:
        sel = self.s_tree.selection()
        if not sel:
            messagebox.showinfo("Mock Exams", "Select a series first.", parent=self._top())
            return None
        return MX.get_series(int(sel[0]))

    def edit_series(self) -> None:
        s = self._selected_series()
        if s:
            series_dialog(self.parent, principal=self.principal, series=s,
                          after=self._after_series)

    def series_status(self) -> None:
        s = self._selected_series()
        if s:
            status_dialog(self.parent, principal=self.principal, series=s,
                          after=self._after_series)

    def delete_series(self) -> None:
        s = self._selected_series()
        if s is None:
            return
        n = MX.results_count(s.series_id)
        if not messagebox.askyesno("Delete series", f"Delete {s.name}, its "
                                   f"{len(MX.papers(s.series_id))} paper(s) and {n} result(s)?",
                                   parent=self._top()):
            return
        try:
            MX.delete_series(s.series_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Delete series", e)
            return
        self._after_series()

    def goto_papers(self) -> None:
        self._pick_series_row()
        self.book.select(self.TABS.index("Papers"))

    def release(self, on: bool) -> None:
        s = self._selected_series() or self.series()
        if s is None:
            return
        if on and not messagebox.askyesno("Release results", f"Release {s.name} results to "
                                          "pupils and parents?", parent=self._top()):
            return
        try:
            MX.release_results(s.series_id, actor=self.principal, release=on)
        except _ERRORS as e:
            self._err("Release results", e)
            return
        self._after_series()

    def show_history(self) -> None:
        s = self._selected_series() or self.series()
        if s is None:
            return
        rows = MX.history(s.series_id)
        _text_window(self.parent, f"History - {s.name}", "\n".join(
            f"{h['at']}  {h['actor']:<14} {h['action']:<15} "
            + ", ".join(f"{k}={v}" for k, v in h["detail"].items()) for h in rows)
            or "No changes recorded.")

    # Papers (the old Papers window)
    def _build_papers(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        if self.editor:
            ttk.Button(bar, text="Add paper", command=self.add_paper).pack(side="left")
            ttk.Button(bar, text="Edit paper", command=self.edit_paper).pack(side="left",
                                                                            padx=(4, 0))
        ttk.Button(bar, text="Results", command=self.paper_results).pack(side="left",
                                                                         padx=(4, 0))
        ttk.Button(bar, text="Summary", command=self.paper_summary).pack(side="left",
                                                                         padx=(4, 0))
        ttk.Button(bar, text="Mark sheet", command=self.goto_marks).pack(side="left",
                                                                         padx=(4, 0))
        if self.editor:
            ttk.Button(bar, text="Delete paper", command=self.delete_paper).pack(side="left",
                                                                                padx=(4, 0))
        ttk.Button(bar, text="Refresh", command=self.refresh_papers).pack(side="right")
        self.p_tree = _tree(tab, [("id", "ID", 50), ("date", "Date", 100),
                                  ("time", "Time", 90), ("subj", "Subj", 90),
                                  ("name", "Paper", 260), ("tier", "Tier", 100),
                                  ("max", "Max", 60), ("bounds", "Boundaries", 160),
                                  ("done", "Marked", 80)], height=14)
        self.p_tree.bind("<Double-1>", lambda _e: self.paper_results())

    def refresh_papers(self) -> None:
        self.p_tree.delete(*self.p_tree.get_children())
        s = self.series()
        if s is None:
            return
        for p in MX.papers(s.series_id):
            n = len(MX.list_results(p.paper_id))
            c = len(MX.candidates(p.paper_id))
            self.p_tree.insert("", "end", iid=str(p.paper_id), values=(
                p.paper_id, p.paper_date, (p.start_time or "") + (
                    f" {p.duration_mins}m" if p.duration_mins else ""),
                p.subject_code, p.paper_name, p.tier, MX._num(p.max_marks),
                p.boundaries_text[:40] or "none", f"{n}/{c}"))

    def _paper(self) -> MX.MockPaper | None:
        sel = self.p_tree.selection()
        if not sel:
            messagebox.showinfo("Papers", "Select a paper first.", parent=self._top())
            return None
        return MX.get_paper(int(sel[0]))

    def add_paper(self) -> None:
        s = self._need_series()
        if s:
            paper_dialog(self.parent, principal=self.principal, series=s,
                         after=self.refresh_papers)

    def edit_paper(self) -> None:
        p = self._paper()
        if p:
            paper_dialog(self.parent, principal=self.principal, series=MX.get_series(
                p.series_id), paper=p, after=self.refresh_papers)

    def paper_results(self) -> None:
        p = self._paper()
        if p:
            results_window(self.parent, principal=self.principal, paper=p)

    def paper_summary(self) -> None:
        p = self._paper()
        if p:
            _text_window(self.parent, f"Summary - {p.label}", summary_text(p.paper_id))

    def delete_paper(self) -> None:
        p = self._paper()
        if p is None or not messagebox.askyesno(
                "Delete paper", f"Delete {p.label} and its "
                f"{len(MX.list_results(p.paper_id))} result(s)?", parent=self._top()):
            return
        try:
            MX.delete_paper(p.paper_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Delete paper", e)
        self.refresh_papers()

    def goto_marks(self) -> None:
        sel = self.p_tree.selection()
        if sel:
            self.state["paper_id"] = int(sel[0])
        self.book.select(self.TABS.index("Mark entry"))

    # Mark entry
    def _build_marks(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Paper:").pack(side="left")
        self.m_paper = tk.StringVar()
        self.m_cb = ttk.Combobox(bar, textvariable=self.m_paper, state="readonly", width=46)
        self.m_cb.pack(side="left", padx=4)
        self.m_cb.bind("<<ComboboxSelected>>", lambda _e: self.load_sheet())
        ttk.Button(bar, text="Save marks", command=self.save_sheet).pack(side="left",
                                                                         padx=(8, 0))
        ttk.Button(bar, text="Import CSV…", command=self.import_marks).pack(side="left",
                                                                            padx=(4, 0))
        ttk.Button(bar, text="Blank sheet CSV…", command=self.export_template).pack(
            side="left", padx=(4, 0))
        self.m_info = tk.StringVar()
        ttk.Label(tab, textvariable=self.m_info, foreground="#666", wraplength=900,
                  justify="left").pack(anchor="w")
        holder = ttk.Frame(tab)
        holder.pack(fill="both", expand=True)
        canvas = tk.Canvas(holder, highlightthickness=0)
        sb = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.m_body = ttk.Frame(canvas)
        canvas.create_window(0, 0, window=self.m_body, anchor="nw")
        self.m_body.bind("<Configure>",
                         lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        self.m_rows: dict[int, dict[str, tk.Variable]] = {}

    def refresh_mark_choices(self) -> None:
        self.m_map = self._papers_map()
        self.m_cb.configure(values=list(self.m_map))
        want = self.state.get("paper_id")
        label = next((k for k, p in self.m_map.items() if p.paper_id == want), None)
        if label is None or self.m_paper.get() not in self.m_map:
            self.m_paper.set(label or next(iter(self.m_map), ""))
        self.load_sheet()

    def load_sheet(self) -> None:
        for w in self.m_body.winfo_children():
            w.destroy()
        self.m_rows = {}
        p = self.m_map.get(self.m_paper.get()) if hasattr(self, "m_map") else None
        if p is None:
            self.m_info.set("Choose a paper (add papers on the Papers tab).")
            return
        self.state["paper_id"] = p.paper_id
        s = MX.get_series(p.series_id)
        sheet = MX.mark_sheet(p.paper_id)
        self.m_info.set(f"{p.label} · out of {MX._num(p.max_marks)} · "
                        + (f"boundaries {p.boundaries_text}" if p.boundaries else
                           "no grade boundaries yet (grades only if typed)")
                        + f" · {len(sheet)} candidate(s) · series {s.status_label.lower()}"
                        + ("" if s.status in MX.MARKING_STATUSES else
                           " - marks can't be entered now"))
        for c, text in enumerate(("Adm no", "Pupil", "Marks", "Grade", "Absent", "Reason",
                                  "Notes", "Access arrangements")):
            ttk.Label(self.m_body, text=text, font=("", 9, "bold")).grid(
                row=0, column=c, sticky="w", padx=3)
        grades = [""] + list(MX.grades_for(p.tier))
        for i, (pupil, r, access) in enumerate(sheet, start=1):
            mine = MX.can_mark(self.principal, p, s, pupil.pupil_id)
            v = {"marks_awarded": tk.StringVar(value=MX._num(r.marks_awarded) if r else ""),
                 "grade": tk.StringVar(value=(r.grade or "") if r and
                                       r.grade_source == "manual" else ""),
                 "absent": tk.BooleanVar(value=bool(r and r.absent)),
                 "absence_reason": tk.StringVar(value=(r.absence_reason or "") if r else ""),
                 "notes": tk.StringVar(value=(r.notes or "") if r else "")}
            state = "normal" if mine else "disabled"
            ttk.Label(self.m_body, text=pupil.admission_no).grid(row=i, column=0, sticky="w",
                                                                 padx=3)
            ttk.Label(self.m_body, text=pupil.display_name
                      + (f"  → {r.grade}" if r and r.grade else "")).grid(
                row=i, column=1, sticky="w", padx=3)
            ttk.Entry(self.m_body, textvariable=v["marks_awarded"], width=6,
                      state=state).grid(row=i, column=2, padx=3)
            ttk.Combobox(self.m_body, textvariable=v["grade"], values=grades, width=5,
                         state="readonly" if mine else "disabled").grid(row=i, column=3,
                                                                        padx=3)
            ttk.Checkbutton(self.m_body, variable=v["absent"], state=state).grid(
                row=i, column=4, padx=3)
            ttk.Combobox(self.m_body, textvariable=v["absence_reason"],
                         values=[""] + list(MX.ABSENCE_REASONS), width=10,
                         state="readonly" if mine else "disabled").grid(row=i, column=5,
                                                                        padx=3)
            ttk.Entry(self.m_body, textvariable=v["notes"], width=22, state=state).grid(
                row=i, column=6, padx=3)
            ttk.Label(self.m_body, text=access or "", foreground="#a60").grid(
                row=i, column=7, sticky="w", padx=3)
            if mine:
                self.m_rows[pupil.pupil_id] = v

    def save_sheet(self) -> None:
        p = self.m_map.get(self.m_paper.get()) if hasattr(self, "m_map") else None
        if p is None or not self.m_rows:
            return
        rows = {}
        for pid, v in self.m_rows.items():
            absent = v["absent"].get()
            rows[pid] = {"marks_awarded": "" if absent else v["marks_awarded"].get(),
                         "grade": "" if absent else v["grade"].get(),
                         "absent": "Y" if absent else "",
                         "absence_reason": v["absence_reason"].get() if absent else "",
                         "notes": v["notes"].get()}
        try:
            n = MX.save_sheet(p.paper_id, rows, actor=self.principal)
        except _ERRORS as e:
            self._err("Save marks", e)
            return
        messagebox.showinfo("Save marks", f"{n} result(s) saved.", parent=self._top())
        self.load_sheet()

    def import_marks(self) -> None:
        p = self.m_map.get(self.m_paper.get()) if hasattr(self, "m_map") else None
        if p is None:
            return
        path = filedialog.askopenfilename(parent=self._top(), title="Marks CSV",
                                          filetypes=[("CSV", "*.csv"), ("All files", "*")])
        if not path:
            return
        try:
            n = MX.import_marks(p.paper_id, path, actor=self.principal)
        except (*_ERRORS, OSError, UnicodeDecodeError) as e:
            self._err("Import marks", e)
            return
        messagebox.showinfo("Import marks", f"{n} result(s) changed.", parent=self._top())
        self.load_sheet()

    def export_template(self) -> None:
        p = self.m_map.get(self.m_paper.get()) if hasattr(self, "m_map") else None
        if p is None:
            return
        path = filedialog.asksaveasfilename(parent=self._top(), title="Blank mark sheet",
                                            defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n = MX.export_sheet_template(p.paper_id, path, actor=self.principal)
        except (*_ERRORS, OSError) as e:
            self._err("Mark sheet", e)
            return
        messagebox.showinfo("Mark sheet", f"{n} candidate(s) written.", parent=self._top())

    # Tiers
    def _build_tiers(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Subject:").pack(side="left")
        self.t_subject = tk.StringVar()
        self.t_cb = ttk.Combobox(bar, textvariable=self.t_subject, state="readonly", width=30)
        self.t_cb.pack(side="left", padx=4)
        self.t_cb.bind("<<ComboboxSelected>>", lambda _e: self.load_tiers())
        ttk.Button(bar, text="Save tiers", command=self.save_tiers).pack(side="left",
                                                                         padx=(8, 0))
        ttk.Label(tab, text="Enter each pupil for Foundation or Higher. A tiered paper's "
                            "candidates are the pupils entered for its tier.",
                  foreground="#666").pack(anchor="w")
        self.t_body = ttk.Frame(tab)
        self.t_body.pack(fill="both", expand=True)
        self.t_rows: dict[int, tk.StringVar] = {}

    def refresh_tier_choices(self) -> None:
        s = self.series()
        subs = {}
        if s:
            for p in MX.papers(s.series_id):
                if p.tier in MX.ENTRY_TIERS:
                    subs[f"{p.subject_code} - {p.subject_name}"] = p.subject_id
        self.t_map = subs
        self.t_cb.configure(values=list(subs))
        if self.t_subject.get() not in subs:
            self.t_subject.set(next(iter(subs), ""))
        self.load_tiers()

    def load_tiers(self) -> None:
        for w in self.t_body.winfo_children():
            w.destroy()
        self.t_rows = {}
        s = self.series()
        sid = getattr(self, "t_map", {}).get(self.t_subject.get())
        if s is None or sid is None:
            ttk.Label(self.t_body, text="No Foundation / Higher papers in this series.",
                      foreground="#777").pack(anchor="w")
            return
        current = MX.entries(s.series_id, sid)
        grid = ttk.Frame(self.t_body)
        grid.pack(anchor="w")
        for i, pupil in enumerate(MX.subject_pupils(s, sid)):
            mine = MX.is_editor(self.principal) or MX.teaches(self.principal, pupil.pupil_id,
                                                              sid, s.academic_year)
            var = tk.StringVar(value=current.get(pupil.pupil_id, ""))
            r, c = divmod(i, 2)
            ttk.Label(grid, text=f"{pupil.admission_no}  {pupil.display_name}").grid(
                row=r, column=c * 2, sticky="w", padx=(0, 6), pady=1)
            ttk.Combobox(grid, textvariable=var, values=["", *MX.ENTRY_TIERS], width=11,
                         state="readonly" if mine else "disabled").grid(
                row=r, column=c * 2 + 1, sticky="w", padx=(0, 24))
            if mine:
                self.t_rows[pupil.pupil_id] = var

    def save_tiers(self) -> None:
        s = self.series()
        sid = getattr(self, "t_map", {}).get(self.t_subject.get())
        if s is None or sid is None:
            return
        try:
            n = MX.set_tiers(s.series_id, sid, {k: v.get() or None
                                                for k, v in self.t_rows.items()},
                             actor=self.principal)
        except _ERRORS as e:
            self._err("Tiers", e)
            return
        messagebox.showinfo("Tiers", f"{n} entr(y/ies) changed.", parent=self._top())
        self.load_tiers()

    # Subject grades
    def _build_grades(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Subject:").pack(side="left")
        self.g_subject = tk.StringVar(value=ALL)
        self.g_cb = ttk.Combobox(bar, textvariable=self.g_subject, state="readonly", width=30)
        self.g_cb.pack(side="left", padx=4)
        self.g_cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_grades())
        ttk.Button(bar, text="Pupil report", command=self.pupil_report).pack(side="left",
                                                                             padx=(8, 0))
        ttk.Button(bar, text="View profile", command=self.view_profile).pack(side="left",
                                                                             padx=(4, 0))
        ttk.Button(bar, text="Export CSV…", command=self.export_results).pack(side="left",
                                                                              padx=(4, 0))
        ttk.Button(bar, text="Refresh", command=self.refresh_grades).pack(side="right")
        self.g_tree = _tree(tab, [("adm", "Adm no", 90), ("name", "Pupil", 180),
                                  ("subj", "Subject", 120), ("tier", "Tier", 80),
                                  ("marks", "Marks", 90), ("pct", "%", 60),
                                  ("grade", "Grade", 60), ("target", "Target", 60),
                                  ("vs", "Against target", 110), ("detail", "Note", 160),
                                  ("pid", "", 0)], height=16)
        self.g_tree.column("pid", width=0, stretch=False)
        self.g_tree.bind("<Double-1>", lambda _e: self.pupil_report())
        self.g_info = tk.StringVar()
        ttk.Label(tab, textvariable=self.g_info, foreground="#666").pack(anchor="w",
                                                                        pady=(4, 0))

    def refresh_grades(self) -> None:
        s = self.series()
        self.g_tree.delete(*self.g_tree.get_children())
        if s is None:
            return
        subs = {f"{p.subject_code} - {p.subject_name}": p.subject_id
                for p in MX.papers(s.series_id)}
        self.g_cb.configure(values=[ALL] + list(subs))
        if self.g_subject.get() not in subs:
            self.g_subject.set(ALL)
        rows = MX.subject_results(s.series_id, subject_id=subs.get(self.g_subject.get()))
        for i, r in enumerate(rows):
            self.g_tree.insert("", "end", iid=str(i), tags=(r["vs_target"],), values=(
                r["pupil"].admission_no, r["pupil"].display_name, r["subject_code"], r["tier"],
                f"{MX._num(r['marks'])}/{MX._num(r['max'])}" if r["marks"] is not None else "",
                r["pct"] if r["pct"] is not None else "", r["grade"] or "", r["target"] or "",
                r["vs_target"], r["note"], r["pupil"].pupil_id))
        below = sum(1 for r in rows if r["vs_target"] in ("Below", "Well below"))
        self.g_info.set(f"{len(rows)} pupil-subject result(s) · {below} below target")

    def _grade_pupil(self) -> int | None:
        sel = self.g_tree.selection()
        if not sel:
            messagebox.showinfo("Subject grades", "Select a pupil first.", parent=self._top())
            return None
        return int(self.g_tree.set(sel[0], "pid"))

    def pupil_report(self) -> None:
        s = self.series()
        pid = self._grade_pupil() if s else None
        if pid is None:
            return
        rep = MX.pupil_report(s.series_id, pid)  # type: ignore[union-attr]
        lines = [f"{rep['pupil'].display_name} ({rep['pupil'].admission_no}) - "
                 f"{rep['series'].name}", ""]
        for r in rep["subjects"]:
            lines.append(f"{r['subject_name'][:24]:<24} {r['tier']:<10} "
                         f"{(r['grade'] or '-'):<5} target {(r['target'] or '-'):<4} "
                         f"{r['vs_target']:<11} {r['note']}")
        lines += ["", "Papers:"]
        for p, res in rep["papers"]:
            lines.append(f"  {p.paper_date} {p.label[:30]:<30} " + (
                "absent" if res.absent else f"{MX._num(res.marks_awarded)}/"
                f"{MX._num(p.max_marks)} {res.grade or ''}"))
        _text_window(self.parent, "Pupil mock report", "\n".join(lines))

    def view_profile(self) -> None:
        pid = self._grade_pupil()
        if pid is not None and self.open_pupil:
            self.open_pupil(pid)

    def export_results(self) -> None:
        s = self._need_series()
        if s is None:
            return
        path = filedialog.asksaveasfilename(parent=self._top(), title="Export mock results",
                                            defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n = MX.export_results(s.series_id, path, actor=self.principal)
        except (*_ERRORS, OSError) as e:
            self._err("Export", e)
            return
        messagebox.showinfo("Export", f"{n} row(s) written.", parent=self._top())

    # Analysis
    def _build_analysis(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Compare with:").pack(side="left")
        self.a_earlier = tk.StringVar()
        self.a_cb = ttk.Combobox(bar, textvariable=self.a_earlier, state="readonly", width=40)
        self.a_cb.pack(side="left", padx=4)
        ttk.Button(bar, text="Compare", command=self.compare).pack(side="left")
        ttk.Button(bar, text="Below target", command=self.below_target).pack(side="left",
                                                                             padx=(8, 0))
        ttk.Button(bar, text="Missing marks", command=self.missing).pack(side="left",
                                                                         padx=(4, 0))
        ttk.Button(bar, text="Refresh", command=self.refresh_analysis).pack(side="right")
        self.a_tree = _tree(tab, [("subj", "Subject", 180), ("pupils", "Pupils", 60),
                                  ("graded", "Graded", 60), ("avg", "Avg %", 60),
                                  ("p4", "4+ %", 60), ("p5", "5+ %", 60), ("p7", "7+ %", 60),
                                  ("below", "Below target", 90),
                                  ("detail", "Grades", 300)], height=14)

    def refresh_analysis(self) -> None:
        s = self.series()
        self.a_tree.delete(*self.a_tree.get_children())
        others = {x.name: x for x in MX.list_series()
                  if s and x.series_id != s.series_id}
        self.a_cb.configure(values=list(others))
        self.a_map = others
        if s is None:
            return
        for r in MX.subject_summary(s.series_id):
            def pc(v):
                return "" if v is None else v
            dist = r["distribution"]
            order = sorted(dist, key=lambda g: -(MX.grade_value(g) or 0))
            self.a_tree.insert("", "end", values=(
                f"{r['subject_code']} {r['subject_name']}", r["pupils"], r["graded"],
                pc(r["avg_pct"]), pc(r["pct4"]), pc(r["pct5"]), pc(r["pct7"]),
                r["below_target"], "  ".join(f"{g}:{dist[g]}" for g in order)))

    def compare(self) -> None:
        s = self.series()
        earlier = getattr(self, "a_map", {}).get(self.a_earlier.get())
        if s is None or earlier is None:
            messagebox.showinfo("Compare", "Choose the series to compare with.",
                                parent=self._top())
            return
        rows = MX.compare_series(s.series_id, earlier.series_id)
        up = sum(1 for r in rows if r["change"] > 0)
        down = sum(1 for r in rows if r["change"] < 0)
        lines = [f"{s.name} against {earlier.name}: {len(rows)} pupil-subject(s), "
                 f"{up} up, {down} down", ""]
        for r in sorted(rows, key=lambda x: x["change"]):
            lines.append(f"{r['pupil'].display_name[:24]:<24} {r['subject_code']:<6} "
                         f"{r['earlier']:>4} → {r['grade']:<4} ({r['change']:+g})")
        _text_window(self.parent, "Compare series", "\n".join(lines))

    def below_target(self) -> None:
        s = self._need_series()
        if s is None:
            return
        rows = MX.below_target(s.series_id)
        _text_window(self.parent, "Below target", "\n".join(
            f"{r['pupil'].display_name[:24]:<24} {r['subject_code']:<6} {r['grade']:<4} "
            f"target {r['target']:<4} {r['vs_target']}" for r in rows)
            or "Nobody below target (or no targets set).")

    def missing(self) -> None:
        s = self._need_series()
        if s is None:
            return
        rows = MX.missing_marks(s.series_id)
        _text_window(self.parent, "Missing marks", "\n".join(
            f"{p.paper_date} {p.label}: " + ", ".join(x.display_name for x in ms)
            for p, ms in rows) or "Every candidate has a result.")

    # Timetable
    def _build_timetable(self, tab: ttk.Frame) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="Clashes…", command=self.show_clashes).pack(side="left")
        ttk.Button(bar, text="Access arrangements…", command=self.show_access).pack(
            side="left", padx=(4, 0))
        ttk.Button(bar, text="Refresh", command=self.refresh_timetable).pack(side="right")
        self.tt_tree = _tree(tab, [("date", "Date", 100), ("time", "Time", 110),
                                   ("name", "Paper", 260), ("room", "Room", 80),
                                   ("cands", "Candidates", 80), ("access", "Access arr.", 80),
                                   ("detail", "Clashes", 280)], height=16)

    def refresh_timetable(self) -> None:
        s = self.series()
        self.tt_tree.delete(*self.tt_tree.get_children())
        if s is None:
            return
        for i, row in enumerate(MX.timetable(s.series_id)):
            p = row["paper"]
            w = p.window()
            self.tt_tree.insert("", "end", iid=str(p.paper_id),
                                tags=("clash",) if row["clashes"] else (), values=(
                p.paper_date, f"{w[0]:%H:%M}-{w[1]:%H:%M}" if w else "not set", p.label,
                p.room or "", row["candidates"], row["access"] or "",
                "; ".join(f"{q.label} ({n})" for q, n in row["clashes"])))

    def show_clashes(self) -> None:
        s = self._need_series()
        if s is None:
            return
        rows = MX.clashes(s.series_id)
        _text_window(self.parent, "Clashes", "\n\n".join(
            f"{p.paper_date}: {p.label} {p.start_time} and {q.label} {q.start_time}\n  "
            + ", ".join(x.display_name for x in ps) for p, q, ps in rows) or "No clashes.")

    def show_access(self) -> None:
        sel = self.tt_tree.selection()
        if not sel:
            messagebox.showinfo("Access arrangements", "Select a paper first.",
                                parent=self._top())
            return
        p = MX.get_paper(int(sel[0]))
        acc = MX.access_arrangements(p.paper_id)
        names = {x.pupil_id: x for x in MX.candidates(p.paper_id)}
        _text_window(self.parent, f"Access arrangements - {p.label}", "\n".join(
            f"{names[k].display_name:<26} {v}" for k, v in acc.items())
            or "No candidates with access arrangements.")


def draw_mock_exams(parent: ttk.Frame, *, principal: Principal, state: dict,
                    open_pupil: Callable[[int], None] | None = None) -> MockExamsPage:
    return MockExamsPage(parent, principal=principal, state=state, open_pupil=open_pupil)


def draw_profile_mocks(parent: ttk.Frame, pupil: P.Pupil) -> None:
    """The pupil's latest mock series on their profile."""
    rows = MX.results_for_pupil(pupil.pupil_id)
    if not rows:
        return
    s = rows[0][0]
    box = ttk.LabelFrame(parent, text=f"Mock exams - {s.name}", padding=8)
    box.pack(fill="x", pady=(8, 0))
    for r in MX.subject_results(s.series_id, pupil_id=pupil.pupil_id):
        ttk.Label(box, text=f"{r['subject_code']}: {r['grade'] or '-'}"
                            + (f" ({r['pct']}%)" if r["pct"] is not None else "")
                            + (f" · target {r['target']} - {r['vs_target'].lower()}"
                               if r["target"] else "")
                            + (f" · {r['note']}" if r["note"] else ""),
                  foreground="#a00" if r["vs_target"] in ("Below", "Well below") else ""
                  ).pack(anchor="w")
    if not s.released:
        ttk.Label(box, text="Not yet released to the pupil.", foreground="#777").pack(
            anchor="w")
