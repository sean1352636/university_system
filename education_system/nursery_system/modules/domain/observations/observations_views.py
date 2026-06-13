"""Tkinter views for Observations (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Shows EYFS observations with a tree + toolbar and an add/edit form
dialog — the GUI counterpart of ``observations_cli.py``.
"""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.nursery_system.modules.domain.observations import (
    observations as data,
)
from education_system.nursery_system.modules.domain.observations.observations import (
    AREAS,
    OBS_TYPES,
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


# (key, label, kind) — kind one of entry/type/area/staff
_FIELDS: list[tuple[str, str, str]] = [
    ("observation_type", "Observation type",        "type"),
    ("area",             "EYFS area",               "area"),
    ("title",            "Title",                   "entry"),
    ("observation_date", "Date (YYYY-MM-DD)",        "entry"),
    ("description",      "Description",             "entry"),
    ("context",          "Context",                 "entry"),
    ("next_step",        "Next step",               "entry"),
    ("staff_id",         "Observer",                "staff"),
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
    logger.debug("GUI: observations open_manager")
    root = _clear(host)
    _header(root, "Observations")

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Observation",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: open_manager(host)).pack(side="left", padx=2)

    cols = ("id", "child", "date", "type", "area", "title")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=16)
    for c, label, w in [
        ("id", "ID", 70), ("child", "Child", 170), ("date", "Date", 100),
        ("type", "Type", 110), ("area", "Area", 260), ("title", "Title", 200),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree)
    host.status_var.set("Observations loaded")


def _refresh(tree: ttk.Treeview) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_observations()
    except Exception:
        logger.exception("Could not refresh observations")
        return
    for ob in rows:
        tree.insert("", "end", iid=ob.observation_id, values=(
            ob.observation_id, ob.child_name or "-", ob.observation_date or "-",
            ob.observation_type or "-", ob.area or "-", ob.title or "-"))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Observations", f"Select an observation to {verb}.",
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
    if not messagebox.askyesno("Delete observation",
                               f"Delete observation {sel}?",
                               parent=host.root):
        return
    try:
        data.delete_observation(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete observation %s", sel)
        messagebox.showerror("Delete observation", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted observation {sel}")


def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 pupil_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("500x480")
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
                     state="readonly" if choices else "normal", width=36).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_["__pupil_label"] = pvar
        row += 1

    for key, label, kind in _FIELDS:
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=2)
        cur = initial.get(key)
        if kind == "type":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=[""] + list(OBS_TYPES),
                         state="readonly", width=34).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "area":
            v = tk.StringVar(value=str(cur or ""))
            ttk.Combobox(frm, textvariable=v, values=[""] + list(AREAS),
                         state="readonly", width=34).grid(
                row=row, column=1, sticky="ew", pady=2)
        elif kind == "staff":
            v = tk.StringVar(value=staff_label_by_id.get(str(cur or ""), ""))
            ttk.Combobox(frm, textvariable=v,
                         values=[""] + [lbl for _i, lbl in staff],
                         state="readonly" if staff else "normal", width=34).grid(
                row=row, column=1, sticky="ew", pady=2)
        else:
            v = tk.StringVar(value="" if cur is None else str(cur))
            ttk.Entry(frm, textvariable=v, width=36).grid(
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
            elif k == "staff_id":
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
    fields = _form_dialog(host, "Add Observation",
                          pupil_choices=_pupil_choices())
    if not fields:
        host.status_var.set("Add observation cancelled")
        open_manager(host)
        return
    if not fields.get("pupil_id"):
        messagebox.showerror("Add observation", "Please choose a child.",
                             parent=host.root)
        open_manager(host)
        return
    try:
        ob = data.create_observation(fields)
    except ValidationError as e:
        messagebox.showerror("Add observation", str(e), parent=host.root)
        open_manager(host)
        return
    host.status_var.set(f"Logged observation {ob.observation_id}")
    open_manager(host)


@_safe_view
def open_edit(host, observation_id: str) -> None:
    ob = data.get_observation(observation_id)
    if ob is None:
        messagebox.showerror("Edit observation",
                             f"No observation with id {observation_id}",
                             parent=host.root)
        return
    initial = {key: getattr(ob, key) for key, _l, _k in _FIELDS}
    fields = _form_dialog(host, f"Edit observation — {ob.child_name}",
                          initial=initial, is_edit=True)
    if not fields:
        return
    try:
        data.update_observation(observation_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit observation", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated observation {observation_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Observations", font=("", 14, "bold")).pack(
        anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Observations from the navigation menu.").pack(
        anchor="w")
    return frame
