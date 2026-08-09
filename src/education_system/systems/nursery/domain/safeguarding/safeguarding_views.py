"""Tkinter views for Safeguarding / Child Protection (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``). Lists safeguarding concerns with a severity-coloured tree + toolbar
and an add/edit form dialog — the GUI counterpart of ``safeguarding_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.safeguarding import (
    safeguarding as data,
)
from education_system.systems.nursery.domain.safeguarding.safeguarding import (
    CATEGORIES,
    SEVERITIES,
    STATUSES,
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


# (key, label, kind). kinds: entry, child, staff, category, severity, status, check
_FIELDS: list[tuple[str, str, str]] = [
    ("pupil_id",      "Child (optional)",     "child"),
    ("category",      "Category",             "category"),
    ("severity",      "Severity",             "severity"),
    ("date_raised",   "Date raised (YYYY-MM-DD)", "entry"),
    ("raised_by",     "Raised by",            "entry"),
    ("description",   "Description",          "entry"),
    ("dsl_reviewer",  "DSL reviewer",         "staff"),
    ("action_taken",  "Action taken",         "entry"),
    ("referral_made", "Referral made",        "check"),
    ("status",        "Status",               "status"),
    ("notes",         "Notes",                "entry"),
]

_SEV_COLOURS = {"high": "#c0392b", "medium": "#b9770e", "low": "#1e7e34"}


def _clear(host) -> ttk.Frame:
    host._clear_content()
    assert host.content_frame is not None
    return host.content_frame


def _header(parent: ttk.Frame, title: str) -> None:
    ttk.Label(parent, text=title, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _child_choices() -> list[tuple[str, str]]:
    try:
        return data.list_pupil_choices()
    except Exception:
        return []


def _staff_choices() -> list[tuple[str, str]]:
    try:
        return data.list_staff_choices()
    except Exception:
        return []


@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: safeguarding open_manager")
    root = _clear(host)
    _header(root, "Safeguarding / Child Protection")

    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 6))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Log Concern",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, summary)).pack(side="left", padx=2)

    cols = ("id", "date", "child", "category", "severity", "referral", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 70), ("date", "Date", 100), ("child", "Child", 150),
        ("category", "Category", 170), ("severity", "Severity", 80),
        ("referral", "Referral", 80), ("status", "Status", 100),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    for sev, colour in _SEV_COLOURS.items():
        tree.tag_configure(sev, foreground=colour)
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, summary)
    host.status_var.set("Safeguarding loaded")


def _refresh(tree: ttk.Treeview, summary: ttk.Label) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_concerns()
        s = data.summary()
    except Exception:
        logger.exception("Could not refresh safeguarding")
        try:
            messagebox.showerror("Safeguarding", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for c in rows:
        tree.insert("", "end", iid=c.concern_id, tags=(c.severity,), values=(
            c.concern_id, c.date_raised or "-", c.child_name or "-",
            c.category or "-", c.severity, "Yes" if c.referral_made else "No",
            c.status))
    summary.config(
        text=f"Concerns: {s['total']}    Open: {s['open']}    "
             f"Referred: {s['referred']}    High & open: {s['high_open']}",
        foreground="#a00" if s["high_open"] else "#555")


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Safeguarding", f"Select a concern to {verb}.",
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
    if not messagebox.askyesno("Delete concern", f"Delete concern {sel}?",
                               parent=host.root):
        return
    try:
        data.delete_concern(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete safeguarding %s", sel)
        messagebox.showerror("Delete concern", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted concern {sel}")


def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None
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
    children = _child_choices()
    staff = _staff_choices()
    child_label_by_id = {sid: lbl for sid, lbl in children}
    child_id_by_label = {lbl: sid for sid, lbl in children}
    staff_label_by_id = {sid: lbl for sid, lbl in staff}
    staff_id_by_label = {lbl: sid for sid, lbl in staff}
    vars_: dict[str, tk.Variable] = {}
    row = 0

    for key, label, kind in _FIELDS:
        if kind == "check":
            v = tk.BooleanVar(value=bool(initial.get(key)))
            ttk.Checkbutton(frm, text=label, variable=v).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=2)
            vars_[key] = v
            row += 1
            continue
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=2)
        cur = initial.get(key)
        if kind == "child":
            v = tk.StringVar(value=child_label_by_id.get(str(cur or ""), ""))
            ttk.Combobox(frm, textvariable=v,
                         values=[""] + [lbl for _i, lbl in children], width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "staff":
            v = tk.StringVar(value=staff_label_by_id.get(str(cur or ""), ""))
            ttk.Combobox(frm, textvariable=v,
                         values=[""] + [lbl for _i, lbl in staff], width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "category":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=[""] + list(CATEGORIES),
                         state="readonly", width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "severity":
            v = tk.StringVar(value=str(cur or "medium"))
            ttk.Combobox(frm, textvariable=v, values=list(SEVERITIES),
                         state="readonly", width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "status":
            v = tk.StringVar(value=str(cur or "open"))
            ttk.Combobox(frm, textvariable=v, values=list(STATUSES),
                         state="readonly", width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        else:
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Entry(frm, textvariable=v, width=34).grid(
                row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, Any] = {}
        for k, v in vars_.items():
            if isinstance(v, tk.BooleanVar):
                out[k] = 1 if v.get() else 0
                continue
            val = (v.get() or "").strip()
            if k == "pupil_id":
                val = child_id_by_label.get(val, "")
            elif k == "dsl_reviewer":
                val = staff_id_by_label.get(val, val)
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
def open_add(host) -> None:
    fields = _form_dialog(host, "Log Safeguarding Concern")
    if not fields:
        host.status_var.set("Log concern cancelled")
        open_manager(host)
        return
    try:
        c = data.create_concern(fields)
    except ValidationError as e:
        messagebox.showerror("Log concern", str(e), parent=host.root)
        open_manager(host)
        return
    host.status_var.set(f"Logged concern {c.concern_id}")
    open_manager(host)


@_safe_view
def open_edit(host, concern_id: str) -> None:
    c = data.get_concern(concern_id)
    if c is None:
        messagebox.showerror("Edit concern", f"No concern with id {concern_id}",
                             parent=host.root)
        return
    initial = {key: getattr(c, key) for key, _l, _k in _FIELDS}
    fields = _form_dialog(host, f"Edit concern {concern_id}", initial=initial)
    if not fields:
        return
    try:
        data.update_concern(concern_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit concern", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated concern {concern_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Safeguarding / Child Protection",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Safeguarding from the navigation menu.").pack(
        anchor="w")
    return frame
