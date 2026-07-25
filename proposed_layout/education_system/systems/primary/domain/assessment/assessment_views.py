"""Tk views for assessment records."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.systems.primary.domain.assessment import (
    assessment as data,
)
from education_system.systems.primary.domain.assessment.assessment import (
    AssessmentRecord, GRADES, GRADE_LABELS, TERMS,
)
from education_system.systems.primary.domain.learners.pupils import (
    pupils as pupils_data,
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
                messagebox.showerror("Assessment", str(e),
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


@_safe_view
def open_assessment(host) -> None:
    logger.debug("GUI: open_assessment")

    win = tk.Toplevel(host.root)
    win.title("Assessment Records")
    win.transient(host.root)
    win.geometry("1080x620")

    top = ttk.Frame(win, padding=10)
    top.pack(fill="x")
    summary_var = tk.StringVar()
    ttk.Label(top, textvariable=summary_var,
              font=("Segoe UI", 10, "bold")).pack(side="left")

    filt = ttk.Frame(win, padding=(10, 0, 10, 6))
    filt.pack(fill="x")
    ttk.Label(filt, text="Year:").pack(side="left")
    year_var = tk.StringVar(value="All")
    year_box = ttk.Combobox(filt, textvariable=year_var,
                            values=["All"], state="readonly", width=10)
    year_box.pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Term:").pack(side="left")
    term_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=term_var,
                 values=["All"] + list(TERMS),
                 state="readonly", width=8).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Subject:").pack(side="left")
    subject_var = tk.StringVar(value="All")
    subject_box = ttk.Combobox(filt, textvariable=subject_var,
                               values=["All"], state="readonly", width=18)
    subject_box.pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Grade:").pack(side="left")
    grade_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=grade_var,
                 values=["All"] + list(GRADES),
                 state="readonly", width=6).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Pupil year:").pack(side="left")
    py_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=py_var,
                 values=["All"] + list(YEAR_GROUPS),
                 state="readonly", width=6).pack(side="left", padx=(4, 10))

    cols = ("assessment_id", "pupil_id", "name", "year", "academic_year",
            "term", "subject", "grade", "score", "assessed_on")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=15)
    for col, label, width, anchor in [
        ("assessment_id", "#", 50, "center"),
        ("pupil_id", "Pupil ID", 90, "w"),
        ("name", "Name", 180, "w"),
        ("year", "Yr", 40, "center"),
        ("academic_year", "AcYr", 80, "center"),
        ("term", "Term", 70, "center"),
        ("subject", "Subject", 160, "w"),
        ("grade", "Grade", 60, "center"),
        ("score", "Score", 70, "center"),
        ("assessed_on", "Assessed", 100, "center"),
    ]:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor=anchor)
    tree.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    btns = ttk.Frame(win, padding=10)
    btns.pack(fill="x")

    def _refresh() -> None:
        try:
            ay = None if year_var.get() == "All" else year_var.get()
            term = None if term_var.get() == "All" else term_var.get()
            subj = None if subject_var.get() == "All" else subject_var.get()
            grade = None if grade_var.get() == "All" else grade_var.get()
            py = None if py_var.get() == "All" else py_var.get()
            rows = data.list_records(academic_year=ay, term=term,
                                     subject=subj, grade=grade,
                                     year_group=py)
        except ValidationError as e:
            messagebox.showerror("Assessment", str(e), parent=win)
            return
        except Exception:
            logger.exception("assessment refresh failed")
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        for iid in tree.get_children():
            tree.delete(iid)
        for rec, p in rows:
            tree.insert("", "end", iid=str(rec.assessment_id), values=(
                rec.assessment_id, rec.pupil_id,
                p.full_name if p else "(unknown)",
                p.year_group if p else "-",
                rec.academic_year, rec.term, rec.subject, rec.grade,
                "" if rec.score is None else f"{rec.score:g}",
                rec.assessed_on or "",
            ))
        try:
            years = data.known_years()
            subjects = data.known_subjects()
        except Exception:
            years, subjects = [], []
        year_box["values"] = ["All"] + years
        subject_box["values"] = ["All"] + subjects
        try:
            s = data.grade_summary(academic_year=ay, term=term, subject=subj)
        except Exception:
            s = {"total": 0, "by_grade": {g: 0 for g in GRADES},
                 "at_or_above_exs": 0, "at_or_above_exs_pct": 0.0,
                 "average_score": None}
        parts = [f"Total: {s['total']}"]
        for g in GRADES:
            parts.append(f"{g}: {s['by_grade'].get(g, 0)}")
        parts.append(f">=EXS: {s['at_or_above_exs']} "
                     f"({s['at_or_above_exs_pct']:.1f}%)")
        if s['average_score'] is not None:
            parts.append(f"Avg score: {s['average_score']:.1f}")
        summary_var.set("   ".join(parts))

    def _selected_id() -> int | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Assessment", "Select a record first.",
                                parent=win)
            return None
        return int(sel[0])

    def _add() -> None:
        _open_form_dialog(win, assessment_id=None, on_saved=_refresh)

    def _edit() -> None:
        aid = _selected_id()
        if aid is None:
            return
        _open_form_dialog(win, assessment_id=aid, on_saved=_refresh)

    def _delete() -> None:
        aid = _selected_id()
        if aid is None:
            return
        if not messagebox.askyesno("Delete record",
                                   f"Delete record #{aid}?", parent=win):
            return
        try:
            data.delete(aid)
        except Exception:
            logger.exception("delete(%s) failed", aid)
            messagebox.showerror("Error", "Could not delete — see logs.",
                                 parent=win)
            return
        _refresh()

    def _grade_help() -> None:
        msg = "\n".join(f"{g}  —  {GRADE_LABELS[g]}" for g in GRADES)
        messagebox.showinfo("Attainment grades", msg, parent=win)

    ttk.Button(btns, text="Record", command=_add).pack(side="left")
    ttk.Button(btns, text="Edit", command=_edit).pack(side="left", padx=(8, 0))
    ttk.Button(btns, text="Delete", command=_delete).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Grade help", command=_grade_help).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Refresh", command=_refresh).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")

    tree.bind("<Double-Button-1>", lambda _e: _edit())
    for v in (year_var, term_var, subject_var, grade_var, py_var):
        v.trace_add("write", lambda *_: _refresh())

    _refresh()


def _open_form_dialog(parent, *, assessment_id: int | None,
                      on_saved: Callable[[], None]) -> None:
    existing: AssessmentRecord | None = None
    if assessment_id is not None:
        try:
            existing = data.get(assessment_id)
        except Exception:
            logger.exception("get(%s) failed", assessment_id)
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=parent)
            return
        if existing is None:
            messagebox.showerror("Assessment",
                                 f"No record #{assessment_id}", parent=parent)
            return

    dlg = tk.Toplevel(parent)
    dlg.title("Record" if existing else "New record")
    dlg.transient(parent)
    dlg.geometry("500x440")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    pupil_var = tk.StringVar(value=existing.pupil_id if existing else "")
    pupil_label = tk.StringVar(value="")
    ttk.Label(frm, text="Pupil ID *").grid(row=0, column=0, sticky="w", pady=3)
    ttk.Entry(frm, textvariable=pupil_var, width=14).grid(
        row=0, column=1, sticky="w", pady=3)
    ttk.Label(frm, textvariable=pupil_label, foreground="#666").grid(
        row=0, column=2, sticky="w", padx=(8, 0))

    def _lookup_pupil(*_a) -> None:
        pid = pupil_var.get().strip()
        if not pid:
            pupil_label.set("")
            return
        try:
            p = pupils_data.get_pupil(pid)
        except Exception:
            pupil_label.set("(error)")
            return
        pupil_label.set(
            f"{p.full_name} (year {p.year_group})" if p else "(unknown)")
    pupil_var.trace_add("write", _lookup_pupil)
    _lookup_pupil()

    ttk.Label(frm, text="Academic year *").grid(
        row=1, column=0, sticky="w", pady=3)
    ay_var = tk.StringVar(value=existing.academic_year if existing else "")
    ttk.Entry(frm, textvariable=ay_var, width=14).grid(
        row=1, column=1, sticky="w", pady=3)
    ttk.Label(frm, text="e.g. 2025-26", foreground="#888").grid(
        row=1, column=2, sticky="w", padx=(8, 0))

    ttk.Label(frm, text="Term *").grid(row=2, column=0, sticky="w", pady=3)
    term_var = tk.StringVar(value=existing.term if existing else TERMS[0])
    ttk.Combobox(frm, textvariable=term_var, values=list(TERMS),
                 state="readonly", width=10).grid(
        row=2, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Subject *").grid(row=3, column=0, sticky="w", pady=3)
    subj_var = tk.StringVar(value=existing.subject if existing else "")
    try:
        known = data.known_subjects()
    except Exception:
        known = []
    ttk.Combobox(frm, textvariable=subj_var, values=known,
                 width=28).grid(row=3, column=1, columnspan=2,
                                sticky="ew", pady=3)

    ttk.Label(frm, text="Grade *").grid(row=4, column=0, sticky="w", pady=3)
    grade_var = tk.StringVar(value=existing.grade if existing else GRADES[2])
    ttk.Combobox(frm, textvariable=grade_var, values=list(GRADES),
                 state="readonly", width=8).grid(
        row=4, column=1, sticky="w", pady=3)
    ttk.Label(frm, text="(BLW < WTS < EXS < GDS)",
              foreground="#888").grid(row=4, column=2, sticky="w", padx=(8, 0))

    ttk.Label(frm, text="Score 0–100").grid(
        row=5, column=0, sticky="w", pady=3)
    score_var = tk.StringVar(
        value="" if not existing or existing.score is None
        else f"{existing.score:g}")
    ttk.Entry(frm, textvariable=score_var, width=8).grid(
        row=5, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Assessed on (YYYY-MM-DD)").grid(
        row=6, column=0, sticky="w", pady=3)
    date_var = tk.StringVar(value=existing.assessed_on if existing else "")
    ttk.Entry(frm, textvariable=date_var, width=14).grid(
        row=6, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Comment").grid(row=7, column=0, sticky="w", pady=3)
    comment_var = tk.StringVar(value=existing.comment if existing else "")
    ttk.Entry(frm, textvariable=comment_var, width=30).grid(
        row=7, column=1, columnspan=2, sticky="ew", pady=3)
    frm.columnconfigure(2, weight=1)

    def _save() -> None:
        payload = {
            "pupil_id": pupil_var.get(),
            "academic_year": ay_var.get(),
            "term": term_var.get(),
            "subject": subj_var.get(),
            "grade": grade_var.get(),
            "score": score_var.get(),
            "assessed_on": date_var.get(),
            "comment": comment_var.get(),
        }
        try:
            if existing is None:
                data.create(payload)
            else:
                data.update(existing.assessment_id, payload)
        except ValidationError as e:
            messagebox.showerror("Assessment", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("save assessment failed")
            messagebox.showerror("Error", "Could not save — see logs.",
                                 parent=dlg)
            return
        on_saved()
        dlg.destroy()

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(14, 0))
    ttk.Button(btn_row, text="Save", command=_save).pack(side="right")
    ttk.Button(btn_row, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))
