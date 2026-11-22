"""Per-alumnus profile sub-tabs: education, career, contacts, tags, achievements, comms, channel prefs, consent."""

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
    comms as alumni_comms,
    compliance as alumni_compliance,
    profile as alumni_profile,
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
    _today,
)


# ── Education sub-tab ─────────────────────────────────────────────

class EducationTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Education")
        cols = ("id", "qualification", "subject", "institution",
                "span", "grade", "status")
        self.tree = ttk.Treeview(self.frame, columns=cols, show="headings")
        widths = {"id": 40, "qualification": 110, "subject": 140,
                  "institution": 180, "span": 160, "grade": 90,
                  "status": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=4, pady=(0, 4))
        ttk.Button(bar, text="Add",  command=self._add).pack(side="left")
        ttk.Button(bar, text="Edit", command=self._edit).pack(side="left",
                                                                padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        for e in alumni_profile.list_education(self.alumni_id):
            span = f"{e.start_date or '?'} → {e.end_date or '…'}"
            self.tree.insert("", "end", iid=str(e.education_id), values=(
                e.education_id, e.qualification, e.subject or "—",
                e.institution, span, e.grade or "—", e.status))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self) -> None:
        EducationDialog(self.frame.winfo_toplevel(),
                          alumni_id=self.alumni_id, existing=None,
                          on_save=self.refresh)

    def _edit(self) -> None:
        eid = self._selected_id()
        if eid is None:
            return
        cur = next((x for x in alumni_profile.list_education(self.alumni_id)
                      if x.education_id == eid), None)
        if cur is None:
            return
        EducationDialog(self.frame.winfo_toplevel(),
                          alumni_id=self.alumni_id, existing=cur,
                          on_save=self.refresh)

    def _delete(self) -> None:
        eid = self._selected_id()
        if eid is None:
            return
        if not messagebox.askyesno("Delete",
                                      f"Delete education row #{eid}?"):
            return
        alumni_profile.delete_education(eid)
        self.refresh()


class EducationDialog:
    def __init__(self, parent: tk.Misc, *, alumni_id: int,
                 existing, on_save: Callable[[], None]) -> None:
        self.alumni_id = alumni_id
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Education" if existing else "Add Education")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        def row(label: str, w: tk.Widget) -> None:
            nonlocal r
            ttk.Label(form, text=label).grid(row=r, column=0,
                                                sticky="e", pady=3)
            w.grid(row=r, column=1, sticky="w", padx=6)
            r += 1

        self.qual_e = ttk.Entry(form, width=28)
        self.subj_e = ttk.Entry(form, width=28)
        self.inst_e = ttk.Entry(form, width=32)
        self.start_e = ttk.Entry(form, width=14)
        self.end_e   = ttk.Entry(form, width=14)
        self.grade_e = ttk.Entry(form, width=14)
        self.status_cb = ttk.Combobox(form, values=EDUCATION_STATUSES,
                                         state="readonly", width=16)
        self.status_cb.set(DEFAULT_EDUCATION_STATUS)
        self.notes_t = tk.Text(form, width=32, height=3)
        if existing:
            self.qual_e.insert(0, existing.qualification)
            if existing.subject:    self.subj_e.insert(0, existing.subject)
            self.inst_e.insert(0, existing.institution)
            if existing.start_date: self.start_e.insert(0,
                                                          existing.start_date)
            if existing.end_date:   self.end_e.insert(0, existing.end_date)
            if existing.grade:      self.grade_e.insert(0, existing.grade)
            self.status_cb.set(existing.status)
            if existing.notes:      self.notes_t.insert("1.0",
                                                          existing.notes)

        row("Qualification:", self.qual_e)
        row("Subject:",       self.subj_e)
        row("Institution:",   self.inst_e)
        row("Start date:",    self.start_e)
        row("End date:",      self.end_e)
        row("Grade:",         self.grade_e)
        row("Status:",        self.status_cb)
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                                sticky="ne", pady=3)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6)
        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        payload = {
            "qualification": self.qual_e.get().strip(),
            "subject":       self.subj_e.get().strip(),
            "institution":   self.inst_e.get().strip(),
            "start_date":    self.start_e.get().strip(),
            "end_date":      self.end_e.get().strip(),
            "grade":         self.grade_e.get().strip(),
            "status":        self.status_cb.get(),
            "notes":         self.notes_t.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                alumni_profile.update_education(self.existing.education_id, payload)
            else:
                alumni_profile.add_education(self.alumni_id, payload)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ── Career sub-tab ────────────────────────────────────────────────

class CareerTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Career")
        cols = ("id", "role", "employer", "sector", "country",
                "span", "current", "salary")
        self.tree = ttk.Treeview(self.frame, columns=cols, show="headings")
        widths = {"id": 40, "role": 140, "employer": 140, "sector": 130,
                  "country": 110, "span": 160, "current": 70, "salary": 110}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=4, pady=(0, 4))
        ttk.Button(bar, text="Add",  command=self._add).pack(side="left")
        ttk.Button(bar, text="Edit", command=self._edit).pack(side="left",
                                                                padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        for c in alumni_profile.list_career(self.alumni_id):
            span = (f"{c.start_date or '?'} → "
                     + ("present" if c.is_current
                        else (c.end_date or '?')))
            self.tree.insert("", "end", iid=str(c.career_id), values=(
                c.career_id, c.role, c.employer, c.sector or "—",
                c.country or "—", span,
                "✓" if c.is_current else "",
                c.salary_band or "—"))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self) -> None:
        CareerDialog(self.frame.winfo_toplevel(),
                       alumni_id=self.alumni_id, existing=None,
                       on_save=self.refresh)

    def _edit(self) -> None:
        cid = self._selected_id()
        if cid is None:
            return
        cur = next((x for x in alumni_profile.list_career(self.alumni_id)
                      if x.career_id == cid), None)
        if cur is None:
            return
        CareerDialog(self.frame.winfo_toplevel(),
                       alumni_id=self.alumni_id, existing=cur,
                       on_save=self.refresh)

    def _delete(self) -> None:
        cid = self._selected_id()
        if cid is None:
            return
        if not messagebox.askyesno("Delete",
                                      f"Delete career row #{cid}?"):
            return
        alumni_profile.delete_career(cid)
        self.refresh()


