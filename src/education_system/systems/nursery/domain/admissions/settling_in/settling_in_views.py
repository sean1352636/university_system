"""Tkinter views for Settling-In (Nursery System).

Renders into the shared content pane of ``gui_main.NurseryMainGUI`` (the
``host``). Shows a per-child settling summary and the session log with a tree +
toolbar and an add/edit form dialog — the GUI counterpart of
``settling_in_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.admissions.settling_in import (
    settling_in as data,
)
from education_system.systems.nursery.domain.admissions.settling_in.settling_in import (
    RATINGS,
    SESSION_TYPES,
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
    ("session_date",     "Session date (YYYY-MM-DD)", "entry"),
    ("session_type",     "Session type",              "type"),
    ("duration_minutes", "Duration (minutes)",        "entry"),
    ("key_person",       "Key person",                "staff"),
    ("settled_rating",   "Settled rating",            "rating"),
    ("notes",            "Notes",                     "entry"),
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


def _staff_choices() -> list[tuple[str, str]]:
    try:
        return data.list_staff_choices()
    except Exception:
        logger.exception("Could not load staff choices")
        return []


@_safe_view
def open_manager(host) -> None:
    logger.debug("GUI: settling_in open_manager")
    root = _clear(host)
    _header(root, "Settling-In")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Session",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: open_manager(host)).pack(side="left", padx=2)

    # Per-child summary (collapsed table at the top).
    ttk.Label(root, text="Children — latest settling status",
              font=("", 10, "bold")).pack(anchor="w", pady=(4, 2))
    scols = ("pupil", "name", "room", "sessions", "rating")
    stree = ttk.Treeview(root, columns=scols, show="headings", height=6)
    for c, label, w in [
        ("pupil", "Pupil", 70), ("name", "Name", 200), ("room", "Room", 140),
        ("sessions", "Sessions", 80), ("rating", "Latest rating", 120),
    ]:
        stree.heading(c, text=label)
        stree.column(c, width=w, anchor="w")
    stree.pack(fill="x")
    try:
        for c in data.list_by_child():
            stree.insert("", "end", values=(
                c.pupil_id, c.child_name, c.room or "-", c.session_count,
                c.latest_rating or "— none —"))
    except Exception:
        logger.exception("Could not load settling-in by-child summary")

    ttk.Label(root, text="Sessions", font=("", 10, "bold")).pack(
        anchor="w", pady=(10, 2))
    cols = ("id", "child", "date", "type", "rating", "key_person")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=12)
    for c, label, w in [
        ("id", "ID", 70), ("child", "Child", 180), ("date", "Date", 100),
        ("type", "Type", 130), ("rating", "Rating", 100),
        ("key_person", "Key person", 160),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree)
    host.status_var.set("Settling-in loaded")


def _refresh(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_sessions()
    except Exception:
        logger.exception("Could not refresh settling-in sessions")
        return
    for s in rows:
        tree.insert("", "end", iid=s.session_id, values=(
            s.session_id, s.child_name or "-", s.session_date or "-",
            s.session_type or "-", s.settled_rating or "-",
            s.key_person_name or "-"))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Settling-in", f"Select a session to {verb}.",
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
    if not messagebox.askyesno("Delete session", f"Delete session {sel}?",
                               parent=host.root):
        return
    try:
        data.delete_session(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete settling-in %s", sel)
        messagebox.showerror("Delete session", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted session {sel}")


def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 pupil_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("450x400")
    try:
        dlg.wait_visibility(); dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    initial = initial or {}
    staff = _staff_choices()
    staff_label_by_id = {sid: lbl for sid, lbl in staff}
    staff_id_by_label = {lbl: sid for sid, lbl in staff}
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
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=2)
        cur = initial.get(key)
        if kind == "type":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=[""] + list(SESSION_TYPES),
                         state="readonly", width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "rating":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=[""] + list(RATINGS),
                         state="readonly", width=32).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "staff":
            v = tk.StringVar(value=staff_label_by_id.get(str(cur or ""), ""))
            ttk.Combobox(frm, textvariable=v,
                         values=[""] + [lbl for _i, lbl in staff],
                         state="readonly" if staff else "normal", width=32).grid(
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
            val = (v.get() or "").strip()
            if k == "__pupil_label":
                out["pupil_id"] = pid_id_by_label.get(val, "")
            elif k == "key_person":
                out[k] = staff_id_by_label.get(val, val)
            else:
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
    fields = _form_dialog(host, "Add Settling-In Session",
                          pupil_choices=_pupil_choices())
    if not fields:
        host.status_var.set("Add session cancelled")
        open_manager(host)
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Add session", "Please choose a child.",
                             parent=host.root)
        open_manager(host)
        return
    try:
        s = data.create_session(fields)
    except ValidationError as e:
        messagebox.showerror("Add session", str(e), parent=host.root)
        open_manager(host)
        return
    host.status_var.set(f"Logged settling-in session {s.session_id}")
    open_manager(host)


@_safe_view
def open_edit(host, session_id: str) -> None:
    s = data.get_session(session_id)
    if s is None:
        messagebox.showerror("Edit session", f"No session with id {session_id}",
                             parent=host.root)
        return
    initial = {key: getattr(s, key) for key, _l, _k in _FIELDS}
    fields = _form_dialog(host, f"Edit session — {s.child_name}",
                          initial=initial, is_edit=True)
    if not fields:
        return
    try:
        data.update_session(session_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit session", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated session {session_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Settling-In", font=("", 14, "bold")).pack(
        anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Settling-In from the navigation menu.").pack(
        anchor="w")
    return frame
