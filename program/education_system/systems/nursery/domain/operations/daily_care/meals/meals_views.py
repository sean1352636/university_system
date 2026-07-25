"""Tkinter views for Meals & Menus (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``). Lists the per-child meal log with a tree + toolbar and an add/edit
form dialog — the GUI counterpart of ``meals_cli.py``. Rows where the meal was
not safe against the child's allergies are highlighted red.
"""

from __future__ import annotations

import datetime as _dt
import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.nursery.domain.operations.daily_care.meals import meals as data
from education_system.systems.nursery.domain.operations.daily_care.meals.meals import (
    AMOUNTS,
    MEAL_TYPES,
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
    logger.debug("GUI: meals open_manager")
    root = _clear(host)
    _header(root, "Meals & Menus")

    date_var = tk.StringVar()
    filt = ttk.Frame(root)
    filt.pack(fill="x", pady=(0, 6))
    ttk.Label(filt, text="Date (YYYY-MM-DD):").pack(side="left")
    ttk.Entry(filt, textvariable=date_var, width=14).pack(side="left", padx=(4, 4))
    ttk.Button(filt, text="Load",
               command=lambda: _refresh(tree, date_var.get())).pack(side="left")
    ttk.Button(filt, text="Clear",
               command=lambda: (date_var.set(""), _refresh(tree, ""))).pack(
        side="left", padx=4)

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 8))
    ttk.Button(bar, text="Add Record",
               command=lambda: open_add(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(tree, host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh(tree, date_var.get())).pack(
        side="left", padx=2)

    cols = ("date", "child", "meal", "menu", "eaten", "safe")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=17)
    for c, label, w in [
        ("date", "Date", 100), ("child", "Child", 180), ("meal", "Meal", 130),
        ("menu", "Menu", 200), ("eaten", "Eaten", 80), ("safe", "Allergy-safe", 100),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.tag_configure("unsafe", foreground="#b00020")
    tree.pack(fill="both", expand=True)
    tree.bind("<Double-1>", lambda _e: _edit_selected(tree, host))

    _refresh(tree, "")
    host.status_var.set("Meals & menus loaded")


def _refresh(tree: ttk.Treeview, meal_date: str) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rows = data.list_records(meal_date=(meal_date or "").strip() or None)
    except Exception:
        logger.exception("Could not refresh meals")
        try:
            messagebox.showerror("Meals & menus", "Could not load — see logs.")
        except Exception:
            logger.debug("Could not show refresh-error dialog", exc_info=True)
        return
    for r in rows:
        tags = () if r.allergy_safe else ("unsafe",)
        tree.insert("", "end", iid=r.meal_id, tags=tags, values=(
            r.meal_date, r.child_name or "-", r.meal_type, r.menu or "-",
            r.amount_eaten or "-", "Yes" if r.allergy_safe else "NO"))


def _selected(tree: ttk.Treeview, host, verb: str) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Meals & menus", f"Select a record to {verb}.",
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
            f"Delete meal record {sel} for {r.child_name}?",
            parent=host.root):
        return
    try:
        data.delete_record(sel)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to delete meal %s", sel)
        messagebox.showerror("Delete record", f"Could not delete:\n\n{e}",
                             parent=host.root)
        return
    open_manager(host)
    host.status_var.set(f"Deleted meal record {sel}")


# ── Form dialog ──────────────────────────────────────────────────────────────

def _form_dialog(host, title: str, *, initial: dict[str, Any] | None = None,
                 is_edit: bool = False,
                 pupil_choices: list[tuple[str, str]] | None = None,
                 staff_choices: list[tuple[str, str]] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("470x500")
    try:
        dlg.wait_visibility(); dlg.grab_set()
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
        pchoices = pupil_choices or []
        pid_id_by_label = {lbl: sid for sid, lbl in pchoices}
        pvar = tk.StringVar()
        ttk.Combobox(frm, textvariable=pvar,
                     values=[lbl for _i, lbl in pchoices],
                     state="readonly" if pchoices else "normal", width=34).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_["__pupil_label"] = pvar
        row += 1

    def label_entry(key: str, label: str) -> None:
        nonlocal row
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=2)
        v = tk.StringVar(value="" if initial.get(key) is None else str(initial[key]))
        ttk.Entry(frm, textvariable=v, width=34).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1

    def label_combo(key: str, label: str, options: tuple[str, ...],
                    default: str = "") -> None:
        nonlocal row
        ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="nw", pady=2)
        v = tk.StringVar(value=str(initial.get(key) or default))
        ttk.Combobox(frm, textvariable=v, values=list(options),
                     state="readonly", width=32).grid(
            row=row, column=1, sticky="ew", pady=2)
        vars_[key] = v
        row += 1

    md = initial.get("meal_date") or _dt.date.today().isoformat()
    ttk.Label(frm, text="Meal date (YYYY-MM-DD):").grid(
        row=row, column=0, sticky="nw", pady=2)
    mdv = tk.StringVar(value=str(md))
    ttk.Entry(frm, textvariable=mdv, width=34).grid(
        row=row, column=1, sticky="ew", pady=2)
    vars_["meal_date"] = mdv
    row += 1

    label_combo("meal_type", "Meal type", MEAL_TYPES, "Lunch")
    label_entry("menu", "Menu")
    label_combo("amount_eaten", "Amount eaten", AMOUNTS)
    label_entry("drink", "Drink")

    safe_default = 1 if "allergy_safe" not in initial else int(
        bool(initial.get("allergy_safe")))
    safe_var = tk.BooleanVar(value=bool(safe_default))
    ttk.Checkbutton(frm, text="Allergy-safe", variable=safe_var).grid(
        row=row, column=0, columnspan=2, sticky="w", pady=2)
    vars_["allergy_safe"] = safe_var
    row += 1

    # Staff picker.
    ttk.Label(frm, text="Recorded by:").grid(row=row, column=0, sticky="nw", pady=2)
    schoices = staff_choices or []
    sid_by_label = {lbl: sid for sid, lbl in schoices}
    cur_sid = initial.get("staff_id")
    cur_label = next((lbl for sid, lbl in schoices if sid == cur_sid), "")
    svar = tk.StringVar(value=cur_label)
    ttk.Combobox(frm, textvariable=svar, values=[""] + [lbl for _i, lbl in schoices],
                 state="readonly" if schoices else "normal", width=34).grid(
        row=row, column=1, sticky="ew", pady=2)
    vars_["__staff_label"] = svar
    row += 1

    label_entry("notes", "Notes")
    frm.columnconfigure(1, weight=1)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        out: dict[str, Any] = {}
        for k, v in vars_.items():
            if k == "__pupil_label":
                out["pupil_id"] = pid_id_by_label.get((v.get() or "").strip(), "")
            elif k == "__staff_label":
                out["staff_id"] = sid_by_label.get((v.get() or "").strip(), "")
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
    logger.debug("GUI: meals open_add")
    fields = _form_dialog(host, "Add Meal Record",
                          pupil_choices=_pupil_choices(),
                          staff_choices=_staff_choices())
    if not fields:
        host.status_var.set("Add meal cancelled")
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
        f"{r.child_name} — {r.meal_type} ({r.meal_date})",
        parent=host.root)
    host.status_var.set(f"Added meal {r.meal_id}")
    open_manager(host)


@_safe_view
def open_edit(host, meal_id: str) -> None:
    logger.debug("GUI: meals open_edit(%s)", meal_id)
    r = data.get_record(meal_id)
    if r is None:
        messagebox.showerror("Edit record", f"No record with id {meal_id}",
                             parent=host.root)
        return
    initial = {
        "meal_date": r.meal_date, "meal_type": r.meal_type, "menu": r.menu,
        "amount_eaten": r.amount_eaten, "drink": r.drink,
        "allergy_safe": r.allergy_safe, "staff_id": r.staff_id, "notes": r.notes,
    }
    fields = _form_dialog(host, f"Edit {r.child_name} — meal",
                          initial=initial, is_edit=True,
                          staff_choices=_staff_choices())
    if not fields:
        return
    try:
        data.update_record(meal_id, fields)
    except ValidationError as e:
        messagebox.showerror("Edit record", str(e), parent=host.root)
        return
    host.status_var.set(f"Updated meal {meal_id}")
    open_manager(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Meals & Menus",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open Meals & Menus from the navigation menu."
              ).pack(anchor="w")
    return frame