class CareerDialog:
    def __init__(self, parent: tk.Misc, *, alumni_id: int,
                 existing, on_save: Callable[[], None]) -> None:
        self.alumni_id = alumni_id
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Career" if existing else "Add Career")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        def row(label: str, w: tk.Widget) -> None:
            nonlocal r
            ttk.Label(form, text=label).grid(row=r, column=0,
                                                sticky="e", pady=3)
            w.grid(row=r, column=1, sticky="w", padx=6)
            r += 1

        self.role_e = ttk.Entry(form, width=30)
        self.emp_e  = ttk.Entry(form, width=30)
        self.sector_cb = ttk.Combobox(form,
                                         values=("",) + SECTORS,
                                         state="readonly", width=24)
        self.country_e = ttk.Entry(form, width=24)
        self.loc_e     = ttk.Entry(form, width=30)
        self.start_e   = ttk.Entry(form, width=14)
        self.end_e     = ttk.Entry(form, width=14)
        self.cur_var   = tk.BooleanVar(value=False)
        self.band_cb   = ttk.Combobox(form,
                                          values=("",) + SALARY_BANDS,
                                          state="readonly", width=20)
        self.notes_t   = tk.Text(form, width=32, height=3)
        if existing:
            self.role_e.insert(0, existing.role)
            self.emp_e.insert(0, existing.employer)
            self.sector_cb.set(existing.sector or "")
            if existing.country:  self.country_e.insert(0, existing.country)
            if existing.location: self.loc_e.insert(0, existing.location)
            if existing.start_date:
                self.start_e.insert(0, existing.start_date)
            if existing.end_date:
                self.end_e.insert(0, existing.end_date)
            self.cur_var.set(existing.is_current)
            self.band_cb.set(existing.salary_band or "")
            if existing.notes:    self.notes_t.insert("1.0",
                                                       existing.notes)

        row("Role:",        self.role_e)
        row("Employer:",    self.emp_e)
        row("Sector:",      self.sector_cb)
        row("Country:",     self.country_e)
        row("Location:",    self.loc_e)
        row("Start date:",  self.start_e)
        row("End date:",    self.end_e)
        ttk.Checkbutton(form, text="Current role",
                          variable=self.cur_var).grid(
            row=r, column=1, sticky="w", padx=6, pady=3)
        r += 1
        row("Salary band:", self.band_cb)
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                                sticky="ne", pady=3)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6)
        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        payload = {
            "role":        self.role_e.get().strip(),
            "employer":    self.emp_e.get().strip(),
            "sector":      self.sector_cb.get().strip(),
            "country":     self.country_e.get().strip(),
            "location":    self.loc_e.get().strip(),
            "start_date":  self.start_e.get().strip(),
            "end_date":    self.end_e.get().strip(),
            "is_current":  self.cur_var.get(),
            "salary_band": self.band_cb.get().strip(),
            "notes":       self.notes_t.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                alumni_profile.update_career(self.existing.career_id, payload)
            else:
                alumni_profile.add_career(self.alumni_id, payload)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ── Contacts sub-tab (emails + phones) ────────────────────────────

class ContactsTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Contacts")
        # Emails
        ttk.Label(self.frame, text="Emails",
                    font=("TkDefaultFont", 10, "bold")
                    ).pack(anchor="w", padx=6, pady=(6, 0))
        self.em_tree = ttk.Treeview(
            self.frame, columns=("id", "label", "email", "primary"),
            show="headings", height=5)
        for c, w in (("id", 40), ("label", 100), ("email", 280),
                      ("primary", 70)):
            self.em_tree.heading(c, text=c.title())
            self.em_tree.column(c, width=w, anchor="w")
        self.em_tree.pack(fill="x", padx=6, pady=4)
        embar = ttk.Frame(self.frame); embar.pack(fill="x", padx=6)
        ttk.Button(embar, text="Add email",
                    command=self._add_email).pack(side="left")
        ttk.Button(embar, text="Make primary",
                    command=self._make_email_primary).pack(side="left",
                                                              padx=4)
        ttk.Button(embar, text="Delete email",
                    command=self._delete_email).pack(side="left")
        # Phones
        ttk.Label(self.frame, text="Phones",
                    font=("TkDefaultFont", 10, "bold")
                    ).pack(anchor="w", padx=6, pady=(12, 0))
        self.ph_tree = ttk.Treeview(
            self.frame, columns=("id", "label", "phone", "primary"),
            show="headings", height=5)
        for c, w in (("id", 40), ("label", 100), ("phone", 200),
                      ("primary", 70)):
            self.ph_tree.heading(c, text=c.title())
            self.ph_tree.column(c, width=w, anchor="w")
        self.ph_tree.pack(fill="x", padx=6, pady=4)
        phbar = ttk.Frame(self.frame); phbar.pack(fill="x", padx=6)
        ttk.Button(phbar, text="Add phone",
                    command=self._add_phone).pack(side="left")
        ttk.Button(phbar, text="Make primary",
                    command=self._make_phone_primary).pack(side="left",
                                                              padx=4)
        ttk.Button(phbar, text="Delete phone",
                    command=self._delete_phone).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.em_tree.get_children(): self.em_tree.delete(i)
        for e in alumni_profile.list_emails(self.alumni_id):
            self.em_tree.insert("", "end", iid=str(e.email_id), values=(
                e.email_id, e.label, e.email,
                "✓" if e.is_primary else ""))
        for i in self.ph_tree.get_children(): self.ph_tree.delete(i)
        for p in alumni_profile.list_phones(self.alumni_id):
            self.ph_tree.insert("", "end", iid=str(p.phone_id), values=(
                p.phone_id, p.label, p.phone,
                "✓" if p.is_primary else ""))

    def _ask(self, title: str, *fields: tuple[str, list[str] | None]
                ) -> dict[str, str] | None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title(title); win.transient(self.frame.winfo_toplevel())
        grab_when_viewable(win)
        form = ttk.Frame(win, padding=12); form.pack(fill="both",
                                                          expand=True)
        widgets: dict[str, tk.Widget] = {}
        for i, (name, choices) in enumerate(fields):
            ttk.Label(form, text=f"{name}:").grid(row=i, column=0,
                                                     sticky="e", pady=3)
            if choices is None:
                w = ttk.Entry(form, width=32)
            else:
                w = ttk.Combobox(form, values=choices,
                                    state="readonly", width=22)
                w.current(0)
            w.grid(row=i, column=1, sticky="w", padx=6)
            widgets[name] = w
        result: dict[str, str] = {}

        def save() -> None:
            for name, w in widgets.items():
                result[name] = w.get().strip()
            win.destroy()

        bar = ttk.Frame(form); bar.grid(row=len(fields), column=0,
                                          columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=win.destroy).pack(side="left", padx=8)
        win.wait_window()
        return result or None

    def _add_email(self) -> None:
        res = self._ask("Add email", ("Email", None),
                          ("Label", list(EMAIL_LABELS)),
                          ("Primary?", ["No", "Yes"]))
        if not res or not res.get("Email"):
            return
        try:
            alumni_profile.add_email(self.alumni_id, res["Email"],
                             label=res.get("Label") or "Personal",
                             is_primary=(res.get("Primary?") == "Yes"))
        except Exception as e:
            messagebox.showerror("Add email", str(e)); return
        self.refresh()

    def _add_phone(self) -> None:
        res = self._ask("Add phone", ("Phone", None),
                          ("Label", list(PHONE_LABELS)),
                          ("Primary?", ["No", "Yes"]))
        if not res or not res.get("Phone"):
            return
        try:
            alumni_profile.add_phone(self.alumni_id, res["Phone"],
                             label=res.get("Label") or "Mobile",
                             is_primary=(res.get("Primary?") == "Yes"))
        except Exception as e:
            messagebox.showerror("Add phone", str(e)); return
        self.refresh()

    def _make_email_primary(self) -> None:
        sel = self.em_tree.selection()
        if not sel: return
        alumni_profile.set_primary_email(int(sel[0])); self.refresh()

    def _make_phone_primary(self) -> None:
        sel = self.ph_tree.selection()
        if not sel: return
        alumni_profile.set_primary_phone(int(sel[0])); self.refresh()

    def _delete_email(self) -> None:
        sel = self.em_tree.selection()
        if not sel: return
        if messagebox.askyesno("Delete", "Delete this email?"):
            alumni_profile.delete_email(int(sel[0])); self.refresh()

    def _delete_phone(self) -> None:
        sel = self.ph_tree.selection()
        if not sel: return
        if messagebox.askyesno("Delete", "Delete this phone?"):
            alumni_profile.delete_phone(int(sel[0])); self.refresh()


# ── Tags sub-tab ──────────────────────────────────────────────────

class TagsTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Tags")
        ttk.Label(self.frame, text="Attached tags",
                    font=("TkDefaultFont", 10, "bold")
                    ).pack(anchor="w", padx=6, pady=(6, 0))
        self.tree = ttk.Treeview(self.frame, columns=("id", "name"),
                                    show="headings", height=8)
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Tag")
        self.tree.column("id", width=50, anchor="w")
        self.tree.column("name", width=320, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=6, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=6, pady=4)
        self.entry = ttk.Entry(bar, width=30)
        self.entry.pack(side="left")
        ttk.Button(bar, text="Add / attach",
                    command=self._add).pack(side="left", padx=4)
        ttk.Button(bar, text="Remove from alumnus",
                    command=self._remove).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for t in alumni_profile.list_tags_for(self.alumni_id):
            self.tree.insert("", "end", iid=str(t.tag_id),
                              values=(t.tag_id, t.name))

    def _add(self) -> None:
        name = self.entry.get().strip()
        if not name:
            return
        try:
            alumni_profile.add_tag(self.alumni_id, name)
        except Exception as e:
            messagebox.showerror("Add tag", str(e)); return
        self.entry.delete(0, "end")
        self.refresh()

    def _remove(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        alumni_profile.remove_tag(self.alumni_id, int(sel[0]))
        self.refresh()


# ── Achievements sub-tab ──────────────────────────────────────────

class AchievementsTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Achievements")
        cols = ("id", "date", "category", "title", "url")
        self.tree = ttk.Treeview(self.frame, columns=cols, show="headings")
        widths = {"id": 40, "date": 100, "category": 130,
                  "title": 320, "url": 240}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4)
        ttk.Button(bar, text="Add",
                    command=self._add).pack(side="left")
        ttk.Button(bar, text="Edit",
                    command=self._edit).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for x in alumni_profile.list_achievements(self.alumni_id):
            self.tree.insert("", "end", iid=str(x.achievement_id),
                              values=(x.achievement_id, x.date or "—",
                                       x.category or "—", x.title,
                                       x.url or ""))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add(self) -> None:
        AchievementDialog(self.frame.winfo_toplevel(),
                            alumni_id=self.alumni_id, existing=None,
                            on_save=self.refresh)

    def _edit(self) -> None:
        aid = self._selected_id()
        if aid is None:
            return
        cur = next((x for x in alumni_profile.list_achievements(self.alumni_id)
                      if x.achievement_id == aid), None)
        if cur is None:
            return
        AchievementDialog(self.frame.winfo_toplevel(),
                            alumni_id=self.alumni_id, existing=cur,
                            on_save=self.refresh)

    def _delete(self) -> None:
        aid = self._selected_id()
        if aid is None:
            return
        if messagebox.askyesno("Delete",
                                  f"Delete achievement #{aid}?"):
            alumni_profile.delete_achievement(aid)
            self.refresh()


class AchievementDialog:
    def __init__(self, parent: tk.Misc, *, alumni_id: int,
                 existing, on_save: Callable[[], None]) -> None:
        self.alumni_id = alumni_id
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Achievement" if existing
                          else "Add Achievement")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)
        r = 0

        def row(label: str, w: tk.Widget) -> None:
            nonlocal r
            ttk.Label(form, text=label).grid(row=r, column=0,
                                                sticky="e", pady=3)
            w.grid(row=r, column=1, sticky="w", padx=6)
            r += 1

        self.title_e = ttk.Entry(form, width=44)
        self.date_e  = ttk.Entry(form, width=14)
        self.cat_cb  = ttk.Combobox(form,
                                       values=("",) + ACHIEVEMENT_CATEGORIES,
                                       state="readonly", width=22)
        self.url_e   = ttk.Entry(form, width=44)
        self.desc_t  = tk.Text(form, width=44, height=4)
        if existing:
            self.title_e.insert(0, existing.title)
            if existing.date: self.date_e.insert(0, existing.date)
            self.cat_cb.set(existing.category or "")
            if existing.url:  self.url_e.insert(0, existing.url)
            if existing.description:
                self.desc_t.insert("1.0", existing.description)
        row("Title:",    self.title_e)
        row("Date:",     self.date_e)
        row("Category:", self.cat_cb)
        row("URL:",      self.url_e)
        ttk.Label(form, text="Description:").grid(row=r, column=0,
                                                       sticky="ne", pady=3)
        self.desc_t.grid(row=r, column=1, sticky="w", padx=6)
        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        payload = {
            "title":       self.title_e.get().strip(),
            "date":        self.date_e.get().strip(),
            "category":    self.cat_cb.get().strip(),
            "url":         self.url_e.get().strip(),
            "description": self.desc_t.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                alumni_profile.update_achievement(
                    self.existing.achievement_id, payload)
            else:
                alumni_profile.add_achievement(self.alumni_id, payload)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ── Communications sub-tab ────────────────────────────────────────

class CommsTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Comms")
        cols = ("id", "date", "channel", "status", "subject")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "date": 100, "channel": 90,
                  "status": 90, "subject": 480}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.bounce_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.bounce_var,
                    foreground="#a64",
                    anchor="w").pack(fill="x", padx=6)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4, pady=4)
        ttk.Button(bar, text="Add",
                    command=self._add).pack(side="left")
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(bar, text="Send email…",
                    command=self._send_email).pack(side="left", padx=12)
        ttk.Button(bar, text="Record bounce",
                    command=self._bounce).pack(side="left")
        ttk.Button(bar, text="Clear bounces",
                    command=self._clear_bounces).pack(side="left",
                                                         padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for c in alumni_comms.list_communications(self.alumni_id):
            when = (c.sent_at or c.received_at or c.created_at or ""
                      )[:16]
            self.tree.insert("", "end", iid=str(c.message_id), values=(
                c.message_id, when, c.channel, c.status,
                c.subject or ""))
        a = alumni_records.get_alumnus(self.alumni_id)
        self.bounce_var.set(
            f"Bounce count: {a.bounce_count}" if a else "")

    def _add(self) -> None:
        CommDialog(self.frame.winfo_toplevel(),
                     alumni_id=self.alumni_id,
                     on_save=self.refresh)

    def _delete(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        if messagebox.askyesno("Delete",
                                  f"Delete comm #{sel[0]}?"):
            alumni_comms.delete_communication(int(sel[0]))
            self.refresh()

    def _send_email(self) -> None:
        SendEmailDialog(self.frame.winfo_toplevel(),
                         alumni_id=self.alumni_id,
                         on_save=self.refresh)

    def _bounce(self) -> None:
        if messagebox.askyesno("Bounce",
                                  "Record a hard bounce for this "
                                  "alumnus?"):
            alumni_comms.record_bounce(self.alumni_id, hard=True)
            self.refresh()

    def _clear_bounces(self) -> None:
        alumni_comms.clear_bounces(self.alumni_id)
        self.refresh()


class CommDialog:
    def __init__(self, parent: tk.Misc, *, alumni_id: int,
                 on_save: Callable[[], None]) -> None:
        self.alumni_id = alumni_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Add communication")
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

        self.date_e = ttk.Entry(form, width=14)
        self.date_e.insert(0, _today())
        self.channel_cb = ttk.Combobox(form, values=COMM_CHANNELS,
                                          state="readonly", width=14)
        self.channel_cb.set("Email")
        self.status_cb = ttk.Combobox(form, values=COMM_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set("Sent")
        self.staff_e = ttk.Entry(form, width=20)
        self.subj_e  = ttk.Entry(form, width=44)
        self.summ_t  = tk.Text(form, width=44, height=4)
        row("Date:",    self.date_e)
        row("Channel:", self.channel_cb)
        row("Status:",  self.status_cb)
        row("Staff id:", self.staff_e)
        row("Subject:", self.subj_e)
        ttk.Label(form, text="Summary:").grid(row=r, column=0,
                                                  sticky="ne", pady=3)
        self.summ_t.grid(row=r, column=1, sticky="w", padx=6); r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        try:
            alumni_comms.add_communication(self.alumni_id, {
                "date":     self.date_e.get().strip(),
                "channel":  self.channel_cb.get(),
                "status":   self.status_cb.get(),
                "staff_id": self.staff_e.get().strip(),
                "subject":  self.subj_e.get().strip(),
                "summary":  self.summ_t.get("1.0", "end").strip(),
            })
        except Exception as e:
            messagebox.showerror("Save failed", str(e)); return
        self.win.destroy()
        self.on_save()


class SendEmailDialog:
    def __init__(self, parent: tk.Misc, *, alumni_id: int,
                 on_save: Callable[[], None]) -> None:
        self.alumni_id = alumni_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Send email")
        self.win.transient(parent); grab_when_viewable(self.win)
        form = ttk.Frame(self.win, padding=12); form.pack(fill="both",
                                                              expand=True)
        ttk.Label(form,
                    text=("Placeholders: {first_name} {last_name} "
                           "{preferred_name} {leaving_year}"),
                    foreground="#666"
                    ).grid(row=0, column=0, columnspan=2,
                            sticky="w", pady=(0, 6))
        ttk.Label(form, text="Subject:").grid(row=1, column=0,
                                                  sticky="e", pady=3)
        self.subj_e = ttk.Entry(form, width=60)
        self.subj_e.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Staff id:").grid(row=2, column=0,
                                                  sticky="e", pady=3)
        self.staff_e = ttk.Entry(form, width=20)
        self.staff_e.grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Body:").grid(row=3, column=0,
                                               sticky="ne", pady=3)
        self.body_t = tk.Text(form, width=60, height=10)
        self.body_t.grid(row=3, column=1, sticky="w", padx=6)
        bar = ttk.Frame(form)
        bar.grid(row=4, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Send",
                    command=self._send).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _send(self) -> None:
        try:
            ok = alumni_comms.send_email_to_alumnus(
                self.alumni_id, self.subj_e.get().strip(),
                self.body_t.get("1.0", "end").strip(),
                staff_id=self.staff_e.get().strip() or None)
        except Exception as e:
            messagebox.showerror("Send failed", str(e)); return
        note = alumni_comms.delivery_note(ok)
        if ok.status == "Failed":
            messagebox.showwarning("Not sent", note, parent=self.win)
        else:
            messagebox.showinfo("Sent" if ok.status == "Sent" else "Queued",
                                note, parent=self.win)
        self.win.destroy()
        self.on_save()


# ── Channel-prefs sub-tab ─────────────────────────────────────────

class ChannelPrefsTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Channels")
        wrap = ttk.Frame(self.frame, padding=12); wrap.pack(fill="x")
        self.email_var = tk.BooleanVar()
        self.post_var  = tk.BooleanVar()
        self.phone_var = tk.BooleanVar()
        self.sms_var   = tk.BooleanVar()
        ttk.Label(wrap, text="Channel preferences",
                    font=("TkDefaultFont", 10, "bold")
                    ).grid(row=0, column=0, columnspan=2,
                            sticky="w", pady=(0, 6))
        ttk.Checkbutton(wrap, text="Email",
                          variable=self.email_var).grid(
            row=1, column=0, sticky="w")
        ttk.Checkbutton(wrap, text="Post",
                          variable=self.post_var).grid(
            row=2, column=0, sticky="w")
        ttk.Checkbutton(wrap, text="Phone",
                          variable=self.phone_var).grid(
            row=3, column=0, sticky="w")
        ttk.Checkbutton(wrap, text="SMS",
                          variable=self.sms_var).grid(
            row=4, column=0, sticky="w")
        ttk.Button(wrap, text="Save",
                    command=self._save).grid(row=5, column=0,
                                                pady=(10, 0))
        self.refresh()

    def refresh(self) -> None:
        p = alumni_comms.get_channel_prefs(self.alumni_id)
        self.email_var.set(p.opt_in_email)
        self.post_var.set(p.opt_in_post)
        self.phone_var.set(p.opt_in_phone)
        self.sms_var.set(p.opt_in_sms)

    def _save(self) -> None:
        try:
            alumni_comms.update_channel_prefs(
                self.alumni_id,
                opt_in_email=self.email_var.get(),
                opt_in_post=self.post_var.get(),
                opt_in_phone=self.phone_var.get(),
                opt_in_sms=self.sms_var.get())
        except Exception as e:
            messagebox.showerror("Save failed", str(e)); return
        messagebox.showinfo("Saved", "Channel preferences updated.")


# ── Consent sub-tab ───────────────────────────────────────────────

class ConsentTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Consent")
        cols = ("id", "scope", "version", "granted_at",
                "withdrawn_at", "source")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "scope": 130, "version": 70,
                  "granted_at": 160, "withdrawn_at": 160,
                  "source": 200}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4, pady=4)
        self.scope_cb = ttk.Combobox(bar, values=CONSENT_SCOPES,
                                        state="readonly", width=18)
        self.scope_cb.set(CONSENT_SCOPES[0])
        self.scope_cb.pack(side="left")
        self.source_e = ttk.Entry(bar, width=22)
        self.source_e.pack(side="left", padx=4)
        ttk.Button(bar, text="Grant",
                    command=self._grant).pack(side="left", padx=4)
        ttk.Button(bar, text="Withdraw selected",
                    command=self._withdraw).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for c in alumni_compliance.list_consents(self.alumni_id):
            self.tree.insert("", "end", iid=str(c.consent_id),
                              values=(c.consent_id, c.scope, c.version,
                                       c.granted_at,
                                       c.withdrawn_at or "—",
                                       c.source or ""))

    def _grant(self) -> None:
        try:
            alumni_compliance.grant_consent(self.alumni_id,
                                 self.scope_cb.get(),
                                 source=self.source_e.get().strip()
                                          or None)
        except Exception as e:
            messagebox.showerror("Grant failed", str(e)); return
        self.source_e.delete(0, "end")
        self.refresh()

    def _withdraw(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        try:
            alumni_compliance.withdraw_consent(int(sel[0]))
        except Exception as e:
            messagebox.showerror("Withdraw failed", str(e)); return
        self.refresh()
