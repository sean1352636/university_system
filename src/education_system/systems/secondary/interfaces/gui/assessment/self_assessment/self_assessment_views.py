"""Tk views for self-assessment."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable

from education_system.systems.secondary.domain.assessment.self_assessment import (
    self_assessment as data,
)
from education_system.systems.secondary.domain.assessment.self_assessment.self_assessment import (
    TERMS, STATUSES, MIN_RATING, MAX_RATING,
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
                messagebox.showerror("Self Assessment", str(e),
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


def _assessment_dialog(host, title: str,
                        initial: dict[str, Any] | None = None
                        ) -> dict[str, Any] | None:
    dlg = tk.Toplevel(host.root)
    dlg.title(title)
    dlg.transient(host.root)
    dlg.geometry("560x720")
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
    term_var   = tk.StringVar(value=str(initial.get("term") or "Autumn"))
    date_var   = tk.StringVar(value=str(initial.get("assessment_date")
                                          or ""))
    conf_var   = tk.StringVar(value=str(initial.get("confidence_level")
                                          or ""))
    eff_var    = tk.StringVar(value=str(initial.get("effort_level")
                                          or ""))
    enj_var    = tk.StringVar(value=str(initial.get("enjoyment_level")
                                          or ""))
    status_var = tk.StringVar(value=str(initial.get("status") or "Draft"))
    reviewer_var = tk.StringVar(value=str(initial.get("reviewed_by")
                                             or ""))
    reviewed_date_var = tk.StringVar(value=str(initial.get("reviewed_date")
                                                  or ""))

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
        ("Pupil ID:",      ttk.Entry(frm, textvariable=pupil_var,
                                       width=14)),
        ("Subject:",       ttk.Combobox(frm, textvariable=subject_var,
                                         values=subject_labels,
                                         state="readonly", width=42)),
        ("Academic year:", ttk.Entry(frm, textvariable=ay_var,
                                       width=10)),
        ("Term:",          ttk.Combobox(frm, textvariable=term_var,
                                         values=list(TERMS),
                                         state="readonly", width=10)),
        ("Date:",          ttk.Entry(frm, textvariable=date_var,
                                       width=14)),
        (f"Confidence ({MIN_RATING}-{MAX_RATING}):",
                            ttk.Spinbox(frm, from_=MIN_RATING,
                                          to=MAX_RATING,
                                          textvariable=conf_var,
                                          width=4)),
        (f"Effort ({MIN_RATING}-{MAX_RATING}):",
                            ttk.Spinbox(frm, from_=MIN_RATING,
                                          to=MAX_RATING,
                                          textvariable=eff_var,
                                          width=4)),
        (f"Enjoyment ({MIN_RATING}-{MAX_RATING}):",
                            ttk.Spinbox(frm, from_=MIN_RATING,
                                          to=MAX_RATING,
                                          textvariable=enj_var,
                                          width=4)),
        ("Status:",        ttk.Combobox(frm, textvariable=status_var,
                                         values=list(STATUSES),
                                         state="readonly", width=12)),
        ("Reviewer:",      ttk.Entry(frm, textvariable=reviewer_var,
                                       width=24)),
        ("Reviewed date:", ttk.Entry(frm,
                                       textvariable=reviewed_date_var,
                                       width=14)),
    ]
    for i, (label, widget) in enumerate(rows):
        ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w",
                                         pady=2)
        widget.grid(row=i, column=1, sticky="ew", pady=2)
    frm.columnconfigure(1, weight=1)

    text_fields = [("Strengths:", "strengths", 3),
                   ("Areas to improve:", "areas_to_improve", 3),
                   ("Goals:", "goals", 3),
                   ("Reviewer comments:", "reviewer_comments", 3),
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

    def _parse_subject(label: str) -> str:
        label = (label or "").strip()
        if not label.startswith("#"):
            return ""
        return label.split()[0][1:]

    def _save() -> None:
        nonlocal result
        result = {
            "pupil_id":         pupil_var.get().strip(),
            "subject_id":       _parse_subject(subject_var.get()),
            "academic_year":    ay_var.get().strip(),
            "term":             term_var.get().strip(),
            "assessment_date":  date_var.get().strip(),
            "confidence_level": conf_var.get().strip(),
            "effort_level":     eff_var.get().strip(),
            "enjoyment_level":  enj_var.get().strip(),
            "status":           status_var.get().strip(),
            "reviewed_by":      reviewer_var.get().strip(),
            "reviewed_date":    reviewed_date_var.get().strip(),
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


@_safe_view
def open_self_assessment(host) -> None:
    logger.debug("GUI: open_self_assessment")
    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Self Assessment",
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
    ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 4))
    status_var = tk.StringVar(value="")
    ttk.Combobox(bar, textvariable=status_var,
                 values=["", *STATUSES], state="readonly",
                 width=10).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Apply",
               command=lambda: _refresh()).pack(side="left", padx=2)
    ttk.Button(bar, text="New / update",
               command=lambda: _new(host, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Edit",
               command=lambda: _edit(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Review",
               command=lambda: _review(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Summary",
               command=lambda: _summary(host,
                                          year_var.get().strip() or None,
                                          term_var.get().strip() or None)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Delete",
               command=lambda: _delete(host, tree, on_done=_refresh)
               ).pack(side="left", padx=2)
    ttk.Button(bar, text="Refresh",
               command=lambda: _refresh()).pack(side="left", padx=2)

    cols = ("id", "pupil", "year", "subj", "ay", "term", "date",
            "conf", "eff", "enj", "avg", "status")
    tree = ttk.Treeview(root, columns=cols, show="headings", height=18)
    for c, label, w in [
        ("id", "ID", 50), ("pupil", "Pupil", 90),
        ("year", "Yr", 50), ("subj", "Subj", 70),
        ("ay", "AY", 90), ("term", "Term", 80),
        ("date", "Date", 100),
        ("conf", "Conf", 60), ("eff", "Eff", 50),
        ("enj", "Enj", 50), ("avg", "Avg", 60),
        ("status", "Status", 100),
    ]:
        tree.heading(c, text=label)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    def _refresh() -> None:
        for i in tree.get_children():
            tree.delete(i)
        try:
            rows = data.list_assessments(
                year_group=year_var.get().strip() or None,
                pupil_id=pupil_var.get().strip() or None,
                term=term_var.get().strip() or None,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            messagebox.showerror("Self Assessment", str(e),
                                 parent=host.root)
            return
        except Exception as e:
            logger.exception("self_assessment refresh failed")
            messagebox.showerror("Self Assessment",
                                 f"Could not load:\n\n{e}",
                                 parent=host.root)
            return
        for a in rows:
            avg = (f"{a.average_rating:.2f}"
                   if a.average_rating is not None else "-")
            tree.insert("", "end", iid=str(a.assessment_id), values=(
                a.assessment_id, a.pupil_id, a.pupil_year or "-",
                a.subject_code or "?", a.academic_year, a.term,
                a.assessment_date,
                a.confidence_level if a.confidence_level is not None
                else "-",
                a.effort_level if a.effort_level is not None else "-",
                a.enjoyment_level if a.enjoyment_level is not None
                else "-",
                avg, a.status,
            ))
        try:
            s = data.cohort_summary(
                year_group=year_var.get().strip() or None,
                term=term_var.get().strip() or None)
            summary_var.set(
                f"Records: {s['count']}    "
                f"Conf: "
                f"{s['avg_confidence'] if s['avg_confidence'] is not None else '-'}    "
                f"Eff: "
                f"{s['avg_effort'] if s['avg_effort'] is not None else '-'}    "
                f"Enj: "
                f"{s['avg_enjoyment'] if s['avg_enjoyment'] is not None else '-'}")
        except Exception:
            summary_var.set(f"{len(rows)} assessment(s)")
        host.status_var.set(f"Self Assessment: {len(rows)} record(s)")

    tree.bind("<Double-1>", lambda _e: _edit(host, tree,
                                              on_done=_refresh))
    year_var.trace_add("write", lambda *_: _refresh())
    term_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())
    _refresh()


def _selected_id(tree: ttk.Treeview, host) -> int | None:
    sel = tree.focus()
    if not sel:
        messagebox.showinfo("Self Assessment",
                            "Select a record first.",
                            parent=host.root)
        return None
    try:
        return int(sel)
    except ValueError:
        return None


@_safe_view
def _new(host, *, on_done=None) -> None:
    fields = _assessment_dialog(host, "New / update self-assessment")
    if not fields:
        return
    a = data.upsert(fields)
    messagebox.showinfo(
        "Self Assessment",
        f"Saved {a.pupil_id} / {a.subject_code} "
        f"({a.academic_year} {a.term}) — status {a.status}",
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
        "pupil_id", "subject_id", "academic_year", "term",
        "assessment_date", "confidence_level", "effort_level",
        "enjoyment_level", "strengths", "areas_to_improve",
        "goals", "status", "reviewed_by", "reviewer_comments",
        "reviewed_date", "notes")}
    fields = _assessment_dialog(host, f"Edit #{aid}", initial=initial)
    if not fields:
        return
    data.upsert(fields)
    if on_done:
        on_done()


@_safe_view
def _review(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_id(tree, host)
    if aid is None:
        return
    reviewer = simpledialog.askstring(
        "Review", "Reviewer name:", parent=host.root)
    if not reviewer:
        return
    comments = simpledialog.askstring(
        "Review", "Reviewer comments:", parent=host.root)
    data.set_status(aid, "Reviewed",
                     reviewer=reviewer.strip(),
                     reviewer_comments=(comments or "").strip() or None)
    if on_done:
        on_done()


@_safe_view
def _delete(host, tree: ttk.Treeview, *, on_done=None) -> None:
    aid = _selected_id(tree, host)
    if aid is None:
        return
    existing = data.get(aid)
    if existing is None:
        return
    if not messagebox.askyesno(
            "Delete assessment",
            f"Delete self-assessment for {existing.pupil_id} / "
            f"{existing.subject_code} ({existing.academic_year} "
            f"{existing.term})?",
            parent=host.root):
        return
    data.delete(aid)
    if on_done:
        on_done()


@_safe_view
def _summary(host, year_group: str | None, term: str | None) -> None:
    s = data.cohort_summary(year_group=year_group, term=term)
    lines = [
        f"Records: {s['count']}",
        "",
        f"Avg confidence: "
        f"{s['avg_confidence'] if s['avg_confidence'] is not None else '-'}",
        f"Avg effort:     "
        f"{s['avg_effort'] if s['avg_effort'] is not None else '-'}",
        f"Avg enjoyment:  "
        f"{s['avg_enjoyment'] if s['avg_enjoyment'] is not None else '-'}",
    ]
    if s["by_status"]:
        lines.append("")
        lines.append("By status:")
        for k, v in s["by_status"].items():
            lines.append(f"  {k:<12} {v}")
    if s["by_term"]:
        lines.append("")
        lines.append("By term:")
        for k, v in s["by_term"].items():
            lines.append(f"  {k:<10} {v}")
    messagebox.showinfo("Self Assessment — summary",
                        "\n".join(lines), parent=host.root)
