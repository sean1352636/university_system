"""Tkinter views for Sixth Form Disciplinary."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.shared import branding
from education_system.post_16.sixthform_system.modules.domain.pastoral.disciplinary import (
    disciplinary as data,
)
from education_system.post_16.sixthform_system.modules.domain.pastoral.disciplinary.disciplinary import (
    CASE_TYPES,
    DEFAULT_CASE_TYPE,
    DEFAULT_STATUS,
    DisciplinaryCase,
    SEVERITIES,
    STATUSES,
    ValidationError,
    severity_label,
)
from education_system.post_16.sixthform_system.modules.domain.students.students import (
    students as student_data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Reported":            ("#fff7e6", "#7a5800"),
    "Under Investigation": ("#fff0d6", "#7a5800"),
    "Sanction Issued":     ("#ffe6e6", "#8c0d0d"),
    "Sanction Served":     ("#e6f7e6", "#0d6b2a"),
    "Appealed":            ("#e6e6ff", "#3a3a8c"),
    "Appeal Upheld":       ("#ffd1d1", "#8c0d0d"),
    "Appeal Overturned":   ("#d6ffd6", "#0d6b2a"),
    "Closed":              ("#eeeeee", "#444444"),
}


def open_disciplinary_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Disciplinary — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    CasesTab(nb, scope="open",              label="Open")
    CasesTab(nb, scope="active_sanction",   label="Active Sanctions")
    CasesTab(nb, scope="appeals",           label="Appeals Pending")
    CasesTab(nb, scope="parent_meetings",   label="Parent Meetings")
    CasesTab(nb, scope="all",               label="All")
    SummaryTab(nb)


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


class CasesTab:
    def __init__(self, nb: ttk.Notebook, *,
                 scope: str, label: str) -> None:
        self.scope = scope
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student id:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar, values=("",) + CASE_TYPES,
                                     state="readonly", width=22)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))

        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + STATUSES,
                                           state="readonly", width=20)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None

        ttk.Label(bar, text="Min sev:").pack(side="left")
        self.f_sev = ttk.Combobox(bar, values=("", "1", "2", "3",
                                                  "4", "5"),
                                     state="readonly", width=4)
        self.f_sev.current(0)
        self.f_sev.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Issued by:").pack(side="left")
        self.f_issued = ttk.Entry(bar, width=14)
        self.f_issued.pack(side="left", padx=(2, 8))

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                  padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "incident", "student", "type", "severity",
                "title", "status", "sanction", "parent")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 60, "incident": 90, "student": 100,
                   "type": 170, "severity": 80, "title": 220,
                   "status": 130, "sanction": 170, "parent": 100}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "severity")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.tag_configure("active_sanction",
                                  background="#ffd1d1",
                                  foreground="#8c0d0d")
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("View / Edit",     self._edit),
                ("Issue sanction",  self._issue),
                ("Mark served",     self._served),
                ("Inform parent",   self._parent),
                ("Submit appeal",   self._appeal),
                ("Resolve appeal",  self._resolve),
                ("Close case",      self._close),
                ("Change status",   self._set_status),
                ("Delete",          self._delete),
                ("Refresh",         self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_type.current(0)
        self.f_sev.current(0)
        self.f_issued.delete(0, "end")
        if self.f_status is not None:
            self.f_status.current(0)
        self.refresh()

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_student.get().strip():
            f["student_id"] = self.f_student.get().strip()
        if self.f_type.get():
            f["case_type"] = self.f_type.get()
        if self.f_sev.get():
            f["severity_min"] = int(self.f_sev.get())
        if self.f_issued.get().strip():
            f["issued_by_like"] = self.f_issued.get().strip()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "open":
            f["open_only"] = True
        elif self.scope == "active_sanction":
            f["active_sanction"] = True
        elif self.scope == "appeals":
            f["appeal_pending"] = True
        elif self.scope == "parent_meetings":
            f["parent_meeting_pending"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_cases(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Disciplinary", str(e),
                                    parent=self.frame)
            return
        for c in rows:
            sanc = "—"
            if c.sanction_start or c.sanction_end:
                sanc = (f"{c.sanction_start or '?'} → "
                          f"{c.sanction_end or '?'}")
                if c.sanction_active:
                    sanc = f"ACTIVE  {sanc}"
            parent_str = ("yes" if c.parent_informed else "no")
            if c.parent_meeting_on:
                parent_str = f"mtg {c.parent_meeting_on}"
            elif c.parent_meeting_pending:
                parent_str = "PENDING"
            tag = ("active_sanction" if c.sanction_active
                     else c.status)
            self.tree.insert("", "end", iid=str(c.case_id),
                              values=(c.case_id,
                                       c.incident_date,
                                       c.student_id,
                                       c.case_type,
                                       (f"{c.severity} "
                                        f"{severity_label(c.severity)[:3]}"),
                                       c.title, c.status,
                                       sanc, parent_str),
                              tags=(tag,))
        self.count.config(text=f"{len(rows)} case(s)")

    def _selected(self) -> DisciplinaryCase | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Disciplinary",
                                  "Select a case first.",
                                  parent=self.frame)
            return None
        return data.get_case(int(sel[0]))

    def _new(self) -> None:
        if DisciplinaryEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        c = self._selected()
        if c and DisciplinaryEditor(self.frame,
                                          case=c).result is not None:
            self.refresh()

    def _issue(self) -> None:
        c = self._selected()
        if not c:
            return
        if SanctionDialog(self.frame, case=c).result is not None:
            self.refresh()

    def _served(self) -> None:
        c = self._selected()
        if not c:
            return
        try:
            data.mark_served(c.case_id)
        except ValidationError as e:
            messagebox.showerror("Disciplinary", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _parent(self) -> None:
        c = self._selected()
        if not c:
            return
        if ParentDialog(self.frame, case=c).result is not None:
            self.refresh()

    def _appeal(self) -> None:
        c = self._selected()
        if not c:
            return
        try:
            data.submit_appeal(c.case_id)
        except ValidationError as e:
            messagebox.showerror("Disciplinary", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _resolve(self) -> None:
        c = self._selected()
        if not c:
            return
        if AppealDialog(self.frame, case=c).result is not None:
            self.refresh()

    def _close(self) -> None:
        c = self._selected()
        if not c:
            return
        if CloseDialog(self.frame, case=c).result is not None:
            self.refresh()

    def _set_status(self) -> None:
        c = self._selected()
        if not c:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES), default=c.status)
        if not new:
            return
        try:
            data.set_status(c.case_id, new)
        except ValidationError as e:
            messagebox.showerror("Disciplinary", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        c = self._selected()
        if not c:
            return
        if not messagebox.askyesno(
                "Disciplinary", f"Delete case #{c.case_id}?",
                parent=self.frame):
            return
        data.delete_case(c.case_id)
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
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.refresh()

    def refresh(self) -> None:
        s = data.summary()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", "Disciplinary Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total                : {s.total}\n"
                            f"Open                 : {s.open_count}\n"
                            f"Active sanctions     : {s.active_sanctions}\n"
                            f"Appeals pending      : {s.appeals_pending}\n"
                            f"Parent mtgs pending  : {s.pending_parent_meetings}\n"
                            f"Distinct students    : {s.distinct_students}\n"
                            f"Average severity     : "
                            f"{s.average_severity if s.average_severity is not None else '—'}\n\n")
        self.text.insert("end", "By status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy type:\n")
        for k in CASE_TYPES:
            n = s.by_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<24}: {n}\n")
        self.text.insert("end", "\nBy severity:\n")
        for sev in SEVERITIES:
            n = s.by_severity.get(sev, 0)
            if n:
                self.text.insert("end",
                                    f"  {sev}  {severity_label(sev):<12}: {n}\n")
        self.text.config(state="disabled")


# ── Editor ────────────────────────────────────────────────────────

class DisciplinaryEditor:
    def __init__(self, parent, *,
                 case: DisciplinaryCase | None = None) -> None:
        self.case = case
        self.result: DisciplinaryCase | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit case #{case.case_id}"
                          if case else "New disciplinary case")
        self.win.geometry("840x820")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if case:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}

        ttk.Label(body, text="Student*").grid(
            row=0, column=0, sticky="w", padx=4, pady=2)
        self.student_combo = ttk.Combobox(body, state="readonly",
                                              width=42)
        opts = _student_options()
        self._student_opts = opts
        self.student_combo["values"] = [lbl for _, lbl in opts]
        self.student_combo.grid(row=0, column=1, columnspan=3,
                                  sticky="ew", padx=4, pady=2)

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

        entry(1, 0, "Title*", "title", width=46)
        entry(2, 0, "Incident date*", "incident_date")
        entry(2, 2, "Reported on", "reported_on")
        combo(3, 0, "Type*", "case_type", CASE_TYPES)
        combo(3, 2, "Severity*", "severity",
                 ("1", "2", "3", "4", "5"))
        combo(4, 0, "Status*", "status", STATUSES)
        entry(4, 2, "Location", "location")
        entry(5, 0, "Issued by", "issued_by")
        entry(5, 2, "Signed off by", "signed_off_by")
        entry(6, 0, "Witnesses", "witnesses")
        entry(6, 2, "Linked behaviour id", "related_behaviour_id")
        entry(7, 0, "Sanction start", "sanction_start")
        entry(7, 2, "Sanction end", "sanction_end")
        entry(8, 0, "Sanction days", "sanction_days")
        self.parent_informed = tk.BooleanVar()
        ttk.Checkbutton(body, text="Parent informed",
                         variable=self.parent_informed).grid(
            row=8, column=2, sticky="w", padx=4, pady=2)
        entry(9, 0, "Parent informed on", "parent_informed_on")
        entry(9, 2, "Parent meeting on", "parent_meeting_on")
        entry(10, 0, "Appeal submitted on", "appeal_submitted_on")
        entry(10, 2, "Appeal outcome", "appeal_outcome")

        row = 11
        for key, label in (
                ("description",         "Description"),
                ("sanction_summary",    "Sanction summary"),
                ("reintegration_plan",  "Reintegration plan"),
                ("notes",               "Notes"),
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

        today = _dt.date.today().isoformat()
        self.vars["incident_date"].set(today)
        self.vars["reported_on"].set(today)
        self.vars["case_type"].set(DEFAULT_CASE_TYPE)
        self.vars["severity"].set("2")
        self.vars["status"].set(DEFAULT_STATUS)

    def _load(self) -> None:
        c = self.case
        assert c is not None
        for i, (sid, _) in enumerate(self._student_opts):
            if sid == c.student_id:
                self.student_combo.current(i)
                break
        for key in ("title", "incident_date", "reported_on",
                     "case_type", "status", "location",
                     "issued_by", "signed_off_by", "witnesses",
                     "sanction_start", "sanction_end",
                     "parent_informed_on", "parent_meeting_on",
                     "appeal_submitted_on", "appeal_outcome"):
            self.vars[key].set(getattr(c, key) or "")
        self.vars["severity"].set(str(c.severity))
        self.vars["sanction_days"].set(
            str(c.sanction_days) if c.sanction_days is not None
            else "")
        self.vars["related_behaviour_id"].set(
            str(c.related_behaviour_id)
            if c.related_behaviour_id else "")
        self.parent_informed.set(c.parent_informed)
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(c, k) or "")

    def _save(self) -> None:
        idx = self.student_combo.current()
        if idx < 0:
            messagebox.showerror("Disciplinary",
                                    "Pick a student.",
                                    parent=self.win)
            return
        payload: dict = {
            "student_id": self._student_opts[idx][0],
            "parent_informed": self.parent_informed.get(),
        }
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.case:
                self.result = data.update_case(
                    self.case.case_id, payload)
            else:
                self.result = data.create_case(payload)
        except ValidationError as exc:
            messagebox.showerror("Disciplinary", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


# ── Workflow dialogs ──────────────────────────────────────────────

class SanctionDialog:
    def __init__(self, parent, *, case: DisciplinaryCase) -> None:
        self.case = case
        self.result: DisciplinaryCase | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Issue sanction — #{case.case_id}")
        self.win.geometry("560x440")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Summary*").grid(
            row=0, column=0, sticky="nw", padx=4, pady=4)
        self.summary = tk.Text(body, height=5, width=52,
                                  wrap="word")
        self.summary.insert("1.0", case.sanction_summary or "")
        self.summary.grid(row=0, column=1, sticky="ew",
                            padx=4, pady=4)
        ttk.Label(body, text="Issued by*").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.issued = tk.StringVar(value=case.issued_by or "")
        ttk.Entry(body, textvariable=self.issued).grid(
            row=1, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Start").grid(
            row=2, column=0, sticky="w", padx=4, pady=4)
        self.start = tk.StringVar(value=case.sanction_start or "")
        ttk.Entry(body, textvariable=self.start, width=14).grid(
            row=2, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="End").grid(
            row=3, column=0, sticky="w", padx=4, pady=4)
        self.end = tk.StringVar(value=case.sanction_end or "")
        ttk.Entry(body, textvariable=self.end, width=14).grid(
            row=3, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Days").grid(
            row=4, column=0, sticky="w", padx=4, pady=4)
        self.days = tk.StringVar(
            value=str(case.sanction_days)
            if case.sanction_days is not None else "")
        ttk.Entry(body, textvariable=self.days, width=8).grid(
            row=4, column=1, sticky="w", padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Issue",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        days_raw = self.days.get().strip()
        days = (int(days_raw) if days_raw.isdigit() else None)
        try:
            self.result = data.issue_sanction(
                self.case.case_id,
                summary=self.summary.get("1.0", "end").rstrip(),
                issued_by=self.issued.get().strip(),
                start=self.start.get().strip() or None,
                end=self.end.get().strip() or None,
                days=days)
        except ValidationError as exc:
            messagebox.showerror("Disciplinary", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class ParentDialog:
    def __init__(self, parent, *, case: DisciplinaryCase) -> None:
        self.case = case
        self.result: DisciplinaryCase | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Inform parent — #{case.case_id}")
        self.win.geometry("420x200")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Informed on").grid(
            row=0, column=0, sticky="w", padx=4, pady=6)
        self.when = tk.StringVar(
            value=case.parent_informed_on
            or _dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when, width=14).grid(
            row=0, column=1, sticky="w", padx=4, pady=6)
        ttk.Label(body, text="Meeting on (optional)").grid(
            row=1, column=0, sticky="w", padx=4, pady=6)
        self.meeting = tk.StringVar(
            value=case.parent_meeting_on or "")
        ttk.Entry(body, textvariable=self.meeting, width=14).grid(
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
            self.result = data.inform_parent(
                self.case.case_id,
                informed_on=self.when.get().strip()
                or _dt.date.today().isoformat(),
                meeting_on=self.meeting.get().strip() or None)
        except ValidationError as exc:
            messagebox.showerror("Disciplinary", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class AppealDialog:
    def __init__(self, parent, *, case: DisciplinaryCase) -> None:
        self.case = case
        self.result: DisciplinaryCase | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Resolve appeal — #{case.case_id}")
        self.win.geometry("520x320")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Outcome*").grid(
            row=0, column=0, sticky="nw", padx=4, pady=4)
        self.outcome = tk.Text(body, height=6, width=48,
                                  wrap="word")
        self.outcome.insert("1.0", case.appeal_outcome or "")
        self.outcome.grid(row=0, column=1, sticky="ew",
                            padx=4, pady=4)
        self.upheld = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            body, text="Appeal upheld (sanction stands)",
            variable=self.upheld).grid(
            row=1, column=0, columnspan=2, sticky="w",
            padx=4, pady=8)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.resolve_appeal(
                self.case.case_id,
                outcome=self.outcome.get("1.0", "end").rstrip(),
                upheld=self.upheld.get())
        except ValidationError as exc:
            messagebox.showerror("Disciplinary", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class CloseDialog:
    def __init__(self, parent, *, case: DisciplinaryCase) -> None:
        self.case = case
        self.result: DisciplinaryCase | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Close case — #{case.case_id}")
        self.win.geometry("520x280")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Reintegration plan").grid(
            row=0, column=0, sticky="nw", padx=4, pady=4)
        self.plan = tk.Text(body, height=6, width=48, wrap="word")
        self.plan.insert("1.0", case.reintegration_plan or "")
        self.plan.grid(row=0, column=1, sticky="ew",
                          padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Close case",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.close_case(
                self.case.case_id,
                reintegration_plan=self.plan.get("1.0", "end").rstrip()
                or None)
        except ValidationError as exc:
            messagebox.showerror("Disciplinary", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


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


__all__ = ["open_disciplinary_window"]
