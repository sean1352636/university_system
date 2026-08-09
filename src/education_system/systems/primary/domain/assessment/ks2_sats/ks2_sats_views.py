"""Tk views for KS2 SATs results."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.systems.primary.domain.assessment.ks2_sats import (
    ks2_sats as data,
)
from education_system.systems.primary.domain.assessment.ks2_sats.ks2_sats import (
    KS2Result, OUTCOMES, OUTCOME_LABELS, SUBJECTS,
    SCALED_SCORE_MAX, SCALED_SCORE_MIN,
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
                messagebox.showerror("KS2 SATs", str(e),
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
def open_ks2_sats(host) -> None:
    logger.debug("GUI: open_ks2_sats")

    win = tk.Toplevel(host.root)
    win.title("KS2 SATs")
    win.transient(host.root)
    win.geometry("1100x620")

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
    ttk.Label(filt, text="Subject:").pack(side="left")
    subj_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=subj_var,
                 values=["All"] + list(SUBJECTS),
                 state="readonly", width=10).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Outcome:").pack(side="left")
    oc_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=oc_var,
                 values=["All"] + list(OUTCOMES),
                 state="readonly", width=8).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Pupil year:").pack(side="left")
    py_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=py_var,
                 values=["All"] + list(YEAR_GROUPS),
                 state="readonly", width=6).pack(side="left", padx=(4, 10))

    cols = ("result_id", "pupil_id", "name", "year", "academic_year",
            "subject", "score", "outcome", "assessed_on")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=15)
    for col, label, width, anchor in [
        ("result_id", "#", 50, "center"),
        ("pupil_id", "Pupil ID", 90, "w"),
        ("name", "Name", 200, "w"),
        ("year", "Yr", 40, "center"),
        ("academic_year", "AcYr", 80, "center"),
        ("subject", "Subject", 110, "w"),
        ("score", "Score", 70, "center"),
        ("outcome", "Outcome", 80, "center"),
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
            subj = None if subj_var.get() == "All" else subj_var.get()
            oc = None if oc_var.get() == "All" else oc_var.get()
            py = None if py_var.get() == "All" else py_var.get()
            rows = data.list_results(academic_year=ay, subject=subj,
                                     outcome=oc, year_group=py)
        except ValidationError as e:
            messagebox.showerror("KS2 SATs", str(e), parent=win)
            return
        except Exception:
            logger.exception("KS2 refresh failed")
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        for iid in tree.get_children():
            tree.delete(iid)
        for rec, p in rows:
            tree.insert("", "end", iid=str(rec.result_id), values=(
                rec.result_id, rec.pupil_id,
                p.full_name if p else "(unknown)",
                p.year_group if p else "-",
                rec.academic_year, rec.subject,
                "" if rec.scaled_score is None else rec.scaled_score,
                rec.outcome, rec.assessed_on or "",
            ))
        try:
            years = data.known_years()
        except Exception:
            years = []
        year_box["values"] = ["All"] + years
        try:
            s = data.summary(academic_year=ay, subject=subj)
        except Exception:
            s = {"total": 0, "by_outcome": {o: 0 for o in OUTCOMES},
                 "at_or_above_exs": 0, "at_or_above_exs_pct": 0.0,
                 "average_scaled": None, "scaled_count": 0}
        parts = [f"Total: {s['total']}"]
        for o in OUTCOMES:
            parts.append(f"{o}: {s['by_outcome'].get(o, 0)}")
        parts.append(f">=EXS: {s['at_or_above_exs']} "
                     f"({s['at_or_above_exs_pct']:.1f}%)")
        if s['average_scaled'] is not None:
            parts.append(f"Avg scaled: {s['average_scaled']:.1f}")
        if ay and not subj:
            try:
                rwm = data.cohort_combined_summary(ay)
                parts.append(f"RWM>=EXS: {rwm['exs_in_RWM']} "
                             f"({rwm['exs_in_RWM_pct']:.1f}%)")
            except Exception:
                logger.exception("cohort_combined_summary failed for %s", ay)
        summary_var.set("   ".join(parts))

    def _selected_id() -> int | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("KS2 SATs", "Select a result first.",
                                parent=win)
            return None
        return int(sel[0])

    def _add() -> None:
        _open_form_dialog(win, result_id=None, on_saved=_refresh)

    def _edit() -> None:
        rid = _selected_id()
        if rid is None:
            return
        _open_form_dialog(win, result_id=rid, on_saved=_refresh)

    def _delete() -> None:
        rid = _selected_id()
        if rid is None:
            return
        if not messagebox.askyesno("Delete result",
                                   f"Delete result #{rid}?", parent=win):
            return
        try:
            data.delete(rid)
        except Exception:
            logger.exception("delete(%s) failed", rid)
            messagebox.showerror("Error", "Could not delete — see logs.",
                                 parent=win)
            return
        _refresh()

    def _outcome_help() -> None:
        msg = "\n".join(f"{o}  —  {OUTCOME_LABELS[o]}" for o in OUTCOMES)
        messagebox.showinfo("KS2 outcomes", msg, parent=win)

    ttk.Button(btns, text="Record", command=_add).pack(side="left")
    ttk.Button(btns, text="Edit", command=_edit).pack(side="left", padx=(8, 0))
    ttk.Button(btns, text="Delete", command=_delete).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Outcome help", command=_outcome_help).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Refresh", command=_refresh).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")

    tree.bind("<Double-Button-1>", lambda _e: _edit())
    for v in (year_var, subj_var, oc_var, py_var):
        v.trace_add("write", lambda *_: _refresh())

    _refresh()


def _open_form_dialog(parent, *, result_id: int | None,
                      on_saved: Callable[[], None]) -> None:
    existing: KS2Result | None = None
    if result_id is not None:
        try:
            existing = data.get(result_id)
        except Exception:
            logger.exception("get(%s) failed", result_id)
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=parent)
            return
        if existing is None:
            messagebox.showerror("KS2 SATs",
                                 f"No result #{result_id}", parent=parent)
            return

    dlg = tk.Toplevel(parent)
    dlg.title("KS2 result" if existing else "New KS2 result")
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

    ttk.Label(frm, text="Subject *").grid(row=2, column=0, sticky="w", pady=3)
    subj_var = tk.StringVar(value=existing.subject if existing else SUBJECTS[0])
    ttk.Combobox(frm, textvariable=subj_var, values=list(SUBJECTS),
                 state="readonly", width=14).grid(
        row=2, column=1, sticky="w", pady=3)

    ttk.Label(frm, text=f"Scaled score {SCALED_SCORE_MIN}-{SCALED_SCORE_MAX}").grid(
        row=3, column=0, sticky="w", pady=3)
    score_var = tk.StringVar(
        value="" if not existing or existing.scaled_score is None
        else str(existing.scaled_score))
    ttk.Entry(frm, textvariable=score_var, width=8).grid(
        row=3, column=1, sticky="w", pady=3)
    suggest_var = tk.StringVar(value="")
    ttk.Label(frm, textvariable=suggest_var,
              foreground="#888").grid(row=3, column=2, sticky="w", padx=(8, 0))

    ttk.Label(frm, text="Outcome *").grid(row=4, column=0, sticky="w", pady=3)
    oc_var = tk.StringVar(
        value=existing.outcome if existing else "EXS")
    ttk.Combobox(frm, textvariable=oc_var, values=list(OUTCOMES),
                 state="readonly", width=8).grid(
        row=4, column=1, sticky="w", pady=3)

    def _on_score_change(*_a) -> None:
        raw = score_var.get().strip()
        if not raw.isdigit():
            suggest_var.set("")
            return
        sug = data.suggest_outcome(int(raw))
        suggest_var.set(f"suggested: {sug}" if sug else "")
    score_var.trace_add("write", _on_score_change)
    _on_score_change()

    ttk.Label(frm, text="Assessed on (YYYY-MM-DD)").grid(
        row=5, column=0, sticky="w", pady=3)
    date_var = tk.StringVar(value=existing.assessed_on or "" if existing else "")
    ttk.Entry(frm, textvariable=date_var, width=14).grid(
        row=5, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Notes").grid(row=6, column=0, sticky="w", pady=3)
    notes_var = tk.StringVar(value=existing.notes or "" if existing else "")
    ttk.Entry(frm, textvariable=notes_var, width=30).grid(
        row=6, column=1, columnspan=2, sticky="ew", pady=3)
    frm.columnconfigure(2, weight=1)

    def _save() -> None:
        payload = {
            "pupil_id": pupil_var.get(),
            "academic_year": ay_var.get(),
            "subject": subj_var.get(),
            "scaled_score": score_var.get(),
            "outcome": oc_var.get(),
            "assessed_on": date_var.get(),
            "notes": notes_var.get(),
        }
        try:
            if existing is None:
                data.create(payload)
            else:
                data.update(existing.result_id, payload)
        except ValidationError as e:
            messagebox.showerror("KS2 SATs", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("save KS2 failed")
            messagebox.showerror("Error", "Could not save — see logs.",
                                 parent=dlg)
            return
        on_saved()
        dlg.destroy()

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(14, 0))
    ttk.Button(btn_row, text="Save", command=_save).pack(side="right")
    ttk.Button(btn_row, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))
