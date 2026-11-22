"""Unarchived leavers, events + RSVPs, mentoring, speaker and volunteering tabs."""

from __future__ import annotations
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any, Callable
from education_system.platform import branding
from education_system.systems.sixth_form.domain.learners.alumni import (
    events as alumni_events,
    linking as alumni_linking,
    mentoring as alumni_mentoring,
    profile as alumni_profile,
    programmes as alumni_programmes,
    records as alumni_records,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.learners.alumni.models import (
    ACHIEVEMENT_CATEGORIES,
    Alumnus,
    CAMPAIGN_STATUSES,
    APPLICATION_STATUSES,
    BEQUEST_STATUSES,
    CUSTOM_FIELD_TYPES,
    ERASURE_STATUSES,
    WEBHOOK_EVENT_TYPES,
    CHAPTER_ROLES,
    CONNECTION_KINDS,
    DIRECTORY_CONSENT_SCOPE,
    DONOR_STAGES,
    DRIP_STATUSES,
    JOB_STATUSES,
    JOB_TYPES,
    NEET_STATUSES,
    NEWSLETTER_STATUSES,
    PROFICIENCY_LEVELS,
    RECURRING_FREQS,
    RECURRING_STATUSES,
    SAFEGUARDING_STATUSES,
    SOCIAL_PLATFORMS,
    TRACK_KINDS,
    CONSENT_SCOPES,
    DEFAULT_CAMPAIGN_STATUS,
    DEFAULT_DESTINATION,
    DEFAULT_EDUCATION_STATUS,
    DEFAULT_EVENT_STATUS,
    DEFAULT_LEAVING_REASON,
    DEFAULT_PLEDGE_STATUS,
    DEFAULT_RSVP_STATUS,
    DEFAULT_STATUS,
    DESTINATION_TYPES,
    EDUCATION_STATUSES,
    EMAIL_LABELS,
    EVENT_STATUSES,
    EVENT_TYPES,
    GENDER_OPTIONS,
    LEAVING_REASONS,
    MENTORSHIP_STATUSES,
    PAYMENT_METHODS,
    PHONE_LABELS,
    PLEDGE_STATUSES,
    RSVP_STATUSES,
    SALARY_BANDS,
    SECTORS,
    SESSION_FORMATS,
    STATUSES,
    VOLUNTEER_ACTIVITY_TYPES,
)
from education_system.systems.sixth_form.domain.learners.alumni.integrations import MEDIA_KINDS
from education_system.systems.sixth_form.domain.learners.alumni.compliance import PROTECTED_CHARS
from education_system.systems.sixth_form.domain.learners.alumni.engagement import (
    CHAPTER_KINDS,
    MILESTONE_KINDS,
)
from education_system.systems.sixth_form.domain.learners.alumni.comms import (
    COMM_CHANNELS,
    COMM_STATUSES,
)
from education_system.systems.sixth_form.domain.learners.alumni.db import ValidationError
from ._common import (
    _money_str,
    _today,
)
from .views_giving import (
    StatusPickerDialog,
)


# ── Unarchived leavers tab ────────────────────────────────────────

class UnarchivedLeaversTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Unarchived Leavers")
        ttk.Label(
            self.frame,
            text=("Students who look like leavers — UCAS final "
                   "decision or past exam year — but have no alumni "
                   "row yet."),
            foreground="#555", anchor="w"
        ).pack(fill="x", padx=8, pady=(8, 4))
        cols = ("sid", "name", "email", "ucas_year",
                "exam_year", "destination")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"sid": 90, "name": 200, "email": 220,
                  "ucas_year": 80, "exam_year": 80,
                  "destination": 360}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        ttk.Button(bar, text="Archive selected (auto-enrich)",
                    command=self._archive).pack(side="left", padx=4)
        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                    anchor="w").pack(fill="x", padx=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        rows = alumni_linking.find_unarchived_leavers()
        for r in rows:
            self.tree.insert("", "end", iid=r.student_id, values=(
                r.student_id, r.full_name, r.email or "—",
                r.ucas_cycle_year or "—",
                r.last_exam_year or "—",
                r.final_destination or "—"))
        self.count_var.set(f"{len(rows)} flagged.")

    def _archive(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        sid = sel[0]
        if not messagebox.askyesno(
                "Archive",
                f"Archive student {sid} as an alumnus "
                "(auto-enriching from UCAS / exam results / "
                "bursaries)?"):
            return
        try:
            a = alumni_linking.archive_student_enriched(sid)
        except Exception as e:
            messagebox.showerror("Archive failed", str(e))
            return
        messagebox.showinfo(
            "Archived",
            f"Archived as alumnus #{a.alumni_id}\n"
            f"Destination: {a.destination_type} — "
            f"{a.destination_detail or '—'}\n"
            f"Tags: "
            f"{', '.join(t.name for t in alumni_profile.list_tags_for(a.alumni_id)) or '—'}\n"
            f"Education rows seeded: "
            f"{len(alumni_profile.list_education(a.alumni_id))}")
        self.refresh()


# ══ Events tab (top-level) ══════════════════════════════════════

class EventsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Events")
        cols = ("id", "name", "type", "date", "location",
                "capacity", "cost", "status")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "name": 220, "type": 110, "date": 100,
                  "location": 160, "capacity": 70, "cost": 90,
                  "status": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree.bind("<Double-1>", lambda _e: self._open_rsvps())
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="New event",
                    command=self._add).pack(side="left")
        ttk.Button(bar, text="Edit",
                    command=self._edit).pack(side="left", padx=4)
        ttk.Button(bar, text="RSVPs / Attendance",
                    command=self._open_rsvps).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for e in alumni_events.list_events():
            self.tree.insert("", "end", iid=str(e.event_id), values=(
                e.event_id, e.name, e.event_type,
                e.event_date or "—", e.location or "—",
                e.capacity if e.capacity is not None else "—",
                _money_str(e.cost_pence), e.status))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self) -> None:
        EventDialog(self.frame.winfo_toplevel(), existing=None,
                      on_save=self.refresh)

    def _edit(self) -> None:
        eid = self._selected_id()
        if eid is None: return
        ev = alumni_events.get_event(eid)
        if ev is None: return
        EventDialog(self.frame.winfo_toplevel(), existing=ev,
                      on_save=self.refresh)

    def _open_rsvps(self) -> None:
        eid = self._selected_id()
        if eid is None:
            messagebox.showinfo("RSVPs", "Select an event first.")
            return
        EventRsvpDialog(self.frame.winfo_toplevel(), eid,
                          on_save=self.refresh)

    def _delete(self) -> None:
        eid = self._selected_id()
        if eid is None: return
        if messagebox.askyesno("Delete event",
                                  f"Delete event #{eid} and all RSVPs?"):
            alumni_events.delete_event(eid)
            self.refresh()


