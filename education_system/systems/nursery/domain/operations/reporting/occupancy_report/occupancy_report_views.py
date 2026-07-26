"""Tkinter view for the Occupancy Report (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``): a per-room occupancy board (capacity vs active children, over-capacity
rooms in red), a setting-wide summary line and Refresh / Export-CSV buttons.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from education_system.systems.nursery.domain.operations.reporting.occupancy_report import (
    occupancy_report as data,
)

logger = logging.getLogger(__name__)


def open_occupancy_report_window(host) -> None:
    """Open the Occupancy Report in the GUI host's content pane."""
    try:
        host._clear_content()
        root = host.content_frame
        ttk.Label(root, text="Occupancy Report",
                  font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

        summary = ttk.Label(root, foreground="#555")
        summary.pack(anchor="w", pady=(0, 6))

        bar = ttk.Frame(root)
        bar.pack(fill="x", pady=(0, 8))
        cols = ("room", "age", "cap", "used", "free", "pct", "status")
        tree = ttk.Treeview(root, columns=cols, show="headings", height=16)
        ttk.Button(bar, text="Refresh",
                   command=lambda: _refresh(tree, summary)).pack(side="left", padx=2)
        ttk.Button(bar, text="Export CSV",
                   command=lambda: _export(host)).pack(side="left", padx=2)

        for c, label, w in [
            ("room", "Room", 160), ("age", "Age group", 150),
            ("cap", "Capacity", 80), ("used", "Occupied", 80),
            ("free", "Free", 70), ("pct", "Occupancy", 90),
            ("status", "Status", 110),
        ]:
            tree.heading(c, text=label)
            tree.column(c, width=w, anchor="w")
        tree.tag_configure("over", foreground="#c0392b")
        tree.tag_configure("full", foreground="#b9770e")
        tree.tag_configure("ok", foreground="#1e7e34")
        tree.pack(fill="both", expand=True)

        _refresh(tree, summary)
        host.status_var.set("Occupancy report loaded")
    except Exception:
        logger.exception("open_occupancy_report_window failed")
        try:
            messagebox.showerror(
                "Occupancy Report",
                "Could not open the Occupancy Report — see logs for details.",
                parent=getattr(host, "root", None))
        except Exception:
            logger.debug("Could not show error dialog", exc_info=True)


def _refresh(tree: ttk.Treeview, summary: ttk.Label) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_room_occupancy()
        s = data.summary()
    except Exception:
        logger.exception("Could not refresh occupancy report")
        messagebox.showerror("Occupancy Report", "Could not load — see logs.")
        return
    for r in rows:
        if r.over_capacity:
            tag = "over"
        elif r.capacity and r.occupied >= r.capacity:
            tag = "full"
        else:
            tag = "ok"
        pct = "-" if r.occupancy_pct is None else f"{r.occupancy_pct}%"
        tree.insert("", "end", tags=(tag,), values=(
            r.name, r.age_group or "-", r.capacity, r.occupied,
            r.places_remaining, pct, r.status))
    overall = "-" if s["occupancy_pct"] is None else f"{s['occupancy_pct']}%"
    summary.config(
        text=f"Rooms: {s['rooms']}   Capacity: {s['capacity']}   "
             f"Occupied: {s['occupied']}   Free: {s['places_remaining']}   "
             f"Overall: {overall}   Full: {s['full_rooms']}   "
             f"Over capacity: {s['over_capacity_rooms']}   "
             f"Unplaced: {s['unplaced_children']}",
        foreground="#a00" if s["over_capacity_rooms"] else "#555")


def _export(host) -> None:
    path = filedialog.asksaveasfilename(
        parent=getattr(host, "root", None), title="Export Occupancy Report",
        defaultextension=".csv", filetypes=[("CSV files", "*.csv")],
        initialfile="occupancy_report.csv")
    if not path:
        return
    try:
        res = data.export_csv(path)
        messagebox.showinfo(
            "Occupancy Report",
            f"Wrote {res['row_count']} row(s) to:\n{res['path']}",
            parent=getattr(host, "root", None))
        host.status_var.set(f"Exported occupancy report → {res['path']}")
    except OSError as e:
        messagebox.showerror("Occupancy Report", str(e),
                             parent=getattr(host, "root", None))


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Occupancy Report",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open the Occupancy Report from the navigation menu."
              ).pack(anchor="w")
    return frame
