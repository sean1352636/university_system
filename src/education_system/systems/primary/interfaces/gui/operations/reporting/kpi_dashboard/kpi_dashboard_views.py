"""GUI for the Primary School KPI Dashboard.

A tile grid that mirrors the welcome screen's KPI strip but covers the
full set of headline metrics, with controls to change the rolling
window and at-risk threshold and refresh in place.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.systems.primary.domain.operations.reporting.kpi_dashboard import kpi_dashboard as data
from education_system.systems.primary.domain.operations.reporting.kpi_dashboard.kpi_dashboard import (
    DEFAULT_THRESHOLD,
    DEFAULT_WINDOW_DAYS,
    Snapshot,
)
from education_system.systems.primary.interfaces.gui import kit

logger = logging.getLogger(__name__)

_TILE_COLUMNS = 4


def _status(gui, text: str) -> None:
    var = getattr(gui, "status_var", None)
    if var is not None:
        var.set(text)


def open_kpi_dashboard_window(gui) -> None:
    kit.show_page(gui, "KPI Dashboard", lambda parent: _draw_kpi_dashboard(parent, gui))


def _draw_kpi_dashboard(frame: ttk.Frame, gui) -> None:
    kit.page_heading(frame, "KPI Dashboard")
    meta_var = tk.StringVar(value="")
    ttk.Label(frame, textvariable=meta_var, foreground="#666").pack(
        anchor="w", pady=(0, 12))

    bar = ttk.Frame(frame)
    bar.pack(fill="x", pady=(0, 12))

    window_var = tk.StringVar(value=str(DEFAULT_WINDOW_DAYS))
    threshold_var = tk.StringVar(value=str(DEFAULT_THRESHOLD))

    ttk.Label(bar, text="Window (days):").pack(side="left")
    kit.NumberField(bar, window_var, from_=1, to=3650, width=6).pack(
        side="left", padx=(4, 12))
    ttk.Label(bar, text="At-risk threshold (%):").pack(side="left")
    kit.NumberField(bar, threshold_var, from_=0, to=100, increment=0.5, width=6).pack(
        side="left", padx=(4, 12))

    grid_holder = ttk.Frame(frame)
    grid_holder.pack(fill="both", expand=True)
    for c in range(_TILE_COLUMNS):
        grid_holder.columnconfigure(c, weight=1, uniform="kpi")

    def _make_tile(parent: ttk.Frame, row: int, col: int,
                    label: str, value: str, hint: str) -> None:
        tile = ttk.LabelFrame(parent, padding=12)
        tile.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
        ttk.Label(tile, text=label, foreground="#666").pack(anchor="w")
        ttk.Label(tile, text=value, font=("", 22, "bold")).pack(
            anchor="w", pady=(2, 0))
        ttk.Label(tile, text=hint, foreground="#888", font=("", 9)).pack(
            anchor="w", pady=(2, 0))

    def _render(snap: Snapshot) -> None:
        for w in grid_holder.winfo_children():
            w.destroy()
        for i, tile in enumerate(snap.tiles):
            row, col = divmod(i, _TILE_COLUMNS)
            _make_tile(grid_holder, row, col, tile.label, tile.value, tile.hint)
        meta_var.set(f"Generated {snap.generated_at} · window: last {snap.window_days} days")

    def _refresh() -> None:
        try:
            window = max(1, int(window_var.get()))
        except ValueError:
            window = DEFAULT_WINDOW_DAYS
            window_var.set(str(window))
        try:
            threshold = max(0.0, min(100.0, float(threshold_var.get())))
        except ValueError:
            threshold = DEFAULT_THRESHOLD
            threshold_var.set(str(threshold))
        try:
            snap = data.snapshot(window_days=window, threshold_pct=threshold)
        except Exception as e:
            logger.exception("kpi snapshot failed")
            for w in grid_holder.winfo_children():
                w.destroy()
            ttk.Label(grid_holder, text=f"Error: {e}",
                      foreground="#a33").grid(row=0, column=0, sticky="w")
            return
        _render(snap)
        _status(gui, "KPI Dashboard refreshed")

    ttk.Button(bar, text="Refresh", command=_refresh).pack(
        side="left", padx=(8, 0))

    _refresh()
