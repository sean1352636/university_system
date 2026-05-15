"""Tkinter views for Sixth Form Admissions.

Notebook with 4 tabs:
* Open Pipeline    — applicants still in process (filterable).
* All Applicants   — every applicant including terminal states.
* Interviews       — interview scheduling overview.
* Summary          — pipeline counts.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.shared import branding
from education_system.sixthform_system.modules.domain.students.admissions import (
    admissions as data,
)
from education_system.sixthform_system.modules.domain.students.admissions.admissions import (
    Applicant,
    DEFAULT_OFFER_TYPE,
    DEFAULT_SOURCE,
    DEFAULT_STATUS,
    OFFER_TYPES,
    SOURCES,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_admissions_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Admissions — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    ApplicantsTab(nb, open_only=True, label="Open Pipeline")
    ApplicantsTab(nb, open_only=False, label="All Applicants")
    InterviewsTab(nb)
    SummaryTab(nb)


def _today() -> str:
    return _dt.date.today().isoformat()


def _subject_options() -> list[str]:
    try:
        from education_system.sixthform_system.modules.domain.academics.subjects import (
            subjects as _subjects,
        )
        return [s.name for s in _subjects.list_subjects()]
    except Exception:
        return []


# ══ Applicants tab ════════════════════════════════════════════════

class ApplicantsTab:
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

        ttk.Label(bar, text="Search:").pack(side="left")
        self.f_search = ttk.Entry(bar, width=18)
        self.f_search.pack(side="left", padx=(2, 10))
        self.f_search.bind("<Return>", lambda _e: self.refresh())

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                       state="readonly", width=22)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Source:").pack(side="left")
        self.f_source = ttk.Combobox(bar, values=("",) + SOURCES,
                                       state="readonly", width=18)
        self.f_source.current(0)
        self.f_source.pack(side="left", padx=(2, 10))

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "name", "submitted", "status", "offer",
                "source", "subjects", "interview")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        headings = {"id": "ID", "name": "Name", "submitted": "Submitted",
                    "status": "Status", "offer": "Offer",
                    "source": "Source", "subjects": "Subjects",
                    "interview": "Interview"}
        widths = {"id": 80, "name": 180, "submitted": 100,
                  "status": 140, "offer": 110, "source": 130,
                  "subjects": 260, "interview": 110}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        # Status colour bands
        self.tree.tag_configure("Submitted",           background="#eef7ff")
        self.tree.tag_configure("Under Review",        background="#eef7ff")
        self.tree.tag_configure("Interview Scheduled", background="#fff7d0")
        self.tree.tag_configure("Interviewed",         background="#fff7d0")
        self.tree.tag_configure("Offer Made",          background="#fff7d0")
        self.tree.tag_configure("Offer Accepted",      background="#d8f4d8")
        self.tree.tag_configure("Enrolled",            background="#d8f4d8")
        self.tree.tag_configure("Offer Declined",     background="#eeeeee")
        self.tree.tag_configure("Rejected",            background="#ffd0d0")
        self.tree.tag_configure("Withdrawn",           background="#eeeeee")
        self.tree.tag_configure("Waitlisted",          background="#eef7ff")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

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
        ttk.Button(actions, text="Status",
                    command=self._status_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Make offer",
                    command=self._offer_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Accept",
                    command=lambda: self._quick_status(
                        "Offer Accepted")).pack(side="left", padx=2)
        ttk.Button(actions, text="Decline",
                    command=lambda: self._quick_status(
                        "Offer Declined")).pack(side="left", padx=2)
        ttk.Button(actions, text="Reject",
                    command=lambda: self._quick_status(
                        "Rejected")).pack(side="left", padx=2)
        ttk.Button(actions, text="Convert",
                    command=self._convert_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_search.delete(0, "end")
        self.f_status.current(0)
        self.f_source.current(0)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = data.list_applicants(
                status=self.f_status.get() or None,
                source=self.f_source.get() or None,
                search=self.f_search.get().strip() or None,
                open_only=self.open_only,
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for a in rows:
            subj = ", ".join(a.subjects)
            tags = (a.status,) if a.status in STATUSES else ()
            self.tree.insert("", "end", iid=a.applicant_id, values=(
                a.applicant_id, a.full_name, a.submitted_at,
                a.status, a.offer_type or "—",
                a.application_source, subj,
                a.interview_date or "—",
            ), tags=tags)
        self.count_var.set(f"{len(rows)} applicant(s).")

    def _selected_id(self) -> str | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return sel[0]

    def _selected(self) -> Applicant | None:
        aid = self._selected_id()
        if aid is None:
            return None
        return data.get_applicant(aid)

    def _view_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("View", "Select an applicant first.")
            return
        lines = [
            f"Applicant   : {a.applicant_id}",
            f"Name        : {a.full_name}",
            f"DOB         : {a.dob or '—'}",
            f"Email       : {a.email or '—'}",
            f"Phone       : {a.phone or '—'}",
            f"Address     : {a.address or '—'}",
            f"Prev school : {a.previous_school or '—'}",
            f"GCSEs       : {a.predicted_gcses or '—'}",
            f"Subjects    : "
            f"{', '.join(a.subjects) if a.subjects else '—'}",
            f"Reference   : {a.reference_name or '—'}  "
            f"({a.reference_contact or '—'})",
            f"Source      : {a.application_source}",
            f"Submitted   : {a.submitted_at}",
            f"Status      : {a.status}",
        ]
        if a.offer_type:
            lines.append(f"Offer       : {a.offer_type}")
            if a.offer_conditions:
                lines.append(f"  Conditions: {a.offer_conditions}")
        if a.interview_date or a.interviewer:
            lines.append(
                f"Interview   : {a.interview_date or '—'} with "
                f"{a.interviewer or '—'}")
            if a.interview_notes:
                lines.append(f"  Notes     : {a.interview_notes}")
        if a.decision_by or a.decision_date:
            lines.append(
                f"Decision    : {a.decision_date or '—'} by "
                f"{a.decision_by or '—'}")
            if a.decision_notes:
                lines.append(f"  Notes     : {a.decision_notes}")
        if a.converted_student_id:
            lines.append(
                f"Enrolled as : {a.converted_student_id}")
        if a.notes:
            lines.append("")
            lines.append("Notes:")
            lines.append(a.notes)
        messagebox.showinfo(f"Applicant {a.applicant_id}",
                              "\n".join(lines))

    def _new(self) -> None:
        ApplicantDialog(self.frame.winfo_toplevel(),
                          existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Edit", "Select an applicant first.")
            return
        ApplicantDialog(self.frame.winfo_toplevel(),
                          existing=a, on_save=self.refresh)

    def _status_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Status", "Select an applicant first.")
            return
        StatusDialog(self.frame.winfo_toplevel(), a,
                       on_save=self.refresh)

    def _offer_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Offer", "Select an applicant first.")
            return
        OfferDialog(self.frame.winfo_toplevel(), a,
                      on_save=self.refresh)

    def _quick_status(self, new_status: str) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo(new_status,
                                  "Select an applicant first.")
            return
        if not messagebox.askyesno(
                new_status,
                f"Set {a.applicant_id} ({a.full_name}) → {new_status}?"):
            return
        try:
            data.set_status(a.applicant_id, new_status)
        except ValidationError as e:
            messagebox.showerror(new_status, str(e))
            return
        self.refresh()

    def _convert_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Convert",
                                  "Select an applicant first.")
            return
        if not messagebox.askyesno(
                "Convert to Student",
                f"Create a `students` row for {a.applicant_id} "
                f"({a.full_name})?\n"
                f"Applicant must be in 'Offer Accepted' status and "
                f"have all three subjects + an email."):
            return
        try:
            _, sid = data.convert_to_student(a.applicant_id)
        except ValidationError as e:
            messagebox.showerror("Convert", str(e))
            return
        messagebox.showinfo("Convert",
                              f"Enrolled as student {sid}.")
        self.refresh()

    def _delete_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Delete",
                                  "Select an applicant first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete applicant {a.applicant_id} ({a.full_name})?\n"
                "If they're already enrolled, the student record "
                "is NOT removed — only the applicant audit row."):
            return
        try:
            data.delete_applicant(a.applicant_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Interviews tab ════════════════════════════════════════════════

class InterviewsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Interviews")
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
        plus = (_dt.date.today() + _dt.timedelta(days=30)).isoformat()
        self.to_e.insert(0, plus)
        self.to_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Next 7",
                    command=lambda: self._preset(7)
                    ).pack(side="left", padx=2)
        ttk.Button(bar, text="Next 30",
                    command=lambda: self._preset(30)
                    ).pack(side="left", padx=2)
        ttk.Button(bar, text="Schedule…",
                    command=self._schedule).pack(side="left", padx=8)

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("date", "id", "name", "interviewer", "status",
                "subjects")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"date": 110, "id": 80, "name": 200,
                  "interviewer": 160, "status": 160, "subjects": 320}
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("done", background="#eeeeee")

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

    def _preset(self, days: int) -> None:
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
        df = self.from_e.get().strip()
        dt = self.to_e.get().strip()
        rows = [a for a in data.list_applicants() if a.interview_date]
        rows = [a for a in rows
                 if (not df or a.interview_date >= df)
                 and (not dt or a.interview_date <= dt)]
        rows.sort(key=lambda a: a.interview_date or "")
        today = _today()
        for a in rows:
            tags = ("done",) if a.interview_date and a.interview_date < today else ()
            self.tree.insert("", "end", iid=a.applicant_id, values=(
                a.interview_date or "—", a.applicant_id,
                a.full_name, a.interviewer or "—",
                a.status, ", ".join(a.subjects),
            ), tags=tags)
        self.count_var.set(
            f"{len(rows)} interview(s) between {df} and {dt}.")

    def _schedule(self) -> None:
        rows = data.list_applicants(open_only=True)
        if not rows:
            messagebox.showinfo("Schedule",
                                  "No open applicants.")
            return
        ScheduleDialog(self.frame.winfo_toplevel(), rows,
                          on_save=self.refresh)


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
        ttk.Label(bar, text="Upcoming interview window (days):").pack(
            side="left")
        self.window_e = ttk.Entry(bar, width=6)
        self.window_e.insert(0, "14")
        self.window_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left")

        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.configure(state="disabled")

    def refresh(self) -> None:
        try:
            win = int(self.window_e.get().strip() or "14")
        except ValueError:
            messagebox.showerror("Summary",
                                    "Window must be a number.")
            return
        summ = data.summary(upcoming_window_days=win)
        lines = [
            f"Total applicants     : {summ.total}",
            f"Open                 : {summ.open_count}",
            f"Awaiting decision    : {summ.awaiting_decision}",
            f"Pending offers       : {summ.pending_offers}",
            f"Converted to student : {summ.converted}",
            f"Rejected             : {summ.rejected}",
            f"Upcoming interviews  : {summ.upcoming_interviews}  "
            f"(next {win} days)",
            "",
            "By status:",
        ]
        for s in STATUSES:
            n = summ.by_status.get(s, 0)
            lines.append(f"  {s:<22} : {n}")
        lines.append("")
        lines.append("By source:")
        for s in SOURCES:
            n = summ.by_source.get(s, 0)
            if n:
                lines.append(f"  {s:<22} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Dialogs ═══════════════════════════════════════════════════════

class StatusDialog:
    def __init__(self, parent: tk.Misc, existing: Applicant,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — {existing.applicant_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form,
                   text=f"Applicant: {existing.applicant_id} — "
                         f"{existing.full_name}").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(form, text="New status:").grid(row=1, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=STATUSES,
                                  state="readonly", width=22)
        self.cb.set(existing.status)
        self.cb.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Decided by:").grid(row=2, column=0,
                                                    sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        if existing.decision_by:
            self.by_e.insert(0, existing.decision_by)
        self.by_e.grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Notes:").grid(row=3, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=40, height=4)
        if existing.decision_notes:
            self.notes_t.insert("1.0", existing.decision_notes)
        self.notes_t.grid(row=3, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=4, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.set_status(
                self.existing.applicant_id, self.cb.get(),
                decision_by=self.by_e.get().strip() or None,
                decision_notes=self.notes_t.get("1.0", "end").strip()
                or None,
            )
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class OfferDialog:
    def __init__(self, parent: tk.Misc, existing: Applicant,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Make offer — {existing.applicant_id}")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form,
                   text=f"Applicant: {existing.applicant_id} — "
                         f"{existing.full_name}").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(form, text="Offer type:").grid(row=1, column=0,
                                                    sticky="e", pady=4)
        self.type_cb = ttk.Combobox(form, values=OFFER_TYPES,
                                       state="readonly", width=18)
        self.type_cb.set(existing.offer_type or DEFAULT_OFFER_TYPE)
        self.type_cb.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Conditions:").grid(row=2, column=0,
                                                    sticky="ne", pady=4)
        self.cond_t = tk.Text(form, width=44, height=4)
        if existing.offer_conditions:
            self.cond_t.insert("1.0", existing.offer_conditions)
        self.cond_t.grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Decided by:").grid(row=3, column=0,
                                                    sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        if existing.decision_by:
            self.by_e.insert(0, existing.decision_by)
        self.by_e.grid(row=3, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=4, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Make offer",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            data.make_offer(
                self.existing.applicant_id,
                offer_type=self.type_cb.get(),
                conditions=self.cond_t.get("1.0", "end").strip() or None,
                decided_by=self.by_e.get().strip() or None,
            )
        except Exception as e:
            messagebox.showerror("Offer", str(e))
            return
        self.win.destroy()
        self.on_save()


class ScheduleDialog:
    def __init__(self, parent: tk.Misc, applicants: list[Applicant],
                 on_save: Callable[[], None]) -> None:
        self.applicants = applicants
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Schedule interview")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Applicant:").grid(row=0, column=0,
                                                   sticky="e", pady=4)
        self._ids = [a.applicant_id for a in applicants]
        self.cb = ttk.Combobox(
            form,
            values=[f"{a.applicant_id} — {a.full_name}"
                     for a in applicants],
            state="readonly", width=44)
        self.cb.current(0)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Date:").grid(row=1, column=0,
                                              sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, _today())
        self.date_e.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Interviewer:").grid(row=2, column=0,
                                                     sticky="e", pady=4)
        self.by_e = ttk.Entry(form, width=30)
        self.by_e.grid(row=2, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Schedule",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        idx = self.cb.current()
        if idx < 0:
            messagebox.showerror("Schedule", "Pick an applicant")
            return
        try:
            data.schedule_interview(
                self._ids[idx],
                interview_date=self.date_e.get().strip(),
                interviewer=self.by_e.get().strip() or None,
            )
        except Exception as e:
            messagebox.showerror("Schedule failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class ApplicantDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Applicant | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Applicant" if existing else "New Applicant")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        ttk.Label(form, text="First name:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.first_e = ttk.Entry(form, width=22)
        if self.existing:
            self.first_e.insert(0, self.existing.first_name)
        self.first_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Last name:").grid(row=r, column=2,
                                                   sticky="e", pady=4)
        self.last_e = ttk.Entry(form, width=22)
        if self.existing:
            self.last_e.insert(0, self.existing.last_name)
        self.last_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="DOB:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.dob_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.dob:
            self.dob_e.insert(0, self.existing.dob)
        self.dob_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Email:").grid(row=r, column=2,
                                               sticky="e", pady=4)
        self.email_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.email:
            self.email_e.insert(0, self.existing.email)
        self.email_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Phone:").grid(row=r, column=0,
                                               sticky="e", pady=4)
        self.phone_e = ttk.Entry(form, width=18)
        if self.existing and self.existing.phone:
            self.phone_e.insert(0, self.existing.phone)
        self.phone_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Address:").grid(row=r, column=2,
                                                 sticky="e", pady=4)
        self.addr_e = ttk.Entry(form, width=40)
        if self.existing and self.existing.address:
            self.addr_e.insert(0, self.existing.address)
        self.addr_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Previous school:").grid(row=r, column=0,
                                                          sticky="e", pady=4)
        self.prev_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.previous_school:
            self.prev_e.insert(0, self.existing.previous_school)
        self.prev_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Predicted GCSEs:").grid(row=r, column=2,
                                                          sticky="e", pady=4)
        self.gcse_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.predicted_gcses:
            self.gcse_e.insert(0, self.existing.predicted_gcses)
        self.gcse_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        opts = _subject_options()
        for col, (lbl, attr) in enumerate(
                (("Subject 1", "subject_1"),
                 ("Subject 2", "subject_2"),
                 ("Subject 3", "subject_3"))):
            ttk.Label(form, text=f"{lbl}:").grid(
                row=r, column=col * 2 if col < 2 else 0,
                sticky="e", pady=4)
        # Simpler: stack subjects vertically.
        for i, attr in enumerate(("subject_1", "subject_2", "subject_3")):
            ttk.Label(form, text=f"Subject {i+1}:").grid(
                row=r + i, column=0, sticky="e", pady=4)
            cb = ttk.Combobox(form, values=("",) + tuple(opts), width=30)
            current = (getattr(self.existing, attr, None) or "")
            cb.set(current)
            cb.grid(row=r + i, column=1, sticky="w", padx=6)
            setattr(self, f"_subj_{i+1}_cb", cb)

        r += 3
        ttk.Label(form, text="Reference name:").grid(row=r, column=0,
                                                        sticky="e", pady=4)
        self.refname_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.reference_name:
            self.refname_e.insert(0, self.existing.reference_name)
        self.refname_e.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Reference contact:").grid(row=r, column=2,
                                                            sticky="e", pady=4)
        self.refcontact_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.reference_contact:
            self.refcontact_e.insert(0, self.existing.reference_contact)
        self.refcontact_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Source:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.source_cb = ttk.Combobox(form, values=SOURCES,
                                         state="readonly", width=18)
        self.source_cb.set(self.existing.application_source
                              if self.existing else DEFAULT_SOURCE)
        self.source_cb.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Submitted:").grid(row=r, column=2,
                                                   sticky="e", pady=4)
        self.sub_e = ttk.Entry(form, width=14)
        self.sub_e.insert(0, (self.existing.submitted_at
                                if self.existing else _today()))
        self.sub_e.grid(row=r, column=3, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.status_cb = ttk.Combobox(form, values=STATUSES,
                                         state="readonly", width=22)
        self.status_cb.set(self.existing.status
                              if self.existing else DEFAULT_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=70, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, columnspan=3,
                            sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=4, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _collect(self) -> dict:
        return {
            "first_name":         self.first_e.get().strip(),
            "last_name":          self.last_e.get().strip(),
            "dob":                self.dob_e.get().strip(),
            "email":              self.email_e.get().strip(),
            "phone":              self.phone_e.get().strip(),
            "address":            self.addr_e.get().strip(),
            "previous_school":    self.prev_e.get().strip(),
            "predicted_gcses":    self.gcse_e.get().strip(),
            "subject_1":          self._subj_1_cb.get().strip() or None,
            "subject_2":          self._subj_2_cb.get().strip() or None,
            "subject_3":          self._subj_3_cb.get().strip() or None,
            "reference_name":     self.refname_e.get().strip(),
            "reference_contact":  self.refcontact_e.get().strip(),
            "application_source": self.source_cb.get().strip(),
            "submitted_at":       self.sub_e.get().strip(),
            "status":             self.status_cb.get().strip(),
            "notes":              self.notes_t.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                data.update_applicant(self.existing.applicant_id, payload)
            else:
                data.create_applicant(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