class EventDialog:
    def __init__(self, parent: tk.Misc, *, existing,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit event" if existing else "New event")
        self.win.transient(parent); grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12); form.pack(fill="both",
                                                              expand=True)
        r = 0

        def row(label: str, w: tk.Widget) -> None:
            nonlocal r
            ttk.Label(form, text=label).grid(row=r, column=0,
                                                sticky="e", pady=3)
            w.grid(row=r, column=1, sticky="w", padx=6)
            r += 1

        self.name_e = ttk.Entry(form, width=44)
        self.type_cb = ttk.Combobox(form, values=EVENT_TYPES,
                                       state="readonly", width=22)
        self.type_cb.set(EVENT_TYPES[0])
        self.date_e = ttk.Entry(form, width=14)
        self.loc_e  = ttk.Entry(form, width=44)
        self.cap_e  = ttk.Entry(form, width=8)
        self.cost_e = ttk.Entry(form, width=10)
        self.cost_e.insert(0, "0")
        self.status_cb = ttk.Combobox(form, values=EVENT_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(DEFAULT_EVENT_STATUS)
        self.notes_t = tk.Text(form, width=44, height=3)

        if existing:
            self.name_e.insert(0, existing.name)
            self.type_cb.set(existing.event_type)
            if existing.event_date:
                self.date_e.insert(0, existing.event_date)
            if existing.location: self.loc_e.insert(0, existing.location)
            if existing.capacity is not None:
                self.cap_e.insert(0, str(existing.capacity))
            self.cost_e.delete(0, "end")
            self.cost_e.insert(0, f"{existing.cost_pence / 100:.2f}")
            self.status_cb.set(existing.status)
            if existing.notes:
                self.notes_t.insert("1.0", existing.notes)

        row("Name:",     self.name_e)
        row("Type:",     self.type_cb)
        row("Date:",     self.date_e)
        row("Location:", self.loc_e)
        row("Capacity:", self.cap_e)
        row("Cost £:",   self.cost_e)
        row("Status:",   self.status_cb)
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                                sticky="ne", pady=3)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6); r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        payload = {
            "name":       self.name_e.get().strip(),
            "event_type": self.type_cb.get(),
            "event_date": self.date_e.get().strip(),
            "location":   self.loc_e.get().strip(),
            "capacity":   self.cap_e.get().strip() or None,
            "cost":       self.cost_e.get().strip() or 0,
            "status":     self.status_cb.get(),
            "notes":      self.notes_t.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                alumni_events.update_event(self.existing.event_id, payload)
            else:
                alumni_events.create_event(payload)
        except Exception as e:
            messagebox.showerror("Save failed", str(e)); return
        self.win.destroy()
        self.on_save()


class EventRsvpDialog:
    def __init__(self, parent: tk.Misc, event_id: int,
                 on_save: Callable[[], None]) -> None:
        self.event_id = event_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"RSVPs for event #{event_id}")
        self.win.geometry("760x520")
        self.win.transient(parent); grab_when_viewable(self.win)

        ev = alumni_events.get_event(event_id)
        if ev:
            ttk.Label(self.win,
                        text=f"{ev.name}  ·  {ev.event_date or '—'}  "
                              f"·  {ev.location or '—'}",
                        font=("TkDefaultFont", 11, "bold"),
                        padding=8).pack(fill="x")
        self.att_var = tk.StringVar(value="")
        ttk.Label(self.win, textvariable=self.att_var,
                    padding=(8, 0, 8, 4)).pack(fill="x")

        cols = ("rsvp", "alumni", "name", "status", "guests",
                "attended")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        widths = {"rsvp": 60, "alumni": 60, "name": 200,
                  "status": 110, "guests": 70, "attended": 70}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win); bar.pack(fill="x", padx=8,
                                                pady=(0, 8))
        ttk.Button(bar, text="Add / update RSVP",
                    command=self._add).pack(side="left")
        ttk.Button(bar, text="Toggle attended",
                    command=self._toggle_attended).pack(side="left",
                                                          padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left")
        ttk.Button(bar, text="Close",
                    command=self._close).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for r in alumni_events.list_rsvps_for_event(self.event_id):
            a = alumni_records.get_alumnus(r.alumni_id)
            name = a.full_name if a else f"#{r.alumni_id}"
            self.tree.insert("", "end", iid=str(r.rsvp_id), values=(
                r.rsvp_id, r.alumni_id, name, r.status, r.guests,
                "✓" if r.attended else ""))
        att = alumni_events.event_attendance(self.event_id)
        self.att_var.set(
            f"Invited {att.invited}  ·  Accepted {att.accepted}  "
            f"·  Declined {att.declined}  ·  Attended {att.attended}  "
            f"(headcount {att.headcount})")

    def _add(self) -> None:
        RsvpDialog(self.win, event_id=self.event_id,
                     on_save=self.refresh)

    def _toggle_attended(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        rid = int(sel[0])
        rows = alumni_events.list_rsvps_for_event(self.event_id)
        r = next((x for x in rows if x.rsvp_id == rid), None)
        if r is None: return
        alumni_events.set_rsvp(self.event_id, r.alumni_id,
                        status=r.status, attended=not r.attended,
                        guests=r.guests)
        self.refresh()

    def _delete(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        alumni_events.delete_rsvp(int(sel[0]))
        self.refresh()

    def _close(self) -> None:
        self.win.destroy()
        self.on_save()


class RsvpDialog:
    def __init__(self, parent: tk.Misc, *, event_id: int,
                 on_save: Callable[[], None]) -> None:
        self.event_id = event_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Add / update RSVP")
        self.win.transient(parent); grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12); form.pack(fill="both",
                                                              expand=True)
        alumni = alumni_records.list_alumni()
        self._ids = [a.alumni_id for a in alumni]
        ttk.Label(form, text="Alumnus:").grid(row=0, column=0,
                                                  sticky="e", pady=3)
        self.cb = ttk.Combobox(form, state="readonly", width=40,
                                  values=[f"#{a.alumni_id} {a.full_name}"
                                            for a in alumni])
        if alumni: self.cb.current(0)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Status:").grid(row=1, column=0,
                                                  sticky="e", pady=3)
        self.status_cb = ttk.Combobox(form, values=RSVP_STATUSES,
                                          state="readonly", width=14)
        self.status_cb.set(DEFAULT_RSVP_STATUS)
        self.status_cb.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Guests:").grid(row=2, column=0,
                                                  sticky="e", pady=3)
        self.guests_e = ttk.Entry(form, width=6)
        self.guests_e.insert(0, "0")
        self.guests_e.grid(row=2, column=1, sticky="w", padx=6)
        self.attended_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Attended",
                          variable=self.attended_var).grid(
            row=3, column=1, sticky="w", padx=6, pady=3)
        bar = ttk.Frame(form)
        bar.grid(row=4, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        idx = self.cb.current()
        if idx < 0:
            return
        try:
            alumni_events.set_rsvp(
                self.event_id, self._ids[idx],
                status=self.status_cb.get(),
                guests=int(self.guests_e.get() or 0),
                attended=self.attended_var.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e)); return
        self.win.destroy()
        self.on_save()


