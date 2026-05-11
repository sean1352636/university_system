"""Tkinter views for the Sixth Form Attendance Report."""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Callable
from education_system.sixthform_system.modules.domain.attendance_report import attendance_report
from education_system.sixthform_system.modules.domain.class_groups import class_groups
from education_system.sixthform_system.modules.domain.students import students as data
from education_system.sixthform_system.modules.domain.class_groups import class_groups as cg_data
from education_system.sixthform_system.modules.domain.students import students as student_data
from education_system.sixthform_system.modules.domain.attendance_report.attendance_report import (
    DOW_NAMES,
    StatusBreakdown,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_attendance_report_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title("Attendance Report — Sixth Form System")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    CohortTab(nb)
    PerStudentTab(nb)
    PerGroupTab(nb)
    DailyTab(nb)
    DowTab(nb)
    RiskTab(nb)


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v:.1f}%"


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}") for s in rows]


def _group_options() -> list[tuple[int | None, str]]:
    groups = cg_data.list_groups()
    return [(None, "(all)")] + [(g.group_id,
                                    f"#{g.group_id} — {g.group_name}")
                                  for g in groups]


# ══ Cohort tab ═════════════════════════════════════════════════════

class CohortTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Cohort")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="From:").pack(side="left")
        self.from_e = ttk.Entry(bar, width=12)
        self.from_e.pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="To:").pack(side="left")
        self.to_e = ttk.Entry(bar, width=12)
        self.to_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Window (days):").pack(side="left")
        self.window_e = ttk.Entry(bar, width=4)
        self.window_e.insert(0, "28")
        self.window_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Group:").pack(side="left")
        opts = _group_options()
        self._gids = [g for g, _ in opts]
        self.group_cb = ttk.Combobox(bar, values=[l for _, l in opts],
                                        state="readonly", width=28)
        self.group_cb.current(0)
        self.group_cb.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Threshold %:").pack(side="left")
        self.thr_e = ttk.Entry(bar, width=5)
        self.thr_e.insert(0, "90")
        self.thr_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Run",
                    command=self.refresh).pack(side="left", padx=(10, 4))
        ttk.Button(bar, text="Refresh groups",
                    command=self._refresh_groups).pack(side="left")

        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10), state="disabled")
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _refresh_groups(self) -> None:
        opts = _group_options()
        self._gids = [g for g, _ in opts]
        self.group_cb["values"] = [l for _, l in opts]
        self.group_cb.current(0)

    def refresh(self) -> None:
        try:
            r = data.cohort_report(
                date_from=self.from_e.get().strip() or None,
                date_to=self.to_e.get().strip() or None,
                window_days=int(self.window_e.get().strip() or "28"),
                group_id=self._gids[self.group_cb.current()]
                          if self.group_cb.current() >= 0 else None,
                threshold_pct=float(self.thr_e.get().strip() or "90"),
            )
        except (ValidationError, ValueError) as e:
            messagebox.showerror("Cohort", str(e))
            return
        b = r.breakdown
        L = [
            f"Cohort report",
            f"=============",
            f"  Window         : {r.date_from} → {r.date_to}",
            f"  Group filter   : "
            + (f"#{r.breakdown and ''}"
                if False else
                ("(all)" if self.group_cb.current() == 0
                 else self.group_cb.get())),
            f"  Sessions       : {r.sessions}",
            f"  Distinct students: {r.student_count}",
            "",
            f"  Total records  : {b.total}",
            f"    Present      : {b.present}",
            f"    Late         : {b.late}",
            f"    Absent       : {b.absent}",
            f"    Authorised   : {b.authorised}",
            f"  Attendance     : {_pct(b.percentage)}",
            "",
            f"  Students below {r.threshold_pct}% : "
            f"{r.students_below_threshold}",
        ]
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(L))
        self.text.configure(state="disabled")


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
        ttk.Label(bar, text="From:").pack(side="left")
        self.from_e = ttk.Entry(bar, width=12)
        self.from_e.pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="To:").pack(side="left")
        self.to_e = ttk.Entry(bar, width=12)
        self.to_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Window:").pack(side="left")
        self.window_e = ttk.Entry(bar, width=4)
        self.window_e.insert(0, "84")
        self.window_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Run",
                    command=self.refresh).pack(side="left", padx=(10, 0))
        ttk.Button(bar, text="Refresh roster",
                    command=self._refresh_roster).pack(side="left", padx=4)

        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   anchor="w", font=("", 10, "bold")).pack(
            fill="x", padx=12, pady=(0, 4))

        panes = ttk.Panedwindow(self.frame, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Left: by day-of-week
        left = ttk.LabelFrame(panes, text="By day of week")
        cols = ("dow", "total", "p", "l", "a", "au", "pct")
        widths = {"dow": 50, "total": 60, "p": 50, "l": 50, "a": 50,
                  "au": 50, "pct": 70}
        self.dow_tree = ttk.Treeview(left, columns=cols, show="headings",
                                        height=8)
        heads = {"dow": "DoW", "total": "Total", "p": "P", "l": "L",
                 "a": "A", "au": "Au", "pct": "%"}
        for c in cols:
            self.dow_tree.heading(c, text=heads[c])
            self.dow_tree.column(c, width=widths[c],
                                    anchor="e" if c != "dow" else "w")
        self.dow_tree.pack(fill="both", expand=True, padx=6, pady=6)
        panes.add(left, weight=1)

        # Right: daily trend
        right = ttk.LabelFrame(panes, text="Daily trend (recent)")
        dcols = ("date", "total", "p", "l", "a", "au", "pct")
        self.daily_tree = ttk.Treeview(right, columns=dcols,
                                          show="headings")
        dwidths = {"date": 100, "total": 60, "p": 50, "l": 50,
                   "a": 50, "au": 50, "pct": 70}
        for c in dcols:
            self.daily_tree.heading(c, text=heads.get(c, c.capitalize()))
            self.daily_tree.column(c, width=dwidths[c],
                                      anchor="e" if c != "date" else "w")
        vs = ttk.Scrollbar(right, orient="vertical",
                            command=self.daily_tree.yview)
        self.daily_tree.configure(yscrollcommand=vs.set)
        self.daily_tree.pack(side="left", fill="both", expand=True,
                                padx=6, pady=6)
        vs.pack(side="right", fill="y")
        panes.add(right, weight=2)

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
            r = data.per_student_report(
                sid,
                date_from=self.from_e.get().strip() or None,
                date_to=self.to_e.get().strip() or None,
                window_days=int(self.window_e.get().strip() or "84"),
            )
        except (ValidationError, ValueError) as e:
            messagebox.showerror("Per-student", str(e))
            return

        b = r.breakdown
        self.summary_var.set(
            f"{r.student_id} — {r.full_name}    "
            f"Window {r.date_from} → {r.date_to}    "
            f"Total {b.total}   "
            f"P={b.present} L={b.late} A={b.absent} Au={b.authorised}   "
            f"Attendance {_pct(b.percentage)}   "
            f"(recent 28d: lates={r.recent_lates}, "
            f"absences={r.recent_absences})"
        )
        for i in self.dow_tree.get_children():
            self.dow_tree.delete(i)
        for d in DOW_NAMES:
            bb = r.by_dow[d]
            self.dow_tree.insert("", "end", values=(
                d, bb.total, bb.present, bb.late, bb.absent,
                bb.authorised, _pct(bb.percentage)))
        for i in self.daily_tree.get_children():
            self.daily_tree.delete(i)
        for date, bb in r.daily_trend:
            self.daily_tree.insert("", "end", values=(
                date, bb.total, bb.present, bb.late, bb.absent,
                bb.authorised, _pct(bb.percentage)))


# ══ Per-Group tab ══════════════════════════════════════════════════

class PerGroupTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Per-Group")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Group:").pack(side="left")
        opts = [(g.group_id, f"#{g.group_id} — {g.group_name}")
                 for g in cg_data.list_groups()]
        self._gids = [g for g, _ in opts]
        self.group_cb = ttk.Combobox(bar,
                                        values=[l for _, l in opts],
                                        state="readonly", width=40)
        if opts:
            self.group_cb.current(0)
        self.group_cb.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="From:").pack(side="left")
        self.from_e = ttk.Entry(bar, width=12)
        self.from_e.pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="To:").pack(side="left")
        self.to_e = ttk.Entry(bar, width=12)
        self.to_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Window:").pack(side="left")
        self.window_e = ttk.Entry(bar, width=4)
        self.window_e.insert(0, "28")
        self.window_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Highlight <").pack(side="left")
        self.thr_e = ttk.Entry(bar, width=5)
        self.thr_e.insert(0, "90")
        self.thr_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Run",
                    command=self.refresh).pack(side="left", padx=(10, 4))
        ttk.Button(bar, text="Refresh groups",
                    command=self._refresh_groups).pack(side="left")

        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   anchor="w", font=("", 10, "bold")).pack(
            fill="x", padx=12, pady=(0, 4))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("student", "name", "total", "p", "l", "a", "au", "pct")
        widths = {"student": 90, "name": 240, "total": 70, "p": 50,
                  "l": 50, "a": 50, "au": 50, "pct": 80}
        heads = {"student": "Student", "name": "Name",
                 "total": "Total", "p": "P", "l": "L",
                 "a": "A", "au": "Au", "pct": "%"}
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c],
                                anchor="e" if c not in ("student", "name")
                                else "w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("low", background="#ffd0d0")
        self.tree.tag_configure("nodata", foreground="#888")

    def _refresh_groups(self) -> None:
        opts = [(g.group_id, f"#{g.group_id} — {g.group_name}")
                 for g in cg_data.list_groups()]
        self._gids = [g for g, _ in opts]
        self.group_cb["values"] = [l for _, l in opts]
        if opts:
            self.group_cb.current(0)

    def refresh(self) -> None:
        idx = self.group_cb.current()
        if idx < 0:
            return
        gid = self._gids[idx]
        try:
            thr = float(self.thr_e.get().strip() or "90")
            r = data.per_group_report(
                gid,
                date_from=self.from_e.get().strip() or None,
                date_to=self.to_e.get().strip() or None,
                window_days=int(self.window_e.get().strip() or "28"),
            )
        except (ValidationError, ValueError) as e:
            messagebox.showerror("Per-group", str(e))
            return
        b = r.breakdown
        self.summary_var.set(
            f"Group #{r.group_id} — {r.group_name}    "
            f"Members {r.total_members}    "
            f"Window {r.date_from} → {r.date_to}    "
            f"Total {b.total}   "
            f"P={b.present} L={b.late} A={b.absent} Au={b.authorised}   "
            f"Attendance {_pct(b.percentage)}"
        )
        for i in self.tree.get_children():
            self.tree.delete(i)
        for row in r.rows:
            bb = row.breakdown
            tags: list[str] = []
            if bb.total == 0:
                tags.append("nodata")
            elif bb.percentage is not None and bb.percentage < thr:
                tags.append("low")
            self.tree.insert("", "end", values=(
                row.student_id, row.full_name, bb.total,
                bb.present, bb.late, bb.absent, bb.authorised,
                _pct(bb.percentage)), tags=tuple(tags))


