"""GUI panels for Sixth Form Risk Analytics.

Two-tab Notebook:

* Register — a "Run scan" button plus the at-risk register sorted by
  score; double-click a row to drill into the breakdown.
* Per-student — pick a student ID and see factors + subject forecast.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.post_16.sixthform_system.modules.domain.assessment.risk_analytics import (
    risk_analytics as data,
)

logger = logging.getLogger(__name__)

_BAND_COLOUR = {
    "Low": "#2e7d32", "Medium": "#f9a825",
    "High": "#ef6c00", "Critical": "#c62828",
}


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))


def open_directory(gui) -> None:
    parent = _clear(gui)
    _heading(parent, "Risk Analytics")
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)

    reg = ttk.Frame(nb, padding=10)
    stu = ttk.Frame(nb, padding=10)
    nb.add(reg, text="At-Risk Register")
    nb.add(stu, text="Per-Student")
    _build_register_tab(gui, reg)
    _build_student_tab(gui, stu)


def _build_register_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))

    band_var = tk.StringVar(value="All")
    ttk.Label(bar, text="Band:").pack(side="left")
    ttk.Combobox(bar, textvariable=band_var, width=10, state="readonly",
                 values=["All", *data.BANDS]).pack(side="left", padx=(4, 12))

    summary_var = tk.StringVar(value="")
    ttk.Label(bar, textvariable=summary_var).pack(side="left")

    cols = ("student", "score", "band", "attend", "behaviour")
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=18)
    for c, t, w in (("student", "Student", 220), ("score", "Score", 70),
                    ("band", "Band", 90), ("attend", "Attendance", 100),
                    ("behaviour", "Neg. points", 100)):
        tree.heading(c, text=t)
        tree.column(c, width=w, anchor="w" if c == "student" else "center")
    for b, col in _BAND_COLOUR.items():
        tree.tag_configure(b, foreground=col)
    tree.pack(fill="both", expand=True)

    def refresh() -> None:
        tree.delete(*tree.get_children())
        band = None if band_var.get() == "All" else band_var.get()
        snaps = data.latest_snapshots(band=band)
        for s in snaps:
            att = f"{s['attendance_pct']}%" if s["attendance_pct"] is not None else "—"
            tree.insert("", "end", iid=s["student_id"], tags=(s["band"],),
                        values=(s["full_name"], s["score"], s["band"], att,
                                s["behaviour_points"]))
        counts = data.summary()
        summary_var.set("   ".join(f"{b}: {counts.get(b, 0)}" for b in data.BANDS))
        if not snaps:
            summary_var.set("No snapshots yet — run a scan.")

    def run_scan() -> None:
        try:
            results = data.scan_all()
        except Exception as e:
            logger.exception("Risk scan failed")
            messagebox.showerror("Risk Analytics", f"Scan failed: {e}")
            return
        messagebox.showinfo("Risk Analytics", f"Assessed {len(results)} students.")
        refresh()

    def on_open(_evt=None) -> None:
        sel = tree.selection()
        if sel:
            _show_breakdown(gui, sel[0])

    ttk.Button(bar, text="Run scan", command=run_scan).pack(side="right")
    ttk.Button(bar, text="Refresh", command=refresh).pack(side="right", padx=(0, 6))
    tree.bind("<Double-1>", on_open)
    band_var.trace_add("write", lambda *_: refresh())
    refresh()


def _build_student_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Student ID:").pack(side="left")
    sid_var = tk.StringVar()
    entry = ttk.Entry(bar, textvariable=sid_var, width=16)
    entry.pack(side="left", padx=(4, 8))

    body = ttk.Frame(parent)
    body.pack(fill="both", expand=True)

    def load() -> None:
        for w in body.winfo_children():
            w.destroy()
        sid = sid_var.get().strip()
        if not sid:
            return
        try:
            a = data.assess_student(sid)
        except ValueError as e:
            ttk.Label(body, text=str(e), foreground="#c62828").pack(anchor="w")
            return
        head = f"{a.full_name} ({a.student_id}) — {a.score}/100  ·  {a.band}"
        ttk.Label(body, text=head, font=("", 13, "bold"),
                  foreground=_BAND_COLOUR.get(a.band)).pack(anchor="w", pady=(0, 6))
        ttk.Label(body, text=f"Attendance {a.attendance_pct}%   "
                             f"Net negative behaviour {a.behaviour_points}").pack(anchor="w")

        ttk.Label(body, text="Contributing factors", font=("", 11, "bold")).pack(
            anchor="w", pady=(10, 2))
        if a.factors:
            for f in a.factors:
                ttk.Label(body, text=f"  +{f.points}  {f.detail}").pack(anchor="w")
        else:
            ttk.Label(body, text="  None detected.").pack(anchor="w")

        ttk.Label(body, text="Subject forecast", font=("", 11, "bold")).pack(
            anchor="w", pady=(10, 2))
        cols = ("subject", "base", "mock", "pred", "fcast", "target", "ot")
        t = ttk.Treeview(body, columns=cols, show="headings", height=6)
        for c, txt, w in (("subject", "Subject", 180), ("base", "Base", 60),
                          ("mock", "Mock", 60), ("pred", "Pred", 60),
                          ("fcast", "Forecast", 80), ("target", "Target", 70),
                          ("ot", "On target", 90)):
            t.heading(c, text=txt)
            t.column(c, width=w, anchor="w" if c == "subject" else "center")
        for p in a.predictions:
            ot = "—" if p.on_target is None else ("yes" if p.on_target else "NO")
            t.insert("", "end", values=(p.subject, p.baseline_grade or "—",
                     p.latest_mock_grade or "—", p.predicted_grade or "—",
                     p.forecast_grade or "—", p.target_grade or "—", ot))
        t.pack(fill="x")

    ttk.Button(bar, text="Assess", command=load).pack(side="left")
    entry.bind("<Return>", lambda _e: load())


def _show_breakdown(gui, student_id: str) -> None:
    """Re-open the per-student tab content in a popup for a register row."""
    top = tk.Toplevel(gui.content_frame)
    top.title(f"Risk breakdown — {student_id}")
    top.geometry("560x460")
    frame = ttk.Frame(top, padding=12)
    frame.pack(fill="both", expand=True)
    try:
        a = data.assess_student(student_id)
    except ValueError as e:
        ttk.Label(frame, text=str(e)).pack()
        return
    ttk.Label(frame, text=f"{a.full_name} — {a.score}/100 · {a.band}",
              font=("", 13, "bold"), foreground=_BAND_COLOUR.get(a.band)).pack(anchor="w")
    for f in a.factors:
        ttk.Label(frame, text=f"+{f.points}  {f.detail}", wraplength=520,
                  justify="left").pack(anchor="w", pady=1)
    if not a.factors:
        ttk.Label(frame, text="No risk factors detected.").pack(anchor="w")
