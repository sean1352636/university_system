"""Tkinter views for Secondary School Council."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.platform import branding
from education_system.systems.secondary.domain.pastoral.school_council import (
    school_council as data,
)
from education_system.systems.secondary.domain.pastoral.school_council.school_council import (
    DEFAULT_MEETING_STATUS,
    DEFAULT_MEETING_TYPE,
    DEFAULT_MEMBER_STATUS,
    DEFAULT_MOTION_OUTCOME,
    DEFAULT_ROLE,
    MEETING_STATUSES,
    MEETING_TYPES,
    MEMBER_STATUSES,
    MOTION_OUTCOMES,
    Meeting,
    Member,
    Motion,
    ROLES,
    ValidationError,
)
from education_system.systems.secondary.domain.pastoral import _pupils_bridge as student_data

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_MEMBER_TAGS = {
    "Active":     ("#e6f7e6", "#0d6b2a"),
    "Resigned":   ("#ffe6e6", "#8c0d0d"),
    "Departed":   ("#dddddd", "#444444"),
    "Suspended":  ("#fff0d6", "#7a5800"),
    "Term Ended": ("#eeeeee", "#444444"),
}
_MEETING_TAGS = {
    "Scheduled": ("#fff7e6", "#7a5800"),
    "Confirmed": ("#e6f0ff", "#1a3f8c"),
    "Completed": ("#e6f7e6", "#0d6b2a"),
    "Cancelled": ("#ffd1d1", "#8c0d0d"),
}
_MOTION_TAGS = {
    "Pending":   ("#fff7e6", "#7a5800"),
    "Passed":    ("#e6f7e6", "#0d6b2a"),
    "Failed":    ("#ffd1d1", "#8c0d0d"),
    "Withdrawn": ("#eeeeee", "#444444"),
    "Deferred":  ("#e6e6ff", "#3a3a8c"),
}


def open_school_council_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"School Council — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    MembersTab(nb)
    MeetingsTab(nb)
    SummaryTab(nb)


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


# ── Members tab ──────────────────────────────────────────────

class MembersTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Members")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Role:").pack(side="left")
        self.f_role = ttk.Combobox(bar, values=("",) + ROLES,
                                     state="readonly", width=20)
        self.f_role.current(0)
        self.f_role.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar,
                                       values=("",) + MEMBER_STATUSES,
                                       state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))
        self.active_only = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Active only",
                         variable=self.active_only,
                         command=self.refresh).pack(side="left",
                                                        padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "role", "term_start",
                "term_end", "elected_on", "status", "portfolio")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "student": 110, "role": 150,
                   "term_start": 110, "term_end": 110,
                   "elected_on": 110, "status": 110,
                   "portfolio": 180}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c == "id" else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _MEMBER_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("Edit",           self._edit),
                ("End term",       self._end_term),
                ("Change status",  self._set_status),
                ("Delete",         self._delete),
                ("Refresh",        self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_role.get():
            f["role"] = self.f_role.get()
        if self.f_status.get():
            f["status"] = self.f_status.get()
        if self.active_only.get() and not f.get("status"):
            f["active_only"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        rows = data.list_members(**self._filters())
        for m in rows:
            self.tree.insert(
                "", "end", iid=str(m.member_id),
                values=(m.member_id, m.student_id, m.role,
                         m.term_start, m.term_end or "—",
                         m.elected_on or "—", m.status,
                         m.portfolio or "—"),
                tags=(m.status,))
        self.count.config(text=f"{len(rows)} member(s)")

    def _selected(self) -> Member | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("School Council",
                                  "Select a member first.",
                                  parent=self.frame)
            return None
        return data.get_member(int(sel[0]))

    def _new(self) -> None:
        if MemberEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        m = self._selected()
        if m and MemberEditor(self.frame,
                                    member=m).result is not None:
            self.refresh()

    def _end_term(self) -> None:
        m = self._selected()
        if not m:
            return
        when = _prompt_text(self.frame, "Ended on (YYYY-MM-DD)",
                              initial=_dt.date.today().isoformat())
        if not when:
            return
        try:
            data.end_term(m.member_id, ended_on=when)
        except ValidationError as exc:
            messagebox.showerror("School Council", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        m = self._selected()
        if not m:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(MEMBER_STATUSES),
                                default=m.status)
        if not new:
            return
        try:
            data.set_member_status(m.member_id, new)
        except ValidationError as exc:
            messagebox.showerror("School Council", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        m = self._selected()
        if not m:
            return
        if not messagebox.askyesno(
                "School Council",
                f"Delete member #{m.member_id}?",
                parent=self.frame):
            return
        data.delete_member(m.member_id)
        self.refresh()


# ── Meetings tab ──────────────────────────────────────────

class MeetingsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Meetings")
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
        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(bar,
                                     values=("",) + MEETING_TYPES,
                                     state="readonly", width=18)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Status:").pack(side="left")
        self.f_status = ttk.Combobox(bar,
                                       values=("",) + MEETING_STATUSES,
                                       state="readonly", width=14)
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(2, 8))
        self.upcoming_only = tk.BooleanVar()
        ttk.Checkbutton(bar, text="Upcoming only",
                         variable=self.upcoming_only,
                         command=self.refresh).pack(side="left",
                                                        padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="New meeting",
                    command=self._new).pack(side="left",
                                                padx=(16, 0))

        table_frame = ttk.Frame(self.top)
        table_frame.pack(fill="both", expand=True)
        cols = ("id", "date", "time", "type", "title",
                "chair", "status", "motions")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "date": 90, "time": 60,
                   "type": 140, "title": 280,
                   "chair": 130, "status": 110, "motions": 80}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "motions")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _MEETING_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.bind("<<TreeviewSelect>>",
                         lambda _e: self._refresh_motions())
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.top)
        actions.pack(fill="x", pady=(4, 0))
        for label, cmd in (
                ("Edit",     self._edit),
                ("Confirm",  self._confirm),
                ("Complete", self._complete),
                ("Cancel",   self._cancel),
                ("Delete",   self._delete),
                ("Refresh",  self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _build_bottom(self) -> None:
        bar = ttk.Frame(self.bottom)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="Motions").pack(side="left")
        ttk.Button(bar, text="Add",
                    command=self._add_motion).pack(side="right",
                                                       padx=4)
        ttk.Button(bar, text="Record vote",
                    command=self._record_vote).pack(side="right",
                                                       padx=4)
        ttk.Button(bar, text="Edit",
                    command=self._edit_motion).pack(side="right",
                                                       padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_motion).pack(side="right",
                                                          padx=4)

        table_frame = ttk.Frame(self.bottom)
        table_frame.pack(fill="both", expand=True)
        mcols = ("id", "n", "title", "proposer", "seconder",
                   "for", "against", "abstain", "outcome")
        self.mtree = ttk.Treeview(table_frame, columns=mcols,
                                       show="headings",
                                       selectmode="browse")
        mwidths = {"id": 50, "n": 40, "title": 280,
                     "proposer": 110, "seconder": 110,
                     "for": 60, "against": 60,
                     "abstain": 60, "outcome": 100}
        for c in mcols:
            self.mtree.heading(c,
                                   text=c.replace("_", " ").title())
            self.mtree.column(c, width=mwidths[c],
                                  anchor=("center"
                                           if c in ("id", "n",
                                                      "for",
                                                      "against",
                                                      "abstain")
                                           else "w"))
        mvsb = ttk.Scrollbar(table_frame, orient="vertical",
                                command=self.mtree.yview)
        self.mtree.configure(yscrollcommand=mvsb.set)
        self.mtree.pack(side="left", fill="both", expand=True)
        mvsb.pack(side="right", fill="y")
        for outcome, (bg, fg) in _MOTION_TAGS.items():
            self.mtree.tag_configure(outcome, background=bg,
                                          foreground=fg)
        self.mtree.bind("<Double-Button-1>",
                            lambda _e: self._edit_motion())

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_type.get():
            f["meeting_type"] = self.f_type.get()
        if self.f_status.get():
            f["status"] = self.f_status.get()
        if self.upcoming_only.get():
            f["upcoming_only"] = True
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        rows = data.list_meetings(**self._filters())
        for m in rows:
            motion_count = len(
                data.list_motions(meeting_id=m.meeting_id))
            self.tree.insert(
                "", "end", iid=str(m.meeting_id),
                values=(m.meeting_id, m.meeting_date,
                         m.meeting_time or "—",
                         m.meeting_type, m.title,
                         m.chair or "—", m.status,
                         motion_count),
                tags=(m.status,))
        self.count.config(text=f"{len(rows)} meeting(s)")
        self._refresh_motions()

    def _selected(self) -> Meeting | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("School Council",
                                  "Select a meeting first.",
                                  parent=self.frame)
            return None
        return data.get_meeting(int(sel[0]))

    def _refresh_motions(self) -> None:
        for iid in self.mtree.get_children():
            self.mtree.delete(iid)
        sel = self.tree.selection()
        if not sel:
            return
        mid = int(sel[0])
        for mo in data.list_motions(meeting_id=mid):
            self.mtree.insert(
                "", "end", iid=str(mo.motion_id),
                values=(mo.motion_id, mo.motion_number,
                         mo.title, mo.proposer or "—",
                         mo.seconder or "—",
                         mo.votes_for, mo.votes_against,
                         mo.votes_abstain, mo.outcome),
                tags=(mo.outcome,))

    def _selected_motion(self) -> Motion | None:
        sel = self.mtree.selection()
        if not sel:
            return None
        return data.get_motion(int(sel[0]))

    def _new(self) -> None:
        if MeetingEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        m = self._selected()
        if m and MeetingEditor(self.frame,
                                     meeting=m).result is not None:
            self.refresh()

    def _confirm(self) -> None:
        m = self._selected()
        if not m:
            return
        try:
            data.confirm_meeting(m.meeting_id)
        except ValidationError as exc:
            messagebox.showerror("School Council", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _complete(self) -> None:
        m = self._selected()
        if not m:
            return
        if CompleteMeetingDialog(
                self.frame, meeting=m).result is not None:
            self.refresh()

    def _cancel(self) -> None:
        m = self._selected()
        if not m:
            return
        try:
            data.cancel_meeting(m.meeting_id)
        except ValidationError as exc:
            messagebox.showerror("School Council", str(exc),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        m = self._selected()
        if not m:
            return
        if not messagebox.askyesno(
                "School Council",
                f"Delete meeting #{m.meeting_id} "
                "and all motions?", parent=self.frame):
            return
        data.delete_meeting(m.meeting_id)
        self.refresh()

    def _add_motion(self) -> None:
        m = self._selected()
        if not m:
            return
        if MotionEditor(
                self.frame,
                meeting_id=m.meeting_id).result is not None:
            self._refresh_motions()
            self.refresh()

    def _edit_motion(self) -> None:
        mo = self._selected_motion()
        if not mo:
            messagebox.showinfo("School Council",
                                  "Select a motion first.",
                                  parent=self.frame)
            return
        if MotionEditor(self.frame,
                            meeting_id=mo.meeting_id,
                            motion=mo).result is not None:
            self._refresh_motions()
            self.refresh()

    def _record_vote(self) -> None:
        mo = self._selected_motion()
        if not mo:
            messagebox.showinfo("School Council",
                                  "Select a motion first.",
                                  parent=self.frame)
            return
        if VoteDialog(self.frame,
                          motion=mo).result is not None:
            self._refresh_motions()

    def _delete_motion(self) -> None:
        mo = self._selected_motion()
        if not mo:
            return
        if not messagebox.askyesno(
                "School Council",
                f"Delete motion #{mo.motion_id}?",
                parent=self.frame):
            return
        data.delete_motion(mo.motion_id)
        self._refresh_motions()
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
        self.text.insert("end", "School Council Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total members        : {s.total_members}\n"
                            f"Active members       : {s.active_members}\n"
                            f"Total meetings       : {s.total_meetings}\n"
                            f"Completed meetings   : {s.completed_meetings}\n"
                            f"Total motions        : {s.total_motions}\n"
                            f"Motions passed       : {s.motions_passed}\n"
                            f"Motions failed       : {s.motions_failed}\n"
                            f"Motions pending      : {s.motions_pending}\n\n")
        self.text.insert("end", "By role:\n")
        for k in ROLES:
            n = s.by_role.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<18}: {n}\n")
        self.text.insert("end", "\nBy meeting type:\n")
        for k in MEETING_TYPES:
            n = s.by_meeting_type.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<18}: {n}\n")
        self.text.insert("end", "\nBy motion outcome:\n")
        for k in MOTION_OUTCOMES:
            n = s.by_outcome.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<12}: {n}\n")
        self.text.config(state="disabled")


# ── Editors ──────────────────────────────────────────────────

class MemberEditor:
    def __init__(self, parent, *,
                 member: Member | None = None) -> None:
        self.member = member
        self.result: Member | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit member #{member.member_id}"
                          if member else "New member")
        self.win.geometry("620x520")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if member:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        self.vars: dict[str, tk.Variable] = {}

        ttk.Label(body, text="Student*").grid(
            row=0, column=0, sticky="w", padx=4, pady=2)
        self.student_combo = ttk.Combobox(body, state="readonly",
                                              width=42)
        opts = _student_options()
        self._student_opts = opts
        self.student_combo["values"] = [lbl for _, lbl in opts]
        self.student_combo.grid(row=0, column=1, sticky="ew",
                                  padx=4, pady=2)

        def row_entry(row, label, key):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Entry(body, textvariable=v).grid(
                row=row, column=1, sticky="ew", padx=4, pady=2)

        def row_combo(row, label, key, values):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly").grid(
                row=row, column=1, sticky="ew", padx=4, pady=2)

        row_combo(1, "Role*", "role", ROLES)
        row_entry(2, "Term start*", "term_start")
        row_entry(3, "Term end", "term_end")
        row_entry(4, "Elected on", "elected_on")
        row_combo(5, "Status*", "status", MEMBER_STATUSES)
        row_entry(6, "Portfolio", "portfolio")
        ttk.Label(body, text="Notes").grid(
            row=7, column=0, sticky="nw", padx=4, pady=4)
        self.notes = tk.Text(body, height=6, wrap="word")
        self.notes.grid(row=7, column=1, sticky="ew",
                          padx=4, pady=4)

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")

        self.vars["role"].set(DEFAULT_ROLE)
        self.vars["term_start"].set(_dt.date.today().isoformat())
        self.vars["status"].set(DEFAULT_MEMBER_STATUS)

    def _load(self) -> None:
        m = self.member
        assert m is not None
        for i, (sid, _) in enumerate(self._student_opts):
            if sid == m.student_id:
                self.student_combo.current(i)
                break
        for key in ("role", "term_start", "term_end",
                     "elected_on", "status", "portfolio"):
            self.vars[key].set(getattr(m, key) or "")
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", m.notes or "")

    def _save(self) -> None:
        idx = self.student_combo.current()
        if idx < 0:
            messagebox.showerror("School Council",
                                    "Pick a student.",
                                    parent=self.win)
            return
        payload: dict = {
            "student_id": self._student_opts[idx][0],
            "notes": self.notes.get("1.0", "end").rstrip()
            or None,
        }
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        try:
            if self.member:
                self.result = data.update_member(
                    self.member.member_id, payload)
            else:
                self.result = data.create_member(payload)
        except ValidationError as exc:
            messagebox.showerror("School Council", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class MeetingEditor:
    def __init__(self, parent, *,
                 meeting: Meeting | None = None) -> None:
        self.meeting = meeting
        self.result: Meeting | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit meeting #{meeting.meeting_id}"
                          if meeting else "New meeting")
        self.win.geometry("780x780")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if meeting:
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

        def combo(row, col, label, key, values, width=22):
            ttk.Label(body, text=label).grid(
                row=row, column=col, sticky="w", padx=4, pady=2)
            v = tk.StringVar()
            self.vars[key] = v
            ttk.Combobox(body, textvariable=v, values=values,
                          state="readonly", width=width).grid(
                row=row, column=col + 1, sticky="ew", padx=4, pady=2)

        entry(0, 0, "Title*", "title", width=48)
        entry(1, 0, "Date*", "meeting_date")
        entry(1, 2, "Time", "meeting_time")
        combo(2, 0, "Type*", "meeting_type", MEETING_TYPES)
        combo(2, 2, "Status*", "status", MEETING_STATUSES)
        entry(3, 0, "Location", "location")
        entry(3, 2, "Next meeting on", "next_meeting_on")
        entry(4, 0, "Chair", "chair")
        entry(4, 2, "Secretary", "secretary")

        row = 5
        for key, label in (
                ("attendees", "Attendees"),
                ("apologies", "Apologies"),
                ("agenda",    "Agenda"),
                ("minutes",   "Minutes"),
                ("decisions", "Decisions"),
                ("actions",   "Actions"),
                ("notes",     "Notes"),
        ):
            ttk.Label(body, text=label).grid(
                row=row, column=0, sticky="nw", padx=4, pady=(6, 2))
            t = tk.Text(body, height=2, width=70, wrap="word")
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

        now = _dt.datetime.now()
        self.vars["meeting_date"].set(
            _dt.date.today().isoformat())
        self.vars["meeting_time"].set(now.strftime("%H:%M"))
        self.vars["meeting_type"].set(DEFAULT_MEETING_TYPE)
        self.vars["status"].set(DEFAULT_MEETING_STATUS)

    def _load(self) -> None:
        m = self.meeting
        assert m is not None
        for key in ("title", "meeting_date", "meeting_time",
                     "meeting_type", "status", "location",
                     "chair", "secretary", "next_meeting_on"):
            self.vars[key].set(getattr(m, key) or "")
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(m, k) or "")

    def _save(self) -> None:
        payload: dict = {}
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.meeting:
                self.result = data.update_meeting(
                    self.meeting.meeting_id, payload)
            else:
                self.result = data.create_meeting(payload)
        except ValidationError as exc:
            messagebox.showerror("School Council", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class CompleteMeetingDialog:
    def __init__(self, parent, *, meeting: Meeting) -> None:
        self.meeting = meeting
        self.result: Meeting | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Complete — #{meeting.meeting_id}")
        self.win.geometry("560x520")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        self.texts: dict[str, tk.Text] = {}
        for i, (key, label) in enumerate((
                ("minutes",   "Minutes"),
                ("decisions", "Decisions"),
                ("actions",   "Actions"),
        )):
            ttk.Label(body, text=label).grid(
                row=i, column=0, sticky="nw", padx=4, pady=4)
            t = tk.Text(body, height=5, width=52, wrap="word")
            t.insert("1.0", getattr(meeting, key) or "")
            t.grid(row=i, column=1, sticky="ew",
                     padx=4, pady=4)
            self.texts[key] = t
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Complete",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            self.result = data.complete_meeting(
                self.meeting.meeting_id,
                minutes=self.texts["minutes"].get(
                    "1.0", "end").rstrip() or None,
                decisions=self.texts["decisions"].get(
                    "1.0", "end").rstrip() or None,
                actions=self.texts["actions"].get(
                    "1.0", "end").rstrip() or None)
        except ValidationError as exc:
            messagebox.showerror("School Council", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class MotionEditor:
    def __init__(self, parent, *,
                 meeting_id: int,
                 motion: Motion | None = None) -> None:
        self.meeting_id = meeting_id
        self.motion = motion
        self.result: Motion | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit motion #{motion.motion_id}"
                          if motion else "New motion")
        self.win.geometry("560x520")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Title*").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.title = tk.StringVar()
        ttk.Entry(body, textvariable=self.title,
                    width=48).grid(
            row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Proposer").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.proposer = tk.StringVar()
        ttk.Entry(body, textvariable=self.proposer).grid(
            row=1, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Seconder").grid(
            row=2, column=0, sticky="w", padx=4, pady=4)
        self.seconder = tk.StringVar()
        ttk.Entry(body, textvariable=self.seconder).grid(
            row=2, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Outcome").grid(
            row=3, column=0, sticky="w", padx=4, pady=4)
        self.outcome = tk.StringVar(value=DEFAULT_MOTION_OUTCOME)
        ttk.Combobox(body, textvariable=self.outcome,
                      values=MOTION_OUTCOMES,
                      state="readonly").grid(
            row=3, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(body, text="Description").grid(
            row=4, column=0, sticky="nw", padx=4, pady=4)
        self.desc = tk.Text(body, height=8, width=48,
                                wrap="word")
        self.desc.grid(row=4, column=1, sticky="ew",
                          padx=4, pady=4)

        if motion:
            self.title.set(motion.title)
            self.proposer.set(motion.proposer or "")
            self.seconder.set(motion.seconder or "")
            self.outcome.set(motion.outcome)
            self.desc.insert("1.0", motion.description or "")

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        payload = {
            "title": self.title.get().strip(),
            "proposer": self.proposer.get().strip() or None,
            "seconder": self.seconder.get().strip() or None,
            "description": self.desc.get("1.0",
                                              "end").rstrip() or None,
            "outcome": self.outcome.get(),
        }
        try:
            if self.motion:
                payload.update({
                    "votes_for": self.motion.votes_for,
                    "votes_against": self.motion.votes_against,
                    "votes_abstain": self.motion.votes_abstain,
                    "decided_on": self.motion.decided_on,
                    "notes": self.motion.notes,
                })
                self.result = data.update_motion(
                    self.motion.motion_id, payload)
            else:
                self.result = data.add_motion(
                    self.meeting_id, payload)
        except ValidationError as exc:
            messagebox.showerror("School Council", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class VoteDialog:
    def __init__(self, parent, *, motion: Motion) -> None:
        self.motion = motion
        self.result: Motion | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Vote — M{motion.motion_number}")
        self.win.geometry("360x240")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text=motion.title, wraplength=320,
                   font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w",
            padx=4, pady=4)
        self.f_for = tk.StringVar(value=str(motion.votes_for))
        self.f_against = tk.StringVar(
            value=str(motion.votes_against))
        self.f_abs = tk.StringVar(
            value=str(motion.votes_abstain))
        for i, (label, var) in enumerate((
                ("Votes for*",     self.f_for),
                ("Votes against*", self.f_against),
                ("Votes abstain",  self.f_abs),
        )):
            ttk.Label(body, text=label).grid(
                row=i + 1, column=0, sticky="w", padx=4, pady=4)
            ttk.Entry(body, textvariable=var, width=8).grid(
                row=i + 1, column=1, sticky="w",
                padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Record",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            f = int(self.f_for.get())
            a = int(self.f_against.get())
            ab = int(self.f_abs.get() or 0)
        except ValueError:
            messagebox.showerror("School Council",
                                    "Votes must be integers.",
                                    parent=self.win)
            return
        try:
            self.result = data.record_vote(
                self.motion.motion_id,
                votes_for=f, votes_against=a,
                votes_abstain=ab)
        except ValidationError as exc:
            messagebox.showerror("School Council", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


# ── Helpers ───────────────────────────────────────────────

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


__all__ = ["open_school_council_window"]
