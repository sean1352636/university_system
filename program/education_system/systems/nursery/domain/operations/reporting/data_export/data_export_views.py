"""Tkinter view for Data Export (Nursery System).

Renders into the shared content pane of the GUI host: a table of exportable
nursery tables with live row counts (multi-select), a destination directory
with a Browse… button, and Export Selected / Export All buttons that write one
``<table>.csv`` per table and report how many files / rows were written.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from education_system.systems.nursery.domain.operations.reporting.data_export import (
    data_export as data,
)

logger = logging.getLogger(__name__)


def open_data_export_window(host) -> None:
    """Open Data Export in the GUI host's content pane."""
    try:
        host._clear_content()
        root = host.content_frame
        ttk.Label(root, text="Data Export",
                  font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(root, text="Select tables to export, then choose a "
                  "destination. One CSV is written per table.",
                  foreground="#555").pack(anchor="w", pady=(0, 8))

        cols = ("table", "rows")
        tree = ttk.Treeview(root, columns=cols, show="headings",
                            selectmode="extended", height=14)
        tree.heading("table", text="Table")
        tree.heading("rows", text="Rows")
        tree.column("table", width=240, anchor="w")
        tree.column("rows", width=90, anchor="e")
        tree.pack(fill="both", expand=True, pady=(0, 8))

        dest = ttk.Frame(root)
        dest.pack(fill="x", pady=(0, 8))
        ttk.Label(dest, text="Destination:").pack(side="left", padx=(0, 4))
        dest_var = tk.StringVar(value=str(data.default_export_dir()))
        entry = ttk.Entry(dest, textvariable=dest_var)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(dest, text="Browse…",
                   command=lambda: _browse(host, dest_var)).pack(side="left")

        bar = ttk.Frame(root)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="Export Selected",
                   command=lambda: _export(host, tree, dest_var, False)
                   ).pack(side="left", padx=2)
        ttk.Button(bar, text="Export All",
                   command=lambda: _export(host, tree, dest_var, True)
                   ).pack(side="left", padx=2)
        ttk.Button(bar, text="Refresh",
                   command=lambda: _refresh(tree)).pack(side="left", padx=2)

        _refresh(tree)
        host.status_var.set("Data Export loaded")
    except Exception:
        logger.exception("open_data_export_window failed")
        try:
            messagebox.showerror(
                "Data Export",
                "Could not open Data Export — see logs for details.",
                parent=getattr(host, "root", None))
        except Exception:
            logger.debug("Could not show error dialog", exc_info=True)


def _refresh(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        tables = data.list_tables()
    except Exception:
        logger.exception("Could not load exportable tables")
        messagebox.showerror("Data Export", "Could not load tables — see logs.")
        return
    for t in tables:
        tree.insert("", "end", iid=t["table"],
                    values=(t["label"], t["rows"]))


def _browse(host, dest_var: tk.StringVar) -> None:
    chosen = filedialog.askdirectory(
        parent=getattr(host, "root", None),
        title="Choose export destination",
        initialdir=dest_var.get() or None)
    if chosen:
        dest_var.set(chosen)


def _export(host, tree: ttk.Treeview, dest_var: tk.StringVar,
            all_tables: bool) -> None:
    dir_path = dest_var.get().strip()
    if not dir_path:
        messagebox.showwarning("Data Export", "Please choose a destination.",
                               parent=getattr(host, "root", None))
        return
    tables: list[str] | None
    if all_tables:
        tables = None
    else:
        tables = list(tree.selection())
        if not tables:
            messagebox.showwarning(
                "Data Export", "Select one or more tables, or use Export All.",
                parent=getattr(host, "root", None))
            return
    try:
        res = data.export_all(dir_path, tables)
    except (data.ValidationError, OSError) as e:
        messagebox.showerror("Data Export", str(e),
                             parent=getattr(host, "root", None))
        return
    errors = [f for f in res["files"] if "error" in f]
    msg = (f"Wrote {res['table_count']} file(s), "
           f"{res['total_rows']} total row(s) to:\n{res['dir']}")
    if errors:
        msg += f"\n\nSkipped {len(errors)} table(s) — see logs."
    messagebox.showinfo("Data Export", msg, parent=getattr(host, "root", None))
    host.status_var.set(
        f"Exported {res['table_count']} table(s) → {res['dir']}")


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Data Export",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Data Export from the navigation menu."
              ).pack(anchor="w")
    return frame
