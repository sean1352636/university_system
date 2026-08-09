"""Tkinter views for the Sixth Form Progress Dashboard."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.systems.sixth_form.domain.operations.reporting.progress import progress
from education_system.platform import branding
from education_system.systems.sixth_form.domain.operations.reporting.progress_dashboard import (
    progress_dashboard as data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_RISK_COLOURS = {
    "Critical": "#c62828",
    "High":     "#e65100",
    "Medium":   "#f9a825",
    "Low":      "#2e7d32",
}


def open_progress_dashboard_window(parent=None) -> None:
    progress.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Progress Dashboard — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    OverviewTab(nb)
    DistributionTab(nb)
    AttentionTab(nb)


def _att(v: float | None) -> str:
    return "—" if v is None else f"{v:.1f}%"


# ══ Overview tab ══════════════════════════════════════════════════

class OverviewTab:
    COLS = ("student_id", "name", "risk", "overall",
            "attendance", "open", "overdue", "met", "missed",
            "period", "date")
    HEADERS = {
        "student_id": "Student",  "name": "Name",
        "risk": "Risk",           "overall": "Overall",
        "attendance": "Att%",     "open": "Open",
        "overdue": "Overdue",     "met": "Met",
        "missed": "Missed",       "period": "Period",
        "date": "Review Date",
    }
    WIDTHS = {
        "student_id": 80, "name": 200, "risk": 80, "overall": 200,
        "attendance": 60, "open": 60, "overdue": 70, "met": 60,
        "missed": 70, "period": 180, "date": 100,
    }

    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Overview")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)

        ttk.Label(bar, text="Risk filter:").pack(side="left")
        self.risk_cb = ttk.Combobox(
            bar, values=["(all)"] + list(progress.RISK_LEVELS),
            state="readonly", width=12)
        self.risk_cb.current(0)
        self.risk_cb.pack(side="left", padx=(2, 10))

        self.unreviewed_v = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Unreviewed only",
                          variable=self.unreviewed_v).pack(side="left", padx=4)
        self.overdue_v = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Overdue targets only",
                          variable=self.overdue_v).pack(side="left", padx=4)

        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left", padx=(10, 4))

        self.summary_lbl = ttk.Label(bar, text="", anchor="e")
        self.summary_lbl.pack(side="right")

        tree_wrap = ttk.Frame(self.frame)
        tree_wrap.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.tree = ttk.Treeview(tree_wrap, columns=self.COLS,
                                    show="headings", height=22)
        for c in self.COLS:
            self.tree.heading(c, text=self.HEADERS[c])
            self.tree.column(c, width=self.WIDTHS[c],
                              anchor=("e" if c in ("attendance", "open",
                                                       "overdue", "met",
                                                       "missed")
                                       else "w"))
        ysb = ttk.Scrollbar(tree_wrap, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscroll=ysb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")

        for risk, colour in _RISK_COLOURS.items():
            self.tree.tag_configure(f"risk_{risk}", foreground=colour)

    def refresh(self) -> None:
        try:
            rf = self.risk_cb.get()
            d = data.build_dashboard(
                risk_filter=None if rf == "(all)" else rf,
                only_unreviewed=self.unreviewed_v.get(),
                only_overdue=self.overdue_v.get(),
            )
        except Exception as e:
            logger.exception("Dashboard refresh failed")
            messagebox.showerror("Progress Dashboard", str(e))
            return
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for r in d.rows:
            tag = f"risk_{r.risk}" if r.risk in _RISK_COLOURS else ""
            self.tree.insert("", "end", values=(
                r.student_id, r.full_name,
                r.risk or "—", r.overall or "—",
                _att(r.attendance_pct),
                r.open_targets, r.overdue_targets,
                r.met_targets, r.missed_targets,
                r.latest_period or "—",
                r.latest_date or "—",
            ), tags=(tag,) if tag else ())
        cov = d.review_coverage_pct
        cov_s = "—" if cov is None else f"{cov:.1f}%"
        self.summary_lbl.configure(
            text=(f"{d.total_students} students · "
                  f"{d.reviewed_students} reviewed ({cov_s}) · "
                  f"{d.high_risk_students} high/critical · "
                  f"{d.overdue_target_students} with overdue"))


# ══ Distribution tab ══════════════════════════════════════════════

class DistributionTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Distributions")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10), state="disabled")
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _bar(self, label: str, n: int, total: int, width: int = 30) -> str:
        if total <= 0:
            blocks = 0
        else:
            blocks = round(width * n / total)
        return f"  {label:<28} | {'█' * blocks}{'·' * (width - blocks)} {n}"

    def refresh(self) -> None:
        d = data.build_dashboard()
        L: list[str] = []
        L.append("Risk distribution")
        L.append("-----------------")
        total = max(d.reviewed_students, 1)
        for r in progress.RISK_LEVELS:
            n = d.by_risk.get(r, 0)
            L.append(self._bar(r, n, total))
        L.append("")
        L.append("Overall rating")
        L.append("--------------")
        for r in progress.RATINGS:
            n = d.by_overall.get(r, 0)
            L.append(self._bar(r, n, total))
        L.append("")
        L.append("Review status")
        L.append("-------------")
        for s in progress.REVIEW_STATUSES:
            n = d.by_status.get(s, 0)
            L.append(self._bar(s, n, total))
        L.append("")
        L.append("Targets")
        L.append("-------")
        s = d.summary
        L.append(f"  Total              : {s.total_targets}")
        L.append(f"  Open               : {s.open_targets}")
        L.append(f"  Met                : {s.met_targets}")
        L.append(f"  Missed             : {s.missed_targets}")
        L.append(f"  Overdue (open)     : {s.overdue_open_targets}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(L))
        self.text.configure(state="disabled")


# ══ Attention tab ═════════════════════════════════════════════════

class AttentionTab:
    """Three lists side-by-side: at-risk, unreviewed, overdue."""

    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Needs Attention")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")

        body = ttk.Frame(self.frame)
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.risk_list, self.risk_lbl = self._panel(body, "High / Critical Risk")
        self.unrev_list, self.unrev_lbl = self._panel(body, "Without a Review")
        self.overdue_list, self.overdue_lbl = self._panel(body, "Overdue Targets")

    def _panel(self, parent, title: str) -> tuple[tk.Listbox, ttk.Label]:
        col = ttk.Frame(parent)
        col.pack(side="left", fill="both", expand=True, padx=4)
        lbl = ttk.Label(col, text=title, font=("TkDefaultFont", 10, "bold"))
        lbl.pack(anchor="w")
        wrap = ttk.Frame(col)
        wrap.pack(fill="both", expand=True)
        lb = tk.Listbox(wrap, font=("TkFixedFont", 10), activestyle="none")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return lb, lbl

    def _populate(self, lb: tk.Listbox, rows, fmt) -> None:
        lb.delete(0, "end")
        if not rows:
            lb.insert("end", "  (none)")
            return
        for r in rows:
            lb.insert("end", fmt(r))

    def refresh(self) -> None:
        risk = data.students_at_risk()
        unrev = data.students_without_review()
        ovr = data.students_with_overdue_targets()
        self._populate(
            self.risk_list, risk,
            lambda r: f" {r.student_id:<8} {r.full_name[:22]:<22} {r.risk}")
        self._populate(
            self.unrev_list, unrev,
            lambda r: f" {r.student_id:<8} {r.full_name[:30]}")
        self._populate(
            self.overdue_list, ovr,
            lambda r: f" {r.student_id:<8} {r.full_name[:22]:<22} "
                       f"{r.overdue_targets} overdue")
        self.risk_lbl.configure(text=f"High / Critical Risk ({len(risk)})")
        self.unrev_lbl.configure(text=f"Without a Review ({len(unrev)})")
        self.overdue_lbl.configure(text=f"Overdue Targets ({len(ovr)})")
