"""Tk views for SEND."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.systems.secondary.domain.pastoral.send import (
    send as data,
)
from education_system.systems.secondary.domain.pastoral.send.send import (
    PROVISION_STAGES, NEED_CATEGORIES, SEND_STATUSES, REVIEW_OUTCOMES,
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
                messagebox.showerror("SEND", str(e),
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


def _record_dialog(host, title: str,
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

    pupil_var   = tk.StringVar(value=str(initial.get("pupil_id") or ""))
    ay_var      = tk.StringVar(value=str(initial.get("academic_year")
                                           or ""))
    stage_var   = tk.StringVar(value=str(initial.get("provision_stage")
                                           or "Monitoring"))
    primary_var = tk.StringVar(value=str(initial.get("primary_need")
                                           or "Cognition and learning"))
    secondary_var = tk.StringVar(value=str(initial.get("secondary_need")
                                              or ""))
    status_var  = tk.StringVar(value=str(initial.get("status")
                                           or "Active"))
    senco_var   = tk.StringVar(value=str(initial.get("senco") or ""))
    keyworker_var = tk.StringVar(value=str(initial.get("keyworker")
                                              or ""))
    parent_var  = tk.StringVar(value=str(initial.get("parent_contact")
                                           or ""))
    email_var   = tk.StringVar(value=str(initial.get("parent_email")
                                           or ""))
    ehcp_var    = tk.StringVar(value=str(initial.get("ehcp_reference")
                                           or ""))
    start_var   = tk.StringVar(value=str(initial.get("start_date")
                                           or ""))
    nextrev_var = tk.StringVar(value=str(initial.get("next_review_date")
                                            or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:",    ttk.Entry(frm, textvariable=pupil_var,
                                      width=14)),
        ("Academic year:", ttk.Entry(frm, textvariable=ay_var,
                                       width=10)),
        ("Provision stage:", ttk.Combobox(frm, textvariable=stage_var,
                                            values=list(PROVISION_STAGES),
                                            state="readonly", width=36)),
        ("Primary need:", ttk.Combobox(frm, textvariable=primary_var,
                                         values=list(NEED_CATEGORIES),
                                         state="readonly", width=36)),
        ("Secondary need:", ttk.Combobox(frm,
                                           textvariable=secondary_var,
                                           values=["", *NEED_CATEGORIES],
                                           state="readonly", width=36)),
        ("Status:",      ttk.Combobox(frm, textvariable=status_var,
                                        values=list(SEND_STATUSES),
                                        state="readonly", width=14)),
        ("SENCo:",       ttk.Entry(frm, textvariable=senco_var,
                                      width=24)),
        ("Keyworker:",   ttk.Entry(frm, textvariable=keyworker_var,
                                      width=24)),
        ("Parent contact:", ttk.Entry(frm, textvariable=parent_var,
                                        width=24)),
        ("Parent email:", ttk.Entry(frm, textvariable=email_var,
                                       width=30)),
        ("EHCP reference:", ttk.Entry(frm, textvariable=ehcp_var,
                                         width=18)),
        ("Start date:",  ttk.Entry(frm, textvariable=start_var,
                                      width=14)),
        ("Next review:", ttk.Entry(frm, textvariable=nextrev_var,
                                      width=14)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    text_fields = [("Provision summary:", "provision_summary", 3),
                   ("Diagnosis:", "diagnosis", 2),
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
            "pupil_id":          pupil_var.get().strip(),
            "academic_year":     ay_var.get().strip(),
            "provision_stage":   stage_var.get().strip(),
            "primary_need":      primary_var.get().strip(),
            "secondary_need":    secondary_var.get().strip(),
            "status":            status_var.get().strip(),
            "senco":             senco_var.get().strip(),
            "keyworker":         keyworker_var.get().strip(),
            "parent_contact":    parent_var.get().strip(),
            "parent_email":      email_var.get().strip(),
            "ehcp_reference":    ehcp_var.get().strip(),
            "start_date":        start_var.get().strip(),
            "next_review_date":  nextrev_var.get().strip(),
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


def _review_dialog(host, send_id: int,
                    initial: dict[str, Any] | None = None
                    ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Review — SEND record #{send_id}")
    dlg.transient(host.root)
    dlg.geometry("520x520")
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
                                            or "Continue"))
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
                   ("Adjustments:", "adjustments", 3),
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
            "send_id":           send_id,
            "review_date":       date_var.get().strip(),
            "reviewer":          reviewer_var.get().strip(),
            "outcome":           outcome_var.get().strip(),
            "next_review_date":  next_var.get().strip(),
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


@_safe_view
def open_send(host) -> None:
    logger.debug("GUI: open_send")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="SEND",
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
    ttk.Label(bar, text="Stage:").pack(side="left", padx=(0, 4))
    stage_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=stage_var,
                 values=["", *PROVISION_STAGES], state="readonly",
                 width=30).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                 values=["", *SEND_STATUSES], state="readonly",
                 width=12).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New / update",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Reviews",
               command=lambda: _open_reviews(host, tree)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Overdue",
               command=lambda: _overdue(host)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "ay", "pupil", "year", "stage", "primary",
            "status", "next")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("ay", "Academic yr", 100),
        ("pupil", "Pupil", 90), ("year", "Yr", 50),
        ("stage", "Stage", 220), ("primary", "Primary need", 240),
        ("status", "Status", 100), ("next", "Next review", 100),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_records(
                year_group=year_var.get().strip() or None,
                provision_stage=stage_var.get().strip() or None,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("SEND", str(e), parent=host.root)
            return
        except Exception as e:
            logger.exception("SEND refresh failed")
            messagebox.showerror("SEND",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for r in rows:
            tree.insert("", "end", iid=str(r.send_id), values=(
                r.send_id, r.academic_year, r.pupil_id,
                r.pupil_year or "-", r.provision_stage,
                r.primary_need, r.status,
                r.next_review_date or "-",
            ))
        try:
            s = data.cohort_summary(
                year_group=year_var.get().strip() or None)
            summary_var.set(
                f"Records: {s['total']}    EHCP: {s['ehcp_count']}    "
                + "    ".join(f"{k}: {v}"
                                for k, v in s["by_status"].items()))
        except Exception:
            summary_var.set(f"{len(rows)} record(s)")
        host.status_var.set(f"SEND: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _open_reviews(host, tree))
    year_var.trace_add("write", lambda *_: _refresh())
    stage_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("SEND",
                            "Select a record first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _record_dialog(host, "New / update SEND record")
    if not fields:
        return
    r = data.upsert(fields)
    messagebox.showinfo(
        "SEND",
        f"Saved {r.pupil_id} ({r.academic_year}) — "
        f"{r.provision_stage}",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    sid = _selected_id(tree, host)
    if sid is None:
        return
    existing = data.get(sid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "pupil_id", "academic_year", "provision_stage",
        "primary_need", "secondary_need", "status",
        "senco", "keyworker", "parent_contact", "parent_email",
        "ehcp_reference", "start_date", "next_review_date",
        "provision_summary", "diagnosis", "notes")}
    fields = _record_dialog(host, f"Edit SEND record #{sid}",
                              initial=initial)
    if not fields:
        return
    data.upsert(fields)
    if on_done:
        on_done()


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    sid = _selected_id(tree, host)
    if sid is None:
        return
    existing = data.get(sid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete SEND record",
            f"Delete SEND record for {existing.pupil_id} "
            f"({existing.academic_year}) and ALL reviews?",
            parent=host.root):
        return
    data.delete(sid)
    if on_done:
        on_done()


@_safe_view
def _overdue(host) -> None:
    rows = data.overdue_reviews()
    dlg = tk.Toplevel(host.root)
    dlg.title("Overdue SEND reviews")
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
              text=f"{len(rows)} record(s) with overdue reviews",
              font=("", 10, "bold")).pack(anchor="w", pady=(0, 8))
    t = ttk.Treeview(frm,
                       columns=("id", "pupil", "year", "stage",
                                 "next"),
                       show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("pupil", "Pupil", 100),
        ("year", "Yr", 50), ("stage", "Stage", 240),
        ("next", "Next review", 110),
    ]:
        t.heading(c, text=label)
        t.column(c, width=w, anchor="w")
    t.pack(fill="both", expand=True)
    for r in rows:
        t.insert("", "end", values=(
            r.send_id, r.pupil_id, r.pupil_year or "-",
            r.provision_stage, r.next_review_date,
        ))
    ttk.Button(frm, text="Close",
               command=dlg.destroy).pack(side="right", pady=(10, 0))


@_safe_view
def _open_reviews(host, tree: ttk.Treeview) -> None:
    sid = _selected_id(tree, host)
    if sid is None:
        return
    rec = data.get(sid)
    if rec is None:
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Reviews — SEND record #{sid}")
    dlg.transient(host.root)
    dlg.geometry("780x500")
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
        ("reviewer", "Reviewer", 140), ("outcome", "Outcome", 120),
        ("next", "Next review", 100),
        ("progress", "Progress", 240),
    ]:
        t.heading(c, text=label)
        t.column(c, width=w, anchor="w")
    t.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in t.get_children():
            t.delete(i)
        try:
            s = data.record_summary(sid)
        except Exception as e:
            logger.exception("record_summary failed")
            messagebox.showerror("SEND",
                                 f"Could not load:\n\n{e}",
                                 parent=dlg)
            return
        r = s["record"]
        header_var.set(
            f"#{r.send_id} {r.pupil_id} ({r.academic_year})    "
            f"{r.provision_stage} / {r.primary_need}    "
            f"Reviews: {s['review_count']}    "
            f"Last: {s['last_review'] or '-'}")
        for rev in s["reviews"]:
            t.insert("", "end", iid=str(rev.review_id), values=(
                rev.review_id, rev.review_date,
                rev.reviewer or "-", rev.outcome,
                rev.next_review_date or "-",
                (rev.progress or "-")[:80],
            ))

    def _do_add() -> None:
        fields = _review_dialog(host, sid)
        if not fields:
            return
        try:
            data.add_review(fields)
        except ValidationError as e:
            messagebox.showerror("SEND", str(e), parent=dlg)
            return
        _refresh()

    def _do_delete() -> None:
        sel = t.focus()
        if not sel:
            messagebox.showinfo("SEND",
                                "Select a review first.", parent=dlg)
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
