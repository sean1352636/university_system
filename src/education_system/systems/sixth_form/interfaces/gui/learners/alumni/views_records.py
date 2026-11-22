"""Alumni records: list tab, summary, status/archive/edit dialogs, detail window."""

from __future__ import annotations
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any, Callable
from education_system.platform import branding
from education_system.systems.sixth_form.domain.learners.alumni import records as alumni_records
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
    _today,
)
from .views_careers import (
    MentorProfileTab,
    PromotionTimelineTab,
    SkillsTab,
)
from .views_compliance import (
    CustomValuesTab,
    MediaTab,
    NEETChecksTab,
    ProtectedCharsTab,
    SafeguardingTab,
)
from .views_engagement import (
    ChapterMembershipTab,
    ConnectionsTab,
    DirectoryConsentTab,
    EngagementTab,
    SocialHandlesTab,
)
from .views_giving import (
    DonationsTab,
    GiftAidTab,
)
from .views_messaging import (
    SMSTab,
)
from .views_profile import (
    AchievementsTab,
    CareerTab,
    ChannelPrefsTab,
    CommsTab,
    ConsentTab,
    ContactsTab,
    EducationTab,
    TagsTab,
)
from .views_programmes import (
    MentoringTab,
    SpeakerTab,
    VolunteeringTab,
)
from .views_reports import (
    AuditLogDialog,
)


# ══ Alumni tab ════════════════════════════════════════════════════

class AlumniTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Alumni")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(bar, text="Search:").pack(side="left")
        self.f_search = ttk.Entry(bar, width=18)
        self.f_search.pack(side="left", padx=(2, 10))
        self.f_search.bind("<Return>", lambda _e: self.refresh())

        ttk.Label(bar, text="Year:").pack(side="left")
        self.f_year = ttk.Entry(bar, width=8)
        self.f_year.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Destination:").pack(side="left")
        self.f_dest = ttk.Combobox(bar, values=("",) + DESTINATION_TYPES,
                                     state="readonly", width=18)
        self.f_dest.current(0)
        self.f_dest.pack(side="left", padx=(2, 10))

        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar, values=("",) + STATUSES,
                                       state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 10))

        self.contactable_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Contactable only",
                          variable=self.contactable_var,
                          command=self.refresh).pack(side="left", padx=4)

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "name", "year", "destination", "detail",
                "employer", "email", "status", "opt_in")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        widths = {"id": 50, "name": 180, "year": 60,
                  "destination": 130, "detail": 220,
                  "employer": 140, "email": 180,
                  "status": 100, "opt_in": 60}
        headings = {"id": "ID", "name": "Name", "year": "Year",
                    "destination": "Destination", "detail": "Detail",
                    "employer": "Employer", "email": "Email",
                    "status": "Status", "opt_in": "Opt-in"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c in ("year", "opt_in") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("Active",       background="#d8f4d8")
        self.tree.tag_configure("Lost Contact", background="#fff7d0")
        self.tree.tag_configure("Deceased",     background="#eeeeee")
        self.tree.tag_configure("Opt-out",      background="#eeeeee")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="View",
                    command=self._view_selected).pack(side="left")
        ttk.Button(actions, text="New (manual)",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(actions, text="Archive student…",
                    command=self._archive).pack(side="left", padx=4)
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Details…",
                    command=self._open_details).pack(side="left", padx=4)
        ttk.Button(actions, text="Audit log",
                    command=self._open_audit).pack(side="left", padx=4)
        ttk.Button(actions, text="Record contact",
                    command=self._record_contact).pack(side="left", padx=4)
        ttk.Button(actions, text="Status",
                    command=self._status_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def _clear(self) -> None:
        self.f_search.delete(0, "end")
        self.f_year.delete(0, "end")
        self.f_dest.current(0)
        self.f_status.current(0)
        self.contactable_var.set(False)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            rows = alumni_records.list_alumni(
                search=self.f_search.get().strip() or None,
                leaving_year=self.f_year.get().strip() or None,
                destination_type=self.f_dest.get() or None,
                status=self.f_status.get() or None,
                contactable_only=self.contactable_var.get(),
            )
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for a in rows:
            tags = (a.status,) if a.status in STATUSES else ()
            self.tree.insert("", "end", iid=str(a.alumni_id), values=(
                a.alumni_id, a.full_name, a.leaving_year or "—",
                a.destination_type,
                a.destination_detail or "—",
                a.current_employer or "—",
                a.email or "—", a.status,
                "✓" if a.opt_in_contact else "",
            ), tags=tags)
        self.count_var.set(f"{len(rows)} alumnus/alumni.")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _selected(self) -> Alumnus | None:
        aid = self._selected_id()
        if aid is None:
            return None
        return alumni_records.get_alumnus(aid)

    def _view_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("View", "Select an alumnus first.")
            return
        lines = [
            f"Alumnus       : #{a.alumni_id}",
            f"Name          : {a.display_name}",
            f"Original id   : {a.original_student_id or '—'}",
            f"DOB           : {a.dob or '—'}",
            f"Leaving year  : {a.leaving_year or '—'}",
            f"Leaving date  : {a.leaving_date or '—'}",
            f"Leaving reason: {a.leaving_reason or '—'}",
            f"Destination   : {a.destination_type}",
            f"  Detail      : {a.destination_detail or '—'}",
            f"Current role  : {a.current_role or '—'}",
            f"Employer      : {a.current_employer or '—'}",
            f"Location      : {a.current_location or '—'}",
            f"Email         : {a.email or '—'}",
            f"Phone         : {a.phone or '—'}",
            f"Address       : {a.address or '—'}",
            f"LinkedIn      : {a.linkedin or '—'}",
            f"Other social  : {a.other_social or '—'}",
            f"Opt-in        : {'yes' if a.opt_in_contact else 'no'}",
            f"Status        : {a.status}",
            f"Last contact  : {a.last_contacted or '—'}",
        ]
        if a.notes:
            lines.append("")
            lines.append("Notes:")
            lines.append(a.notes)
        messagebox.showinfo(f"Alumnus #{a.alumni_id}", "\n".join(lines))

    def _new(self) -> None:
        AlumnusDialog(self.frame.winfo_toplevel(),
                        existing=None, on_save=self.refresh)

    def _archive(self) -> None:
        ArchiveDialog(self.frame.winfo_toplevel(),
                       on_save=self.refresh)

    def _edit_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Edit", "Select an alumnus first.")
            return
        AlumnusDialog(self.frame.winfo_toplevel(),
                        existing=a, on_save=self.refresh)

    def _open_details(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Details", "Select an alumnus first.")
            return
        DetailWindow(self.frame.winfo_toplevel(), a)

    def _open_audit(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Audit log",
                                  "Select an alumnus first.")
            return
        AuditLogDialog(self.frame.winfo_toplevel(), a.alumni_id)

    def _record_contact(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Contact",
                                  "Select an alumnus first.")
            return
        try:
            alumni_records.record_contact(a.alumni_id)
        except Exception as e:
            messagebox.showerror("Contact", str(e))
            return
        self.refresh()

    def _status_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Status",
                                  "Select an alumnus first.")
            return
        StatusDialog(self.frame.winfo_toplevel(), a,
                       on_save=self.refresh)

    def _delete_selected(self) -> None:
        a = self._selected()
        if a is None:
            messagebox.showinfo("Delete",
                                  "Select an alumnus first.")
            return
        if not messagebox.askyesno(
                "Delete", f"Delete alumnus #{a.alumni_id} "
                            f"({a.full_name})?"):
            return
        try:
            alumni_records.delete_alumnus(a.alumni_id)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        ttk.Button(self.frame, text="Refresh",
                    command=self.refresh).pack(side="top", anchor="w",
                                                 padx=8, pady=(8, 4))
        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.text.configure(state="disabled")

    def refresh(self) -> None:
        summ = alumni_records.summary()
        lines = [
            f"Total alumni      : {summ.total}",
            f"Contactable       : {summ.contactable}",
            f"No contact method : {summ.no_contact_method}",
            f"Most recent year  : {summ.most_recent_year or '—'}",
            "",
            "By status:",
        ]
        for s in STATUSES:
            n = summ.by_status.get(s, 0)
            if n:
                lines.append(f"  {s:<14} : {n}")
        lines.append("")
        lines.append("By destination:")
        for d in DESTINATION_TYPES:
            n = summ.by_destination.get(d, 0)
            if n:
                lines.append(f"  {d:<18} : {n}")
        if summ.by_leaving_year:
            lines.append("")
            lines.append("By leaving year:")
            for year, n in list(summ.by_leaving_year.items())[:15]:
                lines.append(f"  {year} : {n}")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Dialogs ═══════════════════════════════════════════════════════

class StatusDialog:
    def __init__(self, parent: tk.Misc, existing: Alumnus,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title(f"Status — alumnus #{existing.alumni_id}")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="New status:").grid(row=0, column=0,
                                                    sticky="e", pady=4)
        self.cb = ttk.Combobox(form, values=STATUSES,
                                  state="readonly", width=14)
        self.cb.set(existing.status)
        self.cb.grid(row=0, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=1, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            alumni_records.set_status(self.existing.alumni_id, self.cb.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class ArchiveDialog:
    def __init__(self, parent: tk.Misc,
                 on_save: Callable[[], None]) -> None:
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Archive student → alumni")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        students = sorted(student_data.list_students(),
                           key=lambda s: s.student_id)
        self._ids = [s.student_id for s in students]
        ttk.Label(form, text="Student:").grid(row=0, column=0,
                                                 sticky="e", pady=4)
        self.student_cb = ttk.Combobox(
            form,
            values=[f"{s.student_id} — {s.full_name}"
                     for s in students],
            state="readonly", width=44)
        if students:
            self.student_cb.current(0)
        self.student_cb.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Leaving year:").grid(row=1, column=0,
                                                      sticky="e", pady=4)
        self.year_e = ttk.Entry(form, width=8)
        self.year_e.insert(0, str(_dt.date.today().year))
        self.year_e.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Leaving date:").grid(row=2, column=0,
                                                      sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, _today())
        self.date_e.grid(row=2, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Reason:").grid(row=3, column=0,
                                                sticky="e", pady=4)
        self.reason_cb = ttk.Combobox(form, values=LEAVING_REASONS,
                                         state="readonly", width=22)
        self.reason_cb.set(DEFAULT_LEAVING_REASON)
        self.reason_cb.grid(row=3, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Destination:").grid(row=4, column=0,
                                                     sticky="e", pady=4)
        self.dest_cb = ttk.Combobox(form, values=DESTINATION_TYPES,
                                       state="readonly", width=18)
        self.dest_cb.set(DEFAULT_DESTINATION)
        self.dest_cb.grid(row=4, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Destination detail:").grid(row=5, column=0,
                                                            sticky="e",
                                                            pady=4)
        self.detail_e = ttk.Entry(form, width=44)
        self.detail_e.grid(row=5, column=1, sticky="w", padx=6)

        self.delete_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form,
                          text="Also delete the student row "
                                "(cascade-removes history)",
                          variable=self.delete_var).grid(
            row=6, column=1, sticky="w", padx=6, pady=4)

        bar = ttk.Frame(form)
        bar.grid(row=7, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Archive",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        idx = self.student_cb.current()
        if idx < 0:
            messagebox.showerror("Archive", "Pick a student")
            return
        sid = self._ids[idx]
        try:
            alumni_records.archive_student(
                sid,
                leaving_year=self.year_e.get().strip() or None,
                leaving_date=self.date_e.get().strip() or None,
                leaving_reason=self.reason_cb.get().strip() or None,
                destination_type=self.dest_cb.get().strip() or
                                  DEFAULT_DESTINATION,
                destination_detail=self.detail_e.get().strip() or None,
                delete_student=self.delete_var.get(),
            )
        except Exception as e:
            messagebox.showerror("Archive failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class AlumnusDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: Alumnus | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Alumnus" if existing else "New Alumnus")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        def add_row(label: str, widget: tk.Widget) -> None:
            nonlocal r
            ttk.Label(form, text=label).grid(row=r, column=0,
                                                sticky="e", pady=3)
            widget.grid(row=r, column=1, sticky="w", padx=6)
            r += 1

        self.first_e = ttk.Entry(form, width=24)
        if self.existing:
            self.first_e.insert(0, self.existing.first_name)
        add_row("First name:", self.first_e)

        self.last_e = ttk.Entry(form, width=24)
        if self.existing:
            self.last_e.insert(0, self.existing.last_name)
        add_row("Last name:", self.last_e)

        self.preferred_e = ttk.Entry(form, width=24)
        if self.existing and self.existing.preferred_name:
            self.preferred_e.insert(0, self.existing.preferred_name)
        add_row("Preferred name:", self.preferred_e)

        self.pronouns_e = ttk.Entry(form, width=18)
        if self.existing and self.existing.pronouns:
            self.pronouns_e.insert(0, self.existing.pronouns)
        add_row("Pronouns:", self.pronouns_e)

        self.gender_cb = ttk.Combobox(
            form, values=("",) + GENDER_OPTIONS,
            state="readonly", width=22)
        self.gender_cb.set((self.existing.gender or "")
                              if self.existing else "")
        add_row("Gender:", self.gender_cb)

        self.dob_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.dob:
            self.dob_e.insert(0, self.existing.dob)
        add_row("DOB:", self.dob_e)

        self.year_e = ttk.Entry(form, width=8)
        if self.existing and self.existing.leaving_year:
            self.year_e.insert(0, self.existing.leaving_year)
        add_row("Leaving year:", self.year_e)

        self.date_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.leaving_date:
            self.date_e.insert(0, self.existing.leaving_date)
        add_row("Leaving date:", self.date_e)

        self.reason_cb = ttk.Combobox(form, values=("",) + LEAVING_REASONS,
                                         state="readonly", width=22)
        self.reason_cb.set((self.existing.leaving_reason or "")
                              if self.existing else "")
        add_row("Leaving reason:", self.reason_cb)

        self.dest_cb = ttk.Combobox(form, values=DESTINATION_TYPES,
                                       state="readonly", width=18)
        self.dest_cb.set((self.existing.destination_type
                            if self.existing else DEFAULT_DESTINATION))
        add_row("Destination:", self.dest_cb)

        self.dest_detail_e = ttk.Entry(form, width=44)
        if self.existing and self.existing.destination_detail:
            self.dest_detail_e.insert(0, self.existing.destination_detail)
        add_row("Destination detail:", self.dest_detail_e)

        self.role_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.current_role:
            self.role_e.insert(0, self.existing.current_role)
        add_row("Current role:", self.role_e)

        self.employer_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.current_employer:
            self.employer_e.insert(0, self.existing.current_employer)
        add_row("Employer:", self.employer_e)

        self.sector_cb = ttk.Combobox(
            form, values=("",) + SECTORS, state="readonly", width=22)
        self.sector_cb.set((self.existing.current_sector or "")
                              if self.existing else "")
        add_row("Sector:", self.sector_cb)

        self.location_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.current_location:
            self.location_e.insert(0, self.existing.current_location)
        add_row("Location:", self.location_e)

        self.country_e = ttk.Entry(form, width=24)
        if self.existing and self.existing.country:
            self.country_e.insert(0, self.existing.country)
        add_row("Country:", self.country_e)

        self.region_e = ttk.Entry(form, width=24)
        if self.existing and self.existing.region:
            self.region_e.insert(0, self.existing.region)
        add_row("Region:", self.region_e)

        self.email_e = ttk.Entry(form, width=30)
        if self.existing and self.existing.email:
            self.email_e.insert(0, self.existing.email)
        add_row("Email:", self.email_e)

        self.phone_e = ttk.Entry(form, width=20)
        if self.existing and self.existing.phone:
            self.phone_e.insert(0, self.existing.phone)
        add_row("Phone:", self.phone_e)

        self.linkedin_e = ttk.Entry(form, width=44)
        if self.existing and self.existing.linkedin:
            self.linkedin_e.insert(0, self.existing.linkedin)
        add_row("LinkedIn:", self.linkedin_e)

        self.photo_e = ttk.Entry(form, width=44)
        if self.existing and self.existing.photo_path:
            self.photo_e.insert(0, self.existing.photo_path)
        add_row("Photo path:", self.photo_e)

        ttk.Label(form, text="Bio:").grid(row=r, column=0,
                                              sticky="ne", pady=3)
        self.bio_t = tk.Text(form, width=44, height=3)
        if self.existing and self.existing.bio:
            self.bio_t.insert("1.0", self.existing.bio)
        self.bio_t.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        self.opt_var = tk.BooleanVar(
            value=(self.existing.opt_in_contact
                   if self.existing else False))
        ttk.Checkbutton(form, text="Opt-in to contact",
                          variable=self.opt_var).grid(
            row=r, column=1, sticky="w", padx=6, pady=3)
        r += 1

        self.status_cb = ttk.Combobox(form, values=STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status
                              if self.existing else DEFAULT_STATUS)
        add_row("Status:", self.status_cb)

        self.last_e = ttk.Entry(form, width=14)
        if self.existing and self.existing.last_contacted:
            self.last_e.insert(0, self.existing.last_contacted)
        add_row("Last contacted:", self.last_e)

        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=3)
        self.notes_t = tk.Text(form, width=44, height=4)
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
        return {
            "first_name":         self.first_e.get().strip(),
            "last_name":          self.last_e.get().strip(),
            "preferred_name":     self.preferred_e.get().strip(),
            "pronouns":           self.pronouns_e.get().strip(),
            "gender":             self.gender_cb.get().strip(),
            "dob":                self.dob_e.get().strip(),
            "leaving_year":       self.year_e.get().strip(),
            "leaving_date":       self.date_e.get().strip(),
            "leaving_reason":     self.reason_cb.get().strip(),
            "destination_type":   self.dest_cb.get().strip(),
            "destination_detail": self.dest_detail_e.get().strip(),
            "current_role":       self.role_e.get().strip(),
            "current_employer":   self.employer_e.get().strip(),
            "current_sector":     self.sector_cb.get().strip(),
            "current_location":   self.location_e.get().strip(),
            "country":            self.country_e.get().strip(),
            "region":             self.region_e.get().strip(),
            "email":              self.email_e.get().strip(),
            "phone":              self.phone_e.get().strip(),
            "linkedin":           self.linkedin_e.get().strip(),
            "photo_path":         self.photo_e.get().strip(),
            "bio":                self.bio_t.get("1.0", "end").strip(),
            "opt_in_contact":     self.opt_var.get(),
            "status":             self.status_cb.get().strip(),
            "last_contacted":     self.last_e.get().strip(),
            "notes":              self.notes_t.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            payload = self._collect()
            if self.existing:
                alumni_records.update_alumnus(self.existing.alumni_id, payload)
            else:
                alumni_records.create_alumnus(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Detail window (per-alumnus sub-tabs) ═══════════════════════════

class DetailWindow:
    """Per-alumnus window with sub-tabs for education, career,
    contacts, tags, achievements."""

    def __init__(self, parent: tk.Misc, alumnus: Alumnus) -> None:
        self.alumnus = alumnus
        self.win = tk.Toplevel(parent)
        self.win.title(f"Alumnus #{alumnus.alumni_id} — "
                         f"{alumnus.display_name}")
        self.win.geometry("1000x650")
        self.win.minsize(800, 500)
        self.win.transient(parent)

        header = ttk.Frame(self.win, padding=8)
        header.pack(fill="x")
        ttk.Label(header,
                    text=f"#{alumnus.alumni_id}  {alumnus.display_name}",
                    font=("TkDefaultFont", 12, "bold")
                    ).pack(side="left")
        bits = []
        if alumnus.pronouns:
            bits.append(alumnus.pronouns)
        if alumnus.current_role and alumnus.current_employer:
            bits.append(f"{alumnus.current_role} @ "
                         f"{alumnus.current_employer}")
        if alumnus.current_sector:
            bits.append(alumnus.current_sector)
        if bits:
            ttk.Label(header, text="  ·  ".join(bits),
                        foreground="#555").pack(side="left", padx=12)
        if alumnus.bio:
            ttk.Label(self.win, text=alumnus.bio,
                        foreground="#444", wraplength=960,
                        padding=(8, 0, 8, 6)).pack(fill="x")

        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        EducationTab(nb, alumnus.alumni_id)
        CareerTab(nb, alumnus.alumni_id)
        ContactsTab(nb, alumnus.alumni_id)
        TagsTab(nb, alumnus.alumni_id)
        AchievementsTab(nb, alumnus.alumni_id)
        CommsTab(nb, alumnus.alumni_id)
        ChannelPrefsTab(nb, alumnus.alumni_id)
        ConsentTab(nb, alumnus.alumni_id)
        MentoringTab(nb, alumnus.alumni_id)
        SpeakerTab(nb, alumnus.alumni_id)
        VolunteeringTab(nb, alumnus.alumni_id)
        DonationsTab(nb, alumnus.alumni_id)
        SocialHandlesTab(nb, alumnus.alumni_id)
        ConnectionsTab(nb, alumnus.alumni_id)
        EngagementTab(nb, alumnus.alumni_id)
        ChapterMembershipTab(nb, alumnus.alumni_id)
        DirectoryConsentTab(nb, alumnus.alumni_id)
        SkillsTab(nb, alumnus.alumni_id)
        PromotionTimelineTab(nb, alumnus.alumni_id)
        MentorProfileTab(nb, alumnus.alumni_id)
        SafeguardingTab(nb, alumnus.alumni_id)
        SMSTab(nb, alumnus.alumni_id)
        NEETChecksTab(nb, alumnus.alumni_id)
        GiftAidTab(nb, alumnus.alumni_id)
        ProtectedCharsTab(nb, alumnus.alumni_id)
        CustomValuesTab(nb, alumnus.alumni_id)
        MediaTab(nb, alumnus.alumni_id)