# ══ Mentoring sub-tab ════════════════════════════════════════════

class MentoringTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Mentoring")
        cols = ("id", "mentee", "topic", "started", "ended", "status")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "mentee": 100, "topic": 220,
                  "started": 100, "ended": 100, "status": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4)
        ttk.Button(bar, text="Start mentorship",
                    command=self._start).pack(side="left")
        ttk.Button(bar, text="Sessions…",
                    command=self._sessions).pack(side="left", padx=4)
        ttk.Button(bar, text="End",
                    command=self._end).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for m in alumni_mentoring.list_mentorships_by_mentor(self.alumni_id):
            self.tree.insert("", "end", iid=str(m.mentorship_id),
                              values=(m.mentorship_id,
                                       m.mentee_student_id,
                                       m.topic or "—",
                                       m.started_on,
                                       m.ended_on or "—",
                                       m.status))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _start(self) -> None:
        MentorshipDialog(self.frame.winfo_toplevel(),
                           alumni_id=self.alumni_id,
                           on_save=self.refresh)

    def _sessions(self) -> None:
        mid = self._selected_id()
        if mid is None: return
        MentorSessionsDialog(self.frame.winfo_toplevel(),
                                mentorship_id=mid)

    def _end(self) -> None:
        mid = self._selected_id()
        if mid is None: return
        StatusPickerDialog(
            self.frame.winfo_toplevel(),
            title="End mentorship — final status",
            options=MENTORSHIP_STATUSES,
            on_pick=lambda s: (
                alumni_mentoring.end_mentorship(mid, status=s), self.refresh()))

    def _delete(self) -> None:
        mid = self._selected_id()
        if mid is None: return
        if messagebox.askyesno(
                "Delete mentorship",
                "Delete mentorship and all its sessions?"):
            alumni_mentoring.delete_mentorship(mid)
            self.refresh()


