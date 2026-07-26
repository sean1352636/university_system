"""Tk views for attendance reporting."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from education_system.systems.primary.domain.operations.reporting.attendance_report import (
    attendance_report as data,
)
from education_system.systems.primary.domain.operations.reporting.attendance_report.attendance_report import (
    PERSISTENT_ABSENCE_THRESHOLD_PCT, PupilAttendance,
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
                messagebox.showerror("Attendance Report", str(e),
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
def open_attendance_report(host) -> None:
    logger.debug("GUI: open_attendance_report")

    win = tk.Toplevel(host.root)
    win.title("Attendance Report")
    win.transient(host.root)
    win.geometry("1180x680")

    top = ttk.Frame(win, padding=10)
    top.pack(fill="x")
    ttk.Label(top, text="Attendance Report",
              font=("Segoe UI", 13, "bold")).pack(side="left")
    ttk.Label(top,
              text=f"Persistent-absentee threshold: "
                   f"<{PERSISTENT_ABSENCE_THRESHOLD_PCT:g}%",
              foreground="#666").pack(side="right")

    filt = ttk.Frame(win, padding=(10, 0, 10, 6))
    filt.pack(fill="x")
    fr_default, to_default = data.default_term_range()
    ttk.Label(filt, text="From:").pack(side="left")
    from_var = tk.StringVar(value=fr_default)
    ttk.Entry(filt, textvariable=from_var, width=12).pack(
        side="left", padx=(4, 10))
    ttk.Label(filt, text="To:").pack(side="left")
    to_var = tk.StringVar(value=to_default)
    ttk.Entry(filt, textvariable=to_var, width=12).pack(
        side="left", padx=(4, 10))
    ttk.Label(filt, text="Year:").pack(side="left")
    year_var = tk.StringVar(value="All")
    ttk.Combobox(filt, textvariable=year_var,
                 values=["All"] + list(YEAR_GROUPS),
                 state="readonly", width=6).pack(side="left", padx=(4, 10))
    ttk.Label(filt, text="PA threshold %:").pack(side="left")
    thr_var = tk.StringVar(value=f"{PERSISTENT_ABSENCE_THRESHOLD_PCT:g}")
    ttk.Entry(filt, textvariable=thr_var, width=6).pack(
        side="left", padx=(4, 10))

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    cohort_tab = ttk.Frame(nb, padding=10)
    pupils_tab = ttk.Frame(nb, padding=10)
    pa_tab = ttk.Frame(nb, padding=10)
    daily_tab = ttk.Frame(nb, padding=10)
    nb.add(cohort_tab, text="Cohort")
    nb.add(pupils_tab, text="Per pupil")
    nb.add(pa_tab, text="Persistent absentees")
    nb.add(daily_tab, text="Daily breakdown")

    # --- Cohort tab -----------------------------------------------------
    cohort_var = tk.StringVar()
    ttk.Label(cohort_tab, textvariable=cohort_var,
              font=("Segoe UI", 11, "bold")).pack(anchor="w")
    cohort_body = tk.Text(cohort_tab, height=10, wrap="word")
    cohort_body.pack(fill="x", pady=(6, 10))
    cohort_body.config(state="disabled")

    ttk.Label(cohort_tab, text="By year group",
              font=("Segoe UI", 10, "bold")).pack(anchor="w")
    cols_y = ("year", "sessions", "present", "late",
              "auth", "unauth", "att_pct")
    ytree = ttk.Treeview(cohort_tab, columns=cols_y, show="headings", height=8)
    for col, label, width, anchor in [
        ("year", "Year", 60, "center"),
        ("sessions", "Sessions", 90, "center"),
        ("present", "Present", 80, "center"),
        ("late", "Late", 60, "center"),
        ("auth", "Auth", 60, "center"),
        ("unauth", "Unauth", 70, "center"),
        ("att_pct", "Attendance %", 110, "center"),
    ]:
        ytree.heading(col, text=label)
        ytree.column(col, width=width, anchor=anchor)
    ytree.pack(fill="both", expand=True, pady=(4, 0))

    # --- Per-pupil tab --------------------------------------------------
    cols_p = ("pupil_id", "name", "year", "sessions", "present", "late",
              "auth", "unauth", "att_pct", "pa")
    ptree = ttk.Treeview(pupils_tab, columns=cols_p, show="headings",
                         height=18)
    for col, label, width, anchor in [
        ("pupil_id", "Pupil ID", 90, "w"),
        ("name", "Name", 220, "w"),
        ("year", "Yr", 40, "center"),
        ("sessions", "Sess", 60, "center"),
        ("present", "Pres", 60, "center"),
        ("late", "Late", 60, "center"),
        ("auth", "Auth", 60, "center"),
        ("unauth", "Unauth", 70, "center"),
        ("att_pct", "Attendance %", 110, "center"),
        ("pa", "PA", 50, "center"),
    ]:
        ptree.heading(col, text=label)
        ptree.column(col, width=width, anchor=anchor)
    ptree.tag_configure("pa", background="#fdecea", foreground="#a32118")
    ptree.pack(fill="both", expand=True)

    p_btns = ttk.Frame(pupils_tab, padding=(0, 6, 0, 0))
    p_btns.pack(fill="x")

    # --- Persistent absentees tab --------------------------------------
    pa_summary_var = tk.StringVar()
    ttk.Label(pa_tab, textvariable=pa_summary_var,
              font=("Segoe UI", 10, "bold")).pack(anchor="w")
    pa_tree = ttk.Treeview(pa_tab, columns=cols_p, show="headings", height=18)
    for col, label, width, anchor in [
        ("pupil_id", "Pupil ID", 90, "w"),
        ("name", "Name", 220, "w"),
        ("year", "Yr", 40, "center"),
        ("sessions", "Sess", 60, "center"),
        ("present", "Pres", 60, "center"),
        ("late", "Late", 60, "center"),
        ("auth", "Auth", 60, "center"),
        ("unauth", "Unauth", 70, "center"),
        ("att_pct", "Attendance %", 110, "center"),
        ("pa", "PA", 50, "center"),
    ]:
        pa_tree.heading(col, text=label)
        pa_tree.column(col, width=width, anchor=anchor)
    pa_tree.tag_configure("pa", background="#fdecea", foreground="#a32118")
    pa_tree.pack(fill="both", expand=True, pady=(6, 0))

    # --- Daily tab ------------------------------------------------------
    daily_help = ttk.Label(daily_tab,
                           text="Day-by-day breakdown across the date range.",
                           foreground="#666")
    daily_help.pack(anchor="w")
    cols_d = ("date", "sessions", "present", "late",
              "auth", "unauth", "att_pct")
    dtree = ttk.Treeview(daily_tab, columns=cols_d, show="headings", height=20)
    for col, label, width, anchor in [
        ("date", "Date", 110, "center"),
        ("sessions", "Sessions", 90, "center"),
        ("present", "Present", 90, "center"),
        ("late", "Late", 70, "center"),
        ("auth", "Auth", 70, "center"),
        ("unauth", "Unauth", 80, "center"),
        ("att_pct", "Attendance %", 120, "center"),
    ]:
        dtree.heading(col, text=label)
        dtree.column(col, width=width, anchor=anchor)
    dtree.pack(fill="both", expand=True, pady=(6, 0))

    # --- Refresh logic --------------------------------------------------
    def _populate_pupils(tree: ttk.Treeview, rows: list[PupilAttendance]) -> None:
        for iid in tree.get_children():
            tree.delete(iid)
        for r in rows:
            tags = ("pa",) if r.is_persistent_absentee else ()
            tree.insert("", "end", iid=r.pupil_id, values=(
                r.pupil_id, r.full_name, r.year_group,
                r.total_sessions, r.present, r.late,
                r.authorised_absent, r.unauthorised_absent,
                f"{r.attendance_pct:.2f}",
                "YES" if r.is_persistent_absentee else "",
            ), tags=tags)

    def _refresh() -> None:
        fr = from_var.get().strip() or None
        to = to_var.get().strip() or None
        yg = None if year_var.get() == "All" else year_var.get()
        try:
            thr = float(thr_var.get()) if thr_var.get() else PERSISTENT_ABSENCE_THRESHOLD_PCT
        except ValueError:
            thr = PERSISTENT_ABSENCE_THRESHOLD_PCT
        # Cohort
        try:
            cs = data.cohort_summary(from_date=fr, to_date=to, year_group=yg)
        except ValidationError as e:
            messagebox.showerror("Attendance Report", str(e), parent=win)
            return
        except Exception:
            logger.exception("cohort_summary failed")
            messagebox.showerror("Error", "Could not load — see logs.",
                                 parent=win)
            return
        cohort_var.set(
            f"{(cs['year_group'] or 'Whole school')}   "
            f"{fr or 'all-time'} → {to or 'now'}   "
            f"Attendance: {cs['attendance_pct']:.2f}%"
        )
        cohort_body.config(state="normal")
        cohort_body.delete("1.0", "end")
        cohort_body.insert("end",
            f"Sessions:              {cs['sessions']}\n"
            f"Unique pupils:         {cs['unique_pupils']}\n"
            f"Present:               {cs['present']}\n"
            f"Late:                  {cs['late']}\n"
            f"Authorised absent:     {cs['auth_absent']}\n"
            f"Unauthorised absent:   {cs['unauth_absent']}\n"
            f"Other:                 {cs['other']}\n"
            f"Attendance %:          {cs['attendance_pct']:.2f}\n")
        cohort_body.config(state="disabled")
        # By year
        try:
            year_rows = data.by_year_group(from_date=fr, to_date=to)
        except Exception:
            logger.exception("by_year_group failed")
            year_rows = []
        for iid in ytree.get_children():
            ytree.delete(iid)
        for s in year_rows:
            ytree.insert("", "end", values=(
                s["year_group"], s["sessions"], s["present"], s["late"],
                s["auth_absent"], s["unauth_absent"],
                f"{s['attendance_pct']:.2f}",
            ))
        # Per pupil
        try:
            pupil_rows = data.pupil_attendance(from_date=fr, to_date=to,
                                               year_group=yg)
        except Exception:
            logger.exception("pupil_attendance failed")
            pupil_rows = []
        _populate_pupils(ptree, pupil_rows)
        # Persistent absentees
        try:
            pa_rows = data.persistent_absentees(
                from_date=fr, to_date=to, year_group=yg, threshold_pct=thr)
        except ValidationError as e:
            messagebox.showerror("Attendance Report", str(e), parent=win)
            return
        except Exception:
            logger.exception("persistent_absentees failed")
            pa_rows = []
        _populate_pupils(pa_tree, pa_rows)
        pa_summary_var.set(
            f"Threshold: < {thr:g}%   "
            f"Persistent absentees: {len(pa_rows)} of {len(pupil_rows)}"
        )
        # Daily
        for iid in dtree.get_children():
            dtree.delete(iid)
        if fr and to:
            try:
                drows = data.daily_breakdown(from_date=fr, to_date=to,
                                             year_group=yg)
            except Exception:
                logger.exception("daily_breakdown failed")
                drows = []
            for d in drows:
                dtree.insert("", "end", values=(
                    d["date"], d["sessions"], d["present"], d["late"],
                    d["auth_absent"], d["unauth_absent"],
                    f"{d['attendance_pct']:.2f}",
                ))

    def _export_pupils() -> None:
        path = filedialog.asksaveasfilename(
            parent=win, title="Export per-pupil rollup",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        fr = from_var.get().strip() or None
        to = to_var.get().strip() or None
        yg = None if year_var.get() == "All" else year_var.get()
        try:
            rows = data.pupil_attendance(from_date=fr, to_date=to,
                                         year_group=yg)
            n = data.export_csv(Path(path), rows)
        except ValidationError as e:
            messagebox.showerror("Attendance Report", str(e), parent=win)
            return
        except Exception:
            logger.exception("export_csv failed")
            messagebox.showerror("Error", "Could not export — see logs.",
                                 parent=win)
            return
        messagebox.showinfo("Attendance Report",
                            f"Wrote {n} pupil row(s) to:\n{path}",
                            parent=win)

    ttk.Button(p_btns, text="Export CSV...",
               command=_export_pupils).pack(side="left")
    ttk.Button(p_btns, text="Refresh",
               command=_refresh).pack(side="left", padx=(8, 0))

    bottom = ttk.Frame(win, padding=10)
    bottom.pack(fill="x")
    ttk.Button(bottom, text="Refresh", command=_refresh).pack(side="left")
    ttk.Button(bottom, text="Close", command=win.destroy).pack(side="right")

    for v in (from_var, to_var, year_var, thr_var):
        v.trace_add("write", lambda *_: _refresh())

    _refresh()
