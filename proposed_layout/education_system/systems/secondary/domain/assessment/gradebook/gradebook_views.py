"""Tk views for the gradebook."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.systems.secondary.domain.assessment.gradebook import (
    gradebook as data,
)
from education_system.systems.secondary.domain.assessment.gradebook.gradebook import (
    ASSESSMENT_TYPES, TERMS,
)
from education_system.systems.secondary.domain.academics.subjects import (
    subjects as subjects_data,
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
                messagebox.showerror("Gradebook", str(e),
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


def _entry_dialog(host, title: str,
                  initial: dict[str, Any] | None = None
                  ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("500x520")
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
    name_var   = tk.StringVar(value=str(initial.get("assessment_name")
                                          or ""))
    type_var   = tk.StringVar(value=str(initial.get("assessment_type")
                                          or "Test"))
    term_var   = tk.StringVar(value=str(initial.get("term") or "Autumn"))
    date_var   = tk.StringVar(value=str(initial.get("assessment_date")
                                          or ""))
    marks_var  = tk.StringVar(value=str(initial.get("marks_awarded") or ""))
    max_var    = tk.StringVar(value=str(initial.get("max_marks") or ""))
    grade_var  = tk.StringVar(value=str(initial.get("grade") or ""))
    teacher_var = tk.StringVar(value=str(initial.get("teacher") or ""))

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
        ("Pupil ID:",       ttk.Entry(frm, textvariable=pupil_var,
                                        width=14)),
        ("Subject:",        ttk.Combobox(frm, textvariable=subject_var,
                                          values=subject_labels,
                                          state="readonly", width=42)),
        ("Assessment name:", ttk.Entry(frm, textvariable=name_var,
                                         width=40)),
        ("Type:",           ttk.Combobox(frm, textvariable=type_var,
                                          values=list(ASSESSMENT_TYPES),
                                          state="readonly", width=14)),
        ("Term:",           ttk.Combobox(frm, textvariable=term_var,
                                          values=list(TERMS),
                                          state="readonly", width=10)),
        ("Date:",           ttk.Entry(frm, textvariable=date_var,
                                       width=14)),
        ("Marks awarded:",  ttk.Entry(frm, textvariable=marks_var,
                                       width=8)),
        ("Max marks:",      ttk.Entry(frm, textvariable=max_var,
                                       width=8)),
        ("Grade:",          ttk.Entry(frm, textvariable=grade_var,
                                       width=6)),
        ("Teacher:",        ttk.Entry(frm, textvariable=teacher_var,
                                       width=24)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="Comments:").grid(row=len(rows), column=0,
                                           sticky="nw", pady=2)
    comments_w = tk.Text(frm, width=40, height=4, wrap="word")
    comments_w.insert("1.0", str(initial.get("comments") or ""))
    comments_w.grid(row=len(rows), column=1, sticky="ew", pady=2)

    result: dict[str, Any] | None = None

    def _parse_subject(label: str) -> str:
        label = (label or "").strip()
        if not label.startswith("#"):
            return ""
        return label.split()[0][1:]

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id":        pupil_var.get().strip(),
            "subject_id":      _parse_subject(subject_var.get()),
            "assessment_name": name_var.get().strip(),
            "assessment_type": type_var.get().strip(),
            "term":            term_var.get().strip(),
            "assessment_date": date_var.get().strip(),
            "marks_awarded":   marks_var.get().strip(),
            "max_marks":       max_var.get().strip(),
            "grade":           grade_var.get().strip(),
            "teacher":         teacher_var.get().strip(),
            "comments":        comments_w.get("1.0", "end").strip(),
        }
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="e",
              pady=(12, 0))
    ttk.Button(btns, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()
    return result


@_safe_view
def open_gradebook(host) -> None:
    logger.debug("GUI: open_gradebook")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Gradebook",
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
    ttk.Label(bar, text="Pupil:").pack(side="left", padx=(0, 4))
    pupil_var = tk.StringVar(value="")
    ttk.Entry(bar, textvariable=pupil_var, width=12).pack(
        side="left", padx=(0, 6))
    ttk.Label(bar, text="Term:").pack(side="left", padx=(0, 4))
    term_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=term_var,
                 values=["", *TERMS], state="readonly",
                 width=8).pack(side="left", padx=(0, 6))
    ttk.Label(bar, text="Type:").pack(side="left", padx=(0, 4))
    type_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=type_var,
                 values=["", *ASSESSMENT_TYPES], state="readonly",
                 width=12).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New entry",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Summary",
               command=lambda: _pupil_summary(host)).pack(side="left",
                                                          padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "date", "pupil", "year", "subj", "term", "type",
            "name", "marks", "pct", "grade")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("date", "Date", 90),
        ("pupil", "Pupil", 90), ("year", "Yr", 40),
        ("subj", "Subj", 70), ("term", "Term", 70),
        ("type", "Type", 90), ("name", "Assessment", 220),
        ("marks", "Marks", 80), ("pct", "%", 50),
        ("grade", "Grade", 60),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_entries(
                pupil_id=pupil_var.get().strip() or None,
                year_group=year_var.get().strip() or None,
                term=term_var.get().strip() or None,
                assessment_type=type_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Gradebook", str(e), parent=host.root)
            return
        except Exception as e:
            logger.exception("gradebook refresh failed")
            messagebox.showerror("Gradebook",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for e in rows:
            marks = ("-" if e.marks_awarded is None
                     else (f"{e.marks_awarded:g}/{e.max_marks:g}"
                            if e.max_marks else f"{e.marks_awarded:g}"))
            tree.insert("", "end", iid=str(e.entry_id), values=(
                e.entry_id, e.assessment_date, e.pupil_id,
                e.pupil_year or "-", e.subject_code or "?",
                e.term, e.assessment_type, e.assessment_name,
                marks,
                f"{e.mark_pct:.0f}" if e.mark_pct is not None else "-",
                e.grade or "-",
            ))
        summary_var.set(f"{len(rows)} entry(ies) listed")
        host.status_var.set(f"Gradebook: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _edit(host, tree,
                                              on_done=_refresh))
    year_var.trace_add("write", lambda *_: _refresh())
    term_var.trace_add("write", lambda *_: _refresh())
    type_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Gradebook", "Select an entry first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _entry_dialog(host, "New gradebook entry")
    if not fields:
        return
    e = data.upsert_entry(fields)
    messagebox.showinfo(
        "Gradebook",
        f"Saved entry: {e.pupil_id} / {e.subject_code} — "
        f"{e.assessment_name}",
        parent=host.root,
    )
    if on_done:
        on_done()


@_safe_view
def _edit(host, tree: ttk.Treeview, *, on_done=None) -> None:
    eid = _selected_id(tree, host)
    if eid is None:
        return
    existing = data.get_entry(eid)
    if existing is None:
        return
    initial = {k: getattr(existing, k) for k in (
        "pupil_id", "subject_id", "assessment_name",
        "assessment_type", "term", "assessment_date",
        "marks_awarded", "max_marks", "grade",
        "teacher", "comments")}
    fields = _entry_dialog(host, f"Edit entry #{eid}", initial=initial)
    if not fields:
        return
    data.upsert_entry(fields)
    if on_done:
        on_done()


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    eid = _selected_id(tree, host)
    if eid is None:
        return
    existing = data.get_entry(eid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete entry",
            f"Delete entry for {existing.pupil_id} — "
            f"{existing.assessment_name}?",
            parent=host.root):
        return
    data.delete_entry(eid)
    if on_done:
        on_done()


@_safe_view
def _pupil_summary(host) -> None:
    pid = simpledialog.askstring("Summary", "Pupil ID:",
                                  parent=host.root)
    if not pid:
        return
    sid_raw = simpledialog.askstring("Summary", "Subject ID:",
                                       parent=host.root)
    if not sid_raw:
        return
    try:
        sid = int(sid_raw.strip())
    except ValueError:
        messagebox.showerror("Gradebook",
                             "Subject ID must be a number.",
                             parent=host.root)
        return
    s = data.pupil_subject_summary(pid.strip(), sid)
    lines = [
        f"Pupil: {pid}    Subject: #{sid}",
        f"Entries: {s['count']}",
        f"Avg %: {s['avg_pct'] if s['avg_pct'] is not None else '-'}",
        f"Latest grade: {s['latest_grade'] or '-'}",
        "",
        "By term: " + "    ".join(f"{k}: {v}"
                                    for k, v in s["by_term"].items()),
    ]
    messagebox.showinfo("Gradebook — summary", "\n".join(lines),
                        parent=host.root)
