"""Tkinter views for Sixth Form Peer Mentoring."""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.shared import branding
from education_system.post_16.sixthform_system.modules.domain.pastoral.peer_mentoring import (
    peer_mentoring as data,
)
from education_system.post_16.sixthform_system.modules.domain.pastoral.peer_mentoring.peer_mentoring import (
    DEFAULT_FREQUENCY,
    DEFAULT_PROGRAMME,
    DEFAULT_STATUS,
    FREQUENCIES,
    PROGRAMMES,
    Pairing,
    STATUSES,
    Session,
    ValidationError,
)
from education_system.post_16.sixthform_system.modules.domain.students.students import (
    students as student_data,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_STATUS_TAGS = {
    "Pending Match": ("#fff7e6", "#7a5800"),
    "Active":        ("#e6f7e6", "#0d6b2a"),
    "Paused":        ("#eeeeee", "#555555"),
    "Completed":     ("#e6e6ff", "#3a3a8c"),
    "Withdrawn":     ("#ffd1d1", "#8c0d0d"),
    "Archived":      ("#dddddd", "#444444"),
}


def open_peer_mentoring_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Peer Mentoring — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    PairingsTab(nb, scope="active",  label="Active")
    PairingsTab(nb, scope="open",    label="Open")
    PairingsTab(nb, scope="pending", label="Pending Match")
    PairingsTab(nb, scope="all",     label="All")
    PerStudentTab(nb)
    SummaryTab(nb)


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


class PairingsTab:
    def __init__(self, nb: ttk.Notebook, *,
                 scope: str, label: str) -> None:
        self.scope = scope
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text=label)
        # Paned: list above, sessions panel below
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
        ttk.Label(bar, text="Programme:").pack(side="left")
        self.f_prog = ttk.Combobox(bar, values=("",) + PROGRAMMES,
                                     state="readonly", width=22)
        self.f_prog.current(0)
        self.f_prog.pack(side="left", padx=(2, 8))
        if self.scope == "all":
            ttk.Label(bar, text="Status:").pack(side="left")
            self.f_status = ttk.Combobox(bar,
                                           values=("",) + STATUSES,
                                           state="readonly", width=14)
            self.f_status.current(0)
            self.f_status.pack(side="left", padx=(2, 8))
        else:
            self.f_status = None
        ttk.Label(bar, text="Mentor id:").pack(side="left")
        self.f_mentor = ttk.Entry(bar, width=10)
        self.f_mentor.pack(side="left", padx=(2, 4))
        ttk.Label(bar, text="Mentee id:").pack(side="left")
        self.f_mentee = ttk.Entry(bar, width=10)
        self.f_mentee.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Coord:").pack(side="left")
        self.f_coord = ttk.Entry(bar, width=12)
        self.f_coord.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left",
                                                  padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New pairing",
                    command=self._new).pack(side="left",
                                                padx=(16, 0))

        table_frame = ttk.Frame(self.top)
        table_frame.pack(fill="both", expand=True)
        cols = ("id", "start", "programme", "mentor", "mentee",
                "freq", "coordinator", "status", "sessions")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "start": 90, "programme": 180,
                   "mentor": 100, "mentee": 100, "freq": 100,
                   "coordinator": 130, "status": 120,
                   "sessions": 110}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center"
                                       if c in ("id", "sessions")
                                       else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for status, (bg, fg) in _STATUS_TAGS.items():
            self.tree.tag_configure(status, background=bg,
                                       foreground=fg)
        self.tree.bind("<<TreeviewSelect>>",
                         lambda _e: self._refresh_sessions())
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._edit())

        actions = ttk.Frame(self.top)
        actions.pack(fill="x", pady=(4, 0))
        for label, cmd in (
                ("View / Edit",   self._edit),
                ("Activate",      self._activate),
                ("Pause",         self._pause),
                ("Complete",      self._complete),
                ("Withdraw",      self._withdraw),
                ("Change status", self._set_status),
                ("Delete",        self._delete),
                ("Refresh",       self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _build_bottom(self) -> None:
        bar = ttk.Frame(self.bottom)
        bar.pack(fill="x", pady=(0, 4))
        self.session_lbl = ttk.Label(bar, text="Sessions: —")
        self.session_lbl.pack(side="left")
        ttk.Button(bar, text="Add session",
                    command=self._add_session).pack(side="right",
                                                       padx=4)
        ttk.Button(bar, text="Edit session",
                    command=self._edit_session).pack(side="right",
                                                        padx=4)
        ttk.Button(bar, text="Delete session",
                    command=self._delete_session).pack(side="right",
                                                          padx=4)

        table_frame = ttk.Frame(self.bottom)
        table_frame.pack(fill="both", expand=True)
        cols = ("id", "date", "mins", "attended", "focus", "notes")
        self.sess_tree = ttk.Treeview(table_frame, columns=cols,
                                          show="headings",
                                          selectmode="browse")
        widths = {"id": 50, "date": 90, "mins": 60,
                   "attended": 80, "focus": 200, "notes": 320}
        for c in cols:
            self.sess_tree.heading(c,
                                       text=c.replace("_", " ").title())
            self.sess_tree.column(c, width=widths[c],
                                      anchor=("center"
                                               if c in ("id", "mins",
                                                          "attended")
                                               else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.sess_tree.yview)
        self.sess_tree.configure(yscrollcommand=vsb.set)
        self.sess_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.sess_tree.bind("<Double-Button-1>",
                                lambda _e: self._edit_session())

    def _clear(self) -> None:
        self.f_prog.current(0)
        self.f_mentor.delete(0, "end")
        self.f_mentee.delete(0, "end")
        self.f_coord.delete(0, "end")
        if self.f_status is not None:
            self.f_status.current(0)
        self.refresh()

    def _filters(self) -> dict:
        f: dict = {}
        if self.f_prog.get():
            f["programme"] = self.f_prog.get()
        if self.f_mentor.get().strip():
            f["mentor_id"] = self.f_mentor.get().strip()
        if self.f_mentee.get().strip():
            f["mentee_id"] = self.f_mentee.get().strip()
        if self.f_coord.get().strip():
            f["coordinator_like"] = self.f_coord.get().strip()
        if self.f_status is not None and self.f_status.get():
            f["status"] = self.f_status.get()
        if self.scope == "active":
            f["active_only"] = True
        elif self.scope == "open":
            f["open_only"] = True
        elif self.scope == "pending":
            f["status"] = "Pending Match"
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_pairings(**self._filters())
        except ValidationError as e:
            messagebox.showerror("Peer Mentoring", str(e),
                                    parent=self.frame)
            return
        for p in rows:
            stats = data.pairing_session_stats(p.pairing_id)
            sess = (f"{stats['attended']}/{stats['total']}  "
                     f"({stats['total_hours']}h)")
            self.tree.insert("", "end", iid=str(p.pairing_id),
                              values=(p.pairing_id, p.start_date,
                                       p.programme, p.mentor_id,
                                       p.mentee_id, p.frequency,
                                       p.coordinator or "—",
                                       p.status, sess),
                              tags=(p.status,))
        self.count.config(text=f"{len(rows)} pairing(s)")
        self._refresh_sessions()

    def _selected(self) -> Pairing | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Peer Mentoring",
                                  "Select a pairing first.",
                                  parent=self.frame)
            return None
        return data.get_pairing(int(sel[0]))

    def _refresh_sessions(self) -> None:
        for iid in self.sess_tree.get_children():
            self.sess_tree.delete(iid)
        sel = self.tree.selection()
        if not sel:
            self.session_lbl.config(text="Sessions: —")
            return
        pid = int(sel[0])
        rows = data.list_sessions(pid)
        stats = data.pairing_session_stats(pid)
        self.session_lbl.config(
            text=(f"Sessions for #{pid}: "
                  f"{stats['attended']} attended / "
                  f"{stats['total']} logged  "
                  f"({stats['total_hours']}h)"))
        for s in rows:
            note = (s.notes.splitlines()[0]
                     if s.notes else "")
            self.sess_tree.insert(
                "", "end", iid=str(s.session_id),
                values=(s.session_id, s.session_date,
                         s.duration_minutes,
                         "yes" if s.attended else "no",
                         s.focus or "—", note))

    def _new(self) -> None:
        if PairingEditor(self.frame).result is not None:
            self.refresh()

    def _edit(self) -> None:
        p = self._selected()
        if p and PairingEditor(self.frame,
                                    pairing=p).result is not None:
            self.refresh()

    def _activate(self) -> None:
        p = self._selected()
        if not p:
            return
        try:
            data.activate(p.pairing_id)
        except ValidationError as e:
            messagebox.showerror("Peer Mentoring", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _pause(self) -> None:
        p = self._selected()
        if not p:
            return
        try:
            data.pause(p.pairing_id)
        except ValidationError as e:
            messagebox.showerror("Peer Mentoring", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _complete(self) -> None:
        p = self._selected()
        if not p:
            return
        if CompleteDialog(self.frame,
                              pairing=p).result is not None:
            self.refresh()

    def _withdraw(self) -> None:
        p = self._selected()
        if not p:
            return
        reason = _prompt_text(self.frame, "Withdrawal reason")
        if reason is None:
            return
        try:
            data.withdraw(p.pairing_id, reason=reason or None)
        except ValidationError as e:
            messagebox.showerror("Peer Mentoring", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _set_status(self) -> None:
        p = self._selected()
        if not p:
            return
        new = _prompt_choice(self.frame, "New status",
                                list(STATUSES), default=p.status)
        if not new:
            return
        try:
            data.set_status(p.pairing_id, new)
        except ValidationError as e:
            messagebox.showerror("Peer Mentoring", str(e),
                                    parent=self.frame)
            return
        self.refresh()

    def _delete(self) -> None:
        p = self._selected()
        if not p:
            return
        if not messagebox.askyesno(
                "Peer Mentoring",
                f"Delete pairing #{p.pairing_id} "
                "(and all sessions)?",
                parent=self.frame):
            return
        data.delete_pairing(p.pairing_id)
        self.refresh()

    def _add_session(self) -> None:
        p = self._selected()
        if not p:
            return
        if SessionEditor(self.frame,
                              pairing_id=p.pairing_id).result is not None:
            self._refresh_sessions()
            self.refresh()

    def _selected_session(self) -> Session | None:
        sel = self.sess_tree.selection()
        if not sel:
            messagebox.showinfo("Peer Mentoring",
                                  "Select a session first.",
                                  parent=self.frame)
            return None
        sid = int(sel[0])
        pairing_sel = self.tree.selection()
        if not pairing_sel:
            return None
        rows = data.list_sessions(int(pairing_sel[0]))
        return next((s for s in rows if s.session_id == sid), None)

    def _edit_session(self) -> None:
        p = self._selected()
        s = self._selected_session()
        if not p or not s:
            return
        if SessionEditor(self.frame,
                              pairing_id=p.pairing_id,
                              session=s).result is not None:
            self._refresh_sessions()
            self.refresh()

    def _delete_session(self) -> None:
        s = self._selected_session()
        if not s:
            return
        if not messagebox.askyesno(
                "Peer Mentoring",
                f"Delete session #{s.session_id}?",
                parent=self.frame):
            return
        data.delete_session(s.session_id)
        self._refresh_sessions()
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
        rows = data.pairings_for_student(sid)
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end",
                            f"Peer mentoring history for {sid}\n"
                            f"{'=' * 60}\n\n"
                            f"Total pairings : {len(rows)}\n\n")
        for p in rows:
            role = ("mentor" if p.mentor_id == sid else "mentee")
            other = (p.mentee_id if role == "mentor"
                       else p.mentor_id)
            stats = data.pairing_session_stats(p.pairing_id)
            self.text.insert("end",
                                f"#{p.pairing_id}  {p.start_date}  "
                                f"{p.programme}  "
                                f"role={role} (other: {other})  "
                                f"[{p.status}]\n"
                                f"  sessions {stats['attended']}/"
                                f"{stats['total']}  "
                                f"({stats['total_hours']}h)\n")
            if p.goals:
                self.text.insert("end",
                                    f"  Goals: "
                                    f"{p.goals.splitlines()[0]}\n")
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
        self.text.insert("end", "Peer Mentoring Summary\n")
        self.text.insert("end", "=" * 60 + "\n\n")
        self.text.insert("end",
                            f"Total pairings        : {s.total}\n"
                            f"Active                : {s.active}\n"
                            f"Pending match         : {s.pending}\n"
                            f"Completed             : {s.completed}\n"
                            f"Distinct mentors      : {s.distinct_mentors}\n"
                            f"Distinct mentees      : {s.distinct_mentees}\n"
                            f"Total sessions logged : {s.total_sessions}\n"
                            f"Total hours           : {s.total_hours}\n"
                            f"Average mentee rating : "
                            f"{s.average_mentee_rating if s.average_mentee_rating is not None else '—'}\n\n")
        self.text.insert("end", "By programme:\n")
        for k in PROGRAMMES:
            n = s.by_programme.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<22}: {n}\n")
        self.text.insert("end", "\nBy status:\n")
        for k in STATUSES:
            n = s.by_status.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<16}: {n}\n")
        self.text.insert("end", "\nBy frequency:\n")
        for k in FREQUENCIES:
            n = s.by_frequency.get(k, 0)
            if n:
                self.text.insert("end", f"  {k:<14}: {n}\n")
        self.text.config(state="disabled")


# ── Editors & dialogs ────────────────────────────────────────────

class PairingEditor:
    def __init__(self, parent, *,
                 pairing: Pairing | None = None) -> None:
        self.pairing = pairing
        self.result: Pairing | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit pairing #{pairing.pairing_id}"
                          if pairing else "New pairing")
        self.win.geometry("820x780")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        self._build()
        if pairing:
            self._load()
        self.win.wait_window()

    def _build(self) -> None:
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)
        self.vars: dict[str, tk.Variable] = {}
        self.texts: dict[str, tk.Text] = {}

        opts = _student_options()
        self._student_opts = opts
        labels = [lbl for _, lbl in opts]

        ttk.Label(body, text="Mentor*").grid(
            row=0, column=0, sticky="w", padx=4, pady=2)
        self.mentor_combo = ttk.Combobox(body, state="readonly",
                                            values=labels, width=42)
        self.mentor_combo.grid(row=0, column=1, columnspan=3,
                                  sticky="ew", padx=4, pady=2)
        ttk.Label(body, text="Mentee*").grid(
            row=1, column=0, sticky="w", padx=4, pady=2)
        self.mentee_combo = ttk.Combobox(body, state="readonly",
                                            values=labels, width=42)
        self.mentee_combo.grid(row=1, column=1, columnspan=3,
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

        combo(2, 0, "Programme*", "programme", PROGRAMMES)
        combo(2, 2, "Frequency*", "frequency", FREQUENCIES)
        entry(3, 0, "Start date*", "start_date")
        entry(3, 2, "Planned end", "planned_end")
        entry(4, 0, "Actual end", "actual_end")
        entry(4, 2, "Sessions planned", "sessions_planned")
        entry(5, 0, "Coordinator", "coordinator")
        entry(5, 2, "Location", "location")
        entry(6, 0, "Subject focus", "subject_focus")
        combo(6, 2, "Status*", "status", STATUSES)
        combo(7, 0, "Mentor rating", "mentor_rating",
                 ("", "1", "2", "3", "4", "5"))
        combo(7, 2, "Mentee rating", "mentee_rating",
                 ("", "1", "2", "3", "4", "5"))

        row = 8
        for key, label in (
                ("goals",           "Goals"),
                ("mentor_feedback", "Mentor feedback"),
                ("mentee_feedback", "Mentee feedback"),
                ("notes",           "Notes"),
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

        self.vars["start_date"].set(_dt.date.today().isoformat())
        self.vars["programme"].set(DEFAULT_PROGRAMME)
        self.vars["frequency"].set(DEFAULT_FREQUENCY)
        self.vars["status"].set(DEFAULT_STATUS)

    def _load(self) -> None:
        p = self.pairing
        assert p is not None
        for i, (sid, _) in enumerate(self._student_opts):
            if sid == p.mentor_id:
                self.mentor_combo.current(i)
            if sid == p.mentee_id:
                self.mentee_combo.current(i)
        for key in ("programme", "frequency", "start_date",
                     "planned_end", "actual_end", "coordinator",
                     "location", "subject_focus", "status"):
            self.vars[key].set(getattr(p, key) or "")
        self.vars["sessions_planned"].set(
            str(p.sessions_planned)
            if p.sessions_planned is not None else "")
        self.vars["mentor_rating"].set(
            str(p.mentor_rating)
            if p.mentor_rating is not None else "")
        self.vars["mentee_rating"].set(
            str(p.mentee_rating)
            if p.mentee_rating is not None else "")
        for k in self.texts:
            self.texts[k].delete("1.0", "end")
            self.texts[k].insert("1.0", getattr(p, k) or "")

    def _save(self) -> None:
        mi = self.mentor_combo.current()
        ei = self.mentee_combo.current()
        if mi < 0 or ei < 0:
            messagebox.showerror("Peer Mentoring",
                                    "Pick both mentor and mentee.",
                                    parent=self.win)
            return
        payload: dict = {
            "mentor_id": self._student_opts[mi][0],
            "mentee_id": self._student_opts[ei][0],
        }
        for k, v in self.vars.items():
            payload[k] = v.get().strip()
        for k, t in self.texts.items():
            payload[k] = t.get("1.0", "end").rstrip()
        try:
            if self.pairing:
                self.result = data.update_pairing(
                    self.pairing.pairing_id, payload)
            else:
                self.result = data.create_pairing(payload)
        except ValidationError as exc:
            messagebox.showerror("Peer Mentoring", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class SessionEditor:
    def __init__(self, parent, *, pairing_id: int,
                 session: Session | None = None) -> None:
        self.pairing_id = pairing_id
        self.session = session
        self.result: Session | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(
            f"Edit session #{session.session_id}"
            if session else "New session")
        self.win.geometry("520x420")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Date*").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.when = tk.StringVar(
            value=(session.session_date if session
                    else _dt.date.today().isoformat()))
        ttk.Entry(body, textvariable=self.when, width=14).grid(
            row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Duration (mins)*").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.dur = tk.StringVar(
            value=(str(session.duration_minutes)
                    if session else "30"))
        ttk.Entry(body, textvariable=self.dur, width=10).grid(
            row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Focus").grid(
            row=2, column=0, sticky="w", padx=4, pady=4)
        self.focus = tk.StringVar(
            value=(session.focus if session else "") or "")
        ttk.Entry(body, textvariable=self.focus).grid(
            row=2, column=1, sticky="ew", padx=4, pady=4)
        self.attended = tk.BooleanVar(
            value=(session.attended if session else True))
        ttk.Checkbutton(body, text="Attended",
                         variable=self.attended).grid(
            row=3, column=0, columnspan=2, sticky="w",
            padx=4, pady=4)
        ttk.Label(body, text="Notes").grid(
            row=4, column=0, sticky="nw", padx=4, pady=4)
        self.notes = tk.Text(body, height=6, width=44, wrap="word")
        if session and session.notes:
            self.notes.insert("1.0", session.notes)
        self.notes.grid(row=4, column=1, sticky="ew",
                            padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Save",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        payload = {
            "session_date": self.when.get().strip(),
            "duration_minutes": self.dur.get().strip(),
            "focus": self.focus.get().strip() or None,
            "attended": self.attended.get(),
            "notes": self.notes.get("1.0", "end").rstrip() or None,
        }
        try:
            if self.session:
                self.result = data.update_session(
                    self.session.session_id, payload)
            else:
                self.result = data.add_session(self.pairing_id,
                                                    payload)
        except ValidationError as exc:
            messagebox.showerror("Peer Mentoring", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


class CompleteDialog:
    def __init__(self, parent, *, pairing: Pairing) -> None:
        self.pairing = pairing
        self.result: Pairing | None = None
        self.win = tk.Toplevel(parent)
        self.win.title(f"Complete pairing #{pairing.pairing_id}")
        self.win.geometry("560x500")
        self.win.transient(parent); self.win.after_idle(self.win.grab_set)
        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)
        ttk.Label(body, text="Ended on").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.when = tk.StringVar(value=_dt.date.today().isoformat())
        ttk.Entry(body, textvariable=self.when, width=14).grid(
            row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Mentor rating").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self.mr = tk.StringVar(
            value=str(pairing.mentor_rating)
            if pairing.mentor_rating else "")
        ttk.Combobox(body, textvariable=self.mr,
                      values=("", "1", "2", "3", "4", "5"),
                      state="readonly", width=6).grid(
            row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Mentee rating").grid(
            row=2, column=0, sticky="w", padx=4, pady=4)
        self.me = tk.StringVar(
            value=str(pairing.mentee_rating)
            if pairing.mentee_rating else "")
        ttk.Combobox(body, textvariable=self.me,
                      values=("", "1", "2", "3", "4", "5"),
                      state="readonly", width=6).grid(
            row=2, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(body, text="Mentor feedback").grid(
            row=3, column=0, sticky="nw", padx=4, pady=4)
        self.mfb = tk.Text(body, height=4, width=48, wrap="word")
        self.mfb.insert("1.0", pairing.mentor_feedback or "")
        self.mfb.grid(row=3, column=1, sticky="ew",
                          padx=4, pady=4)
        ttk.Label(body, text="Mentee feedback").grid(
            row=4, column=0, sticky="nw", padx=4, pady=4)
        self.efb = tk.Text(body, height=4, width=48, wrap="word")
        self.efb.insert("1.0", pairing.mentee_feedback or "")
        self.efb.grid(row=4, column=1, sticky="ew",
                          padx=4, pady=4)
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(bar, text="Complete",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="right")
        self.win.wait_window()

    def _save(self) -> None:
        try:
            mr = int(self.mr.get()) if self.mr.get().isdigit() else None
            me = int(self.me.get()) if self.me.get().isdigit() else None
            self.result = data.complete(
                self.pairing.pairing_id,
                mentor_feedback=self.mfb.get("1.0", "end").rstrip()
                or None,
                mentee_feedback=self.efb.get("1.0", "end").rstrip()
                or None,
                mentor_rating=mr, mentee_rating=me,
                ended_on=self.when.get().strip()
                or _dt.date.today().isoformat())
        except ValidationError as exc:
            messagebox.showerror("Peer Mentoring", str(exc),
                                    parent=self.win)
            return
        self.win.destroy()


def _prompt_text(parent, title: str, *,
                  initial: str = "") -> str | None:
    win = tk.Toplevel(parent)
    win.title(title); win.geometry("420x180")
    win.transient(parent); win.after_idle(win.grab_set)
    ttk.Label(win, text=title).pack(anchor="w", padx=8, pady=8)
    txt = tk.Text(win, height=4, wrap="word")
    txt.insert("1.0", initial)
    txt.pack(fill="both", expand=True, padx=8)
    result: dict = {"value": None}

    def ok() -> None:
        result["value"] = txt.get("1.0", "end").rstrip()
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


__all__ = ["open_peer_mentoring_window"]