# ══ Daily tab ═══════════════════════════════════════════════════════

class DailyTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Daily")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="From:").pack(side="left")
        self.from_e = ttk.Entry(bar, width=12)
        self.from_e.pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="To:").pack(side="left")
        self.to_e = ttk.Entry(bar, width=12)
        self.to_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Window:").pack(side="left")
        self.window_e = ttk.Entry(bar, width=4)
        self.window_e.insert(0, "28")
        self.window_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Group:").pack(side="left")
        opts = _group_options()
        self._gids = [g for g, _ in opts]
        self.group_cb = ttk.Combobox(bar,
                                        values=[l for _, l in opts],
                                        state="readonly", width=28)
        self.group_cb.current(0)
        self.group_cb.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Run",
                    command=self.refresh).pack(side="left", padx=(10, 4))
        ttk.Button(bar, text="Refresh groups",
                    command=self._refresh_groups).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("date", "total", "p", "l", "a", "au", "pct")
        widths = {"date": 110, "total": 70, "p": 60, "l": 60, "a": 60,
                  "au": 60, "pct": 80}
        heads = {"date": "Date", "total": "Total", "p": "Present",
                 "l": "Late", "a": "Absent", "au": "Authorised",
                 "pct": "Attendance %"}
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c],
                                anchor="e" if c != "date" else "w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def _refresh_groups(self) -> None:
        opts = _group_options()
        self._gids = [g for g, _ in opts]
        self.group_cb["values"] = [l for _, l in opts]
        self.group_cb.current(0)

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.daily_breakdown(
                date_from=self.from_e.get().strip() or None,
                date_to=self.to_e.get().strip() or None,
                window_days=int(self.window_e.get().strip() or "28"),
                group_id=self._gids[self.group_cb.current()]
                          if self.group_cb.current() >= 0 else None,
            )
        except (ValidationError, ValueError) as e:
            messagebox.showerror("Daily", str(e))
            return
        for d in rows:
            b = d.breakdown
            self.tree.insert("", "end", values=(
                d.date, b.total, b.present, b.late,
                b.absent, b.authorised, _pct(b.percentage)))
        self.summary_var.set(f"{len(rows)} day(s) with records.")


