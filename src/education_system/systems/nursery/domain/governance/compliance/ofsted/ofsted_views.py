"""Tkinter view for Ofsted Readiness (Nursery System).

Renders into the shared content pane of the GUI ``host``: a readiness scorecard
header (coloured by grade), a Treeview of the EYFS welfare checks (coloured by
status) and Refresh / Export-CSV buttons. Read-only.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from education_system.systems.nursery.domain.governance.compliance.ofsted import ofsted as data

logger = logging.getLogger(__name__)

_STATUS_LABEL = {"ok": "OK", "warning": "Warning", "fail": "Fail", "info": "Info"}


def open_ofsted_window(host) -> None:
    """Open the Ofsted Readiness report in the host's content pane."""
    try:
        host._clear_content()
        root = host.content_frame
        ttk.Label(root, text="Ofsted Readiness",
                  font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

        header = ttk.Label(root, font=("", 12, "bold"))
        header.pack(anchor="w", pady=(0, 6))

        bar = ttk.Frame(root)
        bar.pack(fill="x", pady=(0, 8))
        cols = ("area", "check", "status", "detail")
        tree = ttk.Treeview(root, columns=cols, show="headings", height=14)
        ttk.Button(bar, text="Refresh",
                   command=lambda: _refresh(tree, header)).pack(side="left",
                                                                padx=2)
        ttk.Button(bar, text="Export CSV",
                   command=lambda: _export(host)).pack(side="left", padx=2)

        for c, label, w in [
            ("area", "Area", 150), ("check", "Check", 180),
            ("status", "Status", 90), ("detail", "Detail", 420),
        ]:
            tree.heading(c, text=label)
            tree.column(c, width=w, anchor="w")
        tree.tag_configure("fail", foreground="#c0392b")
        tree.tag_configure("warning", foreground="#b9770e")
        tree.tag_configure("ok", foreground="#1e7e34")
        tree.tag_configure("info", foreground="#777")
        tree.pack(fill="both", expand=True)

        _refresh(tree, header)
        host.status_var.set("Ofsted readiness loaded")
    except Exception:
        logger.exception("open_ofsted_window failed")
        try:
            messagebox.showerror(
                "Ofsted Readiness",
                "Could not open Ofsted Readiness — see logs for details.",
                parent=getattr(host, "root", None))
        except Exception:
            logger.debug("Could not show error dialog", exc_info=True)


def _grade_colour(pct: float) -> str:
    if pct >= 90:
        return "#1e7e34"
    if pct >= 75:
        return "#b9770e"
    if pct >= 50:
        return "#c0392b"
    return "#a00"


def _refresh(tree: ttk.Treeview, header: ttk.Label) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        checks = data.readiness()
        s = data.score()
    except Exception:
        logger.exception("Could not refresh Ofsted readiness")
        messagebox.showerror("Ofsted Readiness", "Could not load — see logs.")
        return
    for c in checks:
        tree.insert("", "end", tags=(c.status,), values=(
            c.area, c.title, _STATUS_LABEL.get(c.status, c.status), c.detail))
    pct = float(s["pct"])
    header.config(
        text=f"{s['grade']} — {pct}% ready   "
             f"(✓ {s['ok']}  ⚠ {s['warning']}  ✗ {s['fail']}  · {s['info']})",
        foreground=_grade_colour(pct))


def _export(host) -> None:
    path = filedialog.asksaveasfilename(
        parent=getattr(host, "root", None), title="Export Ofsted Readiness",
        defaultextension=".csv", filetypes=[("CSV files", "*.csv")],
        initialfile="ofsted_readiness.csv")
    if not path:
        return
    try:
        res = data.export_csv(path)
        messagebox.showinfo(
            "Ofsted Readiness",
            f"Wrote {res['row_count']} row(s) to:\n{res['path']}",
            parent=getattr(host, "root", None))
        host.status_var.set(f"Exported Ofsted readiness → {res['path']}")
    except OSError as e:
        messagebox.showerror("Ofsted Readiness", str(e),
                             parent=getattr(host, "root", None))


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Ofsted Readiness",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Ofsted Readiness from the navigation menu."
              ).pack(anchor="w")
    return frame
