"""Tkinter views for Sixth Form Quality Assurance."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.shared import branding
from education_system.post_16.sixthform_system.modules.domain.assessment.quality_assurance import (
    quality_assurance as data,
)
from education_system.post_16.sixthform_system.modules.domain.assessment.quality_assurance.quality_assurance import (
    ACTIVITY_TYPES,
    DEFAULT_ACTIVITY_TYPE,
    DEFAULT_FOCUS_AREA,
    DEFAULT_STATUS,
    FOCUS_AREAS,
    JUDGEMENTS,
    QAActivity,
    STATUSES,
    ValidationError,
    judgement_label,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Planned":            ("#eef5ff", "#1a3f8c"),
    "In Progress":        ("#fff7e6", "#7a5800"),
    "Findings Recorded":  ("#e6f0ff", "#1a3f8c"),
    "Actions Set":        ("#fff0d6", "#7a5800"),
    "Action In Progress": ("#fff0d6", "#7a5800"),
    "Closed":             ("#e6f7e6", "#0d6b2a"),
}


def open_quality_assurance_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Quality Assurance — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    QATab(nb, scope="open",            label="Open")
    QATab(nb, scope="actions_open",    label="Actions Outstanding")
    QATab(nb, scope="actions_overdue", label="Actions Overdue")
    QATab(nb, scope="all",             label="All")
    SummaryTab(nb)


class QATab:
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
        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar,
                                     values=("",) + ACTIVITY_TYPES,
                                     state="readonly", width=18)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Focus:").pack(side="left")
        self.f_focus = ttk.Combobox(bar, values=("",) + FOCUS_AREAS,
                                      state="readonly", width=20)
        self.f_focus.current(0)
        self.f_focus.pack(side="left", padx=(2, 8))

        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + STATUSES,
                                           state="readonly", width=18)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None

        ttk.Label(bar, text="Lead:").pack(side="left")
        self.f_lead = ttk.Entry(bar, width=14)
        self.f_lead.pack(side="left", padx=(2, 8))

        ttk.Label(bar, text="Subject:").pack(side="left")
        self.f_subject = ttk.Entry(bar, width=14)
        self.f_subject.pack(side="left", padx=(2, 8))

        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                  padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "date", "type", "title", "lead",
                "focus", "judgement", "status", "action")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 60, "date": 90, "type": 130,
                   "title": 220, "lead": 130, "focus": 170,
                   "judgement": 80, "status": 140, "action": 130}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center" if c in ("id",
                                                          "judgement")
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
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("View / Edit",      self._edit),
                ("Record findings",  self._findings),
                ("Set action",       self._action),
                ("Complete action",  self._complete),
                ("Change status",    self._set_status),
                ("Delete",           self._delete),
                ("Refresh",          self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _clear(self) -> None:
        self.f_type.current(0)
        self.f_focus.current(0)
        self.f_lead.delete(0, "end")
        self.f_subject.delete(0, "end")
        if self.f_status is not None:
            self.f_status.current(0)
        self.refresh()

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_type.get():
            f["activity_type"] = self.f_type.get()
        if self.f_focus.get():
            f["focus_area"] = self.f_focus.get()
        if self.f_lead.get().strip():
            f["lead_like"] = self.f_lead.get().strip()
        if self.f_subject.get().strip():
            f["subject"] = self.f_subject.get().strip()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "open":
            f["open_only"] = True
        elif self.scope == "actions_open":
            f["action_outstanding"] = True
        elif self.scope == "actions_overdue":
            f["action_overdue"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_activities(**self._filters())
        except ValidationError as e:
            messagebox.showerror("QA", str(e), parent=self.frame)
            return
        for a in rows:
            action = "—"
            if a.action_summary:
                if a.action_completed:
                    action = "✓ done"
                elif a.action_overdue:
                    action = f"OVERDUE {a.action_due}"
                else:
                    action = f"open {a.action_due or ''}"
            tag = "overdue" if a.action_overdue else a.status
            self.tree.insert("", "end", iid=str(a.activity_id),
                              values=(a.activity_id,
                                       a.activity_date,
                                       a.activity_type,
                                       a.title,
                                       a.lead,
                                       a.focus_area or "—",
                                       (f"{a.judgement} "
                                        f"{judgement_label(a.judgement)[:3]}"
                                        if a.judgement else "—"),
                                       a.status, action),
                              tags=(tag,))
        self.count.config(text=f"{len(rows)} activity(ies)")

    def _selected(self) -> QAActivity | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("QA",
                                  "Select an activity first.",
                                  parent=self.frame)
            return None
        return data.get_activity(int(sel[0]))

    def _new(self) -> None:
        if QAActivityEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        a = self._selected()
        if a and QAActivityEditor(self.frame,
                                          activity=a).result is not None:
            self.refresh()

    def _findings(self) -> None:
        a = self._selected()
        if not a:
            return
        if FindingsDialog(self.frame,
                              activity=a).result is not None:
            self.refresh()

    def _action(self) -> None:
        a = self._selected()
        if not a:
            return
        if ActionDialog(self.frame,
                            activity=a).result is not None:
            self.refresh()

    def _complete(self) -> None:
        a = self._selected()
        if not a:
            return
        if CompleteActionDialog(self.frame,
                                    activity=a).result is not None:
            self.refresh()

    def _set_status(self) -> None:
        a = self._selected()
        if not a:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES), default=a.status)
        if not new:
            return
        try:
            data.set_status(a.activity_id, new)
        except ValidationError as e:
            messagebox.showerror("QA", str(e), parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        a = self._selected()
        if not a:
            return
        if not messagebox.askyesno("QA",
                                       f"Delete #{a.activity_id}?",
                                       parent=self.frame):
            return
        data.delete_activity(a.activity_id)
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
        self.text.insert("end", "Quality Assurance Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total                 : {s.total}\n"
                            f"Open                  : {s.open_count}\n"
                            f"Actions outstanding   : {s.actions_outstanding}\n"
                            f"Actions overdue       : {s.actions_overdue}\n"
                            f"Average judgement     : "
                            f"{s.average_judgement if s.average_judgement is not None else '—'}\n"
                            f"Distinct leads        : {s.distinct_leads}\n\n")
        self.text.insert("end", "By status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy type:\n")
        for k in ACTIVITY_TYPES:
            n = s.by_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy judgement:\n")
        for j in JUDGEMENTS:
            n = s.by_judgement.get(j, 0)
            if n:
                self.text.insert("end",
                                    f"  {j}  {judgement_label(j):<24}: {n}\n")
        if s.by_focus:
            self.text.insert("end", "\nBy focus area:\n")
            for f, n in s.by_focus.items():
                self.text.insert("end", f"  {f:<24}: {n}\n")
        self.text.config(state="disabled")


# ── Editor ────────────────────────────────────────────────────────

class QAActivityEditor:
    def __init__(self, parent, *,
                 activity: QAActivity | None = None) -> None:
        self.activity = activity
        self.result: QAActivity | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit QA #{activity.activity_id}"
                          if activity else "New QA activity")
        self.win.geometry("780x780")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()
        if activity:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}

        def entry(row, col, label, key, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v, width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        def combo(row, col, label, key, values, width=18):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        entry(0, 0, "Title*", "title", width=46)
        entry(1, 0, "Date* (YYYY-MM-DD)", "activity_date")
        combo(1, 2, "Type*", "activity_type", ACTIVITY_TYPES)
        combo(2, 0, "Focus area", "focus_area",
                 ("",) + FOCUS_AREAS)
        entry(2, 2, "Lead*", "lead")
        entry(3, 0, "Participants", "participants")
        entry(3, 2, "Subject", "subject")
        entry(4, 0, "Department", "department")
        combo(4, 2, "Judgement", "judgement",
                 ("", "1", "2", "3", "4"))
        combo(5, 0, "Status*", "status", STATUSES)

        row = 6
        for key, label in (
                ("strengths",         "Strengths"),
                ("areas_to_develop",  "Areas to develop"),
                ("evidence",          "Evidence"),
                ("action_summary",    "Action summary"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
            t = tk.Text(body, height=2, width=70, wrap="word")
            t.grid(row=row, column=1, columnspan=3,
                     sticky="ew", padx=4, pady=(6, 2))
            self.texts[key] = t
            row += 1

        entry(row, 0, "Action owner", "action_owner"); row_owner = row
        entry(row, 2, "Action due", "action_due"); row += 1
        self.action_done = tk.BooleanVar()
        ttk.Checkbutton(body, text="Action completed",
                         variable=self.action_done).grid(
            row=row, column=0, sticky="w", padx=4, pady=4)
        entry(row, 2, "Impact reviewed on", "impact_reviewed_on")
        row += 1

        ttk.Label(body, text="Impact review").grid(
            row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
        t = tk.Text(body, height=2, width=70, wrap="word")
        t.grid(row=row, column=1, columnspan=3,
                 sticky="ew", padx=4, pady=(6, 2))
        self.texts["impact_review"] = t
        row += 1

        ttk.Label(body, text="Notes").grid(
            row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
        t = tk.Text(body, height=2, width=70, wrap="word")
        t.grid(row=row, column=1, columnspan=3,
                 sticky="ew", padx=4, pady=(6, 2))
        self.texts["notes"] = t

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["activity_date"].set(_dt.date.today().isoformat())
        self.vars["activity_type"].set(DEFAULT_ACTIVITY_TYPE)
        self.vars["focus_area"].set(DEFAULT_FOCUS_AREA)
        self.vars["status"].set(DEFAULT_STATUS)

    def _load(self) -> None:
        a = self.activity
        assert a is not None
        for key in ("title", "activity_date", "activity_type",
                     "focus_area", "lead", "participants",
                     "subject", "department", "status",
                     "action_owner", "action_due",
                     "impact_reviewed_on"):
            v = getattr(a, key) or ""
            self.vars[key].set(str(v))
        self.vars["judgement"].set(
            str(a.judgement) if a.judgement is not None else "")
        self.action_done.set(a.action_completed)
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(a, k) or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        payload["action_completed"] = self.action_done.get()
        try:
            if self.activity:
                self.result = data.update_activity(
                    self.activity.activity_id, payload)
            else:
                self.result = data.create_activity(payload)
        except ValidationError as e:
            messagebox.showerror("QA", str(e), parent=self.win)
            return
        self.win.destroy()


# ── Small workflow dialogs ────────────────────────────────────────

class FindingsDialog:
    def __init__(self, parent, *, activity: QAActivity) -> None:
        self.activity = activity
        self.result: QAActivity | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Record findings — #{activity.activity_id}")
        self.win.geometry("600x540")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build(); self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Judgement").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.j = tk.StringVar(
            value=str(self.activity.judgement)
            if self.activity.judgement else "")
        ttk.Combobox(body, textvariable=self.j,
                      values=("", "1", "2", "3", "4"),
                      state="readonly", width=8).grid(
            row=0, column=1, sticky="w", padx=4, pady=4)
        self.texts: dict[str, tk.Text] = {}
        row = 1
        for k, label in (("strengths", "Strengths"),
                            ("areas", "Areas to develop"),
                            ("evidence", "Evidence")):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=4)
            t = tk.Text(body, height=4, width=50, wrap="word")
            init = (self.activity.strengths if k == "strengths"
                     else self.activity.areas_to_develop
                     if k == "areas" else self.activity.evidence) or ""
            t.insert("1.0", init)
            t.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
            self.texts[k] = t
            row += 1
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

    def _save(self) -> None:
        j_raw = self.j.get().strip()
        j = int(j_raw) if j_raw.isdigit() else None
        try:
            self.result = data.record_findings(
                self.activity.activity_id,
                strengths=self.texts["strengths"].get("1.0", "end").rstrip(),
                areas=self.texts["areas"].get("1.0", "end").rstrip(),
                evidence=self.texts["evidence"].get("1.0", "end").rstrip(),
                judgement=j,
            )
        except ValidationError as e:
            messagebox.showerror("QA", str(e), parent=self.win)
            return
        self.win.destroy()


class ActionDialog:
    def __init__(self, parent, *, activity: QAActivity) -> None:
        self.activity = activity
        self.result: QAActivity | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Set action — #{activity.activity_id}")
        self.win.geometry("520x320")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Summary*").grid(
            row=0, column=0, sticky="nw", padx=4, pady=4)
        self.summary = tk.Text(body, height=4, width=46, wrap="word")
        self.summary.insert("1.0", activity.action_summary or "")
        self.summary.grid(row=0, column=1, sticky="ew",
                            padx=4, pady=4)
        ttk.Label(body, text="Owner*").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.owner = tk.StringVar(value=activity.action_owner or "")
        ttk.Entry(body, textvariable=self.owner).grid(
            row=1, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Due (YYYY-MM-DD)").grid(
            row=2, column=0, sticky="w", padx=4, pady=4)
        self.due = tk.StringVar(value=activity.action_due or "")
        ttk.Entry(body, textvariable=self.due, width=14).grid(
            row=2, column=1, sticky="w", padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.set_action(
                self.activity.activity_id,
                summary=self.summary.get("1.0", "end").rstrip(),
                owner=self.owner.get().strip(),
                due=self.due.get().strip() or None)
        except ValidationError as e:
            messagebox.showerror("QA", str(e), parent=self.win)
            return
        self.win.destroy()


class CompleteActionDialog:
    def __init__(self, parent, *, activity: QAActivity) -> None:
        self.activity = activity
        self.result: QAActivity | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Complete action — #{activity.activity_id}")
        self.win.geometry("520x340")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Impact review").grid(
            row=0, column=0, sticky="nw", padx=4, pady=4)
        self.impact = tk.Text(body, height=6, width=46, wrap="word")
        self.impact.insert("1.0", activity.impact_review or "")
        self.impact.grid(row=0, column=1, sticky="ew",
                            padx=4, pady=4)
        ttk.Label(body, text="Reviewed on").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.when = tk.StringVar(
            value=activity.impact_reviewed_on
            or _dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when, width=14).grid(
            row=1, column=1, sticky="w", padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.complete_action(
                self.activity.activity_id,
                impact=self.impact.get("1.0", "end").rstrip(),
                reviewed_on=self.when.get().strip()
                or _dt.date.today().isoformat())
        except ValidationError as e:
            messagebox.showerror("QA", str(e), parent=self.win)
            return
        self.win.destroy()


# ── Helpers ────────────────────────────────────────────────────────

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


__all__ = ["open_quality_assurance_window"]
