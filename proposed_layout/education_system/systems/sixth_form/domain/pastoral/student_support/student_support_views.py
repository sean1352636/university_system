"""Tkinter views for Sixth Form Student Support."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.platform import branding
from education_system.systems.sixth_form.domain.pastoral.student_support import (
    student_support as data,
)
from education_system.systems.sixth_form.domain.pastoral.student_support.student_support import (
    DEFAULT_SOURCE,
    DEFAULT_STATUS,
    DEFAULT_SUPPORT_TYPE,
    PRIORITIES,
    Referral,
    SOURCES,
    STATUSES,
    SUPPORT_TYPES,
    ValidationError,
    priority_label,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Referred":    ("#fff7e6", "#7a5800"),
    "Triaged":     ("#e6f0ff", "#1a3f8c"),
    "In Progress": ("#fff0d6", "#7a5800"),
    "On Hold":     ("#eeeeee", "#555555"),
    "Resolved":    ("#e6f7e6", "#0d6b2a"),
    "Closed":      ("#dddddd", "#444444"),
}


def open_student_support_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Student Support — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    ReferralsTab(nb, scope="open",    label="Open")
    ReferralsTab(nb, scope="urgent",  label="Urgent")
    ReferralsTab(nb, scope="overdue", label="Overdue")
    ReferralsTab(nb, scope="all",     label="All")
    PerStudentTab(nb)
    SummaryTab(nb)


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


class ReferralsTab:
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
        self.f_type = ttk.Combobox(bar, values=("",) + SUPPORT_TYPES,
                                     state="readonly", width=22)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Source:").pack(side="left")
        self.f_source = ttk.Combobox(bar, values=("",) + SOURCES,
                                       state="readonly", width=18)
        self.f_source.current(0)
        self.f_source.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + STATUSES,
                                           state="readonly", width=14)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None
        ttk.Label(bar, text="Min P:").pack(side="left")
        self.f_pri = ttk.Combobox(bar, values=("",) + tuple(str(p)
                                                              for p in PRIORITIES),
                                     state="readonly", width=4)
        self.f_pri.current(0)
        self.f_pri.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Assigned:").pack(side="left")
        self.f_assigned = ttk.Entry(bar, width=12)
        self.f_assigned.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                  padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "referred", "student", "type", "priority",
                "source", "assigned", "status", "target",
                "sessions")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 60, "referred": 90, "student": 100,
                   "type": 170, "priority": 90, "source": 140,
                   "assigned": 130, "status": 110, "target": 110,
                   "sessions": 80}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center" if c in ("id",
                                                          "priority",
                                                          "sessions")
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
        self.tree.tag_configure("urgent", background="#ffe6cc",
                                  foreground="#a04400")
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("View / Edit",   self._edit),
                ("Triage",        self._triage),
                ("Log session",   self._log),
                ("Resolve",       self._resolve),
                ("Close",         self._close),
                ("Change status", self._set_status),
                ("Delete",        self._delete),
                ("Refresh",       self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _clear(self) -> None:
        self.f_student.delete(0, "end")
        self.f_type.current(0)
        self.f_source.current(0)
        self.f_pri.current(0)
        self.f_assigned.delete(0, "end")
        if self.f_status is not None:
            self.f_status.current(0)
        self.refresh()

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_student.get().strip():
            f["student_id"] = self.f_student.get().strip()
        if self.f_type.get():
            f["support_type"] = self.f_type.get()
        if self.f_source.get():
            f["source"] = self.f_source.get()
        if self.f_pri.get():
            f["priority_min"] = int(self.f_pri.get())
        if self.f_assigned.get().strip():
            f["assigned_to_like"] = self.f_assigned.get().strip()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "open":
            f["open_only"] = True
        elif self.scope == "urgent":
            f["urgent_only"] = True
        elif self.scope == "overdue":
            f["overdue_only"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_referrals(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Student Support", str(e),
                                    parent=self.frame)
            return
        for r in rows:
            target = r.target_close_date or "—"
            if r.overdue:
                target = f"OVERDUE ({target})"
            sess = (f"{r.sessions_completed}"
                     + (f"/{r.sessions_planned}"
                          if r.sessions_planned is not None
                          else ""))
            if r.overdue:
                tag = "overdue"
            elif r.is_open and r.priority >= 4:
                tag = "urgent"
            else:
                tag = r.status
            self.tree.insert("", "end", iid=str(r.referral_id),
                              values=(r.referral_id, r.referred_on,
                                       r.student_id,
                                       r.support_type,
                                       (f"{r.priority} "
                                        f"{priority_label(r.priority)[:3]}"),
                                       r.source,
                                       r.assigned_to or "—",
                                       r.status, target, sess),
                              tags=(tag,))
        self.count.config(text=f"{len(rows)} referral(s)")

    def _selected(self) -> Referral | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Student Support",
                                  "Select a referral first.",
                                  parent=self.frame)
            return None
        return data.get_referral(int(sel[0]))

    def _new(self) -> None:
        if ReferralEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        r = self._selected()
        if r and ReferralEditor(self.frame,
                                    referral=r).result is not None:
            self.refresh()

    def _triage(self) -> None:
        r = self._selected()
        if not r:
            return
        if TriageDialog(self.frame,
                            referral=r).result is not None:
            self.refresh()

    def _log(self) -> None:
        r = self._selected()
        if not r:
            return
        if LogSessionDialog(self.frame,
                                referral=r).result is not None:
            self.refresh()

    def _resolve(self) -> None:
        r = self._selected()
        if not r:
            return
        if ResolveDialog(self.frame,
                            referral=r).result is not None:
            self.refresh()

    def _close(self) -> None:
        r = self._selected()
        if not r:
            return
        try:
            data.close_referral(r.referral_id)
        except ValidationError as e:
            messagebox.showerror("Student Support", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        r = self._selected()
        if not r:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES), default=r.status)
        if not new:
            return
        try:
            data.set_status(r.referral_id, new)
        except ValidationError as e:
            messagebox.showerror("Student Support", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        r = self._selected()
        if not r:
            return
        if not messagebox.askyesno(
                "Student Support",
                f"Delete referral #{r.referral_id}?",
                parent=self.frame):
            return
        data.delete_referral(r.referral_id)
        self.refresh()


class PerStudentTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Per Student")
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Student:").pack(side="left")
        self.combo = ttk.Combobox(bar, state="readonly", width=42)
        opts = _student_options()
        self._opts = opts
        self.combo["values"] = [lbl for _, lbl in opts]
        self.combo.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Show",
                    command=self._show).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.config(state="disabled")

    def _show(self) -> None:
        idx = self.combo.current()
        if idx < 0:
            return
        sid = self._opts[idx][0]
        rows = data.referrals_for_student(sid)
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end",
                            f"Support history for {sid}\n"
                            f"{'=' * 60}\n\n"
                            f"Total referrals : {len(rows)}\n\n")
        for r in rows:
            self.text.insert("end",
                                f"#{r.referral_id}  {r.referred_on}  "
                                f"{r.support_type}  P{r.priority}  "
                                f"[{r.status}]\n"
                                f"  Referrer: {r.referrer}  "
                                f"({r.source})\n")
            if r.assigned_to:
                self.text.insert("end",
                                    f"  Assigned: {r.assigned_to}; "
                                    f"sessions {r.sessions_completed}"
                                    + (f"/{r.sessions_planned}"
                                        if r.sessions_planned is not None
                                        else "") + "\n")
            if r.outcome:
                self.text.insert("end",
                                    f"  Outcome : "
                                    f"{r.outcome.splitlines()[0]}\n")
            self.text.insert("end", "\n")
        self.text.config(state="disabled")


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
        self.text.insert("end", "Student Support Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total              : {s.total}\n"
                            f"Open               : {s.open_count}\n"
                            f"Urgent open        : {s.urgent_open}\n"
                            f"Overdue            : {s.overdue}\n"
                            f"Distinct students  : {s.distinct_students}\n"
                            f"Sessions logged    : {s.total_sessions}\n\n")
        self.text.insert("end", "By type:\n")
        for k in SUPPORT_TYPES:
            n = s.by_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<26}: {n}\n")
        self.text.insert("end", "\nBy source:\n")
        for k in SOURCES:
            n = s.by_source.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy priority:\n")
        for p in PRIORITIES:
            n = s.by_priority.get(p, 0)
            if n:
                self.text.insert("end",
                                    f"  {p}  {priority_label(p):<10}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.config(state="disabled")


# ── Editor & dialogs ──────────────────────────────────────────────

class ReferralEditor:
    def __init__(self, parent, *,
                 referral: Referral | None = None) -> None:
        self.referral = referral
        self.result: Referral | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit referral #{referral.referral_id}"
                          if referral else "New referral")
        self.win.geometry("780x780")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if referral:
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

        entry(1, 0, "Referred on*", "referred_on")
        combo(1, 2, "Support type*", "support_type", SUPPORT_TYPES)
        combo(2, 0, "Source*", "source", SOURCES)
        entry(2, 2, "Referrer*", "referrer")
        combo(3, 0, "Priority*", "priority",
                 ("1", "2", "3", "4", "5"))
        combo(3, 2, "Status*", "status", STATUSES)
        entry(4, 0, "Assigned to", "assigned_to")
        entry(4, 2, "Target close", "target_close_date")
        entry(5, 0, "Subject context", "subject_context")
        entry(5, 2, "Closed on", "closed_on")
        entry(6, 0, "Sessions planned", "sessions_planned")
        entry(6, 2, "Sessions completed", "sessions_completed")

        row = 7
        for key, label in (
                ("presenting_issue", "Presenting issue"),
                ("agreed_actions",   "Agreed actions"),
                ("outcome",          "Outcome"),
                ("review_notes",     "Review notes"),
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

        self.vars["referred_on"].set(_dt.date.today().isoformat())
        self.vars["support_type"].set(DEFAULT_SUPPORT_TYPE)
        self.vars["source"].set(DEFAULT_SOURCE)
        self.vars["priority"].set("3")
        self.vars["status"].set(DEFAULT_STATUS)
        self.vars["sessions_completed"].set("0")

    def _load(self) -> None:
        r = self.referral
        assert r is not None
        for i, (sid, _) in enumerate(self._student_opts):
            if sid == r.student_id:
                self.student_combo.current(i)
                break
        for key in ("referred_on", "support_type", "source",
                     "referrer", "status", "assigned_to",
                     "target_close_date", "subject_context",
                     "closed_on"):
            self.vars[key].set(getattr(r, key) or "")
        self.vars["priority"].set(str(r.priority))
        self.vars["sessions_planned"].set(
            str(r.sessions_planned)
            if r.sessions_planned is not None else "")
        self.vars["sessions_completed"].set(
            str(r.sessions_completed))
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(r, k) or "")

    def _save(self) -> None:
        idx = self.student_combo.current()
        if idx < 0:
            messagebox.showerror("Student Support",
                                    "Pick a student.",
                                    parent=self.win)
            return
        payload: dict = {"student_id": self._student_opts[idx][0]}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.referral:
                self.result = data.update_referral(
                    self.referral.referral_id, payload)
            else:
                self.result = data.create_referral(payload)
        except ValidationError as exc:
            messagebox.showerror("Student Support", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class TriageDialog:
    def __init__(self, parent, *, referral: Referral) -> None:
        self.referral = referral
        self.result: Referral | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Triage — #{referral.referral_id}")
        self.win.geometry("440x220")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Assigned to*").grid(
            row=0, column=0, sticky="w", padx=4, pady=6)
        self.assigned = tk.StringVar(value=referral.assigned_to or "")
        ttk.Entry(body, textvariable=self.assigned).grid(
            row=0, column=1, sticky="ew", padx=4, pady=6)
        ttk.Label(body, text="Priority (1-5)").grid(
            row=1, column=0, sticky="w", padx=4, pady=6)
        self.pri = tk.StringVar(value=str(referral.priority))
        ttk.Combobox(body, textvariable=self.pri,
                      values=("1", "2", "3", "4", "5"),
                      state="readonly", width=6).grid(
            row=1, column=1, sticky="w", padx=4, pady=6)
        ttk.Label(body, text="Target close").grid(
            row=2, column=0, sticky="w", padx=4, pady=6)
        self.target = tk.StringVar(
            value=referral.target_close_date or "")
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
            self.result = data.triage(
                self.referral.referral_id,
                assigned_to=self.assigned.get().strip(),
                priority=int(self.pri.get())
                if self.pri.get().isdigit() else None,
                target_close_date=self.target.get().strip()
                or None)
        except ValidationError as exc:
            messagebox.showerror("Student Support", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class LogSessionDialog:
    def __init__(self, parent, *, referral: Referral) -> None:
        self.referral = referral
        self.result: Referral | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Log session — #{referral.referral_id}")
        self.win.geometry("480x280")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Note (optional)").grid(
            row=0, column=0, sticky="nw", padx=4, pady=6)
        self.note = tk.Text(body, height=6, width=44, wrap="word")
        self.note.grid(row=0, column=1, sticky="ew",
                          padx=4, pady=6)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Log",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.log_session(
                self.referral.referral_id,
                note=self.note.get("1.0", "end").rstrip() or None)
        except ValidationError as exc:
            messagebox.showerror("Student Support", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class ResolveDialog:
    def __init__(self, parent, *, referral: Referral) -> None:
        self.referral = referral
        self.result: Referral | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Resolve — #{referral.referral_id}")
        self.win.geometry("520x320")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Outcome*").grid(
            row=0, column=0, sticky="nw", padx=4, pady=6)
        self.outcome = tk.Text(body, height=8, width=48,
                                  wrap="word")
        self.outcome.insert("1.0", referral.outcome or "")
        self.outcome.grid(row=0, column=1, sticky="ew",
                            padx=4, pady=6)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Resolve",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.resolve(
                self.referral.referral_id,
                outcome=self.outcome.get("1.0", "end").rstrip())
        except ValidationError as exc:
            messagebox.showerror("Student Support", str(exc),
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


__all__ = ["open_student_support_window"]
