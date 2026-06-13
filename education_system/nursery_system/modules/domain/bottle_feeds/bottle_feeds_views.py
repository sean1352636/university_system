"""Tkinter views for Bottle Feeds (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Lists milk-feed records with a tree + toolbar and an add/edit form
dialog — the GUI counterpart of ``bottle_feeds_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.nursery_system.modules.domain.bottle_feeds import (
    bottle_feeds as data,
)
from education_system.nursery_system.modules.domain.bottle_feeds.bottle_feeds import (
    MILK_TYPES,
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


def _pupil_choices() -> list[tuple[str, str]]:
    try:
        return data.list_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        return []


def _staff_choices() -> list[tuple[str, str]]:
    try:
        return data.list_staff_choices()
    except Exception:
        logger.exception("Could not load staff choices")
        return []


@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: bottle_feeds open_manager")
    root = _clear(host)
    _header(root, "Bottle Feeds")

    date_var = tk.StringVar()

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Date (YYYY-MM-DD):").pack(side="left", padx=(0, 4))
    ttk.Entry(bar, textvariable=date_var, width=14).pack(side="left", padx=2)
    ttk.Button(bar, text="Load",
               command=lambda: _refresh(tree, date_var.get())).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Add",
               command=lambda: open_add(host)).pack(side="left", padx=(12, 2))
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, date_var.get())).pack(
        side="left", padx=2)

    cols = ("date", "time", "child", "milk", "offered", "taken", "temp")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=17)
    for c, label, w in [
        ("date", "Date", 100), ("time", "Time", 70), ("child", "Child", 180),
        ("milk", "Milk type", 170), ("offered", "Offered ml", 90),
        ("taken", "Taken ml", 90), ("temp", "Temp checked", 100),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, date_var.get())
    host.status_var.set("Bottle feeds loaded")


def _refresh(tree: ttk.Treeview, date_filter: str) -> None:
    for i in tree.get_children():
        tree.delete(i)
    df = (date_filter or "").strip() or None
    try:
        rows = data.list_records(feed_date=df)
    except Exception:
        logger.exception("Could not refresh bottle feeds")
        try:
            messagebox.showerror("Bottle feeds", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for r in rows:
        offered = r.offered_ml if r.offered_ml is not None else "-"
        taken = r.taken_ml if r.taken_ml is not None else "-"
        temp = "Yes" if r.temperature_checked else "No"
        tree.insert("", "end", iid=r.feed_id, values=(
            r.feed_date, r.feed_time or "-", r.child_name or "-", r.milk_type,
            offered, taken, temp))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Bottle feeds", f"Select a record to {verb}.",
                            parent=host.root)
        return None
    return sel


def _edit_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "edit")
    if sel:
        open_edit(host, sel)


def _delete_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "delete")
    if not sel:
        return
    r = data.get_record(sel)
    if r is None:
        return
    if not messagebox.askyesno(
            "Delete record",
            f"Delete bottle-feed record {sel} for {r.child_name}?",
            parent=host.root):
        return
    try:
        data.delete_record(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete bottle-feed %s", sel)
        messagebox.showerror("Delete record", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted bottle-feed record {sel}")


# ── Form dialog ──────────────────────────────────────────────────────────────

def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 pupil_choices: list[tuple[str, str]] | None = None,
                 staff_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("470x520")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    row = 0

    # Child picker only when adding a new record.
    pupil_choices = pupil_choices or []
    pid_by_label = {lbl: sid for sid, lbl in pupil_choices}
    pvar = tk.StringVar()
    if not is_edit:
        ttk.Label(frm, text="Child:").grid(row=row, column=0, sticky="nw", pady=2)
        ttk.Combobox(frm, textvariable=pvar,
                     values=[lbl for _i, lbl in pupil_choices],
                     state="readonly" if pupil_choices else "normal", width=34).grid(
            row=row, column=1, sticky="ew", pady=2)
        row += 1

    date_var = tk.StringVar(value=str(initial.get("feed_date") or ""))
    ttk.Label(frm, text="Feed date (YYYY-MM-DD):").grid(
        row=row, column=0, sticky="nw", pady=2)
    ttk.Entry(frm, textvariable=date_var, width=34).grid(
        row=row, column=1, sticky="ew", pady=2)
    row += 1

    time_var = tk.StringVar(value=str(initial.get("feed_time") or ""))
    ttk.Label(frm, text="Feed time (HH:MM):").grid(
        row=row, column=0, sticky="nw", pady=2)
    ttk.Entry(frm, textvariable=time_var, width=34).grid(
        row=row, column=1, sticky="ew", pady=2)
    row += 1

    milk_var = tk.StringVar(value=str(initial.get("milk_type") or "Formula"))
    ttk.Label(frm, text="Milk type:").grid(row=row, column=0, sticky="nw", pady=2)
    ttk.Combobox(frm, textvariable=milk_var, values=list(MILK_TYPES),
                 state="readonly", width=32).grid(
        row=row, column=1, sticky="ew", pady=2)
    row += 1

    offered_var = tk.StringVar(
        value="" if initial.get("offered_ml") is None else str(initial["offered_ml"]))
    ttk.Label(frm, text="Offered (ml):").grid(row=row, column=0, sticky="nw", pady=2)
    ttk.Entry(frm, textvariable=offered_var, width=34).grid(
        row=row, column=1, sticky="ew", pady=2)
    row += 1

    taken_var = tk.StringVar(
        value="" if initial.get("taken_ml") is None else str(initial["taken_ml"]))
    ttk.Label(frm, text="Taken (ml):").grid(row=row, column=0, sticky="nw", pady=2)
    ttk.Entry(frm, textvariable=taken_var, width=34).grid(
        row=row, column=1, sticky="ew", pady=2)
    row += 1

    temp_default = initial.get("temperature_checked", 1) if initial else 1
    temp_var = tk.BooleanVar(value=bool(temp_default))
    ttk.Checkbutton(frm, text="Temperature checked", variable=temp_var).grid(
        row=row, column=0, columnspan=2, sticky="w", pady=2)
    row += 1

    winded_var = tk.BooleanVar(value=bool(initial.get("winded")))
    ttk.Checkbutton(frm, text="Winded", variable=winded_var).grid(
        row=row, column=0, columnspan=2, sticky="w", pady=2)
    row += 1

    staff_choices = staff_choices or []
    sid_by_label = {lbl: sid for sid, lbl in staff_choices}
    label_by_sid = {sid: lbl for sid, lbl in staff_choices}
    svar = tk.StringVar(value=label_by_sid.get(initial.get("staff_id"), ""))
    ttk.Label(frm, text="Staff:").grid(row=row, column=0, sticky="nw", pady=2)
    ttk.Combobox(frm, textvariable=svar,
                 values=[""] + [lbl for _i, lbl in staff_choices],
                 state="readonly" if staff_choices else "normal", width=34).grid(
        row=row, column=1, sticky="ew", pady=2)
    row += 1

    notes_var = tk.StringVar(value=str(initial.get("notes") or ""))
    ttk.Label(frm, text="Notes:").grid(row=row, column=0, sticky="nw", pady=2)
    ttk.Entry(frm, textvariable=notes_var, width=34).grid(
        row=row, column=1, sticky="ew", pady=2)
    row += 1
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, Any] = {
            "feed_date": date_var.get().strip(),
            "feed_time": time_var.get().strip(),
            "milk_type": milk_var.get().strip(),
            "offered_ml": offered_var.get().strip(),
            "taken_ml": taken_var.get().strip(),
            "temperature_checked": 1 if temp_var.get() else 0,
            "winded": 1 if winded_var.get() else 0,
            "staff_id": sid_by_label.get(svar.get().strip(), ""),
            "notes": notes_var.get().strip(),
        }
        if not is_edit:
            out["pupil_id"] = pid_by_label.get(pvar.get().strip(), "")
        result = out
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_add(host) -> None:
    logger.debug("GUI: bottle_feeds open_add")
    fields = _form_dialog(host, "Add Bottle Feed",
                          pupil_choices=_pupil_choices(),
                          staff_choices=_staff_choices())
    if not fields:
        host.status_var.set("Add bottle-feed cancelled")
        open_manager(host)
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Add record", "Please choose a child.",
                             parent=host.root)
        open_manager(host)
        return
    try:
        r = data.create_record(fields)
    except ValidationError as e:
        messagebox.showerror("Add record", str(e), parent=host.root)
        open_manager(host)
        return
    messagebox.showinfo(
        "Record added",
        f"{r.child_name} — {r.milk_type} on {r.feed_date}",
        parent=host.root)
    host.status_var.set(f"Added bottle-feed {r.feed_id}")
    open_manager(host)


@_safe_view
def open_edit(host, feed_id: str) -> None:
    logger.debug("GUI: bottle_feeds open_edit(%s)", feed_id)
    r = data.get_record(feed_id)
    if r is None:
        messagebox.showerror("Edit record", f"No record with id {feed_id}",
                             parent=host.root)
        return
    initial = {
        "feed_date": r.feed_date, "feed_time": r.feed_time,
        "milk_type": r.milk_type, "offered_ml": r.offered_ml,
        "taken_ml": r.taken_ml, "temperature_checked": r.temperature_checked,
        "winded": r.winded, "staff_id": r.staff_id, "notes": r.notes,
    }
    fields = _form_dialog(host, f"Edit {r.child_name} — bottle feed",
                          initial=initial, is_edit=True,
                          staff_choices=_staff_choices())
    if not fields:
        return
    try:
        data.update_record(feed_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit record", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated bottle-feed {feed_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Bottle Feeds",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Bottle Feeds from the navigation menu."
              ).pack(anchor="w")
    return frame
