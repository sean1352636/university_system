"""Tk views for homework assignments and submissions."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.systems.primary.domain.academics.homework import (
    homework as data,
)
from education_system.systems.primary.domain.academics.homework.homework import (
    ASSIGNMENT_STATUSES, SUBMISSION_STATUSES,
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
                messagebox.showerror("Homework", str(e),
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


def _assignment_dialog(host, title: str,
                       initial: dict[str, Any] | None = None
                       ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("520x540")
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
    setby_var    = tk.StringVar(value=str(initial.get("set_by") or ""))
    setdate_var  = tk.StringVar(value=str(initial.get("set_date") or ""))
    duedate_var  = tk.StringVar(value=str(initial.get("due_date") or ""))
    points_var   = tk.StringVar(value=str(initial.get("points") or ""))
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

    rows: list[tuple[str, tk.Widget]] = [
        ("Title:",    ttk.Entry(frm, textvariable=title_var, width=44)),
        ("Subject:",  ttk.Combobox(frm, textvariable=subject_var,
                                    values=subject_labels,
                                    state="readonly", width=42)),
        ("Year:",     ttk.Combobox(frm, textvariable=year_var,
                                    values=list(YEAR_GROUPS),
                                    state="readonly", width=8)),
        ("Form:",     ttk.Entry(frm, textvariable=form_var, width=12)),
        ("Set by:",   ttk.Entry(frm, textvariable=setby_var, width=30)),
        ("Set date:", ttk.Entry(frm, textvariable=setdate_var, width=14)),
        ("Due date:", ttk.Entry(frm, textvariable=duedate_var, width=14)),
        ("Points:",   ttk.Entry(frm, textvariable=points_var, width=8)),
        ("Status:",   ttk.Combobox(frm, textvariable=status_var,
                                    values=list(ASSIGNMENT_STATUSES),
                                    state="readonly", width=12)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="nw",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Instructions:").grid(row=len(rows), column=0,
                                               sticky="nw", pady=2)
    instr_w = tk.Text(frm, width=46, height=5, wrap="word")
    instr_w.insert("1.0", str(initial.get("instructions") or ""))
    instr_w.grid(row=len(rows), column=1, sticky="ew", pady=2)

    ttk.Label(frm, text="Notes:").grid(row=len(rows) + 1, column=0,
                                        sticky="nw", pady=2)
    notes_w = tk.Text(frm, width=46, height=3, wrap="word")
    notes_w.insert("1.0", str(initial.get("notes") or ""))
    notes_w.grid(row=len(rows) + 1, column=1, sticky="ew", pady=2)

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
            "set_by":       setby_var.get().strip(),
            "set_date":     setdate_var.get().strip(),
            "due_date":     duedate_var.get().strip(),
            "points":       points_var.get().strip(),
            "status":       status_var.get().strip(),
            "instructions": instr_w.get("1.0", "end").strip(),
            "notes":        notes_w.get("1.0", "end").strip(),
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


def _submission_dialog(host, assignment: data.Assignment,
                       existing: data.Submission | None,
                       initial_pupil: str | None = None
                       ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Submission — assignment #{assignment.assignment_id}")
    dlg.transient(host.root)
    dlg.geometry("440x360")
    dlg.update_idletasks()
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        pass
    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    pupil_var = tk.StringVar(value=str(
        (existing.pupil_id if existing else initial_pupil) or ""))
    status_var = tk.StringVar(value=str(
        existing.status if existing else "Pending"))
    subdate_var = tk.StringVar(value=str(
        existing.submitted_date if existing else ""))
    grade_var = tk.StringVar(value=str(
        existing.grade if existing else ""))
    pct_var = tk.StringVar(value=str(
        existing.mark_pct if existing and existing.mark_pct is not None
        else ""))

    ttk.Label(frm,
              text=f"Assignment: {assignment.title}",
              font=("", 10, "bold")).pack(anchor="w", pady=(0, 8))

    rows: list[tuple[str, tk.Widget]] = [
        ("Pupil ID:",  ttk.Entry(frm, textvariable=pupil_var, width=14,
                                  state=("readonly" if existing
                                          else "normal"))),
        ("Status:",    ttk.Combobox(frm, textvariable=status_var,
                                     values=list(SUBMISSION_STATUSES),
                                     state="readonly", width=12)),
        ("Submitted:", ttk.Entry(frm, textvariable=subdate_var, width=14)),
        ("Grade:",     ttk.Entry(frm, textvariable=grade_var, width=10)),
        ("Mark %:",    ttk.Entry(frm, textvariable=pct_var, width=8)),
    ]
    for i, (label, widget) in enumerate(rows):
        row = ttk.Frame(frm)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=12).pack(side="left")
        widget.pack(in_=row, side="left", padx=4)

    ttk.Label(frm, text="Feedback:").pack(anchor="w", pady=(8, 0))
    feedback_w = tk.Text(frm, width=44, height=4, wrap="word")
    feedback_w.insert("1.0", str(existing.feedback if existing else ""))
    feedback_w.pack(fill="x", pady=2)

    result: dict[str, Any] | None = None

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id":       pupil_var.get().strip(),
            "status":         status_var.get().strip(),
            "submitted_date": subdate_var.get().strip(),
            "grade":          grade_var.get().strip(),
            "mark_pct":       pct_var.get().strip(),
            "feedback":       feedback_w.get("1.0", "end").strip(),
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
def open_homework(host) -> None:
    logger.debug("GUI: open_homework")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Homework",
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
                 values=["", *ASSIGNMENT_STATUSES], state="readonly",
                 width=8).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="New",
               command=lambda: _new_assignment(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit_assignment(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Set status",
               command=lambda: _status_assignment(host, tree,
                                                    on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Seed",
               command=lambda: _seed(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Submissions",
               command=lambda: _open_submissions(host, tree)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Summary",
               command=lambda: _summary(host, tree)).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete_assignment(host, tree,
                                                    on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "due", "year", "form", "subj", "title", "by",
            "pts", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("due", "Due", 100),
        ("year", "Yr", 50), ("form", "Form", 60),
        ("subj", "Subject", 90), ("title", "Title", 240),
        ("by", "Set by", 140), ("pts", "Pts", 50), ("status", "Status", 80),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_assignments(
                year_group=year_var.get().strip() or None,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Homework", str(e), parent=host.root)
            return
        except Exception as e:
            logger.exception("homework refresh failed")
            messagebox.showerror("Homework",
                                 f"Could not load assignments:\n\n{e}",
                                 parent=host.root)
            return
        for a in rows:
            tree.insert("", "end", iid=str(a.assignment_id), values=(
                a.assignment_id, a.due_date, a.year_group,
                a.form_group or "-", a.subject_code or "?",
                a.title, a.set_by or "-",
                a.points if a.points is not None else "-",
                a.status,
            ))
        try:
            c = data.assignment_status_counts()
            total = sum(c.values())
            summary_var.set(
                f"Total: {total}    " +
                "    ".join(f"{s}: {c[s]}" for s in ASSIGNMENT_STATUSES))
        except Exception:
            logger.exception("assignment counts failed")
            summary_var.set("(counts unavailable)")
        host.status_var.set(f"Homework: {len(rows)} assignment(s)")

    tree.bind("<Double-1>", lambda _e: _open_submissions(host, tree))
    year_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_assignment_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Homework", "Select an assignment first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new_assignment(host, *, on_done=None) -> None:
    fields = _assignment_dialog(host, "New assignment")
    if not fields:
        return
    a = data.create_assignment(fields)
    if messagebox.askyesno(
            "Seed submissions?",
            f"Created assignment #{a.assignment_id}.\n\nSeed Pending "
            f"submission rows for all Year {a.year_group}"
            f"{('/' + a.form_group) if a.form_group else ''} pupils?",
            parent=host.root):
        try:
            added = data.seed_submissions(a.assignment_id)
            messagebox.showinfo("Homework",
                                f"Seeded {added} submission row(s).",
                                parent=host.root)
        except Exception as e:
            logger.exception("seed after create failed")
            messagebox.showerror("Homework",
                                 f"Seed failed:\n\n{e}", parent=host.root)
    if on_done:
        on_done()


@_safe_view
def _edit_assignment(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_assignment_id(tree, host)
    if aid is None:
        return
    existing = data.get_assignment(aid)
    if existing is None:
        return
    initial = {
        "title": existing.title, "subject_id": existing.subject_id,
        "year_group": existing.year_group,
        "form_group": existing.form_group,
        "set_by": existing.set_by, "set_date": existing.set_date,
        "due_date": existing.due_date, "points": existing.points,
        "status": existing.status, "instructions": existing.instructions,
        "notes": existing.notes,
    }
    fields = _assignment_dialog(host, f"Edit assignment #{aid}",
                                initial=initial)
    if not fields:
        return
    data.update_assignment(aid, fields)
    if on_done:
        on_done()


@_safe_view
def _status_assignment(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_assignment_id(tree, host)
    if aid is None:
        return
    a = data.get_assignment(aid)
    if a is None:
        return
    dlg = tk.Toplevel(host.root)
    dlg.title(f"Status — #{aid}")
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
    ttk.Label(frm, text=a.title[:40]).pack(anchor="w")
    ttk.Label(frm, text=f"Current status: {a.status}",
              foreground="#666").pack(anchor="w", pady=(0, 8))
    new_var = tk.StringVar(value=a.status)
    ttk.Combobox(frm, textvariable=new_var,
                 values=list(ASSIGNMENT_STATUSES),
                 state="readonly").pack(fill="x")

    def _save() -> None:
        try:
            data.set_assignment_status(aid, new_var.get())
        except ValidationError as e:
            messagebox.showerror("Homework", str(e), parent=dlg)
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
def _delete_assignment(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_assignment_id(tree, host)
    if aid is None:
        return
    a = data.get_assignment(aid)
    if a is None:
        return
    if not messagebox.askyesno(
            "Delete assignment",
            f"Delete '{a.title}' and ALL submissions?",
            parent=host.root):
        return
    data.delete_assignment(aid)
    if on_done:
        on_done()


@_safe_view
def _seed(host, tree: ttk.Treeview) -> None:
    aid = _selected_assignment_id(tree, host)
    if aid is None:
        return
    added = data.seed_submissions(aid)
    messagebox.showinfo("Homework",
                        f"Added {added} new submission row(s).",
                        parent=host.root)


@_safe_view
def _summary(host, tree: ttk.Treeview) -> None:
    aid = _selected_assignment_id(tree, host)
    if aid is None:
        return
    s = data.submission_summary(aid)
    a = s["assignment"]
    lines = [
        f"{a.title}",
        f"Yr {a.year_group}"
        f"{('/' + a.form_group) if a.form_group else ''}    "
        f"due {a.due_date}    status {a.status}",
        "",
        f"Total submissions: {s['total']}",
        f"Marked: {s['marked']}    Avg %: "
        f"{s['avg_mark_pct'] if s['avg_mark_pct'] is not None else '-'}",
        "",
        "By status:",
    ]
    for k, v in s["by_status"].items():
        lines.append(f"   {k:<10} {v}")
    messagebox.showinfo("Homework — summary", "\n".join(lines),
                        parent=host.root)


@_safe_view
def _open_submissions(host, tree: ttk.Treeview) -> None:
    aid = _selected_assignment_id(tree, host)
    if aid is None:
        return
    a = data.get_assignment(aid)
    if a is None:
        return

    dlg = tk.Toplevel(host.root)
    dlg.title(f"Submissions — {a.title}")
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
    ttk.Label(frm,
              text=f"{a.title}    Yr {a.year_group}"
                   f"{('/' + a.form_group) if a.form_group else ''}    "
                   f"due {a.due_date}    status {a.status}",
              font=("", 10, "bold")).pack(anchor="w")

    bar = ttk.Frame(frm)
    bar.pack(fill="x", pady=(8, 4))
    ttk.Button(bar, text="Seed pupils",
               command=lambda: (_run_seed(), _refresh())).pack(side="left",
                                                                padx=2)
    ttk.Button(bar, text="Add / edit submission",
               command=lambda: _do_upsert(None)).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit selected",
               command=lambda: _do_upsert("selected")).pack(side="left",
                                                            padx=2)
    ttk.Button(bar, text="Delete selected",
               command=lambda: _do_delete()).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    sub_tree = ttk.Treeview(frm,
                             columns=("id", "pupil", "submitted", "status",
                                       "grade", "pct", "feedback"),
                             show="headings", height=16)
    for c, label, w in [
        ("id", "ID", 50), ("pupil", "Pupil", 100),
        ("submitted", "Submitted", 100), ("status", "Status", 90),
        ("grade", "Grade", 70), ("pct", "%", 50),
        ("feedback", "Feedback", 260),
    ]:
        sub_tree.heading(c, text=label)
        sub_tree.column(c, width=w, anchor="w")
    sub_tree.pack(fill="both", expand=True)

    def _run_seed() -> None:
        try:
            added = data.seed_submissions(aid)
        except ValidationError as e:
            messagebox.showerror("Homework", str(e), parent=dlg)
            return
        messagebox.showinfo("Homework",
                            f"Added {added} submission row(s).",
                            parent=dlg)

    def _refresh() -> None:
        for i in sub_tree.get_children():
            sub_tree.delete(i)
        try:
            rows = data.list_submissions(aid)
        except Exception as e:
            logger.exception("submissions list failed")
            messagebox.showerror("Homework",
                                 f"Could not load submissions:\n\n{e}",
                                 parent=dlg)
            return
        for s in rows:
            sub_tree.insert("", "end", iid=str(s.submission_id), values=(
                s.submission_id, s.pupil_id, s.submitted_date or "-",
                s.status, s.grade or "-",
                f"{s.mark_pct:.0f}" if s.mark_pct is not None else "-",
                (s.feedback or "-")[:80],
            ))

    def _do_upsert(mode: str | None) -> None:
        existing: data.Submission | None = None
        initial_pupil: str | None = None
        if mode == "selected":
            sel = sub_tree.focus()
            if not sel:
                messagebox.showinfo("Homework",
                                    "Select a submission first.",
                                    parent=dlg)
                return
            try:
                existing = data.get_submission(int(sel))
            except Exception:
                logger.exception("get_submission failed")
                return
        else:
            initial_pupil = simpledialog.askstring(
                "Pupil ID", "Pupil ID:", parent=dlg)
            if not initial_pupil:
                return
        fields = _submission_dialog(host, a, existing,
                                     initial_pupil=initial_pupil)
        if not fields:
            return
        try:
            data.upsert_submission(aid, fields)
        except ValidationError as e:
            messagebox.showerror("Homework", str(e), parent=dlg)
            return
        _refresh()

    def _do_delete() -> None:
        sel = sub_tree.focus()
        if not sel:
            messagebox.showinfo("Homework",
                                "Select a submission first.",
                                parent=dlg)
            return
        try:
            sid = int(sel)
        except ValueError:
            return
        rec = data.get_submission(sid)
        if rec is None:
            return
        if not messagebox.askyesno(
                "Delete submission",
                f"Delete submission for pupil {rec.pupil_id}?",
                parent=dlg):
            return
        data.delete_submission(sid)
        _refresh()

    sub_tree.bind("<Double-1>", lambda _e: _do_upsert("selected"))
    _refresh()
