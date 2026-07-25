"""Tkinter views for Sixth Form Complaints."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.platform import branding
from education_system.systems.nursery.domain.pastoral.complaints import (
    complaints as data,
)
from education_system.systems.nursery.domain.pastoral.complaints.complaints import (
    CATEGORIES,
    COMPLAINANT_ROLES,
    Complaint,
    DEFAULT_CATEGORY,
    DEFAULT_COMPLAINANT_ROLE,
    DEFAULT_SATISFACTION,
    DEFAULT_STAGE,
    DEFAULT_STATUS,
    OUTCOMES,
    SATISFACTIONS,
    SEVERITIES,
    STAGES,
    STATUSES,
    ValidationError,
    severity_label,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Received":            ("#fff7e6", "#7a5800"),
    "Acknowledged":        ("#e6f0ff", "#1a3f8c"),
    "Under Investigation": ("#fff0d6", "#7a5800"),
    "Response Drafted":    ("#e6e6ff", "#3a3a8c"),
    "Response Issued":     ("#e6f7e6", "#0d6b2a"),
    "Escalated":           ("#ffd1d1", "#8c0d0d"),
    "Closed":              ("#eeeeee", "#444444"),
}


def open_complaints_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Complaints — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    ComplaintsTab(nb, scope="open",     label="Open")
    ComplaintsTab(nb, scope="overdue",  label="Overdue")
    ComplaintsTab(nb, scope="stage2",   label="Stage 2 / Appeal")
    ComplaintsTab(nb, scope="all",      label="All")
    SummaryTab(nb)


class ComplaintsTab:
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
        ttk.Label(bar, text="Category:").pack(side="left")
        self.f_cat = ttk.Combobox(bar, values=("",) + CATEGORIES,
                                    state="readonly", width=22)
        self.f_cat.current(0)
        self.f_cat.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Stage:").pack(side="left")
        self.f_stage = ttk.Combobox(bar, values=("",) + STAGES,
                                       state="readonly", width=16)
        self.f_stage.current(0)
        self.f_stage.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + STATUSES,
                                           state="readonly", width=18)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None
        ttk.Label(bar, text="Outcome:").pack(side="left")
        self.f_outcome = ttk.Combobox(bar,
                                          values=("",) + OUTCOMES,
                                          state="readonly", width=16)
        self.f_outcome.current(0)
        self.f_outcome.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Subject:").pack(side="left")
        self.f_subj = ttk.Entry(bar, width=12)
        self.f_subj.pack(side="left", padx=(2, 8))

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                  padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "received", "complainant", "category",
                "subject", "stage", "severity", "status",
                "outcome", "target")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "received": 90, "complainant": 140,
                   "category": 180, "subject": 200,
                   "stage": 130, "severity": 90,
                   "status": 130, "outcome": 130, "target": 100}
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
        self.tree.tag_configure("overdue", background="#ffd1d1",
                                  foreground="#8c0d0d")
        self.tree.tag_configure("critical", background="#ffb0b0",
                                  foreground="#6c0000")
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("View / Edit",     self._edit),
                ("Acknowledge",     self._acknowledge),
                ("Investigate",     self._investigate),
                ("Issue response",  self._response),
                ("Escalate",        self._escalate),
                ("Satisfaction",    self._satisfaction),
                ("Close",           self._close),
                ("Change status",   self._set_status),
                ("Delete",          self._delete),
                ("Refresh",         self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _clear(self) -> None:
        self.f_cat.current(0)
        self.f_stage.current(0)
        self.f_outcome.current(0)
        self.f_subj.delete(0, "end")
        if self.f_status is not None:
            self.f_status.current(0)
        self.refresh()

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_cat.get():
            f["category"] = self.f_cat.get()
        if self.f_stage.get():
            f["stage"] = self.f_stage.get()
        if self.f_outcome.get():
            f["outcome"] = self.f_outcome.get()
        if self.f_subj.get().strip():
            f["subject_like"] = self.f_subj.get().strip()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "open":
            f["open_only"] = True
        elif self.scope == "overdue":
            f["overdue_only"] = True
        elif self.scope == "stage2":
            f["stage2_or_higher"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_complaints(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Complaints", str(e),
                                    parent=self.frame)
            return
        for c in rows:
            target = c.target_response_date or "—"
            if c.response_overdue:
                target = f"OVERDUE ({target})"
                tag = "overdue"
            elif c.severity >= 4:
                tag = "critical"
            else:
                tag = c.status
            self.tree.insert(
                "", "end", iid=str(c.complaint_id),
                values=(c.complaint_id, c.received_on,
                         c.complainant_name, c.category,
                         c.subject, c.stage,
                         f"{c.severity} {severity_label(c.severity)[:3]}",
                         c.status, c.outcome or "—", target),
                tags=(tag,))
        self.count.config(text=f"{len(rows)} complaint(s)")

    def _selected(self) -> Complaint | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Complaints",
                                  "Select a complaint first.",
                                  parent=self.frame)
            return None
        return data.get_complaint(int(sel[0]))

    def _new(self) -> None:
        if ComplaintEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        c = self._selected()
        if c and ComplaintEditor(self.frame,
                                       complaint=c).result is not None:
            self.refresh()

    def _acknowledge(self) -> None:
        c = self._selected()
        if not c:
            return
        if AcknowledgeDialog(
                self.frame, complaint=c).result is not None:
            self.refresh()

    def _investigate(self) -> None:
        c = self._selected()
        if not c:
            return
        try:
            data.start_investigation(c.complaint_id)
        except ValidationError as exc:
            messagebox.showerror("Complaints", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _response(self) -> None:
        c = self._selected()
        if not c:
            return
        if ResponseDialog(self.frame,
                              complaint=c).result is not None:
            self.refresh()

    def _escalate(self) -> None:
        c = self._selected()
        if not c:
            return
        idx = STAGES.index(c.stage)
        if idx >= len(STAGES) - 1:
            messagebox.showinfo("Complaints",
                                  f"Already at final stage: {c.stage}",
                                  parent=self.frame)
            return
        if EscalateDialog(self.frame,
                              complaint=c).result is not None:
            self.refresh()

    def _satisfaction(self) -> None:
        c = self._selected()
        if not c:
            return
        sat = _prompt_choice(self.frame, "Satisfaction",
                                list(SATISFACTIONS),
                                default=c.complainant_satisfaction)
        if not sat:
            return
        try:
            data.record_satisfaction(c.complaint_id,
                                            satisfaction=sat)
        except ValidationError as exc:
            messagebox.showerror("Complaints", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _close(self) -> None:
        c = self._selected()
        if not c:
            return
        try:
            data.close_complaint(c.complaint_id)
        except ValidationError as exc:
            messagebox.showerror("Complaints", str(exc),
                                    parent=self.frame)
            return
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
            data.set_status(c.complaint_id, new)
        except ValidationError as exc:
            messagebox.showerror("Complaints", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        c = self._selected()
        if not c:
            return
        if not messagebox.askyesno(
                "Complaints",
                f"Delete complaint #{c.complaint_id}?",
                parent=self.frame):
            return
        data.delete_complaint(c.complaint_id)
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
        self.text.insert("end", "Complaints Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total                 : {s.total}\n"
                            f"Open                  : {s.open_count}\n"
                            f"Overdue               : {s.overdue}\n"
                            f"Serious / Major       : {s.serious_or_major}\n"
                            f"Stage 2 / Appeal      : {s.at_stage_2_or_appeal}\n"
                            f"Governors informed    : {s.governors_informed}\n"
                            f"Closed                : {s.closed_count}\n"
                            f"Upheld                : {s.upheld_count}\n"
                            f"Not upheld            : {s.not_upheld_count}\n"
                            f"Avg days to close     : "
                            f"{s.average_days_to_close if s.average_days_to_close is not None else '—'}\n\n")
        self.text.insert("end", "By category:\n")
        for k in CATEGORIES:
            n = s.by_category.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<24}: {n}\n")
        self.text.insert("end", "\nBy stage:\n")
        for k in STAGES:
            n = s.by_stage.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy outcome:\n")
        for k in OUTCOMES:
            n = s.by_outcome.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.config(state="disabled")


# ── Editor & dialogs ──────────────────────────────────────────────

class ComplaintEditor:
    def __init__(self, parent, *,
                 complaint: Complaint | None = None) -> None:
        self.complaint = complaint
        self.result: Complaint | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit complaint #{complaint.complaint_id}"
                          if complaint else "New complaint")
        self.win.geometry("860x880")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if complaint:
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

        entry(0, 0, "Subject*", "subject", width=48)
        entry(1, 0, "Received on*", "received_on")
        entry(1, 2, "Complainant name*", "complainant_name")
        combo(2, 0, "Complainant role*", "complainant_role",
                 COMPLAINANT_ROLES)
        combo(2, 2, "Category*", "category", CATEGORIES)
        combo(3, 0, "Stage*", "stage", STAGES)
        combo(3, 2, "Severity*", "severity",
                 ("1", "2", "3", "4", "5"))
        entry(4, 0, "Email", "contact_email")
        entry(4, 2, "Phone", "contact_phone")
        entry(5, 0, "Assigned to", "assigned_to")
        combo(5, 2, "Status*", "status", STATUSES)
        entry(6, 0, "Acknowledged on", "acknowledged_on")
        entry(6, 2, "Target response", "target_response_date")
        entry(7, 0, "Response issued on", "response_issued_on")
        entry(7, 2, "Closed on", "closed_on")
        combo(8, 0, "Outcome", "outcome", ("",) + OUTCOMES)
        combo(8, 2, "Satisfaction", "complainant_satisfaction",
                 SATISFACTIONS)
        entry(9, 0, "Linked to", "linked_to", width=48)

        flags = ttk.LabelFrame(body, text="Flags")
        flags.grid(row=10, column=0, columnspan=4,
                     sticky="ew", padx=4, pady=(8, 4))
        for col, (key, label) in enumerate((
                ("complainant_informed", "Complainant informed"),
                ("escalated_to_stage_2", "Escalated to Stage 2"),
                ("escalated_to_appeal",  "Escalated to Appeal"),
                ("governors_informed",   "Governors informed"),
        )):
            v = tk.BooleanVar()
            self.bools[key] = v
            ttk.Checkbutton(flags, text=label,
                             variable=v).grid(
                row=0, column=col, sticky="w", padx=6, pady=4)

        row = 11
        for key, label in (
                ("description",      "Description"),
                ("response_summary", "Response summary"),
                ("actions_taken",    "Actions taken"),
                ("notes",            "Notes"),
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

        self.vars["received_on"].set(_dt.date.today().isoformat())
        self.vars["complainant_role"].set(DEFAULT_COMPLAINANT_ROLE)
        self.vars["category"].set(DEFAULT_CATEGORY)
        self.vars["stage"].set(DEFAULT_STAGE)
        self.vars["severity"].set("2")
        self.vars["status"].set(DEFAULT_STATUS)
        self.vars["complainant_satisfaction"].set(
            DEFAULT_SATISFACTION)

    def _load(self) -> None:
        c = self.complaint
        assert c is not None
        for key in ("subject", "received_on", "complainant_name",
                     "complainant_role", "category", "stage",
                     "contact_email", "contact_phone",
                     "assigned_to", "status",
                     "acknowledged_on", "target_response_date",
                     "response_issued_on", "closed_on",
                     "outcome", "complainant_satisfaction",
                     "linked_to"):
            self.vars[key].set(getattr(c, key) or "")
        self.vars["severity"].set(str(c.severity))
        for k in self.bools:
            self.bools[k].set(getattr(c, k))
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(c, k) or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        for k, b in self.bools.items():
            payload[k] = b.get()
        try:
            if self.complaint:
                self.result = data.update_complaint(
                    self.complaint.complaint_id, payload)
            else:
                self.result = data.create_complaint(payload)
        except ValidationError as exc:
            messagebox.showerror("Complaints", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class AcknowledgeDialog:
    def __init__(self, parent, *, complaint: Complaint) -> None:
        self.complaint = complaint
        self.result: Complaint | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Acknowledge — #{complaint.complaint_id}")
        self.win.geometry("440x240")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Assign to").grid(
            row=0, column=0, sticky="w", padx=4, pady=6)
        self.assigned = tk.StringVar(
            value=complaint.assigned_to or "")
        ttk.Entry(body, textvariable=self.assigned).grid(
            row=0, column=1, sticky="ew", padx=4, pady=6)
        ttk.Label(body, text="Acknowledged on").grid(
            row=1, column=0, sticky="w", padx=4, pady=6)
        self.when = tk.StringVar(value=_dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when, width=14).grid(
            row=1, column=1, sticky="w", padx=4, pady=6)
        ttk.Label(body, text="Target response date").grid(
            row=2, column=0, sticky="w", padx=4, pady=6)
        self.target = tk.StringVar(
            value=complaint.target_response_date or "")
        ttk.Entry(body, textvariable=self.target, width=14).grid(
            row=2, column=1, sticky="w", padx=4, pady=6)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.acknowledge(
                self.complaint.complaint_id,
                assigned_to=self.assigned.get().strip() or None,
                acknowledged_on=self.when.get().strip()
                or _dt.date.today().isoformat(),
                target_response_date=self.target.get().strip()
                or None)
        except ValidationError as exc:
            messagebox.showerror("Complaints", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class ResponseDialog:
    def __init__(self, parent, *, complaint: Complaint) -> None:
        self.complaint = complaint
        self.result: Complaint | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Issue response — #{complaint.complaint_id}")
        self.win.geometry("560x500")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Outcome*").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.outcome = tk.StringVar(
            value=complaint.outcome or OUTCOMES[0])
        ttk.Combobox(body, textvariable=self.outcome,
                      values=OUTCOMES, state="readonly").grid(
            row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Issued on").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.when = tk.StringVar(
            value=complaint.response_issued_on
            or _dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when, width=14).grid(
            row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Response summary*").grid(
            row=2, column=0, sticky="nw", padx=4, pady=4)
        self.summary = tk.Text(body, height=6, width=48,
                                  wrap="word")
        self.summary.insert("1.0", complaint.response_summary or "")
        self.summary.grid(row=2, column=1, sticky="ew",
                            padx=4, pady=4)
        ttk.Label(body, text="Actions taken").grid(
            row=3, column=0, sticky="nw", padx=4, pady=4)
        self.actions = tk.Text(body, height=4, width=48,
                                  wrap="word")
        self.actions.insert("1.0", complaint.actions_taken or "")
        self.actions.grid(row=3, column=1, sticky="ew",
                            padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Issue",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.issue_response(
                self.complaint.complaint_id,
                summary=self.summary.get("1.0", "end").rstrip(),
                outcome=self.outcome.get(),
                issued_on=self.when.get().strip()
                or _dt.date.today().isoformat(),
                actions_taken=self.actions.get(
                    "1.0", "end").rstrip() or None)
        except ValidationError as exc:
            messagebox.showerror("Complaints", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class EscalateDialog:
    def __init__(self, parent, *, complaint: Complaint) -> None:
        self.complaint = complaint
        self.result: Complaint | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Escalate — #{complaint.complaint_id}")
        self.win.geometry("500x300")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        idx = STAGES.index(complaint.stage)
        choices = list(STAGES[idx + 1:])
        ttk.Label(body, text=f"Current stage: {complaint.stage}").grid(
            row=0, column=0, columnspan=2, sticky="w",
            padx=4, pady=4)
        ttk.Label(body, text="Escalate to").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.to_stage = tk.StringVar(value=choices[0])
        ttk.Combobox(body, textvariable=self.to_stage,
                      values=choices, state="readonly").grid(
            row=1, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Reason").grid(
            row=2, column=0, sticky="nw", padx=4, pady=4)
        self.reason = tk.Text(body, height=6, width=44,
                                 wrap="word")
        self.reason.grid(row=2, column=1, sticky="ew",
                            padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Escalate",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.escalate(
                self.complaint.complaint_id,
                to_stage=self.to_stage.get(),
                reason=self.reason.get("1.0", "end").rstrip()
                or None)
        except ValidationError as exc:
            messagebox.showerror("Complaints", str(exc),
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


__all__ = ["open_complaints_window"]
