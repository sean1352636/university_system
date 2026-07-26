"""Tk views for teaching assistants."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.systems.primary.domain.staff.teaching_assistants import (
    teaching_assistants as data,
)
from education_system.systems.primary.domain.staff.teaching_assistants.teaching_assistants import (
    EMPLOYMENT_TYPES, ROLES, ROLE_LABELS, TeachingAssistant,
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
                messagebox.showerror("Teaching Assistants", str(e),
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
def open_teaching_assistants(host) -> None:
    logger.debug("GUI: open_teaching_assistants")

    win = tk.Toplevel(host.root)
    win.title("Teaching Assistants")
    win.transient(host.root)
    win.geometry("1140x600")

    top = ttk.Frame(win, padding=10)
    top.pack(fill="x")
    summary_var = tk.StringVar()
    ttk.Label(top, textvariable=summary_var,
              font=("Segoe UI", 10, "bold")).pack(side="left")

    filt = ttk.Frame(win, padding=(10, 0, 10, 6))
    filt.pack(fill="x")
    ttk.Label(filt, text="Role:").pack(side="left")
    role_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=role_var,
                 values=["All"] + list(ROLES),
                 state="readonly", width=18).pack(side="left", padx=(4, 10))
    active_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(filt, text="Active only",
                    variable=active_var).pack(side="left")
    dbs_only = tk.BooleanVar(value=False)
    ttk.Checkbutton(filt, text="No DBS only",
                    variable=dbs_only).pack(side="left", padx=(8, 0))
    sg_only = tk.BooleanVar(value=False)
    ttk.Checkbutton(filt, text="No safeguarding only",
                    variable=sg_only).pack(side="left", padx=(8, 0))
    ttk.Label(filt, text="Search:").pack(side="left", padx=(10, 0))
    search_var = tk.StringVar()
    ttk.Entry(filt, textvariable=search_var, width=22).pack(
        side="left", padx=(4, 0))

    cols = ("ta_id", "name", "role", "class", "hours",
            "employment", "dbs", "safeguarding", "active")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=15)
    for col, label, width, anchor in [
        ("ta_id", "ID", 50, "center"),
        ("name", "Name", 220, "w"),
        ("role", "Role", 160, "w"),
        ("class", "Assigned class", 140, "w"),
        ("hours", "Hrs/wk", 70, "center"),
        ("employment", "Employment", 120, "w"),
        ("dbs", "DBS", 60, "center"),
        ("safeguarding", "SG", 60, "center"),
        ("active", "Active", 70, "center"),
    ]:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor=anchor)
    tree.tag_configure("nodbs", background="#fdecea")
    tree.tag_configure("inactive", foreground="#888")
    tree.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    btns = ttk.Frame(win, padding=10)
    btns.pack(fill="x")

    def _refresh() -> None:
        try:
            role = None if role_var.get() == "All" else role_var.get()
            rows = data.list_all(
                role=role, active_only=active_var.get(),
                search=search_var.get().strip() or None,
                needs_dbs=True if dbs_only.get() else None,
                needs_safeguarding=True if sg_only.get() else None,
            )
        except ValidationError as e:
            messagebox.showerror("Teaching Assistants", str(e), parent=win)
            return
        except Exception:
            logger.exception("TA refresh failed")
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        for iid in tree.get_children():
            tree.delete(iid)
        for t in rows:
            tags = []
            if t.is_active and not t.dbs_checked:
                tags.append("nodbs")
            if not t.is_active:
                tags.append("inactive")
            hpw = "" if t.hours_per_week is None else f"{t.hours_per_week:g}"
            tree.insert("", "end", iid=str(t.ta_id), values=(
                t.ta_id, t.full_name, t.role,
                t.assigned_class or "", hpw,
                t.employment_type, "yes" if t.dbs_checked else "NO",
                "yes" if t.safeguarding_trained else "no",
                "yes" if t.is_active else "no",
            ), tags=tags)
        try:
            s = data.summary()
        except Exception:
            s = {"total": 0, "active": 0, "needs_dbs": 0,
                 "needs_safeguarding": 0, "total_hours_per_week": 0.0}
        summary_var.set(
            f"Active: {s['active']}/{s['total']}   "
            f"Needs DBS: {s['needs_dbs']}   "
            f"Needs safeguarding: {s['needs_safeguarding']}   "
            f"Total hours/wk: {s['total_hours_per_week']:.1f}   "
            f"Showing: {len(rows)}"
        )

    def _selected_id() -> int | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Teaching Assistants",
                                "Select a TA first.", parent=win)
            return None
        return int(sel[0])

    def _add() -> None:
        _open_form_dialog(win, ta_id=None, on_saved=_refresh)

    def _edit() -> None:
        tid = _selected_id()
        if tid is None:
            return
        _open_form_dialog(win, ta_id=tid, on_saved=_refresh)

    def _toggle() -> None:
        tid = _selected_id()
        if tid is None:
            return
        try:
            data.toggle_active(tid)
        except Exception:
            logger.exception("toggle_active(%s) failed", tid)
            messagebox.showerror("Error", "Could not toggle — see logs.",
                                 parent=win)
            return
        _refresh()

    def _delete() -> None:
        tid = _selected_id()
        if tid is None:
            return
        if not messagebox.askyesno("Delete TA",
                                   f"Delete TA #{tid}? "
                                   f"Consider deactivating instead.",
                                   parent=win):
            return
        try:
            data.delete(tid)
        except Exception:
            logger.exception("delete(%s) failed", tid)
            messagebox.showerror("Error", "Could not delete — see logs.",
                                 parent=win)
            return
        _refresh()

    def _help() -> None:
        msg = "Roles:\n" + "\n".join(
            f"{r}  —  {ROLE_LABELS[r]}" for r in ROLES)
        msg += f"\n\nEmployment types: {', '.join(EMPLOYMENT_TYPES)}"
        msg += ("\n\nRed rows have no DBS check on record. "
                "Greyed-out rows are inactive.")
        messagebox.showinfo("Teaching Assistants", msg, parent=win)

    ttk.Button(btns, text="New TA", command=_add).pack(side="left")
    ttk.Button(btns, text="Edit", command=_edit).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Toggle active", command=_toggle).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Delete", command=_delete).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Help", command=_help).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Refresh", command=_refresh).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")

    tree.bind("<Double-Button-1>", lambda _e: _edit())
    for v in (role_var, active_var, dbs_only, sg_only, search_var):
        v.trace_add("write", lambda *_: _refresh())

    _refresh()


def _open_form_dialog(parent, *, ta_id: int | None,
                      on_saved: Callable[[], None]) -> None:
    existing: TeachingAssistant | None = None
    if ta_id is not None:
        try:
            existing = data.get(ta_id)
        except Exception:
            logger.exception("get(%s) failed", ta_id)
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=parent)
            return
        if existing is None:
            messagebox.showerror("Teaching Assistants",
                                 f"No TA #{ta_id}", parent=parent)
            return

    dlg = tk.Toplevel(parent)
    dlg.title("Teaching Assistant" if existing else "New TA")
    dlg.transient(parent)
    dlg.geometry("540x580")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    def _row(idx: int, label: str, var: tk.Variable, *,
             width: int = 30, choices: list[str] | None = None,
             readonly: bool = False) -> None:
        ttk.Label(frm, text=label).grid(row=idx, column=0, sticky="w", pady=3)
        if choices is not None:
            ttk.Combobox(frm, textvariable=var, values=choices,
                         state="readonly" if readonly else "normal",
                         width=width).grid(
                row=idx, column=1, columnspan=2, sticky="ew", pady=3)
        else:
            ttk.Entry(frm, textvariable=var, width=width).grid(
                row=idx, column=1, columnspan=2, sticky="ew", pady=3)

    fn_var = tk.StringVar(value=existing.first_name if existing else "")
    ln_var = tk.StringVar(value=existing.last_name if existing else "")
    email_var = tk.StringVar(value=existing.email or "" if existing else "")
    phone_var = tk.StringVar(value=existing.phone or "" if existing else "")
    role_var = tk.StringVar(value=existing.role if existing else "TA")
    emp_var = tk.StringVar(
        value=existing.employment_type if existing else "permanent")
    class_var = tk.StringVar(
        value=existing.assigned_class or "" if existing else "")
    hours_var = tk.StringVar(
        value="" if not existing or existing.hours_per_week is None
        else f"{existing.hours_per_week:g}")
    start_var = tk.StringVar(
        value=existing.start_date or "" if existing else "")
    end_var = tk.StringVar(value=existing.end_date or "" if existing else "")
    dbs_var = tk.BooleanVar(value=existing.dbs_checked if existing else False)
    sg_var = tk.BooleanVar(
        value=existing.safeguarding_trained if existing else False)
    active_var = tk.BooleanVar(value=existing.is_active if existing else True)
    notes_var = tk.StringVar(value=existing.notes or "" if existing else "")

    _row(0, "First name *", fn_var)
    _row(1, "Last name *", ln_var)
    _row(2, "Email", email_var)
    _row(3, "Phone", phone_var)
    _row(4, "Role *", role_var, choices=list(ROLES), readonly=True)
    _row(5, "Employment type *", emp_var,
         choices=list(EMPLOYMENT_TYPES), readonly=True)
    _row(6, "Assigned class", class_var)
    _row(7, "Hours per week", hours_var, width=10)
    _row(8, "Start date (YYYY-MM-DD)", start_var, width=14)
    _row(9, "End date (YYYY-MM-DD)", end_var, width=14)

    ttk.Checkbutton(frm, text="DBS checked",
                    variable=dbs_var).grid(
        row=10, column=1, sticky="w", pady=3)
    ttk.Checkbutton(frm, text="Safeguarding trained",
                    variable=sg_var).grid(
        row=11, column=1, sticky="w", pady=3)
    ttk.Checkbutton(frm, text="Active",
                    variable=active_var).grid(
        row=12, column=1, sticky="w", pady=3)

    _row(13, "Notes", notes_var)
    frm.columnconfigure(1, weight=1)
    frm.columnconfigure(2, weight=1)

    def _save() -> None:
        payload = {
            "first_name": fn_var.get(),
            "last_name": ln_var.get(),
            "email": email_var.get(),
            "phone": phone_var.get(),
            "role": role_var.get(),
            "employment_type": emp_var.get(),
            "assigned_class": class_var.get(),
            "hours_per_week": hours_var.get(),
            "start_date": start_var.get(),
            "end_date": end_var.get(),
            "dbs_checked": dbs_var.get(),
            "safeguarding_trained": sg_var.get(),
            "is_active": active_var.get(),
            "notes": notes_var.get(),
        }
        try:
            if existing is None:
                data.create(payload)
            else:
                data.update(existing.ta_id, payload)
        except ValidationError as e:
            messagebox.showerror("Teaching Assistants", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("save TA failed")
            messagebox.showerror("Error", "Could not save — see logs.",
                                 parent=dlg)
            return
        on_saved()
        dlg.destroy()

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=14, column=0, columnspan=3, sticky="ew", pady=(14, 0))
    ttk.Button(btn_row, text="Save", command=_save).pack(side="right")
    ttk.Button(btn_row, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))
