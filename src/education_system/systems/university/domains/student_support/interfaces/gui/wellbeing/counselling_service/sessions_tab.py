"""Caseload & Sessions: allocated episodes, and one episode's case window.

The window is where a counsellor books and records sessions, scores the
outcome measures (PHQ-9, GAD-7, CORE-10), keeps case notes, changes the session
cap and escalates. Opening it is an audited look at a sealed clinical record
(``counselling_pathway.case_detail``).
"""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from education_system.platform.delivery.gui import window_sizing
from education_system.systems.university.domains.student_support.domain.mental_health import (
    counselling_pathway as pathway,
    outcome_measures,
)
from education_system.systems.university.domains.student_support.interfaces.gui.wellbeing.counselling_service import (
    common,
    team_tabs,
)


class CaseloadTab(ttk.Frame):
    """Allocated episodes, everyone's or one counsellor's."""

    COLUMNS = (("referral_id", "#", 50), ("student_id", "Student", 90),
               ("student_name", "Name", 170), ("counsellor_name", "Counsellor", 140),
               ("risk_rating", "Risk", 80), ("pathway", "Pathway", 90),
               ("sessions_used", "Sessions", 70), ("session_cap", "Cap", 50),
               ("next_session", "Next session", 100), ("allocated_at", "Allocated", 140))
    EVERYONE = "Everyone"

    def __init__(self, master, auth):
        super().__init__(master, padding=8)
        self.auth = auth
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(bar, text="Open case…", command=self._open).pack(side=tk.LEFT)
        ttk.Button(bar, text="Book session…", command=self._book).pack(side=tk.LEFT, padx=4)
        ttk.Label(bar, text="Counsellor:").pack(side=tk.LEFT, padx=(12, 4))
        self.counsellor = tk.StringVar(value=self.EVERYONE)
        self.picker = ttk.Combobox(bar, textvariable=self.counsellor, state="readonly", width=30)
        self.picker.pack(side=tk.LEFT)
        self.picker.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side=tk.RIGHT)
        self.view = common.tree(self, self.COLUMNS)
        self.view.bind("<Double-1>", lambda _e: self._open())
        self.rows = {}
        self.people = {}
        self.refresh()

    def refresh(self):
        people = common.run(self, pathway.counsellors, self.auth) or []
        self.people = {p["name"]: p["counselor_id"] for p in people}
        self.picker.configure(values=[self.EVERYONE, *self.people])
        if self.counsellor.get() not in self.people:
            self.counsellor.set(self.EVERYONE)
        rows = common.run(self, pathway.caseload, self.auth,
                          self.people.get(self.counsellor.get())) or []
        self.rows = common.fill(self.view, rows, self.COLUMNS, "No allocated episodes")

    def _pick(self):
        return common.selected(self.view, self.rows, self, "an episode")

    def _open(self):
        row = self._pick()
        if row:
            CaseWindow(self, self.auth, row["referral_id"], on_change=self.refresh)

    def _book(self):
        row = self._pick()
        if row:
            book_session_dialog(self, self.auth, row["referral_id"], self.refresh)


