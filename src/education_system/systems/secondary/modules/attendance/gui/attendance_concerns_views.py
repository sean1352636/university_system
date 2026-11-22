"""Attendance Concerns screen.

The old Attendance Concerns window is the first tab ("Cases") with its
toolbar (Academic year and Status filters, Open only; Apply, New, Edit,
Close, Delete, Refresh), its columns (ID, Pupil, Yr, AY, Type, Level, Att%,
Status, Opened, Review), its row colours (severe, closed, escalated) and its
concern dialog (Pupil ID, Academic year, Concern type, Level, Attendance %,
Threshold %, Opened, Next review, Closed, Status, Key worker, Parent contact,
Intervention, Notes). Added: Year / Stage / Type filters, Set status,
Summary, Timeline (notes), Add note, Next stage, Letter home, Review, Refer to
LA, LA outcome, CME, Trend, Open pupil, History, Export CSV.

New tabs: From the registers (persistent / severe absentees with no case),
Reviews due, Watch (penalty-notice threshold and children missing education)
and Dashboard (by year group and form). Rules are in
:mod:`modules.attendance.domain.attendance_concerns`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui import tk_threads
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.attendance.domain import attendance_concerns as AC
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
YEARS = ("7", "8", "9", "10", "11")
_ERRORS = W.ERRORS
_problems = W.problems
_text_window = W.text_window
_form = W.form_dialog
_TAGS = {**W.STANDARD_TAGS, "severe": "#fde7e7", "closed": {"foreground": "#888"},
         "escalated": "#ffe4b3"}
_LETTER_LABELS = {v[2]: k for k, v in AC.LETTERS.items()}


def _tree(parent, columns, height: int = 16, select: str = "browse") -> ttk.Treeview:
    return W.tree(parent, columns, height=height, select=select,
                  stretch={"pupil", "summary", "step", "group", "type"}, tags=_TAGS)


def _pct(v: float | None) -> str:
    return f"{v:.1f}" if v is not None else ""


def _fields(c: AC.Concern | None, pupil: str = "") -> list:
    """The old dialog's fields in its order, then the new ones."""
    def g(k, default=""):
        v = getattr(c, k) if c else None
        return default if v is None else v
    return [
        ("pupil_id", "Pupil ID / admission no.", c.admission_no if c else pupil, None),
        ("academic_year", "Academic year (blank = from opened)", g("academic_year"), None),
        ("concern_type", "Concern type", g("concern_type", AC.DEFAULT_TYPE), AC.CONCERN_TYPES),
        ("level", "Level (blank = from attendance)", g("level"), ["", *AC.CONCERN_LEVELS]),
        ("attendance_pct", "Attendance % (blank = from registers)", g("attendance_pct"), None),
        ("threshold_pct", "Threshold %", g("threshold_pct", 90.0), None),
        ("opened_date", "Opened (blank = today)", g("opened_date"), None),
        ("next_review_date", "Next review (blank = 4 weeks)", g("next_review_date"), None),
        ("closed_date", "Closed", g("closed_date"), None),
        ("status", "Status", g("status", AC.DEFAULT_STATUS), AC.CONCERN_STATUSES),
        ("key_worker", "Key worker", g("key_worker"), None),
        ("parent_contact", "Parent contact", g("parent_contact"), None),
        ("intervention", "Intervention", g("intervention"), "text"),
        ("notes", "Notes", g("notes"), "text"),
        ("target_pct", "Target %", g("target_pct"), None),
        ("meeting_date", "Attendance meeting date", g("meeting_date"), None),
        ("support_plan", "Attendance support plan", g("support_plan"), "text"),
    ]


def _background(widget, work: Callable[[], Any], done: Callable[[Any, Exception | None], None]
                ) -> None:
    """Run *work* off the main thread; *done(result, error)* back on it."""
    def run() -> None:
        try:
            res = work()
        except Exception as e:  # noqa: BLE001 - shown to the user
            logger.exception("Attendance concerns background work failed")
            tk_threads.ui(widget, done, None, e)
            return
        tk_threads.ui(widget, done, res, None)
    tk_threads.start_thread(widget, run, name="secondary-attendance-concerns")


