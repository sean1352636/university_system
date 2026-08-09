"""Tk views for quality-assurance reviews."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.systems.secondary.domain.assessment.quality_assurance import (
    quality_assurance as data,
)
from education_system.systems.secondary.domain.assessment.quality_assurance.quality_assurance import (
    REVIEW_TYPES, REVIEW_STATUSES, JUDGEMENTS, ACTION_STATUSES,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
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
                messagebox.showerror("Quality Assurance", str(e),
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


def _review_dialog(host, title: str,
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

    title_var  = tk.StringVar(value=str(initial.get("title") or ""))
    type_var   = tk.StringVar(value=str(initial.get("review_type")
                                          or "Department"))
    focus_var  = tk.StringVar(value=str(initial.get("focus_area") or ""))
    lead_var   = tk.StringVar(value=str(initial.get("lead_reviewer")
                                          or ""))
    team_var   = tk.StringVar(value=str(initial.get("additional_team")
                                          or ""))
    date_var   = tk.StringVar(value=str(initial.get("review_date") or ""))
    status_var = tk.StringVar(value=str(initial.get("status")
                                          or "Planned"))
    jud_var    = tk.StringVar(value=str(initial.get("judgement")
                                          or "Not judged"))
    follow_var = tk.StringVar(value=str(initial.get("follow_up_date")
                                          or ""))

    rows: list[tuple[str, tk.Widget]] = [
        ("Title:",        ttk.Entry(frm, textvariable=title_var,
                                      width=44)),
        ("Type:",         ttk.Combobox(frm, textvariable=type_var,
                                        values=list(REVIEW_TYPES),
                                        state="readonly", width=20)),
        ("Focus area:",   ttk.Entry(frm, textvariable=focus_var,
                                      width=34)),
        ("Lead reviewer:", ttk.Entry(frm, textvariable=lead_var,
                                       width=24)),
        ("Additional team:", ttk.Entry(frm, textvariable=team_var,
                                         width=34)),
        ("Review date:",  ttk.Entry(frm, textvariable=date_var,
                                      width=14)),
        ("Status:",       ttk.Combobox(frm, textvariable=status_var,
                                        values=list(REVIEW_STATUSES),
                                        state="readonly", width=14)),
        ("Judgement:",    ttk.Combobox(frm, textvariable=jud_var,
                                        values=list(JUDGEMENTS),
                                        state="readonly", width=22)),
        ("Follow-up date:", ttk.Entry(frm, textvariable=follow_var,
                                        width=14)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    text_fields = [("Strengths:", "strengths", 3),
                   ("Areas for development:",
                    "areas_for_development", 3),
                   ("Summary:", "summary", 3),
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
            "title":          title_var.get().strip(),
            "review_type":    type_var.get().strip(),
            "focus_area":     focus_var.get().strip(),
            "lead_reviewer":  lead_var.get().strip(),
            "additional_team": team_var.get().strip(),
            "review_date":    date_var.get().strip(),
            "status":         status_var.get().strip(),
            "judgement":      jud_var.get().strip(),
            "follow_up_date": follow_var.get().strip(),
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


def _action_dialog(host, review_id: int,
                    initial: dict[str, Any] | None = None
                    ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Action — review #{review_id}")
    dlg.transient(host.root)
    dlg.geometry("440x420")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    initial = initial or {}
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    action_var = tk.StringVar(value=str(initial.get("action") or ""))
    owner_var  = tk.StringVar(value=str(initial.get("owner") or ""))
    due_var    = tk.StringVar(value=str(initial.get("due_date") or ""))
    status_var = tk.StringVar(value=str(initial.get("status") or "Open"))

    rows: list[tuple[str, tk.Widget]] = [
        ("Action:", ttk.Entry(frm, textvariable=action_var, width=34)),
        ("Owner:",  ttk.Entry(frm, textvariable=owner_var, width=24)),
        ("Due date:", ttk.Entry(frm, textvariable=due_var, width=14)),
        ("Status:", ttk.Combobox(frm, textvariable=status_var,
                                   values=list(ACTION_STATUSES),
                                   state="readonly", width=12)),
    ]
    for label, widget in rows:
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=12).pack(side="left")
        widget.pack(in_=row, side="left", padx=4)

    ttk.Label(frm, text="Evidence (required if Done):").pack(
        anchor="w", pady=(8, 0))
    evidence_w = tk.Text(frm, width=44, height=4, wrap="word")
    evidence_w.insert("1.0", str(initial.get("evidence") or ""))
    evidence_w.pack(fill="x", pady=2)

    ttk.Label(frm, text="Notes:").pack(anchor="w", pady=(8, 0))
    notes_w = tk.Text(frm, width=44, height=2, wrap="word")
    notes_w.insert("1.0", str(initial.get("notes") or ""))
    notes_w.pack(fill="x", pady=2)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "review_id": review_id,
            "action":    action_var.get().strip(),
            "owner":     owner_var.get().strip(),
            "due_date":  due_var.get().strip(),
            "status":    status_var.get().strip(),
            "evidence":  evidence_w.get("1.0", "end").strip(),
            "notes":     notes_w.get("1.0", "end").strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(10, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_quality_assurance(host) -> None:
    logger.debug("GUI: open_quality_assurance")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Quality Assurance",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(root, textvariable=summary_var, foreground="#666").pack(
        anchor="w", pady=(0, 8))

    bar = ttk.Frame(root)
    bar.pack(fill="x", pady=(0, 6))
    ttk.Label(bar, text="Type:").pack(side="left", padx=(0, 4))
    type_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=type_var,
                 values=["", *REVIEW_TYPES], state="readonly",
                 width=18).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                 values=["", *REVIEW_STATUSES], state="readonly",
                 width=12).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Judgement:").pack(side="left", padx=(0, 4))
    jud_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=jud_var,
                 values=["", *JUDGEMENTS], state="readonly",
                 width=20).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Actions",
               command=lambda: _open_actions(host, tree)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Status",
               command=lambda: _status(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "date", "type", "focus", "lead", "status",
            "judgement")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("date", "Date", 100),
        ("type", "Type", 140), ("focus", "Focus", 200),
        ("lead", "Lead", 160), ("status", "Status", 100),
        ("judgement", "Judgement", 180),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_reviews(
                review_type=type_var.get().strip() or None,
                status=status_var.get().strip() or None,
                judgement=jud_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Quality Assurance", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("QA refresh failed")
            messagebox.showerror("Quality Assurance",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for r in rows:
            tree.insert("", "end", iid=str(r.review_id), values=(
                r.review_id, r.review_date, r.review_type,
                r.focus_area or "-", r.lead_reviewer,
                r.status, r.judgement,
            ))
        try:
            s = data.cohort_summary()
            summary_var.set(
                f"Reviews: {s['reviews']}    "
                f"Actions: {s['actions']}    "
                f"Open: {s['open_actions']}    "
                f"Overdue: {s['overdue_actions']}")
        except Exception:
            summary_var.set(f"{len(rows)} review(s) listed")
        host.status_var.set(f"QA: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _open_actions(host, tree))
    type_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    jud_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Quality Assurance",
                            "Select a review first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _review_dialog(host, "New QA review")
    if not fields:
        return
    r = data.create_review(fields)
    messagebox.showinfo("Quality Assurance",
                        f"Created review #{r.review_id}: {r.title}",
                        parent=host.root)
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    rid = _selected_id(tree, host)
    if rid is None:
        return
    existing = data.get_review(rid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "title", "review_type", "focus_area", "lead_reviewer",
        "additional_team", "review_date", "status", "judgement",
        "strengths", "areas_for_development", "summary",
        "follow_up_date", "notes")}
    fields = _review_dialog(host, f"Edit review #{rid}",
                              initial=initial)
    if not fields:
        return
    data.update_review(rid, fields)
    if on_done:
        on_done()


@_safe_view
def _status(host, tree: ttk.Treeview, *, on_done=None) -> None:
    rid = _selected_id(tree, host)
    if rid is None:
        return
    r = data.get_review(rid)
    if r is None:
        return
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Status — #{rid}")
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
    ttk.Label(frm, text=r.title[:40]).pack(anchor="w")
    ttk.Label(frm, text=f"Current: {r.status}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    new_var = tk.StringVar(value=r.status)
    ttk.Combobox(frm, textvariable=new_var,
                 values=list(REVIEW_STATUSES),
                 state="readonly").pack(fill="x")

    def _save() -> None:
        try:
            data.set_review_status(rid, new_var.get())
        except ValidationError as ex:
            messagebox.showerror("Quality Assurance", str(ex),
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
    rid = _selected_id(tree, host)
    if rid is None:
        return
    existing = data.get_review(rid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete review",
            f"Delete review '{existing.title}' and ALL its actions?",
            parent=host.root):
        return
    data.delete_review(rid)
    if on_done:
        on_done()


@_safe_view
def _open_actions(host, tree: ttk.Treeview) -> None:
    rid = _selected_id(tree, host)
    if rid is None:
        return
    rec = data.get_review(rid)
    if rec is None:
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Actions — review #{rid}")
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
    overdue_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(bar, text="Overdue only",
                    variable=overdue_var,
                    command=lambda: _refresh()).pack(side="left",
                                                     padx=(0, 8))
    ttk.Button(bar, text="Add",
               command=lambda: _do_add()).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _do_edit()).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _do_delete()).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    t = ttk.Treeview(frm,
                       columns=("id", "due", "od", "status",
                                 "owner", "action"),
                       show="headings", height=14)
    for c, label, w in [
        ("id", "ID", 50), ("due", "Due", 100),
        ("od", "OD", 40), ("status", "Status", 100),
        ("owner", "Owner", 160), ("action", "Action", 320),
    ]:
        t.heading(c, text=label)
        t.column(c, width=w, anchor="w")
    t.pack(fill="both", expand=True)
    t.tag_configure("overdue", background="#ffcccc")

    def _refresh() -> None:
        for i in t.get_children():
            t.delete(i)
        try:
            rows = data.list_actions(
                review_id=rid,
                overdue_only=bool(overdue_var.get()))
            s = data.review_summary(rid)
        except Exception as e:
            logger.exception("actions list failed")
            messagebox.showerror("Quality Assurance",
                                 f"Could not load:\n\n{e}",
                                 parent=dlg)
            return
        header_var.set(
            f"Review #{rid}: {rec.title}    "
            f"Actions: {len(s['actions'])}    "
            f"Open: {s['open_actions']}    "
            f"Done: {s['done_actions']}    "
            f"Overdue: {s['overdue']}")
        for a in rows:
            tags = ("overdue",) if a.overdue else ()
            t.insert("", "end", iid=str(a.action_id), values=(
                a.action_id, a.due_date or "-",
                "!" if a.overdue else "-",
                a.status, a.owner or "-", a.action,
            ), tags=tags)

    def _do_add() -> None:
        fields = _action_dialog(host, rid)
        if not fields:
            return
        try:
            data.add_action(fields)
        except ValidationError as e:
            messagebox.showerror("Quality Assurance", str(e),
                                 parent=dlg)
            return
        _refresh()

    def _do_edit() -> None:
        sel = t.focus()
        if not sel:
            messagebox.showinfo("Quality Assurance",
                                "Select an action first.",
                                parent=dlg)
            return
        try:
            aid = int(sel)
        except ValueError:
            return
        existing = data.get_action(aid)
        if existing is None:
            return
        initial = {k: getattr(existing, k) for k in (
            "action", "owner", "due_date", "status",
            "evidence", "notes")}
        fields = _action_dialog(host, rid, initial=initial)
        if not fields:
            return
        try:
            data.update_action(aid, fields)
        except ValidationError as e:
            messagebox.showerror("Quality Assurance", str(e),
                                 parent=dlg)
            return
        _refresh()

    def _do_delete() -> None:
        sel = t.focus()
        if not sel:
            messagebox.showinfo("Quality Assurance",
                                "Select an action first.",
                                parent=dlg)
            return
        try:
            aid = int(sel)
        except ValueError:
            return
        if not messagebox.askyesno(
                "Delete action",
                f"Delete action #{aid}?", parent=dlg):
            return
        data.delete_action(aid)
        _refresh()

    t.bind("<Double-1>", lambda _e: _do_edit())
    _refresh()