def book_session_dialog(parent, auth, referral_id, on_done=None):
    win = common.dialog(parent, f"Book a session — referral #{referral_id}", "460x280")
    values = {"date": tk.StringVar(value=date.today().isoformat()),
              "time": tk.StringVar(value="10:00"), "duration": tk.StringVar(value="50"),
              "mode": tk.StringVar(value="in-person"), "stage": tk.StringVar(value="")}
    fields = (("Date (YYYY-MM-DD):", "date"), ("Time (HH:MM):", "time"),
              ("Minutes:", "duration"))
    for i, (label, key) in enumerate(fields):
        ttk.Label(win, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(win, textvariable=values[key], width=16).grid(row=i, column=1, sticky="w",
                                                                padx=8)
    ttk.Label(win, text="Mode:").grid(row=3, column=0, sticky="w", padx=8, pady=4)
    ttk.Combobox(win, textvariable=values["mode"], state="readonly", width=14,
                 values=("in-person", "online", "telephone")).grid(row=3, column=1, sticky="w",
                                                                   padx=8)
    ttk.Label(win, text="Stage:").grid(row=4, column=0, sticky="w", padx=8, pady=4)
    ttk.Combobox(win, textvariable=values["stage"], state="readonly", width=14,
                 values=("", *pathway.SESSION_STAGES)).grid(row=4, column=1, sticky="w", padx=8)
    ttk.Label(win, text="(blank = worked out from the session number)",
              foreground="#777777").grid(row=5, column=1, sticky="w", padx=8)

    def save():
        try:
            minutes = int(values["duration"].get().strip() or 50)
        except ValueError:
            common.show_error(win, ValueError("Minutes must be a whole number."))
            return
        try:
            pathway.book_session(auth, referral_id, values["date"].get(), values["time"].get(),
                                 duration_minutes=minutes, mode=values["mode"].get(),
                                 stage=values["stage"].get() or None)
        except Exception as exc:
            common.show_error(win, exc)
            return
        win.destroy()
        if on_done:
            on_done()
    ttk.Button(win, text="Book", command=save).grid(row=6, column=1, sticky="e", padx=8, pady=10)


def record_session_dialog(parent, auth, session, on_done=None):
    win = common.dialog(parent, f"Record session {session.get('session_number') or ''} — "
                                f"{session.get('session_date') or ''}", "640x520")
    # Actions first so they stay on screen however small the window is.
    actions = ttk.Frame(win, padding=8)
    actions.pack(side=tk.BOTTOM, fill=tk.X)
    form = ttk.Frame(win, padding=8)
    form.pack(fill=tk.BOTH, expand=True)
    ttk.Label(form, text="Status:").grid(row=0, column=0, sticky="w", pady=4)
    status = tk.StringVar(value="attended")
    ttk.Combobox(form, textvariable=status, values=pathway.SESSION_STATUSES[1:],
                 state="readonly", width=14).grid(row=0, column=1, sticky="w")
    ttk.Label(form, text="Stage:").grid(row=1, column=0, sticky="w", pady=4)
    stage = tk.StringVar(value=session.get("session_stage") or "")
    ttk.Combobox(form, textvariable=stage, values=pathway.SESSION_STAGES, state="readonly",
                 width=14).grid(row=1, column=1, sticky="w")
    ttk.Label(form, text="Clinical notes:").grid(row=2, column=0, sticky="nw", pady=4)
    notes = common.text_box(form, height=10, width=60)
    notes.insert("1.0", session.get("notes") or "")
    notes.grid(row=2, column=1, sticky="nsew", pady=4)
    ttk.Label(form, text="Outcome:").grid(row=3, column=0, sticky="nw", pady=4)
    outcome = common.text_box(form, height=4, width=60)
    outcome.insert("1.0", session.get("outcome") or "")
    outcome.grid(row=3, column=1, sticky="nsew", pady=4)
    form.columnconfigure(1, weight=1)
    form.rowconfigure(2, weight=1)

    def save():
        try:
            pathway.record_session(auth, session["id"], status.get(),
                                   notes=common.read_text(notes) or None,
                                   outcome=common.read_text(outcome) or None,
                                   stage=stage.get() or None)
        except Exception as exc:
            common.show_error(win, exc)
            return
        win.destroy()
        if on_done:
            on_done()
    ttk.Button(actions, text="Save", command=save).pack(side=tk.RIGHT)


class MeasureDialog:
    """Complete one questionnaire, one row of answers per item."""

    def __init__(self, parent, auth, referral_id, sessions=(), on_done=None):
        self.auth, self.referral_id, self.on_done = auth, referral_id, on_done
        self.sessions = {f"Session {s['session_number']} ({s['session_date']})": s["id"]
                         for s in sessions if s.get("status") != "cancelled"}
        self.win = win = common.dialog(parent, f"Outcome measure — referral #{referral_id}",
                                       "1000x640")
        top = ttk.Frame(win, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Measure:").pack(side=tk.LEFT)
        self.code = tk.StringVar(value=next(iter(outcome_measures.MEASURES)))
        box = ttk.Combobox(top, textvariable=self.code, state="readonly", width=10,
                           values=list(outcome_measures.MEASURES))
        box.pack(side=tk.LEFT, padx=(4, 12))
        box.bind("<<ComboboxSelected>>", lambda _e: self._draw())
        ttk.Label(top, text="Stage:").pack(side=tk.LEFT)
        self.stage = tk.StringVar(value=outcome_measures.STAGES[0])
        ttk.Combobox(top, textvariable=self.stage, state="readonly", width=8,
                     values=outcome_measures.STAGES).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(top, text="Session:").pack(side=tk.LEFT)
        self.session = tk.StringVar(value="")
        ttk.Combobox(top, textvariable=self.session, state="readonly", width=26,
                     values=("", *self.sessions)).pack(side=tk.LEFT, padx=4)
        actions = ttk.Frame(win, padding=8)
        actions.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(actions, text="Score and save", command=self._save).pack(side=tk.RIGHT)
        self.body = ttk.Frame(win, padding=8)
        self.body.pack(fill=tk.BOTH, expand=True)
        self.answers: list[tk.StringVar] = []
        self.labels: list[str] = []
        self._draw()

    def _draw(self):
        for child in self.body.winfo_children():
            child.destroy()
        measure = outcome_measures.get(self.code.get())
        ttk.Label(self.body, text=measure.title, font=("Arial", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.labels = [f"{i} — {answer}" for i, answer in enumerate(measure.answers)]
        self.answers = []
        for number, item in enumerate(measure.items, start=1):
            ttk.Label(self.body, text=f"{number}. {item}", wraplength=620, justify=tk.LEFT).grid(
                row=number, column=0, sticky="w", pady=2)
            var = tk.StringVar()
            ttk.Combobox(self.body, textvariable=var, values=self.labels, state="readonly",
                         width=30).grid(row=number, column=1, sticky="e", padx=(8, 0))
            self.answers.append(var)
        self.body.columnconfigure(0, weight=1)

    def _save(self):
        answers = [var.get().split(" — ")[0] if var.get() else None for var in self.answers]
        try:
            result = pathway.record_measure(self.auth, self.referral_id, self.code.get(),
                                            self.stage.get(), answers,
                                            session_id=self.sessions.get(self.session.get()))
        except Exception as exc:
            common.show_error(self.win, exc)
            return
        text = (f"{result['measure']}: {result['total']} of {result['max_total']} "
                f"({result['band']}).")
        if result["risk_flag"]:
            messagebox.showwarning(common.title(), text + "\n\nThe risk item was scored "
                                   f"{result['risk_item_score']}. Review the risk now and "
                                   "escalate if needed.", parent=self.win)
        else:
            messagebox.showinfo(common.title(), text, parent=self.win)
        self.win.destroy()
        if self.on_done:
            self.on_done()


class CaseWindow:
    """One episode of care. Closes itself if the record cannot be read."""

    SESSIONS = (("session_number", "No.", 45), ("session_date", "Date", 95),
                ("session_time", "Time", 60), ("duration_minutes", "Mins", 50),
                ("mode", "Mode", 90), ("session_stage", "Stage", 80),
                ("status", "Status", 80), ("counsellor", "Counsellor", 140),
                ("notes", "Notes", 340))
    MEASURES = (("recorded_at", "Recorded", 145), ("measure", "Measure", 80),
                ("stage", "Stage", 70), ("total", "Total", 55), ("band", "Band", 130),
                ("risk", "Risk item", 70), ("recorded_by", "By", 120))
    NOTES = (("created_at", "When", 145), ("note_type", "Type", 90), ("author", "By", 120),
             ("note", "Note", 660))

    def __init__(self, parent, auth, referral_id, on_change=None):
        self.auth, self.referral_id, self.on_change = auth, referral_id, on_change
        self.detail = common.run(parent, pathway.case_detail, auth, referral_id)
        if self.detail is None:
            return
        window_sizing.install()
        self.win = win = tk.Toplevel(parent)
        win.title(f"Counselling case — referral #{referral_id}")
        window_sizing.center(win, 1400, 900, minsize=(1200, 800))
        self.heading = tk.StringVar()
        ttk.Label(win, textvariable=self.heading, font=("Arial", 13, "bold"),
                  padding=(10, 8, 10, 0)).pack(anchor="w")
        bar = ttk.Frame(win, padding=(10, 6))
        bar.pack(fill=tk.X)
        ttk.Button(bar, text="Change session cap…", command=self._cap).pack(side=tk.LEFT)
        ttk.Button(bar, text="Escalate to crisis…", command=self._escalate).pack(side=tk.LEFT,
                                                                                padx=4)
        ttk.Button(bar, text="Refresh", command=self._reload).pack(side=tk.RIGHT)
        book = ttk.Notebook(win)
        book.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self._summary_tab(book)
        self._sessions_tab(book)
        self._measures_tab(book)
        self._notes_tab(book)
        self._show()

    # ---------------------------------------------------------------- tabs
    def _summary_tab(self, book):
        tab = ttk.Frame(book, padding=8)
        book.add(tab, text="Summary")
        self.summary = tk.Text(tab, wrap="word")
        self.summary.pack(fill=tk.BOTH, expand=True)

    def _sessions_tab(self, book):
        tab = ttk.Frame(book, padding=8)
        book.add(tab, text="Sessions")
        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(bar, text="Book session…", command=lambda: book_session_dialog(
            self.win, self.auth, self.referral_id, self._changed)).pack(side=tk.LEFT)
        ttk.Button(bar, text="Record selected…", command=self._record).pack(side=tk.LEFT, padx=4)
        self.session_view = common.tree(tab, self.SESSIONS)
        self.session_view.bind("<Double-1>", lambda _e: self._record())
        self.session_rows = {}

    def _measures_tab(self, book):
        tab = ttk.Frame(book, padding=8)
        book.add(tab, text="Outcome measures")
        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(bar, text="Add measure…", command=lambda: MeasureDialog(
            self.win, self.auth, self.referral_id, self.detail["sessions"],
            self._changed)).pack(side=tk.LEFT)
        self.change = tk.StringVar()
        ttk.Label(tab, textvariable=self.change, justify=tk.LEFT).pack(anchor="w", pady=(0, 6))
        self.measure_view = common.tree(tab, self.MEASURES)

    def _notes_tab(self, book):
        tab = ttk.Frame(book, padding=8)
        book.add(tab, text="Case notes")
        form = ttk.LabelFrame(tab, text="Add a note", padding=8)
        form.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))
        self.note = common.text_box(form, height=4)
        self.note.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(form, text="Save note", command=self._add_note).pack(side=tk.LEFT, padx=(8, 0))
        self.note_view = common.tree(tab, self.NOTES)

    # ---------------------------------------------------------------- data
    def _show(self):
        ref = self.detail["referral"]
        student = self.detail["student"]
        counsellor = self.detail["counsellor"]
        self.heading.set(f"{student.get('name') or ref['student_id']} ({ref['student_id']}) — "
                         f"{ref['status_label']}")
        lines = [f"Student: {student.get('name')} ({ref['student_id']})",
                 f"Email: {student.get('email_address') or 'not recorded'}",
                 f"Status: {ref['status_label']}",
                 f"Referred: {str(ref.get('referred_at') or '')[:16]} "
                 f"by {ref.get('referred_by') or 'unknown'} ({ref.get('source') or 'unknown'})",
                 f"About: {ref.get('presenting_issue') or 'not given'}",
                 f"Risk: {ref.get('risk_rating') or 'not triaged'}"
                 f" — pathway {ref.get('pathway') or 'none'}",
                 f"Counsellor: {counsellor.get('name') or 'not allocated'}",
                 f"Session cap: {ref.get('session_cap') or 'not set'}"]
        if ref.get("safeguarding_concern_id"):
            lines.append(f"Safeguarding concern: #{ref['safeguarding_concern_id']}")
        for key, label in (("reason", "Reason for referral"), ("triage_notes", "Triage notes"),
                           ("discharge_summary", "Discharge summary")):
            if ref.get(key):
                lines += ["", f"{label}:", str(ref[key])]
        self.summary.configure(state="normal")
        self.summary.delete("1.0", tk.END)
        self.summary.insert("1.0", "\n".join(lines))
        self.summary.configure(state="disabled")
        self.session_rows = common.fill(self.session_view, self.detail["sessions"],
                                        self.SESSIONS, "No sessions yet")
        measures = [{**m, "risk": bool(m.get("risk_flag"))} for m in self.detail["measures"]]
        common.fill(self.measure_view, measures, self.MEASURES, "No measures recorded")
        self.change.set(self._change_text(measures))
        common.fill(self.note_view, self.detail["notes"], self.NOTES, "No case notes")

    @staticmethod
    def _change_text(measures) -> str:
        """First against last for each measure completed at both stages."""
        lines = []
        for code in outcome_measures.MEASURES:
            taken = [m for m in measures if m["measure"] == code]
            first = next((m for m in taken if m["stage"] == "first"), None)
            last = next((m for m in reversed(taken) if m["stage"] == "last"), None)
            if not first or not last:
                continue
            result = outcome_measures.change(code, first["total"], last["total"])
            line = (f"{code}: {result['first']} → {result['last']} ({result['category']}"
                    + ("; reliable recovery" if result["reliable_recovery"]
                       else "; recovered" if result["recovered"] else "") + ")")
            lines.append(line)
        return "\n".join(lines)

    def _reload(self):
        detail = common.run(self.win, pathway.case_detail, self.auth, self.referral_id)
        if detail is not None:
            self.detail = detail
            self._show()

    def _changed(self):
        self._reload()
        if self.on_change:
            self.on_change()

    # ------------------------------------------------------------- actions
    def _record(self):
        row = common.selected(self.session_view, self.session_rows, self.win, "a session")
        if row:
            record_session_dialog(self.win, self.auth, row, self._changed)

    def _add_note(self):
        if common.run(self.win, pathway.add_case_note, self.auth, self.referral_id,
                      common.read_text(self.note)) is not None:
            self.note.delete("1.0", tk.END)
            self._changed()

    def _escalate(self):
        team_tabs.escalate_dialog(self.win, self.auth, self.referral_id, self._changed)

    def _cap(self):
        win = common.dialog(self.win, "Change the session cap", "520x280")
        current = self.detail["referral"].get("session_cap") or pathway.DEFAULT_SESSION_CAP
        ttk.Label(win, text="New cap:").pack(anchor="w", padx=8, pady=(8, 0))
        cap = tk.StringVar(value=str(current))
        ttk.Spinbox(win, from_=1, to=pathway.MAX_SESSION_CAP, textvariable=cap, width=6).pack(
            anchor="w", padx=8)
        ttk.Label(win, text="Clinical reason (kept as a case note):").pack(anchor="w", padx=8,
                                                                           pady=(8, 0))

        def save():
            try:
                pathway.extend_cap(self.auth, self.referral_id, cap.get(),
                                   common.read_text(reason))
            except Exception as exc:
                common.show_error(win, exc)
                return
            win.destroy()
            self._changed()
        ttk.Button(win, text="Save", command=save).pack(side=tk.BOTTOM, anchor="e", padx=8,
                                                        pady=8)
        reason = common.text_box(win, height=5)
        reason.pack(fill=tk.BOTH, expand=True, padx=8)