class AttendanceConcernsPage:
    TABS = ("Cases", "From the registers", "Reviews due", "Watch", "Dashboard")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = AC.is_editor(principal)
        activity_log.record("attendance_concerns.view")
        ttk.Label(parent, text="Attendance Concerns", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self._built: set[str] = set()
        start = state.get("tab") if state.get("tab") in self.TABS else "Cases"
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # ── helpers ──────────────────────────────────────────────────────

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, _problems(e), parent=self._top())

    def _info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text, parent=self._top())

    def _button(self, bar, text: str, command, editor_only: bool = False) -> ttk.Button:
        b = ttk.Button(bar, text=text, command=command)
        if editor_only and not self.editor:
            b.state(["disabled"])
        b.pack(side="left", padx=2)
        return b

    def _builders(self) -> dict[str, tuple[Callable, Callable]]:
        return {"Cases": (self._build_cases, self.refresh),
                "From the registers": (self._build_candidates, self.refresh_candidates),
                "Reviews due": (self._build_due, self.refresh_due),
                "Watch": (self._build_watch, self.refresh_watch),
                "Dashboard": (self._build_dash, self.refresh_dash)}

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        build, refresh = self._builders()[name]
        if name not in self._built:
            self._built.add(name)
            build(self.tabs[name])
        refresh()

    def _refresh_all(self) -> None:
        for name, (_b, fn) in self._builders().items():
            if name in self._built and name in ("Cases", "Reviews due"):
                fn()

    def _alive(self) -> bool:
        try:
            return bool(self.parent.winfo_exists())
        except tk.TclError:
            return False

    # ── Cases (the old window) ───────────────────────────────────────

    _COLUMNS = [("id", "ID", 50), ("pupil", "Pupil", 200), ("year", "Yr", 40),
                ("ay", "AY", 70), ("type", "Type", 150), ("level", "Level", 150),
                ("att", "Att%", 55), ("status", "Status", 90), ("opened", "Opened", 90),
                ("review", "Review", 90), ("stage", "Stage", 170)]

    def _build_cases(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.ay = tk.StringVar(value=self.state.get("ay", ""))
        self.status = tk.StringVar(value=self.state.get("status", ""))
        self.year = tk.StringVar(value=self.state.get("year", ""))
        self.stage = tk.StringVar(value=self.state.get("stage", ""))
        self.ctype = tk.StringVar(value=self.state.get("type", ""))
        self.open_only = tk.BooleanVar(value=self.state.get("open_only", True))
        ttk.Label(bar, text="Academic year:").pack(side="left", padx=(0, 4))
        ttk.Entry(bar, textvariable=self.ay, width=9).pack(side="left", padx=(0, 6))
        for label, var, values, width in (
                ("Status:", self.status, ["", *AC.CONCERN_STATUSES], 11),
                ("Year:", self.year, ["", *YEARS], 4),
                ("Stage:", self.stage, ["", *AC.STAGES], 22),
                ("Type:", self.ctype, ["", *AC.CONCERN_TYPES], 18)):
            ttk.Label(bar, text=label).pack(side="left", padx=(0, 4))
            cb = ttk.Combobox(bar, textvariable=var, values=values, state="readonly",
                              width=width)
            cb.pack(side="left", padx=(0, 6))
            cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Checkbutton(bar, text="Open only", variable=self.open_only,
                        command=self.refresh).pack(side="left", padx=4)
        bar1 = ttk.Frame(tab)
        bar1.pack(fill="x", pady=(0, 4))
        for text, cmd, lead in (("Apply", self.refresh, False), ("New", self.new, True),
                                ("Edit", self.edit, True), ("Close", self.close, True),
                                ("Delete", self.delete, True), ("Refresh", self.refresh, False),
                                ("Set status", self.set_status, True),
                                ("Summary", self.summary, False)):
            self._button(bar1, text, cmd, lead)
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(0, 4))
        for text, cmd, lead in (("Timeline", self.timeline, False),
                                ("Add note…", self.add_note, False),
                                ("Next stage…", self.next_stage, True),
                                ("Letter home…", self.letter, True),
                                ("Review…", self.review, True),
                                ("Refer to LA…", self.refer, True),
                                ("LA outcome…", self.la_outcome, True),
                                ("CME…", self.cme, True)):
            self._button(bar2, text, cmd, lead)
        bar3 = ttk.Frame(tab)
        bar3.pack(fill="x", pady=(0, 6))
        for text, cmd, lead in (("Trend", self.trend, False),
                                ("Open pupil", self._open_selected, False),
                                ("History", self.history, False),
                                ("Update % from registers", self.refresh_figures, True),
                                ("Export CSV…", self.export, False)):
            self._button(bar3, text, cmd, lead)
        self.tree = _tree(tab, self._COLUMNS)
        self.tree.bind("<Double-1>", lambda _e: self.timeline())
        self.rows: dict[str, AC.Concern] = {}

    def refresh(self) -> None:
        f = dict(ay=self.ay.get().strip(), status=self.status.get(), year=self.year.get(),
                 stage=self.stage.get(), type=self.ctype.get(), open_only=self.open_only.get())
        self.state.update(f)
        try:
            rows = AC.list_concerns(academic_year=f["ay"] or None, status=f["status"] or None,
                                    year_group=f["year"] or None, stage=f["stage"] or None,
                                    concern_type=f["type"] or None, open_only=f["open_only"])
        except _ERRORS as e:
            self._err("Attendance Concerns", e)
            return
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for c in rows:
            self.rows[str(c.concern_id)] = c
            tag = ("closed" if not c.is_open else "escalated" if c.status == "Escalated" else
                   "severe" if (c.attendance_pct is not None and c.attendance_pct < 80) else
                   "warn" if c.review_overdue else "")
            self.tree.insert("", "end", iid=str(c.concern_id), tags=(tag,) if tag else (),
                             values=(c.concern_id, f"{c.pupil_name} ({c.admission_no})",
                                     c.pupil_year, c.academic_year, c.concern_type, c.level,
                                     _pct(c.attendance_pct), c.status, c.opened_date,
                                     c.next_review_date or "",
                                     f"{c.stage_no}. {c.stage}" + (" · CME" if c.cme else "")))
        s = AC.cohort_summary(academic_year=f["ay"] or None)
        avg = f"{s['avg_attendance']:.1f}%" if s["avg_attendance"] is not None else "-"
        self.summary_var.set(f"Cases: {s['total']}    Open: {s['open']}    Pupils: "
                             f"{s['pupils']}    Average attendance: {avg}    CME: {s['cme']}"
                             f"    LA referrals: {s['referrals']}")

    def _selected(self, title: str) -> AC.Concern | None:
        sel = self.tree.selection()
        if not sel:
            self._info(title, "Select a case first.")
            return None
        return AC.get(int(sel[0]))

    def _confirm(self, data: dict[str, Any], concern_id: int | None = None) -> None:
        try:
            warnings = AC.check(data, actor=self.principal, concern_id=concern_id)
        except _ERRORS:
            return
        if warnings and not messagebox.askyesno(
                "Attendance Concerns", "\n\n".join(warnings) + "\n\nSave anyway?",
                parent=self._top()):
            raise AC.ValidationError(["Not saved yet - change the details, or Save again and "
                                      "answer Yes"])

    def new(self, pupil: str = "") -> None:
        def save(v):
            v = {k: x for k, x in v.items() if x not in ("", None)}
            self._confirm(v)
            AC.create(v, actor=self.principal)
            self._refresh_all()
        _form(self.parent, "New attendance concern", _fields(None, pupil), save,
              note="Attendance % is read from the registers (this school year) when left "
                   "blank, and the level from it.")

    def edit(self) -> None:
        c = self._selected("Edit concern")
        if c is None:
            return

        def save(v):
            v.pop("pupil_id", None)
            v.pop("academic_year", None)
            changes = {k: x for k, x in v.items() if str(x or "") != str(
                getattr(c, k) if getattr(c, k) is not None else "")}
            AC.update(c.concern_id, changes, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Edit concern #{c.concern_id}", _fields(c), save)

    def set_status(self) -> None:
        c = self._selected("Set status")
        if c is None:
            return

        def save(v):
            AC.set_status(c.concern_id, v["status"], actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Status - concern #{c.concern_id}",
              [("status", "Status", c.status, AC.CONCERN_STATUSES)], save)

    def close(self) -> None:
        c = self._selected("Close concern")
        if c is None:
            return

        def save(v):
            AC.close(c.concern_id, v["day"] or None, actor=self.principal, reason=v["reason"])
            self._refresh_all()
        _form(self.parent, f"Close concern #{c.concern_id}", [
            ("day", "Closed date (blank = today)", "", None),
            ("reason", "Why (optional)", "", "text")], save)

    def delete(self) -> None:
        c = self._selected("Delete concern")
        if c is None or not messagebox.askyesno(
                "Delete concern", f"Delete concern #{c.concern_id} for {c.pupil_name} and its "
                                  "timeline?", parent=self._top()):
            return
        try:
            AC.delete(c.concern_id, actor=self.principal)
        except _ERRORS as e:
            self._err("Delete concern", e)
            return
        self._refresh_all()

    def summary(self) -> None:
        s = AC.cohort_summary(academic_year=self.ay.get().strip() or None)
        lines = [f"Total: {s['total']}   Open: {s['open']}   Pupils: {s['pupils']}",
                 "Average attendance: " + (f"{s['avg_attendance']:.2f}%"
                                           if s["avg_attendance"] is not None else "-"),
                 f"Children missing education: {s['cme']}   LA referrals: {s['referrals']}", ""]
        for key in ("by_status", "by_type", "by_level", "by_stage"):
            lines.append(key[3:].title() + ":")
            lines += [f"    {k:<42} {v}" for k, v in s[key].items()] or ["    -"]
        _text_window(self.parent, "Cohort summary", "\n".join(lines))

    # ── Timeline and notes ───────────────────────────────────────────

    def timeline(self) -> None:
        c = self._selected("Timeline")
        if c is None:
            return
        win, frm = W.dialog(self.parent, f"Timeline — #{c.concern_id} {c.pupil_name}",
                            size="820x460")
        info = (f"{c.concern_type} · {c.level} · stage {c.stage_no} {c.stage} · {c.status}"
                + (f" · target {c.target_pct:g}%" if c.target_pct else "")
                + (" · CHILD MISSING EDUCATION" if c.cme else ""))
        ttk.Label(frm, text=info, foreground="#555").pack(anchor="w")
        if c.support_plan:
            ttk.Label(frm, text=f"Support plan: {c.support_plan}", wraplength=780,
                      justify="left").pack(anchor="w")
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=6)
        tree = _tree(frm, [("date", "Date", 90), ("type", "Type", 120), ("pct", "Att%", 55),
                           ("summary", "Summary", 420), ("by", "By", 90)], height=12)
        rows: dict[str, AC.Action] = {}

        def refresh() -> None:
            tree.delete(*tree.get_children())
            rows.clear()
            for a in AC.list_actions(c.concern_id):
                rows[str(a.action_id)] = a
                tree.insert("", "end", iid=str(a.action_id), values=(
                    a.action_date, a.action_type, _pct(a.attendance_pct), a.summary,
                    a.created_by or ""))

        def add() -> None:
            self._note_form(win, c, refresh)

        def remove() -> None:
            sel = tree.selection()
            if not sel or not messagebox.askyesno("Delete entry", "Delete the selected entry?",
                                                  parent=win):
                return
            try:
                AC.delete_action(int(sel[0]), actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Delete entry", _problems(e), parent=win)
                return
            refresh()

        def view() -> None:
            sel = tree.selection()
            if sel:
                a = rows[sel[0]]
                _text_window(win, f"{a.action_type} - {a.action_date}", "\n".join(
                    f"{k}: {v}" for k, v in (("Date", a.action_date), ("Type", a.action_type),
                                             ("Summary", a.summary), ("Outcome", a.outcome),
                                             ("Attendance %", a.attendance_pct),
                                             ("Recorded by", a.created_by)) if v is not None))
        b = ttk.Button(bar, text="Add note", command=add)
        if not AC.can_add_note(self.principal, c):
            b.state(["disabled"])
        b.pack(side="left", padx=2)
        d = ttk.Button(bar, text="Delete selected", command=remove)
        if not self.editor:
            d.state(["disabled"])
        d.pack(side="left", padx=2)
        ttk.Button(bar, text="View", command=view).pack(side="left", padx=2)
        ttk.Button(bar, text="Refresh", command=refresh).pack(side="left", padx=2)
        tree.bind("<Double-1>", lambda _e: view())
        refresh()

    def _note_form(self, owner, c: AC.Concern, after: Callable[[], None]) -> None:
        def save(v):
            AC.add_note(c.concern_id, v, actor=self.principal)
            after()
        types = AC.ACTION_TYPES if self.editor else AC.NOTE_TYPES
        _form(owner, f"Note - {c.pupil_name}", [
            ("action_type", "Type", "Note", types),
            ("action_date", "Date (blank = today)", "", None),
            ("summary", "Summary (required)", "", "text"),
            ("outcome", "Outcome", "", "text")], save,
            note="Form tutors and heads of year can add notes on their pupils.")

    def add_note(self) -> None:
        c = self._selected("Add note")
        if c is None:
            return
        if not AC.can_add_note(self.principal, c):
            self._info("Add note", "Only the attendance lead or the pupil's form tutor / head "
                                   "of year can add notes.")
            return
        self._note_form(self.parent, c, self._refresh_all)

    # ── Stages, letters, reviews, the local authority ────────────────

    def next_stage(self) -> None:
        c = self._selected("Next stage")
        if c is None:
            return
        later = [s for s in AC.STAGES[c.stage_no:] if s != AC.REFERRAL]
        if not later:
            self._info("Next stage", "Use \"Refer to LA…\" for the last stage.")
            return

        def save(v):
            AC.advance_stage(c.concern_id, v["stage"], actor=self.principal,
                             day=v["day"] or None, note=v["note"],
                             meeting_date=v["meeting"] or None, support_plan=v["plan"],
                             leave_in_term_time=v["leave"])
            self._refresh_all()
        _form(self.parent, f"Next stage - #{c.concern_id} (now: {c.stage})", [
            ("stage", "Move to", later[0], later),
            ("day", "Date (blank = today)", "", None),
            ("meeting", "Meeting date (attendance meeting)", c.meeting_date or "", None),
            ("plan", "Support plan (attendance meeting)", c.support_plan or "", "text"),
            ("leave", "Leave in term time (support not needed first)", False, "check"),
            ("note", "Note", "", "text")], save,
            note="Stages: " + " → ".join(AC.STAGES) + ". Letters home move the stage on too.")

    def letter(self) -> None:
        c = self._selected("Letter home")
        if c is None:
            return

        def save(v):
            res = AC.send_letter(c.concern_id, _LETTER_LABELS[v["letter"]],
                                 actor=self.principal, note=v["note"],
                                 meeting_date=v["meeting"] or None,
                                 leave_in_term_time=v["leave"])
            self._refresh_all()
            self._deliver(res)
        _form(self.parent, f"Letter home - {c.pupil_name}", [
            ("letter", "Letter", AC.LETTERS["letter_1"][2], list(_LETTER_LABELS)),
            ("meeting", "Meeting date (meeting invitation)", c.meeting_date or "", None),
            ("leave", "Leave in term time (notice without a meeting)", False, "check"),
            ("note", "Extra message (optional)", "", "text")], save,
            note="Sent to contacts with parental responsibility through the school outbox, "
                 "with this year's attendance figures.")

    def _deliver(self, res: dict[str, Any]) -> None:
        if not res["message_id"]:
            self._info("Letter home", "No contact with parental responsibility has an e-mail "
                                      "address. Send it by post and add a note.")
            return
        text = f"{res['emails']} letter(s) prepared."
        from education_system.systems.secondary.modules.communication.gui import email_views

        def done(_report, error) -> None:
            try:
                self._info("Letter home", text + (f"\n\nQueued - delivery failed: {error}"
                                                  if error else "\n\nSent."))
            except tk.TclError:
                pass
        email_views.deliver_in_background(self.parent, res["message_id"], self.principal, done)

    def review(self) -> None:
        c = self._selected("Review")
        if c is None:
            return

        def save(v):
            r = AC.record_review(c.concern_id, actor=self.principal, summary=v["summary"],
                                 next_review_date=v["next"] or None,
                                 status=v["status"] or None, day=v["day"] or None)
            self._refresh_all()
            self._info("Review", f"Since the case opened: {_pct(r['since']) or '-'}%; this "
                                 f"year: {_pct(r['year']) or '-'}%."
                                 + ("\nTarget met." if r["met"] else "\nTarget not met yet.")
                                 + f"\nStatus: {r['concern'].status}.")
        _form(self.parent, f"Review - {c.pupil_name}", [
            ("day", "Review date (blank = today)", "", None),
            ("summary", "Summary", "", "text"),
            ("status", "Status (blank = from the target)", "", ["", *AC.CONCERN_STATUSES]),
            ("next", "Next review (blank = 4 weeks)", "", None)], save,
            note=f"Attendance since {c.opened_date} is compared with the target "
                 f"({(c.target_pct or c.threshold_pct):g}%).")

    def refer(self) -> None:
        c = self._selected("Refer to LA")
        if c is None:
            return
        t = AC.penalty_threshold(c.pupil_id)

        def save(v):
            AC.refer_to_la(c.concern_id, v["type"], actor=self.principal, day=v["day"] or None,
                           note=v["note"], leave_in_term_time=v["leave"])
            self._refresh_all()
        _form(self.parent, f"Refer to the local authority - {c.pupil_name}", [
            ("type", "Referral for", AC.REFERRAL_TYPES[0], AC.REFERRAL_TYPES),
            ("day", "Date (blank = today)", "", None),
            ("leave", "Leave in term time", False, "check"),
            ("note", "Note", "", "text")], save,
            note=f"{t['sessions']} unauthorised session(s) from {t['from']} to {t['to']} "
                 f"(threshold {AC.PENALTY_SESSIONS} in {AC.PENALTY_WEEKS} school weeks: "
                 f"{'met' if t['met'] else 'not met'}).")

    def la_outcome(self) -> None:
        c = self._selected("LA outcome")
        if c is None:
            return

        def save(v):
            AC.record_la_outcome(c.concern_id, v["outcome"], actor=self.principal,
                                 day=v["day"] or None, note=v["note"])
            self._refresh_all()
        _form(self.parent, f"LA outcome - {c.pupil_name}", [
            ("outcome", "Outcome", c.la_outcome or "", AC.LA_OUTCOMES),
            ("day", "Date (blank = today)", "", None), ("note", "Note", "", "text")], save)

    def cme(self) -> None:
        c = self._selected("Children missing education")
        if c is None:
            return
        run = AC.unexplained_run(c.pupil_id)

        def save(v):
            AC.set_cme(c.concern_id, v["flag"], actor=self.principal,
                       reported_date=v["day"] or None, notes=v["notes"])
            self._refresh_all()
        _form(self.parent, f"Children missing education - {c.pupil_name}", [
            ("flag", "Missing education", c.cme, "check"),
            ("day", "Local authority told on", c.cme_reported_date or "", None),
            ("notes", "Notes (enquiries made)", c.cme_notes or "", "text")], save,
            note=f"{run} consecutive school day(s) of unexplained absence. At "
                 f"{AC.CME_DAYS} or more, make reasonable enquiries and tell the local "
                 "authority.")

    # ── Trend, pupil, history, export ────────────────────────────────

    def trend(self) -> None:
        c = self._selected("Trend")
        if c is None:
            return
        rows = AC.weekly_trend(c.pupil_id, weeks=16)
        lines = [f"{c.pupil_name} - attendance week by week", ""]
        for w in rows:
            bar = "█" * int(w["pct"] // 5)
            lines.append(f"w/c {w['week']}  {w['pct']:5.1f}%  {bar:<20}  "
                         f"{w['attended']}/{w['possible']}"
                         + (f"  ({w['unauthorised']} unauthorised)" if w["unauthorised"]
                            else ""))
        if not rows:
            lines.append("No marks in the last 16 weeks.")
        t = AC.penalty_threshold(c.pupil_id)
        lines += ["", f"Unauthorised sessions in the last {AC.PENALTY_WEEKS} school weeks: "
                      f"{t['sessions']}" + (" - penalty-notice threshold met" if t["met"]
                                            else "")]
        _text_window(self.parent, "Trend", "\n".join(lines))

    def _open_selected(self) -> None:
        c = self._selected("Open pupil")
        if c and self.open_pupil:
            self.open_pupil(c.pupil_id)

    def history(self) -> None:
        c = self._selected("History")
        if c is None:
            return
        _text_window(self.parent, "History", "\n".join(
            f"{h['at']}  {h['actor']:<14} {h['action']:<12} "
            + ", ".join(f"{k}={v}" for k, v in h["detail"].items())
            for h in AC.history(c.concern_id)) or "No changes recorded.")

    def refresh_figures(self) -> None:
        def done(n, error) -> None:
            if not self._alive():
                return
            if error:
                self._err("Update %", error)
                return
            self.refresh()
            self._info("Update %", f"Updated {n} open case(s) from the registers.")
        _background(self.parent, lambda: AC.refresh_figures(actor=self.principal), done)

    def export(self) -> None:
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile="attendance_concerns.csv")
        if not path:
            return
        try:
            n = AC.export_csv(path, actor=self.principal, open_only=self.open_only.get(),
                              year_group=self.year.get() or None,
                              status=self.status.get() or None)
        except _ERRORS as e:
            self._err("Export", e)
            return
        self._info("Export", f"Exported {n} case(s).")

    def _goto(self, concern_id: int) -> None:
        self.book.select(self.TABS.index("Cases"))
        for v in (self.ay, self.status, self.year, self.stage, self.ctype):
            v.set("")
        self.open_only.set(False)
        self.refresh()
        if self.tree.exists(str(concern_id)):
            self.tree.selection_set(str(concern_id))
            self.tree.see(str(concern_id))

    # ── From the registers ───────────────────────────────────────────

    def _build_candidates(self, tab) -> None:
        ttk.Label(tab, text="Pupils below 90% attendance this school year (persistent) or at "
                            "50% or below (severe) with no open case.",
                  foreground="#555").pack(anchor="w")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=4)
        self.cand_year = tk.StringVar(value="")
        ttk.Label(bar, text="Year:").pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self.cand_year, values=["", *YEARS], width=4,
                          state="readonly")
        cb.pack(side="left", padx=(4, 8))
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_candidates())
        self._button(bar, "Open cases for selected", self.open_selected_cases, True)
        self._button(bar, "Open pupil", lambda: self._open_from(self.cand_tree))
        self._button(bar, "Refresh", self.refresh_candidates)
        self.cand_status = tk.StringVar()
        ttk.Label(bar, textvariable=self.cand_status, foreground="#777").pack(side="left",
                                                                              padx=8)
        self.cand_tree = _tree(tab, [("pupil", "Pupil", 220), ("year", "Yr", 40),
                                     ("form", "Form", 60), ("pct", "Att%", 60),
                                     ("auth", "Authorised", 80), ("unauth", "Unauthorised", 90),
                                     ("band", "Band", 90)], select="extended")

    def refresh_candidates(self) -> None:
        self.cand_status.set("Reading the registers…")
        year = self.cand_year.get() or None

        def done(rows, error) -> None:
            if not self._alive():
                return
            if error:
                self.cand_status.set("")
                self._err("From the registers", error)
                return
            self.cand_tree.delete(*self.cand_tree.get_children())
            for p, s in rows:
                self.cand_tree.insert("", "end", iid=str(p.pupil_id),
                                      tags=("bad",) if s.band == "severe" else ("warn",),
                                      values=(f"{p.legal_last_name}, {p.display_name.split()[0]}"
                                              f" ({p.admission_no})", p.year_group,
                                              p.form_group or "", _pct(s.attendance_pct),
                                              s.authorised, s.unauthorised, s.band))
            self.cand_status.set(f"{len(rows)} pupil(s)")
        _background(self.parent, lambda: AC.candidates(year_group=year), done)

    def open_selected_cases(self) -> None:
        sel = [int(i) for i in self.cand_tree.selection()]
        if not sel:
            self._info("Open cases", "Select pupils first (Ctrl/Shift-click for several).")
            return
        try:
            res = AC.open_from_attendance(sel, actor=self.principal)
        except _ERRORS as e:
            self._err("Open cases", e)
            return
        self.refresh_candidates()
        self._refresh_all()
        self._info("Open cases", f"Opened {len(res['created'])} case(s)."
                   + ("\n\nNot opened:\n" + "\n".join(res["skipped"]) if res["skipped"]
                      else ""))

    def _open_from(self, tree) -> None:
        sel = tree.selection()
        if sel and self.open_pupil:
            self.open_pupil(int(sel[0].split(":")[0]))

    # ── Reviews due ──────────────────────────────────────────────────

    def _build_due(self, tab) -> None:
        ttk.Label(tab, text="Open cases with a review due in the next 7 days, overdue, or "
                            "with no review date.", foreground="#555").pack(anchor="w")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=4)
        self._button(bar, "Go to case", lambda: self._goto_from(self.due_tree))
        self._button(bar, "Refresh", self.refresh_due)
        self.due_tree = _tree(tab, [("review", "Review", 90), ("flag", "", 70),
                                    ("id", "Case", 50), ("pupil", "Pupil", 220),
                                    ("stage", "Stage", 200), ("worker", "Key worker", 120)])
        self.due_tree.bind("<Double-1>", lambda _e: self._goto_from(self.due_tree))

    def refresh_due(self) -> None:
        self.due_tree.delete(*self.due_tree.get_children())
        for c in AC.due_reviews():
            self.due_tree.insert("", "end", iid=f"{c.pupil_id}:{c.concern_id}",
                                 tags=("bad",) if c.review_overdue else (),
                                 values=(c.next_review_date or "-",
                                         "OVERDUE" if c.review_overdue else "", c.concern_id,
                                         f"{c.pupil_name} ({c.admission_no})", c.stage,
                                         c.key_worker or ""))

    def _goto_from(self, tree) -> None:
        sel = tree.selection()
        if sel and ":" in sel[0]:
            self._goto(int(sel[0].split(":")[1]))

    # ── Watch: penalty threshold and CME ─────────────────────────────

    def _build_watch(self, tab) -> None:
        ttk.Label(tab, text=f"Open cases at the penalty-notice threshold ({AC.PENALTY_SESSIONS}"
                            f" unauthorised sessions in a rolling {AC.PENALTY_WEEKS} school "
                            "weeks).", font=("", 11, "bold")).pack(anchor="w")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=4)
        self._button(bar, "Go to case", lambda: self._goto_from(self.pen_tree))
        self._button(bar, "Refresh", self.refresh_watch)
        self.watch_status = tk.StringVar()
        ttk.Label(bar, textvariable=self.watch_status, foreground="#777").pack(side="left")
        self.pen_tree = _tree(tab, [("pupil", "Pupil", 240), ("sessions", "Sessions", 70),
                                    ("from", "From", 90), ("stage", "Stage", 220)], height=8)
        ttk.Label(tab, text=f"Children who may be missing education: {AC.CME_DAYS}+ consecutive "
                            "school days of unexplained absence (N / O).",
                  font=("", 11, "bold")).pack(anchor="w", pady=(10, 4))
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=4)
        self._button(bar2, "New case", self._new_for_cme, True)
        self._button(bar2, "Open pupil", lambda: self._open_from(self.cme_tree))
        self.cme_tree = _tree(tab, [("pupil", "Pupil", 240), ("days", "Days", 60),
                                    ("case", "Case", 200)], height=6)

    def refresh_watch(self) -> None:
        self.watch_status.set("Checking the registers…")

        def work():
            open_by = {c.pupil_id: c for c in AC.list_concerns(open_only=True)}
            return AC.penalty_watch(), [(p, n, open_by.get(p.pupil_id))
                                        for p, n in AC.cme_watch()]

        def done(res, error) -> None:
            if not self._alive():
                return
            self.watch_status.set("")
            if error:
                self._err("Watch", error)
                return
            pen, cme = res
            self.pen_tree.delete(*self.pen_tree.get_children())
            for c, t in pen:
                self.pen_tree.insert("", "end", iid=f"{c.pupil_id}:{c.concern_id}",
                                     values=(f"{c.pupil_name} ({c.admission_no})",
                                             t["sessions"], t["from"], c.stage))
            self.cme_tree.delete(*self.cme_tree.get_children())
            for p, n, c in cme:
                self.cme_tree.insert("", "end", iid=str(p.pupil_id), tags=("bad",),
                                     values=(f"{p.display_name} ({p.admission_no})", n,
                                             f"#{c.concern_id} {c.stage}" + (" · CME" if c.cme
                                                                              else "")
                                             if c else "no case"))
        _background(self.parent, work, done)

    def _new_for_cme(self) -> None:
        sel = self.cme_tree.selection()
        p = AC._pupil(int(sel[0])) if sel else None
        self.new(p.admission_no if p else "")

    # ── Dashboard ────────────────────────────────────────────────────

    def _build_dash(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        self.dash_by = tk.StringVar(value=self.state.get("dash_by", "Year group"))
        ttk.Label(bar, text="By:").pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self.dash_by, values=["Year group", "Form"],
                          state="readonly", width=12)
        cb.pack(side="left", padx=(4, 8))
        cb.bind("<<ComboboxSelected>>", lambda _e: self.refresh_dash())
        self._button(bar, "Refresh", self.refresh_dash)
        self.dash_status = tk.StringVar()
        ttk.Label(bar, textvariable=self.dash_status, foreground="#777").pack(side="left",
                                                                              padx=8)
        self.dash_tree = _tree(tab, [("group", "Group", 160), ("pupils", "Pupils", 70),
                                     ("pct", "Attendance %", 100),
                                     ("pa", "Persistent (<90%)", 120),
                                     ("sa", "Severe (≤50%)", 100), ("open", "Open cases", 90)])

    def refresh_dash(self) -> None:
        self.state["dash_by"] = self.dash_by.get()
        self.dash_status.set("Reading the registers…")

        def done(d, error) -> None:
            if not self._alive():
                return
            self.dash_status.set(f"School year {AC.current_year()} to date")
            if error:
                self._err("Dashboard", error)
                return
            rows = d["by_year"] if self.dash_by.get() == "Year group" else d["by_form"]
            self.dash_tree.delete(*self.dash_tree.get_children())
            for g in [*rows, d["school"]]:
                name = f"Year {g['group']}" if isinstance(g["group"], int) else g["group"]
                tag = ("bad",) if g["pct"] is not None and g["pct"] < 90 else ()
                self.dash_tree.insert("", "end", tags=tag, values=(
                    name, g["pupils"], _pct(g["pct"]), g["persistent"], g["severe"],
                    g["open"]))
        _background(self.parent, AC.dashboard, done)


def draw_attendance_concerns(parent: ttk.Frame, *, principal: Principal, state: dict,
                             open_pupil: Callable[[int], None] | None = None
                             ) -> AttendanceConcernsPage:
    return AttendanceConcernsPage(parent, principal=principal, state=state,
                                  open_pupil=open_pupil)
