"""Tkinter views for Staff : Child Ratios (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``). Shows the live ratio-compliance board (one row per room, breaches in
red) and lets you set a room's required ratio — the GUI counterpart of
``ratios_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.systems.nursery.domain.operations.ratios import ratios as data
from education_system.systems.nursery.domain.operations.ratios.ratios import (
    ValidationError,
)

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        parent = getattr(host, "root", None)
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror(func.__name__, str(e), parent=parent)
            except Exception:
                logger.debug("Could not show validation dialog", exc_info=True)
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


def _header(parent: ttk.Frame, title: str) -> None:
    ttk.Label(parent, text=title, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _flag(r: data.RoomRatio) -> str:
    if r.compliant is None:
        return "no ratio set"
    return "OK" if r.compliant else f"UNDER by {r.shortfall}"


@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: ratios open_manager")
    root = _clear(host)
    _header(root, "Staff : Child Ratios")

    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 4))
    warn = ttk.Label(root, foreground="#a00")
    warn.pack(anchor="w", pady=(0, 6))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Set Room Ratio",
               command=lambda: _set_ratio_selected(tree, host)).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, summary, warn)).pack(
        side="left", padx=2)

    cols = ("room", "age", "ratio", "children", "staff", "required", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=16)
    for c, label, w in [
        ("room", "Room", 160), ("age", "Age group", 130), ("ratio", "Ratio", 70),
        ("children", "Children", 80), ("staff", "Staff", 70),
        ("required", "Required", 80), ("status", "Status", 140),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.tag_configure("breach", foreground="#c0392b")
    tree.tag_configure("noratio", foreground="#b9770e")
    tree.tag_configure("ok", foreground="#1e7e34")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _set_ratio_selected(tree, host))

    _refresh(tree, summary, warn)
    host.status_var.set("Ratios loaded")


def _refresh(tree: ttk.Treeview, summary: ttk.Label, warn: ttk.Label) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_room_ratios()
        s = data.summary()
    except Exception:
        logger.exception("Could not refresh ratios")
        try:
            messagebox.showerror("Ratios", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for r in rows:
        if r.compliant is None:
            tag = "noratio"
        elif r.compliant:
            tag = "ok"
        else:
            tag = "breach"
        req = "-" if r.required_staff is None else str(r.required_staff)
        tree.insert("", "end", iid=r.room_id, tags=(tag,), values=(
            r.name, r.age_group or "-", r.staff_ratio or "-", r.children,
            r.staff, req, _flag(r)))
    summary.config(
        text=f"Rooms: {s['rooms']}   Children: {s['children']}   "
             f"Staff: {s['staff']}   Breaches: {s['breaches']}   "
             f"No ratio set: {s['no_ratio_set']}",
        foreground="#a00" if s["breaches"] else "#555")
    warn.config(text=(
        f"⚠ {s['unplaced_children']} active child(ren) not assigned to a known "
        "room — not counted above." if s["unplaced_children"] else ""))


def _set_ratio_selected(tree: ttk.Treeview, host) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Ratios", "Select a room first.", parent=host.root)
        return
    rows = {r.room_id: r for r in data.list_room_ratios()}
    r = rows.get(sel)
    if r is None:
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Ratio — {r.name}")
    dlg.transient(host.root)
    dlg.geometry("360x150")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"{r.name} — {r.children} children, {r.staff} staff",
              font=("", 11, "bold")).pack(anchor="w", pady=(0, 8))
    ttk.Label(frm, text="Required ratio (adults:children):").pack(anchor="w")
    var = tk.StringVar(value=r.staff_ratio or "")
    ttk.Combobox(frm, textvariable=var,
                 values=["1:3", "1:4", "1:8", "1:13"], width=18).pack(
        anchor="w", pady=(2, 10))

    def _save() -> None:
        try:
            data.set_room_ratio(sel, var.get())
        except ValidationError as e:
            messagebox.showerror("Ratios", str(e), parent=dlg)
            return
        dlg.destroy()
        open_manager(host)
        host.status_var.set(f"Set ratio for {r.name}")

    btns = ttk.Frame(frm)
    btns.pack(fill="x")
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Staff : Child Ratios",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Staff : Child Ratios from the navigation menu."
              ).pack(anchor="w")
    return frame
