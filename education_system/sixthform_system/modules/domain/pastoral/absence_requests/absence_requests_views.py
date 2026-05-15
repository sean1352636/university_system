"""Tkinter views for Sixth Form Absence Requests.

A 4-tab notebook:
* Pending Requests  (decision queue)
* All Requests
* Calendar (overlap query — list everything overlapping a date range)
* Summary
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Callable
from education_system.shared import branding
from education_system.sixthform_system.modules.domain.pastoral.absence_requests import (
    absence_requests as data,
)
from education_system.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.sixthform_system.modules.domain.pastoral.absence_requests.absence_requests import (
    AbsenceRequest,
    DECIDED_STATUSES,
    DEFAULT_REASON,
    DEFAULT_STATUS,
    DEFAULT_SUBMITTER,
    REASONS,
    STATUSES,
    SUBMITTERS,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_absence_requests_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Absence Requests — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    RequestsTab(nb, pending_only=True, label="Pending Requests")
    RequestsTab(nb, pending_only=False, label="All Requests")
    CalendarTab(nb)
    SummaryTab(nb)


def _name_lookup() -> dict[str, str]:
    return {s.student_id: s.full_name for s in student_data.list_students()}


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}") for s in rows]


def _today() -> str:
    return _date.today().isoformat()


# ══ Requests tab (pending / all) ═══════════════════════════════════

class RequestsTab:
    def __init__(self, nb: ttk.Notebook, *,
                 pending_only: bool, label: str) -> None:
        self.pending_only = pending_only
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

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                       state="readonly", width=12)
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
        cols = ("id", "student", "name", "submitted", "start", "end",
                "days", "reason", "status", "decided_by")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        headings = {"id": "ID", "student": "Student", "name": "Name",
                    "submitted": "Submitted", "start": "From",
                    "end": "To", "days": "Days", "reason": "Reason",
                    "status": "Status", "decided_by": "Decided by"}
        widths = {"id": 60, "student": 90, "name": 180,
                  "submitted": 100, "start": 100, "end": 100,
                  "days": 50, "reason": 200, "status": 100,
                  "decided_by": 140}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c == "days" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Pending",   background="#fff7d0")
        self.tree.tag_configure("Approved",  background="#d8f4d8")
        self.tree.tag_configure("Denied",    background="#ffd0d0")
        self.tree.tag_configure("Cancelled", background="#eeeeee")
        self.tree.tag_configure("Withdrawn", background="#eeeeee")
        self.tree.bind("<Double-1>", lambda _e: self._view_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(actions, text="New",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Approve",
                    command=lambda: self._decide_selected(True)
                    ).pack(side="left", padx=4)
        ttk.Button(actions, text="Deny",
                    command=lambda: self._decide_selected(False)
                    ).pack(side="left", padx=4)
        ttk.Button(actions, text="Status",
                    command=self._status_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_status.current(0)
        self.f_reason.current(0)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_requests(
                student_id=self.f_student.get().strip() or None,
                status=self.f_status.get() or None,
                reason=self.f_reason.get() or None,
                pending_only=self.pending_only,
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        names = _name_lookup()
        for r in rows:
            tags = (r.status,) if r.status in (
                "Pending", "Approved", "Denied",
                "Cancelled", "Withdrawn") else ()
            self.tree.insert("", "end", values=(
                r.request_id, r.student_id, names.get(r.student_id, "?"),
                r.request_date, r.start_date, r.end_date, r.day_count,
                r.reason, r.status, r.decided_by or "—",
            ), tags=tags)
        self.count_var.set(f"{len(rows)} request(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(self.tree.item(sel[0])["values"][0])

    def _view_selected(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("View", "Select a request first.")
            return
        r = data.get_request(rid)
        if r is None:
            messagebox.showerror("View", f"No request #{rid}")
            return
        names = _name_lookup()
        lines = [
            f"Request    : #{r.request_id}",
            f"Student    : {r.student_id} — {names.get(r.student_id, '?')}",
            f"Submitted  : {r.request_date}",
            f"By         : {r.submitted_by or '—'} "
            f"({r.submitter_type or '—'})",
            f"Phone      : {r.contact_phone or '—'}",
            f"Dates      : {r.start_date} → {r.end_date} "
            f"({r.day_count} day{'s' if r.day_count != 1 else ''})",
            f"Reason     : {r.reason}",
            f"Status     : {r.status}",
        ]
        if r.is_decided:
            lines += [
                f"Decided    : {r.decision_date or '—'} "
                f"by {r.decided_by or '—'}",
            ]
        lines += [
            f"Doc        : {r.supporting_doc or '—'}",
            "",
            "Description:",
            r.description or "  —",
            "",
            "Decision notes:",
            r.decision_notes or "  —",
            "",
            "Notes:",
            r.notes or "  —",
        ]
        messagebox.showinfo(f"Request #{r.request_id}", "\n".join(lines))

    def _new(self) -> None:
        RequestDialog(self.frame.winfo_toplevel(),
                       existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Edit", "Select a request first.")
            return
        existing = data.get_request(rid)
        if existing is None:
            messagebox.showerror("Edit", f"No request #{rid}")
            return
        RequestDialog(self.frame.winfo_toplevel(),
                       existing=existing, on_save=self.refresh)

    def _decide_selected(self, approve_flag: bool) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo(
                "Decide", "Select a request first.")
            return
        existing = data.get_request(rid)
        if existing is None:
            return
        DecideDialog(self.frame.winfo_toplevel(), existing,
                      approve_flag=approve_flag, on_save=self.refresh)

    def _status_selected(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Status", "Select a request first.")
            return
        existing = data.get_request(rid)
        if existing is None:
            return
        StatusDialog(self.frame.winfo_toplevel(), existing,
                      on_save=self.refresh)

    def _delete_selected(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Delete", "Select a request first.")
            return
        if not messagebox.askyesno("Delete", f"Delete request #{rid}?"):
            return
        try:
            data.delete_request(rid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Calendar tab ══════════════════════════════════════════════════

class CalendarTab:
    """List all requests overlapping a date range — useful for cover
    planning and trip clashes."""

    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Calendar")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="From:").pack(side="left")
        self.from_e = ttk.Entry(bar, width=12)
        self.from_e.insert(0, _today())
        self.from_e.pack(side="left", padx=(2, 10))
        ttk.Label(bar, text="To:").pack(side="left")
        self.to_e = ttk.Entry(bar, width=12)
        import datetime as _dt
        plus = (_dt.date.today() + _dt.timedelta(days=30)).isoformat()
        self.to_e.insert(0, plus)
        self.to_e.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                       state="readonly", width=12)
        self.f_status.set("Approved")
        self.f_status.pack(side="left", padx=(2, 10))

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Next 7 days",
                    command=lambda: self._preset(7)).pack(side="left", padx=2)
        ttk.Button(bar, text="Next 30 days",
                    command=lambda: self._preset(30)).pack(side="left", padx=2)
        ttk.Button(bar, text="This term (90)",
                    command=lambda: self._preset(90)).pack(side="left", padx=2)

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "name", "start", "end", "days",
                "reason", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        headings = {"id": "ID", "student": "Student", "name": "Name",
                    "start": "From", "end": "To", "days": "Days",
                    "reason": "Reason", "status": "Status"}
        widths = {"id": 60, "student": 90, "name": 220,
                  "start": 110, "end": 110, "days": 60,
                  "reason": 220, "status": 110}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c == "days" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Pending",  background="#fff7d0")
        self.tree.tag_configure("Approved", background="#d8f4d8")
        self.tree.tag_configure("Denied",   background="#ffd0d0")

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def _preset(self, days: int) -> None:
        import datetime as _dt
        today = _dt.date.today()
        self.from_e.delete(0, "end")
        self.from_e.insert(0, today.isoformat())
        self.to_e.delete(0, "end")
        self.to_e.insert(0,
                          (today + _dt.timedelta(days=days)).isoformat())
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        from_d = self.from_e.get().strip()
        to_d = self.to_e.get().strip()
        if not from_d or not to_d:
            self.count_var.set("Enter a from/to date.")
            return
        try:
            rows = data.list_requests(
                status=self.f_status.get() or None,
                overlaps_from=from_d, overlaps_to=to_d,
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        names = _name_lookup()
        for r in rows:
            tags = (r.status,) if r.status in (
                "Pending", "Approved", "Denied") else ()
            self.tree.insert("", "end", values=(
                r.request_id, r.student_id, names.get(r.student_id, "?"),
                r.start_date, r.end_date, r.day_count,
                r.reason, r.status,
            ), tags=tags)
        self.count_var.set(
            f"{len(rows)} request(s) overlapping {from_d} → {to_d}.")


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Upcoming window (days):").pack(side="left")
        self.window_e = ttk.Entry(bar, width=6)
        self.window_e.insert(0, "14")
        self.window_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))

        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.configure(state="disabled")

    def refresh(self) -> None:
        try:
            window = int(self.window_e.get().strip() or "14")
        except ValueError:
            messagebox.showerror("Summary", "Window must be a number.")
            return
        summ = data.summary(upcoming_window_days=window)
        lines: list[str] = []
        lines.append(f"Total requests        : {summ.total}")
        lines.append("")
        lines.append("Alerts:")
        lines.append(f"  Pending             : {summ.pending_count}")
        lines.append(f"  Overdue pending     : {summ.overdue_pending}")
        lines.append(f"  In progress today   : {summ.in_progress}")
        lines.append(f"  Upcoming ({window}d){' ' * (8 - len(str(window)))}: "
                       f"{summ.upcoming_approved}")
        lines.append("")
        lines.append("By status:")
        for st in STATUSES:
            lines.append(f"  {st:<14} : {summ.by_status.get(st, 0)}")
        lines.append("")
        lines.append("By reason:")
        for rsn in REASONS:
            n = summ.by_reason.get(rsn, 0)
            if n:
                lines.append(f"  {rsn:<30} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Dialogs ═══════════════════════════════════════════════════════

class StatusDialog:
    def __init__(self, parent: tk.Misc, existing: AbsenceRequest,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — request #{existing.request_id}")
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
            data.set_status(self.existing.request_id, self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class DecideDialog:
    def __init__(self, parent: tk.Misc, existing: AbsenceRequest, *,
                 approve_flag: bool,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.approve_flag = approve_flag
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        verb = "Approve" if approve_flag else "Deny"
        self.win.title(f"{verb} request #{existing.request_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)

        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        names = _name_lookup()
        ttk.Label(
            form,
            text=f"Student: {existing.student_id} — "
                 f"{names.get(existing.student_id, '?')}\n"
                 f"Dates:   {existing.start_date} → {existing.end_date}\n"
                 f"Reason:  {existing.reason}",
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(form, text=f"{verb}d by:").grid(row=1, column=0,
                                                     sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        self.by_e.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Decision date:").grid(row=2, column=0,
                                                       sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, _today())
        self.date_e.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Notes:").grid(row=3, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=40, height=4)
        self.notes_t.grid(row=3, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=4, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text=verb, command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        decided_by = self.by_e.get().strip() or None
        notes = self.notes_t.get("1.0", "end").strip() or None
        date = self.date_e.get().strip() or None
        try:
            if self.approve_flag:
                data.approve(self.existing.request_id,
                              decided_by=decided_by,
                              decision_notes=notes)
            else:
                data.deny(self.existing.request_id,
                           decided_by=decided_by,
                           decision_notes=notes)
            if date:
                data.update_request(self.existing.request_id,
                                     {"decision_date": date})
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class RequestDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: AbsenceRequest | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Request" if existing else "New Absence Request")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0

        ttk.Label(form, text="Student:").grid(row=r, column=0,
                                                 sticky="e", pady=4)
        if self.existing:
            sid = self.existing.student_id
            self._student_id = sid
            self.student_cb = None
            names = _name_lookup()
            ttk.Label(form,
                       text=f"{sid} — {names.get(sid, '?')}"
                       ).grid(row=r, column=1, sticky="w", padx=6)
        else:
            opts = _student_options()
            self._student_ids = [s for s, _ in opts]
            self.student_cb = ttk.Combobox(
                form, values=[l for _, l in opts],
                state="readonly", width=44)
            if opts:
                self.student_cb.current(0)
            self.student_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Request date:").grid(row=r, column=0,
                                                     sticky="e", pady=4)
        self.request_e = ttk.Entry(form, width=14)
        self.request_e.insert(0, self.existing.request_date
                                if self.existing else _today())
        self.request_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Start date:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.start_e = ttk.Entry(form, width=14)
        self.start_e.insert(0, self.existing.start_date
                              if self.existing else _today())
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="End date:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.end_e = ttk.Entry(form, width=14)
        self.end_e.insert(0, self.existing.end_date
                            if self.existing else _today())
        self.end_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Reason:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.reason_cb = ttk.Combobox(form, values=REASONS,
                                         state="readonly", width=30)
        self.reason_cb.set(self.existing.reason
                              if self.existing else DEFAULT_REASON)
        self.reason_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Description:").grid(row=r, column=0,
                                                     sticky="ne", pady=4)
        self.desc_t = tk.Text(form, width=44, height=3)
        if self.existing and self.existing.description:
            self.desc_t.insert("1.0", self.existing.description)
        self.desc_t.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Submitter type:").grid(row=r, column=0,
                                                       sticky="e", pady=4)
        self.subt_cb = ttk.Combobox(form, values=SUBMITTERS,
                                       state="readonly", width=14)
        self.subt_cb.set((self.existing.submitter_type or DEFAULT_SUBMITTER)
                          if self.existing else DEFAULT_SUBMITTER)
        self.subt_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Submitted by:").grid(row=r, column=0,
                                                      sticky="e", pady=4)
        self.subby_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.submitted_by:
            self.subby_e.insert(0, self.existing.submitted_by)
        self.subby_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Contact phone:").grid(row=r, column=0,
                                                       sticky="e", pady=4)
        self.phone_e = ttk.Entry(form, width=20)
        if self.existing and self.existing.contact_phone:
            self.phone_e.insert(0, self.existing.contact_phone)
        self.phone_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Supporting doc:").grid(row=r, column=0,
                                                        sticky="e", pady=4)
        self.doc_e = ttk.Entry(form, width=44)
        if self.existing and self.existing.supporting_doc:
            self.doc_e.insert(0, self.existing.supporting_doc)
        self.doc_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.status_cb = ttk.Combobox(form, values=STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status
                              if self.existing else DEFAULT_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Decided by:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.decby_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.decided_by:
            self.decby_e.insert(0, self.existing.decided_by)
        self.decby_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Decision date:").grid(row=r, column=0,
                                                      sticky="e", pady=4)
        self.decdate_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.decision_date:
            self.decdate_e.insert(0, self.existing.decision_date)
        self.decdate_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Decision notes:").grid(row=r, column=0,
                                                       sticky="ne", pady=4)
        self.decnotes_t = tk.Text(form, width=44, height=3)
        if self.existing and self.existing.decision_notes:
            self.decnotes_t.insert("1.0", self.existing.decision_notes)
        self.decnotes_t.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=44, height=3)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _collect(self) -> dict:
        if self.existing:
            student_id = self._student_id
        elif self.student_cb is not None:
            idx = self.student_cb.current()
            if idx < 0:
                raise ValidationError("Select a student")
            student_id = self._student_ids[idx]
        else:
            raise ValidationError("Select a student")
        return {
            "student_id":     student_id,
            "request_date":   self.request_e.get().strip(),
            "start_date":     self.start_e.get().strip(),
            "end_date":       self.end_e.get().strip(),
            "reason":         self.reason_cb.get().strip(),
            "description":    self.desc_t.get("1.0", "end").strip(),
            "submitter_type": self.subt_cb.get().strip(),
            "submitted_by":   self.subby_e.get().strip(),
            "contact_phone":  self.phone_e.get().strip(),
            "supporting_doc": self.doc_e.get().strip(),
            "status":         self.status_cb.get().strip(),
            "decided_by":     self.decby_e.get().strip(),
            "decision_date":  self.decdate_e.get().strip(),
            "decision_notes": self.decnotes_t.get("1.0", "end").strip(),
            "notes":          self.notes_t.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_request(self.existing.request_id, payload)
            else:
                data.create_request(payload)
        except ValidationError as e:
            messagebox.showerror("Save failed", str(e))
            return
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
