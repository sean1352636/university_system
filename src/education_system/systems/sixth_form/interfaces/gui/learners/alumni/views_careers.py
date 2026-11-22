"""Career & network: skills, promotion timeline, employers, jobs, internships, mentor matching, mentor profile."""

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
    careers as alumni_careers,
    mentoring as alumni_mentoring,
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
    _ask_choice,
    _money_str,
    _pick_alumnus_dialog,
    _prompt_string,
)


# ══ Career-cluster extensions (items 9–16) ════════════════════════

# ── Per-alumnus: Skills ───────────────────────────────────────────

class SkillsTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Skills")
        cols = ("id", "name", "proficiency", "years")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "name": 240, "proficiency": 130,
                    "years": 80}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=4)
        ttk.Label(bar, text="Skill:").pack(side="left")
        self.entry = ttk.Entry(bar, width=20); self.entry.pack(side="left",
                                                                   padx=4)
        self.prof = ttk.Combobox(bar, values=list(PROFICIENCY_LEVELS),
                                    state="readonly", width=12)
        self.prof.set("Intermediate"); self.prof.pack(side="left")
        ttk.Label(bar, text="Years:").pack(side="left", padx=(8, 0))
        self.years = ttk.Entry(bar, width=6); self.years.pack(side="left",
                                                                   padx=4)
        ttk.Button(bar, text="Add / update",
                     command=self._add).pack(side="left", padx=4)
        ttk.Button(bar, text="Remove selected",
                     command=self._remove).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for s in alumni_careers.list_skills_for(self.alumni_id):
            self.tree.insert(
                "", "end", iid=str(s.skill_id),
                values=(s.skill_id, s.skill_name, s.proficiency,
                          s.years if s.years is not None else "—"))

    def _add(self) -> None:
        name = self.entry.get().strip()
        if not name: return
        yrs_raw = self.years.get().strip()
        try:
            yrs = float(yrs_raw) if yrs_raw else None
            alumni_careers.add_skill_to_alumnus(self.alumni_id, name,
                                          proficiency=self.prof.get(),
                                          years=yrs)
        except Exception as e:
            messagebox.showerror("Add skill", str(e)); return
        self.entry.delete(0, "end"); self.years.delete(0, "end")
        self.refresh()

    def _remove(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        alumni_careers.remove_skill_from_alumnus(self.alumni_id, int(sel[0]))
        self.refresh()


# ── Per-alumnus: Promotion timeline ──────────────────────────────

class PromotionTimelineTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Timeline")
        cols = ("start", "end", "role", "employer", "current")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"start": 100, "end": 100, "role": 220,
                    "employer": 220, "current": 80}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)
        ttk.Button(self.frame, text="Refresh",
                     command=self.refresh).pack(anchor="w",
                                                  padx=4, pady=4)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for s in alumni_careers.promotion_timeline(self.alumni_id):
            self.tree.insert(
                "", "end",
                values=(s.start_date or "—", s.end_date or "—",
                          s.role, s.employer,
                          "✓" if s.is_current else ""))


# ── Top-level: Employers directory ───────────────────────────────

class EmployersTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Employers")
        cols = ("id", "name", "sector", "website", "country")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "name": 260, "sector": 130,
                    "website": 220, "country": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8,
                                                  pady=(0, 8))
        ttk.Button(bar, text="Add / update",
                     command=self._upsert).pack(side="left")
        ttk.Button(bar, text="Add alias",
                     command=self._alias).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                     command=self._delete).pack(side="left")
        ttk.Button(bar, text="Top employers report",
                     command=self._top).pack(side="left", padx=12)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for e in alumni_careers.list_employers():
            self.tree.insert(
                "", "end", iid=str(e.employer_id),
                values=(e.employer_id, e.canonical_name,
                          e.sector or "—", e.website or "—",
                          e.country or "—"))

    def _selected(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _upsert(self) -> None:
        EmployerDialog(self.frame.winfo_toplevel(),
                          existing=None, on_save=self.refresh)

    def _alias(self) -> None:
        eid = self._selected()
        if eid is None: return
        alias = _prompt_string(self.frame.winfo_toplevel(),
                                  "Alias", "Alias name:")
        if not alias: return
        try:
            alumni_careers.add_employer_alias(alias, eid)
        except Exception as e:
            messagebox.showerror("Alias", str(e)); return
        messagebox.showinfo("Alias", f"Alias '{alias}' → #{eid}")

    def _delete(self) -> None:
        eid = self._selected()
        if eid is None: return
        if not messagebox.askyesno("Delete",
                                      f"Delete employer #{eid}?"):
            return
        alumni_careers.delete_employer(eid)
        self.refresh()

    def _top(self) -> None:
        TopEmployersDialog(self.frame.winfo_toplevel())


class EmployerDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing, on_save: Callable[[], None]) -> None:
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Employer")
        self.win.transient(parent); grab_when_viewable(self.win)
        frm = ttk.Frame(self.win, padding=10); frm.pack(fill="both",
                                                          expand=True)
        ttk.Label(frm, text="Canonical name:").grid(row=0, column=0,
                                                       sticky="w")
        self.name = ttk.Entry(frm, width=40); self.name.grid(
            row=0, column=1, sticky="w", pady=2)
        ttk.Label(frm, text="Sector:").grid(row=1, column=0, sticky="w")
        self.sector = ttk.Combobox(frm, values=list(SECTORS), width=22)
        self.sector.grid(row=1, column=1, sticky="w", pady=2)
        ttk.Label(frm, text="Website:").grid(row=2, column=0, sticky="w")
        self.web = ttk.Entry(frm, width=40); self.web.grid(
            row=2, column=1, sticky="w", pady=2)
        ttk.Label(frm, text="Country:").grid(row=3, column=0, sticky="w")
        self.country = ttk.Entry(frm, width=22); self.country.grid(
            row=3, column=1, sticky="w", pady=2)
        bar = ttk.Frame(frm); bar.grid(row=4, column=0, columnspan=2,
                                          pady=8, sticky="e")
        ttk.Button(bar, text="Save",
                     command=self._save).pack(side="right")
        ttk.Button(bar, text="Cancel",
                     command=self.win.destroy
                     ).pack(side="right", padx=4)

    def _save(self) -> None:
        try:
            alumni_careers.upsert_employer(self.name.get(),
                                     sector=self.sector.get() or None,
                                     website=self.web.get() or None,
                                     country=self.country.get() or None)
        except Exception as e:
            messagebox.showerror("Save", str(e)); return
        self.on_save()
        self.win.destroy()


class TopEmployersDialog:
    def __init__(self, parent: tk.Misc) -> None:
        self.win = tk.Toplevel(parent)
        self.win.title("Top employers")
        self.win.transient(parent); self.win.geometry("600x500")
        bar = ttk.Frame(self.win); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Year:").pack(side="left")
        self.year = ttk.Entry(bar, width=8); self.year.pack(side="left",
                                                                padx=4)
        ttk.Label(bar, text="Limit:").pack(side="left", padx=(8, 0))
        self.limit = ttk.Entry(bar, width=6); self.limit.insert(0, "25")
        self.limit.pack(side="left", padx=4)
        ttk.Button(bar, text="Run",
                     command=self.refresh).pack(side="left", padx=8)
        cols = ("count", "employer")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        self.tree.heading("count", text="#")
        self.tree.heading("employer", text="Employer")
        self.tree.column("count", width=60, anchor="w")
        self.tree.column("employer", width=420, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        try:
            lim = int(self.limit.get() or "25")
        except ValueError:
            messagebox.showerror("Limit", "Must be a number"); return
        year = self.year.get().strip() or None
        for r in alumni_careers.top_employers(limit=lim, leaving_year=year):
            self.tree.insert("", "end",
                               values=(r.alumni_count, r.employer))


class JobsBoardTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Jobs")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Status:").pack(side="left")
        self.status = ttk.Combobox(
            bar, values=["(all)", *JOB_STATUSES],
            state="readonly", width=10)
        self.status.set("Open"); self.status.pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Post (per alumnus)…",
                     command=self._post).pack(side="left", padx=12)
        ttk.Button(bar, text="Set status…",
                     command=self._set_status).pack(side="left")
        ttk.Button(bar, text="Applicants…",
                     command=self._applicants).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                     command=self._delete).pack(side="left")
        cols = ("id", "title", "employer", "type", "salary",
                "status", "deadline")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "title": 200, "employer": 160,
                    "type": 100, "salary": 110, "status": 80,
                    "deadline": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        s = self.status.get()
        status = None if s == "(all)" else s
        for j in alumni_careers.list_jobs(status=status):
            self.tree.insert(
                "", "end", iid=str(j.job_id),
                values=(j.job_id, j.title, j.employer or "—",
                          j.job_type, j.salary_band or "—",
                          j.status, j.deadline or "—"))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _post(self) -> None:
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        JobDialog(self.frame.winfo_toplevel(), alumni_id=aid,
                     on_save=self.refresh)

    def _set_status(self) -> None:
        jid = self._selected_id()
        if jid is None: return
        st = _ask_choice(self.frame, "Status", list(JOB_STATUSES))
        if not st: return
        try:
            alumni_careers.set_job_status(jid, st)
        except Exception as e:
            messagebox.showerror("Status", str(e)); return
        self.refresh()

    def _applicants(self) -> None:
        jid = self._selected_id()
        if jid is None: return
        JobApplicantsDialog(self.frame.winfo_toplevel(), jid)

    def _delete(self) -> None:
        jid = self._selected_id()
        if jid is None: return
        if not messagebox.askyesno("Delete", f"Delete job #{jid}?"):
            return
        alumni_careers.delete_job(jid)
        self.refresh()


