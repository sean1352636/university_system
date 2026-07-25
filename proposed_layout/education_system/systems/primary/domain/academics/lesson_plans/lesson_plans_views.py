"""Tk views for lesson plans."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.systems.primary.domain.academics.lesson_plans import (
    lesson_plans as data,
)
from education_system.systems.primary.domain.academics.lesson_plans.lesson_plans import (
    STATUSES, MIN_PERIOD, MAX_PERIOD,
)
from education_system.systems.primary.domain.academics.subjects import (
    subjects as subjects_data,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
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
                messagebox.showerror("Lesson Plans", str(e),
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


def _form_dialog(host, title: str, initial: dict[str, Any] | None = None
                 ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("620x640")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped — dialog not viewable", exc_info=True)

    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    title_var    = tk.StringVar(value=str(initial.get("title") or ""))
    year_var     = tk.StringVar(value=str(initial.get("year_group") or "7"))
    form_var     = tk.StringVar(value=str(initial.get("form_group") or ""))
    date_var     = tk.StringVar(value=str(initial.get("planned_date") or ""))
    period_var   = tk.StringVar(value=str(initial.get("period") or ""))
    duration_var = tk.StringVar(value=str(initial.get("duration_min") or 60))
    teacher_var  = tk.StringVar(value=str(initial.get("teacher") or ""))
    status_var   = tk.StringVar(value=str(initial.get("status") or "Draft"))

    try:
        subjects = subjects_data.list_all(active_only=True)
    except Exception:
        subjects = []
    subject_labels = [f"#{s.subject_id} {s.code} — {s.name}"
                      for s in subjects]
    subject_var = tk.StringVar(value="")
    initial_sid = initial.get("subject_id")
    if initial_sid is not None:
        for s in subjects:
            if s.subject_id == int(initial_sid):
                subject_var.set(f"#{s.subject_id} {s.code} — {s.name}")
                break

    grid_rows: list[tuple[str, tk.Widget]] = [
        ("Title:",    ttk.Entry(frm, textvariable=title_var, width=50)),
        ("Subject:",  ttk.Combobox(frm, textvariable=subject_var,
                                    values=subject_labels,
                                    state="readonly", width=48)),
        ("Year:",     ttk.Combobox(frm, textvariable=year_var,
                                    values=list(YEAR_GROUPS),
                                    state="readonly", width=8)),
        ("Form:",     ttk.Entry(frm, textvariable=form_var, width=14)),
        ("Date:",     ttk.Entry(frm, textvariable=date_var, width=14)),
        ("Period:",   ttk.Spinbox(frm, from_=MIN_PERIOD, to=MAX_PERIOD,
                                   textvariable=period_var, width=6)),
        ("Duration (min):", ttk.Spinbox(frm, from_=5, to=240,
                                         textvariable=duration_var, width=8)),
        ("Teacher:",  ttk.Entry(frm, textvariable=teacher_var, width=30)),
        ("Status:",   ttk.Combobox(frm, textvariable=status_var,
                                    values=list(STATUSES),
                                    state="readonly", width=14)),
    ]
    for i, (label, widget) in enumerate(grid_rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="nw", pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    # Multi-line text fields
    text_fields = [
        ("Objectives:",      "objectives", 3),
        ("Activities:",      "activities", 4),
        ("Resources:",       "resources", 2),
        ("Differentiation:", "differentiation", 2),
        ("Assessment:",      "assessment", 2),
        ("Homework:",        "homework", 2),
        ("Notes:",           "notes", 2),
    ]
    text_widgets: dict[str, tk.Text] = {}
    for i, (label, key, lines) in enumerate(text_fields,
                                              start=len(grid_rows)):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="nw",
                                         pady=2)
        t = tk.Text(frm, width=50, height=lines, wrap="word")
        t.insert("1.0", str(initial.get(key) or ""))
        t.grid(row=i, column=1, sticky="ew", pady=2)
        text_widgets[key] = t

    result: dict[str, Any] | None = None

    def _parse_subject(label: str) -> str:
        label = (label or "").strip()
        if not label.startswith("#"):
            return ""
        return label.split()[0][1:]

    def _save() -> None:
        nonlocal result
        result = {
            "title":        title_var.get().strip(),
            "subject_id":   _parse_subject(subject_var.get()),
            "year_group":   year_var.get().strip(),
            "form_group":   form_var.get().strip(),
            "planned_date": date_var.get().strip(),
            "period":       period_var.get().strip(),
            "duration_min": duration_var.get().strip(),
            "teacher":      teacher_var.get().strip(),
            "status":       status_var.get().strip(),
        }
        for key, w in text_widgets.items():
            result[key] = w.get("1.0", "end").strip()
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(grid_rows) + len(text_fields), column=0,
              columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")

    dlg.wait_window()
    return result


@_safe_view
def open_lesson_plans(host) -> None:
    logger.debug("GUI: open_lesson_plans")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Lesson Plans",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var, foreground="#666").pack(
        anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Year:").pack(side="left", padx=(0, 4))
    year_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=year_var,
                 values=["", *YEAR_GROUPS], state="readonly", width=5).pack(
        side="left", padx=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                 values=["", *STATUSES], state="readonly", width=10).pack(
        side="left", padx=(0, 6))
    ttk.Label(bar, text="Teacher:").pack(side="left", padx=(0, 4))
    teacher_var = tk.StringVar(value="")
    ttk.Entry(bar, textvariable=teacher_var, width=14).pack(side="left",
                                                            padx=(0, 8))
    ttk.Button(bar, text="New",
               command=lambda: _new(host, on_done=_refresh)).pack(side="left",
                                                                   padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_selected(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Set status",
               command=lambda: _status_selected(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_selected(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "date", "period", "year", "form", "subject",
            "title", "teacher", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("date", "Date", 90),
        ("period", "P", 40), ("year", "Yr", 50), ("form", "Form", 60),
        ("subject", "Subject", 90), ("title", "Title", 240),
        ("teacher", "Teacher", 140), ("status", "Status", 90),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    detail = ttk.LabelFrame(root, text="Selected plan", padding=8)
    detail.pack(fill="x", pady=(8, 0))
    detail_var = tk.StringVar(value="(select a row to see details)")
    ttk.Label(detail, textvariable=detail_var, justify="left").pack(
        anchor="w")

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_plans(
                year_group=year_var.get().strip() or None,
                teacher=teacher_var.get().strip() or None,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Lesson Plans", str(e), parent=host.root)
            return
        except Exception as e:
            logger.exception("lesson_plans refresh failed")
            messagebox.showerror("Lesson Plans",
                                 f"Could not load plans:\n\n{e}",
                                 parent=host.root)
            return
        for p in rows:
            tree.insert("", "end", iid=str(p.plan_id), values=(
                p.plan_id, p.planned_date,
                p.period if p.period else "-",
                p.year_group, p.form_group or "-",
                p.subject_code or "?", p.title,
                p.teacher or "-", p.status,
            ))
        try:
            c = data.status_counts()
            total = sum(c.values())
            summary_var.set(
                f"Total: {total}    " +
                "    ".join(f"{s}: {c[s]}" for s in STATUSES))
        except Exception:
            logger.exception("status_counts failed")
            summary_var.set("(counts unavailable)")
        detail_var.set("(select a row to see details)")
        host.status_var.set(f"Lesson Plans: {len(rows)} record(s)")

    def _on_select(_e=None) -> None:
        sel = tree.focus()
        if not sel:
            return
        try:
            p = data.get(int(sel))
        except Exception:
            logger.exception("lesson_plans detail lookup failed")
            return
        if p is None:
            return
        detail_var.set(
            f"{p.title}    Subject: {p.subject_code} ({p.subject_name})\n"
            f"Yr {p.year_group}"
            f"{('/' + p.form_group) if p.form_group else ''}    "
            f"{p.planned_date} P{p.period or '-'} "
            f"({p.duration_min or '?'} min)    "
            f"Teacher: {p.teacher or '-'}    Status: {p.status}\n"
            f"Objectives: {(p.objectives or '-')[:120]}\n"
            f"Activities: {(p.activities or '-')[:120]}"
        )

    tree.bind("<<TreeviewSelect>>", _on_select)
    tree.bind("<Double-1>", lambda _e: _edit_selected(host, tree,
                                                       on_done=_refresh))
    year_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Lesson Plans", "Select a plan first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _form_dialog(host, "New lesson plan")
    if not fields:
        return
    p = data.create(fields)
    messagebox.showinfo("Lesson Plans",
                        f"Created plan #{p.plan_id}: {p.title}",
                        parent=host.root)
    if on_done:
        on_done()


@_safe_view
def _edit_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    plan_id = _selected_id(tree, host)
    if plan_id is None:
        return
    existing = data.get(plan_id)
    if existing is None:
        return
    initial = {
        "title": existing.title,
        "subject_id": existing.subject_id,
        "year_group": existing.year_group,
        "form_group": existing.form_group,
        "planned_date": existing.planned_date,
        "period": existing.period,
        "duration_min": existing.duration_min,
        "teacher": existing.teacher, "status": existing.status,
        "objectives": existing.objectives,
        "activities": existing.activities,
        "resources": existing.resources,
        "differentiation": existing.differentiation,
        "assessment": existing.assessment,
        "homework": existing.homework, "notes": existing.notes,
    }
    fields = _form_dialog(host, f"Edit plan #{plan_id}", initial=initial)
    if not fields:
        return
    data.update(plan_id, fields)
    if on_done:
        on_done()


@_safe_view
def _status_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    plan_id = _selected_id(tree, host)
    if plan_id is None:
        return
    p = data.get(plan_id)
    if p is None:
        return
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Status — plan #{plan_id}")
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
    ttk.Label(frm, text=p.title[:40]).pack(anchor="w")
    ttk.Label(frm, text=f"Current status: {p.status}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    new_var = tk.StringVar(value=p.status)
    ttk.Combobox(frm, textvariable=new_var, values=list(STATUSES),
                 state="readonly").pack(fill="x")

    def _save() -> None:
        try:
            data.set_status(plan_id, new_var.get())
        except ValidationError as e:
            messagebox.showerror("Lesson Plans", str(e), parent=dlg)
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
def _delete_selected(host, tree: ttk.Treeview, *, on_done=None) -> None:
    plan_id = _selected_id(tree, host)
    if plan_id is None:
        return
    p = data.get(plan_id)
    if p is None:
        return
    if not messagebox.askyesno(
            "Delete plan",
            f"Delete plan #{plan_id} ({p.title})?",
            parent=host.root):
        return
    data.delete(plan_id)
    if on_done:
        on_done()
