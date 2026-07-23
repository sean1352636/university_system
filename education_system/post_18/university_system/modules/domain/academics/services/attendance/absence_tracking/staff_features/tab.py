"""Split from staff_features.py — see package __init__.py for public API."""
from __future__ import annotations

import json
import logging
import secrets
import sqlite3
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, Iterable, Optional

from education_system.post_18.university_system.modules.domain.academics.services.attendance.absence_tracking.admin_features import (
    safe, audit, _combo_dialog, _show_table, _export_rows_to_csv,
    _get_setting, _set_setting, ensure_support_tables,
    pick_date, pick_date_range,
)

try:
    from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
    logger = configure_logging(name="absence_tracker.staff")
except Exception:
    logger = logging.getLogger("absence_tracker.staff")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)

from .context import StaffContext, ensure_staff_tables
from .facade import StaffServices
from .registry import FEATURES, FeatureSpec

def build_staff_tab(notebook: ttk.Notebook, ctx: StaffContext) -> None:
    """Render all 50 staff features into a dedicated notebook tab."""
    try:
        ensure_support_tables(ctx.db)
        ensure_staff_tables(ctx.db)
    except sqlite3.Error:
        logger.exception("could not ensure staff tables")
        messagebox.showerror(
            "Staff Tools",
            "Could not initialise staff-tools tables. See log.",
            parent=ctx.parent)
        return

    services = StaffServices.for_context(ctx)

    frame = ttk.Frame(notebook)
    notebook.add(frame, text="🧑‍🏫 Staff Tools (50)")

    canvas = tk.Canvas(frame, bg="#f0f4f8", highlightthickness=0)
    vsb = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    canvas.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")

    inner = tk.Frame(canvas, bg="#f0f4f8")
    canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    by_cat: dict[str, list[FeatureSpec]] = {}
    for spec in FEATURES:
        by_cat.setdefault(spec.category, []).append(spec)

    for cat, items in by_cat.items():
        box = tk.LabelFrame(inner, text=cat, padx=10, pady=8,
                            font=("Arial", 11, "bold"), bg="#f0f4f8",
                            fg="#1e3a5f")
        box.pack(fill="x", padx=12, pady=8)
        cols = 3
        for i, spec in enumerate(items):
            try:
                callback = spec.method(services)
            except Exception:
                logger.exception("feature %d binding failed", spec.number)
                continue
            btn = tk.Button(
                box, text=f"{spec.number:02d}. {spec.label}",
                command=callback,
                bg="#7c3aed", fg="white", activebackground="#6d28d9",
                relief="flat", cursor="hand2",
                width=32, anchor="w", padx=8, pady=6,
            )
            btn.grid(row=i // cols, column=i % cols, padx=4, pady=3, sticky="w")

    logger.info("staff tools tab built (%d features)", len(FEATURES))