class MentorshipDialog:
    def __init__(self, parent: tk.Misc, *, alumni_id: int,
                 on_save: Callable[[], None]) -> None:
        self.alumni_id = alumni_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Start mentorship")
        self.win.transient(parent); grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12); form.pack()
        ttk.Label(form, text="Mentee student id:").grid(
            row=0, column=0, sticky="e", pady=3)
        self.mentee_e = ttk.Entry(form, width=20)
        self.mentee_e.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Topic:").grid(row=1, column=0,
                                                sticky="e", pady=3)
        self.topic_e = ttk.Entry(form, width=40)
        self.topic_e.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Notes:").grid(row=2, column=0,
                                                sticky="ne", pady=3)
        self.notes_t = tk.Text(form, width=40, height=3)
        self.notes_t.grid(row=2, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Start",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            alumni_mentoring.start_mentorship(
                self.alumni_id, self.mentee_e.get().strip(),
                topic=self.topic_e.get().strip() or None,
                notes=self.notes_t.get("1.0", "end").strip() or None)
        except Exception as e:
            messagebox.showerror("Save failed", str(e)); return
        self.win.destroy()
        self.on_save()


class MentorSessionsDialog:
    def __init__(self, parent: tk.Misc, *, mentorship_id: int) -> None:
        self.mentorship_id = mentorship_id
        self.win = tk.Toplevel(parent)
        self.win.title(f"Sessions for mentorship #{mentorship_id}")
        self.win.geometry("760x440")
        self.win.transient(parent); grab_when_viewable(self.win)
        cols = ("id", "date", "mins", "format", "summary")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        widths = {"id": 50, "date": 100, "mins": 60, "format": 90,
                  "summary": 460}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win); bar.pack(fill="x", padx=8,
                                                pady=(0, 8))
        ttk.Button(bar, text="Log session",
                    command=self._add).pack(side="left")
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(bar, text="Close",
                    command=self.win.destroy).pack(side="right")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for s in alumni_mentoring.list_mentor_sessions(self.mentorship_id):
            self.tree.insert("", "end", iid=str(s.session_id),
                              values=(s.session_id, s.session_date,
                                       s.duration_minutes or 0,
                                       s.format or "—",
                                       (s.summary or "")[:100]))

    def _add(self) -> None:
        win = tk.Toplevel(self.win); win.title("Log session")
        win.transient(self.win); grab_when_viewable(win)
        form = ttk.Frame(win, padding=12); form.pack()
        date_e = ttk.Entry(form, width=14); date_e.insert(0, _today())
        dur_e  = ttk.Entry(form, width=8)
        fmt_cb = ttk.Combobox(form, values=("",) + SESSION_FORMATS,
                                 state="readonly", width=14)
        summ_t = tk.Text(form, width=40, height=4)
        for i, (lbl, w) in enumerate((("Date", date_e),
                                       ("Duration (min)", dur_e),
                                       ("Format", fmt_cb))):
            ttk.Label(form, text=lbl + ":").grid(row=i, column=0,
                                                     sticky="e", pady=3)
            w.grid(row=i, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Summary:").grid(row=3, column=0,
                                                  sticky="ne", pady=3)
        summ_t.grid(row=3, column=1, sticky="w", padx=6)

        def save() -> None:
            try:
                alumni_mentoring.log_mentor_session(self.mentorship_id, {
                    "session_date":     date_e.get().strip(),
                    "duration_minutes": dur_e.get().strip(),
                    "format":           fmt_cb.get(),
                    "summary":          summ_t.get("1.0",
                                                       "end").strip(),
                })
            except Exception as e:
                messagebox.showerror("Save failed", str(e)); return
            win.destroy()
            self.refresh()

        bar = ttk.Frame(form); bar.grid(row=4, column=0, columnspan=2,
                                          pady=(12, 0))
        ttk.Button(bar, text="Save", command=save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)

    def _delete(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        alumni_mentoring.delete_mentor_session(int(sel[0]))
        self.refresh()


# ══ Speaker sub-tab ══════════════════════════════════════════════

class SpeakerTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Speaker")
        wrap = ttk.Frame(self.frame, padding=12); wrap.pack(fill="x")
        ttk.Label(wrap, text="Speaker register profile",
                    font=("TkDefaultFont", 10, "bold")
                    ).grid(row=0, column=0, columnspan=2,
                            sticky="w", pady=(0, 6))
        self.topics_e = ttk.Entry(wrap, width=56)
        self.years_e  = ttk.Entry(wrap, width=24)
        self.avail_t  = tk.Text(wrap, width=56, height=4)
        ttk.Label(wrap, text="Topics:").grid(row=1, column=0,
                                                  sticky="e", pady=3)
        self.topics_e.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(wrap, text="Year groups:").grid(row=2, column=0,
                                                       sticky="e",
                                                       pady=3)
        self.years_e.grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(wrap, text="Availability:").grid(row=3, column=0,
                                                       sticky="ne",
                                                       pady=3)
        self.avail_t.grid(row=3, column=1, sticky="w", padx=6)
        self.conf_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(wrap, text="Confirm willingness today",
                          variable=self.conf_var).grid(
            row=4, column=1, sticky="w", padx=6, pady=4)
        self.last_var = tk.StringVar(value="")
        ttk.Label(wrap, textvariable=self.last_var,
                    foreground="#555").grid(row=5, column=1,
                                               sticky="w", padx=6)
        bbar = ttk.Frame(wrap); bbar.grid(row=6, column=0,
                                              columnspan=2,
                                              pady=(10, 0),
                                              sticky="w")
        ttk.Button(bbar, text="Save",
                    command=self._save).pack(side="left")
        ttk.Button(bbar, text="Remove from register",
                    command=self._remove).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        p = alumni_programmes.get_speaker(self.alumni_id)
        self.topics_e.delete(0, "end")
        self.years_e.delete(0, "end")
        self.avail_t.delete("1.0", "end")
        self.conf_var.set(False)
        if p:
            if p.topics: self.topics_e.insert(0, p.topics)
            if p.year_groups: self.years_e.insert(0, p.year_groups)
            if p.availability_notes:
                self.avail_t.insert("1.0", p.availability_notes)
            self.last_var.set(
                f"Last confirmed: {p.last_confirmed_at or 'never'}")
        else:
            self.last_var.set("Not on register yet.")

    def _save(self) -> None:
        try:
            alumni_programmes.upsert_speaker(
                self.alumni_id,
                topics=self.topics_e.get(),
                year_groups=self.years_e.get(),
                availability_notes=self.avail_t.get("1.0", "end"),
                confirm=self.conf_var.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e)); return
        messagebox.showinfo("Saved", "Speaker profile updated.")
        self.refresh()

    def _remove(self) -> None:
        if messagebox.askyesno(
                "Remove",
                "Remove this alumnus from the speaker register?"):
            alumni_programmes.remove_speaker(self.alumni_id)
            self.refresh()


