"""Tkinter view for the DfE 16-18 measures (approximations).

A table of every measure with its value, basis and formula, the
"approximates DfE methodology" caveat, and a drill-down of the rows
behind the selected measure. Used as a tab in the Census / ILR window
and as a window of its own (:func:`open_measures_window`).
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import ttk
from education_system.systems.sixth_form.interfaces.gui._sidebar import SidebarBook
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.platform import branding
from education_system.systems.sixth_form.domain.governance.compliance.measures import (
    measures as data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def run_async(widget: tk.Misc, work, done, *, status: ttk.Label | None = None,
              busy_text: str = "Working…") -> None:
    """Run *work()* off the Tk thread, then *done(result, error)* on it."""
    box: dict = {}

    def _worker() -> None:
        try:
            box["result"] = work()
        except Exception as e:          # handed back to the Tk thread
            logger.exception("background task failed")
            box["error"] = e

    if status is not None:
        status.config(text=busy_text)
    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    def _poll() -> None:
        if t.is_alive():
            widget.after(150, _poll)
            return
        if status is not None:
            status.config(text="")
        done(box.get("result"), box.get("error"))

    widget.after(150, _poll)


class MeasuresTab:
    def __init__(self, nb: ttk.Notebook, *, label: str = "16-18 Measures") -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        self.report: data.MeasuresReport | None = None
        self._build()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Academic year:").pack(side="left")
        self.year = tk.StringVar(value=data.current_year())
        ttk.Entry(bar, textvariable=self.year, width=10).pack(side="left",
                                                               padx=(2, 8))
        ttk.Button(bar, text="Calculate", command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Copy report",
                   command=self._copy).pack(side="left", padx=8)
        self.status = ttk.Label(bar, text="", foreground="#666")
        self.status.pack(side="right")
        ttk.Label(self.frame, text=data.DISCLAIMER, foreground="#8c0d0d",
                  wraplength=1200).pack(anchor="w", padx=8)

        pane = ttk.PanedWindow(self.frame, orient="vertical")
        pane.pack(fill="both", expand=True, padx=8, pady=4)
        top = ttk.Frame(pane)
        cols = ("measure", "value", "basis", "formula")
        self.tree = ttk.Treeview(top, columns=cols, show="headings",
                                 selectmode="browse", height=9)
        for c, w in zip(cols, (240, 90, 110, 760)):
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._show_detail())
        pane.add(top, weight=1)

        bottom = ttk.Frame(pane)
        self.notes = ttk.Label(bottom, text="", justify="left",
                               foreground="#444", wraplength=1200)
        self.notes.pack(anchor="w")
        self.detail = ttk.Treeview(bottom, show="headings")
        vsb = ttk.Scrollbar(bottom, orient="vertical",
                            command=self.detail.yview)
        self.detail.configure(yscrollcommand=vsb.set)
        self.detail.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        pane.add(bottom, weight=2)

    def refresh(self) -> None:
        year = self.year.get().strip() or None

        def done(report, err) -> None:
            if err is not None:
                messagebox.showerror("16-18 measures", str(err),
                                     parent=self.frame)
                return
            self.report = report
            self.tree.delete(*self.tree.get_children())
            for m in report.measures:
                self.tree.insert("", "end", iid=m.key,
                                 values=(m.label, m.display, m.basis,
                                         m.formula))
            self.status.config(text=f"Generated {report.generated_at}")

        run_async(self.frame, lambda: data.compute_all(year), done,
                  status=self.status, busy_text="Calculating measures…")

    def _show_detail(self) -> None:
        sel = self.tree.selection()
        if not sel or self.report is None:
            return
        m = self.report.get(sel[0])
        if m is None:
            return
        self.notes.config(text="\n".join(m.notes))
        self.detail.delete(*self.detail.get_children())
        keys = list(m.rows[0].keys()) if m.rows else []
        self.detail.configure(columns=keys)
        for k in keys:
            self.detail.heading(k, text=k.replace("_", " ").title())
            self.detail.column(k, width=160, anchor="w")
        for r in m.rows:
            self.detail.insert("", "end", values=[
                "" if r.get(k) is None else r.get(k) for k in keys])

    def _copy(self) -> None:
        if self.report is None:
            messagebox.showinfo("16-18 measures", "Calculate first.",
                                parent=self.frame)
            return
        self.frame.clipboard_clear()
        self.frame.clipboard_append(self.report.text())


def open_measures_window(parent=None) -> None:
    from education_system.platform.delivery.gui import window_sizing
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"16-18 Measures — {branding.SYSTEM_NAME}")
    window_sizing.fit(win, WIN_GEOMETRY, WIN_MINSIZE)
    nb = SidebarBook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    MeasuresTab(nb)


__all__ = ["MeasuresTab", "open_measures_window", "run_async"]
