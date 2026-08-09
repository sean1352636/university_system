"""Tk views for progress reporting."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from education_system.systems.primary.domain.operations.reporting.progress_report import (
    progress_report as data,
)
from education_system.systems.primary.domain.assessment.assessment import (
    GRADES,
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
                messagebox.showerror("Progress Report", str(e),
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
def open_progress_report(host) -> None:
    logger.debug("GUI: open_progress_report")

    win = tk.Toplevel(host.root)
    win.title("Progress Report")
    win.transient(host.root)
    win.geometry("1200x680")

    top = ttk.Frame(win, padding=10)
    top.pack(fill="x")
    ttk.Label(top, text="Progress Report",
              font=("Segoe UI", 13, "bold")).pack(side="left")

    filt = ttk.Frame(win, padding=(10, 0, 10, 6))
    filt.pack(fill="x")
    ttk.Label(filt, text="Academic year:").pack(side="left")
    year_var = tk.StringVar(value="All")
    year_box = ttk.Combobox(filt, textvariable=year_var,
                            values=["All"], state="readonly", width=10)
    year_box.pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Year group:").pack(side="left")
    yg_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=yg_var,
                 values=["All"] + list(YEAR_GROUPS),
                 state="readonly", width=6).pack(side="left", padx=(4, 10))

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    overview_tab = ttk.Frame(nb, padding=10)
    subjects_tab = ttk.Frame(nb, padding=10)
    pupils_tab = ttk.Frame(nb, padding=10)
    nb.add(overview_tab, text="Cohort overview")
    nb.add(subjects_tab, text="Subjects")
    nb.add(pupils_tab, text="Pupils")

    # --- Overview tab ---------------------------------------------------
    overview_body = tk.Text(overview_tab, wrap="word", height=22)
    overview_body.pack(fill="both", expand=True)
    overview_body.config(state="disabled")

    # --- Subjects tab ---------------------------------------------------
    cols_s = ("subject", "total", *GRADES, "exs_plus", "exs_plus_pct")
    stree = ttk.Treeview(subjects_tab, columns=cols_s, show="headings",
                         height=18)
    headings = [("subject", "Subject", 220, "w"),
                ("total", "Total", 70, "center")]
    for g in GRADES:
        headings.append((g, g, 60, "center"))
    headings.append(("exs_plus", ">=EXS", 80, "center"))
    headings.append(("exs_plus_pct", "% >=EXS", 80, "center"))
    for col, label, width, anchor in headings:
        stree.heading(col, text=label)
        stree.column(col, width=width, anchor=anchor)
    stree.pack(fill="both", expand=True)

    # --- Pupils tab -----------------------------------------------------
    p_cols = ("pupil_id", "name", "year", "data_points")
    ptree = ttk.Treeview(pupils_tab, columns=p_cols, show="headings",
                         height=18)
    for col, label, width, anchor in [
        ("pupil_id", "Pupil ID", 100, "w"),
        ("name", "Name", 280, "w"),
        ("year", "Year", 70, "center"),
        ("data_points", "Data points", 110, "center"),
    ]:
        ptree.heading(col, text=label)
        ptree.column(col, width=width, anchor=anchor)
    ptree.pack(fill="both", expand=True)

    p_btns = ttk.Frame(pupils_tab, padding=(0, 6, 0, 0))
    p_btns.pack(fill="x")

    def _refresh() -> None:
        ay = None if year_var.get() == "All" else year_var.get()
        yg = None if yg_var.get() == "All" else yg_var.get()
        # Overview
        try:
            cs = data.cohort_overview(academic_year=ay)
        except Exception:
            logger.exception("cohort_overview failed")
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        overview_body.config(state="normal")
        overview_body.delete("1.0", "end")
        _write_overview(overview_body, cs)
        overview_body.config(state="disabled")
        # Subjects
        try:
            by_subj = data.cohort_subject_summary(
                academic_year=ay, year_group=yg)
        except ValidationError as e:
            messagebox.showerror("Progress Report", str(e), parent=win)
            return
        except Exception:
            logger.exception("subject summary failed")
            by_subj = {}
        for iid in stree.get_children():
            stree.delete(iid)
        for subj in sorted(by_subj):
            bucket = by_subj[subj]
            values = [subj, bucket["total"]]
            values.extend(bucket.get(g, 0) for g in GRADES)
            values.extend([bucket["exs_plus"],
                           f"{bucket['exs_plus_pct']:.1f}"])
            stree.insert("", "end", values=values)
        # Pupils
        try:
            pupil_rows = data.find_pupils_with_data(year_group=yg,
                                                    academic_year=ay)
        except ValidationError as e:
            messagebox.showerror("Progress Report", str(e), parent=win)
            return
        except Exception:
            logger.exception("find_pupils_with_data failed")
            pupil_rows = []
        for iid in ptree.get_children():
            ptree.delete(iid)
        for p, n in pupil_rows:
            ptree.insert("", "end", iid=p.pupil_id, values=(
                p.pupil_id, p.full_name, p.year_group, n,
            ))
        # Refresh year list
        from education_system.systems.primary.domain.assessment import (
            assessment as assessment_data,
        )
        try:
            years = assessment_data.known_years()
        except Exception:
            years = []
        year_box["values"] = ["All"] + years

    def _open_pupil() -> None:
        sel = ptree.selection()
        if not sel:
            messagebox.showinfo("Progress Report",
                                "Select a pupil first.", parent=win)
            return
        _open_pupil_dialog(win, sel[0])

    def _open_pupil_by_id() -> None:
        from tkinter import simpledialog
        pid = simpledialog.askstring("Open pupil",
                                     "Pupil ID:", parent=win)
        if not pid:
            return
        _open_pupil_dialog(win, pid.strip())

    def _export() -> None:
        path = filedialog.asksaveasfilename(
            parent=win, title="Export cohort progress CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        ay = None if year_var.get() == "All" else year_var.get()
        yg = None if yg_var.get() == "All" else yg_var.get()
        try:
            n = data.export_cohort_csv(Path(path),
                                       academic_year=ay, year_group=yg)
        except ValidationError as e:
            messagebox.showerror("Progress Report", str(e), parent=win)
            return
        except Exception:
            logger.exception("export_cohort_csv failed")
            messagebox.showerror("Error", "Could not export — see logs.",
                                 parent=win)
            return
        messagebox.showinfo("Progress Report",
                            f"Wrote {n} pupil row(s) to:\n{path}",
                            parent=win)

    ttk.Button(p_btns, text="Open pupil progress...",
               command=_open_pupil).pack(side="left")
    ttk.Button(p_btns, text="Open by ID...",
               command=_open_pupil_by_id).pack(side="left", padx=(8, 0))
    ttk.Button(p_btns, text="Export cohort CSV...",
               command=_export).pack(side="left", padx=(8, 0))
    ptree.bind("<Double-Button-1>", lambda _e: _open_pupil())

    bottom = ttk.Frame(win, padding=10)
    bottom.pack(fill="x")
    ttk.Button(bottom, text="Refresh", command=_refresh).pack(side="left")
    ttk.Button(bottom, text="Close", command=win.destroy).pack(side="right")

    year_var.trace_add("write", lambda *_: _refresh())
    yg_var.trace_add("write", lambda *_: _refresh())

    _refresh()


def _write_overview(text: tk.Text, s: dict) -> None:
    text.tag_configure("h", font=("Segoe UI", 10, "bold"),
                       spacing1=4, spacing3=2)
    label_year = s.get("academic_year") or "all years"
    text.insert("end", f"Cohort overview — {label_year}\n", "h")

    a = s.get("assessment", {})
    text.insert("end", "\nAssessment records\n", "h")
    text.insert("end",
        f"  Total: {a.get('total', 0)}\n"
        f"  >=EXS: {a.get('at_or_above_exs', 0)} "
        f"({a.get('at_or_above_exs_pct', 0.0):.1f}%)\n")
    if a.get("by_grade"):
        for g in GRADES:
            text.insert("end", f"  {g}: {a['by_grade'].get(g, 0)}\n")

    ks1 = s.get("ks1", {})
    if ks1:
        text.insert("end", "\nKS1 SATs\n", "h")
        text.insert("end",
            f"  Total: {ks1.get('total', 0)}   "
            f">=EXS: {ks1.get('at_or_above_exs', 0)} "
            f"({ks1.get('at_or_above_exs_pct', 0.0):.1f}%)\n")
    ks2 = s.get("ks2", {})
    if ks2:
        text.insert("end", "\nKS2 SATs\n", "h")
        text.insert("end",
            f"  Total: {ks2.get('total', 0)}   "
            f">=EXS: {ks2.get('at_or_above_exs', 0)} "
            f"({ks2.get('at_or_above_exs_pct', 0.0):.1f}%)\n")
        rwm = s.get("ks2_rwm", {})
        if rwm:
            text.insert("end",
                f"  RWM combined: {rwm.get('exs_in_RWM', 0)} of "
                f"{rwm.get('pupils_recorded', 0)} "
                f"({rwm.get('exs_in_RWM_pct', 0.0):.1f}%)\n")
    mtc = s.get("mtc", {})
    if mtc:
        text.insert("end", "\nMultiplication Tables Check\n", "h")
        text.insert("end",
            f"  Year: {mtc.get('academic_year', '-')}   "
            f"total: {mtc.get('total', 0)}   "
            f"avg: {mtc.get('average_score', 0.0):.1f}/25   "
            f"met expected: {mtc.get('met_pct', 0.0):.1f}%   "
            f"full marks: {mtc.get('full_marks', 0)}\n")
    ps = s.get("phonics_screening", {})
    if ps:
        text.insert("end", "\nPhonics screening (Year 1)\n", "h")
        text.insert("end",
            f"  Year: {ps.get('academic_year', '-')}   "
            f"total: {ps.get('total', 0)}   "
            f"passed: {ps.get('passed', 0)}   "
            f"pass rate: {ps.get('pass_rate', 0.0):.1f}%   "
            f"avg: {ps.get('average_score', 0.0):.1f}/40\n")
    eyfs = s.get("eyfs_gld", {})
    if eyfs:
        text.insert("end", "\nEYFS profile\n", "h")
        text.insert("end",
            f"  Year: {eyfs.get('academic_year', '-')}   "
            f"pupils with records: {eyfs.get('pupils', 0)}   "
            f"GLD: {eyfs.get('gld_count', 0)} "
            f"({eyfs.get('gld_pct', 0.0):.1f}%)\n")


def _open_pupil_dialog(parent, pupil_id: str) -> None:
    try:
        pp = data.pupil_progress(pupil_id)
    except ValidationError as e:
        messagebox.showerror("Progress Report", str(e), parent=parent)
        return
    except Exception:
        logger.exception("pupil_progress(%s) failed", pupil_id)
        messagebox.showerror("Error", "Could not load — see logs.",
                             parent=parent)
        return
    p = pp.pupil

    dlg = tk.Toplevel(parent)
    dlg.title(f"Progress — {p.full_name}")
    dlg.transient(parent)
    dlg.geometry("820x680")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm,
              text=f"{p.full_name}  ({p.pupil_id}, year {p.year_group})",
              font=("Segoe UI", 12, "bold")).pack(anchor="w")
    ttk.Label(frm,
              text=f"Data points across modules: {pp.total_data_points}",
              foreground="#666").pack(anchor="w", pady=(2, 8))

    text = tk.Text(frm, wrap="word")
    text.pack(fill="both", expand=True)
    text.tag_configure("h", font=("Segoe UI", 10, "bold"),
                       spacing1=6, spacing3=2)

    def _section(title: str) -> None:
        text.insert("end", f"{title}\n", "h")

    if pp.assessments:
        _section(f"Assessment records ({len(pp.assessments)})")
        for r in pp.assessments[:30]:
            score = "-" if r.score is None else f"{r.score:g}"
            text.insert("end",
                f"  {r.academic_year} {r.term}  {r.subject}: "
                f"{r.grade}  score={score}\n")
        if len(pp.assessments) > 30:
            text.insert("end",
                f"  (+{len(pp.assessments) - 30} more — see Assessment "
                f"Records)\n")
        text.insert("end", "\n")

    if pp.mtc_results:
        _section(f"Multiplication Tables Check ({len(pp.mtc_results)})")
        for r in pp.mtc_results:
            tag = ("FULL" if r.full_marks
                   else "met" if r.met_expected else "below")
            text.insert("end",
                f"  {r.academic_year}: {r.score}/25 ({tag})\n")
        text.insert("end", "\n")

    if pp.phonics_screening:
        _section(f"Phonics screening ({len(pp.phonics_screening)})")
        for r in pp.phonics_screening:
            text.insert("end",
                f"  {r.academic_year} attempt {r.attempt}: "
                f"{r.score}/40 "
                f"({'pass' if r.passed else 'fail'})\n")
        text.insert("end", "\n")

    if pp.phonics_record:
        _section("Phonics (current)")
        rec = pp.phonics_record
        text.insert("end",
            f"  Phase {rec.phase} ({rec.status})  "
            f"last assessed {rec.last_assessed or '-'}\n\n")

    if pp.reading_record:
        _section("Reading levels (current)")
        rec = pp.reading_record
        text.insert("end",
            f"  Band: {rec.band} ({rec.status})  "
            f"last assessed {rec.last_assessed or '-'}\n")
        if rec.book_title:
            text.insert("end", f"  Current book: {rec.book_title}\n")
        text.insert("end", "\n")

    if pp.eyfs_profiles:
        _section(f"EYFS profile ({len(pp.eyfs_profiles)} year(s))")
        for ay, prof in pp.eyfs_profiles:
            text.insert("end",
                f"  {ay}: ELGs {prof.elgs_recorded}/{prof.elgs_total}, "
                f"Expected: {prof.expected_count}, "
                f"GLD: {'YES' if prof.has_gld else 'no'}\n")
        text.insert("end", "\n")

    if pp.ks1_results:
        _section(f"KS1 SATs ({len(pp.ks1_results)})")
        for r in pp.ks1_results:
            score = r.scaled_score if r.scaled_score is not None else "-"
            text.insert("end",
                f"  {r.academic_year} {r.subject}: "
                f"{r.outcome} (scaled={score})\n")
        text.insert("end", "\n")

    if pp.ks2_results:
        _section(f"KS2 SATs ({len(pp.ks2_results)})")
        for r in pp.ks2_results:
            score = r.scaled_score if r.scaled_score is not None else "-"
            text.insert("end",
                f"  {r.academic_year} {r.subject}: "
                f"{r.outcome} (scaled={score})\n")
        text.insert("end", "\n")

    if pp.targets:
        _section(f"Targets ({len(pp.targets)})")
        for t in pp.targets:
            text.insert("end",
                f"  {t.academic_year} {t.subject}: {t.target_grade} "
                f"— status: {t.status}\n")
        text.insert("end", "\n")

    if pp.total_data_points == 0:
        text.insert("end", "(no data on record)\n")

    text.config(state="disabled")

    ttk.Button(frm, text="Close",
               command=dlg.destroy).pack(anchor="e", pady=(10, 0))