# ══ Volunteering sub-tab ═════════════════════════════════════════

class VolunteeringTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Volunteering")
        cols = ("id", "date", "hours", "activity", "event", "notes")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "date": 100, "hours": 70,
                  "activity": 160, "event": 80, "notes": 360}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.total_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.total_var,
                    foreground="#444",
                    padding=(8, 0, 8, 4)).pack(fill="x")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4,
                                                  pady=4)
        ttk.Button(bar, text="Log hours",
                    command=self._add).pack(side="left")
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for v in alumni_programmes.list_volunteer_hours(self.alumni_id):
            self.tree.insert("", "end", iid=str(v.volunteer_id),
                              values=(v.volunteer_id,
                                       v.activity_date,
                                       f"{v.hours:g}",
                                       v.activity_type,
                                       f"#{v.event_id}"
                                          if v.event_id else "—",
                                       v.notes or ""))
        self.total_var.set(
            f"Total: {alumni_programmes.total_volunteer_hours(self.alumni_id):g}h")

    def _add(self) -> None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title("Log hours")
        win.transient(self.frame.winfo_toplevel()); grab_when_viewable(win)
        form = ttk.Frame(win, padding=12); form.pack()
        date_e   = ttk.Entry(form, width=14); date_e.insert(0, _today())
        hours_e  = ttk.Entry(form, width=8)
        type_cb  = ttk.Combobox(
            form, values=VOLUNTEER_ACTIVITY_TYPES,
            state="readonly", width=22)
        type_cb.set(VOLUNTEER_ACTIVITY_TYPES[0])
        events = alumni_events.list_events()
        event_choices = ["(no event)"] + [
            f"#{e.event_id} {e.name[:30]}" for e in events]
        event_cb = ttk.Combobox(form, values=event_choices,
                                   state="readonly", width=40)
        event_cb.current(0)
        notes_e = ttk.Entry(form, width=40)
        for i, (lbl, w) in enumerate((("Date", date_e),
                                       ("Hours", hours_e),
                                       ("Activity", type_cb),
                                       ("Attach event", event_cb),
                                       ("Notes", notes_e))):
            ttk.Label(form, text=lbl + ":").grid(row=i, column=0,
                                                     sticky="e", pady=3)
            w.grid(row=i, column=1, sticky="w", padx=6)

        def save() -> None:
            idx = event_cb.current()
            ev_id = events[idx - 1].event_id if idx > 0 else None
            try:
                alumni_programmes.log_volunteer_hours(
                    self.alumni_id,
                    float(hours_e.get() or 0),
                    activity_type=type_cb.get(),
                    activity_date=date_e.get().strip(),
                    event_id=ev_id,
                    notes=notes_e.get().strip() or None)
            except Exception as e:
                messagebox.showerror("Save failed", str(e)); return
            win.destroy()
            self.refresh()

        bar = ttk.Frame(form); bar.grid(row=5, column=0, columnspan=2,
                                          pady=(12, 0))
        ttk.Button(bar, text="Save", command=save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)

    def _delete(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        alumni_programmes.delete_volunteer_entry(int(sel[0]))
        self.refresh()
