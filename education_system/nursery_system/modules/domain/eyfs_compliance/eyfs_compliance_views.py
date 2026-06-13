"""Tkinter view for EYFS Compliance (Nursery System).

Renders into the shared content pane of the GUI host: an overall score header
(colour-coded by grade), a status-coded Treeview of every EYFS welfare check
grouped by section, and Refresh / Export-CSV buttons. Read-only.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from education_system.nursery_system.modules.domain.eyfs_compliance import (
    eyfs_compliance as data,
)

logger = logging.getLogger(__name__)

_MARKERS = {"ok": "✓", "warning": "⚠", "fail": "✗", "info": "·"}


def open_eyfs_compliance_window(host) -> None:
    """Open the EYFS Compliance checklist in the host's content pane."""
    try:
        host._clear_content()
        root = host.content_frame
        ttk.Label(root, text="EYFS Compliance",
                  font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

        header = ttk.Label(root, font=("", 11, "bold"))
        header.pack(anchor="w", pady=(0, 6))

        bar = ttk.Frame(root)
        bar.pack(fill="x", pady=(0, 8))
        cols = ("section", "check", "status", "detail")
        tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
        ttk.Button(bar, text="Refresh",
                   command=lambda: _refresh(tree, header)).pack(
                       side="left", padx=2)
        ttk.Button(bar, text="Export CSV",
                   command=lambda: _export(host)).pack(side="left", padx=2)

        for c, label, w in [
            ("section", "Section", 200), ("check", "Check", 230),
            ("status", "Status", 90), ("detail", "Detail", 420),
        ]:
            tree.heading(c, text=label)
            tree.column(c, width=w, anchor="w")
        tree.tag_configure("fail", foreground="#c0392b")
        tree.tag_configure("warning", foreground="#b9770e")
        tree.tag_configure("ok", foreground="#1e7e34")
        tree.tag_configure("info", foreground="#555")
        tree.pack(fill="both", expand=True)

        _refresh(tree, header)
        host.status_var.set("EYFS compliance loaded")
    except Exception:
        logger.exception("open_eyfs_compliance_window failed")
        try:
            messagebox.showerror(
                "EYFS Compliance",
                "Could not open EYFS Compliance — see logs for details.",
                parent=getattr(host, "root", None))
        except Exception:
            logger.debug("Could not show error dialog", exc_info=True)


def _grade_colour(grade: str) -> str:
    return {
        "Fully compliant": "#1e7e34",
        "Mostly compliant": "#1e7e34",
        "Partially compliant": "#b9770e",
        "Significant gaps": "#c0392b",
    }.get(grade, "#555")


def _refresh(tree: ttk.Treeview, header: ttk.Label) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        checks = data.compliance()
        s = data.score()
    except Exception:
        logger.exception("Could not refresh EYFS compliance")
        messagebox.showerror("EYFS Compliance", "Could not load — see logs.")
        return

    ordered = data.sections_in_order()
    seen = {c.section for c in checks}
    sections = ordered + [sec for sec in sorted(seen) if sec not in ordered]
    for section in sections:
        for c in [x for x in checks if x.section == section]:
            marker = _MARKERS.get(c.status, "?")
            tree.insert("", "end", tags=(c.status,), values=(
                c.section, c.title, f"{marker} {c.status}", c.detail))

    header.config(
        text=f"{s['grade']} — {s['pct']}% compliant   "
             f"(✓ {s['ok']}  ⚠ {s['warning']}  ✗ {s['fail']}  · {s['info']})",
        foreground=_grade_colour(str(s["grade"])))


def _export(host) -> None:
    path = filedialog.asksaveasfilename(
        parent=getattr(host, "root", None), title="Export EYFS Compliance",
        defaultextension=".csv", filetypes=[("CSV files", "*.csv")],
        initialfile="eyfs_compliance.csv")
    if not path:
        return
    try:
        res = data.export_csv(path)
        messagebox.showinfo(
            "EYFS Compliance",
            f"Wrote {res['row_count']} row(s) to:\n{res['path']}",
            parent=getattr(host, "root", None))
        host.status_var.set(f"Exported EYFS compliance → {res['path']}")
    except OSError as e:
        messagebox.showerror("EYFS Compliance", str(e),
                             parent=getattr(host, "root", None))


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="EYFS Compliance",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open EYFS Compliance from the navigation menu."
              ).pack(anchor="w")
    return frame
