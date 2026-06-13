"""Tk views for accessibility arrangements."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.pastoral.accessibility import (
    accessibility as data,
)
from education_system.secondarysch_system.modules.domain.pastoral.accessibility.accessibility import (
    ARRANGEMENT_TYPES, CATEGORIES, STATUSES, EVIDENCE_SOURCES,
)
from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
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
                messagebox.showerror("Accessibility", str(e),
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


def _arrangement_dialog(host, title: str,
                         initial: dict[str, Any] | None = None
                         ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("560x620")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    pupil_var  = tk.StringVar(value=str(initial.get("pupil_id") or ""))
    type_var   = tk.StringVar(value=str(initial.get("arrangement_type")
                                          or "Reasonable adjustment"))
    cat_var    = tk.StringVar(value=str(initial.get("category") or ""))
    exam_var   = tk.BooleanVar(value=bool(initial.get("exam_only")))
    start_var  = tk.StringVar(value=str(initial.get("start_date") or ""))
    end_var    = tk.StringVar(value=str(initial.get("end_date") or ""))
    status_var = tk.StringVar(value=str(initial.get("status")
                                          or "Proposed"))
    src_var    = tk.StringVar(value=str(initial.get("evidence_source")
                                          or ""))
    ref_var    = tk.StringVar(value=str(initial.get("evidence_reference")
                                          or ""))
    approver_var = tk.StringVar(value=str(initial.get("approved_by")
                                             or ""))
    appdate_var = tk.StringVar(value=str(initial.get("approval_date")
                                            or ""))
    review_var  = tk.StringVar(value=str(initial.get("review_date")
                                            or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:",       ttk.Entry(frm, textvariable=pupil_var,
                                        width=14)),
        ("Type:",           ttk.Combobox(frm, textvariable=type_var,
                                          values=list(ARRANGEMENT_TYPES),
                                          state="readonly", width=28)),
        ("Category:",       ttk.Combobox(frm, textvariable=cat_var,
                                          values=list(CATEGORIES),
                                          width=28)),
        ("Exam only:",      ttk.Checkbutton(frm, variable=exam_var)),
        ("Start date:",     ttk.Entry(frm, textvariable=start_var,
                                        width=14)),
        ("End date:",       ttk.Entry(frm, textvariable=end_var,
                                        width=14)),
        ("Status:",         ttk.Combobox(frm, textvariable=status_var,
                                          values=list(STATUSES),
                                          state="readonly", width=14)),
        ("Evidence source:", ttk.Combobox(frm, textvariable=src_var,
                                            values=["",
                                                     *EVIDENCE_SOURCES],
                                            state="readonly", width=28)),
        ("Evidence ref:",   ttk.Entry(frm, textvariable=ref_var,
                                        width=22)),
        ("Approved by:",    ttk.Entry(frm, textvariable=approver_var,
                                        width=24)),
        ("Approval date:",  ttk.Entry(frm, textvariable=appdate_var,
                                        width=14)),
        ("Review date:",    ttk.Entry(frm, textvariable=review_var,
                                        width=14)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Description:").grid(row=len(rows), column=0,
                                              sticky="nw", pady=2)
    desc_w = tk.Text(frm, width=48, height=4, wrap="word")
    desc_w.insert("1.0", str(initial.get("description") or ""))
    desc_w.grid(row=len(rows), column=1, sticky="ew", pady=2)

    ttk.Label(frm, text="Notes:").grid(row=len(rows) + 1, column=0,
                                        sticky="nw", pady=2)
    notes_w = tk.Text(frm, width=48, height=3, wrap="word")
    notes_w.insert("1.0", str(initial.get("notes") or ""))
    notes_w.grid(row=len(rows) + 1, column=1, sticky="ew", pady=2)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id":           pupil_var.get().strip(),
            "arrangement_type":   type_var.get().strip(),
            "category":           cat_var.get().strip(),
            "exam_only":          bool(exam_var.get()),
            "start_date":         start_var.get().strip(),
            "end_date":           end_var.get().strip(),
            "status":             status_var.get().strip(),
            "evidence_source":    src_var.get().strip(),
            "evidence_reference": ref_var.get().strip(),
            "approved_by":        approver_var.get().strip(),
            "approval_date":      appdate_var.get().strip(),
            "review_date":        review_var.get().strip(),
            "description":        desc_w.get("1.0", "end").strip(),
            "notes":              notes_w.get("1.0", "end").strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows) + 2, column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_accessibility(host) -> None:
    logger.debug("GUI: open_accessibility")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Accessibility",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var, foreground="#666").pack(
        anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
    year_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=year_var,
                 values=["", *YEAR_GROUPS], state="readonly",
                 width=5).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Type:").pack(side="left", padx=(0, 4))
    type_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=type_var,
                 values=["", *ARRANGEMENT_TYPES], state="readonly",
                 width=22).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                 values=["", *STATUSES], state="readonly",
                 width=12).pack(side="left", padx=(0, 6))
    exam_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(bar, text="Exam only",
                    variable=exam_var,
                    command=lambda: _refresh()).pack(side="left",
                                                     padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Status",
               command=lambda: _status(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Expired",
               command=lambda: _expired(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "start", "pupil", "year", "type", "category",
            "exam", "status", "approved")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("start", "Start", 90),
        ("pupil", "Pupil", 90), ("year", "Yr", 50),
        ("type", "Type", 180), ("category", "Category", 180),
        ("exam", "Exam", 60), ("status", "Status", 100),
        ("approved", "Approved by", 140),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    tree.tag_configure("expired", background="#fde7e7")

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_arrangements(
                year_group=year_var.get().strip() or None,
                arrangement_type=type_var.get().strip() or None,
                status=status_var.get().strip() or None,
                exam_only=(True if exam_var.get() else None),
            )
        except ValidationError as e:
            messagebox.showerror("Accessibility", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("accessibility refresh failed")
            messagebox.showerror("Accessibility",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for a in rows:
            tags = ("expired",) if a.expired else ()
            tree.insert("", "end", iid=str(a.arrangement_id), values=(
                a.arrangement_id, a.start_date, a.pupil_id,
                a.pupil_year or "-", a.arrangement_type,
                a.category,
                "Yes" if a.exam_only else "No",
                a.status, a.approved_by or "-",
            ), tags=tags)
        try:
            s = data.cohort_summary(
                year_group=year_var.get().strip() or None)
            summary_var.set(
                f"Total: {s['total']}    "
                f"Active: {s['active']}    "
                f"Exam-only: {s['exam_only']}    "
                f"Expired (Active): {s['expired_active']}")
        except Exception:
            summary_var.set(f"{len(rows)} record(s)")
        host.status_var.set(f"Accessibility: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _edit(host, tree,
                                              on_done=_refresh))
    year_var.trace_add("write", lambda *_: _refresh())
    type_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Accessibility",
                            "Select an arrangement first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _arrangement_dialog(host, "New arrangement")
    if not fields:
        return
    a = data.create(fields)
    messagebox.showinfo(
        "Accessibility",
        f"Created arrangement #{a.arrangement_id} for {a.pupil_id}: "
        f"{a.category}",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_id(tree, host)
    if aid is None:
        return
    existing = data.get(aid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "pupil_id", "arrangement_type", "category", "description",
        "exam_only", "start_date", "end_date", "status",
        "evidence_source", "evidence_reference", "approved_by",
        "approval_date", "review_date", "notes")}
    fields = _arrangement_dialog(host, f"Edit arrangement #{aid}",
                                    initial=initial)
    if not fields:
        return
    data.update(aid, fields)
    if on_done:
        on_done()


@_safe_view
def _status(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_id(tree, host)
    if aid is None:
        return
    a = data.get(aid)
    if a is None:
        return
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Status — #{aid}")
    dlg.transient(host.root)
    dlg.geometry("340x140")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=f"{a.pupil_id} — {a.category}").pack(
        anchor="w")
    ttk.Label(frm, text=f"Current: {a.status}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    new_var = tk.StringVar(value=a.status)
    ttk.Combobox(frm, textvariable=new_var,
                 values=list(STATUSES),
                 state="readonly").pack(fill="x")

    def _save() -> None:
        try:
            data.set_status(aid, new_var.get())
        except ValidationError as ex:
            messagebox.showerror("Accessibility", str(ex), parent=dlg)
            return
        dlg.destroy()
        if on_done:
            on_done()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_id(tree, host)
    if aid is None:
        return
    existing = data.get(aid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete arrangement",
            f"Delete arrangement #{aid} ({existing.pupil_id}, "
            f"{existing.category})?",
            parent=host.root):
        return
    data.delete(aid)
    if on_done:
        on_done()


@_safe_view
def _expired(host) -> None:
    rows = data.expired_arrangements()
    dlg = tk.Toplevel(host.root)
    dlg.title("Expired (Active but past end-date)")
    dlg.transient(host.root)
    dlg.geometry("700x400")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"{len(rows)} expired Active arrangement(s)",
              font=("", 10, "bold")).pack(anchor="w", pady=(0, 8))
    t = ttk.Treeview(frm,
                       columns=("id", "pupil", "category", "end",
                                 "approver"),
                       show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("pupil", "Pupil", 100),
        ("category", "Category", 220), ("end", "End", 100),
        ("approver", "Approved by", 160),
    ]:
        t.heading(c, text=label)
        t.column(c, width=w, anchor="w")
    t.pack(fill="both", expand=True)
    for r in rows:
        t.insert("", "end", values=(
            r.arrangement_id, r.pupil_id, r.category,
            r.end_date or "-", r.approved_by or "-",
        ))
    ttk.Button(frm, text="Close",
               command=dlg.destroy).pack(side="right", pady=(10, 0))
