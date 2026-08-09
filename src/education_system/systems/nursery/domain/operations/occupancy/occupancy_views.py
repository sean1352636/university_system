"""Tkinter views for Occupancy & Income (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``). A read-only dashboard: KPI tiles for occupancy + income and a
per-room occupancy table — the GUI counterpart of ``occupancy_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.systems.nursery.domain.operations.occupancy import occupancy as data

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        parent = getattr(host, "root", None)
        try:
            return func(host, *args, **kwargs)
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=parent)
            except Exception:
                logger.debug("Could not show error dialog", exc_info=True)
    return wrapper


def _clear(host) -> ttk.Frame:
    host._clear_content()
    assert host.content_frame is not None
    return host.content_frame


def _tile(parent: ttk.Frame, col: int, label: str, value: str, hint: str) -> None:
    tile = ttk.LabelFrame(parent, padding=12)
    tile.grid(row=0, column=col, padx=4, sticky="nsew")
    parent.columnconfigure(col, weight=1, uniform="kpi")
    ttk.Label(tile, text=label, foreground="#666").pack(anchor="w")
    ttk.Label(tile, text=value, font=("", 20, "bold")).pack(anchor="w", pady=(2, 0))
    ttk.Label(tile, text=hint, foreground="#888", font=("", 9)).pack(
        anchor="w", pady=(2, 0))


@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: occupancy open_manager")
    root = _clear(host)

    head = ttk.Frame(root)
    head.pack(fill="x", pady=(0, 8))
    ttk.Label(head, text="Occupancy & Income", font=("", 16, "bold")).pack(
        side="left")
    ttk.Button(head, text="↻ Refresh",
               command=lambda: open_manager(host)).pack(side="right")

    t = data.occupancy_totals()
    inc = data.income_summary()
    total_income = round(inc["collected"] + inc["funding_paid"], 2)

    tiles = ttk.Frame(root)
    tiles.pack(fill="x", pady=(0, 12))
    pct = "—" if t["pct"] is None else f"{t['pct']:g}%"
    _tile(tiles, 0, "Occupancy", pct,
          f"{t['occupancy']}/{t['capacity']} places")
    _tile(tiles, 1, "Places left", str(t["places_left"]),
          f"across {t['rooms']} rooms")
    _tile(tiles, 2, "Outstanding", f"£{inc['outstanding']:.0f}",
          "unpaid invoice balance")
    _tile(tiles, 3, "Income (paid)", f"£{total_income:.0f}",
          "fees collected + funding paid")

    # Per-room occupancy table.
    ttk.Label(root, text="Occupancy by room", font=("", 11, "bold")).pack(
        anchor="w", pady=(4, 4))
    cols = ("room", "occupancy", "places", "fill", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=8)
    for c, label, w, anc in [
        ("room", "Room", 200, "w"), ("occupancy", "Occupancy", 110, "w"),
        ("places", "Places left", 100, "e"), ("fill", "Fill %", 90, "e"),
        ("status", "Status", 90, "w"),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor=anc)
    tree.tag_configure("full", foreground="#c0392b")
    tree.pack(fill="x")
    for r in data.list_room_occupancy():
        tag = "full" if r.places_left == 0 and r.capacity > 0 else ""
        tree.insert("", "end", tags=(tag,) if tag else (), values=(
            r.name, f"{r.occupancy}/{r.capacity}", r.places_left,
            "-" if r.pct is None else f"{r.pct:g}%", r.status))

    # Income breakdown.
    ttk.Label(root, text="Income breakdown", font=("", 11, "bold")).pack(
        anchor="w", pady=(12, 4))
    grid = ttk.Frame(root)
    grid.pack(anchor="w")
    rows = [
        ("Invoiced (fees)", inc["invoiced"]),
        ("Collected", inc["collected"]),
        ("Outstanding", inc["outstanding"]),
        ("Payments received", inc["payments_received"]),
        ("Funding claimed", inc["funding_total"]),
        ("Funding paid", inc["funding_paid"]),
    ]
    for i, (lbl, val) in enumerate(rows):
        ttk.Label(grid, text=f"{lbl}:", foreground="#555").grid(
            row=i, column=0, sticky="w", padx=(0, 16), pady=1)
        ttk.Label(grid, text=f"£{val:.2f}").grid(row=i, column=1, sticky="e", pady=1)

    host.status_var.set("Occupancy & income loaded")


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Occupancy & Income", font=("", 14, "bold")).pack(
        anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Occupancy & Income from the navigation menu.").pack(
        anchor="w")
    return frame
