"""Tk views for pupil target setting."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.primarysch_system.modules.domain.target_setting import (
    target_setting as data,
)
from education_system.primarysch_system.modules.domain.target_setting.target_setting import (
    STATUSES, STATUS_LABELS, TARGET_GRADES, TARGET_GRADE_LABELS, Target,
)
from education_system.primarysch_system.modules.domain.pupils import (
    pupils as pupils_data,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
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
                messagebox.showerror("Target Setting", str(e),
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
def open_target_setting(host) -> None:
    logger.debug("GUI: open_target_setting")

    win = tk.Toplevel(host.root)
    win.title("Target Setting")
    win.transient(host.root)
    win.geometry("1140x620")

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
    subj_box = ttk.Combobox(filt, textvariable=subj_var,
                            values=["All"], state="readonly", width=16)
    subj_box.pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Status:").pack(side="left")
    status_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=status_var,
                 values=["All"] + list(STATUSES),
                 state="readonly", width=10).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="Pupil year:").pack(side="left")
    py_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=py_var,
                 values=["All"] + list(YEAR_GROUPS),
                 state="readonly", width=6).pack(side="left", padx=(4, 10))

    cols = ("target_id", "pupil_id", "name", "year", "academic_year",
            "subject", "grade", "score", "review", "status")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=15)
    for col, label, width, anchor in [
        ("target_id", "#", 50, "center"),
        ("pupil_id", "Pupil ID", 90, "w"),
        ("name", "Name", 180, "w"),
        ("year", "Yr", 40, "center"),
        ("academic_year", "AcYr", 80, "center"),
        ("subject", "Subject", 140, "w"),
        ("grade", "Grade", 60, "center"),
        ("score", "Score", 70, "center"),
        ("review", "Review", 100, "center"),
        ("status", "Status", 100, "w"),
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
            st = None if status_var.get() == "All" else status_var.get()
            py = None if py_var.get() == "All" else py_var.get()
            rows = data.list_targets(academic_year=ay, subject=subj,
                                     status=st, year_group=py)
        except ValidationError as e:
            messagebox.showerror("Target Setting", str(e), parent=win)
            return
        except Exception:
            logger.exception("targets refresh failed")
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        for iid in tree.get_children():
            tree.delete(iid)
        for rec, p in rows:
            tree.insert("", "end", iid=str(rec.target_id), values=(
                rec.target_id, rec.pupil_id,
                p.full_name if p else "(unknown)",
                p.year_group if p else "-",
                rec.academic_year, rec.subject, rec.target_grade,
                "" if rec.target_score is None else f"{rec.target_score:g}",
                rec.review_date or "", rec.status,
            ))
        try:
            year_box["values"] = ["All"] + data.known_years()
            subj_box["values"] = ["All"] + data.known_subjects()
        except Exception:
            pass
        try:
            s = data.summary(academic_year=ay, subject=subj)
        except Exception:
            s = {"total": 0, "by_status": {st: 0 for st in STATUSES},
                 "met_or_exceeded": 0, "met_or_exceeded_pct": 0.0}
        parts = [f"Total: {s['total']}"]
        for ststat in STATUSES:
            parts.append(f"{ststat}: {s['by_status'].get(ststat, 0)}")
        parts.append(f"Met+exceeded: {s['met_or_exceeded']} "
                     f"({s['met_or_exceeded_pct']:.1f}%)")
        summary_var.set("   ".join(parts))

    def _selected_id() -> int | None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Target Setting",
                                "Select a target first.", parent=win)
            return None
        return int(sel[0])

    def _add() -> None:
        _open_form_dialog(win, target_id=None, on_saved=_refresh)

    def _edit() -> None:
        tid = _selected_id()
        if tid is None:
            return
        _open_form_dialog(win, target_id=tid, on_saved=_refresh)

    def _set_status() -> None:
        tid = _selected_id()
        if tid is None:
            return
        _open_status_dialog(win, tid, on_saved=_refresh)

    def _delete() -> None:
        tid = _selected_id()
        if tid is None:
            return
        if not messagebox.askyesno("Delete target",
                                   f"Delete target #{tid}?", parent=win):
            return
        try:
            data.delete(tid)
        except Exception:
            logger.exception("delete(%s) failed", tid)
            messagebox.showerror("Error", "Could not delete — see logs.",
                                 parent=win)
            return
        _refresh()

    def _help() -> None:
        msg = "Target grades:\n" + "\n".join(
            f"{g}  —  {TARGET_GRADE_LABELS[g]}" for g in TARGET_GRADES)
        msg += "\n\nStatuses:\n" + "\n".join(
            f"{s}  —  {STATUS_LABELS[s]}" for s in STATUSES)
        messagebox.showinfo("Target Setting", msg, parent=win)

    ttk.Button(btns, text="New target", command=_add).pack(side="left")
    ttk.Button(btns, text="Edit", command=_edit).pack(side="left", padx=(8, 0))
    ttk.Button(btns, text="Change status...", command=_set_status).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Delete", command=_delete).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Help", command=_help).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Refresh", command=_refresh).pack(
        side="left", padx=(8, 0))
    ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")

    tree.bind("<Double-Button-1>", lambda _e: _edit())
    for v in (year_var, subj_var, status_var, py_var):
        v.trace_add("write", lambda *_: _refresh())

    _refresh()


def _open_form_dialog(parent, *, target_id: int | None,
                      on_saved: Callable[[], None]) -> None:
    existing: Target | None = None
    if target_id is not None:
        try:
            existing = data.get(target_id)
        except Exception:
            logger.exception("get(%s) failed", target_id)
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=parent)
            return
        if existing is None:
            messagebox.showerror("Target Setting",
                                 f"No target #{target_id}", parent=parent)
            return

    dlg = tk.Toplevel(parent)
    dlg.title("Target" if existing else "New target")
    dlg.transient(parent)
    dlg.geometry("520x520")
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
    subj_var = tk.StringVar(value=existing.subject if existing else "")
    try:
        known = data.known_subjects()
    except Exception:
        known = []
    ttk.Combobox(frm, textvariable=subj_var, values=known,
                 width=28).grid(row=2, column=1, columnspan=2,
                                sticky="ew", pady=3)

    ttk.Label(frm, text="Target grade *").grid(
        row=3, column=0, sticky="w", pady=3)
    grade_var = tk.StringVar(
        value=existing.target_grade if existing else "EXS")
    ttk.Combobox(frm, textvariable=grade_var, values=list(TARGET_GRADES),
                 state="readonly", width=8).grid(
        row=3, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Target score (optional)").grid(
        row=4, column=0, sticky="w", pady=3)
    score_var = tk.StringVar(
        value="" if not existing or existing.target_score is None
        else f"{existing.target_score:g}")
    ttk.Entry(frm, textvariable=score_var, width=8).grid(
        row=4, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Set on (YYYY-MM-DD)").grid(
        row=5, column=0, sticky="w", pady=3)
    set_var = tk.StringVar(value=existing.set_on or "" if existing else "")
    ttk.Entry(frm, textvariable=set_var, width=14).grid(
        row=5, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Review date (YYYY-MM-DD)").grid(
        row=6, column=0, sticky="w", pady=3)
    review_var = tk.StringVar(
        value=existing.review_date or "" if existing else "")
    ttk.Entry(frm, textvariable=review_var, width=14).grid(
        row=6, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Status").grid(row=7, column=0, sticky="w", pady=3)
    status_var = tk.StringVar(value=existing.status if existing else "open")
    ttk.Combobox(frm, textvariable=status_var, values=list(STATUSES),
                 state="readonly", width=12).grid(
        row=7, column=1, sticky="w", pady=3)

    ttk.Label(frm, text="Notes").grid(row=8, column=0, sticky="w", pady=3)
    notes_var = tk.StringVar(value=existing.notes or "" if existing else "")
    ttk.Entry(frm, textvariable=notes_var, width=30).grid(
        row=8, column=1, columnspan=2, sticky="ew", pady=3)
    frm.columnconfigure(2, weight=1)

    def _save() -> None:
        payload = {
            "pupil_id": pupil_var.get(),
            "academic_year": ay_var.get(),
            "subject": subj_var.get(),
            "target_grade": grade_var.get(),
            "target_score": score_var.get(),
            "set_on": set_var.get(),
            "review_date": review_var.get(),
            "status": status_var.get(),
            "notes": notes_var.get(),
        }
        try:
            if existing is None:
                data.create(payload)
            else:
                data.update(existing.target_id, payload)
        except ValidationError as e:
            messagebox.showerror("Target Setting", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("save target failed")
            messagebox.showerror("Error", "Could not save — see logs.",
                                 parent=dlg)
            return
        on_saved()
        dlg.destroy()

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(14, 0))
    ttk.Button(btn_row, text="Save", command=_save).pack(side="right")
    ttk.Button(btn_row, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))


def _open_status_dialog(parent, target_id: int,
                        on_saved: Callable[[], None]) -> None:
    try:
        existing = data.get(target_id)
    except Exception:
        logger.exception("get(%s) failed", target_id)
        messagebox.showerror("Error", "Could not load — see logs.",
                             parent=parent)
        return
    if existing is None:
        messagebox.showerror("Target Setting",
                             f"No target #{target_id}", parent=parent)
        return

    dlg = tk.Toplevel(parent)
    dlg.title(f"Status — target #{target_id}")
    dlg.transient(parent)
    dlg.geometry("380x180")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm,
              text=f"Target #{existing.target_id}: pupil {existing.pupil_id}, "
                   f"{existing.subject}",
              font=("Segoe UI", 10, "bold")).pack(anchor="w")
    ttk.Label(frm, text=f"Current status: {existing.status}",
              foreground="#666").pack(anchor="w", pady=(2, 8))
    new_var = tk.StringVar(value=existing.status)
    ttk.Combobox(frm, textvariable=new_var, values=list(STATUSES),
                 state="readonly", width=12).pack(anchor="w")

    def _save() -> None:
        try:
            data.set_status(target_id, new_var.get())
        except ValidationError as e:
            messagebox.showerror("Target Setting", str(e), parent=dlg)
            return
        except Exception:
            logger.exception("set_status failed")
            messagebox.showerror("Error", "Could not save — see logs.",
                                 parent=dlg)
            return
        on_saved()
        dlg.destroy()

    btn_row = ttk.Frame(frm)
    btn_row.pack(fill="x", pady=(12, 0))
    ttk.Button(btn_row, text="Save", command=_save).pack(side="right")
    ttk.Button(btn_row, text="Cancel",
               command=dlg.destroy).pack(side="right", padx=(0, 8))