class JobDialog:
    def __init__(self, parent: tk.Misc, *, alumni_id: int,
                 on_save: Callable[[], None]) -> None:
        self.alumni_id = alumni_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Post a job"); self.win.transient(parent)
        grab_when_viewable(self.win)
        frm = ttk.Frame(self.win, padding=10); frm.pack(fill="both",
                                                          expand=True)
        rows = [
            ("Title", "title", None),
            ("Employer", "employer", None),
            ("Sector", "sector", list(SECTORS)),
            ("Location", "location", None),
            ("Job type", "job_type", list(JOB_TYPES)),
            ("Salary band", "salary_band", list(SALARY_BANDS)),
            ("Apply URL", "apply_url", None),
            ("Deadline (YYYY-MM-DD)", "deadline", None),
        ]
        self.widgets: dict[str, tk.Widget] = {}
        for i, (lbl, key, opts) in enumerate(rows):
            ttk.Label(frm, text=lbl + ":").grid(row=i, column=0,
                                                   sticky="w")
            if opts:
                w = ttk.Combobox(frm, values=opts, width=24)
            else:
                w = ttk.Entry(frm, width=40)
            w.grid(row=i, column=1, sticky="w", pady=2)
            self.widgets[key] = w
        ttk.Label(frm, text="Description:").grid(row=len(rows),
                                                    column=0, sticky="nw")
        self.desc = tk.Text(frm, width=40, height=4)
        self.desc.grid(row=len(rows), column=1, sticky="w", pady=2)
        if "Graduate" in JOB_TYPES:
            self.widgets["job_type"].set("Graduate")
        bar = ttk.Frame(frm); bar.grid(row=len(rows) + 1, column=0,
                                          columnspan=2, pady=8,
                                          sticky="e")
        ttk.Button(bar, text="Post",
                     command=self._save).pack(side="right")
        ttk.Button(bar, text="Cancel",
                     command=self.win.destroy
                     ).pack(side="right", padx=4)

    def _save(self) -> None:
        payload = {k: (w.get() if not isinstance(w, tk.Text)
                          else w.get("1.0", "end").strip())
                    for k, w in self.widgets.items()}
        payload["description"] = self.desc.get("1.0", "end").strip()
        try:
            alumni_careers.post_job(self.alumni_id, payload)
        except Exception as e:
            messagebox.showerror("Post", str(e)); return
        self.on_save(); self.win.destroy()


