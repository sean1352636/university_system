"""Tkinter views for Sleep Log (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``). Lists nap records with a tree + toolbar and an add/edit form
dialog — the GUI counterpart of ``sleep_log_cli.py``.
"""

from __future__ import annotations

import datetime as _dt
import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.operations.daily_care.sleep_log import sleep_log as data
from education_system.systems.nursery.domain.operations.daily_care.sleep_log.sleep_log import (
    LOCATIONS,
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


def _fmt_duration(minutes: int | None) -> str:
    if minutes is None:
        return "-"
    h, m = divmod(minutes, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m"


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
    logger.debug("GUI: sleep_log open_manager")
    root = _clear(host)
    _header(root, "Sleep Log")

    date_var = tk.StringVar()

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Label(bar, text="Date (YYYY-MM-DD):").pack(side="left", padx=(0, 4))
    ttk.Entry(bar, textvariable=date_var, width=14).pack(side="left", padx=2)
    ttk.Button(bar, text="Load",
               command=lambda: _refresh(tree, summary, date_var.get())).pack(
        side="left", padx=2)
    ttk.Button(bar, text="Clear",
               command=lambda: (date_var.set(""),
                                _refresh(tree, summary, ""))).pack(
        side="left", padx=2)

    bar2 = ttk.Frame(root)
    bar2.pack(fill="x", pady=(0, 8))
    ttk.Button(bar2, text="Add Record",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar2, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar2, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar2, text="Refresh",
               command=lambda: _refresh(tree, summary, date_var.get())).pack(
        side="left", padx=2)

    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 6))

    cols = ("date", "child", "start", "end", "duration", "location", "checks")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=17)
    for c, label, w in [
        ("date", "Date", 100), ("child", "Child", 180), ("start", "Start", 70),
        ("end", "End", 70), ("duration", "Duration", 90),
        ("location", "Location", 110), ("checks", "Checks", 70),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, summary, "")
    host.status_var.set("Sleep log loaded")


