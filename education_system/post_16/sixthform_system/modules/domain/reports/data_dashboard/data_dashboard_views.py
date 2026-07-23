"""GUI for the Sixth Form Data Dashboard.

A tabbed view: one tab per panel. Each tab renders a Treeview with the
panel's rows and a small total/notes label underneath. A shared toolbar
above the notebook lets staff change the rolling window and refresh
every panel in one go.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from education_system.post_16.sixthform_system.modules.domain.reports.data_dashboard import data_dashboard as data
from education_system.post_16.sixthform_system.modules.domain.reports.data_dashboard.data_dashboard import (
    DEFAULT_WINDOW_DAYS,
    DataSnapshot,
    Panel,
)

logger = logging.getLogger(__name__)


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _render_panel(parent: ttk.Frame, panel: Panel) -> None:
    for w in parent.winfo_children():
        w.destroy()
    lbl_col, count_col, extra_col = panel.columns

    if panel.note:
        ttk.Label(parent, text=panel.note, foreground="#888").pack(
            anchor="w", pady=(0, 6))

    table = ttk.Frame(parent)
    table.pack(fill="both", expand=True)

    cols = ("label", "count") + (("extra",) if extra_col else ())
    tree = ttk.Treeview(table, columns=cols, show="headings", height=16)
    tree.heading("label", text=lbl_col)
    tree.heading("count", text=count_col)
    tree.column("label", width=240, anchor="w")
    tree.column("count", width=90, anchor="e")
    if extra_col:
        tree.heading("extra", text=extra_col)
        tree.column("extra", width=120, anchor="e")

    vs = ttk.Scrollbar(table, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vs.set)
    tree.pack(side="left", fill="both", expand=True)
    vs.pack(side="right", fill="y")

    for r in panel.rows:
        if extra_col:
            tree.insert("", "end", values=(r.label, r.count, r.extra))
        else:
            tree.insert("", "end", values=(r.label, r.count))

    footer = ttk.Label(
        parent,
        text=(f"Total: {panel.total}" if panel.total is not None else ""),
        foreground="#555",
    )
    footer.pack(anchor="w", pady=(6, 0))


def open_data_dashboard_window(gui) -> None:
    frame = _clear(gui)

    ttk.Label(frame, text="Data Dashboard", font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 4))
    meta_var = tk.StringVar(value="")
    ttk.Label(frame, textvariable=meta_var, foreground="#666").pack(
        anchor="w", pady=(0, 12))

    bar = ttk.Frame(frame)
    bar.pack(fill="x", pady=(0, 8))

    window_var = tk.StringVar(value=str(DEFAULT_WINDOW_DAYS))
    ttk.Label(bar, text="Window (days):").pack(side="left")
    ttk.Entry(bar, textvariable=window_var, width=6).pack(
        side="left", padx=(4, 12))

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True, pady=(4, 0))

    # tab frames are created/destroyed on refresh because the panel set
    # is stable but rendering inside each tab varies on every refresh.
    def _refresh() -> None:
        try:
            window = max(1, int(window_var.get()))
        except ValueError:
            window = DEFAULT_WINDOW_DAYS
            window_var.set(str(window))
        try:
            snap: DataSnapshot = data.build_panels(window_days=window)
        except Exception as e:
            logger.exception("data dashboard snapshot failed")
            for tab in nb.tabs():
                nb.forget(tab)
            err_tab = ttk.Frame(nb, padding=8)
            nb.add(err_tab, text="Error")
            ttk.Label(err_tab, text=f"Could not load dashboard: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        # Rebuild tabs so old data doesn't linger.
        for tab in nb.tabs():
            nb.forget(tab)
        for p in snap.panels:
            tab = ttk.Frame(nb, padding=8)
            tab.pack_propagate(False)
            label = p.name
            if p.total is not None:
                label = f"{label} ({p.total})"
            nb.add(tab, text=label)
            _render_panel(tab, p)
        meta_var.set(f"Generated {snap.generated_at} · window: last {snap.window_days} days")
        gui.status_var.set("Data Dashboard refreshed")

    ttk.Button(bar, text="Refresh", command=_refresh).pack(
        side="left", padx=(8, 0))

    _refresh()
