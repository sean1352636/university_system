"""Tk views for alumni in the Secondary School System."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.systems.secondary.domain.learners.alumni import (
    alumni as data,
)
from education_system.systems.secondary.domain.learners.alumni.alumni import (
    STATUSES,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
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
                messagebox.showerror("Alumni", str(e),
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
    ("first_name",    "First name"),
    ("last_name",     "Last name"),
    ("date_of_birth", "Date of birth (YYYY-MM-DD)"),
    ("year_left",     "Year left"),
    ("leaving_date",  "Leaving date (YYYY-MM-DD)"),
    ("pupil_id",      "Pupil ID (optional)"),
    ("current_email", "Current email"),
    ("current_phone", "Current phone"),
    ("destination",   "Destination"),
    ("employer",      "Employer"),
    ("status",        "Status"),
    ("notes",         "Notes"),
]


def _form_dialog(host, title: str, initial: dict[str, Any] | None = None
                 ) -> dict[str, str] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("460x520")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    initial = initial or {}
    vars_: dict[str, tk.Variable] = {}

    for i, (key, label) in enumerate(_FIELDS):
        ttk.Label(frm, text=f"{label}:").grid(row=i, column=0, sticky="w",
                                               pady=2)
        if key == "year_left":
            v = tk.StringVar(value=str(initial.get(key) or YEAR_GROUPS[-1]))
            ttk.Combobox(frm, textvariable=v, values=list(YEAR_GROUPS),
                         state="readonly", width=10).grid(
                row=i, column=1, sticky="w", pady=2)
        elif key == "status":
            v = tk.StringVar(value=str(initial.get(key) or "active"))
            ttk.Combobox(frm, textvariable=v, values=list(STATUSES),
                         state="readonly", width=12).grid(
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

    btns = ttk.Frame(frm)
    btns.grid(row=len(_FIELDS), column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right",
                                                               padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")

    dlg.wait_window()
    return result


@_safe_view
def open_alumni(host) -> None:
    logger.debug("GUI: open_alumni")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Alumni", font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var, foreground="#666").pack(
        anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                 values=["", *STATUSES], state="readonly", width=10).pack(
        side="left", padx=(0, 8))
    ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
    year_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=year_var,
                 values=["", *YEAR_GROUPS], state="readonly", width=6).pack(
        side="left", padx=(0, 8))
    ttk.Label(bar, text="Search:").pack(side="left", padx=(0, 4))
    search_var = tk.StringVar(value="")
    ttk.Entry(bar, textvariable=search_var, width=22).pack(side="left",
                                                            padx=(0, 8))
    ttk.Button(bar, text="New",
               command=lambda: _new(host, on_done=_refresh)).pack(side="left",
                                                                   padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Set Status",
               command=lambda: _status_selected(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Promote Pupil",
               command=lambda: _promote(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "left", "year", "name", "status", "pupil",
            "destination", "employer")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "Alumni ID", 110), ("left", "Left", 90),
        ("year", "Yr", 50), ("name", "Name", 180),
        ("status", "Status", 80), ("pupil", "Pupil ID", 90),
        ("destination", "Destination", 180), ("employer", "Employer", 140),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    detail = ttk.LabelFrame(root, text="Selected alumnus", padding=8)
    detail.pack(fill="x", pady=(8, 0))
    detail_var = tk.StringVar(value="(select a row to see details)")
    ttk.Label(detail, textvariable=detail_var, justify="left").pack(
        anchor="w")

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            q = search_var.get().strip()
            if q:
                rows = data.search_alumni(q)
                s = status_var.get().strip() or None
                y = year_var.get().strip() or None
                if s:
                    rows = [r for r in rows if r.status == s]
                if y:
                    rows = [r for r in rows if r.year_left == y]
            else:
                rows = data.list_alumni(
                    status=status_var.get().strip() or None,
                    year_left=year_var.get().strip() or None,
                )
        except ValidationError as e:
            messagebox.showerror("Alumni", str(e), parent=host.root)
            return
        except Exception as e:
            logger.exception("alumni refresh failed")
            messagebox.showerror("Alumni",
                                 f"Could not load alumni:\n\n{e}",
                                 parent=host.root)
            return
        for a in rows:
            tree.insert("", "end", iid=a.alumni_id, values=(
                a.alumni_id, a.leaving_date or "-",
                a.year_left, a.full_name,
                a.status, a.pupil_id or "-",
                a.destination or "-", a.employer or "-",
            ))
        try:
            counts = data.status_counts()
            total = sum(counts.values())
            summary_var.set(
                f"Total: {total}    " +
                "    ".join(f"{s}: {counts[s]}" for s in STATUSES))
        except Exception:
            logger.exception("alumni status_counts failed")
            summary_var.set("(counts unavailable)")
        detail_var.set("(select a row to see details)")
        host.status_var.set(f"Alumni: {len(rows)} record(s)")

    def _on_select(_e=None) -> None:
        sel = tree.focus()
        if not sel:
            return
        try:
            a = data.get_alumnus(sel)
        except Exception:
            logger.exception("alumni detail lookup failed")
            detail_var.set("(lookup failed — see logs)")
            return
        if a is None:
            detail_var.set("(alumnus not found)")
            return
        detail_var.set(
            f"Name: {a.full_name}    DOB: {a.date_of_birth or '-'}\n"
            f"Year left: {a.year_left}    Leaving: {a.leaving_date or '-'}    "
            f"Status: {a.status}    Pupil: {a.pupil_id or '-'}\n"
            f"Email: {a.current_email or '-'}   "
            f"Phone: {a.current_phone or '-'}\n"
            f"Destination: {a.destination or '-'}   "
            f"Employer: {a.employer or '-'}\n"
            f"Notes: {a.notes or '-'}"
        )

    tree.bind("<<TreeviewSelect>>", _on_select)
    tree.bind("<Double-1>", lambda _e: _edit_selected(host, tree,
                                                       on_done=_refresh))
    status_var.trace_add("write", lambda *_: _refresh())
    year_var.trace_add("write", lambda *_: _refresh())
    search_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> str | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Alumni", "Select an alumnus first.",
                            parent=host.root)
        return None
    return sel


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _form_dialog(host, "New alumnus")
    if not fields:
        return
    a = data.create_alumnus(fields)
    messagebox.showinfo(
        "Alumni",
        f"Created alumnus {a.alumni_id}\nFor {a.full_name} "
        f"(year left {a.year_left})",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_id(tree, host)
    if not aid:
        return
    a = data.get_alumnus(aid)
    if a is None:
        messagebox.showerror("Alumni", f"No alumnus with id {aid}",
                             parent=host.root)
        return
    initial = {k: getattr(a, k) for k, _ in _FIELDS}
    fields = _form_dialog(host, f"Edit {a.alumni_id}", initial=initial)
    if not fields:
        return
    data.update_alumnus(aid, fields)
    if on_done:
        on_done()


@_safe_view
def _status_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_id(tree, host)
    if not aid:
        return
    a = data.get_alumnus(aid)
    if a is None:
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Status — {aid}")
    dlg.transient(host.root)
    dlg.geometry("320x140")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"Alumnus: {a.full_name}").pack(anchor="w")
    ttk.Label(frm, text=f"Current status: {a.status}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    new_var = tk.StringVar(value=a.status)
    ttk.Combobox(frm, textvariable=new_var, values=list(STATUSES),
                 state="readonly").pack(fill="x")

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
def _promote(host, *, on_done=None) -> None:
    pid = simpledialog.askstring(
        "Promote pupil",
        "Pupil ID to promote to alumni:",
        parent=host.root,
    )
    if not pid:
        return
    pid = pid.strip()
    if not pid:
        return
    extras_dialog = _form_dialog(
        host,
        f"Promote {pid} — optional extras",
        initial={"first_name": "(from pupil)", "last_name": "(from pupil)"},
    )
    # Drop the placeholder fields and any blanks — promote_from_pupil
    # fills first/last/year_left/etc. from the pupil row.
    extras: dict[str, str] = {}
    if extras_dialog:
        for k, v in extras_dialog.items():
            if k in ("first_name", "last_name") and v.startswith("(from"):
                continue
            if v:
                extras[k] = v
    a = data.promote_from_pupil(pid, extras=extras or None)
    messagebox.showinfo(
        "Promoted",
        f"Pupil {pid} is now alumnus {a.alumni_id}\n"
        f"{a.full_name} (year left {a.year_left})",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _delete_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_id(tree, host)
    if not aid:
        return
    a = data.get_alumnus(aid)
    if a is None:
        return
    if not messagebox.askyesno(
            "Delete alumnus",
            f"Delete alumnus {aid} ({a.full_name})?",
            parent=host.root):
        return
    data.delete_alumnus(aid)
    if on_done:
        on_done()
