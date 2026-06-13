"""Tk views for classes in the Primary School System."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.primarysch_system.modules.domain.classes import (
    classes as data,
)
from education_system.primarysch_system.modules.domain.classes.classes import (
    SchoolClass,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror("Classes", str(e),
                                     parent=getattr(host, "root", None))
            except Exception:
                pass
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=getattr(host, "root", None),
                )
            except Exception:
                pass
    return wrapper


@_safe_view
def open_classes(host) -> None:
    logger.debug("GUI: open_classes")

    win = tk.Toplevel(host.root)
    win.title("Classes")
    win.transient(host.root)
    win.geometry("960x560")

    top = ttk.Frame(win, padding=10)
    top.pack(fill="x")
    summary_var = tk.StringVar()
    ttk.Label(top, textvariable=summary_var,
              font=("Segoe UI", 10, "bold")).pack(side="left")

    filt = ttk.Frame(win, padding=(10, 0, 10, 6))
    filt.pack(fill="x")
    ttk.Label(filt, text="Year:").pack(side="left")
    year_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=year_var,
                 values=["All"] + list(YEAR_GROUPS),
                 state="readonly", width=6).pack(side="left", padx=(4, 12))
    active_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(filt, text="Active only",
                    variable=active_var).pack(side="left")

    cols = ("class_id", "name", "year", "teacher", "room",
            "capacity", "enrolled", "active")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=15)
    for col, label, width, anchor in [
        ("class_id", "ID", 50, "center"),
        ("name", "Name", 180, "w"),
        ("year", "Year", 60, "center"),
        ("teacher", "Teacher", 200, "w"),
        ("room", "Room", 100, "w"),
        ("capacity", "Cap", 60, "center"),
        ("enrolled", "Enrolled", 80, "center"),
        ("active", "Active", 70, "center"),
    ]:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor=anchor)
    tree.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    btns = ttk.Frame(win, padding=10)
    btns.pack(fill="x")

    def _refresh() -> None:
        try:
            y = None if year_var.get() == "All" else year_var.get()
            rows = data.list_all(year_group=y, active_only=active_var.get())
        except ValidationError as e:
            messagebox.showerror("Classes", str(e), parent=win)
            return
        except Exception:
            logger.exception("classes refresh failed")
            messagebox.showerror("Error",
                                 "Could not load classes — see logs.",
                                 parent=win)
            return
        for iid in tree.get_children():
            tree.delete(iid)
        for c in rows:
            try:
                enrolled = len(data.pupils_in_class(c.name))
            except Exception:
                logger.exception("pupils_in_class(%s) failed", c.name)
                enrolled = 0
            tree.insert("", "end", iid=str(c.class_id), values=(
                c.class_id, c.name, c.year_group, c.teacher or "",
                c.room or "", c.capacity if c.capacity is not None else "",
                enrolled, "yes" if c.is_active else "no",
            ))
        try:
            counts = data.counts()
        except Exception:
            counts = {"total": 0, "active": 0, "inactive": 0}
        summary_var.set(
            f"Total: {counts['total']}   "
            f"Active: {counts['active']}   "
            f"Inactive: {counts['inactive']}"
        )

    def _selected_id() -> int | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Classes", "Select a class first.", parent=win)
            return None
        return int(sel[0])

    def _add() -> None:
        _open_form_dialog(win, class_id=None, on_saved=_refresh)

    def _edit() -> None:
        cid = _selected_id()
        if cid is None:
            return
        _open_form_dialog(win, class_id=cid, on_saved=_refresh)

    def _view_pupils() -> None:
        cid = _selected_id()
        if cid is None:
            return
        try:
            cls = data.get(cid)
        except Exception:
            logger.exception("get(%s) failed", cid)
            messagebox.showerror("Error", "Could not load class — see logs.",
                                 parent=win)
            return
        if cls is None:
            messagebox.showerror("Classes", f"No class #{cid}", parent=win)
            return
        _open_pupils_dialog(win, cls)

    def _toggle() -> None:
        cid = _selected_id()
        if cid is None:
            return
        try:
            data.toggle_active(cid)
        except ValidationError as e:
            messagebox.showerror("Classes", str(e), parent=win)
            return
        except Exception:
            logger.exception("toggle_active(%s) failed", cid)
            messagebox.showerror("Error", "Could not toggle — see logs.",
                                 parent=win)
            return
        _refresh()

    def _delete() -> None:
        cid = _selected_id()
        if cid is None:
            return
        if not messagebox.askyesno("Delete class",
                                   f"Delete class #{cid}?", parent=win):
            return
        try:
            data.delete(cid)
        except ValidationError as e:
            messagebox.showerror("Classes", str(e), parent=win)
            return
        except Exception:
            logger.exception("delete(%s) failed", cid)
            messagebox.showerror("Error", "Could not delete — see logs.",
                                 parent=win)
            return
        _refresh()

    ttk.Button(btns, text="Add class", command=_add).pack(side="left")
    ttk.Button(btns, text="Edit", command=_edit).pack(side="left", padx=(8, 0))
    ttk.Button(btns, text="View pupils...", command=_view_pupils).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Toggle active", command=_toggle).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Delete", command=_delete).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Refresh", command=_refresh).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")

    tree.bind("<Double-Button-1>", lambda _e: _edit())
    year_var.trace_add("write", lambda *_: _refresh())
    active_var.trace_add("write", lambda *_: _refresh())

    _refresh()


FORM_FIELDS: list[tuple[str, str]] = [
    ("name", "Name *"),
    ("year_group", "Year group *"),
    ("teacher", "Class teacher"),
    ("room", "Room"),
    ("capacity", "Capacity"),
    ("notes", "Notes"),
]


def _open_form_dialog(parent, *, class_id: int | None,
                      on_saved: Callable[[], None]) -> None:
    existing: SchoolClass | None = None
    if class_id is not None:
        try:
            existing = data.get(class_id)
        except Exception:
            logger.exception("get(%s) failed", class_id)
            messagebox.showerror("Error", "Could not load class — see logs.",
                                 parent=parent)
            return
        if existing is None:
            messagebox.showerror("Classes", f"No class #{class_id}",
                                 parent=parent)
            return

    dlg = tk.Toplevel(parent)
    dlg.title("Class" if existing else "New class")
    dlg.transient(parent)
    dlg.geometry("440x380")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    vars_: dict[str, tk.StringVar] = {}
    for i, (key, label) in enumerate(FORM_FIELDS):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=3)
        v = tk.StringVar()
        if existing is not None:
            val = getattr(existing, key, "")
            if key == "capacity":
                v.set("" if val in (None, "") else str(val))
            else:
                v.set(val or "")
        vars_[key] = v
        if key == "year_group":
            ttk.Combobox(frm, textvariable=v, values=list(YEAR_GROUPS),
                         state="readonly", width=28).grid(
                row=i, column=1, sticky="ew", pady=3)
        else:
            ttk.Entry(frm, textvariable=v, width=30).grid(
                row=i, column=1, sticky="ew", pady=3)
    frm.columnconfigure(1, weight=1)

    active_var = tk.BooleanVar(value=existing.is_active if existing else True)
    ttk.Checkbutton(frm, text="Active", variable=active_var).grid(
        row=len(FORM_FIELDS), column=1, sticky="w", pady=(6, 0))

    def _save() -> None:
        payload = {k: v.get() for k, v in vars_.items()}
        payload["is_active"] = active_var.get()
        try:
            if existing is None:
                rec = data.create(payload)
                logger.info("GUI created class #%d", rec.class_id)
            else:
                data.update(existing.class_id, payload)
        except ValidationError as e:
            messagebox.showerror("Classes", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("save class failed")
            messagebox.showerror("Error", "Could not save — see logs.",
                                 parent=dlg)
            return
        on_saved()
        dlg.destroy()

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=len(FORM_FIELDS) + 1, column=0, columnspan=2,
                 sticky="ew", pady=(12, 0))
    ttk.Button(btn_row, text="Save", command=_save).pack(side="right")
    ttk.Button(btn_row, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))


def _open_pupils_dialog(parent, cls: SchoolClass) -> None:
    try:
        pupils = data.pupils_in_class(cls.name)
    except Exception:
        logger.exception("pupils_in_class(%s) failed", cls.name)
        messagebox.showerror("Error", "Could not load pupils — see logs.",
                             parent=parent)
        return

    dlg = tk.Toplevel(parent)
    dlg.title(f"Pupils in {cls.name}")
    dlg.transient(parent)
    dlg.geometry("520x440")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm,
              text=f"{cls.name} — year {cls.year_group}",
              font=("Segoe UI", 11, "bold")).pack(anchor="w")
    cap_text = (f"Capacity: {cls.capacity}" if cls.capacity is not None
                else "Capacity: not set")
    ttk.Label(frm, text=f"{cap_text}   Enrolled: {len(pupils)}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    if cls.capacity and len(pupils) > cls.capacity:
        ttk.Label(
            frm,
            text=f"WARNING: enrolment exceeds capacity by "
                 f"{len(pupils) - cls.capacity}",
            foreground="#c0392b").pack(anchor="w", pady=(0, 6))

    cols = ("pupil_id", "name", "year")
    tree = ttk.Treeview(frm, columns=cols, show="headings", height=14)
    for col, label, width, anchor in [
        ("pupil_id", "Pupil ID", 90, "w"),
        ("name", "Name", 240, "w"),
        ("year", "Year", 60, "center"),
    ]:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor=anchor)
    tree.pack(fill="both", expand=True, pady=(0, 8))
    for p in pupils:
        tree.insert("", "end", values=(p.pupil_id, p.full_name, p.year_group))

    ttk.Button(frm, text="Close", command=dlg.destroy).pack(anchor="e")