def _refresh(tree: ttk.Treeview, summary: ttk.Label, sleep_date: str) -> None:
    sleep_date = (sleep_date or "").strip()
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_records(sleep_date=sleep_date or None)
    except Exception:
        logger.exception("Could not refresh sleep log")
        try:
            messagebox.showerror("Sleep log", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    total = 0
    for r in rows:
        total += r.duration_minutes or 0
        tree.insert("", "end", iid=r.sleep_id, values=(
            r.sleep_date, r.child_name or "-", r.start_time or "-",
            r.end_time or "-", _fmt_duration(r.duration_minutes),
            r.location or "-", r.checks))
    scope = f"date {sleep_date}" if sleep_date else "all dates"
    summary.config(text=f"Naps ({scope}): {len(rows)}   "
                        f"Total slept: {_fmt_duration(total)}")


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Sleep log", f"Select a record to {verb}.",
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
            f"Delete sleep record {sel} for {r.child_name}?",
            parent=host.root):
        return
    try:
        data.delete_record(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete sleep-log %s", sel)
        messagebox.showerror("Delete record", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted sleep record {sel}")


# ── Form dialog ──────────────────────────────────────────────────────────────

def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 pupil_choices: list[tuple[str, str]] | None = None,
                 staff_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("470x470")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    vars_: dict[str, tk.Variable] = {}
    row = 0

    # Child picker only when adding a new record.
    pid_id_by_label: dict[str, str] = {}
    if not is_edit:
        ttk.Label(frm, text="Child:").grid(row=row, column=0, sticky="nw", pady=2)
        choices = pupil_choices or []
        pid_id_by_label = {lbl: sid for sid, lbl in choices}
        pvar = tk.StringVar()
        ttk.Combobox(frm, textvariable=pvar,
                     values=[lbl for _i, lbl in choices],
                     state="readonly" if choices else "normal", width=34).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_["__pupil_label"] = pvar
        row += 1

    def _entry(key: str, label: str) -> None:
        nonlocal row
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=2)
        v = tk.StringVar(value="" if initial.get(key) is None else str(initial[key]))
        ttk.Entry(frm, textvariable=v, width=34).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1

    today = _dt.date.today().isoformat()
    if not initial.get("sleep_date"):
        initial = {**initial, "sleep_date": today}
    _entry("sleep_date", "Sleep date (YYYY-MM-DD)")
    _entry("start_time", "Start time (HH:MM)")
    _entry("end_time", "End time (HH:MM)")

    # Location combobox (editable).
    ttk.Label(frm, text="Location:").grid(row=row, column=0, sticky="nw", pady=2)
    lvar = tk.StringVar(value=str(initial.get("location") or ""))
    ttk.Combobox(frm, textvariable=lvar, values=list(LOCATIONS),
                 width=32).grid(row=row, column=1, sticky="ew", pady=2)
    vars_["location"] = lvar
    row += 1

    # Checks spinbox.
    ttk.Label(frm, text="Sleep checks:").grid(row=row, column=0, sticky="nw", pady=2)
    cvar = tk.StringVar(value=str(initial.get("checks") if initial.get("checks")
                                  is not None else 0))
    tk.Spinbox(frm, from_=0, to=99, textvariable=cvar, width=6).grid(
        row=row, column=1, sticky="w", pady=2)
    vars_["checks"] = cvar
    row += 1

    # Staff combobox.
    ttk.Label(frm, text="Staff:").grid(row=row, column=0, sticky="nw", pady=2)
    schoices = staff_choices or []
    sid_id_by_label = {lbl: sid for sid, lbl in schoices}
    label_by_sid = {sid: lbl for sid, lbl in schoices}
    svar = tk.StringVar(value=label_by_sid.get(initial.get("staff_id"), ""))
    ttk.Combobox(frm, textvariable=svar, values=[lbl for _i, lbl in schoices],
                 state="readonly" if schoices else "normal", width=34).grid(
        row=row, column=1, sticky="ew", pady=2)
    vars_["__staff_label"] = svar
    row += 1

    _entry("notes", "Notes")
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, Any] = {}
        for k, v in vars_.items():
            if k == "__pupil_label":
                out["pupil_id"] = pid_id_by_label.get((v.get() or "").strip(), "")
            elif k == "__staff_label":
                out["staff_id"] = sid_id_by_label.get((v.get() or "").strip(), "")
            else:
                out[k] = (v.get() or "").strip()
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
    logger.debug("GUI: sleep_log open_add")
    fields = _form_dialog(host, "Add Sleep Record",
                          pupil_choices=_pupil_choices(),
                          staff_choices=_staff_choices())
    if not fields:
        host.status_var.set("Add sleep record cancelled")
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
        f"{r.child_name}\n{r.sleep_date}  ·  {_fmt_duration(r.duration_minutes)}",
        parent=host.root)
    host.status_var.set(f"Added sleep record {r.sleep_id}")
    open_manager(host)


@_safe_view
def open_edit(host, sleep_id: str) -> None:
    logger.debug("GUI: sleep_log open_edit(%s)", sleep_id)
    r = data.get_record(sleep_id)
    if r is None:
        messagebox.showerror("Edit record", f"No record with id {sleep_id}",
                             parent=host.root)
        return
    initial = {
        "sleep_date": r.sleep_date, "start_time": r.start_time,
        "end_time": r.end_time, "duration_minutes": r.duration_minutes,
        "location": r.location, "checks": r.checks,
        "staff_id": r.staff_id, "notes": r.notes,
    }
    fields = _form_dialog(host, f"Edit {r.child_name} — sleep record",
                          initial=initial, is_edit=True,
                          staff_choices=_staff_choices())
    if not fields:
        return
    try:
        data.update_record(sleep_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit record", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated sleep record {sleep_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Sleep Log",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Sleep Log from the navigation menu."
              ).pack(anchor="w")
    return frame