class JobApplicantsDialog:
    def __init__(self, parent: tk.Misc, job_id: int) -> None:
        self.job_id = job_id
        self.win = tk.Toplevel(parent)
        self.win.title(f"Applicants — job #{job_id}")
        self.win.transient(parent); self.win.geometry("700x400")
        cols = ("app_id", "kind", "applicant", "applied", "status")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        widths = {"app_id": 60, "kind": 80, "applicant": 120,
                    "applied": 120, "status": 110}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win); bar.pack(fill="x", padx=8,
                                                pady=(0, 8))
        ttk.Button(bar, text="Set status",
                     command=self._status).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for r in alumni_careers.list_job_applications(self.job_id):
            self.tree.insert(
                "", "end", iid=str(r.application_id),
                values=(r.application_id, r.applicant_kind,
                          r.applicant_id, r.applied_on, r.status))

    def _status(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        st = _ask_choice(self.win, "Application status",
                            list(APPLICATION_STATUSES))
        if not st: return
        try:
            alumni_careers.set_job_application_status(int(sel[0]), st)
        except Exception as e:
            messagebox.showerror("Status", str(e)); return
        self.refresh()


# ── Top-level: Internships board ─────────────────────────────────

class InternshipsBoardTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Internships")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Status:").pack(side="left")
        self.status = ttk.Combobox(
            bar, values=["(all)", *JOB_STATUSES],
            state="readonly", width=10)
        self.status.set("Open"); self.status.pack(side="left", padx=4)
        self.paid_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Paid only",
                          variable=self.paid_only,
                          command=self.refresh
                          ).pack(side="left", padx=8)
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Post (per alumnus)…",
                     command=self._post).pack(side="left", padx=12)
        ttk.Button(bar, text="Set status",
                     command=self._set_status).pack(side="left")
        ttk.Button(bar, text="Applicants…",
                     command=self._applicants).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                     command=self._delete).pack(side="left")
        cols = ("id", "title", "employer", "weeks", "paid",
                "hourly", "status", "deadline")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "title": 200, "employer": 160,
                    "weeks": 70, "paid": 60, "hourly": 90,
                    "status": 80, "deadline": 100}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        s = self.status.get()
        status = None if s == "(all)" else s
        for ip in alumni_careers.list_internships(
                status=status, paid_only=self.paid_only.get()):
            self.tree.insert(
                "", "end", iid=str(ip.internship_id),
                values=(ip.internship_id, ip.title,
                          ip.employer or "—",
                          ip.duration_weeks or "—",
                          "Y" if ip.paid else "N",
                          _money_str(ip.hourly_pence),
                          ip.status, ip.deadline or "—"))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _post(self) -> None:
        aid = _pick_alumnus_dialog(self.frame.winfo_toplevel())
        if aid is None: return
        InternshipDialog(self.frame.winfo_toplevel(),
                            alumni_id=aid, on_save=self.refresh)

    def _set_status(self) -> None:
        iid = self._selected_id()
        if iid is None: return
        st = _ask_choice(self.frame, "Status", list(JOB_STATUSES))
        if not st: return
        try:
            alumni_careers.set_internship_status(iid, st)
        except Exception as e:
            messagebox.showerror("Status", str(e)); return
        self.refresh()

    def _applicants(self) -> None:
        iid = self._selected_id()
        if iid is None: return
        InternshipApplicantsDialog(self.frame.winfo_toplevel(), iid)

    def _delete(self) -> None:
        iid = self._selected_id()
        if iid is None: return
        if not messagebox.askyesno("Delete",
                                      f"Delete internship #{iid}?"):
            return
        alumni_careers.delete_internship(iid)
        self.refresh()


class InternshipDialog:
    def __init__(self, parent: tk.Misc, *, alumni_id: int,
                 on_save: Callable[[], None]) -> None:
        self.alumni_id = alumni_id
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Post an internship")
        self.win.transient(parent); grab_when_viewable(self.win)
        frm = ttk.Frame(self.win, padding=10); frm.pack(fill="both",
                                                          expand=True)
        rows = [
            ("Title", "title", None),
            ("Employer", "employer", None),
            ("Sector", "sector", list(SECTORS)),
            ("Location", "location", None),
            ("Duration weeks", "duration_weeks", None),
            ("Hourly pay £ (e.g. 12.50)", "hourly_pay", None),
            ("Start window", "start_window", None),
            ("Apply URL", "apply_url", None),
            ("Deadline (YYYY-MM-DD)", "deadline", None),
        ]
        self.widgets: dict[str, tk.Widget] = {}
        for i, (lbl, key, opts) in enumerate(rows):
            ttk.Label(frm, text=lbl + ":").grid(row=i, column=0,
                                                   sticky="w")
            if opts:
                w = ttk.Combobox(frm, values=opts, width=24)
            else:
                w = ttk.Entry(frm, width=40)
            w.grid(row=i, column=1, sticky="w", pady=2)
            self.widgets[key] = w
        self.paid_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="Paid",
                          variable=self.paid_var
                          ).grid(row=len(rows), column=1,
                                  sticky="w", pady=2)
        ttk.Label(frm, text="Requirements:").grid(
            row=len(rows) + 1, column=0, sticky="nw")
        self.req = tk.Text(frm, width=40, height=4)
        self.req.grid(row=len(rows) + 1, column=1, sticky="w", pady=2)
        bar = ttk.Frame(frm); bar.grid(row=len(rows) + 2, column=0,
                                          columnspan=2, pady=8,
                                          sticky="e")
        ttk.Button(bar, text="Post",
                     command=self._save).pack(side="right")
        ttk.Button(bar, text="Cancel",
                     command=self.win.destroy
                     ).pack(side="right", padx=4)

    def _save(self) -> None:
        payload: dict[str, object] = {
            k: w.get() for k, w in self.widgets.items()}
        payload["paid"] = self.paid_var.get()
        payload["requirements"] = self.req.get("1.0", "end").strip()
        try:
            alumni_careers.post_internship(self.alumni_id, payload)
        except Exception as e:
            messagebox.showerror("Post", str(e)); return
        self.on_save(); self.win.destroy()


