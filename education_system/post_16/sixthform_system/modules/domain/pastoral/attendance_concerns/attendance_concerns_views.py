"""Tkinter views for Sixth Form Attendance Concerns.

A 4-tab notebook:
* Watchlist (live, computed from attendance records)
* Open Concerns
* All Concerns
* Summary
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Callable
from education_system.post_16.sixthform_system.modules.domain.pastoral.attendance_concerns import attendance_concerns
from education_system.post_16.sixthform_system.modules.domain.pastoral.attendance_concerns import attendance_concerns as data
from education_system.post_16.sixthform_system.modules.domain.students.students import students as student_data
from education_system.shared import branding
from education_system.post_16.sixthform_system.modules.domain.pastoral.attendance_concerns.attendance_concerns import (
    CONCERN_LEVELS,
    Concern,
    DEFAULT_LEVEL,
    DEFAULT_REASON,
    DEFAULT_STATUS,
    REASONS,
    STATUSES,
    ValidationError,
    WatchlistEntry,
    WatchlistThresholds,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_attendance_concerns_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Attendance Concerns — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    WatchlistTab(nb)
    ConcernsTab(nb, open_only=True, label="Open Concerns")
    ConcernsTab(nb, open_only=False, label="All Concerns")
    SummaryTab(nb)


def _name_lookup() -> dict[str, str]:
    return {s.student_id: s.full_name for s in student_data.list_students()}


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}") for s in rows]


def _today() -> str:
    return _date.today().isoformat()


# ══ Watchlist tab ══════════════════════════════════════════════════

class WatchlistTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Watchlist")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Window (days):").pack(side="left")
        self.window_e = ttk.Entry(bar, width=4)
        self.window_e.insert(0, "28")
        self.window_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Min %:").pack(side="left")
        self.minpct_e = ttk.Entry(bar, width=5)
        self.minpct_e.insert(0, "90")
        self.minpct_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Max lates:").pack(side="left")
        self.maxlate_e = ttk.Entry(bar, width=4)
        self.maxlate_e.insert(0, "5")
        self.maxlate_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Max absences:").pack(side="left")
        self.maxabs_e = ttk.Entry(bar, width=4)
        self.maxabs_e.insert(0, "3")
        self.maxabs_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Max unauth:").pack(side="left")
        self.maxun_e = ttk.Entry(bar, width=4)
        self.maxun_e.insert(0, "1")
        self.maxun_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Reset",
                    command=self._reset).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("student", "name", "pct", "p", "l", "a", "au",
                "severity", "open", "reasons")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        headings = {"student": "Student", "name": "Name", "pct": "%",
                    "p": "P", "l": "L", "a": "A", "au": "Au",
                    "severity": "Severity", "open": "Open?",
                    "reasons": "Reasons"}
        widths = {"student": 90, "name": 200, "pct": 60, "p": 50,
                  "l": 50, "a": 50, "au": 50, "severity": 90,
                  "open": 70, "reasons": 460}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Critical", background="#ffd0d0")
        self.tree.tag_configure("High", background="#ffe6d0")
        self.tree.tag_configure("Medium", background="#fff7d0")

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        self.actions_holder = ttk.Frame(self.frame)
        self.actions_holder.pack(fill="x", padx=8, pady=(4, 8))
        self._build_actions()

    def _build_actions(self) -> None:
        for w in self.actions_holder.winfo_children():
            w.destroy()
        bar = ttk.Frame(self.actions_holder)
        bar.pack(fill="x")
        ttk.Button(bar, text="Raise Concern",
                    command=self._raise_selected).pack(side="left")
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _reset(self) -> None:
        for e, v in ((self.window_e, "28"), (self.minpct_e, "90"),
                      (self.maxlate_e, "5"), (self.maxabs_e, "3"),
                      (self.maxun_e, "1")):
            e.delete(0, "end")
            e.insert(0, v)
        self.refresh()

    def _read_thresholds(self) -> WatchlistThresholds | None:
        try:
            return WatchlistThresholds(
                window_days=int(self.window_e.get().strip() or "28"),
                min_pct=float(self.minpct_e.get().strip() or "90"),
                max_lates=int(self.maxlate_e.get().strip() or "5"),
                max_absences=int(self.maxabs_e.get().strip() or "3"),
                max_unauth=int(self.maxun_e.get().strip() or "1"),
            )
        except ValueError as e:
            messagebox.showerror("Threshold error", str(e))
            return None

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        t = self._read_thresholds()
        if t is None:
            return
        self._entries = data.watchlist(t)
        for e in self._entries:
            pct = "—" if e.percentage is None else f"{e.percentage:.1f}"
            tags = (e.severity,) if e.severity in (
                "Critical", "High", "Medium") else ()
            self.tree.insert("", "end", iid=e.student_id, values=(
                e.student_id, e.student_name, pct,
                e.present, e.late, e.absent, e.authorised,
                e.severity, "yes" if e.has_open_concern else "no",
                "; ".join(e.reasons),
            ), tags=tags)
        self.count_var.set(f"{len(self._entries)} student(s) on watchlist.")
        self._build_actions()

    def _selected_entry(self) -> WatchlistEntry | None:
        sel = self.tree.selection()
        if not sel:
            return None
        sid = sel[0]
        return next((e for e in self._entries if e.student_id == sid), None)

    def _raise_selected(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            messagebox.showinfo("Raise", "Select a student first.")
            return
        t = self._read_thresholds()
        if t is None:
            return
        prefill = {
            "student_id":    entry.student_id,
            "reason":        DEFAULT_REASON,
            "level":         entry.severity,
            "status":        DEFAULT_STATUS,
            "threshold_pct": t.min_pct,
            "observed_pct":  entry.percentage,
            "window_days":   t.window_days,
            "description":   "; ".join(entry.reasons),
        }
        ConcernDialog(self.frame.winfo_toplevel(),
                       existing=None, prefill=prefill,
                       on_save=self.refresh)


# ══ Concerns tab (open / all) ══════════════════════════════════════

class ConcernsTab:
    def __init__(self, nb: ttk.Notebook, *,
                 open_only: bool, label: str) -> None:
        self.open_only = open_only
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student ID:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Level:").pack(side="left")
        self.f_level = ttk.Combobox(bar, values=("",) + CONCERN_LEVELS,
                                      state="readonly", width=10)
        self.f_level.current(0)
        self.f_level.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                       state="readonly", width=16)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="Reason:").pack(side="left")
        self.f_reason = ttk.Combobox(bar, values=("",) + REASONS,
                                       state="readonly", width=24)
        self.f_reason.current(0)
        self.f_reason.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "name", "raised", "reason", "level",
                "status", "obs", "follow", "assigned")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 60, "student": 90, "name": 180, "raised": 100,
                  "reason": 200, "level": 80, "status": 130,
                  "obs": 60, "follow": 100, "assigned": 130}
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Critical", background="#ffd0d0")
        self.tree.tag_configure("High", background="#ffe6d0")
        self.tree.bind("<Double-1>", lambda _e: self._view_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        self.actions_holder = ttk.Frame(self.frame)
        self.actions_holder.pack(fill="x", padx=8, pady=(4, 8))
        self._build_actions()

    def _build_actions(self) -> None:
        for w in self.actions_holder.winfo_children():
            w.destroy()
        bar = ttk.Frame(self.actions_holder)
        bar.pack(fill="x")
        ttk.Button(bar, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(bar, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Status",
                    command=self._status_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_level.current(0)
        self.f_status.current(0)
        self.f_reason.current(0)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_concerns(
                student_id=self.f_student.get().strip() or None,
                level=self.f_level.get() or None,
                status=self.f_status.get() or None,
                reason=self.f_reason.get() or None,
                open_only=self.open_only,
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        names = _name_lookup()
        for c in rows:
            obs = "—" if c.observed_pct is None else f"{c.observed_pct:.1f}"
            tags = (c.level,) if c.level in ("Critical", "High") else ()
            self.tree.insert("", "end", values=(
                c.concern_id, c.student_id, names.get(c.student_id, "?"),
                c.raised_date, c.reason, c.level, c.status,
                obs, c.follow_up_date or "—", c.assigned_to or "—",
            ), tags=tags)
        self.count_var.set(f"{len(rows)} concern(s).")
        self._build_actions()

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(self.tree.item(sel[0])["values"][0])

    def _view_selected(self) -> None:
        cid = self._selected_id()
        if cid is None:
            messagebox.showinfo("View", "Select a concern first.")
            return
        c = data.get_concern(cid)
        if c is None:
            messagebox.showerror("View", f"No concern #{cid}")
            return
        names = _name_lookup()
        lines = [
            f"Concern    : #{c.concern_id}",
            f"Student    : {c.student_id} — {names.get(c.student_id, '?')}",
            f"Raised     : {c.raised_date}  by {c.raised_by or '—'}",
            f"Reason     : {c.reason}",
            f"Level      : {c.level}",
            f"Status     : {c.status}",
            f"Assigned   : {c.assigned_to or '—'}",
            f"Threshold% : {c.threshold_pct if c.threshold_pct is not None else '—'}",
            f"Observed%  : {c.observed_pct if c.observed_pct is not None else '—'}",
            f"Window     : "
            f"{(str(c.window_days) + ' days') if c.window_days else '—'}",
            f"Follow-up  : {c.follow_up_date or '—'}",
            "",
            "Description:",
            c.description or "  —",
            "",
            "Action taken:",
            c.action_taken or "  —",
            "",
            "Notes:",
            c.notes or "  —",
        ]
        messagebox.showinfo(f"Concern #{c.concern_id}", "\n".join(lines))

    def _new(self) -> None:
        ConcernDialog(self.frame.winfo_toplevel(),
                       existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        cid = self._selected_id()
        if cid is None:
            messagebox.showinfo("Edit", "Select a concern first.")
            return
        existing = data.get_concern(cid)
        if existing is None:
            messagebox.showerror("Edit", f"No concern #{cid}")
            return
        ConcernDialog(self.frame.winfo_toplevel(),
                       existing=existing, on_save=self.refresh)

    def _status_selected(self) -> None:
        cid = self._selected_id()
        if cid is None:
            messagebox.showinfo("Status", "Select a concern first.")
            return
        existing = data.get_concern(cid)
        if existing is None:
            return
        StatusDialog(self.frame.winfo_toplevel(), existing,
                      on_save=self.refresh)

    def _delete_selected(self) -> None:
        cid = self._selected_id()
        if cid is None:
            messagebox.showinfo("Delete", "Select a concern first.")
            return
        if not messagebox.askyesno("Delete", f"Delete concern #{cid}?"):
            return
        try:
            data.delete_concern(cid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


class StatusDialog:
    def __init__(self, parent: tk.Misc, existing: Concern,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — concern #{existing.concern_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=STATUSES,
                                  state="readonly", width=20)
        self.cb.set(existing.status)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.set_status(self.existing.concern_id, self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class ConcernDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Concern | None,
                 prefill: dict | None = None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.prefill = prefill or {}
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Concern" if existing else "New Concern")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0

        ttk.Label(form, text="Student:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        if self.existing or self.prefill.get("student_id"):
            self.student_cb = None
            sid = (self.existing.student_id if self.existing
                   else self.prefill["student_id"])
            self._student_id = sid
            names = _name_lookup()
            ttk.Label(form,
                       text=f"{sid} — {names.get(sid, '?')}"
                       ).grid(row=r, column=1, sticky="w", padx=6)
        else:
            opts = _student_options()
            self._student_ids = [s for s, _ in opts]
            self.student_cb = ttk.Combobox(form,
                                              values=[l for _, l in opts],
                                              state="readonly", width=40)
            if opts:
                self.student_cb.current(0)
            self.student_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Raised date:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.raised_e = ttk.Entry(form, width=14)
        self.raised_e.insert(0, self.existing.raised_date
                                if self.existing else _today())
        self.raised_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Reason:").grid(row=r, column=0,
                                               sticky="e", pady=4)
        self.reason_cb = ttk.Combobox(form, values=REASONS,
                                         state="readonly", width=28)
        self.reason_cb.set(self.existing.reason if self.existing
                              else self.prefill.get("reason", DEFAULT_REASON))
        self.reason_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Level:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.level_cb = ttk.Combobox(form, values=CONCERN_LEVELS,
                                        state="readonly", width=14)
        self.level_cb.set(self.existing.level if self.existing
                             else self.prefill.get("level", DEFAULT_LEVEL))
        self.level_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                               sticky="e", pady=4)
        self.status_cb = ttk.Combobox(form, values=STATUSES,
                                         state="readonly", width=18)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Raised by:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.rb_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.raised_by:
            self.rb_e.insert(0, self.existing.raised_by)
        self.rb_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Assigned to:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.assign_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.assigned_to:
            self.assign_e.insert(0, self.existing.assigned_to)
        self.assign_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Threshold %:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.thr_e = ttk.Entry(form, width=8)
        thr = (self.existing.threshold_pct if self.existing
               else self.prefill.get("threshold_pct"))
        if thr is not None:
            self.thr_e.insert(0, str(thr))
        self.thr_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Observed %:").grid(row=r, column=0,
                                                   sticky="e", pady=4)
        self.obs_e = ttk.Entry(form, width=8)
        obs = (self.existing.observed_pct if self.existing
               else self.prefill.get("observed_pct"))
        if obs is not None:
            self.obs_e.insert(0, str(obs))
        self.obs_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Window (days):").grid(row=r, column=0,
                                                      sticky="e", pady=4)
        self.wd_e = ttk.Entry(form, width=8)
        wd = (self.existing.window_days if self.existing
              else self.prefill.get("window_days", 28))
        if wd is not None:
            self.wd_e.insert(0, str(wd))
        self.wd_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Follow-up date:").grid(row=r, column=0,
                                                      sticky="e", pady=4)
        self.fu_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.follow_up_date:
            self.fu_e.insert(0, self.existing.follow_up_date)
        self.fu_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Description:").grid(row=r, column=0,
                                                    sticky="ne", pady=4)
        self.desc_text = tk.Text(form, width=60, height=4, wrap="word")
        seed = ((self.existing.description if self.existing
                 else self.prefill.get("description")) or "")
        self.desc_text.insert("1.0", seed)
        self.desc_text.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Action taken:").grid(row=r, column=0,
                                                     sticky="ne", pady=4)
        self.action_text = tk.Text(form, width=60, height=4, wrap="word")
        if self.existing and self.existing.action_taken:
            self.action_text.insert("1.0", self.existing.action_taken)
        self.action_text.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                              sticky="ne", pady=4)
        self.notes_text = tk.Text(form, width=60, height=4, wrap="word")
        if self.existing and self.existing.notes:
            self.notes_text.insert("1.0", self.existing.notes)
        self.notes_text.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        if self.student_cb is not None:
            idx = self.student_cb.current()
            if idx < 0:
                messagebox.showerror("Validation", "Pick a student.")
                return
            sid = self._student_ids[idx]
        else:
            sid = self._student_id
        payload = {
            "student_id":     sid,
            "raised_date":    self.raised_e.get().strip(),
            "reason":         self.reason_cb.get(),
            "level":          self.level_cb.get(),
            "status":         self.status_cb.get(),
            "raised_by":      self.rb_e.get().strip(),
            "assigned_to":    self.assign_e.get().strip(),
            "threshold_pct":  self.thr_e.get().strip() or None,
            "observed_pct":   self.obs_e.get().strip() or None,
            "window_days":    self.wd_e.get().strip() or None,
            "follow_up_date": self.fu_e.get().strip(),
            "description":    self.desc_text.get("1.0", "end").strip(),
            "action_taken":   self.action_text.get("1.0", "end").strip(),
            "notes":          self.notes_text.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_concern(self.existing.concern_id, payload)
            else:
                data.create_concern(payload)
        except ValidationError as e:
            messagebox.showerror("Validation", str(e))
            return
        except Exception as e:
            logger.exception("save concern failed")
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Follow-up window (days):").pack(side="left")
        self.window_e = ttk.Entry(bar, width=4)
        self.window_e.insert(0, "14")
        self.window_e.pack(side="left", padx=6)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left", padx=8)

        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10), state="disabled")
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))

    def refresh(self) -> None:
        try:
            window = int(self.window_e.get().strip() or "14")
        except ValueError:
            messagebox.showerror("Summary", "Window must be a whole number.")
            return
        summ = data.summary(upcoming_window_days=window)
        L: list[str] = []
        L.append("Concerns")
        L.append("--------")
        L.append(f"  Total                 : {summ.total}")
        L.append(f"  Open                  : {summ.open_count}")
        L.append("")
        L.append("Alerts")
        L.append("------")
        L.append(f"  High/Critical open    : {summ.high_critical_open}")
        L.append(f"  Overdue follow-ups    : {summ.overdue_follow_ups}")
        L.append(f"  Upcoming ({window}d)      : "
                  f"{summ.upcoming_follow_ups}")
        L.append(f"  Unassigned open       : {summ.unassigned_open}")
        L.append("")
        L.append("Watchlist (live, default thresholds)")
        L.append("-----------------------------------")
        L.append(f"  Students breaching    : {summ.watchlist_size}")
        L.append(f"  …without open concern : "
                  f"{summ.watchlist_without_concern}")
        L.append("")
        L.append("By level")
        L.append("--------")
        for lvl in CONCERN_LEVELS:
            L.append(f"  {lvl:<10} : {summ.by_level.get(lvl, 0)}")
        L.append("")
        L.append("By status")
        L.append("---------")
        for st in STATUSES:
            L.append(f"  {st:<22} : {summ.by_status.get(st, 0)}")
        L.append("")
        L.append("By reason")
        L.append("---------")
        for r in REASONS:
            n = summ.by_reason.get(r, 0)
            if n:
                L.append(f"  {r:<30} : {n}")
        body = "\n".join(L)
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", body)
        self.text.configure(state="disabled")