# ══ Day-of-Week tab ═════════════════════════════════════════════════

class DowTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="By DoW")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="From:").pack(side="left")
        self.from_e = ttk.Entry(bar, width=12)
        self.from_e.pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="To:").pack(side="left")
        self.to_e = ttk.Entry(bar, width=12)
        self.to_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Window:").pack(side="left")
        self.window_e = ttk.Entry(bar, width=4)
        self.window_e.insert(0, "84")
        self.window_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Group:").pack(side="left")
        opts = _group_options()
        self._gids = [g for g, _ in opts]
        self.group_cb = ttk.Combobox(bar,
                                        values=[l for _, l in opts],
                                        state="readonly", width=28)
        self.group_cb.current(0)
        self.group_cb.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Run",
                    command=self.refresh).pack(side="left", padx=(10, 4))
        ttk.Button(bar, text="Refresh groups",
                    command=self._refresh_groups).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("dow", "total", "p", "l", "a", "au", "pct")
        widths = {"dow": 60, "total": 70, "p": 60, "l": 60,
                  "a": 60, "au": 60, "pct": 80}
        heads = {"dow": "DoW", "total": "Total", "p": "Present",
                 "l": "Late", "a": "Absent", "au": "Authorised",
                 "pct": "Attendance %"}
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings", height=8)
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c],
                                anchor="e" if c != "dow" else "w")
        self.tree.pack(fill="both", expand=True)

    def _refresh_groups(self) -> None:
        opts = _group_options()
        self._gids = [g for g, _ in opts]
        self.group_cb["values"] = [l for _, l in opts]
        self.group_cb.current(0)

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.by_dow_breakdown(
                date_from=self.from_e.get().strip() or None,
                date_to=self.to_e.get().strip() or None,
                window_days=int(self.window_e.get().strip() or "84"),
                group_id=self._gids[self.group_cb.current()]
                          if self.group_cb.current() >= 0 else None,
            )
        except (ValidationError, ValueError) as e:
            messagebox.showerror("DoW", str(e))
            return
        for r in rows:
            b = r.breakdown
            self.tree.insert("", "end", values=(
                r.dow, b.total, b.present, b.late,
                b.absent, b.authorised, _pct(b.percentage)))


