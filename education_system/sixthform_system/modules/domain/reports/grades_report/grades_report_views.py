"""Tkinter views for the Sixth Form Grades Report."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.sixthform_system.modules.domain.reports.grades_report import grades_report
from education_system.sixthform_system.modules.domain.students.students import students
from education_system.sixthform_system.modules.domain.reports.grades_report import grades_report as data
from education_system.sixthform_system.modules.domain.students.students import students as student_data
from education_system.sixthform_system.modules.domain.academics.subjects import subjects as subject_data
from education_system.shared import branding
from education_system.sixthform_system.modules.domain.reports.grades_report.grades_report import (
    GradeDistribution,
    LETTER_GRADES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_grades_report_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Grades Report — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    CohortTab(nb)
    PerStudentTab(nb)
    PerSubjectTab(nb)
    PredVsActualTab(nb)
    AlertsTab(nb)


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}") for s in rows]


def _subject_names() -> list[str]:
    try:
        rows = subject_data.list_subjects()
    except Exception:
        return []
    out: list[str] = []
    for s in rows:
        n = getattr(s, "name", None) or getattr(s, "subject", None)
        if n:
            out.append(n)
    return sorted(set(out))


def _delta(d: int | None) -> str:
    if d is None:
        return "—"
    return f"+{d}" if d > 0 else str(d)


# ══ Shared distribution widget ═════════════════════════════════════

class DistributionPanel:
    """A reusable side-by-side widget: bar table + summary stats."""

    def __init__(self, parent: tk.Misc, title: str) -> None:
        self.frame = ttk.LabelFrame(parent, text=title)
        cols = ("grade", "count", "bar")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings", height=8)
        self.tree.heading("grade", text="Grade")
        self.tree.heading("count", text="#")
        self.tree.heading("bar", text="Bar")
        self.tree.column("grade", width=60, anchor="w")
        self.tree.column("count", width=60, anchor="e")
        self.tree.column("bar", width=160, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=6, pady=(6, 2))
        self.stats_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.stats_var,
                   justify="left", anchor="w").pack(
            fill="x", padx=6, pady=(0, 6))

    def update(self, dist: GradeDistribution) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        max_n = max(dist.by_grade.values()) if dist.total else 0
        for g in LETTER_GRADES:
            n = dist.by_grade.get(g, 0)
            bar = "█" * int(20 * n / max_n) if max_n else ""
            self.tree.insert("", "end", values=(g, n, bar))
        if dist.total == 0:
            self.stats_var.set("(no data)")
        else:
            self.stats_var.set(
                f"Total: {dist.total}    "
                f"Avg pts: {dist.average_points}    "
                f"Pass (A*–E): {dist.pass_count} "
                f"({dist.pass_pct}%)    "
                f"Top (A*–C): {dist.top_count} ({dist.top_pct}%)"
            )


# ══ Cohort tab ═════════════════════════════════════════════════════

class CohortTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Cohort")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Subject:").pack(side="left")
        self.subject_cb = ttk.Combobox(bar,
                                          values=[""] + _subject_names(),
                                          state="readonly", width=24)
        self.subject_cb.current(0)
        self.subject_cb.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Year:").pack(side="left")
        self.year_e = ttk.Entry(bar, width=8)
        self.year_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Run",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Refresh subjects",
                    command=self._refresh_subjects).pack(side="left")

        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   anchor="w").pack(fill="x", padx=12, pady=(0, 8))

        panes = ttk.Frame(self.frame)
        panes.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.pred = DistributionPanel(panes, "Predicted")
        self.mock = DistributionPanel(panes, "Mock")
        self.actual = DistributionPanel(panes, "Actual")
        self.pred.frame.pack(side="left", fill="both", expand=True,
                                padx=2)
        self.mock.frame.pack(side="left", fill="both", expand=True,
                                padx=2)
        self.actual.frame.pack(side="left", fill="both", expand=True,
                                  padx=2)

    def _refresh_subjects(self) -> None:
        self.subject_cb["values"] = [""] + _subject_names()
        self.subject_cb.current(0)

    def refresh(self) -> None:
        sub = self.subject_cb.get().strip() or None
        yr = self.year_e.get().strip()
        try:
            y = int(yr) if yr else None
        except ValueError:
            messagebox.showerror("Cohort", "Year must be a number.")
            return
        try:
            r = data.cohort_grade_report(year=y, subject=sub)
        except ValidationError as e:
            messagebox.showerror("Cohort", str(e))
            return
        self.summary_var.set(
            f"Subject: {sub or '(all)'}    "
            f"Year: {y if y else '(all)'}    "
            f"Predicted rows: {r.predicted_subjects}    "
            f"Mock papers: {r.mock_papers}    "
            f"Actual results: {r.actual_papers}"
        )
        self.pred.update(r.predicted)
        self.mock.update(r.mock)
        self.actual.update(r.actual)


# ══ Per-Student tab ════════════════════════════════════════════════

class PerStudentTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Per-Student")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Student:").pack(side="left")
        opts = _student_options()
        self._sids = [s for s, _ in opts]
        self.student_cb = ttk.Combobox(bar,
                                          values=[l for _, l in opts],
                                          state="readonly", width=40)
        if opts:
            self.student_cb.current(0)
        self.student_cb.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Run",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Refresh roster",
                    command=self._refresh_roster).pack(side="left")

        self.head_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.head_var,
                   anchor="w", font=("", 10, "bold")).pack(
            fill="x", padx=12, pady=(0, 4))

        self.avg_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.avg_var,
                   anchor="w").pack(fill="x", padx=12)

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("subject", "pred", "mock", "actual",
                "dmock", "dactual")
        widths = {"subject": 220, "pred": 80, "mock": 80,
                  "actual": 80, "dmock": 80, "dactual": 90}
        heads = {"subject": "Subject", "pred": "Predicted",
                 "mock": "Latest mock", "actual": "Best actual",
                 "dmock": "Δ Mock", "dactual": "Δ Actual"}
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        for c in cols:
            self.tree.heading(c, text=heads[c])
            anchor = "e" if c in ("dmock", "dactual") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("below", background="#ffe0e0")
        self.tree.tag_configure("above", background="#e0ffe0")

        self.notes_text = tk.Text(self.frame, wrap="word", height=6,
                                     state="disabled")
        self.notes_text.pack(fill="x", padx=8, pady=(4, 8))

    def _refresh_roster(self) -> None:
        opts = _student_options()
        self._sids = [s for s, _ in opts]
        self.student_cb["values"] = [l for _, l in opts]
        if opts:
            self.student_cb.current(0)

    def refresh(self) -> None:
        idx = self.student_cb.current()
        if idx < 0:
            return
        sid = self._sids[idx]
        try:
            r = data.per_student_grade_report(sid)
        except ValidationError as e:
            messagebox.showerror("Per-student", str(e))
            return
        self.head_var.set(f"{r.student_id} — {r.full_name}")
        self.avg_var.set(
            f"Average points  →  predicted: {r.avg_predicted}    "
            f"mock: {r.avg_mock}    actual: {r.avg_actual}"
        )
        for i in self.tree.get_children():
            self.tree.delete(i)
        for row in r.subjects:
            tags: list[str] = []
            if row.delta_actual_vs_pred is not None:
                if row.delta_actual_vs_pred < 0:
                    tags.append("below")
                elif row.delta_actual_vs_pred > 0:
                    tags.append("above")
            elif row.delta_mock_vs_pred is not None:
                if row.delta_mock_vs_pred <= -2:
                    tags.append("below")
                elif row.delta_mock_vs_pred > 0:
                    tags.append("above")
            self.tree.insert("", "end", values=(
                row.subject,
                row.predicted_grade or "—",
                row.latest_mock_grade or "—",
                row.best_actual_grade or "—",
                _delta(row.delta_mock_vs_pred),
                _delta(row.delta_actual_vs_pred),
            ), tags=tuple(tags))
        self.notes_text.configure(state="normal")
        self.notes_text.delete("1.0", "end")
        if r.notes:
            self.notes_text.insert("1.0", "\n".join(
                f"• {n}" for n in r.notes))
        self.notes_text.configure(state="disabled")


# ══ Per-Subject tab ════════════════════════════════════════════════

class PerSubjectTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Per-Subject")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Subject:").pack(side="left")
        self.subject_cb = ttk.Combobox(bar,
                                          values=_subject_names(),
                                          state="readonly", width=24)
        names = _subject_names()
        if names:
            self.subject_cb.current(0)
        self.subject_cb.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Year:").pack(side="left")
        self.year_e = ttk.Entry(bar, width=8)
        self.year_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Run",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Refresh subjects",
                    command=self._refresh_subjects).pack(side="left")

        self.head_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.head_var,
                   anchor="w", font=("", 10, "bold")).pack(
            fill="x", padx=12, pady=(0, 4))

        panes = ttk.Frame(self.frame)
        panes.pack(fill="x", padx=8, pady=(0, 4))
        self.pred = DistributionPanel(panes, "Predicted")
        self.mock = DistributionPanel(panes, "Mock")
        self.actual = DistributionPanel(panes, "Actual")
        self.pred.frame.pack(side="left", fill="both", expand=True,
                                padx=2)
        self.mock.frame.pack(side="left", fill="both", expand=True,
                                padx=2)
        self.actual.frame.pack(side="left", fill="both", expand=True,
                                  padx=2)

        bottom = ttk.Frame(self.frame)
        bottom.pack(fill="both", expand=True, padx=8, pady=4)
        topf = ttk.LabelFrame(bottom, text="Top predicted")
        botf = ttk.LabelFrame(bottom, text="Lowest predicted")
        topf.pack(side="left", fill="both", expand=True, padx=2)
        botf.pack(side="left", fill="both", expand=True, padx=2)
        cols = ("student", "name", "grade")
        widths = {"student": 90, "name": 220, "grade": 60}
        self.top_tree = ttk.Treeview(topf, columns=cols, show="headings",
                                        height=6)
        self.bot_tree = ttk.Treeview(botf, columns=cols, show="headings",
                                        height=6)
        for tr in (self.top_tree, self.bot_tree):
            for c in cols:
                tr.heading(c, text=c.capitalize())
                tr.column(c, width=widths[c],
                            anchor="e" if c == "grade" else "w")
            tr.pack(fill="both", expand=True, padx=6, pady=6)

    def _refresh_subjects(self) -> None:
        names = _subject_names()
        self.subject_cb["values"] = names
        if names:
            self.subject_cb.current(0)

    def refresh(self) -> None:
        sub = self.subject_cb.get().strip()
        if not sub:
            messagebox.showinfo("Per-subject",
                                  "Pick a subject first.")
            return
        yr = self.year_e.get().strip()
        try:
            y = int(yr) if yr else None
        except ValueError:
            messagebox.showerror("Per-subject", "Year must be a number.")
            return
        try:
            r = data.per_subject_report(sub, year=y)
        except ValidationError as e:
            messagebox.showerror("Per-subject", str(e))
            return
        self.head_var.set(
            f"Subject: {r.subject}    "
            f"Year: {y if y else '(all)'}")
        self.pred.update(r.predicted)
        self.mock.update(r.mock)
        self.actual.update(r.actual)
        for i in self.top_tree.get_children():
            self.top_tree.delete(i)
        for sid, name, g in r.top_predicted:
            self.top_tree.insert("", "end", values=(sid, name, g))
        for i in self.bot_tree.get_children():
            self.bot_tree.delete(i)
        for sid, name, g in r.bottom_predicted:
            self.bot_tree.insert("", "end", values=(sid, name, g))


# ══ Predicted vs Actual tab ════════════════════════════════════════

class PredVsActualTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Pred vs Actual")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Subject:").pack(side="left")
        self.subject_cb = ttk.Combobox(bar,
                                          values=[""] + _subject_names(),
                                          state="readonly", width=24)
        self.subject_cb.current(0)
        self.subject_cb.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Year:").pack(side="left")
        self.year_e = ttk.Entry(bar, width=8)
        self.year_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Run",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Refresh subjects",
                    command=self._refresh_subjects).pack(side="left")

        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   anchor="w").pack(fill="x", padx=12, pady=(0, 4))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("student", "name", "subject", "pred", "actual", "delta")
        widths = {"student": 90, "name": 220, "subject": 220,
                  "pred": 80, "actual": 80, "delta": 80}
        heads = {"student": "Student", "name": "Name",
                 "subject": "Subject", "pred": "Predicted",
                 "actual": "Actual", "delta": "Δ"}
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        for c in cols:
            self.tree.heading(c, text=heads[c])
            anchor = "e" if c == "delta" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("below", background="#ffe0e0")
        self.tree.tag_configure("above", background="#e0ffe0")

    def _refresh_subjects(self) -> None:
        self.subject_cb["values"] = [""] + _subject_names()
        self.subject_cb.current(0)

    def refresh(self) -> None:
        sub = self.subject_cb.get().strip() or None
        yr = self.year_e.get().strip()
        try:
            y = int(yr) if yr else None
        except ValueError:
            messagebox.showerror("Pred vs Actual",
                                  "Year must be a number.")
            return
        try:
            rows = data.compare_predicted_vs_actual(year=y,
                                                       subject=sub)
        except ValidationError as e:
            messagebox.showerror("Pred vs Actual", str(e))
            return
        for i in self.tree.get_children():
            self.tree.delete(i)
        above = on = below = 0
        for r in rows:
            tags = []
            if r.delta > 0:
                above += 1
                tags.append("above")
            elif r.delta < 0:
                below += 1
                tags.append("below")
            else:
                on += 1
            self.tree.insert("", "end", values=(
                r.student_id, r.full_name, r.subject,
                r.predicted_grade, r.actual_grade, _delta(r.delta)
            ), tags=tuple(tags))
        self.summary_var.set(
            f"{len(rows)} comparison(s).  "
            f"Beat: {above}   On: {on}   Below: {below}"
        )


# ══ Alerts tab ═════════════════════════════════════════════════════

class AlertsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Alerts")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar,
                   text="Flag if mock is N grades below prediction:").pack(
            side="left")
        self.gap_e = ttk.Entry(bar, width=4)
        self.gap_e.insert(0, "2")
        self.gap_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar,
                   text="Min target points (blank=skip):").pack(side="left")
        self.target_e = ttk.Entry(bar, width=4)
        self.target_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="(A*=6 A=5 B=4 C=3 D=2 E=1)",
                   foreground="#888").pack(side="left")
        ttk.Button(bar, text="Run",
                    command=self.refresh).pack(side="left", padx=(10, 4))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("student", "name", "subject", "pred", "mock", "reasons")
        widths = {"student": 90, "name": 200, "subject": 220,
                  "pred": 70, "mock": 70, "reasons": 460}
        heads = {"student": "Student", "name": "Name",
                 "subject": "Subject", "pred": "Pred",
                 "mock": "Mock", "reasons": "Reasons"}
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("alert", background="#ffe0e0")

        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        try:
            gap = int(self.gap_e.get().strip() or "2")
            tgt = self.target_e.get().strip()
            target = int(tgt) if tgt else None
        except ValueError:
            messagebox.showerror("Alerts", "Numeric values required.")
            return
        try:
            rows = data.alerts(mock_below_pred_by=gap,
                                  min_target_pred_points=target)
        except ValidationError as e:
            messagebox.showerror("Alerts", str(e))
            return
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in rows:
            self.tree.insert("", "end", values=(
                r.student_id, r.full_name, r.subject,
                r.predicted or "—", r.latest_mock or "—",
                "; ".join(r.reasons),
            ), tags=("alert",))
        self.summary_var.set(f"{len(rows)} alert(s).")
