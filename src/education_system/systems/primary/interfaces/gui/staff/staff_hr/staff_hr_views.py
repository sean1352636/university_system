"""Tkinter views for Primary School Staff HR."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.platform import branding
from education_system.systems.primary.domain.staff.staff_hr import (
    staff_hr as data,
)
from education_system.systems.primary.domain.staff.staff_hr.staff_hr import (
    CONTRACT_TYPES,
    DEFAULT_CONTRACT_TYPE,
    DEFAULT_EMPLOYMENT_STATUS,
    DEFAULT_EVENT_STATUS,
    DEFAULT_EVENT_TYPE,
    DEFAULT_SALARY_SCALE,
    EMPLOYMENT_STATUSES,
    EVENT_STATUSES,
    EVENT_TYPES,
    HREvent,
    HRRecord,
    SALARY_SCALES,
    ValidationError,
)
from education_system.systems.primary.interfaces.gui import kit

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_EMP_TAGS = {
    "Permanent":  ("#e6f7e6", "#0d6b2a"),
    "Fixed Term": ("#e6f0ff", "#1a3f8c"),
    "Temporary":  ("#fff7e6", "#7a5800"),
    "Supply":     ("#fff7e6", "#7a5800"),
    "Casual":     ("#fff7e6", "#7a5800"),
    "Probation":  ("#fff0d6", "#7a5800"),
    "Notice":     ("#ffd1d1", "#8c0d0d"),
    "Left":       ("#eeeeee", "#444444"),
}
_EVENT_TAGS = {
    "Requested": ("#fff7e6", "#7a5800"),
    "Approved":  ("#e6f0ff", "#1a3f8c"),
    "Taken":     ("#e6f7e6", "#0d6b2a"),
    "Declined":  ("#ffd1d1", "#8c0d0d"),
    "Cancelled": ("#eeeeee", "#444444"),
}


def open_staff_hr_window(parent=None) -> None:
    data.init_db()
    if parent is None:
        # Run on its own (no main window): a root window of its own.
        win = tk.Tk()
        win.title(f"Staff HR — {branding.SYSTEM_NAME}")
        win.geometry(WIN_GEOMETRY)
        win.minsize(*WIN_MINSIZE)
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)
        _draw_staff_hr(frame, None)
        return
    kit.show_page(parent, "Staff HR",
                  lambda page: _draw_staff_hr(page, parent))


def _draw_staff_hr(parent, host) -> None:
    kit.page_heading(
        parent, "Staff HR",
        "Employment records, contracts, DBS / safeguarding checks, "
        "reviews and HR events (leave, sickness).")
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)

    RecordsTab(nb, scope="active",     label="Active")
    RecordsTab(nb, scope="probation",  label="Probation")
    RecordsTab(nb, scope="dbs_exp",    label="DBS Expired")
    RecordsTab(nb, scope="sg_exp",     label="Safeguarding Expired")
    RecordsTab(nb, scope="rev_due",    label="Reviews Overdue")
    RecordsTab(nb, scope="rtw_miss",   label="RTW Missing")
    RecordsTab(nb, scope="all",        label="All Records")
    EventsTab(nb)
    SummaryTab(nb)


def _date_years(*, ahead: int = 6, back: int = 15) -> list[str]:
    """Years for HR dates: expiries / contract ends run years ahead."""
    y = _dt.date.today().year
    return [str(v) for v in range(y + ahead, y - back - 1, -1)]


def _grid_date(body, row, col, var, **kw):
    kit.DateField(body, var, years=_date_years(), **kw).grid(
        row=row, column=col, sticky="w", padx=4, pady=2)


# ── Records tab ──────────────────────────────────────────

class RecordsTab:
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
        ttk.Label(bar, text="Employment:").pack(side="left")
        self.f_emp = kit.ChoiceField(
            bar, tk.StringVar(), choices=EMPLOYMENT_STATUSES,
            blank=True, width=14)
        self.f_emp.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Contract:").pack(side="left")
        self.f_contract = kit.ChoiceField(
            bar, tk.StringVar(), choices=CONTRACT_TYPES,
            blank=True, width=14)
        self.f_contract.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Scale:").pack(side="left")
        self.f_scale = kit.ChoiceField(
            bar, tk.StringVar(), choices=SALARY_SCALES,
            blank=True, width=14)
        self.f_scale.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "staff", "employment", "contract",
                "fte", "scale", "salary",
                "dbs_exp", "sg_exp", "review_due", "flags")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "staff": 110,
                   "employment": 120, "contract": 130,
                   "fte": 50, "scale": 100, "salary": 90,
                   "dbs_exp": 100, "sg_exp": 100,
                   "review_due": 100, "flags": 130}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "fte",
                                                  "salary")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _EMP_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.tag_configure("alert", background="#ffd1d1",
                                  foreground="#8c0d0d")
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",              self._edit),
                ("Renew DBS",         self._renew_dbs),
                ("Safeguarding done", self._safeguarding),
                ("Record review",     self._review),
                ("Change status",     self._set_status),
                ("Mark Left",         self._mark_left),
                ("Delete",            self._delete),
                ("Refresh",           self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_emp.get():
            f["employment_status"] = self.f_emp.get()
        if self.f_contract.get():
            f["contract_type"] = self.f_contract.get()
        if self.f_scale.get():
            f["salary_scale"] = self.f_scale.get()
        if self.scope == "active":
            f["active_only"] = True
        elif self.scope == "probation":
            f["probation_only"] = True
        elif self.scope == "dbs_exp":
            f["dbs_expired"] = True
        elif self.scope == "sg_exp":
            f["safeguarding_expired"] = True
        elif self.scope == "rev_due":
            f["reviews_overdue"] = True
        elif self.scope == "rtw_miss":
            f["rtw_missing"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        rows = data.list_records(**self._filters())
        for r in rows:
            flags = []
            if r.dbs_expired:
                flags.append("DBS")
            if r.safeguarding_expired:
                flags.append("SG")
            if r.review_overdue:
                flags.append("REV")
            if r.probation_ending_soon:
                flags.append("PROB30")
            if not r.right_to_work_checked:
                flags.append("RTW")
            tag = ("alert" if flags else r.employment_status)
            self.tree.insert(
                "", "end", iid=str(r.record_id),
                values=(r.record_id, r.staff_id,
                         r.employment_status, r.contract_type,
                         f"{r.fte_percent:.0f}",
                         r.salary_scale,
                         (f"£{r.salary_amount:.0f}"
                            if r.salary_amount else "—"),
                         r.dbs_expires_on or "—",
                         r.safeguarding_expires_on or "—",
                         r.next_review_due or "—",
                         ",".join(flags)),
                tags=(tag,))
        self.count.config(text=f"{len(rows)} record(s)")

    def _selected(self) -> HRRecord | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Staff HR",
                                  "Select a record first.",
                                  parent=self.frame)
            return None
        return data.get_record(int(sel[0]))

    def _new(self) -> None:
        if RecordEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        r = self._selected()
        if r and RecordEditor(self.frame,
                                    record=r).result is not None:
            self.refresh()

    def _renew_dbs(self) -> None:
        r = self._selected()
        if not r:
            return
        if DBSDialog(self.frame, record=r).result is not None:
            self.refresh()

    def _safeguarding(self) -> None:
        r = self._selected()
        if not r:
            return
        if SafeguardingDialog(
                self.frame, record=r).result is not None:
            self.refresh()

    def _review(self) -> None:
        r = self._selected()
        if not r:
            return
        if ReviewDialog(self.frame,
                            record=r).result is not None:
            self.refresh()

    def _set_status(self) -> None:
        r = self._selected()
        if not r:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(EMPLOYMENT_STATUSES),
                                default=r.employment_status)
        if not new:
            return
        try:
            data.set_employment_status(r.record_id, new)
        except ValidationError as exc:
            messagebox.showerror("Staff HR", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _mark_left(self) -> None:
        r = self._selected()
        if not r:
            return
        when = _prompt_text(self.frame, "End date",
                              initial=_dt.date.today().isoformat(),
                              kind="date")
        if not when:
            return
        try:
            data.mark_left(r.record_id, end_date=when)
        except ValidationError as exc:
            messagebox.showerror("Staff HR", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        r = self._selected()
        if not r:
            return
        if not messagebox.askyesno(
                "Staff HR",
                f"Delete HR record #{r.record_id}?",
                parent=self.frame):
            return
        data.delete_record(r.record_id)
        self.refresh()


# ── Events tab ───────────────────────────────────────────

class EventsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Events")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Staff:").pack(side="left")
        self.f_staff = kit.StaffPicker(bar, tk.StringVar(),
                                        active_only=False, width=30)
        self.f_staff.pack(side="left", padx=(2, 8))
        self.f_staff.bind_change(lambda _v: self.refresh())
        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = kit.ChoiceField(bar, tk.StringVar(),
                                       choices=EVENT_TYPES,
                                       blank=True, width=18)
        self.f_type.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = kit.ChoiceField(
            bar, tk.StringVar(), choices=EVENT_STATUSES,
            blank=True, width=12)
        self.f_status.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "staff", "type", "start", "end",
                "days", "hours", "status", "approved_by")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "staff": 110, "type": 150,
                   "start": 100, "end": 100,
                   "days": 70, "hours": 70,
                   "status": 110, "approved_by": 130}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "days",
                                                  "hours")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _EVENT_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",       self._edit),
                ("Approve",    self._approve),
                ("Decline",    self._decline),
                ("Mark taken", self._mark_taken),
                ("Delete",     self._delete),
                ("Refresh",    self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_staff.get().strip():
            f["staff_id"] = self.f_staff.get().strip()
        if self.f_type.get():
            f["event_type"] = self.f_type.get()
        if self.f_status.get():
            f["event_status"] = self.f_status.get()
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        rows = data.list_events(**self._filters())
        for e in rows:
            self.tree.insert(
                "", "end", iid=str(e.event_id),
                values=(e.event_id, e.staff_id, e.event_type,
                         e.start_date, e.end_date or "—",
                         (e.days if e.days is not None
                          else "—"),
                         (e.hours if e.hours is not None
                          else "—"),
                         e.event_status,
                         e.approved_by or "—"),
                tags=(e.event_status,))
        self.count.config(text=f"{len(rows)} event(s)")

    def _selected(self) -> HREvent | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Staff HR",
                                  "Select an event first.",
                                  parent=self.frame)
            return None
        return data.get_event(int(sel[0]))

    def _new(self) -> None:
        if EventEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        e = self._selected()
        if e and EventEditor(self.frame,
                                  event=e).result is not None:
            self.refresh()

    def _approve(self) -> None:
        e = self._selected()
        if not e:
            return
        by = _prompt_text(self.frame, "Approved by",
                            initial=e.approved_by or "",
                            kind="staff_name")
        if not by:
            return
        try:
            data.approve_event(e.event_id, approved_by=by)
        except ValidationError as exc:
            messagebox.showerror("Staff HR", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _decline(self) -> None:
        e = self._selected()
        if not e:
            return
        try:
            data.decline_event(e.event_id)
        except ValidationError as exc:
            messagebox.showerror("Staff HR", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _mark_taken(self) -> None:
        e = self._selected()
        if not e:
            return
        try:
            data.mark_taken(e.event_id)
        except ValidationError as exc:
            messagebox.showerror("Staff HR", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        e = self._selected()
        if not e:
            return
        if not messagebox.askyesno(
                "Staff HR",
                f"Delete event #{e.event_id}?",
                parent=self.frame):
            return
        data.delete_event(e.event_id)
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
        self.text.insert("end", "Staff HR Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total records           : {s.total_records}\n"
                            f"Active records          : {s.active_records}\n"
                            f"On probation            : {s.on_probation}\n"
                            f"Probation ending soon   : {s.probation_ending_soon}\n"
                            f"DBS expired             : {s.dbs_expired}\n"
                            f"Safeguarding expired    : {s.safeguarding_expired}\n"
                            f"Reviews overdue         : {s.reviews_overdue}\n"
                            f"Right-to-work missing   : {s.right_to_work_missing}\n"
                            f"Total events            : {s.total_events}\n"
                            f"Sick events open        : {s.sick_events_open}\n"
                            f"Annual leave taken days : {s.annual_leave_taken_days}\n"
                            f"Sick days taken         : {s.sick_taken_days}\n\n")
        self.text.insert("end", "By employment status:\n")
        for k in EMPLOYMENT_STATUSES:
            n = s.by_employment_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.insert("end", "\nBy contract type:\n")
        for k in CONTRACT_TYPES:
            n = s.by_contract_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<18}: {n}\n")
        self.text.insert("end", "\nBy scale:\n")
        for k in SALARY_SCALES:
            n = s.by_scale.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<18}: {n}\n")
        self.text.insert("end", "\nBy event type:\n")
        for k in EVENT_TYPES:
            n = s.by_event_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.config(state="disabled")


# ── Editors ──────────────────────────────────────────────

class RecordEditor:
    def __init__(self, parent, *,
                 record: HRRecord | None = None) -> None:
        self.record = record
        self.result: HRRecord | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit HR #{record.record_id}"
                          if record else "New HR record")
        self.win.geometry("1000x700")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if record:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body, bar = kit.scrolled_form(self.win)
        self.vars: dict[str, tk.Variable] = {}
        self.bools: dict[str, tk.BooleanVar] = {}

        ttk.Label(body, text="Staff*").grid(
            row=0, column=0, sticky="w", padx=4, pady=2)
        self.staff_var = tk.StringVar()
        kit.StaffPicker(body, self.staff_var, active_only=False,
                        width=44).grid(row=0, column=1, columnspan=3,
                                       sticky="w", padx=4, pady=2)

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
            kit.ChoiceField(body, v, choices=values, width=width).grid(
                row=row, column=col + 1, sticky="w", padx=4, pady=2)

        def date(row, col, label, key):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            _grid_date(body, row, col + 1, v)

        def number(row, col, label, key, **kw):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            kit.NumberField(body, v, **kw).grid(
                row=row, column=col + 1, sticky="w", padx=4, pady=2)

        combo(1, 0, "Employment status*", "employment_status",
                 EMPLOYMENT_STATUSES)
        combo(1, 2, "Contract type*", "contract_type",
                 CONTRACT_TYPES)
        number(2, 0, "FTE percent (0-100)", "fte_percent", to=100)
        combo(2, 2, "Salary scale*", "salary_scale",
                 SALARY_SCALES)
        entry(3, 0, "Spine point", "spine_point")
        number(3, 2, "Salary (£)", "salary_amount",
               increment=0.01, to=999999, width=12)
        number(4, 0, "Holiday entitle. (days)",
                 "holiday_entitlement_days", to=366)
        date(4, 2, "Start date*", "start_date")
        date(5, 0, "Probation end", "probation_end")
        date(5, 2, "Contract end", "contract_end")
        date(6, 0, "End date", "end_date")
        entry(6, 2, "DBS number", "dbs_number")
        date(7, 0, "DBS issued on", "dbs_issued_on")
        date(7, 2, "DBS expires on", "dbs_expires_on")
        date(8, 0, "RTW checked on", "right_to_work_checked_on")
        date(8, 2, "Safeguarding trained on",
                 "safeguarding_training_on")
        date(9, 0, "Safeguarding expires on",
                 "safeguarding_expires_on")
        date(9, 2, "Last review on", "last_review_on")
        date(10, 0, "Next review due", "next_review_due")
        entry(10, 2, "Union", "union_member")

        self.bools["right_to_work_checked"] = tk.BooleanVar()
        ttk.Checkbutton(body, text="Right to work checked",
                         variable=self.bools["right_to_work_checked"]
                         ).grid(row=11, column=0, sticky="w",
                                  padx=4, pady=4)
        self.bools["pension_enrolled"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(body, text="Pension enrolled",
                         variable=self.bools["pension_enrolled"]
                         ).grid(row=11, column=2, sticky="w",
                                  padx=4, pady=4)

        ttk.Label(body, text="Notes").grid(
            row=12, column=0, sticky="nw", padx=4, pady=(6, 2))
        self.notes = tk.Text(body, height=4, width=74, wrap="word")
        self.notes.grid(row=12, column=1, columnspan=3,
                          sticky="ew", padx=4, pady=(6, 2))

        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["employment_status"].set(
            DEFAULT_EMPLOYMENT_STATUS)
        self.vars["contract_type"].set(DEFAULT_CONTRACT_TYPE)
        self.vars["fte_percent"].set("100")
        self.vars["salary_scale"].set(DEFAULT_SALARY_SCALE)
        self.vars["start_date"].set(
            _dt.date.today().isoformat())

    def _load(self) -> None:
        r = self.record
        assert r is not None
        self.staff_var.set(r.staff_id)
        for key in ("employment_status", "contract_type",
                     "salary_scale", "spine_point",
                     "start_date", "probation_end",
                     "contract_end", "end_date",
                     "dbs_number", "dbs_issued_on",
                     "dbs_expires_on",
                     "right_to_work_checked_on",
                     "safeguarding_training_on",
                     "safeguarding_expires_on",
                     "last_review_on", "next_review_due",
                     "union_member"):
            self.vars[key].set(getattr(r, key) or "")
        self.vars["fte_percent"].set(str(r.fte_percent))
        self.vars["salary_amount"].set(
            str(r.salary_amount)
            if r.salary_amount is not None else "")
        self.vars["holiday_entitlement_days"].set(
            str(r.holiday_entitlement_days)
            if r.holiday_entitlement_days is not None else "")
        self.bools["right_to_work_checked"].set(
            r.right_to_work_checked)
        self.bools["pension_enrolled"].set(r.pension_enrolled)
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", r.notes or "")

    def _save(self) -> None:
        staff_id = self.staff_var.get().strip()
        if not staff_id:
            messagebox.showerror("Staff HR",
                                    "Pick a staff member.",
                                    parent=self.win)
            return
        payload: dict = {
            "staff_id": staff_id,
            "notes": self.notes.get("1.0", "end").rstrip() or None,
        }
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, b in self.bools.items():
            payload[k] = b.get()
        try:
            if self.record:
                self.result = data.update_record(
                    self.record.record_id, payload)
            else:
                self.result = data.create_record(payload)
        except ValidationError as exc:
            messagebox.showerror("Staff HR", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class DBSDialog:
    def __init__(self, parent, *, record: HRRecord) -> None:
        self.record = record
        self.result: HRRecord | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Renew DBS — #{record.record_id}")
        self.win.geometry("520x220")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="DBS number*").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.num = tk.StringVar(value=record.dbs_number or "")
        ttk.Entry(body, textvariable=self.num).grid(
            row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Issued on").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.issued = tk.StringVar(
            value=_dt.date.today().isoformat())
        _grid_date(body, 1, 1, self.issued)
        ttk.Label(body, text="Expires on").grid(
            row=2, column=0, sticky="w", padx=4, pady=4)
        self.expires = tk.StringVar()
        _grid_date(body, 2, 1, self.expires)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.renew_dbs(
                self.record.record_id,
                number=self.num.get().strip(),
                issued_on=self.issued.get().strip()
                or _dt.date.today().isoformat(),
                expires_on=self.expires.get().strip() or None)
        except ValidationError as exc:
            messagebox.showerror("Staff HR", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class SafeguardingDialog:
    def __init__(self, parent, *, record: HRRecord) -> None:
        self.record = record
        self.result: HRRecord | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Safeguarding — #{record.record_id}")
        self.win.geometry("520x200")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Trained on").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.trained = tk.StringVar(
            value=_dt.date.today().isoformat())
        _grid_date(body, 0, 1, self.trained)
        ttk.Label(body, text="Expires on").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.expires = tk.StringVar()
        _grid_date(body, 1, 1, self.expires)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.mark_safeguarding_completed(
                self.record.record_id,
                trained_on=self.trained.get().strip()
                or _dt.date.today().isoformat(),
                expires_on=self.expires.get().strip() or None)
        except ValidationError as exc:
            messagebox.showerror("Staff HR", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class ReviewDialog:
    def __init__(self, parent, *, record: HRRecord) -> None:
        self.record = record
        self.result: HRRecord | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Record review — #{record.record_id}")
        self.win.geometry("520x200")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Reviewed on").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.when = tk.StringVar(
            value=_dt.date.today().isoformat())
        _grid_date(body, 0, 1, self.when)
        ttk.Label(body, text="Next review due").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.next_due = tk.StringVar(
            value=record.next_review_due or "")
        _grid_date(body, 1, 1, self.next_due)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.record_review(
                self.record.record_id,
                reviewed_on=self.when.get().strip(),
                next_review_due=self.next_due.get().strip()
                or None)
        except ValidationError as exc:
            messagebox.showerror("Staff HR", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class EventEditor:
    def __init__(self, parent, *,
                 event: HREvent | None = None) -> None:
        self.event = event
        self.result: HREvent | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit event #{event.event_id}"
                          if event else "New event")
        self.win.geometry("720x600")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if event:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body, bar = kit.scrolled_form(self.win)
        body.grid_columnconfigure(1, weight=1)
        self.vars: dict[str, tk.Variable] = {}

        ttk.Label(body, text="Staff*").grid(
            row=0, column=0, sticky="w", padx=4, pady=2)
        self.staff_var = tk.StringVar()
        kit.StaffPicker(body, self.staff_var, active_only=False,
                        width=44).grid(row=0, column=1, sticky="w",
                                       padx=4, pady=2)

        def label(row, text):
            ttk.Label(body, text=text).grid(
                row=row, column=0, sticky="w", padx=4, pady=2)

        def var(key):
            v = tk.StringVar()
            self.vars[key] = v
            return v

        def place(row, widget, sticky="w"):
            widget.grid(row=row, column=1, sticky=sticky, padx=4, pady=2)

        def entry(row, text, key):
            label(row, text)
            place(row, ttk.Entry(body, textvariable=var(key)), "ew")

        def combo(row, text, key, values):
            label(row, text)
            place(row, kit.ChoiceField(body, var(key), choices=values))

        def date(row, text, key):
            label(row, text)
            place(row, kit.DateField(body, var(key), years=_date_years()))

        def number(row, text, key):
            label(row, text)
            place(row, kit.NumberField(body, var(key), to=999,
                                       increment=0.5, width=8))

        combo(1, "Event type*", "event_type", EVENT_TYPES)
        combo(2, "Event status*", "event_status", EVENT_STATUSES)
        date(3, "Start date*", "start_date")
        date(4, "End date", "end_date")
        number(5, "Days", "days")
        number(6, "Hours", "hours")
        entry(7, "Reason", "reason")
        label(8, "Approved by")
        place(8, kit.StaffPicker(body, var("approved_by"), by="name",
                                 active_only=False, width=44))
        date(9, "Approved on", "approved_on")
        ttk.Label(body, text="Notes").grid(
            row=10, column=0, sticky="nw", padx=4, pady=4)
        self.notes = tk.Text(body, height=4, wrap="word")
        self.notes.grid(row=10, column=1, sticky="ew",
                          padx=4, pady=4)

        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["event_type"].set(DEFAULT_EVENT_TYPE)
        self.vars["event_status"].set(DEFAULT_EVENT_STATUS)
        self.vars["start_date"].set(
            _dt.date.today().isoformat())

    def _load(self) -> None:
        e = self.event
        assert e is not None
        self.staff_var.set(e.staff_id)
        for key in ("event_type", "event_status",
                     "start_date", "end_date", "reason",
                     "approved_by", "approved_on"):
            self.vars[key].set(getattr(e, key) or "")
        self.vars["days"].set(
            str(e.days) if e.days is not None else "")
        self.vars["hours"].set(
            str(e.hours) if e.hours is not None else "")
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", e.notes or "")

    def _save(self) -> None:
        staff_id = self.staff_var.get().strip()
        if not staff_id:
            messagebox.showerror("Staff HR",
                                    "Pick a staff member.",
                                    parent=self.win)
            return
        payload: dict = {
            "staff_id": staff_id,
            "notes": self.notes.get("1.0", "end").rstrip() or None,
        }
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        try:
            if self.event:
                self.result = data.update_event(
                    self.event.event_id, payload)
            else:
                self.result = data.create_event(payload)
        except ValidationError as exc:
            messagebox.showerror("Staff HR", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


def _prompt_text(parent, title: str, *,
                  initial: str = "", kind: str = "text") -> str | None:
    """Ask for one value: typed text, a date (``kind="date"``) or a
    member of staff by name (``kind="staff_name"``)."""
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("460x140")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    var = tk.StringVar(value=initial)
    if kind == "date":
        kit.DateField(win, var, years=_date_years()).pack(anchor="w", padx=8)
    elif kind == "staff_name":
        kit.StaffPicker(win, var, by="name", active_only=False,
                        width=44).pack(anchor="w", padx=8)
    else:
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
    kit.ChoiceField(win, var, choices=options).pack(fill="x", padx=8)
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


__all__ = ["open_staff_hr_window"]
