"""Tk views for phonics tracking in the Primary School System."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.systems.primary.domain.assessment.phonics import (
    phonics as data,
)
from education_system.systems.primary.domain.assessment.phonics.phonics import (
    PHASES, PHASE_LABELS, STATUSES,
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
                messagebox.showerror("Phonics", str(e),
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
def open_phonics(host) -> None:
    logger.debug("GUI: open_phonics")

    win = tk.Toplevel(host.root)
    win.title("Phonics Tracking")
    win.transient(host.root)
    win.geometry("960x560")

    top = ttk.Frame(win, padding=10)
    top.pack(fill="x")
    summary_var = tk.StringVar()
    ttk.Label(top, textvariable=summary_var,
              font=("Segoe UI", 10, "bold")).pack(side="left")

    filt = ttk.Frame(win, padding=(10, 0, 10, 6))
    filt.pack(fill="x")
    ttk.Label(filt, text="Year:").pack(side="left")
    year_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=year_var,
                 values=["All"] + list(YEAR_GROUPS),
                 state="readonly", width=6).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Phase:").pack(side="left")
    phase_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=phase_var,
                 values=["All"] + list(PHASES),
                 state="readonly", width=6).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Status:").pack(side="left")
    status_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=status_var,
                 values=["All"] + list(STATUSES),
                 state="readonly", width=10).pack(side="left", padx=(4, 12))

    cols = ("pupil_id", "name", "year", "phase", "status", "last_assessed")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=15)
    for col, label, width, anchor in [
        ("pupil_id", "Pupil ID", 90, "w"),
        ("name", "Name", 240, "w"),
        ("year", "Year", 60, "center"),
        ("phase", "Phase", 70, "center"),
        ("status", "Status", 80, "w"),
        ("last_assessed", "Last assessed", 110, "center"),
    ]:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor=anchor)
    tree.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    btns = ttk.Frame(win, padding=10)
    btns.pack(fill="x")

    def _refresh() -> None:
        try:
            y = None if year_var.get() == "All" else year_var.get()
            p = None if phase_var.get() == "All" else phase_var.get()
            s = None if status_var.get() == "All" else status_var.get()
            rows = data.list_records(year_group=y, phase=p, status=s)
        except ValidationError as e:
            messagebox.showerror("Phonics", str(e), parent=win)
            return
        except Exception:
            logger.exception("phonics refresh failed")
            messagebox.showerror("Error",
                                 "Could not load phonics — see logs.",
                                 parent=win)
            return
        for iid in tree.get_children():
            tree.delete(iid)
        for pupil, rec in rows:
            tree.insert("", "end", iid=pupil.pupil_id, values=(
                pupil.pupil_id, pupil.full_name, pupil.year_group,
                rec.phase if rec else "-",
                rec.status if rec else "-",
                (rec.last_assessed if rec else "") or "-",
            ))
        try:
            counts = data.phase_summary()
        except Exception:
            counts = {ph: 0 for ph in PHASES}
        total = sum(counts.values())
        summary_var.set(
            f"Tracked: {total}   " + "   ".join(
                f"P{ph}: {counts[ph]}" for ph in PHASES))

    def _selected() -> str | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Phonics", "Select a pupil first.", parent=win)
            return None
        return sel[0]

    def _record() -> None:
        pid = _selected()
        if pid is None:
            return
        _open_record_dialog(win, pid, _refresh)

    def _view() -> None:
        pid = _selected()
        if pid is None:
            return
        _open_pupil_dialog(win, pid, _refresh)

    def _clear() -> None:
        pid = _selected()
        if pid is None:
            return
        if not messagebox.askyesno(
                "Clear record",
                f"Clear current phonics record for {pid}? "
                f"(History will be kept.)",
                parent=win):
            return
        try:
            data.clear_pupil(pid)
        except Exception:
            logger.exception("clear_pupil(%s) failed", pid)
            messagebox.showerror("Error", "Could not clear — see logs.",
                                 parent=win)
            return
        _refresh()

    ttk.Button(btns, text="Record assessment...", command=_record).pack(
        side="left")
    ttk.Button(btns, text="View / history...", command=_view).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Clear current", command=_clear).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Refresh", command=_refresh).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")

    tree.bind("<Double-Button-1>", lambda _e: _view())
    year_var.trace_add("write", lambda *_: _refresh())
    phase_var.trace_add("write", lambda *_: _refresh())
    status_var.trace_add("write", lambda *_: _refresh())

    _refresh()


def _open_record_dialog(parent, pupil_id: str,
                        on_saved: Callable[[], None]) -> None:
    pupil = pupils_data.get_pupil(pupil_id)
    if pupil is None:
        messagebox.showerror("Phonics", f"No pupil with id {pupil_id}",
                             parent=parent)
        return
    existing = None
    try:
        existing = data.get_record(pupil_id)
    except Exception:
        logger.exception("get_record(%s) failed", pupil_id)

    dlg = tk.Toplevel(parent)
    dlg.title(f"Record phonics — {pupil.full_name}")
    dlg.transient(parent)
    dlg.geometry("440x340")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm,
              text=f"{pupil.full_name}  ({pupil.pupil_id}, year {pupil.year_group})",
              font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))
    if existing is not None:
        ttk.Label(frm,
                  text=f"Current: phase {existing.phase} ({existing.status}), "
                       f"last {existing.last_assessed or '-'}",
                  foreground="#666").pack(anchor="w", pady=(0, 8))

    grid = ttk.Frame(frm)
    grid.pack(fill="x")
    ttk.Label(grid, text="Phase *").grid(row=0, column=0, sticky="w", pady=4)
    phase_var = tk.StringVar(value=existing.phase if existing else PHASES[0])
    ttk.Combobox(grid, textvariable=phase_var, values=list(PHASES),
                 state="readonly", width=10).grid(row=0, column=1, sticky="w", pady=4)
    ttk.Label(grid, text="Status *").grid(row=1, column=0, sticky="w", pady=4)
    status_var = tk.StringVar(value=existing.status if existing else "working")
    ttk.Combobox(grid, textvariable=status_var, values=list(STATUSES),
                 state="readonly", width=10).grid(row=1, column=1, sticky="w", pady=4)
    ttk.Label(grid, text="Assessed on (YYYY-MM-DD)").grid(
        row=2, column=0, sticky="w", pady=4)
    date_var = tk.StringVar()
    ttk.Entry(grid, textvariable=date_var, width=14).grid(
        row=2, column=1, sticky="w", pady=4)
    ttk.Label(grid, text="Notes").grid(row=3, column=0, sticky="w", pady=4)
    notes_var = tk.StringVar()
    ttk.Entry(grid, textvariable=notes_var, width=30).grid(
        row=3, column=1, sticky="ew", pady=4)
    grid.columnconfigure(1, weight=1)

    def _save() -> None:
        try:
            data.record_assessment(pupil_id, {
                "phase": phase_var.get(),
                "status": status_var.get(),
                "assessed_on": date_var.get(),
                "notes": notes_var.get(),
            })
        except ValidationError as e:
            messagebox.showerror("Phonics", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("record_assessment failed for %s", pupil_id)
            messagebox.showerror("Error",
                                 "Could not save — see logs.", parent=dlg)
            return
        on_saved()
        dlg.destroy()

    btn_row = ttk.Frame(frm)
    btn_row.pack(fill="x", pady=(14, 0))
    ttk.Button(btn_row, text="Save", command=_save).pack(side="right")
    ttk.Button(btn_row, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))


def _open_pupil_dialog(parent, pupil_id: str,
                       on_saved: Callable[[], None]) -> None:
    pupil = pupils_data.get_pupil(pupil_id)
    if pupil is None:
        messagebox.showerror("Phonics", f"No pupil with id {pupil_id}",
                             parent=parent)
        return
    try:
        rec = data.get_record(pupil_id)
        history = data.list_history(pupil_id)
    except Exception:
        logger.exception("loading pupil %s phonics failed", pupil_id)
        messagebox.showerror("Error",
                             "Could not load — see logs.", parent=parent)
        return

    dlg = tk.Toplevel(parent)
    dlg.title(f"Phonics — {pupil.full_name}")
    dlg.transient(parent)
    dlg.geometry("620x520")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm,
              text=f"{pupil.full_name}  ({pupil.pupil_id}, year {pupil.year_group})",
              font=("Segoe UI", 11, "bold")).pack(anchor="w")
    if rec is None:
        ttk.Label(frm, text="No phonics record yet.",
                  foreground="#666").pack(anchor="w", pady=(2, 8))
    else:
        ttk.Label(frm,
                  text=f"Current phase: {rec.phase} ({rec.status})   "
                       f"Last assessed: {rec.last_assessed or '-'}",
                  foreground="#444").pack(anchor="w", pady=(2, 2))
        if rec.notes:
            ttk.Label(frm, text=f"Notes: {rec.notes}",
                      foreground="#666").pack(anchor="w", pady=(0, 8))

    ttk.Label(frm, text=f"History ({len(history)}):",
              font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(6, 2))
    cols = ("id", "date", "phase", "status", "notes")
    tree = ttk.Treeview(frm, columns=cols, show="headings", height=10)
    for col, label, width, anchor in [
        ("id", "#", 50, "center"),
        ("date", "Date", 100, "center"),
        ("phase", "Phase", 60, "center"),
        ("status", "Status", 80, "w"),
        ("notes", "Notes", 280, "w"),
    ]:
        tree.heading(col, text=label)
        tree.column(col, width=width, anchor=anchor)
    tree.pack(fill="both", expand=True)
    for h in history:
        tree.insert("", "end", iid=str(h.assessment_id), values=(
            h.assessment_id, h.assessed_on, h.phase, h.status, h.notes or ""))

    def _delete() -> None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Phonics", "Select a history row first.",
                                parent=dlg)
            return
        aid = int(sel[0])
        if not messagebox.askyesno("Delete assessment",
                                   f"Delete assessment #{aid}?",
                                   parent=dlg):
            return
        try:
            data.delete_assessment(aid)
        except Exception:
            logger.exception("delete_assessment(%s) failed", aid)
            messagebox.showerror("Error", "Could not delete — see logs.",
                                 parent=dlg)
            return
        dlg.destroy()
        on_saved()

    btn_row = ttk.Frame(frm)
    btn_row.pack(fill="x", pady=(10, 0))
    ttk.Button(btn_row, text="Delete selected",
               command=_delete).pack(side="left")
    ttk.Button(btn_row, text="Close",
               command=dlg.destroy).pack(side="right")
