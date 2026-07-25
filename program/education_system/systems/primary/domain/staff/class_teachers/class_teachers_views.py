"""Tk views for class teacher assignments."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.systems.primary.domain.staff.class_teachers import (
    class_teachers as data,
)
from education_system.systems.primary.domain.staff.class_teachers.class_teachers import (
    Assignment, ROLES,
)
from education_system.systems.primary.domain.academics.classes import (
    classes as classes_data,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError,
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
                messagebox.showerror("Class Teachers", str(e),
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


def _load_class_choices() -> tuple[list[str], dict[str, int]]:
    """Return (labels, label->class_id) for the readonly combobox."""
    try:
        all_classes = classes_data.list_all()
    except Exception:
        logger.exception("list_all classes failed")
        return [], {}
    labels: list[str] = []
    mapping: dict[str, int] = {}
    for c in all_classes:
        label = f"#{c.class_id}  {c.name}  (year {c.year_group})"
        labels.append(label)
        mapping[label] = c.class_id
    return labels, mapping


@_safe_view
def open_class_teachers(host) -> None:
    logger.debug("GUI: open_class_teachers")

    win = tk.Toplevel(host.root)
    win.title("Class Teachers")
    win.transient(host.root)
    win.geometry("1080x600")

    top = ttk.Frame(win, padding=10)
    top.pack(fill="x")
    summary_var = tk.StringVar()
    ttk.Label(top, textvariable=summary_var,
              font=("Segoe UI", 10, "bold")).pack(side="left")

    filt = ttk.Frame(win, padding=(10, 0, 10, 6))
    filt.pack(fill="x")
    ttk.Label(filt, text="Year:").pack(side="left")
    year_var = tk.StringVar(value="All")
    year_box = ttk.Combobox(filt, textvariable=year_var,
                            values=["All"], state="readonly", width=10)
    year_box.pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Role:").pack(side="left")
    role_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=role_var,
                 values=["All"] + list(ROLES),
                 state="readonly", width=16).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Staff contains:").pack(side="left")
    staff_var = tk.StringVar()
    ttk.Entry(filt, textvariable=staff_var, width=18).pack(
        side="left", padx=(4, 10))

    cols = ("assignment_id", "class_name", "year", "academic_year",
            "role", "staff_name", "primary", "start", "end")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=15)
    for col, label, width, anchor in [
        ("assignment_id", "#", 50, "center"),
        ("class_name", "Class", 180, "w"),
        ("year", "Yr", 40, "center"),
        ("academic_year", "AcYr", 80, "center"),
        ("role", "Role", 140, "w"),
        ("staff_name", "Staff", 200, "w"),
        ("primary", "P", 40, "center"),
        ("start", "Start", 90, "center"),
        ("end", "End", 90, "center"),
    ]:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor=anchor)
    tree.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    btns = ttk.Frame(win, padding=10)
    btns.pack(fill="x")

    def _refresh() -> None:
        try:
            ay = None if year_var.get() == "All" else year_var.get()
            role = None if role_var.get() == "All" else role_var.get()
            staff = staff_var.get().strip() or None
            rows = data.list_assignments(academic_year=ay, role=role,
                                         staff_name=staff)
        except ValidationError as e:
            messagebox.showerror("Class Teachers", str(e), parent=win)
            return
        except Exception:
            logger.exception("class_teachers refresh failed")
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        for iid in tree.get_children():
            tree.delete(iid)
        for a, cls in rows:
            tree.insert("", "end", iid=str(a.assignment_id), values=(
                a.assignment_id,
                cls.name if cls else f"#{a.class_id}",
                cls.year_group if cls else "-",
                a.academic_year, a.role, a.staff_name,
                "*" if a.is_primary else "",
                a.start_date or "", a.end_date or "",
            ))
        try:
            year_box["values"] = ["All"] + data.known_years()
            c = data.counts(academic_year=ay)
        except Exception:
            c = {"total": 0, "primary": 0, "staff": 0}
        summary_var.set(
            f"Assignments: {c['total']}   "
            f"Primary class teachers: {c['primary']}   "
            f"Distinct staff: {c['staff']}"
        )

    def _selected_id() -> int | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Class Teachers",
                                "Select an assignment first.", parent=win)
            return None
        return int(sel[0])

    def _add() -> None:
        _open_form_dialog(win, assignment_id=None, on_saved=_refresh)

    def _edit() -> None:
        aid = _selected_id()
        if aid is None:
            return
        _open_form_dialog(win, assignment_id=aid, on_saved=_refresh)

    def _make_primary() -> None:
        aid = _selected_id()
        if aid is None:
            return
        try:
            data.set_primary(aid)
        except ValidationError as e:
            messagebox.showerror("Class Teachers", str(e), parent=win)
            return
        except Exception:
            logger.exception("set_primary(%s) failed", aid)
            messagebox.showerror("Error", "Could not update — see logs.",
                                 parent=win)
            return
        _refresh()

    def _delete() -> None:
        aid = _selected_id()
        if aid is None:
            return
        if not messagebox.askyesno("Delete assignment",
                                   f"Delete assignment #{aid}?", parent=win):
            return
        try:
            data.delete(aid)
        except Exception:
            logger.exception("delete(%s) failed", aid)
            messagebox.showerror("Error", "Could not delete — see logs.",
                                 parent=win)
            return
        _refresh()

    ttk.Button(btns, text="New assignment", command=_add).pack(side="left")
    ttk.Button(btns, text="Edit", command=_edit).pack(side="left", padx=(8, 0))
    ttk.Button(btns, text="Make primary", command=_make_primary).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Delete", command=_delete).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Refresh", command=_refresh).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")

    tree.bind("<Double-Button-1>", lambda _e: _edit())
    for v in (year_var, role_var, staff_var):
        v.trace_add("write", lambda *_: _refresh())

    _refresh()


def _open_form_dialog(parent, *, assignment_id: int | None,
                      on_saved: Callable[[], None]) -> None:
    existing: Assignment | None = None
    if assignment_id is not None:
        try:
            existing = data.get(assignment_id)
        except Exception:
            logger.exception("get(%s) failed", assignment_id)
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=parent)
            return
        if existing is None:
            messagebox.showerror("Class Teachers",
                                 f"No assignment #{assignment_id}",
                                 parent=parent)
            return

    dlg = tk.Toplevel(parent)
    dlg.title("Assignment" if existing else "New assignment")
    dlg.transient(parent)
    dlg.geometry("500x460")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    labels, mapping = _load_class_choices()
    initial_label = ""
    if existing is not None:
        for lbl, cid in mapping.items():
            if cid == existing.class_id:
                initial_label = lbl
                break

    ttk.Label(frm, text="Class *").grid(row=0, column=0, sticky="w", pady=3)
    class_var = tk.StringVar(value=initial_label)
    class_box = ttk.Combobox(frm, textvariable=class_var, values=labels,
                             state="readonly", width=42)
    class_box.grid(row=0, column=1, columnspan=2, sticky="ew", pady=3)

    ttk.Label(frm, text="Staff name *").grid(row=1, column=0, sticky="w", pady=3)
    name_var = tk.StringVar(value=existing.staff_name if existing else "")
    ttk.Entry(frm, textvariable=name_var, width=30).grid(
        row=1, column=1, columnspan=2, sticky="ew", pady=3)

    ttk.Label(frm, text="Staff ID (optional)").grid(
        row=2, column=0, sticky="w", pady=3)
    staff_id_var = tk.StringVar(value=existing.staff_id or "" if existing else "")
    ttk.Entry(frm, textvariable=staff_id_var, width=20).grid(
        row=2, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Academic year *").grid(
        row=3, column=0, sticky="w", pady=3)
    ay_var = tk.StringVar(value=existing.academic_year if existing else "")
    ttk.Entry(frm, textvariable=ay_var, width=14).grid(
        row=3, column=1, sticky="w", pady=3)
    ttk.Label(frm, text="e.g. 2025-26", foreground="#888").grid(
        row=3, column=2, sticky="w", padx=(8, 0))

    ttk.Label(frm, text="Role *").grid(row=4, column=0, sticky="w", pady=3)
    role_var = tk.StringVar(
        value=existing.role if existing else ROLES[0])
    ttk.Combobox(frm, textvariable=role_var, values=list(ROLES),
                 state="readonly", width=22).grid(
        row=4, column=1, sticky="w", pady=3)

    primary_var = tk.BooleanVar(value=existing.is_primary if existing else False)
    ttk.Checkbutton(frm, text="Primary class teacher (one per class/year)",
                    variable=primary_var).grid(
        row=5, column=1, columnspan=2, sticky="w", pady=3)

    ttk.Label(frm, text="Start date (YYYY-MM-DD)").grid(
        row=6, column=0, sticky="w", pady=3)
    start_var = tk.StringVar(value=existing.start_date or "" if existing else "")
    ttk.Entry(frm, textvariable=start_var, width=14).grid(
        row=6, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="End date (YYYY-MM-DD)").grid(
        row=7, column=0, sticky="w", pady=3)
    end_var = tk.StringVar(value=existing.end_date or "" if existing else "")
    ttk.Entry(frm, textvariable=end_var, width=14).grid(
        row=7, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Notes").grid(row=8, column=0, sticky="w", pady=3)
    notes_var = tk.StringVar(value=existing.notes or "" if existing else "")
    ttk.Entry(frm, textvariable=notes_var, width=42).grid(
        row=8, column=1, columnspan=2, sticky="ew", pady=3)
    frm.columnconfigure(1, weight=1)
    frm.columnconfigure(2, weight=1)

    def _save() -> None:
        chosen = class_var.get()
        if chosen not in mapping:
            messagebox.showerror("Class Teachers",
                                 "Please choose a class.", parent=dlg)
            return
        payload = {
            "class_id": mapping[chosen],
            "staff_name": name_var.get(),
            "staff_id": staff_id_var.get(),
            "academic_year": ay_var.get(),
            "role": role_var.get(),
            "is_primary": primary_var.get(),
            "start_date": start_var.get(),
            "end_date": end_var.get(),
            "notes": notes_var.get(),
        }
        try:
            if existing is None:
                data.create(payload)
            else:
                data.update(existing.assignment_id, payload)
        except ValidationError as e:
            messagebox.showerror("Class Teachers", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("save class teacher failed")
            messagebox.showerror("Error", "Could not save — see logs.",
                                 parent=dlg)
            return
        on_saved()
        dlg.destroy()

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(14, 0))
    ttk.Button(btn_row, text="Save", command=_save).pack(side="right")
    ttk.Button(btn_row, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))