class InternshipApplicantsDialog:
    def __init__(self, parent: tk.Misc, internship_id: int) -> None:
        self.internship_id = internship_id
        self.win = tk.Toplevel(parent)
        self.win.title(f"Applicants — internship #{internship_id}")
        self.win.transient(parent); self.win.geometry("700x400")
        cols = ("app_id", "student", "applied", "status")
        self.tree = ttk.Treeview(self.win, columns=cols,
                                    show="headings")
        widths = {"app_id": 60, "student": 120,
                    "applied": 120, "status": 110}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(self.win); bar.pack(fill="x", padx=8,
                                                pady=(0, 8))
        ttk.Button(bar, text="Set status",
                     command=self._status).pack(side="left")
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        for r in alumni_careers.list_internship_applications(self.internship_id):
            self.tree.insert(
                "", "end", iid=str(r.application_id),
                values=(r.application_id, r.student_id,
                          r.applied_on, r.status))

    def _status(self) -> None:
        sel = self.tree.selection()
        if not sel: return
        st = _ask_choice(self.win, "Application status",
                            list(APPLICATION_STATUSES))
        if not st: return
        try:
            alumni_careers.set_internship_application_status(int(sel[0]), st)
        except Exception as e:
            messagebox.showerror("Status", str(e)); return
        self.refresh()


# ── Top-level: Mentor matching ───────────────────────────────────

class MentorMatchTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Mentor match")
        bar = ttk.Frame(self.frame); bar.pack(fill="x", padx=8, pady=8)
        ttk.Label(bar, text="Student id:").pack(side="left")
        self.student = ttk.Entry(bar, width=12)
        self.student.pack(side="left", padx=4)
        ttk.Button(bar, text="Pick…",
                     command=self._pick_student).pack(side="left")
        ttk.Label(bar, text="Limit:").pack(side="left", padx=(8, 0))
        self.limit = ttk.Entry(bar, width=4); self.limit.insert(0, "10")
        self.limit.pack(side="left", padx=4)
        self.require_consent = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Require Mentoring consent",
                          variable=self.require_consent
                          ).pack(side="left", padx=8)
        ttk.Button(bar, text="Run",
                     command=self.refresh).pack(side="left", padx=8)
        cols = ("score", "alumni_id", "name", "sector", "reasons")
        self.tree = ttk.Treeview(self.frame, columns=cols,
                                    show="headings")
        widths = {"score": 70, "alumni_id": 70, "name": 220,
                    "sector": 140, "reasons": 600}
        for c in cols:
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

    def _pick_student(self) -> None:
        rows = student_data.list_students()
        if not rows:
            messagebox.showinfo("Pick", "No current students.")
            return
        dlg = tk.Toplevel(self.frame.winfo_toplevel())
        dlg.title("Pick student"); dlg.transient(
            self.frame.winfo_toplevel()); grab_when_viewable(dlg)
        lb = tk.Listbox(dlg, width=50, height=20)
        for s in rows:
            lb.insert("end", f"{s.student_id}  {s.full_name}")
        lb.pack(padx=8, pady=8)

        def ok() -> None:
            sel = lb.curselection()
            if not sel: return
            sid = rows[sel[0]].student_id
            self.student.delete(0, "end")
            self.student.insert(0, sid)
            dlg.destroy()
        ttk.Button(dlg, text="OK", command=ok).pack(pady=(0, 8))
        self.frame.winfo_toplevel().wait_window(dlg)

    def refresh(self) -> None:
        for i in self.tree.get_children(): self.tree.delete(i)
        sid = self.student.get().strip()
        if not sid:
            messagebox.showinfo("Run", "Pick a student first."); return
        try:
            lim = int(self.limit.get() or "10")
        except ValueError:
            messagebox.showerror("Limit", "Must be a number"); return
        for m in alumni_mentoring.match_mentors_for_student(
                sid, limit=lim,
                require_consent=self.require_consent.get()):
            self.tree.insert(
                "", "end", iid=str(m.alumnus.alumni_id),
                values=(m.score, m.alumnus.alumni_id,
                          m.alumnus.full_name,
                          m.alumnus.current_sector or "—",
                          "; ".join(m.reasons)))


