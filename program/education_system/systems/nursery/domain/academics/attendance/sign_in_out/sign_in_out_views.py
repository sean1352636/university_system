"""Tkinter views for Sign In / Sign Out (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``). Lists the day's arrival / collection events with a tree + toolbar
and a sign-in / sign-out form dialog — the GUI counterpart of
``sign_in_out_cli.py``.
"""

from __future__ import annotations

import datetime as _dt
import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.academics.attendance.sign_in_out import (
    sign_in_out as data,
)
from education_system.systems.nursery.domain.academics.attendance.sign_in_out.sign_in_out import (
    ValidationError,
)

logger = logging.getLogger(__name__)


def _today() -> str:
    return _dt.date.today().isoformat()


def _now() -> str:
    return _dt.datetime.now().strftime("%H:%M")


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
    logger.debug("GUI: sign_in_out open_manager")
    root = _clear(host)
    _header(root, "Sign In / Sign Out")

    date_var = tk.StringVar(value=_today())

    filt = ttk.Frame(root)
    filt.pack(fill="x", pady=(0, 6))
    ttk.Label(filt, text="Date (YYYY-MM-DD):").pack(side="left")
    ttk.Entry(filt, textvariable=date_var, width=14).pack(side="left", padx=4)
    ttk.Button(filt, text="Load",
               command=lambda: _refresh(tree, date_var.get())).pack(side="left")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Sign In",
               command=lambda: open_sign(host, "in")).pack(side="left", padx=2)
    ttk.Button(bar, text="Sign Out",
               command=lambda: open_sign(host, "out")).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, date_var.get())).pack(
        side="left", padx=2)

    cols = ("time", "child", "direction", "person", "relationship", "recorded")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=17)
    for c, label, w in [
        ("time", "Time", 70), ("child", "Child", 180),
        ("direction", "Direction", 90), ("person", "Person", 170),
        ("relationship", "Relationship", 130), ("recorded", "Recorded by", 160),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.tag_configure("out", background="#fce8e6")
    tree.tag_configure("in", background="#e6f4ea")
    tree.pack(fill="both", expand=True)

    _refresh(tree, date_var.get())
    host.status_var.set("Sign in / out loaded")


def _refresh(tree: ttk.Treeview, event_date: str) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_events(event_date=(event_date or "").strip() or None)
    except Exception:
        logger.exception("Could not refresh sign in / out")
        try:
            messagebox.showerror("Sign in / out", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for r in rows:
        tree.insert("", "end", iid=r.event_id, tags=(r.direction,), values=(
            r.event_time or "-", r.child_name or "-", r.direction,
            r.person_name or "-", r.relationship or "-",
            r.recorded_by_name or "-"))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Sign in / out", f"Select an event to {verb}.",
                            parent=host.root)
        return None
    return sel


def _delete_selected(tree: ttk.Treeview, host) -> None:
    sel = _selected(tree, host, "delete")
    if not sel:
        return
    r = data.get_event(sel)
    if r is None:
        return
    if not messagebox.askyesno(
            "Delete event",
            f"Delete event {sel} ({r.direction} — {r.child_name})?",
            parent=host.root):
        return
    try:
        data.delete_event(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete sign in / out %s", sel)
        messagebox.showerror("Delete event", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted event {sel}")


# ── Form dialog ──────────────────────────────────────────────────────────────

def _form_dialog(host, direction: str,
                 pupil_choices: list[tuple[str, str]],
                 staff_choices: list[tuple[str, str]]) -> dict[str, Any] | None:
    verb = "In" if direction == "in" else "Out"
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Sign {verb}")
    dlg.transient(host.root)
    dlg.geometry("470x420")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    pid_by_label = {lbl: sid for sid, lbl in pupil_choices}
    staff_by_label = {lbl: sid for sid, lbl in staff_choices}

    row = 0
    ttk.Label(frm, text="Child:").grid(row=row, column=0, sticky="nw", pady=2)
    pvar = tk.StringVar()
    ttk.Combobox(frm, textvariable=pvar,
                 values=[lbl for _i, lbl in pupil_choices],
                 state="readonly" if pupil_choices else "normal", width=34).grid(
        row=row, column=1, sticky="ew", pady=2)
    row += 1

    ttk.Label(frm, text="Person name:").grid(row=row, column=0, sticky="nw", pady=2)
    person_var = tk.StringVar()
    ttk.Entry(frm, textvariable=person_var, width=34).grid(
        row=row, column=1, sticky="ew", pady=2)
    row += 1

    ttk.Label(frm, text="Relationship:").grid(row=row, column=0, sticky="nw", pady=2)
    rel_var = tk.StringVar()
    ttk.Entry(frm, textvariable=rel_var, width=34).grid(
        row=row, column=1, sticky="ew", pady=2)
    row += 1

    ttk.Label(frm, text="Time (HH:MM):").grid(row=row, column=0, sticky="nw", pady=2)
    time_var = tk.StringVar(value=_now())
    ttk.Entry(frm, textvariable=time_var, width=34).grid(
        row=row, column=1, sticky="ew", pady=2)
    row += 1

    ttk.Label(frm, text="Recorded by:").grid(row=row, column=0, sticky="nw", pady=2)
    staff_var = tk.StringVar()
    ttk.Combobox(frm, textvariable=staff_var,
                 values=[lbl for _i, lbl in staff_choices],
                 state="readonly" if staff_choices else "normal", width=34).grid(
        row=row, column=1, sticky="ew", pady=2)
    row += 1

    ttk.Label(frm, text="Notes:").grid(row=row, column=0, sticky="nw", pady=2)
    notes_var = tk.StringVar()
    ttk.Entry(frm, textvariable=notes_var, width=34).grid(
        row=row, column=1, sticky="ew", pady=2)
    row += 1
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id": pid_by_label.get((pvar.get() or "").strip(), ""),
            "direction": direction,
            "event_time": (time_var.get() or "").strip(),
            "person_name": (person_var.get() or "").strip(),
            "relationship": (rel_var.get() or "").strip(),
            "recorded_by": staff_by_label.get((staff_var.get() or "").strip(), ""),
            "notes": (notes_var.get() or "").strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_sign(host, direction: str) -> None:
    logger.debug("GUI: sign_in_out open_sign(%s)", direction)
    fields = _form_dialog(host, direction, _pupil_choices(), _staff_choices())
    if not fields:
        host.status_var.set("Sign in / out cancelled")
        open_manager(host)
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Sign in / out", "Please choose a child.",
                             parent=host.root)
        open_manager(host)
        return
    try:
        r = data.create_event(fields)
    except ValidationError as e:
        messagebox.showerror("Sign in / out", str(e), parent=host.root)
        open_manager(host)
        return
    verb = "in" if direction == "in" else "out"
    messagebox.showinfo(
        "Event recorded",
        f"{r.child_name} signed {verb} at {r.event_time or '-'}.",
        parent=host.root)
    host.status_var.set(f"Signed {r.child_name} {verb} ({r.event_id})")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Sign In / Sign Out",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Sign In / Sign Out from the navigation menu."
              ).pack(anchor="w")
    return frame
