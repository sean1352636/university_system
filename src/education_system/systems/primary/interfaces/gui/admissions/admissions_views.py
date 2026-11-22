"""Tk views for admissions in the Primary School System."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.primary.domain.admissions import (
    admissions as data,
)
from education_system.systems.primary.domain.admissions.admissions import (
    STATUSES,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
)
from education_system.systems.primary.interfaces.gui import kit

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        try:
            return func(host, *args, **kwargs)
        except ValidationError as e:
            logger.warning("%s validation: %s", func.__name__, e)
            try:
                messagebox.showerror("Admissions", str(e),
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


_FIELDS = [
    ("applicant_first", "First name"),
    ("applicant_last",  "Last name"),
    ("date_of_birth",   "Date of birth"),
    ("year_applying",   "Year applying"),
    ("parent_name",     "Parent name"),
    ("parent_phone",    "Parent phone"),
    ("parent_email",    "Parent email"),
    ("notes",           "Notes"),
]


def _owner(host, widget: tk.Misc | None = None) -> tk.Misc:
    """The window messages and pop-ups belong to: the page's own window
    (main window or pop-out) when known, otherwise the main window."""
    if widget is not None:
        try:
            return widget.winfo_toplevel()
        except tk.TclError:
            pass
    return getattr(host, "root", host)


def _form_dialog(host, title: str, initial: dict[str, Any] | None = None,
                 *, owner: tk.Misc | None = None) -> dict[str, str] | None:
    parent_win = _owner(host, owner)
    dlg = tk.Toplevel(parent_win)
    dlg.title(title)
    dlg.transient(parent_win)
    dlg.geometry("560x460")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    frm, footer = kit.scrolled_form(dlg)
    initial = initial or {}
    vars_: dict[str, tk.Variable] = {}

    for i, (key, label) in enumerate(_FIELDS):
        ttk.Label(frm, text=f"{label}:").grid(row=i, column=0, sticky="w",
                                               pady=2)
        if key == "year_applying":
            v = tk.StringVar(value=str(initial.get(key) or YEAR_GROUPS[0]))
            kit.YearGroupPicker(frm, v).grid(row=i, column=1, sticky="w", pady=2)
        elif key == "date_of_birth":
            v = tk.StringVar(value=str(initial.get(key) or ""))
            kit.DateField(frm, v, years=kit.pupil_birth_years(), today=False).grid(
                row=i, column=1, sticky="w", pady=2)
        else:
            v = tk.StringVar(value=str(initial.get(key) or ""))
            ttk.Entry(frm, textvariable=v, width=34).grid(
                row=i, column=1, sticky="ew", pady=2)
        vars_[key] = v
    frm.columnconfigure(1, weight=1)

    result: dict[str, str] | None = None

    def _save() -> None:
        nonlocal result
        result = {k: (v.get() or "").strip() for k, v in vars_.items()}
        dlg.destroy()

    ttk.Button(footer, text="Cancel", command=dlg.destroy).pack(side="right",
                                                                 padx=4)
    ttk.Button(footer, text="Save", command=_save).pack(side="right")

    dlg.wait_window()
    return result


@_safe_view
def open_admissions(host) -> None:
    logger.debug("GUI: open_admissions")
    kit.show_page(host, "Admissions", lambda parent: _draw_admissions(parent, host))


def _draw_admissions(root: ttk.Frame, host) -> None:
    kit.page_heading(root, "Admissions", "Applications for a place, from first contact to enrolment.")

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var, foreground="#666").pack(
        anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Filter status:").pack(side="left", padx=(0, 6))
    filter_var = tk.StringVar(value="")
    kit.ChoiceField(bar, filter_var, choices=STATUSES, blank=True, width=12).pack(
        side="left", padx=(0, 8))
    ttk.Button(bar, text="New",
               command=lambda: _new(host, on_done=_refresh, owner=root)).pack(side="left",
                                                                              padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Set Status",
               command=lambda: _status_selected(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Enrol",
               command=lambda: _enrol_selected(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "date", "year", "name", "status", "parent", "pupil")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "Application ID", 110), ("date", "Date", 90),
        ("year", "Year", 50), ("name", "Applicant", 180),
        ("status", "Status", 90), ("parent", "Parent", 160),
        ("pupil", "Pupil ID", 100),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    detail = ttk.LabelFrame(root, text="Selected application", padding=8)
    detail.pack(fill="x", pady=(8, 0))
    detail_var = tk.StringVar(value="(select a row to see details)")
    ttk.Label(detail, textvariable=detail_var, justify="left").pack(
        anchor="w")

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            f = filter_var.get().strip() or None
            rows = data.list_applications(status=f)
        except Exception as e:
            logger.exception("admissions refresh failed")
            messagebox.showerror("Admissions",
                                 f"Could not load applications:\n\n{e}",
                                 parent=root.winfo_toplevel())
            return
        for a in rows:
            tree.insert("", "end", iid=a.application_id, values=(
                a.application_id, a.application_date or "-",
                a.year_applying, a.applicant_name,
                a.status, a.parent_name or "-", a.pupil_id or "-",
            ))
        try:
            counts = data.status_counts()
            total = sum(counts.values())
            summary_var.set(
                f"Total: {total}    " +
                "    ".join(f"{s}: {counts[s]}" for s in STATUSES))
        except Exception:
            logger.exception("admissions status_counts failed")
            summary_var.set("(counts unavailable)")
        detail_var.set("(select a row to see details)")
        if getattr(host, "status_var", None) is not None:
            host.status_var.set(f"Admissions: {len(rows)} record(s)")

    def _on_select(_e=None) -> None:
        sel = tree.focus()
        if not sel:
            return
        try:
            a = data.get_application(sel)
        except Exception:
            logger.exception("admissions detail lookup failed")
            detail_var.set("(lookup failed — see logs)")
            return
        if a is None:
            detail_var.set("(application not found)")
            return
        detail_var.set(
            f"Applicant: {a.applicant_name}    DOB: {a.date_of_birth or '-'}\n"
            f"Year applying: {a.year_applying}    Status: {a.status}    "
            f"Pupil: {a.pupil_id or '-'}\n"
            f"Parent: {a.parent_name or '-'}   "
            f"Phone: {a.parent_phone or '-'}   "
            f"Email: {a.parent_email or '-'}\n"
            f"Notes: {a.notes or '-'}"
        )

    tree.bind("<<TreeviewSelect>>", _on_select)
    tree.bind("<Double-1>", lambda _e: _edit_selected(host, tree,
                                                       on_done=_refresh))
    filter_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Admissions",
                            "Select an application first.",
                            parent=_owner(host, tree))
        return None
    return sel


@_safe_view
def _new(host, *, on_done=None, owner: tk.Misc | None = None) -> None:
    fields = _form_dialog(host, "New application", owner=owner)
    if not fields:
        return
    a = data.create_application(fields)
    messagebox.showinfo(
        "Admissions",
        f"Created application {a.application_id}\nFor {a.applicant_name} "
        f"(year {a.year_applying})",
        parent=_owner(host, owner),
    )
    if on_done:
        on_done()


@_safe_view
def _edit_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_id(tree, host)
    if not aid:
        return
    a = data.get_application(aid)
    if a is None:
        messagebox.showerror("Admissions", f"No application with id {aid}",
                             parent=_owner(host, tree))
        return
    initial = {k: getattr(a, k) for k, _ in _FIELDS}
    fields = _form_dialog(host, f"Edit {a.application_id}", initial=initial,
                          owner=tree)
    if not fields:
        return
    data.update_application(aid, fields)
    if on_done:
        on_done()


@_safe_view
def _status_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_id(tree, host)
    if not aid:
        return
    a = data.get_application(aid)
    if a is None:
        return

    owner = _owner(host, tree)
    dlg = tk.Toplevel(owner)
    dlg.title(f"Status — {aid}")
    dlg.transient(owner)
    dlg.geometry("320x140")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"Application: {a.applicant_name}").pack(anchor="w")
    ttk.Label(frm, text=f"Current status: {a.status}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    new_var = tk.StringVar(value=a.status)
    kit.ChoiceField(frm, new_var, choices=STATUSES).pack(fill="x")

    def _save() -> None:
        try:
            data.set_status(aid, new_var.get())
        except ValidationError as e:
            messagebox.showerror("Set status", str(e), parent=dlg)
            return
        dlg.destroy()
        if on_done:
            on_done()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right",
                                                               padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")


@_safe_view
def _enrol_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_id(tree, host)
    if not aid:
        return
    a = data.get_application(aid)
    if a is None:
        return
    if a.status != "accepted":
        messagebox.showerror(
            "Enrol",
            f"Only 'accepted' applications can be enrolled "
            f"(currently '{a.status}').",
            parent=_owner(host, tree),
        )
        return
    if not messagebox.askyesno(
            "Enrol applicant",
            f"Create a pupil record for {a.applicant_name} "
            f"(year {a.year_applying})?",
            parent=_owner(host, tree)):
        return
    _app, pupil = data.enrol_application(aid)
    messagebox.showinfo(
        "Enrolled",
        f"{a.applicant_name} is now pupil {pupil.pupil_id}\n"
        f"Email: {pupil.email}",
        parent=_owner(host, tree),
    )
    if on_done:
        on_done()


@_safe_view
def _delete_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_id(tree, host)
    if not aid:
        return
    a = data.get_application(aid)
    if a is None:
        return
    if not messagebox.askyesno(
            "Delete application",
            f"Delete application {aid} ({a.applicant_name})?",
            parent=_owner(host, tree)):
        return
    data.delete_application(aid)
    if on_done:
        on_done()
