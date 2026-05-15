"""Tk views for pupil-support plans."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.pupil_support import (
    pupil_support as data,
)
from education_system.primarysch_system.modules.domain.pupil_support.pupil_support import (
    PLAN_TYPES, PLAN_STATUSES, PRIORITIES, REVIEW_OUTCOMES,
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
                messagebox.showerror("Pupil Support", str(e),
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


def _plan_dialog(host, title: str,
                  initial: dict[str, Any] | None = None
                  ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("560x680")
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
    ay_var     = tk.StringVar(value=str(initial.get("academic_year")
                                          or ""))
    type_var   = tk.StringVar(value=str(initial.get("plan_type")
                                          or "Academic"))
    title_var  = tk.StringVar(value=str(initial.get("title") or ""))
    coord_var  = tk.StringVar(value=str(initial.get("coordinator")
                                          or ""))
    pri_var    = tk.StringVar(value=str(initial.get("priority")
                                          or "Medium"))
    start_var  = tk.StringVar(value=str(initial.get("start_date")
                                          or ""))
    end_var    = tk.StringVar(value=str(initial.get("end_date") or ""))
    next_var   = tk.StringVar(value=str(initial.get("next_review_date")
                                          or ""))
    status_var = tk.StringVar(value=str(initial.get("status")
                                          or "Draft"))

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:",       ttk.Entry(frm, textvariable=pupil_var,
                                        width=14)),
        ("Academic year:",  ttk.Entry(frm, textvariable=ay_var,
                                        width=10)),
        ("Type:",           ttk.Combobox(frm, textvariable=type_var,
                                          values=list(PLAN_TYPES),
                                          state="readonly", width=18)),
        ("Title:",          ttk.Entry(frm, textvariable=title_var,
                                        width=44)),
        ("Coordinator:",    ttk.Entry(frm, textvariable=coord_var,
                                        width=28)),
        ("Priority:",       ttk.Combobox(frm, textvariable=pri_var,
                                          values=list(PRIORITIES),
                                          state="readonly", width=10)),
        ("Start date:",     ttk.Entry(frm, textvariable=start_var,
                                        width=14)),
        ("End date:",       ttk.Entry(frm, textvariable=end_var,
                                        width=14)),
        ("Next review:",    ttk.Entry(frm, textvariable=next_var,
                                        width=14)),
        ("Status:",         ttk.Combobox(frm, textvariable=status_var,
                                          values=list(PLAN_STATUSES),
                                          state="readonly", width=14)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    text_fields = [("Target:", "target", 3),
                   ("Success criteria:", "success_criteria", 3),
                   ("Outcome:", "outcome", 2),
                   ("Notes:", "notes", 2)]
    text_widgets: dict[str, tk.Text] = {}
    for i, (label, key, lines) in enumerate(text_fields,
                                              start=len(rows)):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="nw",
                                         pady=2)
        t = tk.Text(frm, width=48, height=lines, wrap="word")
        t.insert("1.0", str(initial.get(key) or ""))
        t.grid(row=i, column=1, sticky="ew", pady=2)
        text_widgets[key] = t

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id":         pupil_var.get().strip(),
            "academic_year":    ay_var.get().strip(),
            "plan_type":        type_var.get().strip(),
            "title":            title_var.get().strip(),
            "coordinator":      coord_var.get().strip(),
            "priority":         pri_var.get().strip(),
            "start_date":       start_var.get().strip(),
            "end_date":         end_var.get().strip(),
            "next_review_date": next_var.get().strip(),
            "status":           status_var.get().strip(),
        }
        for k, w in text_widgets.items():
            result[k] = w.get("1.0", "end").strip()
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows) + len(text_fields), column=0,
              columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


def _review_dialog(host, plan_id: int,
                    initial: dict[str, Any] | None = None
                    ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Review — plan #{plan_id}")
    dlg.transient(host.root)
    dlg.geometry("520x500")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    date_var = tk.StringVar(value=str(initial.get("review_date") or ""))
    reviewer_var = tk.StringVar(value=str(initial.get("reviewer")
                                             or ""))
    outcome_var = tk.StringVar(value=str(initial.get("outcome")
                                            or "On track"))
    next_var = tk.StringVar(value=str(initial.get("next_review_date")
                                         or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Date:",    ttk.Entry(frm, textvariable=date_var, width=14)),
        ("Reviewer:", ttk.Entry(frm, textvariable=reviewer_var,
                                  width=24)),
        ("Outcome:", ttk.Combobox(frm, textvariable=outcome_var,
                                    values=list(REVIEW_OUTCOMES),
                                    state="readonly", width=14)),
        ("Next review:", ttk.Entry(frm, textvariable=next_var,
                                     width=14)),
    ]
    for label, widget in rows:
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=14).pack(side="left")
        widget.pack(in_=row, side="left", padx=4)

    text_fields = [("Progress:", "progress", 4),
                   ("Next steps:", "next_steps", 3),
                   ("Notes:", "notes", 2)]
    text_widgets: dict[str, tk.Text] = {}
    for label, key, lines in text_fields:
        ttk.Label(frm, text=label).pack(anchor="w", pady=(8, 0))
        t = tk.Text(frm, width=54, height=lines, wrap="word")
        t.insert("1.0", str(initial.get(key) or ""))
        t.pack(fill="x")
        text_widgets[key] = t

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "plan_id":          plan_id,
            "review_date":      date_var.get().strip(),
            "reviewer":         reviewer_var.get().strip(),
            "outcome":          outcome_var.get().strip(),
            "next_review_date": next_var.get().strip(),
        }
        for k, w in text_widgets.items():
            result[k] = w.get("1.0", "end").strip()
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


_PRIORITY_COLOURS = {
    "Critical": "#ffcccc",
    "High":     "#ffe0b3",
    "Medium":   "#ffffb3",
    "Low":      "#e6f2ff",
}


@_safe_view
def open_pupil_support(host) -> None:
    logger.debug("GUI: open_pupil_support")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Pupil Support",
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
                 values=["", *PLAN_TYPES], state="readonly",
                 width=14).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Priority:").pack(side="left", padx=(0, 4))
    pri_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=pri_var,
                 values=["", *PRIORITIES], state="readonly",
                 width=10).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                 values=["", *PLAN_STATUSES], state="readonly",
                 width=12).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Reviews",
               command=lambda: _open_reviews(host, tree)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Status",
               command=lambda: _status(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Overdue",
               command=lambda: _overdue(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "ay", "pupil", "year", "type", "pri", "status",
            "next", "title")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("ay", "Academic yr", 100),
        ("pupil", "Pupil", 90), ("year", "Yr", 50),
        ("type", "Type", 120), ("pri", "Priority", 90),
        ("status", "Status", 100), ("next", "Next review", 100),
        ("title", "Title", 280),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)
    for pri, colour in _PRIORITY_COLOURS.items():
        tree.tag_configure(f"pri_{pri}", background=colour)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_plans(
                year_group=year_var.get().strip() or None,
                plan_type=type_var.get().strip() or None,
                priority=pri_var.get().strip() or None,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Pupil Support", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("pupil_support refresh failed")
            messagebox.showerror("Pupil Support",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for p in rows:
            tree.insert("", "end", iid=str(p.plan_id), values=(
                p.plan_id, p.academic_year, p.pupil_id,
                p.pupil_year or "-", p.plan_type, p.priority,
                p.status, p.next_review_date or "-", p.title,
            ), tags=(f"pri_{p.priority}",))
        try:
            s = data.cohort_summary()
            summary_var.set(
                f"Plans: {s['total']}    Active: {s['active']}    "
                + "    ".join(f"{k}: {v}"
                                for k, v in s["by_priority"].items()))
        except Exception:
            summary_var.set(f"{len(rows)} plan(s)")
        host.status_var.set(f"Pupil Support: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _open_reviews(host, tree))
    year_var.trace_add("write", lambda *_: _refresh())
    type_var.trace_add("write", lambda *_: _refresh())
    pri_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Pupil Support",
                            "Select a plan first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _plan_dialog(host, "New support plan")
    if not fields:
        return
    p = data.create_plan(fields)
    messagebox.showinfo(
        "Pupil Support",
        f"Created plan #{p.plan_id}: {p.title} ({p.plan_type})",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    pid = _selected_id(tree, host)
    if pid is None:
        return
    existing = data.get_plan(pid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "pupil_id", "academic_year", "plan_type", "title",
        "target", "success_criteria", "coordinator", "priority",
        "start_date", "end_date", "next_review_date", "status",
        "outcome", "notes")}
    fields = _plan_dialog(host, f"Edit plan #{pid}", initial=initial)
    if not fields:
        return
    data.update_plan(pid, fields)
    if on_done:
        on_done()


@_safe_view
def _status(host, tree: ttk.Treeview, *, on_done=None) -> None:
    pid = _selected_id(tree, host)
    if pid is None:
        return
    p = data.get_plan(pid)
    if p is None:
        return
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Status — #{pid}")
    dlg.transient(host.root)
    dlg.geometry("360x200")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=p.title[:40]).pack(anchor="w")
    ttk.Label(frm, text=f"Current: {p.status}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    new_var = tk.StringVar(value=p.status)
    ttk.Combobox(frm, textvariable=new_var,
                 values=list(PLAN_STATUSES),
                 state="readonly").pack(fill="x")
    outcome_var = tk.StringVar(value=p.outcome or "")
    ttk.Label(frm,
              text="Outcome (required for Complete / Closed):").pack(
        anchor="w", pady=(8, 0))
    ttk.Entry(frm, textvariable=outcome_var).pack(fill="x")

    def _save() -> None:
        try:
            data.set_status(pid, new_var.get(),
                             outcome=outcome_var.get().strip() or None)
        except ValidationError as ex:
            messagebox.showerror("Pupil Support", str(ex),
                                 parent=dlg)
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
    pid = _selected_id(tree, host)
    if pid is None:
        return
    existing = data.get_plan(pid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete plan",
            f"Delete plan #{pid} ({existing.title}) and ALL reviews?",
            parent=host.root):
        return
    data.delete_plan(pid)
    if on_done:
        on_done()


@_safe_view
def _overdue(host) -> None:
    rows = data.overdue_reviews()
    dlg = tk.Toplevel(host.root)
    dlg.title("Overdue support plan reviews")
    dlg.transient(host.root)
    dlg.geometry("760x420")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"{len(rows)} Active plan(s) with overdue reviews",
              font=("", 10, "bold")).pack(anchor="w", pady=(0, 8))
    t = ttk.Treeview(frm,
                       columns=("id", "pupil", "year", "type", "title",
                                 "next"),
                       show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("pupil", "Pupil", 100),
        ("year", "Yr", 50), ("type", "Type", 120),
        ("title", "Title", 280), ("next", "Next review", 110),
    ]:
        t.heading(c, text=label)
        t.column(c, width=w, anchor="w")
    t.pack(fill="both", expand=True)
    for r in rows:
        t.insert("", "end", values=(
            r.plan_id, r.pupil_id, r.pupil_year or "-",
            r.plan_type, r.title, r.next_review_date,
        ))
    ttk.Button(frm, text="Close",
               command=dlg.destroy).pack(side="right", pady=(10, 0))


@_safe_view
def _open_reviews(host, tree: ttk.Treeview) -> None:
    pid = _selected_id(tree, host)
    if pid is None:
        return
    rec = data.get_plan(pid)
    if rec is None:
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Reviews — plan #{pid}")
    dlg.transient(host.root)
    dlg.geometry("780x520")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass

    frm = ttk.Frame(dlg, padding=10)
    frm.pack(fill="both", expand=True)
    header_var = tk.StringVar()
    ttk.Label(frm, textvariable=header_var,
              font=("", 10, "bold")).pack(anchor="w")

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 4))
    ttk.Button(bar, text="Add review",
               command=lambda: _do_add()).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete selected",
               command=lambda: _do_delete()).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    t = ttk.Treeview(frm,
                       columns=("id", "date", "reviewer", "outcome",
                                 "next", "progress"),
                       show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("date", "Date", 100),
        ("reviewer", "Reviewer", 140), ("outcome", "Outcome", 110),
        ("next", "Next review", 100),
        ("progress", "Progress", 280),
    ]:
        t.heading(c, text=label)
        t.column(c, width=w, anchor="w")
    t.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in t.get_children():
            t.delete(i)
        try:
            s = data.plan_summary(pid)
        except Exception as e:
            logger.exception("plan_summary failed")
            messagebox.showerror("Pupil Support",
                                 f"Could not load:\n\n{e}",
                                 parent=dlg)
            return
        p = s["plan"]
        header_var.set(
            f"#{p.plan_id} {p.title} ({p.plan_type}, "
            f"{p.priority})    "
            f"Pupil {p.pupil_id} — Yr {p.pupil_year or '-'}    "
            f"Reviews: {s['review_count']}    "
            f"Last: {s['last_review'] or '-'}")
        for r in s["reviews"]:
            t.insert("", "end", iid=str(r.review_id), values=(
                r.review_id, r.review_date, r.reviewer or "-",
                r.outcome, r.next_review_date or "-",
                (r.progress or "-")[:100],
            ))

    def _do_add() -> None:
        fields = _review_dialog(host, pid)
        if not fields:
            return
        try:
            data.add_review(fields)
        except ValidationError as e:
            messagebox.showerror("Pupil Support", str(e), parent=dlg)
            return
        _refresh()

    def _do_delete() -> None:
        sel = t.focus()
        if not sel:
            messagebox.showinfo("Pupil Support",
                                "Select a review first.",
                                parent=dlg)
            return
        try:
            rid = int(sel)
        except ValueError:
            return
        if not messagebox.askyesno(
                "Delete review",
                f"Delete review #{rid}?", parent=dlg):
            return
        data.delete_review(rid)
        _refresh()

    _refresh()