# ══ Mentor + comms extensions (items 17–26) ═══════════════════════

# ── Per-alumnus: Mentor profile (capacity & availability) ─────────

class MentorProfileTab:
    def __init__(self, nb: ttk.Notebook, alumni_id: int) -> None:
        self.alumni_id = alumni_id
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Mentor profile")
        frm = ttk.Frame(self.frame, padding=10); frm.pack(fill="x")
        ttk.Label(frm, text="max_mentees:").grid(row=0, column=0,
                                                    sticky="w")
        self.mx = ttk.Entry(frm, width=8); self.mx.grid(row=0, column=1,
                                                          sticky="w")
        ttk.Label(frm, text="available_from:").grid(row=1, column=0,
                                                       sticky="w")
        self.af = ttk.Entry(frm, width=14); self.af.grid(row=1, column=1,
                                                            sticky="w")
        ttk.Label(frm, text="available_until:").grid(row=2, column=0,
                                                        sticky="w")
        self.au = ttk.Entry(frm, width=14); self.au.grid(row=2, column=1,
                                                            sticky="w")
        self.paused = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="paused", variable=self.paused
                          ).grid(row=3, column=1, sticky="w")
        ttk.Label(frm, text="bio:").grid(row=4, column=0, sticky="nw")
        self.bio = tk.Text(frm, width=42, height=4); self.bio.grid(
            row=4, column=1, sticky="w", pady=2)
        self.status = ttk.Label(frm, text="", foreground="#666")
        self.status.grid(row=5, column=0, columnspan=2,
                           sticky="w", pady=(6, 0))
        bar = ttk.Frame(frm); bar.grid(row=6, column=0, columnspan=2,
                                          pady=8, sticky="w")
        ttk.Button(bar, text="Save",
                     command=self._save).pack(side="left")
        ttk.Button(bar, text="Refresh",
                     command=self.refresh).pack(side="left", padx=4)
        self.refresh()

    def refresh(self) -> None:
        p = alumni_mentoring.get_mentor_profile(self.alumni_id)
        self.mx.delete(0, "end"); self.af.delete(0, "end")
        self.au.delete(0, "end"); self.bio.delete("1.0", "end")
        if p is None:
            self.mx.insert(0, "3")
            self.paused.set(False)
            self.status.configure(text="(no profile yet)")
        else:
            self.mx.insert(0, str(p.max_mentees))
            if p.available_from: self.af.insert(0, p.available_from)
            if p.available_until: self.au.insert(0, p.available_until)
            self.paused.set(p.paused)
            if p.bio: self.bio.insert("1.0", p.bio)
            cap = "has capacity" if alumni_mentoring.mentor_has_capacity(
                self.alumni_id) else "FULL / unavailable"
            self.status.configure(
                text=f"active mentees: "
                     f"{alumni_mentoring.active_mentee_count(self.alumni_id)} — {cap}")

    def _save(self) -> None:
        try:
            alumni_mentoring.upsert_mentor_profile(
                self.alumni_id,
                max_mentees=int(self.mx.get() or "0"),
                available_from=self.af.get() or None,
                available_until=self.au.get() or None,
                paused=self.paused.get(),
                bio=self.bio.get("1.0", "end").strip() or None)
        except Exception as e:
            messagebox.showerror("Save", str(e)); return
        self.refresh()