# ══ Risk tab ════════════════════════════════════════════════════════

class RiskTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Risk")
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="From:").pack(side="left")
        self.from_e = ttk.Entry(bar, width=12)
        self.from_e.pack(side="left", padx=(2, 6))
        ttk.Label(bar, text="To:").pack(side="left")
        self.to_e = ttk.Entry(bar, width=12)
        self.to_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Window:").pack(side="left")
        self.window_e = ttk.Entry(bar, width=4)
        self.window_e.insert(0, "28")
        self.window_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Min %:").pack(side="left")
        self.thr_e = ttk.Entry(bar, width=5)
        self.thr_e.insert(0, "90")
        self.thr_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Max lates:").pack(side="left")
        self.late_e = ttk.Entry(bar, width=4)
        self.late_e.insert(0, "5")
        self.late_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Max absences:").pack(side="left")
        self.abs_e = ttk.Entry(bar, width=4)
        self.abs_e.insert(0, "3")
        self.abs_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Run",
                    command=self.refresh).pack(side="left", padx=(10, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("student", "name", "pct", "p", "l", "a", "au", "reasons")
        widths = {"student": 90, "name": 220, "pct": 70, "p": 50,
                  "l": 50, "a": 50, "au": 50, "reasons": 480}
        heads = {"student": "Student", "name": "Name",
                 "pct": "%", "p": "P", "l": "L", "a": "A",
                 "au": "Au", "reasons": "Reasons"}
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c],
                                anchor="e" if c in (
                                    "pct", "p", "l", "a", "au") else "w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        self.summary_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.summary_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.risk_report(
                date_from=self.from_e.get().strip() or None,
                date_to=self.to_e.get().strip() or None,
                window_days=int(self.window_e.get().strip() or "28"),
                threshold_pct=float(self.thr_e.get().strip() or "90"),
                max_lates=int(self.late_e.get().strip() or "5"),
                max_absences=int(self.abs_e.get().strip() or "3"),
            )
        except (ValidationError, ValueError) as e:
            messagebox.showerror("Risk", str(e))
            return
        for r in rows:
            b = r.breakdown
            self.tree.insert("", "end", values=(
                r.student_id, r.full_name, _pct(b.percentage),
                b.present, b.late, b.absent, b.authorised,
                "; ".join(r.reasons)))
        self.summary_var.set(f"{len(rows)} student(s) flagged.")
