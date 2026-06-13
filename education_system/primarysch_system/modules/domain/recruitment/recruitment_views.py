"""Tkinter views for Primary School Recruitment."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.shared import branding
from education_system.primarysch_system.modules.domain.recruitment import (
    recruitment as data,
)
from education_system.primarysch_system.modules.domain.recruitment.recruitment import (
    APPLICANT_SOURCES,
    APPLICANT_STATUSES,
    Applicant,
    CONTRACT_TYPES,
    DEFAULT_APPLICANT_SOURCE,
    DEFAULT_APPLICANT_STATUS,
    DEFAULT_CONTRACT_TYPE,
    DEFAULT_ROLE_TYPE,
    DEFAULT_VACANCY_STATUS,
    ROLE_TYPES,
    VACANCY_STATUSES,
    Vacancy,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_VAC_TAGS = {
    "Draft":        ("#fff7e6", "#7a5800"),
    "Advertised":   ("#e6f0ff", "#1a3f8c"),
    "Shortlisting": ("#fff0d6", "#7a5800"),
    "Interview":    ("#fff0d6", "#7a5800"),
    "Filled":       ("#e6f7e6", "#0d6b2a"),
    "Closed":       ("#eeeeee", "#444444"),
    "Withdrawn":    ("#ffd1d1", "#8c0d0d"),
    "On Hold":      ("#dddddd", "#444444"),
}
_APP_TAGS = {
    "Applied":                   ("#fff7e6", "#7a5800"),
    "Under Review":              ("#fff7e6", "#7a5800"),
    "Shortlisted":               ("#e6f0ff", "#1a3f8c"),
    "Rejected (Pre-Interview)":  ("#ffd1d1", "#8c0d0d"),
    "Interview Scheduled":       ("#fff0d6", "#7a5800"),
    "Interviewed":               ("#e6e6ff", "#3a3a8c"),
    "Offer Made":                ("#e6f7e6", "#0d6b2a"),
    "Offer Accepted":            ("#d6ffd6", "#0d6b2a"),
    "Offer Declined":            ("#ffd1d1", "#8c0d0d"),
    "Withdrew":                  ("#eeeeee", "#444444"),
    "Rejected (Post-Interview)": ("#ffd1d1", "#8c0d0d"),
    "Started":                   ("#d6ffd6", "#0d6b2a"),
}


def open_recruitment_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Recruitment — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    VacanciesTab(nb)
    SummaryTab(nb)


# ── Vacancies tab ────────────────────────────────────────

class VacanciesTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Vacancies & Applicants")
        paned = ttk.PanedWindow(self.frame, orient="vertical")
        paned.pack(fill="both", expand=True, padx=8, pady=8)
        self.top = ttk.Frame(paned)
        self.bottom = ttk.Frame(paned)
        paned.add(self.top, weight=3)
        paned.add(self.bottom, weight=2)
        self._build_top()
        self._build_bottom()
        self.refresh()

    def _build_top(self) -> None:
        bar = ttk.Frame(self.top)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="Role:").pack(side="left")
        self.f_role = ttk.Combobox(bar,
                                     values=("",) + ROLE_TYPES,
                                     state="readonly", width=18)
        self.f_role.current(0)
        self.f_role.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(
            bar, values=("",) + VACANCY_STATUSES,
            state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))
        self.open_only = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Open only",
                         variable=self.open_only,
                         command=self.refresh).pack(side="left",
                                                        padx=(2, 8))
        self.closing_passed = tk.BooleanVar()
        ttk.Checkbutton(bar, text="Closing passed",
                         variable=self.closing_passed,
                         command=self.refresh).pack(side="left",
                                                        padx=(2, 8))
        ttk.Label(bar, text="Title:").pack(side="left")
        self.f_title = ttk.Entry(bar, width=20)
        self.f_title.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New vacancy",
                    command=self._new_vacancy).pack(
            side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.top)
        table_frame.pack(fill="both", expand=True)
        cols = ("id", "title", "role", "contract", "department",
                "salary", "closing", "interview", "applicants",
                "status")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "title": 240, "role": 140,
                   "contract": 110, "department": 130,
                   "salary": 130, "closing": 100,
                   "interview": 100, "applicants": 90,
                   "status": 110}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id",
                                                  "applicants")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _VAC_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.tag_configure("closing_passed",
                                   background="#ffd1d1",
                                   foreground="#8c0d0d")
        self.tree.bind("<<TreeviewSelect>>",
                         lambda _e: self._refresh_applicants())
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit_vacancy())

        actions = ttk.Frame(self.top)
        actions.pack(fill="x", pady=(4, 0))
        for label, cmd in (
                ("Edit vacancy",  self._edit_vacancy),
                ("Advertise",     self._advertise),
                ("Mark Filled",   self._mark_filled),
                ("Change status", self._set_vacancy_status),
                ("Delete",        self._delete_vacancy),
                ("Refresh",       self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _build_bottom(self) -> None:
        bar = ttk.Frame(self.bottom)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="Applicants for selected vacancy"
                  ).pack(side="left")
        for label, cmd in (
                ("Delete",          self._delete_applicant),
                ("Change status",   self._set_applicant_status),
                ("Reject",          self._reject_applicant),
                ("Mark Started",    self._mark_started),
                ("Offer response",  self._offer_response),
                ("Make offer",      self._make_offer),
                ("Record interview", self._record_interview),
                ("Schedule interview", self._schedule_interview),
                ("Shortlist toggle", self._toggle_shortlist),
                ("Edit",            self._edit_applicant),
                ("Add applicant",   self._new_applicant),
        ):
            ttk.Button(bar, text=label,
                        command=cmd).pack(side="right", padx=4)

        table_frame = ttk.Frame(self.bottom)
        table_frame.pack(fill="both", expand=True)
        acols = ("id", "name", "email", "source", "short",
                   "score", "interview_on", "offer_on",
                   "status")
        self.atree = ttk.Treeview(table_frame, columns=acols,
                                       show="headings",
                                       selectmode="browse")
        awidths = {"id": 50, "name": 180, "email": 200,
                     "source": 130, "short": 60, "score": 60,
                     "interview_on": 110, "offer_on": 110,
                     "status": 180}
        for c in acols:
            self.atree.heading(c,
                                   text=c.replace("_", " ").title())
            self.atree.column(c, width=awidths[c],
                                  anchor=("center"
                                           if c in ("id", "short",
                                                      "score")
                                           else "w"))
        avsb = ttk.Scrollbar(table_frame, orient="vertical",
                                command=self.atree.yview)
        self.atree.configure(yscrollcommand=avsb.set)
        self.atree.pack(side="left", fill="both", expand=True)
        avsb.pack(side="right", fill="y")
        for status, (bg, fg) in _APP_TAGS.items():
            self.atree.tag_configure(status, background=bg,
                                          foreground=fg)
        self.atree.bind("<Double-Button-1>",
                            lambda _e: self._edit_applicant())

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_role.get():
            f["role_type"] = self.f_role.get()
        if self.f_status.get():
            f["status"] = self.f_status.get()
        if self.f_title.get().strip():
            f["title_like"] = self.f_title.get().strip()
        if self.open_only.get() and not self.f_status.get():
            f["open_only"] = True
        if self.closing_passed.get():
            f["closing_passed"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        rows = data.list_vacancies(**self._filters())
        for v in rows:
            sal = "—"
            if v.salary_min is not None and v.salary_max is not None:
                sal = f"£{v.salary_min:.0f}–{v.salary_max:.0f}"
            elif v.salary_min is not None or v.salary_max is not None:
                sal = f"£{v.salary_min or v.salary_max:.0f}"
            tag = ("closing_passed"
                     if v.closing_passed else v.status)
            self.tree.insert(
                "", "end", iid=str(v.vacancy_id),
                values=(v.vacancy_id, v.title, v.role_type,
                         v.contract_type,
                         v.department or "—",
                         sal,
                         v.closing_date or "—",
                         v.interview_date or "—",
                         data.applicant_count(v.vacancy_id),
                         v.status),
                tags=(tag,))
        self.count.config(text=f"{len(rows)} vacancy(ies)")
        self._refresh_applicants()

    def _selected_vacancy(self) -> Vacancy | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Recruitment",
                                  "Select a vacancy first.",
                                  parent=self.frame)
            return None
        return data.get_vacancy(int(sel[0]))

    def _refresh_applicants(self) -> None:
        for iid in self.atree.get_children():
            self.atree.delete(iid)
        sel = self.tree.selection()
        if not sel:
            return
        vid = int(sel[0])
        for a in data.list_applicants(vacancy_id=vid):
            self.atree.insert(
                "", "end", iid=str(a.applicant_id),
                values=(a.applicant_id, a.full_name,
                         a.email or "—", a.source,
                         "yes" if a.shortlisted else "",
                         (a.interview_score
                          if a.interview_score is not None
                          else "—"),
                         a.interview_date or "—",
                         a.offer_made_on or "—",
                         a.status),
                tags=(a.status,))

    def _selected_applicant(self) -> Applicant | None:
        sel = self.atree.selection()
        if not sel:
            messagebox.showinfo("Recruitment",
                                  "Select an applicant first.",
                                  parent=self.frame)
            return None
        return data.get_applicant(int(sel[0]))

    def _new_vacancy(self) -> None:
        if VacancyEditor(self.frame).result is not None:
            self.refresh()

    def _edit_vacancy(self) -> None:
        v = self._selected_vacancy()
        if v and VacancyEditor(
                self.frame, vacancy=v).result is not None:
            self.refresh()

    def _advertise(self) -> None:
        v = self._selected_vacancy()
        if not v:
            return
        try:
            data.advertise(v.vacancy_id)
        except ValidationError as e:
            messagebox.showerror("Recruitment", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _mark_filled(self) -> None:
        v = self._selected_vacancy()
        if not v:
            return
        try:
            data.mark_filled(v.vacancy_id)
        except ValidationError as e:
            messagebox.showerror("Recruitment", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_vacancy_status(self) -> None:
        v = self._selected_vacancy()
        if not v:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(VACANCY_STATUSES),
                                default=v.status)
        if not new:
            return
        try:
            data.set_vacancy_status(v.vacancy_id, new)
        except ValidationError as e:
            messagebox.showerror("Recruitment", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete_vacancy(self) -> None:
        v = self._selected_vacancy()
        if not v:
            return
        if not messagebox.askyesno(
                "Recruitment",
                f"Delete vacancy #{v.vacancy_id} and all "
                "applicants?", parent=self.frame):
            return
        data.delete_vacancy(v.vacancy_id)
        self.refresh()

    def _new_applicant(self) -> None:
        v = self._selected_vacancy()
        if not v:
            return
        if ApplicantEditor(self.frame,
                                vacancy_id=v.vacancy_id
                                ).result is not None:
            self._refresh_applicants()
            self.refresh()

    def _edit_applicant(self) -> None:
        a = self._selected_applicant()
        if a and ApplicantEditor(
                self.frame, vacancy_id=a.vacancy_id,
                applicant=a).result is not None:
            self._refresh_applicants()
            self.refresh()

    def _toggle_shortlist(self) -> None:
        a = self._selected_applicant()
        if not a:
            return
        try:
            data.shortlist(a.applicant_id,
                              shortlisted=not a.shortlisted)
        except ValidationError as e:
            messagebox.showerror("Recruitment", str(e),
                                    parent=self.frame)
            return
        self._refresh_applicants()

    def _schedule_interview(self) -> None:
        a = self._selected_applicant()
        if not a:
            return
        when = _prompt_text(
            self.frame, "Interview date (YYYY-MM-DD)",
            initial=a.interview_date or "")
        if not when:
            return
        try:
            data.schedule_interview(a.applicant_id,
                                          interview_date=when)
        except ValidationError as e:
            messagebox.showerror("Recruitment", str(e),
                                    parent=self.frame)
            return
        self._refresh_applicants()

    def _record_interview(self) -> None:
        a = self._selected_applicant()
        if not a:
            return
        if InterviewDialog(self.frame,
                              applicant=a).result is not None:
            self._refresh_applicants()

    def _make_offer(self) -> None:
        a = self._selected_applicant()
        if not a:
            return
        if OfferDialog(self.frame,
                          applicant=a).result is not None:
            self._refresh_applicants()

    def _offer_response(self) -> None:
        a = self._selected_applicant()
        if not a:
            return
        if OfferResponseDialog(
                self.frame, applicant=a).result is not None:
            self._refresh_applicants()

    def _mark_started(self) -> None:
        a = self._selected_applicant()
        if not a:
            return
        when = _prompt_text(self.frame,
                              "Started on (YYYY-MM-DD)",
                              initial=_dt.date.today().isoformat())
        if not when:
            return
        try:
            data.mark_started(a.applicant_id, started_on=when)
        except ValidationError as e:
            messagebox.showerror("Recruitment", str(e),
                                    parent=self.frame)
            return
        self._refresh_applicants()

    def _reject_applicant(self) -> None:
        a = self._selected_applicant()
        if not a:
            return
        if RejectDialog(self.frame,
                            applicant=a).result is not None:
            self._refresh_applicants()

    def _set_applicant_status(self) -> None:
        a = self._selected_applicant()
        if not a:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(APPLICANT_STATUSES),
                                default=a.status)
        if not new:
            return
        try:
            data.set_applicant_status(a.applicant_id, new)
        except ValidationError as e:
            messagebox.showerror("Recruitment", str(e),
                                    parent=self.frame)
            return
        self._refresh_applicants()

    def _delete_applicant(self) -> None:
        a = self._selected_applicant()
        if not a:
            return
        if not messagebox.askyesno(
                "Recruitment",
                f"Delete applicant #{a.applicant_id}?",
                parent=self.frame):
            return
        data.delete_applicant(a.applicant_id)
        self._refresh_applicants()
        self.refresh()


class SummaryTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8,
                          pady=(4, 8))
        self.refresh()

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "Recruitment Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total vacancies      : {s.total_vacancies}\n"
                            f"Open                 : {s.open_vacancies}\n"
                            f"Advertised           : {s.advertised}\n"
                            f"Closing passed       : {s.closing_passed}\n"
                            f"Total applicants     : {s.total_applicants}\n"
                            f"Active applicants    : {s.active_applicants}\n"
                            f"Shortlisted          : {s.shortlisted}\n"
                            f"Interviewed          : {s.interviewed}\n"
                            f"Offers made          : {s.offers_made}\n"
                            f"Offers accepted      : {s.offers_accepted}\n"
                            f"Started              : {s.started}\n"
                            f"Rejected             : {s.rejected}\n\n")
        self.text.insert("end", "By role type:\n")
        for k in ROLE_TYPES:
            n = s.by_role_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy vacancy status:\n")
        for k in VACANCY_STATUSES:
            n = s.by_vacancy_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<16}: {n}\n")
        self.text.insert("end", "\nBy applicant status:\n")
        for k in APPLICANT_STATUSES:
            n = s.by_applicant_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<26}: {n}\n")
        self.text.insert("end", "\nBy source:\n")
        for k in APPLICANT_SOURCES:
            n = s.by_source.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<18}: {n}\n")
        self.text.config(state="disabled")


# ── Editors ──────────────────────────────────────────────

class VacancyEditor:
    def __init__(self, parent, *,
                 vacancy: Vacancy | None = None) -> None:
        self.vacancy = vacancy
        self.result: Vacancy | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit vacancy #{vacancy.vacancy_id}"
                          if vacancy else "New vacancy")
        self.win.geometry("880x820")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if vacancy:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}
        self.bools: dict[str, tk.BooleanVar] = {}

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        entry(0, 0, "Title*", "title", width=48)
        entry(1, 0, "Reference", "reference")
        entry(1, 2, "Department", "department")
        combo(2, 0, "Role type*", "role_type", ROLE_TYPES)
        combo(2, 2, "Contract type*", "contract_type",
                 CONTRACT_TYPES)
        entry(3, 0, "FTE percent", "fte_percent")
        combo(3, 2, "Status*", "status", VACANCY_STATUSES)
        entry(4, 0, "Salary min (£)", "salary_min")
        entry(4, 2, "Salary max (£)", "salary_max")
        entry(5, 0, "Salary scale", "salary_scale")
        entry(5, 2, "Hiring manager", "hiring_manager")
        entry(6, 0, "Advertised on", "advertised_on")
        entry(6, 2, "Closing date", "closing_date")
        entry(7, 0, "Shortlisting date", "shortlisting_date")
        entry(7, 2, "Interview date", "interview_date")
        entry(8, 0, "Start date", "start_date")
        entry(8, 2, "Advert URL", "advert_url")
        self.bools["safeguarding_statement"] = tk.BooleanVar(
            value=True)
        ttk.Checkbutton(body,
                         text="Safeguarding statement included",
                         variable=self.bools[
                             "safeguarding_statement"]).grid(
            row=9, column=0, columnspan=2, sticky="w",
            padx=4, pady=4)

        row = 10
        for key, label in (
                ("description",  "Description"),
                ("requirements", "Requirements"),
                ("benefits",     "Benefits"),
                ("notes",        "Notes"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
            t = tk.Text(body, height=2, width=74, wrap="word")
            t.grid(row=row, column=1, columnspan=3,
                     sticky="ew", padx=4, pady=(6, 2))
            self.texts[key] = t
            row += 1

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["role_type"].set(DEFAULT_ROLE_TYPE)
        self.vars["contract_type"].set(DEFAULT_CONTRACT_TYPE)
        self.vars["fte_percent"].set("100")
        self.vars["status"].set(DEFAULT_VACANCY_STATUS)

    def _load(self) -> None:
        v = self.vacancy
        assert v is not None
        for key in ("title", "reference", "department",
                     "role_type", "contract_type",
                     "salary_scale", "hiring_manager",
                     "advertised_on", "closing_date",
                     "shortlisting_date", "interview_date",
                     "start_date", "advert_url", "status"):
            self.vars[key].set(getattr(v, key) or "")
        self.vars["fte_percent"].set(str(v.fte_percent))
        self.vars["salary_min"].set(
            str(v.salary_min)
            if v.salary_min is not None else "")
        self.vars["salary_max"].set(
            str(v.salary_max)
            if v.salary_max is not None else "")
        self.bools["safeguarding_statement"].set(
            v.safeguarding_statement)
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(v, k) or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        for k, b in self.bools.items():
            payload[k] = b.get()
        try:
            if self.vacancy:
                self.result = data.update_vacancy(
                    self.vacancy.vacancy_id, payload)
            else:
                self.result = data.create_vacancy(payload)
        except ValidationError as exc:
            messagebox.showerror("Recruitment", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class ApplicantEditor:
    def __init__(self, parent, *,
                 vacancy_id: int,
                 applicant: Applicant | None = None) -> None:
        self.vacancy_id = vacancy_id
        self.applicant = applicant
        self.result: Applicant | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit applicant #{applicant.applicant_id}"
                          if applicant else "New applicant")
        self.win.geometry("780x720")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if applicant:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}
        self.bools: dict[str, tk.BooleanVar] = {}

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        entry(0, 0, "First name*", "first_name")
        entry(0, 2, "Last name*", "last_name")
        entry(1, 0, "Email", "email")
        entry(1, 2, "Phone", "phone")
        entry(2, 0, "Application received*",
                 "application_received_on")
        combo(2, 2, "Source*", "source", APPLICANT_SOURCES)
        entry(3, 0, "Interview date", "interview_date")
        entry(3, 2, "Interview score", "interview_score")
        entry(4, 0, "Offer made on", "offer_made_on")
        entry(4, 2, "Offer response on", "offer_response_on")
        entry(5, 0, "Offer salary (£)", "offer_salary")
        entry(5, 2, "Started on", "started_on")
        combo(6, 0, "Status*", "status", APPLICANT_STATUSES)

        flags = ttk.LabelFrame(body, text="Flags")
        flags.grid(row=7, column=0, columnspan=4,
                     sticky="ew", padx=4, pady=(8, 4))
        for col, (key, label) in enumerate((
                ("cv_received",               "CV"),
                ("application_form_received", "Form"),
                ("references_received",       "Refs"),
                ("dbs_clearance",             "DBS"),
                ("shortlisted",               "Shortlisted"),
        )):
            v = tk.BooleanVar()
            self.bools[key] = v
            ttk.Checkbutton(flags, text=label,
                             variable=v).grid(
                row=0, column=col, sticky="w", padx=6, pady=4)

        row = 8
        for key, label in (
                ("interview_notes",   "Interview notes"),
                ("rejection_reason",  "Rejection reason"),
                ("notes",             "Notes"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
            t = tk.Text(body, height=3, width=70, wrap="word")
            t.grid(row=row, column=1, columnspan=3,
                     sticky="ew", padx=4, pady=(6, 2))
            self.texts[key] = t
            row += 1

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["application_received_on"].set(
            _dt.date.today().isoformat())
        self.vars["source"].set(DEFAULT_APPLICANT_SOURCE)
        self.vars["status"].set(DEFAULT_APPLICANT_STATUS)

    def _load(self) -> None:
        a = self.applicant
        assert a is not None
        for key in ("first_name", "last_name", "email", "phone",
                     "application_received_on", "source",
                     "interview_date", "offer_made_on",
                     "offer_response_on", "started_on",
                     "status"):
            self.vars[key].set(getattr(a, key) or "")
        self.vars["interview_score"].set(
            str(a.interview_score)
            if a.interview_score is not None else "")
        self.vars["offer_salary"].set(
            str(a.offer_salary)
            if a.offer_salary is not None else "")
        for k in self.bools:
            self.bools[k].set(getattr(a, k))
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(a, k) or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        for k, b in self.bools.items():
            payload[k] = b.get()
        try:
            if self.applicant:
                self.result = data.update_applicant(
                    self.applicant.applicant_id, payload)
            else:
                self.result = data.add_applicant(
                    self.vacancy_id, payload)
        except ValidationError as exc:
            messagebox.showerror("Recruitment", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class InterviewDialog:
    def __init__(self, parent, *, applicant: Applicant) -> None:
        self.applicant = applicant
        self.result: Applicant | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Interview — #{applicant.applicant_id}")
        self.win.geometry("520x380")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Score (0-100)").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.score = tk.StringVar(
            value=str(applicant.interview_score)
            if applicant.interview_score is not None else "")
        ttk.Entry(body, textvariable=self.score,
                    width=8).grid(
            row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Notes").grid(
            row=1, column=0, sticky="nw", padx=4, pady=4)
        self.notes = tk.Text(body, height=10, width=50,
                                wrap="word")
        self.notes.insert("1.0", applicant.interview_notes or "")
        self.notes.grid(row=1, column=1, sticky="ew",
                          padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        score_raw = self.score.get().strip()
        score = (int(score_raw)
                  if score_raw and score_raw.isdigit() else None)
        try:
            self.result = data.record_interview(
                self.applicant.applicant_id,
                score=score,
                notes=self.notes.get("1.0", "end").rstrip()
                or None)
        except ValidationError as exc:
            messagebox.showerror("Recruitment", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class OfferDialog:
    def __init__(self, parent, *, applicant: Applicant) -> None:
        self.applicant = applicant
        self.result: Applicant | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Make offer — #{applicant.applicant_id}")
        self.win.geometry("420x200")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Salary (£)").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.salary = tk.StringVar(
            value=str(applicant.offer_salary)
            if applicant.offer_salary is not None else "")
        ttk.Entry(body, textvariable=self.salary).grid(
            row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Made on").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.when = tk.StringVar(
            value=_dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when,
                    width=14).grid(
            row=1, column=1, sticky="w", padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        sal_raw = self.salary.get().strip()
        sal = None
        if sal_raw:
            try:
                sal = float(sal_raw)
            except ValueError:
                messagebox.showerror("Recruitment",
                                        "Salary must be a number.",
                                        parent=self.win)
                return
        try:
            self.result = data.make_offer(
                self.applicant.applicant_id,
                salary=sal,
                offer_made_on=self.when.get().strip())
        except ValidationError as exc:
            messagebox.showerror("Recruitment", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class OfferResponseDialog:
    def __init__(self, parent, *, applicant: Applicant) -> None:
        self.applicant = applicant
        self.result: Applicant | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Offer response — #{applicant.applicant_id}")
        self.win.geometry("400x180")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        self.accepted = tk.BooleanVar(value=True)
        ttk.Checkbutton(body, text="Accepted",
                         variable=self.accepted).grid(
            row=0, column=0, columnspan=2, sticky="w",
            padx=4, pady=6)
        ttk.Label(body, text="Response on").grid(
            row=1, column=0, sticky="w", padx=4, pady=6)
        self.when = tk.StringVar(
            value=_dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when, width=14).grid(
            row=1, column=1, sticky="w", padx=4, pady=6)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.offer_response(
                self.applicant.applicant_id,
                accepted=self.accepted.get(),
                response_on=self.when.get().strip())
        except ValidationError as exc:
            messagebox.showerror("Recruitment", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class RejectDialog:
    def __init__(self, parent, *, applicant: Applicant) -> None:
        self.applicant = applicant
        self.result: Applicant | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Reject — #{applicant.applicant_id}")
        self.win.geometry("500x300")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Reason*").grid(
            row=0, column=0, sticky="nw", padx=4, pady=4)
        self.reason = tk.Text(body, height=6, width=48,
                                  wrap="word")
        self.reason.insert("1.0",
                              applicant.rejection_reason or "")
        self.reason.grid(row=0, column=1, sticky="ew",
                            padx=4, pady=4)
        self.post_iv = tk.BooleanVar()
        ttk.Checkbutton(body, text="Post-interview rejection",
                         variable=self.post_iv).grid(
            row=1, column=0, columnspan=2, sticky="w",
            padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Reject",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.reject_applicant(
                self.applicant.applicant_id,
                reason=self.reason.get("1.0", "end").rstrip(),
                post_interview=self.post_iv.get())
        except ValidationError as exc:
            messagebox.showerror("Recruitment", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


def _prompt_text(parent, title: str, *,
                  initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("360x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=initial)
    ttk.Entry(win, textvariable=var).pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get().strip()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


def _prompt_choice(parent, title: str, options: list[str], *,
                    default: str | None = None) -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("320x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=default or (options[0] if options else ""))
    ttk.Combobox(win, textvariable=var, values=options,
                  state="readonly").pack(fill="x", padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = var.get()
        win.destroy()

    bar = ttk.Frame(win)
    bar.pack(fill="x", padx=8, pady=12)
    ttk.Button(bar, text="OK", command=ok).pack(side="right", padx=4)
    ttk.Button(bar, text="Cancel",
                command=win.destroy).pack(side="right")
    win.wait_window()
    return result["value"]


__all__ = ["open_recruitment_window"]
