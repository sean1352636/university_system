"""Tkinter views for Transition to School (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``). Lists transitions with a tree + toolbar and an add/edit form dialog
— the GUI counterpart of ``transitions_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.progression.transitions import (
    transitions as data,
)
from education_system.systems.nursery.domain.progression.transitions.transitions import (
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


_FIELDS: list[tuple[str, str, str]] = [
    ("destination_school",     "Destination school",          "entry"),
    ("expected_start",         "Expected start (YYYY-MM-DD)", "entry"),
    ("transition_report_sent", "Transition report sent",      "check"),
    ("report_sent_date",       "Report sent date (YYYY-MM-DD)", "entry"),
    ("teacher_visit",          "Reception teacher visit done", "check"),
    ("activities",             "Transition activities",       "entry"),
    ("notes",                  "Notes",                       "entry"),
    ("status",                 "Status",                      "status"),
]


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


@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: transitions open_manager")
    root = _clear(host)
    _header(root, "Transition to School")

    summary = ttk.Label(root, foreground="#555")
    summary.pack(anchor="w", pady=(0, 6))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Transition",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, summary)).pack(side="left", padx=2)

    cols = ("id", "child", "secondary", "start", "report", "visit", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 70), ("child", "Child", 170), ("secondary", "Destination", 200),
        ("start", "Start", 100), ("report", "Report sent", 90),
        ("visit", "Teacher visit", 100), ("status", "Status", 100),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, summary)
    host.status_var.set("Transitions loaded")


def _refresh(tree: ttk.Treeview, summary: ttk.Label) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_transitions()
        counts = data.counts_by_status()
    except Exception:
        logger.exception("Could not refresh transitions")
        try:
            messagebox.showerror("Transitions", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for t in rows:
        tree.insert("", "end", iid=t.transition_id, values=(
            t.transition_id, t.child_name or "-", t.destination_school or "-",
            t.expected_start or "-",
            "Yes" if t.transition_report_sent else "No",
            "Yes" if t.teacher_visit else "No", t.status))
    summary.config(text="Totals: " + "  ".join(
        f"{k}={v}" for k, v in sorted(counts.items())) if counts else "")


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Transitions", f"Select a transition to {verb}.",
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
    if not messagebox.askyesno("Delete transition", f"Delete transition {sel}?",
                               parent=host.root):
        return
    try:
        data.delete_transition(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete transition %s", sel)
        messagebox.showerror("Delete transition", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted transition {sel}")


def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 pupil_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("470x440")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    vars_: dict[str, tk.Variable] = {}
    row = 0

    pid_id_by_label: dict[str, str] = {}
    if not is_edit:
        ttk.Label(frm, text="Child:").grid(row=row, column=0, sticky="nw", pady=2)
        choices = pupil_choices or []
        pid_id_by_label = {lbl: sid for sid, lbl in choices}
        pvar = tk.StringVar()
        ttk.Combobox(frm, textvariable=pvar, values=[lbl for _i, lbl in choices],
                     state="readonly" if choices else "normal", width=34).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_["__pupil_label"] = pvar
        row += 1

    for key, label, kind in _FIELDS:
        if key == "status" and not is_edit:
            continue
        if kind == "check":
            v = tk.BooleanVar(value=bool(initial.get(key)))
            ttk.Checkbutton(frm, text=label, variable=v).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=2)
            vars_[key] = v
            row += 1
            continue
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=2)
        cur = initial.get(key)
        if kind == "status":
            v = tk.StringVar(value=str(cur or "planned"))
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
            if k == "__pupil_label":
                out["pupil_id"] = pid_id_by_label.get((v.get() or "").strip(), "")
            elif isinstance(v, tk.BooleanVar):
                out[k] = 1 if v.get() else 0
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
    fields = _form_dialog(host, "Add Transition", pupil_choices=_pupil_choices())
    if not fields:
        host.status_var.set("Add transition cancelled")
        open_manager(host)
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Add transition", "Please choose a child.",
                             parent=host.root)
        open_manager(host)
        return
    try:
        t = data.create_transition(fields)
    except ValidationError as e:
        messagebox.showerror("Add transition", str(e), parent=host.root)
        open_manager(host)
        return
    host.status_var.set(f"Added transition {t.transition_id}")
    open_manager(host)


@_safe_view
def open_edit(host, transition_id: str) -> None:
    t = data.get_transition(transition_id)
    if t is None:
        messagebox.showerror("Edit transition",
                             f"No transition with id {transition_id}",
                             parent=host.root)
        return
    initial = {key: getattr(t, key) for key, _l, _k in _FIELDS}
    fields = _form_dialog(host, f"Edit transition — {t.child_name}",
                          initial=initial, is_edit=True)
    if not fields:
        return
    try:
        data.update_transition(transition_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit transition", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated transition {transition_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Transition to School",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Transition to School from the navigation menu."
              ).pack(anchor="w")
    return frame
