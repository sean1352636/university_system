"""Tkinter views for Rooms & Age Groups (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Provides a rooms manager with an occupancy tree + toolbar and an
add/edit form dialog — the GUI counterpart of the flow in ``rooms_cli.py``.

Every entry point is wrapped by :func:`_safe_view`: domain/DB errors are
logged and surfaced in a dialog rather than crashing the GUI. A legacy
:func:`build` is kept so the old placeholder call site still works.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.operations.rooms import rooms as data
from education_system.systems.nursery.domain.operations.rooms.rooms import (
    RATIO_OPTIONS,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    """Catch unexpected errors in a Tk view; log and show an error dialog."""
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
        except Exception as e:  # noqa: BLE001 - last-resort GUI guard
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=parent,
                )
            except Exception:
                logger.debug("Could not show error dialog", exc_info=True)
    return wrapper


# (field key, label, widget kind). Widget kind drives the form dialog.
_FIELDS: list[tuple[str, str, str]] = [
    ("name",           "Room name",            "entry"),
    ("age_group",      "Age group",            "entry"),
    ("min_age_months", "Minimum age (months)", "entry"),
    ("max_age_months", "Maximum age (months)", "entry"),
    ("capacity",       "Capacity",             "entry"),
    ("staff_ratio",    "Staff ratio",          "ratio"),
    ("room_leader",    "Room leader",          "leader"),
    ("location",       "Location",             "entry"),
    ("notes",          "Notes",                "entry"),
    ("status",         "Status",               "status"),
]


def _clear(host) -> ttk.Frame:
    host._clear_content()
    assert host.content_frame is not None
    return host.content_frame


def _header(parent: ttk.Frame, title: str) -> None:
    ttk.Label(parent, text=title, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _leader_choices() -> list[tuple[str, str]]:
    try:
        return data.list_leader_choices()
    except Exception:
        logger.exception("Could not load room-leader choices")
        return []


def _age_band(r: data.Room) -> str:
    if r.min_age_months is None and r.max_age_months is None:
        return r.age_group or "-"
    lo = "" if r.min_age_months is None else str(r.min_age_months)
    hi = "" if r.max_age_months is None else str(r.max_age_months)
    return f"{lo}-{hi} mo"


# ── Manager ──────────────────────────────────────────────────────────────────

@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: rooms open_manager")
    root = _clear(host)
    _header(root, "Rooms & Age Groups")

    show_closed = tk.BooleanVar(value=True)

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Room",
               command=lambda: open_add_room(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit Selected",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete Selected",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Open / Close",
               command=lambda: _toggle_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, show_closed.get())).pack(
        side="left", padx=2)
    ttk.Checkbutton(
        bar, text="Show closed", variable=show_closed,
        command=lambda: _refresh(tree, show_closed.get()),
    ).pack(side="left", padx=(12, 2))

    cols = ("id", "name", "age", "ratio", "occupancy", "leader", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 70), ("name", "Name", 160), ("age", "Age band", 110),
        ("ratio", "Ratio", 70), ("occupancy", "Occupancy", 110),
        ("leader", "Room leader", 180), ("status", "Status", 90),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, show_closed.get())
    host.status_var.set("Rooms loaded")


def _refresh(tree: ttk.Treeview, include_closed: bool = True) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_rooms(include_closed=include_closed)
    except Exception:
        logger.exception("Could not refresh rooms")
        try:
            messagebox.showerror(
                "Rooms", "Could not load the room list — see logs for details.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for r in rows:
        occ = f"{r.occupancy}/{r.capacity}" + (" FULL" if r.is_full else "")
        tree.insert("", "end", iid=r.room_id, values=(
            r.room_id, r.name, _age_band(r), r.staff_ratio or "-",
            occ, r.room_leader_name or "-", r.status,
        ))


def _edit_selected(tree: ttk.Treeview, host) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Edit room", "Select a room first.", parent=host.root)
        return
    open_edit_room(host, sel, on_done=lambda: _refresh(tree))


def _delete_selected(tree: ttk.Treeview, host) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Delete room", "Select a room first.", parent=host.root)
        return
    try:
        r = data.get_room(sel)
    except Exception:
        logger.exception("Lookup failed before delete for id=%s", sel)
        messagebox.showerror("Delete room", "Could not look up room.",
                             parent=host.root)
        return
    if r is None:
        return
    if not messagebox.askyesno(
            "Delete room",
            f"Permanently delete {r.name} ({r.room_id})?",
            parent=host.root):
        return
    try:
        data.delete_room(sel)
    except ValidationError as e:
        messagebox.showerror("Delete room", str(e), parent=host.root)
        return
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete room id=%s", sel)
        messagebox.showerror("Delete room", f"Could not delete room:\n\n{e}",
                             parent=host.root)
        return
    _refresh(tree)
    host.status_var.set(f"Deleted room {sel}")


def _toggle_selected(tree: ttk.Treeview, host) -> None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Open / Close room", "Select a room first.",
                            parent=host.root)
        return
    try:
        r = data.get_room(sel)
        if r is None:
            return
        new_status = "closed" if r.status == "open" else "open"
        data.set_status(sel, new_status)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to toggle status for room id=%s", sel)
        messagebox.showerror("Open / Close room", f"Could not update room:\n\n{e}",
                             parent=host.root)
        return
    _refresh(tree)
    host.status_var.set(f"Room {sel} set to {new_status}")


# ── Form dialog ──────────────────────────────────────────────────────────────

def _form_dialog(host, title: str, initial: dict[str, Any] | None = None,
                 *, is_edit: bool = False) -> dict[str, str] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("460x500")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    leaders = _leader_choices()
    lead_label_by_id = {sid: label for sid, label in leaders}
    lead_id_by_label = {label: sid for sid, label in leaders}

    vars_: dict[str, tk.Variable] = {}

    row = 0
    for key, label, kind in _FIELDS:
        if key == "status" and not is_edit:
            continue  # new rooms default to 'open'
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw",
                                              pady=2)
        cur = initial.get(key)
        if kind == "ratio":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=list(RATIO_OPTIONS),
                         width=30).grid(row=row, column=1, sticky="ew", pady=2)
        elif kind == "status":
            v = tk.StringVar(value=str(cur or "open"))
            ttk.Combobox(frm, textvariable=v, values=list(STATUSES),
                         state="readonly", width=30).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "leader":
            display = lead_label_by_id.get(str(cur or ""), "")
            v = tk.StringVar(value=display)
            state = "readonly" if leaders else "normal"
            ttk.Combobox(frm, textvariable=v,
                         values=[""] + [lbl for _id, lbl in leaders],
                         state=state, width=30).grid(
                row=row, column=1, sticky="ew", pady=2)
        else:
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Entry(frm, textvariable=v, width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1
    frm.columnconfigure(1, weight=1)

    result: dict[str, str] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, str] = {}
        for k, v in vars_.items():
            val = (v.get() or "").strip()
            if k == "room_leader":
                val = lead_id_by_label.get(val, val)
            out[k] = val
        result = out
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")

    dlg.wait_window()
    return result


@_safe_view
def open_add_room(host) -> None:
    logger.debug("GUI: rooms open_add_room")
    fields = _form_dialog(host, "Add Room")
    if not fields:
        host.status_var.set("Add room cancelled")
        open_manager(host)
        return
    try:
        r = data.create_room(fields)
    except ValidationError as e:
        messagebox.showerror("Add room", str(e), parent=host.root)
        open_manager(host)
        return
    messagebox.showinfo(
        "Room added",
        f"Created {r.name}\nID: {r.room_id}\nCapacity: {r.capacity}",
        parent=host.root,
    )
    host.status_var.set(f"Added room {r.room_id}")
    open_manager(host)


@_safe_view
def open_edit_room(host, room_id: str, *, on_done=None) -> None:
    logger.debug("GUI: rooms open_edit_room(%s)", room_id)
    r = data.get_room(room_id)
    if r is None:
        messagebox.showerror("Edit room", f"No room with id {room_id}",
                             parent=host.root)
        return
    initial = {key: getattr(r, key) for key, _label, _kind in _FIELDS}
    fields = _form_dialog(host, f"Edit {r.name}", initial=initial, is_edit=True)
    if not fields:
        return
    try:
        data.update_room(room_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit room", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated room {room_id}")
    if on_done:
        try:
            on_done()
        except Exception:
            logger.exception("on_done callback failed after edit")


# ── Legacy placeholder entry point ───────────────────────────────────────────

def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    """Standalone frame fallback (kept for the old placeholder call site)."""
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Rooms & Age Groups",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(
        frame,
        text="Open Rooms & Age Groups from the navigation menu.",
    ).pack(anchor="w")
    return frame
